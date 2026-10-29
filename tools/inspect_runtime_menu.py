"""Inspect naturally constructed title-menu resources in retained PS1 recordings.

Allocation generations, original allocator call sites and explicit menu members
identify ownership. A matching vtable or an equal address alone is insufficient.
This does not run constructors, control an emulator or accept a whole feature.
"""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import inspect_sdk_reads as sdk
from tools.compare_cold_start import physical
from tools.compare_npc_history import owned_file
from tools.inspect_file_heap import analyze_file_heap
from tools.inventory_runtime_scene import word
from tools.psx_image import ORIGINAL_SHA1, executable_offset

PANEL = 0x80086D44
MAIN_VTABLE = 0x80086B60
TEXT_VTABLE = 0x8006EB90
GLYPH_VTABLE = 0x8006EC74
TIM_VTABLE = 0x8006E558
CURSOR_VTABLE = 0x8006EAC0
ROOT_ALLOC_RETURN = 0x8004D534
MAX_PAYLOAD = 128 * 1024 * 1024
HEAP_TARGETS = {5: (0x80017B34, 456), 6: (0x80017CFC, 428),
                7: (0x80026A50, 100), 8: (0x800269F0, 96),
                9: (0x80026C20, 96), 10: (0x80026AB4, 84)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_blob(path, limit, member=None):
    """Read one raw, XZ or exact tar member in memory; never extract to disk."""
    path = Path(path)
    if member is not None:
        require(isinstance(member, str) and member, 'Choose one exact tar member.')
        with tarfile.open(path, 'r|*') as archive:
            for item in archive:
                if item.name != member:
                    continue
                require(item.isfile() and 0 <= item.size <= limit,
                        'The selected tar member is not a bounded regular file.')
                with archive.extractfile(item) as stream:
                    raw = stream.read(limit + 1)
                require(len(raw) == item.size, 'Incomplete retained tar member.')
                return raw
        raise ValueError('The exact retained tar member is absent.')
    opener = lzma.open if path.suffix.lower() == '.xz' else open
    with opener(path, 'rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'Retained payload exceeds the inspection bound.')
    return raw


class History:
    """Validated native generations with conservative, interior-frame liveness."""
    def __init__(self, raw, frame, executable, records, model):
        require(len(raw) == 0x200000, 'Use complete MainRAM, without masks.')
        require(type(frame) is int and frame >= 0, 'Invalid checkpoint frame.')
        self.raw, self.frame, self.executable = raw, frame, executable
        self.records = {r['entry_id']: r for r in records}
        require(len(self.records) == len(records), 'Duplicate native boundary ID.')
        self.generations = model['allocation_generations']
        self.by_id, self.live, self.owned = {}, {}, {}
        for item in self.generations:
            ident = item['id']
            require(ident not in self.by_id and ident in self.records,
                    'Duplicate or missing allocation generation.')
            row = self.records[ident]
            require(row['kind'] == 5 and row['v0'] == item['original_pointer']
                    and (row['v0'] & 0x1FFFFFFF) == item['address']
                    and row['a0'] == item['requested']
                    and sdk.sequence(row) == item['start']
                    and row['frame'] == item['allocation_frame'],
                    'Allocation generation differs from its actual native return.')
            if item['end'] is None:
                require(item['free_id'] is None and item['free_frame'] is None,
                        'An open generation has a native free.')
            else:
                free = self.records.get(item['free_id'])
                require(free is not None and free['kind'] == 6
                        and (free['a0'] & 0x1FFFFFFF) == item['address']
                        and sdk.sequence(free, 'entry_') == item['end'] > item['start']
                        and free['entry_frame'] == item['free_frame'],
                        'Allocation closure differs from its actual native free.')
            self.by_id[ident] = item
            if self.alive(item):
                require(item['address'] not in self.live,
                        'Two live generations share an allocation address.')
                self.live[item['address']] = item

    def alive(self, item):
        # A frame-boundary allocation/free needs instruction-position evidence;
        # do not guess its ordering relative to a post-frame RAM checkpoint.
        return (item['allocation_frame'] < self.frame
                and (item['free_frame'] is None or self.frame < item['free_frame']))

    def u32(self, pointer):
        return word(self.raw, physical(pointer, 4))

    def original(self, pointer, size):
        at = executable_offset(self.executable, pointer, size)
        return self.executable[at:at + size]

    def immutable(self, pointer, size, what):
        at = physical(pointer, size)
        require(self.raw[at:at + size] == self.original(pointer, size),
                'Changed original ' + what + '.')

    def allocation(self, pointer, requested=None, caller=None):
        at = physical(pointer, 4)
        item = self.live.get(at)
        require(item is not None, 'A menu pointer has no live allocation generation.')
        require(requested is None or item['requested'] == requested,
                'A menu allocation has the wrong original request size.')
        header = word(self.raw, at - 4)
        require(not header & 0x40000000 and (header & 0x0FFFFFFF) == item['capacity'] + 4,
                'A menu pointer has a changed or freed native heap header.')
        if caller is not None:
            ra = self.records[item['id']]['entry_ra']
            require(ra == caller if isinstance(caller, int) else caller[0] <= ra < caller[1],
                    'A menu allocation comes from a different original call site.')
        return item

    def own(self, pointer, requested, role, caller):
        item = self.allocation(pointer, requested, caller)
        require(item['id'] not in self.owned, 'Two owned menu members alias one allocation.')
        self.owned[item['id']] = dict(role=role, **item,
            allocation_return_pc=self.records[item['id']]['entry_ra'])
        return item['id']

    def object(self, pointer, size, table, role, caller):
        ident = self.own(pointer, size, role, caller)
        require(self.u32(pointer) == table, 'A live menu object has the wrong vtable.')
        self.immutable(table, 16, 'menu vtable prefix')
        return ident

    def string(self, pointer):
        at = physical(pointer, 1)
        end = self.raw.find(b'\0', at, min(len(self.raw), at + 256))
        require(end >= at, 'Unterminated bounded menu string.')
        raw = self.raw[at:end + 1]
        require(raw == self.original(pointer, len(raw)), 'Changed original menu label.')
        return raw[:-1]

    def line(self, pointer, font, role, text=None):
        ident = self.object(pointer, 0xB8, TEXT_VTABLE, role, 0x800408F8)
        at = physical(pointer, 0xB8)
        count = self.raw[at + 0xA9]
        require(0 < count <= 255 and (text is None or count == len(text)),
                'Text-line glyph capacity differs from its original label.')
        require(self.u32(pointer + 0x48) == font + 0x2C,
                'Text line does not borrow its panel font metadata.')
        array = self.u32(pointer + 0xB4)
        array_id = self.own(array, count * 4, role + '.glyphs', 0x800409B8)
        glyph_ids, characters = [], bytearray()
        for index in range(count):
            glyph = self.u32(array + index * 4)
            glyph_ids.append(self.object(glyph, 0xAC, GLYPH_VTABLE,
                f'{role}.glyph[{index}]', 0x80041AD8))
            require(self.u32(glyph + 0x48) == font + 0x2C,
                    'Glyph does not borrow its panel font metadata.')
            characters.append(self.raw[physical(glyph, 0xAC) + 0xA8])
        require(text is None or characters == text, 'Natural glyph characters differ from the label.')
        return dict(allocation_id=ident, glyph_array_id=array_id, glyph_count=count,
                    characters_sha256=sha(characters),
                    free_order=glyph_ids + [array_id, ident])

    def closure(self, order, root):
        require(len(order) == len(set(order)) and set(order) == set(self.owned),
                'Owned-resource release plan loses or duplicates a generation.')
        if root['end'] is None:
            return dict(status='open_root_generation', selected_owned_resources=len(order),
                        all_selected_resources_released=False, release_order_checked=False)
        for ident in order:
            item = self.by_id[ident]
            require(item['end'] is not None and root['start'] <= item['start']
                    and item['end'] <= root['end'],
                    'A selected owned resource outlives its naturally released menu.')
        observed = sorted(order, key=lambda ident: self.by_id[ident]['end'])
        require(observed == order, 'Natural owned-resource release order differs.')
        return dict(status='selected_owned_generations_closed_in_native_order',
                    selected_owned_resources=len(order), all_selected_resources_released=True,
                    release_order_checked=True, root_free_frame=root['free_frame'],
                    ordered_generation_ids=order)


def inspect_snapshot(raw, frame, executable, records, payload, model):
    """Analyze a checkpoint after validate_records/analyze_file_heap qualification."""
    h = History(raw, frame, executable, records, model)
    roots = [a for a in h.generations
             if h.records[a['id']]['entry_ra'] == ROOT_ALLOC_RETURN]
    require(all(a['requested'] == 0xC4 for a in roots), 'Unexpected main-menu factory allocation.')
    live = [a for a in roots if h.alive(a)]
    require(len(live) <= 1, 'More than one live title-menu factory generation.')
    base = dict(frame=frame, RAM_sha256=sha(raw), factory_generations=len(roots),
                root_history=[dict(a) for a in roots], new_C_bytes=0,
                menu_constructor_entry_boundaries_observed=0, whole_feature_groups_accepted=0,
                whole_NPC_encounters_accepted=0, complete_state_parity_checked=False,
                original_hardware_timing_verified=False)
    if not live:
        boundary = any(frame == a['allocation_frame'] or frame == a['free_frame'] for a in roots)
        if boundary:
            return dict(status='unqualified_title_menu_frame_boundary', **base)
        return dict(status='no_live_title_menu_at_checkpoint', **base)
    root = live[0]
    menu = root['original_pointer']
    root_id = h.object(menu, 0xC4, MAIN_VTABLE, 'menu', ROOT_ALLOC_RETURN)
    require(h.u32(menu + 0x4C) == PANEL, 'Title menu uses a different panel descriptor.')
    panel_at = physical(PANEL, 0x28)
    descriptor = raw[panel_at:panel_at + 0x28]
    original = h.original(PANEL, 0x28)
    require(descriptor[:4] == original[:4] and descriptor[8:] == original[8:],
            'Changed title descriptor outside its mutable texture handle.')
    font = h.u32(PANEL + 4)
    font_id = h.object(font, 0x50, TIM_VTABLE, 'panel.font', 0x8003B3B8)
    require(h.u32(font + 0x10) == 0, 'The observed font file buffer is not released.')
    releases = [r for r in model['releases'] if r['allocation_id'] == font_id and r['freed_buffer']]
    require(len(releases) == 1, 'Font lacks one generation-qualified native buffer release.')
    release = releases[0]
    native = h.records[release['id']]
    require(native['kind'] == 9 and native['a0'] == font and native['frame'] < frame,
            'Font buffer release is not before this checkpoint.')
    buffers = [a for a in h.generations if a['free_id'] == release['native_free_id']]
    require(len(buffers) == 1, 'Font release does not close one backing generation.')
    backing = buffers[0]
    require(backing['original_pointer'] == release['freed_buffer']
            and backing['end'] < sdk.sequence(native)
            and backing['start'] > root['start'], 'Font backing lifetime disagrees with its release.')
    extent = payload[native['buffer_offset']:native['buffer_offset'] + native['buffer_bytes']]
    require(len(extent) == 88, 'Incomplete native font-release field snapshots.')
    before, after = struct.unpack('<22I', extent)[:11], struct.unpack('<22I', extent)[11:]
    require(before[0] == after[0] == TIM_VTABLE and before[4] == backing['original_pointer']
            and before[5] == backing['requested'] and after[4] == 0,
            'Native release does not identify the original TIM backing buffer.')
    stale_metadata = [h.u32(font + offset) for offset in (0x38, 0x44)]
    require(all(backing['address'] <= physical(p, 1) < backing['address'] + backing['requested']
                for p in stale_metadata), 'TIM metadata no longer identifies its released backing extent.')

    count = h.u32(menu + 0x50)
    require(count == 6, 'The retail title panel must contain six rows.')
    arrays = {offset: h.u32(menu + offset) for offset in (0x54, 0x5C, 0x60, 0x64)}
    array_ids = {off: h.own(ptr, count * 4, f'panel.array_{off:02x}', (0x8003CE98, 0x8003D050))
                 for off, ptr in arrays.items()}
    strings, choices = h.u32(PANEL + 0x1C), h.u32(PANEL + 0x24)
    h.immutable(strings, 28, 'title label table')
    h.immutable(choices, 24, 'title choice-descriptor table')
    rows, row_order, unused, choice_count, glyphs = [], [], [], 0, 0
    for index in range(count):
        text = h.string(h.u32(strings + index * 4))
        line = h.line(h.u32(arrays[0x54] + index * 4), font, f'panel.row[{index}]', text)
        glyphs += line['glyph_count']
        entry = h.u32(choices + index * 4)
        options = []
        if entry:
            h.immutable(entry, 4, 'choice descriptor prefix')
            h.immutable(entry + 8, 20, 'choice descriptor suffix')
            names = h.u32(entry + 0x18)
            h.immutable(names, 12, 'SHAKE choice-name table')
            option_count = h.u32(arrays[0x5C] + index * 4)
            selected = h.u32(arrays[0x60] + index * 4)
            require(option_count == 2 and selected < option_count and selected == h.u32(entry + 4),
                    'Natural SHAKE choice count or selected index disagrees.')
            table = h.u32(arrays[0x64] + index * 4)
            table_id = h.own(table, option_count * 4, f'panel.row[{index}].choices', (0x8003D5CC, 0x8003D6D4))
            for choice in range(option_count):
                option_text = h.string(h.u32(names + choice * 4))
                option = h.line(h.u32(table + choice * 4), font,
                                f'panel.row[{index}].choice[{choice}]', option_text)
                glyphs += option['glyph_count']
                row_order.extend(option['free_order'])
                options.append(dict(label=option_text.decode('ascii'), **option))
            row_order.append(table_id)
            choice_count += option_count
        else:
            # These slots are never initialized or consumed for a row without
            # choices. Preserve/report their bytes; do not follow stale words.
            unused.append(dict(row=index, words=[h.u32(arrays[off] + index * 4)
                                                  for off in (0x5C, 0x60, 0x64)]))
        row_order.extend(line['free_order'])
        rows.append(dict(label=text.decode('ascii'), choices=options, **line))
    selected_row = h.u32(menu + 0x58)
    disabled_table = h.u32(PANEL + 0x18)
    disabled = [h.u32(disabled_table + index * 4) for index in range(count)]
    require(all(value in (0, 1) for value in disabled) and selected_row < count
            and not disabled[selected_row], 'Natural selected row is invalid or disabled.')
    cursor_id = h.object(h.u32(menu + 0x68), 0x6C, CURSOR_VTABLE, 'panel.cursor', 0x800404FC)
    day = h.line(h.u32(menu + 0xB0), font, 'menu.day_label')
    order = day['free_order'] + [font_id, cursor_id] + row_order
    order += [array_ids[off] for off in (0x64, 0x60, 0x5C, 0x54)] + [root_id]
    closure = h.closure(order, root)
    reused = []
    for item in h.owned.values():
        require(item['start'] >= root['start'], 'Owned resource predates this menu generation.')
        if (item['address'] < backing['address'] + backing['requested']
                and backing['address'] < item['address'] + item['requested']):
            require(item['start'] > backing['end'],
                    'A menu resource overlaps its still-live font file backing.')
            reused.append(item['id'])
    return dict(status='inspected_bounded_natural_title_menu', **base,
        root_allocation_id=root_id, menu_address=menu,
        descriptor_address=PANEL, mutable_descriptor_fields=['tex'],
        initial_descriptor_sha256=sha(original), runtime_descriptor_sha256=sha(descriptor),
        row_count=count, choice_count=choice_count, panel_glyphs=glyphs,
        selected_row=selected_row, disabled_rows=disabled, rows=rows, day_label=day,
        unused_choice_storage=unused,
        outer_array_sha256={f'{off:02x}':sha(raw[physical(ptr,24):physical(ptr,24)+24])
                            for off,ptr in arrays.items()},
        font_buffer=dict(allocation_id=backing['id'], release_id=release['id'],
                         requested=backing['requested'], allocation_frame=backing['allocation_frame'],
                         free_frame=backing['free_frame'], native_release_fields_sha256=sha(extent),
                         metadata_pointers_are_released_views=True,
                         reused_by_selected_allocations=len(reused), reused_generation_ids=reused),
        owned_allocations=list(h.owned.values()), closure=closure,
        scope='Observed allocation call sites, natural construction state and selected ownership lifetimes; '
              'not complete constructor-path coverage, all hidden resources, rendering or whole menu acceptance.')


def load_heap(folder, payload_path=None, executable_path=None):
    """Revalidate retained inputs and every original SDK/heap boundary in memory."""
    folder = Path(folder).resolve(strict=True)
    manifest_raw = (folder / 'run-inputs.json').read_bytes()
    manifest = json.loads(manifest_raw)
    require(manifest.get('schema_version') == 1 and manifest.get('runtime_kind') == 'dispatch_observer'
            and all(manifest.get(key) is False for key in
                    ('game_RAM_injected', 'restored_state', 'emulator_UI_controlled')),
            'Use an uninjected, unrestored retained native observer recording.')
    pins = []
    for item in manifest['source_snapshots']:
        data = owned_file(folder, item['file']).read_bytes()
        require(len(data) == item['bytes'] and sha(data) == item['sha256'] == item['original']['sha256'],
                'A retained observer source snapshot changed.')
        pins.append(dict(file=item['file'], bytes=len(data), sha256=sha(data)))
    for name, key in [('program.json', 'program_file'), ('settings.json', 'settings_file'),
                      ('submitted.tsv', 'submitted')]:
        data = (folder / name).read_bytes()
        require(len(data) == manifest[key]['bytes'] and sha(data) == manifest[key]['sha256'],
                'A retained program, settings or controller file changed.')
        pins.append(dict(file=name, bytes=len(data), sha256=sha(data)))
    program = json.loads((folder / 'program.json').read_bytes())
    settings = json.loads((folder / 'settings.json').read_bytes())
    require(program == manifest['program'] and settings == manifest['settings']
            and program['method_trace'].get('heap_lifetime') is True,
            'Retained native settings or heap selection disagree with the manifest.')
    targets = settings['return_trace']['sdk_targets']
    for kind, span in HEAP_TARGETS.items():
        chosen = [(t['pc'],t['bytes']) for t in targets if t['kind'] == kind]
        require(chosen == [span], 'The original native heap/file target selection changed.')
    executable = Path(executable_path or ROOT / 'rom/SLPS_015.56').read_bytes()
    require(hashlib.sha1(executable).hexdigest() == ORIGINAL_SHA1, 'Use the canonical Japanese executable.')
    data = (folder / 'observations/sdk-reads.bin').read_bytes()
    payload = read_blob(payload_path or folder / 'observations/sdk-read-data.bin', MAX_PAYLOAD)
    summary_raw = (folder / 'observations/sdk-read-summary.json').read_bytes()
    summary = json.loads(summary_raw)
    require(summary['frame_payload_limit'] == manifest['observer_profile']['sdk_read_frame_payload_bytes'],
            'Native payload capacity differs from the retained observer profile.')
    transport, records = sdk.validate_records(data, payload, summary, targets, executable, program)
    model = analyze_file_heap(records, payload, [], [], [], program, check_read_lifetimes=False)
    require(model['unobserved_allocation_frees'] == 0, 'Observed menu history has unqualified native frees.')
    report = json.loads((folder / 'observations/report.json').read_bytes())
    result = json.loads((folder / 'result.json').read_bytes())
    exit_status = json.loads((folder / 'exit.json').read_bytes())
    require(exit_status.get('exit_code') == 0 and result.get('input_files_preserved') is True
            and report.get('frames_advanced') == program['frames'] + 1
            and report.get('submitted_frames') == program['frames']
            and report.get('observer_enabled') is True
            and all(report.get(k) is False for k in ('restored_state', 'game_RAM_injected', 'emulator_UI_controlled')),
            'Retained native recording did not finish with its declared inputs intact.')
    proof = dict(manifest_sha256=sha(manifest_raw), source_snapshots=pins,
                 SDK_records_sha256=sha(data), SDK_payload_sha256=sha(payload),
                 SDK_summary_sha256=sha(summary_raw), SDK_transport=transport,
                 queued_Read_lifetimes_rechecked=False,
                 all_runtime_or_output_artifacts_reaudited=False)
    return executable, records, payload, model, report, proof


def inspect_capture(folder, frame, ram_path=None, ram_member=None, payload_path=None, executable_path=None):
    executable, records, payload, model, report, proof = load_heap(folder, payload_path, executable_path)
    raw = read_blob(ram_path or Path(folder)/f'observations/mainram-{frame}.bin', 0x200000, ram_member)
    points = [p for p in report['checkpoints'] if p['relative_frame'] == frame]
    require(len(points) == 1 and points[0]['RAM_sha256'] == sha(raw),
            'Complete checkpoint RAM does not match its retained recording report.')
    result = inspect_snapshot(raw, frame, executable, records, payload, model)
    result['input_verification'] = proof
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--frame', type=int, required=True)
    parser.add_argument('--ram', type=Path, help='Raw/XZ MainRAM or retained tar archive')
    parser.add_argument('--ram-member', help='One exact regular member in --ram')
    parser.add_argument('--sdk-payload', type=Path, help='Raw or XZ retained sdk-read-data.bin')
    parser.add_argument('--executable', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'Refusing to replace an existing analysis report.')
    require(args.ram_member is None or args.ram is not None, '--ram-member requires --ram.')
    result = inspect_capture(args.capture, args.frame, args.ram, args.ram_member,
                             args.sdk_payload, args.executable)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status', 'frame', 'new_C_bytes', 'whole_feature_groups_accepted')}))


if __name__ == '__main__':
    main()
