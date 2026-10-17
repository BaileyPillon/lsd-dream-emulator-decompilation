# Roadmap

The goal is readable C recovery of the original game, followed by reviewed
comparison evidence for its behavior and content. Optional mods and analysis
tools have separate deliverables. See [PROJECT_OBJECTIVE.md](../PROJECT_OBJECTIVE.md)
for the completion requirements and [provenance](PROVENANCE.md) for the evidence
boundary of the published snapshot.

The [software movie decoder audit](MOVIE_DECODE.md) now checks all 39 routed
movie payloads, including every encoded tail frame and XA packet. A separate
raw-byte hashing pass agrees throughout. Extend this content evidence to
native MDEC/GPU and audio output, natural playback of every movie, skip/error
paths and timing. Software decoding changes no source-recovery or runtime
feature-acceptance count.

The [Astronaut profile](ASTRONAUT_BEHAVIOR.md) raises bounded original callback
coverage to 40 / 107 through actual mood, proximity and spatial dependencies.
Extend these constructed poses and scheduled script calls to natural encounters,
model animation, populated collision graphs, engine lifetimes and visible output.
Apartment Bear additionally needs its model-animation switch fixture; it has
not been counted as a newly profiled callback.

The [locomotive profiles](LOCOMOTIVE_SCRIPTS.md) bring bounded original callback
coverage to 39 / 107, following the [Gunman profiles](GUNMAN_SCRIPTS.md).
The earlier [periodic spatial profiles](NPC_PERIODIC_SPATIAL.md)
add Minotaur and Giant Minotaur and replace Bird's ratio contract with its real
helper. The earlier
[NPC state and cycle profiles](STATE_CYCLE_SCRIPTS.md) retain all their inputs.
Recover natural encounters, real downstream effects and lifetime histories;
bounded request comparisons do not complete those gates.

The [populated actor child profile](ACTOR_CHILD_FLAGS.md) now verifies the flag
fan-out through real scene-node and bit-setter code, including repeated changes
and duplicate list entries. Extend natural construction, encounters and visible
effects separately; this profile adds no newly recovered assembly function.

The [actor child construction checker](ACTOR_CHILD_CONSTRUCTION.md) executes
the original allocator and constructors from real model first frames with
independent full-buffer comparisons. Extend full actor creation, resource-cache
ownership, allocation failures and playback beyond its supplied descriptors
and SDK matrix fixture; construction checks do not accept whole encounters.
The optional [child lifetime profile](ACTOR_CHILD_LIFETIMES.md) now checks
destruction, repeated cleanup and guarded reconstruction on the same pool.
The [factory ownership profile](ACTOR_FACTORY_OWNERSHIP.md) now executes actual
model/actor creation and animation-zero parent attachment. Extend its independent
checks to allocation failures, resource-cache loading, later playback and
natural encounters. Its optional
[model-data profile](MODEL_MAPPING.md) now compares the entire guarded MOM copy
through construction, original mapping reentry and destruction. Pointer tables
are predicted independently; geometry interpretation and later playback remain
separate gates. The optional [model-object profile](MODEL_OBJECTS.md) checks
complete model payloads at initial factory return. The optional
[actor-object profile](ACTOR_OBJECTS.md) now checks every live pool payload
after successful actor construction and first-frame interpretation. Extend
later animation state, model/actor mutations and natural lifetimes separately.

The [glyph character interface](GLYPH_CHARACTER_API.md) now has typed receivers
and the original unsigned-byte getter return. Its compiled callers pass 4,656
bounded native inputs without output substitutions. The
[accessor recovery](ACCESSOR_STORAGE_RECOVERY.md) now explains the getter's
inherited storage; extend natural menu/rendering histories separately.

## Matching C recovery

The [collision interface](COLLISION_API.md) now has typed outputs and checked
compiled-caller evidence. Its primitive C candidate still has 22 differing
bytes; recover its storage lifetimes before accepting that assembly function.

The [matching model interfaces](MODEL_ENUMERATION.md) now explicitly forward
the native enumeration arguments. The game also has a verified
[local play launcher](PLAYING.md). These complete no remaining assembly
function or whole-feature gate; continue the source work below.

- Use the [memory-store tracer](COMPILER_MEMORY_STORES.md) to distinguish real
  consumed storage from retained unused regions. The earlier math-pair candidate
  retains two extra stores; the later [accessor recovery](ACCESSOR_STORAGE_RECOVERY.md)
  instead resolves the packed-word and matrix-stream functions through real
  input views. Continue the remaining source gates below.

Two game functions remain in assembly after the
[sprite-scale and bounds recovery](UI_SCALE_BOUNDS_MATCHING_C.md): the
796-byte hull/face query (`func_8001DDF4`) and the 1,944-byte primitive-face query
(`func_8001F8B8`). Matching C covers 197,172 / 199,912 bytes (98.63%). The two
inherited debug-driver storage explanations remain open separately.

The [earlier bounds candidate](BOUNDS_NARROW_COMPARISON.md) retains its
19-byte difference and 4,648-input comparison as historical research. The later
recovery uses a signed cell record and the inclusive in-range predicate; its
complete executable matches. Continue the two collision queries and natural
runtime coverage rather than revisiting the superseded bounds candidate.

The expanded audit identified 28 unused-storage functions and withdrew four
padded promotions. Twenty-four inherited explanations remained at that snapshot;
the correction's historical count was 194,212 / 199,912 (97.15%). The two
generation and two menu recoveries raised it to 195,844 / 199,912 (97.97%).
The grid-window recovery raised it to 196,504 / 199,912 (98.30%); sprite scaling
and the bounds predicate subsequently raise it to 197,172 / 199,912 (98.63%).
The [callback storage recovery](CALLBACK_STORAGE_RECOVERY.md) now explains five
inherited functions. The subsequent
[constructor and actor storage recovery](CONSTRUCTOR_ACTOR_STORAGE.md) explains
two more. The [accessor recovery](ACCESSOR_STORAGE_RECOVERY.md) explains another
three. The [input storage recovery](INPUT_STORAGE_RECOVERY.md) explains six
more. The [text and render callback recovery](TEXT_CALLBACK_STORAGE.md) explains
another two. The [atlas and tile-buffer recovery](ATLAS_TILE_STORAGE.md) explains
four more. Recover the real storage and helper lifetimes for the remaining two
identified functions.

Those two are empty debug-driver stubs with unexplained 64-byte reservations.
Keep them explicit while recovering the two remaining game assembly functions;
unused fields or discarded identity chains do not explain those stubs.

All four withdrawn functions have replacement matching C; the earlier
[source-layout candidates](../research/source_layout/README.md) remain
historical research. Full source quality and runtime acceptance are separate.

For the recovered generation update, [native structure checks](GENERATION_STRUCTURES.md)
cover actual dispatch, position replacement and mode 3 sprite RNG/scaling
without output contracts. The initialized typed vtable snapshot resolves the
scalar candidate's missing frame allocation. Extend natural object histories
and construction; the older argument-pair hypotheses remain rejected research.
The later [mode 0 extension](GENERATION_EFFECTS.md) now checks all eight rate
variants and four active child layouts, including ordered periodic resets and
consecutive graph updates. Recover actual construction/parameter selection and
natural lifecycle histories next; fifteen-routine bounded composition alone
does not establish those gates. Six direct aggregate forms retain the same
rejected output, so they do not explain the scalar frame lifetime.

For F025, [entry scanner composition](GENERATION_ENTRIES.md) now checks all
56 original records through the actual world transform. Its ten-byte packet
is retained in the matching C recovery. An initialized vtable snapshot and
scalar method return resolve the frame and call-register differences. Continue
through natural parameter selection, sound/entity spawning and lifetimes;
complete F025 runtime acceptance remains open.

For F008, [overlap source recovery](OVERLAP_RECOVERY.md) removes an unexplained
private buffer tail and checks the twelve-byte midpoint candidate in 6,912 paired
native graphs. Twenty-seven source forms and actual compiler traces retain no
exact match. Recover the remaining frame/register lifetime without artificial
storage; natural geometry, histories and hardware timing also remain open.
The later [result-lifetime study](OVERLAP_RESULT_LIFETIMES.md) reproduces the
original 176-byte frame and reduces the complete-image difference to 148 bytes.
Its additional storage comes from late reloads, leaving the earlier original
region unexplained. The same bounded native graph domain passes; exact source
and whole-feature acceptance remain open.
The latest [control-flow study](OVERLAP_CONTROL_FLOW.md) reduces the difference
to 26 stack-displacement bytes with the original opcode/register sequence and
176-byte frame. All 6,912 existing pairs pass. Recover the earlier 24-byte
region before the address-taken scalars; extra late reloads, mutable argument
materialization and unused padding do not establish the original layout.

The initial seven also remained after the [save-title recovery](SAVE_LABEL.md). That
additional game-support helper was discovered in a segment classified as SDK;
it had not been included in this list. Continue auditing raw SDK-labelled
segments for mixed game support as well as checking the known inclusions.
The [SDK signature audit](SDK_SIGNATURE_AUDIT.md) records candidate provenance
and a sound-API correction; unmatched functions still need further analysis.
The [bounds-predicate audit](RENDER_BOUNDS.md) verifies the original
`func_8004CD38` contract on bounded fixtures. The
[current source-lifetime report](BOUNDS_SOURCE_LIFETIMES.md) and
[recipe](../research/render_bounds/README.md) retain earlier source candidates.
The later [narrow comparison](BOUNDS_NARROW_COMPARISON.md) reproduces the current
19-byte candidate; exact C recovery remains open.
The earlier [allocation diagnostic](COMPILER_ALLOCATION.md) checked 68 source
forms against a 38-byte-different candidate. The later report supersedes that
starting point and observes the new allocation in the complete source unit.
The [save workflow audit](CARD_SAVE.md) verifies the wrapper, writer and native
helpers in 13,152 bounded cases. Its full C candidate agrees on those fixtures
and retained an eight-byte mismatch at that checkpoint. The later
[matching writer recovery](CARD_WRITER_RECOVERY.md) resolves the argument
layout and promotes its 960-byte function to C. Standard and clean builds
remain exact; physical cards and natural error/cancel scenarios remain open.
The [persisted-card profile](CARD_ROUNDTRIP.md) now compares an ordinary day-two
save and cold-boot load from the actual card file, including all 1,792 native
payload bytes. Continue with missing/full/corrupt cards, cancel/overwrite paths,
other slots and saved contents; this one history accepts no complete card feature.
The [empty-card Load investigation](EMPTY_CARD_LOAD.md) observes the not-found
dialog and preserves its eight-byte core-state mismatch. The
[native accessor extension](NYMASHOCK_STATE.md#empty-card-extension-and-native-accessors)
identifies the same emulator media-label capacity described in the earlier
cold-boot diagnosis and checks the bundled accessors. Full-state acceptance,
other consumers and the other card paths remain open; the diagnostic does not
change the strict comparator.
The [grid-window audit](RENDER_GRID.md) verifies all 65,536 angle words within
74,832 scalar fixtures. Its full C candidate agrees on those fixtures but
reorders two stores, differing in four bytes. Real GTE transforms and the
downstream builder remain external contracts.
The later [streaming composition audit](RENDER_STREAM.md) executes that builder,
its row splitter and slot selector in 45,408 cases. This reduces the remaining
contracts to position lookup and the two GTE helpers; the same full C candidate
still differs in four bytes. The later [world-position composition](RENDER_POSITION.md)
executes the lookup chain and reduces that composition to two GTE contracts.
Scene ownership, framebuffer and timing acceptance remain open.
The later [rotation composition](RENDER_ROTATION.md) executes the original
SDK `RotMatrix` and packed table. Only `ApplyMatrixLV` remains contracted;
actual hardware operations and natural scene ownership still need evidence.
The subsequent [native GTE composition](RENDER_GTE.md) executes that helper
with checked Nymashock MVMVA commands. Eleven original functions pass 13,230
distinct composed cases with zero function-output stubs. Its reviewed COP2
transfer adapter verifies the bounded arithmetic; full PS1 CPU timing,
original hardware and natural scene acceptance remain open.
The [collision composition](COLLISION.md) executes the remaining primitive and
transform routines through actual bounds, decoder and native GTE dependencies.
It adds bounded evidence for contact-height filtering and expanded-box behavior;
both routines still require exact C recovery and natural collision scenarios.
The later [collision C candidate](../research/collision/README.md) reduces the
primitive's whole-executable mismatch from 103 to 22 stack-displacement bytes.
Its SDK arithmetic and distance storage match; recover the original late
bounds-storage lifetime without padding. The paired checker covers 1,566
additional caller overlaps, while 5,400 non-NULL clipping fixtures now execute
the midpoint helper. These remain bounded checks and an unaccepted candidate.
The [compiler-layout diagnostic](COMPILER_LAYOUT.md) now traces actual allocator
calls with unchanged assembly output. Fifty-five further source compilations
find no exact match; the primitive's 22-byte storage mismatch remains open.
The later [compiler-lifetime diagnostic](COMPILER_LIFETIMES.md) measures outward
promotion of an address-taken local and reuse after an inline helper returns.
Sixty-nine additional compiled forms find no exact match. Explain the native
early 16-byte region with real source boundaries before accepting a candidate.
The [ordered-store audit](RENDER_MATCHING.md) shows why final-output agreement
is insufficient: that candidate reverses two stores in 68,306 scalar fixtures.
A corrected full candidate retains native store order but differs in 13 bytes;
106 additional source trials did not produce an exact match.
The [matching grid-window recovery](GRID_MATCHING_C.md) now resolves the
remaining scheduling and frame differences through signed/unsigned angle
views and a consumed inclusive-endpoint operand. All 660 function bytes and
the complete ordinary/fresh executable match. The earlier
[prologue](GRID_RECOVERY.md), [compiler-phase](GRID_PHASES.md) and
[native candidate](GRID_NATIVE_COMPOSITION.md) studies retain their rejected
forms and bounded evidence. Continue natural scene ownership, framebuffer and
hardware timing verification; this source recovery does not accept F033.

| Function | Source |
| --- | --- |
| `func_8001DDF4` | [`src/base/transform.c`](../src/base/transform.c) |
| `func_8001F8B8` | [`src/file/tmd_prim_geom.c`](../src/file/tmd_prim_geom.c) |
| `func_8004CD38` | [`src/scene/render_context.c`](../src/scene/render_context.c) |
| `func_8004441C` | [`src/menu/ui_sprite.c`](../src/menu/ui_sprite.c) |

Confirm the live catalogue after building with
`python tools/decomp_workbench.py catalog`. SDK assembly is tracked separately.
Each C promotion must retain complete-executable equality and meaningful
types and control flow. Do not use copied instruction blobs or padding to
raise a coverage number.

The [level-model loader recovery](LBD_RECOVERY.md) removes `func_8004BE54`
from that list. It adds 600 bytes of matching C, preserves complete standard
and clean-build equality, and rechecks the 418 local LBD files. The C-byte
total at that checkpoint was 194,884 / 199,912 (97.48%); whole-feature acceptance remains open.

The [sprite scaling audit](UI_SCALE.md) checks 203,472 original and candidate
fixtures each, with zero stubs. Preserve the post-X-store Y denominator read
and skipped-division register behavior in further C attempts. The full C
candidate still has 12 byte differences; 108 additional helper trials did not
produce an exact match. UI drawing, natural caller reachability and PS1 timing
remain separate acceptance work.

## Original behavior and content

- Extend the [cold-start menu/dream/movement profile](COLD_START.md). Its
  recorded game outputs agree across two isolated original/rebuilt pairs,
  with a strict full-state pass in the published-tool repeat. The earlier
  unused emulator-label differences leave cold-boot repeatability open.
  Complete content, encounter, camera and original-hardware acceptance remain.

- Extend the [menu profile](MENU_LAYOUT.md) from constructed ownership graphs
  to natural constructors, screen assets, rendered glyphs/effects and complete
  controller reachability. Its 864 histories and 39 native methods are bounded
  F035/F036 evidence; sprite-scale matching C recovery remains open.
The [level-model loader audit](LBD_PIPELINE.md) checks all 418 inventoried local
LBD files, including native destruction/reloading, with actual allocator,
decoder, constructors and SDK routines. Two virtual-call declarations now
match the observed default methods. This closes those calls for the recorded
ready-CD fixture; pending I/O, cold hardware, caller ownership and rendering
remain separate work. Its initial full C loader candidate differed in 118 bytes,
and 191 initial source trials found no exact match. The subsequent
[matching recovery](LBD_RECOVERY.md) resolves it with 580 further source forms.

- Resolve asset/command inventory gaps and runtime reachability.
- Close virtual-call dependencies and verify semantic callback signatures.
- Extend native fixtures beyond the 39 currently checked callbacks and their
  documented scopes; see the [proximity composition](NPC_PROXIMITY.md) and
  [Hoop Girl script checks](HOOP_SCRIPTS.md). Complete natural encounters and
  actual movement/facing/scaling dependencies remain separate gates.
- Compare natural animation construction, lifetime and actor/render behavior.
- Review every feature's recorded scenarios, including rare RNG, save/card
  error, audio and hardware-timing branches.
- Extend [Japanese asset and replay evidence](JAPANESE_EDITION.md) beyond the
  recorded 6,000-frame scenario and review exhaustive content coverage
  separately from English v1. The [state diagnosis](NYMASHOCK_STATE.md)
  identifies the eight cold-boot bytes as unused Nymashock label storage;
  strict byte comparisons retain those differences.
- Extend the [Japanese controller and movement replay](MOVEMENT_PARITY.md)
  beyond its stage-3 floor-type-7 controls and one earlier link transition.
  Use native pad samples and all three input guards to distinguish requested
  controls from effective behavior, including pressed versus held commands.

The catalogue currently has 40 provisional groups. None has been accepted for
all required runtime scenarios. The [inventory](FEATURE_INVENTORY.md) lists the
remaining scenario for each group; 98.63% describes current game C bytes only.

## Developer tools and optional mods

- Keep AI-assisted context export and local analysis separate from original
  NPC behavior. The supplied tools make no model API calls.
- Retain explicit input hashes, dependencies and negative controls in reports.
- Extend emulator checks for duration multipliers and passive Gray Man.
- Keep all optional patched executables and discs outside the canonical build.

After the matching generation recoveries, 37 / 40 groups have all listed core
functions in C. The [NPC spatial composition](NPC_SPATIAL.md) checks seven
callbacks through actual transform/SDK/GTE dependencies in 26,194 fixtures;
natural histories, encounters and timing remain open. These overlapping
source groups retain zero whole-feature acceptances.

The [Gunman profile](GUNMAN_SCRIPTS.md) checks both original scripts and their
effect color arithmetic, including scheduled callback histories and mode-two
callback clearing. That profile raised bounded coverage to 36 / 107 at its
checkpoint. The locomotive extension now brings it to 39 / 107. Complete engine
frames, natural encounters, constructed attachment graphs, effect/render/audio lifetimes and
controller reachability remain required; this bounded profile does not close
F027. Current C recovery is measured separately above.
