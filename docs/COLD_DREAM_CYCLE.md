# Cold boot through the first dream

The original and rebuilt Japanese discs have matching recorded game outputs
through a **30,000-frame**
controller-only replay: boot, the title menu, a new dream, turning and walking,
the natural time limit, the dream chart, and the next-day menu. The later neutral
follow-up includes title-movie imagery. Both owned runs exit normally. Complete
emulator states differ in eight unused media-label bytes at every checkpoint;
the strict comparison retains a nonzero result.

This extends the earlier [6,000-frame cold-start profile](COLD_START.md).
Its original reports remain unchanged, including the earlier strict state
failure. [cold-dream-cycle-checks.json](cold-dream-cycle-checks.json) records
the new producers, hashes, before/after counts and comparison scope.

## Observed first-day sequence

| Relative frame | Same observation on both discs |
| --- | --- |
| 1,963 | First owner-qualified main menu |
| 2,382 | First owner-qualified dream session |
| 2,689 | First unlocked dream; movement follows |
| 23,699 | Native dream timer first reaches its observed limit of 3,600 |
| 23,705 | Input locks; timer is 3,601 |
| 23,706 | Timer resets to zero; stored day advances from zero to one |
| 24,000 | Inspected screenshot shows the dream chart |
| 24,578 | Owner-qualified main menu returns |
| 25,200 | Inspected menu screenshot visibly shows `Day 002` |
| 27,000 | Inspected screenshot shows subsequent title-movie imagery |

The one-frame 3,601 observation matters: the recovered timer routine increments
before its limit notification completes. These are field observations at emulator
boundaries, not instruction-entry traces. The day number shown in the menu is
also checked visually; it is separate from applying the getter's plus-one rule
to the stored day.

After the dream, the view-transform binding at DreamSys offset `0x5C` is zero
in the recorded checkpoints, while the player-coordinate pointer at `0x14`
remains stored. Retained coordinates do not establish an active dream scene.
Chart checkpoint records require the expected type and dream/graphics bindings;
they do not establish complete construction or allocator-lifetime coverage.
The observer's `startup` classification is a fallback outside its menu/dream
classes, including chart, transition and movie screens. It does not mean the
machine rebooted at each later occurrence.

## Exact comparison

Each run records 30,001 consecutive native observations, full 1 MiB GPU hashes
at every observation, and all 26 submitted controller values for every advanced
frame. All logs agree byte for byte. The recorder restores no saved state,
writes no game memory and stops requesting buttons after its movement sequence.

All **61 checkpoint pairs** agree in complete 2 MiB MainRAM, 1 MiB GPU memory
and PNG bytes. Save-state members agree except for `Core.bin.zst`, whose decoded
payload differs by eight bytes in every pair. Complete WAV bytes and
**22,113,556 stereo PCM sample frames** agree at 44,100 Hz and 16 bits per
channel. No state bytes are masked. Launch manifests revalidate the same disc
contents/layout, BIOS, runtime/core files, configuration and executed observer.
The first recorded boundary is emulator frame one.

The strict comparator returns **two**. All eight decoded differences in each
of the 61 pairs map to unused
bytes 16 through 23 of Nymashock's native `CD` media-type string, at Waterbox
guest addresses `0x36f0080fc10` through `0x36f0080fc17`. These are emulator
addresses, separate from PlayStation RAM. The [existing diagnosis](NYMASHOCK_STATE.md)
describes the native owner and copy path. The new pair repeats the same two
captured string objects across its checkpoints. Twelve actual bundled `c_str()`
and `size()` baseline/control calls check those objects: live text is `CD`,
length is two, and the tested accessors do not read the changed capacity.
Earlier allocator contents and every other possible consumer remain unverified.
This diagnosis does not change the raw result or accept full-state parity.

The optional `--require-day-advance` gate
requires a native one-day change under the same dream owner and a full checkpoint
after that change. The retained 6,000-frame history still passes ordinary
comparison and returns two when presented to this stronger gate. It cannot be
reported as next-day evidence merely by changing the requested report.

## Reproduce with local game inputs

Use the same supported local inputs as [the cold-start guide](COLD_START.md).
Choose a new capture workspace and report path; existing captures and ordinary
play saves are preserved.

```powershell
python tools/capture_cold_start.py --frames 30000 `
  --workspace D:/QA/lsd-first-dream-new `
  --original-cue D:/Private/original.cue --rebuilt-cue D:/Private/rebuilt.cue `
  --emulator-root D:/Tools/BizHawk-2.11.1 --bios-root D:/Private/BIOS

python tools/compare_cold_start.py --frames 30000 --require-day-advance `
  --original D:/QA/lsd-first-dream-new/original `
  --rebuilt D:/QA/lsd-first-dream-new/rebuilt `
  --output .decomp-lab/first-dream-new.json
```

Both commands retain the 6,000-frame default and support 6,000 through 30,000
frames. The executed Lua observer is unchanged from the earlier profile.
The tooling suite passes 719 tests on Windows and WSL, with two expected skips
on each. The matching 306-object build remains canonical and all 392 game
build inputs are unchanged.

Matching C remains **196,504 / 199,912 bytes (98.30%)**, with four game assembly
functions and two inherited storage explanations. The 40 provisional groups,
37 listed-core C groups, 36 of 107 bounded NPC callbacks, and zero accepted
whole feature groups or NPC encounters retain their existing counts. This
replay does not establish every dream, NPC branch, movie, card/error path or
original hardware timing requirement. Use [PLAYING.md](PLAYING.md) for ordinary
play; the remaining [project requirements](../PROJECT_OBJECTIVE.md) stay open.
