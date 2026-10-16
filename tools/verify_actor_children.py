"""Run original actor child construction on every bounded model in an extraction.

Requires a complete matching build, your own dumpsxiso extraction and isolated
requirements-card-heap.txt. Reports stay private. No model API or gameplay edits.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.compare_function import elf_function
from tools import actor_child_model as model
from tools import verify_native_ai as native
from tools import verify_card_heap as heap
from tools.decomp_workbench import candidate_link_command
from tools.inventory_animations import inspect_animations
from tools.progress import build_manifest

RANGES = ROOT / 'docs/actor-child-construction-function-ranges.json'
NINJA_VERSION = '1.13.2'
# The pinned PyPI package's executable includes this upstream build suffix.
NINJA_BUILD_VERSIONS = (NINJA_VERSION, NINJA_VERSION + '.git.kitware.jobserver-pipe-1')
IDENTITY_KEYS = ('package_version', 'library_api', 'loaded_library_sha256',
                 'binding_entry_sha256', 'binding_sources_sha256', 'binding_source_count')
FAULTS = (
    dict(name='child-lifetime', address=0x800571EC, old=0xA4820048, replacement=0xA4800048),
    dict(name='coordinate-matrix', address=0x80012854, old=0xACC20004, replacement=0xACC20008),
)
DEPENDENCIES = ('tools/verify_actor_children.py', 'tools/actor_child_model.py',
                'tools/heap_model.py', 'tools/verify_card_heap.py', 'tools/verify_card_cleanup.py',
                'tools/verify_native_ai.py', 'tools/inventory_animations.py', 'tools/inventory_disc.py',
                'tools/inventory_vtables.py', 'tools/psx_image.py', 'tools/progress.py',
                'tools/decomp_workbench.py', 'research/compiler/compare_function.py',
                'docs/actor-child-construction-function-ranges.json', 'requirements-card-heap.txt',
                'requirements.txt')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, report):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


def output_directory(value):
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if path == lab or not path.is_relative_to(lab) or path.exists():
        raise ValueError('Choose a fresh output directory inside .decomp-lab; existing evidence is preserved.')
    return path


def require_ninja():
    """Probe read-only before any dry run can invalidate a newer Ninja log."""
    ninja = shutil.which('ninja', path=str(Path(sys.executable).parent)) or shutil.which('ninja')
    if not ninja:
        raise ValueError('Install the pinned Ninja from requirements.txt in this environment.')
    version = subprocess.check_output([ninja, '--version'], cwd=ROOT, text=True).strip()
    if version not in NINJA_BUILD_VERSIONS:
        raise ValueError('Ninja ' + NINJA_VERSION + ' is required before checking build freshness; found ' + version)
    return dict(version=version, executable_sha256=sha(Path(ninja).read_bytes()))


def build_inputs():
    paths = {ROOT / source for source, _ in build_manifest()}
    paths.update(ROOT / name for name in ('configure.py', configure.SPLAT_CONFIG, configure.SYMBOLS))
    for folder in ('src', 'include'):
        paths.update((ROOT / folder).rglob('*.h'))
        paths.update((ROOT / folder).rglob('*.inc'))
    if any(not path.is_file() for path in paths):
        raise ValueError('Canonical build inputs are incomplete.')
    return {path.relative_to(ROOT).as_posix(): sha(path.read_bytes()) for path in sorted(paths)}


def dependency_hashes():
    return {name: sha((ROOT / name).read_bytes()) for name in DEPENDENCIES}


def qualify_diagnostic(program, elf, binary, functions):
    # No sized symbol is trusted until the complete diagnostic image matches.
    if binary != program.ROM:
        raise ValueError('The complete symbol diagnostic differs from the canonical executable.')
    ranges = []
    for record in functions:
        name, address, length = record['function'], int(record['address'], 16), record['bytes']
        code, _ = elf_function(elf, name, address)
        if (program.symbols.get(name) != address or len(code) != length
                or sha(code) != record['sha256'] or code != program.target(address, length)):
            raise ValueError('Sized canonical function qualification failed: ' + name)
        ranges.append((address & native.MASK, (address & native.MASK) + length, name))
    ranges.sort()
    if not ranges or len({row[2] for row in ranges}) != len(ranges) or any(
            a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
        raise ValueError('Scoped canonical function ranges overlap or repeat.')
    return ranges


def symbol_diagnostic(program, destination, functions):
    objects = [Path(configure.BUILD_DIR) / (source + '.o') for source, _ in build_manifest()]
    if any(not (ROOT / path).is_file() for path in objects) or configure.LD_FLAGS.count('-s') != 1:
        raise ValueError('Complete canonical objects and the expected strip flag are required.')
    flags = [flag for flag in configure.LD_FLAGS if flag != '-s']
    elf, binary = destination / 'canonical-symbols.elf', destination / 'canonical-symbols.exe'
    with (destination / 'link.log').open('xb') as log:
        subprocess.run(candidate_link_command(elf, destination / 'canonical-symbols.map',
                       Path(configure.LD_SCRIPT), objects, flags), cwd=ROOT,
                       stdout=log, stderr=log, check=True)
        subprocess.run([configure.CROSS + 'objcopy', '-O', 'binary', str(elf), str(binary)],
                       cwd=ROOT, stdout=log, stderr=log, check=True)
    ranges = qualify_diagnostic(program, elf.read_bytes(), binary.read_bytes(), functions)
    return ranges, dict(elf_sha256=sha(elf.read_bytes()), executable_sha256=sha(binary.read_bytes()),
                        object_count=len(objects), original_link_flags=configure.LD_FLAGS,
                        diagnostic_link_flags=flags, complete_canonical_image_equal=True)


def corpus_models(inventory):
    unresolved = inventory['MML_reference_audit']['unresolved_counts']
    if (inventory['unresolved_direct_model_files'] or inventory['LBD_unresolved_files']
            or inventory['rejected'] or any(unresolved.values())):
        raise ValueError('A partial or unresolved animation inventory cannot qualify the complete corpus.')
    planned = []
    for file in inventory['files']:
        data = Path(file['source']).read_bytes()
        if sha(data) != file['sha256'] or len(data) != file['bytes']:
            raise ValueError('Extracted asset changed during inventory: ' + file['path'])
        for item in file['models']:
            start, length = item['offset'], item['bytes']
            if start < 0 or length < 24 or start + length > len(data):
                raise ValueError('Model inventory extent exceeds its source file.')
            raw = data[start:start + length]
            frame = model.decode_first_frame(raw)
            if not 0 < frame.child_count < 256:
                raise ValueError('A model requires an unsupported zero/wrapping child count: ' + file['path'])
            planned.append((dict(source=file['path'], asset_sha256=file['sha256'],
                                 model_offset=start, model_bytes=length, model_sha256=sha(raw)), frame))
    if not planned or len(planned) != inventory['totals']['validated_MOM_instances']:
        raise ValueError('The complete model-instance corpus was not selected.')
    return planned


def equal_buffer(label, actual, expected):
    if actual != expected:
        differences = [index for index, (a, b) in enumerate(zip(actual, expected)) if a != b][:16]
        raise ValueError(label + ': buffer mismatch at ' + str(differences))


class Machine:
    """Closed original instruction graph, fresh CPU per model, no output stubs."""
    def __init__(self, program, ranges, globals_, mos_size, fault=None):
        import unicorn
        from unicorn import mips_const as reg
        self.unicorn, self.reg, self.program = unicorn, reg, program
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_MIPS, unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, 0x200000)
        self.cpu.mem_write(program.LOAD & native.MASK, program.ROM[0x800:])
        self.ranges, self.starts = ranges, [row[0] for row in ranges]
        self.entries, self.allocations, self.steps, self.fault_hits = Counter(), [], 0, 0
        self.fault, self.recent = fault, []
        self.saved = [getattr(reg, 'UC_MIPS_REG_S' + str(i)) for i in range(8)] + [reg.UC_MIPS_REG_FP]
        self.write_ranges = [(model.MANAGER, model.MANAGER + 0x100),
                             (model.POOL, model.POOL + model.POOL_SIZE + 0x80),
                             (model.ACTOR - 0x20, model.ACTOR + 0x160),
                             (native.STACK - 0x1000, native.STACK + 0x100)]
        self.write_ranges += [(address, address + 4) for address in globals_.values()]
        self.read_ranges = self.write_ranges + [
            (program.LOAD & native.MASK, (program.LOAD & native.MASK) + len(program.ROM) - 0x800),
            (model.MODEL - 0x20, model.MODEL + 0xE0),
            (model.PART_LIST - 0x20, model.PART_LIST + 0xE0),
            (model.DATA - 0x20, model.DATA + mos_size + 0x20), (model.SDK_TABLE, model.SDK_TABLE + 32)]
        if fault:
            address = fault['address'] & native.MASK
            if int.from_bytes(self.cpu.mem_read(address, 4), 'little') != fault['old']:
                raise ValueError('Fault control no longer identifies its original instruction.')
            self.cpu.mem_write(address, struct.pack('<I', fault['replacement']))
        self.cpu.hook_add(unicorn.UC_HOOK_CODE, self.code_hook)
        self.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE | unicorn.UC_HOOK_MEM_READ, self.access_hook)

    def code_hook(self, cpu, address, size, _):
        address &= native.MASK
        index = bisect_right(self.starts, address) - 1
        if index < 0 or address + size > self.ranges[index][1]:
            raise ValueError('Instruction execution left a qualified sized function: ' + hex(address))
        self.steps += 1
        self.recent = (self.recent + [hex(address)])[-12:]
        if self.fault and address == self.fault['address'] & native.MASK:
            self.fault_hits += 1
        if address == self.ranges[index][0]:
            name = self.ranges[index][2]
            self.entries[name] += 1
            if name == 'memory_allocate_mem':
                self.allocations.append(cpu.reg_read(self.reg.UC_MIPS_REG_A0))

    def access_hook(self, cpu, access, address, size, value, _):
        address &= native.MASK
        ranges = self.write_ranges if access == self.unicorn.UC_MEM_WRITE else self.read_ranges
        if not any(begin <= address and address + size <= end for begin, end in ranges):
            raise ValueError('Native data access left its guarded fixture: ' + hex(address))

    def call(self, name, *arguments):
        cpu, reg = self.cpu, self.reg
        cpu.mem_write(native.STACK - 0x1000, b'\xCD' * 0x1100)
        saved = [native.u32(0xA7000000 + i * 0x10301) for i in range(len(self.saved))]
        for register, value in zip(self.saved, saved):
            cpu.reg_write(register, value)
        for i in range(4):
            cpu.reg_write(getattr(reg, 'UC_MIPS_REG_A' + str(i)), arguments[i] if i < len(arguments) else 0)
        for register, value in ((reg.UC_MIPS_REG_SP, native.STACK),
                                (reg.UC_MIPS_REG_GP, heap.GP), (reg.UC_MIPS_REG_RA, native.END)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.program.symbols[name] & native.MASK, native.END, count=2000000)
        if (cpu.reg_read(reg.UC_MIPS_REG_PC) != native.END
                or cpu.reg_read(reg.UC_MIPS_REG_SP) != native.STACK
                or cpu.reg_read(reg.UC_MIPS_REG_GP) != heap.GP
                or cpu.reg_read(reg.UC_MIPS_REG_RA) != native.END
                or [cpu.reg_read(register) for register in self.saved] != saved):
            raise ValueError('Native call return, instruction budget or saved-register contract failed: ' + name)
        for address in (native.STACK - 0x1000, native.STACK + 0x40):
            equal_buffer('stack_red_zone', bytes(cpu.mem_read(address, 64)), b'\xCD' * 64)
        return cpu.reg_read(reg.UC_MIPS_REG_V0)


def run_case(program, ranges, globals_, frame, pattern, source, fault=None):
    machine = Machine(program, ranges, globals_, len(frame.mos), fault)
    report = dict(status='failed_bounded_actor_child_construction', source=source, pattern=pattern,
                  fault=fault, dependency_output_stubs=0)
    began = time.monotonic()
    try:
        reference = model.initial_pool(pattern)
        for name, address in (('manager', model.MANAGER), ('pool', model.POOL)):
            machine.cpu.mem_write(address, bytes(reference.buffers[name]))
        machine.call('memory_set_manager', reference.manager_pointer)
        machine.call('memory_set_lock', 0)
        reference.setup()
        machine.call('memory_setup_manager', 0)
        for name, address in (('manager', model.MANAGER), ('pool', model.POOL)):
            equal_buffer('setup_' + name, bytes(machine.cpu.mem_read(address, len(reference.buffers[name]))),
                         bytes(reference.buffers[name]))
        actor, object_model, part_list = model.descriptors(program.symbols, pattern)
        mos = model.filled(len(frame.mos) + 64, pattern, 223)
        mos[32:32 + len(frame.mos)] = frame.mos
        readonly = ((model.MODEL - 32, object_model), (model.PART_LIST - 32, part_list),
                    (model.DATA - 32, mos), (model.SDK_TABLE, model.SDK_MATRIX))
        machine.cpu.mem_write(model.ACTOR - 32, bytes(actor))
        for address, buffer in readonly:
            machine.cpu.mem_write(address, bytes(buffer))
        expected = model.construct_reference(reference, frame, actor, program.symbols['D_800878D4'],
                    model.rational_values(program.target(0x8006B684, 12)),
                    model.rational_values(program.target(0x8006B690, 12)))
        if machine.call('func_80065E1C', model.ACTOR) != 0:
            raise ValueError('Original child construction did not return success.')
        if machine.allocations != expected['requests']:
            raise ValueError('Native allocation order disagrees with the independent model.')
        equal_buffer('actor_and_guards', bytes(machine.cpu.mem_read(model.ACTOR - 32, len(actor))), expected['actor'])
        for name, address, label in (('manager', model.MANAGER, 'manager_and_guards'),
                                      ('pool', model.POOL, 'complete_pool_and_guards')):
            equal_buffer(label, bytes(machine.cpu.mem_read(address, len(reference.buffers[name]))),
                         bytes(reference.buffers[name]))
        for address, buffer in readonly:
            equal_buffer('readonly_fixture_' + hex(address), bytes(machine.cpu.mem_read(address, len(buffer))), bytes(buffer))
        for name, value in (('memory_set_manager', reference.manager_pointer), ('memory_set_lock', 0)):
            equal_buffer('allocator_global_' + name, bytes(machine.cpu.mem_read(globals_[name], 4)), struct.pack('<I', value))
        report.update(status='passed_bounded_actor_child_construction', child_count=frame.child_count,
                      children=expected['children'], script_order_type_bytes=expected['types'],
                      selected_child_index=expected['selected_index'], independent_full_buffer_model=True,
                      complete_actor_bytes_checked=len(actor), complete_manager_bytes_checked=0x100,
                      complete_pool_bytes_checked=model.POOL_SIZE + 0x80)
    except (ValueError, machine.unicorn.UcError) as error:
        report.update(error=str(error), recent_native_addresses=machine.recent)
    report.update(entered_original_functions=dict(machine.entries), allocation_sizes=machine.allocations,
                  instructions=machine.steps, changed_instruction_hits=machine.fault_hits,
                  elapsed_seconds=time.monotonic() - began)
    return report


def verify(layout, destination, edition_label):
    ninja = require_ninja()
    backend = {key: value for key, value in heap.backend_identity().items() if key in IDENTITY_KEYS}
    functions = json.loads(RANGES.read_text(encoding='utf-8'))['functions']
    before, dependencies = build_inputs(), dependency_hashes()
    program = native.load_program(functions)
    inventory = inspect_animations(layout)
    planned = corpus_models(inventory)
    ranges, diagnostic = symbol_diagnostic(program, destination, functions)
    write_json(destination / 'inventory.json', inventory)
    write_json(destination / 'symbol-diagnostic.json', diagnostic)
    completed, controls, totals = [], [], Counter()
    began = time.monotonic()
    for index, (source, frame) in enumerate(planned):
        for pattern in model.PATTERNS:
            name = 'model-' + str(index).zfill(3) + '-' + pattern
            report = run_case(program, ranges, heap.global_addresses(program), frame, pattern, source)
            write_json(destination / (name + '.json'), report)
            row = dict(case=name, passed=report['status'] == 'passed_bounded_actor_child_construction',
                       child_count=report.get('child_count', 0), allocations=len(report['allocation_sizes']),
                       model_sha256=source['model_sha256'], report_sha256=sha((destination / (name + '.json')).read_bytes()))
            completed.append(row)
            if not row['passed']:
                raise ValueError('Native construction failed; retained ' + name + '.json: ' + report.get('error', ''))
            totals.update(report['entered_original_functions'])
        if (index + 1) % 10 == 0 or index + 1 == len(planned):
            print(json.dumps(dict(models_completed=index + 1, planned_models=len(planned),
                                  memory_patterns=len(model.PATTERNS))), flush=True)
    source, frame = planned[0]
    for fault in FAULTS:
        name = 'fault-' + fault['name']
        report = run_case(program, ranges, heap.global_addresses(program), frame, 'distinct', source, fault)
        write_json(destination / (name + '.json'), report)
        if (report['status'] != 'failed_bounded_actor_child_construction'
                or not report['changed_instruction_hits'] or 'complete_pool_and_guards' not in report.get('error', '')):
            raise ValueError('Instruction fault was not detected by the full pool comparison: ' + name)
        controls.append(dict(fault, changed_instruction_hits=report['changed_instruction_hits'],
                        detection=report['error'], report_sha256=sha((destination / (name + '.json')).read_bytes())))
    # Re-read every selected asset and layout. No extraction is silently replaced during execution.
    if (sha(Path(inventory['layout']).read_bytes()) != inventory['layout_sha256']
            or any(sha(Path(file['source']).read_bytes()) != file['sha256'] for file in inventory['files'])
            or before != build_inputs() or dependencies != dependency_hashes()
            or ninja != require_ninja()
            or backend != {key: value for key, value in heap.backend_identity().items() if key in IDENTITY_KEYS}
            or native.load_program(functions).ROM != program.ROM):
        raise ValueError('Source, assets, backend or the complete canonical build changed during verification.')
    if set(totals) != {record['function'] for record in functions}:
        raise ValueError('The corpus did not enter every scoped original function.')
    report = dict(schema_version=1, status='passed_bounded_original_actor_child_construction',
        recorded_utc=datetime.now(timezone.utc).isoformat(), edition_label=edition_label,
        edition_label_is_user_supplied=True, original_model_instances=len(planned),
        distinct_model_contents=len({source['model_sha256'] for source, _ in planned}),
        memory_patterns=list(model.PATTERNS), positive_construction_executions=len(completed),
        children_constructed=sum(row['child_count'] for row in completed),
        native_allocation_calls=sum(row['allocations'] for row in completed),
        results=completed, negative_controls_detected=controls, executed_native_entry_counts=dict(totals),
        qualified_original_functions=functions, dependency_output_stubs=0, backend=backend, ninja=ninja,
        execution_profile=dict(fresh_cpu_per_model_and_pattern=True, ram_preserved_between_setup_calls=True,
                               uninterrupted_cpu_within_child_construction_graph=True),
        symbol_diagnostic=diagnostic, inventory_sha256=sha((destination / 'inventory.json').read_bytes()),
        layout_sha256=inventory['layout_sha256'], sdk_matrix_fixture_sha256=sha(model.SDK_MATRIX),
        canonical_sha256=sha(program.ROM), canonical_complete_image_equal=True,
        protected_build_input_sha256=before, producer_dependency_sha256=dependencies,
        all_game_build_inputs_preserved=True, original_behavior_modified=False, model_api_calls=0,
        new_C_bytes=0, new_NPC_callback_profiles=0, whole_feature_acceptances=0, whole_NPC_encounters_accepted=0,
        elapsed_seconds=time.monotonic() - began, goal_complete=False,
        scope='Every bounded model first frame in this extraction drives original enumeration, allocation, '
              'scene-node and transform constructors. Actor/model/list descriptors, native pool and SDK identity '
              'table are supplied fixtures. Full actor creation, resource/cache ownership, allocation failure, '
              'playback, rendering, natural encounters and PS1 timing remain open.')
    write_json(destination / 'report.json', report)
    print(json.dumps({key: report[key] for key in ('status', 'original_model_instances',
          'positive_construction_executions', 'children_constructed', 'native_allocation_calls')}), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', required=True, help='Your dumpsxiso extraction XML.')
    parser.add_argument('--output', required=True, help='Fresh directory within .decomp-lab.')
    parser.add_argument('--edition-label', default='unspecified', help='Provenance label only; not edition detection.')
    args = parser.parse_args(argv)
    created = False
    try:
        destination = output_directory(args.output)
        destination.mkdir(parents=True, exist_ok=False)
        created = True
        verify(Path(args.layout).resolve(), destination, args.edition_label)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, ET.ParseError) as error:
        if created:
            write_json(destination / 'failure.json', dict(status='failed_actor_child_verification',
                       error=str(error), goal_complete=False, whole_feature_acceptances=0))
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
