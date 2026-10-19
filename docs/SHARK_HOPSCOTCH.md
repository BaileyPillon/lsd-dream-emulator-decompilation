# Shark and Hopscotch Girl behavior

Two more original callbacks have bounded native execution comparisons, raising
coverage from **41 to 43 / 107**. Matching C remains **197,172 / 199,912 bytes
(98.63%)**, with two assembly functions and three inherited storage explanations
still open. Whole NPC encounters and whole feature groups accepted remain zero.

The [evidence record](shark-hopscotch-checks.json) distinguishes original game
behavior from the separate analysis tool. The tool makes no external model calls
and changes no game behavior, executable, asset or optional mod.

| Evidence | Verified count |
| --- | ---: |
| Distinct initialized fixtures | 1,535 |
| Shark fixtures | 377 |
| Hopscotch Girl fixtures | 1,158 |
| Repeated initialized fixtures excluded | 30 |
| Constructed callback histories | 3 |
| Callback calls in those histories | 1,044 |
| Additional literal native-output checks | 25 |
| Complete original function ranges qualified and entered | 28 |
| Positive native GTE commands | 2,486 |
| Executed instruction faults detected | 7 |
| Escaped command stores rejected before execution | 1 |
| Dependency-output stubs | 0 |

## Embedded command context

The callback argument points to the entity's own 84-byte context at offset
`0x9c`. The fixture sets its owner and callback pointers to the tested entity
and original callback. Context writes are compared both through that view and
through the complete entity buffer. Shark's link-disable path stops this same
context. All three sound handles begin inactive; the actual sound-stop routine
executes without an active sound backend.

The original property rows remain intact. Shark uses entity ID **34** and its
actual zero proximity byte. Hopscotch Girl uses ID **55** and proximity **20**.
The profile does not substitute a positive Shark radius to fit another verifier.

## Original Shark decisions

The unsigned tick windows are checked at their exact endpoints, including
signed-word extremes. Turns use the original rational angle records and native
transform, `RotMatrix`, `ApplyMatrixLV` and GTE implementations.

| Callback tick | Decision |
| --- | --- |
| 400 through 409 | Add the original +9-degree yaw record |
| 700 through 709 | Add the original -9-degree yaw record |
| 830 through 833 | Add the original -9-degree yaw record |
| 851 or later, outside a turn window | Disable linking and stop its behavior context |
| Below 800 | Request forward movement -60 |
| 800 or later | Request forward movement -512 |

The original fixed-point conversion produces yaw increments of **+102 / -102**
in the constructed zero-angle hand checks. Disabling occurs before movement;
the tick-851 callback still finishes its movement request. This does not prove
that the engine schedules another callback after disabling.

Movement mode 6 also executes the original scene-node and base-transform query.
The graph is meshless, so populated collider traversal and collision responses
remain outside this profile.

## Original Hopscotch Girl decisions

At entity tick zero, the original RNG draws once. A result divisible by three
selects the original scale record `(1, 2, 1)`. Later ticks do not take this
initialization draw. Native seed-zero and seed-one checks separately confirm
the taken and untaken scale branches.

The original proximity calculation writes context slot four. Integer division
matters: with proximity 20 and scale 1000, distance 40,960 produces **1024**;
distance 40,961 produces **-1**. Missing dream context also produces -1.

The callback subtracts 32 from an animation frame at least 32 **once**. It
issues command 19 at resulting frame 9, 17 or 23, with a second command at 23.
Thus frames 23 and 55 emit both commands; frame 87 does not. The checks preserve
this distinction rather than treating the frame as a repeating modulo-32 loop.

## Scope and reproduction

One persistent Shark VM is called at supplied ticks 0 through 851. Two
Hopscotch Girl VMs use different initial RNG seeds over 96 calls each. Entity,
pose, context and RNG state persist; **tick, command timer and animation frame
are supplied externally**. These are constructed callback histories, not
engine-driven animation playback or naturally reached encounters.

Full buffers, ordered helper calls, RNG state, ordered GTE requests/results,
return registers, stack boundaries and declared-write regions are checked.
Seven executed mutations change turn/speed/disable boundaries, command writes,
the RNG increment or movement storage. A separate mutation attempts a store
outside every declared graph buffer and is rejected before that write.

Natural construction, registered engine dispatch, populated collision graphs,
active sound handles, drawing/audio output, controller reachability, complete
encounters and PS1 timing remain unverified here. This evidence adds no accepted
whole feature, newly implemented original feature, C byte or optional mod.

Run from a current canonical build with the installed analysis backend:

```sh
python -B -m tools.verify_shark_hopscotch \
  --output .decomp-lab/shark-hopscotch-new \
  --bridge /path/to/existing/gte-bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'
```

Use a fresh private output directory and reuse the existing native bridge and
runtime. Successful cases retain hashes and compact reports/logs. No emulator
runtime, extracted asset tree, game disc or successful raw buffer set is copied.
The published source pins distinguish executed working-file bytes from Git
blobs where inherited files differ only in line endings.
