"""Model construction payloads, retained residue and guarded return observation."""
import struct
from types import SimpleNamespace
import unittest

from tools.actor_factory_model import OwnershipPlan
from tools.model_payload_model import ModelPayload, ModelPayloadPlan
from tools import verify_actor_factory as factory


SYMBOLS = dict(zip(ModelPayloadPlan.VTABLES,
                   (0x8006F384, 0x8006F13C, 0x8006BEA0, 0x8006F590, 0x8006F240)))


def fixture(objects=2, animations=2):
    animation = 20 + animations * 4
    tmd = animation + 28
    raw = bytearray(tmd + 12 + objects * 28)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<II', raw, 4, len(raw), tmd)
    struct.pack_into('<I', raw, 16, animations)
    for index in range(animations):
        struct.pack_into('<I', raw, 20 + index * 4, animation - 12)
    struct.pack_into('<I', raw, animation + 4, 1)
    struct.pack_into('<H', raw, animation + 10, 2)
    struct.pack_into('<III', raw, animation + 16, 9 | 8 << 16 | 1 << 24,
                     9 | 3 << 16 | 2 << 24, 0)
    struct.pack_into('<III', raw, tmd, 0x41, 0, objects)
    return raw


def planned(raw=None, pattern='distinct', scenario='actor-first'):
    pool = factory.initial_pool(pattern)
    pool.setup()
    plan = ModelPayloadPlan(fixture() if raw is None else raw, pool, SYMBOLS, factory.DATA)
    plan.run(scenario)
    return plan


def word(payload, offset):
    return struct.unpack_from('<I', payload.expected, offset)[0]


class ModelPayloadTests(unittest.TestCase):
    def test_all_ownership_events_remain_independently_identical(self):
        for scenario in factory.SCENARIOS:
            for pattern in ('poison', 'distinct'):
                with self.subTest(scenario=scenario, pattern=pattern):
                    raw = fixture()
                    original = bytes(raw)
                    plain_pool = factory.initial_pool(pattern)
                    plain_pool.setup()
                    plain = OwnershipPlan(raw, plain_pool)
                    expected = plain.run(scenario)
                    result = planned(raw, pattern, scenario)
                    self.assertEqual(result.events, expected)
                    self.assertEqual(bytes(raw), original)
                    self.assertEqual(len(result.model_payloads), 1)
                    self.assertTrue(result.pool.blocks[0].free)

    def test_model_headers_and_linked_tables_use_planned_addresses(self):
        plan = planned()
        payloads = {item.kind: item for item in plan.model_payloads[0]}
        model = plan.models[0]
        for kind, vtable, source in (
                ('model', 'D_8006F384', factory.DATA),
                ('geometry', 'D_8006F13C', factory.DATA + plan.tmd),
                ('animation-list', 'D_8006F590', factory.DATA + 12)):
            payload = payloads[kind]
            self.assertEqual(word(payload, 0), SYMBOLS[vtable])
            self.assertEqual(word(payload, 16), source)
            for offset in (4, 8, 12, 20, 32, 40):
                self.assertEqual(word(payload, offset), 0)
            self.assertEqual(word(payload, 36), 1)
        self.assertEqual([word(payloads['model'], offset) for offset in (44, 48, 52)],
                         [model.tmd, model.parts, 1])
        self.assertEqual(word(payloads['geometry'], 44), model.primitive_table)
        self.assertEqual(struct.unpack('<3I', payloads['primitive-table'].expected),
                         (*model.primitives, 0))
        self.assertEqual(word(payloads['animation-0'], 0), SYMBOLS['D_8006F240'])
        self.assertEqual(word(payloads['animation-0'], 16), factory.DATA + 20 + plan.animations * 4)

    def test_every_primitive_has_its_own_descriptor_and_retains_unused_words(self):
        plan = planned()
        initial = factory.initial_pool('distinct')
        for index in range(2):
            payload = next(item for item in plan.model_payloads[0] if item.kind == 'primitive-' + str(index))
            descriptor = factory.DATA + plan.tmd + 12 + index * 28
            self.assertEqual([word(payload, offset) for offset in (0, 4, 8, 12, 16)],
                             [SYMBOLS['g_CLASS_FA50_VTABLE'], 0, 0, descriptor - 12, descriptor])
            begin = payload.pointer - initial.bases['pool']
            self.assertEqual(payload.expected[20:], initial.buffers['pool'][begin + 20:begin + 36])

    def test_uninitialized_file_words_preserve_each_original_residue_pattern(self):
        for pattern in ('poison', 'distinct'):
            plan = planned(pattern=pattern)
            initial = factory.initial_pool(pattern)
            for item in plan.model_payloads[0]:
                if item.kind.startswith('primitive'):
                    continue
                begin = item.pointer - initial.bases['pool']
                self.assertEqual(item.expected[24:32], initial.buffers['pool'][begin + 24:begin + 32])

    def test_minimum_allocator_capacity_and_table_terminator_are_both_checked(self):
        plan = planned(fixture(objects=0))
        table = next(item for item in plan.model_payloads[0] if item.kind == 'primitive-table')
        self.assertEqual(table.requested_bytes, 4)
        self.assertEqual(len(table.expected), 12)
        self.assertEqual(word(table, 0), 0)

    def test_invalid_symbol_or_raw_copy_address_is_rejected(self):
        for address in (-4, 1, True, 0xFFFFFFFC):
            pool = factory.initial_pool('poison')
            pool.setup()
            with self.subTest(address=address), self.assertRaises(ValueError):
                ModelPayloadPlan(fixture(), pool, SYMBOLS, address)
        for identity in (0, 3, True, 0x100000000):
            symbols = dict(SYMBOLS, D_8006F384=identity)
            pool = factory.initial_pool('poison')
            pool.setup()
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                ModelPayloadPlan(fixture(), pool, symbols, factory.DATA)

    def test_misaligned_secondary_animation_offset_is_rejected(self):
        raw = fixture()
        struct.pack_into('<I', raw, 24, 3)
        with self.assertRaisesRegex(ValueError, 'animation pointer'):
            planned(raw)

    def test_missing_vtable_identity_is_rejected(self):
        pool = factory.initial_pool('poison')
        pool.setup()
        with self.assertRaisesRegex(ValueError, 'every qualified vtable'):
            ModelPayloadPlan(fixture(), pool, {}, factory.DATA)


class FactoryReturnObserverTests(unittest.TestCase):
    def machine(self, actual=b'abcdefgh'):
        machine = object.__new__(factory.Machine)
        machine.reg = SimpleNamespace(UC_MIPS_REG_SP=1, UC_MIPS_REG_V0=2)
        registers = {1: 0x1000, 2: 0xA0000}
        machine.cpu = SimpleNamespace(reg_read=lambda register: registers[register],
                                      mem_read=lambda address, size: actual[:size])
        machine.model_payload_pending = (0x2000, 0x1000)
        machine.model_payloads = (ModelPayload('model', 0xA0000, 4, b'abcdefgh'),)
        machine.model_payload_snapshots = []
        return machine, registers

    def test_return_address_and_stack_pointer_must_both_match(self):
        machine, registers = self.machine()
        machine.finish_model_payloads(0x2004)
        self.assertFalse(machine.model_payload_snapshots)
        registers[1] = 0x1004
        machine.finish_model_payloads(0x2000)
        self.assertFalse(machine.model_payload_snapshots)
        registers[1] = 0x1000
        machine.finish_model_payloads(0x2000)
        machine.finish_model_payloads(0x2000)
        self.assertEqual(len(machine.model_payload_snapshots), 1)
        self.assertIsNone(machine.model_payload_pending)

    def test_bytes_after_requested_length_are_included_in_comparison(self):
        machine, _ = self.machine(b'abcdefgX')
        machine.finish_model_payloads(0x2000)
        row, = machine.model_payload_snapshots
        self.assertFalse(row['matched'])
        self.assertEqual((row['first_difference'], row['requested_bytes'], row['bytes_compared']), (7, 4, 8))

    def test_wrong_factory_return_pointer_is_rejected(self):
        machine, registers = self.machine()
        registers[2] += 4
        with self.assertRaisesRegex(ValueError, 'planned model'):
            machine.finish_model_payloads(0x2000)


if __name__ == '__main__':
    unittest.main()
