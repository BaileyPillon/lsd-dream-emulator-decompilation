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
still differs in four bytes. Scene/framebuffer/timing acceptance remains open.
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
- Measure complete Japanese-asset coverage separately from the local translated
  asset edition used in the existing comparisons.

The catalogue currently has 40 provisional groups. None has been accepted for
all required runtime scenarios. The [inventory](FEATURE_INVENTORY.md) lists the
remaining scenario for each group; 97.18% describes game C bytes only.

## Developer tools and optional mods

- Keep AI-assisted context export and local analysis separate from original
  NPC behavior. The supplied tools make no model API calls.
- Retain explicit input hashes, dependencies and negative controls in reports.
- Extend emulator checks for duration multipliers and passive Gray Man.
- Keep all optional patched executables and discs outside the canonical build.
