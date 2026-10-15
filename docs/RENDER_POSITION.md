# Original world-position and streaming composition

The original position lookup passes **6,141 native executions over 5,919
distinct fixtures, with zero stubs**. A further **5,670 distinct cases** execute
the complete lookup alongside grid
generation and streaming: nine original functions, with two explicit GTE
contracts. This removes the position-lookup contract from that composition.
It does not accept whole rendering, scene lifetime or PS1 timing.

The tool detects six deliberate instruction faults and observes the original
division-by-zero `BREAK` path in three cases. Canonical game code is unchanged;
no function is promoted. Metadata, source pins and before/after counts are in
[render-position-checks.json](render-position-checks.json).

## Original call chain and recovered rules

The canonical render-context vtable binds slot `0x10C` to `func_8004C158`,
the wrapper that invokes the world-coordinate resolver. The full chain is:

```text
func_8004C158 -> func_8004C1C0 -> func_8004C470 -> func_8004C434
                              -> func_8004C368 -> func_8004C434
```

The five functions contain 1,004 native bytes. Their table targets, bytes and
symbols are verified against the canonical executable before execution.
World position comes from the context's owner/inner coordinate record. An
optional output argument receives its pointer. Without a result buffer the
wrapper returns the cached context address at `0xBC`; it skips resolution.
With a buffer, a successful resolver returns that cached address and a missing
world slot returns null without changing the result buffer.

The later [typed query result cleanup](RENDER_QUERY_RECORD.md) reuses the
resolver's 44-byte output record in `func_8004CC74`. Actual compiler traces
explain its 48-byte local allocation, and the complete executable is unchanged.
The fixture counts and native scope in this position audit remain unchanged.

The selector considers labels 0 through 6, resolving each through the actual
seven-record table. Record storage order does not alter label priority. Its
horizontal bounds are half-open intervals of size `0xA000` in x and z.
In height-layer mode, label i accepts y in `(-0x800*(i+1), -0x800*i]`;
flat mode ignores y. Signed 32-bit endpoint wrapping is retained, including
intervals whose upper endpoint wraps below their lower endpoint.

The resolver splits each object marker using the signed layout divisor, with
quotient truncated toward zero and byte-sized quotient/remainder outputs.
It computes 2,048-unit cells, centered local residues with a 1,024-unit bias,
origin-relative positions, the selected record pointer and its marker. The
independent model retains native byte/halfword wrapping and untouched output
padding. A zero divisor reaches the original `BREAK` at `0x8004C384`, word
`0x0007000D`. Unicorn subsequently reports PC zero; the instruction hook
records the actual break location before the exception. The game's exception
handler and original hardware response do not execute in this audit.

## Bounded evidence

| Position fixture group | Native executions |
| --- | ---: |
| Horizontal bounds and cell edges | 4,536 |
| Height-layer bounds and overlapping rectangles | 1,008 |
| Cached and missing lookup paths | 36 |
| Signed marker partition | 429 |
| Record-label scans and misses | 96 |
| Signed world-coordinate wrapping | 36 |
| **Total** | **6,141** |

The position phase contains 222 repeated input executions: 216 across the
height-layer/overlap cases and six in the cached/missing group. They are
counted as executions, preserving **5,919 distinct position inputs**. The
composition phase has no repeated case inputs. The first private report
predates this count clarification and remains preserved separately.

Lookup outcomes are 3,525 resolved positions, 2,073 missing world slots and
18 cached lookups without a result buffer. The other cases enter the marker
partition and label helpers directly. Three segment aliases, two record
permutations and whole guarded context, owner, coordinate, table, slot and
output buffers are checked, alongside exact returns, call order/arguments,
stack guards, GP, RA and saved registers.

The composition executes those five functions plus `func_8004C6A8`,
`func_8004C93C`, `func_8004CAF0` and `func_8004C588`: **2,560 native bytes**.
Its 5,670 cases cover all seven labels, cell edges and centers, both angular
orientations, three projection sign pairs, record permutations and segment
aliases. It records 2,268 transverse and 3,402 longitudinal decisions, emitting
one, two or three rectangles. Whole info, matrix and template outputs and the
native row/selector trace agree with the independent scalar/rectangle models.
`RotMatrix` and `ApplyMatrixLV` still have explicit argument/output contracts.

Fault controls alter signed division, the local-coordinate bias, the horizontal
upper bound, record stride and wrapper success condition. A sixth repeats the
bias fault through the composition. Five produce output/trace differences;
the stride fault produces an invalid memory read, recorded distinctly.

The fixtures own their valid seven-slot object graphs and coordinate records.
Natural level construction/ownership, invalid graphs, actual GTE operations,
textures, framebuffer output and PS1 timing need separate evidence. Counts
distinguish executions and distinct fixture inputs; they do not count accepted
scenes or whole original features. Earlier three-contract
[streaming evidence](RENDER_STREAM.md) remains preserved at its original scope.

## Reproduce locally

After a current canonical build, install `requirements-analysis.txt` in your
Linux/WSL analysis environment:

```bash
python tools/verify_render_position.py \
  --output .decomp-lab/render-position-native-new.json
```

The report path must be new and private. The tool reads your canonical input,
changes only its own Unicorn memory, and makes no model API calls. Public CI
uses synthetic fixtures and needs no game, emulator or BIOS files. All **188**
local tooling tests pass on Windows Python 3.14 and Linux Python 3.13.

## Matching C and before/after counts

A separate natural API experiment combines longitudinal origin calculation
with its row/column dimensions. All 360 source forms compile under the pinned
flags, but none matches; the smallest difference is 91 bytes. The earlier
ordered-store C candidate still differs in 13 bytes, and the four-byte
candidate still reverses two stores. Neither is promoted.

Before and after this supplement, matching game C remains **194,884 / 199,912
bytes (97.48%)**, with six known game functions in assembly. The inventory
retains 40 provisional groups, 35 with every listed core function in C, and
zero whole groups independently accepted. NPC counts remain 107 C callbacks
and 11 with bounded checks; developer capabilities remain 10 and optional
mods 3. The exhaustive original feature total remains unknown. The complete
505,856-byte canonical executable and earlier feature records are preserved.
