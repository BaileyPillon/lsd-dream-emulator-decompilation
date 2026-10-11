# Original collision and native GTE audit

The original collision routines execute through their actual primitive decoder,
bounds helpers and SDK arithmetic, with **zero function-output stubs**. The
checked Nymashock bridge now executes the original OP and SQR commands and its
native leading-sign-bit counter. Reviewed COP2 register transfers remain an
explicit adapter around Unicorn; complete PS1 CPU timing and gameplay acceptance
remain open.

This supplement extends bounded evidence for F008. It promotes no assembly
function to C: `func_8001DDF4` and `func_8001F8B8` remain among the six remaining
game functions. C recovery stays **194,884 / 199,912 (97.48%)**. Whole provisional
feature-group acceptance stays **0 / 40**; the exhaustive original feature total
is still unknown. NPC, developer-capability and optional-mod counts are unchanged.

## Native checks

| Check | Runs | Input scope |
| --- | ---: | --- |
| Original `OuterProduct10` | 4,108 | Signed-halfword edge products, overlapping outputs and pointer aliases |
| Original `Square0` | 1,740 | Full-word inputs narrowed through IR, overlapping outputs and aliases |
| Original `SquareRoot0` | 6,396 | Unique positive/negative words, normalized table buckets and power boundaries |
| Original primitive collision | 12,696 | Unique initialized buffers and arguments, all 32 supported primitive modes and conditional payload layouts |
| Original transform composition | 6,912 | Unique stage-input graphs over planes, heights, flags, face transforms and aliases |

The composition contains **5,760 distinct final transform inputs**, repeated
1,152 times. With zero displacement, selecting another cuboid face changes a
stage argument without changing the generated points. These repetitions are
classified separately rather than counted as new transform inputs.

The main suite enters 15 original functions. The 16 curated ranges also include
`func_8001E2E8`, which is not called here: the transform passes a NULL clipping
midpoint. Entering a function does not establish exhaustive branch coverage.

The native bridge handles **46,561 OP/SQR commands** and **29,826 LZCS writes**,
including repeated requests and the three fault controls. A separate integer
audit checks all **76,387 ordered responses** and identifies **10,669 distinct
native requests**. Its MVMVA identity self-check is counted separately.

## Recovered behavior

`class_FA50_is_active` returns the global word `D_8008AC4C`; it ignores the
model argument. `class_FA50_reset_flag` writes one. These operations do not count
live model instances. The collision loops use that global word as an enumeration
bound, and the test includes synthetic negative, zero, one and two values.

`refresh_source_vertices` computes minimum/maximum coordinates from eight-byte
vertex records and writes six signed halfwords into shared storage at
`D_8008B21C`. `get_source_vertices` returns that same storage regardless of the
supplied model or index. Earlier comments describing a 24-vertex buffer and an
instance count are corrected; the function bodies remain unchanged.

`func_8001F51C` expands model bounds into an eight-point cuboid, and
`func_8001F66C` permutes its faces and applies signed-halfword coordinate updates.
Those original functions construct and alter the query cloud before the larger
transform routine runs. Its first pass tests the two face midpoints; its fallback
tests two corresponding corner segments per cloud record.

`func_8001F8B8` takes a model, nearest-distance output, six-byte contact point,
optional height output, and two six-byte segment endpoints. It resets the
nearest-distance output to `INT_MAX` on each invocation. The decoder ignores the
incoming cursor when the primitive index is zero, so the inherited unspecified
incoming S1 value does not determine the first primitive pointer in these checks.

The primitive routine uses a plane intersection and an axis-aligned bounding box
expanded by 24 coordinate units. It does not perform a point-in-triangle test:
some contacts outside the triangle but inside that expanded box are accepted.
Equal nearest distances retain the first accepted contact.

The optional height output is **contact Y minus the primitive's minimum Y**.
It is separate from travel distance. The transform compares that height against
512; filtering a contact can produce a zero result after the contact buffer has
already been updated. It also resets its object mask and reports cloud masks.
These details are preserved rather than replaced with a conventional collision
algorithm. The retained return-two branch is not reached by these proper-ABI
callee paths.

The original square-root helper uses a 192-halfword positive-input table. Its
signed shifts can index the preceding memory for negative inputs; the local
audit pins that 640-byte neighboring window separately. Zero and negative one
both return zero before a table read. No table or neighboring game bytes are
published. Replacing this helper with a floating-point square root would change
the observed integer behavior.

## Fault controls and reproduction

Three private Unicorn instruction mutations are detected:

- Return contact Y in place of height above the primitive minimum.
- Shrink one expanded-box boundary from 24 units to 23.
- Accept a height of exactly 512 in the transform's first pass.

The original executable, game inputs and native runtime remain unchanged.

Build a new private bridge using the instructions in [RENDER_GTE.md](RENDER_GTE.md).
With a current matching build, optional Unicorn installed in WSL, and the checked
local BizHawk 2.11.1 runtime, run:

```bash
python tools/verify_collision.py \
  --output .decomp-lab/collision-new/report.json \
  --bridge .decomp-lab/collision-new/bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1' \
  --ranges docs/collision-function-ranges.json
```

Report and log paths must be new and private. The
[range manifest](collision-function-ranges.json) contains names, addresses,
lengths and hashes, with no original instruction bytes. The
[evidence metadata](collision-checks.json) pins the private proofs, request-log
audit, producer sources and local validation. Synthetic tooling tests require
neither a game executable nor a native emulator.

The native implementation is the pinned software core described in
[RENDER_GTE.md](RENDER_GTE.md); source context is the checked
[Mednafen GTE implementation](https://github.com/TASEmulators/mednafen/blob/382ff1b8d293c9a862497706808cbb79b2cecbfb/src/psx/gte.cpp).
It is not an original-hardware measurement. Natural collision geometry,
multi-cloud encounter coverage, unsupported primitive codes, complete CPU load
delays/cycles and the enumerated paired gameplay scenarios remain open.
