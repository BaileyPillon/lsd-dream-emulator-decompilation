# Source and evidence provenance

The [input storage recovery](INPUT_STORAGE_RECOVERY.md) explains six existing
C frames through actual event, release, viewport, history-cell and spawn-key
inputs. Fifty-four unused declared bytes are removed. Twelve actual compiler
observations and fully relocated sized functions retain the original executable;
the ordinary/fresh builds and native cleanup regression are recorded in
[new metadata](input-storage-recovery-checks.json). Four source units change;
the other 388 protected game inputs retain their hashes. Identified inherited
storage explanations fall from 14 to 8, with no new C byte, NPC callback profile,
whole-feature acceptance or relaxed goal requirement.

The [accessor storage recovery](ACCESSOR_STORAGE_RECOVERY.md) removes three
inherited arrays while preserving their original instructions. Six actual
compiler observations distinguish the old arrays, removed-array controls and
consumed accessors. Identified storage explanations fall from 17 to 14; the
232 function bytes were already in C. Regular and fresh complete build evidence
is retained in [new metadata](accessor-storage-recovery-checks.json).

The [model/actor factory profile](ACTOR_FACTORY_OWNERSHIP.md) checks original
resource preparation, animation-zero initialization and three ownership
histories against an independent allocation/release plan. Its English-labelled
campaign preceded the accessor cleanup; its Japanese-labelled campaign follows
it. Both execute the same canonical image. Source, backend, input and executed
fault records are retained in [factory metadata](actor-factory-ownership-checks.json).
Complete object-payload oracles and natural encounters remain open. These
records add no matching C byte, NPC callback profile or whole-feature acceptance.

The [callback storage recovery](CALLBACK_STORAGE_RECOVERY.md) explains five
existing C functions through real four-byte callback/table views. Their forty
unused declared bytes and dead comparisons are removed; original function
instructions and normal/fresh complete images remain unchanged. Nine compiler
observations compare baseline, removed-array control and matching source.
The [new metadata](callback-storage-recovery-checks.json) appends the reduction
from 24 to 19 identified inherited explanations without adding C bytes or
runtime acceptance. Earlier snapshots, raw private evidence and all full-goal
requirements are retained.

The [matching menu recovery](MENU_LOOKUP_RECOVERY.md) adds 1,052 C bytes through
consumed typed vtable snapshots. Its normal/fresh complete builds, qualified
function spans, actual allocator traces and retained 864-history native profile
are recorded in [new metadata](menu-lookup-recovery-checks.json). Only the menu
C unit changes among the 392 protected game inputs; prior snapshots, original
data layouts, the frozen objective, the player and Bevy repository are retained.

The [generation lookup recovery](GENERATION_LOOKUP_RECOVERY.md) replaces two
assembly fallbacks with 580 matching C bytes. Normal and fresh complete builds,
requalified function spans and unchanged-assembly compiler traces support the
source recovery. Existing entry and structure native profiles pass before and
after promotion with their original inputs and explicit remaining scope.
[Recovery metadata](generation-lookup-recovery-checks.json) appends current
counts; earlier snapshots and the frozen project objective are retained.
Raw images, ELF files, generated assembly, debugger traces and buffers stay
private. The separate Bevy repository and running player are unchanged.

The [effect lifecycle supplement](EFFECT_LIFECYCLE.md) publishes metadata for
768 constructed lifecycle histories and earlier 471 construction fixtures.
The native harness, interval/object models, raw buffers, complete canonical
symbol link and failed diagnostics remain private local evidence. Four executed
behavior faults include one detected only by notification arguments. Two C
declaration corrections retain ordinary and fresh clean executable equality;
the recorded native campaigns preceded those edits and their original code
is byte-identical to the resulting build. The additive inventory preserves
earlier reports and acceptance counts.

The current project title is **LSD: Dream Emulator Decompilation**, published at
[LSD: Dream Emulator Decompilation](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation). The repository retains its original
GitHub identity, fork ancestry and Git history. Earlier frozen evidence
records retain their publication URLs and local paths.

## Repository ancestry

- Upstream: [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled).
- Imported upstream commit: `16a3914b9bcb75bd94a6b983ed3a952234461625`.
- Upstream history and authorship are retained. The publication adds the current
  C recovery and reusable tooling in a separate commit.
- [FirecatFG/lsddecomp](https://github.com/FirecatFG/lsddecomp) is acknowledged
  for original-toolchain identification and early segment research.

## Target identity

The target is the original Japanese PlayStation executable `SLPS_015.56`:

| Property | Value |
| --- | --- |
| Architecture | Little-endian R3000 MIPS-I |
| File size | 505,856 bytes |
| SHA-1 | `76322eeade5ebb22dca57fdeac7d68c30f06308d` |
| SHA-256 | `282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f` |

The local disc used for recorded emulator comparisons was an English-v1 asset
edition with this same canonical executable. Its translated assets are a
separate edition boundary. Those results compare original and rebuilt code
using the same assets and BIOS; they do not establish equivalence to every
Japanese-disc asset or hardware configuration.

## Publication boundary

The [Hoop Girl replay](NATURAL_HOOP_ENCOUNTER.md) and
[generation return-temporary investigation](GENERATION_RETURN_TEMPORARY.md)
append new evidence to the existing snapshots. Their check manifests contain
identities, hashes, bounded observations, and exclusions. The executed recorder
is published unchanged, with a separate pure helper regression check. Original
captures, save states, compiler RTL/assembly, and failed diagnostics remain
private. The older window recorder's input limitation is documented without
rewriting its executed bytes or frozen comparison metadata.

The October 11, 2026 feature inventory is a frozen report of local checks,
not an independently rerun result supplied by GitHub CI. References beneath
`.decomp-lab/` identify private evidence artifacts and are deliberately not
published. Ghidra databases, copyrighted inputs, full binary/context exports,
raw emulator captures and local service configuration stay outside Git.
Absolute paths in the published inventory have been replaced with logical
artifact references; their recorded content hashes remain unchanged.

Build and tooling instructions are reusable. A contributor with the required
original inputs can generate new matching-build, asset, NPC and replay reports
using the documented tools. Public CI runs the synthetic-fixture tests only.
The publication checkout's clean build and tooling checks are summarized in
[publication-checks.json](publication-checks.json); this contains metadata,
not game input or output bytes.

The feature catalogue records C recovery, inherited C-plus-assembly behavior,
bounded native checks and whole-feature runtime acceptance separately. It does
not claim a developer-official feature total or completed end-to-end parity.

The [save workflow supplement](CARD_SAVE.md) extends native evidence through
the original retry wrapper and actual SDK string/label helpers. Seven explicit
contracts cover file I/O, allocation and diagnostic output. Its independent
model, full-executable C comparison and private Ghidra metadata remain separate
from whole-feature and hardware acceptance. [card-save-checks.json](card-save-checks.json)
records the publication's source and evidence pins without game bytes.

## Save-title classification correction

The [save-title supplement](SAVE_LABEL.md) recovers `func_800507F8` in matching
C. The old 336-byte `asm/40FF8.s` segment combined this 240-byte game-support
formatter with six BIOS wrappers and their padding, totalling 96 bytes. The
whole segment had been classified as SDK. The new split counts the formatter
as game support while keeping the BIOS wrappers under `src/psyq/`.

Current game C coverage is 194,284 of 199,912 bytes, with 147,880 SDK bytes and
188 startup bytes excluded. Both the C numerator and game denominator increase
by 240 bytes; this is one recovered function and a classification correction.
The seven previously listed game assembly functions remain. The frozen initial
publication and pre-prompt reports retain their original measurements.

A matching complete build, isolated whole-executable comparison and 1,952
bounded native save-title fixtures verify the new source. The three public NPC
verifiers were rerun against the current build and passed their existing 6,784
cases. Hashes and scope are appended to [features.json](features.json). Original
inputs and reports remain private; public CI still tests synthetic fixtures.

## SDK signature and volume-API supplement

The [SDK audit](SDK_SIGNATURE_AUDIT.md) uses a pinned external catalogue to
check the ordered six-function volume region. It corrects the getter/automatic
volume names and declarations while retaining original executable equality.
The native getter passed 384 cases and three controls without stubs. Raw SDK
object and function-sized signature matches retain their different evidence
scopes and ambiguities. Historical reports remain preserved; current producer
hashes and callback rechecks are appended separately to the feature inventory.

## Render-context bounds supplement

The [bounds audit](RENDER_BOUNDS.md) verifies the original assembly function
in 4,648 native cases, including signed fields, inclusive boundaries and exact
short-circuit data-read traces. Four changed instructions are detected without
stubs. A compiled C candidate agrees on the bounded fixtures but differs at 38
byte positions and is not promoted. C coverage, NPC counts and whole-feature
acceptance are unchanged.

The private Ghidra project now reflects the reviewed SDK volume names and
three explicitly typed MIPS prototypes. Parameter storage and unchanged native
bytes were checked before saving. The project database, binary exports and C
candidate remain private; the public supplement contains metadata only.

## Rendering grid-window supplement

The [grid-window audit](RENDER_GRID.md) runs the original 660-byte helper in
74,832 scalar cases, including all angle words, with four explicit contracts
and eight detected controls. The private full C candidate gives the same
bounded results but differs in four executable bytes across two stores.
It is not promoted. Saved private Ghidra has reviewed caller/helper/builder
prototypes; their 1,232 native bytes are unchanged. Current counts and hashes
are appended separately to the inventory. Real GTE, downstream rendering
and whole-feature parity remain open.

## Rendering grid and streaming composition supplement

The [streaming composition audit](RENDER_STREAM.md) extends native execution
through the original builder, row splitter and seven-object slot selector.
It passes 45,408 bounded cases and detects four controls with three remaining
position/GTE contracts. The original table's slot binding is verified before
synthetic vtable execution. The nonmatching full C candidate passes the same
fixtures but retains four byte differences and is not promoted.

Two reviewed private Ghidra prototypes retain 460 native bytes unchanged;
parameter storage and successful saving were checked. Source/evidence pins in
[render-stream-checks.json](render-stream-checks.json) extend the publication
record without changing original feature, NPC, C or developer-capability counts.

## Rendering matching and ordered-store supplement

The [ordered-store audit](RENDER_MATCHING.md) adds executed-store observation
with immediate readback to the same 74,832 scalar fixtures. All three native
variants preserve checked final outputs. The four-byte C candidate changes
store order in 68,306 cases; a corrected full C candidate preserves it but
retains 13 executable differences. Neither is promoted.

The initial unsuccessful memory-hook method and controlled diagnostic are
preserved separately. The successful proof's hashes and 106 additional source
trials are pinned in [render-matching-checks.json](render-matching-checks.json).
Original inputs, raw reports and C candidates remain private. C, feature,
NPC, developer-capability and optional-mod counts are unchanged.

## Original sprite scaling supplement

The [sprite scaling audit](UI_SCALE.md) executes 203,472 original cases and the
same number of nonmatching C-candidate cases, with zero stubs. It checks ordered
halfword access and store readback, guarded buffers and the unused stack. Four
wrong controls alter checked outputs; 32 overlap fixtures expose the fresh Y
denominator read after X's store.

The failed global memory-hook method is preserved with an eight-run diagnostic
and producer hash. The successful verifier and private-output tests are public;
game inputs, candidate images and raw reports remain private. The full candidate
retains 12 byte differences and is not promoted. Metadata and historical count
preservation are recorded in [ui-scale-checks.json](ui-scale-checks.json).

## Original level-model loader supplement

The [level-model loader audit](LBD_PIPELINE.md) uses all 418 previously
inventoried local LBD files through both cold loading and native destruction
and reloading. The actual allocator, constructors, decoder, SDK routines and
driver-vtable initialization execute, with one ready-CD state contract and no
dependency stubs. Cold outputs and heap layouts have an independent reference;
reloads check defined fields and compare complete arenas between implementations.

The full candidate's loader bytes equal those used in the 1,672 native runs,
but its complete executable still differs in 118 bytes. Two header signature
corrections preserve the canonical build; no C function is promoted. The
public checker and metadata contain no disc bytes or candidate image. Inputs,
raw results and failed harness preflights remain private and preserved.
Source/evidence pins and unchanged counts are recorded in
[lbd-pipeline-checks.json](lbd-pipeline-checks.json).

## Matching level-model loader recovery

The [subsequent loader recovery](LBD_RECOVERY.md) promotes `func_8004BE54` as
600 bytes of C after a zero-difference comparison of the complete executable.
The standard build and a fresh source/toolchain copy also reproduce the
canonical executable. The clean copy contains no preexisting build objects.

The original 576-form typed search and four grid-capture forms, complete
candidate, source backup, native reports and clean-build inputs remain private
with preserved hashes. The promoted build passes 1,672 bounded loader runs and
five output controls. Earlier nonmatching candidates and publication records
remain unchanged. The new source moves C coverage to 97.48% and six remaining
assembly functions; it does not imply new original features or whole-feature
acceptance. Pins and before/after measurements are in
[lbd-recovery-checks.json](lbd-recovery-checks.json).

## Japanese edition and reconstruction supplement

The [Japanese edition verification](JAPANESE_EDITION.md) retains source metadata
and hashes for a separately acquired Japanese-labelled disc. Both editions'
683 extracted files were freshly hashed; all paths, LBAs and storage types
agree, with 69 changed payloads. Original CUE and failed reconstruction evidence
are preserved. A separate working CUE resolves the supplied filename mismatch.
The corrected packager preserves two EDC words only for identical valid Form2
sector bodies and reproduces the complete 648,088,896-byte source image.

Earlier runtime manifests did not pin the actual Nymashock binary. This
limitation remains explicit; fresh repeated runs use core selection and
schema-two identity checks. The new original/rebuild cold and shared-state
pairs agree, while an additional same-original cold boot still has eight
decoded state differences. These are retained without masking. Metadata in
[japanese-edition-checks.json](japanese-edition-checks.json) pins private evidence
and the public tooling changes without publishing disc, BIOS, asset or capture
bytes. Original feature and C-recovery counts remain unchanged.

## Nymashock native-state supplement

The [state diagnosis](NYMASHOCK_STATE.md) follows the actual loaded core's
symbols, native pointer graph and short-string copy instructions. Across 44
recorded checkpoint pairs, the 12 nonidentical decoded pairs each vary only in
eight unused bytes of the native `"CD"` label. Windows and Linux decoders agree;
input snapshots remain unchanged and no bytes are masked. These comparisons
retain their whole-byte failures and do not create whole-feature acceptances.

[nymashock-state-checks.json](nymashock-state-checks.json) pins private reports,
native disassembly, primary source snapshots and the read-only diagnostic.
The earlier Japanese report and metadata remain preserved at their published
hashes. Synthetic tests and source experiments include no original game,
emulator, BIOS, asset or captured state bytes in the public repository.

## Original position and streaming supplement

The [world-position audit](RENDER_POSITION.md) executes the actual wrapper,
resolver, world-slot selector, marker partition and record lookup. It verifies
their canonical virtual bindings and 1,004 native bytes. Five functions run
without stubs in 6,141 executions over 5,919 distinct inputs; nine original
functions run through the complete world-to-stream chain in another 5,670
cases with two GTE contracts. Six
deliberate faults are detected, and three original zero-divisor exceptions
are tied to the executed `BREAK` rather than Unicorn's subsequent PC-zero report.

[render-position-checks.json](render-position-checks.json) pins the complete
private proof and code, preserves preliminary diagnostic failures separately,
and records 360 further nonmatching C comparisons. No game source, compiler
flags or canonical executable bytes change. The fixtures and metadata contain
no distributed game, BIOS, emulator, asset or captured state bytes.

## Original SDK rotation supplement

The [rotation audit](RENDER_ROTATION.md) executes 652 bytes of inherited
SDK `RotMatrix` against independent staged Euler products, using the verified
canonical packed table as a shared local data input. It records 203,259
executions over 203,257 distinct guarded fixtures and 5,670 ten-function
composition inputs with only `ApplyMatrixLV` contracted. The individual
axis sweeps do not exhaust the full three-angle Cartesian domain.

[render-rotation-checks.json](render-rotation-checks.json) pins the native
proof, input-count audit, four detected faults and local tooling checks.
The preliminary import failure is preserved separately. No game/SDK source,
compiler flags or canonical executable bytes change. The public metadata
and synthetic tests contain no original table, game, BIOS, emulator, asset
or captured state bytes.

## Original matrix application and native GTE supplement

The [native GTE audit](RENDER_GTE.md) executes the original SDK helper over
109,501 distinct guarded fixtures and eleven original functions over 13,230
distinct composed inputs, with zero function-output stubs. A checked native
Nymashock core handles 245,470 commands plus one identity self-check. A
separate audit verifies every logged request/response and records 8,982
distinct command inputs; command repetitions remain explicit.

[render-gte-checks.json](render-gte-checks.json) pins private proofs, ordered
logs, compiler/runtime inputs, primary source snapshots, four detected faults
and tooling checks. Initial compiler-reference and cycle-assertion failures
remain preserved. Reviewed inlined CR/MAC transfers are explicit; complete
PS1 CPU execution, load delays, original hardware and scenes are unaccepted.
No game/SDK sources or canonical executable bytes change. The public profile,
code and synthetic tests distribute no emulator, game, BIOS or asset bytes.

## Original collision supplement

The [collision audit](COLLISION.md) executes original primitive and transform
paths through their real bounds, decoder and SDK dependencies, with no output
stubs. Its 12,244 SDK checks, 12,696 distinct primitive inputs and 6,912 stage
graphs remain bounded evidence. The audit separates 1,152 repeated transform
inputs and checks all 76,387 native command/counter responses independently.

[collision-checks.json](collision-checks.json) pins the private proofs, sources,
ordered log audit, range metadata, fault controls and local validation. Initial
preparation diagnostics and the corrected clipping-test expectation are retained
separately. Two misleading source comments change; game function bodies,
compiler flags and canonical executable bytes are preserved. The public files
contain no game, BIOS, emulator, lookup-table or captured-state bytes. Complete
CPU timing, natural encounters and whole-feature acceptance remain open.

## Primitive C candidate and non-NULL midpoint supplement

The [collision research fragment](../research/collision/README.md) is separate
from the canonical build. Its full private executable differs in 22 bytes,
all in the primitive's later bounds-stack displacements; it is unaccepted C.
The SDK workspace, instruction sequence, registers and distance storage match.
The original executable and game source remain unchanged.

[collision-recovery-checks.json](collision-recovery-checks.json) pins private
full-build comparisons, 251 compiled source trials, the public fragment,
paired comparison proofs and ordered native-log audits. It distinguishes
12,696 primitive pairs, 1,566 caller overlap pairs and 6,912 stage graphs from
repeated original/candidate executions. The 5,400-fixture midpoint audit
checks original clipping with caller overlaps and a deliberate broken shift.
Initial bridge-path and synthetic test-fixture failures are retained separately.
One report field changes after the paired run; its comparison-engine AST and
the current candidate's reported value are verified unchanged.

The public files contain reconstructed C, synthetic fixtures, addresses,
offsets and hashes, without proprietary executable, asset, BIOS or runtime
bytes. No C promotion or original-feature acceptance is claimed. Complete
CPU timing, natural scenes and multi-cloud encounters remain open.

## Collision compiler-layout supplement

The [compiler-layout diagnostic](COMPILER_LAYOUT.md) observes the actual bundled
GCC allocator rather than inferring allocation solely from published FSF source.
Its six final compilation runs retain 199 nested allocator calls and require
complete assembly equality against untraced compilation. Compiler, source,
producer, backend and configuration identities are checked before and after.

[compiler-layout-checks.json](compiler-layout-checks.json) pins the final public
producer and reports, 55 compiled source-form comparisons, retained RTL dumps
and earlier private allocator traces. Actual row minima are 22, 1,411 and 103;
the private lab's initialized threshold is recorded separately. A synthetic-leaf
calibration failure is retained: GCC makes a zero-byte call even when no stack
area is needed. Corrected G0/G8 controls verify no area growth.

The existing complete 22-byte candidate image is revalidated rather than rebuilt
or promoted. The canonical 305-object build and its original image retain byte
equality; 247 tooling tests pass locally on Windows and Linux. No original game
or emulator is executed by the tracer, and no native gameplay coverage is added.
Private assembly and compiler logs remain outside Git. Earlier feature evidence
and every accepted C, original-feature, NPC, developer-capability and optional-mod
count are preserved; the full parity objective remains unfinished.

## Collision compiler-lifetime supplement

The [lifetime diagnostic](COMPILER_LIFETIMES.md) decodes the exact bundled
compiler's 32-byte temporary-slot records after checking its SHA-256. The
layout is checked against retained actual compiler instructions. Five successful
runs retain 1,336 calls, with complete assembly equal to normal compilation;
a separate absent-function control is rejected.

[compiler-lifetime-checks.json](compiler-lifetime-checks.json) pins producer,
backend, helper, compiler, source and private-output identities. It records raw
slot promotion, release and reuse, and independently scores 69 compiled source
forms. The measured helper boundary leaves the native early region unexplained;
no exact C implementation or original runtime feature is accepted.

Normal GDB breakpoint instrumentation is acknowledged separately from the
absence of additional explicit writes, substitutions or forced results.
Compiler observations execute no original game or model service. Earlier
allocator evidence and every original feature record remain frozen. Private
compiler logs, generated assembly and game inputs remain outside Git.

## Existing source-padding audit

The [source-quality audit](SOURCE_QUALITY.md) identifies five literal dummy
stack declarations in matching C, with 56 declared local bytes. Git ancestry
and the frozen pre-prompt commit show the constructs already existed before
this prompt. The audit preserves their canonical source and earlier coverage
records while making their unresolved source explanations explicit.

[source-quality-checks.json](source-quality-checks.json) pins five complete
private removal builds and independent comparisons. Each failure is confined
to the selected function's SP-relative displacements. Mapped code spans total
1,504 bytes; boundaries use the retained link map rather than an absent ELF
symbol table. No proprietary image, generated assembly or captured game state
is published. Ten additional collision source forms and one actual compiler
allocation trace are recorded separately from original gameplay evidence.

The complete canonical build still matches. No C promotion, new original
gameplay coverage, whole-feature acceptance or count change is claimed.
The six assembly functions and five known source workarounds remain distinct
completion requirements; the audit does not certify every possible workaround.

## Card cleanup supplement

The [cleanup audit](CARD_CLEANUP.md) adds a reusable original-machine-code
verifier and eleven synthetic contract/custody tests. Original and private
padding-removal images pass the same 501 bounded inputs; three faults are
detected. One allocator stub poisons volatile registers and performs declared
adversarial writes. Real allocator behavior and physical card I/O are not
accepted by this proof.

[card-cleanup-checks.json](card-cleanup-checks.json) pins those runs, 36 rejected
source forms, two controls and four unchanged-output compiler traces. Earlier
source-quality and compiler metadata remains frozen. No original image,
generated assembly, raw memory capture or game input is published. The current
complete build still matches; no C source, feature or padding-removal promotion
is claimed. Original game behavior and optional mods remain unchanged.

## Native card heap supplement

The [heap composition](CARD_HEAP.md) adds a separate valid-ownership profile
that executes cleanup through the original pool allocator and lock helpers,
without function-output stubs. The earlier allocator-contract profile and
its broader adversarial inputs remain frozen rather than being relabelled
as native heap behavior.

[card-heap-checks.json](card-heap-checks.json) pins the final native producer
report, all seven original ranges, three fault controls, isolated backend
library/bindings and failed stock/current-source backend diagnostics. It
retains 96 component sequences and 180 cleanup fixture layouts per image,
with a second cleanup call per layout. Complete guarded buffers, native
global/lock transitions, release order, stack and saved registers are checked.
The original and candidate nested cleanup graphs run uninterrupted; entire
RAM images are preserved between separate host-issued calls.

The private executable, native reports, backend binaries and logs are excluded
from publication. No original game or disc input is distributed. The current
canonical build still matches; accepted source/feature/NPC/mod counts and the
six assembly plus five source-workaround requirements remain unchanged.

## Matching writer recovery

The [writer supplement](CARD_WRITER_RECOVERY.md) promotes one 960-byte game
function, preserving byte identity in both standard and fresh clean complete
builds. [card-writer-recovery-checks.json](card-writer-recovery-checks.json)
records the LF Git source and retained CRLF local-source hashes separately.
The historical GNU varargs interface is a matching reconstruction; original
author declarations remain unknown. Existing feature records are preserved
verbatim before the new supplement, whose overrides mark F037 and F038
listed-core C completion. It accepts no whole feature and distributes no
original inputs, compiler traces or native execution buffers.
## Japanese movement and controller-poll supplement

The [movement supplement](MOVEMENT_PARITY.md) retains four strict shared-state
original/rebuild comparisons. [movement-parity-checks.json](movement-parity-checks.json)
pins private reports, the original pad-table identity, script/start-state/core
identities, public producer hashes and both local test logs. No decoded field,
pad mask or state member is normalized. All 9,000 emulator-frame records, 27
image/GPU/state checkpoints and 6,634,234 stereo PCM sample frames per side
agree. Historical 43-field records remain distinct from current 47-field ones.
Private short-pulse diagnostics remain preserved rather than being relabelled
as effective inputs. Original game images, BIOS, captures and raw state buffers
remain excluded. No game C function or whole feature is promoted; original
NPC behavior, AI-assisted tooling and optional mods retain separate counts.
## Additional original scripted callback supplement

The [callback extension](SCRIPTED_EXTENSION.md) records five newly checked
original callbacks and rechecks the preceding scripted, Lion and Gray Man
profiles. [scripted-extension-checks.json](scripted-extension-checks.json) pins
current reports, producer/model tests, original function/property bindings,
loaded Unicorn and binding identities, actual call/state counts and private
negative controls. Original game inputs, raw buffers and faulted code remain
private. The canonical executable and its source/configuration are unchanged.
The new publication supplement raises bounded callback coverage from 11 to 16
without altering earlier inventory bytes or accepting a whole encounter or
feature group. Developer analysis and optional mods stay separate from original
scripted NPC behavior; no model API call or new gameplay behavior is added.
## Expanded layout correction and spatial composition

[source-layout-expanded-checks.json](source-layout-expanded-checks.json) pins
the wider 28-function source review, full-unit removal builds, upstream lineage,
four withdrawals and current standard/clean canonical builds. The unaccepted
padding-free fragments preserve readable work in research. No game input or
generated assembly is published. Earlier C measurements are retained as dated
compiled-source snapshots; they do not waive the no-padding source criterion.

[npc-spatial-checks.json](npc-spatial-checks.json) pins seven-callback spatial
composition, actual routine/GTE entry counts, bridge/backend identities, four
detected faults and source/tests. The earlier abstract profile remains frozen.
Valid synthetic object graphs and one trigger-ratio contract leave natural
construction, histories, visible/audio behavior and full hardware timing open.

## Generation structure source and execution supplement

[generation-structure-checks.json](generation-structure-checks.json) retains
hashes and summaries for 34 qualified source forms, three complete candidate
images, actual compiler stack/lifetime observations and bounded native
original/candidate comparisons. Two initial unused-argument diagnostics remain
excluded; corrected forms preserve their negative result. Full graph buffers,
source/build/backend preservation and five deliberate faults are checked.
Only original function/table identities, source fragments and evidence metadata
are published. Complete game images, raw buffers and altered native code remain
private. Earlier feature records are retained through an append-only supplement.
Matching C remains unchanged; bounded execution does not waive the source gate
or accept construction, encounters, lifecycle histories or a whole feature.

## Mode 0 effects and consecutive graph supplement

[generation-effects-checks.json](generation-effects-checks.json) pins the current
checker, fifteen original methods, nine tables, full graph comparisons,
consecutive histories and nine detected faults. Changed-instruction execution
is measured; native method outputs are not replaced. Six private direct
aggregate diagnostics emit the same rejected code as the earlier pointer
hypothesis. Earlier source and inventory records remain frozen and reconstruct
exactly after removing only the new supplement. Runtime inputs, raw buffers
and faulted code remain private; no original behavior or whole feature is added.

## Original entry scanner and source-lifetime supplement

[generation-entry-checks.json](generation-entry-checks.json) pins the original
entry/table/owner bindings, three actual methods, full packet/graph comparisons,
six executed faults and backend/source preservation. Thirty-eight qualified
source forms exclude six initial unused-local diagnostics. Original standalone
text-section lengths and selected-function spans remain distinct: the by-value
form emits a forty-byte helper. Published ten-byte fragments with defined word
arithmetic reproduce their recorded complete candidate images. Original game
inputs, generated assembly, raw buffers and faulted code stay private. Earlier
inventory and source measurements remain frozen; no source or whole feature is
promoted by bounded matching behavior.

## Unpadded overlap source supplement

[overlap-recovery-checks.json](overlap-recovery-checks.json) pins the two-point
fragment, complete-image isolation, 27 qualified source forms, actual compiler
allocation observations and 6,912 paired native graphs. The failed older-bridge
attempt is retained separately from the successful current-bridge run. The height
fault has a measured coarse-path execution; its second patched location is not
claimed executed. Raw game images, generated assembly, caller buffers and faulted
code stay private. Earlier feature records remain frozen and reconstruct after
removing only the new supplement. Neither source nor whole feature is promoted.

## Grid compiler-phase source supplement

[grid-phase-checks.json](grid-phase-checks.json) pins 133 independently rechecked
source trials, two complete candidate builds and two actual compiler observations.
The phase reader revalidates raw trace qualification and preserved artifact/input
hashes. Unsized GNU marker labels are excluded from function spans; later
function-begin note relocation is distinguished from earlier source boundaries.
Original code, generated assembly and candidate executables remain private.
Earlier feature and source measurements remain frozen. No source or whole
feature is promoted, and no new gameplay execution is claimed.

## Original menu layout and acceptance supplement

[menu-layout-checks.json](menu-layout-checks.json) pins 62 independently
rechecked source trials, three nonmatching complete images and 864 constructed
histories replayed through 39 original methods per image. The successful proof
checks complete caller/heap/global buffers, independent semantic rules, three
executed faults and preservation of 27 dependencies. Its qualified isolated
Unicorn 2.1.2 backend remains separate from the main analysis environment.

Two callback declaration corrections are verified by standard and fresh clean
builds. The new clean copy starts without build objects and pins 363 build
inputs; only those two declarations differ from the previous clean inputs.
Older source-trial headers remain verified against the retained earlier copy.
The initial stripped-ELF, stale-object and wrong-backend attempts remain
diagnostics, separate from the successful active-object range proof. Public
code and metadata contain no original game images, generated assembly, raw
buffers, BIOS, assets or faulted native code. Earlier feature records reconstruct
after removing only the new supplement; no source or whole feature is promoted.

## Actual compiler memory-store supplement

[compiler-memory-stores-checks.json](compiler-memory-stores-checks.json) pins two
observations made with the public exact-compiler tracer, independently rechecks
eight memory-store decisions and eight equality calls, and preserves complete
assembly equality. Raw traced compiler memory, original code and generated
assembly stay private. The mirrored GNU 2.6.3 source is a separately pinned
reference; actual binary observations support the recorded decisions.

Fifty C source forms retain zero exact selected functions. Three C++ controls
compare isolated bodies with the same integer typedefs; they are not complete
translation-unit checks or C promotions. Initial preprocessing/declaration
failures remain excluded diagnostics. All 377 local tooling tests pass; earlier
feature records reconstruct exactly after removing only the new supplement.

## Original NPC proximity supplement

[npc-proximity-checks.json](npc-proximity-checks.json) pins the public checker,
six semantic/domain guards, 26 original function ranges, original entity-table
bindings and the report from 10,408 distinct fixtures through 25 actual routines.
The loaded Unicorn 2.1.4 library and Python binding, bridge executable and four
native runtime components are retained by hash. The exact Windows runtime path
is documented in [NPC_PROXIMITY.md](NPC_PROXIMITY.md); it differs from older
illustrative runtime paths.

An independent audit reconstructs the distinct generated inputs, verifies
original words and seven executed faults, and checks all 7,266 ordered GTE
exchanges. There are no dependency output stubs. Original code executes through
the event path with inactive geometry in deliberately meshless, childless
graphs; this is not natural encounter or full timing acceptance.

Initial wrong-runtime, command-observation-shape and event-number diagnostics
remain separate from the passing preflight and full proof. Raw game images,
generated assembly, full memory buffers, GTE logs and private faulted code stay
outside Git. All 383 local tooling tests pass. Earlier feature bytes reconstruct
after removing only this supplement; four new bounded callbacks do not promote
source functions or accept whole features.

## Bounds return/type source supplement

[bounds-source-types-checks.json](bounds-source-types-checks.json) pins three
retained experiment reports and an independent ELF qualification. It checks
66 C forms and six isolated C++ bodies against complete original/function spans;
no exact match or source promotion is claimed. The C++ named-return reference
is a later GNU manual; actual syntax acceptance and emitted bytes come from the
pinned retained frontend.

Thirty-two parser attempts represent sixteen packed-word ideas tried with two
attribute placements. They remain excluded and unqualified. The initial
missing optional ELF-library attempt is retained separately; the successful
audit uses the standard library. All game/source inputs are preserved, raw
code stays private and removing only this supplement restores earlier feature
bytes. No new original gameplay cases, tools, mods or whole features are added.

## Menu storage, ABI and function-comparison supplement

[menu-abi-source-checks.json](menu-abi-source-checks.json) pins 27 independently
linked menu C forms, eleven complete linked spans from twelve compiler ABI
diagnostics, and two retained candidate demonstrations with the public comparator.
The original span authority remains a separate reviewed inventory requirement;
the comparator validates complete candidate ELF extents. It never promotes source
or treats reordered bytes as a complete-image match.

The initial menu source guard stops before compilation. One ABI link failure and
five packed syntax/layout probes remain excluded from complete candidate counts.
All 391 canonical build inputs and 363 retained clean inputs are unchanged;
the standard and retained clean executables preserve the canonical hashes.
All 396 local tooling tests pass on Windows and WSL. Raw words, linked ELFs,
compiler output and images stay private. Earlier feature bytes reconstruct after
removing only this supplement; no C function or whole feature is promoted.

## Matching cell-bounds data and native selection supplement

[stream-exclusion-checks.json](stream-exclusion-checks.json) pins a twelve-byte
record recovered from the original data section into C, the corrected setter
interface, standard/fresh 306-object builds and native selection evidence. The
complete C data section and its sole named label establish ownership despite the
legacy label's zero symbol size/type; a full executable comparison preserves all
original bytes. The failed stronger symbol assumption stays separate.

The corrected native proof checks 9,252 distinct constructed graphs through ten
actual routines with no dependency output stubs. An independent audit reconstructs
the domain, verifies native slot/row entry counts and rechecks three executed
fault controls. The failed final-tally assertion remains a retained diagnostic.
Older source/build/feature snapshots remain frozen; removing only this supplement
restores earlier feature bytes. Raw images, original code and native buffers stay
private. One C data record does not raise C function or whole-feature counts.

## Model enumeration and playable-build supplement

[model-enumeration-checks.json](model-enumeration-checks.json) pins six source
declaration corrections, five independently qualified complete linked function
spans, standard and fresh 306-object matching builds, and the repeatable native
profile. Its 1,584 owned fixtures and 213,984 decoder visits execute original
code with no substituted outputs. The failed initial report writer is retained
as an excluded diagnostic, and the repaired producer is run in fresh processes.

[play-build-checks.json](play-build-checks.json) records preparation of a verified
local play profile and a strict 1,800-frame original/rebuilt movement/audio
replay. Desktop shortcut paths, original disc/BIOS inputs, full captures, linked
images, native details, and compiler outputs remain private. Only bounded
counts, hashes, and scope metadata are published.

The added feature-inventory supplement preserves every earlier field and
snapshot. Matching C bytes and whole-feature acceptance do not increase.

## Natural window-link supplement

[natural-window-link-checks.json](natural-window-link-checks.json) records the
2,400-frame original/rebuilt window scenario. The published Lua bytes equal
the executed scripts. All declared launch inputs are revalidated, every
controller/NPC/scene log byte agrees, and five complete RAM/image/save-state
member checkpoints agree. ZIP wrapper bytes differ and are reported separately.
Audio, direct callback entries and whole-feature acceptance are not claimed.
Original game inputs and raw captures remain private. Removing only the new
feature supplement reconstructs the preceding committed inventory bytes.

## Generation-interface supplement

[generation-interface-checks.json](generation-interface-checks.json) records
the three matching C/header corrections, both complete builds, sixteen
qualified source forms, the separate unaccepted dispatcher comparisons, and
five existing original/rebuilt RAM snapshot pairs. The observer and source
fragments are published; game files, RAM and altered-input copies stay private.

The native campaign tests the ten-byte-different scalar candidate. The later
eight-byte method-return form has a complete-image comparison but no native
campaign in this supplement. Line-ending-only normalization is recorded
separately from source-interface recovery. Neither observation nor a plausible
stack frame raises original feature, NPC, or matching-C recovery counts.

## Grid candidate native-composition supplement

[grid-native-composition-checks.json](grid-native-composition-checks.json)
records complete candidate-build qualification and the paired original/C
comparison through the existing eleven-function SDK/GTE and streaming graph.
The 24,780 distinct inputs per image include 13,230 retained inputs and 11,550
added to this graph profile. Positive code is unchanged; every fault stays in
a separate private VM. Executables, generated ELF/assembly, complete source
units, native command logs and graph bytes remain private. Published evidence
contains counts, hashes, fault locations and scope metadata.

The inventory supplement preserves all preceding fields and snapshots. C
recovery, whole-feature acceptance, NPC coverage and optional mods do not
increase, and the Bevy repository is separate.

## NPC state and cycle supplement

[state-cycle-script-checks.json](state-cycle-script-checks.json) records four
complete callback extents from a fresh canonical 306-object symbol link and
the expanded 278,115-fixture native scripted campaign. The 155,597 added
fixtures retain explicit dependency contracts. Fox's actor-child fan-out
executes with zero children; visible effects are not inferred from that
traversal. All 122,518 previous input records retain their frozen digest.

Game images, generated code, buffers, faulted VM copies and compiler outputs
stay private. Published records contain counts, hashes, scoped behavior and
measured controls. Earlier inventory fields remain intact. Bounded NPC coverage
increases; matching-C bytes and whole-feature acceptance do not.

## Glyph character interface supplement

[glyph-character-api-checks.json](glyph-character-api-checks.json) records the
before-header compiler rejection and corrected typed-call compilation, complete
original method spans, 4,656 native inputs, three measured faults and eight
target ABI assertions. The original table and template are pinned. Both regular
and fresh 306-object clean builds retain the entire canonical executable.

Compiler products, complete source units, game bytes, native buffers and faulted
VM copies remain private. Published records distinguish the two analysis callers
from the original methods and preserve preceding inventory fields. This changes
two game build inputs and no original behavior; C recovery, NPC coverage and
whole-feature acceptance retain their preceding counts. Bevy remains separate.

## Populated actor child flag supplement

[actor-child-flag-checks.json](actor-child-flag-checks.json) records the original
typed-call compiler rejection, corrected compiled caller, three complete native
function spans, original table bindings, 16,512 case inputs and four measured
instruction faults. The 48 histories retain the same graph between five calls.
Every positive method runs without a function-output contract. The first failed
guard comparison is retained as excluded instrumentation evidence.

Both complete builds remain canonical. Two pinned game inputs change; the other
390 retain their prior hashes. Original game bytes, generated caller/ELF code,
complete native graphs and compiler outputs remain private. Earlier inventory
fields and source/feature/NPC counts are preserved. Fox's callback and natural
encounters are outside this new campaign, and Bevy remains separate.

## Periodic NPC spatial supplement

[npc-periodic-spatial-checks.json](npc-periodic-spatial-checks.json) records
three complete callback extents and their original property bindings from a
fresh canonical 306-object symbol link. All 2,628 distinct initialized inputs
pass with real proximity, movement and GTE dependencies, without output stubs.
The shared harness also repeats the preceding 10,408-case proximity campaign
with its original checked-buffer digest unchanged.

Published data contains hashes, counts, method ranges and measured fault
locations. Game images, generated code, full graph buffers and native logs
remain private. Two new bounded callbacks raise coverage from 32 to 34 of 107;
Bird was already counted. Matching-C bytes and whole-feature/encounter
acceptance do not increase. All prior inventory snapshots and the separate
Bevy port are preserved.

## Collision query interface supplement

[collision-api-checks.json](collision-api-checks.json) records the before/after
compiler diagnostics, 21 target layout assertions, 76-byte analysis caller,
12,696 reused constructed query inputs and four executed field-load faults.
Both complete game builds remain canonical. Three pinned game inputs change;
the other 389 retain their preceding hashes. The primitive research fragment
retains its complete nonmatching code and 22-byte difference.

Generated code, game images, full buffers and compiler products remain private.
The scene-node caller is qualified by complete executable equality; it is not
executed in this new native campaign. Published metadata distinguishes those
claims and preserves previous inventory fields and source/feature/NPC counts.
Original NPC AI, optional mods, AI-assisted tools and Bevy remain separate.

## Narrow bounds comparison supplement

[bounds-narrow-comparison-checks.json](bounds-narrow-comparison-checks.json)
records the published 19-byte research candidate, its complete sized function,
4,648 repeated original/candidate inputs, eleven executed differing instruction
words, four measured faults and actual compiler allocation observations.
The 128 compiler observations include controls; twenty diagnostic relinks add
no compilations. The initial linker-placement failures and wrapper status-label
assertion remain retained, with the subsequent audit recorded separately.

All 392 matching-game build inputs and the complete canonical executable remain
unchanged. Earlier 21-byte source evidence and all prior inventory snapshots
are retained. Original game images, linked code, complete buffers, failed runs
and compiler outputs stay private. No accepted C bytes, whole-feature/encounter
coverage, NPC profile, mod or capability category is added. Bevy is unchanged.

## Gunman script and effect supplement

[gunman-script-checks.json](gunman-script-checks.json) pins the two-callback
comparison, 26 sized native spans, all original property bindings, source and
backend identities. The 36,338 standalone fixtures, 15 scheduled histories and
eleven completed instruction faults are distinct from the pre-execution store
guard control. The initial memory-hook and delay-slot guard failures remain
retained alongside their exact source snapshots; they are not passing reports.

The final report executes the original effect factory and color arithmetic,
with explicit effect-construction, attachment, geometry, notification and sound
contracts. All 392 matching-game build inputs remain unchanged. Original images,
ELF/assembly, whole buffers, source snapshots and faulted code stay private.
Only developer code, tests and metadata are published. The inventory appends
two bounded callback profiles while preserving previous measurements, the
canonical executable, source/feature acceptance counts and the Bevy repository.

## Effect activation type recovery

[effect-activation-api-checks.json](effect-activation-api-checks.json) records
three original effect slot bindings and the corrected four-argument interface.
The entity field at `0x50` has a pointer producer in the original scene-node
attachment code and is consumed as an object by activation. The source now
names that field `m_EffectTarget` and removes the two callback casts.

Four game inputs change, with the other 388 retained. Normal and clean builds,
MIPS layout checks, two rejected declaration regressions, the virtual-table
audit and the existing Gunman replay retain their separate evidence records.
Replay fixtures are reused and add no new original scenarios or NPC profiles.
Private compiler inputs, complete outputs, original images and failed controls
remain outside publication. C recovery, feature/encounter acceptance, mods,
developer capability categories and the separate Bevy repository are unchanged.

## Constructor and actor storage recovery

[constructor-actor-storage-checks.json](constructor-actor-storage-checks.json)
records two existing C functions whose unused storage is replaced by consumed
four-byte method/table references. Eight qualified source comparisons and six
complete-source allocator observations preserve exact functions and full images.
Regular and fresh 306-object builds remain canonical. Two of 392 protected game
inputs change; the other 390 and the frozen objective retain their hashes.

The inherited storage remainder falls from 19 to 17, with no new C bytes,
original fixture domains, NPC profiles or whole-feature acceptance. Thirty-seven
separate renderer/overlap comparisons retain no exact match. Six further forms
emit a real helper and are excluded from the single-function count. Failed
attempts, game images, ELF exports and complete compiler traces remain private.
Historical measurements are preserved; the Bevy repository and player are unchanged.

## Overlap result lifetimes

[overlap-result-lifetimes-checks.json](overlap-result-lifetimes-checks.json)
records the current unaccepted 148-byte overlap difference, its complete sized
ELF span and three normal/instrumented source observations. All 69 isolated
source comparisons are independently requalified. The original early region
remains unexplained despite the matching total frame size.

The current candidate repeats the existing 6,912 native graph pairs, retaining
full caller buffers, ABI and ordered GTE comparisons. The height control patches
two sites but enters only the coarse one. Candidate frame metadata now comes
from the actual prologue/epilogue. No C bytes or original runtime domain are added.
All 392 canonical inputs, the original executable and historical metadata remain
unchanged; private images, source trials and complete reports stay outside Git.

## Reproducible actor child construction

[actor-child-construction-checks.json](actor-child-construction-checks.json)
records a public extraction-driven CLI for 22 sized original functions. The
diagnostic ELF retains symbols only after its complete executable equals the
canonical image. English-v1 and Japanese-labelled extractions each pass 222
construction executions, with complete independent actor/manager/pool checks,
two memory patterns and two executed faults. Edition runs are not additional
content or features; descriptors, pool binding and SDK matrix remain fixtures.

All 392 canonical game inputs, source-recovery counts and the frozen objective
retain their hashes. Reports, diagnostic images and extracted assets remain
private. No NPC callback or whole encounter is accepted by this profile, and
no model API is invoked. The separate Bevy port and current player are unchanged.

## Original child destruction and reuse

[actor-child-lifetime-checks.json](actor-child-lifetime-checks.json) records the
optional native lifetime profile. It checks original construction, populated
entry guards, destruction, repeated cleanup and reconstruction on one actor,
CPU and pool. All 40 original function extents must match sized symbols and
canonical bytes; no dependency outputs are supplied by the host.

Complete buffer and allocator-ownership comparisons retain stale payloads and
the original terminal count of -1. Five private instruction faults must execute
and fail their declared independent buffer comparisons. Supplied descriptors,
the pool binding and SDK matrix table remain explicit inputs. Full actor/model
creation, attached descendants, failures, playback and natural encounters remain
open. C recovery, source-quality remainders and whole-feature/NPC acceptance
counts are unchanged; the earlier constructor-only evidence remains frozen.
