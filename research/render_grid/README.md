# Grid-window C recovery

[c6a8_candidate.c](c6a8_candidate.c) is an **unaccepted research fragment** for
the original 660-byte `func_8004C6A8`. Its complete candidate executable differs
from the original at eleven byte positions in three prologue instructions.
The other 162 instruction words and every byte outside the function match.
The canonical game retains its assembly implementation.

Prepare the fragment in the current complete source unit:

```bash
python research/render_grid/prepare_candidate.py \
  --output .decomp-lab/grid-candidate-new

python tools/decomp_workbench.py check \
  --source src/scene/render_context.c \
  --candidate .decomp-lab/grid-candidate-new/render_context.c \
  --output .decomp-lab/grid-candidate-build-new
```

The preparation script preserves the current source and replaces only the
selected assembly inclusion in a fresh private file. Build in Linux/WSL with
the configured toolchain and original executable. The check currently returns
exit code 1 because eleven differences remain; no promotion is allowed.

The fragment uses the source unit's existing lookup-output type, real local
width/height values, the original 32-byte matrix layout and consumed row/column
setters. It adds no dummy storage, physical-register binding, instruction
substitution or copied assembly. Compiler flags are unchanged.

[GRID_RECOVERY.md](../../docs/GRID_RECOVERY.md) records compiler observations,
ordered-store results and comparison hashes. Original scenes, hardware timing
and whole-feature acceptance remain separate requirements.
