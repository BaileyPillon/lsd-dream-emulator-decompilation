# LSD: Dream Emulator Decompilation

**A matching decompilation of LSD: Dream Emulator for the original PlayStation.**

[![Tooling tests](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/actions/workflows/tools.yml/badge.svg)](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/actions/workflows/tools.yml)

This project reconstructs the 1998 game's native MIPS code in readable C,
with a reproducible build and tools for studying its dream systems, assets
and scripted NPCs. It continues [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled)
and preserves that project's Git history and contributor attribution.

The verified local build reproduces the original Japanese executable byte for
byte. **Full C recovery and independently reviewed gameplay coverage are still
in progress.** The remaining assembly is regenerated from your own executable.
Game discs, executables, extracted assets and PlayStation BIOS files are not
distributed here.

## Current status

The current verified source snapshot is dated October 12, 2026. These are
separate measures, not a whole-game completion percentage. The initial
publication and subsequent evidence are retained separately.

| Measure | Verified snapshot |
| --- | ---: |
| Matching game-function bytes compiled from C | 194,212 / 199,912 (97.15%) |
| Known remaining game assembly functions | 9 |
| Known C functions with unresolved unused local storage | 24 |
| Original NPC/behavior callbacks with C bodies | 107 / 107 |
| Original callbacks with bounded native comparisons | 16 / 107 |
| Provisional behavior/system groups with listed core functions in C | 35 / 40 |
| Entire feature groups independently accepted at runtime | 0 / 40 |

The feature inventory has 40 provisional groups; an official exhaustive
feature total is unknown. SDK and startup code are excluded from the C-byte
denominator. Bounded native and emulator comparisons have passed, including
a 6,000-frame sequence with matching frame, GPU, state and PCM audio output.
Their scope and remaining gaps are documented in the
[feature inventory](docs/FEATURE_INVENTORY.md) and [roadmap](docs/ROADMAP.md).
The [expanded source-layout audit](docs/SOURCE_LAYOUT_EXPANDED.md) corrects the
earlier selected five-function scan. It identifies 28 unused-storage functions
and withdraws four promotions that added padding. Their readable padding-free
candidates remain research; 24 inherited source explanations and nine assembly
functions remain. C-byte coverage does not certify original source quality.
The [generation structure checks](docs/GENERATION_STRUCTURES.md) execute eleven
original routines and compare 1,116 fixtures per original/candidate image,
including virtual dispatch, position updates and mode 3 sprite RNG/scaling.
The padding-free candidate agrees on those fixtures but still fails the exact
source gate. It adds no whole-feature acceptance or new NPC callback coverage.
The later [generation effect checks](docs/GENERATION_EFFECTS.md) extend mode 0
through all eight rate variants and four active child layouts, using fifteen
original routines, 3,116 fixtures and 40 consecutive-update histories per image.
Its nine faults are detected with measured changed-instruction execution.
The [generation entry checks](docs/GENERATION_ENTRIES.md) recover the actual
ten-byte transform packet and check all 56 original entry records through the
scanner and real coordinate conversion in 4,116 fixtures per image. The
readable C candidate agrees on those fixtures but retains its source gate.
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
The [save workflow checks](docs/CARD_SAVE.md) exercise the original writer,
retry wrapper and native string helpers; physical card I/O and the writer's
exact C recovery remained open at that checkpoint.
The later [matching writer recovery](docs/CARD_WRITER_RECOVERY.md) promotes
the complete 960-byte writer to C, with standard and clean builds matching
the original. Both card groups now have every listed core function in C;
physical I/O and whole-feature acceptance remain open.
The [card cleanup audit](docs/CARD_CLEANUP.md) checks 501 original/candidate
fixture pairs with an explicit allocator stub. It verifies dynamic reloads
and release order while retaining the eight-byte source-layout mismatch.
The later [native heap composition](docs/CARD_HEAP.md) runs the real allocator
and lock helpers with zero output stubs, checking 96 allocator sequences and
180 cleanup layouts per image. The source-layout mismatch remains unresolved.
The [rendering grid-window checks](docs/RENDER_GRID.md) verify every angle word
and bounded scalar grid/clamp rules; the closest C candidate still has four
byte differences in two stores.
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
The [grid source-recovery fragment](research/render_grid/README.md) now retains
the native body and store order, with eleven differences in three prologue
instructions. Its complete candidate remains outside the matching game.
The [sprite scaling audit](docs/UI_SCALE.md) checks 203,472 native cases,
including overlapping inputs and incoming-register quirks. Its full C
candidate still differs in 12 executable bytes and remains unaccepted.
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
airship RNG/link/child decisions. Current bounded comparisons cover 16 of
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
- [Feature inventory and before/after measurements](docs/FEATURE_INVENTORY.md)
- [Original NPC behavior](docs/NATIVE_AI.md), [native dispatch](docs/NATIVE_DISPATCH.md) and [animation structures](docs/NATIVE_ANIMATIONS.md)
- [Nine additional original scripted callback checks](docs/SCRIPTED_AI.md)
- [Asset inventory](docs/ASSET_INVENTORY.md) and [runtime comparison](docs/RUNTIME_COMPARISON.md)
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
