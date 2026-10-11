# Roadmap

The goal is readable C recovery of the original game, followed by reviewed
comparison evidence for its behavior and content. Optional mods and analysis
tools have separate deliverables. See [PROJECT_OBJECTIVE.md](../PROJECT_OBJECTIVE.md)
for the completion requirements and [provenance](PROVENANCE.md) for the evidence
boundary of the published snapshot.

## Matching C recovery

Seven game functions remain in assembly in the initial publication:

| Function | Source |
| --- | --- |
| `func_8001DDF4` | [`src/base/transform.c`](../src/base/transform.c) |
| `func_8001F8B8` | [`src/file/tmd_prim_geom.c`](../src/file/tmd_prim_geom.c) |
| `func_8004EF6C` | [`src/menu/card/memory_card.c`](../src/menu/card/memory_card.c) |
| `func_8004BE54` | [`src/scene/render_context.c`](../src/scene/render_context.c) |
| `func_8004C6A8` | [`src/scene/render_context.c`](../src/scene/render_context.c) |
| `func_8004CD38` | [`src/scene/render_context.c`](../src/scene/render_context.c) |
| `func_8004441C` | [`src/menu/ui_sprite.c`](../src/menu/ui_sprite.c) |

Confirm the live catalogue after building with
`python tools/decomp_workbench.py catalog`. SDK assembly is tracked separately.
Each C promotion must retain complete-executable equality and meaningful
types and control flow. Do not use copied instruction blobs or padding to
raise a coverage number.

## Original behavior and content

- Resolve asset/command inventory gaps and runtime reachability.
- Close virtual-call dependencies and verify semantic callback signatures.
- Extend native fixtures beyond the currently bounded Lion and Gray Man cases.
- Compare natural animation construction, lifetime and actor/render behavior.
- Review every feature's recorded scenarios, including rare RNG, save/card
  error, audio and hardware-timing branches.
- Measure complete Japanese-asset coverage separately from the local translated
  asset edition used in the existing comparisons.

The catalogue currently has 40 provisional groups. None has been accepted for
all required runtime scenarios. The [inventory](FEATURE_INVENTORY.md) lists the
remaining scenario for each group; 97.18% describes game C bytes only.

## Developer tools and optional mods

- Keep AI-assisted context export and local analysis separate from original
  NPC behavior. The supplied tools make no model API calls.
- Retain explicit input hashes, dependencies and negative controls in reports.
- Extend emulator checks for duration multipliers and passive Gray Man.
- Keep all optional patched executables and discs outside the canonical build.
