# Full native movie buffers through the history reel

The original Japanese disc and the matching-C disc agree on **30,374 complete
backing-RAM buffer observations**, hashing **944,165,108 payload bytes per run**.
Both also agree across 62,530 emulated frames, 105 unmasked complete-state
observations, every full-buffer output window and all four decoded PNGs.
[Machine-readable evidence](full-movie-payload-checks.json) records sources,
native build qualification, capture hashes and analysis controls.

This extends the [entry/prefix study](NATIVE_REEL_DECODER.md). Full encoded
inputs now match the original disc's complete frame hashes. Complete VLC output
ranges match the later `DecDCTin` input ranges, and both runs reproduce the final
timed cutoff. Completed hardware DMA and individual encoded-frame presentation
on the GPU remain separate, unaccepted gates.

| Observed boundary | Buffers per run | Complete bytes hashed per run | Size definition |
| --- | ---: | ---: | --- |
| Encoded input at VLC entry | 10,125 | 144,094,224 | Accepted native STR header's encoded size |
| RLE output at actual VLC return | 10,125 | 400,039,092 | Command word plus its declared 32-bit words |
| RLE input at `DecDCTin` entry | 10,124 | 400,031,792 | The same complete command/data range |

The size range is 2,712–18,144 encoded bytes and 7,300–64,388 RLE bytes in this
profile. Every observed command's word count is a multiple of 32, matching the
original SDK's DMA block granularity. This is input-range evidence, rather than
observation of completed DMA.

| Measurement | Before this study | After |
| --- | ---: | ---: |
| Complete native buffers compared at these boundaries | 0 | 30,374 |
| Complete native payload bytes compared per side | 0 | 944,165,108 |
| Distinct reel source films identified by recorded inputs | 20 / 20 | 20 / 20 |
| Matching game C bytes | 199,912 / 199,912 | 199,912 / 199,912 |
| Provisional feature groups / C-recovered NPC callbacks | 40 / 107 | 40 / 107 |
| Accepted whole features / whole NPC encounters | 0 / 0 | 0 / 0 |

Earlier values remain historical measurements. The new overlay extends F022/F032;
it adds no gameplay feature, matching-C byte, developer-capability category or
model API call. The exhaustive original feature total remains unknown. Original
NPC behavior and optional AI-assisted analysis/modding tools remain distinct.

## Accepted headers, completed outputs and the timed stop

The native hook observes the accepted stream callback and records its actual
frame ID, SDK header and ring pointer. Its address calculation is checked against
the original `StGetNext`. At `func_80046568` entry, it copies the full encoded
range before the guest continues. The host hashes every copied byte.

At the wrapper's observed return-jump and delay PCs, the observer records the
canonical RAM words and checks the stack/return registers. Once the caller PC
resumes with its restored stack, the observer copies the complete destination
range. It associates that completed output with the later `DecDCTin` entry and
requires equality of the full-buffer hash, size, command and source identity.
The return evidence consists of CPU PCs/registers and RAM words; it is not a
complete instruction-fetch or instruction-execution trace.

All 39 source movie extents and their complete frame/chunk streams are checked
against the existing inventory. The full encoded source corpus contains 22,382
frames. Complete native input hashes, native sizes, IDs, dimensions and quantizer/
version fields select candidate source frames; sequence intersections uniquely
identify all twenty reel films. Repeated identical frames remain ambiguous until
the sequence resolves them. Endpoint lengths do not force source identities.

The first nineteen films reach every source ID at all three boundaries.
`SPDAY10B.STR` contains 500 frames. IDs 1–492 reach VLC entry and return;
IDs 1–491 reach `DecDCTin`. Its completed frame-492 RLE output is **7,300 bytes**,
observed at emulated input frame **62,348**. Its full SHA-256 is retained in the
evidence. Reel removal follows at 62,349, with that one completed output still
awaiting a later MDEC input call. IDs 493–500 are not reached. Both discs exhibit
this original timed behavior; the last source film is not expected to reach EOF
under this interval.

The [prepared external card](CARD_REEL_PLAYBACK.md) and its constructed history
are unchanged. Its Load UI, ordinary dream, chart event, reel and post-reel
interval are all retained. Naturally earning that history remains open.

## Separate observer and storage qualification

The new native observer is built as one adapter object linked with pinned cached
BizHawk/Mednafen objects. Its complete source, compiler/input hashes, uncompressed
core hash and compressed core hash are recorded. The original CPU source and
installed player remain unchanged. It uses the existing read-only DebugMode hook;
it reads backing MainRAM and writes only its separate host transport buffers.

The QA runtime links the existing DLLs and complete stock game database. Its
ordinary contents match the complete stock set; the separate observer core is
the qualified difference. All frozen native inputs and runtime/disc/BIOS/compiler
records are rehashed before and after both runs.

All six complete output channels—MainRAM, GPU RAM, RGB with dimensions, returned
PCM, native observations and submitted controls—match stock on both runs.
Stock/observer serialized-state hashes differ in all 105 windows; these are
different cores with different observation state. Those hashes remain unmasked
and the differences remain explicit. Original/rebuilt states under the same
observer match completely.

The rebuilt host independently generates its compressed full-payload journal in
a fixed 1.5 MiB memory buffer. After generation, it compares **every compressed
byte** with the reviewed original journal. Only exact equality permits an
immutable hard link; different generated bytes are retained independently.
The reference journal participates in storage comparison. Guest inputs remain
the disc, BIOS, QA card and controller replay. This avoids a second allocated
copy while retaining the full independently generated comparison result.

The original was independently inspected before replay. The exact checker used
for that review is retained losslessly with its complete hash. Twenty-one faults
in copies of actual saved analysis/comparison data are detected. Twelve synthetic
native-transport cases and nine Python journal tests separately cover bounds,
return association, source ambiguity, lossless encoding and changes beyond the
old 44-byte prefix. The complete Windows suite passed 1,683 tests with 16 skips;
WSL passed 1,680 with 12 skips. These tests support their stated layers.

## Reproduce with local game inputs

Use the pinned native checkout, recorded media adapter and a current cached
release build as described in [the native observer setup](CD_ERROR_RESET_RECOVERY.md).
In Linux/WSL, build a new observer directory:

```sh
python -B tools/build_movie_payload_observer.py --source-root PINNED-NATIVE-SOURCE --output NEW-OBSERVER
```

Create a separate QA runtime view using linked installed DLLs and the complete
stock game database. Put the new compressed core at `dll/shock.wbx.zst`; keep an
expanded `dll/shock.wbx` absent so it cannot shadow that core. The builder records
its cached-object scope; it does not claim a fresh full-core rebuild.

Compile [RecordCardPayloadWindows.cs](../research/headless/RecordCardPayloadWindows.cs),
[MoviePayloadTrace.cs](../research/headless/MoviePayloadTrace.cs), `ReplayColdStart.cs`
and `BoundedSha256Stream.cs`, x64, with
`/main:Lsd.Research.Headless.RecordCardPayloadWindows` and the qualified
[Windows references/configuration](COLD_MOVIE_WINDOWS.md#reproduce-and-inspect).
Use your complete Japanese disc, BIOS files and separately prepared QA card.

```text
RecordCardPayloadWindows.exe RUNTIME ORIGINAL.cue BIOS-J BIOS-U BIOS-E NEW-ORIGINAL card-reel 62529 - PREPARED.SaveRAM
```

Inspect the original and its images before recording the rebuilt disc:

```powershell
python -B tools/inspect_movie_payloads.py NEW-ORIGINAL --disc ORIGINAL.bin --stock STOCK-ORIGINAL --output ORIGINAL-REVIEW.json
attrib +R "NEW-ORIGINAL\payload-entries.bin.gz"
```

Run the rebuilt cue into a new folder, replacing `-` with
`NEW-ORIGINAL/inputs.tsv`. Then compare:

```powershell
python -B tools/inspect_movie_payloads.py NEW-ORIGINAL NEW-REBUILT --disc ORIGINAL.bin --stock STOCK-ORIGINAL --output NEW-COMPARISON.json
python -B -m unittest tests.test_movie_payload_observer tests.test_movie_payloads -v
```

Both journals retain lossless per-target signed-delta/zigzag/varint numeric
records. `payload-entries.bin.gz` adds a full-range SHA-256 to each 43-word native
record; its header is `LSDMOV1\0`. The older prefix journal separately retains
each original entry/body qualification. The reader checks gzip integrity,
canonical varints, native/source joins, complete byte totals and hash chains.

Bounds are 16 native payload events and 1 MiB of copied transport data per frame;
40,000 records and 32 MiB of raw journal bytes per run; and 1,572,864 compressed
payload-journal bytes. The retained pair's aggregate capture limit is 6 MiB,
including any incomplete attempts. Keep the existing wall-time, memory,
process-ownership and storage guards. Existing outputs are refused and an owned
`STOP` remains incomplete evidence. The checker returns 0 for equality in scope,
1 for recorded differences and 2 for invalid/incomplete evidence.

Remaining work includes hardware DMA completion and individual frame
presentation, other movie/event/ending routes, naturally earned and repeated/
disabled/missing-cell histories, and complete gameplay/NPC acceptance. The
canonical playable build and user saves remain available. The full goal is active.
