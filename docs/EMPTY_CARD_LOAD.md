# Empty-card Load: observed dialog and unresolved state comparison

The original and rebuilt Japanese game both enter the native **save not found**
state when Load is selected with a formatted card containing no files. The
controller trace, recorded game objects, full RAM/GPU checkpoints, screenshots
and persisted card files agree in both 6,000-frame input variants.
The complete emulator-state comparison **does not pass**: every checkpoint has
eight differing bytes in the decoded core payload. Those bytes are retained.
This is bounded runtime evidence, with no whole-feature acceptance.

## Native fields and observed route

The matching C now names two existing signed 32-bit fields:

| Offset | Field | Evidence |
| --- | --- | --- |
| `0x24` | `m_Operation` | `func_8004F638` selects Load (`1`); `func_8004F8A4` selects Save (`2`); `func_8004FBE4` returns it to idle (`0`) |
| `0x28` | `m_State` | The same transition handler stores the current dialog/operation state and clears it on completion |

Operation constants name idle, Load and Save. State constants name idle and
not found; other state numbers retain their existing labels. Field widths,
offsets, virtual bindings and control flow remain unchanged. Standard and fresh
306-object builds both reproduce the canonical 505,856-byte executable, SHA-256
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.
These names clarify existing C; they add no recovered function bytes and resolve
none of the 24 inherited storage explanations.

| Relative frame | Observed operation/state |
| --- | --- |
| 2,428 | Load requested: operation `1`, state `0` |
| 2,536 | No matching files: operation `1`, state `13` |
| 2,580 | Confirmation has returned operation/state to `0`/`0` |

The canonical table at `0x80086E80`, indexed by state `13`, resolves to
`CARD\NOTFOUND.TIM`. The frame-2,580 screenshot still displays the Japanese
message that the corresponding file is absent from the memory card. This
display can outlive the state transition; a screenshot alone does not identify
the current operation. Stored day remains zero (displayed Day 001), and the
new-game flag remains one. No saved data is selected or loaded.

## Card writes and the full-state limitation

The first input is the complete blank card retained in an earlier native
emulator state. Its fifteen directory entries are free and unlinked. Both runs
write exactly three bytes, at card offsets `8064`, `8065` and `8191`, to copy the
header into block 0, frame 63. Their exit cards agree byte for byte, and each
backup preserves its input card. Frame 63 is the documented write-test frame
in the [PSX-SPX format reference](https://psx-spx.consoledev.net/psx-spx.pdf).
The particular write is a runtime observation; its full caller chain has not
been traced.

The initial comparator incorrectly required the exit card to equal its input.
That rejection and producer identity remain private. The corrected verifier
requires the complete expected header-copy result and compares both full card
images. It masks no card or emulator-state bytes. An initialized write-test
frame is also a supported input. A second completed original/rebuilt pair uses
the first pair's actual exit card: no persisted card bytes change, and the
eight-byte core-state difference remains. The public capture command executes
this second input variant. These are two initial cards for the same not-found
route, with no additional accepted gameplay scenario.

Each pair records 6,001 rows with 135 columns, a complete GPU-memory hash
at each frame, and 16 full RAM/GPU/image/state checkpoints per image. All
non-state records and game-buffer checkpoints agree. Each decoded core state
differs in eight bytes, already present at the initial frame. Serialized offsets
move with the state layout; they are not PS1 memory addresses. The
[native accessor extension](NYMASHOCK_STATE.md#empty-card-extension-and-native-accessors)
maps every differing byte to unused capacity in Nymashock's `"CD"` media label.
Actual bundled `c_str()` and `size()` paths do not read that capacity. Two
additional same-disc cold-boot controls reproduce the difference without
switching the disc. The allocator's earlier contents and every possible
consumer have not been traced. The verifier still returns a nonzero result
for the full-state mismatch and accepts no complete runtime profile.

Five altered-record controls detect a changed write-test frame, changed backup,
wrong native error state, changed operation word in a private RAM copy, and an
unexpected submitted button. Seventeen new synthetic tests run without game
files. Faults affect private copies only; no game or emulator instructions are
patched, and the interactive play session is not used for QA.

## Reproduce with local inputs

Use the configured Windows BizHawk 2.11.1/Nymashock environment and a formatted
raw 128 KiB card with fifteen free, unlinked directory entries. All paths below
are local inputs or new output directories; original game files stay private.

```powershell
python tools/capture_card_roundtrip.py `
  --workspace D:\qa\empty-card-new `
  --original-cue D:\game\original.cue `
  --rebuilt-cue D:\game\rebuilt.cue `
  --emulator-root D:\BizHawk-2.11.1 `
  --bios-root D:\bios `
  --phase load --card D:\qa\empty.SaveRAM --card-kind empty

python tools/compare_empty_card_load.py `
  --original D:\qa\empty-card-new\original `
  --rebuilt D:\qa\empty-card-new\rebuilt `
  --output .decomp-lab/empty-card-comparison-new.json
```

The default capture profile still requires the persisted slot-01 save used by
the [successful round trip](CARD_ROUNDTRIP.md). An empty card is an explicit
alternative for cold Load. No saved state or arbitrary game-memory write is
used during either cold capture. The source card is preserved, and each run's
exit card and backup are retained in its own output folder.

The new comparator checks the native route, input alignment, pinned launch
inputs, independently reread RAM words, GPU hashes, complete state members,
card transition and preserved backups. Reports are created only at new paths
inside `.decomp-lab`. The tools call no AI model and add no original gameplay
or optional mod. [Evidence metadata](empty-card-load-checks.json) records both
input hashes, comparisons, matching builds, controls and unchanged inventory
counts. Private captures and the initial rejected comparator remain retained.

C remains 194,212 / 199,912 bytes (97.15%), with nine retained assembly functions,
24 inherited storage explanations and 35 / 40 listed-core C groups. Full state
agreement, disconnected/unformatted/full/corrupt cards, cancel/overwrite paths,
other slots, physical cards, audio and timing remain open. The feature inventory
is still provisional; whole-feature acceptance remains zero.
