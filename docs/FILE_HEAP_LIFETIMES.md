# Natural file-view and allocation lifetimes

The optional observer now follows the original allocator and file-view methods
alongside disc reads. A **30,000-frame original/rebuilt replay** checks all
**35 backing allocations** used by the 49 queued reads, from their allocation
generations through their actual frees. The final 16 retire at frames
**23,018–23,029**, and the recording reaches the visible **Day 002** menu.

Matching C remains **197,172 / 199,912 bytes (98.63%)**. The complete executable,
all 392 game build inputs and the playable matching-C launcher are unchanged.
This is additional original-behavior evidence and an analysis tool.

## What changed

| Measure | Earlier SDK-only profile | Natural lifetime profile |
| --- | ---: | ---: |
| Controller frames | 6,000 | 30,000 |
| Queued Read origin/replay/completion chains | 49 | 49 |
| Those chains with qualified receiver/destination lifetimes | 0 | 49 |
| Their backing allocation generations followed through free | 0 | 35 |
| Recorded heap/file-view call/return records | 0 | 39,624 |
| Completed SDK reads | 102 | 117 |
| Accepted complete file feature | No | No |

A shorter lifetime recording first closed 19 relevant allocations and left
16 live. Extending the same first 6,000 inputs through natural dream teardown
closes all 35. The shorter recording's raw call/return records, payloads,
controller observations, RAM observations and PCM are byte-identical prefixes
of the longer recording. Subsequent inputs release every controller button.

## Original behavior checked

The twelve complete function ranges cover six SDK boundaries plus the original
allocation, free, base file constructor, destructor, release and cleanup
functions. A complete canonical 306-object symbolic link and independent GNU
symbol extents qualify every selected range. Eleven targets execute naturally;
the base cleanup function has **zero observed calls** and gains no runtime
acceptance from its range alone.

The 40,890 balanced records contain:

| Original boundary | Observed returns |
| --- | ---: |
| Successful allocations | 19,717 |
| Free calls with matched allocation generations | 19,303 |
| Null-pointer free calls | 15 |
| Base file constructors | 187 |
| File-buffer releases | 221 |
| Base file destructors | 181 |
| SDK request/poll/control/sync calls | 1,266 |

Each allocation is identified by its observed API return and actual block
header. The verifier checks four-byte rounding, the minimum payload, the
original split threshold and allocated/free flags. A free ends that specific
generation. Reusing the same address requires a new allocation and constructor;
an address match cannot borrow an earlier object's identity.

Before/after file-view snapshots check the constructor's initialized fields
and retained locator words. All 221 release histories obey the original
buffer, size and ownership flags; 39 free a buffer and clear its pointer.
Every observed base destructor returns zero and contains its exact object
free. Post-free RAM is retained as raw data and is not interpreted as a live
object.

For each queued read, the original receiver and complete sector destination
remain within their qualified backing allocations from the originating call
through SDK completion. The following frees are observed later. These 49
windows cover **3,506,176 full-sector RAM bytes**; the earlier distinction
between requested byte arguments and their 18,832 tails remains intact.

The longer profile also verifies **117 completed SDK reads**, totaling
**5,328,896 sector RAM bytes** across 2,108 distinct sectors. Disc positions
follow observed successful Setloc and completed-read history. There are no
lost events, overflows, unmatched frees, overlapping live allocation extents,
failed allocations, pending calls or pending SDK transfers. Another 414
allocations remain live at the final menu; their future lifetimes are open.

## Reproduce locally

Use the private disc/BIOS preparation in [Playing](PLAYING.md) and the native
source requirements in [Headless replay](HEADLESS_REPLAY.md). Build a separate
observer in Linux/WSL:

```sh
python tools/sdk_reads.py \
  --export-ranges .decomp-lab/file-heap-ranges-new --heap-lifetime
python tools/build_dispatch_observer.py \
  --source-root /private/pinned-bizhawk-source \
  --output .decomp-lab/file-heap-observer-new --sdk-reads
```

The range export reproduces the committed heap boundary manifest. Record each
verified disc capture in a fresh Windows workspace; omit `--observer-profile`
for the distributed-core control:

```powershell
python tools/record_dispatch_history.py `
  --capture-folder D:/private/cold-boot-original `
  --workspace D:/private/file-heap-original-new `
  --program research/headless/file-driver-heap-cycle-route.json `
  --observer-profile .decomp-lab/file-heap-observer-new/profile.json

python tools/inspect_file_heap.py `
  --reference D:/private/file-heap-original-new `
  --candidate D:/private/file-heap-rebuilt-new `
  --output .decomp-lab/file-heap-comparison-new.json

python tools/inspect_file_heap.py `
  --reference D:/private/file-heap-original-new `
  --candidate D:/private/file-heap-distributed-new `
  --mode observer-output `
  --output .decomp-lab/file-heap-observer-control-new.json
```

The stable 464-byte record layout now has tagged heap/header/file-view payloads
in addition to SDK buffers. Its capacity is 32,768 records and 32 MiB per frame;
this history peaks at 1,201 records and 551,356 payload bytes. Older SDK-only
captures retain their frozen 8 MiB profiles and continue to validate. The new
core is one separately compiled adapter linked with pinned cached native
objects; it is not a fresh full-core build.

## Verification and remaining work

Original/rebuilt raw records, complete code/RAM payloads and allocation models
are byte-identical. Both original/rebuilt and observer/distributed comparisons
pass **30,001 GPU observations, 5,149 RAM observations, 226 complete RAM/GPU/RGB
checkpoints and 88,457,172 PCM bytes per run**. An independent numeric-layout,
generation and sector audit agrees, rehashes 114 source snapshots and decodes
all 678 PNGs against their RGB payloads. Twenty contradictory retained-data
controls are rejected; these are parser tests, not executed game faults.

Nineteen owned lifetime tests and four additional SDK transfer-context tests
bring both platform suites to **1,113 passing tests**, with two expected skips
each. Earlier SDK-only and return captures still validate. The observer arms
at frame 900 and compares the full boot; the earlier frame-zero discrepancy
remains documented.

The 35 closed storage generations do not settle every object or file route.
Cleanup dispatch, debug/card I/O, SDK failures and retries, later sessions,
complete save states and original-hardware timing remain open. Whole-feature
acceptance stays zero. Original NPC behavior and optional AI-assisted tools
retain their separate measurements; this profile calls no model API and adds
no game behavior. The Bevy repository is unchanged.

Six new collision-source forms plus two controls were independently qualified.
None improved the primitive query's 22 differing bytes. Both assembly functions
and three inherited storage explanations still require recovery.

[Validation metadata](file-heap-lifetime-checks.json) seals the source identities,
counts, private evidence hashes and acceptance boundaries.

The later [CD error/reset profile](CD_ERROR_RESET_RECOVERY.md) extends this
tooling to actual failed reads and a controller-reset boundary. Its separate
heap epochs preserve the distinction between actual frees and reset-censored
allocations. The measurements above describe this earlier successful route.
