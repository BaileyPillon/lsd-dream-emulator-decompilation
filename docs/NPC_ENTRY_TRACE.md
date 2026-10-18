# Original NPC instruction-entry tracing

Record a fixed controller route from a cold boot and observe the original
`entity_buddha` instruction as the game reaches it naturally. The optional
observer is an extension to the PS1 emulator adapter, separate from the matching
game and its original NPC AI. It changes no game code, injects no game RAM and
restores no saved state. The tools make no model API calls and do not choose
controller inputs from live observations.

## Qualified history

The published build, recorder and comparer were executed on three separate
30,000-step cold boots: the distributed core with the original disc, the
observer core with the original disc, and the same observer core with the
matching rebuilt disc. All three use the same static controller history.

| Observation, per run | Recorded result |
| --- | ---: |
| Controller steps | 30,000 in 61 contiguous segments |
| Native frame / complete GPU-memory hash observations | 30,001 |
| Complete 2 MiB RAM hash samples | 5,003 |
| Selected complete RAM, GPU and raw RGB checkpoints | 125 |
| Complete stereo PCM | 88,457,172 bytes / 22,114,293 sample frames |
| Original callback entries, when tracing | 2,700 |

The default strict comparison passes for the observer's original/rebuilt pair.
An explicit `observer-output` comparison passes for the distributed/observer
original pair: every GPU observation, RAM sample, selected raw buffer and
complete PCM file agrees. The comparer reports both core identities instead
of treating the runtimes as identical. The existing global runtime-input and
state comparators retain their strict core-identity requirements.

The two complete entry logs are byte-identical. They identify the original
228-byte function at **`0x8005EFF4`**, entity ID **20**, instance
`0x801CF954`, caller return address `0x8002CD88`, and original entry instruction
`0x27BDFFE0`. The first recorded entry is at relative frame **5,407**, with
context tick zero; the last is at **22,574**, with context tick 2,699. These
frames label individual core advances, rather than wall time. The last entry
does not by itself identify the frame when the game disables the context.
Sixty-one selected RAM checkpoints per traced run corroborate the original
callback registration, context owner and clock.

A separate audit compares all three recordings against the earlier retained
uninstrumented history and decodes all **375** PNGs independently with Pillow.
Every decoded image agrees with its corresponding raw RGB buffer. The public
CLI compares raw RGB directly and checks PNG dimensions, chunks and CRCs; it
does **not** decode PNG pixels. PNG container-byte differences are preserved
as diagnostics. All 125 containers happen to agree in each new comparison.

The aggregate, source hashes and retained private-report hashes are in
[`npc-entry-trace-checks.json`](npc-entry-trace-checks.json). Original media,
BIOS, emulator binaries and raw captures are not published.

## Build the separate observer

First prepare the pinned BizHawk 2.11.1 native checkout using the
[complete native-build recipe](EMULATOR_LABEL_INITIALIZATION.md#build-separate-emulator-profiles).
That recipe covers its submodules, Waterbox sysroot, Clang 18 and `zstd`.
The native checkout path must contain no spaces. Either the pristine pinned
media adapter or the documented complete-record initialization patch is
accepted; all other tracked source changes are rejected.

From this repository in Linux/WSL, after the ordinary native release target
is built and current:

```bash
python tools/build_npc_observer.py \
  --source-root /path/to/ready-BizHawk-2.11.1 \
  --output .decomp-lab/npc-observer-new
```

This is an **adapter-only build using pinned cached native objects**, not a
fresh full-core rebuild. It compiles one new adapter object containing
[`npc_entry_observer.h`](../research/runtime_state/npc_entry_observer.h), then
links a separate core. Source revisions, CPU source, compiler version, cached
objects and supplied release core are checked and retained unchanged. The
output includes `profile.json`, both core files, source copies and build logs.
The profile's `runtime_verified: false` describes the build alone; runtime
qualification requires recording and comparison below.

The observer uses Mednafen's existing `SetCPUHook` interface. Enabling that
hook selects the existing DebugMode CPU execution path. Unchanged CPU source
does not establish unchanged execution timing; the output comparisons above
qualify this specific recorded route. No original-hardware timing or complete
emulator-state parity is claimed.

## Record the three profiles

Use 64-bit Windows, .NET Framework 4.8 and an installed stable .NET SDK 8 or
later, as described in [the headless replay guide](HEADLESS_REPLAY.md).
The Python wrappers use the standard library. Supply your own verified
[cold-start capture](COLD_START.md), BizHawk 2.11.1 with default Nymashock
settings, Japanese disc, canonical executable and BIOS inputs.

The capture provides validated **launch inputs**. The new recorder feeds the
published static route; it does not replay the capture's earlier controller
history. The route pins the full Japanese disc track and canonical executable
hashes, which must match your local inputs.

```powershell
python tools/record_npc_history.py `
  --capture-folder D:/QA/cold-start/original `
  --workspace D:/QA/npc-distributed-new

python tools/record_npc_history.py `
  --capture-folder D:/QA/cold-start/original `
  --observer-profile .decomp-lab/npc-observer-new/profile.json `
  --workspace D:/QA/npc-observer-original-new

python tools/record_npc_history.py `
  --capture-folder D:/QA/cold-start/rebuilt `
  --observer-profile .decomp-lab/npc-observer-new/profile.json `
  --workspace D:/QA/npc-observer-rebuilt-new
```

Choose a fresh workspace for every run, outside the supplied capture, runtime
and observer build. Each run builds its own host, copies its runtime, launches
one hidden process at below-normal priority and preserves its PID, exit code
and logs. It does not control an existing EmuHawk window or use its saves.
`result.json` records completion; comparison is a separate step.

The default [`buddha-timed-route.json`](../research/headless/buddha-timed-route.json)
expands to the previously recorded controller TSV, with SHA-256
`c33fdd031c9a04809c1093067d7d197adf0270d8baa6c6f737c7c7504b23672b`.
There is one initial neutral advance at relative frame zero, followed by
30,000 controller steps. RAM is hashed every six frames and at the declared
checkpoints. The 125 checkpoints include the first and last callback-entry
frames. `--frames 6000` records a shorter prefix for preparation; that prefix
does not qualify the full history.

Each workspace retains `run-inputs.json`, frozen source snapshots, the actual
compiled host and runtime identities, submitted inputs and settings. Its
`observations/` directory contains GPU hashes, RAM samples, complete PCM,
selected raw RAM/GPU/RGB buffers, PNGs and the optional instruction log.

## Compare retained recordings

```powershell
python tools/compare_npc_history.py `
  --reference D:/QA/npc-observer-original-new `
  --candidate D:/QA/npc-observer-rebuilt-new `
  --output .decomp-lab/npc-original-rebuilt-new.json

python tools/compare_npc_history.py `
  --reference D:/QA/npc-distributed-new `
  --candidate D:/QA/npc-observer-original-new `
  --mode observer-output `
  --output .decomp-lab/npc-observer-output-new.json
```

The default `same-runtime` mode rejects a changed runtime identity. The
explicit `observer-output` mode requires exactly one distributed run and one
observer run, permits differences only in the two PS1 core files and reports
those differences. Unrelated runtime changes remain errors. Existing output
records are preserved.

Before comparing outputs, the tool checks retained sources, qualified runtime
libraries, inputs, host binaries, function bytes, trace counters, caller
instruction, stack bounds and context clocks. Missing, repeated, truncated or
unexpected trace entries fail validation. Frozen sources allow a retained
recording to be checked after the repository's working files change.

## Recovery and acceptance boundaries

Matching C is unchanged at **197,172 / 199,912 bytes (98.63%)**. Two assembly
functions and two inherited storage explanations remain. The project still
tracks 40 provisional feature groups, 38 with listed core C implementations,
and 107 original callbacks with 40 bounded callback profiles. The official
exhaustive feature total is unknown. This workflow adds no C bytes, bounded
callback profiles, accepted whole NPC classes or accepted whole feature groups.
The existing 10 developer-capability categories and three optional mods are
unchanged.

This repeats and strengthens **one** natural timed Buddha history, including
its instruction entries. It does not cover all NPCs, seeds, encounter branches,
collisions, save/load paths or timing conditions. Whole-encounter acceptance,
complete-state comparison and original-hardware timing remain separate gates.
Original NPC behavior, optional analysis tools and gameplay mods continue to
have separate implementations and progress measurements.

The source-only test suite passes **880 tests**, with two expected skips, on
Windows Python 3.14 and Linux/WSL Python 3.13. Its 20 new test methods use owned
fixtures and include seven wrong-trace controls, runtime-identity rejection,
source/payload corruption and complete-audio checks. Native qualification
requires the private inputs described above; synthetic tests do not substitute
for running the game.
