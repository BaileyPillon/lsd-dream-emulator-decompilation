# Source recovery quality

> Historical selected-function audit. The subsequent
> [expanded audit](SOURCE_LAYOUT_EXPANDED.md),
> [callback recovery](CALLBACK_STORAGE_RECOVERY.md) and
> [constructor/actor recovery](CONSTRUCTOR_ACTOR_STORAGE.md) supersede its
> counts. Seventeen identified inherited storage explanations remain open;
> the measurements below retain their original scope.

The current complete executable matches the original, with 194,884 of 199,912
game-function bytes compiled from C. That byte count includes **five existing
C functions with explicit dummy stack padding**. They need source recovery
work under the project's no-padding requirement, in addition to the six
functions still retained in assembly.

This audit identifies the literal `dummy_stack_padding` declarations and their
empty pointer-comparison branches. It does not certify the absence of every
possible source workaround. SDK vector layout padding and original file-format
padding are separate, necessary representation details.

## Verified existing workarounds

Each function was tested by removing its declaration and empty branch in a
fresh, complete translation unit, then comparing the whole candidate image.

| Function | Source | Dummy local bytes | Original / removal frame | Changed executable bytes |
| --- | --- | ---: | ---: | ---: |
| `func_80051AC8` | [select menu](../src/menu/card/select_menu.c) | 8 | 56 / 48 | 18 |
| `memory_card_wait_event` | [memory card](../src/menu/card/memory_card.c) | 8 | 56 / 48 | 16 |
| `func_8004F810` | [memory card](../src/menu/card/memory_card.c) | 8 | 40 / 32 | 8 |
| `func_8004FBE4` | [memory card](../src/menu/card/memory_card.c) | 8 | 56 / 48 | 10 |
| `func_8004ADD8` | [render context](../src/scene/render_context.c) | 24 | 64 / 40 | 12 |

All five candidate images remain 505,856 bytes long. Every difference is
confined to the selected function and changes only an SP-relative displacement;
instruction opcodes, register choices and function lengths remain intact.
None passes the exact executable gate. The canonical source is preserved.

The declarations total 56 local bytes. The five mapped code spans total
1,504 bytes; these are code-range measurements, not additional C recovery.
Boundaries come from current link-map function starts through the next distinct
named symbol. The canonical ELF is stripped, so its absent symbol table was
not used to assert function sizes.

Git history and the frozen pre-prompt commit
`16a3914b9bcb75bd94a6b983ed3a952234461625` show that the five declarations
already existed before this reverse-engineering prompt. The audit adds no
padding, changes no original behavior and promotes no source function. Earlier
byte-coverage and feature records remain frozen; their counts are still valid
as C-compilation and original-behavior inventories.

## Reproduce a private removal check

Copy one listed source file into a fresh directory under `.decomp-lab` and
remove only the selected function's `dummy_stack_padding` declaration and its
empty pointer-comparison branch. For the first row, run:

```bash
python tools/decomp_workbench.py check \
  --source src/menu/card/select_menu.c \
  --candidate .decomp-lab/source-quality-new/select_menu.c \
  --output .decomp-lab/source-quality-new/build
```

The recorded removal returns an unsuccessful matching gate, with 18 changed
bytes. This is a diagnostic candidate, not an accepted patch. Replacing the
dummy array with another unused object, unreachable branch or instruction copy
would leave the source explanation unresolved.

## Collision inline argument result

The preceding [compiler lifetime investigation](COMPILER_LIFETIMES.md) measured
reuse of helper-owned square storage. Ten additional by-value segment-helper
forms now compile successfully, but their actual best result differs in 1,631
bytes. A compiler trace retains 48 allocator calls with complete assembly equal
to normal compilation. The selected form allocates a 32-byte incoming-argument
area, growing the virtual local area from 76 to 112 bytes, then a 144-byte
inline local area, growing it to 256. This does not explain the original early
16-byte region; the previously published 22-byte candidate remains the best.

[source-quality-checks.json](source-quality-checks.json) pins the five complete
removal builds, independent stack-displacement checks, pre-prompt provenance,
ten source comparisons, actual compiler observations and canonical build.
The current 305-object executable retains byte equality. These compiler and
source checks execute no original gameplay and add no whole-feature acceptance.
NPC, feature, developer-capability and optional-mod counts remain unchanged.

The remaining work is six assembly functions, five known source workarounds,
the broader source/SDK audit and the existing asset, dispatch and reviewed
runtime requirements. Actual source or inline boundaries must explain the
original storage before a replacement can be accepted.
## Wider audit and corrected current status

This five-function report is a historical selected-name audit. The later
[expanded review](SOURCE_LAYOUT_EXPANDED.md) checks 28 unused-storage functions,
withdraws four padded C promotions and retains 24 inherited source explanations.
Current source is 194,212 / 199,912 C bytes with nine assembly functions.
The earlier comparison results stay frozen; their limited search boundary does
not establish the total number of source workarounds.
