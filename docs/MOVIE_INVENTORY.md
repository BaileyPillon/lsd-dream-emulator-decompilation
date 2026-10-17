# Original movie structure and route selection

The Japanese-labelled reference contains **39 mixed-sector movies** with
**22,382 encoded frames**. Every frame has complete, ordered chunks, contiguous
IDs, consistent metadata, and an encoded prefix matching its sector header.
All observed video frames are 320 × 240, STR version 2.

This checkpoint covers structure and bounded native routing. The later
[complete software decode](MOVIE_DECODE.md) validates all 22,382 video frames
and 27,921 XA audio packets through FFmpeg and a separate raw-byte hashing pass.
Native MDEC/GPU/audio equivalence, natural playback of every movie, controller
skips, hardware cadence, and complete startup/special-day/ending scenarios
remain open. No additional C function or
whole feature is accepted by these checks.

## Native thresholds

The 653 path records at `0x80081A04` and 50 signed halfwords at `0x80086170`
match their C initializers byte for byte. The threshold values are encoded
frame IDs, **not seconds**. `str_stream_get_next` reads `header[2]`; a positive
threshold contributes to its negative completion result when that ID reaches
the threshold. Nonpositive thresholds bypass this comparison.

The MDEC caller can decode a returned buffer before handling a negative stream
result. A stream threshold must therefore not be equated with the last displayed
frame without runtime proof. The sole game-source edit corrects the table's
two-line comment; its values and compiled instructions are unchanged.

Thirty-six files have ten encoded frames beyond their threshold. `SPDAY08A`
and `SPDAY11B` have eleven; `SPDAY11A` has twelve. Normalizing every threshold
to `frame_count - 10` would change the original game. Eleven table entries,
indices 38–48, remain unbound by these getters; index 48 is signed `-10`.
Their roles remain unresolved and they are not eleven additional movies.

## Complete routed inventory

The seven openings, ending, and logo are under `/CDI/ETC/` (nine files).
The six events and 24 special-day clips are under `/CDI/FILM/` (30 files).
The final column is encoded frame count minus threshold, not observed display
duration. The route paths in the metadata retain their exact native directories.

| File | Threshold index | Native threshold | Encoded frames | Difference |
| --- | ---: | ---: | ---: | ---: |
| `OPENINGA.STR` | 0 | 1060 | 1070 | 10 |
| `OPENINGB.STR` | 1 | 1088 | 1098 | 10 |
| `OPENINGC.STR` | 2 | 953 | 963 | 10 |
| `OPENINGD.STR` | 3 | 1179 | 1189 | 10 |
| `OPENINGE.STR` | 4 | 979 | 989 | 10 |
| `OPENINGF.STR` | 5 | 1231 | 1241 | 10 |
| `OPENINGG.STR` | 6 | 1046 | 1056 | 10 |
| `ENDING.STR` | 7 | 474 | 484 | 10 |
| `EVENT1.STR` | 8 | 524 | 534 | 10 |
| `EVENT2.STR` | 9 | 439 | 449 | 10 |
| `EVENT3.STR` | 10 | 349 | 359 | 10 |
| `EVENT4.STR` | 11 | 379 | 389 | 10 |
| `EVENT5.STR` | 12 | 352 | 362 | 10 |
| `EVENT6.STR` | 13 | 352 | 362 | 10 |
| `SPDAY01A.STR` | 14 | 475 | 485 | 10 |
| `SPDAY01B.STR` | 15 | 867 | 877 | 10 |
| `SPDAY02A.STR` | 16 | 527 | 537 | 10 |
| `SPDAY02B.STR` | 17 | 445 | 455 | 10 |
| `SPDAY03A.STR` | 18 | 399 | 409 | 10 |
| `SPDAY03B.STR` | 19 | 579 | 589 | 10 |
| `SPDAY04A.STR` | 20 | 264 | 274 | 10 |
| `SPDAY04B.STR` | 21 | 541 | 551 | 10 |
| `SPDAY05A.STR` | 22 | 566 | 576 | 10 |
| `SPDAY05B.STR` | 23 | 325 | 335 | 10 |
| `SPDAY06A.STR` | 24 | 436 | 446 | 10 |
| `SPDAY06B.STR` | 25 | 524 | 534 | 10 |
| `SPDAY07A.STR` | 26 | 522 | 532 | 10 |
| `SPDAY07B.STR` | 27 | 523 | 533 | 10 |
| `SPDAY08A.STR` | 28 | 649 | 660 | 11 |
| `SPDAY08B.STR` | 29 | 451 | 461 | 10 |
| `SPDAY09A.STR` | 30 | 465 | 475 | 10 |
| `SPDAY09B.STR` | 31 | 473 | 483 | 10 |
| `SPDAY10A.STR` | 32 | 411 | 421 | 10 |
| `SPDAY10B.STR` | 33 | 490 | 500 | 10 |
| `SPDAY11A.STR` | 34 | 467 | 479 | 12 |
| `SPDAY11B.STR` | 35 | 523 | 534 | 11 |
| `SPDAY12A.STR` | 36 | 187 | 197 | 10 |
| `SPDAY12B.STR` | 37 | 384 | 394 | 10 |
| `ASMK.STR` | 49 | 90 | 100 | 10 |

The 224,034 mixed sectors comprise **195,920 video**, **27,921 XA audio**, and
**193 zero-data filler** sectors. XA submode is classified before apparent
video magic, so audio bytes cannot be mistaken for frame headers. Mixed sectors
retain their original 2,336-byte extraction layout.

The fortieth STR record, `/CDI/ZDUMMY/ZDUMMY.STR`, uses data sectors. Its
61,937,664 bytes are hashed and preserved, but not parsed as movie data. It
contains nonzero data; its name is not grounds for discarding it.

## Original MIPS route checks

The verifier executes **620 bounded fixtures** through **15 original routines**:
thirteen game helpers and SDK `rand`/`srand`, with zero dependency-output stubs.
A complete unstripped diagnostic image equals the canonical executable,
qualifying actual ELF function extents and hashes before reuse in the verifier.

Checks cover nullable outputs, ignored ending arguments, six event routes,
twelve special days with six packed variants, two negative low-halfword values,
90 reel windows/counts, and all 50 signed thresholds. Special variants 0/1
select movies; variants 2–5 select still-image paths with index `-1`. Negative
low halfwords select event paths in these bounded contexts.

Reel thresholds retain the original sum of `(threshold + 10)` over `2 * count`
entries, then subtract ten. Zero count returns `-10`. This verifies native
arithmetic, not natural reachability or complete reel playback.

Sixteen seeded histories execute sixteen random opening choices each through
the original RNG. An independent integer recurrence checks the returned path,
optional output index, and RNG state. A 32-byte output guard, return address,
SP, GP, and callee-saved registers are checked. This is not whole-RAM comparison
or PS1 hardware-timing verification.

Three faults in owned VM memory are detected after reaching their targets:
unsigned threshold loading, a changed threshold, and a changed path character.
Original files are never patched.

## Repeat the checks

After a current canonical build, use the configured Linux/WSL environment:

```sh
python tools/inventory_movies.py \
  --layout /private/extraction/disc.xml \
  --edition-label "My verified reference edition" \
  --output .decomp-lab/movie-inventory-new.json
```

For original instruction execution, also install the pinned optional analysis
dependencies in `requirements-analysis.txt`:

```sh
python tools/verify_movie_paths.py \
  --output .decomp-lab/movie-paths-new.json
```

Both tools require a new private report path and a current matching build.
They make no model API calls. Full frame hashes and fixtures stay private;
[movie metadata](movie-inventory-checks.json) pins producers, reports, tables,
function ranges, file summaries, and unchanged recovery counts.

The parser is independently authored using the native consumers and Michael
Sabin's [PlayStation STR format document, v1.20](https://github.com/m35/jpsxdec/blob/fd5403629ac81aaca0feff0dc89e6cadd6353b26/jpsxdec/PlayStation1_STR_format.txt).
That document is MIT licensed; the separate jPSXdec program has a different
license. No converter implementation or original movie data is copied here.

At this structural-audit checkpoint, all 428 Python tooling tests passed with
owned fixtures. The standard build remained canonical after the comment
correction, with the other 391 protected inputs unchanged. The later
[startup playback comparison](MOVIE_PLAYBACK.md) adds runtime observations and
a clearer, matching viewport type; complete movie acceptance remains open.
C recovery remains **194,212 / 199,912 bytes**, with nine
assembly functions and 24 inherited storage explanations. Whole-feature
acceptance remains **0 / 40** provisional groups.
