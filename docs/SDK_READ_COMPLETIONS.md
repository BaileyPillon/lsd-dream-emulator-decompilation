# Original SDK read completions

The optional read observer now follows actual SDK requests through successful
poll returns and compares their complete destination RAM with the original
Japanese disc. The 6,000-frame original/rebuilt profile qualifies **102 completed
reads**, including the **49 queued Read handoffs** identified previously.
Matching C remains **197,172 / 199,912 bytes (98.63%)**; this adds runtime evidence
and analysis tools, with no game-code promotion or whole-feature acceptance.

| Evidence | Earlier return/handoff profiles | This SDK profile |
| --- | ---: | ---: |
| Queued Read origin/replay pairs | 49 | 49 |
| Those pairs linked to actual SDK completion | 0 | 49 |
| Complete SDK boundary transcripts in this profile | 0 | 1,199 |
| Completed SDK transfers in this profile | 0 | 102 |
| SDK-completion RAM bytes compared in this profile | 0 | 4,593,664 |
| Matching game C bytes | 197,172 | 197,172 |
| Accepted complete feature groups | 0 | 0 |

The earlier synchronous-helper profile already qualified 14 requested buffers;
its evidence is retained in [Original method returns](DISPATCH_RETURNS.md).
Those reads are included in this broader SDK profile, rather than counted as
new original-game features.

## Observed original behavior

The six selected SDK functions have complete ranges qualified by a canonical
306-object symbolic link and independent GNU symbol extents. The observer
captures their actual entries, returns, arguments, complete entry code, stack
and return addresses, executed JAL/JR operands and delay slots, instruction-cache
context, and SDK RAM words. The 1,199 balanced calls comprise 102 requests,
912 poll returns, 119 control calls and 66 synchronization calls. Of the polls,
810 return busy and 102 return success. There are no lost records, overflows,
pending calls, pending transfers, overlapping requests or unassociated polls.

At each successful zero-valued poll return, the observer copies the original
request destination for the original sector count times 2,048 bytes. It also
checks the SDK's unchanged request count/base and advanced destination cursor.
The observed word at `0x8006D8E0` is the request count; it is not treated as a
decrementing remaining-sector counter.

| Original request call | Completed reads | Full-sector RAM bytes compared |
| --- | ---: | ---: |
| `0x8002866C`, queued Read state | 49 | 3,506,176 |
| `0x80028AF4`, synchronous helper | 14 | 1,007,616 |
| `0x800287CC`, second driver read state | 3 | 6,144 |
| `0x8002BFE4`, other SDK caller | 36 | 73,728 |
| **Total** | **102** | **4,593,664** |

Disc positions come from **104 observed successful Setloc calls**, followed by
the sector counts of completed original reads. Reusing a receiver's cached
starting location for every sequential read would give incorrect positions.
Every completed sector window matches the verified raw MODE2 Form1 track,
including its header position and data. The profile covers 2,032 distinct disc
sectors; repeated reads remain repeated observations, not new content.

All 49 queued pairs are linked in instruction order: originating Read, FIFO
replay, replay return with the driver busy, original SDK request, and successful
SDK completion before the next replay. Receiver/destination arguments retain
their earlier qualification. The original Read path passes `byte_length >> 11`
as the sector count. Its argument words sum to 3,525,008 bytes; 18,832 tail bytes
lie outside those full-sector transfers and are not credited as completed RAM.
The Read result word remains a status word, not a byte-transfer count.

## Reproduce locally

Supply your own verified disc, BIOS and existing cold-boot capture as described
in [Playing](PLAYING.md) and [Headless replay](HEADLESS_REPLAY.md). Original game
data, RAM payloads, captured code and emulator binaries are not distributed.

Build a separate analysis core in the qualified Linux/WSL environment:

```sh
python tools/sdk_reads.py --export-ranges .decomp-lab/sdk-ranges-new
python tools/build_dispatch_observer.py \
  --source-root /private/pinned-bizhawk-source \
  --output .decomp-lab/sdk-observer-new --sdk-reads
```

The range exporter independently reproduces the checked SDK boundaries in
`research/sdk_reads/sdk-function-ranges.json`. The core builder compiles one
adapter and links the recorded cached native objects; this is not a fresh
full-core build. It leaves the original CPU source and supplied runtime intact.

Record original and rebuilt discs, and a distributed-core control, in separate
new Windows workspaces. Use the same command for each disc capture; omit
`--observer-profile` for the distributed control:

```powershell
python tools/record_dispatch_history.py `
  --capture-folder D:/private/cold-boot-original `
  --workspace D:/private/sdk-original-new `
  --program research/headless/file-driver-sdk-route.json `
  --observer-profile .decomp-lab/sdk-observer-new/profile.json

python tools/inspect_sdk_reads.py `
  --reference D:/private/sdk-original-new `
  --candidate D:/private/sdk-rebuilt-new `
  --output .decomp-lab/sdk-comparison-new.json

python tools/inspect_sdk_reads.py `
  --reference D:/private/sdk-original-new `
  --candidate D:/private/sdk-distributed-new `
  --mode observer-output `
  --output .decomp-lab/sdk-observer-control-new.json
```

## Verification and remaining gates

All three cold boots use the same 6,000 controller inputs. Original/rebuilt SDK
records and complete code/RAM payloads are byte-identical. Both original/rebuilt
and observer/distributed comparisons pass all 6,001 recorded GPU observations,
1,117 RAM observations, 178 complete RAM/GPU/RGB checkpoints and 17,692,008 PCM
bytes per run. An independent numeric-layout and sector parser agrees, rehashes
114 source snapshots, and independently decodes all 534 PNGs against their RGB
payloads. Twenty retained-data faults are rejected; these are parser controls,
not executed game-instruction fault injections. Twenty owned SDK tests cover
sequential cursor progression and invalid evidence. Two additional tests guard
the earlier return-only host's optional-null settings compatibility. Both
platform suites pass **1,090 tests**, with two expected skips each. A separate
2,000-frame return-only run and the older retained 6,000-frame return capture
also pass their original inspections.

The observer uses read-only CPU/cache peeks and RAM copies. Its hook arms at
frame 900 while comparisons include the whole boot. The earlier frame-zero
observer discrepancy remains documented; it is not excused by a tolerance.

This profile does not accept object lifetime, every file/driver route, SDK
errors/retries, memory-card/debug I/O, complete save states, hardware timing or
the complete file feature. Whole-feature acceptance remains zero. Original NPC
behavior, optional AI-assisted tools and the separate Bevy port retain their
existing measurements and scope.

The later [natural file-lifetime profile](FILE_HEAP_LIFETIMES.md) closes the
observed lifetimes of the 35 allocations backing these 49 queued reads, using
a longer capture and original allocator/file-view boundaries. The earlier
SDK-only checker retains the narrower scope described here.

Twelve new callable/member-address collision forms plus two controls were
independently GNU-qualified. None improved the hull's 26 differing bytes, and
none was promoted. Two assembly functions and three inherited storage
explanations remain open. The complete canonical executable and all 392 game
build inputs are unchanged, as is the playable matching-C launcher.

[Validation metadata](sdk-read-checks.json) records hashes, bounded counts and
the exact acceptance limits.
