"""Build a separate original-method observer without changing NPC profiles.

The native provenance/build checks intentionally preserve the qualified NPC
builder's existing source identity; both builders share its read-only helpers.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_npc_observer import UPSTREAM, MEDNAFEN, SOURCE_SHA256, MEDIA_SHA256, VARIABLES, parse_make_variables, artifact
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import record_file
from tools.collision_calls import EXPORTS as COLLISION_EXPORTS,ORDINAL_EXPORTS as COLLISION_ORDINAL_EXPORTS,EVENT_BYTES as COLLISION_EVENT_BYTES,FRAME_BYTES as COLLISION_FRAME_BYTES,FUNCTIONS as COLLISION_FUNCTIONS
OBSERVER = ROOT / 'research/runtime_state/dispatch_entry_observer.h'
FLOW_OBSERVER = ROOT / 'research/runtime_state/dispatch_flow_observer.h'
RETURN_OBSERVER = ROOT / 'research/runtime_state/dispatch_return_observer.h'
SDK_OBSERVER = ROOT / 'research/runtime_state/sdk_read_observer.h'
COLLISION_OBSERVER = ROOT / 'research/runtime_state/collision_call_observer.h'
SDK_EXPORTS = ('LsdResetSdkReads','LsdAddSdkReadTarget','LsdStartSdkReads','LsdBeginSdkReadFrame',
    'LsdGetSdkReadCount','LsdGetSdkReadTotal','LsdGetSdkReadEntries','LsdGetSdkReadOverflow',
    'LsdGetSdkReadPending','LsdGetSdkReadMaxDepth','LsdGetSdkReadTransfer','LsdGetSdkReadCompletions',
    'LsdGetSdkReadFailures','LsdGetSdkReadUnassociated','LsdGetSdkReadOverlaps',
    'LsdGetSdkReadEvents','LsdGetSdkReadData','LsdGetSdkReadDataBytes')
RETURN_EXPORTS = ('LsdResetDispatchReturns','LsdConfigureDispatchReturns','LsdConfigureDispatchReturnIO','LsdStartDispatchReturns',
    'LsdBeginDispatchReturnFrame','LsdGetDispatchReturnCount','LsdGetDispatchReturnTotal',
    'LsdGetDispatchReturnEntries','LsdGetDispatchReturnOverflow','LsdGetDispatchReturnMismatches',
    'LsdGetDispatchReturnPending','LsdGetDispatchReturnMaxDepth','LsdGetDispatchReturnEvents',
    'LsdGetDispatchReturnData','LsdGetDispatchReturnDataBytes')
FLOW_EXPORTS = ('LsdResetDispatchFlow', 'LsdAddDispatchFlowSite', 'LsdStartDispatchFlow',
    'LsdBeginDispatchFlowFrame', 'LsdGetDispatchFlowCount', 'LsdGetDispatchFlowTotal',
    'LsdGetDispatchFlowOverflow', 'LsdGetDispatchFlowEvents')
EXPORTS = ('LsdResetDispatchTrace', 'LsdAddDispatchTarget', 'LsdConfigureDispatchWords',
    'LsdStartDispatchTrace', 'LsdBeginDispatchFrame', 'LsdGetDispatchCount',
    'LsdGetDispatchTotal', 'LsdGetDispatchOverflow', 'LsdGetDispatchEvents', 'LsdDisableDispatchTrace')


def build(source_root, output, *, flow=False, returns=False, sdk_reads=False, collision_calls=False):
    output = Path(output).resolve()
    require(not output.exists(), 'Choose a new output directory; existing builds are preserved.')
    require(sys.platform == 'linux', 'Build the native observer in Linux/WSL.')
    source = Path(source_root).resolve(strict=True)
    require(not any(char.isspace() for char in str(source)), 'The supplied native build path must not contain whitespace.')
    require(not output.is_relative_to(source), 'Keep observer output outside the supplied native checkout.')
    nyma = source / 'waterbox/nyma'
    git = lambda *args: subprocess.check_output(['git', *args], cwd=source, text=True).strip()
    require(git('rev-parse', 'HEAD') == UPSTREAM, 'Use the pinned BizHawk 2.11.1 source revision.')
    changes = set(git('diff', 'HEAD', '--name-only', '--ignore-submodules=untracked').splitlines())
    require(changes <= {'waterbox/nyma/cdrom.cpp'}, 'The supplied checkout contains unsupported tracked source changes.')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=nyma / 'mednafen', text=True).strip() == MEDNAFEN,
            'Use the pinned Mednafen submodule.')
    require(subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=nyma / 'mednafen').returncode == 0,
            'Preserve the pinned native CPU source.')
    source_records = {name: record_file(nyma / name) for name in SOURCE_SHA256}
    require(all(source_records[name]['sha256'] == digest for name, digest in SOURCE_SHA256.items()),
            'The adapter or CPU source differs from the qualified source.')
    media = record_file(nyma / 'cdrom.cpp')
    require(media['sha256'] in MEDIA_SHA256, 'The media adapter is neither the pinned source nor the documented patch.')
    require(subprocess.run(['make', '-q', '-f', 'shock.mak', 'release'], cwd=nyma).returncode == 0,
            'Build the supplied native source first; its cached release target is absent or stale.')
    text = subprocess.check_output(['make', '-s', '-f', 'shock.mak',
                                    *('print-' + name for name in VARIABLES)], cwd=nyma, text=True)
    settings = parse_make_variables(text)
    objects = shlex.split(settings['OBJS'])
    old_adapter = str(nyma / 'obj/release/shock.cpp.o')
    require(objects.count(old_adapter) == 1 and all(Path(path).is_file() for path in objects),
            'The cached object set is incomplete or has an unexpected adapter path.')
    env = dict(os.environ, PATH=str(source / 'tools') + ':/usr/bin:/bin')
    clang = shutil.which('clang', path=env['PATH'])
    require(clang is not None, 'Clang 18 is required by the pinned Waterbox build.')
    compiler_version = subprocess.check_output([clang, '--version'], text=True, env=env)
    require('clang version 18.' in compiler_version, 'Use Clang 18 with the pinned native objects.')
    require(not collision_calls or not (flow or returns or sdk_reads),'Collision snapshots use a separate entry-only observer.')
    returns = returns or sdk_reads
    flow = flow or returns
    headers = (OBSERVER, FLOW_OBSERVER, RETURN_OBSERVER) if returns else (OBSERVER, FLOW_OBSERVER) if flow else (OBSERVER,)
    exports = EXPORTS + (FLOW_EXPORTS if flow else ()) + (RETURN_EXPORTS if returns else ())
    if sdk_reads:
        headers += (SDK_OBSERVER,)
        exports += SDK_EXPORTS
    if collision_calls:
        headers += (COLLISION_OBSERVER,)
        exports += COLLISION_EXPORTS + COLLISION_ORDINAL_EXPORTS
    inputs = [Path(__file__).resolve(), ROOT / "tools/build_npc_observer.py", *headers, Path(settings['CC']), Path(clang).resolve(),
              nyma / 'shock.cpp', nyma / 'cdrom.cpp', nyma / 'common.mak', nyma / 'shock.mak',
              source / 'waterbox/common.mak', source / 'waterbox/linkscript.T',
              nyma / 'mednafen/src/psx/cpu.cpp', nyma / 'mednafen/src/psx/cpu.h',
              Path(settings['TARGET_RELEASE']), *map(Path, objects),
              *map(Path, shlex.split(settings['EMULIBC_OBJS']))]
    if collision_calls:
        inputs.append(ROOT / 'tools/collision_calls.py')
    # Deduplicate the adapter object while preserving a stable manifest order.
    inputs = list(dict.fromkeys(path.resolve(strict=True) for path in inputs))
    before = [record_file(path) for path in inputs]
    output.mkdir(parents=True, exist_ok=False)
    for source_header in headers:
        shutil.copyfile(source_header, output / source_header.name)
    header = output / OBSERVER.name
    adapter = output / 'observer-adapter.cpp'
    include = COLLISION_OBSERVER.name if collision_calls else SDK_OBSERVER.name if sdk_reads else RETURN_OBSERVER.name if returns else FLOW_OBSERVER.name if flow else OBSERVER.name
    adapter.write_bytes((nyma / 'shock.cpp').read_bytes() + ('\n#include "' + include + '"\n').encode('ascii'))
    obj, core = output / 'observer-adapter.o', output / 'shock.wbx'
    compile_command = [settings['CC'], '-c', '-o', str(obj), str(adapter), '-I' + str(nyma),
                       *shlex.split(settings['CXXFLAGS']), *shlex.split(settings['CXXFLAGS_RELEASE'])]
    link_objects = [str(obj) if path == old_adapter else path for path in objects]
    link_command = [settings['CC'], '-o', str(core), *shlex.split(settings['LDFLAGS']),
                    *shlex.split(settings['LDFLAGS_RELEASE']), *shlex.split(settings['CCFLAGS']),
                    *shlex.split(settings['CCFLAGS_RELEASE']), *link_objects,
                    *shlex.split(settings['EMULIBC_OBJS']), *shlex.split(settings['EXTRA_LIBS'])]
    with (output / 'build.log').open('xb') as log:
        subprocess.run(compile_command, cwd=nyma, env=env, stdout=log, stderr=log, check=True)
        subprocess.run(link_command, cwd=nyma, env=env, stdout=log, stderr=log, check=True)
    symbols = subprocess.check_output(['nm', '--defined-only', str(core)], text=True)
    require(all(any(line.split()[-1] == name for line in symbols.splitlines() if line.split()) for name in exports),
            'The linked observer is missing a required export.')
    compressed = output / 'shock.wbx.zst'
    subprocess.run(['zstd', '-q', '-T1', str(core), '-o', str(compressed)], check=True)
    require([record_file(path) for path in inputs] == before, 'A supplied source, cached object or build input changed.')
    require(all((output / source_header.name).read_bytes() == source_header.read_bytes() for source_header in headers),
            'Observer source changed during the build.')
    profile = dict(schema_version=1, status='built_separate_dispatch_observer_core',
        upstream_commit=UPSTREAM, mednafen_commit=MEDNAFEN,
        observer_header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
        original_adapter_sha256=source_records['shock.cpp']['sha256'],
        media_adapter=MEDIA_SHA256[media['sha256']], media_adapter_sha256=media['sha256'],
        compiler_version=compiler_version.strip(), compile_command=compile_command, link_command=link_command,
        core=artifact(core), compressed_core=artifact(compressed), adapter=artifact(adapter),
        inputs=before, input_files_preserved=True, existing_CPU_source_modified=False,
        supplied_runtime_modified=False, game_inputs_loaded=False, runtime_verified=False,
        build_scope='One new adapter object linked with the recorded pinned cached native objects; not a fresh full-core rebuild.',
        observer_uses_existing_DebugMode_hook=True, original_game_RAM_written_by_observer=False,
        exported_functions=list(exports), observer_mode='method_entries',
        producer_sha256=record_file(Path(__file__).resolve())['sha256'])
    if flow:
        profile.update(flow_protocol=1, flow_event_bytes=664, flow_history_instructions=16,
            flow_header_sha256=record_file(FLOW_OBSERVER)['sha256'])
    if returns:
        profile.update(return_protocol=1,return_event_bytes=600,return_frame_payload_bytes=8*1024*1024,
            return_header_sha256=record_file(RETURN_OBSERVER)['sha256'])
    if sdk_reads:
        profile.update(sdk_read_protocol=1,sdk_read_event_bytes=464,sdk_read_frame_payload_bytes=32*1024*1024,
            sdk_read_header_sha256=record_file(SDK_OBSERVER)['sha256'])
    if collision_calls:
        profile.update(collision_call_protocol=1,collision_call_event_bytes=COLLISION_EVENT_BYTES,
            collision_call_frame_payload_bytes=COLLISION_FRAME_BYTES,
            collision_call_header_sha256=record_file(COLLISION_OBSERVER)['sha256'],
            collision_call_ordinal_selection=True,
            collision_call_indirect_entry_context=True,
            collision_call_functions={name:dict(pc=pc,bytes=length) for name,(pc,length) in COLLISION_FUNCTIONS.items()})
    write_json(output / 'profile.json', profile)
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--flow', action='store_true', help='Add read-only caller load-chain context; keep the entry-only core separate.')
    parser.add_argument('--returns', action='store_true', help='Add original returns and bounded read buffers; implies --flow.')
    parser.add_argument('--sdk-reads', action='store_true', help='Observe original SDK requests, polling and completed RAM; implies --returns.')
    parser.add_argument('--collision-calls',action='store_true',help='Add separate sampled collision entry/return RAM and architectural registers.')
    args = parser.parse_args(argv)
    try:
        profile = build(args.source_root, args.output, flow=args.flow, returns=args.returns, sdk_reads=args.sdk_reads,collision_calls=args.collision_calls)
        print(profile['status'])
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
