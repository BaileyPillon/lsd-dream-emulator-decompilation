# All seven opening choices

One original-disc cold start and its exact-input rebuilt replay agree across
**162,803 paired emulated frames**, **272 complete-state observations**
and **120,007,579 returned stereo PCM sample frames per side**. The game's normal
title-screen attract loop completes all seven opening choices, including repeated
selections, with 31 completed opening lifetimes per run.
The one startup logo also completes. No controller button is pressed.

All retained full-buffer windows, native observations, inputs, lifetimes and
decoded final images agree. [Machine-readable evidence](opening-attract-checks.json)
binds the executed sources, host, runtime records, original function ranges and
private capture hashes. This extends the [three cold movie/skip profiles](COLD_MOVIE_WINDOWS.md)
without changing their recordings or checker.

| Evidence scope | Before this study | After this study |
| --- | ---: | ---: |
| Normal opening choices observed | 1 / 7 | 7 / 7 |
| Distinct routed movie payloads observed | 2 / 39 | 8 / 39 |
| Matching game C bytes | 199,912 / 199,912 | 199,912 / 199,912 |
| Provisional feature groups | 40 | 40 |
| NPC callbacks recovered in C | 107 / 107 | 107 / 107 |
| Accepted whole features / NPC encounters | 0 / 0 | 0 / 0 |

Movie payloads are content records within feature groups, rather than new game
features. The official exhaustive feature total remains unknown. The study adds
no gameplay feature, optional mod, recovered C bytes or model API calls.

## Normal native lifetimes

Original `get_random_opening_movie_path` consumes a new random value for each
selection. `game_flow_execute_phases` returns to the intro when the title menu
idles out. This route uses those original paths without changing the seed,
loading a state, writing game RAM/instructions, or accessing the player's UI or
saves. Four complete original function ranges were checked against the canonical
executable; this is a source/static binding, without instruction-entry events.

| Native file | Requested threshold | Accepted IDs sampled while streaming |
| --- | ---: | --- |
| `ASMK.STR` | 90 | 0–89 |
| `OPENINGA.STR` | 1,060 | 0–1,059 |
| `OPENINGB.STR` | 1,088 | 0–1,087 |
| `OPENINGC.STR` | 953 | 0–952 |
| `OPENINGD.STR` | 1,179 | 0–1,178 |
| `OPENINGE.STR` | 979 | 0–978 |
| `OPENINGF.STR` | 1,231 | 0–1,230 |
| `OPENINGG.STR` | 1,046 | 0–1,045 |

Every completed lifetime retains setup, streaming and stopped samples, a stable
native filename/LBA/logical size, contiguous nondecreasing accepted IDs, both
MDEC completion fields and subsequent removal of the active pointer. Repeated
openings remain separate lifetimes. The two complete runs end 180 frames after
the last previously unseen choice clears.

The thresholds are the original game's stopping conditions. The
[movie inventory](MOVIE_INVENTORY.md) separately records encoded tails. Accepted
IDs and completion flags alone do not prove that every encoded image was
presented, or establish original hardware timing.

## Retained incomplete attempt

The first original run reached its 160,001-frame bound after thirty completed
opening lifetimes and six distinct choices. OPENINGC had begun at frame 158,791
but reached only accepted ID 296. It is retained as an **unpaired, incomplete
attempt**, with its original recorder and reports; no all-seven comparison or
rebuilt replay is attributed to it.

After saved-data review, a fresh cold run allowed a later endpoint, bounded to
170,001 frames. Only the recorder's maximum permitted endpoint changed. Its
first 160,001 native rows agree exactly with the incomplete recording, and the
first 266 complete buffer/state windows agree (159,600 frames). The earlier
401-frame final partial buffer window has a different endpoint and is not
independently compared with a prefix of the later whole window.

The completed extended original was independently read before launching its
rebuilt replay. Both completed native processes exited with code zero. The
incomplete attempt's code one explicitly records its frame ceiling.

## Streaming comparison and controls

Every advanced frame contributes complete MainRAM, GPURAM, RGB, returned PCM,
native words and submitted controls to framed SHA-256 windows. Each payload is
prefixed by input frame, core frame and payload length as three signed
little-endian 32-bit words. RGB includes width/height and complete row-major RGB;
PCM includes every returned signed 16-bit stereo sample, including empty returns.
Windows contain 600 consecutive frames plus the exact final partial window.

Each window also ends with an unmasked full serialized-state hash and final
RAM/GPU/RGB hashes. The host saves each state twice, verifies stable hashes and
checks that observation changes neither RAM/GPU nor the core frame. The reader
requires every channel, full byte counts, the complete frame schedule and exact
neutral input. It recomputes framed native/control hashes from one bounded line
at a time, without retaining the complete decompressed journal or per-frame row
dictionaries. Native gzip streams, CRCs and final decoded PNGs are checked.

13 controls on copies of the recorded analysis detect changed
disc extents/native fields, unsupported closed-stream lifecycles, missing buffer
bytes or states, incomplete scope, and GPU/PCM/state/image differences. These
controls alter neither the game nor retained captures. Synthetic tests separately
check malformed journals, lifecycle/order, bounds and explicit partial-review
handling. Partial data cannot pass the all-seven comparator.

All 174 previously frozen runtime/disc/BIOS/compiler records were rehashed around
the recordings. The profile reuses the [qualified initialized-media core](SERIALIZED_CORE_STATES.md).
Working-source and Git-blob hashes are recorded separately; any unchanged CRLF/LF
representation difference is explicitly identified.

## Reproduce and inspect

Compile [RecordOpeningAttract.cs](../research/headless/RecordOpeningAttract.cs)
with `ReplayColdStart.cs` and `BoundedSha256Stream.cs`, selecting
`/main:Lsd.Research.Headless.RecordOpeningAttract`, x64 and the same .NET Framework
and BizHawk references as the [cold movie host](COLD_MOVIE_WINDOWS.md#reproduce-and-inspect).
Use a linked shared runtime, its existing binding configuration and your own
complete Japanese disc and J/U/E BIOS files. No emulator, BIOS, game asset or
native binary is included in this repository.

```text
RecordOpeningAttract.exe RUNTIME DISC.cue BIOS-J BIOS-U BIOS-E NEW-OUTPUT neutral 170000 -
```

Review the completed original before recording the rebuilt disc. Pass the
original report's `last_frame` and its `inputs.tsv` as the rebuilt endpoint and
replay input. Keep wall-time, private-memory and aggregate-output supervision;
the host refuses existing output folders and honors its owned `STOP` file.
The reported bounds are limits, rather than a guarantee that another seed will
choose every opening within them. A ceiling result remains incomplete.

Compare completed folders without an emulator or game data:

```powershell
python -B tools/inspect_opening_attract.py ORIGINAL-FOLDER REBUILT-FOLDER --output PRIVATE-REPORT.json
```

The checker returns 0 for equality within this recorded scope, 1 for retained
differences and 2 for invalid/incomplete inputs. Its optional Python API
`load_recording(..., allow_incomplete=True)` supports explicit partial review;
such data is rejected by the all-seven comparator.

The other 31 routed payloads, all skip timings/disabled/error branches, exact
encoded-frame presentation, complete ending review, other seeds, natural
scene/input histories and whole-feature/NPC acceptance remain open. Original NPC
behavior, optional mods and AI-assisted development tools remain separate.
