# Matching sprite scaling and cell bounds

`func_8004441C` (560 bytes) and `func_8004CD38` (108 bytes) now compile from C
with every original instruction preserved. The combined standard build and a
fresh 306-object build reproduce the complete 505,856-byte Japanese executable.
[Recorded checks](ui-scale-bounds-matching-c-checks.json) identify the source,
compiler, assembler, complete functions and build evidence.

| Measure | Before | After |
| --- | ---: | ---: |
| Matching game C bytes | 196,504 / 199,912 | 197,172 / 199,912 |
| Matching game C coverage | 98.30% | 98.63% |
| Remaining game assembly functions | 4 | 2 |
| Remaining game assembly bytes | 3,408 | 2,740 |
| Listed-core C groups | 37 / 40 | 38 / 40 |
| Unexplained inherited storage functions | 2 | 2 |
| Whole feature groups independently accepted | 0 / 40 | 0 / 40 |

F035 now has every listed core function in C. F008 retains the hull/face query
and F033 the primitive-face query. The 40-group inventory is provisional;
source coverage does not establish an exhaustive feature total or runtime parity.

## Source and attribution

The implementations were adapted from `brian-oblivion/lsddecomp` at commit
`90a398e4f429b4371be05648605fc198b9efb395`:

- [BgLayer__UpdateScale](https://github.com/brian-oblivion/lsddecomp/blob/90a398e4f429b4371be05648605fc198b9efb395/src/graphics/bg_layer.c)
  supplies the signed-halfword ratio records, replacement clamp and additive
  scale behavior. The local function uses the existing sprite layout and names.
- [IsPointOutOfBounds](https://github.com/brian-oblivion/lsddecomp/blob/90a398e4f429b4371be05648605fc198b9efb395/src/world/stage_map.c)
  supplies the signed cell record and inclusive in-range expression. The local
  function keeps the existing bounds/byte-pointer ABI with a signed cell view.
- The upstream [CC0 dedication](https://github.com/brian-oblivion/lsddecomp/blob/90a398e4f429b4371be05648605fc198b9efb395/LICENSE)
  covers this original project code. Source comments retain the commit and names.

Downloaded files were checked against their commit-pinned Git blob hashes.
The local names, layout mapping, qualifiers and constants were reviewed and
recompiled before import. This project retains its original compiler flags and
unmodified pinned assembler. No external setup script or assembler patch was
executed. Neither imported function adds unused storage, inline instructions,
physical register bindings or a binary replacement.

The external project's complete-decompilation claim is separate from these
checks. Its two other collision implementations include explicitly unused
storage and were retained as reference material. They were not imported.

## Verification and limits

Each function first passed a complete relocated-function comparison and a
complete-unit executable comparison. Final local names/comments were qualified
again. Independent `objcopy` extraction agrees with the original complete
function bytes. The combined standard and fresh builds then preserve the entire
original image, including both remaining assembly functions. Only two of 392
protected game build inputs change; the other 390 retain their hashes.

The earlier [sprite audit](UI_SCALE.md) and [bounds comparison](BOUNDS_NARROW_COMPARISON.md)
retain their original bounded fixture evidence. No new fixture domain, natural
replay, whole feature acceptance or NPC encounter acceptance is counted here.
The sprite's skipped zero-denominator division still leaves a machine-register
value available in additive mode; the recovered source preserves those original
bytes rather than defining a new portable host-C behavior for that input.

After configuring the documented matching toolchain and providing your original
executable, reproduce the combined build from the repository root:

```bash
python configure.py
ninja check
python tools/progress.py --json
```

Expected executable SHA-1: `76322eeade5ebb22dca57fdeac7d68c30f06308d`.
The separate Bevy/Rust repository and the running player profile are unchanged.
