# Natural day progression

The original Japanese disc and matching rebuild completed **seven natural days**
in separate controller-only cold runs. All **209 sampled MainRAM, GPURAM and RGB
hash pairs** agree, as do the exact controller history and **201 complete PCM
windows**. The **nine complete serialized-state hash pairs differ**. The strict
complete-state comparison fails and remains recorded as a failure.

This is a bounded progression result, not acceptance of the 365-day ending.
Matching C remains **197,172 / 199,912 bytes (98.6294%)**: two assembly functions
and three inherited storage explanations remain. Whole-feature acceptance
remains **zero**. [Machine-readable evidence](natural-progression-pilot-checks.json)
binds the producer, inputs, measurements and limits.

The feature file's October 11 before/initial-pass snapshots remain frozen. A
dated supplement uses the current configured sources and active assembly
catalogue: **38 of 40 catalogued core groups** have C, and **6 of 40** have all
their listed shared support in C. The frozen initial-pass core count was 35.
These are provisional source groups, not an exhaustive count of the game's
features or a runtime-parity percentage. This study promotes no new C.

The independent [progression-history checker](PROGRESSION_HISTORY.md) now
reproduces the recorded results from either expanded or sealed journals,
including all nine complete-state failures. Its year-window option does not
establish complete ending decode or whole-feature parity.

## Observed route

Each isolated Nymashock instance advances 120,001 emulator frames, including its
initial neutral frame. The original uses ordinary startup/menu confirm and up
inputs and releases controls during the dream timer. The rebuild replays the
original's exact 169 run-length input changes. No game RAM, instruction, save,
state, disc or running emulator UI is changed.

The pilot requested eight completed days within 120,000 input frames. It reached
**seven**, ending during the eighth displayed day. Both runs terminate at the
frame ceiling; the requested eight-day target is **not reached**. The recorded
zero-based counters are 0 through 7. This distinction is retained in the report.

| Recorded comparison | Pairs | Matching pairs |
| --- | ---: | ---: |
| Read-only progression fields at checkpoints | 209 | 209 |
| Complete MainRAM hashes | 209 | 209 |
| Complete GPURAM hashes | 209 | 209 |
| Complete RGB hashes | 209 | 209 |
| Consecutive complete returned-PCM windows | 201 | 201 |
| Complete serialized-state hashes | 9 | **0** |

The PCM windows cover every returned sample, including the initial observation
and final partial window: 88,456,635 stereo sample frames per run. RAM/GPU/RGB
observations occur every 600 frames, at native day-counter changes and at the
final frame. These are sampled video/state comparisons, not all-frame video.

The host locates the original dream object by its vtable and validates day/year
bounds. Menu choices other than the ordinary dream are not confirmed. It reads
the native day, year, timer, limit, pause, flashback and menu fields; it never
writes those fields. A watchdog bounds a stalled day.

## Complete-state failure

The host serializes twice at each day-boundary/final checkpoint. Within each
run, both hashes agree and recaptured RAM, GPU memory and frame count remain
unchanged. Across the original and rebuild, all nine non-null state hashes
differ. The other 200 checkpoints contain no serialized-state observation;
two absent hashes do not count as equal states.

Only hashes of these nine complete states were retained. Their differing bytes
cannot be located from those hashes. The existing
[stock-core diagnosis](NYMASHOCK_STATE.md) identifies unused native media-label
storage in earlier captures of this same distributed core, but that ownership
has **not** been proven for these nine new states. No bytes are masked,
normalized or discarded to make the strict comparison pass.

The existing [initialized-media core qualification](SERIALIZED_CORE_STATES.md)
provides a separate tested profile for further work. Its earlier successful
opening-state comparisons do not retroactively change this stock-core failure.

## Producer and remaining gates

[RecordProgressionHistory.cs](../research/headless/RecordProgressionHistory.cs)
is the maintained managed producer. The pilot's evidence pins its earlier
executed body; the later [streaming-hash update](STATE_HASH_STREAMING.md) removes
duplicate state buffers and adds resource telemetry without changing that
historical result. It is research source, separate from game logic and from
AI/model tooling. It uses the shared
[headless host definitions](../research/headless/ReplayColdStart.cs), distributed
BizHawk 2.11.1 assemblies and existing local disc/BIOS inputs. The retained private
manifest records the full compiler command and input identities. Runtime, disc
and asset-tree copies are zero; PCM and complete native states are hashed rather
than dumped to disk. Compile the maintained producer with
`BoundedSha256Stream.cs` as well as the shared host definitions.

The prototype's positional arguments are runtime directory, cue, Japanese/US/EU
BIOS paths, new output directory, maximum input frames, target completed days,
and either `-` for its controller policy or a recorded `inputs.tsv` for replay.
The published result covers this seven-day pilot; larger argument limits do not
establish that larger routes have been verified.

Days 364/365, the year boundary, ending playback, alternate seeds, controller and
memory-card error branches, continuous video and original-hardware timing remain
outside this pilot. No new C function, NPC profile, original gameplay feature or
model-API call follows from these measurements. The Bevy port is unchanged.
