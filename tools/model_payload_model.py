"""Predict complete model allocations at successful factory return.

Inputs are original MOM bytes, fixed symbol identities and an independent pool.
Native fields, allocation observations and execution traces are never inputs.
This models construction before actor attachment or first-frame interpretation.
"""
from dataclasses import dataclass
import struct

from tools.actor_factory_model import OwnershipPlan


@dataclass(frozen=True)
class ModelPayload:
    kind: str
    pointer: int
    requested_bytes: int
    expected: bytes


class ModelPayloadPlan(OwnershipPlan):
    VTABLES = ('D_8006F384', 'D_8006F13C', 'g_CLASS_FA50_VTABLE',
               'D_8006F590', 'D_8006F240')

    def __init__(self, raw, pool, symbols, data_address):
        super().__init__(raw, pool)
        if any(name not in symbols for name in self.VTABLES):
            raise ValueError('Model construction requires every qualified vtable identity.')
        self.vtables = {name: symbols[name] for name in self.VTABLES}
        if any(type(value) is not int or not 0 < value <= 0xFFFFFFFC or value % 4
               for value in self.vtables.values()):
            raise ValueError('Model vtable identities must be aligned 32-bit pointers.')
        if (type(data_address) is not int or data_address < 0 or data_address % 4
                or data_address + len(raw) > 0x100000000):
            raise ValueError('Use a bounded aligned original MOM address.')
        self.data_address = data_address
        self.model_payloads = []

    def put(self, pointer, offset, value):
        block = self.pool.owned_block(pointer)
        if offset < 0 or offset % 4 or offset + 4 > block.size - 4:
            raise ValueError('A model field exceeds its owned allocation.')
        self.pool.put('pool', self.pool.pool_offset + block.offset + 4 + offset, value)

    def file_header(self, pointer, vtable, source):
        # Base lists, file state, supplied data pointer and zero file size.
        # The native constructor leaves words 0x18 and 0x1c untouched.
        for offset, value in ((0, vtable), (4, 0), (8, 0), (12, 0),
                              (16, source), (20, 0), (32, 0), (36, 1), (40, 0)):
            self.put(pointer, offset, value)

    def snapshot(self, kind, pointer, requested_bytes):
        block = self.pool.owned_block(pointer)
        if not 0 < requested_bytes <= block.size - 4:
            raise ValueError('The model payload does not fit its planned allocation.')
        begin = self.pool.pool_offset + block.offset + 4
        return ModelPayload(kind, pointer, requested_bytes,
                            bytes(self.pool.buffers['pool'][begin:begin + block.size - 4]))

    def create_model(self):
        model = super().create_model()
        data, tmd = self.data_address, self.data_address + self.tmd
        self.file_header(model.pointer, self.vtables['D_8006F384'], data)
        self.put(model.pointer, 44, model.tmd)
        self.put(model.pointer, 48, model.parts)
        self.put(model.pointer, 52, 1)
        self.file_header(model.tmd, self.vtables['D_8006F13C'], tmd)
        self.put(model.tmd, 44, model.primitive_table)
        for index, pointer in enumerate(model.primitives):
            self.put(model.primitive_table, index * 4, pointer)
            descriptor = tmd + 12 + index * 28
            for offset, value in ((0, self.vtables['g_CLASS_FA50_VTABLE']),
                                  (4, 0), (8, 0), (12, descriptor - 12),
                                  (16, descriptor)):
                self.put(pointer, offset, value)
        self.put(model.primitive_table, len(model.primitives) * 4, 0)
        self.file_header(model.parts, self.vtables['D_8006F590'], data + 12)
        for index, pointer in enumerate(model.animations):
            offset = struct.unpack_from('<I', self.raw, 20 + 4 * index)[0]
            if offset % 4 or not 20 + self.animations * 4 <= 12 + offset <= self.tmd - 8:
                raise ValueError('A model animation pointer exceeds the original MOS extent.')
            self.file_header(pointer, self.vtables['D_8006F240'], data + 12 + offset)
        allocations = [('model', model.pointer, 56), ('geometry', model.tmd, 48),
                       ('primitive-table', model.primitive_table, (self.objects + 1) * 4)]
        allocations.extend(('primitive-' + str(index), pointer, 36)
                           for index, pointer in enumerate(model.primitives))
        allocations.append(('animation-list', model.parts, 44))
        allocations.extend(('animation-' + str(index), pointer, 44)
                           for index, pointer in enumerate(model.animations))
        self.model_payloads.append(tuple(self.snapshot(*allocation) for allocation in allocations))
        return model
