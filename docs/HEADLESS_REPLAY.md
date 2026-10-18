# Headless PS1 replay

Replay a validated cold-start capture through the original BizHawk PS1 core
without opening or controlling EmuHawk. The recorder feeds all 26 recorded
controller values into a fresh core, starting from the BIOS and disc. It
restores no saved state and injects no game RAM. Existing play sessions and
save files remain separate.

This is optional analysis tooling. The matching game continues to use its
original [C/MIPS build](../README.md#build-the-matching-executable). The C# host
provides an isolated frontend for the existing PS1 emulator.

## Verified profiles

The published Python wrapper builds and runs the published C# source against
BizHawk 2.11.1. Both the original and matching Japanese discs pass these
retained controller histories:

| Profile, per disc | Submitted frames | Native/GPU observations | Complete RAM/GPU and RGB checkpoints | Complete GUI PCM window |
| --- | ---: | ---: | ---: | ---: |
| [Cold start into a dream](COLD_START.md) | 6,000 | 6,001 | 16 | 4,422,265 stereo sample frames |
| [First dream through the next-day menu](COLD_DREAM_CYCLE.md) | 30,000 | 30,001 | 61 | 22,113,556 stereo sample frames |

Across the four runs, all **72,004** complete GPU-memory hashes agree with the
GUI recordings. All **154** selected complete 2 MiB RAM buffers, 1 MiB GPU
buffers and RGB images agree. A separate decoder independently checks every
RGB image. Original/rebuilt headless traces, complete PCM files, complete RAM
checkpoints and headless PNG files also agree within each profile pair.

These are two lengths of the same opening controller route. They are not four
independent feature scenarios. The longer route includes the natural dream
limit, chart, next-day menu and recorded movie imagery.

## Image and audio boundaries

The GUI screenshots record display density at 120 DPI; the headless exporter
uses 96 DPI. The retained PNG files differ only in their `pHYs` density chunks.
Their dimensions, RGB pixels and every other PNG chunk agree. Both PNG files
remain available, and the report preserves their byte inequality. Density
metadata is separate from the original PS1 image.

The Lua observer records frame one as relative boundary zero, then advances
6,000 or 30,000 frames. The GUI's `--dump-length` records 6,000 or 30,000 audio
frames. Consequently, headless PCM includes one additional observation frame:
**737 stereo sample frames** in both tested profiles. Its complete PCM files
contain 4,423,002 and 22,114,293 sample frames respectively.

The verifier derives the comparison window from the declared GUI dump length
and recorded per-frame sample counts. It compares the **entire** GUI WAV PCM
payload and retains all headless audio, including that final frame and its
separate hash. A different WAV window is rejected. No emulator state bytes
are masked, and no complete-state comparison is claimed. The earlier
[distributed-core state mismatch](COLD_DREAM_CYCLE.md#exact-comparison) remains
recorded separately.

## Run with your own local capture

Use 64-bit Windows, .NET Framework 4.8, a stable installed .NET SDK 8 or later,
and a completed capture from [the cold-start recorder](COLD_START.md). The
qualified build used SDK 8.0.424. The current adapter requires the recorder's
default Nymashock settings. All Python dependencies are in the standard library.

```powershell
python tools/replay_cold_start_headless.py `
  --capture-folder D:/QA/lsd-cold-start-new/original `
  --workspace D:/QA/lsd-headless-new
```

Select a new workspace outside the reference capture and emulator runtime.
The wrapper revalidates the capture and its pinned disc, BIOS, core,
configuration and observer. It copies the runtime libraries and game database,
builds the owned recorder, and runs only that process. The supplied runtime,
reference files and source hashes are checked again after execution.

`comparison.json` records the result and boundaries. The workspace also retains
the exact source, compiler command/log, process identity and exit code, complete
PCM, every GPU hash, checkpoint RAM/GPU buffers and PNGs. Existing output is
preserved. Game discs, BIOS files, executable images and captures are not
distributed with this repository.

## Controls and remaining work

Four real cold-core controls reject an incorrect RGB pixel, GPU hash, RAM byte
and input frame counter. The counter error is rejected before the second
advance. A fifth offline control rejects altered reference PCM. Only owned
reference copies change; game and emulator instructions remain intact.
Seventeen synthetic tests cover protocol failures and evidence preservation.
The full tooling suite passes 860 tests on Windows and WSL, with two expected
skips on each.

[headless-replay-checks.json](headless-replay-checks.json) pins the executed
sources and private qualification/control reports. [ILSpy](TOOL_ASSESSMENT.md)
was used on the shipped managed adapter to identify its APIs and required
database initialization. It does not decompile the original MIPS game.

Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two remaining
assembly functions and two inherited storage explanations. The provisional
inventory remains 40 groups, 38 with listed core functions in C, 40 of 107
callbacks with bounded native profiles, and zero accepted whole feature groups
or NPC encounters. This replayer collects no callback instruction-entry trace;
natural NPC activation, complete content/branch coverage, complete emulator
states and original hardware timing remain separate gates.
