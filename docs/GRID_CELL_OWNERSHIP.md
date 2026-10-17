# Grid cell ownership and matching-C boundaries

This historical study predates the [matching grid-window recovery](GRID_MATCHING_C.md).
The canonical function is now C with complete-executable equality; the two
rejected source forms and their measurements below are retained as evidence.

The grid-window function now has two reproducible, unaccepted C source forms.
They make different source choices and leave different native instructions
unexplained. Neither satisfies complete executable equality.

| Research form | Changed executable bytes | Changed instruction words | Function / frame bytes |
| --- | ---: | ---: | ---: |
| Existing `edge` reference | 8 | 2 | 660 / 152 |
| New `cell-reuse` alternative | 7 | 4 | 660 / 152 |

The [existing reference](../research/render_grid/c6a8_candidate.c) remains the
default because it changes fewer instruction words. The
[alternative](../research/render_grid/c6a8_cell_reuse_candidate.c) has fewer
differing byte positions. These are separate diagnostics, not percentages of
recovered gameplay or proof that one source is the original author's code.
The canonical game retains `func_8004C6A8` in assembly.

## Source and native differences

The alternative computes the first inclusive edge as `x - width + 1`. In the
longitudinal branch it converts the real Z cell to the far edge:

```c
if (matrix.vector.z > 0) {
    origin = z;
} else {
    z -= height;
    origin = z + 1;
}
```

Every changed value is consumed. It introduces no dummy storage, extra record
tails, physical-register bindings, compiler-flag changes or embedded assembly.
Its complete 505,856-byte image has SHA-1
`262c2ba58cd2533c14d0227e7e2d096d84407c58`.

Only four words differ from the original executable. The two coordinate loads
at `0x8004C700` and `0x8004C704` exchange order. The longitudinal subtraction at
`0x8004C88C` writes the updated Z register rather than the original temporary;
the following addition reads that updated register. All other executable bytes
match, including the first edge's subtract-then-add sequence. Those remaining
differences prohibit promotion into matching C.

## Observed allocation

Four observations use the exact bundled compiler and the public
[allocation tracer](../research/compiler/trace_allocation.py). Every observed
compilation preserves complete assembly, agrees with the emitted register
dispositions and passes the independently calculated priority comparisons.
Each run observes fourteen global allocations. Register names here describe
the compiler's results; the C source never binds them.

| Complete-unit source | Width refs / live length / register | Z refs / live length / register |
| --- | --- | --- |
| Formal arithmetic control | 4 / 52 / `s6` | 5 / 65 / `s7` |
| Z read after angle load | 4 / 52 / `s6` | 5 / 65 / `s7` |
| Z read after angle adjustment | 4 / 52 / `s7` | 5 / 63 / `s6` |
| Cell-reuse alternative | 4 / 52 / `s7` | 7 / 70 / `s6` |

Moving the Z read past the angle load leaves identical complete function bytes
and allocation. Moving it past the adjustment changes priority and restores
the native arithmetic, but relocates six instructions near the function start.
The cell-reuse form raises Z's priority through actual value uses and restores
the native persistent-register choices, while leaving the four differences
above. Simple source statement movement and scalar helper boundaries do not
therefore explain the entire original sequence.

Sixty-three complete source units compile and link: fifteen coordinate-read
forms, thirteen split-arithmetic forms, ten coordinate-ownership forms, eight
angle representations, eight longitudinal-helper forms and nine Z-result/type
forms. These include twelve repeated controls. One failed source-pattern
preparation is excluded because it never reached compilation. No form matches
the complete original executable. Private
full-function comparisons retain length differences separately from changed
bytes within the common range.

## Bounded execution

The alternative is compared with the original in the same **74,832 distinct
scalar fixtures per image** used for the earlier reference. Both full positive
images are checked against the initial VM program bytes before execution. All
four differing instructions execute. The checks compare whole guarded buffers,
ordered dependency requests, matrix/template data, stack state and saved
registers against the existing independent integer model.

All eight retained original-image controls are detected. Two additional
candidate-image controls also fail as expected: an unsigned Z load and an
incorrect longitudinal inclusive end. The positive runs execute the actual
compiled instructions unchanged. All fault mutations stay in separate private
Unicorn memories.

This repeats existing fixture classes for a different candidate image; it adds
no new original scenario class. Position lookup, `RotMatrix`, `ApplyMatrixLV`
and the grid builder retain four explicit contracts. Natural scenes, actual
SDK/GTE composition, GPU/audio output and PS1 timing remain separate gates.

## Reproduce

Use the matching Linux/WSL compiler environment and a current canonical build:

```bash
python research/render_grid/prepare_candidate.py --variant cell-reuse \
  --output .decomp-lab/grid-cell-source-new
python tools/decomp_workbench.py check \
  --source src/scene/render_context.c \
  --candidate .decomp-lab/grid-cell-source-new/render_context.c \
  --function func_8004C6A8 --output .decomp-lab/grid-cell-build-new
```

The expected matching-gate result is exit code 1 with seven differing bytes.
Omit `--variant`, or use `--variant edge`, for the retained eight-byte reference.
Both preparations require fresh private directories and preserve canonical
source. Unsupported variant names are rejected before output creation.

[grid-cell-ownership-checks.json](grid-cell-ownership-checks.json) pins the
published fragments, reproductions, native comparison, allocator observations,
source studies and before/after measures. All 392 protected build inputs remain
unchanged. C recovery stays 194,212 / 199,912 bytes (97.15%), with nine remaining
assembly functions, 24 inherited storage explanations and 22 / 107 bounded NPC
callbacks. Original behavior, developer capabilities and optional mods retain
separate counts; no whole-feature or whole-NPC acceptance is added.
