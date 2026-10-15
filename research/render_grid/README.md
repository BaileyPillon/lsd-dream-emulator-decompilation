# Grid-window C recovery

[c6a8_candidate.c](c6a8_candidate.c) is an **unaccepted research fragment** for
the original 660-byte `func_8004C6A8`. Its complete candidate executable differs
from the original at eight byte positions in two edge-arithmetic instructions.
The other 163 instruction words and every byte outside the function match.
The canonical game retains its assembly implementation.

The separate [cell-reuse candidate](c6a8_cell_reuse_candidate.c) differs in seven
bytes across four instruction words. It preserves the original subtraction
order but changes coordinate-load order and the longitudinal subtraction's
destination. The default above retains fewer changed instruction words; neither
source form matches. [The cell-ownership study](../../docs/GRID_CELL_OWNERSHIP.md)
records both measures, actual allocation observations and bounded comparisons.

Select that alternative with the existing preparation command:

```bash
python research/render_grid/prepare_candidate.py --variant cell-reuse \
  --output .decomp-lab/grid-cell-reuse-new
```

Omitting `--variant` keeps the eight-byte `edge` reference. Complete executable
equality remains the source acceptance gate for both variants.

Prepare the fragment in the current complete source unit:

```bash
python research/render_grid/prepare_candidate.py \
  --output .decomp-lab/grid-candidate-new

python tools/decomp_workbench.py check \
  --source src/scene/render_context.c \
  --candidate .decomp-lab/grid-candidate-new/render_context.c \
  --function func_8004C6A8 \
  --output .decomp-lab/grid-candidate-build-new
```

The preparation script preserves the current source and replaces only the
selected assembly inclusion in a fresh private file. Build in Linux/WSL with
the configured toolchain and original executable. The check currently returns
exit code 1 because eight differences remain; no promotion is allowed.

The fragment uses the source unit's existing lookup-output type, real local
width/height parameters, the original 32-byte matrix layout and consumed row/column
setters. It adds no dummy storage, physical-register binding, instruction
substitution or copied assembly. Compiler flags are unchanged.

[The edge-lifetime study](../../docs/GRID_PHASES.md#inclusive-edge-lifetime-study)
records the improved fragment, actual allocation observations and a repeated
74,832-case original/candidate scalar comparison. Position lookup, rotation,
matrix application and the builder retain four explicit contracts in that
comparison. Original scenes, hardware timing and whole-feature acceptance
remain separate requirements.

[GRID_RECOVERY.md](../../docs/GRID_RECOVERY.md) preserves the earlier
eleven-byte fragment and comparison snapshot.

## Read qualified compiler phases

The initial [phase comparison](../../docs/GRID_PHASES.md) follows the incoming-height
copy through seven actual compiler stages in both formal and local source forms.
It identifies the first scheduling pass's order change and rechecks complete
eleven- and thirteen-byte candidates. A further 133 qualified source forms have
no exact match; the canonical game retains assembly.

`inspect_compiler_phases.py` reads qualified outputs of the existing allocation
tracer. It checks every preserved input and pinned artifact, reconstructs
qualification and writes a new private journal. Function-begin note positions
are stage-specific; late note relocation does not establish original source.
