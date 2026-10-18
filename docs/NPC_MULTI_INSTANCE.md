# Compared multi-instance NPC history

The [NPC recorder](NPC_ENTRY_TRACE.md) and
[lifetime inspector](NPC_LIFETIME.md) now verify interleaved instances of one
original callback. Each instance needs its own declared entry count, first and
last entry boundaries, monotonic context clock and RAM corroboration. The
default single-instance profile remains strict.

## Recorded Corpse cohort

The [fixed controller program](../research/headless/corpse-wall-link-route.json)
cold-boots the Japanese game, follows an original wall link into map 5, and
reaches seven instances of the source-labelled `entity_corpse` callback. The
original function is 64 bytes at `0x80061158`, with entity table ID 56. Its
original caller returns to `0x8002CD88`.

Three separate 12,000-step runs use the same inputs: distributed emulator core
with original disc, observer core with original disc, and observer core with
the matching rebuilt disc. The strict original/rebuilt comparison and explicit
distributed/observer output comparison both pass. The latter permits only the
declared PS1 core files to differ and reports their identities.

| Observation | Result per run |
| --- | ---: |
| Native frame/GPU observations | 12,001 |
| Complete-RAM hash samples | 2,036 |
| Selected complete RAM/GPU/raw RGB checkpoints | 153 |
| Complete stereo PCM | 35,383,300 bytes |
| Original instruction entries with tracing | 21 |
| Traced instances | 7 |
| Entries per traced instance | 3 |
| Clock corroborations per traced instance | 12 |

The seven addresses and their exact entry windows are declared in the program.
Each instance enters at relative frames 6,300, 6,306 and 6,311, with context
ticks zero, one and two. The full original/rebuilt instruction logs agree.
These are core-advance boundaries, not wall-clock or original-hardware timing.

Two instances first become reachable and enabled at frame 6,298; the other
five do so at 6,299. All seven leave the followed game-flow/dream graph between
6,311 and 6,312. Every boundary is checked in adjacent complete RAM captures.
The inspector checks 139 distinct snapshots and **973 instance snapshots** per
traced run. All seven histories and transition windows agree between discs.

The first update also has a measured effect. For every instance, stored
transform Y changes from -200 at 6,299 to -400 at 6,300, while X and Z agree.
Y remains -400 after the next two entries. Both the entity tick and sound-context
tick advance from zero through three. This agrees with the callback's first-tick
virtual call using -200; it does not establish a visible animation or the
physical allocation lifetime of the objects.

An independent audit decodes all **459** retained PNGs with Pillow and checks
each against raw RGB. Five alterations of native entry-log copies are rejected:
missing entry, duplicated entry, wrong instance tick, undeclared instance and
wrong instance first boundary. Two further controls exclude a primary or
nonprimary instance from clock corroboration; both fail despite the other six
valid clocks. Original recordings are preserved.

## Profile and report contract

Multi-instance profiles add `trace.expected_instances`. Each item supplies
`entity_address`, `expected_entries`, `expected_first_frame` and
`expected_last_frame`. Addresses must be valid and unique; counts and outer
boundaries must agree with the complete callback profile. Every declared
instance must appear when its first entry is due, including in prefix runs.
Unlisted owners, missing ticks and missing RAM clock evidence are rejected.

Each instance currently qualifies one activation with ticks starting at zero.
Repeated activation of the same instance needs a separate, explicit profile;
tick resets are rejected. The original default profile still requires one
instance when no instance list is supplied.

The lifetime JSON contains every instance under `instances`, with its own
rows and transition windows. `checked_snapshots` counts distinct RAM snapshots;
`checked_instance_snapshots` counts their per-instance inspections. Earlier
primary-instance fields remain available for existing readers. Disabled context
payload and unreachable former storage are left uninterpreted.

Fourteen new test methods use owned fixtures for interleaving, instance omission,
tick faults, unknown owners, incomplete clocks, prefix boundaries and malformed
metadata. Prefixes cannot exceed an instance's final count or complete it before
its declared last entry. The earlier Buddha recording retains identical rows and transition
windows under the extended inspector.

## Reproduce

Follow the existing [observer build and recording setup](NPC_ENTRY_TRACE.md),
then supply the new program to each recording:

```powershell
python tools/record_npc_history.py `
  --capture-folder D:/QA/cold-start/original `
  --observer-profile .decomp-lab/npc-observer-new/profile.json `
  --program research/headless/corpse-wall-link-route.json `
  --workspace D:/QA/corpse-original-new
```

Repeat with the rebuilt capture and a fresh workspace. For the distributed
original run, omit `--observer-profile`. Compare the observer pair with the
default strict mode; compare distributed/original-observer output only with
the explicit `--mode observer-output`. Run `tools/inspect_npc_lifetime.py`
separately on both traced recordings. All commands preserve existing outputs.

[`npc-multi-instance-checks.json`](npc-multi-instance-checks.json) pins the
sources and retained private evidence. Proprietary inputs, emulator binaries
and raw captures are excluded from the repository. The tools control no
existing emulator window and make no model API calls.

## Progress and remaining scope

Distinct callback types with compared natural instruction-entry histories
increase from **one to two**: Buddha and Corpse. Seven Corpse instances share
one callback type. This does not accept either whole NPC type or a feature group.

Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two assembly
functions and two inherited storage explanations remaining. The inventory
remains 40 provisional feature groups, 38 with listed core C, 107 original
callbacks and 40 bounded callback profiles. The exhaustive feature total is
unknown; whole-NPC and whole-feature acceptance remain zero. Other routes,
seeds, activation cycles, visible effects, complete emulator-state parity and
hardware timing remain open. Original game behavior, optional mods, the
playable build and the separate Bevy port are unchanged.
