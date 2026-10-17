# Text and render callback input storage

Two inherited C functions now retain their original stack layouts through
consumed callback inputs. Their unused four-byte and 24-byte locals are
removed, together with the render routine's empty address-comparison branch.
The identified storage remainder falls from **8 to 6**. These **432 function
bytes already counted as C**; matching C remains **195,844 / 199,912 (97.97%)**.

The source, compiler observations and complete builds are recorded in
[text-callback-storage-checks.json](text-callback-storage-checks.json).

## Reconstructed inputs

| Original function | Bytes / frame | Consumed input |
| --- | ---: | --- |
| `func_8003D2CC` at `0x8003D2CC` | 228 / 48 | Text-data pointer passed to each line's original callback |
| `func_8004ADD8` at `0x8004ADD8` | 204 / 64 | Receiver, resource pointer and event kind passed to a matching render callback |

The text helper carries the same pointer already supplied to the line's
`Unk45` method. The original loop order, selection save/restore and conditional
screen callback remain intact. Its one-field view is checked to occupy four
bytes, and the field supplies the actual argument.

The render routine retains its original event switch and zero-terminated
filter scan. Only an existing match constructs the three input views. Each
contains exactly one checked four-byte value; every value supplies the original
virtual call. The callback order and the subsequent list read remain intact.
There are no unused record fields or repeated identity-helper chains.

These are matching source explanations, not recovered copies of the original
author's declarations. Neither change adds a game feature, compiler option,
physical register binding or instruction substitution.

## Observed compiler allocation

Six complete-unit observations cover each original source, its removed-storage
control and its matching reconstruction. For every observation, normal and
GDB-observed complete assembly agree. The observer changes no inferior memory
or instructions and invokes no extra inferior functions.

| Function | Original local allocation | Removed-storage control | Matching reconstruction |
| --- | --- | --- | --- |
| Text update | Four-byte request, eight-byte frame region | No local request | One four-byte reload request, eight-byte region |
| Render dispatch | 24-byte request, 24-byte frame region | No local request | Three four-byte reload requests, eight bytes each |

The compiler's `alter_reg` contexts identify the reconstruction requests.
The regions above are part of the complete 48-byte and 64-byte frames, which
also include the routines' ordinary call and saved-register areas. The final
linked instructions, including prologue and epilogue, match the original.

To inspect a complete source unit in the configured WSL/Linux environment:

```bash
python research/collision/trace_compiler_stack.py \
  --source src/menu/ui_screen.c \
  --output .decomp-lab/text-callback-allocation-new
python research/collision/trace_compiler_stack.py \
  --source src/scene/render_context.c \
  --output .decomp-lab/render-callback-allocation-new
```

These commands require GDB and the pinned bundled compiler. They observe
compiler allocation; they do not execute the game.

## Build evidence and remaining gates

Both fully relocated, sized ELF functions match their complete original spans.
Retaining diagnostic symbols produces the same entire executable. The ordinary
build and a fresh Git-archive build with both changed units reproduce all
**505,856 original bytes**. The fresh build compiles **306 objects** with the
pinned toolchain and MASPSX revision. The other 390 protected build inputs and
the canonical executable remain unchanged.

The six remaining identified inherited storage explanations are:

- `debug_file_driver_unk15`
- `debug_file_driver_open`
- `func_80044F90`
- `func_80045060`
- `func_80044D40`
- `func_80044E64`

Five game assembly fallbacks also remain. Bounded original NPC coverage is
**36 / 107**, and whole-feature acceptance is **0 / 40** provisional groups.
This source-layout recovery adds no runtime input domain or natural gameplay
comparison. The [play launcher](PLAYING.md) still uses the matching executable;
no new play session is claimed here. All requirements in the
[frozen objective](../PROJECT_OBJECTIVE.md) remain in force. Original game
behavior, optional mods, AI-assisted tools and the
separate Bevy port retain their existing boundaries.
