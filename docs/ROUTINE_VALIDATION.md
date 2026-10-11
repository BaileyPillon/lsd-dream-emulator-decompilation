# Bounded native routine checks

The complete executable comparison remains the gate for matching C. During
recovery, private candidate routines are also executed alongside original
instruction bytes and an independent integer/data model. These experiments
help identify semantic mistakes and preserve original edge cases. Their
results do not increase feature-group runtime acceptance or replace the
[original/rebuilt emulator comparison](RUNTIME_COMPARISON.md).

The following records were generated for specific, unaccepted candidate
revisions. Each report identifies its original and candidate bytes or source
hashes. A newer candidate needs new evidence. Current accepted source counts
are in the [feature inventory](FEATURE_INVENTORY.md).

| Original routine | Compared case pairs | Covered observations | Private evidence |
| --- | ---: | --- | --- |
| `func_8004CD38` | 720,896 | Every signed-byte coordinate pair for ten bounds cases and a null bounds pointer; inclusive range decisions | `.decomp-lab/dream-work/cd38-semantic-proof.json` |
| `func_8004441C` | 8,486 | Signed-short scale edges, seeded zero-denominator registers, deterministic random inputs, both output fields, other object bytes, stack and saved registers | `.decomp-lab/file-work/ui-243-semantic-proof.json` |
| `func_8004EF6C` | 8,064 | Device selection, both open-failure paths, size boundaries, icon counts, all four input/output buffer alignments, header/payload bytes, call order, stack and saved registers | `.decomp-lab/root-work/card-write-semantic-proof.json` |
| `func_8004EF6C` | 968 additional | Every 128-byte padding remainder around the tested ranges, an 8 KiB block boundary, all 256 icon-byte values, filename/title lengths and opaque Shift-JIS bytes | `.decomp-lab/root-work/card-write-semantic-proof-extended.json` |
| `func_8004EF6C` | 12 additional | Forced `delete`, `close` and `write` return values | `.decomp-lab/root-work/card-write-io-failure-proof.json` |
| `func_8001DDF4` | 2,088 | Signed midpoint coordinates, aggregate callback arguments, strict distance cutoff, first-phase bypass flag, fallback vertex selection, box/path masks, other object bytes, stack and saved registers | `.decomp-lab/root-work/ddf4-semantic-proof.json` |
| `entity_lion` | 1,520 native cases | Original RNG, timer/animation commands, link disabling, distance/state boundaries, dream callback clearing, command buffers, call order and saved registers under explicit external contracts | `.decomp-lab/root-work/lion-native-behavior-proof.json` |
| `func_8001F8B8` | 1,764 | All 32 supported TMD primitive codes, triangles/quads, plane winding, fixed-point intersections, nearest hit, optional height, exact 24-unit bounds edges, aligned buffers and complete output bytes | `.decomp-lab/render-work/f8b8-semantic-proof-1791683821346179206.json` |

The sprite check detected three negative controls: a changed maximum clamp,
subtracting the old scale, and zeroing an incoming ratio. The extended save
check detected changed save magic, creation flags and the icon-byte mask.
These controls check that the comparisons reject concrete behavioral errors.
The collision-aggregate check also rejected changing the distance cutoff to
inclusive, selecting different fallback vertices, and rounding a negative
midpoint toward zero.

An additional Z3 5.1.0 proof checks the three differing straight-line sprite
blocks for all symbolic 32-bit register and byte-memory inputs, including the
one-instruction R3000 halfword-load delay through the following shared shift.
It assumes aligned, readable memory with no faults, interrupts or concurrent
writes. The proof and three detected counterexamples are retained in
`.decomp-lab/file-work/ui-243-symbolic-locals/proof.json`. This local instruction
model is separate from the sampled Unicorn cases; it is not a verified full
interpreter, a whole-function proof, or authorization to accept different bytes.

A separate conservative control-flow attachment audit checks that no outside
branch enters those sprite blocks partway through, no incoming branch/load is
pending, and their sequential exits are clear. It verifies the other 135 words
and control edges and rejects two altered-entry controls. Evidence:
`.decomp-lab/file-work/ui-243-cfg-attachment.json`. This narrows the local proof's
entry assumptions; it does not replace the complete executable gate.

The nearest `func_8004C6A8` candidate differs by four bytes: two adjacent
dimension stores are reversed. A separate Z3 byte-memory model proves equal
registers and memory at the next instruction for all symbolic 32-bit values,
including the preceding word load's R3000 delay. Its three wrong-address,
wrong-value and wrong-load-destination controls produce counterexamples.
The other 162 instruction words match. A conservative attachment checks the
known direct entry's ALU delay instruction, NOP fallthrough and absence of
direct branches into either store; two altered-entry controls are rejected.
Evidence: `.decomp-lab/root-work/c6a8-symbolic-store-order-proof.json` and
`.decomp-lab/root-work/c6a8-symbolic-cfg-attachment-v2.json`.

This local proof assumes aligned, fault-free ordinary memory and no pending
load or branch at entry. It excludes interrupts, concurrent/device observers
between the stores, indirect interior entry and PS1 cycle equivalence. The
candidate remains unaccepted and the canonical executable retains its native
assembly. No matching-C or whole-feature count increases from this result.

The latest full-translation-unit check confirmed four differing bytes across
the entire 505,856-byte executable for that candidate, with every other byte
unchanged. The alternative preserving store order differed by thirteen bytes.
Evidence: `.decomp-lab/root-work/c6a8-nineteenth-full-gate-results.json`.

The backend is Unicorn MIPS32 little endian, executing integer instructions
used by the original R3000 routines. It does not reproduce PS1 load-delay
timing, interrupts, devices, GPU or audio. The save check uses native
`memory_card_build_path` code and explicit deterministic SDK/I/O/allocation
stubs. It does not establish physical memory-card behavior, allocation-failure
handling, caller retry policy, or natural reachability of every tested input.
No instructions in the canonical game were replaced for these experiments.

## Original collision aggregation

`func_8001DDF4` initializes two six-byte midpoint vertices from two pairs of
input vertices. It asks the model owner for a box count, resets the object's
box mask, and first checks the segment between those two midpoints against
each box and the corresponding primitive-intersection callback. A nonzero
global flag requires the returned distance to be strictly greater than 512;
a zero flag bypasses that distance test in this first phase.

When that phase sets any box bit, the output is one and the function returns
one. Otherwise it traverses the input's paths and checks only vertices one
and two against their partners four vertices later. Those fallback checks
always require distance greater than 512. Successful checks set the box bit
in the object and the path bit in the output. The final return indicates
whether the output mask is nonzero.

The private proof contains 1,896 case pairs with explicit deterministic
bounds/intersection callbacks and 192 pairs that execute the unchanged native
`func_8001E110` and `func_8001ECFC` bounds code. Its independent model compares
coordinates, call order, masks and complete object/output data. Index-edge
cases check the compiled target's 32-bit shift behavior; they do not establish
portable C behavior or natural game reachability for those indices.

The C candidate allocates only the proven 12-byte midpoint pair. The native
frame also has an unused 28-byte region whose source allocation remains
unknown. A diagnostic 40-byte array hypothesis is not accepted as an original
object merely because its frame resembles the native frame. The proof keeps
the model-owner and TMD-intersection calls stubbed, and does not establish
polygon-intersection geometry, complete movement or collision parity.

## Original primitive intersection

The private `func_8001F8B8` candidate retains the native 1,944-byte instruction
sequence and 352-byte frame, with 103 differing bytes confined to stack-relative
offsets in 95 instructions. Every other opcode, operand and instruction position
agrees. That is a layout diagnosis, not an accepted byte match.

Its paired execution check uses the original TMD decoder and the original
`SquareRoot0` instruction body and 192-entry table. The GTE outer-product,
squared-vector and leading-bit operations have explicit signed-integer
contracts. An independent model checks geometry, nearest distance, hit bytes,
optional height and SDK calls. All 1,764 aligned case pairs passed; four separate
misaligned-halfword pairs produced the same backend exception and partial-write
observations. Three changed-geometry controls were detected.

The native fine test combines a plane intersection with the polygon's axis
bounds expanded by 24 units. The cases preserve contacts outside a triangle's
actual edges that still satisfy those bounds. Changing it to an exact triangle
edge test would alter original behavior. The explicit GTE contracts and Unicorn
exceptions do not establish hardware exception, GTE saturation/flag, load-delay,
device or cycle parity. The candidate remains private.

## Bounded original NPC check

The Gray Man record at index 98 uses the already-matching 192-byte
`entity_gray_man` callback at `0x80064618`. The native callback and eleven
downstream native routines passed 768 fixture cases against an independent
object/state model. The proof executes the original virtual-table bindings,
effect creation helper, color-step setter, effect-start branch, link-disable
chain and flashback-count reset. It tests nonzero trigger values, fresh effect
allocation success/failure, existing-effect reuse, effect states and flashback
counts, and checks the complete object/context buffers and call arguments.

The allocation, attachment, effect activation/color, sound stop and movement
callbacks have explicit deterministic stubs. The downstream state changes
are native code. The report is
`.decomp-lab/root-work/gray-man-native-behavior-proof.json`; changed movement
and omission of flashback reset were both rejected by private negative controls.
This establishes bounded original NPC behavior under those contracts, not a
complete natural encounter or acceptance of any whole game-feature group.

The reproducible public verifier now provides this same 768-case Gray Man
model through `tools/verify_native_ai.py --callback gray_man`, with fresh
source/build hashes and measured native entry counts. It detects native
movement and flashback-reset mutations in private emulator memory. Evidence:
`.decomp-lab/native-gray-man-verification-second.json`. The Lion selection
passed 1,608 cases at `.decomp-lab/native-lion-verification-fourth.json`.

The additional `.decomp-lab/root-work/gray-man-object-graph-proof-v2.json`
passed 1,728 cases with a synthetic canonical base-class parent and zero,
one or two transform children. Native unlinking removes both list references,
clears the coordinate parent and updates child visibility bits. Two private
wrong-instruction controls were detected. The allocator/free, effect and
movement contracts remain explicit; this is further bounded branch evidence,
not natural encounter or whole-callback acceptance.

## Bounded original animation checks

The original interpreter and its concrete virtual-call chains execute all
26,797 animation record instances extracted from the owned English-v1 disc.
Four private reports cover structural declarations/skips, flags/transforms,
parent attachment with the native allocator, and primitive attachment with
native SDK mapping/linking. They use actual records and child-type order with
synthetic initialized object/state buffers and no native stubs. Ten concrete
instruction mutations are rejected across the four checks.

The corpus count includes repeated model content. The 504 additional boundary
fixtures and 13 synthetic frames are separate measurements. Complete
animation sequences, construction/lifetimes, natural encounter reachability,
render/GTE output and hardware timing remain unaccepted. See
[the animation audit](NATIVE_ANIMATIONS.md) for exact report paths and scopes.
These checks do not add to the 2,376 public NPC fixtures, the provisional
40-feature denominator, matching-C coverage or whole-feature acceptance.

The subsequent private sequence proof covers all 122 extracted animation
instances with persistent synthetic object/heap state. It executes actual
selection, tick, enable and pause functions with native allocation and model
linking: 9,022 frame interpretations, 65,917 record interpretations and 209
loop wraps. Initial disabled ticks, pause/resume, single-frame suppression
and counter-wrap boundaries are checked. Two changed-instruction controls
are detected; all 25 inventoried native routines are entered without stubs.
Evidence: `.decomp-lab/root-work/native-animation-sequence-proof-first.json`.
Natural object construction/lifetimes, action callbacks, render/GTE output,
hardware timing and whole-feature acceptance remain open.

## Original save-writer behavior

`func_8004EF6C` occupies 960 bytes at `0x8004EF6C`. Its original function-byte
SHA-256 is
`a24ccbb37789695a86a6bf46e624aea68a667ed5cac934704edf7e6677349092`.

The function builds a `bu00:` or `bu10:` filename, deletes the prior file,
opens a newly allocated file, closes it and opens it for writing. Its native
creation flags are `(((u32)(size + 0x21FF) >> 13) << 16) | 0x200`. The first
open failure prints the original diagnostic and returns zero; the second
returns zero without that diagnostic.

After the second open succeeds, it allocates a 512-byte buffer and produces:

| Buffer offset | Original contents |
| --- | --- |
| `0x00` | `SC` magic |
| `0x02` | Low byte of `icon_count + 0x10` |
| `0x03` | Low byte of the native 8 KiB payload-block rounding |
| `0x04` | NUL-terminated title copied with `strcpy` |
| `0x60` | 32 CLUT bytes from the TIM image at offset `0x14` |
| `0x80`, `0x100`, `0x180` | Three 128-byte icon frames from TIM offsets `0x40`, `0xC0`, `0x140` |

All three frames are copied even when fewer are requested. The first write
length is `((u8)icon_count << 7) + 0x80`. The buffer is freed, and the payload
is written with its length rounded upward to 128 bytes. The function then
closes the file and returns one. It ignores `delete`, `close` and `write`
return values; this was preserved and tested rather than silently corrected.
Untouched header bytes retain the allocation's prior contents.

At the tested candidate revision, the 960-byte C result differed in eight
register-operand bytes: its title and texture used the opposite pair of saved
registers. The semantic results above did not authorize its promotion.
