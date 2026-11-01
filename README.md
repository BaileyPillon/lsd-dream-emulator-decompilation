# LSD: Dream Emulator Decompilation

**A matching C decompilation of the original PlayStation game.**

[![Tooling tests](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/actions/workflows/tools.yml/badge.svg)](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/actions/workflows/tools.yml)

This project reconstructs the 1998 game's native MIPS code in readable C,
with a reproducible build and tools for studying its dream systems, assets
and scripted NPCs. It continues [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled)
and preserves the upstream Git history and contributor attribution.

[Build](#build-the-matching-executable) · [Play](docs/PLAYING.md) ·
[Read the code](docs/SOURCE_GUIDE.md) · [Verification](docs/VERIFICATION_INDEX.md) ·
[Contribute](CONTRIBUTING.md)

## Current status

**All 199,912 counted game-function bytes compile from matching C.** The current
306-object build reproduces the supported Japanese executable byte for byte.
[The matching-C report](docs/MATCHING_GAME_C.md) documents the denominator,
clean-build evidence and compiler-layout compatibility storage.

| Measure | Status |
| --- | --- |
| Matching game-function C | 199,912 / 199,912 bytes (100%) |
| Complete executable match | Canonical Japanese `SLPS_015.56` |
| SDK and startup assembly | Retained; outside the game-C count |
| Whole-game gameplay verification | In progress; [remaining work](docs/ROADMAP.md) |

The source milestone and gameplay acceptance are separate. The executable
retains the original behavior, including original failure paths and quirks;
this project does not silently repair them. Original discs, executables,
extracted assets and PlayStation BIOS files are supplied locally.

The latest [source maintenance pass](docs/SOURCE_MAINTENANCE.md) improves the
readability of game flow, dream sessions, path selection and audio lifecycle
code while retaining the complete executable match.

## Source layout

Implementation and recovered interfaces live together under `src/`. Begin with
[the source guide](docs/SOURCE_GUIDE.md) for call paths, naming conventions and
compiler constraints.

| Directory | Responsibility |
| --- | --- |
| [`src/game`](src/game) | Startup, menus, dream sessions and ending orchestration |
| [`src/dream`](src/dream) | Dream state, days, links, generation and session ownership |
| [`src/scene`](src/scene) | Scene graphs, maps, actors and original NPC callbacks |
| [`src/menu`](src/menu) | Original menus, charts, movie screens and card UI |
| [`src/file`](src/file) | File drivers, buffers, textures, models and streamed media |
| [`src/sound`](src/sound) | Sound banks, sequence playback and SDK integration |
| [`src/base`](src/base) | Object lifetime, notifications, allocation and shared services |
| [`tools`](tools) | Build, import, inspection and comparison commands |
| [`research`](research) | Reproducible subsystem studies and optional observers |
| [`tests`](tests) | Public tooling tests with owned synthetic fixtures |

## Three separate workflows

| Workflow | Purpose |
| --- | --- |
| Original game | Explain and verify the existing game while preserving the canonical executable. |
| Analysis and AI-assisted development | Export verified context, inspect original data and compare candidates or recorded runs. Supplied tools make no model API calls. |
| Optional gameplay mods | Produce explicitly separate patched executables and discs; see [optional mods](docs/OPTIONAL_MODS.md). |

The [Rust/Bevy reconstruction](https://github.com/BaileyPillon/lsd-dream-emulator-bevy)
is maintained in a separate repository with its own implementation, mod API and
acceptance tracker. C recovery percentages do not measure that port's progress.

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

| Task | Start here |
| --- | --- |
| Understand the implementation | [Source guide](docs/SOURCE_GUIDE.md) |
| Refine recovered C | [Contributing](CONTRIBUTING.md), [source maintenance](docs/SOURCE_MAINTENANCE.md) |
| Understand exact-match constraints | [Matching-C milestone](docs/MATCHING_GAME_C.md), [recovered-C context](docs/RECOVERED_C_CONTEXT.md) |
| Inspect verification scope | [Research index](docs/VERIFICATION_INDEX.md), [feature inventory](docs/FEATURE_INVENTORY.md) |
| Compare runtime behavior | [Runtime comparison](docs/RUNTIME_COMPARISON.md), [headless replay](docs/HEADLESS_REPLAY.md) |
| Study original NPCs | [NPC catalogue](docs/NPC_CATALOGUE.md), [native AI](docs/NATIVE_AI.md) |
| Study rendering and media | [Model packet decoding](docs/MODEL_PACKET_DECODING.md), [movie inventory](docs/MOVIE_INVENTORY.md) |
| Find remaining work | [Roadmap](docs/ROADMAP.md), [project objective](PROJECT_OBJECTIVE.md) |

The [research index](docs/VERIFICATION_INDEX.md) retains the detailed evidence
previously included in this overview. Each report distinguishes constructed
component tests, recorded native histories and complete-feature acceptance.

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
