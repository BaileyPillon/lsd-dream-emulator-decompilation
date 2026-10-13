# Original next-stream exclusion bounds

The original `D_80087150` record is now declared in matching C. It contains
four mixed-width fields in twelve bytes: signed halfword minima for X/Z cells,
then signed word maxima. Its values are `(0, 0, 8, 9)` and its edges are inclusive.
The record is writable data in the original image; consumers hold a const pointer.

The matching build also corrects the renderer's two-argument setter at virtual
slot `0x134` and names its pointer field at context offset `0x1DC`. Stage zero
supplies this record; other stage branches supply null. The map-scene caller now
uses the typed setter rather than an integer-offset function-pointer cast.

The standard build and a separate fresh build both reproduce the canonical
505,856-byte executable. There are 306 build objects after splitting the original
data block around the new C-owned record. This is **one recovered data record,
twelve bytes**, not a new C function. Game-function C coverage remains
194,212 / 199,912 bytes (97.15%); nine assembly functions and 24 inherited storage
explanations remain. The bounds predicate itself still uses original assembly.

## Original consumer behavior

The native selection path queries the cached world position, resolves one of
seven stream slots and derives signed X/Z cell bytes. It appends the current
stream's row first. It then considers the next slot when the point is outside
the configured bounds, or when the bounds pointer is null, subject to the slot
count. It considers the preceding slot when its index is nonnegative.

Consequently, the 90 cell pairs inside X `0..8`, Z `0..9` suppress consideration
of the next slot when these bounds are enabled. Null bounds return "outside"
and permit that consideration. A selected slot whose stream metadata is inactive
produces row index `-1`; it is not removed from the row count by this routine.
These statements describe the selection component, not complete rendering.

Ten original routines execute in **9,252 distinct constructed fixtures** without
dependency output stubs. The checker compares all 25 caller/cache/stream buffers
(4,416 bytes) per fixture and preserves GP, SP, RA and saved registers.

| Constructed domain | Cases |
| --- | ---: |
| Every 20-by-20 cell, seven layers, enabled and null bounds | 5,600 |
| Remaining 127 stream-load masks, seven layers, inside/outside witnesses, both bounds modes | 3,556 |
| Translated stream origins and cached-segment aliases | 96 |
| Total distinct fixtures | 9,252 |

An independent audit reconstructs the inputs and checks 46,260 slot-query entries
and 23,758 row-builder entries against the model. Three deliberate faults change
the setter's destination field or the predicate's maximum-field reads. Each
changed instruction executes once and changes checked buffers. Original files
and the rebuilt executable remain unchanged by these private fault controls.

The fixtures construct valid stream graphs; they do not establish natural scene
construction, asynchronous loading, GPU output, PS1 load-delay timing or complete
gameplay acceptance. NPC bounded coverage stays at 20/107 and whole-feature
acceptance stays at 0/40 provisional groups.

## Source ownership and retained diagnostics

The C object's complete `.data` section is twelve bytes and equals the original
record. `D_80087150` is its sole named data label and remains at `0x80087150` in
the complete link map. The legacy pipeline emits this label without a symbol
size or object type, so ownership is verified from the complete section, source
definition, sole label and full-image equality. No symbol size is fabricated.
The earlier failed size/type assumption is retained separately.

The initial native sweep completed its comparisons but failed an incorrect final
tally assertion. The corrected sweep verifies 96 translated/alias fixtures and
9,252 total cases. Both producers and the diagnostic remain private and pinned.
The reports and before/after measurements are in
[stream-exclusion-checks.json](stream-exclusion-checks.json).

This source recovery adds no original gameplay feature, modern AI API call or
optional mod. The original NPC behavior and analysis/modding tools retain their
separate inventories. Raw game images, original code, native buffers and faulted
code remain excluded from Git.
