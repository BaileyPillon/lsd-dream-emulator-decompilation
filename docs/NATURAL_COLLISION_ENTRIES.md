# Natural hull and primitive collision entries

The original game's opening route now has a compared instruction-entry trace
for both remaining assembly functions: **194 hull queries** and **643 primitive
queries**. Both the center-segment and corner fallback call sites execute in
populated game geometry. Original and matching rebuilt records agree, and the
separate observer matches the stock emulator's recorded game outputs.

Matching C remains **197,172 / 199,912 bytes (98.63%)**. This adds natural call
and argument evidence; it promotes no C function and accepts no whole collision
feature. The existing playable build and separate Bevy repository are unchanged.

## Executed history

Three fresh isolated cores run the existing 6,000 opening controller inputs:
original disc with the observer, rebuilt disc with the observer, and original
disc with the stock core. Submitted controller bytes are unchanged from the
[successful SDK route](SDK_READ_COMPLETIONS.md). There is no game instruction
or RAM patch, saved-state restore, injected pose, or control of a user emulator.

The observer arms at frame 900. The watched entries occur at frames
**3,014–4,926**. Every entry retains its complete original function body,
preceding transfer/delay words, four register arguments, stack pointer and
raw receiver/table windows.

| Observed original call | Entries |
| --- | ---: |
| Indirect hull entry at `0x8001DDF4`, from `0x8001D904` | 194 |
| Primitive entry from hull center segment, `0x8001DF20` | 159 |
| Primitive entry from hull corner segment, `0x8001E048` | 325 |
| Primitive entry from `func_8001E7BC`, `0x8001EA0C` | 156 |
| Primitive entry from `func_8001E7BC`, `0x8001EA3C` | 3 |

The primitive function's 1,944-byte range is separately qualified through the
complete canonical symbolic link and GNU symbol extents. It is not added to
the 838-target declared-vtable catalogue. The existing file-driver range family
keeps its own manifest and qualification contract.

## Address relationships observed

For the **484** primitive entries at the two hull-owned call sites, the nearest
preceding recorded hull entry has consistent original argument relationships:

| Primitive entry field | Observed relationship |
| --- | --- |
| SP | Hull entry SP minus the original 176-byte frame |
| Model argument | Hull receiver word at `+0x20` |
| Output point | The hull's original output argument |
| Nearest-distance address | Hull frame SP plus `0x40` |
| Height address | Hull frame SP plus `0x44` |

These entries correlate with 190 of the 194 hull entries. The other four have
no recorded primitive child; they are not classified as collision misses.
The trace sees ten hull receiver addresses, one hull input address and nine
correlated model addresses. Those cardinalities are neither object-lifetime
identities nor counts of distinct model assets.

The address check detects a retained-data control that moves nearest-distance
storage 24 bytes earlier, matching the unresolved displacement in the C research
candidate. This is an observed stack-role constraint, not permission to rewrite
instructions or normalize a source mismatch.

## Verification and limits

Original/rebuilt complete entry records, body payloads and argument models are
identical. Both comparison pairs agree on **6,001 GPU observations, 1,001 RAM
observations, 52 complete RAM/GPU/RGB checkpoints and 17,692,008 PCM bytes per
run**. Independent TSV, code, stack-role and image checks agree; all 156 PNGs
decode to their recorded RGB, and 114 source snapshots rehash correctly.
Eight contradictory retained-data controls are rejected. They alter parser
inputs, not the executed game. Peak entry load is nine records in one frame.

The bounded entry profile does **not** observe callee returns, hit/miss results,
complete geometry buffers, fifth/sixth stack arguments, every executed
instruction, or complete call-stack/heap lifetimes. Its raw table window does
not establish the hull's virtual receiver/slot load chain. Whole-feature
acceptance, complete emulator states and original-hardware timing remain open.

The native core contains one newly compiled adapter linked with the recorded
pinned cached objects, not a fresh full-core rebuild. Its record format and
entry hook are unchanged. Eighteen owned protocol/role tests bring the tooling
suite to **1,153 tests** on both Windows and Linux, with two expected skips
each. The earlier CD error/reset profile still validates.

## Reproduce locally

Prepare local discs/BIOS as in [Playing](PLAYING.md) and pinned native sources
as in [Headless replay](HEADLESS_REPLAY.md). Export the original function ranges
and build an entry-only observer in Linux/WSL:

```sh
python tools/collision_boundaries.py \
  --output .decomp-lab/collision-ranges-new
python tools/build_dispatch_observer.py \
  --source-root /private/pinned-bizhawk-source \
  --output .decomp-lab/collision-observer-new
```

Record each disc in a fresh Windows workspace; omit `--observer-profile` for
the stock-core control:

```powershell
python tools/record_dispatch_history.py `
  --capture-folder D:/private/cold-boot-original `
  --workspace D:/private/collision-original-new `
  --program research/headless/collision-opening-route.json `
  --observer-profile .decomp-lab/collision-observer-new/profile.json

python tools/inspect_collision_entries.py `
  --reference D:/private/collision-original-new `
  --candidate D:/private/collision-rebuilt-new `
  --output .decomp-lab/collision-pair-new.json

python tools/inspect_collision_entries.py `
  --reference D:/private/collision-original-new `
  --candidate D:/private/collision-stock-new `
  --mode observer-output `
  --output .decomp-lab/collision-stock-new.json
```

Eighteen new source forms test one fully consumed pair of midpoint results,
with two repeated controls. All 20 complete functions are independently
extracted with GNU tools. The best new form differs in 112 bytes; none improves
the published hull control's 26. Both collision assembly functions and three
inherited storage explanations remain required.

Later [primitive snapshots](COLLISION_ORDINAL_CALLS.md) and
[hull call/return records](HULL_CALLS.md) supply the geometry, stack inputs and
returns missing from this entry-only profile. The
[functional replay](NATURAL_COLLISION_REPLAY.md) and
[exception-context investigation](COLLISION_EXCEPTIONS.md) retain 20 cross-frame
failures that require intervening interrupt/device execution. Extend natural
scenes and branches, and recover source that passes the complete canonical
executable gate. Original NPC behavior and optional AI-assisted tools retain
separate counts; this profile calls no model API and adds no mod.
[Validation metadata](collision-entry-checks.json) preserves the source,
before/after measurements and private evidence identities.
