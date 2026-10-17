# Cold start into a playable dream

The original and rebuilt Japanese discs have now been compared through a cold
boot, the title menu, starting a dream, and controller-driven movement. Neither
run restores an emulator state or writes game RAM. This complements the earlier
[saved-state movement replay](RUNTIME_COMPARISON.md#october-15-matching-build-replay)
and [cold-boot card Load](CARD_ROUNDTRIP.md); it exercises the new-dream path.

Two original/rebuilt pairs use separate fresh emulator profiles. Each pair
advances **6,000 frames per disc**, recording 6,001 observations and every
submitted controller value. The primary pair executes the published capture
tool and observer. [cold-start-checks.json](cold-start-checks.json) pins the
producers, private reports, repeated capture and unchanged recovery counts.

## Recorded path and outputs

| Observation | Original and rebuilt |
| --- | --- |
| First observer boundary | Relative frame 0, emulator frame 1 |
| Main menu first observed | Relative frame 1,963 |
| Owner-qualified dream session first observed | Relative frame 2,382 |
| First unlocked dream | Relative frame 2,689 |
| Controller definition | 21 Boolean controls and five numeric controls; all 26 submitted values retained |
| Movement | Native yaw changes during left/right input; position changes during forward/backward input |
| Native/GPU observations | All 6,001 rows, including complete 1 MiB GPU-memory hashes, agree |
| Full checkpoints | All 16 pairs agree in 2 MiB MainRAM, 1 MiB GPU memory and PNG bytes |
| Save states in the published-tool repeat | Every ZIP member payload agrees at all 16 checkpoints |
| Audio | Complete WAV and 16-bit stereo PCM agree: 4,422,265 sample frames at 44,100 Hz |

The observer first sees emulator frame one. It does not observe the preceding
boundary. Screen classifications require the game-flow and dream-system owner
chain, the original session/map types, the player transform and unlocked input.
The verifier rereads those fields from complete RAM at each checkpoint. Turning
and walking claims require changes in native yaw and position, rather than
button names alone. Looking inputs are retained; this profile does not claim
complete camera/view behavior coverage or direct instruction-entry tracing.

## Retain the earlier full-state mismatch

The published-tool repeat passes the strict comparator, including every
save-state member. The earlier exploratory pair remains a separate failed
comparison: each of its 16 checkpoint pairs differs in eight decoded bytes of
`Core.bin.zst`. The [existing Nymashock diagnostic](NYMASHOCK_STATE.md) maps every
changed byte to unused capacity in the native `CD` media label at Waterbox guest
addresses `0x36f0080fc10` through `0x36f0080fc17`. These are emulator addresses,
not PlayStation RAM offsets. The raw differences remain in the earlier report.

The bundled `c_str()` and `size()` methods are executed against copies of the
first pair's label objects, with the documented capacity/length/character
controls. Their results agree with the earlier field diagnosis. This checks
native emulator accessors; it does not recover another game function, trace the
allocator's prior contents or establish every possible consumer.

The strict comparison returns **exit code 2 for the earlier pair** and
**exit code 0 for the published-tool repeat**. No state bytes are masked.
This verifies one bounded cold-start history; it does not establish identical
state for every cold boot or accept a complete original feature group.
All-content coverage, natural NPC encounters, physical hardware timing and
the remaining matching C work remain separate requirements.

The later [first-dream replay](COLD_DREAM_CYCLE.md) extends the same observer
to 30,000 frames, through the natural dream end, chart and next-day menu.
Its comparison and day-advance requirement are recorded separately.

## Reproduce with local inputs

Use the matching build, supported complete Japanese original/rebuilt CUEs,
BizHawk 2.11.1/Nymashock, and your own BIOS files. Close an existing emulator
session before starting this isolated recorder. Choose new output directories;
the tool preserves its owned exit SaveRAM and rejects an existing workspace.

```powershell
python tools/capture_cold_start.py `
  --workspace D:/QA/lsd-cold-start-new `
  --original-cue D:/Private/original.cue `
  --rebuilt-cue D:/Private/rebuilt.cue `
  --emulator-root D:/Tools/BizHawk-2.11.1 --bios-root D:/Private/BIOS

python tools/compare_cold_start.py `
  --original D:/QA/lsd-cold-start-new/original `
  --rebuilt D:/QA/lsd-cold-start-new/rebuilt `
  --output .decomp-lab/cold-start-new.json
```

The comparator validates the complete launch identity, cold-start boundary,
observer bytes, frame continuity, every submitted control, native checkpoint
fields, full GPU hashes, PCM and every saved-state member. Use
`tools/inspect_nymashock_state.py` separately to diagnose a state difference;
that diagnostic does not change the strict result.

To play interactively, use the [matching-build launcher and controls](PLAYING.md).
The matching game includes its four remaining original assembly functions.
Before and after this profile, matching C remains **196,504 / 199,912 bytes
(98.30%)**, with 40 provisional feature groups, 37 whose listed core routines
are C, 36 of 107 NPC callbacks with bounded native checks, and zero complete
feature groups or NPC encounters accepted. Analysis tools and optional mods
remain separate from original game behavior.
