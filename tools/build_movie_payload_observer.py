"""Build a separate bounded movie-payload observer from pinned cached objects."""
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
from tools.build_npc_observer import (UPSTREAM, MEDNAFEN, SOURCE_SHA256, MEDIA_SHA256,
    VARIABLES, parse_make_variables, artifact)
from tools.runtime_inputs import record_file
from tools.replay_cold_start_headless import require, write_json

ENTRY = ROOT / 'research/runtime_state/dispatch_entry_observer.h'
PAYLOAD = ROOT / 'research/runtime_state/movie_payload_observer.h'
EXPORTS = ('LsdStartMoviePayloadTrace', 'LsdBeginMoviePayloadFrame', 'LsdGetMoviePayloadCount',
    'LsdGetMoviePayloadTotal', 'LsdGetMoviePayloadErrors', 'LsdGetMoviePayloadOverflow',
    'LsdGetMoviePayloadDataBytes', 'LsdGetMoviePayloadEvents', 'LsdGetMoviePayloadData',
    'LsdGetMoviePayloadCallbacks', 'LsdGetMoviePayloadPendingVlc', 'LsdGetMoviePayloadPendingBuffers',
    'LsdResetDispatchTrace', 'LsdAddDispatchTarget', 'LsdConfigureDispatchWords',
    'LsdGetDispatchCount', 'LsdGetDispatchTotal', 'LsdGetDispatchOverflow',
    'LsdGetDispatchEvents', 'LsdDisableDispatchTrace')


def build(source_root, output):
    output = Path(output).resolve()
    require(sys.platform == 'linux', 'Build with the existing pinned WSL/Linux toolchain.')
    require(not output.exists(), 'Use a new output directory; existing studies remain intact.')
    source = Path(source_root).resolve(strict=True)
    require(not any(char.isspace() for char in str(source)), 'The native source path must not contain whitespace.')
    require(not output.is_relative_to(source), 'Keep study output outside the native checkout.')
    nyma = source / 'waterbox/nyma'
    git = lambda *args: subprocess.check_output(['git', *args], cwd=source, text=True).strip()
    require(git('rev-parse', 'HEAD') == UPSTREAM, 'The supplied native revision is not pinned BizHawk 2.11.1.')
    require(set(git('diff', 'HEAD', '--name-only', '--ignore-submodules=untracked').splitlines()) <= {'waterbox/nyma/cdrom.cpp'},
        'The native checkout has unsupported source changes.')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=nyma / 'mednafen', text=True).strip() == MEDNAFEN,
        'The Mednafen revision is not pinned.')
    require(subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=nyma / 'mednafen').returncode == 0,
        'The original native CPU source must remain unchanged.')
    source_records = {name: record_file(nyma / name) for name in SOURCE_SHA256}
    require(all(row['sha256'] == SOURCE_SHA256[name] for name, row in source_records.items()),
        'The qualified adapter or CPU source differs.')
    media = record_file(nyma / 'cdrom.cpp')
    require(media['sha256'] in MEDIA_SHA256, 'The media adapter is unqualified.')
    require(subprocess.run(['make', '-q', '-f', 'shock.mak', 'release'], cwd=nyma).returncode == 0,
        'Reuse the complete current cached release objects.')
    settings = parse_make_variables(subprocess.check_output(['make', '-s', '-f', 'shock.mak',
        *('print-' + name for name in VARIABLES)], cwd=nyma, text=True))
    objects = shlex.split(settings['OBJS'])
    old_adapter = str(nyma / 'obj/release/shock.cpp.o')
    require(objects.count(old_adapter) == 1 and all(Path(path).is_file() for path in objects),
        'The cached native object set is incomplete.')
    env = dict(os.environ, PATH=str(source / 'tools') + ':/usr/bin:/bin')
    clang = shutil.which('clang', path=env['PATH'])
    require(clang is not None, 'The pinned Clang 18 compiler is unavailable.')
    compiler = subprocess.check_output([clang, '--version'], text=True, env=env)
    require('clang version 18.' in compiler, 'Use the existing Clang 18 toolchain.')
    headers = (ENTRY, PAYLOAD)
    inputs = [Path(__file__).resolve(), ROOT / 'tools/build_npc_observer.py', *headers,
        Path(settings['CC']), Path(clang).resolve(), nyma / 'shock.cpp', nyma / 'cdrom.cpp',
        nyma / 'common.mak', nyma / 'shock.mak', source / 'waterbox/common.mak', source / 'waterbox/linkscript.T',
        nyma / 'mednafen/src/psx/cpu.cpp', nyma / 'mednafen/src/psx/cpu.h', Path(settings['TARGET_RELEASE']),
        *map(Path, objects), *map(Path, shlex.split(settings['EMULIBC_OBJS']))]
    inputs = list(dict.fromkeys(path.resolve(strict=True) for path in inputs))
    before = [record_file(path) for path in inputs]
    output.mkdir(parents=True, exist_ok=False)
    for header in headers:
        shutil.copyfile(header, output / header.name)
    adapter, obj, core = output / 'observer-adapter.cpp', output / 'observer-adapter.o', output / 'shock.wbx'
    adapter.write_bytes((nyma / 'shock.cpp').read_bytes() + b'\n#include "movie_payload_observer.h"\n')
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
    require(set(EXPORTS) <= {line.split()[-1] for line in symbols.splitlines() if line.split()},
        'The observer lacks a required export.')
    compressed = output / 'shock.wbx.zst'
    subprocess.run(['zstd', '-q', '-T1', str(core), '-o', str(compressed)], check=True)
    require([record_file(path) for path in inputs] == before, 'A cached native input changed during the build.')
    require(all((output / header.name).read_bytes() == header.read_bytes() for header in headers),
        'A movie-observer header changed during the build.')
    profile = dict(schema_version=1, status='built_separate_movie_payload_observer_core', upstream_commit=UPSTREAM,
        mednafen_commit=MEDNAFEN, compiler_version=compiler.strip(), compile_command=compile_command,
        link_command=link_command, inputs=before, core=artifact(core), compressed_core=artifact(compressed),
        adapter=artifact(adapter), object=artifact(obj), original_adapter_sha256=source_records['shock.cpp']['sha256'],
        media_adapter=MEDIA_SHA256[media['sha256']], media_adapter_sha256=media['sha256'],
        entry_header_sha256=record_file(ENTRY)['sha256'], movie_header_sha256=record_file(PAYLOAD)['sha256'],
        producer_sha256=record_file(Path(__file__).resolve())['sha256'], exported_functions=list(EXPORTS),
        movie_payload_protocol=1, event_bytes=172, frame_event_limit=16, frame_payload_limit_bytes=1024**2,
        complete_encoded_input_at_VLC_entry=True, complete_RLE_at_VLC_return_and_MDEC_input_entry=True,
        full_GPU_presentation_not_observed=True, input_files_preserved=True, original_CPU_source_modified=False,
        original_game_RAM_written_by_observer=False, supplied_runtime_modified=False,
        observer_uses_existing_DebugMode_hook=True, game_inputs_loaded=False, runtime_verified=False,
        build_scope='One separate adapter object linked with pinned cached native objects; not a fresh full-core rebuild.')
    write_json(output / 'profile.json', profile)
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(build(args.source_root, args.output)['status'])
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
