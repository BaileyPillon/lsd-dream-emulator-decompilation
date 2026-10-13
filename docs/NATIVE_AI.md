# Original NPC behavior and AI-assisted developer tools

Original behavior runs in the matching PS1 executable. Developer analysis and
optional mods have separate commands and outputs. The original game does not
call any added analysis tool; those tools currently make zero external model
API calls.

## Original game data

`tools/inventory_entities.py` reads `g_ENTITY_TABLE` at `0x80089EA4` from the
canonical executable and compares every byte with the current C initializer.
Its 130 records are 16 bytes each: twelve signed property bytes followed by a
32-bit callback pointer. All 2,080 table bytes match. Table SHA-256:
`209e6f5d82ab17604cbf2ad16ef1bec624f89c61bdf9d1a3d24905527c47424a`.

The audited table has 111 nonnull callback slots and 19 null slots, referring
to 107 distinct callback addresses. All 107 callbacks now have matching C
bodies. Multiple entity records can share a function; these counts are neither
an exhaustive game-feature total nor a count of independently tested behaviors.
Function labels come from recovered source.

The report exports each record's mood axes, unlock value, behavior and
interaction fields, link/event values and proximity fields with their original
signed values. It includes property histograms, shared callback bindings,
source locations, source/producer/executable hashes and explicit runtime
validation status. Wrong counts, unsupported layouts, changed signed bytes,
wrong pointers, unresolved definitions and stale build inputs fail the audit.

```bash
python tools/inventory_entities.py --output .decomp-lab/native-entities-new.json
```

Use a new output filename. A current canonical matching build is required;
original files remain untouched. The exercised report is
`.decomp-lab/native-entity-inventory-twentieth.json`.

## What the recovered behavior code shows

The [entity lifecycle](../src/scene/entity.c) uses proximity, interaction
rules, timers, state fields, player input, dream mood and the original RNG.
`entity_start_behaviour` initializes the original sound/effect context with
the table callback and resets its tick counter. `entity_tick` updates that
context and advances the entity tick. The property table and context slots
belong to this original behavior system.

For example, the Gray Man record is index 98, with callback `0x80064618`.
In `entity_gray_man`, a triggered entity attempts to create an effect. Only
when that allocation succeeds does the callback configure the effect,
disable its link and reset the flashback list. Preserving the failed-allocation
branch matters for parity.

The Lion callback at `0x80063144` is shared by indices 81 and 120, whose
properties differ. At tick zero it conditionally chooses a state using the
original RNG. Triggered states alter effect-context slots at twenty-tick
boundaries and take different distance/state paths. Sharing the code does
not make the two property records equivalent.

These are source-grounded explanations. The static byte audit and matching
build do not independently exercise every encounter, allocation failure,
state, RNG, input or timing branch. Callback runtime acceptance remains
separate in [the feature inventory](FEATURE_INVENTORY.md).

The Gray Man now has a separate [bounded native execution check](ROUTINE_VALIDATION.md)
with 768 fixture cases. It executes the original callback, eleven downstream
native routines and the original virtual-table bindings, with explicit stubs
for allocation and the remaining external effects. This verifies preservation
of the failed-allocation path, existing-effect reuse, link/trigger state and
flashback-count reset under those contracts. It does not establish a complete
encounter, effect rendering, or whole-callback runtime acceptance. Evidence:
`.decomp-lab/root-work/gray-man-native-behavior-proof.json`.
An independent entry audit confirmed all twelve inventoried routines were
entered across these cases. Entry coverage is separate from branch coverage:
the detach helper's nonnull-parent path and nonempty child lists remain
untested. The audit is retained at
`.decomp-lab/dream-work/gray-man-entry-review.json`.

The reusable Lion check covers 1,608 cases, including a seed that selects each
of the three initial randomized states. Its original
868-byte callback, actual seeded RNG, link-disable chain and dream callback
clearers run against deterministic reference rules. The check covers RNG
state selection, signed timer remainders, animation commands, distance
boundaries, state changes and movement requests. Entire entity, dream and
command buffers, the final RNG seed, call order, stack restoration and saved
registers are compared. Deliberately wrong distance, timer and movement
controls must be detected. Geometry, trigger-ratio, orientation, scale,
notification, sound and movement calls have explicit contracts; empty child
lists and dream movement mode 1 are fixtures. Natural encounters, real
geometry/motion, other movement modes and PS1 timing remain open.

The reproducible developer tool uses the optional local dependency in
`requirements-analysis.txt`. Run it in the configured WSL build environment:

```bash
python -m pip install -r requirements-analysis.txt
python tools/verify_native_ai.py --output .decomp-lab/native-lion-new.json
python tools/verify_native_ai.py --callback gray_man --output .decomp-lab/native-gray-man-new.json
```

It requires the canonical executable and a current matching build, verifies
native range/symbol hashes, and preserves earlier reports. Negative controls
change private emulator memory only. Its reference rules are ordinary Python;
the tool does not call an AI model or change NPC behavior. This evidence
belongs to a bounded developer check, with whole-callback acceptance still
zero. The earlier private compiler-based experiment is preserved at
`.decomp-lab/root-work/lion-native-behavior-proof.json` with 1,520 cases.
The reusable report distinguishes hashed native ranges from routines actually
entered. In particular, `func_8001D1A4` is inventoried but not executed by the
empty-child fixture.
The exercised public report is
`.decomp-lab/native-lion-verification-fourth.json`. The feature summary binds
that report's SHA-256 and retains both its native inventory and actual entry
coverage. Changed producer/configuration/dependency files, unsupported
callbacks, malformed case counts, invented function entries and altered
mutation controls fail ingestion.

The same command now selects the Gray Man with `--callback gray_man`. Its
public report at `.decomp-lab/native-gray-man-verification-second.json` passed
the same 768 fixture cases and detected private-memory mutations of the
movement request and flashback-reset call. It checks canonical range/symbol
hashes, a current matching build and producer/native-source dependencies
before and after execution. All twelve inventoried native routines were
actually entered; measured counts are retained separately from branch coverage.
The original private proof and independent entry review remain preserved.

These two public checks cover 2,376 fixture cases across two of the 107
callback functions. They add evidence to the existing developer capability;
they do not add game behavior or increase whole-callback acceptance. Repeat
`--native-ai-validation` when refreshing the feature report to retain both
callbacks. Duplicate callbacks, incorrect Gray Man entry counts, a changed
effect source, omitted allocation-failure cases and unsupported controls fail
the evidence check.

The [scripted callback verifier](SCRIPTED_AI.md) adds Bird, Rocket, Horse, UFO,
Dog, Can, Car in water, Walking fetus and Jumping fetus. Their 4,408 native
cases and nine detected instruction controls extend bounded coverage to eleven
of the 107 callbacks and 6,784 cases. Original action reads, RNG and behavior
stop helpers execute; movement, animation selection and sound retain explicit
contracts. The previously published inventory snapshot is preserved, with
these new counts recorded in its publication supplement. Whole-callback and
whole-feature acceptance remain zero.

A separate private extension passed 1,728 Gray Man object-graph fixtures.
It exercises the original nonnull-parent detach, both linked-list removals,
coordinate-parent reset and visibility-bit changes for zero, one or two
transform children. Two changed native instructions were detected: incorrect
child visibility and an omitted coordinate-parent reset. Whole buffers, call
order and saved registers were compared; source/build inputs were pinned.
Evidence: `.decomp-lab/root-work/gray-man-object-graph-proof-v2.json`.

These use a synthetic canonical base-class parent and transform children.
Memory freeing records the native request without running the allocator;
effect attachment/rendering and movement retain the public check's contracts.
This extends bounded coverage beyond the public empty-graph fixtures. It does
not verify realistic ownership graphs, allocator reuse or natural encounters,
and it does not increase the two public callback counts or runtime acceptance.

## Developer additions

The [SDK/API correction](SDK_SIGNATURE_AUDIT.md) subsequently rechecked the same
11 callbacks and 6,784 cases against current source/build inputs. Its separate
SDK getter check adds no NPC callback or original gameplay feature. Current
report hashes are appended to the SDK/API feature-inventory supplement.

The Lion, Gray Man and scripted checks were rerun after the
[save-title source split](SAVE_LABEL.md), retaining 11 of 107 bounded callbacks,
6,784 cases and 14 detected negative controls. The save-title supplement in
[features.json](features.json) records these current-build report hashes and
producer dependencies while preserving the historical reports.

[Context export and the matching workbench](TOOL_ASSESSMENT.md) prepare
byte-verified assembly, Ghidra evidence, headers and source for an AI assistant
or a human. Isolated candidate compilation checks the entire executable.
[Dispatch](NATIVE_DISPATCH.md), [asset](ASSET_INVENTORY.md),
[scene/animation](NATIVE_ANIMATIONS.md) and NPC audits expose native data for
analysis. [Replay comparison](RUNTIME_COMPARISON.md) compares frozen input
identities, frames, GPU/state payloads and recorded PCM audio.

These are separately counted developer capabilities. They do not add an
in-game generative AI character, replace original NPC rules or count toward
original game-feature parity. Optional gameplay mods write separate
executables/discs and require their own runtime checks.

## Original proximity and movement extension

The [proximity profile](NPC_PROXIMITY.md) adds Bear, Rabbit, Acrobats and Ship
through their actual distance, trigger-ratio, RNG, movement, event and GTE
dependencies. It checks 10,408 distinct inputs through 25 original routines,
with no dependency output stubs, and detects seven executed instruction faults.
The retained audit verifies all 7,266 ordered GTE exchanges. Bounded original
callback coverage increases from 16 to 20 of 107; prior counts remain historical.

These constructed graphs have no collider or actor children. Natural encounters,
active geometry, lifetime, animation/render/audio and hardware timing remain
unverified. Whole-callback acceptance stays zero. These are checks of original
NPC rules; the separately counted AI-assisted developer tools and optional mods
are unchanged, with zero model API calls in this profile.
