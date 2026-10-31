# Natural year and ending replay

The original Japanese disc and the matching rebuild each completed **365 natural
days, 7,184,806 emulated frames and a 12,000-frame post-year window**. Their exact
controller histories, day observations, returned audio, sampled memory/images
and every observed complete-state hash agree. The strict comparison passes
without masking or normalizing state bytes.

[Machine-readable evidence](natural-year-ending-checks.json) binds the completed
recordings to their frozen inputs, executed host, analysis source and retained
journal hashes. This advances F003's year-route evidence and F032's ending
lifecycle evidence. **Whole-feature and whole-NPC encounter acceptances remain
zero.** Complete native movie decoding, other routes and original hardware
timing remain open.

The report retains both working-file and Git-blob source hashes. The unchanged
`mdec_movie.h` and `movie_screen.h` working files use CRLF while their Git blobs
use LF; their complete text was checked for that sole representation difference. The executed
progression validator's working bytes and Git blob agree exactly.

## Route and inputs

Each recording starts its own qualified Nymashock instance from cold. The
original uses ordinary Circle and D-pad Up inputs to enter the normal dream
choice; it releases controls while the dream timer runs. The rebuild replays
the original's exact **6,399 run-length controller changes**. Input remains
neutral throughout the ending window. No saved state is loaded, game RAM or
instructions changed, or interactive player/profile accessed.

Both recordings reuse the previously qualified
[initialized-media core](SERIALIZED_CORE_STATES.md) and
[cooperative verification host](COOPERATIVE_FRAME_WAITS.md). No host wait was
needed in either full-year recording. Both native processes exited with code
zero; the rebuilt coordinator completed validation, journal sealing and strict
comparison. The **174 frozen input records**, including disc, BIOS, native
runtime, dependencies and host executable, were rehashed after completion.

The full original and rebuilt Japanese disc images share SHA-256
`cbf377af3e9207964f11044202eb5ecec2594a3c96e0919f7aa807d328654e61`.
Their embedded executable and the current build retain the canonical SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d`.

## Compared observations

| Observation | Compared pairs | Differences |
| --- | ---: | ---: |
| Native day observations, including the initial day | 366 | 0 |
| Sampled state fields | 12,345 | 0 |
| Complete MainRAM hashes | 12,345 | 0 |
| Complete GPURAM hashes | 12,345 | 0 |
| RGB framebuffer hashes | 12,345 | 0 |
| Complete serialized-state hashes | 371 | 0 |
| Consecutive returned-PCM windows | 11,976 | 0 |
| Controller-mask changes | 6,399 | 0 |
| Ending lifecycle observations | 4 | 0 |
| Decoded PNG images | 7 | 0 |

The PCM windows cover all returned **5,296,186,767 stereo sample frames** from
initial through final frame, with no gaps or overlaps. RAM/GPU/RGB checkpoints
occur every 600 frames and at the declared day, ending and final observations.
Complete serialized state is observed only at its 371 declared checkpoints;
the other checkpoints do not count as complete-state comparisons.

The earlier [seven-day pilot](NATURAL_PROGRESSION.md) still records nine
complete-state differences and a failed strict comparison. Its result is
preserved. This later pair uses the separately qualified input/runtime profile
recorded in its own manifest; it does not alter or explain away those failures.

## Year boundary

Every one of the 365 day increments was checked against the journal and sampled
state. The recovered `get_day_number` returns the internal day plus one;
`dream_sys_advance_day` wraps after internal day 364. The final transitions are:

| Input frame | Completed days | Internal year | Internal day | Displayed day | Stored history day |
| --- | ---: | ---: | ---: | ---: | ---: |
| 7,128,641 | 363 | 0 | 363 | 364 | 362 |
| 7,150,730 | 364 | 0 | 364 | 365 | 363 |
| 7,172,805 | 365 | 1 | 0 | 1 | 364 |

The final state remains year 1, internal day 0 after 12,000 further advances.
The counter transition agrees with `game_flow_execute_dream`'s ending condition:
a nonzero year and displayed day 1. The observed history-day field and full
sampled MainRAM hashes agree; the complete dream-history records have not been
independently decoded or reviewed by this year-route comparison.

## Ending lifecycle and images

The same movie object is observed with path `ETC\ENDING.STR`, encoded-frame
threshold **474** and play flags **1**. Its four retained observations agree:

| Input frame | Completion field | Decoder result | Movie present |
| --- | ---: | ---: | --- |
| 7,172,820 | 177408 | 0 | Yes |
| 7,172,940 | 0 | 0 | Yes |
| 7,174,800 | 1 | 1 | Yes |
| 7,174,830 | — | — | No |

The [completion-field lifecycle audit](YEAR_ENDING_FIELD_LIFECYCLE.md) explains
the raw value before event 5 initializes the field. Strict comparison retains
that value. Only the later pending-zero to terminal-one transition contributes
to the year-window gate. The decoder result remains an opaque terminal signal;
its value alone cannot establish successful decoding of every STR frame.

Six images are retained at year-boundary offsets 0, 120, 600, 1,800, 3,600 and
11,999, plus the final frame. All seven decoded RGB images match. The sampled
ending film and later LSD logo were also visually inspected. Continuous native
video and exact frame presentation were not captured. The separate
[software movie decode](MOVIE_DECODE.md) covers the disc's encoded movie content;
it does not establish the native MDEC/GPU/audio playback path.

## Retention and repeatability

Each closed recording retains four journals in a lossless archive. Complete
archive and member SHA-256 checks, readback and actual exact-path restoration
tests passed before expanded journal copies were retired. The two archives
have different container hashes and **identical hashes for all four journal
payloads**. Reports, controller inputs and PNGs remain directly available.
The completed-data audit reads archives in memory and repeats no native frames.

Use the existing [progression-history checker](PROGRESSION_HISTORY.md) with the
two retained private recording directories:

```powershell
python -B tools/inspect_progression_history.py compare `
  D:\private\lsd\year-original D:\private\lsd\year-rebuilt `
  --require-year-ending --output D:\private\lsd\new-year-comparison.json
```

The producer's initial failed coordinator report, prior input manifest and
validator repair remain retained. Source, player, saves, original disc and
matching build were preserved. This publication changes zero game C bytes,
gameplay features or original NPC behavior, and makes zero model API calls.

The [matching-C milestone](MATCHING_GAME_C.md) remains 199,912 / 199,912 counted
game bytes with zero game assembly fallbacks. Forty feature groups remain
provisional. Full dream-history review, complete native movie playback and
skips, other seeds/branches, NPC encounters, card/error scenarios, content and
dispatch closure, and original hardware timing still require their own
evidence. See [the roadmap](ROADMAP.md) and [playable build](PLAYING.md).
