# Rendering C matching and ordered-store evidence

The grid helper's closest C candidate still differs in four executable bytes.
A stronger audit now distinguishes final-output agreement from the sequence
of its dimension stores. The original and a corrected C candidate preserve
that sequence in **74,832 cases each**. The four-byte candidate changes it in
**68,306 cases**, despite preserving the checked final outputs.

The corrected candidate differs at **13 executable byte positions** because
the compiler allocates width and cell-z to different registers. Neither
candidate is promoted. Game C stays at 194,284 / 199,912 bytes (97.18%), with
seven known assembly functions, 40 provisional feature groups and zero
whole-feature acceptances. This extends F033 evidence without changing
original behavior, NPC, developer-capability or optional-mod counts.

## Executed stores and independent outputs

The audit runs the same scalar fixtures as the [grid-window check](RENDER_GRID.md)
through three separate native machine instances: original code, the full
four-byte candidate, and the full corrected candidate. This is **224,496
variant runs over 74,832 distinct fixtures**, not 224,496 distinct scenarios.
Four position/GTE/builder contracts remain explicit.

For each executed word store to context `0x80` or `0x84`, it records the
effective offset, four-byte width and register value. The next instruction's
observation checks that the store reached memory. The independent model
requires `0x80` followed by `0x84`, with the appropriate dimension values.
Whole guarded buffers, matrix/info/template outputs, call traces, stack
guards and saved registers also retain their existing comparison.

| Executed variant | Final-output model passes | Ordered-store passes | Ordered-store failures | Complete-executable differences |
| --- | ---: | ---: | ---: | ---: |
| Original | 74,832 | 74,832 | 0 | 0 |
| Four-byte C candidate | 74,832 | 6,526 | 68,306 | 4 |
| Corrected C candidate | 74,832 | 74,832 | 0 | 13 |

The four-byte candidate keeps the native order in transverse cases and
reverses it in the other orientation. Equal dimension values do not hide the
different offsets and sequence. This establishes an internal instruction/store
trace difference; it does not establish an interrupt, DMA or gameplay observer
of that difference. Real GTE, position resolution, rendering and PS1 timing
still require separate evidence.

Global Unicorn memory-write hooks disrupted the existing transform-call
contracts at the same boundary for original code and both candidates. Six
controlled diagnostic runs established that the failure required those hooks.
The successful audit uses executed-store decoding and immediate readback
without global memory hooks. The initial failed log and diagnostic record are
preserved separately from the successful proof.

## Matching experiments

The corrected source was compiled as a complete translation unit and linked
with the other 304 baseline objects. All 13 differences lie inside the
660-byte helper; the rest of the 505,856-byte executable is unchanged. Its
SHA-1 is `d032d09a66d068cbc5459669f316178736442b8b`.

The original [allocation diagnosis](RENDER_GRID.md) remains relevant: putting
width's store first shortens its scheduled lifetime from 53 to 52 instructions,
making its allocation priority tie cell-z's. New trials keep canonical flags
and avoid copied instructions, padding and physical register bindings:

| Source hypothesis | New trials | Compile errors | Best differing bytes | Exact matches |
| --- | ---: | ---: | ---: | ---: |
| Typed input views for grid dimensions | 38 | 0 | 327 | 0 |
| Coordinate storage widths on both store forms | 32 | 0 | 4 | 0 |
| Typed field accessors/references for the bounds predicate | 36 | 0 | 38 | 0 |
| **Total** | **106** | **0** | | **0** |

Twelve duplicate bounds-accessor sources were skipped. The input-view trials
also changed function size to 656 or 664 bytes, so that approach does not retain
the native layout. The coordinate trials did not improve the four-byte match;
the bounds accessors did not improve its existing 38-byte candidate. These
are eliminated hypotheses, not additional C recovery or accepted behavior.

## Contributor target

Recover readable C that retains both the original store order and register
allocation under the pinned toolchain. Reuse the established scalar contract
and native stream composition; do not repeat the eliminated forms merely to
increase an attempt count. Complete-executable equality remains the acceptance
gate:

```bash
python tools/decomp_workbench.py context --function func_8004C6A8 \
  --output .decomp-lab/grid-context-new
python tools/decomp_workbench.py check --source src/scene/render_context.c \
  --candidate .decomp-lab/grid-full-unit-new.c \
  --output .decomp-lab/grid-check-new
```

The candidate must contain the complete source unit, with only the intended
function replaced. A zero-difference result is required before promotion.
[render-matching-checks.json](render-matching-checks.json) records private
proof/comparison hashes, observation scope and unchanged counts. Source
candidates, binary inputs and raw reports remain private. Public CI does not
execute these proprietary-input checks.
