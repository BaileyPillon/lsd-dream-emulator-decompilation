# Original virtual tables

`tools/inventory_vtables.py` audits the configured game sources and headers
against the original `SLPS_015.56` words. It requires a current matching build,
checks explicit C initializers, and preserves a new report with source and
executable hashes. It does not invoke a model or change game behavior.

```bash
python tools/inventory_vtables.py --output .decomp-lab/native-tables-new.json
```

## Verified declaration inventory

The corrected inventory contains 57 declared tables. Twenty-nine have explicit
C initializers that reproduce every declared word in the original executable;
28 retain their original assembly data. There are 2,463 declared callback
slots, of which 2,205 are non-null, referring to 838 distinct addresses. Every
non-null address has a linker symbol. Repeated inherited methods account for
many repeated slots.

These numbers describe static dispatch bindings. They are separate from the
107 distinct entity behavior callbacks, the 130 entity records, and the
40 provisional game feature groups in [FEATURE_INVENTORY.md](FEATURE_INVENTORY.md).
They do not establish exhaustive call-site coverage, correct inferred C
signatures, or independent runtime acceptance.

The partial `game_flow_screen_vtable_t` interface has a byte-array gap between
its declared Destroy and Run callbacks. It has no bound concrete table symbol
and is explicitly listed as an unsupported type view; it is excluded from the
57 audited table bindings. Its Run/Destroy interface still needs concrete
receiver mapping as part of call-site review.

## Original animation decoder chain

A private execution check resolves the animation record path through its real
receivers. The actor's +0x134 callback is `func_800662BC`; it iterates the frame
count and calls the +0x138 callback, `func_80066340`. That interpreter calls
the object model's +0x84 word at `0x8006F408`, which is `func_800449B8`.
The wrapper reads the model-part list at object-model offset +0x30 and calls
its +0x80 word at `0x8006F610`, which is the field decoder `func_8004416C`.
The interpreter then resolves the child type with `func_80065D64`.

All five original functions are entered in the structural-record fixtures,
with no stubs. Evidence and scope are recorded in
[the animation audit](NATIVE_ANIMATIONS.md) and
`.decomp-lab/root-work/animation-structural-record-native-proof-second.json`.
This establishes the named chain; other indirect receiver paths remain open.

The parent command binds transform table offset `0x4C` at `0x80087920` to
`func_8001D0EC`. With no existing parent, that setter stores the parent and
coordinate parent, then invokes the parent's attachment slot. An actor parent
uses `func_800570B4`, which forwards through `func_8001E57C` and
`func_8001CC48` to the base-class attachment. The native reciprocal list and
allocator helpers are entered in the 1,449 asset-record and 72 allocation
boundary fixtures; these are synthetic object graphs, not closure of all
receiver types. Evidence:
`.decomp-lab/root-work/animation-parent-native-allocator-proof-second.json`.

The primitive command follows object-model offset `0x2C` to its TMD model.
That receiver's `0x80` slot at `0x8006F1BC` selects `func_80043B58`, whose
returned primitive owner reaches `func_8001E770` and SDK `GsLinkObject4`.
All 669 observed primitive records enter this chain with actual associated
TMD bytes relocated by original `GsMapModelingData`. The full 344-byte
`GsLinkObject4` body is hashed, including its disconnected jump-table blocks;
Ghidra's 268-byte discovery alone is incomplete. Evidence:
`.decomp-lab/root-work/animation-primitive-native-SDK-proof-second.json`.

The actor frame-walker slot at `0x134` receives the actor, a script pointer and
a 32-bit option, and returns the advanced script pointer in V0. Its old actor
declaration returned `void`. The actor table declaration, initializer cast
and both typed callers now preserve that return value and pointer argument.
The separate entity table retains its legacy integer cursor view. The private
full translation-unit check and canonical rebuild both produced the complete
original executable byte for byte. Original slot `0x8008A7F8` and the native
frame fixtures ground this correction. Current declaration/binding evidence
is `.decomp-lab/native-vtable-inventory-twenty-third.json`.
Its source snapshots, full-image comparisons and original slot/range hashes
are attached in `.decomp-lab/root-work/actor-animation-cursor-ABI-evidence-first.json`.

## Corrected table boundaries

Fourteen headers declared one four-byte callback beyond the table's original
assembly data span. The extra declaration read the following table's type ID,
a data word, or an adjacent null word as a callback. Removing these trailing
members preserved every previous member offset. The complete build still
produces the canonical 505,856-byte executable with SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d`.

| Header | Original table bytes | Removed trailing member |
| --- | ---: | --- |
| `src/graphics/effect_base.h` | 208 | `Unk51` |
| `src/graphics/renderer.h` | 184 | `Unk45` |
| `src/scene/stage_texture.h` | 132 | `Unk32` |
| `src/file/tmd_model.h` | 136 | `Unk33` |
| `src/file/model_part.h` | 132 | `Unk32` |
| `src/file/object_model.h` | 136 | `Unk33` |
| `src/file/object_model_list.h` | 140 | `Unk34` |
| `src/file/cd_stream.h` | 140 | `Unk34` |
| `src/menu/card/comment_input.h` | 172 | `Unk42` |
| `src/menu/card/select_menu.h` | 160 | `Unk39` |
| `src/menu/mdec_movie.h` | 112 | `Unk27` |
| `src/dream/generation_structure.h` | 240 | `Unk59` |
| `src/dream/generation_sprite.h` | 200 | `Unk49` |
| `src/menu/graph_screen.h` | 296 | `Unk73` |

The pre-correction evidence is retained in
`.decomp-lab/native-vtable-inventory-bounded.json`; the corrected build audit
is in `.decomp-lab/native-vtable-inventory-corrected.json`. Their assembly
records are checked against original bytes rather than trusted as pseudocode.

Assembly labels are reconstructed boundaries, and can also enclose adjacent
data. `g_STR_STREAM_VTABLE` correctly declares 128 bytes; its 144-byte assembly
label includes the following four words `0x1F801800` through `0x1F801803`.
Those words are recorded separately, and no additional callback members were
invented. A regression test covers this distinction.

## Remaining review

The LBD model query has a concrete receiver chain in the original executable.
`func_8004BE54` constructs the file object, creates a TMD object from its bound
header, and stores that result at file-object offset `0x2C`. The file object's
query callback at slot `0x80` selects a tile's model through that TMD object's
slot `0x80`. Original word `0x8006F1BC` is `0x80043B58`, the TMD-selection
routine. Its returned primitive descriptor reaches `GsLinkObject4` in the
render-context construction path. This association is grounded in the
original instruction ranges and table word, rather than an assumed receiver
type; [the scene/animation audit](NATIVE_ANIMATIONS.md) retains byte hashes.
It establishes this static chain and leaves the overall closure gate open.

The stage-path selector has a second concrete registration chain.
`func_80052DE8` takes the renderer from its input object at offset `0x0C`
and calls renderer table slot `0xC8`, passing `func_80052E7C` and the
`map_scene` receiver. Original table word `0x800867B0` binds that slot to
`func_8004ADC4`. The setter stores the selector at renderer offset `0x60`
and its receiver at `0x64`. The grid routine `func_8004BA40` stores the
computed index in output word 1, then invokes that registered selector
with the index and two zero coordinates; its returned path goes in
output word 0. A rejected boundary-mask direction instead clears output
word 0, and both paths write the direction to word 2.

The concrete selector uses grid coordinates when its index is negative;
otherwise it uses the index directly. `get_stage_model_path_by_grid`
converts the coordinates to `x + columns * y`, and
`get_stage_model_path` selects a stage-path record with a 28-byte stride.
The native function ranges, table word, canonical executable identity and
source hashes for this chain are retained in
`.decomp-lab/native-stage-selector-chain-nineteenth.json`. This evidence
does not close alternative callback writers, every renderer instance, or
runtime coverage. The grid routine now has a C replacement that reproduces
the complete canonical executable; its proof is retained in
`.decomp-lab/root-work/ba40-current-formatted-check/comparison.json`.
Its callback view returns a path pointer with the three native integer
arguments. Legacy integer storage of the callback/receiver pointer fields
remains visible pending the wider interface review.

The original table bindings are audited, but inferred field names and argument
types still require semantic review. Unresolved `Unk` names remain explicit.
Each indirect call needs its receiver type, slot offset, possible concrete
table bindings, and reachable behavior documented before virtual-call closure
can be accepted. An exact executable alone does not establish that explanation.

The UI sprite scaling slot has a reviewed argument shape. Original word
`0x8006F30C`, table offset `0x48`, points to `func_8004441C`. The native
routine takes its receiver, a 32-bit argument and a pointer to four signed
16-bit values; it reads that pointer at offsets 0, 2, 4 and 6. The declaration
in `src/menu/ui_sprite.h` now preserves these three arguments. Its old
single-argument view was incomplete. No existing typed call sites use this
UI slot, and unrelated classes' same-named slots are unchanged. A configured
compiler type check and the complete canonical executable comparison passed.
The frozen ABI evidence is `.decomp-lab/file-work/ui-scale-abi-evidence.json`;
the refreshed table audit is `.decomp-lab/native-vtable-inventory-twenty-third.json`.

The adjacent rotation slot also has a reviewed three-argument shape. Original
word `0x8006F308`, table offset `0x44`, points to the matching C routine
`func_80044380`. It receives its object, a 32-bit selector and a byte-buffer
pointer, reading signed halfwords at buffer offsets 8 and 10. The UI header
now agrees with that existing implementation. Its native slot and argument
evidence are retained in `.decomp-lab/file-work/ui-rotation-abi-evidence.json`.
Both declaration corrections passed a fresh rebuild of all 304 objects and
the complete 505,856-byte canonical comparison.

The renderer dimension helper `func_8004C6A8` retains its incoming width and
height as full 32-bit words. At `0x8004C6C0`, it copies A2 into FP unchanged,
then stores that full word to dimension offset `0x80` or `0x84`. Its forward
declaration now uses `s32` for both dimensions. The existing caller still
widens its signed-short height field. This declaration correction passed the
complete canonical executable comparison; its original assembly body remains.
Evidence: `.decomp-lab/root-work/c6a8-parameter-abi-evidence.json`.
