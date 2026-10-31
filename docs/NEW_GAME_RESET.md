# Original new-game and reset state

A subsequent [controller comparison](CONTROLLER_NEW_GAME_RESET.md) observes the
original ordinary and flashback reset routes and resumed gameplay. This page
retains the earlier isolated-VM and retained-checkpoint profile and its limits.

The original initializer writes **576 of the 1,792 save-block bytes**. It preserves
the remaining **1,216 bytes**, including inactive mood history and flashback
records. A new game resets their active counters; it does not erase every old
record. Replacing this behavior with a full zero-fill would change the game.

The matching C now declares `gpNavChallengesComplete` as a byte pointer and
`gpDynamicLinkPenalty` as a word pointer. The navigation initializer takes a byte
array rather than a word array. Its 30 byte stores, global pointer bindings,
scoring consumers and complete executable remain identical to the original.
No game function is newly promoted by this type correction.

## Complete save-block behavior

`dream_sys_get_save_data` returns the object at `+0x178` with size `0x700`.

| Written range, relative to the dream system | Bytes | Reset value |
| --- | ---: | --- |
| Marker at `0x178` | 4 | Original `g_SaveDataMagic` word |
| Year, day and score words at `0x17C–0x18F` | 20 | Zero |
| Flashback count at `0x46C` | 4 | Zero |
| Reserved bytes at `0x5D8` and `0x5DF` | 2 | Zero |
| Navigation flags at `0x5E0–0x5FD` | 30 | Zero |
| Dynamic link count at `0x600` | 4 | Zero |
| Screen shake at `0x678` | 4 | One |
| Reserved words at `0x67C` and `0x680` | 8 | Zero |
| Reserved tail at `0x684–0x877` | 500 | Zero |

The preserved ranges are `0x190–0x46B` (732 bytes), `0x470–0x5D7` (360),
`0x5D9–0x5DE` (6), `0x5FE–0x5FF` (2) and `0x604–0x677` (116). Predictions
include every byte in the complete `0x928`-byte object, auxiliary buffers and
navigation globals, rather than comparing only the written ranges.

The new-game flag at `0x878` is outside the save block. The initializer preserves
it. The constructor sets it to one before initialization; `dream_sys_end_day`
also sets it to one after its mode-two reset. Clearing/querying that flag and
the signed get/set flag at `0x924` are checked separately. The latter exchanges
nonnegative values and treats negative values as queries.

## Original code execution

The [native checker](../tools/verify_new_game_reset.py) qualifies eight complete
original functions, totaling **488 bytes**, through independent ELF and GNU sized
symbols. Its symbolic diagnostic link must reproduce the complete canonical
executable before any function is accepted. The
[function records](../research/new_game_reset/functions.json) pin every body.

**1,032 initialized profiles perform 2,064 original/rebuilt executions.** All
eight original bodies execute, including the real navigation initializer and
`memset`, without output stubs. Profiles cover three RAM aliases, four complete
input byte patterns, mode-two resets in ordinary/flashback contexts, nonreset
end modes, signed flag boundaries, optional save-size pointers and all four
byte alignments of the 30 navigation flags. Normal non-flashback mode-zero
completion needs its separate score/chart model and is explicitly rejected by
this reset profile; it is never silently treated as a no-op.

Every positive call checks complete object/save/auxiliary/global buffers, the
actual save-block store-address union, owned original call flow, original code,
returned values where defined, saved registers and stack guards. The original
compiler passes **27 layout assertions** with warnings treated as errors.
The game translation unit still has unrelated inherited compiler warnings.

Four executed original-instruction controls are rejected by the independent
data expectations: clear 499 bytes, clear 501 bytes, omit the first navigation
flag and store the new-game flag in the wrong word. The first native attempt
completed its positive loop but stopped during fault selection because it
expected ADDIU where the matching assembler emitted ORI. Its exact producer
and partial evidence remain private and unaccepted. The completed run qualifies
both encodings and supplies all four fault witnesses.

A separate audit reconstructs all 1,032 expected buffers, return values,
store unions and call sequences without importing the producer's state model.
This is a second checking implementation, not independent human acceptance.

## Retained natural checkpoints

The [retained-state reader](../tools/inspect_new_game_save.py) rechecks five
MainRAM checkpoint pairs from the earlier qualified
[file/heap recording](FILE_HEAP_LIFETIMES.md), reading exact archive members in
memory. It creates no new emulator recording or expanded RAM file. Complete
checkpoint hashes match both original/rebuilt reports, and all eight original
function bodies are rechecked in the captured RAM.

| Relative frame | RAM day counter | Matches reset-written fields | Nonzero preserved bytes |
| --- | ---: | --- | ---: |
| 1,500 | 001 | Yes | 0 |
| 1,800 | 001 | Yes | 0 |
| 2,100 | 001 | Yes | 0 |
| 24,000 | 002 | No | 14 |
| 30,000 | 002 | No | 14 |

Copies of all five complete objects also pass **20 additional native VM
executions**, covering direct initialization and end mode two in both executable
images. These objects are relocated into isolated fixtures; their remaining
pointers are preserved as opaque bytes. They are not restored whole emulator
states or live-game injections. The two Day 002 contexts retain their 14 nonzero
inactive-history bytes after reset. A separate public CLI integration check
repeats the Day 002 case and reports the same limits.

Matching values in a checkpoint do not prove that a reset event occurred.
Structural pointer/table agreement also does not establish allocation lifetime.
The reports retain both distinctions.

## Reproduce

With the current complete matching build, original compiler and existing
isolated Unicorn **2.1.2** environment, keeping the pinned build Ninja on PATH:

```sh
python -B tools/verify_new_game_reset.py --output .decomp-lab/reset-native-new
```

Inspect one exact retained MainRAM member using its qualified checkpoint hash:

```sh
python -B tools/inspect_new_game_save.py \
  --ram "$RAM_ARCHIVE" --ram-member "$EXACT_RAM_MEMBER" \
  --ram-sha256 "$CHECKPOINT_RAM_SHA256" --exe rom/SLPS_015.56 \
  --functions research/new_game_reset/functions.json --output "$NEW_REPORT"
```

Add `--native-replay --rebuilt-exe build/SLPS015.56` to execute copied-object
fixtures in the isolated VM. This option still does not prove a natural reset.
Synthetic tooling tests need no game files, compiler or native backend:

```sh
python -B -m unittest tests.test_new_game_state tests.test_new_game_reset_profiles tests.test_inspect_new_game_save -v
```

## Remaining acceptance

The original map callback statically exposes the next controller route.
`m_LinkActive != 0` first gates the dispatcher. Under
the default pad table, held index 10 (`0x100`, notification `0x0C`) arms the
request when the text/pause state is active and map state is zero. Pressed
index 4 (`0x10`, notification `0x16`) dispatches the armed callback; releasing
index 10 (`0x2C`) disarms it. The armed callback notifies `0x0D`, and the original
dream-session handler calls `dream_sys_end_day(..., 2)`. Source routing is
separate from observing that complete route through normal controls.

Continue eligible/ineligible controller histories, ordinary/flashback reset
endings, original constructor entry/return boundaries, natural object lifetimes
and the corresponding video/audio/card observations. The bounded integer VM
does not verify PS1 timing or hardware. Full F004 acceptance remains open.

[Validation metadata](new-game-reset-checks.json) records the current producer,
body and evidence hashes. Matching C remains **199,912 / 199,912 bytes**, with
zero game assembly fallbacks, 40 provisional feature groups, 107 original NPC
callbacks in C and zero accepted whole features/encounters. These are analysis
tools, with zero model API calls and no original gameplay changes, optional
mods, new discs or runtime copies. The supported playable build and saves remain
preserved. Earlier inventory nodes and historical source evidence remain intact.
