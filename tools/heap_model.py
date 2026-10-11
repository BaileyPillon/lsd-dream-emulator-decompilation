"""Independent interval/free-queue model of LSD's bounded pool allocation.

The model starts from a supplied manager and pool, not an OS allocation. It
retains obsolete payload/footer bytes so complete-buffer comparisons can
detect unexpected writes. Invalid ownership and overflowing requests are
outside this analysis profile, rather than newly enforced game behavior.
"""
from dataclasses import dataclass
import struct

MASK = 0x1FFFFFFF
FREE = 0x40000000
PREVIOUS_FREE = 0x80000000


@dataclass
class Block:
    offset: int
    size: int
    free: bool


class PoolModel:
    def __init__(self, buffers, bases, manager_offset, pool_offset, pool_size, segment=0):
        if (not {'manager', 'pool'} <= buffers.keys() or buffers.keys() != bases.keys()
                or any(not isinstance(base, int) or base < 0 or base + len(buffers[name]) > MASK
                       for name, base in bases.items())):
            raise ValueError('Pool model needs separate, bounded physical buffers.')
        ranges = sorted((bases[name], bases[name] + len(data)) for name, data in buffers.items())
        if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
            raise ValueError('Pool model buffers overlap.')
        if (segment not in (0, 0x80000000, 0xA0000000) or pool_size < 16
                or pool_offset < 0 or manager_offset < 0
                or pool_size % 4 or pool_offset % 4 or manager_offset % 4
                or pool_offset + pool_size + 4 > len(buffers['pool'])
                or manager_offset + 28 > len(buffers['manager'])):
            raise ValueError('Pool model layout exceeds its bounded buffers.')
        self.buffers = {name: bytearray(data) for name, data in buffers.items()}
        self.bases = dict(bases)
        self.manager_offset = manager_offset
        self.pool_offset = pool_offset
        self.pool_size = pool_size
        self.segment = segment
        self.blocks = []
        self.queue = []
        self.setup_done = False
        if (self.get('manager', manager_offset) != self.pool_pointer
                or self.get('manager', manager_offset + 4) != pool_size):
            raise ValueError('Supplied manager disagrees with its pool binding.')

    @property
    def manager_pointer(self):
        return (self.bases['manager'] + self.manager_offset) | self.segment

    @property
    def pool_pointer(self):
        return (self.bases['pool'] + self.pool_offset) | self.segment

    def put(self, name, offset, value):
        struct.pack_into('<I', self.buffers[name], offset, value & 0xFFFFFFFF)

    def get(self, name, offset):
        return struct.unpack_from('<I', self.buffers[name], offset)[0]

    def block_pointer(self, offset):
        return self.pool_pointer + offset

    def write_header(self, index):
        block = self.blocks[index]
        flags = FREE if block.free else 0
        if index and self.blocks[index - 1].free:
            flags |= PREVIOUS_FREE
        self.put('pool', self.pool_offset + block.offset, flags | block.size)

    def write_following_header(self, index):
        if index + 1 < len(self.blocks):
            self.write_header(index + 1)
        else:
            self.put('pool', self.pool_offset + self.pool_size,
                     PREVIOUS_FREE if self.blocks[index].free else 0)

    def write_queue(self):
        self.put('manager', self.manager_offset + 8,
                 self.block_pointer(self.queue[0]) if self.queue else 0)
        self.put('manager', self.manager_offset + 12,
                 self.block_pointer(self.queue[-1]) if self.queue else 0)
        for index, offset in enumerate(self.queue):
            self.put('pool', self.pool_offset + offset + 4,
                     self.block_pointer(self.queue[index + 1]) if index + 1 < len(self.queue) else 0)
            self.put('pool', self.pool_offset + offset + 8,
                     self.block_pointer(self.queue[index - 1]) if index else 0)

    def write_footer(self, block):
        self.put('pool', self.pool_offset + block.offset + block.size - 4,
                 self.block_pointer(block.offset))

    def setup(self):
        self.blocks = [Block(0, self.pool_size, True)]
        self.queue = [0]
        self.put('manager', self.manager_offset + 16, 1)
        self.write_queue()
        self.write_header(0)
        self.write_footer(self.blocks[0])
        self.write_following_header(0)
        self.setup_done = True
        self.validate()

    def require_setup(self):
        if not self.setup_done:
            raise ValueError('Set up the model pool before allocation or release.')

    def allocate(self, size):
        self.require_setup()
        if not isinstance(size, int) or not 0 <= size <= 0x10000:
            raise ValueError('Request exceeds the bounded nonoverflowing allocation profile.')
        if size == 0:
            return 0
        needed = max(12, (size + 3) & ~3) + 4
        eligible = [offset for offset in self.queue
                    if next(block.size for block in self.blocks if block.offset == offset) >= needed]
        if not eligible:
            return 0
        offset = eligible[0]
        index = next(i for i, block in enumerate(self.blocks) if block.offset == offset)
        block = self.blocks[index]
        remainder = block.size - needed
        queue_index = self.queue.index(offset)
        if remainder >= 16:
            allocated = Block(offset, needed, False)
            trailing = Block(offset + needed, remainder, True)
            self.blocks[index:index + 1] = [allocated, trailing]
            self.queue[queue_index] = trailing.offset
            self.write_header(index)
            self.write_header(index + 1)
            self.write_footer(trailing)
            self.write_following_header(index + 1)
        else:
            block.free = False
            self.queue.pop(queue_index)
            self.write_header(index)
            self.write_following_header(index)
        self.write_queue()
        self.validate()
        return self.block_pointer(offset) + 4

    def owned_block(self, pointer):
        if not isinstance(pointer, int) or not 0 <= pointer <= 0xFFFFFFFF:
            raise ValueError('Pointer exceeds the 32-bit ownership profile.')
        physical = pointer & MASK
        offset = physical - (self.pool_pointer & MASK) - 4
        matches = [block for block in self.blocks if block.offset == offset and not block.free]
        if (pointer & ~MASK) != self.segment or len(matches) != 1:
            raise ValueError('Pointer is not a live allocation owned by this model pool.')
        return matches[0]

    def free(self, pointer):
        self.require_setup()
        if pointer == 0:
            return 0
        block = self.owned_block(pointer)
        index = self.blocks.index(block)
        first = index - 1 if index and self.blocks[index - 1].free else index
        last = index + 1 if index + 1 < len(self.blocks) and self.blocks[index + 1].free else index
        # Preserve intermediate changes to a neighbour that is subsequently
        # removed: its old links become observable bytes inside the merged pool.
        for neighbour_index in (first, last):
            if neighbour_index != index:
                self.queue.remove(self.blocks[neighbour_index].offset)
                self.write_queue()
        merged = Block(self.blocks[first].offset,
                       sum(part.size for part in self.blocks[first:last + 1]), True)
        self.blocks[first:last + 1] = [merged]
        self.queue.insert(0, merged.offset)
        self.write_header(first)
        self.write_following_header(first)
        self.write_queue()
        self.write_footer(merged)
        self.validate()
        return 0

    def write_payload(self, pointer, data):
        block = self.owned_block(pointer)
        if len(data) > block.size - 4:
            raise ValueError('Synthetic payload exceeds its owned allocation.')
        start = self.pool_offset + block.offset + 4
        self.buffers['pool'][start:start + len(data)] = data

    def validate(self):
        self.require_setup()
        if not self.blocks:
            raise ValueError('Model pool has no intervals.')
        expected_manager = (self.pool_pointer, self.pool_size,
                            self.block_pointer(self.queue[0]) if self.queue else 0,
                            self.block_pointer(self.queue[-1]) if self.queue else 0, 1)
        if tuple(self.get('manager', self.manager_offset + i * 4) for i in range(5)) != expected_manager:
            raise ValueError('Model manager fields disagree with the pool and free queue.')
        cursor = 0
        free_offsets = []
        for index, block in enumerate(self.blocks):
            if block.offset != cursor or block.size < 16 or block.size % 4:
                raise ValueError('Model intervals no longer partition a valid pool.')
            if index and block.free and self.blocks[index - 1].free:
                raise ValueError('Model left adjacent free intervals uncoalesced.')
            flags = (FREE if block.free else 0) | (PREVIOUS_FREE if index and self.blocks[index - 1].free else 0)
            if self.get('pool', self.pool_offset + block.offset) != (block.size | flags):
                raise ValueError('Model block header disagrees with its abstract interval.')
            if block.free:
                free_offsets.append(block.offset)
                if self.get('pool', self.pool_offset + block.offset + block.size - 4) != self.block_pointer(block.offset):
                    raise ValueError('Model free interval has an invalid footer.')
            cursor += block.size
        if cursor != self.pool_size or len(set(self.queue)) != len(self.queue) or set(self.queue) != set(free_offsets):
            raise ValueError('Model free queue or pool extent is inconsistent.')
        for index, offset in enumerate(self.queue):
            next_pointer = self.block_pointer(self.queue[index + 1]) if index + 1 < len(self.queue) else 0
            previous_pointer = self.block_pointer(self.queue[index - 1]) if index else 0
            if (self.get('pool', self.pool_offset + offset + 4) != next_pointer
                    or self.get('pool', self.pool_offset + offset + 8) != previous_pointer):
                raise ValueError('Model free queue links disagree with its abstract order.')
        sentinel = PREVIOUS_FREE if self.blocks[-1].free else 0
        if self.get('pool', self.pool_offset + self.pool_size) != sentinel:
            raise ValueError('Model terminal header disagrees with its preceding interval.')

    def snapshot(self):
        return {name: bytes(data) for name, data in self.buffers.items()}
