# Inspecting progression recordings

`tools/inspect_progression_history.py` independently checks the retained
controller-only progression journals, including journals sealed in lossless
archives. It reads archives in memory and never launches an emulator, restores a
game state, writes game RAM, or controls a running player.

The checker reproduces the [seven-day pilot](NATURAL_PROGRESSION.md): all 209
sampled RAM/GPU/RGB pairs and 201 complete PCM windows agree, while all **nine
actual complete-state hash pairs differ**. The comparison returns exit code 1.
The 200 checkpoints without state observations do not count as equal states.
[Qualification metadata](progression-history-inspector-checks.json) records the
executed source, real-data checks, controls and limits.

## Commands

Use a completed private recording directory. Confirm that its owned producer
process is terminal before interpreting it as a finished capture. A progress
file by itself does not establish that a process is still running or has stopped.

```powershell
python -B tools/inspect_progression_history.py inspect D:\private\lsd\original

python -B tools/inspect_progression_history.py compare `
  D:\private\lsd\original D:\private\lsd\rebuilt `
  --output D:\private\lsd\new-comparison.json

python -B tools/inspect_progression_history.py compare `
  D:\private\lsd\original D:\private\lsd\rebuilt `
  --require-year-ending --output D:\private\lsd\new-year-comparison.json
```

Exit codes are **0** for valid inspection or equal observations within the
requested scope, **1** for recorded differences or an unmet year-window gate,
and **2** for invalid/incomplete input. An existing output report is preserved.

This is a saved-data checker. Producer, compiler, runtime, BIOS, disc and input
provenance must be checked separately against their retained manifests. A saved
data comparison does not authenticate a capture's origin or a live process.

## Checked evidence

- Exact input-change ordering, initial neutral controls and neutral inputs after
  the year boundary.
- Consecutive day/year observations, the pinned dream-object address, and the
  agreement of every sampled counter with the day journal.
- The exact 600-frame/day/ending/final checkpoint schedule. Missing observations
  fail validation; absent complete-state hashes are never treated as evidence.
- Consecutive returned-PCM windows from the initial through final frame, their
  total sample counts and their agreement with checkpoint counters.
- Full sampled RAM/GPU/RGB hashes and every present complete-state hash, with
  all differences retained.
- Decoded PNG pixels, container checksums, bounded decompression, and agreement
  of the final image with its native RGB checkpoint. All five PNG row filters
  are covered without an additional image dependency.
- Declared retained stream bytes against actual files/archive members. The
  stream ceiling is 16 MiB per recording.

Sealed recordings use `retained-journals.json` and
`retained-journals.tar.xz`. The index and full archive/member hashes are checked
before analysis. Only the four exact regular journal members are accepted.
Duplicate/unexpected members, oversized payloads and changed restored copies
are rejected. Analysis creates no expanded journal files.

## Year and ending scope

`--require-year-ending` requires the recorded first-year transition through all
365 completed days, the original ending path/threshold/flags, a pending-to-terminal
signal for the same movie object, the six declared ending images, and 12,000
neutral frames after the year boundary. It also requires original/rebuild
agreement on every retained observation, including complete-state hashes.

The terminal signal is an opaque signed native value, not a successful-decode
boolean. The original movie-screen call uses MDEC vtable slot `0x48`, bound in
the canonical image to `func_80045948`. That wrapper can forward slot `0x68`
(`func_80045CFC`); the frame/stop chain also includes unspecified-return paths.
The separate slot-`0x58` stream helper can report stopped/missing-next-frame
conditions. A nonzero signal alone does not prove all ending frames decoded.

The report therefore keeps `complete_ending_decode_verified`, original-hardware
timing, whole-feature acceptance and complete emulator/game parity **false**.
The year option checks a defined observation window. Continuous video, complete
ending decode, callback/instruction events, hardware timing and other seeds
remain separate gates. A synthetic unit-test calendar is never native evidence.

## Qualification

The reader was exercised against the existing closed pilot, then against the
same original journals in a fully verified 19,956-byte archive. Only the small
report, input RLE and PNG were retained beside that archive. An empty ending
member adapts the old pilot to the archive container; it is not an ending
observation. Both paths decode to identical observations, reproduce the nine
state differences and preserve the original capture. No native route was rerun.

The focused tests reject missing/drifting frames, early year wrap, regressed
counters, changed object identity, incomplete audio, unobserved states, changed
hashes, stale restored files, incorrect storage accounting, malformed JSON/PNG
and premature ending claims. These extend replay-analysis tooling and add no
original gameplay feature, NPC profile, model-API invocation or recovered C byte.
