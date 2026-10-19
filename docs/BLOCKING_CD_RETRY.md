# Original blocking CD read retries

The original blocking reader now has an executed, controller-only error profile.
Opening the tray during a 76-sector read produces failures; closing it lets the
same original helper recover without Reset. Original and matching rebuilt discs
agree, and the observer's recorded outputs agree with the stock core.

This is bounded behavior verification. Matching C remains **197,172 / 199,912
bytes (98.63%)**. Two game functions still use assembly, three inherited storage
explanations remain unresolved, and no whole feature or NPC encounter is accepted.
The exhaustive original-game feature total remains unknown: the inventory has
40 provisional groups, 38 with their listed core functions in C, 107 original
NPC callback bodies in C, and 43 bounded callback profiles.

## What the game actually does

The route submits 2,000 controller steps and records 2,001 frame advances,
including the initial neutral frame. It opens the tray at **1,020**, closes it
at **1,070**, and keeps disc index `0`. It restores no state, presses no Reset,
patches no game instruction or RAM, and controls no existing emulator session.

The interrupted helper starts at frame 1,008. Its original Setloc/CdSync loop
includes **210 rejected Setloc commands**, each followed by an observed CdSync
error and another Setloc. It issues the same 76-sector SDK request **75 times**:
74 fail, and the last completes at **frame 1,163**. Every reissue retains the
same logical position, sector count, destination, mode, caller and stack frame.

The final **155,648 bytes** match the actual disc sectors at the SDK poll,
blocking-helper return and enclosing Read return. Read/helper result words are
zero status values; they are not transferred-byte counts. The full canonical
helper body and each executed SDK boundary are checked against the original
executable. The Setloc pointer is linked to its receiver using the `+0x18`
offset decoded from the original argument-setup instruction.

This differs from the earlier [asynchronous error/reset profile](CD_ERROR_RESET_RECOVERY.md),
whose five failed requests reseek and end without reissuing an SDK read.

| Evidence per observer capture | Result |
| --- | ---: |
| Balanced SDK entries and returns | 848 |
| Balanced original method/helper returns | 9 |
| Blocking helper returns | 3 |
| Successful SDK transfers | 38 |
| Complete successful sector data compared | 385,024 bytes |
| Failed SDK transfers | 74 |
| Failed written prefixes compared | 28,672 bytes |
| Rejected Setloc / CdSync-error pairs | 210 |
| Error-to-Setloc retry edges | 284 |
| GPU observations equal across original/rebuilt/stock | 2,001 |
| Complete sampled RAM digests equal | 336 |
| Independently decoded RGB checkpoints equal | 3 |
| Complete PCM window digest/count equal | 5,897,812 bytes |

Failed snapshots retain their entire requested destinations in lossless private
archives. Only the SDK-reported written prefixes are compared with the disc;
unwritten tails are never accepted as transferred content. The first failed
read writes fourteen sectors; the other failed attempts write none.

## Reproduce without copying an emulator

Use the existing verified Japanese cold-boot input captures, the existing
BizHawk 2.11.1 installation, and the retained observer capture qualified by
[CD error/reset evidence](cd-error-reset-checks.json). This needs 64-bit Windows,
the installed .NET SDK/Framework, and locally supplied game/BIOS files. The tool
does not download them or build another native core.

Each destination below must be new. Replace the uppercase paths with your own:

```powershell
python tools/record_compact_dispatch.py ORIGINAL_INPUT_CAPTURE PRIVATE/original --observer-capture QUALIFIED_CD_ERROR_CAPTURE
python tools/record_compact_dispatch.py REBUILT_INPUT_CAPTURE PRIVATE/rebuilt --observer-capture QUALIFIED_CD_ERROR_CAPTURE
python tools/record_compact_dispatch.py ORIGINAL_INPUT_CAPTURE PRIVATE/stock
python tools/verify_blocking_cd_retry.py PRIVATE/original --output PRIVATE/original-checks.json
python tools/verify_blocking_cd_retry.py PRIVATE/rebuilt --output PRIVATE/rebuilt-checks.json
python tools/inspect_compact_dispatch.py compare PRIVATE/original PRIVATE/rebuilt --mode original-rebuilt
python tools/inspect_compact_dispatch.py compare PRIVATE/original PRIVATE/stock --mode observer-stock
```

The default [controller profile](../research/headless/blocking-cd-retry-route.json)
declares the tray pair and complete submitted-input hash. The recorder creates
small producer snapshots and an owned C# host. Its `dll` and `gamedb` junctions
reuse the supplied runtime; no runtime, disc or asset tree is copied.

Compact mode hashes every PCM sample and the complete sampled memory windows,
retains up to four PNG checkpoints, and caps aggregate trace/table streams at
64 MiB. Total retained observations must stay below 128 MiB. Large owned SDK and
return payloads are sealed in XZ archives after a complete lossless roundtrip;
inspection reads those archives in memory. It preserves existing evidence and
refuses ambiguous expanded/archived copies or shared historical payloads.

Historical native-core reuse is explicit: its published compressed-core hash,
retained producer, original adapter, interfaces and exports must agree. This
does not relabel that core as a build of the current producer or relax the
existing current-producer loader. The inspector also qualifies the complete
captured C# source set, compiler inputs, launch inputs and shared runtime.

The focused tests include hand-calculated PNG filters, malformed transport and
sector controls, source/version rejection, multi-payload archive updates, and
six executed Windows C# budget/digest controls. Controls that alter retained
records are parser tests; the executed game interruption uses controller inputs.

## Remaining boundaries

This profile does not explain the helper's inherited unused sector array or the
two debug-driver frame reservations. It adds no C bytes, original game feature,
NPC profile, gameplay mod, developer capability category or model API call.
The tools are optional developer analysis, separate from original NPC behavior.

Other tray timings, media, file routes, helper branches, full emulator state,
whole features and original-hardware timing remain unaccepted. Source and
runtime identities, exact comparisons, controls and unchanged before/after
counts are recorded in [machine evidence](blocking-cd-retry-checks.json).
