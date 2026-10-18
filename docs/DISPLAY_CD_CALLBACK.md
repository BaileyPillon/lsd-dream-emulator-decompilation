# Display callback and queued CD read handoffs

The display's callback field, setter and virtual setter now share the same
signed-word callback type as the installed `cd_file_driver_tick`. Its caller
continues to ignore that result. The complete executable remains canonical;
the remaining callback warning in the CD unit is removed without a function
pointer cast or a new wrapper.

| Measure | Previous checkpoint | Current checkpoint |
| --- | ---: | ---: |
| Ordinary compiler warnings in the CD unit | 3 | 2 |
| Compared native callback guard cases in this profile | 0 | 25 |
| Recorded framed Read entries | 98 | 98 |
| Qualified queued Read origin/replay argument pairs | 0 | 49 |
| New recovered C bytes | 0 | 0 |
| Whole feature groups accepted | 0 | 0 |

The two remaining CD warnings are the previously documented uninitialized
`request` provenance and inherited unused sector buffer. The
[three known storage explanations](UNUSED_LOCAL_CENSUS.md) remain unresolved.

## Callback source and original ABI

The original setter writes the callback at object offset `0x30`; its virtual
setter is at slot `0x84`. The shared C view preserves the `0x34` object and
`0x88` table sizes. The original display loop loads the callback from `0x30`
and calls it at `0x80020AB0`. Its first instruction after the delay slot
overwrites `v0` with the table pointer, so the callback's return word is unused.
That loop relation is static evidence, not a new natural frame history.

The [bounded checker](../research/display_callback/README.md) compiles three C
callers against the shared header and seven target ABI assertions. Twenty-five
initialized lock/memory-lock cases execute fifty original setter calls,
twenty-five CD ticks and five original memory-lock getter calls. The three
callers execute 75 top-level calls. Pointer arguments, zero status results,
owned object/table/global bytes, saved registers and stack guards agree.

The checker uses no function-output stubs. Three instruction faults are
rejected after execution, and three incorrect callback declarations fail
compilation. Five original ranges are qualified through a complete canonical
symbolic link and independent ELF/GNU extents; only three execute positively.
The display loop and the sync-mode setter support static review and a negative
control. VSync, SDK callback registration, active CD phases, natural timing and
whole display behavior remain outside this fixture.

## Queued reads in the retained natural history

The [original return capture](DISPATCH_RETURNS.md) contains 112 CD Read entries:
fourteen synchronous calls and 98 framed calls. The new read-only lifecycle
inspector pairs those 98 framed entries into **49 queued origins and 49 later
dispatches** in original FIFO order. It checks the same receiver, destination
and unsigned byte-length word, and requires the originating call to return
before replay begins. The replayed receiver is open and marked as being
dispatched from the queue.

All 49 replay entries see the driver idle; their returns see it busy. Their
zero Read status is therefore kept separate from later completion evidence.
The requested byte-length words sum to **3,525,008**. This is a sum of arguments,
not a transferred-byte count or unique content measurement. Pairing calls at
the same receiver address does not establish object allocation lifetime.

Original and rebuilt histories agree on every pair. The underlying method,
return, payload and recorded game-output comparisons are rerun before this
analysis is accepted. No new emulator run or controller history is added.
A separate numeric-layout audit agrees, and eight retained-data faults fail
the pairing checks. Fourteen owned source-only tests cover ordering, arguments,
driver state, missing returns and unsupported modes.

With the verified return captures and their original raw tracks still present:

```powershell
python tools/inspect_read_lifecycle.py `
  --reference D:/private/return-original `
  --candidate D:/private/return-rebuilt `
  --output .decomp-lab/read-lifecycle-new.json
```

The profile supports the observed framed mode `(1, 1)` and fails on other
framed modes rather than inferring the same lifecycle. It accepts a queued
handoff, not an SDK request or completed transfer. The receiver's stored file
start position is insufficient to validate later sequential reads; capture
SDK requests, polling results and position progression before accepting their
completed buffers.

## Remaining source and parity gates

The source change touches only the display C unit and its header. Ordinary
and fresh 306-object builds reproduce the original executable, preserving the
other 390 of 392 protected game-build inputs. Both tooling suites pass 1,068
tests with two expected skips per platform.

Ten further primitive-collision comparisons qualify with GNU tools: eight
full-width product forms and two repeated controls. None matches. The best
primitive candidate remains 22 bytes different, and the hull candidate remains
26 bytes different. No collision source is promoted.

Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two assembly
functions and three inherited storage explanations open. The forty provisional
feature groups and 38 listed-core C groups are unchanged; an exhaustive
original feature total is unknown. Whole-feature and whole-NPC acceptance
remain zero. The playable matching build and separate Bevy port preserve their
identities. These development tools add no gameplay, NPC or model-API behavior.

[Validation metadata](display-callback-checks.json) publishes bounded counts and
source/evidence hashes. Original bytes, private captures and fault images stay
outside the repository.
