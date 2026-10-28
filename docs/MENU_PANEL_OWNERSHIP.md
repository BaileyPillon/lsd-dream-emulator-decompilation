# Title-menu panel structure and ownership

The title menu's original descriptor is now represented by one **40-byte
`ui_screen_panel_t`**, replacing a 16-byte pointer array and an adjacent
24-byte word array. Construction, layout and cleanup all consume the same
record. Its callback argument types and the title-label texture access now
use that record explicitly. The complete executable still matches retail
byte for byte; no new game function is promoted from assembly.

The initialized cleanup comparison also now covers populated panels in
**216 contexts through 51 original game/SDK bodies**, without dependency
output contracts. It includes the six retail title rows and the SHAKE
choices, borrowed/owned font textures, and empty/mixed panels. Four executed
ownership faults are rejected. This extends destruction evidence without
accepting natural construction, rendering or a whole menu feature.

## Recovered descriptor

The original record starts at `0x80086D44`. Its initial 40 bytes have SHA-256
`28cf22086de08c4dd0efc841132687acaf84cb4e1308e0b32d3f92f6cf27b5b5`.
The matching C initializer emits those same bytes at that same address, and
a target-compiler assertion checks its `0x28` size.

| Offset | Member and evidence |
| --- | --- |
| `0x00` | Texture path; a nonnull path makes panel cleanup own the texture. |
| `0x04` | Mutable texture handle, populated by construction and used by the day label. |
| `0x08`, `0x0C` | Preserved zero words with unresolved meaning. |
| `0x10`, `0x13` | Two RGB triples used by row layout/selection. |
| `0x16` | Preserved two-byte field with unresolved meaning. |
| `0x18` | Disabled-row flags. |
| `0x1C` | NULL-terminated label-pointer array. |
| `0x20` | Row position pairs. |
| `0x24` | Per-row optional choice descriptors. |

The labels are START, FLASHBACK, SAVE, LOAD, GRAPH and SHAKE. Their glyph
counts are 5, 9, 4, 4, 5 and 5. SHAKE has Off/On choices with three and two
glyphs. The new type preserves the unknown fields instead of assigning
them invented meanings. Its source is in
[ui_screen.h](../src/menu/ui_screen.h); the unified initializer is in
[main_menu.c](../src/menu/main_menu.c).

## Original cleanup execution

Each context starts with an independently modeled valid heap and supplied
hidden resource graphs. Original main-menu destruction reaches shared
panel cleanup at `func_8003D050`, including the real choice-list callback
`func_8003D6D4`, text/glyph destruction and pool release. A panel releases
its owned font texture first, then its cursor effect, row choices, row text
and four outer arrays. A borrowed font object and its backing buffer survive.
The selected-row field is checked alongside complete final buffers.

The cases cross three panel layouts, three RAM aliases, two initial byte
patterns/fragmentation states, linked/detached ownership, three sound states
and borrowed/owned font textures. There are 36 cases per layout/texture
combination, with 36–327 original release calls per case. Zero-byte arrays
use NULL, as required by the original allocator. The empty and mixed cases
are constructed guard contexts; they are not extra retail menu variants.

Private instruction controls skip owned-font destruction, incorrectly free
a borrowed font, suppress choice-row cleanup, and omit choice-array release.
Each changed instruction executes and the destructor returns NULL; ordered
ownership comparison rejects all four. A NULL return alone is insufficient.

An independent audit reconstructs the serialized inputs and walks their raw
ownership structures without importing the producer oracle. It checks all
final manager, pool, guarded-object and supplied SDK-state bytes, plus
104,490 indirect transfers and all four controls. The interval allocator is
shared with the previously qualified heap model; the panel walk is separate.
The existing 144-case resource profile is rerun and retains exactly its
earlier input/output corpus hash.

## Reproduction and scope

After a current matching build, use the existing isolated Unicorn 2.1.2
environment from the [lifecycle instructions](../research/screen_lifecycle/README.md):

```bash
python -B research/screen_lifecycle/verify_panel.py \
  --output .decomp-lab/panel-cleanup-new
```

`--diagnostic` can reuse a retained current diagnostic link. Its complete
allocated image, function spans and typed title descriptor are checked
against the original again. Reports and compressed journals stay private;
[public metadata](menu-panel-ownership-checks.json) records the source hashes,
canonical image, cases, backend, function ownership and executed controls.

The profile executes destruction, not the constructors. Font/file data and
SDK ownership RAM are supplied explicitly. Actual content loading, natural
screen setup, allocation failures, controller interaction, rendered output,
pending I/O, final sound shutdown and timing remain open. These comparisons
accept no whole original feature or NPC encounter and make no model-service
calls. Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two game
assembly functions and three inherited storage explanations remaining.
