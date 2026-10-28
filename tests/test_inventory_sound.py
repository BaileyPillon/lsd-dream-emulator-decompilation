import contextlib
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

from tools import inventory_sound as sound
from research.sound_assets import native_profile
from research.sound_assets import qualify_disc


def bank():
    """Two programs, IDs 0 and 9, with two independently bounded samples."""
    head = bytearray(3616)
    head[:4] = b'pBAV'
    struct.pack_into('<I', head, 4, 7)
    struct.pack_into('<I', head, 12, 3616 + 64)
    struct.pack_into('<4H', head, 16, 0xEEEE, 2, 2, 2)
    head[24:26] = bytes((127, 64))
    for dense, native in enumerate((0, 9)):
        at = 32 + native * 16
        head[at:at + 8] = bytes((1, 127, 64, 0, 64, 0, 0x34, 0x12))
        head[at + 8:at + 16] = b'\xff' * 8
        at = 2080 + dense * 512
        head[at:at + 14] = bytes((64, 4, 100, 64, 60, 0, 0, 127, 0, 0, 0, 0, 2, 2))
        struct.pack_into('<4H', head, at + 16, 0x80ff, 0x5f00, native, dense + 1)
    struct.pack_into('<3H', head, 3104, 0, 4, 4)
    body = bytearray(64)
    body[0:2] = bytes((12, 6))
    body[16:18] = bytes((12, 3))
    body[32:34] = bytes((12, 4))
    body[48:50] = bytes((12, 1))
    return bytes(head), bytes(body)


def seq(events=None, tempo=500000, rhythm=4):
    header = b'pQES' + struct.pack('>IH', 1, 480) + tempo.to_bytes(3, 'big') + bytes((rhythm, 2))
    if events is None:
        events = (b'\x00\x90\x3c\x64'  # Initial program intentionally unknown.
                  b'\x00\xc0\x09'
                  b'\x81\x00\x90\x40\x7f'
                  b'\x00\x41\x64'
                  b'\x01\x40\x00'
                  b'\x00\xff\x2f\x00')
    return header + events


def layout(root, header=None, body=None, sequence=None, reopen=False):
    header, body = bank() if header is None else (header, body)
    (root / 'BANK.VH').write_bytes(header)
    (root / 'BANK.VB').write_bytes(body)
    (root / 'BGA.SEQ').write_bytes(seq() if sequence is None else sequence)
    files = ('<file name="BANK.VH" source="BANK.VH"/>'
             '<file name="BANK.VB" source="BANK.VB"/>'
             '<file name="BGA.SEQ" source="BGA.SEQ"/>')
    content = ('<dir name="FILM" source="unused-directory"/><dir name="FILM">' + files + '</dir>') if reopen else files
    path = root / 'disc.xml'
    path.write_text('<iso_project><track><directory_tree>' + content + '</directory_tree></track></iso_project>')
    return path


def raw_disc(root, extra_audio=False):
    """A complete small Mode 2 track with independently encoded ISO records."""
    xml = layout(root)
    text = xml.read_text()
    for name, lba in (('BANK.VH', 21), ('BANK.VB', 23), ('BGA.SEQ', 24)):
        text = text.replace('name="' + name + '"', 'name="' + name + '" offs="' + str(lba) + '"')
    xml.write_text(text)
    track = bytearray(32 * 2352)
    for lba in range(32):
        offset = lba * 2352
        absolute = lba + 150
        parts = (absolute // 4500, absolute // 75 % 60, absolute % 75)
        track[offset:offset + 12] = b'\0' + b'\xff' * 10 + b'\0'
        track[offset + 12:offset + 16] = bytes((n // 10) * 16 + n % 10 for n in parts) + b'\x02'

    def put(lba, data):
        for index in range(0, len(data), 2048):
            offset = (lba + index // 2048) * 2352 + 24
            track[offset:offset + len(data[index:index + 2048])] = data[index:index + 2048]

    def record(name, lba, length, directory=False):
        size = 33 + len(name)
        size += size % 2
        value = bytearray(size)
        value[0], value[25], value[32] = size, 2 if directory else 0, len(name)
        struct.pack_into('<I', value, 2, lba)
        struct.pack_into('>I', value, 6, lba)
        struct.pack_into('<I', value, 10, length)
        struct.pack_into('>I', value, 14, length)
        value[28:32] = b'\x01\0\0\x01'
        value[33:33 + len(name)] = name
        return value

    volume = bytearray(2048)
    volume[:7] = b'\x01CD001\x01'
    volume[128:132] = b'\0\x08\x08\0'
    volume[156:190] = record(b'\0', 18, 2048, True)
    directory = record(b'\0', 18, 2048, True) + record(b'\x01', 18, 2048, True)
    for name, lba in (('BANK.VH', 21), ('BANK.VB', 23), ('BGA.SEQ', 24)):
        payload = (root / name).read_bytes()
        directory.extend(record((name + ';1').encode(), lba, len(payload)))
        put(lba, payload)
    if extra_audio:
        directory.extend(record(b'MORE.SEQ;1', 25, len(seq())))
        put(25, seq())
    put(16, volume)
    put(18, directory)
    path = root / 'disc.bin'
    path.write_bytes(track)
    return xml, path


class SoundInventoryTests(unittest.TestCase):
    def test_sparse_native_ids_use_dense_tone_storage(self):
        head, body = bank()
        result = sound.vab_info(head, body)
        self.assertEqual(result['native_program_ids'], [0, 9])
        self.assertEqual([p['dense_tone_block'] for p in result['programs']], [0, 1])
        self.assertEqual(result['programs'][1]['tones'][0]['header_offset'], 2592)
        self.assertEqual(result['programs'][1]['tones'][0]['VAG_id'], 2)
        self.assertEqual(result['active_program_ids_outside_count_prefix'], [9])
        self.assertEqual(result['unused_tone_slots'], 30)
        self.assertFalse(result['SPU_transfer_verified'])
        self.assertFalse(result['audible_playback_verified'])

    def test_sample_lengths_are_eight_byte_units_and_flags_are_not_duration(self):
        result = sound.vab_info(*bank())
        self.assertEqual([(s['body_offset'], s['bytes'], s['ADPCM_blocks']) for s in result['samples']],
                         [(0, 32, 2), (32, 32, 2)])
        self.assertEqual([s['first_end_repeats'] for s in result['samples']], [True, False])
        self.assertEqual(result['samples'][0]['loop_start_blocks'], [0])

    def test_unreviewed_header_magic_version_and_extents_are_rejected(self):
        head, body = bank()
        for offset, value in ((0, b'BAD!'), (4, struct.pack('<I', 5)), (12, struct.pack('<I', 1))):
            changed = bytearray(head)
            changed[offset:offset + len(value)] = value
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                sound.vab_info(bytes(changed), body)
        for changed in (head[:-1], head + b'\x00'):
            with self.assertRaises(ValueError):
                sound.vab_info(changed, body)

    def test_header_population_is_not_maximum_native_id(self):
        head, body = bank()
        for offset, value in ((18, 1), (20, 3), (22, 3)):
            changed = bytearray(head)
            struct.pack_into('<H', changed, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                sound.vab_info(bytes(changed), body)

    def test_tone_owner_and_sample_reference_are_checked(self):
        head, body = bank()
        for offset, value in ((2592 + 20, 1), (2592 + 22, 0), (2592 + 22, 3)):
            changed = bytearray(head)
            struct.pack_into('<H', changed, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                sound.vab_info(bytes(changed), body)

    def test_inactive_attributes_remain_opaque_but_active_ranges_are_checked(self):
        head, body = bank()
        changed = bytearray(head)
        changed[32 + 16 + 1:32 + 32] = b'\xff' * 15
        self.assertEqual(sound.vab_info(bytes(changed), body)['declared_programs'], 2)
        changed[32 + 1] = 128
        with self.assertRaises(ValueError):
            sound.vab_info(bytes(changed), body)
        changed = bytearray(head)
        changed[2080 + 6:2080 + 8] = bytes((80, 79))
        with self.assertRaises(ValueError):
            sound.vab_info(bytes(changed), body)

    def test_undeclared_or_reserved_sample_length_is_not_ignored(self):
        head, body = bank()
        for offset in (3104, 3104 + 3 * 2):
            changed = bytearray(head)
            struct.pack_into('<H', changed, offset, 2)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                sound.vab_info(bytes(changed), body)

    def test_sample_alignment_filter_shift_and_end_flag_are_checked(self):
        head, body = bank()
        for offset, value in ((0, 0x5c), (0, 0x0d), (1, 8)):
            changed = bytearray(body)
            changed[offset] = value
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                sound.vab_info(head, bytes(changed))
        changed = bytearray(body)
        changed[1] = changed[17] = 0
        with self.assertRaises(ValueError):
            sound.vab_info(head, bytes(changed))
        changed_head = bytearray(head)
        struct.pack_into('<2H', changed_head, 3106, 3, 5)
        with self.assertRaises(ValueError):
            sound.vab_info(bytes(changed_head), body)

    def test_sequence_running_status_and_unknown_initial_program_are_preserved(self):
        result = sound.seq_info(seq())
        self.assertEqual(result['encoded_tick_span'], 129)
        self.assertEqual(result['events'], 6)
        self.assertEqual(result['event_kinds'], dict(end_of_track=1, note_off=1, note_on=3, program_change=1))
        self.assertEqual(result['running_status_events'], 2)
        self.assertEqual(result['known_program_note_keys'], {'9': [64, 65]})
        self.assertEqual(result['note_ons_before_first_channel_program_change'], 1)
        self.assertFalse(result['initial_channel_programs_assumed'])
        self.assertFalse(result['encoded_ticks_are_playback_duration'])

    def test_original_zero_tempo_and_rhythm_are_retained_without_repair(self):
        data = seq(tempo=0, rhythm=0)
        result = sound.seq_info(data)
        self.assertEqual(result['initial_tempo_word'], 0)
        self.assertEqual(result['rhythm_numerator'], 0)
        self.assertTrue(result['zero_initial_tempo_word'])
        self.assertTrue(result['zero_rhythm_numerator'])
        self.assertFalse(result['zero_header_words_replaced'])
        self.assertFalse(result['native_header_semantics_verified'])
        self.assertEqual(result['raw_sha256'], sound.sha(data))

    def test_truncated_running_status_overlong_delta_and_status_in_data_fail(self):
        bad = [b'\x00\x40\x01', b'\x81\x80\x80\x80\x00\x90\x40\x01',
               b'\x00\x90\x40', b'\x00\x90\x40\x90']
        for events in bad:
            with self.subTest(events=events.hex()), self.assertRaises(ValueError):
                sound.seq_info(seq(events=events))

    def test_channel_message_widths_and_controller_numbers_are_separate(self):
        data = seq(events=(b'\x00\xb1\x63\x14\x00\xa2\x40\x20'
                           b'\x00\xd2\x18\x00\xe3\x00\x40\x00\xff\x2f\x00'))
        result = sound.seq_info(data)
        self.assertEqual(result['controllers'], {99: 1})
        self.assertEqual(result['event_kinds'], dict(channel_pressure=1, control_change=1,
                                                    end_of_track=1, pitch_bend=1, poly_pressure=1))

    def test_unreviewed_meta_system_event_and_trailing_bytes_are_not_skipped(self):
        for events in (b'\x00\xff\x51\x03\x07\xa1\x20', b'\x00\xf0\x00',
                       b'\x00\xff\x2f\x01\x00', b'\x00\xff\x2f\x00\x00'):
            with self.subTest(events=events.hex()), self.assertRaises(ValueError):
                sound.seq_info(seq(events=events))

    def test_sequence_header_magic_version_resolution_and_rhythm_bound(self):
        original = seq()
        for offset, value in ((0, b'nope'), (4, struct.pack('>I', 2)), (8, b'\x00\x00'), (14, b'\x08')):
            changed = bytearray(original)
            changed[offset:offset + len(value)] = value
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                sound.seq_info(bytes(changed))

    def test_reopened_layout_directory_keeps_unique_audio_payload_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            report = sound.collect(layout(Path(temp), reopen=True), 'fixture')
            self.assertEqual(report['totals']['layout_audio_files'], 3)
            self.assertEqual(report['totals']['parsed_banks'], 1)
            self.assertEqual(report['totals']['parsed_sequences'], 1)
            self.assertEqual(report['whole_feature_groups_accepted'], 0)
            self.assertFalse(report['SPU_transfer_verified'])
            self.assertFalse(report['audible_playback_verified'])

    def test_duplicate_file_and_directory_metadata_override_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = layout(root)
            text = path.read_text()
            path.write_text(text.replace('</directory_tree>', '<file name="BGA.SEQ" source="BGA.SEQ"/></directory_tree>'))
            with self.assertRaises(ValueError):
                sound.collect(path)
            path.write_text('<iso_project><track><directory_tree><dir name="X"/><dir name="X" source="Y"/>'
                            '<file name="BGA.SEQ" source="BGA.SEQ"/></directory_tree></track></iso_project>')
            with self.assertRaises(ValueError):
                sound.collect(path)

    def test_source_escape_and_empty_layout_do_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'outer.SEQ').write_bytes(seq())
            sub = root / 'sub'
            sub.mkdir()
            path = sub / 'disc.xml'
            path.write_text('<iso_project><track><directory_tree><file name="A.SEQ" source="../outer.SEQ"/>'
                            '</directory_tree></track></iso_project>')
            with self.assertRaises(ValueError):
                sound.collect(path)
            path.write_text('<iso_project><track><directory_tree/></track></iso_project>')
            with self.assertRaises(ValueError):
                sound.collect(path)

    def test_missing_pair_is_reported_with_original_header_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = layout(root)
            text = path.read_text().replace('<file name="BANK.VB" source="BANK.VB"/>', '')
            path.write_text(text)
            result = sound.collect(path)
            self.assertEqual(result['totals']['unresolved_files'], 1)
            self.assertEqual(result['inputs']['/BANK.VH']['sha256'], sound.sha(bank()[0]))

    def test_orphan_body_is_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = layout(root)
            path.write_text(path.read_text().replace('<file name="BANK.VH" source="BANK.VH"/>', ''))
            result = sound.collect(path)
            self.assertEqual(result['totals']['unresolved_files'], 1)
            self.assertIn('/BANK.VB', result['inputs'])

    def test_zero_tempo_requires_review_without_hiding_structural_success(self):
        with tempfile.TemporaryDirectory() as temp:
            result = sound.collect(layout(Path(temp), sequence=seq(tempo=0, rhythm=0)))
            self.assertEqual(result['totals']['parsed_sequences'], 1)
            self.assertEqual(result['totals']['unresolved_files'], 0)
            self.assertEqual(result['totals']['native_header_review_sequences'], 1)
            self.assertEqual(result['native_header_review'][0]['path'], '/BGA.SEQ')

    def test_cli_existing_report_is_preserved_and_zero_tempo_returns_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = layout(root, sequence=seq(tempo=0))
            report = root / 'report.json'
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = sound.main(['--layout', str(path), '--output', str(report)])
                old = report.read_bytes()
                again = sound.main(['--layout', str(path), '--output', str(report)])
            self.assertEqual(code, 1)
            self.assertEqual(again, 2)
            self.assertEqual(report.read_bytes(), old)

    def test_cli_positive_structure_has_zero_exit_but_no_playback_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = layout(root)
            report = root / 'report.json'
            with contextlib.redirect_stdout(io.StringIO()):
                code = sound.main(['--layout', str(path), '--output', str(report)])
            self.assertEqual(code, 0)
            value = json.loads(report.read_text())
            self.assertFalse(value['audible_playback_verified'])
            self.assertEqual(value['whole_feature_groups_accepted'], 0)

    def test_runtime_header_model_reproduces_exact_sparse_ids_and_sample_ends(self):
        head, body = bank()
        result = native_profile.runtime_header(head, 0x1010)
        self.assertEqual(struct.unpack_from('<I', result, 32 + 9 * 16 + 8)[0], 1)
        self.assertEqual(struct.unpack_from('<I', result, 32 + 8 * 16 + 8)[0], 1)
        self.assertEqual(struct.unpack_from('<2H', result, 32 + 12), (0x202, 0x206))
        self.assertEqual(struct.unpack_from('<H', result, 32 + 16 + 12)[0], 0x20a)
        self.assertEqual(result[2080:], head[2080:])

    def test_pending_and_closed_ram_payloads_are_not_ready_bindings(self):
        head, body = bank()
        raw = bytearray(2**21)
        raw[native_profile.USED] = 2
        struct.pack_into('<I', raw, native_profile.HEADERS, 0xffffffff)
        with self.assertRaises(ValueError):
            native_profile.ready_bindings(bytes(raw), {'BANK': (head, body)})

    def test_ready_binding_checks_every_header_byte_and_registry_pointer(self):
        head, body = bank()
        raw = bytearray(2**21)
        address, base = 0x80110000, 0x1010
        raw[native_profile.USED] = 1
        for table, value in ((native_profile.HEADERS, address), (native_profile.PROGRAM_TABLES, address + 32),
                             (native_profile.TONE_TABLES, address + 2080), (native_profile.SPU_BASES, base),
                             (native_profile.SPU_LENGTHS, len(body))):
            struct.pack_into('<I', raw, table, value)
        raw[0x110000:0x110000 + len(head)] = native_profile.runtime_header(head, base)
        self.assertEqual(native_profile.ready_bindings(bytes(raw), {'BANK': (head, body)})[0]['bank_id'], 0)
        for offset in (0x110000 + 3103, native_profile.TONE_TABLES):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                native_profile.ready_bindings(bytes(changed), {'BANK': (head, body)})

    def test_runtime_sample_end_uses_the_original_sixteen_bit_write(self):
        head, _ = bank()
        result = native_profile.runtime_header(head, 0x7ffc0)
        self.assertEqual(struct.unpack_from('<H', result, 32 + 16 + 12)[0], 0)

    def test_complete_raw_ram_hash_is_required_without_creating_outputs(self):
        raw = b'R' * 2**21
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'ram.bin'
            path.write_bytes(raw)
            self.assertEqual(native_profile.read_ram(path, sound.sha(raw)), raw)
            with self.assertRaises(ValueError):
                native_profile.read_ram(path, '0' * 64)
            self.assertEqual(list(Path(temp).iterdir()), [path])

    def test_one_exact_archived_ram_member_is_read_without_extraction(self):
        raw = b'R' * 2**21
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'ram.tar.xz'
            with tarfile.open(path, 'w:xz') as archive:
                member = tarfile.TarInfo('payloads/ram.bin')
                member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))
            self.assertEqual(native_profile.read_ram(path, sound.sha(raw), 'payloads/ram.bin',
                                                    sound.sha(path.read_bytes())), raw)
            self.assertEqual(list(Path(temp).iterdir()), [path])

    def test_archive_hash_and_missing_exact_member_are_rejected(self):
        raw = b'R' * 2**21
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'ram.tar.xz'
            with tarfile.open(path, 'w:xz') as archive:
                member = tarfile.TarInfo('ram.bin')
                member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))
            with self.assertRaises(ValueError):
                native_profile.read_ram(path, sound.sha(raw), 'ram.bin', '0' * 64)
            with self.assertRaises(ValueError):
                native_profile.read_ram(path, sound.sha(raw), 'other.bin', sound.sha(path.read_bytes()))

    def test_duplicate_link_and_incomplete_ram_members_are_rejected(self):
        raw = b'R' * 2**21
        with tempfile.TemporaryDirectory() as temp:
            for kind in ('duplicate', 'symlink', 'short'):
                path = Path(temp) / (kind + '.tar.xz')
                with tarfile.open(path, 'w:xz') as archive:
                    member = tarfile.TarInfo('ram.bin')
                    member.size = len(raw) - 1 if kind == 'short' else len(raw)
                    if kind == 'symlink':
                        member.type = tarfile.SYMTYPE
                        member.linkname = 'other.bin'
                        member.size = 0
                        archive.addfile(member)
                    else:
                        archive.addfile(member, io.BytesIO(raw))
                        if kind == 'duplicate':
                            archive.addfile(member, io.BytesIO(raw))
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    native_profile.read_ram(path, sound.sha(raw), 'ram.bin', sound.sha(path.read_bytes()))

    def test_native_cli_preserves_existing_report_before_loading_inputs(self):
        from research.sound_assets import selection, verify
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'keep.json'
            path.write_bytes(b'keep this report')
            for producer, extra in ((verify, ['--elf', 'unused.elf', '--ram', 'unused.bin', '--ram-sha256', '0' * 64]),
                                    (qualify_disc, ['--disc', 'unused.bin', '--expected-disc-sha256', '0' * 64]),
                                    (selection, ['--elf', 'unused.elf'])):
                with self.subTest(producer=producer.__name__), contextlib.redirect_stderr(io.StringIO()):
                    result = producer.main(['--layout', 'unused.xml', '--output', str(path), *extra])
                self.assertEqual(result, 2)
                self.assertEqual(path.read_bytes(), b'keep this report')

    def test_raw_disc_qualification_matches_every_audio_byte_without_extracting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml, disc = raw_disc(root)
            paths = set(root.iterdir())
            before = {p: sound.sha(p.read_bytes()) for p in paths}
            result = qualify_disc.qualify(xml, disc, before[disc])
            self.assertEqual(result['audio_files_verified'], 3)
            self.assertEqual({r['path'] for r in result['rows']}, {'/BANK.VH', '/BANK.VB', '/BGA.SEQ'})
            self.assertTrue(result['all_read_Mode2_Form1_sectors_valid'])
            self.assertFalse(result['source_edition_verified_by_this_tool'])
            self.assertEqual(set(root.iterdir()), paths)
            self.assertEqual({p: sound.sha(p.read_bytes()) for p in paths}, before)

    def test_correct_raw_hash_does_not_hide_a_changed_audio_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, disc = raw_disc(Path(temp))
            data = bytearray(disc.read_bytes())
            data[23 * 2352 + 24 + 15] ^= 1
            disc.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'audio bytes differ'):
                qualify_disc.qualify(xml, disc, sound.sha(data))

    def test_raw_sector_headers_and_endian_directory_extents_are_checked(self):
        for kind in ('MSF', 'Form2', 'endianness'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                xml, disc = raw_disc(Path(temp))
                data = bytearray(disc.read_bytes())
                if kind == 'MSF':
                    data[18 * 2352 + 12] ^= 1
                elif kind == 'Form2':
                    data[23 * 2352 + 18] |= 32
                    data[23 * 2352 + 22] |= 32
                else:
                    data[16 * 2352 + 24 + 156 + 6] ^= 1
                disc.write_bytes(data)
                with self.assertRaises(ValueError):
                    qualify_disc.qualify(xml, disc, sound.sha(data))

    def test_unlisted_disc_audio_and_wrong_whole_disc_hash_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            xml, disc = raw_disc(Path(temp), extra_audio=True)
            with self.assertRaisesRegex(ValueError, 'Raw disc hash differs'):
                qualify_disc.qualify(xml, disc, '0' * 64)
            with self.assertRaisesRegex(ValueError, 'audio path sets differ'):
                qualify_disc.qualify(xml, disc, sound.sha(disc.read_bytes()))


if __name__ == '__main__':
    unittest.main()
