# Expanded source-layout audit and corrected recovery status

> Historical baseline: later generation and menu recoveries replace the four
> withdrawn functions with matching C. The subsequent
> [callback storage recovery](CALLBACK_STORAGE_RECOVERY.md) explains five of the
> 24 inherited declarations. The later
> [constructor and actor recovery](CONSTRUCTOR_ACTOR_STORAGE.md) explains two
> more, leaving seventeen identified explanations open.
> The subsequent [accessor recovery](ACCESSOR_STORAGE_RECOVERY.md) explains
> three more, leaving fourteen. Their existing C bytes and all gameplay
> acceptance counts are unchanged.
> The later [input storage recovery](INPUT_STORAGE_RECOVERY.md) explains six
> further frames, leaving eight identified explanations open.
> Measurements below retain their original snapshot and scope.

The earlier [five-function audit](SOURCE_QUALITY.md) inspected selected
`dummy_stack_padding` declarations. A wider review now verifies **28 functions
with unused local storage**, covering 6,720 compiled game-function bytes and
446 declared local bytes. Removing each selected array/tail and its empty
comparison produces a nonmatching complete executable. This does not certify
that every possible source workaround has been found.

A later [render query record cleanup](RENDER_QUERY_RECORD.md) removes an
additional four-byte tail outside this selected audit. Actual compiler traces
show that the real 44-byte record naturally receives the required 48-byte
local allocation, preserving the complete executable. That additional finding
does not reduce the 24 unresolved inherited functions recorded below.

The subsequent [query interface cleanup](RENDER_QUERY_API.md) removes another
four-byte tail in `func_8004AEA4`, also outside this selected audit. The shared
44-byte result receives a natural 48-byte compiler allocation alongside a
separate, fully used 48-byte saved builder record. Both full builds remain
canonical; the 24 unresolved inherited functions remain unchanged.

The [glyph region cleanup](GLYPH_REGIONS.md) replaces two sixteen-byte caller
buffers with the twelve-byte record actually written by their helper. Compiler
observations show natural sixteen-byte allocation in both callers. These eight
additional source-tail bytes were outside this selected audit. The separate
`glyph_get_char` declaration remains unresolved; the count stays at 24.

Twenty-four declarations are present in the imported upstream source. Four
others were introduced when previously retained assembly was promoted during
this project. Those four promotions do not satisfy the no-padding recovery
criterion. Their assembly fallbacks have been restored, and their readable
padding-free candidates remain in [source-layout research](../research/source_layout/README.md).
The original executable and gameplay are unchanged.

| Measure | Before correction | After |
| --- | ---: | ---: |
| Game-function bytes compiled from C | 195,844 / 199,912 (97.97%) | 194,212 / 199,912 (97.15%) |
| Remaining assembly functions | 5 | 9 |
| Known unused-storage source explanations | 5 in the earlier selected audit | 24 remaining after the wider 28-function audit and four withdrawals |
| Groups with every listed core function in C | 37 / 40 | 35 / 40 |
| Entire feature groups independently accepted | 0 / 40 | 0 / 40 |

The four withdrawn functions total 1,632 bytes:

| Function | Bytes | Padding-free complete-image differences |
| --- | ---: | ---: |
| `dream_generation_update_structure_entities` | 136 | 10 |
| `dream_generation_find_entry` | 444 | 20 |
| `func_8003D73C` | 580 | 20 |
| `func_8003DAD4` | 472 | 16 |

F024 and F025 again have retained core assembly. F035 was already incomplete
and now has two additional retained functions. The C-byte count measures
compiled source, including unresolved inherited layouts. Excluding the entire
5,088-byte spans of the remaining 24 identified functions leaves 189,124 C
bytes; this is a conservative function-level exclusion, not a certification
that all other C is original or free of workarounds.

## What the wider review distinguishes

Unused standalone arrays, empty address-comparison branches and unused tails
in scalar index/key records require source explanations. Necessary record,
SDK vector and virtual-table offsets are representation details and remain
intact. For the spawn-key record, the original mood lookup writes exactly two
bytes; its fourteen-byte tail is not part of that output. Actor enumeration
retains the live index field while the separate dummy tail is investigated.

Each removal uses a fresh complete translation unit and the canonical compiler,
flags, objects and linker layout. Some removals change only stack displacements;
others change function sizes and downstream symbol/call addresses. Function
length and global image length alone therefore do not prove matching recovery.

All 28 private comparisons and current source/provenance measurements are
pinned by [source-layout-expanded-checks.json](source-layout-expanded-checks.json).
The earlier five-function report stays frozen. Its five literal findings were
valid within its stated search boundary; using that count for all current
source workarounds was incomplete.

The later [generation structure investigation](GENERATION_STRUCTURES.md)
checks 34 qualified source forms and three complete images. Actual compiler
observations distinguish live aggregate storage and inline argument copies
from the unexplained original eight-byte frame region. The typed scalar
candidate also passes bounded original/candidate behavior comparisons, but its
ten stack-layout differences leave the assembly and source counts unchanged.

The [entry scanner investigation](GENERATION_ENTRIES.md) confirms a ten-byte
input packet, checks 38 qualified source forms and rejects three complete
candidate images. A returned six-byte style temporary reaches the original
frame but adds a copy; passing the style by value emits a separate helper.
The closest candidate retains twenty stack-layout differences, so the original
assembly and current source-quality counts remain intact.

The [menu investigation](MENU_LAYOUT.md) confirms eight consumed XY bytes and
two callback declarations through 39 original glyph, graphics, list and heap
methods. Sixty-two source forms have no exact match. Real returned values can
produce the original frame size but add copies; by-value accessors can emit
separate helpers. Complete candidates retain 20 and 16 differences, so both
callers remain in assembly and unused storage is not reintroduced.

## Build and continuation gates

The [compiler memory-store investigation](COMPILER_MEMORY_STORES.md) checks the
inherited bit-field helper's eight-byte region with consumed state objects.
The closest pair preserves all original instruction words but adds two stores;
actual compiler decisions retain them. Eighteen argument-record hypotheses and
32 grid extent-word forms remain nonmatching. No storage explanation is resolved.

The corrected 305-object standard build and a separate fresh clean build both
produce the canonical 505,856-byte executable, SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d`. Original inputs, generated assembly,
complete candidate images and private compiler reports are not distributed.

Future promotions require complete byte equality and an explained source
layout. Unused arrays, dead pointer comparisons, instruction substitution or
physical register bindings cannot be used to improve the accepted recovery
count. Original NPC behavior, bounded comparison coverage, analysis tools and
optional mods retain their separate measures. The exhaustive feature total,
asset/dispatch closure and reviewed runtime requirements remain open.
