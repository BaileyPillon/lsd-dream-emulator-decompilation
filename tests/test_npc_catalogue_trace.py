"""Owned callback/table fixtures for catalogue provenance and entry classification."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools import npc_catalogue_trace as tool
from tools import record_npc_history as recorder
from tools.build_npc_observer import CATALOGUE_EXPORTS, CATALOGUE_OBSERVER, OBSERVER, SOURCE_SHA256, UPSTREAM, MEDNAFEN


def fixture(complete=False):
    sizes = [2096] + [256] * 106 if complete else [8, 8]
    pcs, cursor = [], 0x80010000
    for size in sizes:
        pcs.append(cursor)
        cursor += size if complete else 32
    table_pc, records = (0x80020000, 130) if complete else (0x80010100, 2)
    payload = bytearray(table_pc - 0x80010000 + records * 16)
    for pc in pcs:
        struct.pack_into('<I', payload, pc - 0x80010000, 0x03E00008)
    struct.pack_into('<I', payload, 0, 0x0C000000 | ((pcs[1] >> 2) & 0x03FFFFFF))
    ids = {pc: [] for pc in pcs}
    for index in range(records):
        slot = index if index < len(pcs) else index - len(pcs) if complete and index < 111 else None
        pc = pcs[slot] if slot is not None else 0
        struct.pack_into('<I', payload, table_pc - 0x80010000 + index * 16 + 12, pc)
        if pc:
            ids[pc].append(index)
    header = bytearray(0x800)
    header[:8] = b'PS-X EXE'
    struct.pack_into('<II', header, 0x18, 0x80010000, len(payload))
    executable = bytes(header + payload)
    rows = []
    for index, (pc, size) in enumerate(zip(pcs, sizes)):
        at = pc - 0x80010000
        code = payload[at:at + size]
        rows.append(dict(callback='entity_owned_' + str(index), pc=f'0x{pc:08X}', entity_ids=ids[pc],
            function_bytes=size, function_sha256=tool.sha(code), entry_instruction_sha256=tool.sha(code[:4])))
    raw_table = payload[table_pc - 0x80010000:]
    value = dict(schema_version=1, kind='original_LSD_NPC_callback_catalogue',
        canonical_executable_sha256=tool.sha(executable), property_records=records,
        original_entity_table=dict(address=f'0x{table_pc:08X}', record_bytes=16, bytes=records * 16,
                                   sha256=tool.sha(raw_table)), targets=rows,
        distinct_callback_functions=len(pcs), total_callback_function_bytes=sum(sizes),
        nonnull_callback_slots=sum(map(len, ids.values())), null_callback_slots=records - sum(map(len, ids.values())))
    return executable, value


def entry(pc=0x80010000, entity_id=0, registered=0x80010000, ra=tool.DISPATCH_RETURN, tick=0, frame=1):
    return dict(relative_frame=frame, pc=pc, entity=0x80100000, ra=ra, sp=0x801FF000,
        timestamp=100, instruction=0, context_tick=tick, entity_vtable=0x80089AD4,
        entity_id=entity_id, context_state=entity_id + 1, context_owner=0x80100000, context_callback=registered)


def text_row(value):
    return {key: f'{value[key]:08X}' if key in tool.HEX_FIELDS else str(value[key]) for key in tool.CATALOGUE_FIELDS}


class CatalogueTraceTests(unittest.TestCase):
    def setUp(self):
        self.exe, self.value = fixture()
        self.targets = tool.catalogue_targets(self.value, self.exe)

    def validated(self, row):
        row = dict(row, instruction=self.targets[row['pc']]['entry_word'])
        return tool.validate_catalogue_rows([text_row(row)], self.targets, self.exe, 0, 10)[0]

    def test_original_raw_table_and_complete_code_form_the_target_set(self):
        self.assertEqual(sorted(self.targets), [0x80010000, 0x80010020])
        self.assertEqual(self.targets[0x80010000]['entity_ids'], [0])

    def test_changed_code_tail_is_not_hidden_by_a_matching_entry_word(self):
        altered = bytearray(self.exe)
        altered[0x804] ^= 1
        value = copy.deepcopy(self.value)
        value['canonical_executable_sha256'] = tool.sha(altered)
        with self.assertRaisesRegex(ValueError, 'code bytes differ'):
            tool.catalogue_targets(value, bytes(altered))

    def test_wrong_raw_binding_and_duplicate_target_are_rejected(self):
        for change in ('binding', 'duplicate'):
            value = copy.deepcopy(self.value)
            if change == 'binding':
                value['targets'][0]['entity_ids'] = [1]
            else:
                value['targets'][1]['pc'] = value['targets'][0]['pc']
            with self.subTest(change=change), self.assertRaises(ValueError):
                tool.catalogue_targets(value, self.exe)

    def test_complete_published_provenance_is_required(self):
        executable, value = fixture(complete=True)
        raw = json.dumps(value).encode()
        provenance = dict(status='verified_original_NPC_callback_catalogue', source_sha256={
            'research/headless/npc-callback-catalogue.json': tool.sha(raw)})
        self.assertEqual(len(tool.verified_catalogue(value, provenance, raw, executable)), 107)
        provenance['source_sha256']['research/headless/npc-callback-catalogue.json'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'published complete-symbol'):
            tool.verified_catalogue(value, provenance, raw, executable)

    def test_partial_catalogue_cannot_claim_the_complete_recording_mode(self):
        raw = json.dumps(self.value).encode()
        provenance = dict(status='verified_original_NPC_callback_catalogue', source_sha256={
            'research/headless/npc-callback-catalogue.json': tool.sha(raw)})
        with self.assertRaisesRegex(ValueError, 'complete original LSD catalogue'):
            tool.verified_catalogue(self.value, provenance, raw, self.exe)

    def test_original_registered_owner_and_dispatch_caller_are_required(self):
        self.assertEqual(self.validated(entry())['classification'], 'registered_dispatch')
        for field, value in (('context_owner', 0x80100004), ('context_callback', 0), ('context_state', 2)):
            row = entry()
            row[field] = value
            with self.subTest(field=field):
                self.assertEqual(self.validated(row)['classification'], 'unregistered_function_entry')

    def test_nested_callback_is_function_execution_not_another_registered_NPC(self):
        nested = self.validated(entry(pc=0x80010020, ra=0x80010008))
        self.assertEqual(nested['classification'], 'nested_callback_function_entry')
        dispatches, _ = tool.dispatch_clock_models([nested])
        self.assertEqual(dispatches, {})

    def test_caller_address_alone_does_not_create_nested_call_evidence(self):
        row = entry(pc=0x80010020, ra=0x80010028)
        self.assertEqual(self.validated(row)['classification'], 'non_dispatch_function_entry')

    def test_other_registered_entity_has_its_own_original_binding(self):
        row = entry(pc=0x80010020, entity_id=1, registered=0x80010020)
        self.assertEqual(self.validated(row)['classification'], 'registered_dispatch')

    def test_disabled_context_payload_is_not_interpreted(self):
        row = entry()
        row.update(context_state=0xFFFFFFFF, context_owner=0xFFFFFFFF,
                   context_callback=0xDEADBEEF, context_tick=0xFFFFFFFF)
        self.assertEqual(self.validated(row)['classification'], 'disabled_context_function_entry')

    def test_non_entity_function_entry_is_not_an_NPC_dispatch(self):
        row = entry()
        row.update(entity_vtable=0xDEADBEEF, entity_id=0xFFFFFFFF, context_owner=0)
        self.assertEqual(self.validated(row)['classification'], 'non_entity_function_entry')

    def test_wrong_entry_instruction_and_observation_boundaries_are_rejected(self):
        for field, value in (('instruction', 0), ('relative_frame', 11), ('timestamp', -1),
                             ('entity', 0x80100001), ('sp', 0), ('ra', 0x80010001)):
            row = entry()
            row['instruction'] = self.targets[row['pc']]['entry_word']
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                tool.validate_catalogue_rows([text_row(row)], self.targets, self.exe, 0, 10)

    def test_duplicated_events_are_rejected(self):
        row = entry()
        row['instruction'] = self.targets[row['pc']]['entry_word']
        with self.assertRaisesRegex(ValueError, 'Repeated catalogue event'):
            tool.validate_catalogue_rows([text_row(row), text_row(row)], self.targets, self.exe, 0, 10)

    def test_unknown_clock_reset_is_kept_unresolved(self):
        rows = [self.validated(entry(tick=tick, frame=index + 1)) for index, tick in enumerate((0, 1, 0))]
        _, clocks = tool.dispatch_clock_models(rows)
        self.assertFalse(next(iter(clocks.values()))['consecutive_entry_ticks'])

    def test_observer_prefix_does_not_invent_tick_zero(self):
        rows = [self.validated(entry(tick=tick, frame=index + 1)) for index, tick in enumerate((7, 8, 9))]
        _, clocks = tool.dispatch_clock_models(rows)
        clock = next(iter(clocks.values()))
        self.assertEqual(clock['first_observed_tick'], 7)
        self.assertTrue(clock['consecutive_entry_ticks'])
        self.assertEqual(clock['rooted_RAM_clock_checks'], 0)


class CatalogueProfileTests(unittest.TestCase):
    def profile(self, root):
        core = root / 'shock.wbx'
        compressed = root / 'shock.wbx.zst'
        core.write_bytes(b'owned catalogue core')
        compressed.write_bytes(b'owned compressed catalogue core')
        artifact = lambda path: dict(file=path.name, bytes=path.stat().st_size, sha256=tool.sha(path.read_bytes()))
        profile = dict(schema_version=1, status='built_separate_NPC_observer_core', observer_mode='catalogue',
            upstream_commit=UPSTREAM, mednafen_commit=MEDNAFEN,
            original_adapter_sha256=SOURCE_SHA256['shock.cpp'], existing_CPU_source_modified=False,
            input_files_preserved=True, observer_header_sha256=tool.sha(OBSERVER.read_bytes()),
            catalogue_header_sha256=tool.sha(CATALOGUE_OBSERVER.read_bytes()),
            producer_sha256=tool.sha((recorder.ROOT / 'tools/build_npc_observer.py').read_bytes()),
            exported_functions=list(CATALOGUE_EXPORTS), core=artifact(core), compressed_core=artifact(compressed))
        path = root / 'profile.json'
        path.write_text(json.dumps(profile))
        return path, profile

    def test_catalogue_profile_requires_explicit_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _ = self.profile(Path(folder))
            loaded, files = recorder.load_observer_profile(path, catalogue=True)
            self.assertEqual(loaded['observer_mode'], 'catalogue')
            self.assertEqual(len(files), 2)
            with self.assertRaisesRegex(ValueError, 'build mode differs'):
                recorder.load_observer_profile(path)

    def test_catalogue_header_and_required_exports_are_pinned(self):
        for change in ('header', 'exports'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                path, profile = self.profile(Path(folder))
                if change == 'header':
                    profile['catalogue_header_sha256'] = '0' * 64
                else:
                    profile['exported_functions'].pop()
                path.write_text(json.dumps(profile))
                with self.assertRaisesRegex(ValueError, 'catalogue observer'):
                    recorder.load_observer_profile(path, catalogue=True)

    def test_loaded_catalogue_core_must_match_its_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, _ = self.profile(root)
            (root / 'shock.wbx').write_bytes(b'changed owned core')
            with self.assertRaisesRegex(ValueError, 'artifact differs'):
                recorder.load_observer_profile(path, catalogue=True)
