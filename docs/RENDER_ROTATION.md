# Original SDK rotation and streaming composition

The original 652-byte SDK `RotMatrix` passes **203,259 native executions over
203,257 distinct fixtures, with zero stubs**. It uses ordinary MIPS operations
and the original packed trigonometric table, without issuing GTE instructions.
The later world-to-stream composition executes **ten original game/SDK
functions in 5,670 distinct cases**, retaining only the `ApplyMatrixLV`
hardware contract. This removes the rotation contract from the earlier
[position composition](RENDER_POSITION.md).

Four deliberate faults are detected. The canonical executable is unchanged;
no game or SDK function is promoted to C, and no whole original feature is
accepted. [render-rotation-checks.json](render-rotation-checks.json) records
source pins, complete private evidence hashes and unchanged before/after counts.

## Recovered rotation rules and table boundary

`D_80066BE0` is the helper's 16,384-byte table: 4,096 little-endian records,
each containing a signed 16-bit sine followed by a signed 16-bit cosine.
Its canonical symbol, bytes and hash are verified before execution. All
components are within the reviewed fixed-point range of -4,096 through 4,096.
The tool consumes this table locally; it does not distribute the table.

Each input Euler component is a signed halfword. For a negative angle the
helper indexes the low 12 bits of its absolute value, then negates the sine
component and retains cosine. A nonnegative angle directly indexes its low
12 bits. The table's cosine equals its sine shifted by a quarter turn, but
3,888 entries disagree with a periodic odd-sine reflection. The signed branch
therefore matters even when two angle encodings suggest an ideal periodic
equivalence. The audit retains the actual data and branch behavior.

The independent model forms Euler products and retains each fixed-point
arithmetic shift by 12. Negating a product before its shift can differ from
negating the shifted product; nested products also retain their intermediate
rounding. Results are stored as nine signed halfwords. The helper preserves
the remaining matrix bytes and returns the original matrix pointer.

All three input components are read before the first matrix write. Sixty
guarded fixtures check identical and partially overlapping input/output
buffers, including halfword-aligned offsets and address aliases. The model
uses the canonical table as a shared data input; it independently checks the
rotation arithmetic rather than claiming an independent reconstruction of
the table's generation.

## Bounded native evidence

| Standalone fixture group | Native executions |
| --- | ---: |
| Complete pitch halfword sweep | 65,536 |
| Complete yaw halfword sweep | 65,536 |
| Complete roll halfword sweep | 65,536 |
| Mixed sign and period boundaries | 6,591 |
| Overlapping input/output buffers | 60 |
| **Total** | **203,259** |

Each axis sweep fixes the other two components to a nonzero mixed rotation.
The shared intersection of the three sweeps contributes two repeated runs;
the report and an independent guarded-buffer/pointer audit retain **203,257
distinct inputs**. Signed and unsigned representations of the same halfword
are normalized before counting. This exhausts each individual halfword
domain at fixed other components, not the full three-angle Cartesian domain.

Each execution checks the complete guarded buffer, return pointer, stack
guards, saved registers, GP and RA. The real table remains unchanged in the
successful standalone and composed machine instances. Original input files,
source and complete canonical build also remain unchanged.

The composition executes the nine functions from the position audit plus
`RotMatrix`: **3,212 native bytes**. Pitch and roll vary across the seven
world labels; yaw retains the grid's angular cases. Its 5,670 distinct inputs
include record permutations and three address aliases. Actual rotation
coefficients reach the `ApplyMatrixLV` call and subsequent original grid/row
builders. Guarded buffers, full matrix/info/template outputs and native call
traces agree with the independent scalar, rotation and rectangle models.

The composition records 3,402 longitudinal and 2,268 transverse decisions,
emitting one, two or three rectangles. `ApplyMatrixLV` still supplies its
existing explicit projection outputs. Actual COP2/GTE operations, natural
level construction and ownership, scene output, invalid graphs, load delays
and PS1 cycle timing require separate evidence.

Fault controls change a fractional shift, negative-pitch reflection and one
packed sine-table bit. A fourth repeats the negative-pitch fault through the
ten-function composition. All four are detected using private Unicorn memory
without changing the original executable or table files.

## Reproduce locally

After a current canonical build and installation of `requirements-analysis.txt`
in your Linux/WSL analysis environment:

```bash
python tools/verify_render_rotation.py \
  --output .decomp-lab/render-rotation-native-new.json
```

The report path must be new and private. The tool makes no model API calls.
Public CI uses synthetic fixtures, including deliberate asymmetric table
values and staged-rounding cases; it needs no game, emulator or BIOS files.
All **201** local tooling tests pass on Windows Python 3.14 and Linux Python 3.13.
The first private smoke launch failed to import the repository module; its
log is preserved separately from the successful smoke and complete proof.

## Before/after counts and remaining recovery

Matching game C remains **194,884 / 199,912 bytes (97.48%)**, with six known
game functions in assembly. The closest ordered grid C candidate still
differs in 13 bytes; its four-byte alternative still reverses two stores.
Neither is promoted. Executing an inherited SDK helper does not raise the
game C numerator or claim SDK source recovery.

The inventory retains 40 provisional original groups, 35 with every listed
core function in C, and zero independently accepted whole groups. NPC counts
remain 107 C callbacks and 11 with bounded checks. Developer capabilities
remain 10 and optional mods 3. This extends the existing native-analysis
workflow; original game behavior remains separate from AI-assisted tools
and mods. The exhaustive original feature total is still unknown.
