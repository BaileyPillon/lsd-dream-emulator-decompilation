# Restoring the recorded replay boundary

The Hoop Girl continuation now starts at the exact checkpoint recorded by the
earlier natural route. Its initial frame counter, all 2,097,152 MainRAM bytes,
and every save-state member payload agree with that source checkpoint. The
original and rebuilt discs then agree through the 1,800-frame continuation.

This resolves the start-boundary difference reported in
[the earlier profile](HOOP_BOUNDARY.md). It adds no recovered C bytes or
whole-encounter acceptance.

## Observed loading difference

Two isolated original-disc processes load the same frame-12000 state from the
[window-to-Hoop Girl route](NATURAL_HOOP_TIMING.md). The diagnostic reads RAM
without calling `emu.frameadvance()`.

| Load method | First observed core frame | MainRAM differences from the source |
| --- | ---: | ---: |
| Command-line `--load-state`, followed by Lua observation | 18,604 | 645 bytes |
| `savestate.load()` inside Lua, before observation | 18,603 | 0 bytes |

These results reproduce the earlier difference and identify a working start
protocol for this BizHawk 2.11.1/Nymashock configuration and saved state. They
do not establish the behavior of every emulator version or loading API.

## Paired continuation

The new [capture launcher](../tools/capture_state_replay.py) prepends a scoped
Lua loader to the unchanged, self-contained observer. It freezes the resulting
complete script and the starting state before fingerprinting them. Its emulator
command omits `--load-state`; the Lua loader restores `start.State` before the
observer runs. Original and rebuilt runs use isolated QA save paths.

| Comparison | Exact scope |
| --- | --- |
| Launch inputs | Disc tracks/layout, seven runtime/core files, three BIOS files, settings, complete executed script and starting state |
| Start against the earlier route | Core frame 18,603, full MainRAM and every save-state member payload |
| Frame observations | All 1,801 rows |
| Submitted input | All 1,800 vectors; 21 false Boolean controls and five unchanged numeric values |
| Game pad observations | Held, released and pressed fields remain zero |
| Full RAM, PNG and save-state members | Seven checkpoints: frames 0, 1,542, 1,547, 1,552, 1,557, 1,562 and 1,800 |

The first observations of ticks 2,399 through 2,403 occur one relative frame
later than in the earlier continuation. Both profiles observe the first facing
change at tick 2,402. The new start includes the preceding saved frame, so the
relative frame numbers describe different starts. No recorded data is shifted,
masked or rewritten to make the comparisons agree. ZIP archive wrappers are
compared separately from their complete member payloads.

The four new tooling tests include an actual Lua execution check of load-before-
capture order, a negative control for the earlier order, and a failed-load
control that must prevent the observer from running. Windows passes all 514
tooling tests with the bundled Lua 5.4 library. WSL passes 512 and skips the two
optional Lua execution tests because its interpreter is unavailable.

## Reproduce

Use the same private starting state required by the
[boundary observer](../research/npc_encounter/README.md#hoop-girl-boundary-continuation).
From Windows, substitute your own paths and a fresh workspace:

```powershell
python tools/capture_state_replay.py `
  --workspace "D:/LSD/qa/hoop-sync-new" `
  --original-cue "D:/LSD/original/LSD.cue" `
  --rebuilt-cue "D:/LSD/rebuilt/LSD.cue" `
  --emulator-root "D:/Tools/BizHawk-2.11.1" `
  --bios-root "D:/Private/PSX-BIOS" `
  --observer research/npc_encounter/hoop_boundary.lua `
  --state "D:/LSD/qa/route/original/frame-12000.State" `
  --frames 1800
```

The observer has specific actor/state requirements. The launcher captures the
pair; matching outputs still require comparison. Its input manifests work with
the existing runtime-input verifier. The profile-specific comparison and all
capture hashes are pinned by [state-replay-boundary-checks.json](state-replay-boundary-checks.json).
Game content, BIOS files, states, images and RAM dumps remain private.

This is one warm-state NPC/RNG history. It proves checkpoint continuity for
the captured state and observations, without proving an uninterrupted process,
cold boot, complete construction/lifetimes, all RNG paths, audible output or
hardware timing. C remains 194,212 / 199,912 bytes (97.15%), with nine assembly
functions and 24 inherited storage explanations. Bounded NPC coverage remains
20 / 107; whole-NPC and whole-feature acceptance remain zero. The ten developer
capability categories and three optional mods retain their separate counts.
