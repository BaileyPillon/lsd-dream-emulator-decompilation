# Persisted save and cold-boot load

The original and matching rebuilt Japanese discs agree on one day-two save
and a subsequent **cold-boot load from the persisted card file**. The entire
1,792-byte saved game buffer is restored in both versions. Loading uses no
emulator save state.

| Recorded phase | Advanced frames per image | Observations per image | Full checkpoints | First registered card state | First return to idle |
| --- | ---: | ---: | ---: | ---: | ---: |
| Save from the naturally reached dream chart | 2,400 | 2,401 | 14 | 614 | 830 |
| Load after cold boot | 6,000 | 6,001 | 20 | 2,553 | 2,863 |

Each observation has 135 columns, including the original screen/card words,
comment/selection records when present, day and new-game fields, native pad
fields, and a SHA-256 of all 1 MiB GPU memory. All submitted controller values
are retained. At all 34 checkpoints, complete 2 MiB main RAM, GPU memory, PNG
bytes, and every save-state ZIP member payload agree. No bytes are masked.

## What was saved and restored

The warm starting state contains a blank formatted card. Ordinary controller
inputs leave the chart, select Save, accept the comment, and confirm the save.
The owned emulator exits before its external SaveRAM is inspected and preserved.

Both versions produce the same raw 131,072-byte card, SHA-256
`e208a7263da45897ffff758e49687995fe139346b3a8c434245acdda914fd722`.
Its only allocated file is `BISLPS-01556-01`, occupying one 8 KiB block;
fourteen blocks remain free. The directory/header checksums, chain termination,
`SC` header, three-icon mode, and original `J01` save-data magic are checked.
The native writer's 512-byte header precedes the 1,792-byte game payload.

The complete payload equals DreamSys offsets `0x178..0x877`, both when the
card operation returns and at the final checkpoint. Payload SHA-256:
`e8220ab85acb95534ddc3bd936f2745da3989027a6fd50319b34d232c1656eb7`.

For Load, a preserved copy of this actual card is staged in a fresh isolated
profile. Cold boot starts with stored day zero and the new-game flag set.
Controller inputs skip the opening, select Load, and choose the saved file.
At frame 2,863 the stored day is one, the new-game flag is clear, and the entire
payload matches the saved data. The card and its emulator-created backup
remain byte-identical after loading. The derived day number uses the original
stored-day-plus-one rule; the frame-level measurements here come from native data.
The retained frame-3,000 menu image displays `Day 002` after the loading dialog
has cleared; the earlier frame-2,863 image still shows that dialog.

Card operation and dialog state are different native words: `m_Unk8` at `0x24`
selects load/save, while `m_Unk9` at `0x28` tracks the card UI state. The verifier
reconstructs its derived flags from those raw fields and independently rereads
every recorded object word at each RAM checkpoint. This is frame observation;
it does not claim direct instruction-entry tracing.

The [writer recovery](CARD_WRITER_RECOVERY.md) and [bounded save checks](CARD_SAVE.md)
retain their earlier scopes. File allocation follows the
[PSX-SPX memory-card format reference](https://psx-spx.consoledev.net/psx-spx.pdf).

## Reproduce with local game inputs

Use a canonical `ninja check` build, Windows, BizHawk 2.11.1/Nymashock, verified
original/rebuilt Japanese CUEs, and the three BIOS inputs required by runtime
pinning. The Save recorder requires the specific naturally reached chart
context described in the [research guide](../research/card_roundtrip/README.md).
Captures and reports must use new private output paths.

```powershell
python tools/capture_card_roundtrip.py --phase save `
  --workspace D:/QA/card-save-new --state D:/Private/day-two-chart.State `
  --original-cue D:/Private/original.cue --rebuilt-cue D:/Private/rebuilt.cue `
  --emulator-root D:/Tools/BizHawk-2.11.1 --bios-root D:/Private/BIOS

python tools/capture_card_roundtrip.py --phase load `
  --workspace D:/QA/card-load-new `
  --card "D:/QA/card-save-new/original/exit-save-ram/LSD - Dream Emulator (Japan).SaveRAM" `
  --original-cue D:/Private/original.cue --rebuilt-cue D:/Private/rebuilt.cue `
  --emulator-root D:/Tools/BizHawk-2.11.1 --bios-root D:/Private/BIOS

python tools/compare_card_roundtrip.py `
  --save-original D:/QA/card-save-new/original --save-rebuilt D:/QA/card-save-new/rebuilt `
  --load-original D:/QA/card-load-new/original --load-rebuilt D:/QA/card-load-new/rebuilt `
  --output .decomp-lab/card-roundtrip-new.json
```

The launcher owns hidden, below-normal-priority instances and separate settings
and card paths. It preserves exit saves, pins inputs before launch, records
process exits, and refuses existing workspaces. The comparator checks complete
tables, the actual input route, state/checkpoint completeness, card allocation,
persisted bytes, and the complete restored native payload. Exit status 0 means
equal recorded outputs; 1 means recorded differences; 2 means invalid inputs.

## Acceptance boundary

This is **one slot and one save/load history**, repeated to exercise the
portable launcher. Repetition does not add independent gameplay scenarios.
The initial Save begins at a warm chart state; only the subsequent Load begins
at cold boot. Full card/error/cancel/overwrite routes, all slots, other saved
days and contents, physical cards, audio output, and original hardware timing
remain open. No complete feature group is accepted by this profile.

Two earlier observer diagnostics and a startup-only load attempt remain
excluded. A further comparator diagnostic wrongly required an embedded card to
occupy the same serialized state offset; the corrected verifier compares full
state payloads without that unsupported assumption. Their identities and the
successful records are pinned in [card-roundtrip-checks.json](card-roundtrip-checks.json).

C recovery remains **194,212 / 199,912 bytes (97.15%)**, with nine retained
assembly functions and 24 inherited unused-storage explanations. Original NPC
behavior, modern AI-assisted tooling, optional mods, and whole-feature
acceptance retain their separate counts. All seven
[completion requirements](../PROJECT_OBJECTIVE.md) remain active.
