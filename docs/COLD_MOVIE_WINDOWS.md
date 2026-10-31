# Cold movie playback and controller skips

Three original-disc cold starts and their exact-input rebuilt replays agree
across **14,995 paired emulated frames** and **27 complete-state observations**.
The routes cover normal startup, skipping the logo, and skipping the selected
opening. Every advanced frame contributes complete MainRAM, GPURAM, RGB, returned
PCM, native movie fields and submitted controls to framed hash windows.

The six native processes exited successfully. All retained windows, native
observations, inputs, lifetimes and decoded final images agree. This adds
bounded F001/F032/F035 evidence; **whole-feature and whole-NPC encounter
acceptances remain zero**. Matching game C stays 199,912 / 199,912 bytes.
[Machine-readable evidence](cold-movie-window-checks.json) records the executed
sources, original function bindings, comparisons, controls and private capture
fingerprints.

Working-file and Git-blob source hashes are recorded separately. The unchanged
`str_stream.c` working text uses CRLF while its Git blob uses LF; its full text
was checked for that sole representation difference.

## Observed routes

All three routes select `OPENINGG.STR`; this covers **one of seven opening
choices and two of 39 routed movie payloads**, including `ASMK.STR`. The
original policy submits ordinary Circle inputs for the skip cases. The rebuild
uses the original's exact run-length input record. Each run begins with a new
qualified Nymashock instance, loads no state, writes no game RAM/instructions,
and leaves the interactive player and its saves untouched.

| Original/rebuilt pair | Frames each | State pairs | Returned stereo sample frames each | Circle pulse starts |
| --- | ---: | ---: | ---: | ---: |
| Normal startup | 6,324 | 11 | 4,661,097 | None |
| Skip logo | 6,042 | 11 | 4,453,224 | 1,338 |
| Skip opening | 2,629 | 5 | 1,937,375 | 2,446 |

Every pulse lasts twelve frames. In the logo case the previous sample reports
encoded ID 20; in the opening case it reports ID 120. The input frame is
zero-based and core frame is input frame plus one. Recordings continue for
180 frames after the first opening's active pointer clears. Their final
images show the original Day 001 menu; two were also visually inspected.

Normal logo streaming samples every accepted ID from 0 through 89. The opening
samples 0 through 1,045. Requested thresholds remain 90 and 1,046 respectively.
The [movie inventory](MOVIE_INVENTORY.md) distinguishes these native thresholds
from encoded file tails and the final image presented by the decoder.

## Forced-stop lifecycle

The new skip recordings expose a transition outside the older neutral-only
reader's contract. The stream is already closed while the MDEC movie pointer
is still active. The next sampled update clears that pointer:

| Route | Circle input | Closed stream, pointer still active | Pointer cleared | Last accepted ID |
| --- | ---: | ---: | ---: | ---: |
| Skip logo | 1,338 | 1,338 | 1,339 | 20 |
| Skip opening | 2,446 | 2,447 | 2,448 | 120 |

Original `func_80045A38` sets both MDEC stop fields, disables looping and calls
the stream's close slot. `str_stream_close` resets stream state to zero.
`func_80045CFC` takes its terminal branch, whose `func_80045C94` clears the active
movie pointer. Four complete function ranges and four vtable words were checked
against the canonical executable and the original function index. These are
source/static bindings plus sampled fields, without an instruction-entry trace.

The legacy lifetime summary's `decode_complete_flag_observed` records the field
at movie offset `0x44`. Forced stop sets this field too; its interpretation
requires the retained stream IDs and lifecycle, with full-movie decode
acceptance still separate.

The new reader accepts this closed transition only with both original stop
flags set, looping disabled, the previous streaming object/counter retained,
the pointer absent in the next sample, and a matching twelve-frame controller
pulse for that movie. Neutral recordings reject it. All raw observations remain
retained. The [existing startup reader](MOVIE_PLAYBACK.md) and its earlier
neutral recording are unchanged.

The first saved-data reader rejected the closed state. Its source and rejection
remain preserved; the native recordings were reused unchanged after the
explicit lifecycle extension. Native buffers and state bytes are never masked.

## Streamed comparison contract

Windows cover consecutive groups of 600 frames, followed by the exact final
partial group. Every channel record prefixes its payload with three signed
little-endian 32-bit words: input frame, core frame and payload byte length.
RGB payloads begin with signed 32-bit width and height followed by row-major
8-bit RGB. PCM contains every returned signed 16-bit stereo sample. Empty PCM
returns still contribute their frame headers.

| Complete payload coverage, per side across the three routes | Bytes |
| --- | ---: |
| MainRAM | 31,446,794,240 |
| GPURAM | 15,723,397,120 |
| RGB, including dimensions | 5,830,492,760 |
| Returned PCM | 44,206,784 |

Each window ends with an unmasked serialized-state hash and final RAM/GPU/RGB
hashes. The host saves each state twice and checks stable hashes, unchanged
RAM/GPU and an unchanged core frame. The offline reader independently rebuilds
the framed native/control hashes from retained observations and rejects gaps,
overlaps, missing channels, wrong byte counts or absent state observations.

Nine controls on copies of the actual analysis data detect missing stop flags,
closed transitions in a neutral profile, missing RAM bytes/state/native rows,
and changed GPU or serialized-state hashes. No game or runtime code is altered
for those controls. Synthetic tests separately cover framing, schema, lifecycle,
input binding and retained mismatches.

Only hashes, compressed native fields, input changes, reports and final PNGs are
retained. The complete six-run capture, logs and process/exit receipts occupy
494,021 logical bytes. Full RAM, video and audio dumps are not retained; a
mismatch is localized to its recorded window rather than an individual lost
buffer byte. Raw native journals decompress in memory for analysis.

## Reproduce and inspect

The Windows source is
[RecordMovieWindows.cs](../research/headless/RecordMovieWindows.cs). Compile it
with `ReplayColdStart.cs` and `BoundedSha256Stream.cs`, selecting
`/main:Lsd.Research.Headless.RecordMovieWindows`, x64, .NET Framework 4.8
references and the same BizHawk 2.11.1 assembly references described in the
[isolated replay workflow](HEADLESS_REPLAY.md). The recorded build uses .NET
SDK 8.0.424's Roslyn compiler with deterministic compilation and warnings as
errors. Keep the executable's `dll` directory linked to the shared qualified
runtime and use its existing binding configuration as the `.exe.config`.

The runtime argument supplies that shared installation's `dll` and `gamedb`.
Pass your own J/U/E BIOS files and complete Japanese disc. Pin these inputs
before execution, keep new captures private, and retain process identities and
exit codes. Example argument order for a compiled host:

```text
RecordMovieWindows.exe RUNTIME DISC.cue BIOS-J BIOS-U BIOS-E NEW-OUTPUT neutral 8000 -
```

Modes are `neutral`, `skip-logo` and `skip-opening`. A replay substitutes the
original report's `last_frame` for 8000 and its `inputs.tsv` path for `-`.
The recorder refuses existing output directories, caps native journals and
frame count, and honors an owned output directory's `STOP` file. External
supervision must retain wall-time, memory and aggregate-output guards.

Analyze a completed original/rebuilt pair with no emulator or game data:

```powershell
python -B tools/inspect_movie_windows.py `
  D:\private\movie-original D:\private\movie-rebuilt `
  --output D:\private\movie-comparison-new.json
```

The reader returns 0 for equality within this recorded scope, 1 for retained
differences and 2 for invalid/incomplete input. Producer/runtime fingerprints
are a separate provenance check. The recorded runs reuse the
[qualified initialized-media core](SERIALIZED_CORE_STATES.md); stock-core
state differences must be retained rather than silently normalized.

All other openings, special-day/reel/event/ending movies, disabled playback,
I/O failures, every skip timing, exact encoded-frame presentation and original
hardware timing remain open. The [natural-year comparison](NATURAL_YEAR_ENDING.md)
has its own ending observations. Original NPC behavior, optional mods and
AI-assisted analysis remain separate; this work invokes no model API.
