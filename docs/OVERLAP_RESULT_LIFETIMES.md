# Overlap result lifetimes

The later [control-flow study](OVERLAP_CONTROL_FLOW.md) supersedes this
148-byte candidate with a 26-byte nonmatch. This page retains the earlier
source, compiler and native evidence at its original checkpoint.

The [shared bounds interface supplement](COLLISION_API.md#shared-bounds-accessor-declaration)
updated the research fragment's primitive pointer declaration and
argument casts at that checkpoint. Its complete linked function and candidate
image remained byte-identical to the 148-byte nonmatch recorded here. The source hashes below
identify the earlier text snapshot; the supplement pins that source revision.

The unaccepted C candidate for `func_8001DDF4` now differs from the complete
original executable in **148 bytes**, improving on the previous 170-byte
fragment. Its 796-byte extent, original 176-byte frame and twelve-byte midpoint
payload are preserved. The canonical game still uses assembly; no C bytes or
whole feature are accepted by this result.

| Measure | Original | Earlier candidate | Current candidate |
| --- | ---: | ---: | ---: |
| Function bytes | 796 | 796 | 796 |
| Complete frame bytes | 176 | 152 | 176 |
| Midpoint payload bytes | 12 | 12 | 12 |
| Complete executable bytes | 505,856 | 505,856 | 505,856 |
| Complete-image differing bytes | 0 | 170 | 148 |

## Consumed results

Three actual calls now pass their results through checked four-byte views:
the global source count, coarse bounds and fallback bounds. Each view contains
one complete value, consumed by the original loop or collision query. Helpers
return the selected scalar or pointer. Original call order, masks, contact
height checks and twelve-byte point storage remain unchanged.

`class_FA50_is_active` still returns the shared enumeration count and ignores
its model argument. `get_source_vertices` still returns shared bounds and
ignores its index. The reconstruction preserves these original behaviors.
It introduces no unused tail, instruction substitution, physical register
binding, new volatile constraint or compiler-flag change.

The previous fragment remains available at
[the baseline commit](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/blob/dacecb8995f393a69367b260b6252b80adbf7be6/research/collision/overlap_candidate.c).
The earlier [overlap report](OVERLAP_RECOVERY.md) and its metadata remain
historical evidence.

## Why the frame is still not a source match

Three complete-source observations compare the earlier fragment, the retained
148-byte form and its formatted public source. Normal and instrumented complete
assembly are identical in every observation.

Both candidates allocate the real twelve-byte point array in a sixteen-byte
local region, followed by two four-byte address-taken scalars. The earlier
candidate then has eight four-byte reload allocations; the new candidate has
eleven. The compiler rounds those reload slots to eight bytes, growing its
virtual local area from 88 to 112 bytes. With 24 outgoing-argument bytes and
40 saved-register bytes, the new frame reaches 176 bytes.

Those three additional reloads occur late. The original places `best` at
SP+`0x40`; the candidate still places it at SP+`0x28`. Equal total frame sizes
therefore do not explain the original earlier region or establish matching
source. Nested temporary/local allocator calls are one allocation, not two.

## Qualified source studies

These 69 isolated compiler observations contain 63 distinct prepared source
texts and include repeated controls. Every result is qualified as one complete
sized ELF function at its original address. None matches exactly.

| Family | Compiler observations |
| --- | ---: |
| Consumed plane records with shared square/bounds storage | 11 |
| References to actual SDK functions | 13 |
| Original overlap argument references | 15 |
| Actual count/bounds result references | 16 |
| Caller-owned count/bounds records | 14 |

The plane records restore a frame but add stores. SDK references add call-site
instructions. Incoming pointer and caller-owned result variants do not improve
the retained candidate. These rejected hypotheses remain separate from recovered
source and runtime acceptance.

The formatted public fragment is rebuilt as a complete translation unit.
An unstripped diagnostic ELF produces the same complete candidate image and
qualifies its exact 796-byte span. Every byte outside that span remains canonical.

## Native paired comparison

All **6,912 graph pairs** pass through the original collision, transform and
SDK bodies with native GTE commands and zero function-output stubs. This repeats
the existing domain: **5,760 distinct final inputs** and **1,152 repeated inputs**.
It adds no new original fixture domain.

The checks compare complete 6,144-byte caller buffers, return values, preserved
ABI, stack guards, GTE state and ordered native results. Fifteen original
routines execute per image; the curated midpoint helper is not entered by this
profile. Both images together issue 22,032 OP/SQR commands and 12,960 leading-bit
requests before controls.

One height-boundary control patches both candidate sites. The coarse-path
changed instruction executes once and the independent composed model detects
its wrong result. The fallback patch is not entered by that control. Its three
commands and two leading-bit requests remain separate from the positive pairs.

The checker now reads the fixed frame from the candidate's actual MIPS prologue
and matching epilogue. It previously reported 152 bytes for every candidate.
Four synthetic tests cover differing valid frames, malformed or mismatched
frames and additional stack adjustments. The CLI requires this profile's single
fixed frame; unsupported stack layouts are rejected rather than mislabelled.

## Reproduce and limits

Use the [existing preparation and native comparison recipe](OVERLAP_RECOVERY.md#reproduce).
The expected complete-image gate is unsuccessful: exit code 1, 505,856 bytes,
148 differing bytes. The subsequent bounded native comparison should pass and
report a 176-byte candidate frame. The candidate is excluded from the game build.

All 392 canonical game inputs retain their hashes and the regular game build
remains exact. C recovery stays at **195,844 / 199,912 bytes (97.97%)** with
**five** assembly fallbacks and **17** identified inherited storage explanations.
Listed-core C groups remain 37 / 40, bounded NPC profiles 36 / 107, and whole
feature/encounter acceptance zero. Ten developer capability categories and
three optional mods retain their separate scope.

Natural collision scenes and histories, complete asset/alias coverage and PS1
timing still need reviewed evidence. The running player and separate Bevy port
are unchanged. No model API is called.

[overlap-result-lifetimes-checks.json](overlap-result-lifetimes-checks.json)
pins the source, complete-image qualification, compiler observations and native
reports. Original images, linked code, full buffers, debugger traces and failed
attempts stay private. Earlier inventory snapshots and the frozen objective
remain intact.
