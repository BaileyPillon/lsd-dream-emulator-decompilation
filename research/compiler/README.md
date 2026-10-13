# Matching-function and exact-compiler diagnostics

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
- [The temporary-slot lifetime tracer](../collision/trace_compiler_lifetimes.py)
  observes allocation, address-taking and reuse; see
  [COMPILER_LIFETIMES.md](../../docs/COMPILER_LIFETIMES.md).

Compiler-observer outputs belong in fresh `.decomp-lab` directories. Unsupported compiler
identities, changed outputs and incomplete traces are rejected. These tools
load no game executable. The function comparator reads the canonical executable;
none of these tools executes gameplay or makes model API calls.
