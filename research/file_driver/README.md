# File-driver interface check

The analysis-only [consumer](consumer.c) compiles four Open/Read callers against
the recovered shared and debug interfaces. Ten [layout assertions](abi_checks.h)
check PS1 word widths, object size, slot offsets and Read result widths.

Run from the repository root in the configured Linux/WSL build environment,
after `ninja check`, using your own canonical `SLPS_015.56`:

```bash
python3 -m venv .decomp-lab/file-driver-venv
.decomp-lab/file-driver-venv/bin/python -m pip install -r requirements.txt -r requirements-card-heap.txt
export PATH="$(pwd)/.decomp-lab/file-driver-venv/bin:$PATH"
python research/file_driver/verify.py --output .decomp-lab/file-driver-interfaces-new
```

Choose a fresh output directory. The command preserves earlier evidence and
does not control an emulator. It requires the pinned Unicorn 2.1.2 environment;
the broader analysis environment can have a different backend.

The verifier qualifies seven complete original function extents from an
unstripped 306-object relink whose entire executable must remain canonical.
Its ELF parser and GNU sized-symbol listing must agree. It compiles all four
owned callers with warnings treated as errors, then checks 600 initialized
cases through both direct original methods and typed callers. The common
view also executes the original driver-slot copier. Execution stays within
these original methods and owned callers; there are no output stubs.

Five executed instruction faults and three separately compiled incorrect
header variants must be rejected. Faults exist only in isolated analysis
memory or private header overlays. Reports, generated code and original game
bytes remain inside `.decomp-lab`.

These are debug no-op methods and bounded CD busy/already-open/closed paths.
Actual disc requests, destination writes, SDK behavior, timing and natural
file histories are outside this check. The two inherited empty debug frames
remain unexplained. See [the evidence and interface description](../../docs/FILE_DRIVER_INTERFACES.md).
