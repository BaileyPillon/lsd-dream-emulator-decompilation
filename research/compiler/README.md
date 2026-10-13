# Exact-compiler diagnostics

These Linux/WSL tools observe the bundled i386 GCC 2.6.3 and retain normal and
debugger-produced complete assembly. A source recovery still requires a
complete executable match and explained source ownership.

- [trace_allocation.py](trace_allocation.py) observes actual register allocation
  and priorities; see [COMPILER_ALLOCATION.md](../../docs/COMPILER_ALLOCATION.md).
- [trace_memory_stores.py](trace_memory_stores.py) observes memory-store deletion
  and address-equality returns; see [COMPILER_MEMORY_STORES.md](../../docs/COMPILER_MEMORY_STORES.md).
- [The temporary-slot lifetime tracer](../collision/trace_compiler_lifetimes.py)
  observes allocation, address-taking and reuse; see
  [COMPILER_LIFETIMES.md](../../docs/COMPILER_LIFETIMES.md).

All outputs belong in fresh `.decomp-lab` directories. Unsupported compiler
identities, changed outputs and incomplete traces are rejected. These tools
load no game executable, execute no original gameplay and make no model API calls.
