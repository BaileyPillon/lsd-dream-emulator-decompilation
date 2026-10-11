# Original rendering grid and streaming composition

The original grid-window helper now runs through its actual grid builder, row
splitter and seven-object slot selector. **45,408 bounded native cases pass**,
and four deliberately wrong instructions are detected. This replaces the
builder contract in the [scalar grid audit](RENDER_GRID.md) with native
execution; position lookup, `RotMatrix` and `ApplyMatrixLV` remain explicit
contracts.

The private full C candidate passes the same composition fixtures, but its
four executable byte differences remain. It is not promoted. Matching game C
stays at 194,284 / 199,912 bytes (97.18%), with seven known assembly functions
and zero whole-feature acceptances. This adds evidence for F033; it adds no
original feature, NPC callback, optional mod or developer capability.

## Native dependency and recovered layout

| Function | Role | Native bytes |
| --- | --- | ---: |
| `func_8004C6A8` | Compute the grid window | 660 |
| `func_8004C93C` | Build rectangle records | 436 |
| `func_8004CAF0` | Split the lower row | 388 |
| `func_8004C588` | Find the first matching streaming object | 72 |
| **Total** | | **1,556** |

Before execution, the verifier checks the original `D_800866E8` table at
`0x800866E8`. Slot `0x120`, at `0x80086808`, targets `func_8004C588`. The fixtures
bind that same target in their guarded synthetic vtable. These are separate
addresses: `0x80086808` is the slot, not the table base.

The builder consumes signed halfword origins at context offsets `0x7C`/`0x7E`
and 32-bit extents at `0x80`/`0x84`. It intersects the window with cells whose
boundary is 20 and whose adjacent row shifts by 10. Origins below zero select
neighboring modes before splitting. The independent model constructs these
intersections and their emission order rather than calling the C candidate.

Each record at `0x8C + index * 12` contains a 32-bit streaming-object index,
then signed halfword x, y, width and height. The count is written at `0x88`.
The first upper piece is followed by any lower pieces, then the upper-right
piece. The lower-row helper receives the original full extent even when the
first upper piece was clipped. The fixtures produce one to four records.

The selector scans seven pointers at `context + 0xEC + index * 0x1C + 4`.
It compares each object's signed halfword at `0x32` with the requested mode.
The first matching index wins; a missing label returns index zero. Reordered,
duplicate, missing and signed-extreme labels check this original behavior.

## Checks and boundaries

| Fixture group | Cases |
| --- | ---: |
| All 400 cell positions, three radii, three heights, four orientations and three vector signs | 43,200 |
| Angle boundaries and corner wraps | 192 |
| Seven label layouts, segment aliases and different initial contents | 2,016 |
| **Total** | **45,408** |

The original executes the window helper, builder and row splitter 45,408
times each, and the selector 90,148 times. Results include 15,960 one-record,
18,672 two-record, 6,260 three-record and 4,516 four-record cases.

Checks compare emitted records, count and order, whole guarded context/owner/
inner/angle/vtable/streaming-object buffers, native call order and all eight
row arguments, matrix/info/template buffers, stack guards, GP, RA and saved
registers. Execution outside the four reviewed functions and three contracts
fails. Controls change the height-wrap threshold, width-wrap threshold,
object-label field or height store; all four are detected in private Unicorn
memory. Original files are preserved.

These fixtures use bounded cell coordinates, radii and dimensions. The
[scalar audit](RENDER_GRID.md) separately covers every angle word and extreme
integer cases. This composition does not prove that every fixture occurs in
play. The three remaining contracts supply lookup and transform results;
real position resolution, GTE, textures, scene lifetime, framebuffer and PS1
timing still need their own evidence.

After a current canonical build and installation of
`requirements-analysis.txt` in Linux/WSL:

```bash
python tools/verify_render_stream.py \
  --output .decomp-lab/render-stream-native-new.json
```

The command requires a new private report path and preserves earlier reports.
It does not change the game or call a model API. Public CI tests synthetic
fixtures; it does not distribute or build the proprietary game inputs.

## C candidate and private Ghidra

The full candidate SHA-1 remains
`cad22662267d1d719f2fa0195cb0d55c4e2bf145`: two dimension stores in the grid
helper are reordered. Its 45,408 passing composition cases strengthen bounded
behavior evidence without satisfying the exact C acceptance gate. The three
downstream functions were already in matching C; their native execution here
does not increase C coverage.

Private Ghidra now has reviewed prototypes for the selector and eight-argument
row helper. Parameters use `a0:4`/`a1:4` for the selector; the row helper uses
`a0:4` through `a3:4`, then four 4-byte stack arguments at `0x10` through `0x1C`.
The saved project retains all 460 native bytes unchanged. `__stdcall` is the
explicit convention in Ghidra's MIPS compiler specification.

[render-stream-checks.json](render-stream-checks.json) records source/evidence
pins and unchanged counts. Binary inputs, native reports, Ghidra database and
nonmatching C candidate remain private.
