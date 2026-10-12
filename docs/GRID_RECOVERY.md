# Grid-window source recovery and prologue

The [published C fragment](../research/render_grid/README.md) improves the
candidate that preserves native store order from **13 to 11 differing
executable bytes**. All eleven differences belong to three prologue
instructions. The remaining **162 / 165 instruction words** and every byte
outside the 660-byte function match. This is source-recovery progress, not a
C promotion; the canonical game retains `func_8004C6A8` in assembly.

The earlier four-byte candidate is closer by byte count but reverses dimension
stores in 68,306 cases. It remains a rejected control, as documented in the
[ordered-store audit](RENDER_MATCHING.md).

## Remaining instruction order

| Address | Original | Current C candidate |
| --- | --- | --- |
| `0x8004C6BC` | Save incoming `fp` at stack offset `0x90` | Set `a1` to stack offset `0x10` |
| `0x8004C6C0` | Copy incoming height from `a2` to `fp` | Save incoming `fp` at stack offset `0x90` |
| `0x8004C6C4` | Set `a1` to stack offset `0x10` | Copy incoming height from `a2` to `fp` |

The comparison covers the complete 505,856-byte executable. Candidate SHA-1
is `b92b6f3868ca6362de2a6b160a67adbdbf56949b`; the original remains
`76322eeade5ebb22dca57fdeac7d68c30f06308d`. Two complete private builds,
including the formatted public fragment, produce this same candidate image.
Original source, compiler configuration and the canonical image are preserved.

## Actual compiler evidence

The [allocation tracer](COMPILER_ALLOCATION.md) now accepts a legitimate
unassigned-register result (`-1`) when GCC omits that pseudo-register from its
final disposition list. An assigned register still cannot be missing, and a
spilled register cannot be reported assigned. One regression test checks these
distinctions; the initial conservative rejections retain their raw outputs.

Four qualified observations preserve complete normal/debugger assembly,
check actual register returns against RTL dispositions and verify every
observed priority-comparison return against the reference calculation:

| Input | Global allocator calls | Priority comparisons |
| --- | ---: | ---: |
| Earlier store-reversing candidate | 14 | 38 |
| Earlier store-correct candidate | 14 | 39 |
| New local-dimension candidate, standalone | 14 | 38 |
| Formatted public fragment in the complete source unit | 14 | 38 |
| Total | 56 | 153 |

Each run records two unassigned global returns. Local and equivalence
entry/return observations also complete in every run.

The earlier store-correct source gives width four references over 52 live
instructions: priority 1,538, tying cell-z's five references over 65
instructions and selecting width first for `s6`. The local-dimension source
gives width 53 live instructions and priority 1,509. Cell-z then receives `s6`
and width receives `s7`, as the original does. The complete-unit trace confirms
these actual compiler returns.

Its RTL deletes the original incoming-height parameter move and puts the real
local-height capture after `FUNCTION_BEG`. The stack-buffer address setup is
scheduled ahead of that capture. This locates the remaining argument/capture
problem without proving the original author's declarations or justifying
forced registers, padding or copied instructions.

## Rechecked source comparisons

This pass independently checks source hashes and emitted bytes for 203
candidate compilations, including controls:

| Hypothesis | Compilations | Minimum differing bytes |
| --- | ---: | ---: |
| Preserve extents and reuse real incoming words for cell coordinates | 14 | 11 |
| Local extent captures and initialization boundaries | 24 | 11 |
| Distinct consumed dimension/edge roles | 48 | 11 |
| Low-16-bit origin operands and local widths | 27 | 13 |
| Typed signed-byte coordinate getters | 30 | 13 |
| Ordinary `const`/`register` and traditional argument declarations | 36 | 11 |
| Setters returning a consumed installed extent | 24 | 13 |

None matches. A first getter with incorrect pointer-member syntax is rejected
separately and repaired in a fresh directory. Warnings about potentially
uninitialized orientation/correction values are retained; the angle fixtures
exercise the source's complete interval partition. No padding or physical
register binding is introduced.

## Native comparison and current scope

The original and new candidate pass the existing **74,832 fixtures each**,
including whole guarded buffers, ABI rules, dimension-store order and immediate
readback. Rows at `0x80` precede columns at `0x84`. The older four-byte control
retains 68,306 order failures. This is 224,496 variant runs over the same 74,832
inputs, not new original behavior cases. Four external lookup/rotation/matrix/
builder contracts remain explicit in this scalar audit.

[grid-recovery-checks.json](grid-recovery-checks.json) records result hashes,
producer/input identities, full-image comparisons and compiler observations.
The public recipe prepares a complete candidate without editing the game.
It must pass complete-executable equality before promotion. Native scenes,
framebuffers, original hardware and full PS1 timing acceptance remain open.

Matching C stays **195,844 / 199,912 bytes (97.97%)**. Five assembly functions
and five inherited source-padding explanations remain. Listed core source
groups stay **37 / 40**; independently accepted whole groups stay **0 / 40**.
The 107 original NPC callbacks with C bodies, ten developer capabilities and
three optional mods are unchanged. Research and analysis remain separate from
original gameplay; this work makes no model API calls.
