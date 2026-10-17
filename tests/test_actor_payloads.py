"""Owned fixtures for full factory payload arithmetic, ordering and observation."""
import struct
from types import SimpleNamespace
import unittest

from tools.actor_factory_model import OwnershipPlan
from tools.model_payload_model import ModelPayload, ModelPayloadPlan
from tools import actor_payload_model as model
from tools import verify_actor_factory as factory

SYMBOLS = dict(zip(ModelPayloadPlan.VTABLES,
    (0x8006F384, 0x8006F13C, 0x8006BEA0, 0x8006F590, 0x8006F240)))
SYMBOLS.update(g_ACTOR_VTABLE=0x8008A140, D_800878D4=0x800878D4, func_80066150=0x80066150)

def command(kind, payload=b'', flags=0, target=9):
    assert len(payload) % 4 == 0
    return struct.pack('<I', target | kind << 16 | flags << 20 | (1+len(payload)//4) << 24)+payload

def mom(extra=(), geometry=True):
    commands = [command(8)]
    if geometry:
        commands.append(command(2, struct.pack('<I', 1)))
    commands.extend(extra)
    animation = 24
    tmd = animation+16+sum(map(len, commands))
    raw = bytearray(tmd+12+28)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<II', raw, 4, len(raw), tmd)
    struct.pack_into('<II', raw, 16, 1, animation-12)
    struct.pack_into('<I', raw, animation+4, 1)
    struct.pack_into('<H', raw, animation+10, len(commands))
    raw[animation+16:tmd] = b''.join(commands)
    struct.pack_into('<III', raw, tmd, 0x41, 0, 1)
    return raw

def plan(raw=None, scenario='owned', pattern='poison'):
    raw = mom() if raw is None else raw
    pool = factory.initial_pool(pattern)
    pool.setup()
    result = model.ActorPayloadPlan(raw, pool, SYMBOLS, factory.DATA, (0,0,0), (4096,4096,4096))
    result.run(scenario)
    return result

def payload(result, kind, index=0):
    found = [row for row in result.actor_payloads[index] if row.kind == kind]
    assert len(found) == 1, (kind, found)
    return found[0]

def words(row, offset, count):
    return struct.unpack_from('<'+str(count)+'I', row.expected, offset)

class ActorPayloadTests(unittest.TestCase):
    def test_all_scenarios_preserve_exact_ownership_events_and_raw_inputs(self):
        raw = mom((command(3, struct.pack('<I', 0)),))
        before = bytes(raw)
        for scenario in factory.SCENARIOS:
            for pattern in ('poison', 'distinct'):
                with self.subTest(scenario=scenario, pattern=pattern):
                    pool = factory.initial_pool(pattern)
                    pool.setup()
                    events = OwnershipPlan(raw, pool).run(scenario)
                    actual = plan(raw, scenario, pattern)
                    self.assertEqual(actual.events, events)
                    self.assertEqual(len(actual.actor_payloads), 2 if scenario == 'actor-first' else 1)
                    self.assertFalse(actual.live)
                    self.assertEqual(len(actual.pool.blocks), 1)
                    self.assertTrue(actual.pool.blocks[0].free)
        self.assertEqual(bytes(raw), before)

    def test_actor_headers_callback_and_animation_header_are_predicted(self):
        result = plan()
        actor = payload(result, 'actor')
        self.assertEqual(words(actor, 0, 1), (SYMBOLS['g_ACTOR_VTABLE'],))
        self.assertEqual(words(actor, 16, 1), (0x80000000,))
        self.assertEqual(words(actor, 88, 4), (0, result.models[0].pointer, 1, 1))
        self.assertEqual(words(actor, 120, 7), (SYMBOLS['func_80066150'], 0, 1, 0,
            factory.DATA+32, 0, 0))
        self.assertEqual(result.actor_returns, [actor.pointer])

    def test_geometry_is_shared_by_root_and_selected_child(self):
        result = plan()
        for kind in ('actor', 'child'):
            row = payload(result, kind)
            self.assertEqual(words(row, 24, 1), (factory.DATA+result.tmd+12,))
            self.assertEqual(words(row, 32, 1), (result.models[0].primitives[0],))
        self.assertEqual(words(payload(result, 'actor'), 104, 1), (payload(result, 'child').pointer,))

    def test_parent_resets_coordinate_position_but_not_state_and_duplicate_does_not_reset(self):
        absolute = command(1, struct.pack('<3i', 123,-7,1), 8)
        parent = command(3, struct.pack('<I', 0))
        relative = command(1, struct.pack('<3i', -3,8,9), 9)
        first = plan(mom((absolute,parent)))
        self.assertEqual(words(payload(first, 'child-state'), 24, 3), (123, 0xFFFFFFF9, 1))
        self.assertEqual(words(payload(first, 'child-coordinate'), 24, 3), (0,0,0))
        second = plan(mom((absolute,parent,relative,parent)))
        self.assertEqual(words(payload(second, 'child-state'), 24, 3), (120,1,10))
        self.assertEqual(words(payload(second, 'child-coordinate'), 24, 3), (120,1,10))
        self.assertEqual(first.events, second.events)

    def test_relative_angle_uses_signed_halfword_and_c_remainder(self):
        first = command(1, struct.pack('<3i', 359,-719,360*5000), 2)
        second = command(1, struct.pack('<3i', -720,-360*4096,360*32768), 3)
        state = payload(plan(mom((first,second))), 'child-state')
        self.assertEqual(struct.unpack_from('<3h', state.expected, 16), (-2,-1,-3192))

    def test_scale_signedness_and_fixed_point_multiplication(self):
        first = command(1, struct.pack('<4h', -32768,32767,4096,1234), 4)
        second = command(1, struct.pack('<4h', 4096,-4096,2048,-1234), 5)
        state = payload(plan(mom((first,second))), 'child-state')
        self.assertEqual(struct.unpack_from('<3i', state.expected), (-32768,-32767,2048))

    def test_word_product_wraps_before_signed_division(self):
        pool = factory.initial_pool('poison')
        pool.setup()
        result = model.ActorPayloadPlan(mom(), pool, SYMBOLS, factory.DATA, (0,0,0), (4096,4096,4096))
        node = result.node(88, 'child')
        result.put(node.state, 0, 0x7FFFFFFF)
        result.motion(node, 5, struct.pack('<4h', -32768,4096,4096,0))
        self.assertEqual(result.word(node.state, 0), 8)

    def test_complete_snapshots_include_uninitialized_fields_and_minimum_tail(self):
        result = plan()
        self.assertEqual(payload(result, 'actor').expected[28:32], b'\xB7'*4)
        self.assertEqual(payload(result, 'child-state').expected[12:16], b'\xB7'*4)
        self.assertEqual(payload(result, 'child-coordinate').expected[36:68], b'\xB7'*32)
        self.assertEqual(payload(result, 'type-table').requested_bytes, 1)
        self.assertEqual(len(payload(result, 'type-table').expected), 12)
        self.assertEqual(payload(result, 'type-table').expected[0], 9)

    def test_unknown_target_command_does_not_touch_known_children(self):
        control = plan()
        changed = plan(mom((command(1, struct.pack('<3i', 1,2,3), 8, 77),)))
        # The raw MOM extent changes its descriptor pointer, so compare actual
        # motion state and coordinate bytes independently of geometry identity.
        self.assertEqual(payload(control, 'child-state').expected, payload(changed, 'child-state').expected)
        self.assertEqual(payload(control, 'child-coordinate').expected, payload(changed, 'child-coordinate').expected)

    def test_missing_geometry_and_truncated_motion_are_outside_successful_profile(self):
        with self.assertRaisesRegex(ValueError, 'without geometry'):
            plan(mom(geometry=False))
        with self.assertRaisesRegex(ValueError, 'truncated selected field'):
            plan(mom((command(1, struct.pack('<I', 0), 8),)))

    def test_invalid_actor_identity_and_default_vector_are_rejected(self):
        for identity in (0, 3, True, 0x100000000):
            pool = factory.initial_pool('poison')
            pool.setup()
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'original symbol'):
                model.ActorPayloadPlan(mom(), pool, dict(SYMBOLS, func_80066150=identity), factory.DATA,
                                       (0,0,0), (4096,4096,4096))
        pool = factory.initial_pool('poison')
        pool.setup()
        with self.assertRaisesRegex(ValueError, 'constructor defaults'):
            model.ActorPayloadPlan(mom(), pool, SYMBOLS, factory.DATA, (0,0), (4096,4096,4096))

class ActorReturnObserverTests(unittest.TestCase):
    def machine(self, actual=b'abcdefgh'):
        machine = object.__new__(factory.Machine)
        machine.reg = SimpleNamespace(UC_MIPS_REG_SP=1, UC_MIPS_REG_V0=2)
        registers = {1: 0x1000, 2: 0xA0000}
        machine.cpu = SimpleNamespace(reg_read=lambda register: registers[register],
                                      mem_read=lambda address, size: actual[:size])
        machine.actor_payload_pending = (0x2000,0x1000,0)
        machine.actor_returns = (0xA0000,)
        machine.actor_payloads = ((ModelPayload('actor',0xA0000,4,b'abcdefgh'),),)
        machine.actor_return_snapshots, machine.actor_payload_snapshots = [], []
        return machine, registers

    def test_only_the_matching_native_stack_and_return_address_trigger_snapshot(self):
        machine, registers = self.machine()
        machine.finish_actor_payloads(0x2004)
        self.assertFalse(machine.actor_payload_snapshots)
        registers[1] += 4
        machine.finish_actor_payloads(0x2000)
        self.assertFalse(machine.actor_payload_snapshots)
        registers[1] -= 4
        machine.finish_actor_payloads(0x2000)
        machine.finish_actor_payloads(0x2000)
        self.assertEqual(len(machine.actor_payload_snapshots),1)
        self.assertIsNone(machine.actor_payload_pending)

    def test_return_pointer_mismatch_is_retained_without_stopping_native_history(self):
        machine, registers = self.machine()
        registers[2] += 4
        machine.finish_actor_payloads(0x2000)
        self.assertFalse(machine.actor_return_snapshots[0]['matched'])

    def test_full_allocator_capacity_detects_a_tail_overwrite(self):
        machine, registers = self.machine(b'abcdefgX')
        machine.finish_actor_payloads(0x2000)
        row, = machine.actor_payload_snapshots
        self.assertFalse(row['matched'])
        self.assertEqual((row['first_difference'],row['requested_bytes'],row['bytes_compared']), (7,4,8))

if __name__ == '__main__':
    unittest.main()
