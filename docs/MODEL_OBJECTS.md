# Original model construction payloads

The optional `--model-objects` profile in the
[factory checker](../tools/verify_actor_factory.py) compares complete allocated
model payloads when the original MOM factory returns. An
[independent construction model](../tools/model_payload_model.py) predicts the
objects from original MOM bytes, qualified vtable identities and its own pool.
Native object fields, observed allocation requests and execution traces are
not inputs to that prediction.

This extends the [ownership histories](ACTOR_FACTORY_OWNERSHIP.md) and can run
alongside the [raw-model mapping profile](MODEL_MAPPING.md). It checks a new
point in those histories without adding or substituting native instructions.

## Objects and observation boundary

The oracle reconstructs the MOM object, TMD object, terminated primitive-pointer
table, every primitive object, MOS list object and every animation-part object.
It predicts their vtables, original-data pointers, links between model resources,
constructor flags and initialized state. Complete payload comparisons also cover
the words the constructors leave untouched, preserving the independent
allocator's residue rather than assuming zero-filled storage. Any tail created
by the allocator's minimum capacity is included.

Every expected allocation address and byte is fixed before native execution.
The checker recognizes the actual factory return using both the return address
and stack pointer. This covers an external model factory call and the same
factory nested inside actor construction. The snapshot occurs before the actor
attaches itself or interprets frame zero. It does not assert that these payloads
remain unchanged during later use.

The existing profile continues through first-frame interpretation and complete
destruction, including borrowed-model reuse and model-first notification. All
ordered heap events, guarded raw-model comparisons, original function-entry
counts and executed instruction counts must agree with the preceding
raw-model campaign. The new observer reads native memory without replacing
function outputs or changing CPU state.

[Campaign metadata](model-object-checks.json) records the measured allocation
and byte totals, source/backend hashes and complete symbol qualification for
the two labelled extractions. Repeated patterns and ownership histories do not
add distinct original content. The corpus remains 111 model instances with
100 distinct payloads, 666 histories and 888 actor lifetimes per extraction.

| Measure | Per extraction |
| --- | ---: |
| Ownership histories | 666 |
| Complete allocated-payload comparisons | 6,936 |
| Allocated payload bytes compared | 275,496 |
| New completed payload fault controls | 3 |

## Fault controls

Three additional controls change one executed instruction each: use a different
nonzero model-construction mode word, set an extra file-state flag, or overwrite
a halfword of retained constructor residue. Each must finish its original
ownership history, preserve the planned heap events and pass the raw-model
comparisons while failing a complete allocated-payload comparison.

A crash, timeout or unexecuted patch does not qualify a control. The three
existing ownership and five raw-model fault controls remain separate.

## Reproduce

Use your own dumpsxiso extraction, a current matching build and the isolated
heap backend described in the
[construction guide](ACTOR_CHILD_CONSTRUCTION.md#reproduce):

```bash
.decomp-lab/actor-children-venv/bin/python tools/verify_actor_factory.py \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/model-objects-new \
  --edition-label your-extraction-label \
  --model-data --model-objects
```

Run from the repository root in Linux/WSL. Output must be a fresh directory
inside `.decomp-lab`. `--model-objects` also works by itself; neither optional
profile changes the default ownership mode. Synthetic tests require no game
assets or Unicorn:

```bash
python -m unittest discover -s tests -p 'test_model_payloads.py' -v
```

## Remaining gates

These are successful constructed factory histories with a supplied pool,
ready CD-driver state and SDK identity matrix. Full actor payloads, subsequent
model mutations, later animation playback, allocation failures, cache/CD
loading, natural NPC encounters, rendering, audio and PS1 timing remain open.
The checker makes no model API calls and does not modify game assets.

This adds no matching C bytes, NPC callback profile, accepted whole encounter
or whole feature. Matching C remains 195,844 / 199,912 bytes (97.97%), with five
assembly fallbacks and two unresolved inherited storage explanations. The
separate Bevy/Rust port is unchanged.
