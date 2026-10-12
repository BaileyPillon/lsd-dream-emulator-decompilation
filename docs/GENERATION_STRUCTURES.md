# Original generation structure dispatch and source lifetimes

The original 136-byte `dream_generation_update_structure_entities` walks the
live structure list and invokes each object's virtual method at `0xEC`.
Its caller supplies a three-word position vector. The canonical generation
structure table binds that method to `func_800564F4`, which increments the
structure tick and calls the position/mode update. The position method at
`0xB8` replaces coordinates; it does not add a second copy of the position.

Eleven actual original routines execute in **1,116 bounded fixtures**, with
no substituted dependency outputs. The complete padding-free C candidate
passes the same fixtures but remains unaccepted because ten stack-layout
bytes differ from the canonical image. The matching build still retains this
function's assembly.

| Fixture group | Cases per image |
| --- | ---: |
| Generation guards, counts, modes and tick boundaries | 840 |
| Sprite RNG, relative/absolute scale and native word width | 216 |
| Mode 0 with disabled children or its first three zero-rate variants | 60 |
| Total | 1,116 |

The comparison checks full structure, coordinate, sprite, player, world and
list buffers; ordered updates, position changes, sprite scaling and RNG calls;
final RNG state; and return, stack and saved-register preservation. Up to 17
structures use the original virtual tables. The original array's next mapped
symbol is 68 bytes later, matching those 17 pointer slots.

Each image enters the structure update 4,380 times, sprite scaling 8,160 times
and the original RNG 16,320 times. Mode 3 runs its four child sprites through
the real scaling method and eight RNG calls per structure. Five deliberate
private faults are detected: the generation guard, list advance, absolute
position mode, sprite scale destination and RNG increment.

These are manually assembled valid graphs. Modes 1, 2 and 3 use their actual
update paths. Mode 0 excludes later child effects for nonzero-rate variants.
Construction, natural encounters, lifecycle histories, dynamic changes to the
list/count inside callbacks, null player vectors with live structures,
rendering/audio and PS1 CPU timing remain open. These methods are outside the
107-entry NPC callback catalogue; bounded NPC coverage stays 16 / 107.

## Source and compiler findings

Thirty-four qualified live-argument, typed-slot and aggregate source forms
retain no exact match. Two initial aggregate-return diagnostics had an unused
formal argument; corrected forms remove it and retain the same nonmatching
output. The two initial diagnostics remain private and excluded from the
qualified count.

| Complete-unit source form | Function bytes | Image bytes | Changed image bytes |
| --- | ---: | ---: | ---: |
| Scalar position-pointer candidate | 136 | 505,856 | 10 |
| Live argument pair passed by pointer | 140 | 505,860 | 155,780 |
| Live argument pair passed by value | 164 | 505,884 | 150,752 |

The scalar candidate has a 32-byte frame; the original reserves 40 bytes.
The pointer form reserves a live eight-byte pair but emits stores absent from
the original. The by-value form retains a 24-byte virtual local area: eight
bytes for the pair and sixteen for its inline argument copy. Actual GCC 2.6.3
stack and lifetime observations preserve complete normal assembly. They explain
these rejected forms, not the original missing lifetime.

The [research fragments](../research/source_layout/README.md) contain the typed
scalar candidate and both aggregate hypotheses. Reproduce the native profile
in WSL after a current matching build and optional analysis dependencies:

```bash
python tools/verify_generation_structures.py \
  --output .decomp-lab/generation-structures-new.json
```

Use `--candidate` with a complete private candidate image whose differences are
confined to this 136-byte function. The existing source-workbench comparison
still decides exact matching; the native checker does not promote C.

[generation-structure-checks.json](generation-structure-checks.json) pins
private comparisons, compiler observations, native functions/tables, producer
identities and tests. Game inputs, raw buffers and altered machine code stay
private. All 340 synthetic tooling tests pass on Windows and WSL. Current C
remains 194,212 / 199,912 (97.15%), with nine assembly functions and 24 inherited
source explanations. No whole feature is accepted or original behavior added.
The developer analysis capability and optional mods remain separate from the
original game; this checker makes zero model API calls.
