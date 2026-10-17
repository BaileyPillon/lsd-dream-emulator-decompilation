# Atlas and tile-buffer input storage

Four existing C routines now retain their original frames through consumed
lookup, invocation, mode and allocation inputs. Three unused 32-byte arrays
and one unused eight-byte array are removed: **104 declared bytes** in total.
The identified inherited storage remainder falls from **6 to 2**.

These **532 function bytes already counted as C**. Matching C remains
**195,844 / 199,912 (97.97%)**, with five game assembly fallbacks. Source,
compiler and build evidence is recorded in
[atlas-tile-storage-checks.json](atlas-tile-storage-checks.json).

## Reconstructed inputs

| Original function | Bytes / frame | Consumed input roles |
| --- | ---: | --- |
| `func_80044F90` at `0x80044F90` | 124 / 64 | Base-driver descriptor, constructor method, receiver and construction mode |
| `func_80045060` at `0x80045060` | 84 / 56 | Update-gate reference, method table, receiver and update method |
| `func_80044D40` at `0x80044D40` | 136 / 64 | Base-driver descriptor, constructor method, receiver and construction mode |
| `func_80044E64` at `0x80044E64` | 188 / 40 | Byte count passed to the existing index allocation |

The inline helpers perform the original method lookup, invocation, mode test
or allocation. Their four-byte views contain one field each, checked with
`sizeof`; every field contributes to that operation. There are no unused tails
or repeated identity-helper chains.

Both constructors retain the original base call, vtable replacement, member
stores and conditional initialization. Atlas update reads its method table
only when the original gate is clear, then performs the original callback and
post-call flag store. Tile allocation retains its original allocation result,
index loop and release path. The complete linked instructions match; no new
runtime calls survive compilation.

These are matching source explanations. The original author's declarations
are unknown, and matching bytes do not establish natural construction or
rendering coverage.

## Observed compiler allocation

Six complete-unit observations cover baseline, removed-storage and matching
versions of each source unit. Each observation checks complete normal assembly
against the GDB-observed assembly. No inferior memory or instructions are
rewritten, and no extra inferior functions are invoked.

| Function | Control local region | Matching reload requests | Restored frame region |
| --- | ---: | ---: | ---: |
| Atlas constructor | 0 | Four requests of four bytes | 32 bytes |
| Atlas update | 0 | Four requests of four bytes | 32 bytes |
| Tile constructor | 0 | Four requests of four bytes | 32 bytes |
| Tile allocation | 0 | One request of four bytes | 8 bytes |

The 13 actual `alter_reg` requests each reserve an eight-byte region in this
compiler. These regions are part of the full frames in the first table; saved
registers and ordinary call areas remain separately present. Flat initialized
record candidates were insufficient: they reserved only 16 bytes for atlas
update and 24 for the constructors. The functional input boundaries recover
the missing lifetimes without adding unused fields or bound registers.

To observe either complete unit in the configured WSL/Linux environment:

```bash
python research/collision/trace_compiler_stack.py \
  --source src/menu/sprite_atlas.c \
  --output .decomp-lab/atlas-input-allocation-new
python research/collision/trace_compiler_stack.py \
  --source src/menu/tile_buffer.c \
  --output .decomp-lab/tile-input-allocation-new
```

These commands require GDB and the pinned compiler. They observe compilation;
they do not run gameplay.

## Preserved count read

Tile allocation's existing `*(volatile u16 *) &This->m_Unk10_2` read is retained
literally. Replacing it with an ordinary read folds the count expression and
produces a nonmatching 172-byte function instead of the original 188 bytes.
Borrowed-reference alternatives also fail. Those comparisons remain private;
the matching reconstruction introduces no new volatile constraint.

The allocation helper explains the inherited eight-byte region independently
of that read. This report does not claim the original author's reason for the
volatile access.

## Build evidence and remaining gates

All four fully relocated sized functions match their complete original spans.
Diagnostic links retaining symbols produce the same complete executable.
The ordinary build and a fresh **306-object** Git-archive build containing both
changed units reproduce all **505,856 original bytes**. The other 390 protected
build inputs remain unchanged. Tooling results are recorded in the metadata;
no additional native-game or gameplay run is claimed here.

Two identified storage explanations remain: `debug_file_driver_unk15` and
`debug_file_driver_open`. Their original bodies only reserve and release
64-byte frames. They remain explicit; discarded work or invented fields do
not establish their source explanation.

Five game assembly functions remain. Bounded original NPC comparisons stay
**36 / 107**, and whole-feature acceptance stays **0 / 40** provisional groups.
The [play launcher](PLAYING.md) retains the matching executable. All requirements
in the [frozen objective](../PROJECT_OBJECTIVE.md) remain in force. Original
behavior, optional mods, AI-assisted tools and the separate Bevy port remain
distinct.
