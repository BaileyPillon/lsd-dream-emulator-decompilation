# Roadmap

The goal is readable C recovery of the original game, followed by reviewed
comparison evidence for its behavior and content. Optional mods and analysis
tools have separate deliverables. See [PROJECT_OBJECTIVE.md](../PROJECT_OBJECTIVE.md)
for the completion requirements and [provenance](PROVENANCE.md) for the evidence
boundary of the published snapshot.

## Matching C recovery

Six game functions remain in assembly after the matching loader recovery:

The initial seven also remained after the [save-title recovery](SAVE_LABEL.md). That
additional game-support helper was discovered in a segment classified as SDK;
it had not been included in this list. Continue auditing raw SDK-labelled
segments for mixed game support as well as checking the known inclusions.
The [SDK signature audit](SDK_SIGNATURE_AUDIT.md) records candidate provenance
and a sound-API correction; unmatched functions still need further analysis.
The [bounds-predicate audit](RENDER_BOUNDS.md) verifies the original
`func_8004CD38` contract and a research candidate on bounded fixtures. Its 38
byte differences remain to resolve before accepting C.
The [save workflow audit](CARD_SAVE.md) verifies the wrapper, writer and native
helpers in 13,152 bounded cases. Its full C candidate agrees on those fixtures
but still differs in eight executable bytes; the writer remains in assembly.
The [grid-window audit](RENDER_GRID.md) verifies all 65,536 angle words within
74,832 scalar fixtures. Its full C candidate agrees on those fixtures but
reorders two stores, differing in four bytes. Real GTE transforms and the
downstream builder remain external contracts.
The later [streaming composition audit](RENDER_STREAM.md) executes that builder,
its row splitter and slot selector in 45,408 cases. This reduces the remaining
contracts to position lookup and the two GTE helpers; the same full C candidate
still differs in four bytes. The later [world-position composition](RENDER_POSITION.md)
executes the lookup chain and reduces that composition to two GTE contracts.
Scene ownership, framebuffer and timing acceptance remain open.
The later [rotation composition](RENDER_ROTATION.md) executes the original
SDK `RotMatrix` and packed table. Only `ApplyMatrixLV` remains contracted;
actual hardware operations and natural scene ownership still need evidence.
The subsequent [native GTE composition](RENDER_GTE.md) executes that helper
with checked Nymashock MVMVA commands. Eleven original functions pass 13,230
distinct composed cases with zero function-output stubs. Its reviewed COP2
transfer adapter verifies the bounded arithmetic; full PS1 CPU timing,
original hardware and natural scene acceptance remain open.
The [collision composition](COLLISION.md) executes the remaining primitive and
transform routines through actual bounds, decoder and native GTE dependencies.
It adds bounded evidence for contact-height filtering and expanded-box behavior;
both routines still require exact C recovery and natural collision scenarios.
The later [collision C candidate](../research/collision/README.md) reduces the
primitive's whole-executable mismatch from 103 to 22 stack-displacement bytes.
Its SDK arithmetic and distance storage match; recover the original late
bounds-storage lifetime without padding. The paired checker covers 1,566
additional caller overlaps, while 5,400 non-NULL clipping fixtures now execute
the midpoint helper. These remain bounded checks and an unaccepted candidate.
The [compiler-layout diagnostic](COMPILER_LAYOUT.md) now traces actual allocator
calls with unchanged assembly output. Fifty-five further source compilations
find no exact match; the primitive's 22-byte storage mismatch remains open.
The later [compiler-lifetime diagnostic](COMPILER_LIFETIMES.md) measures outward
promotion of an address-taken local and reuse after an inline helper returns.
Sixty-nine additional compiled forms find no exact match. Explain the native
early 16-byte region with real source boundaries before accepting a candidate.
The [ordered-store audit](RENDER_MATCHING.md) shows why final-output agreement
is insufficient: that candidate reverses two stores in 68,306 scalar fixtures.
A corrected full candidate retains native store order but differs in 13 bytes;
106 additional source trials did not produce an exact match.

| Function | Source |
| --- | --- |
| `func_8001DDF4` | [`src/base/transform.c`](../src/base/transform.c) |
| `func_8001F8B8` | [`src/file/tmd_prim_geom.c`](../src/file/tmd_prim_geom.c) |
| `func_8004EF6C` | [`src/menu/card/memory_card.c`](../src/menu/card/memory_card.c) |
| `func_8004C6A8` | [`src/scene/render_context.c`](../src/scene/render_context.c) |
| `func_8004CD38` | [`src/scene/render_context.c`](../src/scene/render_context.c) |
| `func_8004441C` | [`src/menu/ui_sprite.c`](../src/menu/ui_sprite.c) |

Confirm the live catalogue after building with
`python tools/decomp_workbench.py catalog`. SDK assembly is tracked separately.
Each C promotion must retain complete-executable equality and meaningful
types and control flow. Do not use copied instruction blobs or padding to
raise a coverage number.

The [level-model loader recovery](LBD_RECOVERY.md) removes `func_8004BE54`
from that list. It adds 600 bytes of matching C, preserves complete standard
and clean-build equality, and rechecks the 418 local LBD files. The C-byte
total is now 194,884 / 199,912 (97.48%); whole-feature acceptance remains open.

The [sprite scaling audit](UI_SCALE.md) checks 203,472 original and candidate
fixtures each, with zero stubs. Preserve the post-X-store Y denominator read
and skipped-division register behavior in further C attempts. The full C
candidate still has 12 byte differences; 108 additional helper trials did not
produce an exact match. UI drawing, natural caller reachability and PS1 timing
remain separate acceptance work.

## Original behavior and content

The [level-model loader audit](LBD_PIPELINE.md) checks all 418 inventoried local
LBD files, including native destruction/reloading, with actual allocator,
decoder, constructors and SDK routines. Two virtual-call declarations now
match the observed default methods. This closes those calls for the recorded
ready-CD fixture; pending I/O, cold hardware, caller ownership and rendering
remain separate work. Its initial full C loader candidate differed in 118 bytes,
and 191 initial source trials found no exact match. The subsequent
[matching recovery](LBD_RECOVERY.md) resolves it with 580 further source forms.

- Resolve asset/command inventory gaps and runtime reachability.
- Close virtual-call dependencies and verify semantic callback signatures.
- Extend native fixtures beyond the 11 currently checked callbacks and their
  documented contracts; see the [scripted callback checks](SCRIPTED_AI.md).
- Compare natural animation construction, lifetime and actor/render behavior.
- Review every feature's recorded scenarios, including rare RNG, save/card
  error, audio and hardware-timing branches.
- Extend [Japanese asset and replay evidence](JAPANESE_EDITION.md) beyond the
  recorded 6,000-frame scenario and review exhaustive content coverage
  separately from English v1. The [state diagnosis](NYMASHOCK_STATE.md)
  identifies the eight cold-boot bytes as unused Nymashock label storage;
  strict byte comparisons retain those differences.

The catalogue currently has 40 provisional groups. None has been accepted for
all required runtime scenarios. The [inventory](FEATURE_INVENTORY.md) lists the
remaining scenario for each group; 97.48% describes game C bytes only.

## Developer tools and optional mods

- Keep AI-assisted context export and local analysis separate from original
  NPC behavior. The supplied tools make no model API calls.
- Retain explicit input hashes, dependencies and negative controls in reports.
- Extend emulator checks for duration multipliers and passive Gray Man.
- Keep all optional patched executables and discs outside the canonical build.
