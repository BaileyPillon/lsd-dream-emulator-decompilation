# Callback lookup storage recovery

Five existing C functions now express their original stack layout through
consumed callback lookups. Their unused eight-byte arrays and associated dead
pointer comparisons are removed. Standard and fresh 306-object builds retain
the complete original executable.

This resolves **five of the 24 identified inherited storage explanations**.
These functions already counted as C: **no C bytes, assembly functions, original
features or runtime profiles are added**.

| Function | Source | Existing C bytes | Matching frame |
| --- | --- | ---: | ---: |
| `func_8003D050` | `src/menu/ui_screen.c` | 324 | 40 bytes |
| `func_8003D194` | `src/menu/ui_screen.c` | 312 | 56 bytes |
| `func_80051C84` | `src/menu/card/select_menu.c` | 152 | 40 bytes |
| `func_8005278C` | `src/menu/card/select_menu.c` | 144 | 40 bytes |
| `graph_screen_update_event` | `src/menu/graph_screen.c` | 432 | 80 bytes |

The baseline is `d7cfae53ae359490f3d6d3b574f5edf3aa9aca62`. Only these three
C units change among 392 protected build inputs; the other 389 retain their
hashes. Compiler, configuration, original executable and frozen objective are
preserved.

## Actual values and compiler allocation

Each new inline getter initializes a four-byte view and returns the actual
selected method as a scalar. UI cleanup, row update, line destruction and graph
event placement retain their original vtable addresses and callback arguments.
Base cleanup snapshots the actual method after calling the original base-table
getter once. Capturing its table instead reserved sixteen bytes and was rejected.

Every view contains one complete pointer, consumed by the real callback lookup
or invocation. Target compiler assertions require each view to be four bytes.
Existing receiver layouts, point records, table offsets and list operations
remain intact. No unused fields, physical register bindings, instruction edits,
new volatile constraints or alternate compiler flags are introduced.

Nine complete-source compiler observations compare the baseline, removed-array
control and matching reconstruction for each of the three units. Every normal
and instrumented assembly pair is identical. The actual allocator calls show:

| Function | Old unused array allocation | Removed-array control | Matching lookup allocation |
| --- | --- | --- | --- |
| UI cleanup | Eight-byte temporary | Absent | Four-byte reload, local area 0 to 8; pseudo 92 |
| Row update | Eight-byte temporary | Absent | Four-byte reload, local area 0 to 8; pseudo 89 |
| Base cleanup | Eight-byte temporary | Absent | Four-byte reload, local area 0 to 8; pseudo 83 |
| Line destruction | Eight-byte temporary | Absent | Four-byte reload, local area 0 to 8; pseudo 83 |
| Graph event update | Eight-byte temporary after the two real XY records | Absent | Four-byte reload, local area 16 to 24; pseudo 117 |

The reload allocations occur through `assign_stack_local`, called by
`alter_reg` during `reload`. The compiler rounds each four-byte allocation to
eight bytes in its local area. Pseudo IDs are compiler observations, not claims
about specific source fields. Nested temporary/local calls describe the same
allocation and are counted once. Ordinary debugger breakpoints are used without
explicit compiler-memory rewrites or forced results.

The original frame and all emitted instructions match. This supplies a
maintainable source explanation; the original author's exact declarations
remain unknown.

## Matching evidence and limits

Each selected candidate is independently qualified as one complete ELF function
at its original address. Its complete translation-unit image matches all
505,856 canonical bytes. The combined changes also pass three private unit
comparisons, followed by the regular and fresh complete game builds.

The canonical SHA-1 remains `76322eeade5ebb22dca57fdeac7d68c30f06308d`; SHA-256
remains `282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.

The optional workbench `--function` diagnostic is restricted to active assembly
inclusions. An initial existing-C invocation was rejected at that selection
check. Its already-qualified ELF span was retained, and the complete source
unit was correctly checked without the option. No mismatching image was accepted.

This checkpoint adds no native fixture domain or emulator sequence. It does not
claim an independently executed cleanup/graph scenario. Existing bounded
reports retain their original inputs and exclusions; natural construction,
ownership and allocation failures, full UI reachability, rendering/audio and
hardware timing remain broader requirements. The running player is untouched.

The separate sprite-scale, bounds-decode and primitive-pointer experiments
produce no exact match; their assembly fallbacks remain. Those failed private
studies do not count as recovered source or behavior.

## Current counts

| Measure | Before | After |
| --- | ---: | ---: |
| Identified inherited storage explanations still open | 24 | 19 |
| Unused declared local bytes removed in this checkpoint | 0 | 40 |
| Matching C game-function bytes | 195,844 / 199,912 (97.97%) | 195,844 / 199,912 (97.97%) |
| Game assembly fallbacks | 5 | 5 |
| Groups with all listed core functions in C | 37 / 40 | 37 / 40 |
| Original NPC callback C bodies | 107 / 107 | 107 / 107 |
| Bounded native NPC profiles | 36 / 107 | 36 / 107 |
| Entire feature groups independently accepted | 0 / 40 | 0 / 40 |

The nineteen-function count is the remainder of the identified inherited audit;
it is not a certificate that every possible source issue has been found. The
original game already retained its functionality in matching C plus assembly.
Ten developer capability categories, three optional mods and the separate Bevy
port retain their counts and scope. No model API is called. Every completion
requirement in the frozen [objective](../PROJECT_OBJECTIVE.md) remains intact.

## Reproduce

With your own supported executable and documented toolchain:

```bash
python configure.py
ninja check
python tools/progress.py --json
python tools/decomp_workbench.py catalog
python -m unittest discover -s tests -v
```

For a private modification to an already-C function, use the complete-image
checker without the assembly-only diagnostic option:

```bash
python tools/decomp_workbench.py check \
  --source src/menu/ui_screen.c \
  --candidate .decomp-lab/my-cleanup/ui_screen.c \
  --output .decomp-lab/my-cleanup/build
```

[callback-storage-recovery-checks.json](callback-storage-recovery-checks.json)
records source identities, allocator observations, counts and private report
hashes. The earlier [expanded audit](SOURCE_LAYOUT_EXPANDED.md) remains a frozen
baseline. Game images, generated assembly, ELF exports and debugger traces stay
private. The matching game remains available through the [play helper](PLAYING.md).
