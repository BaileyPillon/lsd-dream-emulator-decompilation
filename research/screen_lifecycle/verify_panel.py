"""Check populated UI panel ownership through original screen destruction.

The retail title descriptor supplies its six rows and SHAKE choices. Empty
and mixed contexts exercise the same cleanup guards on initialized graphs.
Construction, visible output, pending I/O and hardware shutdown stay separate.
"""
import argparse
from collections import Counter
import gc
import hashlib
import itertools
import json
import lzma
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.screen_lifecycle import verify_cleanup as core

ROOT, heap, native, lifecycle = core.ROOT, core.heap, core.native, core.lifecycle
require = core.require
ROW = dict(function='func_8003D6D4', address='0x8003D6D4', bytes=104,
           sha256='625b1196284b36f4779cc8553819789efff59177121927799db354c94872b40f')
PANEL_ADDRESS = 0x80086D44
PANEL_SHA256 = '28cf22086de08c4dd0efc841132687acaf84cb4e1308e0b32d3f92f6cf27b5b5'
TITLE_LENGTHS = (5, 9, 4, 4, 5, 5)
TITLE_STRINGS = (0x8008A9AC, 0x80011434, 0x8008A9A4, 0x8008A99C, 0x8008A994, 0x8008A98C)
LAYOUTS = ('title', 'empty', 'mixed')
FAULTS = {
    'skip_owned_font': (0x8003D0A0, 0x0040F809, 0),
    'free_borrowed_font': (0x8003D080, 0x10400009, 0),
    'skip_choice_rows': (0x8003D0EC, 0x8C420000, 0x00001021),
    'leak_choice_array': (0x8003D720, 0x0C005F3F, 0),
}


def cases():
    for layout, segment, seed, links, sound, owns_texture in itertools.product(
            LAYOUTS, lifecycle.SEGMENTS, (0, 1), (False, True),
            ('borrowed', 'owned_no_bank', 'owned_bank'), (False, True)):
        yield (dict(kind='main', segment=segment, seed=seed, buffers=True, links=links, sound=sound),
               dict(layout=layout, owns_texture=owns_texture))


def validate_panel(panel):
    require(set(panel) == {'layout', 'owns_texture'} and panel['layout'] in LAYOUTS
            and type(panel['owns_texture']) is bool, 'Unsupported panel ownership context.')


class Fixture(core.Fixture):
    def __init__(self, case, panel):
        validate_panel(panel)
        require(case['kind'] == 'main' and case['buffers'] is True,
                'This profile needs a supplied title menu with owned base resources.')
        self.panel = panel
        super().__init__(case)

    def object_words(self, offset, values):
        require(0 <= offset and offset + 4*len(values) <= core.LENGTHS['object'], 'Panel input exceeds its guarded buffer.')
        for i, value in enumerate(values):
            self.model.put('object', offset + i*4, value)
        self.setup_operations.append(['object_words', offset, list(values)])

    def text(self, count):
        line = self.transform(0xB8, 'text')
        table = self.array(4*count)
        glyphs = [self.transform(0xA8, 'glyph') for _ in range(count)]
        for i, glyph in enumerate(glyphs):
            self.put(table, i*4, glyph)
        self.put(line, 0xA8, (count << 8) | (count << 24))
        self.put(line, 0xB4, table)
        self.extra_owned_objects += [line, *glyphs]
        return line

    def array(self, size):
        # The original allocator returns NULL for a zero-byte request.
        return self.alloc(size) if size else 0

    def initialize_extra_resources(self):
        segment = self.case['segment']
        object_pointer = lambda offset: (heap.BASES['object'] + offset) | segment
        self.descriptor = object_pointer(0x80)
        self.font = self.object(0x50, 'tim')
        self.file_fixture(self.font)
        if self.panel['owns_texture']:
            self.extra_owned_objects.append(self.font)
        else:
            self.extra_retained_pointers.update((self.font, self.file_payloads[self.font]))
        self.cursor = self.transform(0x6C, 'cell')
        self.extra_owned_objects.append(self.cursor)
        layout = self.panel['layout']
        lengths = TITLE_LENGTHS if layout == 'title' else (() if layout == 'empty' else TITLE_LENGTHS[:3])
        self.lines = [self.text(n) for n in lengths]
        self.row_arrays = [self.array(4*len(lengths)) for _ in range(4)]
        for field, pointer in zip((0x54, 0x5C, 0x60, 0x64), self.row_arrays):
            self.put(self.root, field, pointer)
        self.put(self.root, 0x4C, self.descriptor)
        self.put(self.root, 0x50, len(lengths))
        self.put(self.root, 0x58, 0xFFFFFFFF)
        self.put(self.root, 0x68, self.cursor)
        self.choices = {}
        entries = [0]*len(lengths)
        if layout == 'title':
            self.choices[5] = [self.text(3), self.text(2)]
            entries[5] = 0x80086CA8
        elif layout == 'mixed':
            self.choices[0] = []
            self.choices[2] = [self.text(3), self.text(2)]
            entries[0], entries[2] = object_pointer(0), 0x80086CA8
            # A valid empty names list and its separate choice descriptor.
            self.object_words(0, [0, 0, 0, 0, 0, 0, object_pointer(0x20)])
            self.object_words(0x20, [0])
        self.choice_tables = {}
        for i, line in enumerate(self.lines):
            self.put(self.row_arrays[0], 4*i, line)
            if i in self.choices:
                choices = self.choices[i]
                table = self.array(4*len(choices))
                self.choice_tables[i] = table
                self.put(self.row_arrays[1], 4*i, len(choices))
                self.put(self.row_arrays[2], 4*i, 0)
                self.put(self.row_arrays[3], 4*i, table)
                for j, pointer in enumerate(choices):
                    self.put(table, 4*j, pointer)
        labels = 0x80086CF8
        if layout != 'title':
            self.object_words(0x50, [*TITLE_STRINGS[:len(lengths)], 0])
            labels = object_pointer(0x50)
        self.object_words(0xB0, entries or [0])
        words = [0x80011440 if self.panel['owns_texture'] else 0, self.font, 0, 0,
                 0x80505050, 0x80, 0x80086CDC, labels, 0x80086D14, object_pointer(0xB0)]
        self.object_words(0x80, words)

    def destroy_text(self, line):
        table = self.get(line, 0xB4)
        count = self.get(line, 0xA8) >> 8 & 255
        for i in range(count):
            self.destroy_transform(self.get(table, 4*i))
            self.put(table, 4*i, 0)
        self.free(table); self.put(line, 0xB4, 0)
        self.destroy_transform(line)

    def predict_extra_cleanup(self):
        if self.panel['owns_texture']:
            self.destroy_file(self.font)
        self.destroy_transform(self.cursor)
        for i, line in enumerate(self.lines):
            if i in self.choices:
                self.put(self.root, 0x58, i)
                table = self.choice_tables[i]
                for j, pointer in enumerate(self.choices[i]):
                    self.destroy_text(pointer); self.put(table, 4*j, 0)
                self.free(table)
            self.destroy_text(line)
        for pointer in reversed(self.row_arrays):
            self.free(pointer)


class Machine(core.Machine):
    def __init__(self, fixture, rows, fault=None):
        self.panel_fault, self.panel_fault_hits = fault, 0
        super().__init__(fixture, rows)
        if fault:
            pc, old, new = FAULTS[fault]
            require(native.h.target(pc, 4) == struct.pack('<I', old), 'Panel control lost its original instruction.')
            self.cpu.mem_write(pc & native.MASK, struct.pack('<I', new))

    def hook(self, cpu, address, size, unused):
        if self.panel_fault and address & native.MASK == FAULTS[self.panel_fault][0] & native.MASK:
            self.panel_fault_hits += 1
        super().hook(cpu, address, size, unused)


def qualify(output, diagnostic):
    rows, image = core.qualify(output, diagnostic)
    # This companion enters only the title-menu family, whose content cleanup
    # never dispatches the chart's hundred-cell release method.
    rows = [row for row in rows if row['function'] != 'func_80058308']
    directory = Path(diagnostic) if diagnostic is not None else output
    elf_path = directory/'candidate-symbols.elf'
    elf = elf_path.read_bytes()
    symbols_text = subprocess.check_output([core.configure.CROSS+'nm', '-S', '--defined-only', str(elf_path)], text=True)
    gnu = core.nm_functions(symbols_text)
    original = (ROOT/core.configure.ROM).read_bytes()
    owned = lifecycle.owned_record(original, elf, gnu, ROW['function'], int(ROW['address'], 16))
    require(owned == ROW, 'Original choice-list cleanup changed.')
    symbol = [line.split() for line in symbols_text.splitlines() if line.split()[-1] == 'g_TITLE_MENU_PANEL']
    require(len(symbol) == 1 and int(symbol[0][0], 16) == PANEL_ADDRESS, 'Require the unified title descriptor at its original address.')
    data = original[0x800+PANEL_ADDRESS-0x80010000:0x800+PANEL_ADDRESS-0x80010000+40]
    require(core.digest(data) == PANEL_SHA256, 'Complete original title descriptor differs.')
    return rows+[ROW], image


def verify(destination, lab_root=None, diagnostic=None):
    require(sys.platform == 'linux' and Path.cwd().resolve() == ROOT, 'Run from the repository root in Linux/WSL.')
    paths = {Path(__file__), ROOT/'research/screen_lifecycle/verify_cleanup.py',
             ROOT/'src/menu/main_menu.c', ROOT/'src/menu/main_menu.h', ROOT/'src/menu/ui_screen.c',
             ROOT/'src/menu/ui_screen.h', ROOT/'src/menu/movie_screen.c',
             ROOT/'tools/verify_card_heap.py', ROOT/'tools/heap_model.py', ROOT/'tools/verify_native_ai.py',
             ROOT/'research/screen_lifecycle/cleanup-functions.json', ROOT/'PROJECT_OBJECTIVE.md'}
    paths.update(ROOT/name for name,_kind in lifecycle.build_manifest())
    paths.update((ROOT/'src').rglob('*.h'))
    before = {str(p): lifecycle.file_record(p) for p in sorted(paths)}
    output = core.new_output(destination, lab_root)
    rows,image = qualify(output,diagnostic)
    native.initialize_backend(native.load_program(rows));backend = heap.backend_identity()
    counts,groups,seen,aggregate = Counter(),Counter(),set(),hashlib.sha256()
    minimum,maximum = None,None
    journal=output/'cases.jsonl.xz'
    with lzma.open(journal,'xt',encoding='utf-8',newline='\n') as stream:
        for index,(case,panel) in enumerate(cases()):
            identity=json.dumps([case,panel],sort_keys=True)
            require(identity not in seen,'Duplicate panel context.');seen.add(identity)
            fixture=Fixture(case,panel)
            machine=Machine(fixture,rows)
            result=machine.execute();result['panel']=panel
            result['descriptor']=fixture.descriptor
            result['last_choice_row']=fixture.get(fixture.root,0x58)
            counts.update(machine.entries)
            groups[panel['layout']+('/owned_texture' if panel['owns_texture'] else '/borrowed_texture')]+=1
            minimum=len(result['release_trace']) if minimum is None else min(minimum,len(result['release_trace']))
            maximum=len(result['release_trace']) if maximum is None else max(maximum,len(result['release_trace']))
            line=json.dumps(result,sort_keys=True,separators=(',',':'))+'\n'
            stream.write(line);aggregate.update(line.encode())
            if (index+1)%12==0:print(json.dumps(dict(completed=index+1,total=216)),flush=True)
            gc.collect()
    require(set(counts)=={r['function'] for r in rows},'Not every qualified body executed.')
    controls=[]
    case=dict(kind='main',segment=0x80000000,seed=1,buffers=True,links=True,sound='owned_bank')
    for fault,(pc,old,new) in FAULTS.items():
        panel=dict(layout='title',owns_texture=fault!='free_borrowed_font')
        machine=Machine(Fixture(case,panel),rows,fault)
        try:
            machine.execute()
        except ValueError as error:
            require(machine.panel_fault_hits>0 and machine.last_return==0 and 'release order' in str(error),
                    'Panel fault did not complete and trigger its intended ownership rejection.')
            controls.append(dict(fault=fault,pc=hex(pc),executed_hits=machine.panel_fault_hits,
                                 returned=machine.last_return,rejection=str(error)))
        else:
            raise ValueError('Executed panel ownership fault was not rejected: '+fault)
    require(all(lifecycle.file_record(Path(p))==r for p,r in before.items()),'A protected producer or source changed.')
    require(lifecycle.check_build_current(ROOT) is True and heap.backend_identity()==backend,'Build/backend changed.')
    report=dict(schema_version=1,status='passed_bounded_populated_panel_cleanup',profiles=len(seen),groups=dict(groups),
                original_functions=rows,original_entries=dict(counts),input_output_sha256=aggregate.hexdigest(),
                cases_journal=dict(path=journal.name,**lifecycle.file_record(journal)),
                release_count_range=[minimum,maximum],canonical_image=image,backend=backend,
                executed_ownership_controls=controls,
                producer_dependencies=[dict(path=Path(p).relative_to(ROOT).as_posix(),**r) for p,r in before.items()],
                dependency_output_contracts=[],constructors_executed=False,new_game_C_bytes=0,
                original_features_accepted=0,NPC_encounters_accepted=0,model_API_calls=0)
    (output/'panel-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],profiles=len(seen),original_bodies=len(rows))),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--lab-root',type=Path)
    parser.add_argument('--diagnostic',type=Path)
    args=parser.parse_args()
    verify(args.output,args.lab_root,args.diagnostic)
