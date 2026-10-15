# Generation structure interfaces and live object observations

The generated-structure update receives an object and a pointer to three
32-bit position words. Its previous virtual declaration accepted only the
object. The position-summing helper was also declared as writing a complete
generation object, although its actual output is a twelve-byte vector.

The recovered declarations and vector operations now express those interfaces
directly. Both the standard build and a fresh **306-object** build reproduce
the complete **505,856-byte** canonical executable, SHA-256
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.
No baseline objects were copied into the fresh build.

## Recovered interfaces

| Interface | Original binding and recovered meaning |
| --- | --- |
| Generation class slot `0xEC`, `Update` | `func_800564F4(object, position)` increments the tick and forwards the position pointer to `func_80056640` |
| Generation class slot `0xB8`, `SetPosition` | `func_80057384` replaces the three coordinates; this is not an additional position sum |
| `func_80056794(out, left, right)` | Adds three corresponding 32-bit words into a `vec3d_t`; it does not construct or modify an entire generation object |
| `g_GenerationStructures` | An array of generation-structure pointers; the visible C producers call `generation_structure_create` for their four modes |

The mode-0 forwarding declaration keeps the position pointer explicit even
though that callee does not use it. Unrelated classes' same-offset virtual
slots retain their own declarations. This is a scoped interface audit, not a
claim that every virtual call or construction path has been recovered.

The existing original-code checker was rerun with the canonical image and the
**ten-byte-different scalar dispatcher candidate**: fifteen original routines,
**3,116 standalone fixtures and 40 consecutive histories / 480 history frames
per image**, with nine fault controls detected. These manually assembled graphs
do not establish natural construction or complete generation parity. The
source line endings were then normalized for publication; both final complete
builds still match. The metadata records both source identities.

## Narrower remaining source mismatch

Sixteen further source forms use consumed one-word object, position, or method
values. Their complete emitted functions and text sections were independently
qualified. None matches exactly.

The [method-return fragment](../research/source_layout/structure-update-method.c)
reproduces the original **40-byte stack frame** without unused storage. Its
complete linked image differs in **eight bytes**, all within the 136-byte
dispatcher. At relative instruction offsets `0x4C` and `0x54`, it moves the
position earlier and stores the returned method at `sp + 0x10`; the original
has a load-delay NOP and passes the position in the call delay slot.

That store is not present in the original. At this initial checkpoint the
fragment had **not** run through the native fixture campaign above. The later
[return-temporary investigation](GENERATION_RETURN_TEMPORARY.md) records its
own bounded campaign and actual compiler decisions; it remains unaccepted. The
[direct typed candidate](../research/source_layout/dream_generation_update_structure_entities.c)
retains its ten stack-layout differences. The build continues to use the
original assembly dispatcher. A plausible frame size alone does not recover
the original source lifetime.

## Observed original-game receivers

The [window-link replay](NATURAL_WINDOW_LINK.md) already retained five matching
original/rebuilt full MainRAM snapshots. The new
[read-only observer](../research/generation_interface/README.md) verifies the
reference executable, four captured function bodies, and the complete
generation-class virtual table before inspecting each snapshot.

| Relative frame | Generation type | Stored count | Observed active receivers |
| --- | ---: | ---: | --- |
| 0 | 1 | 3 | Three mode-0 generation objects, tick 185 |
| 600 | 1 | 3 | The same three addresses and class, tick 297 |
| 1200, 1800, 2400 | -1 | 3 | Dispatch disabled; the stale list is not dereferenced |

All three active receivers use `D_800876FC`, with update `0x800564F4` and position
setter `0x80057384`. Both observer CLI runs produce identical reports for the
five snapshot pairs. Ten altered-input controls are rejected, and a disabled
generation state safely skips a stale oversized count and null list. Attempts
to overwrite an existing report fail without changing its bytes. These guard
tests modify private copies, not the original captures or a running game.

These are field observations from an earlier controller-only scenario, not a
new emulator replay or direct callback-entry trace. They cover three receivers
and one observed mode. Construction, all natural modes, child lifetimes,
complete RNG history, rendering, audio and hardware timing remain open.

## Progress and reproduction

C recovery remains **194,212 / 199,912 bytes (97.15%)**, with **nine** assembly
functions, **24** inherited storage explanations, **20 / 107** bounded NPC
callbacks, and **0 / 40** complete feature groups accepted. The generation
methods are not additional entries in the 107-entry NPC catalogue.

Use the [observer guide](../research/generation_interface/README.md) for local
MainRAM captures and the [source-layout guide](../research/source_layout/README.md)
for complete-unit compiler comparisons. The original-code profile is documented
in [generation effects](GENERATION_EFFECTS.md). Counts, hashes, source identities,
and exclusions are recorded in [generation-interface-checks.json](generation-interface-checks.json).
Original game files, captures and altered-input controls stay private. The
observer calls no AI model and changes no original game behavior.
