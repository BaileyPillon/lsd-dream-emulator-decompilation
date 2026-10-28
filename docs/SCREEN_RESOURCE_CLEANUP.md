# Original screen resource cleanup

The original title-menu and dream-chart destruction paths now execute in
**144 initialized profiles through 51 complete original function bodies**.
All manager, pool and guarded object buffers agree with an independent
ownership model. Three executed release faults are rejected. These are
constructed resource graphs; natural screen histories remain a separate gate.

The chart declaration also now matches its original factory's **0x244-byte**
allocation. Two unreferenced fields at `0x244` and `0x248` extended the old C
declaration to `0x24C`. They were removed, the final three field offsets are
documented, and a target-compiler size assertion prevents regression. The
event-buffer pointer is at `0x240`, as used by the original cleanup body.
The complete rebuilt executable remains byte-for-byte identical to retail.

## What executes

Each case enters `base_class_destructor` with a supplied, owned screen.
The receiver's original Cleanup slot runs without an output substitute.
The main-menu path also executes its original card and title-text cleanup;
the chart path releases all **100 distinct dream-cell objects**. The shared
UI body releases its sprite, tile buffer, atlas and optional texture/sound.
Their original coordinate, rotation, glyph and file buffers are included.

Parent notifications, reciprocal list removal, detached child links, heap
release order and lock transitions execute their original instructions.
An external observer and borrowed child survive where present. Borrowed
sound and its supplied bank also survive; the checked state distinguishes
them from resources owned by the screen.

| Dimension | Checked contexts |
| --- | --- |
| Screen | Title menu; dream chart |
| Receiver/data alias | Physical RAM; KSEG0; KSEG1 |
| Initial bytes | Two patterns, including fragmented free intervals |
| Optional resources | Absent; nonnull file/card/texture buffers |
| Ownership links | Detached; reciprocal parent and child lists |
| Sound | Borrowed; owned without a bank; owned with an allocated bank |

There are 24 cases per screen/sound combination. Title text contains three
or seven glyphs. A case makes 22–533 release calls, including original NULL
releases, and executes 3,858–138,753 instructions. Every release acquires and
releases the original heap lock, including a NULL release.

For the allocated-bank case, original `sound_close`, `SsVabClose`, `SpuFree`
and `_spu_gcSPU` execute against supplied SDK ownership RAM. The expected
SPU interval, tail sentinel, bank flag and bank count are predicted before
execution. Sound-instance count starts at two and ends at one. This does
not exercise final-instance hardware shutdown or establish audible output.

## Verification and reproduction

The [verifier](../research/screen_lifecycle/verify_cleanup.py) requires a
current canonical build and the existing isolated Unicorn 2.1.2 backend
described in the [lifecycle instructions](../research/screen_lifecycle/README.md).
From the repository root in that Linux environment:

```bash
python -B research/screen_lifecycle/verify_cleanup.py \
  --output .decomp-lab/screen-resource-cleanup-new
```

The command retains a diagnostic link when needed. `--diagnostic` can reuse
an existing diagnostic directory; its complete allocated image is checked
against retail again. GNU symbols, complete ELF function extents and every
original function byte must agree with the [51 published function pins](../research/screen_lifecycle/cleanup-functions.json).
Code, source dependencies, the current build and the backend are checked
for changes. Reports and the compressed execution journal stay private.

Three private instruction changes must execute, return normally, and fail
the intended check: release 99 chart cells instead of 100; retain a file's
NoFree flag; and omit the actual SPU interval-release store. The first two
fail ordered release comparison; the third fails the complete guarded SDK
allocator buffer comparison. A NULL destructor result alone accepts none.

A separate audit reconstructs every initial buffer from the input recipe
and walks the raw ownership structures without importing the producer's
Fixture, Machine or cleanup oracle. It reuses the previously qualified
interval allocator, checks every final buffer and SDK state, and qualifies
104,184 recorded indirect transfers against original instructions, complete
function owners and callee-entry receivers. The
[public metadata](screen-resource-cleanup-checks.json) records hashes,
counts, controls, backend identity and the evidence boundary.

## Remaining gates

Construction and the Run/graphics phase are not executed by this profile.
It supplies hidden, detached render objects and an empty secondary-menu
panel context. Populated panels, pending CD requests, final sound shutdown,
physical card operations, natural input histories, rendering, playback and
timing still require their own comparisons.

The earlier [typed Destroy profile](SCREEN_DESTROY_INTERFACE.md) retains its
four constructor/cleanup contracts; this companion checks different,
initialized destruction contexts and substitutes no dependency outputs.
Neither profile accepts a complete natural lifecycle or an original feature.
C recovery stays at **197,172 / 199,912 bytes (98.63%)**, with two game
assembly functions and three inherited storage explanations remaining.
No new original feature, NPC encounter or model-service call is counted.
