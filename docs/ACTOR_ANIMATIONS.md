# Original actor animation selection

The [animation checker](../tools/verify_actor_animations.py) follows original
actor construction with explicit selection of every valid animation in the
supplied MOM corpus. It compares the immediate first-frame result against an
[independent state model](../tools/actor_animation_model.py), then completes the
original ownership and destruction history.

This extends the [actor construction payload profile](ACTOR_OBJECTS.md).
Animation selection and first-frame interpretation are original game behavior;
the checker is a separate host analysis tool. It does not change gameplay,
call a model API or contribute additional recovered C bytes.

## Matching source interface

`func_80066214` selects a model animation, stores its frame count and first-frame
pointer, resets the actor's frame counter and immediately dispatches that frame
through the actor vtable. Its animation header is eight bytes: two halfwords
followed by the frame count. The first frame starts immediately afterward.

The C source now expresses that header and the model/list/animation lookup
directly. A compile-time size check adds no runtime storage. The two original
index reads remain separate, including the read after the selected index has
been stored. The function already had a matching C body; this improves its
readability without raising source-recovery coverage.

Both the ordinary build and a fresh, independently configured 306-object build
produce the complete canonical executable byte for byte. The 148-byte function
is also qualified against a full-image-matching symbol diagnostic.

## Comparison boundary

The predictor freezes expected snapshots before native execution. Its inputs
are original MOM bytes, qualified original default/symbol data and its own
allocator and object state. Native observations are not used to construct
expected state.

For each original model, the checker selects all valid animation indices in
forward order and then reverse order. Repeated selections retain earlier
object state. Before each call it supplies a valid prior frame counter and
checks that the original selector resets it. These injected counters are not
evidence of elapsed engine frames.

Each selection checks every live allocation's complete capacity, the complete
mapped MOM copy and the allocation manager. The comparisons include untouched
allocator residue, signed/relative motion, ordered attribute masks, the first
nonzero geometry binding, coordinate-parent links and parent commands' original
low-halfword semantics. Heap events, input guards and release of all owned
allocations are checked through destruction.

Both memory patterns run through three histories: an actor owning its model,
two successive actors borrowing one model, and model-first notification that
destroys a borrowed actor. The supplied pool, ready CD-driver state, original
SDK identity matrix and zero auxiliary constructor argument remain explicit
fixture inputs. Original routines execute without dependency-output stubs.

The validated corpus contains 111 model instances, 100 distinct model contents
and 122 animation instances. Its 4,260 total frames are an inventory measure;
this profile applies only each selected animation's immediate first frame.
Repeated histories and duplicate model contents do not add features.

[Campaign metadata](actor-animation-checks.json) records the original inputs,
producer and backend hashes, complete-build comparisons and a separate audit
of raw MOS indices and retained histories.

| Measure | Japanese-labelled extraction |
| --- | ---: |
| Complete ownership histories | 666 |
| Actor lifetimes | 888 |
| Explicit first-frame selections | 1,952 |
| Complete live-allocation comparisons | 150,592 |
| Allocated payload bytes compared | 6,916,928 |
| Complete mapped MOM bytes compared | 15,737,472 |
| Additional completed wrong-output histories | 24 |

The earlier constructor profile checked animation zero's immediate frame in
all 111 instances. Selecting every valid index extends that data axis to 122
instance/index pairs, or 108 distinct-content/index pairs rather than 100.
Those additional indices are not eleven new features or eleven new NPCs.

## Fault controls

Four controls alter the selector's executed index store, duration store,
counter reset or immediate first-frame dispatch. Each runs under both residue
patterns and all three ownership histories. Construction and destruction
execute the original instructions; faults are armed only around the explicit
selections, with translated code invalidated after each patch and restoration.

Every control must execute its changed instruction, finish the native history,
retain the original construction checks and release all owned allocations,
while failing a complete payload comparison. The first three faults expose
the corresponding actor field; the dispatch fault exposes child transform
state. A crash, timeout, memory-guard rejection or unexecuted patch is not a
qualified wrong-output control. Only private VM memory is altered.

## Apartment Bear resource binding

A separate static audit ties the Apartment Bear callback to its original data:

| Link | Original value |
| --- | --- |
| Entity property entry | 77, `entity_bear_apartment` |
| Stage and object group | Stage 0, group 8 |
| Group's selected model slot | 2 |
| Spawn variant indices | 45 and 109 |
| Teleport table entry | Stage 0, entry 1; cell `(0, 1)`; groups 6, 7 and 8 |
| Stage grid | 1 column, 5 rows, vertical |
| Original resource path | `CDI/STG00/M001.LBD` |
| Streamed MML and selected MOM offsets | 30,720 and 36,960 |
| Selected MOM size | 9,820 bytes |
| Animation frame counts | 10 and 30 |

The group record's entity byte and its spawn variant bytes have different
roles. `link_spawn_object` passes entity 77 to `link_create_object`; the latter
passes that entity index to `entity_create` and separately indexes the variant
table. The path follows the original grid-to-file formula and fixed path-table
records, then the MML's model-offset table. This is a static placement/resource
binding, not proof that the encounter is naturally reached.

## Reproduce

Use Linux/WSL, a current matching build and your own dumpsxiso extraction. Create
an isolated environment rather than replacing another analysis backend:

```bash
python3 -m venv .decomp-lab/actor-animation-venv
.decomp-lab/actor-animation-venv/bin/python -m pip install \
  -r requirements.txt -r requirements-card-heap.txt
.decomp-lab/actor-animation-venv/bin/python -m tools.verify_actor_animations \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/actor-animations-new \
  --edition-label your-extraction-label
```

Run from the repository root. The output must be a fresh directory inside
`.decomp-lab`; existing evidence is preserved. The allocator harness requires
Unicorn 2.1.2. The newer analysis backend is not qualified for this profile.
Reports, diagnostic images and game data remain private.

Synthetic tests need neither original media nor Unicorn:

```bash
python -m unittest discover -s tests -p 'test_actor_animations.py' -v
```

## Remaining gates

Later-frame playback, wrap/stop behavior, natural actor/NPC construction,
resource-cache loading, allocation failures, complete engine scheduling,
rendering, audio and PlayStation timing remain open. No NPC callback is newly
profiled by this selector test, and no whole encounter or feature is accepted.

Matching C remains 197,172 / 199,912 bytes (98.63%), with two assembly functions
and two inherited unused-storage explanations still unresolved. The feature
inventory remains 40 provisional groups with 38 listed-core C groups, 40 bounded
NPC callback profiles and zero accepted whole feature groups or encounters.
The Bevy/Rust port remains a separate repository.
