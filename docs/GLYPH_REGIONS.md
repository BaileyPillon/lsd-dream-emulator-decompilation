# Glyph source regions

Glyph construction and character changes now use the twelve-byte region that
the original helper writes, replacing two sixteen-byte byte arrays. The helper
has a typed output pointer and named coordinate fields. The regular and fresh
clean builds reproduce the complete canonical executable. This improves existing
matching C and adds no newly recovered assembly bytes.

## Recovered representation

`func_80041C4C` copies three template words and adjusts the two coordinate
halfwords after masking the character code to eight bits. The caller passes
the region through `sprite_node_construct` to common sprite setup.

| Offset | Field | Observed use |
| --- | --- | --- |
| `0x00` | `u16 u` | Horizontal source coordinate; the character selects a column in a 32-column, eight-pixel grid |
| `0x02` | `u16 v` | Vertical source coordinate; the character selects an eight-pixel row |
| `0x04` | `u32 width` | Template word copied into sprite state; common setup reads its low halfword as width |
| `0x08` | `u32 height` | Template word copied into sprite state; common setup reads its low halfword as height |

All twelve bytes belong to the copied region. The dimension fields retain their
complete word storage; the observed halfword consumers do not establish uses
for their upper halves. The character setter keeps the original signed-byte
conversion before writing the low coordinate bytes into the sprite command.
The type remains local to the glyph translation unit, where both direct
callers and the helper are defined.

## Compiler allocation and matching evidence

Two actual GCC 2.6.3 observations cover the complete translation unit with the
configured G8 flags. For each observation, normal and observed compiler output
agree in their complete assembly files.

| Function | Previous requested / allocated local bytes | Typed region requested / allocated local bytes | Complete function frame |
| --- | ---: | ---: | ---: |
| `glyph_construct` | 16 / 16 | 12 / 16 | 48 |
| `glyph_set_char` | 16 / 16 | 12 / 16 | 40 |

The compiler rounds each real region to sixteen local bytes. The additional
four-byte source tails are unnecessary. This is evidence for a matching source
representation; it does not identify the original author's exact declarations.

A link retaining sized ELF symbols verifies all seven complete glyph functions.
Converting that ELF back to a binary reproduces the entire 505,856-byte original
executable, SHA-256
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.
Thirteen target-compiled assertions check record size, alignment, field offsets,
glyph size and virtual-slot offsets. An incorrect sixteen-byte record assertion
is rejected. Regular and fresh clean builds separately retain canonical equality.

[glyph-region-checks.json](glyph-region-checks.json) records source and private
evidence hashes, complete function checks, compiler observations and before/after
measurements. Original files, generated assembly, linked images and compiler
traces stay private.

With the configured WSL/Linux toolchain and GDB, observe the current allocation
in a fresh private directory:

```bash
python research/collision/trace_compiler_stack.py \
  --source src/menu/glyph.c --output .decomp-lab/glyph-stack-new
ninja check
```

## Remaining scope

The separate `glyph_get_char` function still has its inherited sixteen-byte
unused local declaration. It is one of the 24 unresolved functions in the
[selected storage audit](SOURCE_LAYOUT_EXPANDED.md). These two caller tails
were outside that audit; removing eight source bytes does not reduce its count.

C recovery remains 194,212 / 199,912 bytes (97.15%), with nine assembly fallbacks,
35 / 40 listed-core C groups and 28 / 107 bounded NPC profiles. No new native
fixture campaign, emulator replay, whole NPC encounter or entire feature group
is accepted by this change. Original behavior, AI-assisted tools, optional mods
and the separate Bevy port retain their existing accounting.
