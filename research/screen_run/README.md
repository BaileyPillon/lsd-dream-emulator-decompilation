# Typed screen Run verification

These analysis callers use the real UI, main-menu and chart headers. They are
excluded from the game build. The checker compiles them with GCC 2.6.3 and
executes their complete bodies with the original UI/chart methods and table
getters. See [the interface findings](../../docs/SCREEN_RUN_INTERFACES.md) for
the corrected declarations and evidence limits.

From the repository root in the supported Linux/WSL environment, with the
canonical executable and optional analysis dependencies available:

```bash
python configure.py
ninja check
python research/screen_run/verify.py --output .decomp-lab/screen-run-new
```

Use a fresh output directory under `.decomp-lab`; existing outputs are
preserved. The checker requires a current complete matching build. It saves
the compiled callers, compiler/linker artifacts and a hash-pinned report.
It makes no model API calls and changes no game source or original inputs.

The graphics initializer is an explicit contract, not native initialization.
It validates all arguments, writes the case's result/flag, clobbers
caller-saved registers and supplies an unrelated return word. The original
screen methods must obtain their results from the real receiver fields after
that call. Full guarded objects, exact return words, original dispatch order
and the saved-register/stack ABI are compared for direct and typed calls.
Three isolated instruction faults must execute and change a checked return.

The report pins the loaded Unicorn library and binding. This bounded MIPS
interface check does not prove PS1 timing, real graphics setup, natural menus,
factories, cleanup, whole-feature parity or newly recovered assembly.
