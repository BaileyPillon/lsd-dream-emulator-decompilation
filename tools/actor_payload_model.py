"""Predict every live pool payload at original actor-factory return.

All state derives from original MOM bytes, fixed original
symbol/default data and the independent pool, before any native execution.
Only the successful first-animation construction profile is modeled.
"""
import struct

from tools import actor_child_model as child
from tools.model_payload_model import ModelPayloadPlan


def signed_word(value):
    return ((value & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000


class ActorPayloadPlan(ModelPayloadPlan):
    def __init__(self, raw, pool, symbols, data_address, angles, scales):
        super().__init__(raw, pool, symbols, data_address)
        self.live = {}
        self.actor_payloads = []
        self.actor_returns = []
        self.symbols = dict(symbols)
        for name in ('g_ACTOR_VTABLE', 'D_800878D4', 'func_80066150'):
            value = symbols.get(name)
            if type(value) is not int or not 0 < value <= 0xFFFFFFFC or value % 4:
                raise ValueError('Actor construction requires aligned original symbol identities.')
        if len(angles) != 3 or len(scales) != 3 or any(type(v) is not int for v in (*angles, *scales)):
            raise ValueError('Supply the independently decoded original constructor defaults.')
        self.angles, self.scales = tuple(angles), tuple(scales)
        self.animation_zero = 12 + struct.unpack_from('<I', self.raw, 20)[0]
        cursor = self.animation_zero + 16
        self.payload_commands = []
        for _ in range(struct.unpack_from('<H', self.raw, self.animation_zero+10)[0]):
            lead = struct.unpack_from('<I', self.raw, cursor)[0]
            words = lead >> 24
            if not words or cursor+words*4 > self.tmd:
                raise ValueError('The first-frame command exceeds the bounded original MOS.')
            self.payload_commands.append((lead & 255, lead >> 16 & 15, lead >> 20 & 15,
                                          self.raw[cursor+4:cursor+words*4]))
            cursor += words*4

    def allocate(self, size):
        pointer = super().allocate(size)
        self.live[pointer] = ('unclassified', size)
        return pointer

    def release(self, pointer):
        super().release(pointer)
        if pointer:
            del self.live[pointer]

    def area(self, pointer, offset, length):
        block = self.pool.owned_block(pointer)
        if offset < 0 or length < 0 or offset+length > block.size-4:
            raise ValueError('An actor field exceeds its independently owned allocation.')
        return self.pool.pool_offset+block.offset+4+offset

    def write(self, pointer, offset, data):
        start = self.area(pointer, offset, len(data))
        self.pool.buffers['pool'][start:start+len(data)] = data

    def read(self, pointer, offset, length):
        start = self.area(pointer, offset, length)
        return bytes(self.pool.buffers['pool'][start:start+length])

    def word(self, pointer, offset):
        return struct.unpack('<I', self.read(pointer, offset, 4))[0]

    def half(self, pointer, offset, value):
        self.write(pointer, offset, struct.pack('<H', value & 65535))

    def node(self, size, kind):
        node = super().node(size, kind)
        self.live[node.pointer] = (kind, size)
        self.live[node.coordinate] = (kind+'-coordinate', 80)
        self.live[node.state] = (kind+'-state', 40)
        fields = ((0, self.symbols['D_800878D4']), (4, 0), (8, 0), (12, 0),
                  (16, 0), (20, node.coordinate), (24, 0), (32, 0), (36, 0),
                  (68, 0), (76, 0), (80, 0), (84, 0))
        for offset, value in fields:
            self.put(node.pointer, offset, value)
        self.half(node.pointer, 72, 300)
        self.put(node.coordinate, 0, 1)
        self.write(node.coordinate, 4, child.SDK_MATRIX)
        self.put(node.coordinate, 68, node.state)
        self.put(node.coordinate, 72, 0)
        for axis, value in enumerate(self.scales):
            self.put(node.state, axis*4, child.signed_half(value))
        for axis, value in enumerate(self.angles):
            self.half(node.state, 16+axis*2, child.trunc_div(value, 360))
        return node

    def synchronize_links(self, node):
        for head, links in ((4, node.children), (8, node.parents)):
            self.put(node.pointer, head, links[0][0] if links else 0)
            for index, (pointer, target) in enumerate(links):
                self.live[pointer] = ('child-link' if head == 4 else 'parent-link', 8)
                self.put(pointer, 0, links[index+1][0] if index+1 < len(links) else 0)
                self.put(pointer, 4, target.pointer)

    def attach(self, parent, node):
        super().attach(parent, node)
        self.synchronize_links(parent)
        self.synchronize_links(node)

    def detach(self, parent, node):
        super().detach(parent, node)
        self.synchronize_links(parent)
        self.synchronize_links(node)

    def create_model(self):
        model = super().create_model()
        for payload in self.model_payloads[-1]:
            self.live[payload.pointer] = ('model-'+payload.kind, payload.requested_bytes)
        return model

    def bind_geometry(self, node, model, index):
        if not 0 <= index < len(model.primitives):
            raise ValueError('The original geometry selection exceeds its model.')
        self.put(node.pointer, 32, model.primitives[index])
        self.put(node.pointer, 24, self.data_address+self.tmd+12+index*28)

    def motion(self, node, flags, payload):
        cursor, relative = 0, flags & 1
        required = (12 if flags & 2 else 0)+(8 if flags & 4 else 0)+(12 if flags & 8 else 0)
        if len(payload) < required:
            raise ValueError('The original motion command has a truncated selected field.')
        if flags & 2:
            for axis, value in enumerate(struct.unpack_from('<3i', payload, cursor)):
                angle = child.trunc_div(value, 360)
                if relative:
                    current = struct.unpack('<H', self.read(node.state, 16+axis*2, 2))[0]
                    angle = child.signed_half(current+angle)
                    angle -= child.trunc_div(angle, 4096)*4096
                self.half(node.state, 16+axis*2, angle)
            cursor += 12
        if flags & 4:
            for axis, value in enumerate(struct.unpack_from('<3h', payload, cursor)):
                if relative:
                    value = child.trunc_div(signed_word(value*signed_word(self.word(node.state, axis*4))), 4096)
                self.put(node.state, axis*4, value)
            cursor += 8
        if flags & 8:
            for axis, value in enumerate(struct.unpack_from('<3i', payload, cursor)):
                if relative:
                    value += self.word(node.state, 24+axis*4)
                self.put(node.state, 24+axis*4, value)
            self.write(node.coordinate, 24, self.read(node.state, 24, 12))

    def create_actor(self, model=None):
        actor = self.node(152, 'actor')
        self.put(actor.pointer, 0, self.symbols['g_ACTOR_VTABLE'])
        for offset in (88, 92, 104, 112, 148):
            self.put(actor.pointer, offset, 0)
        actor.owns_model = model is None
        actor.model = self.create_model() if model is None else model
        self.put(actor.pointer, 92, actor.model.pointer)
        self.put(actor.pointer, 96, int(actor.owns_model))
        count = len(self.types)
        actor.child_table, actor.types = self.allocate(count*4), self.allocate(count)
        self.live[actor.child_table], self.live[actor.types] = ('child-table', count*4), ('type-table', count)
        type_bytes, selected = child.enumerate_types(self.frame.records, self.read(actor.types, 0, count))
        if type_bytes != self.types:
            raise ValueError('The actual independent residue changes the successful type enumeration.')
        self.write(actor.types, 0, type_bytes)
        actor.nodes = [self.node(88, 'child') for _ in range(count)]
        for index, node in enumerate(actor.nodes):
            self.put(actor.child_table, index*4, node.pointer)
        for offset, value in ((104, actor.nodes[selected].pointer), (108, count),
                              (112, actor.child_table), (116, actor.types)):
            self.put(actor.pointer, offset, value)
        self.attach(actor, actor.model)
        for offset, value in ((16, 0x80000000), (100, 1), (140, 0),
                              (120, self.symbols['func_80066150']), (144, 0), (124, 0),
                              (128, struct.unpack_from('<I', self.raw, self.animation_zero+4)[0]),
                              (136, self.data_address+self.animation_zero+8), (132, 0)):
            self.put(actor.pointer, offset, value)
        for type_id, kind, flags, payload in self.payload_commands:
            if type_id not in self.types:
                continue
            node = actor.nodes[self.types.index(type_id)]
            self.put(node.coordinate, 0, 0)
            if kind == 0:
                if len(payload) < 8:
                    raise ValueError('An attribute command has a truncated mask.')
                mask, value = struct.unpack_from('<II', payload)
                self.put(node.pointer, 16, (self.word(node.pointer, 16) & mask) | value)
            elif kind == 1:
                self.motion(node, flags, payload)
            elif kind == 2:
                selection = struct.unpack_from('<H', payload)[0]
                if selection and not self.word(node.pointer, 32):
                    self.bind_geometry(node, actor.model, selection-1)
            elif kind == 3 and node.coordinate_parent is None:
                parent_id = struct.unpack_from('<I', payload)[0]
                if parent_id in (0, 0xFFFF):
                    parent = actor
                elif (parent_id & 255) in self.types:
                    parent = actor.nodes[self.types.index(parent_id & 255)]
                else:
                    raise ValueError('A coordinate parent references an absent child.')
                ancestor = parent
                while ancestor is not None:
                    if ancestor is node:
                        raise ValueError('A coordinate parent cycle exceeds this successful profile.')
                    ancestor = ancestor.coordinate_parent
                node.coordinate_parent = parent
                self.put(node.pointer, 12, parent.pointer)
                self.put(node.coordinate, 72, parent.coordinate)
                self.attach(parent, node)
                self.write(node.coordinate, 24, bytes(12))
        primitive = self.word(actor.nodes[selected].pointer, 32)
        if not primitive:
            raise ValueError('A selected child without geometry exceeds the successful actor profile.')
        self.bind_geometry(actor, actor.model, actor.model.primitives.index(primitive))
        if any(kind == 'unclassified' for kind, size in self.live.values()):
            raise ValueError('A live factory allocation lacks a semantic classification.')
        self.actor_payloads.append(tuple(self.snapshot(kind, pointer, size)
            for pointer, (kind, size) in sorted(self.live.items())))
        self.actor_returns.append(actor.pointer)
        return actor

    def clear_parent(self, node):
        self.put(node.pointer, 12, 0)
        self.put(node.coordinate, 72, 0)

    def transform_cleanup(self, node):
        if node.coordinate_parent is not None:
            self.detach(node.coordinate_parent, node)
            node.coordinate_parent = None
            self.clear_parent(node)
        for _, target in list(node.children):
            if target.coordinate_parent is node:
                self.detach(node, target)
                target.coordinate_parent = None
                self.clear_parent(target)
        self.put(node.pointer, 24, 0)
        self.put(node.pointer, 32, 0)
        self.release(node.state)
        self.release(node.coordinate)
        self.base_cleanup(node)

    def destroy_actor(self, actor):
        count = len(actor.nodes)
        for index, node in enumerate(actor.nodes):
            self.put(actor.pointer, 108, count-index-1)
            self.transform_cleanup(node)
            self.release(node.pointer)
        self.put(actor.pointer, 108, 0xFFFFFFFF)
        self.put(actor.pointer, 104, 0)
        self.release(actor.types)
        self.put(actor.pointer, 116, 0)
        self.release(actor.child_table)
        self.put(actor.pointer, 112, 0)
        if actor.owns_model:
            self.destroy_model(actor.model)
        self.put(actor.pointer, 92, 0)
        self.transform_cleanup(actor)
        self.release(actor.pointer)
