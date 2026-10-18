# Original CD errors and reset recovery

A controller-only interruption now exercises actual read errors in the original
game. Original and matching rebuilt discs agree throughout the 30,000-frame
history, including five failed SDK reads and a later controller reset. The
separate observer also matches the stock core's recorded game outputs.

Matching C stays **197,172 / 199,912 bytes (98.63%)**. The executable, all 392
game build inputs and the existing playable launcher are unchanged. This adds
an original-behavior verification profile and optional analysis tooling; it
does not accept a complete file feature or full-game parity.

## Executed scenario

The route opens the original disc tray at frame **2,420**, during a 97-sector
read, and closes it at **2,540**. Disc index `0` selects the original first disc;
`-1` would mean no disc. A separate earlier 6,000-frame diagnostic observed
five read failures and no resumed loading after reinsertion.

The qualified route retains that behavior, then presses the original controller
**Reset** input at frame **3,000**. It replays the normal opening inputs for
6,000 frames and releases all buttons afterward. At checkpoints 6,000 and
9,000, the game visibly reaches an apartment interior and a dream landscape.
The final checkpoint at 30,000 shows original movie text. This profile does
not claim a Day 002 final screen.

The host runs isolated emulator cores. It patches no game instruction or RAM,
restores no saved state and controls no existing EmuHawk session.

## Observed original error behavior

The read polling boundary returns `-1` five times. Each follows the original
asynchronous driver's flush, state-1, Setloc, state-2 and sync path. The first
episode repeats this seek loop through **61 sync errors** before ending the
request at frame 2,544. The other four end at 2,552, 2,560, 2,568 and 2,579.

All five completions clear the original busy/state fields. **None reissues an
SDK sector read before ending that failed driver request.** This is the
observed retail error path, not a successful refill or automatic read recovery.
It differs from the blocking reader's separate retry loop; that loop's executed
error coverage remains open. The ignored return register from `CdFlush` is
retained as opaque data and is not treated as a success flag.

| Evidence, per observer run | Result |
| --- | ---: |
| Balanced SDK, driver, heap and file-view boundaries | 56,405 |
| SDK reads successfully completed | 162: 52 before reset, 110 after |
| Successful complete sector RAM compared with the disc | 6,047,744 bytes |
| Failed SDK reads | 5 |
| Full failed destination RAM retained | 839,680 bytes |
| Written prefix of failed RAM verified against the disc | 59,392 bytes |
| Driver state setter / end-read calls | 254 / 137 |
| Failed-read flushes | 5 |
| Post-reset queued Read lifetime windows qualified | 49 / 49 |
| Their backing allocation generations observed through free | 35 / 35 |

The first failed read writes 29 sectors of its requested 97 before the error.
The other four write none. Every failed snapshot retains its entire requested
destination, but only the observed written prefix is checked against disc
sectors. Unwritten tails are neither accepted content nor successful transfers.

Reset starts a new game/heap epoch. Before it, 15,235 successful allocations
and 689 matched frees leave **14,546 live generations censored by reset**;
reset does not manufacture native frees. After reset, 18,922 allocations and
18,856 matched frees leave 66 live at the final checkpoint. All 35 allocations
used by the qualified post-reset queued reads are actually freed. No complete
pre-reset queued-read lifetime claim is made.

## Verification boundaries

Fifteen complete original function ranges and ten exact driver-global words
are qualified by a canonical 306-object symbolic link and GNU symbol extents.
The sparse driver vectors preserve the declared word order; they are not
claimed to be contiguous 80-byte memory windows. Fourteen targets execute;
the selected base cleanup function still has no observed call.

Original/rebuilt raw boundary records, code/RAM payloads and epoch models are
byte-identical. Both the original/rebuilt and observer/stock comparisons agree
on **30,001 GPU observations, 5,014 RAM observations, 143 complete RAM/GPU/RGB
checkpoints and 88,454,624 PCM bytes per run**. An independent numeric-layout,
allocation-epoch and sector audit agrees, rehashes 114 source snapshots and
decodes all 429 PNGs against their RGB payloads. Eighteen contradictory
retained-data controls are rejected. Those controls alter parser inputs;
the separately executed game interruption uses only tray/reset inputs.

The stable record size remains 464 bytes, with tagged failed-RAM and sparse
driver-state payloads. Capacity is 32,768 records and 32 MiB per frame; this
route peaks at 1,201 records and 551,356 bytes. The core is a separately rebuilt
adapter linked with pinned cached native objects, not a fresh full-core build.
No pending call/transfer, lost record, overflow or overlapping allocation
extent is accepted. The hook survives the original reset without a rearm patch.

Twenty-two owned tests cover failure accounting, partial prefixes, state loops,
reset epochs and source-identified call sites. The full suite passes **1,135
tests** on both Windows and Linux, with two expected skips each. Earlier
success-only SDK and natural lifetime profiles retain their stricter contracts.

## Reproduce locally

Prepare private discs/BIOS as in [Playing](PLAYING.md) and the pinned native
source as in [Headless replay](HEADLESS_REPLAY.md). Build a separate observer
in Linux/WSL:

```sh
python tools/sdk_reads.py \
  --export-ranges .decomp-lab/cd-recovery-ranges-new --cd-recovery
python tools/build_dispatch_observer.py \
  --source-root /private/pinned-bizhawk-source \
  --output .decomp-lab/cd-recovery-observer-new --sdk-reads
```

Use fresh Windows workspaces for each original/rebuilt recording; omit
`--observer-profile` for the stock-core control:

```powershell
python tools/record_dispatch_history.py `
  --capture-folder D:/private/cold-boot-original `
  --workspace D:/private/cd-reset-original-new `
  --program research/headless/file-driver-cd-reset-route.json `
  --observer-profile .decomp-lab/cd-recovery-observer-new/profile.json

python tools/inspect_cd_recovery.py `
  --reference D:/private/cd-reset-original-new `
  --candidate D:/private/cd-reset-rebuilt-new `
  --output .decomp-lab/cd-reset-comparison-new.json

python tools/inspect_cd_recovery.py `
  --reference D:/private/cd-reset-original-new `
  --candidate D:/private/cd-reset-stock-new `
  --mode observer-output `
  --output .decomp-lab/cd-reset-stock-comparison-new.json
```

The shorter `file-driver-cd-recovery-route.json` preserves the no-reset
diagnostic inputs. It is not a qualified recovery profile for this inspector.
The original 13-target pilot capture remains private diagnostic evidence;
the published 15-target manifest does not retroactively qualify it.

Two collision assembly functions and three inherited storage explanations
remain. Six new hull source forms plus two controls were independently
extracted with GNU tools; none improved its 26 differing bytes. No near-match
source was promoted. Original NPC recovery, complete encounters, other I/O
error paths, save/card behavior, complete emulator states and original-hardware
timing retain their separate gates. This profile calls no model API, adds no
gameplay behavior and changes nothing in the Bevy repository.

[Validation metadata](cd-error-reset-checks.json) records the identities,
private evidence hashes, before/after counts and remaining requirements.
