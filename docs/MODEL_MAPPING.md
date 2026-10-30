# Original model-data mapping

The later [full-corpus SDK audit](MODEL_SDK_MAPPING.md) separately executes the
original mapper and linker across all 531 TMD tables. This factory/ownership
profile retains its original allocation, animation and lifetime boundaries.

The optional `--model-data` mode of the
[factory checker](../tools/verify_actor_factory.py) compares every byte of the
guarded, writable MOM copy against an
[independent mapping model](../tools/model_mapping_model.py). It extends the
[ownership profile](ACTOR_FACTORY_OWNERSHIP.md); the original default remains
available without this option.

The oracle starts with original MOM bytes, the supplied copy address and
animation allocation addresses predicted by the independent ownership plan.
Native fields, observed allocations and execution traces are not oracle inputs.
It predicts the TMD mapped flag, the vertex/normal/primitive pointers relative
to the object-table base, and the MOS animation-offset table's replacement with
allocated part pointers. All remaining input bytes retain their original values.
Actor initialization also links the first frame's selected geometry. The oracle
independently walks its primitive packets and predicts the SDK's mode-run counts
in packet headers. Destruction replaces animation-object pointers with the
original destructor return values, zero for this successful profile.

## Checked histories

Each complete campaign checks all 111 model instances, including 100 distinct
payloads, with two initial memory patterns and the three existing ownership
histories. The checker compares the complete model copy and both guards after
construction, original mapping reentry and destruction. The borrowed model
persists through two actor lifetimes; model-first destruction executes the
original notification path. Packet batching survives destruction, while the
MOS animation-object slots are cleared through the original destructor calls.

| Measure | Per extraction |
| --- | ---: |
| Pattern/ownership histories | 666 |
| Actor lifetimes | 888 |
| Complete guarded raw-copy comparisons | 3,108 |
| Explicit original mapping reentries | 666 |
| Retained ownership / new model-data faults detected | 3 / 5 |

The independent plan fixes all expected pointers before native execution.
Original `tmd_map` runs again on its constructed TMD object to verify that
mapping an already mapped model preserves the complete copy. The profile still
checks ordered heap events, releases, return values, the complete manager,
owned-allocation cleanup, stack guards and saved registers. The closed graph's
134 sized original functions are qualified against a complete matching symbol
diagnostic. No function-output stub supplies a mapping or factory result.

[Campaign metadata](model-mapping-checks.json) records measurements, private
report hashes, backend identity, source dependencies and edition boundaries.
English-v1 and Japanese-labelled extractions are separate provenance records;
identical model contents and repeated histories are not additional game content.

## Fault controls

The three existing ownership controls remain. Five additional controls change
one executed instruction each: set an extra mapped-flag bit, omit the
base addition for vertex or normal pointers, clear the final primitive-run
count, or omit animation-slot clearing during destruction. Each altered history
must finish construction and destruction, retain the expected heap events and
fail its complete raw-model comparison. A crash, timeout, unexecuted change or
unrelated guard failure does not qualify a control. Changes exist only in a
fresh analysis VM.

## Reproduce

Use your own dumpsxiso extraction, a current matching build and the isolated
heap backend described in the
[construction guide](ACTOR_CHILD_CONSTRUCTION.md#reproduce):

```bash
.decomp-lab/actor-children-venv/bin/python tools/verify_actor_factory.py \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/model-mapping-new \
  --edition-label your-extraction-label \
  --model-data
```

Run from the repository root in Linux/WSL. The checker refuses existing output
directories, inventories the supplied extraction anew, verifies complete build
freshness and retains all private comparisons. Edition labels are supplied
provenance, not edition detection. The oracle accepts bounded fresh relative
TMD inputs and valid MOS offsets; native reentry checks the mapped state.
Original discs, assets, executable and BIOS files are not distributed or edited.

Synthetic oracle and ownership tests require neither game data nor Unicorn:

```bash
python -m unittest discover -s tests -v
```

## Remaining gates

Full raw-copy equality does not decode or validate the meaning of every vertex,
primitive or animation command. The optional
[model-object profile](MODEL_OBJECTS.md) now checks complete model allocations
at initial factory return. The optional [actor-object profile](ACTOR_OBJECTS.md)
checks all live pool payloads after original actor construction and first-frame
interpretation. Subsequent model/actor mutations, later animation playback,
allocation failures, resource-cache loading, cold CD
initialization, natural NPC encounters, rendering, sound and PS1 timing remain
open. The supplied pool, ready CD state and SDK identity matrix remain fixtures.
These comparisons are developer analysis and invoke no model API.

This adds no matching C byte, bounded NPC callback profile or whole-feature
acceptance. Matching C remains 195,844 / 199,912 bytes (97.97%), with five
assembly fallbacks and two unresolved inherited storage explanations. All 40
provisional feature groups and complete gameplay parity still require their
remaining acceptance evidence. The separate Bevy/Rust port is unchanged.
