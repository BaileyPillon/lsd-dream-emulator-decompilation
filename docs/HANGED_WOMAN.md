# Original Hanged Woman behavior

The [native verifier](../tools/verify_hanged_woman.py) checks the original
Hanged Woman callback and its actual mood, distance, player-control, movement
and held-object dependencies. Bounded callback coverage rises from **43 to
44 / 107**. Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two
assembly functions and three inherited storage explanations outstanding.
No game behavior, model API call or whole-encounter acceptance is added.

The [evidence summary](hanged-woman-checks.json) pins the local native report,
independent audit and public sources. Function addresses, complete lengths and
hashes are published as [range metadata](hanged-woman-function-ranges.json);
original images, instruction bytes, buffers and GTE logs remain private.

## Verified scope

| Measurement | Result |
| --- | ---: |
| Distinct initialized native fixtures | 2,514 |
| Persistent constructed histories | 3 |
| Calls across those histories | 1,106 |
| Additional literal native output checks | 15 |
| Complete original routines actually entered | 30 |
| Positive native GTE commands | 4,306 |
| Executed wrong-output controls detected | 6 |
| Escaped-store control rejected before the write | 1 |
| Dependency-output stubs | 0 |

The fixture groups cover mood/RNG initialization, the strict distance boundary,
three existing movement-control modes, signed clocks, timed motion with varied
poses and word boundaries, and held-object flag polarity. Every case checks
complete declared buffers, ordered helper calls and returns, RNG state, GTE
requests/results, saved registers, return state and guarded writes. Distinct
cases are counted from initialized bytes and seed; there are no duplicates.

The command context occupies the owner's actual 84-byte region at offset
`0x9c`. Owner and callback pointers agree, and the same bytes are checked again
through the complete entity buffer. The original property binding remains
entity ID **58**, with proximity byte **30**.

## Original decisions

At tick zero, yellow dream color arms state 11 without drawing RNG. Other
colors draw the original RNG and select state 12 on a remainder of zero modulo
three. Every hundred command-timer updates, the script refreshes its trigger
ratio and pose commands using original proximity helpers.

In state 11, distance must be **strictly below 1,024** to clear the player's
movement callback and enter state 13. Clearing movement mode 2 also resets view
activity through the original helper; this call does not clear the view-update
callback. State 13 moves the player vertically for ticks below 50, alternates
lateral direction in 20-tick halves until tick 500, then requests notification
code 12 once. The profile verifies that request, not delivery to a dream/session
listener.

State 12 uses the same strict distance condition to stop animation and enter
state 14. Ticks below ten move the entity vertically. At tick ten, the callback
sets its pose and sound command fields, applies the original roll, moves in the
rotated lateral and vertical directions, changes a held node's visibility flag,
and returns to state 1. The held node is loaded from slot one of the owner's
node list. Its flags are at transform offset `0x10`; the original setter updates
bit 31 while preserving the other bits.

Both movement paths execute the actual original transform methods, SDK matrix
routines and the pinned Nymashock GTE bridge. The verifier substitutes no helper
outputs. Control mutations alter only isolated private CPU memory and include
wrong distance/tick limits, motion distance, flag polarity, RNG and an escaped
command store.

## Histories and limits

Two persistent VMs each execute 502 calls from yellow initialization through
the end-request boundary, starting in movement mode 1 or 2. A third executes
102 calls through RNG selection, lifting, roll, held-node update and later
periodic commands. Script ticks advance from the preceding native tick;
command timers are supplied externally.

These are constructed meshless and colliderless graphs with a real held-node
record and no notification recipients. They do not establish natural spawning,
engine dispatch, player world-coordinate propagation, populated collision,
animation playback, sound playback, rendering, delivered day-end transitions or
PS1 timing. Compared natural callback types remain **5 / 107**. Whole-NPC
encounters and whole-feature groups accepted at runtime remain **zero**.

## Reproduce

Use the supported matching WSL toolchain, a current canonical build, and the
existing native GTE bridge/runtime described in [native GTE checks](RENDER_GTE.md).
Choose fresh private output:

```bash
PYTHONDONTWRITEBYTECODE=1 python -B tools/verify_hanged_woman.py \
  --output .decomp-lab/hanged-woman-new \
  --bridge /absolute/path/to/existing/gte-bridge.exe \
  --runtime D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1
```

The [ten source-only tests](../tests/test_hanged_woman.py) use owned fixtures
and need no disc, BIOS, native game execution or GTE bridge. Native evidence
and those tooling tests are separate checks. The matching player, optional mods
and separate Bevy port retain their existing behavior and scope.
