# Original actor construction payloads

The optional `--actor-objects` profile in the
[factory checker](../tools/verify_actor_factory.py) compares every live pool
allocation when the original actor factory returns. The
[independent actor model](../tools/actor_payload_model.py) generates every
expected pointer and byte before native execution, using original MOM bytes,
qualified original symbol/default data and its own allocator state. Native
fields, observed allocation requests and execution traces are never inputs.

This extends the [factory ownership histories](ACTOR_FACTORY_OWNERSHIP.md),
[raw-model mapping](MODEL_MAPPING.md) and
[initial model payload checks](MODEL_OBJECTS.md). It uses the same 134 original
routines without replacing outputs or adding native instructions.

## Observation boundary

The checker observes successful `actor_create` returns using both the return
address and stack pointer. At that point the original constructor has created
the root and children, attached the model, interpreted animation zero's first
frame and bound the root to its selected child's geometry.

| Allocations compared | State included |
| --- | --- |
| Actor root and scene-node children | Vtables, attributes, geometry descriptors, selection, callback and animation fields |
| Each coordinate and transform state | SDK identity matrix, default scales/angles, first-frame motion, dirty flags and coordinate parent |
| Child pointer and type tables | Ordered child identities, selected node and retained minimum-capacity tail |
| Every child/parent list node | Ordered links, reciprocal object lists and untouched allocation tail |
| All live model resources | MOM, TMD, primitive table and objects, MOS list and animation objects after actor attachment |

Complete allocated capacity is compared, including uninitialized fields,
halfword gaps and allocator residue. The predictor retains old payload bytes
through cleanup and reuse; it does not assume zero-filled allocations.

First-frame command order matters. A parent command resets coordinate
translation while retaining transform-state position. A later relative motion
reads that state; a repeated parent command does not reset it again. The model
also preserves signed-halfword angle wrapping, C remainder for negative angles,
32-bit multiplication before fixed-point division, attribute masks and the
first nonzero geometry binding. These are original game behaviors recovered
from the native routines, separate from the host analysis tool added here.

Expected snapshots are immutable before the VM starts. The observer only reads
memory and retains mismatches until the complete native ownership history has
finished. It covers owned models, two actor lifetimes borrowing the same model,
and model-first notification that destroys a borrowed actor.

[Campaign metadata](actor-object-checks.json) records separately labelled
English-v1 and Japanese-labelled extractions. Their MOM content sets are the
same: 111 instances and 100 distinct payloads. Repeated editions, memory
patterns and ownership histories do not add original content or features.

| Measure | Per extraction |
| --- | ---: |
| Original model instances | 111 |
| Complete ownership histories | 666 |
| Successful actor-factory returns | 888 |
| Complete live-allocation comparisons | 66,504 |
| Allocated payload bytes compared | 3,053,664 |
| Additional executed payload fault controls | 4 |

The publication audit compares every case with the prior model-object campaign.
All earlier heap events, raw-model comparisons, initial-model snapshots,
function-entry counts and native instruction counts are retained.

## Fault controls

Four controls change executed instructions to clear a scene-node height,
select a different actor callback, change its enable word, or overwrite an
otherwise untouched geometry-ID word in the SDK binding path. Each must finish
its native ownership history and retain correct heap events, raw-model bytes,
initial-model snapshots and actor return pointers, while failing a complete
actor-return payload comparison.

The controls also run under both residue patterns and all three ownership
histories in a separate 24-case campaign. A crash, timeout or unexecuted patch
does not qualify a control. The three ownership, five raw-model and three
initial-model controls retain their separate scope.

## Reproduce

Use your own dumpsxiso extraction, a current matching build and the isolated
backend from the [construction guide](ACTOR_CHILD_CONSTRUCTION.md#reproduce):

```bash
.decomp-lab/actor-children-venv/bin/python tools/verify_actor_factory.py \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/actor-objects-new \
  --edition-label your-extraction-label \
  --model-data --model-objects --actor-objects
```

Run from the repository root in Linux/WSL. The output must be a fresh directory
inside `.decomp-lab`. `--actor-objects` also works alone. The default ownership
mode and the earlier optional profiles retain their original behavior.

Synthetic tests require neither game data nor Unicorn:

```bash
python -m unittest discover -s tests -p 'test_actor_payloads.py' -v
```

## Remaining gates

These are successful constructed histories with a supplied pool, ready
CD-driver state, SDK identity matrix and zero auxiliary actor-constructor
argument. The new payload boundary is factory
return, not later animation playback, natural NPC encounters or rendered game
frames. Complete freed-pool contents after destruction, allocation failures,
resource-cache loading, cold CD initialization, audio and PS1 timing remain
outside this profile. The original ownership-event and manager/guard checks
continue through destruction.

Matching C remains 195,844 / 199,912 bytes (97.97%), with five assembly functions
and two unresolved inherited storage explanations. The 40 provisional feature
groups, 36 bounded NPC callback profiles and zero accepted whole features or
encounters retain their counts. This tool makes no model API calls; original
NPC behavior and AI-assisted analysis/modding remain separate. The Bevy/Rust
port is a separate repository.
