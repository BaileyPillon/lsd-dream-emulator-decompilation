"""Read the pinned Nymashock 2.11.1 state layout; never change captured bytes."""
from bisect import bisect_right
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import struct
import zipfile

COMPRESSED_CORE_SHA256 = '5c6fe90fadd670318ca74993911b171e15b167c7f2e1e88bf66de4661fc24126'
ELF_CORE_SHA256 = '71f62393c291a16f1f181b18755bf12868432c6e87140b1c0980a51b36ee95bc'
BLOCK_MAGIC = b'ActivatedMemoryBlock'
HOST_END = 'ʇsoHxoqɹǝʇɐMpǝʇɐʌᴉʇɔ∀'.encode()
LIMIT = 256 * 1024 * 1024
PAGE = 4096


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decompress(data):
    try:
        from compression import zstd
        stream = zstd.ZstdFile(io.BytesIO(data), 'rb')
        decode_error = zstd.ZstdError
    except ImportError:
        try:
            import zstandard
        except ImportError as error:
            raise ValueError('Use Python 3.14 or the optional requirements-analysis.txt dependencies.') from error
        stream = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data))
        decode_error = zstandard.ZstdError
    try:
        with stream:
            result = stream.read(LIMIT + 1)
    except (decode_error, EOFError) as error:
        raise ValueError('Invalid Zstandard data: ' + str(error)) from error
    require(len(result) <= LIMIT, 'Decoded data exceeds the supported state limit.')
    return result


@dataclass(frozen=True)
class Layout:
    start: int
    size: int
    elf_size: int
    invisible: tuple


class CoreImage:
    def __init__(self, path):
        raw = Path(path).read_bytes()
        self.input_sha256 = digest(raw)
        require(self.input_sha256 in (COMPRESSED_CORE_SHA256, ELF_CORE_SHA256), 'Unsupported emulator core identity.')
        self.elf = decompress(raw) if self.input_sha256 == COMPRESSED_CORE_SHA256 else raw
        require(digest(self.elf) == ELF_CORE_SHA256, 'Decoded emulator core identity changed.')
        require(self.elf[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', self.elf, 18)[0] == 62,
                'Require the pinned little-endian x86-64 ELF.')
        phoff = struct.unpack_from('<Q', self.elf, 32)[0]
        phents, phnum = struct.unpack_from('<HH', self.elf, 54)
        headers = [struct.unpack_from('<IIQQQQQQ', self.elf, phoff + i * phents) for i in range(phnum)]
        headers = [item for item in headers if item[3]]
        start = min(item[3] for item in headers) & -PAGE
        end = (max(item[3] + item[6] for item in headers) + PAGE - 1) & -PAGE
        elf_size = end - start
        areas = {}
        for name, size in (('main_thread', 1 << 20), ('alt_thread', 1 << 20), ('sbrk', 16 << 20),
                           ('sealed', 48 << 20), ('invisible', 48 << 20), ('plain', 48 << 20), ('mmap', 48 << 20)):
            areas[name] = (end, size)
            end += size
        shoff = struct.unpack_from('<Q', self.elf, 40)[0]
        shents, shnum, names_index = struct.unpack_from('<HHH', self.elf, 58)
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', self.elf, shoff + i * shents) for i in range(shnum)]
        names = self.section_data(self.sections[names_index])
        invisible = [areas[key] for key in ('main_thread', 'alt_thread', 'invisible')]
        self.symbols = []
        for section in self.sections:
            name = self.string(names, section[0])
            if name == '.invis':
                lower = section[3] & -PAGE
                invisible.append((lower, ((section[3] + section[5] + PAGE - 1) & -PAGE) - lower))
            if section[1] != 2:
                continue
            strings = self.section_data(self.sections[section[6]])
            for at in range(section[4], section[4] + section[5], section[9]):
                name_index, _, _, _, value, size = struct.unpack_from('<IBBHQQ', self.elf, at)
                if value and name_index:
                    self.symbols.append((value, size, self.string(strings, name_index)))
        self.layout = Layout(start, end - start, elf_size, tuple(invisible))

    @staticmethod
    def string(data, at):
        return data[at:data.index(0, at)].decode()

    def section_data(self, section):
        return self.elf[section[4]:section[4] + section[5]]

    def symbol(self, name):
        found = [item for item in self.symbols if item[2] == name]
        require(len(found) == 1, 'Missing or ambiguous emulator symbol: ' + name)
        return found[0]

    def methods(self):
        result = {}
        for kind, suffix in (('c_str', '5c_strB8ne180100Ev'), ('size', '4sizeB8ne180100Ev')):
            found = [item for item in self.symbols if item[2].startswith('_ZNKSt3__112basic_stringIc')
                     and item[2].endswith(suffix)]
            require(len(found) == 1, 'Missing or ambiguous string accessor.')
            result[kind] = found[0]
        return result


class Snapshot:
    def __init__(self, payload, layout):
        require(len(payload) <= LIMIT, 'State payload exceeds the supported limit.')
        require(payload.startswith(b'ActivatedWaterboxHost_v1'), 'Unsupported Waterbox state prefix.')
        marker = payload.find(BLOCK_MAGIC)
        require(0 <= marker < 4096 and payload.find(BLOCK_MAGIC, marker + 1) < 0, 'Missing or ambiguous memory block.')
        at = marker + len(BLOCK_MAGIC) + 32
        require(at + 16 <= len(payload), 'Truncated memory-block header.')
        start, size = struct.unpack_from('<QQ', payload, at)
        require((start, size) == (layout.start, layout.size) and size % PAGE == 0, 'Memory layout differs from the pinned core.')
        count = size // PAGE
        require(at + 16 + count * 2 <= len(payload), 'Truncated page map.')
        statuses = payload[at + 16:at + 16 + count]
        dirty = payload[at + 16 + count:at + 16 + count * 2]
        require(set(statuses) <= set(range(7)) and set(dirty) <= {0, 1}, 'Unsupported page status or dirty flag.')
        cursor = at + 16 + count * 2
        self.pages = []
        for index, changed in enumerate(dirty):
            address = start + index * PAGE
            hidden = any(lower <= address < lower + length for lower, length in layout.invisible)
            if changed and not hidden:
                require(cursor + PAGE <= len(payload), 'Truncated serialized guest page.')
                self.pages.append((address, cursor))
                cursor += PAGE
        ending = payload.find(HOST_END, cursor)
        require(ending >= cursor and payload.find(HOST_END, ending + 1) < 0, 'Missing or ambiguous host end marker.')
        managed = ending + len(HOST_END)
        require(managed + 37 <= len(payload), 'Truncated managed state tail.')
        self.frame = struct.unpack_from('<I', payload, managed)[0]
        self.payload = payload
        self.block_hash = payload[marker + len(BLOCK_MAGIC):at].hex()
        self.page_offsets = [position for _, position in self.pages]
        self.page_lookup = dict(self.pages)

    @classmethod
    def from_file(cls, path, layout):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)) and 'Core.bin.zst' in names, 'Missing or duplicate core state member.')
            require(archive.getinfo('Core.bin.zst').file_size <= LIMIT, 'Compressed state exceeds the supported limit.')
            return cls(decompress(archive.read('Core.bin.zst')), layout)

    def read(self, address, size):
        require(0 <= size <= PAGE * 2, 'Unsupported guest read extent.')
        result = bytearray()
        while size:
            page = address & -PAGE
            require(page in self.page_lookup, 'Requested bytes are absent from captured guest pages.')
            length = min(size, PAGE - (address - page))
            at = self.page_lookup[page] + address - page
            result += self.payload[at:at + length]
            address += length
            size -= length
        return bytes(result)

    def word(self, address):
        require(address % 8 == 0, 'Unaligned emulator pointer.')
        return int.from_bytes(self.read(address, 8), 'little')

    def guest_address(self, offset):
        index = bisect_right(self.page_offsets, offset) - 1
        if index >= 0:
            address, position = self.pages[index]
            if position <= offset < position + PAGE:
                return address + offset - position
        return None


def short_label(snapshot, address):
    data = snapshot.read(address, 24)
    require(data[0] & 1 == 0 and data[0] >> 1 <= 22, 'Require the pinned short-string representation.')
    length = data[0] >> 1
    require(data[length + 1] == 0, 'Missing short-string terminator.')
    return data[1:length + 1]


def media_label(core, snapshot):
    info = snapshot.word(core.symbol('_ZN8Mednafen12MDFNGameInfoE')[0])
    require(info == core.symbol('EmulatedPSX')[0], 'Unexpected game-info binding.')
    owner = snapshot.word(info + 0x158)
    drives = [snapshot.word(owner + i * 8) for i in range(3)]
    types = [snapshot.word(owner + 0x18 + i * 8) for i in range(3)]
    require(drives[1] - drives[0] == 80 and drives[1] == drives[2], 'Unexpected drive vector.')
    require(types[1] - types[0] == 24 and types[1] == types[2], 'Require one media-type record.')
    require(short_label(snapshot, drives[0]) == b'Virtual CD Drive', 'Unexpected frontend drive label.')
    require(short_label(snapshot, types[0]) == b'CD', 'Unexpected frontend media label.')
    return {'game_info': info, 'rmd': owner, 'object': types[0], 'object_bytes': 24,
            'data_begin': types[0] + 1, 'length': 2, 'unused_begin': types[0] + 4, 'unused_end': types[0] + 24}


def classify(core, original, rebuilt):
    require(len(original.payload) == len(rebuilt.payload), 'Decoded state lengths differ.')
    require(original.frame == rebuilt.frame and original.block_hash == rebuilt.block_hash, 'Frame or memory-block identity differs.')
    bindings = [media_label(core, snapshot) for snapshot in (original, rebuilt)]
    require(bindings[0] == bindings[1], 'Media-label ownership differs.')
    offsets = [at for at, (a, b) in enumerate(zip(original.payload, rebuilt.payload)) if a != b]
    addresses = [original.guest_address(at) for at in offsets]
    require(addresses == [rebuilt.guest_address(at) for at in offsets], 'Serialized page mappings differ.')
    only_capacity = all(address is not None and bindings[0]['unused_begin'] <= address < bindings[0]['unused_end']
                        for address in addresses)
    return {'core_frame': original.frame, 'decoded_payloads_equal': not offsets, 'different_decoded_bytes': len(offsets),
            'all_differences_in_unused_media_label_storage': bool(offsets) and only_capacity,
            'different_guest_addresses': [hex(address) if address is not None else None for address in addresses],
            'bindings': [{key: hex(value) if key in ('game_info', 'rmd', 'object', 'data_begin', 'unused_begin', 'unused_end')
                          else value for key, value in binding.items()} for binding in bindings],
            'decoded_sha256': [digest(item.payload) for item in (original, rebuilt)], 'state_bytes_masked': 0,
            'whole_feature_groups_accepted': 0}


def execute_accessors(core, snapshot, controls=False):
    """Execute the bundled x86-64 accessor bytes in an isolated Unicorn instance."""
    try:
        import unicorn
        from unicorn.x86_const import (
            UC_X86_REG_RSP, UC_X86_REG_RDI, UC_X86_REG_RIP, UC_X86_REG_RAX,
            UC_X86_REG_RBX, UC_X86_REG_RBP, UC_X86_REG_R12, UC_X86_REG_R13, UC_X86_REG_R14, UC_X86_REG_R15,
        )
    except ImportError as error:
        raise ValueError('Install the optional requirements-analysis.txt dependencies to execute accessors.') from error
    require(unicorn.__version__ == '2.1.4', 'The accessor campaign requires the qualified Unicorn 2.1.4 backend.')
    obj = media_label(core, snapshot)['object']
    original = snapshot.read(obj, 24)
    results = []
    variants = ('baseline', 'capacity-variation', 'live-length', 'live-character') if controls else ('baseline',)
    for variant in variants:
        for kind, (entry, _, _) in core.methods().items():
            if (variant == 'live-length' and kind != 'size') or (variant == 'live-character' and kind != 'c_str'):
                continue
            uc = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_64)
            uc.mem_map(core.layout.start, core.layout.elf_size)
            for section in core.sections:
                if section[2] & 2 and section[1] != 8 and section[5]:
                    uc.mem_write(section[3], core.section_data(section))
            mapped = set(range(core.layout.start, core.layout.start + core.layout.elf_size, PAGE))
            for address, position in snapshot.pages:
                if address not in mapped:
                    uc.mem_map(address, PAGE)
                    mapped.add(address)
                uc.mem_write(address, snapshot.payload[position:position + PAGE])
            data = bytearray(original)
            if variant == 'capacity-variation':
                data[16:24] = bytes([0xa5]) * 8
            elif variant == 'live-length':
                data[0] = 6
            elif variant == 'live-character':
                data[1] = ord('X')
            uc.mem_write(obj, bytes(data))
            stack, stack_size, stop = 0x70000000, 0x10000, 0x71000000
            uc.mem_map(stack, stack_size)
            uc.mem_map(stop, PAGE)
            rsp = stack + stack_size - 8
            uc.mem_write(rsp, struct.pack('<Q', stop))
            uc.reg_write(UC_X86_REG_RSP, rsp)
            uc.reg_write(UC_X86_REG_RDI, obj)
            registers = {register: 0x123450000 + register for register in
                         (UC_X86_REG_RBX, UC_X86_REG_RBP, UC_X86_REG_R12, UC_X86_REG_R13, UC_X86_REG_R14, UC_X86_REG_R15)}
            for register, value in registers.items():
                uc.reg_write(register, value)
            reads, writes, instructions = [], [], []

            def memory(_, access, address, size, value, user):
                if access == unicorn.UC_MEM_READ:
                    reads.append((address, size))
                if access == unicorn.UC_MEM_WRITE and not (stack <= address and address + size <= stack + stack_size):
                    writes.append((address, size))

            uc.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory)
            uc.hook_add(unicorn.UC_HOOK_CODE, lambda _, address, size, user: instructions.append(address))
            try:
                uc.emu_start(entry, stop, count=5000)
            except unicorn.UcError as error:
                raise ValueError('Unmodified accessor execution failed: ' + str(error)) from error
            require(uc.reg_read(UC_X86_REG_RIP) == stop and uc.reg_read(UC_X86_REG_RSP) == rsp + 8,
                    'Accessor did not return with the expected stack.')
            require(not writes and all(uc.reg_read(register) == value for register, value in registers.items()),
                    'Accessor wrote outside the owned stack or changed saved registers.')
            require(bytes(uc.mem_read(obj, 24)) == data, 'Const accessor changed its input object.')
            require(all((stack <= address and address + size <= stack + stack_size)
                        or (obj <= address and address + size <= obj + 24) for address, size in reads),
                    'Accessor read outside the captured object and owned stack.')
            result = uc.reg_read(UC_X86_REG_RAX)
            if kind == 'size':
                expected = 3 if variant == 'live-length' else 2
                require(result == expected, 'Native string length differs.')
                observed = result
            else:
                require(result == obj + 1, 'Native string pointer differs.')
                observed = bytes(uc.mem_read(result, 3)).hex()
                require(observed == (b'XD\0' if variant == 'live-character' else b'CD\0').hex(), 'Native string content differs.')
            require(not any(address < obj + 24 and address + size > obj + 4 for address, size in reads),
                    'Accessor read unused short-string capacity.')
            results.append({'variant': variant, 'method': kind, 'instructions_executed': len(instructions),
                            'result': observed, 'reads_of_differing_capacity': 0, 'abi_preserved': True,
                            'reads_outside_object_and_stack': 0})
    return {'backend': 'Unicorn ' + unicorn.__version__, 'calls': results, 'native_instructions_modified': False,
            'scope': 'Actual bundled c_str and size paths only. Controls change private emulator input copies.'}
