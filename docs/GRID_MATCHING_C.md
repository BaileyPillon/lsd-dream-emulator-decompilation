# Matching grid-window C recovery

`func_8004C6A8` now compiles from readable C in
[`render_context.c`](../src/scene/render_context.c). All **660 original function
bytes** match, including the **152-byte stack frame**. Both the ordinary build
and a fresh compilation of all **306 objects** reproduce the complete
**505,856-byte** Japanese executable.

The executable SHA-1 remains `76322eeade5ebb22dca57fdeac7d68c30f06308d`.
[grid-matching-c-checks.json](grid-matching-c-checks.json) records the source,
compiler, complete-image and bounded verification evidence. The source baseline
is commit `7415704a4f473def92ced9daa4400cf4ba6e7615` in this C repository;
the separate Bevy/Rust port is unchanged.

## Recovered behavior

The routine obtains the current world/grid position, reads the camera angle,
rotates and projects its distance vector, and chooses the longitudinal or
transverse grid window. It sets row/column dimensions and inclusive origins,
clamps the projected correction to the active radius, and calls the existing
rectangle builder. Signed cell coordinates, mixed-width radius reads, angle
wrap and store order retain their original instructions.

Two source choices resolve the final compiler differences:

- The original reads a signed halfword for the angle sign test and an unsigned
  halfword for normalization. Two consumed `s32` views express those operations
  directly. Subsequent interval comparisons retain explicit `u16` truncation.
- A one-field endpoint operand carries the actual width into the inclusive
  `cell - extent + 1` calculation. Every field is consumed; there is no dummy
  member or discarded computation.

The source adds no unused local array, artificial predicate, volatile
constraint, physical-register binding, inline assembly or substituted
instruction. Compiler flags and the bundled GCC 2.6.3 are unchanged. Matching
output does not identify the original author's exact declarations.

## Actual compiler observations

The complete source unit was compiled normally and under the checked
[stack](../research/collision/trace_compiler_stack.py) and
[allocation](../research/compiler/trace_allocation.py) observers. Each preserved
the complete emitted assembly. Diagnostic allocation options changed only
compiler comments.

| Allocation | Compiler frame offset |
| --- | ---: |
| Actual 44-byte lookup output, aligned by the compiler | 0 to 48 |
| Actual 32-byte matrix | 48 to 80 |
| Two four-byte reload requests, each aligned by the compiler | 80 to 96 |
| Outgoing argument area and saved registers | Total frame: 152 |

The nested `assign_stack_temp` / `assign_stack_local` reports describe the same
lookup or matrix allocation; they are not added twice. The matching reload
requests concern pseudos 74 and 113 in this qualified observation. The latter
is the compiler's unused aggregate clobber, rather than an unused source field.
An earlier narrow-angle source also retained a sign-extension reload request;
the explicit signed and unsigned views remove that obsolete request.

The allocation observer independently checks one local allocation pass, one
equivalence update, 14 global allocations and 39 priority comparisons. These
observations explain compiler behavior; they do not add game features or
native gameplay scenarios.

## Build and runtime evidence

The complete linked ELF qualifies the function's address, size and ownership.
Its bytes equal the original span at `0x8004C6A8`, SHA-256
`a50855f634d69c3ce7a04cc5db9fafd9a2d88edfeab167f9e351c7791bdb46d9`.
Every byte outside that span also matches. A fresh archive build compiles all
objects independently, with the same pinned MASPSX revision. The promoted
checkout then passes `ninja check` and the current-build progress audit.

Only `src/scene/render_context.c` changes among the 392 protected game build
inputs. The other 391 inputs, original executable, compiler and frozen project
objective retain their hashes. Game images and private analysis artifacts are
not distributed.

The existing [scalar grid profile](RENDER_GRID.md) and
[native SDK/GTE composition](RENDER_GTE.md) are repeated against the promoted,
byte-identical image. Their independent expected buffers, ABI checks and
negative controls remain separate from the exact-build acceptance. The scalar
profile retains four explicit dependency contracts. The eleven-function
composition executes lookup, rotation, vector application and streaming with
zero function-output stubs, using the pinned Nymashock GTE bridge. Neither
profile checks complete PS1 CPU timing or natural scene ownership. No new
fixture domain, player run or whole-feature acceptance is claimed.

The scalar run passes **74,832 cases**, including every 16-bit angle word, and
detects all **eight** existing faults. The SDK/GTE run passes **109,501 distinct
matrix/vector inputs** and **13,230 renderer graphs** through all eleven
routines. It executes **245,470 native GTE commands**, excluding the identity
self-check, and detects all **four** existing faults. The tooling suite passes
on Windows Python 3.14.2 and WSL Python 3.13.5: **694 tests per platform**, with
**692 passes and two expected skips** on each.

## Progress and remaining work

| Measure | Before | After |
| --- | ---: | ---: |
| Matching game C bytes | 195,844 / 199,912 | 196,504 / 199,912 |
| Matching game C coverage | 97.97% | 98.30% |
| Remaining game assembly functions | 5 | 4 |
| Remaining game assembly bytes | 4,068 | 3,408 |
| Identified inherited storage explanations | 2 | 2 |
| Groups with all listed core functions in C | 37 / 40 | 37 / 40 |
| Independently accepted whole feature groups | 0 | 0 |
| Independently accepted whole NPC encounters | 0 | 0 |

F033 remains partial because the primitive emitter and bounds predicate still
retain assembly. The other remaining functions are the collision overlap
routine and UI scaling routine. The two empty debug-driver frames also retain
unexplained storage. The [roadmap](ROADMAP.md) preserves these source gates and
the separate runtime, content, audio and hardware requirements. Original NPC
behavior, developer tools and optional mods keep their separate inventories.

## Reproduce

Use the [matching build setup](../README.md#build-the-matching-executable) and
your own canonical executable:

```bash
python configure.py
ninja check
python tools/progress.py --json > build/progress-grid.json
python tools/verify_render_grid.py \
  --output .decomp-lab/grid-matching-scalar-new.json
```

For the actual SDK/GTE composition, build a fresh local bridge and run
`tools/verify_render_gte.py` using the
[native GTE reproduction instructions](RENDER_GTE.md#reproduce-locally).
Choose fresh private output names. The earlier
[research fragments](../research/render_grid/README.md) remain rejected source
forms and require their recorded assembly-based baseline.
