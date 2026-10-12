"""Compare recorded emulator outputs; archive timestamps are not emulated state."""

import argparse
from array import array
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import wave
import zipfile

try:
    from .runtime_inputs import compare_inputs
except ImportError:
    from runtime_inputs import compare_inputs


def byte_comparison(original, rebuilt):
    return {"equal": original == rebuilt, "original_bytes": len(original),
            "rebuilt_bytes": len(rebuilt),
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "rebuilt_sha256": hashlib.sha256(rebuilt).hexdigest()}


def compare_state(original, rebuilt):
    with zipfile.ZipFile(original) as before, zipfile.ZipFile(rebuilt) as after:
        original_names, rebuilt_names = before.namelist(), after.namelist()
        if "Core.bin.zst" not in original_names or "Core.bin.zst" not in rebuilt_names:
            raise ValueError("Save-state archives must contain the emulated core payload.")
        if len(set(original_names)) != len(original_names) or len(set(rebuilt_names)) != len(rebuilt_names):
            raise ValueError("Ambiguous duplicate save-state archive members.")
        members = {}
        for name in sorted(set(original_names) | set(rebuilt_names)):
            members[name] = (byte_comparison(before.read(name), after.read(name))
                             if name in original_names and name in rebuilt_names
                             else {"equal": False, "missing": "original" if name not in original_names else "rebuilt"})
    return {"archive_bytes_equal": original.read_bytes() == rebuilt.read_bytes(),
            "member_contents_equal": bool(members) and all(item["equal"] for item in members.values()),
            "members": members}


def inspect_audio(path):
    digest = hashlib.sha256()
    nonzero = 0
    with wave.open(str(path), 'rb') as audio:
        if audio.getcomptype() != 'NONE' or audio.getsampwidth() != 2 or audio.getnframes() <= 0:
            raise ValueError('QA audio must contain nonempty 16-bit PCM samples.')
        channels, frames = audio.getnchannels(), audio.getnframes()
        count = 0
        while block := audio.readframes(8192):
            if len(block) % 2:
                raise ValueError('QA WAV payload ends inside a 16-bit sample.')
            digest.update(block)
            samples = array('h', block)
            if sys.byteorder != 'little':
                samples.byteswap()
            nonzero += sum(sample != 0 for sample in samples)
            count += len(samples)
        if count != frames * channels:
            raise ValueError('QA WAV payload is shorter than its declared sample count.')
        return {'channels': channels, 'sample_rate': audio.getframerate(), 'sample_width': 2,
                'sample_frames': frames, 'nonzero_channel_samples': nonzero,
                'pcm_sha256': digest.hexdigest()}


def compare_audio(original, rebuilt):
    before, after = inspect_audio(original), inspect_audio(rebuilt)
    return {'equal_pcm_output': before == after, 'original': before, 'rebuilt': after,
            'wav_file_bytes': byte_comparison(original.read_bytes(), rebuilt.read_bytes())}


MOVEMENT_FIELDS = (
    'relative_frame', 'core_frame', 'input_phase', 'input_buttons', 'game_flow', 'dream_sys',
    'timer', 'link_state', 'flashback', 'paused', 'input_locked', 'action_pressed',
    'view_mode', 'look_state', 'look_position', 'turn_state', 'turn_offset', 'move_mode',
    'move_state', 'left_right_state', 'is_forward', 'move_direction', 'move_step', 'floor_type',
    'link_interval', 'time_limit', 'map', 'year', 'day', 'flashback_count',
    'auto_move_locked', 'auto_move_active', 'coordinate', 'pose', 'x', 'y', 'z',
    'scale_x', 'scale_y', 'scale_z', 'pitch', 'yaw', 'roll')
PAD_FIELDS = ('pad', 'pad_buttons', 'pad_released', 'pad_pressed')


def compare_native_observations(original, rebuilt, frames):
    """Require every frame of a supplied native probe, including changed fields."""
    paths = [Path(folder) / 'movement.tsv' for folder in (original, rebuilt)]
    if not any(path.exists() for path in paths):
        return {'status': 'native_state_not_captured', 'output_compared': False}
    if not all(path.is_file() for path in paths):
        raise ValueError('Both runs must contain the native movement observations.')
    runs, headers = [], []
    for path in paths:
        with path.open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream, delimiter='\t')
            header = tuple(reader.fieldnames or ())
            if header not in (MOVEMENT_FIELDS, MOVEMENT_FIELDS + PAD_FIELDS):
                raise ValueError('Native movement observation header is unsupported.')
            rows = list(reader)
        if (len(rows) != frames or any(None in row or None in row.values() for row in rows)
                or [int(row['relative_frame']) for row in rows] != list(range(1, frames + 1))):
            raise ValueError('Native observations must contain every frame and field.')
        core_frames = [int(row['core_frame']) for row in rows]
        if core_frames != list(range(core_frames[0], core_frames[0] + frames)):
            raise ValueError('Native observation core frames are not consecutive.')
        if header == MOVEMENT_FIELDS + PAD_FIELDS:
            for row in rows:
                if (not re.fullmatch(r'[0-9a-f]{8}', row['pad'])
                        or not 0 < int(row['pad'], 16) <= 0x1fffe0
                        or int(row['pad'], 16) % 4):
                    raise ValueError('Native pad pointer is outside aligned MainRAM storage.')
                for field in PAD_FIELDS[1:]:
                    if not 0 <= int(row[field]) <= 0xffffffff:
                        raise ValueError('Native pad masks must be unsigned 32-bit values.')
        headers.append(header)
        runs.append(rows)
    if headers[0] != headers[1]:
        raise ValueError('Native movement observation headers must agree between runs.')
    comparison = byte_comparison(paths[0].read_bytes(), paths[1].read_bytes())
    phases = {}
    observed = ('timer', 'link_state', 'paused', 'input_locked', 'action_pressed', 'map',
                'move_state', 'move_direction', 'move_step', 'floor_type', 'look_position',
                'turn_offset', 'auto_move_locked', 'auto_move_active',
                'x', 'y', 'z', 'pitch', 'yaw', 'roll')
    has_pad = headers[0] == MOVEMENT_FIELDS + PAD_FIELDS
    for row in runs[0]:
        phase = phases.setdefault(row['input_phase'], {
            'frames': 0, 'requested_input_frames': 0, 'unlocked_frames': 0,
            'requested_input_while_unlocked_frames': 0, 'value_ranges': {}})
        phase['frames'] += 1
        requested = bool(row['input_buttons'])
        unlocked = all(int(row[field]) == 0
                       for field in ('paused', 'input_locked', 'auto_move_locked'))
        phase['requested_input_frames'] += int(requested)
        phase['unlocked_frames'] += int(unlocked)
        phase['requested_input_while_unlocked_frames'] += int(requested and unlocked)
        if has_pad:
            pad = phase.setdefault('native_pad', {
                'held_masks': [], 'pressed_masks': [], 'released_masks': [],
                'active_while_unlocked_frames': 0,
                'held_without_edge_while_unlocked_frames': 0,
                'pressed_nonzero_frames': 0, 'released_nonzero_frames': 0})
            for field, key in (('pad_buttons', 'held_masks'), ('pad_pressed', 'pressed_masks'),
                               ('pad_released', 'released_masks')):
                value = int(row[field])
                if value not in pad[key]:
                    pad[key].append(value)
                    pad[key].sort()
            pad['active_while_unlocked_frames'] += int(bool(int(row['pad_buttons'])) and unlocked)
            pad['held_without_edge_while_unlocked_frames'] += int(
                bool(int(row['pad_buttons'])) and not int(row['pad_pressed'])
                and not int(row['pad_released']) and unlocked)
            pad['pressed_nonzero_frames'] += int(bool(int(row['pad_pressed'])))
            pad['released_nonzero_frames'] += int(bool(int(row['pad_released'])))
        for name in observed:
            if row[name] == '':
                continue
            value = int(row[name])
            bounds = phase['value_ranges'].setdefault(name, [value, value])
            bounds[0], bounds[1] = min(bounds[0], value), max(bounds[1], value)
    return {'status': 'native_state_compared', 'output_compared': True,
            'equal_native_state': comparison['equal'], 'byte_output': comparison,
            'frame_observations_per_run': frames, 'fields_per_observation': len(headers[0]),
            'native_pad_captured': has_pad,
            'phases': phases,
            'scope': 'Read-only native fields and recorded input phases at each emulator frame. '
                     'Unlocked counts use all three original input guards. Native pad edge counts are sampled '
                     'frames, not distinct events; the game polls less often than the emulator advances. '
                     'Phase names describe requested inputs; observed ranges establish only the exercised state, '
                     'not exhaustive movement, collision, encounter or feature acceptance.'}


def compare_runs(original, rebuilt):
    original, rebuilt = Path(original).resolve(), Path(rebuilt).resolve()
    completions = [(folder / "completed.txt").read_text() for folder in (original, rebuilt)]
    frame_counts = [re.fullmatch(r'(\d+) emulator frames; scenario (\w+); observation script, not exhaustive feature acceptance\.\s*', text)
                    for text in completions]
    if not all(frame_counts) or frame_counts[0].groups() != frame_counts[1].groups():
        raise ValueError("Both runs must have matching, complete scenario markers.")
    frames = int(frame_counts[0][1])
    scenario = frame_counts[0][2]
    inputs = compare_inputs(original, rebuilt, scenario, frames)
    audio = {'status': 'audio_output_not_captured', 'output_compared': False}
    if inputs.get('identity', {}).get('audio_output_requested'):
        audio = {'status': 'pcm_output_compared', 'output_compared': True,
                 **compare_audio(original / 'audio.wav', rebuilt / 'audio.wav')}
    captures = sorted({n for n in (300, 600, 900, 1200, 1500, 1800) if n <= frames}
                      | set(range(600, frames + 1, 600)) | {frames})
    metadata = [(folder / "emulator.txt").read_text() for folder in (original, rebuilt)]
    identity = [{key: re.search(r'^' + key + r' (.+)$', text, re.M)[1]
                 for key in ("BizHawk", "System", "Scenario")} for text in metadata]
    if identity[0] != identity[1] or identity[0]["Scenario"] != scenario:
        raise ValueError("Emulator version, system and scenario must agree.")
    trace_frames = []
    for folder in (original, rebuilt):
        lines = (folder / "trace.tsv").read_text().splitlines()
        if not lines or lines[0] != "relative_frame\tcore_frame\tsystem\tlagged\tgpu_ram_sample_hash":
            raise ValueError("Run traces must have the recorded emulator trace header.")
        trace_frames.append([int(line.split("\t")[0]) for line in lines[1:]])
    if any(recorded != list(range(60, frames + 1, 60)) for recorded in trace_frames):
        raise ValueError("Run traces must contain every scheduled frame sample.")
    files = {"trace.tsv": byte_comparison((original / "trace.tsv").read_bytes(),
                                          (rebuilt / "trace.tsv").read_bytes())}
    states = {}
    missing = []
    for frame in captures:
        for name in (f"frame-{frame}.png", f"gpu-{frame}.bin", f"frame-{frame}.State"):
            if not (original / name).is_file() or not (rebuilt / name).is_file():
                missing.append(name)
                continue
            if name.endswith(".State"):
                states[name] = compare_state(original / name, rebuilt / name)
            else:
                files[name] = byte_comparison((original / name).read_bytes(), (rebuilt / name).read_bytes())
    equal = not missing and all(item["equal"] for item in files.values()) and all(
        item["member_contents_equal"] for item in states.values())
    if audio['output_compared']:
        equal = equal and audio['equal_pcm_output']
    native = compare_native_observations(original, rebuilt, frames)
    if native['output_compared']:
        equal = equal and native['equal_native_state']
    return {"status": "exact_for_recorded_scenario" if equal else "recorded_outputs_differ",
            "equal_recorded_outputs": equal, "original_run": str(original), "rebuilt_run": str(rebuilt),
            "emulator": identity[0], "frames": frames, "checkpoints": captures,
            "frame_trace_samples": len(trace_frames[0]),
            "missing_checkpoints": missing, "byte_outputs": files, "save_states": states,
            "input_provenance": inputs,
            "audio_output": audio,
            "native_observations": native,
            "feature_groups_accepted": 0,
            "scope": "Recorded trace, PNGs, full GPU memory and all save-state member payloads compared. Archive wrappers may differ. "
                     + ("16-bit PCM audio output also compared. " if audio['output_compared'] else "Audio output was not captured. ")
                     + "This is one input scenario, not exhaustive game, content or branch acceptance."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True)
    parser.add_argument("--rebuilt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        report = compare_runs(args.original, args.rebuilt)
        with Path(args.output).open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2)
            out.write("\n")
        print(f"{report['status']}: {report['frames']} frames, {len(report['checkpoints'])} checkpoints")
        return 0 if report["equal_recorded_outputs"] else 1
    except (OSError, ValueError, zipfile.BadZipFile, wave.Error, KeyError, TypeError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
