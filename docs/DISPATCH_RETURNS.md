# Original file-driver returns and synchronous buffers

The optional return observer follows all **176 recorded CD Open/Read calls**
back to their original callers. It also records 14 nested synchronous reader
calls and compares their complete destination buffers with the original disc.
This extends the [executed slot-load evidence](DISPATCH_SLOT_FLOW.md) without
changing the matching game or its C-recovery count.

| Measure | Slot-load checkpoint | Return checkpoint |
| --- | ---: | ---: |
| Compared CD Open/Read entries | 176 | 176 |
| Qualified receiver/table/slot combinations | 36 | 36 |
| Compared original method returns | 0 | 176 |
| Compared synchronous helper returns | 0 | 14 |
| Synchronous destination buffers checked against disc | 0 | 14 |
| Complete requested bytes checked against disc | 0 | 1,007,616 |
| New matching C bytes | 0 | 0 |
| Whole feature groups accepted | 0 | 0 |

## What is verified

Each return has a matching entry ID, original arguments, caller PC, restored
stack pointer and actual `JR RA` plus delay-slot observations. The verifier
checks the original instruction words against both observed RAM and the
effective instruction-cache word. Nested entries and returns must be ordered,
properly parented and balanced; missing, duplicate or unfinished calls fail.
The existing complete-method entry and caller-load traces remain mandatory.

The base set contains 64 CD Open and 112 CD Read calls. The additional helper
is `cd_file_driver_read_sectors` at `0x80028A84`. Its complete 224-byte original
body is independently qualified by the [compiler census](UNUSED_LOCAL_CENSUS.md)
and captured at each helper entry. It remains separate from the four selected
base methods and the 838-target declared-table catalogue.

For each of the 14 synchronous calls, the trace also records the original
request-wrapper entry, arguments, polling entry and final polling return.
Original caller instructions, return boundaries and fixed stack frames must
agree. Each observed final `CdReadSync` result is zero. The helper and enclosing
Read also return zero; **these result words are not transferred-byte counts**.
Open results are retained as raw words without a new interpretation.

The verifier derives the expected file position and logical size from the
receiver captured **at the enclosing Read entry**, before using return data.
Those inputs must agree with the helper's entry snapshot and the disc's ISO
metadata. The original full-file caller requests:

```c
((file_size >> 11) + 1) << 11
```

All requested bytes must match the verified raw MODE2 Form1 sectors, and the
helper's buffer must still be identical when the enclosing Read returns.
The 14 files account for **989,184 logical bytes and 18,432 trailing bytes**.
None of these files is sector-aligned, so a completely additional sector for
an aligned file is covered by an owned synthetic fixture, not this native run.
The logical portions were also checked against the earlier, separately
extracted and hashed files. This second audit does not use the new ISO parser.

The other 98 Read returns retain complete requested RAM snapshots. Their
queued or direct framed transfers are **not accepted as completed I/O** by
this profile. Error paths, Open filename resolution, other resources and
asynchronous completion remain open.

## Recorded comparisons

Three isolated cold boots use the same 6,000-input route: original disc with
the observer, rebuilt disc with the observer, and original disc with the
distributed core. Original/rebuilt entry, flow, return and payload streams
agree byte for byte. Both required comparisons also agree on all recorded
game outputs:

- 6,001 complete GPU-memory observations and 1,117 RAM hashes per run;
- 178 complete RAM, GPU and RGB checkpoints per run;
- 17,692,008 bytes of complete PCM per run.

A second audit parses the numeric return layout independently and decodes
all 534 checkpoint PNGs back to the retained RGB. It checks every requested
sector byte and all 14 logical files against the older extraction inventory.
Eighteen in-memory retained-data faults are rejected, including a wrong
trailing byte in otherwise equal helper/parent buffers. These are verifier
corruption controls, not executed modifications of original game instructions.
Twenty source-only tests use owned MIPS and disc fixtures. The full Windows
and Linux suites each pass 1,054 tests with two expected skips.

The observer arms at relative frame 900, before the first watched entry at
967. Output comparisons include the entire boot, including earlier frames.
The [earlier frame-zero hook discrepancy](DISPATCH_ENTRY_TRACE.md) is retained
and unresolved. These passing runs establish the recorded output comparison;
they do not establish general observer transparency, complete emulator-state
equality or original PlayStation timing.

The first return-host attempt failed before game-frame recording because its
seven-argument native configuration exceeded the adapter's marshalling limit.
The retained failure is superseded by separate three- and four-argument setup
calls, a rebuilt observer and fresh captures from the published sources.

## Reproduce with private inputs

Use the pinned native checkout, verified original/rebuilt cold-start captures
and 64-bit Windows runtime described in [method-entry recording](DISPATCH_ENTRY_TRACE.md).
Build a new observer in Linux/WSL:

```bash
python tools/build_dispatch_observer.py \
  --source-root /path/to/pinned-native-source \
  --output .decomp-lab/return-observer-new --returns
```

`--returns` includes the caller-flow extension. This compiles one new adapter
and relinks the pinned cached native objects; it is not a fresh full-core
rebuild. The build profile retains `runtime_verified: false`. Runtime checks
are separate evidence. Original CPU source and guest RAM remain read-only.

Record fresh original and rebuilt workspaces using
`research/headless/file-driver-return-route.json` and that observer profile.
Record a third original workspace without `--observer-profile`. Use the
commands in [the slot-load workflow](DISPATCH_SLOT_FLOW.md), substituting the
return route and fresh paths. Then run both comparisons:

```powershell
python tools/inspect_dispatch_history.py `
  --reference D:/private/return-original-new `
  --candidate D:/private/return-rebuilt-new --mode same-runtime `
  --output .decomp-lab/return-paired-new.json

python tools/inspect_dispatch_history.py `
  --reference D:/private/return-stock-new `
  --candidate D:/private/return-original-new --mode observer-output `
  --output .decomp-lab/return-stock-new.json
```

Keep the original raw track available: inspection rehashes it before and after
the buffer check. The optional protocol uses 600-byte return records, up to
1,024 returns and 8 MiB of payload per frame, with at most 64 pending calls.
Missing payloads, overflow or unmatched calls fail qualification. Earlier
entry-only and flow-only histories remain inspectable with their retained
source identities; a distributed capture supplies no method records.

## Remaining gates

Matching C remains **197,172 / 199,912 bytes (98.63%)**. Two functions remain
in assembly and three inherited storage explanations remain unresolved,
including this synchronous reader's 2 KB local buffer. There are 40 provisional
feature groups and 38 with their listed core functions in C; the exhaustive
original feature total is unknown. Whole-feature and whole-NPC acceptance
remain zero. This trace closes no complete file-driver feature or encounter.

Continue asynchronous completion, SDK/disc errors, other callbacks and file
histories, source recovery, and the broader original-game parity gates. This
analysis tool calls no model API and adds no NPC behavior. Optional AI-assisted
analysis and modding remain separate from original game behavior. The matching
playable build and the separate Bevy project retain their existing identities.

[Validation metadata](dispatch-return-checks.json) publishes bounded counts,
source hashes and evidence identities. Game images, original code dumps,
destination buffers, BIOS files and raw emulator captures remain private.
