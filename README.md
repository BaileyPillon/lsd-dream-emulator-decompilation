# LSD Recovered

**A matching decompilation of LSD: Dream Emulator for the original PlayStation.**

[![Tooling tests](https://github.com/BaileyPillon/lsd-recovered/actions/workflows/tools.yml/badge.svg)](https://github.com/BaileyPillon/lsd-recovered/actions/workflows/tools.yml)

LSD Recovered reconstructs the 1998 game's native MIPS code in readable C,
with a reproducible build and tools for studying its dream systems, assets
and scripted NPCs. It continues [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled)
and preserves that project's Git history and contributor attribution.

The verified local build reproduces the original Japanese executable byte for
byte. **Full C recovery and independently reviewed gameplay coverage are still
in progress.** The remaining assembly is regenerated from your own executable.
Game discs, executables, extracted assets and PlayStation BIOS files are not
distributed here.

## Current status

The current verified source snapshot is dated October 11, 2026. These are
separate measures, not a whole-game completion percentage. The initial
publication and subsequent evidence are retained separately.

| Measure | Verified snapshot |
| --- | ---: |
| Game function bytes recovered in C | 194,284 / 199,912 (97.18%) |
| Known remaining game assembly functions | 7 |
| Original NPC/behavior callbacks with C bodies | 107 / 107 |
| Provisional behavior/system groups with listed core functions in C | 35 / 40 |
| Entire feature groups independently accepted at runtime | 0 / 40 |

The feature inventory has 40 provisional groups; an official exhaustive
feature total is unknown. SDK and startup code are excluded from the C-byte
denominator. Bounded native and emulator comparisons have passed, including
a 6,000-frame sequence with matching frame, GPU, state and PCM audio output.
Their scope and remaining gaps are documented in the
[feature inventory](docs/FEATURE_INVENTORY.md) and [roadmap](docs/ROADMAP.md).
The [save-title recovery](docs/SAVE_LABEL.md) documents the latest matching C
promotion, its native checks and the correction to SDK/game classification.
The [SDK and sound API audit](docs/SDK_SIGNATURE_AUDIT.md) documents corrected
volume-function names and an external signature workflow with explicit ambiguity.
The [render-context bounds checks](docs/RENDER_BOUNDS.md) recover the smallest
remaining assembly function's bounded behavior; its C candidate still needs
an exact code match.
The [save workflow checks](docs/CARD_SAVE.md) exercise the original writer,
retry wrapper and native string helpers; physical card I/O and the writer's
exact C recovery remain open.

## Three separate workflows

| Workflow | Purpose | Entry points |
| --- | --- | --- |
| Original game | Recover the existing game, including its original scripted NPC behavior, without changing the canonical executable. | `src/`, `ninja check`, [native NPC audit](docs/NATIVE_AI.md) |
| Analysis and AI-assisted development | Export verified context, inspect assets and dispatch tables, test C candidates and compare recorded emulator runs. The supplied tools make no model API calls. | `tools/decomp_workbench.py`, [tool assessment](docs/TOOL_ASSESSMENT.md) |
| Optional gameplay mods | Produce separate patched executables and discs for longer timers, endless timers or a passive Gray Man. | `tools/mod_executable.py`, [optional mods](docs/OPTIONAL_MODS.md) |

The analysis tools and optional mods do not count as recovered original-game
features. There are no added generative-AI NPCs in the matching game.

## Build the matching executable

Use x86-64 Linux or WSL2, Python 3.10 or newer, and Git. The bundled legacy
compiler requires Linux's 32-bit compatibility libraries. On Ubuntu/Debian:

```bash
git clone https://github.com/BaileyPillon/lsd-recovered.git
cd lsd-recovered

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
