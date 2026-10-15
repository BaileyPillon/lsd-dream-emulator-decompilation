# Natural window activation and link comparison

The original and rebuilt Japanese discs agree on a **2,400-frame in-game
scenario**: approach the naturally loaded window entity, activate its behavior,
follow its link, and wait in the destination map. This is a recorded integration
path. It adds no recovered C bytes or whole-feature acceptance.

## Recorded path

Both runs start from the same existing dream save state. The controller reads
the player's position and heading, then uses ordinary directional and Cross
inputs to approach the window. Its policy requests no further buttons after
behavior starts or the map changes. It writes no game RAM and injects no
entities or assets. See the historical input-recording limitation below.

| Observation | Result in both runs |
| --- | --- |
| Initial map key | 3 |
| Window entity record | 75; `entity_window`, original callback `0x800628D4` |
| First pre-frame observation of registered behavior | Relative frame 698 |
| Registered context samples | Frames 720, 750, 780, 810; ticks 5, 11, 17, 23 |
| Context identity | State 76, owner points to the window, callback matches the original property table |
| First pre-frame observation of destination map | Relative frame 773; map key 12 |
| Transition state | Link state 12, input locked |
| Final state | Map key 12, input unlocked, player at `(-48128, -1024, -7168)` |

The 130-record property table in the starting RAM agrees with all 2,080 bytes
in the canonical executable. Other matching object records include an inactive
Hoop Girl record. Its uninitialized context fields are observations, not a
callback trace or additional accepted NPC behavior.

## Exact comparisons

The input manifests revalidate every disc track, CUE layout, seven emulator/core
files, three regional BIOS files, configuration, Lua script, and starting state.
Their comparison identities are equal. The runs use isolated QA configuration
and save paths, separate from ordinary play profiles.

| Output | Comparison scope |
| --- | --- |
| Controller log | All 2,400 requested-input and pre-frame observation rows |
| Scene log | All 81 rows, sampled every 30 emulator frames |
| Entity log | All 74 rows, including the four registered window-context samples |
| Full MainRAM | All 2,097,152 bytes at frames 0, 600, 1200, 1800, 2400 |
| Screenshots | PNG bytes at those same five checkpoints |
| Save states | Every ZIP member payload at those same five checkpoints |

All comparisons are exact. Save-state ZIP wrapper bytes differ; their member
payloads agree without masking or rewriting core data. Full RAM between the
five checkpoints is not captured. Audio was not requested for this scenario.
The earlier [movement/audio comparison](PLAYING.md) remains separate evidence.

## Research scenario and provenance

The [executed Lua scenario](../research/window_link/observe.lua) is published
byte for byte. It is tied to the recorded warm state and its original window
object; it is not a general navigator or a game launcher. The accompanying
[research guide](../research/window_link/README.md) records the required state
identity and setup boundaries.

[natural-window-link-checks.json](natural-window-link-checks.json) pins the
scenario, comparison producer, input identity, private report, and output
hashes. Original game content, BIOS files, RAM dumps, images, and save states
remain local. The [feature inventory](FEATURE_INVENTORY.md) preserves all
earlier snapshots and appends this evidence separately.

## Remaining acceptance gates

The executed historical recorder uses Lua's `is_boolean and false or value`
expression when constructing its starting input table. That expression can
preserve an initially held Boolean. The requested-button log does not capture
the full submitted vector, so it cannot prove that every digital control was
cleared. The recorded output comparisons remain exact for their stated scope;
the original script bytes and frozen metadata are preserved. The newer
[Hoop Girl recorder](../research/npc_encounter/README.md) demonstrates explicit
neutralization, separate numeric submission, and full input/pad logs for its
own warm-state-specific scenario.

The installed Nymashock core reports zero available execution-hook scopes and
zero exposed registers. These are frame-level state observations. Direct
callback entry counts, instruction timing, audio output, cold boot, every
window configuration, and complete encounters are not verified by this profile.

The matching build remains 194,212 / 199,912 game-text bytes in C (97.15%), with
nine assembly functions and 24 inherited unused-storage explanations. The
provisional inventory remains 40 groups, with 35 listed-core C groups and zero
whole groups accepted. The 107 callback C bodies, 20 bounded native callback
profiles, ten developer capability categories, and three optional mods keep
their existing counts. Every [project completion requirement](../PROJECT_OBJECTIVE.md)
remains in force.
