# Controller reset and resumed gameplay

The subsequent [card roundtrip](RESET_CARD_ROUNDTRIP.md) verifies native Save
after the ordinary reset and fresh-process Load of that exact card. This page
retains the earlier ordinary/flashback controller profile and its limits.

The original pause/Select/Triangle reset route now matches between the original
and rebuilt games in both an ordinary dream and a flashback. Each run cold-boots,
loads a separate QA memory card through the original menu, exercises the guards,
resets, returns through the menu loop and plays a fresh dream for 180 frames.

| Recorded route | Paired frames | Output windows | Complete object pairs | Native entry pairs |
| --- | ---: | ---: | ---: | ---: |
| Ordinary dream | 9,975 | 34 | 37 | 346 |
| Flashback with constructed score unlock | 4,940 | 17 | 37 | 601 |
| Total | 14,915 | 51 | 74 | 947 |

Every frame contributes complete MainRAM, GPURAM, rendered RGB, returned stereo
PCM, native observations and controller inputs to framed hashes. All original/
rebuilt hashes, complete object snapshots and final memory-card bytes agree.
An additional original-disc run through the installed stock core agrees for
each route. These six qualified cold boots advance 44,745 frames in total.
Selected original PNGs were visually inspected. Entire serialized core states
and physical PlayStation hardware are outside this comparison.

## Original input route

The default runtime table and observed pad object establish the physical names:
Start produces `0x800`, Select `0x100` and Triangle `0x10` in the original
byte-swapped `PadRead` result. Local recorder mask bits are a separate format.

Start opens the overlay. Held Select dispatches `0x0C`, arming the command when
text is active and map state is zero. Pressed Triangle dispatches `0x16`.
The armed callback resumes the map and notifies link code 13; the dream-session
handler calls `dream_sys_end_day(..., 2)`, followed by the original initializer
and navigation-array reset. The trace observes held Select before pressed
Triangle in that reset frame. Releasing Select dispatches `0x2C` and disarms.

Both profiles also exercise Triangle during gameplay, the chord without the
overlay, Triangle in the overlay without Select, and releasing Select before
Triangle. Four unarmed native confirm calls occur without a reset. Nine stable
guard snapshots per route check the related text/arming/day fields. Polling
latency is retained: the snapshot immediately around release is not required
to reflect a button change before the original controller poll handles it.
Inactive-link and nonzero-map-state guards need further runtime scenarios.

Fourteen original code ranges total 2,088 bytes. Addresses and sizes agree with
retained GNU symbols from a canonical full link. Complete RAM code ranges are
hashed at every recorded entry. Thirteen targets are actually entered across
the two routes, covering 1,988 bytes of entry-qualified code. This is an entry
trace, not an instruction-by-instruction execution-coverage claim. The earlier
[native VM study](NEW_GAME_RESET.md) separately executes complete reset bodies.

## Save and fixture boundaries

The full 1,792-byte save block agrees with the reset oracle: 576 bytes have reset
write destinations, and 1,216 retain their prior contents. Both recorded resets
preserve the same 15 nonzero inactive-history bytes. The comparison uses the
complete object snapshots bracketing reset, not a mask of selected fields.
The reset flag outside the block becomes one. The final card remains identical
to the card supplied at cold boot; these scenarios do not issue Save afterward.

The ordinary scenario uses an unchanged prior QA save. It loads native day 1
and reaches native day 2 before the controlled input window. That intervening
day path is retained in the outputs but is not separately accepted here.

Flashback requires a total unlock score above 9,999,999 and a stored flashback.
The earlier QA card has score 100,000 and a real stored record, so its row stays
disabled. A separate fixture sets only the total and instance score words to
10,000,000, keeping navigation score zero. Six raw-card bytes change; the card
directory, icons, history and existing flashback record stay byte-identical.
This qualifies a controller route from a constructed unlock state, not the
progression that earns the unlock. The source card and player saves stay intact.

## Reproduction and evidence

The asset-free [Windows recorder](../research/headless/RecordNewGameResetWindows.cs)
uses the existing BizHawk 2.11.1 installation, three local PS1 BIOS files, a local
disc and a separate QA card. Its argument order is:

```text
runtime cue BIOS-J BIOS-U BIOS-E output normal|flashback ceiling replay-or-dash raw-card targets observer|stock
```

Compile it with `ReplayColdStart.cs` and `BoundedSha256Stream.cs`, selecting
`Lsd.Research.Headless.RecordNewGameResetWindows` as the entry point. Use the
[target manifest](../research/new_game_reset/controller-functions.json).
Observer mode reuses the previously qualified movie observer core's generic
dispatch API; movie-payload recording stays disabled. Stock mode needs no
observer exports. Keep outputs fresh and bounded; use the original input
schedule for the rebuilt and stock comparisons.

The qualified ordinary run uses the earlier recorder revision retained in Git;
the manifest pins its source blob and SHA-256. The current revision handles
partially initialized map pointers and retired card-child pointers explicitly,
and observes the native new-game clear during Load. It produced the qualified
flashback runs. These observer changes do not write original game RAM or code.

Check a completed pair with the published verifier:

```sh
python -B tools/verify_controller_reset_capture.py \
  --capture "$ORIGINAL_CAPTURE" --mode normal \
  --compare "$REBUILT_CAPTURE" --output "$NEW_REPORT"
```

Use `--mode flashback` for that scenario, or `--stock` when the comparison is the
stock-core capture. The verifier rejects gaps, mismatched full objects, changed
code/arguments, missing guards and inconsistent channels. Nine synthetic tests
cover damaged evidence without game assets. Eight additional analysis-record
controls are rejected across the actual captures, including one changed
preserved byte with its payload hashes recomputed. These are evidence controls,
distinct from the earlier VM's executed game-instruction faults.

[Validation metadata](controller-new-game-reset-checks.json) pins the producers,
runtime identities, native targets and private capture hashes. Original game
assets, cards and object payloads remain private. Initial locator failures and
the locked-card attempt are retained as unqualified observations.

## Remaining scope

Broader input histories, original constructor returns and allocation lifetime,
inactive/nonzero map guards, Save/Load after reset, naturally earned unlocks,
other features and NPC encounters, hardware and independent whole-game
acceptance remain open. F004 is not accepted as a whole feature by this profile.

Matching C remains 199,912 / 199,912 bytes, with zero game assembly fallbacks.
The 40 provisional feature groups, 107 recovered original NPC callbacks and
whole-feature/encounter acceptance totals are unchanged. The new recorder and
verifier extend analysis tooling; they add no gameplay or NPC behavior and make
no model API calls. The supported playable build and its saves are preserved.
