# Original mode 0 structure effects and consecutive updates

The generation checker now executes mode 0's late child effects through the
actual rotation, fractional arithmetic, translation and periodic reset methods.
This extends the earlier [structure profile](GENERATION_STRUCTURES.md), whose
1,116 fixtures excluded the five nonzero-rate variants. Its results remain a
frozen earlier snapshot.

| Current profile | Per original or C-candidate image |
| --- | ---: |
| Standalone graph fixtures | 3,116 |
| Consecutive-update histories | 40 |
| Update frames across those histories | 480 |
| Original routines actually entered | 15 |
| Deliberate faults detected | 9 |
| Substituted dependency outputs | 0 |

All eight mode 0 rate variants and all four active child layouts are covered.
The original and the padding-free complete C candidate agree with the separate
model on full structure, coordinate, pose, child-node, sprite, size-key,
player/world and list buffers. Ordered calls, final RNG state, stack and saved
registers are checked. The candidate still differs in ten executable bytes and
remains outside the canonical build.

## Recovered update behavior

The original increments each structure's tick before processing its effects.
Mode 0's child work requires a nonzero layout, a nonzero rate and an unsigned
tick of at least 501. The five nonzero rate words and periods are:

| Variant index | Native rate | Position-reset period |
| --- | ---: | ---: |
| 3 | -1 | 24,500 |
| 4 | -2 | 12,250 |
| 5 | -4 | 6,125 |
| 6 | -16 | 1,531 |
| 7 | -256 | 95 |

The period uses truncating division of 24,500 by the rate and then its absolute
value. After activation, the structure and both child nodes receive the
original small yaw increment. Their Euler words use signed remainder at
4,096 units, including negative values. The first child adds the rate to its
Z position; the second adds rate plus three. Coordinates are marked dirty.

At a period boundary, the two child positions are replaced after that movement.
Layouts 1 and 2 use successive X offsets from the signed size key and the
original scale table. Layouts 3 and 4 use successive Y offsets. The replacement
also clears the accumulated Z displacement for the original zero-Z base vector.
This ordering matters across frames.

The forty histories cover each of the four active layouts and five nonzero
rates at late activation and the first period reset. Twelve consecutive calls
keep prior graph state while player position and world height change. The
checker measures 12,360 native rotation entries, 8,240 additive translations,
760 reset-method entries and 16,320 RNG entries per image across the standalone
and history profiles.

Nine private faults cover the preceding five controls plus the activation
tick, second-child offset, reset period and rotation destination. Each report
records a positive execution count for the changed instruction. No game input
or canonical instruction is rewritten.

## Source and acceptance boundaries

Six additional direct aggregate forms compile to exactly the same rejected
140-byte output as the earlier live argument-pair helper. Both fields are used;
loop/function scope, initialization and ordinary `register` qualifiers do not
remove the nonoriginal stores. The qualified source-form total is now 40 with
no exact match. This leaves the scalar candidate's original eight-byte frame
lifetime unexplained.

The histories start from manually assembled valid graphs. Construction,
parameter-selection provenance, natural encounters/lifetimes, callback-driven
list/count mutation, null player vectors with live structures, rendering/audio
and PS1 CPU timing remain open. The methods are outside the 107-entry NPC
catalogue; its bounded count stays 16. No whole feature is accepted.

Reproduce the current checker after a matching build and optional WSL analysis
dependencies:

```bash
python tools/verify_generation_structures.py \
  --output .decomp-lab/generation-effects-new.json
```

An optional `--candidate` checks a complete image whose differences are confined
to the selected 136-byte generation-update function. Exact source matching
remains a separate workbench gate.

[generation-effects-checks.json](generation-effects-checks.json) pins the
expanded profile, source diagnostics, original methods/tables, faults and
producer/tests. All 346 synthetic tooling tests pass on Windows and WSL.
The 305-object canonical build and earlier clean inputs remain unchanged.
C remains 194,212 / 199,912 (97.15%), with nine assembly functions and 24 inherited
source explanations. The 40 provisional groups, ten developer capabilities
and three optional mods retain their separate counts. This developer checker
changes no original behavior and invokes no model API.
