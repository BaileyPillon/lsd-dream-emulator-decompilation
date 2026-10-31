# History-triggered movie reel from a prepared card

The original Japanese disc and the matching-C disc agree across **62,530 paired
emulated frames**, **105 complete-state observations** and **46,092,627 returned
stereo PCM sample frames per side** in this profile. Every recorded full-buffer
window, native field, submitted input, card-store observation and all four decoded
PNG images agree. [Machine-readable evidence](card-reel-checks.json) records the
exact sources, host, capture hashes and nine checked original function ranges.

This is a **constructed external memory-card input**. Its four-cell history was
prepared for the test rather than naturally earned. The original game then loads
it through its ordinary UI, starts a dream, updates the chart, consumes the
one-shot flag and plays the special reel. There are no game-RAM/instruction
writes or restored emulator states. The existing player and its saves are preserved.

| Evidence scope | Before this study | After this study |
| --- | ---: | ---: |
| Compared constructed-card reel routes | 0 | 1 |
| Distinct direct native movie start-file bindings | 8 / 39 | 9 / 39 |
| Normal opening choices compared | 7 / 7 | 7 / 7 |
| Matching game C bytes | 199,912 / 199,912 | 199,912 / 199,912 |
| Provisional feature groups | 40 | 40 |
| NPC callbacks recovered in C | 107 / 107 | 107 / 107 |
| Accepted whole features / NPC encounters | 0 / 0 | 0 / 0 |

The ninth start-file binding is `FILM/SPDAY01A.STR`. Starting this stream does
**not** establish consumption of all twenty concatenated movie payloads.
The previous all-opening comparison remains eight completed startup payloads;
its recording and measurements are unchanged. The exhaustive original feature
total is unknown. No gameplay feature, matching-C byte or model API call is added.

## Prepared input and provenance

The source is a prior game-generated QA card: raw 128 KiB, one `BISLPS-01556-01`
file in block 1, `SC 13 01` save header, `J01` data magic and a 1,792-byte payload.
It is separate from the user's live player card. The input copy changes internal
day 1 to day 4 (display Day 005), installs the four signed chart cells
`511, 257, 0, -768` and clears the consumed flag at payload offset `0x467`.
Only five file bytes differ in this retained fixture; the complete offset/before/
after allowlist is in the evidence. Directory checksums, allocation chain, icons,
title and every other byte are retained. The header therefore still carries its
original Day-002 label. This constructed copy is not represented as an entirely
game-generated save.

The cold core's supported `ISaveRam.StoreSaveRam` service receives the card before
frame 1. Full SaveRAM readback equals the input at core frame zero; complete
MainRAM/GPURAM hashes and frame count remain unchanged by that input operation.
The first native Load return contains the exact prepared 1,792-byte payload hash.
Final SaveRAM remains byte-identical to the prepared input on both runs. Original
QA-card and player files retain their previous full hashes.

## Original route and limits

The retained original timeline, reproduced by the rebuilt replay, is:

| Event | Input frame |
| --- | ---: |
| Main-menu object first observed | 1,980 |
| Native card Load observed | 2,436 |
| Load returned with complete prepared payload | 2,744 |
| Ordinary dream timer running | 3,228 |
| Four-cell graph event consumes its flag | 21,114 |
| Reel request starts | 21,884 |
| Active reel pointer clears | 62,349 |
| Post-reel main-menu object reappears | 62,490 |
| Final observation | 62,529 |

The final image shows the Day-006 transition, rather than a fully rendered
selectable menu. The reel is active for 40,465 sampled frames, including 40,427
streaming samples. The graph's flash index visits 0 through 4. Only the startup
logo and opening are controller-skipped; inputs remain neutral during the dream,
chart, reel and post-reel interval. The rebuilt run replays the original input
changes exactly. The original recording was independently checked before that
replay began; its then-current checker is retained losslessly. Later additional
event/frame binding checks pass on both retained captures without recapture.

`graph_screen_setup_video_event` searches up to 100 recent days for all four
cells, then sets the one-shot flag. The main-loop graph-return path calls
`play_special_reel`. Manually visiting Graph first is a different route because
it can consume the flag without the main-loop reel call. The journal column
`graph_result` samples graph-object offset `0x38`; it is **not** a recorded
function return or an instruction-entry event. Early setup fields can retain
uninitialized values and are not promoted to ready-state observations.

The reel passes threshold `-1`. `str_stream_get_next` bypasses its ordinary
positive-threshold accepted-ID checks and leaves the counter at zero while
streaming. The normal-opening contiguous-ID acceptance rule therefore does not
apply. `get_special_reel_movie_path(..., 0, 10)` sums **twenty** duration entries
(indices 14–33), plus transitions, giving 10,122 before quantization. It passes
674 to `SetLength`, whose native field stores 10,110. This corrects the earlier
F022 static observation's wording about ten movie lengths without rewriting that
historical inventory entry.

At reel pointer removal, neither sampled MDEC EOF flag has been set. This profile
compares the configured player interval and removal; complete decoder EOF and
per-file presentation are still open. SDK queue-head header words are retained
and compared, but may represent lookahead and do not prove each frame was consumed.
Nine complete original function ranges and the duration table were rehashed
against the canonical executable; instruction-entry events are not recorded here.

## Reproduce and compare

Use a separate QA card with the qualified first-year Day-002 slot-01/block-1
layout. The preparation command refuses existing output paths and never replaces
the source:

```powershell
python -B tools/prepare_card_reel.py QA-Day002.SaveRAM PREPARED.SaveRAM --manifest PREPARED.json
```

The asset-free helper reproduces the retained fixture exactly from its original
QA card. It preserves all bytes outside the documented calendar/history/flag
fields, and reports every byte actually changed. It is a test-fixture tool,
separate from normal gameplay and original NPC behavior.

Compile [RecordCardReelWindows.cs](../research/headless/RecordCardReelWindows.cs)
with `ReplayColdStart.cs` and `BoundedSha256Stream.cs`, x64 and
`/main:Lsd.Research.Headless.RecordCardReelWindows`, using the same qualified
BizHawk/.NET references and binding configuration as the
[cold movie recorder](COLD_MOVIE_WINDOWS.md#reproduce-and-inspect). Reuse its
runtime and provide your own complete Japanese disc and J/U/E BIOS files.

```text
RecordCardReelWindows.exe RUNTIME DISC.cue BIOS-J BIOS-U BIOS-E NEW-OUTPUT card-reel 80000 - PREPARED.SaveRAM
```

Review the original report, saved journal and images before recording the rebuilt
disc. For the rebuilt invocation, use the original `last_frame` as the ceiling
and its `inputs.tsv` in place of `-`. Retain wall/private-memory/output supervision.
The host caps 80,001 advances, 96 MiB raw native observations and 1,310,720 bytes
of gzip output per run; the pair's aggregate capture budget is 3.5 MiB. It refuses
existing output folders and honors its owned `STOP` file. A ceiling result remains
incomplete and is rejected by this comparison.

```powershell
python -B tools/inspect_card_reel.py ORIGINAL-FOLDER REBUILT-FOLDER --output PRIVATE-REPORT.json
```

Every frame contributes complete RAM, GPU RAM, RGB, returned PCM, native words
and controls to the existing framed-hash format. Windows contain 600 consecutive
frames and the exact final partial interval. Each ends with an unmasked full
serialized-state hash; the host repeats serialization and checks observation
does not alter RAM/GPU/frame state. The streaming reader validates full channel
byte counts, input policy, native lifecycles, gzip/PNG checksums and report scope,
then independently recomputes native/control hashes. It keeps one bounded row
at a time. Fifteen faults on copies of the real analysis are detected; synthetic
tests separately cover invalid cards, layouts, overwrites and malformed evidence.

The checker returns 0 for equality in this scope, 1 for retained differences and
2 for invalid/incomplete inputs. All 174 frozen runtime/disc/BIOS/compiler records
were rehashed around the recordings; no runtime or disc tree was copied.

Natural acquisition and repeat/disabled/missing-cell histories, every
concatenated film's actual decode/presentation, all special-day variants,
skip/error timing, original hardware, other seeds and whole-feature/NPC encounter
acceptance remain open. Existing NPC recovery, optional mods and AI-assisted
analysis remain distinct. The full project goal remains active.
