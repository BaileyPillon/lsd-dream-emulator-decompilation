# Natural Boatman approach history

The [fixed controller program](../research/headless/boatman-approach-route.json)
cold-boots the Japanese game, turns northeast from the recorded map-2 spawn,
and approaches one original Boatman placement. It records actual entries into
the original callback, then compares the rebuilt game and the emulator observer.
This adds evidence for one natural history; whole-NPC acceptance remains open.

## Compared recordings

Three separate runs use the same 9,000 controller steps: distributed emulator
core with original disc, observer core with original disc, and observer core
with the matching rebuilt disc. The default strict original/rebuilt comparison
passes. The explicit `observer-output` comparison also passes for distributed
and observer cores, reporting their different identities.

| Observation | Result per run |
| --- | ---: |
| Controller steps | 9,000 |
| Frame and complete GPU-memory hash observations | 9,001 |
| Complete 2 MiB RAM hash samples | 1,614 |
| Selected complete RAM, GPU and RGB checkpoints | 205 |
| Complete stereo PCM | 26,537,652 bytes |
| Original callback entries in each traced run | 87 |
| Context-clock corroborations in each traced run | 111 |
| Rooted lifecycle snapshots in each traced run | 191 |

The callback is `entity_boatman`, 120 bytes at **`0x8005EC98`**, with original
entity-table ID **14**. Both instruction logs identify instance `0x801D056C`,
caller return address `0x8002CD88`, and context ticks 0 through 86. The complete
entry records agree, including their native timestamps. Relative frames label
core advances, rather than wall time.

The first entry is at relative frame **4,577**, and the last is at **5,069**.
The entity is present with a disabled context at 4,576 and enabled at 4,577.
It remains reachable and enabled at 5,073, then is absent from the checked
object graph at 5,074. This establishes consecutive recorded boundaries;
loss of reachability does not establish physical allocation lifetime.

## Stored effects and independent checks

Every callback-entry advance has a complete RAM checkpoint. Both discs show
the same 87 ten-unit decrements of the stored Z translation: **-41,984 to
-42,854**, with X and Y unchanged. The entity and context clocks advance
together. The captured model-frame field completes a 45-frame cycle and
continues into a second cycle.

The original callback's sound-request slot contains ID **13** at relative
frames **4,633** and **4,891**, corresponding to entry ticks 10 and 55.
The model-frame field is 11 in those post-advance captures. Other entry
checkpoints retain the slot's reset ID, -1. These records agree with the
original callback's movement and frame-dependent request; they do not assign
a particular audible instrument or prove visibility of the NPC.

A separate Pillow pass decodes all **615 PNGs** across the three recordings
and compares their complete pixels with the corresponding raw RGB buffers.
The public comparator directly checks raw RGB and PNG structure; this separate
audit supplies independent pixel decoding. Five changed-entry controls and
one missing-clock control are rejected. Original game code and RAM are never
modified, no saved state is restored, and the tools control no existing emulator
window or call a model API.

One earlier original-only exploration discovered the entry window. It is
retained separately and is not counted as a qualified comparison. The three
qualified recordings keep the same controller inputs and add read-only
checkpoints around the observed boundaries.

## Reproduce

Use the pinned runtime, verified cold-start inputs and separate observer
described in [NPC entry tracing](NPC_ENTRY_TRACE.md). Choose a fresh workspace
for each run:

```powershell
python tools/record_npc_history.py `
  --capture-folder D:/QA/cold-start/original `
  --observer-profile .decomp-lab/npc-observer-new/profile.json `
  --program research/headless/boatman-approach-route.json `
  --workspace D:/QA/boatman-original-new
```

Repeat with the rebuilt capture and a new workspace. For the distributed
original run, omit `--observer-profile`. Then compare the recordings:

```powershell
python tools/compare_npc_history.py `
  --reference D:/QA/boatman-original-new `
  --candidate D:/QA/boatman-rebuilt-new `
  --output .decomp-lab/boatman-original-rebuilt-new.json

python tools/compare_npc_history.py `
  --reference D:/QA/boatman-distributed-new `
  --candidate D:/QA/boatman-original-new `
  --mode observer-output `
  --output .decomp-lab/boatman-observer-output-new.json

python tools/inspect_npc_lifetime.py `
  --recording D:/QA/boatman-original-new `
  --output .decomp-lab/boatman-lifetime-new.json
```

Run the lifetime inspection on the rebuilt recording separately. Every command
preserves existing outputs. The [evidence summary](npc-boatman-checks.json)
pins the published source and retained private reports. Game media, BIOS,
emulator binaries and raw captures are excluded from the repository.

## Progress and remaining requirements

Compared natural instruction-entry histories now cover **three callback
types**: Buddha, Corpse and Boatman. This measure is separate from the
**40 / 107** bounded callback profiles and the **107 / 107** original callbacks
already recovered in C. No whole NPC or feature group is newly accepted.

Matching C stays at **197,172 / 199,912 bytes (98.63%)**, with two assembly
functions and two inherited storage explanations remaining. The inventory
still contains 40 provisional groups, 38 with listed core C; its exhaustive
feature denominator is unknown. Other routes, seeds, activation cycles,
visible effects, full emulator-state parity and original-hardware timing
remain open. Original NPC behavior, optional mods, AI-assisted tools, the
[playable matching build](PLAYING.md) and the separate Bevy port are unchanged.
