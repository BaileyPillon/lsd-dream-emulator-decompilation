# Unaccepted source-layout candidates

The four primary C fragments in this directory retain the readable behavior of earlier
promotions while removing their added unused stack arrays. They remain outside
the canonical build because their complete executable comparisons differ.

| Fragment | Complete source unit | Differing bytes |
| --- | --- | ---: |
| `dream_generation_update_structure_entities.c` | `src/dream/dream_generation.c` | 10 |
| `dream_generation_find_entry.c` | `src/dream/dream_generation_post.c` | 20 |
| `func_8003D73C.c` | `src/menu/ui_screen.c` | 20 |
| `func_8003DAD4.c` | `src/menu/ui_screen.c` | 16 |

Copy the current complete source unit into a fresh `.decomp-lab` directory and
replace the selected `INCLUDE_ASM` with the fragment. Existing unit types and
declarations supply the fragment's dependencies. Then run:

```bash
python tools/decomp_workbench.py check \
  --source src/dream/dream_generation.c \
  --candidate .decomp-lab/layout-new/dream_generation.c \
  --output .decomp-lab/layout-new/build
```

The complete image must match before promotion. Preserve original storage and
ABI behavior through real source lifetimes or helper boundaries; adding unused
arrays, dead branches or instruction substitutions does not close this gate.
The [expanded audit](../../docs/SOURCE_LAYOUT_EXPANDED.md) records the withdrawal,
current standard/clean matching builds and separate source-quality counts.

The later [generation structure checks](../../docs/GENERATION_STRUCTURES.md)
type the update argument as the caller's position pointer. Its complete image
still differs in ten bytes. `structure-update-pointer.c` and
`structure-update-value.c` test two additional live argument-pair hypotheses;
their complete images grow by four and 28 bytes, respectively. These hypotheses
are separate from the four withdrawal candidates and remain outside the game.
Copy either fragment at the same generation-update inclusion and run the
complete-unit workbench above. Actual compiler observations show the added
live storage and stores; neither reproduces the original source lifetime.
