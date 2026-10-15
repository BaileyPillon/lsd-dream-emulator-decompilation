# Sprite-scale source recovery

[scale_candidate.c](scale_candidate.c) is an unaccepted, padding-free C
candidate for the original 560-byte `func_8004441C`. Its complete executable
still differs at twelve byte positions across four instructions. The game
continues to use the original assembly.

The [native scaling profile](../../docs/UI_SCALE.md) records signed ratios,
clamping, input-overlap behavior and 203,472 original/candidate fixtures per
image. This candidate has the same linked function bytes as that tested image;
those are retained fixtures rather than new gameplay coverage.

## Reproduce the source comparison

After a current matching build, run from the repository in Linux or WSL:

```bash
python research/ui_scale/prepare_candidate.py \
  --output .decomp-lab/ui-scale-new
python tools/decomp_workbench.py check \
  --source src/menu/ui_sprite.c \
  --candidate .decomp-lab/ui-scale-new/ui_sprite.c \
  --function func_8004441C \
  --output .decomp-lab/ui-scale-new/build
```

The preparer copies a complete unit into a fresh private directory. The
canonical source, compiler flags and linker inputs remain intact. A nonzero
comparison result is expected until the twelve differences are resolved.

For actual compiler allocation evidence:

```bash
python research/collision/trace_compiler_stack.py \
  --source .decomp-lab/ui-scale-new/ui_sprite.c \
  --output .decomp-lab/ui-scale-new/stack
```

The extended tracer identifies completed `alter_reg` callers behind allocation
events. In this candidate, pseudos 141 and 155 each request a four-byte local
slot, rounded to eight bytes, during register reload. Normal and observed
complete compiler assembly must agree. This explains the candidate's frame;
it does not prove the original source used the same construction.

## Keep the native behavior boundary visible

The original can skip a ratio calculation when its denominator is zero and
then consume the incoming register value in increment mode. The candidate
retains uninitialized C ratios for that source hypothesis. Initializing them
would change the observed native corner cases. This is not a portable,
defined C interface for those inputs, and the fragment is not accepted into
the game. The [scaling guide](../../docs/UI_SCALE.md) records the model,
overlap order, signed narrowing and remaining source/runtime gates.
