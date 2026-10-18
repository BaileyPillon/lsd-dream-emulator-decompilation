# Natural primitive calls across ordinal recordings

The opening-route comparison now checks all 643 primitive invocations observed
between frames 900 and 6,000, extending the earlier
[52-call sample](NATURAL_COLLISION_CALLS.md). Eleven separate recordings of each
game image partition the same entry history. Every captured call agrees with
the recovered fixed-point model on its actual geometry, return, nearest
distance, contact point, and optional height. Original and rebuilt records and
complete RAM payloads match.

This closes the primitive-call sampling gap for this observed history. It adds
no matching C bytes and accepts no whole feature or NPC encounter.

| Evidence in the same observed route | Earlier sample | Ordinal collection |
| --- | ---: | ---: |
| Primitive entries | 643 | 643 |
| Completed primitive calls | 52 | 643 |
| Hits / misses | 19 / 33 | 206 / 437 |
| Polygon visits | 924 | 13,924 |
| Calls crossing a frame boundary | 1 | 29 |
| Observed model / geometry addresses | 12 / 12 | 12 / 12 |
| Original/rebuilt recording pairs | 1 | 11 |
| Separate stock-core controls | 1 | 1 |

The controller program still has 6,000 frames. Tracing is armed at frame 900;
calls before arming are outside this evidence. The history also contains 194
hull entries, whose returns remain unverified. Polygon visits and addresses
are observations, without unique-asset or allocation-lifetime claims. Packet
codes `0x21`, `0x25`, `0x29`, `0x2C`, and `0x2D` occur.

## How the partition works

Each recording selects eligible primitive entries numbered `first`,
`first + step`, and so on. Here `step` is 11 and `first` ranges from 1 to 11.
The first five phases capture 59 calls each; the other six capture 58 each.
The original limits remain 64 calls per recording, one start per frame, one
pending call, and two completed records / 8 MiB of payload per frame.

Eleven phases accommodate 643 calls under the 64-call limit. At most seven
primitive entries occur in a frame in this history. The verifier independently
reconstructs the actual selection and requires zero nested, frame-budget,
sample-limit, duplicate-key, overflow, and outstanding-call losses. These
requirements also cover calls that cross a frame boundary. A changed route can
fail these bounds; preparing partitions alone establishes no coverage.

Each 988-byte record retains architectural CPU/GTE views and effective
call/return instruction contexts, with complete 2 MiB main RAM at both
boundaries. The complete original payload across eleven phases is 2,572 MiB;
the rebuilt collection has the same payload. The observer reads original
state and preserves the game executable and assets.

## What the comparison proves

All 22 observer recordings use the same native runtime and submitted controller
bytes. The only permitted program/settings difference across phases is
`ordinal_first`. Retained program sources and preparation hashes establish
that distinction. Original/rebuilt pairs retain identical settings. Recording
directories must be distinct; a recording cannot certify itself as another run.

Every observed primitive entry appears exactly once in each game's partition.
The checker compares original method-entry histories and actual game output
bytes across phases, between original/rebuilt pairs, and against the stock-core
control. Each run retains 6,001 GPU observations, 1,001 RAM observations, 52
complete RAM/GPU/RGB checkpoints, and 17,692,008 PCM bytes. Equal checkpoint
metadata alone is insufficient: complete checkpoint and audio files are read.

A separate audit decodes all 1,196 checkpoint PNGs, rehashes 963 retained
producer-source snapshots, and independently reconstructs the captured polygon
streams for all 643 calls. Twenty contradictory retained-data cases are
rejected. These controls alter analysis inputs; they are not executed game
faults. All 1,199 tooling tests pass on Windows and Linux with two expected
skips per platform.

The separate native core reuses pinned native objects and recompiles its
adapter. Its build profile retains `runtime_verified: false`; these bounded
recordings do not certify every core mode or a fresh full native build.

## Reproduce with local game inputs

Build the separate observer with `tools/build_dispatch_observer.py
--collision-calls`, using the pinned source and native-object prerequisites
described in [the method observer guide](DISPATCH_ENTRY_TRACE.md). Game media,
BIOS, raw recordings, and private research evidence are not distributed.

Prepare fresh partitions from the published controller template:

```bash
python tools/collision_call_batches.py \
  --program research/headless/collision-ordinal-opening-route.json \
  --output .decomp-lab/collision-ordinal-programs-new
```

Copy that prepared directory into a fresh collection as `programs`, retaining
its `plan.json` separately as `program-plan.json`. Use
`tools/record_dispatch_history.py` to record every phase with the separate
observer, once from the verified original cold-capture inputs and once from
the rebuilt cold-capture inputs. Keep each workspace distinct. Record phase 1
again with the distributed stock core, without an observer profile.

Place this manifest in the collection directory, after the recordings exist:

```json
{
  "schema_version": 1,
  "type": "ordinal_collision_recording_collection",
  "canonical_executable_sha256": "282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f",
  "ordinal_step": 11,
  "program_plan": "program-plan.json",
  "prepared_programs": "programs",
  "reference": [
    "original/phase-01", "original/phase-02", "original/phase-03",
    "original/phase-04", "original/phase-05", "original/phase-06",
    "original/phase-07", "original/phase-08", "original/phase-09",
    "original/phase-10", "original/phase-11"
  ],
  "candidate": [
    "rebuilt/phase-01", "rebuilt/phase-02", "rebuilt/phase-03",
    "rebuilt/phase-04", "rebuilt/phase-05", "rebuilt/phase-06",
    "rebuilt/phase-07", "rebuilt/phase-08", "rebuilt/phase-09",
    "rebuilt/phase-10", "rebuilt/phase-11"
  ],
  "stock": "stock/phase-01"
}
```

Then validate the retained collection:

```bash
python tools/inspect_collision_call_batches.py \
  --manifest /path/to/collection/collection.json \
  --output .decomp-lab/collision-ordinal-comparison-new.json
```

[Publication metadata](collision-ordinal-checks.json) records executed inputs,
source hashes, before/after counts, and the retained evidence hashes. Keep large
recordings on a data drive; original game assets and private RAM stay outside Git.

## Remaining work

The two collision routines still require matching C, and three inherited C
storage explanations remain unresolved. Broader original-feature coverage,
other collision histories, complete NPC encounters, hull returns, geometry
ownership, full instruction paths, opaque CPU/GTE state, and original-hardware
timing remain open. The feature denominator is still 40 provisional groups;
the exhaustive original feature count is unknown. This collection accepts zero
whole-feature groups and changes neither the optional mods nor the Bevy port.
