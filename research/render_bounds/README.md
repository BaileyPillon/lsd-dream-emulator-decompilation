# Bounds predicate source research

[`bounds_candidate.c`](bounds_candidate.c) is an **unaccepted** C reconstruction
of the original 108-byte `func_8004CD38`. Its complete executable differs from
the canonical game at **19 byte positions**, all within this function. The
matching build continues to use the original assembly.

The fragment uses the twelve-byte mixed-width bounds type from the existing
header. It recovers signed coordinates from two unsigned bytes. The initial
address argument is preserved as a pointer, then reused as a comparison operand.
This is a source-lifetime hypothesis for the configured 32-bit MIPS ABI; it does
not identify the original author's declarations or certify portable host C.

## Prepare and compare

Preparing the file needs the source tree but no game inputs. The recipe checks
the current prototype, caller and assembly inclusion before creating a fresh
private directory. It preserves existing outputs and canonical source files.

```bash
python research/render_bounds/prepare_candidate.py \
  --output .decomp-lab/bounds-candidate-new
python tools/decomp_workbench.py check \
  --source src/scene/render_context.c \
  --candidate .decomp-lab/bounds-candidate-new/render_context.c \
  --function func_8004CD38 \
  --output .decomp-lab/bounds-candidate-new/build
```

The second command requires your canonical executable and configured toolchain.
**Expected matching-gate result: exit code 1**, a 505,856-byte image, zero length
difference and 19 changed bytes. Retain that failed gate. Promote the fragment
only after the complete executable matches and the source explanation is reviewed.

The [current comparison](../../docs/BOUNDS_NARROW_COMPARISON.md) records the
complete linked function, native fixture boundary and actual compiler allocation.
The [source-lifetime report](../../docs/BOUNDS_SOURCE_LIFETIMES.md) retains the
preceding 21-byte source snapshot and its original evidence.
The [original predicate profile](../../docs/RENDER_BOUNDS.md) documents read
order, inclusive edges, mixed widths and the null-input rule.

## Compare constructed inputs

With `requirements-analysis.txt` installed, use the complete workbench image
and sized diagnostic ELF produced above:

```bash
python research/render_bounds/compare_candidate.py \
  --candidate .decomp-lab/bounds-candidate-new/build/candidate.exe \
  --symbols .decomp-lab/bounds-candidate-new/build/candidate-symbols.elf \
  --output .decomp-lab/bounds-candidate-new/native
```

The checker requires canonical bytes outside the complete function and verifies
that retaining symbols preserves the entire image. It compares the original,
candidate and independent model on 4,648 existing inputs. All changed instruction
words must execute, and four candidate-local faults must produce wrong returns.
An altered instruction layout requires control review; an exception alone is
not a successful fault detection. No function-output stubs are used.

## Observe allocation

In the configured WSL/Linux environment with GDB:

```bash
python research/compiler/trace_allocation.py \
  --source .decomp-lab/bounds-candidate-new/render_context.c \
  --function func_8004CD38 --output .decomp-lab/bounds-allocation-new
```

Normal and observed complete assembly must agree. Diagnostic options may change
only compiler-option comments. Reported registers describe observed decisions;
the fragment binds no physical registers and changes no compiler flags.

Agreement on the existing 4,648 native inputs does not establish renderer,
stage, framebuffer or PS1 timing parity. This research adds no accepted C bytes,
original feature, whole NPC encounter, optional mod or developer-capability category.
