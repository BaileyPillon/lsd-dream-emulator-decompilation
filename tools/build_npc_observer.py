"""Build an optional NPC observer from a pinned, already built PS1 core.

Run in Linux/WSL after the documented BizHawk 2.11.1 native build. Only a new
adapter object is compiled; the supplied checkout, cached objects and core are
preserved. This analysis build is separate from the game's matching C build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import record_file

UPSTREAM = 'bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5'
MEDNAFEN = '382ff1b8d293c9a862497706808cbb79b2cecbfb'
OBSERVER = ROOT / 'research/runtime_state/npc_entry_observer.h'
SOURCE_SHA256 = {
    'shock.cpp': '70d0193ac5081b486ae52b3930a5c4e60ddef0481c4bb9c495d65ae3918d94ea',
    'mednafen/src/psx/cpu.cpp': '4ddd7b0192db03ed1ce81bb9b83bd92a14a0c64e6e3c1633d05cf0e7b127aad7',
    'mednafen/src/psx/cpu.h': '9705356dbb793421017daf1755c3f3838ff5b093d6b1620410fd5c23a60c014a',
}
MEDIA_SHA256 = {
    'd47e109d5d33558a5cf5f55b5b07886289b61268e45d329f5f8537fd62617268': 'distributed source',
    'e35995cf92baabd13c4bb9216c9c2ef7405db38202d0aff0d6fb55d9e06d7c6a': 'complete-record initialization patch',
}
EXPORTS = ('LsdConfigureNpcTrace', 'LsdBeginNpcTraceFrame', 'LsdGetNpcTraceCount',
           'LsdGetNpcTraceTotal', 'LsdGetNpcTraceOverflow', 'LsdGetNpcTraceEvents', 'LsdDisableNpcTrace')
VARIABLES = ('CC', 'CXXFLAGS', 'CXXFLAGS_RELEASE', 'LDFLAGS', 'LDFLAGS_RELEASE',
             'CCFLAGS', 'CCFLAGS_RELEASE', 'OBJS', 'EMULIBC_OBJS', 'EXTRA_LIBS', 'TARGET_RELEASE')


def parse_make_variables(text):
    values = {}
    for line in text.splitlines():
        key, separator, value = line.partition(' =')
        if separator and key in VARIABLES:
            require(key not in values, 'Make reported a repeated build variable.')
            values[key] = value.lstrip()
    require(set(values) == set(VARIABLES), 'Make did not report the complete native build configuration.')
    require(values['CC'] and values['OBJS'] and values['TARGET_RELEASE'], 'Incomplete cached native build.')
    return values


def artifact(path):
    item = record_file(path)
    return dict(file=Path(path).name, bytes=item['bytes'], sha256=item['sha256'])


def build(source_root, output):
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
    inputs = [Path(__file__).resolve(), OBSERVER, Path(settings['CC']), Path(clang).resolve(),
              nyma / 'shock.cpp', nyma / 'cdrom.cpp', nyma / 'common.mak', nyma / 'shock.mak',
              source / 'waterbox/common.mak', source / 'waterbox/linkscript.T',
              nyma / 'mednafen/src/psx/cpu.cpp', nyma / 'mednafen/src/psx/cpu.h',
              Path(settings['TARGET_RELEASE']), *map(Path, objects),
              *map(Path, shlex.split(settings['EMULIBC_OBJS']))]
    # Deduplicate the adapter object while preserving a stable manifest order.
    inputs = list(dict.fromkeys(path.resolve(strict=True) for path in inputs))
    before = [record_file(path) for path in inputs]
    output.mkdir(parents=True, exist_ok=False)
    header = output / OBSERVER.name
    shutil.copyfile(OBSERVER, header)
    adapter = output / 'observer-adapter.cpp'
    adapter.write_bytes((nyma / 'shock.cpp').read_bytes() + b'\n#include "npc_entry_observer.h"\n')
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
    require(all(any(line.split()[-1] == name for line in symbols.splitlines() if line.split()) for name in EXPORTS),
            'The linked observer is missing a required export.')
    compressed = output / 'shock.wbx.zst'
    subprocess.run(['zstd', '-q', '-T1', str(core), '-o', str(compressed)], check=True)
    require([record_file(path) for path in inputs] == before, 'A supplied source, cached object or build input changed.')
    require(header.read_bytes() == OBSERVER.read_bytes(), 'Observer source changed during the build.')
    profile = dict(schema_version=1, status='built_separate_NPC_observer_core',
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
        exported_functions=list(EXPORTS), producer_sha256=record_file(Path(__file__).resolve())['sha256'])
    write_json(output / 'profile.json', profile)
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True, help='Ready pinned native BizHawk checkout, without spaces.')
    parser.add_argument('--output', type=Path, required=True, help='New observer build directory outside that checkout.')
    args = parser.parse_args(argv)
    profile = build(args.source_root, args.output)
    print(json.dumps(dict(status=profile['status'], core=profile['core'], runtime_verified=False)))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
