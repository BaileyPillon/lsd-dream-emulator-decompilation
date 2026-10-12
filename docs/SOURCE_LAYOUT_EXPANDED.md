# Expanded source-layout audit and corrected recovery status

The earlier [five-function audit](SOURCE_QUALITY.md) inspected selected
`dummy_stack_padding` declarations. A wider review now verifies **28 functions
with unused local storage**, covering 6,720 compiled game-function bytes and
446 declared local bytes. Removing each selected array/tail and its empty
comparison produces a nonmatching complete executable. This does not certify
that every possible source workaround has been found.

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

## Build and continuation gates

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
