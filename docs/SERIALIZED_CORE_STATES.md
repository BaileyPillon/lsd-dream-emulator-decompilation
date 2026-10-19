# Serialized emulator checkpoints

The original Japanese disc and the matching rebuild emit identical raw
`IStatable.SaveStateBinary` bytes at all **52 checkpoints** in the retained
6,000-input-frame opening route. A separate cold start of the original repeats
those bytes. A fourth run, with serialization disabled, agrees on every recorded
game output. [Machine-readable evidence](serialized-core-state-checks.json)
records the inputs, hashes, controls, and scope.

This is bounded emulator evidence. Matching C remains **197,172 / 199,912 bytes
(98.63%)**. The two remaining assembly functions and three inherited storage
explanations are unchanged. No whole feature or NPC encounter is accepted.

## Recorded comparisons

All four runs use the same frozen controller program, BIOS, complete disc
content, host sources, and native-core profile. Instruction observation stays
disabled, with zero instruction-hook entries. The earlier media-record
initialization patch is already part of this profile; this work does not rebuild
the native core or change game code.

| Run | Input frames | GPU observations | RAM samples | Complete checkpoints | Raw states retained |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 6,000 | 6,001 | 1,001 | 52 | 52 |
| Rebuild | 6,000 | 6,001 | 1,001 | 52 | 52 |
| Repeated original | 6,000 | 6,001 | 1,001 | 52 | 52 |
| Original without serialization | 6,000 | 6,001 | 1,001 | 52 | 0 |

The initial neutral frame accounts for the extra observation. Each run emits
4,423,002 stereo sample frames, or 17,692,008 PCM bytes. Complete PCM bytes,
per-frame GPU observations, sampled RAM, and checkpoint RAM/GPU/RGB buffers agree
in all three original-referenced comparisons. Independent Pillow decoding checks
all 208 PNGs against their retained RGB buffers and hashes. The audit also
rehashes 172 retained producer-source snapshots.

The host serializes twice at each selected frame. It compares complete byte
arrays, then recaptures MainRAM and GPURAM and checks the frame counter. Across
the three serialized runs, there are **156 unique same-frame repeat checks and
312 serializer calls**, with 156 first states retained. The retained states total
533,546,868 bytes. These totals count each run once; the original is shared by
the two pairwise state comparisons.

Both byte arrays are retained if a same-frame repeat differs, and the recorder
fails while preserving its observations. Successful runs retain the first
array, both digests and sizes, memory digests, counters, and the actual core
determinism declaration. Every observed `DeterministicEmulation` value is
**false**; repeated equality here does not change that emulator declaration.

## Earlier eight-byte cold-boot variation

The earlier [Japanese-edition failures](JAPANESE_EDITION.md) remain preserved.
Re-decoding and rehashing their 36 saved states reproduces the original 18
checkpoint comparisons: twelve differ and six agree. Every differing byte in
those twelve failed comparisons maps to object offsets 16 through 23 in
`MDFNGameInfo.RMD.MediaTypes[0].Name`.

The logical media name is `CD`, length two, with its terminator at object offset
three. The differing bytes occupy unused capacity in its 24-byte short-string
object. Mapping uses the distributed core's own symbols, its actual saved-page
layout, the `MDFNGameInfo` pointer, and the nested media vectors. The associated
drive name provides another ownership check. A separate six-state pilot records
the same ownership chain.

The distributed adapter constructs the media-label record with uncleared
short-string capacity. The existing complete-record initialization patch creates
the vector element before assigning its name. Three two-checkpoint pilots using
that profile repeat raw state bytes; the longer recordings above extend this
observation. No serialized bytes are masked, normalized, rewritten, or restored.
The old failures remain failures in their original reports.

## Serialization contract and limits

The source audit verifies 17 emulator source files against their pinned Git blob
identities at BizHawk commit
`bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5`. The reader validates the Waterbox v1
envelope, managed frame/lag/cycle/video/clock fields, and the Nyma controller
signature and length. The selected controller configuration has a twelve-byte
controller trailer with zero switch-buffer bytes.

Relevant upstream contracts are
[WaterboxCore.SaveStateBinary](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Emulation.Cores/Waterbox/WaterboxCore.cs),
[Nyma controller serialization](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Emulation.Cores/Waterbox/NymaCore.Controller.cs),
and [Waterbox memory serialization](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/waterbox/waterboxhost/src/memory_block/mod.rs).

Native payloads are opaque to the general reader and compared byte for byte.
Waterbox deliberately excludes invisible regions, including its main and
alternate stacks, invisible heap, and `.invis` section. A serialization contract
cannot establish every native or hardware state. The profile still records
`runtime_verified: false`; these observations do not certify every path through
the customized emulator.

This route does not establish other scenes, seeds, complete NPC encounters,
memory-card/error paths, all audio/movie events, endings, timing, or exhaustive
asset and virtual-call closure. State loading and replay from a restored state
are outside this experiment. Whole-feature acceptance and original-hardware
timing remain open.

## Capture and inspect

Use a verified local capture and an existing compatible observer-core profile.
Choose fresh private directories on a drive with sufficient space. Disc images,
BIOS, raw states, and captures stay outside Git. The recorder controls its own
headless process and does not operate a running player.

```powershell
python tools/record_dispatch_history.py `
  --capture-folder D:\private\lsd\verified-original `
  --workspace D:\CodexArtifacts\LSD\working\new-state-run `
  --program D:\private\lsd\opening-program.json `
  --observer-profile D:\private\lsd\core-profile.json `
  --frames 6000 --serialized-state --disable-instruction-observer

python tools/inspect_serialized_core_states.py inspect `
  D:\CodexArtifacts\LSD\working\new-state-run `
  --output D:\CodexArtifacts\LSD\working\new-state-inspection.json

python tools/inspect_serialized_core_states.py compare `
  D:\CodexArtifacts\LSD\working\original-run `
  D:\CodexArtifacts\LSD\working\rebuilt-run `
  --output D:\CodexArtifacts\LSD\working\new-state-comparison.json
```

Serialization is opt-in. The inspector also accepts older history manifests
with their original instruction-observer defaults. State comparisons require
identical recorder settings, complete runtime and producer identities, and the
same controller program. Exit status is zero for equal states, one for valid
recordings with raw differences, and two for invalid inputs. Existing output
reports are preserved.

Six saved-data corruption controls are rejected. A seventh control changes one
opaque native byte and updates its recorded digest: format validation succeeds,
but raw comparison detects the byte difference. These are saved-data controls,
not executed game faults. The 23 added tests cover truncation, controller
framing, counter/dimension mismatches, storage identity, path escapes, memory
digests, and legacy observer modes. Windows and Linux each pass all 1,252 tests,
with two existing skips.

## Remaining primitive source work

The parallel source investigation qualifies 28 observations containing 26
distinct candidate source texts, including 24 new source forms. Pointer/native
word views and real inline pointer-parameter homes do not improve the retained
22-byte primitive mismatch. GNU extraction independently verifies six distinct
function images. Two complete-image controls still differ by 22 and 117 bytes,
entirely within the primitive function's span.

Actual compiler declaration traces agree with normal complete assembly. The
pointer-word results stay in registers; inline formal homes are later reused by
edge vectors. Neither observation explains the original early storage region.
No candidate is promoted. The 392 protected game-build inputs and canonical
executable remain unchanged.
