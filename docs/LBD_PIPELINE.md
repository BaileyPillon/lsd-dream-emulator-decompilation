# Original level-model loader audit

The original `func_8004BE54` and a private C candidate pass **418 local LBD
files**, each loaded once and then reloaded through the native destructor.
The **1,672 loader runs** use the original allocator, constructors, tile
decoder, model accessor and SDK mapping/linking routines. Five deliberately
wrong controls change checked outputs. There are **zero dependency stubs**
and one explicit initial-state contract: CD initialization has already finished.

The complete candidate build still differs in **118 executable bytes**.
The canonical build retains the original loader assembly. Two virtual-call
declarations were corrected; the complete standard build remains byte-identical
to `SLPS_015.56`. Recorded hashes and scopes are in
[lbd-pipeline-checks.json](lbd-pipeline-checks.json).

## Native data flow

The loader receives a streaming slot in its second argument. It points the
slot's file object at the LBD tile grid, destroys an existing TMD model, and
constructs a new model from the stream's TMD offset. The model constructor
allocates a null-terminated primitive-pointer array and one object for each
TMD descriptor. Actual `GsMapModelingData` converts relative descriptor offsets
once; subsequent loads use the already-mapped data.

The file object's query returns a model handle for an occupied record, `-1`
for an empty record, and zero once the cell index reaches 400. Occupied records
select a TMD descriptor, call `GsLinkObject4`, copy cell position and orientation,
and mark the node dirty. Empty records clear its model and descriptor while
also marking it dirty. A continuation keeps the same cell index and links to
an additional node. Only an occupied continuation advances the extra-node
cursor; this preserves the original empty-record behavior.

The observed corpus contains:

| Measure | One load of each of the 418 files |
| --- | ---: |
| Fixed grid cells | 167,200 |
| Additional occupied continuation records | 270 |
| Occupied records | 95,842 |
| Empty records visited | 71,628 |
| TMD object descriptors constructed | 13,033 |
| Primitive packets walked by linking | 281,945 |

Repeated loads double these visits per implementation. The constructor and
destructor exercise native allocation, free-list coalescing and virtual calls;
the external LBD buffer remains owned by the caller.

## Virtual-call declarations

The canonical file-object vtable at `0x8006D940`, slot `0x78`, binds
`class_1C92C_unk29` at `0x8002C278`. Its declaration now returns a 32-bit result
and takes the object, payload and cell index. The original method supplies
four registers to the TMD accessor, forwarding the cell and payload as well
as the model and descriptor index.

The default TMD vtable at `0x8006F13C`, slot `0x80`, binds `func_80043B58` at
`0x80043B58`. That implementation consumes the model and index and returns the
selected 32-bit handle. Its declaration now reflects those consumed arguments;
the query's explicit four-argument forwarding is preserved. Native
`file_driver_set_class(0x13)` initializes the shared driver slots before the
tests; the fixture does not invent replacement callbacks.

## Verification and limits

The cold-load oracle independently constructs expected tile outputs, mapped
and grouped TMD data, allocation layout, complete heap and caller buffers.
The reload executes the real destructor and checks complete caller buffers,
defined constructor fields and allocation headers. Native freeing can alter
otherwise uninitialized payload fields; the two implementations' entire
reloaded arenas are also compared. Guard bytes, unused stack, GP, RA and saved
registers are checked. Source, input and canonical-build hashes stay pinned.

The local files come from the previously inventoried English-v1 disc assets
with the canonical Japanese executable. This proves the recorded composition
under that input and state boundary. Cold CD hardware initialization, pending
I/O requests, caller node allocation/ownership, memory aliasing, actual GPU
drawing, PS1 timing and whole-game acceptance remain outside this audit.

The candidate's full translation unit was compiled with the canonical flags
and linked against all 305 baseline objects. Its 600-byte loader body equals
the body used in the native comparisons, but its executable has 118 byte
differences. Another 191 unique source trials found no exact match; one
duplicate was skipped. No C function was promoted.

Run with your own extracted assets and matching build:

```sh
python tools/inventory_animations.py --layout /path/to/disc.xml --output .decomp-lab/levels-inventory-new.json
python tools/verify_lbd_pipeline.py --inventory .decomp-lab/levels-inventory-new.json --output .decomp-lab/levels-native-new.json
# Optional bounded comparison with a private compiled 600-byte loader body:
python tools/verify_lbd_pipeline.py --inventory .decomp-lab/levels-inventory-new.json --candidate .decomp-lab/candidate-loader.bin --output .decomp-lab/levels-candidate-new.json
```

Reports must be new files inside `.decomp-lab`. The reusable checker is part
of the existing analysis capability, with no model API calls. Matching C bytes
remain 194,284 / 199,912, seven game functions remain in assembly, and the
provisional 40 feature groups retain zero whole-feature acceptances. Original
NPC behavior, separate AI-assisted tools and optional mods retain their counts.
