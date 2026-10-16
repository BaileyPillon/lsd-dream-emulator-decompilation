# Matching menu layout and acceptance

The original menu layout and acceptance routines now compile from C with all
**1,052 bytes** matching the executable. Standard and fresh 306-object builds
reproduce the complete 505,856-byte canonical image.

| Function | Original address | Bytes | Original and matching frame |
| --- | --- | ---: | ---: |
| Layout, `func_8003D73C` | `0x8003D73C` | 580 | 88 bytes |
| Acceptance, `func_8003DAD4` | `0x8003DAD4` | 472 | 64 bytes |

The source baseline is `8129a82b6d3a4ecf4d85fb8fd4ded465f1f824ba`.
Only `src/menu/ui_screen.c` changes among 392 protected build inputs; the other
391 retain their hashes. The complete executable retains SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d` and SHA-256
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.

## Recovered method lifetimes

The earlier scalar layout candidate reserved 72 bytes and differed in twenty
bytes. The scalar acceptance candidate reserved 56 bytes and differed in
sixteen. Extending position or size arrays had previously produced matching
frames without explaining the original storage.

The [generation lookup recovery](GENERATION_LOOKUP_RECOVERY.md) supplies a
different source explanation: initialized, fully consumed four-byte vtable
snapshots with scalar callback returns. The menu code shares one typed snapshot
definition and uses three inline method getters:

- Layout retrieves the first loop's actual row-hide method and the placement
  loop's actual row-attachment method through separate snapshots.
- Acceptance retrieves the actual row-visibility method through one snapshot.

Each snapshot's sole element supplies its original callback. All existing
receivers, arguments and callback bindings remain intact. XY positions and
effect sizes remain two-word arrays with their actual uses. The caller-owned
menu data layout is unchanged. No unused local storage, instruction edits,
physical register bindings or alternate compiler flags are introduced.

Actual GCC 2.6.3 allocation observations show why the matching frames result:

| Function | Direct scalar local area | Matching local area | Added reload allocations |
| --- | ---: | ---: | --- |
| Layout | 16 bytes | 32 bytes | Two four-byte slots, each rounded to eight bytes; pseudos 100 and 137 |
| Acceptance | 8 bytes | 16 bytes | One four-byte slot rounded to eight bytes; pseudo 113 |

The slots are allocated by `assign_stack_local` through `alter_reg` during
`reload`. These pseudo IDs are observations, not source-field identities.
Nested temporary/local calls for each real array describe the same allocation
and are counted once. Normal and traced complete assembly agree for both the
matching and scalar-control source units. Ordinary debugger breakpoints are
used without explicit compiler-memory rewrites or forced results.

Nine qualified complete-function observations, including two repeated controls,
retain the exact spans and original addresses. Two subsequent combined source
units match the complete image, including the version sharing the typed vtable
view. The initial layout experiment had an incorrect control-frame expectation;
the measured 72-byte control and corrected study are retained separately.
The reconstruction does not establish the original author's exact C spelling.

## Native comparison and scope

The original and exact combined candidate pass the same **864 constructed
histories per image** through all **39 scoped original methods**. The promoted
build passes the profile again. Each phase compares all 98,316 bytes of retained
caller, heap and global state, alongside independent XY, visibility, color,
selection and timer rules. No dependency output is substituted.

All three deliberate faults are detected with positive measured executions of
their changed instructions: layout spacing, acceptance spacing and persisted
selection. Actual graphics, glyph, ownership-list and pool-allocator code runs.
The separate Unicorn 2.1.2 environment has the same library and binding hashes
as the earlier qualified [menu profile](MENU_LAYOUT.md); the main analysis
environment remains unchanged.

These are existing fixture domains, not new natural menu scenarios. Natural
construction and assets, rendered output, full controller/menu reachability,
audio and PS1 timing remain open. No new emulator play sequence or complete
feature acceptance is claimed. The running player is untouched.

## Progress

| Measure | Before | After |
| --- | ---: | ---: |
| Matching C game-function bytes | 194,792 / 199,912 (97.44%) | 195,844 / 199,912 (97.97%) |
| Game assembly fallbacks | 7 | 5 |
| Groups with all listed core functions in C | 37 / 40 | 37 / 40 |
| Inherited unused-storage explanations | 24 | 24 |
| Original NPC callbacks with C bodies | 107 / 107 | 107 / 107 |
| Bounded native NPC profiles | 36 / 107 | 36 / 107 |
| Entire feature groups independently accepted | 0 / 40 | 0 / 40 |

F035 still requires the remaining UI-scale function and broader runtime evidence.
All four source-layout withdrawals now have replacement matching C recoveries;
the rejected historical fragments remain available. The forty groups remain a
provisional inventory, with no official exhaustive feature total established.
Ten developer capability categories, three optional mods, the separate Bevy
port and the frozen [project objective](../PROJECT_OBJECTIVE.md) are unchanged.
This work calls no model API and adds no original gameplay feature.

## Reproduce

After the documented setup and with your own supported executable:

```bash
python configure.py
ninja check
python tools/progress.py --json
python tools/decomp_workbench.py catalog
python -m unittest discover -s tests -v
```

In a separate environment with `requirements-card-heap.txt` installed:

```bash
python tools/verify_menu_layout.py --output .decomp-lab/menu-recovered-new
```

Use fresh private outputs. The [play helper](PLAYING.md) continues to launch the
matching game. Synthetic tooling tests and bounded native histories do not
certify whole-game parity.

[menu-lookup-recovery-checks.json](menu-lookup-recovery-checks.json) records the
source/compiler identities, proof scope and current counts. Complete game
images, candidate executables, generated assembly, ELF exports, native buffers
and compiler traces remain private. Earlier reports retain their measurements.
