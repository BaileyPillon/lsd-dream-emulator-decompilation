# Natural title-menu construction state and lifetimes

Six retained original/rebuilt checkpoints now have generation-qualified menu
ownership checks. They identify **three separate menus at the same address**,
follow **196 selected allocations through two natural menu releases**, and
leave the final menu's **98 selected allocations open**. The comparison reuses
the [30,000-frame file/heap recording](FILE_HEAP_LIFETIMES.md); it creates no
new emulator recording or expanded memory payload.

The matching C now names the original `m_RowCount` and `m_SelectedRow` fields
at offsets `0x50` and `0x58` in the shared and title-menu views. Five C/header
inputs change only identifiers. All 392 build inputs are checked against the
preceding snapshot, and the rebuilt 505,856-byte executable remains canonical.
Matching C stays **197,172 / 199,912 bytes (98.63%)**; this is semantic recovery
and runtime evidence, with no newly promoted C function or accepted whole feature.

## Three generations, one reused address

| Allocation generation | Allocated at frame | Native receiver release | Inspected checkpoints |
| --- | ---: | ---: | --- |
| 587 | 1,911 | 2,150 | 2,100 |
| 38,619 | 23,865 | 24,622 | 24,000 and 24,500 |
| 40,394 | 29,736 | Still open at capture end | 30,000 |

All three receiver pointers are `0x80091F70`. At frames 2,400 and 25,000,
there is no live generation from that factory. A vtable pattern or equal
address cannot establish identity. Checkpoints on an allocation/free frame
are reported as unqualified because the frame alone does not order that
boundary against the RAM snapshot.

The inspector revalidates 40,890 original native call/return records, including
complete callee bytes, transfer instructions, delays, stacks and nested call
intervals. The prequalified file/heap model supplies 19,717 successful allocation
generations and 19,303 matched nonnull frees, with no unobserved allocation free.
Original and rebuilt record bytes, retained payload and reconstructed generations
agree. This recheck does not repeat every earlier disc-transfer or runtime-file audit.

## Selected ownership graph

Each inspected menu has the same 98 selected owned allocations:

| Resource | Allocations |
| --- | ---: |
| Menu receiver, font TIM object and cursor effect | 3 |
| Four outer row/choice arrays | 4 |
| Six row text objects, two SHAKE choices and one day label | 9 |
| Their glyph-pointer arrays | 9 |
| Glyph objects: 37 panel glyphs and 35 day-label glyphs | 72 |
| SHAKE choice-pointer array | 1 |

The six row labels and Off/On choice characters match their original labels.
Every selected allocation has a live generation, the expected request size,
an intact native heap header and the corresponding original allocation call
site. Text and glyph objects borrow the live font's TIM metadata. Duplicate
ownership is rejected. This explicit member walk includes resources that a
scan of the menu's ordinary child list alone misses.

For both closed menus, the selected native frees occur in the order required
by the original cleanup: day label, font, cursor, row choices/text, outer arrays,
and receiver. These are selected resources, not a claim that every hidden
resource, base-list node, sound bank or failure path has been accepted.

The 34,816-byte font file buffer is released before each populated checkpoint.
Its former extent is then reused by 92 selected allocations per menu. The TIM
object remains live, and its parsed pixel/CLUT pointers still describe the
released extent; those pointers are not treated as live ownership. The native
release snapshots and allocation generations distinguish those cases.

Rows without choice descriptors also retain uninitialized words in their
choice arrays. The checker reports and hashes all those bytes, while following
choice pointers only for the row whose descriptor enables them. Full RAM
comparison uses no masks or rewritten bytes.

## Output evidence and verification

The six checkpoint pairs have freshly verified complete RAM, GPU memory and
RGB bytes. Twelve retained PNGs are independently decoded and checked against
the RGB streams. Visual inspection of frames 2,100 and 30,000 shows the Day 001
and Day 002 menus with START selected and FLASHBACK hidden. Allocated row text
does not imply that every row is visible or every route has been exercised.

A separate raw member walk, without importing the menu producer oracle,
reconstructs all 294 distinct selected generations and both release orders.
It shares the previously qualified native transport/heap validator. Fourteen
offline corruption controls are rejected, covering descriptor fields, font
views, glyphs, ownership aliases, heap headers, allocation call sites, leaks
and reversed release order. A stale vtable receives no resource credit; arbitrary
unused choice words remain visible in the hashes without being dereferenced.
These controls modify analysis copies of retained inputs, with no game RAM injection.

[Machine-readable metadata](natural-menu-lifetime-checks.json) records source
hashes, checkpoint identities, corpus hashes, controls and the separate audit.
Raw game/capture data and detailed journals remain private.

## Reproduction and remaining gates

After the matching build, run the inspector against an existing qualified
heap-observer recording and your canonical executable. It reads a raw or XZ
SDK payload and one exact RAM tar member directly in memory:

```bash
python -B tools/inspect_runtime_menu.py \
  --capture "$CAPTURE" --frame 2100 \
  --ram "$RAM_ARCHIVE" --ram-member "$RAM_MEMBER" \
  --sdk-payload "$SDK_PAYLOAD_XZ" --output "$NEW_REPORT"
```

Choose the archive/member from the retained index; the storage archive README
describes its verification. A raw or standalone XZ RAM file can instead be
passed with `--ram` alone. The inspector refuses to overwrite an output report
and binds the complete RAM bytes to the recording's checkpoint hash.

This extends the [typed panel](MENU_PANEL_OWNERSHIP.md) and initialized cleanup
profiles with natural state and allocation histories. The capture records
allocation transfers inside the relevant helpers, rather than instrumenting
menu-constructor entry boundaries or every constructor path. Allocation-failure
continuation, remaining menu routes, pending I/O, final sound shutdown, the
third menu's eventual release, hardware timing and full gameplay/ending
comparison remain open. Whole-feature and whole-NPC acceptance remain zero.
