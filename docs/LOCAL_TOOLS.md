# Local analysis and emulator setup

The matching build and synthetic-fixture tests do not require Ghidra, an MCP
server or an emulator. Install these tools separately when doing native analysis
or runtime comparison. All launcher paths are explicit; no personal drive
layout or network model service is assumed.

## Original movie content and routing

After a current canonical build, `tools/inventory_movies.py` reads a local
mixed-sector extraction and checks complete movie frames against original
path/threshold tables. With `requirements-analysis.txt` installed,
`tools/verify_movie_paths.py` executes the original helpers and RNG in bounded
MIPS fixtures. The [movie audit](MOVIE_INVENTORY.md#repeat-the-checks) gives
commands, exact scope, and remaining decoded-playback requirements. Both tools
require new private output paths, preserve original inputs, and make no model
API calls.

For actual startup playback, `tools/capture_movie_playback.py` runs an owned
pair with isolated SaveRAM and per-frame full GPU hashes.
`tools/compare_movie_playback.py` checks the complete trace, neutral controls,
checkpoint state and finalized PCM. The [startup movie guide](MOVIE_PLAYBACK.md)
gives the exact commands and separates setup words, accepted-frame counters,
complete observed lifetimes, and partial repeats.

## Windows build helper

For interactive play, use the Python [matching-game launcher](PLAYING.md).
It can invoke the WSL build directly, including on Windows installations where
PowerShell script files are disabled.

Set up the Linux toolchain inside your WSL distribution using the README.
Pass its exact name, for example:

```powershell
.\tools\build.ps1 -Distro Ubuntu -Action check
```

The helper uses the repository's `.venv`, or the optional prepared environment
`/opt/lsd-decomp-venv`, if present.

## Complete candidate functions

The [source-interface and diagnostic guide](SOURCE_INTERFACE_DIAGNOSTICS.md)
explains the workbench's optional `check --function` comparison. It uses real
ELF function boundaries only after a symbol-bearing diagnostic link reproduces
the complete candidate executable. The original whole-image gate and exit
status remain authoritative; detailed instruction evidence stays private.

## Native save workflow

After building the canonical executable, install the optional analysis
dependencies in that Linux/WSL Python environment:

```bash
python -m pip install -r requirements-analysis.txt
python tools/verify_card_save.py --output .decomp-lab/card-save-native-new.json
```

The [save workflow audit](CARD_SAVE.md) explains the fixtures, seven explicit
file/allocation/diagnostic contracts and remaining physical-card gates.
Reports require a new private path. This analysis tool does not modify the
game or call a model API.

## Native rendering grid window

After building the canonical executable and installing
`requirements-analysis.txt` in the same Linux/WSL environment:

```bash
python tools/verify_render_grid.py --output .decomp-lab/render-grid-native-new.json
```

The [grid-window audit](RENDER_GRID.md) describes the scalar fixtures, four
external contracts and exact C/renderer gates. Reports require a new private
path. The tool does not modify the game or call a model API.

## Native rendering grid and streaming composition

After the same canonical build and analysis dependency setup:

```bash
python tools/verify_render_stream.py --output .decomp-lab/render-stream-native-new.json
```

The [streaming composition audit](RENDER_STREAM.md) executes the original grid
builder, row splitter and slot selector alongside the window helper. Three
position/GTE contracts remain. Reports require a new private path; the tool
does not modify the game or call a model API.

## Ghidra MCP

Import the verified analysis ELF into a Ghidra project named `lsd-original`
under your chosen analysis root's `projects` directory, with program path
`/original-symbols.elf`. Use `MIPS:LE:32:default` and LSD's GP value
`0x8008A808`. The existing recorded analysis used Ghidra 12.1.4 and the
GhidraMCP 7.0.0 server; other versions need their own validation.

```powershell
.\tools\start_analysis.ps1 `
  -AnalysisRoot 'C:\LSD-Research' `
  -GhidraRoot 'C:\Tools\ghidra' `
  -JavaRoot 'C:\Tools\jdk21' `
  -ServerJar 'C:\Tools\ghidra-mcp\GhidraMCP-7.0.0.jar'
```

The launcher uses a dedicated analysis profile and binds to localhost on port
8101. It rejects an occupied port and preserves existing services. It does not
install an MCP connection into your editor or invoke an AI model.

## BizHawk runtime comparison

The recorded workflow used BizHawk 2.11.1. Supply its installation directory,
your game CUE, all required regional BIOS files and a fresh output directory:

```powershell
.\tools\start_runtime_qa.ps1 `
  -EmulatorRoot 'C:\Tools\BizHawk' `
  -BiosRoot 'C:\Private\PSX-BIOS' `
  -Cue 'C:\Private\LSD\original.cue' `
  -Output '.decomp-lab\qa-boot-new' `
  -Scenario boot -Frames 1800
```

Supply BIOS files named `scph5500.bin`, `scph5501.BIN` and `scph5502.BIN`.
Replay comparisons require the same assets, emulator/core, BIOS, settings,
script and starting state on both sides. See [RUNTIME_COMPARISON.md](RUNTIME_COMPARISON.md)
for paired runs and audio capture.

## Nymashock saved-state diagnosis

Use Python 3.14, or install `requirements-analysis.txt` for its Zstandard
decoder on earlier supported Python versions. The diagnostic reads existing
private states from the checked Windows BizHawk 2.11.1 Nymashock core:

```bash
python tools/inspect_nymashock_state.py \
  --original /private/original/frame-1800.State \
  --rebuilt /private/repeated/frame-1800.State \
  --core /private/BizHawk/dll/shock.wbx.zst \
  --output .decomp-lab/nymashock-state-new.json
```

The [native field diagnosis](NYMASHOCK_STATE.md) describes its fixed binary
profile and limitations. Reports require a new output path and retain complete
decoded differences alongside their classification. No state bytes are masked,
and the tool does not modify inputs, launch an emulator or call a model API.

## Native world-position and streaming composition

After a canonical build and installation of `requirements-analysis.txt` in
your Linux/WSL environment:

```bash
python tools/verify_render_position.py \
  --output .decomp-lab/render-position-native-new.json
```

The [position audit](RENDER_POSITION.md) executes original lookup functions
without stubs and the complete grid/stream composition with two GTE contracts.
It checks guarded buffers, native call traces, deliberate faults and zero-
divisor exceptions. Reports require a new private path. Changes are confined
to the tool's own Unicorn memory; it does not modify the game or call a model API.

## Original SDK rotation and streaming composition

After a canonical build and installation of `requirements-analysis.txt` in
your Linux/WSL environment:

```bash
python tools/verify_render_rotation.py \
  --output .decomp-lab/render-rotation-native-new.json
```

The [rotation audit](RENDER_ROTATION.md) executes the original `RotMatrix`
without stubs and composes it with lookup, grid generation and streaming.
Only the `ApplyMatrixLV` hardware contract remains. The tool verifies the
canonical table locally, checks guarded overlaps and reports distinct inputs
separately from runs. It changes only its own Unicorn memory and requires a
new private report path; it makes no model API calls.

## Original matrix application through native Nymashock GTE

The [native GTE audit](RENDER_GTE.md) supplies a headless C# bridge, an explicit
COP2 transfer adapter and a verifier for original `ApplyMatrixLV` and the
eleven-function world-to-stream chain. Compile the bridge with
`tools/build_nymashock_gte_bridge.ps1`, supplying your local BizHawk 2.11.1
directory, installed `netstandard.dll` reference facade and a new private
output. Then run `tools/verify_render_gte.py` in WSL with the bridge path,
Windows runtime path and a new private report path. The audit document gives
the complete commands and exact supported binary profile.

The bridge checks core/library hashes and native function mappings before
executing MVMVA. It mounts its own Waterbox host and needs no game or BIOS;
the MIPS verifier requires a current matching game build. Detailed command
logs and binaries remain private. This validates bounded native arithmetic
and composition, with PS1 CPU timing and natural scene acceptance separate.

## Original collision through native GTE dependencies

The same checked bridge now supports the original OP/SQR command words and
native LZCS writes used by the collision SDK helpers. The
[collision audit](COLLISION.md) supplies `tools/verify_collision.py` and a
metadata-only range manifest. It exercises the original primitive and transform
paths, guarded buffers, contact-height filtering and shared bounds access.
Use a new private report and a newly compiled bridge. Full PS1 CPU timing,
unsupported primitive inputs, natural encounters and whole-feature acceptance
remain separate requirements.
