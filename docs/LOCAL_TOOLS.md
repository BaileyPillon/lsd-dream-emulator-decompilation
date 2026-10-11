# Local analysis and emulator setup

The matching build and synthetic-fixture tests do not require Ghidra, an MCP
server or an emulator. Install these tools separately when doing native analysis
or runtime comparison. All launcher paths are explicit; no personal drive
layout or network model service is assumed.

## Windows build helper

Set up the Linux toolchain inside your WSL distribution using the README.
Pass its exact name, for example:

```powershell
.\tools\build.ps1 -Distro Ubuntu -Action check
```

The helper uses the repository's `.venv`, or the optional prepared environment
`/opt/lsd-decomp-venv`, if present.

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
