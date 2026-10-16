"""Check the shared collision API through a compiled, analysis-only C caller.

Original collision/decoder/SDK code executes with a checked native GTE bridge.
Constructed models do not establish natural scene or whole-feature parity.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as n
from tools import verify_collision as c
from tools import verify_scripted_ai as scripts
from tools.decomp_workbench import candidate_commands
from tools.compile_c import run_stages
from research.compiler.compare_function import elf_function
import configure

CALLER, REQUEST = 0x80180000, 0x1100
NAME = 'collision_api_invoke'
CONSUMER = ROOT / 'research/collision_api/consumer.c'
FUNCTIONS = json.loads((ROOT / 'docs/collision-function-ranges.json').read_bytes())


def new_output(path):
    output = Path(path).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if output == lab or not output.is_relative_to(lab) or output.exists():
        raise ValueError('Choose a fresh private evidence directory inside .decomp-lab.')
    return output


def initialized(case):
    data, args = c.model_fixture(**case)
    # The request is analysis-only. Its order is independently checked by the C
    # layout assertions; the original game still receives six ordinary args.
    struct.pack_into('<6I', data, REQUEST, args[0], args[4], args[5], args[2], args[1], args[3])
    return data, args


def expected(case, data, args, read_halfword):
    result, nearest, hit, height = c.primitive_model(case['polygons'], case['start'], case['end'], read_halfword)
    output = bytearray(data)
    struct.pack_into('<i', output, c.NEAREST, nearest)
    if hit is not None:
        c.pack_point(output, c.CONTACT, hit)
        if args[3]:
            struct.pack_into('<i', output, c.HEIGHT, height)
    return result, bytes(output)


def compile_caller(folder, legacy):
    folder.mkdir(exist_ok=False)
    obj, elf = folder / 'caller.o', folder / 'caller.elf'
    commands = candidate_commands('src/base/object_math.c', CONSUMER, obj)
    if legacy:
        commands[0].insert(-1, '-DLSD_COLLISION_LEGACY_DECLARATION')
    script = folder / 'caller.ld'
    script.write_text('_gp = 0x8008a808; func_8001F8B8 = 0x8001f8b8;\n'
        'SECTIONS { .text 0x80180000 : SUBALIGN(4) { *(.text) } '
        '/DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n')
    with (folder / 'compiler.log').open('xb') as log:
        previous = os.dup(2)
        try:
            os.dup2(log.fileno(), 2)
            assert run_stages(commands) == b''
        finally:
            os.dup2(previous, 2)
            os.close(previous)
        subprocess.run([configure.CROSS + 'ld', '-EL', '-nostdlib', '-T', str(script), '-o', str(elf), str(obj)],
                       check=True, stdout=log, stderr=log)
    code, qualification = elf_function(elf.read_bytes(), NAME, CALLER)
    if not qualification['function_covers_complete_section'] or qualification['other_sized_functions']:
        raise ValueError('The analysis caller must occupy its complete single-function section.')
    return code, (folder / 'compiler.log').read_text()


class Machine(c.CollisionMachine):
    def __init__(self, bridge, caller_code, patches=None):
        self.changed_hits, self.changed = Counter(), set()
        record = dict(function=NAME, address=hex(CALLER), bytes=len(caller_code),
                      sha256=hashlib.sha256(caller_code).hexdigest())
        super().__init__(bridge, FUNCTIONS + [record], patches)
        self.cpu.mem_write(CALLER & n.MASK, caller_code)
        for address, word in (patches or {}).items():
            self.cpu.mem_write(address & n.MASK, word)
            self.changed.add(address & n.MASK)

    def hook(self, cpu, address, size, unused):
        if address & n.MASK in self.changed:
            self.changed_hits[address & n.MASK] += 1
        super().hook(cpu, address, size, unused)

    def run(self, case, data, args, via_caller):
        self.changed_hits.clear()
        self.adapter.reset()
        self.cpu.mem_write(c.BUFFER, bytes(data))
        actual = self.invoke(NAME if via_caller else 'func_8001F8B8',
            (c.pointer(REQUEST, case.get('segment', 0)),) if via_caller else args)
        if self.cpu.reg_read(n.reg.UC_MIPS_REG_GP) != 0x8008a808:
            raise ValueError('Collision caller changed GP.')
        return actual, bytes(self.cpu.mem_read(c.BUFFER, c.BUFFER_BYTES))


def controls(bridge, caller_code, read_halfword):
    triangle = ((-1024, -1024, 0), (1024, -1024, 0), (-1024, 1024, 0))
    case = dict(polygons=(triangle,), start=(-512, -512, -1000), end=(-512, -512, 1000))
    data, args = initialized(case)
    model = expected(case, data, args, read_halfword)
    if model[0] != 1:
        raise ValueError('The fault witness must hit the original primitive.')
    rows = []
    for field, offset, changed in [('height_to_nearest', 20, 16), ('nearest_to_height', 16, 20),
                                   ('start_to_end', 4, 8), ('hit_to_start', 12, 4)]:
        offsets = [i for i in range(0, len(caller_code), 4) if
            (word := struct.unpack_from('<I', caller_code, i)[0]) >> 26 == 35
            and (word >> 21) & 31 != 29 and word & 0xffff == offset]
        if len(offsets) != 1:
            raise ValueError('The caller field load is not unique: ' + field)
        pc = CALLER + offsets[0]
        original, = struct.unpack_from('<I', caller_code, offsets[0])
        fault = (original & 0xffff0000) | changed
        broken = Machine(bridge, caller_code, {pc: struct.pack('<I', fault)})
        actual = broken.run(case, data, args, True)
        hits = broken.changed_hits[pc & n.MASK]
        if actual == model or not hits:
            raise ValueError('Caller fault must execute and change a buffer or return: ' + field)
        rows.append(dict(kind=field, address=hex(pc), original_word=hex(original), changed_word=hex(fault),
            changed_instruction_hits=hits, wrong_return=actual[0] != model[0],
            wrong_buffer=actual[1] != model[1], detecting_case=case))
    return rows


def verify(output, executable, runtime):
    output = new_output(output)
    paths = n.evidence_dependencies('research/collision_api/verify.py', 'research/collision_api/consumer.c',
        'research/collision_api/abi_checks.h', 'tools/verify_collision.py', 'tools/verify_render_gte.py',
        'tools/verify_scripted_ai.py', 'tools/compile_c.py', 'tools/decomp_workbench.py',
        'research/compiler/compare_function.py', 'docs/collision-function-ranges.json',
        'src/file/tmd_prim.h', 'src/file/tmd_prim_geom.c', 'src/base/object_math.h',
        'include/common.h', 'tools/nymashock_gte_bridge.cs')
    preserved = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    n.initialize_backend(n.load_program(FUNCTIONS))
    backend = scripts.backend_identity()
    executable = Path(executable).resolve(strict=True)
    bridge_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    legacy_code, legacy_log = compile_caller(output / 'legacy-declaration', True)
    caller_code, typed_log = compile_caller(output / 'shared-header', False)
    if 'warning' not in legacy_log.lower() or 'arg 4' not in legacy_log or 'warning' in typed_log.lower():
        raise ValueError('Expected a legacy height-pointer diagnostic and a clean shared-header caller.')
    abi_assertions = len(re.findall(r'^COLLISION_ABI_CHECK\(', (ROOT / 'research/collision_api/abi_checks.h').read_text(), re.M))
    if abi_assertions != 21:
        raise ValueError('Review the declared target ABI assertion count.')
    n.h.symbols[NAME] = CALLER  # Analysis-only entry, added solely to this VM.
    read_halfword = lambda address: struct.unpack('<h', n.h.target(address, 2))[0]
    bridge = c.CollisionBridge(executable, runtime, output / 'gte.log')
    digests = {name: hashlib.sha256() for name in ('original', 'typed_caller')}
    cases, duplicates, entries, input_digest = 0, 0, Counter(), hashlib.sha256()
    seen = set()
    try:
        original, typed = Machine(bridge, caller_code), Machine(bridge, caller_code)
        for case in c.collision_cases():
            data, args = initialized(case)
            key = bytes(data) + struct.pack('<6I', *args)
            identity = hashlib.sha256(key).hexdigest()
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
            model = expected(case, data, args, read_halfword)
            for name, machine, via_caller in [('original', original, False), ('typed_caller', typed, True)]:
                actual = machine.run(case, data, args, via_caller)
                if actual != model:
                    (output / 'failure.json').write_text(json.dumps(dict(stage=name, case=case,
                        actual_return=actual[0], expected_return=model[0], differing_buffer_offsets=[
                            i for i, (a, b) in enumerate(zip(actual[1], model[1])) if a != b]), indent=2) + '\n')
                    raise ValueError('Original collision or typed caller differs from the independent model.')
                digests[name].update(struct.pack('<I', actual[0]) + actual[1])
            input_digest.update(len(key).to_bytes(4, 'little') + key)
            cases += 1
            if cases % 500 == 0:
                print('Collision API distinct inputs passed:', cases, flush=True)
        entries.update(original.entries)
        entries.update(typed.entries)
        commands, leading = bridge.count, bridge.lz_count
        faults = controls(bridge, caller_code, read_halfword)
    finally:
        bridge.close()
    if (scripts.backend_identity() != backend or hashlib.sha256(executable.read_bytes()).hexdigest() != bridge_hash
            or (ROOT / configure.ROM).read_bytes() != n.h.ROM or (ROOT / configure.EXE).read_bytes() != n.h.ROM
            or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in preserved.items())):
        raise ValueError('Source/build/backend inputs changed during the API comparison.')
    if len({digest.hexdigest() for digest in digests.values()}) != 1:
        raise ValueError('Direct and compiled-caller buffer digests differ.')
    report = dict(status='passed_bounded_collision_api_comparison', distinct_initialized_inputs=cases,
        positive_executions=cases * 2, duplicate_inputs_skipped=duplicates, existing_collision_domain_reused=True,
        analysis_caller=dict(address=hex(CALLER), bytes=len(caller_code), sha256=hashlib.sha256(caller_code).hexdigest(),
            included_in_game=False, legacy_and_typed_code_equal=legacy_code == caller_code,
            legacy_height_pointer_warning=True, typed_caller_warning_free=True, target_ABI_assertions=abi_assertions),
        native_functions=FUNCTIONS, executed_native_entry_counts=dict(entries),
        original_and_typed_output_sha256={name: digest.hexdigest() for name, digest in digests.items()},
        initialized_inputs_sha256=input_digest.hexdigest(), negative_controls=faults, dependency_output_stubs=0,
        positive_GTE_commands=commands, positive_leading_sign_bit_queries=leading,
        control_GTE_commands=bridge.count - commands, control_leading_sign_bit_queries=bridge.lz_count - leading,
        bridge_executable_sha256=bridge_hash, backend_identity=backend,
        producer_dependencies=[dict(path=path.relative_to(ROOT).as_posix(), sha256=digest) for path, digest in preserved.items()],
        source_promoted=False, new_C_bytes=0, new_bounded_NPC_callbacks=0, original_game_behavior_modified=False,
        whole_feature_groups_accepted=0, model_API_calls=0,
        scope='Compiled typed C caller and direct original primitive query on constructed models. '
              'Full model/request/output buffers, return, saved registers, GP and lower stack guard checked; '
              'real decoder/SDK and native GTE/leading-bit operations. No scene-node caller execution, natural '
              'construction, argument-output aliasing, complete collision domain or PS1 timing acceptance.')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--bridge', required=True, type=Path)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    report = verify(args.output, args.bridge, args.runtime)
    print(json.dumps({key: report[key] for key in ('status', 'distinct_initialized_inputs', 'positive_executions')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
