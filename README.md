# LSD: Dream Emulator Decompilation

**A matching decompilation of LSD: Dream Emulator for the original PlayStation.**

[![Tooling tests](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/actions/workflows/tools.yml/badge.svg)](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/actions/workflows/tools.yml)

This project reconstructs the 1998 game's native MIPS code in readable C,
with a reproducible build and tools for studying its dream systems, assets
and scripted NPCs. It continues [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled)
and preserves that project's Git history and contributor attribution.

[Build](#build-the-matching-executable) · [Play the matching build](docs/PLAYING.md) ·
[Status and roadmap](docs/ROADMAP.md) · [Contribute](CONTRIBUTING.md)

The [cold-start comparison](docs/COLD_START.md) now exercises the original
title menu into a playable dream, with recorded turning, walking and audio.
The published-tool repeat matches all recorded outputs, including save states;
an earlier pair's emulator-label differences remain documented separately.

The [first-dream replay](docs/COLD_DREAM_CYCLE.md) now extends that route
through the natural time limit, dream chart and visible `Day 002` menu,
with 30,000 frames per disc and matching complete PCM. Its eight differing
emulator-label bytes per state remain visible in the strict result.

An optional [emulator media-initialization patch](docs/EMULATOR_LABEL_INITIALIZATION.md)
passes that 30,000-frame first-dream profile with all 61 complete-state
checkpoint pairs equal. The distributed profile retains its recorded failure.

The verified local build reproduces the original Japanese executable byte for
byte. **Full C recovery and independently reviewed gameplay coverage are still
in progress.** The remaining assembly is regenerated from your own executable.
Game discs, executables, extracted assets and PlayStation BIOS files are not
distributed here.

## Current status

The current verified snapshot is dated October 17, 2026. These are
separate measures, not a whole-game completion percentage. The initial
publication and subsequent evidence are retained separately.

The [movie audit](docs/MOVIE_INVENTORY.md) now checks all 39 movie streams,
22,382 encoded frames, and 620 original path/RNG fixtures. The later
[startup comparison](docs/MOVIE_PLAYBACK.md) matches 9,001 complete GPU-memory
hashes, 32 full-state checkpoints, and complete PCM for one neutral replay.
All-movie decoding, skip/error branches, and complete feature acceptance remain open.

| Measure | Verified snapshot |
| --- | ---: |
| Matching game-function bytes compiled from C | 197,172 / 199,912 (98.63%) |
| Known remaining game assembly functions | 2 |
| Known C functions with unresolved unused local storage | 2 |
| Original NPC/behavior callbacks with C bodies | 107 / 107 |
| Original callbacks with bounded native comparisons | 39 / 107 |
| Provisional behavior/system groups with listed core functions in C | 38 / 40 |
| Entire feature groups independently accepted at runtime | 0 / 40 |

The feature inventory has 40 provisional groups; an official exhaustive
feature total is unknown. SDK and startup code are excluded from the C-byte
denominator. Bounded native and emulator comparisons have passed, including
a 6,000-frame sequence with matching frame, GPU, state and PCM audio output.
Their scope and remaining gaps are documented in the
[feature inventory](docs/FEATURE_INVENTORY.md) and [roadmap](docs/ROADMAP.md).
The [model enumeration interfaces](docs/MODEL_ENUMERATION.md) now explicitly
forward the original arguments through the object/list/part callback chain.
The optional [model-data comparison](docs/MODEL_MAPPING.md) checks the complete
guarded MOM copy through original pointer mapping, primitive batching and
destruction against independently predicted bytes. It extends the existing
ownership histories without adding C bytes or accepting whole encounters.
The optional [model-object comparison](docs/MODEL_OBJECTS.md) also checks every
allocated model payload at the original factory return, including retained
allocator residue. The [actor-object comparison](docs/ACTOR_OBJECTS.md) checks
every live pool allocation at actor-factory return, after the original
first-frame commands. Later playback and natural encounters remain open.
The [collision query interface](docs/COLLISION_API.md) now declares the original
pointer roles and output sizes. A compiled C caller passes 12,696 bounded inputs;
the complete matching executable and source-recovery counts are unchanged.
The matching game can be launched with the [play helper](docs/PLAYING.md),
which verifies local inputs and creates an isolated emulator profile.
The [NPC state and cycle checks](docs/STATE_CYCLE_SCRIPTS.md) extend the scripted
suite to 278,115 fixtures across 26 callbacks. All 122,518 earlier inputs remain.
The suite detects 37 faults and observes every altered instruction executing.
The earlier [periodic NPC checks](docs/PERIODIC_SCRIPTS.md),
[Hoop Girl](docs/HOOP_SCRIPTS.md) and
[Bell Striker and Opera Singer](docs/BELL_OPERA_SCRIPTS.md) checkpoints retain
their original evidence within this suite. Whole encounters remain open.
The [populated actor child checks](docs/ACTOR_CHILD_FLAGS.md) extend Fox's
downstream flag path through the real scene-node and bit-setter methods.
They verify 16,512 case inputs without output stubs and correct the actor
virtual declaration while preserving both complete matching builds.
The [actor construction checker](docs/ACTOR_CHILD_CONSTRUCTION.md) now makes
the original child allocator and constructors reproducible from a disc
extraction, with independent complete-buffer comparisons and two memory patterns.
Supplied descriptors and SDK initialization remain explicit fixture boundaries.
The optional [child lifetime profile](docs/ACTOR_CHILD_LIFETIMES.md) follows
those objects through original destruction, repeated cleanup and pool reuse.
The [model/actor factory checker](docs/ACTOR_FACTORY_OWNERSHIP.md) now creates
the real model resources and checks three ownership histories against an
independent allocation/release plan. Its optional
[actor-object profile](docs/ACTOR_OBJECTS.md) checks complete live allocations
at successful constructor return; natural encounters remain open.
The [NPC proximity checks](docs/NPC_PROXIMITY.md) add Bear, Rabbit, Acrobats and
Ship in 10,408 distinct fixtures through 25 original routines. Real distance,
trigger-ratio, RNG, movement, event and GTE dependencies execute with no output
stubs. Natural encounters and whole-callback acceptance remain open.
The [periodic spatial checks](docs/NPC_PERIODIC_SPATIAL.md) add Minotaur and
Giant Minotaur and replace Bird's trigger-ratio output contract with the real
method. All 2,628 distinct initialized inputs pass through original movement
and native GTE code. These are bounded profiles; no whole encounter is accepted.
The [Gunman checks](docs/GUNMAN_SCRIPTS.md) add 36,338 fixtures for the two
Gunman callbacks and 15 scheduled script histories. Actual effect activation,
color arithmetic, RNG and callback clearing execute under declared allocation,
attachment, geometry and sound contracts; whole encounters remain open.
The [locomotive checks](docs/LOCOMOTIVE_SCRIPTS.md) add the Factory, Kyoto and
Natural callbacks in 70,345 distinct fixtures and 14 scheduled histories.
Original RNG, mood/color calculation, animation flags and callback resets
execute under explicit geometry, notification and sound contracts. All three
callbacks already had matching C bodies; this extends behavior evidence.
The [expanded source-layout audit](docs/SOURCE_LAYOUT_EXPANDED.md) corrects the
earlier selected five-function scan. It identifies 28 unused-storage functions
and withdraws four promotions that added padding. Their readable padding-free
candidates remain historical research. The later
[generation lookup recovery](docs/GENERATION_LOOKUP_RECOVERY.md) replaces the
entry scanner and structure updater with matching C, adding 580 recovered bytes.
The [menu lookup recovery](docs/MENU_LOOKUP_RECOVERY.md) adds another 1,052
matching C bytes and resolves all four withdrawn source functions through
consumed method lifetimes. The later
[callback storage recovery](docs/CALLBACK_STORAGE_RECOVERY.md) removes five
inherited unused arrays while retaining every original instruction. The
[constructor and actor recovery](docs/CONSTRUCTOR_ACTOR_STORAGE.md) explains
two more. The [accessor recovery](docs/ACCESSOR_STORAGE_RECOVERY.md) explains
another three. Fourteen identified inherited source explanations and five
assembly functions remained at that checkpoint. The
[input storage recovery](docs/INPUT_STORAGE_RECOVERY.md) explains six more,
leaving eight identified source explanations at that checkpoint. The
[text and render callback recovery](docs/TEXT_CALLBACK_STORAGE.md) explains
two further functions, leaving six identified explanations at that checkpoint.
The [atlas and tile-buffer recovery](docs/ATLAS_TILE_STORAGE.md) explains four
more, leaving two identified storage explanations at that checkpoint. The
[matching grid-window recovery](docs/GRID_MATCHING_C.md) now replaces another
660 bytes of assembly with C, leaving four assembly functions. Ordinary and
fresh 306-object builds reproduce the complete original executable.
The later [sprite-scale and bounds recovery](docs/UI_SCALE_BOUNDS_MATCHING_C.md)
adds 668 matching C bytes from reviewed, attributed source. Both functions and
the combined ordinary/fresh builds match the original executable, leaving two
game assembly functions. The original compiler and assembler are unchanged.
C-byte coverage does not certify original source quality or whole-game parity.
The [overlap result-lifetime study](docs/OVERLAP_RESULT_LIFETIMES.md) reduces
that unaccepted candidate's complete-image difference to 148 bytes and checks
it through native collision/GTE dependencies. Its assembly fallback remains.
The [render query record cleanup](docs/RENDER_QUERY_RECORD.md) removes a
separately identified redundant buffer tail. Actual compiler traces explain
its allocation, and the complete executable remains identical; the counts
above are unchanged.
The [bounds research comparison](docs/BOUNDS_NARROW_COMPARISON.md) publishes
the retained 19-byte candidate and a confined native checker. It improves the
research starting point while the matching game retains its assembly fallback.
The [generation structure checks](docs/GENERATION_STRUCTURES.md) execute eleven
original routines and compare 1,116 fixtures per original/candidate image,
including virtual dispatch, position updates and mode 3 sprite RNG/scaling.
That earlier padding-free candidate agreed on the fixtures and failed the exact
source gate. The later matching lookup recovery closes this source gate while
whole-feature acceptance and NPC callback coverage remain unchanged.
The later [generation effect checks](docs/GENERATION_EFFECTS.md) extend mode 0
through all eight rate variants and four active child layouts, using fifteen
original routines, 3,116 fixtures and 40 consecutive-update histories per image.
Its nine faults are detected with measured changed-instruction execution.
The [generation entry checks](docs/GENERATION_ENTRIES.md) recover the actual
ten-byte transform packet and check all 56 original entry records through the
scanner and real coordinate conversion in 4,116 fixtures per image. The earlier
[entry method-return candidate](docs/GENERATION_ENTRY_METHOD.md) reduced the
complete image's differences from twenty to six bytes. The matching lookup
recovery now resolves the frame, store and call-register differences; natural
spawning, lifetimes and whole-feature acceptance remain open.
The [overlap source recovery](docs/OVERLAP_RECOVERY.md) checks a two-point,
twelve-byte collision candidate in 6,912 native graph pairs with matching caller
buffers and ordered GTE results. Its frame and 170 code differences still need
recovery; the canonical game retains assembly and the completion counts remain
unchanged.
The [save-title recovery](docs/SAVE_LABEL.md) documents an earlier matching C
promotion, its native checks and the correction to SDK/game classification.
The [SDK and sound API audit](docs/SDK_SIGNATURE_AUDIT.md) documents corrected
volume-function names and an external signature workflow with explicit ambiguity.
The [render-context bounds checks](docs/RENDER_BOUNDS.md) recover the smallest
remaining assembly function's bounded behavior; its C candidate still needs
an exact code match.
The [bounds source recipe](research/render_bounds/README.md) reproduces the
current 21-byte-different candidate and its explicitly failed matching gate.
The [stream exclusion recovery](docs/STREAM_EXCLUSION.md) puts the original
twelve-byte bounds record in matching C and corrects its typed setter. The
actual cached-position and row-selection path passes 9,252 constructed fixtures
through ten original routines without output stubs. C function coverage and
whole-feature acceptance remain unchanged.
The [render-position query interfaces](docs/RENDER_QUERY_API.md) now share the
44-byte result record and declare the original pointer arguments and return
values. Compiler allocation traces explain another redundant buffer tail;
regular and fresh clean builds preserve the complete original executable.
The [glyph region cleanup](docs/GLYPH_REGIONS.md) replaces two oversized byte
buffers with their twelve-byte source region. Compiler observations explain
the original allocation; C coverage and the 24 unresolved storage functions
remain unchanged.
The [glyph character interface](docs/GLYPH_CHARACTER_API.md) corrects the
virtual getter's unsigned-byte return and both character-method receivers.
Compiled C callers pass 4,656 native checks through the original methods;
regular and fresh clean builds retain the complete canonical executable.
The [save workflow checks](docs/CARD_SAVE.md) exercise the original writer,
retry wrapper and native string helpers; physical card I/O and the writer's
exact C recovery remained open at that checkpoint.
The later [matching writer recovery](docs/CARD_WRITER_RECOVERY.md) promotes
the complete 960-byte writer to C, with standard and clean builds matching
the original. Both card groups now have every listed core function in C;
physical I/O and whole-feature acceptance remain open.
The [persisted-card round trip](docs/CARD_ROUNDTRIP.md) compares an ordinary
day-two save and a cold-boot load, including complete card files and restoration
of the 1,792-byte native save buffer. The replay tools preserve isolated QA
profiles; source recovery and the remaining card/error routes stay separate.
The [empty-card Load investigation](docs/EMPTY_CARD_LOAD.md) identifies the
native not-found dialog and names its operation/state fields in matching C.
Recorded game buffers agree; eight differing core-state bytes keep its full
runtime comparison open. The [native accessor checks](docs/NYMASHOCK_STATE.md#empty-card-extension-and-native-accessors)
locate these bytes in the emulator's unused media-label storage and execute
the bundled string methods. Raw state comparisons remain unchanged.
The [card cleanup audit](docs/CARD_CLEANUP.md) checks 501 original/candidate
fixture pairs with an explicit allocator stub. It verifies dynamic reloads
and release order while retaining the eight-byte source-layout mismatch.
The later [native heap composition](docs/CARD_HEAP.md) runs the real allocator
and lock helpers with zero output stubs, checking 96 allocator sequences and
180 cleanup layouts per image. The source-layout mismatch remains unresolved.
The [rendering grid-window checks](docs/RENDER_GRID.md) verify every angle word
and bounded scalar grid/clamp rules; complete matching C remains unresolved.
The [grid and streaming composition](docs/RENDER_STREAM.md) checks 45,408 cases
through the original builder, row splitter and object selector; three position
and GTE contracts remain.
The later [world-position composition](docs/RENDER_POSITION.md) executes the
original lookup chain with zero stubs and integrates it into nine-function
grid/stream checks. Two GTE contracts remain; scene and timing acceptance are
still open.
The later [original SDK rotation audit](docs/RENDER_ROTATION.md) executes
`RotMatrix` with its canonical table, reducing the ten-function composition
to one `ApplyMatrixLV` hardware contract. Actual GTE and scene acceptance
remained open at that checkpoint. The subsequent [native GTE audit](docs/RENDER_GTE.md)
executes the original matrix helper with checked Nymashock commands in 109,501
distinct fixtures and composes eleven original functions in 13,230 cases
without function-output stubs. Its explicit COP2 transfer adapter leaves
full PS1 CPU timing, natural scenes and whole-feature acceptance open.
The [collision audit](docs/COLLISION.md) executes the original primitive and
transform routines through their actual dependencies, with 12,696 primitive
cases and 6,912 composed graphs. It verifies native cross-product, square and
square-root behavior, preserves contact-height and expanded-bounds quirks, and
detects three faults. Both remaining collision functions still need matching C.
The later [collision recovery research](research/collision/README.md) publishes
an unaccepted primitive C fragment whose complete build differs in 22 bytes,
down from 103. Paired native checks and non-NULL midpoint checks pass; those
results add bounded evidence without accepting either remaining C function.
The [fraction and reload study](docs/COLLISION_FRACTIONS.md) makes the candidate's
fraction operands useful without changing its executable and locates its seven
reload allocations after the main workspace. Fourteen complete-unit source
comparisons leave the original bounds lifetime unresolved.
The [compiler-layout diagnostic](docs/COMPILER_LAYOUT.md) observes actual GCC
allocator calls and verifies that tracing preserves complete assembly output;
the primitive's bounds-storage lifetime still needs recovery.
The later [compiler-lifetime investigation](docs/COMPILER_LIFETIMES.md) measures
why an address-taken local survives a nested block and verifies reuse after an
inline helper returns. The native early storage region remains unexplained;
69 additional source forms produce no exact match.
The [register-allocation tracer](docs/COMPILER_ALLOCATION.md) records actual
local/global compiler decisions, verifies priority comparisons and preserves
complete assembly output. It extends candidate analysis without accepting a
nonmatching source form or changing original gameplay.
The [inline-call diagnostic](docs/COMPILER_INLINE_TYPES.md) identifies the
bundled compiler's aggregate type-identity rejection and includes a standalone
reproducer. Normal and observed complete assembly must agree; C recovery and
gameplay acceptance counts remain unchanged.
The [matching grid-window source](docs/GRID_MATCHING_C.md) now reproduces all
660 original function bytes, including its 152-byte frame. The signed angle
test, unsigned normalization and consumed inclusive-endpoint operand resolve
the earlier scheduling and reload differences. The
[grid research sources](research/render_grid/README.md) retain the historical
eight-byte edge and seven-byte cell-reuse candidates. The
[cell-ownership study](docs/GRID_CELL_OWNERSHIP.md) repeats 74,832 scalar pairs
and detects ten faults; both source forms remain outside the matching game.
The [native candidate comparison](docs/GRID_NATIVE_COMPOSITION.md) extends
those source forms through actual lookup, SDK/GTE and streaming dependencies
in 24,780 distinct graph inputs per image, with zero function-output stubs.
Those comparisons remain bounded evidence; natural-scene acceptance remains open.
The [grid phase comparison](docs/GRID_PHASES.md) locates the height-copy order
change in the first scheduling pass, rechecks two complete builds and rules out
133 further source forms. Its reusable phase reader retains the exact source
gate and adds no whole-feature acceptance. The later edge-lifetime study
explains the allocation change and checks the improved C image against all
74,832 existing scalar fixtures per image, retaining four dependency contracts.
The [compiler memory-store investigation](docs/COMPILER_MEMORY_STORES.md)
observes why a consumed math work pair retains two extra stores, checks 50
further source forms and compares three isolated frontend controls. Its
reusable tracer preserves complete assembly; exact source recovery remains open.
The [menu layout checks](docs/MENU_LAYOUT.md) compare 864 constructed histories
per original and three candidate images through 39 original methods, including
glyphs, graphics effects, parent lists and the allocator. Two callback declaration
corrections preserve standard and fresh clean builds; both menu callers still
need matching C and natural screen/input/render evidence.
The [sprite scaling audit](docs/UI_SCALE.md) checks 203,472 native cases,
including overlapping inputs and incoming-register quirks. Its full C
candidate still differs in 12 executable bytes and remains unaccepted. The
[public source recipe](research/ui_scale/README.md) reproduces that comparison
and the actual reload allocations behind its stack frame.
The [level-model loader audit](docs/LBD_PIPELINE.md) checks 418 local level
files through native construction and destruction, including repeated loads.
The later [matching loader recovery](docs/LBD_RECOVERY.md) promotes its 600-byte
function to C, with complete standard and clean builds matching the original.
The [Japanese disc verification](docs/JAPANESE_EDITION.md) compares both asset
editions and corrects two checksum words to reproduce the complete Japanese
disc byte for byte. Its replay evidence is recorded separately. The later
[Nymashock state diagnosis](docs/NYMASHOCK_STATE.md) identifies the eight varying
cold-boot bytes as unused media-label storage, while retaining every strict
byte difference and the remaining gameplay acceptance requirements.

The [Japanese movement and controller-poll evidence](docs/MOVEMENT_PARITY.md)
adds 9,000 paired emulator frames, with observed original controls and native
pad press/hold/release fields. It corrects the replay's running binding and
tap duration while preserving the canonical game and whole-feature gates.

## Three separate workflows

| Workflow | Purpose | Entry points |
| --- | --- | --- |
| Original game | Recover the existing game, including its original scripted NPC behavior, without changing the canonical executable. | `src/`, `ninja check`, [native NPC audit](docs/NATIVE_AI.md) |
| Analysis and AI-assisted development | Export verified context, inspect assets and dispatch tables, test C candidates and compare recorded emulator runs. The supplied tools make no model API calls. | `tools/decomp_workbench.py`, [tool assessment](docs/TOOL_ASSESSMENT.md) |
| Optional gameplay mods | Produce separate patched executables and discs for longer timers, endless timers or a passive Gray Man. | `tools/mod_executable.py`, [optional mods](docs/OPTIONAL_MODS.md) |

The analysis tools and optional mods do not count as recovered original-game
features. There are no added generative-AI NPCs in the matching game.

The [additional original NPC checks](docs/SCRIPTED_EXTENSION.md) cover the
fish's full 24,000-tick joint command cycle, elephant scale requests and
airship RNG/link/child decisions. That profile's bounded comparisons cover 16 of
107 callbacks; natural encounters and whole-feature acceptance remain open.
The [spatial composition](docs/NPC_SPATIAL.md) executes original transform,
axis/world, SDK rotation and GTE dependencies for seven of those callbacks in
26,194 additional composition fixtures. It retains one trigger-ratio contract.

## Build the matching executable

Use x86-64 Linux or WSL2, Python 3.10 or newer, and Git. The bundled legacy
compiler requires Linux's 32-bit compatibility libraries. On Ubuntu/Debian:

```bash
git clone https://github.com/BaileyPillon/lsd-dream-emulator-decompilation.git
cd lsd-dream-emulator-decompilation

sudo apt update
sudo apt install python3 python3-venv python3-pip git build-essential \
  gcc-mipsel-linux-gnu binutils-mipsel-linux-gnu libc6-i386
python3 -m venv .venv
source .venv/bin/activate
python configure.py setup
```

Setup installs the pinned Python build dependencies and checks out MASPSX at
the revision recorded in `configure.py`. An existing MASPSX checkout is
preserved.

Copy `SLPS_015.56` from your own game disc into `rom/SLPS_015.56`, or extract it
from a local BIN/CUE/ISO:

```bash
python tools/extract_executable.py "/path/to/LSD.cue"
python configure.py doctor
python configure.py
ninja check
python tools/progress.py
```

The extractor verifies the input and refuses to replace a different existing
file. `ninja check` builds `build/SLPS015.56` and checks its canonical SHA-1:

```text
76322eeade5ebb22dca57fdeac7d68c30f06308d
```

The original executable is 505,856 bytes. Its SHA-256 is
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.
Paths containing spaces are supported. `ninja clean` preserves handwritten
assembly in `src/`.

On Windows, complete setup inside your WSL distribution, then use PowerShell:

```powershell
.\tools\build.ps1 -Distro Ubuntu
.\tools\build.ps1 -Distro Ubuntu -Action doctor
.\tools\build.ps1 -Distro Ubuntu -Action progress
```

Replace `Ubuntu` with the name shown by `wsl --list --quiet`. Analysis and
emulator launchers require explicit paths to your own tools and inputs; see
[local tools](docs/LOCAL_TOOLS.md).

## Contribute without game assets

The tooling tests use synthetic fixtures and need no game files or MIPS
toolchain:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Linux and Windows. The public CI suite checks
tooling behavior; the proprietary-input matching build is verified locally.
For C recovery, use the exact-match workflow in [CONTRIBUTING.md](CONTRIBUTING.md).
For bugs and research findings, use the repository's issue templates.

## Documentation

- [Roadmap and remaining work](docs/ROADMAP.md)
- [Play the matching game](docs/PLAYING.md)
- [Model enumeration and callback interfaces](docs/MODEL_ENUMERATION.md)
- [Feature inventory and before/after measurements](docs/FEATURE_INVENTORY.md)
- [Original NPC behavior](docs/NATIVE_AI.md), [native dispatch](docs/NATIVE_DISPATCH.md) and [animation structures](docs/NATIVE_ANIMATIONS.md)
- [Nine additional original scripted callback checks](docs/SCRIPTED_AI.md)
- [Factory, Kyoto and Natural locomotive checks](docs/LOCOMOTIVE_SCRIPTS.md)
- [Asset inventory](docs/ASSET_INVENTORY.md) and [runtime comparison](docs/RUNTIME_COMPARISON.md)
- [Saved-state replay boundary and synchronous capture](docs/STATE_REPLAY_BOUNDARY.md)
- [Optional exploration mods](docs/OPTIONAL_MODS.md)
- [Local tool setup](docs/LOCAL_TOOLS.md), [tool applicability](docs/TOOL_ASSESSMENT.md) and [provenance](docs/PROVENANCE.md)

## Credits and licensing

The upstream decompilation is by [cawfee](https://github.com/cawfee).
[FirecatFG/lsddecomp](https://github.com/FirecatFG/lsddecomp) identified the
original toolchain and provided initial segments. Thanks also to the PS1
decompilation community and the authors of splat, spimdisasm, MASPSX and the
other tools documented here.

The upstream project has no repository-wide license file. This continuation
does not assign a blanket license to inherited game or SDK code. Existing
third-party notices are preserved; see [NOTICES.md](NOTICES.md).

This is an independent research project, unaffiliated with Asmik Ace,
OutSide Directors Company, Osamu Sato or Sony.
