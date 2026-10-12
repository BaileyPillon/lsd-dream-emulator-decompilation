# Japanese movement and controller-poll evidence

Four original/rebuilt replay pairs add 9,000 recorded emulator frames per side,
27 image/GPU/state checkpoints per side and 6,634,234 stereo PCM sample frames
per side. All compared outputs agree. The first pair records 43 native fields
per frame; the next three record 47, including the original pad object.
[movement-parity-checks.json](movement-parity-checks.json) pins the private
reports and public producers. The captures and game inputs remain private.

These are bounded replay results. Matching game C stays at 195,844 / 199,912
bytes (97.97%), with five assembly functions and five inherited source-padding
requirements. Whole-feature acceptance stays at 0 / 40 provisional groups.
The original game's behavior is unchanged; these developer tools make no
model API calls and do not change optional mods.

## What the original controls do

The canonical pad table at `0x80010764`, `pad_poll`, `func_80025D10` and
`set_move_from_pad` establish the bindings. The dispatcher distinguishes
pressed, held and released notifications. Up starts forward motion on a held
notification; Circle sets the action flag on a pressed notification. Cross
selects movement direction 4 when forward motion is active. Releasing Up
restores the preceding movement direction.

The current probe reads `g_GAME_FLOW`, its graphics-context pointer, the pad
pointer at context + `0x04`, and the original dream-system pointer. It validates
all three original virtual tables and follows only aligned MainRAM pointers.
It records the pad's held, released and pressed masks at offsets `0x10`,
`0x14` and `0x18`, together with native movement, view, lock and pose fields.
It writes no game memory.

| Requested control | Native mask | Observed effect in the unlocked stage-3 replay |
| --- | ---: | --- |
| Triangle | `0x0010` | Look position reaches -8,400; releasing returns it toward zero. |
| Square | `0x0080` | Look position reaches +8,400; releasing returns it toward zero. |
| D-pad Left / Right | `0x8000` / `0x2000` | Heading changes in both directions while position remains fixed. |
| L1 / R1 | `0x0004` / `0x0008` | Turn offset reaches -180 / +180 and returns to zero after release. |
| L2 / R2 | `0x0001` / `0x0002` | Move states 3 / 4 and opposing X displacement occur. |
| D-pad Down / Up | `0x4000` / `0x1000` | Move states 2 / 1 and opposing Z displacement occur. |
| Up + Cross | `0x1040` | Movement direction changes from 3 to 4 with forward displacement; release restores 3. |
| Circle pulses | `0x0020` | The original action flag is observed as 1 with native press/release masks. |
| Up pulses | `0x1000` | Twelve-frame pulses reach a held notification, move state 1 and Z displacement. |

The control names describe requested emulator inputs. The native fields support
the effects listed here; they do not establish every downstream action target,
surface, collision result or link destination.

## Why the replay was refined

The first 1,800-frame pair begins in stage 2 and enters stage 3 through a link
transition. Both runs agree, including the resulting input lock. Backwards,
turning and looking phases mostly fall inside that lock. Their labels therefore
do not demonstrate that those controls took effect. Its final original state
provides the same exact unlocked starting file for the next three pairs.

Those 2,400-frame pairs stay in stage 3 with all three input guards clear:
`paused`, `input_locked` and `auto_move_locked`. Look and turn controls precede
translation, and neutral gaps expose releases. The corrected running phase
uses Up + Cross. All phase durations and inputs are fixed in advance, and each
pair loads the same original state file on both sides.

The last two phases test controller polling with three pulse widths:

| Pulse width, once every 20 emulator frames | Requested frames in each 60-frame phase | Native result |
| --- | ---: | --- |
| 1 frame | 3 | Neither Circle nor Up reaches the native pad in this recorded alignment. |
| 8 frames | 24 | Both press/release masks appear. Circle sets the action flag; Up has no held-without-edge samples and does not move. |
| 12 frames | 36 | Both controls also have 15 held-without-edge sampled frames. Circle sets the action flag; Up moves. |

The eight-frame result is consistent with the original dispatch: Up's pressed
notification does not select forward movement. The public probe now uses
twelve-frame pulses. This is verified for this recorded state and poll cadence;
it is not a universal minimum pulse duration.

Pad edge fields persist across several emulator frames. The report counts
sampled frames with nonzero masks, rather than calling them distinct input
events. A phase can also begin before the original pad next polls the newly
requested controls. Requested-input counts, native pad counts and original
input-guard counts are retained separately.

## Reproducing and checking the result

Use the [runtime comparison workflow](RUNTIME_COMPARISON.md) with a saved
in-dream state and an absolute path to `tools/runtime_movement_probe.lua`.
Choose a new output folder for every run and the same state, scenario, frame
count and script for both discs. The launch helper freezes and hashes its
inputs, explicitly selects Nymashock, and records the actual native core,
Waterbox host, regional BIOS, disc track and configuration identities.

`tools/compare_runtime.py` accepts the complete historical 43-column format
or the complete current 47-column format. Both sides must use the same header.
Every scheduled frame and every field is required and compared. Native pad
pointers and unsigned masks are validated. Per-phase summaries count requested
inputs separately from frames passing the original three input guards.

Seven new synthetic guards check changed pad output despite equal images and
positions, each input lock, persistent edge sampling, missing/partial pad
capture, invalid pad pointers and out-of-range masks. All 314 tooling tests pass
on Windows and Linux. The canonical complete build still matches, and all 305
objects are current. The public CI checks developer tooling with synthetic
inputs; it does not distribute or rerun these private game captures.

## Remaining acceptance work

The records strengthen bounded evidence for F006 input, movement and camera
behavior, F005 session lifecycle, and one F010-related transition. The first transition's
fixed/dynamic destination selection and eligibility branches are not fully
classified. Stage 3 uses the observed floor type 7; other surfaces, stages,
controller modes, NPC interactions, rare states, save/card paths and original
hardware timing still need their own reviewed scenarios. None of these whole
feature groups is accepted by this supplement.
