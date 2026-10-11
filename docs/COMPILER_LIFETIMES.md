# Collision compiler lifetime investigation

The collision candidate remains **22 bytes** different from the original
executable. This investigation measures why a nested C block does not release
its square-output storage and verifies a helper boundary that permits later
bounds storage to reuse it. No game function is promoted to C and no original
feature group is accepted.

## Reproduce the observation

The [lifetime tracer](../research/collision/trace_compiler_lifetimes.py) extends
the earlier [allocator diagnostic](COMPILER_LAYOUT.md). It observes
`assign_stack_temp`, `mark_temp_addr_taken`, `preserve_temp_slots`,
`free_temp_slots` and `pop_temp_slots` in a selected C function. It records the
compiler's temporary-slot list before and after each completed call.

From the repository root in the existing Linux/WSL build environment, prepare
a complete candidate translation unit using the
[collision research recipe](../research/collision/README.md), then run:

```bash
python research/collision/trace_compiler_lifetimes.py \
  --source .decomp-lab/collision-candidate-new/tmd_prim_geom.c \
  --function func_8001F8B8 \
  --output .decomp-lab/collision-lifetimes-new
```

The default compiler mode is G8; use `--compiler-mode g0` for G0 units. GDB and
the configured MIPS preprocessor must be available. Reports require a fresh
directory inside `.decomp-lab`; existing evidence cannot be overwritten.

Heap decoding requires the exact bundled compiler SHA-256,
`3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab`.
The 32-byte i386 `temp_slot` layout was checked against that binary's allocator
and lifetime instructions. Both the command-line producer and GDB backend
reject another compiler identity. Compiler virtual local offsets are distinct
from emitted PS1 stack displacements.

`lifetimes.json` records raw slot identities, sizes, levels, address-taking and
in-use flags. `report.json` records commands, input hashes, output hashes and
the complete assembly comparison. A missing function, debugger error,
unfinished return, malformed slot, changed input or changed assembly rejects
the observation. The compiler runs normally as well as under GDB; both complete
assembly outputs must be identical.

Normal GDB breakpoint machinery can temporarily instrument compiler memory.
The backend makes no additional explicit inferior-memory writes or opcode
substitutions, forces no results and invokes no extra inferior functions.
Neither compiler diagnostic loads an original game executable, emulator or
model service.

## Measured storage lifetimes

Five successful diagnostic runs retain **1,336 lifetime calls**:

| Input | Calls | Complete assembly equal |
| --- | ---: | --- |
| Published candidate in its complete translation unit | 445 | Yes |
| Nested caller-owned square buffer | 448 | Yes |
| Helper-owned square, then a later bounds object | 439 | Yes |
| Synthetic leaf, G0 | 2 | Yes |
| Same synthetic leaf, G8 | 2 | Yes |

These counts include nested operations. They are not counts of locals, game
executions or independently tested gameplay cases. A separate absent-function
control is correctly rejected and retains its raw logs.

For the nested caller-owned square, allocation grows the virtual local area
from 200 to 216 bytes at temporary level 4. Passing its address to `Square0`
sets `addr_taken`. Two `preserve_temp_slots` calls move its level from 4 to 3,
then from 3 to 2. Closing the inner block leaves it live; the later bounds
allocation grows the local area rather than reusing the square's slot.

For the helper-owned square, an inlined scalar-return helper allocates the same
16-byte area, and `pop_temp_slots` immediately marks it unused. The later
12-byte bounds allocation returns the **same RTL storage identity and list
node**, changes `in_use` from 0 to 1, and leaves the local area at 220 bytes.
This demonstrates actual storage reuse without an explicit C union or padding.

That boundary is a useful source hypothesis, not proof of the game's original
source. It still fails to explain the original unused early 16-byte region;
the emitted SDK workspace is displaced and the complete native match remains
open. The published 22-byte candidate stays outside the canonical build.

## Rejected source comparisons and remaining work

The investigation compiled **69 additional source forms**, excluding three
duplicate forms that were skipped:

| Experiment | Compilations | Actual minimum differing bytes |
| --- | ---: | ---: |
| Symmetric inline square/length helpers | 24 | 50 |
| One caller-owned square and one helper-owned square | 24 | 22 |
| Four-pointer collision query context | 6 | 1,619 |
| Aggregate or pointer-return bounds with helper-owned square | 15 | 22 |

Each score and source hash is independently rechecked against the retained
emitted function bytes. No compilation fails, no exact match is found, and
the existing global best remains 22. The successful lifetime hypothesis alone
does not justify dummy storage or instruction rewriting to obtain a match.

[compiler-lifetime-checks.json](compiler-lifetime-checks.json) pins the public
producer, backend, tests and document, private observations, compiler layout
evidence and measured source comparisons. Earlier allocator metadata and all
earlier feature records remain intact. Ten new guard tests verify unsupported
compiler rejection, retained evidence, incomplete traces and changed-output
rejection. The original C, feature, NPC, developer-capability and optional-mod
counts remain unchanged; this extends existing candidate-analysis tools.

The next source-recovery step is to explain the native early region with real
declarations or inline boundaries, then require a complete executable match
and relevant native behavior checks before any C promotion. Full PS1 timing,
natural collision scenarios and whole-feature acceptance remain open.
