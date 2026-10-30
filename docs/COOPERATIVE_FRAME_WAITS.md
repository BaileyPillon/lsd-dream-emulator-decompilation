# Cooperative waits during native verification

Long controller replays can encounter temporary system memory pressure. The
research host can now acknowledge a wait between completed emulated frames,
retain an exact state witness, and resume after its supervisor releases it.
This preserves a cold-start history without loading a saved state.

The [qualification evidence](cooperative-frame-wait-checks.json) records four
successful native runs, one retained failed supervisor attempt, and the
unchanged source and runtime boundaries. Matching game C remains
**197,172 / 199,912 bytes (98.63%)**. These checks accept no whole game feature,
year boundary, ending, hardware timing claim or native PC port.

## Native qualification

| Check | Observed result |
| --- | --- |
| Original and rebuilt discs, 6,001 core advances each | All recorded checkpoint, controller, day, PCM and decoded PNG comparisons agree |
| Held original versus retained original without waits | All recorded outputs agree |
| Stop while a wait is acknowledged | Clean stop report after 3,001 core advances; closed journals independently validated |
| Wait across the unchanged 180-second progress watchdog | Held for 186,313 ms, resumed, and completed with the same recorded outputs as the run without waits |

Every deliberate wait occurs after input frame 3,000, at core frame 3,001.
Before and after witnesses agree on the frame counter, full serialized state,
complete MainRAM and GPURAM, RGB image, and accumulated returned PCM sample
count. Full-state observation itself is checked against game memory.
The continuing replay comparison separately checks actual PCM hashes.

Each successful capture's closed journals passed full SHA-256 readback and an
actual restoration to the exact original checkpoint path before retirement.
The source bodies used by the private qualification are byte-identical to the
published host and shared helpers listed in the evidence file.

## Wait protocol

[CooperativeFrameWait.cs](../research/headless/CooperativeFrameWait.cs) has no
emulator dependency. A caller invokes it between frames and supplies the
boundary observations. It uses three files inside the caller's output folder:

1. The supervisor atomically creates `HOST-WAIT`, containing an ASCII token of
   1–128 letters, digits or hyphens, without a newline.
2. The host records its pre-wait witness before creating `HOST-WAIT-ACK` with
   that same token. Only this acknowledgment permits the supervisor to exclude
   elapsed wait time from its frame-progress watchdog.
3. The supervisor removes `HOST-WAIT` to release the host. The host compares
   the post-wait witness before advancing another frame, then removes its own
   acknowledgment.
4. `STOP` also releases a wait. The result distinguishes stop from timeout;
   the caller must honor either condition. A replacement token or stale
   acknowledgment fails explicitly.

The host retains `host-waits.jsonl` and an atomic `host-wait-status.json`.
The wait journal has its own 256 KiB bound. It is separate from the original
16 MiB progression journals, whose byte-count contract is unchanged.

## Year producer

[RecordYearProgression.cs](../research/headless/RecordYearProgression.cs)
publishes the qualified natural-year/ending-object recorder. Compile it with
`ReplayColdStart.cs`, `BoundedSha256Stream.cs` and `CooperativeFrameWait.cs`,
using the existing BizHawk/.NET Framework references and the entry point
`Lsd.Research.Headless.YearProgressionEnding`.

Its arguments, in order, are:

```text
runtime-folder cue japanese-bios us-bios european-bios new-output-folder
input-frame-ceiling target-days replay-inputs-or-minus forced-wait-frame wait-limit-ms
```

The runtime folder must select the qualified existing `dll/` and `gamedb/`
directories. The measured runs use the existing
[initialized-media core](SERIALIZED_CORE_STATES.md); their exact native hashes
are pinned in the evidence. Supply your own matching Japanese disc and BIOS.
The output directory must be new. The ordinary year profile uses a ceiling of
`8000000`, target `365`, replay `-`, forced wait `-1`, and wait limit `3600000`.
The bounded qualification uses forced frame `3000` and a declared shorter
wait limit. Input frame ceilings are inclusive; core advance counts are
reported separately.

Run this host inside an owned process supervisor. The measured supervision
uses a 1 GiB private-memory bound, a 12-hour wall bound per run, and a
180-second active frame-progress watchdog. It requests a cooperative wait
below 2 GiB of system commit headroom, and resumes after at least 8 GiB has
remained available for 60 seconds. Below 512 MiB it requests an emergency
stop. Waits are limited to one hour. The year preflight also requires 60
seconds of stable 8 GiB headroom. No unrelated application is stopped.

The supervisor retains the exact resource sample on every request,
acknowledgment, release and stop. The 40 MiB output ceiling includes root logs
and resource journals. [capture_storage.py](../tools/capture_storage.py)
counts those outputs without following shared runtime symlinks or NTFS
junctions. This logical output bound is separate from the project's physical
storage audits.

The producer observes 365 natural transitions and a further 12,000 neutral
frames. A year result also requires the original ending-path object to change
from pending to completed with a decoder result. Compare completed original
and rebuilt captures using:

```bash
python -B tools/inspect_progression_history.py compare ORIGINAL REBUILT --require-year-ending
```

Object completion is still distinct from complete ending decode, every-frame
video agreement, hardware cadence, other seeds and branches, and reviewed
whole-feature acceptance.

## Retained failures and open work

The first qualification's supervisor followed an NTFS junction while counting
output, incorrectly charging about 152 MB of shared runtime files to a small
capture. It also recorded a stop before the output folder existed without
retrying delivery. After its grace interval it terminated only its owned test
child. That attempt has no valid terminal capture report and does not qualify.
The executed source, manifest, logs and partial journals remain retained.
The corrected supervisor excludes links and retries stop delivery. Its native
stop-during-wait check and filesystem regression tests pass.

The previous October 29 year attempt reached 16 days and stopped at its
2 GiB system commit guard; no rebuilt year replay started. The earlier
day-153 Windows disc-read resource exception still has no established cause.
The newly qualified protocol supports another supervised cold-start attempt;
these qualification results do not supply its full-year or ending result.

The [original seven-day pilot](NATURAL_PROGRESSION.md), including its nine
failed cross-run state comparisons, remains intact. The
[streaming hash qualification](STATE_HASH_STREAMING.md) is separate evidence.

## Data-free checks

```bash
python -B -m unittest tests.test_cooperative_frame_wait tests.test_capture_storage -v
```

Ten wait tests compile and operate the actual helper in a separate process,
checking release, stop, timeout, token replacement, stale acknowledgments,
invalid requests and callback failures. Five filesystem tests check actual
owned files and links, including a Windows NTFS junction. An existing .NET SDK
and reference packs are required for the managed checks; unavailable
capabilities are explicitly skipped. No dependency is downloaded or installed.
