# Glyph character interface

The glyph virtual table now declares the character setter with its glyph
receiver and the getter with its original unsigned-byte return. Previously,
the getter slot returned `void` and its initializer hid the mismatch behind a
cast. An ordinary C caller could not read a character through that slot.
The corrected declarations preserve the complete original executable.

## Recovered interface

| Slot | Method | Signature |
| --- | --- | --- |
| `0xC4` | `glyph_set_char` | `void (class_glyph_t *, u8)` |
| `0xC8` | `glyph_get_char` | `u8 (class_glyph_t *)` |

The existing slot identifiers remain intact. The glyph is `0xAC` bytes, its
character is at offset `0xA8`, and the virtual table is `0xCC` bytes. Eight
assertions compiled by the matching toolchain check these sizes, pointer and
byte widths, unsigned-byte conversion and slot offsets.

The same two analysis-only C callers were compiled before and after the
declaration correction. Against the previous header, GCC 2.6.3 exits with code
33 and a `void value` diagnostic. With the corrected header, both callers
compile and link: a 52-byte virtual getter and an 88-byte virtual setter/getter.
They are excluded from the game build.

## Native comparison

The checker executes the original 76-byte setter, 20-byte getter and 80-byte
region helper, together with the compiled analysis callers. The original
virtual table and region template are retained. No function outputs are
substituted.

| Entry | Distinct initialized inputs |
| --- | ---: |
| Direct original getter | 1,536 |
| Compiled virtual getter | 1,536 |
| Compiled virtual setter/getter | 1,584 |
| Total | 4,656 |

Both getter domains cover all 256 character bytes, three PS1 address aliases
and two initialized buffer patterns. The setter/getter domain uses all 256
byte values plus eight signed-word boundary and conversion inputs, across the
same aliases and patterns. The independent model narrows the code to eight
bits, selects its 32-column, eight-pixel atlas cell and checks coordinate-byte
wrapping. Every complete guarded glyph buffer, return word, method order and
saved register/stack boundary agrees.

Three separate faulted VMs detect a signed getter load, a misplaced character
store and an incorrect atlas-row mask. Each changed instruction executes in
its detecting input. The signed-load control uses the direct getter because a
typed byte-return caller could mask that fault. The positive code stays intact.

## Reproduce

Configure the [matching toolchain](../README.md#build-the-matching-executable), supply the canonical game
executable and install `requirements-analysis.txt` in WSL/Linux. With a current
canonical build, choose a fresh private output directory:

```bash
ninja check
python research/glyph_character/verify.py \
  --output .decomp-lab/glyph-character-new
python -m unittest discover -s tests
```

The checker refuses existing or public output directories and records its
source, toolchain and backend dependencies. Generated callers, compiler output,
game bytes and complete native buffers stay private.
[glyph-character-api-checks.json](glyph-character-api-checks.json) publishes
the corresponding counts, hashes, measured controls and scope.

## Acceptance boundary

Regular and fresh clean builds reproduce the entire 505,856-byte canonical
executable. All 306 objects were absent before the clean rebuild. Only the
glyph source and header change among the 392 pinned build inputs; the other
390 inputs retain their previous hashes.

This is an interface correction to existing C. Recovery stays at
194,212 / 199,912 C bytes (97.15%), with nine assembly functions, 24 inherited
storage explanations, 35 / 40 listed-core C groups and 32 / 107 bounded NPC
profiles. The getter's inherited sixteen-byte unused local remains unresolved.
These constructed checks establish no natural menu history, rendered pixels,
PS1 timing, whole NPC encounter or whole-feature acceptance. Original NPC AI,
AI-assisted analysis, optional mods and the separate Bevy port retain their
existing accounting.
