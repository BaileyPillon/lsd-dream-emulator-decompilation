# Original model and actor factory ownership

The [factory checker](../tools/verify_actor_factory.py) executes original MOM,
TMD and MOS preparation, actor construction, animation-zero interpretation and
actor/model destruction. An [independent ownership plan](../tools/actor_factory_model.py)
predicts every ordered allocation request, release pointer and return word
before native execution begins. Native heap requests are also checked by the
independent interval allocator; those observed requests are not the factory
plan's inputs.

This extends the [child lifetime profile](ACTOR_CHILD_LIFETIMES.md) beyond its
supplied model/list descriptors. The original code now creates those objects,
maps the geometry, transforms the animation-part table, creates actor children
and interprets the model's first animation frame. The supplied pool, SDK identity
matrix and ready CD-driver state remain explicit fixture inputs.

## Corpus and ownership histories

A complete run checks all **111 model instances**, containing **100 distinct
payloads**, in a validated extraction. Two initial memory patterns and three
ownership histories produce **666 cases** and **888 actor lifetimes**:

1. **Actor first:** create an external model, construct and destroy two borrowed
   actors consecutively, then destroy the surviving model. The model and pool
   persist between actor lifetimes.
2. **Owned model:** let the actor factory create its own model, then destroy the
   actor. Its model resources must be released through the original ownership path.
3. **Model first:** construct a borrowed actor, then destroy only its model.
   Original parent notification must destroy the actor automatically.

The closed graph contains [134 sized original functions](actor-factory-function-ranges.json).
Every range must agree with both the canonical executable and an unstripped
diagnostic ELF. Retaining those symbols must preserve the entire executable
before any sized range is trusted. All published ranges must execute during a
complete positive campaign. Native helpers run without function-output stubs.

Measured runs, source hashes and edition boundaries are retained in
[actor-factory-ownership-checks.json](actor-factory-ownership-checks.json).
Repeated patterns, lifetimes and separately labelled extractions do not add
model contents, original game features or independently accepted encounters.

## What the independent plan checks

The model derives resource counts from the original MOM/TMD/MOS headers and
parent links from animation-zero commands. It independently allocates model,
geometry, animation, actor, coordinate, state, child-table and linked-list
ownership intervals. It models notification and teardown without consulting
native object fields or recorded heap traces. All expected events are computed
before the emulator starts.

Each native call checks its instruction budget, return path, saved registers,
stack pointer, `gp`, return address and stack red zones. Runtime memory accesses
are limited to the canonical image, supplied records, writable model copy,
guarded pool/manager, SDK matrix and enumerated driver globals/vtable slots.
The fifteen original file-driver vtables receive their eleven driver methods
through the original initializer.

The final complete manager buffer must match the independent model. Pool and
raw-MOM boundary guards, supplied argument records and the SDK matrix remain
checked. Ordered heap requests, releases and return values must match exactly,
and all owned intervals must be released. CPU and RAM persist through each
case's native construction/destruction graph. The host resets the caller stack
between separate calls; each case starts a fresh CPU.

## Executed fault controls

Three controls complete their native histories and must produce a wrong event
against the independent plan:

- Change a primitive allocation from 36 to 32 bytes.
- Replace a child-state release argument with NULL.
- Exchange the type-table and pointer-table release order while still freeing
  both allocations successfully.

All changed instructions must execute. A crash, timeout or rejected input alone
does not qualify a control. The release-order control changes two instructions;
both must execute and the resulting event sequence must disagree.

## Reproduce

Use your own dumpsxiso extraction and a complete matching build. Install the
isolated heap backend described in the
[construction guide](ACTOR_CHILD_CONSTRUCTION.md#reproduce); this profile uses
the same pinned Unicorn 2.1.2 backend and Ninja requirements.

```bash
.decomp-lab/actor-children-venv/bin/python tools/verify_actor_factory.py \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/actor-factory-ownership-new \
  --edition-label your-extraction-label
```

Run from the repository root in Linux/WSL. The command inventories the supplied
extraction anew, verifies complete build freshness, creates a private symbol
diagnostic and refuses existing or external output directories. Reports retain
the actual backend, producer dependencies, asset/layout hashes and executed
function counts. Edition labels are supplied provenance, not edition detection.
Game assets, executable bytes, buffers and diagnostic ELF files remain private.

Synthetic model and comparison tests need neither game data nor Unicorn:

```bash
python -m unittest discover -s tests -p 'test_actor_factory_ownership.py' -v
```

## Remaining boundaries

The default independent model covers ownership events. The optional
[`--model-data` profile](MODEL_MAPPING.md) now compares the complete guarded raw
model copy and original mapping reentry using separately predicted pointers.
Complete allocated object payloads and geometry interpretation remain open.
Successful factories
do not cover allocation failures, resource-cache loading, cold physical CD
initialization, later animation playback, natural NPC encounters, rendering,
audio or PS1 timing. `g_CdInitialized=1` is a ready-state fixture; the checker
does not claim to initialize CD hardware.

This adds **zero matching C bytes**, **zero NPC callback profiles** and
**zero whole-feature acceptances**. Original game behavior and separate
AI-assisted analysis/modding remain distinct; the checker calls no model API.
The separate [accessor storage recovery](ACCESSOR_STORAGE_RECOVERY.md) explains
three existing C frames while preserving the original executable.
