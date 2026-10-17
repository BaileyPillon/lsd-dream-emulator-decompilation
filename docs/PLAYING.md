# Play the matching build

This repository builds the original PlayStation executable. The matching game
can be played in a PlayStation emulator with your own complete disc and BIOS.
The two remaining assembly functions are included in that executable; their
source recovery is still unfinished. See [the roadmap](ROADMAP.md) for the
remaining C and original-behavior verification work.

## Requirements

- The matching Linux or WSL toolchain described in [the README](../README.md).
- Windows and Python 3.10 or newer for the interactive launcher.
- BizHawk **2.11.1**, with its Nymashock core and runtime files.
- Your own supported game CUE/BIN and Japanese `scph5500.bin` BIOS.
- A new local profile directory for emulator settings, memory cards, and states.

The launcher reads your supplied disc and requires its embedded executable to
equal `build/SLPS015.56`, with the canonical executable hash. It fingerprints
all CUE tracks, the BIOS, and the selected emulator/runtime files. Existing game
files, profiles, and memory cards are preserved.
The executable hash alone does not identify the asset edition. Keep the disc
edition and track hashes with comparison evidence, as described in
[the Japanese-edition audit](JAPANESE_EDITION.md).

## Build and launch on Windows

From the repository root, replace the paths and WSL distribution name:

```powershell
python tools/play_game.py --distro Ubuntu `
  --cue "D:/Games/LSD/LSD.cue" `
  --emulator-root "D:/Tools/BizHawk-2.11.1" `
  --bios-root "D:/Private/PSX-BIOS" `
  --profile "D:/Games/LSD/play-profile-new"
```

The command builds and checks the canonical executable inside WSL, verifies
the supplied disc, creates an isolated profile, and starts BizHawk. It uses
Python directly and requires no change to PowerShell's script execution policy.
Supply a full disc CUE so maps, textures, music, movies, and other content remain
available during play.

The selected disc may be your verified original or a disc created from the
matching build with [the disc packaging tool](../tools/package_disc.py).
Both contain the same executable bytes. The launcher retains input hashes in
`play.json` and each launch's process/log record in a new `session-*` directory.

To prepare the files without opening an emulator, append `--prepare-only`.
To play again using a prepared profile:

```powershell
python tools/play_game.py --resume --profile "D:/Games/LSD/play-profile-new"
```

Resume checks the pinned disc, BIOS, and emulator inputs again. It keeps your
profile's settings and saves. A later source build does not replace the disc
already selected by that profile; prepare a new profile when changing inputs.

## Keyboard controls

| PlayStation input | Keyboard |
| --- | --- |
| Directional pad | Arrow keys |
| Start | Enter |
| Select | Space |
| Circle | X |
| Cross | Z |
| Square / Triangle | A / S |
| L1 / R1 | Q / W |
| L2 / R2 | E / R |

Focus the emulator window to use these bindings. At the title screen, use Start
and Circle to proceed through the original Japanese menu. Xbox-style controller
bindings are also included in the prepared profile.

Sound is enabled at normal speed. Actual output depends on the host audio
device; a configuration flag alone is not a listening test.

## Verification scope

The [runtime comparison guide](RUNTIME_COMPARISON.md) records original/rebuilt
replays with pinned discs, emulator/core, BIOS, configuration, script, and saved
state. Comparisons cover frames, GPU memory, save-state payloads, native movement
fields, and captured PCM where requested. These are bounded scenarios.

A matching executable and a playable session do not finish the C recovery,
exhaustive content inventory, natural NPC encounters, card error cases, or every
other requirement in [the project objective](../PROJECT_OBJECTIVE.md). Original
parity, optional mods, and AI-assisted developer tools retain separate evidence.

A further [natural window-link replay](NATURAL_WINDOW_LINK.md) verifies one
controller-driven activation, transition from map key 3 to 12, and continued
in-game updates in the matching build. Its five RAM/image/state checkpoints
and complete recorded input/NPC/scene logs agree with the original disc.

The [cold-start profile](COLD_START.md) also reaches an unlocked dream through
the title menu without restoring a state, then verifies controller-driven
turning and walking. The published-tool repeat agrees in every recorded output,
including full state-member payloads. An earlier pair's eight unused emulator
label differences remain preserved. This adds no recovered C bytes or
whole-feature acceptance.
