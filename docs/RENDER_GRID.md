# Original rendering grid-window checks

The original 660-byte `func_8004C6A8` passes **74,832 bounded native cases**,
including all 65,536 angle words. Eight deliberately wrong instructions are
detected. This recovers scalar rules around four explicit contracts: position
lookup, `RotMatrix`, `ApplyMatrixLV` and the downstream grid builder.

A full C translation-unit candidate passes the same fixtures but differs at
**four executable byte positions in two stores**. It remains private and is
not promoted. Game C recovery stays at 194,284 / 199,912 bytes (97.18%), with
seven known game assembly functions. This extends F033 evidence; whole
rendering and feature acceptance remain open. Original behavior, optional
mods and AI-assisted tools stay separate.

## Recovered scalar contract

The angle-record pointer is retained before calling virtual slot `0x10C`.
After that call, the function reads signed byte coordinates at output offsets
2 and 3 and the signed angle halfword at record offset `0x12`. The lookup's
return value is ignored. The fixtures explicitly check callback changes to
the angle, distance and radius and subsequent read order.

Negative angles receive `0x1000`, retaining the low 16 bits. The intervals
`[0x200, 0x600)` and `[0xA00, 0xE00)` select the transverse window; every other
angle word reaches the other orientation. A 32-byte matrix template is copied,
translation x/y are zeroed, and z receives context distance at `0x74`.
Rotation receives the angle triple at record offset `0x10`. Matrix application
uses the same translation pointer for input and output.

Let x/z be the signed cell coordinates, px/pz the supplied transformed vector,
and half the **unsigned** halfword at context offset `0x78`:

| Rule | Transverse window | Other orientation |
| --- | --- | --- |
| Rows at `0x80` | height | width |
| Columns at `0x84` | width | height |
| Initial x origin | x if px > 0; otherwise x - width + 1 | x - half - 1 if px > 0; otherwise x - half + 1 |
| Initial z origin | z - half - 1 if pz > 0; otherwise z - half + 1 | z if pz > 0; otherwise z - height + 1 |
| Correction component | pz | px |
| Corrected origin | z | x |

Correction uses an arithmetic right shift by 11. Clamping reads the radius
as a **signed** halfword: first replace values `>= radius` with `radius - 1`,
then replace values `<= -radius` with `-radius + 1`. Both checks execute,
including for zero and negative radii. Origins are stored as low 16-bit
halfwords at `0x7C`/`0x7E`, dimensions as 32-bit words. The builder is called
after these fields are written.

## Native evidence and limits

| Fixture group | Cases |
| --- | ---: |
| Complete angle-word sweep | 65,536 |
| Projection/clamp boundaries, including signed radius extremes | 896 |
| Signed coordinate, dimension, direction and wrap edges | 8,232 |
| Lookup results and callback mutation order | 72 |
| Segment aliases and different template contents | 96 |
| **Total** | **74,832** |

The original executes 6,526 transverse and 68,306 other-orientation cases.
The independent model uses angle intervals and native integer/store rules,
not the C candidate's branch expressions. Checks compare whole guarded
context/owner/inner/angle/vtable buffers, call arguments/order, rotation
inputs, intermediate matrices, final grid fields, matrix/info buffers,
stack guards, GP, RA and saved registers. Contracts overwrite volatile
registers. Execution outside the reviewed function/call boundaries fails.

Controls alter an angle interval, coordinate signedness, row extent, origin
boundary, radius signedness, shift kind, upper clamp or correction axis.
All eight are detected in private Unicorn memory; original files are intact.

The external contracts supply lookup data and the transformed vector, update
rotation bytes, and observe the completed grid. The template is fixture-owned.
Real GTE transformations, position resolution and downstream grid construction
do not execute. Scene, framebuffer and PS1 timing parity remain open. Extreme
dimension/radius fixtures describe native arithmetic without proving those
inputs occur in play.

After a current canonical build and installation of
`requirements-analysis.txt` in Linux/WSL:

```bash
python tools/verify_render_grid.py \
  --output .decomp-lab/render-grid-native-new.json
```

Reports require a new private path; existing evidence is preserved. Public
tooling tests use synthetic inputs.

## C and Ghidra recovery

The full candidate reproduces every executable byte outside two dimension
stores. It writes columns before rows in the second orientation, giving
candidate SHA-1 `cad22662267d1d719f2fa0195cb0d55c4e2bf145` rather than canonical
`76322eeade5ebb22dca57fdeac7d68c30f06308d`. Its matching fixture results do not
meet the zero-difference C acceptance gate.

Correcting the stores changes width's post-scheduling lifetime from 53 to 52
instructions. Its four references then tie cell-z's five references over 65
instructions under the priority rule in the archived
[GCC 2.6.3 source](https://mirrors.slackware.com/slackware/slackware-2.2.0/source/d/gcc/gcc-2.6.3.tar.gz).
The bundled compiler's dumps show width allocated before cell-z after that
change. This is consistent with the older source's tie handling, not proof
of the complete Sony compiler implementation. Equivalent edge arithmetic,
extent reads/types and SDK declarations did not close the gap. Canonical
flags are unchanged; no padding or physical register bindings are used.

Private Ghidra now has reviewed prototypes for caller `func_8004C620`, this
function, and builder `func_8004C93C`. Context uses `a0:4`; width/height use
`a1:4`/`a2:4`. Saved metadata and all 1,232 native bytes across these functions
were checked. The explicit calling convention is `__stdcall` in Ghidra's
MIPS compiler specification.

Hashes, source pins and counts are in
[render-grid-checks.json](render-grid-checks.json). Native reports, database
and nonmatching C candidate remain private.
