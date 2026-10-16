# Menu layout, glyphs and acceptance

> The later [matching menu recovery](MENU_LOOKUP_RECOVERY.md) closes both
> callers' C-source gates. This earlier nonmatching-candidate report retains its
> measurements; natural menu/rendering and whole-feature acceptance stay open.

The original menu layout and acceptance routines pass 864 constructed histories
per original and three padding-free candidate images. All 39 scoped methods
execute, including glyph positioning/color/visibility, graphics effects, parent
lists and the original allocator. No function output is stubbed. These are the
same 864 parameter histories replayed in four images, not 3,456 distinct cases.

The candidates still differ by 20, 16 and 36 bytes. Both menu callers retain
assembly. Bounded behavior agreement does not waive their exact source gate.

## Recovered behavior and interfaces

Layout hides the existing rows, copies an eight-byte XY position from the entry,
subtracts the stored selection times ten, then places each row ten units below
the preceding row. The optional graphics effect receives two size words: 40 and
the row count times twelve. Its actual setter reads halfwords at byte offsets
zero and four. This object comes from `effect_base_create`; the older research
variable named `sound` was misleading.

Acceptance acts only in mode two. It positions rows relative to the current
selection, disables their glyph windows, enables and colors the selected window,
persists the selection, detaches the graphics effect, changes mode to one and
issues timer event sixteen. Other tested modes leave acceptance inert.

Initial attachment walks the start/length window and applies the optional gap.
Later repositioning walks the full glyph-index range and omits that gap; only
attached glyphs accept positions. The checks preserve this difference, signed
spacing, empty glyph windows and repeated hide/attach histories.

Two callback declarations now match their actual methods: text-line slot `0xBC`
takes an XY pointer, and effect slot `0xC0` takes a halfword view of the size data.
Standard and fresh clean builds remain byte-identical to the canonical executable.
The buffers do not justify adding an unused third coordinate.

## Source and native evidence

Sixty-two source trials retain no exact match. Real returned XY values can reach
the original frame size but emit additional copies. Some by-value accessors emit
separate helpers; selected function spans are distinguished from whole text.
The published candidates contain no dummy arrays or physical-register bindings.
Their older trial inputs remain pinned separately from the corrected interfaces.

The paired checker compares all 98,316 bytes of caller, heap and global snapshots
after each phase, with independent position, visibility, color, selection and
timer rules. All three deliberate original-instruction faults are detected, with
measured changed-instruction execution: layout spacing, acceptance spacing and
persisting the wrong selection. Each host call checks ABI and stack guards;
complete RAM is preserved between fresh host-call CPUs, and nested calls execute
uninterrupted on one CPU.

Use the separate allocator environment described in [CARD_HEAP.md](CARD_HEAP.md):

```bash
.decomp-lab/card-heap-venv/bin/python tools/verify_menu_layout.py \
  --output .decomp-lab/menu-layout-new
```

Optional repeated `--candidate` arguments accept complete images differing only
inside the two original menu spans. Reports refuse to overwrite existing evidence.
[menu-layout-checks.json](menu-layout-checks.json) pins range, source, candidate,
backend and clean-build records. The initial stripped-ELF, stale-object and
wrong-backend setup attempts remain separate diagnostics. Successful ranges come
from the 305 active build objects and linker map, using isolated Unicorn 2.1.2.

These are manual valid ownership graphs. Natural constructors, asset contexts,
rendered menus, full controller reachability and PS1 timing remain open. Native
histories use the declared XY context; synthetic word-wrap tests are separate.
No whole feature or NPC is accepted. Current C remains 194,212 / 199,912 (97.15%),
with nine assembly functions and 24 inherited storage explanations. All 371
tooling tests pass locally; the 40 provisional groups, 16 / 107 bounded NPC count,
ten developer capabilities and three optional mods retain their separate measures.
