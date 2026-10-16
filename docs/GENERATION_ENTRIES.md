# Original generation entry selection and world-coordinate conversion

The original `dream_generation_find_entry` consumes eight-byte records from
fourteen stage tables. The tables contain **56 original records**. A positive
signed type flag allows a record to be tested; zero and negative flags are
skipped. Every examined record advances the global index, including rejected
ones. A null query or an exhausted table returns without advancing it.

The scanner copies four placement bytes and six local-offset bytes into a
ten-byte spawn packet. The owner table `D_800866E8` binds virtual slot `0xE8`
to `func_8004B418`, which calls the actual coordinate converter
`func_8004B44C`. The converter reads exactly those ten packet bytes. Enlarging
the input record cannot explain the scanner's missing source lifetime.

| Verified profile | Per original or complete C-candidate image |
| --- | ---: |
| Original stage tables / entry records | 14 / 56 |
| Native fixtures | 4,116 |
| Actual original routines entered | 3 |
| Native world-transform calls | 12,844 |
| Deliberate faults detected | 6 |
| Substituted dependency outputs | 0 |

The fixture groups cover 420 guard/flag cases, 3,024 boundaries for every
original entry, and 672 signed world/distance edges. The original and the
padding-free complete candidate agree on full owner, grid, output, query,
distance and all-entry buffers; ordered ten-byte packet inputs; returned entry
pointer and final index; stack restoration and saved registers. Every deliberate
fault has a positive measured execution count for its changed instruction.

## Recovered selection and transform rules

Four placement bytes encode signed tile X/Z and cell X/Z. The next six bytes
are signed local X/Y/Z offsets. The original data uses style selector zero for
all 56 records. Normal grids use the encoded tile row and grid height; a
nonzero mode uses row zero and height one. Odd normal rows shift X by
`0x5000`. Tile and cell spacing are `0xA000` and `0x800`, with the original
`0x400` local-cell offset. Original owner origins and packet Y offsets determine
world Y.

Selection uses wrapped native X/Z differences and their signed Manhattan
distance. Query Y does not enter that predicate. The distance must be strictly
less than the original type-specific range. Native overflow diagnostics preserve
the original wrapped result, including the `INT_MIN` absolute-value case;
these are arithmetic observations rather than reachable-gameplay claims.

Private controls alter index advancement, positive-flag eligibility, the style
halfword destination, the distance axis, the range predicate and grid-row parity.
The final control executes inside the real coordinate converter. Original
executables, source and canonical game behavior remain intact.

## Source and compiler findings

Thirty-eight qualified source forms check packet representations, pointer/value
style copies and live packet/transform helper boundaries. None matches the
complete executable. Six earlier boundary diagnostics left an unused local
after extracting its work; corrected forms remove it and preserve the same
negative output. The initial diagnostics remain excluded from the qualified
count.

| Published source hypothesis | Scanner bytes | Additional helper bytes | Frame bytes | Image changes |
| --- | ---: | ---: | ---: | ---: |
| Pointer style copy | 444 | 0 | 72 | 20 bytes, unchanged image length |
| Returned style value | 472 | 0 | 80 | 148,474 bytes, image grows by 28 |
| Style passed by value | 472 | 40 | 72 | 168,586 bytes, image grows by 68 |

The original scanner is 444 bytes with an 80-byte frame. The returned-style
form allocates a real six-byte temporary, increasing the compiler's virtual
local area from sixteen to twenty-four bytes. It reaches the original frame
size but emits an extra copy. Passing the style by value retains an emitted
forty-byte helper; its 512-byte standalone text section is not a 512-byte
scanner. ELF symbol sizes and complete link maps distinguish those spans.

The [research fragments](../research/source_layout/README.md) use a ten-byte
packet and explicit unsigned-word arithmetic for the native wrap behavior.
Those expressions reproduce the previous complete candidate images exactly.
Actual whole-unit compiler stack/lifetime observations preserve complete normal
assembly. The pointer-style candidate retains twenty stack-layout differences.
The later [method-return candidate](GENERATION_ENTRY_METHOD.md) supplies the
original frame through a consumed method temporary and reduces the complete
image's differences to six bytes. Its retained store and argument scheduling
still fail the exact source gate; both candidates remain outside the game.

Reproduce after a matching build and optional WSL analysis dependencies:

```bash
python tools/verify_generation_entries.py \
  --output .decomp-lab/generation-entries-new.json
```

An optional `--candidate` compares a complete image whose differences are
confined to the selected 444-byte scanner. Exact matching remains a separate
source-workbench gate.

[generation-entry-checks.json](generation-entry-checks.json) pins original
tables/methods, source diagnostics, three published complete candidates,
compiler observations, native comparisons and tests. All 355 synthetic tooling
tests pass on Windows and WSL. Manual valid grid/query/flag contexts leave
natural construction, exact per-map parameter provenance, nonzero selectors,
sound/entity spawning, lifetimes, rendering/audio and PS1 CPU timing open.
These methods add no NPC catalogue entry or whole-feature acceptance. Current
C remains 194,212 / 199,912 (97.15%), with nine assembly functions, 24 inherited
source explanations and 35 / 40 listed-core C groups. Original behavior, ten
developer capabilities and three optional mods stay separate; no model API is
invoked by this checker.
