# Bounds predicate source lifetimes

The smallest remaining assembly function now has a reproducible
[C research candidate](../research/render_bounds/README.md) with **21 differing
executable bytes**, improving on the earlier published 38-byte comparison.
It remains unaccepted: the matching game retains the original assembly, and
compiled C coverage is unchanged.

The 21-byte form was already retained privately. This publication adds its
recipe, current-unit qualification, allocation observations and candidate fault
controls; it does not claim a new algorithm discovery.

## Complete comparison

The recipe inserts the fragment into the current complete render-context unit
using its shared bounds type. Both executables are 505,856 bytes. The candidate
function is the complete 108-byte sized MIPS ELF symbol at `0x8004CD38`; every
byte outside that span matches. A diagnostic link retaining symbols converts
back to the same complete candidate image.

The shared record calls its second axis Z. The older generic fixture checker
calls that byte Y; both names refer to the second coordinate at the same offset.

Original and candidate agree on the existing 4,648 native inputs: whole guarded
buffers, result words, read order and widths, zero writes, stack/global-pointer
state and saved registers. Execution is confined to the complete candidate
function. The published fragment emits exactly the candidate bytes executed in
this campaign. Repeated runs add no distinct original behavior cases.
Four candidate-local faults are detected, with every changed instruction
observed in its detecting fixture. Each control uses an input from the existing
positive domain.

The [original profile](RENDER_BOUNDS.md) covers byte sweeps, signed extremes,
reversed intervals, aliases, unaligned byte pointers, segment aliases and null
bounds with an unmapped coordinate pointer. Renderer/stage composition, natural
scenes, framebuffer/audio output and PS1 timing remain outside this scalar profile.

## Actual compiler decisions

Two qualified observations cover an isolated candidate and its complete source
unit. Each records one local-allocation pass, one equivalence update, six global
allocations and ten priority comparisons. Normal and observed complete assembly,
reference priorities and final register dispositions agree. Diagnostic options
change only compiler-option comments.

| Value | Original instructions | Observed candidate |
| --- | --- | --- |
| Preserved bounds pointer | `a2` | `a2` |
| Packed X intermediate | `a3` | `v0` |
| Persistent outside result | `v0` | `a3`, moved to `v0` at return |

The candidate's local allocator assigns `v0` to packed X before global allocation.
The persistent result then conflicts with that assignment. This locates the
remaining allocation problem without proving the original source boundary.

Sixty-eight qualified forms, including repeated controls, use the newer seed:

| Source family | Forms | Minimum differing function bytes |
| --- | ---: | ---: |
| Result/return widths and returned GNU statement expressions | 42 | 21 |
| Whole-predicate inline boundaries and return consumption | 17 | 21 |
| Nested final returns and packed-X guard placement | 9 | 21 |

None matches. Narrow local results produce 112-byte functions with 37 differing
bytes. Inline alternatives emit 104-byte functions with 89 differences;
nested-return alternatives retain 83 or 84. One preparatory naming error stops
before candidate compilation and is excluded from the 68. Its failure and the
corrected fresh run remain private.

Sixteen additional primitive-intersection plane-result forms, including two
controls, also find no exact match. Their best remains the separate 22-byte
collision candidate. Those comparisons resolve no collision source gate.

## Evidence and remaining gate

[bounds-source-lifetimes-checks.json](bounds-source-lifetimes-checks.json) pins
the source, recipe, tests, full-image comparison, native reference and compiler
observations. Original inputs, raw words, linked images, compiler dumps and
failed attempts remain private. Synthetic recipe tests check preservation and
invalid-input rejection without game files.

All 392 canonical game build inputs are retained. C remains
194,212 / 199,912 bytes (97.15%), with nine assembly functions, 24 inherited
storage explanations, 35 / 40 listed-core C groups and 28 / 107 bounded NPC
profiles. No entire feature group or whole NPC encounter is newly accepted.
Original behavior, AI-assisted tools and optional mods retain separate accounting;
the Bevy repository is unchanged. Complete executable equality and a reviewed
source explanation remain required before promotion.
