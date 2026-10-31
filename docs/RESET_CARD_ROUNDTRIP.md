# Reset, native Save and cold Load

The original and rebuilt games agree when the player resets through the
pause/Select/Triangle route, saves through the original menu, then cold-boots
again and loads the exact native-written card. The second process selects
slot 02 from the game's two-file chooser and resumes an ordinary dream for
180 frames. No save state or guest RAM/instruction write supplies the result.

| Phase | Paired frames | Hash windows | Complete object pairs | Native entry pairs |
| --- | ---: | ---: | ---: | ---: |
| Load existing card, reset, Save | 9,594 | 32 | 40 | 1,741 |
| Fresh-process Load, resumed dream | 3,865 | 13 | 5 | 301 |
| Total | 13,459 | 45 | 45 | 2,042 |

Each phase also agrees with an original-disc run using the installed stock
core. The six qualified cold boots advance 40,377 frames in total. Every frame
contributes complete MainRAM, GPURAM, rendered RGB, returned stereo PCM, native
observations and controller inputs to framed hashes. Each paired side returns
9,920,012 stereo sample frames. Complete object snapshots, native card/menu
transitions, observer entry records and the full native-written card images
agree. Whole serialized core state and physical hardware are not compared.

## What survives the roundtrip

The unchanged prior QA card contains `BISLPS-01556-01`. The original game loads
it, reaches native day 2 and executes the same ordinary reset route as the
[earlier controller profile](CONTROLLER_NEW_GAME_RESET.md). The reset's entire
1,792-byte payload agrees with the separately executed original-code model:
576 bytes have reset-write destinations and 1,216 retain prior contents,
including 15 nonzero inactive-history bytes. The new-game flag outside that
payload becomes one.

Native Save creates `BISLPS-01556-02` without changing any of slot 01's 8,192
logical file bytes. The card header, allocation chains, directory checksums,
save header and complete reset payload are checked. Native write, success
notification 22 and the original new-game flag clear occur in that order.
The recorder retains the resulting card and observes another 120 frames.
The first success-frame screenshot still shows the retiring Save message;
the final screenshot shows the stable menu at `Day 001`.

Cold Load starts a separate process with this exact exported card. Its initial
RAM payload differs from the requested save, so the check cannot pass merely
because the old process left those bytes in memory. The native file chooser
contains both filenames and selects slot 02. The original read targets the
dream object's full 1,792-byte save block; success notification 22 executes
the original flag clear. All loaded payload bytes agree with native Save.
The card remains unchanged while the new ordinary dream runs, including a
recorded movement input. The final original frame shows the dream environment.

## Persistence and observer boundaries

The supported `ISaveRam` interface exports and restores the separate QA card.
Before the first frame, storing that card is checked to leave guest RAM,
GPURAM and the core frame counter unchanged. No player card or profile is used.

All three Save runs log two identical core warnings about opening the virtual
path `SAV:0.mcr`. The native core's delayed virtual-file auto-flush therefore
is **not verified**. That warning is retained and distinguished from the valid
frontend card export, the unchanged original logical file and the successful
fresh-process Load. The three Load runs log no such warning; its absence does
not prove auto-flush. No core or player configuration is changed to suppress it.

Sixteen registered code ranges total 2,576 bytes. Their addresses and sizes
agree with retained symbols from a canonical full link; all sixteen are
entered across the observer runs. Complete RAM code ranges are hashed at
each recorded entry. This is not instruction-by-instruction execution coverage.
The stock comparison uses no observer entries and qualifies only the common
recorded outputs. Movie-payload recording remains disabled.

## Reproduce and check

The [Windows driver](../research/headless/RecordResetCardRoundtripWindows.cs)
extends the shared reset observer without changing its earlier behavior. The
primary source's `partial` declaration was separately compiled with the prior
entry point and reproduces the entire prior 76,288-byte driver binary exactly.

Compile the driver with `RecordNewGameResetWindows.cs`, `ReplayColdStart.cs` and
`BoundedSha256Stream.cs` against the existing BizHawk 2.11.1 dependencies. Select
`Lsd.Research.Headless.RecordResetCardRoundtripWindows` as the entry point. Its
argument order is:

```text
runtime cue BIOS-J BIOS-U BIOS-E output save|load ceiling replay-or-dash QA-card targets observer|stock target-filename expected-payload-sha256
```

Use the [qualified target manifest](../research/card_roundtrip/reset-controller-functions.json).
Keep each output directory fresh. Bound captures to 30,001 frame advances,
2 MiB of retained files and 900 seconds; stop on the owned sentinel or watchdog.
Review the original before replaying its exact input schedule on the rebuilt
and stock cores. For Load, use each role's own verified native-written card,
with no card editing between the two processes.

Check a completed pair with the [public verifier](../tools/verify_reset_card_roundtrip.py):

```sh
python -B tools/verify_reset_card_roundtrip.py \
  --capture "$ORIGINAL_LOAD" --input-card "$ORIGINAL_SAVED_CARD" --mode load \
  --compare "$REBUILT_LOAD" --compare-input-card "$REBUILT_SAVED_CARD" \
  --stderr "$ORIGINAL_STDERR" --compare-stderr "$REBUILT_STDERR" \
  --output "$NEW_PRIVATE_REPORT"
```

Use `--mode save` and the unchanged initial QA card for the Save pair. Add
`--stock` for the stock-core comparison. Without `--compare`, `--stock` checks
a single stock capture. Reports refuse to overwrite an existing path.

Fifteen asset-free tests exercise complete card bytes, both logical files,
frame/channel integrity, success/clear causality and unmasked comparisons.
Eleven additional in-memory faults in the actual evidence are rejected,
including a single changed preserved history byte with valid recomputed
payload hashes. These are analysis-record controls, not executed game faults.

[Validation metadata](reset-card-roundtrip-checks.json) pins the executed
producer, normalized Git sources, runtime identities, input cards and private
evidence hashes. Game assets, BIOS, card images and object payloads stay private.
The first compile diagnostic and superseded analysis revisions are retained;
they are not qualified game captures. All six actual captures use one frozen
driver binary.

## Remaining scope

This closes the bounded ordinary reset/Save/cold-Load route, not all card or
F004 behavior. Flashback reset persistence, overwrite/full/missing-card/error
states, original constructor returns and allocation lifetimes, other input
histories and map guards, naturally earned unlocks, broader feature/NPC
acceptance, hardware and independent whole-game review remain open.

Matching C stays 199,912 / 199,912 bytes, with zero game assembly fallbacks.
The same 40 provisional feature groups and 107 original NPC callbacks remain;
whole-feature and whole-encounter acceptance counts remain zero. This increment
adds capture and checking tools, with no new gameplay behavior, optional mod or
model API call. The supported matching-C player remains available through the
[existing launcher](PLAYING.md).
