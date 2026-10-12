"""Compare original menu layout and acceptance through original graphics/list/heap code.

Manual constructed object graphs, not natural menu construction or rendering.
Requires the isolated Unicorn 2.1.2 backend qualified for the original allocator.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as n
from tools.verify_card_heap import backend_identity

BASE, SIZE = 0x100000, 0x18000
UI, PARENT, EFFECT, CONFIG = BASE, BASE + 0x200, BASE + 0x400, BASE + 0x600
COUNTS, SELECTIONS, ROWS, TABLE = BASE + 0x800, BASE + 0x820, BASE + 0x840, BASE + 0x860
ENTRY, ROW_ARRAY, LINES, GLYPHS, COORDS = BASE + 0x900, BASE + 0x1000, BASE + 0x2000, BASE + 0x4000, BASE + 0xA000
MANAGER, POOL = BASE + 0x11000, BASE + 0x12000
GP = 0x8008A808
SOURCE_FUNCTIONS = {'func_8003D73C': (0x8003D73C, 580), 'func_8003DAD4': (0x8003DAD4, 472)}


def s32(value):
    return (value + 0x80000000) % 0x100000000 - 0x80000000


def validate_case(case):
    count, glyphs, start, length = (case[key] for key in ('count', 'glyphs', 'start', 'length'))
    if (any(type(value) is not int for value in case.values() if not isinstance(value, tuple))
            or not 1 <= count <= 4 or not 0 <= glyphs <= 4 or not 0 <= start <= glyphs
            or not 0 <= length <= glyphs - start or not 0 <= case['old'] < count
            or not 0 <= case['selected'] < count or case['mode'] not in (0, 1, 2, 3)
            or case['show'] not in (0, 1, -1) or not 0 <= case['gap'] <= 4
            or not -16 <= case['spacing'] <= 16 or case['repeats'] not in (1, 2)
            or len(case['xy']) != 2 or any(type(v) is not int or not -0x80000000 <= v <= 0x7fffffff for v in case['xy'])):
        raise ValueError('Case exceeds the valid constructed menu/ownership profile.')


def put(buffer, address, value):
    struct.pack_into('<I', buffer, address - BASE, n.u32(value))


def line_address(row):
    return LINES + row * 0x200


def glyph_address(row, index):
    return GLYPHS + row * 0x1000 + 0x100 + index * 0x200


def initial(case):
    validate_case(case)
    data = bytearray(SIZE)
    for address, table in ((UI, 'D_8006E730'), (PARENT, 'g_BASE_CLASS_VTABLE'), (EFFECT, 'D_8006EAC0')):
        put(data, address, n.h.symbols[table])
    for offset, value in ((0x14, PARENT), (0x1c, 99), (0x20, 42), (0x28, 77), (0x3c, case['mode']),
                          (0x4c, CONFIG), (0x58, 0), (0x5c, COUNTS), (0x60, SELECTIONS), (0x64, ROWS), (0x68, EFFECT)):
        put(data, UI + offset, value)
    put(data, PARENT + 0x14, 0xABCD4000)
    put(data, EFFECT + 0x14, COORDS)
    struct.pack_into('<2h', data, EFFECT - BASE + 0x60, 71, -83)
    put(data, CONFIG + 0x24, TABLE)
    data[CONFIG - BASE + 0x10:CONFIG - BASE + 0x13] = bytes((0x23, 0xA4, 0x7F))
    for address, value in ((COUNTS, case['count']), (SELECTIONS, case['selected']), (ROWS, ROW_ARRAY),
                           (TABLE, ENTRY), (ENTRY + 4, case['old']), (ENTRY + 0x10, case['xy'][0]), (ENTRY + 0x14, case['xy'][1])):
        put(data, address, value)
    for row in range(case['count']):
        line = line_address(row)
        put(data, ROW_ARRAY + row * 4, line)
        put(data, line, n.h.symbols['g_TEXT_LINE_VTABLE'])
        put(data, line + 0x14, COORDS + 0x100 + row * 0x100)
        put(data, line + 0xb0, case['spacing'])
        put(data, line + 0xb4, GLYPHS + row * 0x1000)
        for offset, value in ((0xa9, case['glyphs']), (0xaa, case['gap']), (0xab, case['length']), (0xac, case['start'])):
            data[line - BASE + offset] = value
        for index in range(case['glyphs']):
            glyph = glyph_address(row, index)
            put(data, GLYPHS + row * 0x1000 + index * 4, glyph)
            put(data, glyph, n.h.symbols['g_GLYPH_VTABLE'])
            put(data, glyph + 0x14, COORDS + 0x600 + row * 0x400 + index * 0x80)
            put(data, glyph + 0x64, 0x12345678)
            data[glyph - BASE + 0x78:glyph - BASE + 0x7b] = bytes((7, 11, 13))
    put(data, MANAGER, POOL)
    put(data, MANAGER + 4, 0x2000)
    return data


def expected_objects(case, accepted):
    active = accepted and case['mode'] == 2
    selection = case['selected'] if active else case['old']
    result = {'mode': 1 if active else case['mode'], 'stored_selection': selection,
              'ticks': 0 if active else 99, 'timer_mode': 5 if active else 42,
              'effect_parent': PARENT if case['show'] and not active else 0,
              'effect_dimensions': [40, case['count'] * 12] if case['show'] else [71, -83],
              'lines': []}
    for row in range(case['count']):
        point = [case['xy'][0], s32(case['xy'][1] - selection * 10 + row * 10)]
        line = {'parent': PARENT, 'position': point, 'glyphs': []}
        x = case['xy'][0]
        for index in range(case['glyphs']):
            attached = case['start'] <= index < case['start'] + case['length']
            if attached and not active:
                if case['gap'] and index == case['gap']:
                    x = s32(x + 16)
                position = [x, point[1]]
                x = s32(x + case['spacing'])
            elif attached:
                position = [s32(case['xy'][0] + index * case['spacing']), point[1]]
            else:
                position = [0, 0]
            visible = row == selection or (not active and bool(case['show']))
            flag = 0x12345678 if visible else 0x92345678
            line['glyphs'].append({'parent': line_address(row) if attached else 0, 'position': position,
                                  'flags': flag if attached else 0x12345678,
                                  'color': [0x23, 0xA4, 0x7F] if active and row == selection and attached else [7, 11, 13]})
        result['lines'].append(line)
    return result


def observed_objects(data, case):
    word = lambda address: struct.unpack_from('<I', data, address - BASE)[0]
    xy = lambda address: list(struct.unpack_from('<2i', data, address - BASE))
    result = {'mode': word(UI + 0x3c), 'stored_selection': word(ENTRY + 4), 'ticks': word(UI + 0x1c),
              'timer_mode': word(UI + 0x20), 'effect_parent': word(EFFECT + 0x0c),
              'effect_dimensions': list(struct.unpack_from('<2h', data, EFFECT - BASE + 0x60)), 'lines': []}
    for row in range(case['count']):
        line = line_address(row)
        result['lines'].append({'parent': word(line + 0x0c), 'position': xy(line + 0xa0), 'glyphs': [
            {'parent': word(glyph_address(row, index) + 0x0c), 'position': xy(glyph_address(row, index) + 0xa0),
             'flags': word(glyph_address(row, index) + 0x64),
             'color': list(data[glyph_address(row, index) - BASE + 0x78:glyph_address(row, index) - BASE + 0x7b])}
            for index in range(case['glyphs'])]})
    return result


def candidate_patches(reference, candidate, load):
    if len(candidate) != len(reference):
        raise ValueError('Complete menu candidate length changed.')
    allowed = []
    patches = {}
    for name, (address, length) in SOURCE_FUNCTIONS.items():
        start = 0x800 + address - load
        allowed.append((start, start + length))
        if candidate[start:start + length] != reference[start:start + length]:
            patches[name] = candidate[start:start + length]
    if any(a != b and not any(start <= index < end for start, end in allowed)
           for index, (a, b) in enumerate(zip(reference, candidate))):
        raise ValueError('Complete candidate differs outside the two menu function spans.')
    return patches


class Machine(n.Machine):
    def __init__(self, functions, patches=None):
        self.entries, self.changed_hits = Counter(), Counter()
        self.instructions = []
        super().__init__(start=n.h.symbols['func_8003D73C'] & n.MASK, native_functions=functions)
        self.ranges = [(int(row['address'], 16) & n.MASK, (int(row['address'], 16) & n.MASK) + row['bytes']) for row in functions]
        self.changed_addresses = set()
        for name, data in (patches or {}).items():
            address, length = SOURCE_FUNCTIONS[name]
            if len(data) != length:
                raise ValueError('Menu patch exceeds its fixed native span.')
            self.cpu.mem_write(address & n.MASK, data)

    def hook(self, cpu, address, size, unused):
        pc = address & n.MASK
        if not any(start <= pc < end for start, end in self.ranges):
            raise ValueError('Menu graph executed outside reviewed native ranges: ' + hex(pc))
        if pc in self.native_entries:
            self.entries[self.native_entries[pc]] += 1
        if pc in self.changed_addresses:
            self.changed_hits[pc] += 1

    def call(self, name, *arguments):
        previous = bytes(self.cpu.mem_read(0, 0x200000))
        cpu = n.Uc(n.UC_ARCH_MIPS, n.UC_MODE_MIPS32 | n.UC_MODE_LITTLE_ENDIAN)
        cpu.mem_map(0, 0x200000)
        cpu.mem_write(0, previous)
        if bytes(cpu.mem_read(0, 0x200000)) != previous:
            raise ValueError('Fresh CPU lost native RAM between host-issued calls.')
        self.cpu = cpu
        cpu.hook_add(n.UC_HOOK_CODE, self.hook)
        cpu.mem_write(n.STACK - 0x800, bytes([0xCC]) * 0x900)
        saved = [n.u32(0xAB000000 + index * 0x10203) for index in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, GP), (n.reg.UC_MIPS_REG_RA, n.END)):
            cpu.reg_write(register, value)
        for index in range(4):
            cpu.reg_write(getattr(n.reg, 'UC_MIPS_REG_A' + str(index)), arguments[index] if index < len(arguments) else 0xBCA00000 + index)
        cpu.emu_start(n.h.symbols[name] & n.MASK, n.END, count=200000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != GP or [cpu.reg_read(r) for r in n.SAVED] != saved
                or bytes(cpu.mem_read(n.STACK, 0x100)) != bytes([0xCC]) * 0x100
                or bytes(cpu.mem_read(n.STACK - 0x800, 0x100)) != bytes([0xCC]) * 0x100):
            raise ValueError('Native menu graph violated its return/ABI/red-zone rules.')
        return bytes(cpu.mem_read(BASE, SIZE)) + bytes(cpu.mem_read(0x8A818, 12))


def history(machine, case):
    machine.cpu.mem_write(BASE, bytes(initial(case)))
    machine.call('memory_set_manager', MANAGER)
    machine.call('memory_setup_manager', MANAGER)
    snapshots = []
    for _ in range(case['repeats']):
        data = machine.call('func_8003D73C', UI, PARENT, n.u32(case['show']))
        if observed_objects(data, case) != expected_objects(case, False):
            raise ValueError('Original menu layout differs from independent object rules.')
        snapshots.append(data)
    data = machine.call('func_8003DAD4', UI)
    if observed_objects(data, case) != expected_objects(case, True):
        raise ValueError('Original menu acceptance differs from independent object rules.')
    snapshots.append(data)
    return snapshots


def cases():
    layouts = ((0, 0, 0, 0, 8), (3, 0, 3, 2, 8), (4, 1, 2, 2, -8), (3, 1, 1, 0, 0))
    for count in (1, 2, 4):
        selections = sorted({0, count - 1})
        for old, selected, mode, show, layout, repeats in itertools.product(selections, selections, (0, 1, 2, 3), (0, 1, -1), layouts, (1, 2)):
            glyphs, start, length, gap, spacing = layout
            yield dict(count=count, old=old, selected=selected, mode=mode, show=show, glyphs=glyphs,
                       start=start, length=length, gap=gap, spacing=spacing, repeats=repeats, xy=(31, 51))


def controls(functions):
    case = dict(count=2, old=0, selected=1, mode=2, show=1, glyphs=3, start=0,
                length=3, gap=2, spacing=8, repeats=1, xy=(31, 51))
    faults = [('layout_row_spacing', 'func_8003D73C', 0x1C8, 0x2442000A, 0x24420009),
              ('accept_row_spacing', 'func_8003DAD4', 0xE8, 0x2442000A, 0x24420009),
              ('persist_wrong_selection', 'func_8003DAD4', 0x16C, 0xAC540004, 0xAC400004)]
    records = []
    for label, name, offset, expected_word, changed_word in faults:
        address, length = SOURCE_FUNCTIONS[name]
        code = bytearray(n.h.target(address, length))
        if struct.unpack_from('<I', code, offset)[0] != expected_word:
            raise ValueError('Fault no longer identifies the reviewed original instruction: ' + label)
        struct.pack_into('<I', code, offset, changed_word)
        machine = Machine(functions, {name: bytes(code)})
        pc = (address + offset) & n.MASK
        machine.changed_addresses.add(pc)
        try:
            history(machine, case)
        except ValueError as error:
            if 'differs from independent object rules' not in str(error):
                raise
        else:
            raise ValueError('Independent menu rules failed to detect the native fault: ' + label)
        if not machine.changed_hits[pc]:
            raise ValueError('Fault fixture did not execute the changed instruction: ' + label)
        records.append({'kind': label, 'function': name, 'function_offset': offset,
                        'expected_word': hex(expected_word), 'changed_word': hex(changed_word),
                        'changed_instruction_executions': machine.changed_hits[pc],
                        'scope': 'Private original-function emulator memory; game inputs unchanged.'})
    return records


def verify(args):
    output = Path(args.output).resolve()
    if not output.is_relative_to((ROOT / '.decomp-lab').resolve()) or output.exists():
        raise ValueError('Choose a fresh private directory inside .decomp-lab.')
    functions = json.loads((ROOT / 'docs/menu-function-ranges.json').read_bytes())
    n.initialize_backend(n.load_program(functions))
    backend = backend_identity()
    dependencies = [Path(__file__), ROOT / 'docs/menu-function-ranges.json',
                    ROOT / 'tools/verify_native_ai.py', ROOT / 'tools/verify_card_heap.py',
                    ROOT / 'tools/progress.py', ROOT / 'configure.py',
                    ROOT / 'src/menu/ui_screen.c', ROOT / 'src/menu/ui_screen.h',
                    ROOT / 'src/menu/text_line.c', ROOT / 'src/menu/text_line.h',
                    ROOT / 'src/menu/sprite_node.c', ROOT / 'src/menu/sprite_node.h',
                    ROOT / 'src/menu/sprite.c', ROOT / 'src/menu/sprite.h',
                    ROOT / 'src/menu/glyph.c', ROOT / 'src/menu/glyph.h',
                    ROOT / 'src/graphics/effect_base.c', ROOT / 'src/graphics/effect_base.h',
                    ROOT / 'src/base/base.c', ROOT / 'src/base/base.h', ROOT / 'src/base/transform.c',
                    ROOT / 'src/base/timer.c', ROOT / 'rom/SLPS_015.56', ROOT / 'build/SLPS015.56',
                    *(args.candidate or [])]
    preserved = {path.resolve(): hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    variants = [('original', {})]
    for index, path in enumerate(args.candidate or []):
        variants.append(('candidate_' + str(index + 1), candidate_patches(n.h.ROM, path.read_bytes(), n.h.LOAD)))
    output.mkdir(parents=True, exist_ok=False)
    entries = {name: Counter() for name, patches in variants}
    digest, total, started = hashlib.sha256(), 0, time.monotonic()
    for case in cases():
        baseline = None
        for name, patches in variants:
            machine = Machine(functions, patches)
            snapshots = history(machine, case)
            entries[name].update(machine.entries)
            if baseline is None:
                baseline = snapshots
                for data in snapshots:
                    digest.update(data)
            elif snapshots != baseline:
                raise ValueError('Complete caller/heap/global buffers differ between original and menu candidate.')
        total += 1
        if total % 100 == 0:
            print('Menu histories', total, 'passed', flush=True)
    faults = controls(functions)
    if (backend_identity() != backend or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in preserved.items())):
        raise ValueError('Menu source, native backend or preserved inputs changed during verification.')
    report = {'status': 'passed_bounded_original_menu_histories', 'histories_each_image': total,
              'variants': [name for name, patches in variants], 'actual_native_entries': {name: dict(counts) for name, counts in entries.items()},
              'full_snapshot_bytes': SIZE + 12, 'original_snapshots_sha256': digest.hexdigest(), 'backend_identity': backend,
              'dependency_output_stubs': 0, 'source_promoted': False, 'whole_feature_groups_accepted': 0, 'model_api_calls': 0,
              'negative_controls_detected': faults,
              'preserved_dependencies': [{'path': str(path), 'sha256': value} for path, value in preserved.items()],
              'elapsed_seconds': round(time.monotonic() - started, 3),
              'scope': 'Manual valid object/ownership graphs with original menu, glyph, graphics, list and heap methods. '
                       'Independent XY/visibility/color/selection/timer rules plus complete original/candidate caller/heap/global buffers. '
                       'Excludes natural constructors/assets, rendered output, full input/menu reachability and PS1 hardware timing.'}
    (output / 'report.json').write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps({'passed': True, 'histories_each_image': total, 'variants': len(variants)}))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--candidate', action='append', type=Path)
    args = parser.parse_args(argv)
    verify(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
