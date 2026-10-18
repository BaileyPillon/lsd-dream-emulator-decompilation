# Matching-function and exact-compiler diagnostics

For a complete translation unit, use
[`decomp_workbench.py check --function`](../../docs/SOURCE_INTERFACE_DIAGNOSTICS.md#repeatable-complete-function-diagnostics).
The original whole-image link is preserved; a diagnostic link may retain
symbols only when its entire binary equals the candidate. Full instruction
details stay in the private `comparison.json` report.

[compare_function.py](compare_function.py) compares a complete, sized function
from an unstripped linked MIPS ELF against a supplied span of the canonical
executable. It reports changed instruction fields, operand swaps and contiguous
reordered words. It rejects relocatable, stripped, truncated or wrong-architecture
ELFs, missing function sizes, incorrect addresses and incomplete function spans.
Other section bytes remain explicitly outside the selected-function comparison.

Obtain the original address and size from a reviewed original-function inventory.
The tool checks the candidate's complete ELF extent; it does not independently
establish the original function boundary. For the 108-byte bounds predicate:

```powershell
python research/compiler/compare_function.py --elf .decomp-lab/my-bounds.elf --function func_8004CD38 --address 0x8004CD38 --bytes 108 --output .decomp-lab/my-bounds-comparison.json
```

The report includes raw original/candidate instruction words, so it can only be
written to a fresh `.json` file inside `.decomp-lab`. Public output paths and
overwrites are rejected before reading game inputs. A matching function report
does not promote C or verify a complete executable. Reordered instructions remain
nonmatching and require independent behavior/timing review.

The following Linux/WSL tools observe the bundled i386 GCC 2.6.3 and retain normal and
debugger-produced complete assembly. A source recovery still requires a
complete executable match and explained source ownership.

- [trace_allocation.py](trace_allocation.py) observes actual register allocation
  and priorities; see [COMPILER_ALLOCATION.md](../../docs/COMPILER_ALLOCATION.md).
- [trace_memory_stores.py](trace_memory_stores.py) observes memory-store deletion
  and address-equality returns; see [COMPILER_MEMORY_STORES.md](../../docs/COMPILER_MEMORY_STORES.md).
- [trace_inline_calls.py](trace_inline_calls.py) records inline returns and the
  argument mode/type gate. A standalone reproducer and its type-identity result
  are documented in [COMPILER_INLINE_TYPES.md](../../docs/COMPILER_INLINE_TYPES.md).
- [The temporary-slot lifetime tracer](../collision/trace_compiler_lifetimes.py)
  observes allocation, address-taking and reuse; see
  [COMPILER_LIFETIMES.md](../../docs/COMPILER_LIFETIMES.md).

Compiler-observer outputs belong in fresh `.decomp-lab` directories. Unsupported compiler
identities, changed outputs and incomplete traces are rejected. These tools
load no game executable. The function comparator reads the canonical executable;
none of these tools executes gameplay or makes model API calls.

The stack and temporary-lifetime tracers also accept `--lab-root` for an
existing absolute private artifact directory on another drive. External roots
must be outside Git worktrees; output must be a fresh child directory. The
checkout's `.decomp-lab` remains the default. For example, from the checkout in
WSL, with `/mnt/d/CodexArtifacts/LSD/working` already created:

```bash
python research/collision/trace_compiler_lifetimes.py \
  --source /mnt/d/CodexArtifacts/LSD/working/candidate.c \
  --function func_8001DDF4 \
  --lab-root /mnt/d/CodexArtifacts/LSD/working \
  --output /mnt/d/CodexArtifacts/LSD/working/new-lifetime-trace
```

Only these two tracers support this option. Keep private game-derived data and
closed comparison evidence outside published repositories. Relocating an
artifact directory does not change the matching executable or any source or
runtime acceptance gate.

The [recorded off-drive checks](../../docs/compiler-artifact-storage-checks.json)
include four real compiler observations with this option and 1,229 tooling tests
on each local platform. A related hull study qualifies 14 complete standalone
functions from 14 C sources: two calibrations and twelve caller-owned input
record forms. Independent GNU extraction agrees with every raw comparison.
Three pointer-pair records reserve the early 24-byte region, but their generated
copies grow the function to 896 bytes versus the original 796. They are rejected.
The existing candidate remains 26 bytes away; matching game C stays at
197,172 / 199,912 bytes (98.63%). No source, original feature, or NPC encounter is
accepted from this study.
