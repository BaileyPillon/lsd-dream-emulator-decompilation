# Native decoder entries during the history reel

The original Japanese disc and the matching-C disc produce identical native
decoder-entry journals during the prepared-card history reel: **10,125 accepted
stream callbacks, 10,125 VLC entries and 10,124 MDEC input entries**. Both runs
also agree across **62,530 frames, 105 unmasked complete-state observations** and
all recorded full-buffer output windows. The entry sequence identifies all
twenty `SPDAY01A` through `SPDAY10B` films against the canonical source corpus.
[Machine-readable evidence](native-reel-decoder-checks.json) binds the executed
host, canonical ranges, source hashes, captures and analysis controls.

The first nineteen films reach every encoded frame ID at VLC and MDEC input
entry. The final film has 500 encoded frames: IDs 1–492 reach VLC, IDs 1–491
reach MDEC input, and IDs 493–500 never reach either entry before the timed stop.
Its last decoded work buffer has no subsequent MDEC input call. This cutoff is
observed in the original game and reproduced by the rebuilt disc.

These are **function-entry and buffer-association observations**. They do not
establish completed MDEC DMA, full encoded/RLE payload identity or presentation
of every encoded frame on the GPU. The retained external card has constructed
history; it does not establish naturally earned chart progression.

| Evidence scope | Before | After |
| --- | ---: | ---: |
| Compared native reel decoder profiles | 0 | 1 |
| Uniquely attributed reel source films | 0 / 20 | 20 / 20 |
| Reel films reaching all source IDs at both VLC and MDEC input entry | Unmeasured | 19 / 20 |
| Distinct direct native movie start-file bindings | 9 / 39 | 9 / 39 |
| Matching game C bytes | 199,912 / 199,912 | 199,912 / 199,912 |
| Provisional feature groups / recovered NPC callbacks | 40 / 107 | 40 / 107 |
| Accepted whole features / whole NPC encounters | 0 / 0 | 0 / 0 |

The prior eight startup payloads and this twenty-film reel are different source
identities, but only nine direct native start-file bindings have been observed.
Attribution within a concatenated stream is not a new start-file request. Earlier
inventory entries and measurements remain unchanged; the new overlay extends
F022/F032 evidence. The exhaustive original feature total remains unknown. This
study adds no game behavior, matching-C bytes or model API calls.

## What was observed

The separately qualified native observer records actual entries to:

| Original function | Address | Checked body bytes | Entries per run |
| --- | --- | ---: | ---: |
| `str_stream_invoke_callback` | `0x800477B0` | 96 | 10,125 |
| `func_80046568` | `0x80046568` | 80 | 10,125 |
| `DecDCTin` | `0x80045F84` | 124 | 10,124 |

The host checks the complete original function body on every entry. Each record
retains the actual direct caller instruction, delay-slot instruction, return
address, arguments, stack, frame, timestamp bits, active-movie pointer, SDK
indices, source first word and function size. The Python reader validates these
against [canonical target metadata](../research/headless/reel-decoder-targets.json).
Checking a body hash is not tracing execution of every instruction in that body.

The stream callback's actual frame ID and ring-buffer pointer are associated
with the subsequent VLC input. At VLC entry, a SHA-256 fingerprint of the first
44 encoded bytes identifies candidates in the disc corpus. The VLC destination
is then associated with the later `DecDCTin` input pointer, mode 2 and command
header. Reuse without submission, missing pairs, changed callers, invalid
pointers and source-prefix mismatches are rejected. In the JSON, the historical
field name `MDEC_submissions` counts **entries to `DecDCTin`**, not completed DMA.

All 39 movie extents are read directly from the original disc. Their complete
mixed-sector hashes, frame/chunk ordering, sizes, sector types and subheaders
are checked against the existing movie inventory. The corpus contains 22,382
encoded frames and 21,281 distinct ID/prefix keys. Of those keys, 480 occur in
multiple files, including identical black frames. The intersection across each
observed segment identifies one source film; film endpoint lengths are reported
separately and are not used to force an identity.

| Source film | Encoded source frames | VLC entries | MDEC input entries |
| --- | ---: | ---: | ---: |
| `SPDAY01A.STR` | 485 | 485 | 485 |
| `SPDAY01B.STR` | 877 | 877 | 877 |
| `SPDAY02A.STR` | 537 | 537 | 537 |
| `SPDAY02B.STR` | 455 | 455 | 455 |
| `SPDAY03A.STR` | 409 | 409 | 409 |
| `SPDAY03B.STR` | 589 | 589 | 589 |
| `SPDAY04A.STR` | 274 | 274 | 274 |
| `SPDAY04B.STR` | 551 | 551 | 551 |
| `SPDAY05A.STR` | 576 | 576 | 576 |
| `SPDAY05B.STR` | 335 | 335 | 335 |
| `SPDAY06A.STR` | 446 | 446 | 446 |
| `SPDAY06B.STR` | 534 | 534 | 534 |
| `SPDAY07A.STR` | 532 | 532 | 532 |
| `SPDAY07B.STR` | 533 | 533 | 533 |
| `SPDAY08A.STR` | 660 | 660 | 660 |
| `SPDAY08B.STR` | 461 | 461 | 461 |
| `SPDAY09A.STR` | 475 | 475 | 475 |
| `SPDAY09B.STR` | 483 | 483 | 483 |
| `SPDAY10A.STR` | 421 | 421 | 421 |
| `SPDAY10B.STR` | 500 | 492 | 491 |

The observer arms before input frame 21,884. Actual entries span frames 21,929
through 62,347; the existing native journal observes reel removal at 62,349.
Input IDs are contiguous from one in each segment. There is one pending decoded
buffer at the end: final-film ID 492. The first nineteen segments reach their
source endpoints and have matching MDEC input counts.

## Qualification and retained limits

This study reuses the [qualified CD-error observer](CD_ERROR_RESET_RECOVERY.md)
and the previous [stock card/reel capture](CARD_REEL_PLAYBACK.md). No native core,
disc or complete runtime is rebuilt or copied. The capture host composes the
existing observer DLL directory with the complete stock game database through
directory links; ordinary runtime contents match the frozen stock inputs.

All six full-buffer output channels—MainRAM, GPU RAM, RGB with dimensions,
returned PCM, native observations and controller inputs—match stock for both
observer runs. The native journal, four decoded PNGs, card input and dimensions
also match. Stock and observer complete serialized-state hashes differ in all
105 windows because their native core bodies differ. Those hashes remain
unmasked and their differences are reported. Output equality does not establish
stock/observer state equality. Observer-original and observer-rebuilt complete
states and decoder journals do match.

The original recording was reviewed before the rebuilt replay started. That
review's timestamp, file timestamp and original private reader are retained.
The review did not embed its reader hash; its reader is hash-bound at publication,
with its earlier file timestamp recorded. The final public reader independently
rechecks both saved captures. Seventeen faults in copies of actual parsed or
compared evidence are detected; ten synthetic unit tests cover the wire format,
caller/context validation, associations, source matching and scope distinctions.
Neither kind of control changes a retained capture or the game.

Two earlier incomplete attempts remain in the private record: a 714-frame owned
stop after an exclusive-file reader error, and a v1 trace that stopped at its
compressed entry bound with 13,730 partial entries. They are not complete-run
parity evidence. The compact format removes repetitive transport fields and
encodes numeric deltas losslessly; it preserves every selected entry and its
timestamp bits. No selected events are sampled out. Each completed trace is
441,973 compressed bytes, representing 1,125,387 event bytes plus its header.

## Reproduce with your own inputs

Prepare a separate QA card as described in [the prior profile](CARD_REEL_PLAYBACK.md).
Compile [RecordCardDecodeCompactWindows.cs](../research/headless/RecordCardDecodeCompactWindows.cs)
with `ReplayColdStart.cs` and `BoundedSha256Stream.cs`, x64, using
`/main:Lsd.Research.Headless.RecordCardDecodeCompactWindows` and the existing
[headless references and configuration](COLD_MOVIE_WINDOWS.md#reproduce-and-inspect).
Use a runtime with the qualified method-entry observer ABI, not the stock core.
Reuse the complete stock database and installed libraries; do not copy their trees.

```text
RecordCardDecodeCompactWindows.exe RUNTIME ORIGINAL.cue BIOS-J BIOS-U BIOS-E NEW-ORIGINAL card-reel 62529 - PREPARED.SaveRAM
```

Review the original entries, source matches, full stock outputs and images before
recording the rebuilt disc. Its invocation uses a new folder, the rebuilt cue
and the saved original `inputs.tsv` in place of `-`. Keep the existing wall-time,
memory, process-ownership and aggregate-output supervision. Never recapture an
existing route merely because a historical payload was archived.

The host refuses existing output files, limits entries to 40,000, raw decoder
events to 32 MiB and compressed decoder output to 786,432 bytes per run. Native
journal bounds remain those of the previous host. The private study's aggregate
capture limit is 4 MiB, including its incomplete attempts. The owned `STOP` file
terminates a run, and stopped recordings are rejected as complete evidence.

```powershell
python -B tools/inspect_reel_decoder.py NEW-ORIGINAL NEW-REBUILT --disc ORIGINAL.bin --stock STOCK-ORIGINAL --output NEW-REPORT.json
python -B -m unittest tests.test_reel_decoder -v
```

The reader creates no movie extraction tree and refuses an existing output
report. Return codes are 0 for equality within the stated scope, 1 for retained
differences, and 2 for invalid or incomplete inputs. The entry stream has header
`LSDDEC2\0`, a target tag and 21 per-target signed-delta/zigzag/varint-encoded
32-bit words per event. VLC records additionally contain the 32-byte SHA-256
fingerprint. The reader checks canonical varints, bounds and gzip integrity.

Full native encoded/RLE payload hashes, individual frame presentation, original
hardware timing, naturally earned/repeated/disabled/missing-cell histories,
other special-day and ending branches, and complete gameplay/NPC acceptance
remain open. The canonical playable build and its saves are retained. Original
game behavior remains separate from optional mods and AI-assisted analysis.
