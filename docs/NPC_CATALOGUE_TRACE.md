# Multi-target original NPC observations

The optional catalogue observer records original instruction entries at all
**107 verified NPC callback PCs** in a second log. The existing selected-PC
trace remains independent and must match its projection from that log.
This is analysis tooling for the matching C project. It changes no original
NPC behavior, invokes no model API and adds no generative AI to the game.
The [Bevy port](https://github.com/BaileyPillon/lsd-dream-emulator-bevy) has its
own repository and progress measurements.

## Compared history

Three fresh, controller-only cold boots use the unchanged
[Boatman route](../research/headless/boatman-approach-route.json): the original
disc on the distributed core, the original disc on the catalogue core, and
the rebuilt disc on that same catalogue core. Each run advances 9,000 input
steps and retains 9,001 GPU observations, 1,614 sampled complete-RAM hashes,
205 full RAM/GPU/RGB checkpoints and 26,537,652 bytes of complete PCM.

The two traced runs have identical original entry records. The stock/observer
comparison also agrees on every recorded GPU and RAM observation, selected
raw buffer and PCM sample. A separate Pillow pass decodes all 615 PNGs and
compares their RGB pixels with the retained native RGB files.

Each traced run contains **2,467 registered dispatches** across three callback
types and five instances:

| Recovered label | Entity ID | Owner | Entries | Relative frames | Entry ticks | Rooted RAM clock checks |
| --- | ---: | --- | ---: | --- | --- | ---: |
| Boatman | 14 | `0x801D056C` | 87 | 4,577–5,069 | 0–86 | 111 |
| Fish | 35 | `0x801C9ABC` | 595 | 5,432–8,996 | 0–594 | 44 |
| Fish | 35 | `0x801CA6EC` | 595 | 5,432–8,996 | 0–594 | 44 |
| Fish | 35 | `0x801CB32C` | 595 | 5,432–8,996 | 0–594 | 44 |
| Giant Fish | 118 | `0x801CBF6C` | 595 | 5,432–8,996 | 0–594 | 44 |

These frames bound observed entries, not an exact allocation or visibility
lifetime. Names come from recovered source labels. The independent selected-PC
trace still contains all 87 Boatman entries. Fish and Giant Fish are two new
compared natural callback types, bringing that cumulative measure from three
to five; the route observes three of the 107 watched targets.

## Observation boundaries

The separate native core adds a PC bitmap and an independent 1,024-event
per-frame buffer. Every event includes the original instruction, registers,
timestamp, entity vtable, ID and context state, owner, callback and clock.
Overflow or a mismatch between drained entries and the native total fails
the recording. Original game instructions and emulated RAM are read-only.

Before recording, the wrapper validates the complete published catalogue,
its original property-table bindings and every full-function hash. It freezes
the catalogue, provenance, host sources, observer build and launch inputs.
The inspector checks every loaded callback span at each selected checkpoint
after the observer is armed. A matching entry word cannot hide a changed tail.

A registered dispatch requires the original entity vtable, enabled context,
owner, entity ID and callback binding, plus the original dispatcher return
address. A different callback reached by an actual original `JAL` is classified
as nested function execution. It does not create another registered NPC.
Disabled payload and unregistered contexts do not count as live dispatches.

Each observed instance keeps its first recorded tick. Consecutive entries
are corroborated through contexts reachable from the original game-flow and
dream roots. Unknown tick resets remain unresolved; the tool does not invent
an activation epoch or silently reset a clock. Non-dream checkpoints are
reported explicitly and supply no rooted NPC evidence.

## Reproduce

Use the qualified [entry-recording setup](NPC_ENTRY_TRACE.md), matching game
inputs and pinned native source checkout. Create a fresh catalogue core in
Linux/WSL:

```bash
python tools/build_npc_observer.py \
  --source-root /path/to/pinned-native-source \
  --output .decomp-lab/catalogue-observer-new \
  --catalogue
```

From 64-bit Windows, record the original disc with that profile:

```powershell
python tools/record_npc_history.py `
  --capture-folder D:/private/original-cold-start `
  --workspace D:/private/catalogue-original-new `
  --program research/headless/boatman-approach-route.json `
  --observer-profile .decomp-lab/catalogue-observer-new/profile.json `
  --catalogue
```

Repeat with the rebuilt disc in a new workspace. Also record the original
with `--catalogue` and no `--observer-profile` to use the distributed core.
The latter freezes the same catalogue and host source set but emits no
instruction logs. Compare the two traced runs with the default strict mode:

```powershell
python tools/compare_npc_history.py `
  --reference D:/private/catalogue-original-new `
  --candidate D:/private/catalogue-rebuilt-new `
  --output .decomp-lab/catalogue-original-rebuilt-new.json
```

Compare the distributed run against the original observer run with the explicit
`--mode observer-output`. Retain the full runtime differences in that report.
The default runtime comparison remains strict. A single-PC profile cannot be
used for a catalogue recording, and vice versa. Source changes require a new
observer profile and fresh recordings; retained earlier recordings remain
inspectable through their frozen source identities.

## Validation and remaining work

Eighteen source-only tests cover catalogue provenance and complete binding
closure, full code spans, actual nested calls, ownership, disabled contexts,
duplicate events, unresolved clocks and profile/header/core identities. The
full suite passes on Windows Python 3.14 and WSL Python 3.13: 947 tests per
platform, with two expected skips each. Retained Buddha, Corpse and Boatman
single-PC recordings still pass their original strict inspection.

Seven private native-capture corruption controls are rejected: an omitted
selected entry, a duplicated Fish entry, an altered original instruction,
a truncated event, a false native total, a changed loaded function tail and
a consistently shifted clock origin. Two additional controls retain an
unregistered owner and an unresolved clock without granting dispatch or
clock acceptance. The [evidence summary](npc-catalogue-trace-checks.json)
contains hashes and scope metadata; proprietary captures remain private.

Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two remaining
game assembly functions and two inherited storage explanations. This work
adds zero C bytes. Bounded callback profiles remain **40 / 107**. Accepted
whole NPCs and feature groups remain **zero**. The exhaustive original
gameplay-feature denominator is still unknown.

Further routes, seeds, activation cycles, downstream effects, visible behavior,
audio causality, complete emulator state and original hardware timing need
evidence. This route does not validate all 107 targets or a whole encounter.
The playable matching build, optional mods and Rust/Bevy port are unchanged.
