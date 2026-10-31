# Ending completion-field lifecycle

A retained original-disc recording completed **365 natural days and 12,000
post-year frames**. Its native process exited successfully. The first Python
validation stopped because an ending movie's completion field initially held
`177408`, before later observations held `0` and `1`.

The validator now preserves this raw pre-pending observation and validates the
later pending/completion transition. It does not discard the observation or
count its arbitrary value as completion. **The later
[rebuilt-disc replay and strict comparison](NATURAL_YEAR_ENDING.md) now pass.**
This document retains the earlier validator-repair evidence. Full native movie
decoding and whole-game parity remain separate requirements.

[Machine-readable evidence](year-ending-field-lifecycle-checks.json) records
the original capture dimensions, canonical function hashes, source hashes,
journal hashes and analysis-copy controls.

## Original behavior

The recovered [movie-screen structure](../src/menu/movie_screen.h) places
`m_Unk53` at offset `0xd8`. `movie_screen_construct` does not initialize this
field. Its two direct assignments in
[movie_screen.c](../src/menu/movie_screen.c) occur in `func_8003BC14`:

| Movie event | Assignment |
| --- | --- |
| 5 | Completion field becomes zero |
| 7 | Completion field becomes one |

The complete executable is canonical. The original constructor's 248-byte
range and event handler's 224-byte range also agree with the public original
function index. The native observer recorded the same movie address in order
with raw field values **177408 → 0 → 1**, followed by no matching movie object.
This is consistent with observing the object before its field is initialized.
No game field was changed to obtain the recording.

## Validation contract

Completion-field observations must be signed 32-bit integers; booleans and
out-of-range values remain invalid. A nonboolean raw value is permitted only
before a pending zero has been observed for that object. It contributes no
pending or terminal evidence. A nonboolean value after pending is rejected.

Completion still requires an observed zero followed on a later frame by one
with a nonzero decoder result, for the same object. The original path,
threshold, play flags, year boundary, checkpoint schedule, neutral ending
inputs, PCM windows and decoded PNG checks remain enforced. A nonzero decoder
result is an opaque terminal signal, rather than proof of complete STR decode.

Strict original/rebuilt comparison still compares the entire raw ending
journal, including the pre-pending value, and every recorded memory/state
hash. A different raw initial value fails comparison even when both recordings
individually satisfy the lifecycle schema.

## Retained evidence

The existing native original run was inspected without repeating its
7,184,806 frames. The repaired validator accepts its saved observation format:

| Observation | Count |
| --- | ---: |
| Natural day transitions | 365 |
| Checkpoints | 12,345 |
| Complete serialized-state observations | 371 |
| PCM windows | 11,976 |
| Stereo sample frames | 5,296,186,767 |
| Controller-mask changes | 6,399 |
| Raw pre-pending flag observations | 1 |
| Pending then terminal ending objects | 1 |

Three controls edit analysis copies of the actual saved observations. A raw
initial-value change fails strict comparison; removal of the pending zero and
a nonboolean value after pending both fail validation. These controls do not
modify runtime instructions or the retained capture. Data-free tests exercise
the same boundaries, including signed extremes and invalid types.

The failed coordinator report and original input manifest remain preserved.
All 171 original input records other than the post-capture validator remain
unchanged. The exact old validator bytes remain in Git; the replacement
analysis source is explicitly pinned for the rebuilt replay. The native host,
game, BIOS and disc inputs are reused unchanged. Completed journal payloads
are losslessly sealed with complete member hashes and an actual exact-path
restore test; reports, inputs and PNGs remain directly available.

This repair adds zero recovered C bytes, gameplay features or whole-feature
or NPC-encounter acceptances. Original NPC behavior and AI-assisted analysis
remain separate. No model API calls are made.
