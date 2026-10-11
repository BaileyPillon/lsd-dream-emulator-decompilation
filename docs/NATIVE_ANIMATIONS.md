# Native grid, library and animation evidence

The supported audit reads an existing DUMPSXISO extraction without changing it:

```bash
python tools/inventory_animations.py --layout /path/to/disc.xml --output .decomp-lab/animations-new.json
python -m unittest discover -s tests -p test_inventory_animations.py -v
```

The layout reader requires the canonical LSD executable and bounds every source
path to its extraction directory. Reports retain the layout, original executable
and asset hashes, producer/dependency hashes, source-anchor hashes, original
instruction-range and vtable-word hashes, and sample record offsets. Existing
output reports are preserved. The 30 asset-free regression tests cover command
payloads, malformed offsets/extents, child and primitive references, cyclic
tile chains, streamed-library bounds, overlapping model entries, aliased
references, and input/output preservation. The latest full tooling suite
passed 134 tests; its log is `.decomp-lab/twenty-third-tooling-tests.log`.
A successful CLI exit means the report was saved; any
unresolved structures remain explicit inside it.

## Verified static corpus

The owned English-v1 extraction was audited on 2026-10-10. Its executable is
505856 bytes with canonical SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d`. The fresh local report is
`.decomp-lab/native-animation-lbd-inventory-twenty-third.json`; the preceding
`.decomp-lab/native-animation-inventory-current.json` report is preserved.
Local disc-derived reports and game assets are ignored rather than included in
contributions.

| Content | Instances in extraction | Distinct model content |
| --- | ---: | ---: |
| MOM models | 111 | 100 SHA-256 hashes |
| Animations | 122 | 108 |
| Frames | 4260 | 4076 |
| Records | 26797 | 25716 |

All 420 extracted MOM/LBD files were scanned. Valid models occur in 100 files;
nine containers contain multiple models. All 111 discovered MOM signatures pass
the native extent checks. No commands refer to missing child types from the
first animation, no parent references miss those types, and no one-based
primitive selections exceed the accompanying TMD object count. Each parsed
animation ends exactly at its next animation or TMD boundary. These counts
describe asset content; they do not change the provisional gameplay-feature
denominator in [the feature inventory](FEATURE_INVENTORY.md).

| Native grid/library content | Count |
| --- | ---: |
| Bounded LBD files | 418 of 418 |
| Fixed grid cells | 167200 |
| Additional tile records | 270 |
| Present tile records, including additional records | 95842 |
| Continuation links | 270 |
| Streamed MML libraries | 98 |
| MML references to MOM models | 109 |

Each native query enumerates 400 cells using a 20-column position calculation.
Tile records have a 12-byte stride, zero-based TMD model index, presence tag,
and grid-relative continuation offset. The audit bounds TMD descriptor tables
and walks continuation chains without executing them. A zero presence tag
suppresses the original model lookup, so unused model-index bytes are not
misreported as live references. Continuations to any bounded tile record are
allowed; the observed corpus links all 270 continuations to additional records.

The header's nonzero halfword at +2 requests a streamed MML block at the
file-relative offset +16, with byte length +20. MML holds a count and a
relative offset table. Each referenced MOM is bounded by the next distinct
model offset or the streamed block's end. Every one of the 109 MOMs discovered
in LBD files is referenced by these native MML tables; the other two MOM files
are direct inputs. There are zero unresolved LBD files, zero unreferenced
discovered MOMs, and zero references missing from the bounded signature scan.
Repeated references are counted separately and never added again to the
existing model, animation, frame or record totals.

| Native record kind | Records | Source-grounded behavior |
| --- | ---: | --- |
| 0 | 669 | Child flags: mask then set |
| 1 | 22439 | Relative or absolute angles, scale and position |
| 2 | 669 | One-based primitive selection and attachment |
| 3 | 1449 | Parent link or actor-root sentinel |
| 8 | 1449 | Child type declarations read by the model-part walker |
| 15 | 122 | Observed type 0 is absent from child types; original interpreter skips it |

Kind 1 records include 1449 absolute and 20990 relative transforms. Observed
flags are 14, 3, 9, 7, 5, 13 and 11. Their native lengths are respectively 9, 4,
4, 6, 3, 6 and 7 words, including the lead word. All have enough payload for the
interpreter's selected fields. This grounds the recovered code in actual assets
without claiming every possible flag combination was exercised.

## Original execution of structural records

The separate private report
`.decomp-lab/root-work/animation-structural-record-native-proof-second.json`
executes all 1,449 observed kind-8 records and all 122 kind-15 records. It uses
the actual record bytes and first-animation child-type order with synthetic
child nodes and coordinates. No native dependency is stubbed. Six synthetic
frames additionally check the original frame walker with 0, 1, 2, 3, 8 and 16
records. Full actor, model, type/list, child, coordinate, state and script
buffers, return cursor, stack and saved registers are checked.

All observed kind-8 records have a matching child type. The runtime interpreter
clears that child's coordinate flag and advances one word; child allocation
from these declarations occurs elsewhere and is outside this check. All
observed kind-15 records have type 0, flags 0 and one word. Type 0 is absent
from every corresponding child-type list, so the original lookup returns -1
and the record is skipped. This establishes that observed path without
assigning the record an inferred end-marker meaning.

The frame walker runs six times. The record interpreter, object-model
forwarder, field decoder and child-type lookup each run 1,601 times, including
the 30 commands in the synthetic frames. Two mutations are rejected: omitting
the coordinate-flag clear and advancing by the wrong record stride. The report
pins 420 input files and 441 producer/source/build/asset dependencies before
and after execution. These are bounded record checks, separate from the public
NPC fixtures, complete animation playback and whole-feature acceptance.

## Original execution of flags, transforms and attachments

Three further private reports execute the remaining observed record kinds
with original instruction bodies and no stubs:

| Record kinds | Actual asset instances checked | Additional boundary fixtures | Private report in `.decomp-lab/root-work/` |
| --- | ---: | ---: | --- |
| 0 and 1 | 23,108 | 416 | `animation-flags-transforms-native-proof-second.json` |
| 3 | 1,449 | 72 | `animation-parent-native-allocator-proof-second.json` |
| 2 | 669 | 16 | `animation-primitive-native-SDK-proof-second.json` |

The flags/transform check covers mask/set flags and relative or absolute
angles, scales and positions. It retains signed division, halfword wrapping
and low-word multiplication/addition. Seven synthetic frames add 62 commands;
boundary fixtures exercise all 16 transform flags, three initialized state
profiles, signed arithmetic edges and missing children. Wrong flag masking,
forced absolute transforms and omitted coordinate updates are detected.

The parent-link check executes the original parent setter, scene-node
attachment, reciprocal linked-list operations and native allocator/lock
helpers. Synthetic native pools cover an exhausted first allocation, failure
of the second reciprocal allocation, actor-root sentinels, child parents,
missing children and existing parents. Complete node, coordinate, manager and
heap buffers are compared. Omitting the coordinate parent or reciprocal
parent-list call is detected. Resource-cache attachment for other receiver
types, freeing/coalescing and natural allocation pressure remain outside it.

The primitive check relocates actual accompanying TMD data in private RAM
with `GsMapModelingData`, then executes the primitive-array query,
`func_8001E770` attachment and original SDK `GsLinkObject4`. An independent
reference follows the original packet-stride jump table and grouping rules;
9,323 selected primitive packets are checked. Boundaries cover zero selection,
existing attachments, missing children and repeat mapping. Wrong mapping,
owner-field and packet run-count instructions are detected. The checked
`GsLinkObject4` span is its full 344-byte assembly body, including jump-table
targets outside Ghidra's shorter discovered function span.

Together with the structural check, these reports cover all 26,797 record
instances in this extraction, including repeated model content. They use the
actual record bytes and child-type order with synthetic initialized objects.
Each report checks full fixture buffers, script preservation, cursor, stack
and saved registers and pins dependencies before and after execution. These
counts are neither features nor independent NPC fixtures. Complete natural
animation playback, object construction/lifetimes, render/GTE behavior, natural
encounters and PS1 hardware timing remain separate requirements; F029 has
zero whole-feature runtime acceptance.

The separate attachment audit
`.decomp-lab/root-work/animation-record-proof-closure-second.json` reparses the
actual assets and matches all 26,797 instances to exactly one of those four
reports by file, model, animation, frame, record offset and bytes. It rechecks
453 unique producer dependencies, 21 original native function spans, ten
concrete callback words and the ten control instructions. This is an evidence
closure check; it does not rerun the native executions.

These second reports reran the unchanged fixture/reference logic after the
actor cursor-callback declaration was corrected. The first reports and their
source snapshots remain preserved. The corrected `0x134` actor slot returns
the advanced script pointer and receives a script pointer; both typed callers
now agree. A full candidate translation-unit comparison and the subsequent
canonical build retained every executable byte. The private comparison is
`.decomp-lab/root-work/actor-animation-cursor-abi-full-check-first/comparison.json`.

## Original animation selection and tick sequences

`.decomp-lab/root-work/native-animation-sequence-proof-first.json` executes
all 122 extracted animation instances, containing 4,260 asset frames, with
persistent synthetic actor, child, coordinate, model and heap state. Original
`func_80066214` selects an animation and immediately interprets its first
frame. Original `func_80065FD8` advances enabled animations with at least two
frames, wraps their cursors, increments the actor counter and invalidates the
actor coordinate cache. Enable and pause use the original setters.

The check runs 9,022 frame interpretations and 65,917 record interpretations.
Its native phases include 366 initially disabled ticks, 8,764 playing ticks,
209 loop wraps, 366 paused ticks, 122 resumed ticks and 122 counter-wrap
boundaries. The first frame is interpreted on selection and again on the
first playing tick; this native ordering is preserved. Single-frame animations
retain their initial frame without advancing during ticks.

All 25 inventoried native routines are entered. Native allocation, reciprocal
parent attachment, TMD mapping and SDK primitive linking execute without
stubs. Each call compares complete fixture, model/script, mapped TMD, manager
and heap buffers, cursor/index/counter, stack and saved registers. Changed
frame increments and a pause setter writing the wrong field are detected.

The objects and resource descriptors are initialized fixtures; actor action
callbacks are disabled. Natural construction/lifetimes, allocation/free
histories, every animation-switch history, actor callbacks, render/GTE output
and PS1 timing remain outside the check. These results do not accept the
whole F029 feature or increase the public NPC-fixture or gameplay-feature
counts. The earlier per-record checks and their failure-boundary fixtures
remain separate evidence.

## Native source anchors

- `src/file/object_model.c:func_80044858` locates TMD data with the MOM offset
  at +8 and starts MOS animation data at +12.
- `src/file/model_part_list.c:func_800452FC` reads the MOS animation count and
  relative offset table. `func_800453DC` selects the first animation's initial
  frame for child enumeration.
- `src/file/model_part.c:func_8004416C` extracts type, kind, flags and word
  count from the record lead word. The byte-exact C `func_80043FE4` enumerates
  kind 8 declarations and resolves selected kind 2 records. Its wrapping byte
  count is promoted to unsigned 16-bit for the output rewind and signed 16-bit
  for the search bound; both represent 0–255 and reproduce the native branch
  and 88-byte frame without added storage.
- `src/scene/actor.c:func_80066214` reads the animation's 32-bit frame count;
  `func_800662BC` reads each frame's 16-bit record count. The byte-exact C
  `func_80066340` interprets kinds 0–3 and advances by the lead word's word count.
- `src/scene/render_context.c:func_8004BE54` adds the header's +4 grid offset
  to its +8 relative TMD offset, constructs the TMD model, and stores it in
  the file object's +44 attachment field. The original native range is
  `0x8004BE54`–`0x8004C0AC`.
- `src/file/file_object.c:class_1C92C_unk29` follows tile continuations and
  calls the attached model's +128 callback. The original word at `0x8006F1BC`
  binds that callback to `src/file/tmd_model.c:func_80043B58`, a zero-based
  primitive-array lookup. These bounds do not decode the primitive contents.
- `src/file/cd_stream.c:func_80048BC0` requests the MML stream from the
  LBD header. `src/scene/map_scene_post.c:func_80054120` passes its buffer to
  `src/scene/link.c:link_spawn_object_group`.
- `src/file/object_model_list.c:func_80044B88` resolves MML-relative MOM
  offsets and creates the model list; `func_80044C90` bounds the model index
  selected by the spawn consumer.

For example, `/CDI/STG00/M000.LBD` contains a MOM at offset 43020. Its animation
0, frame 9, record 1 is a kind 1 / flags 7 transform at container offset 44084
with type 6 and six words: relative angles and scale. The report stores such
sample coordinates for each observed kind/flag pair.

The static inventory establishes bounded grids, continuation chains, streamed MML-to-MOM
references, and animation payloads in this extraction. It does not decode TMD
primitive contents or collision structures, prove the complete runtime resource
graph, or establish animation playback or visual parity. The separate native
checks above establish the observed kind-15 skip path and selected primitive
mapping behavior. No whole runtime feature group is accepted from these audits.
