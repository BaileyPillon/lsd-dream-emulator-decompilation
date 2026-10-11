# Collision compiler-layout investigation

The unaccepted `func_8001F8B8` candidate still differs from the complete original
executable in **22 bytes**, all bounding-box stack displacements. This update
adds an actual compiler allocator trace and a reproducible diagnostic. It
promotes no game function and accepts no original feature group.

## Reproducible diagnostic

[trace_compiler_stack.py](../research/collision/trace_compiler_stack.py) runs the
bundled compiler normally and under GDB, then requires their **complete assembly
outputs to be identical**. The backend observes allocator arguments, returns,
function names, temporary nesting levels and call stacks using normal GDB
breakpoint machinery. Software breakpoints can temporarily instrument compiler
memory. The backend makes no additional explicit memory writes or opcode
substitutions, forces no results and invokes no extra inferior functions. The
source, compiler and backend files must remain intact.

Use Linux/WSL with the existing matching compiler and MIPS preprocessor. Install
GDB if necessary. First prepare a complete C candidate translation unit using
the recipe in the [collision research guide](../research/collision/README.md).

```bash
python research/collision/trace_compiler_stack.py \
  --source .decomp-lab/collision-candidate-new/tmd_prim_geom.c \
  --output .decomp-lab/collision-stack-new
```

Use `--compiler-mode g0` for a G0 unit; the default is G8. Reports require a fresh
directory inside `.decomp-lab`. The diagnostic checks the compiler's ELF32,
little-endian i386 profile before interpreting its cdecl argument stack. It
requires the existing allocator and function-name symbols. The original game
executable and optional emulator backend are not loaded by this tool.

`allocations.json` retains every observed call. `report.json` records input and
output identities, commands and the normal-versus-traced assembly comparison.
`frame_offset_before` and `frame_offset_after` refer to the compiler's virtual
local area, not PS1 addresses. An allocation can reuse storage without growing
that area. Nested `assign_stack_temp`/`assign_stack_local` calls are both observed;
the event count is not a count of distinct locals.

## Observations and limits

Six diagnostic compilation runs pass with **199 observed allocator calls**:

| Input | Calls | Complete assembly equal |
| --- | ---: | --- |
| Published candidate in its genuine translation unit | 68 | Yes |
| Closest standalone research candidate | 43 | Yes |
| Distance scalar and ordinary final-square lifetime | 43 | Yes |
| Distance scalar and nested final-square lifetime | 43 | Yes |
| Synthetic leaf, G0 | 1 | Yes |
| Same synthetic leaf, G8 | 1 | Yes |

For the closest standalone candidate, the 12-byte bounds object grows the
virtual local area from 72 to 88 bytes. Its 16-byte square object grows it from
216 to 232 bytes. The emitted function's 24-byte outgoing-argument area places
these at SP+`0x60` and SP+`0xF0`, respectively. The original instructions use
SP+`0xF0` for both square output and later bounds, with no direct references to
the early 16-byte region. This establishes the layout discrepancy, not the
original source declaration or a safe padding substitute.

Earlier private traces separately show that the explicit square/bounds union
reduces the frame by 16 bytes and that a grouped contact helper allocates a
single 144-byte inlined local area. Those candidates remain nonmatching. The
two isolated square-lifetime variants above each retain 103 byte differences;
closing a C block alone does not produce the required reuse.

This investigation compiled **55 source forms including one baseline refresh**:

| Experiment | Compilations | Actual minimum differences |
| --- | ---: | ---: |
| Plane/segment value copies and pointer/grouped contact helpers | 21 | 22, baseline only |
| Addressable segment-helper arguments and local-lifetime variants | 32 | 1,411 |
| Isolated final-square scopes with a distance scalar | 2 | 103 |

No compilation failed and no exact match was found. The stored private lab
helper also retains an initialized score threshold; the table above is
calculated from actual compiled rows rather than that threshold. The global
best remains the previously published 22-byte candidate.

An initial synthetic-leaf calibration incorrectly expected zero allocator
calls. Actual GCC makes one **zero-byte** call with the local area remaining
zero. The failed calibration and successful compiler report are retained;
the corrected G0/G8 controls check the allocation's size and unchanged area.

These results concern compiler layout. They add no native gameplay cases,
NPC checks, exact C promotions or whole-feature acceptance. All original
feature, C-recovery, developer-capability and optional-mod counts remain
unchanged. The tracer extends the existing C-candidate analysis workflow.
Natural scenes, PS1 timing and the complete parity objective remain open.

[compiler-layout-checks.json](compiler-layout-checks.json) pins the producer,
private reports, compiler identity and candidate comparisons. Public tooling
tests additionally check output preservation, ABI rejection, unsuccessful or
unfinished traces and rejection of changed assembly.
