# Recorded window-link scenario

[observe.lua](observe.lua) is the exact Lua script executed in the
[natural window-link comparison](../../docs/NATURAL_WINDOW_LINK.md). It uses
controller input and read-only MainRAM inspection in BizHawk 2.11.1/Nymashock.
It never writes game RAM. This directory is research, outside the matching
game build and recovered-C count.

The historical executed script is preserved unchanged. Its Lua
`is_boolean and false or value` expression can retain an initially held
Boolean, and its policy log is not a complete submitted-input record. Its
recorded output comparisons remain valid within that capture scope. For new
controller harnesses, follow the explicit neutralization and complete logging
in the [new NPC recorder](../npc_encounter/README.md); that recorder has its own
Hoop Girl starting-state requirements and is not a drop-in window scenario.

## Required local inputs

- The supported Japanese game content, canonical executable, and local BIOS.
- The pinned BizHawk 2.11.1 runtime/core files recorded in the comparison metadata.
- A 1,327,679-byte starting save state with SHA-256
  `1c8d29944fa9422c88ec28e453542dcdaccfb6b934eee9a9f8926c5c26319c34`.
- A new, isolated QA output directory and dedicated save/configuration paths.

The original state is not distributed. It comes from the recorded Japanese
play run, already inside map key 3. The script expects the existing window
record at physical RAM address `0x001C690C`, entity ID 75. A different save or
edition is not an equivalent reproduction, even if the executable matches.

The existing [runtime QA helper](../../tools/start_runtime_qa.ps1) accepts a
custom `-Script`, `-LoadState`, `-Scenario play`, and `-Frames 2400`. Run QA in a
dedicated emulator copy and keep its save paths separate from ordinary play.
The recorded pair used a private Python launcher with explicit isolated paths;
the public PowerShell helper was not used for this pair. Do not change system
execution policy to run it. [PLAYING.md](../../docs/PLAYING.md) provides the
ordinary Python game launcher.

## Outputs and checks

The environment variables `LSD_QA_OUTPUT` and `LSD_QA_FRAMES` select the new
directory and frame limit. The recorded limit is 2,400. Outputs include
`controls.tsv`, `scene.tsv`, `npc.tsv`, capability information, five full-RAM/
image/state checkpoints, and a completion marker. Raw outputs stay private.

The observer scans aligned entity-vtable matches and records matching dream
and entity IDs. An address match alone does not prove a live actor. Registered
window samples additionally require the correct context state, owner and
original-table callback; their advancing ticks are recorded separately.

The controller requests inputs based on the current player/window positions.
For a comparison, both runs must produce identical requested-input logs;
using the same adaptive policy alone is insufficient. Input manifests must
also revalidate all content, runtime, configuration, script and state identities.
The retained private comparison checks these identities, every log byte,
five complete MainRAM images, PNG bytes, and every save-state member payload.

No original content is included here. This scenario does not accept a whole
NPC, every link, audio, hardware timing, or full game parity.
