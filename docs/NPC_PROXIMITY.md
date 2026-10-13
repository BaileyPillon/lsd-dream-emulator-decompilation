# Original NPC proximity and movement

Bear, Rabbit, Acrobats and Ship pass **10,408 distinct constructed fixtures**
through 25 original routines, with no dependency output stubs. Seven private
instruction faults are detected, each after executing its changed instruction.
These four callbacks extend bounded native coverage from **16 to 20 of 107**.
Whole-callback and whole-feature acceptance remain zero.

| Original callback | Entity-table ID | Proximity byte | Distinct fixtures |
| --- | ---: | ---: | ---: |
| Bear | 43 | 10 | 4,496 |
| Rabbit | 44 | 10 | 5,084 |
| Acrobats | 66 | 20 | 279 |
| Ship | 64 | 40 | 549 |

The checker derives these bindings from the original 130-record entity table.
It pins all 26 reviewed function ranges; the vertical movement wrapper is
reviewed but never entered in this profile. Its counts are not new game
features, a count of natural encounters, or a whole-game parity percentage.

## Recovered rules

The distance routine measures X/Z Manhattan distance. It reads the entity's
local position and the player's cached world position, ignores Y, and retains
signed 32-bit subtraction, negation and addition wrapping. In particular,
negating the minimum signed word does not produce a positive distance.

The trigger routine returns -1 without a dream-system context or outside the
inclusive radius. The radius is the signed property byte shifted left by 11.
Inside that radius it performs two truncating divisions:

```text
ratio = distance / (radius / entity.proximityScale)
```

For proximity 10 and scale 1,000, a distance of 20,480 is inside the radius and
returns 1,024. Combining the divisions would change original behavior. Fixtures
cover scales 1, 100 and 1,000, both signs and axes, split X/Z distances, radius
boundaries and missing dream contexts. Zero scales and zero inner quotients
are excluded; the original division-trap paths remain unverified here.

Bear and Rabbit execute their shared initialization and real RNG. Its ten
residues select ordinary behavior, state 10, or the original fractional scale
record. State 10 translates the coordinate from tick 201 before the trigger
ratio is computed. Boundary fixtures check that ordering directly.

Bear issues command 18 on frames 0 and 15 and starts randomized local-X motion
and yaw changes at tick 321. Rabbit issues command 3 on frames 7 and 22; its
unsigned tick windows select forward motion, yaw changes, then randomized
flagged local-X motion. That flagged path dispatches **event 7** through the
original scene-node and base-event routines. It does not dispatch event 8.

Acrobats issue command 13 every 30 timer units. Ship uses its original signed
300-unit remainder, issues commands 5/-2 during its first 20 nonnegative phases,
issues the stop command at phase 22, and moves forward by -10. Every nonnegative
phase of both periods and additional signed boundaries is represented.

## Execution and comparison

Original MIPS instructions execute in the pinned Unicorn 2.1.4 backend.
Original spatial helpers call `RotMatrix` and `ApplyMatrixLV`; reviewed COP2
transfers connect to the pinned Nymashock implementation through the
[native GTE bridge](RENDER_GTE.md). An independent integer model checks every
ordered command result. The run checks 7,262 positive GTE commands plus four
commands from fault controls. One separate bridge startup identity check is
excluded from those 7,266 commands.

Every fixture compares complete entity, dream, command, coordinate, pose,
player-coordinate, parent-root and linked-child buffers, together with the RNG
word and motion scratch: 3,508 bytes of buffers and value fields. Ordered RNG,
GTE and event observations are compared separately. Return completion, stack
and global-pointer restoration, saved registers and stack red zones are checked.

The seven fault controls target all four command destinations, the distance
routine's Z field, the trigger routine's property byte and the flagged movement
event call. Changes exist only in the control's private emulator memory. Each
control executes its modified instruction once and fails the comparison.

An independent retained audit reconstructs all 10,408 distinct generated
inputs, rehashes the original ranges and proof dependencies, verifies every
fault word and execution count, and checks all 7,266 logged GTE exchanges.
[npc-proximity-checks.json](npc-proximity-checks.json) pins the report, audit,
public producer, tests, original ranges, backend and runtime identities.

## Reproduce

Use a current matching build, the optional analysis dependencies and a fresh
bridge built with `tools/build_nymashock_gte_bridge.ps1` as described in
[RENDER_GTE.md](RENDER_GTE.md). The verified local runtime was installed at the
Windows path used below; set that argument to your own pinned BizHawk runtime.

```bash
python tools/verify_npc_proximity.py \
  --output .decomp-lab/npc-proximity-new \
  --bridge .decomp-lab/my-gte-bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'
```

Run from the repository in WSL and use forward slashes for the Windows runtime
argument. The evidence directory must be new and inside `.decomp-lab`. Source,
build, backend and bridge identities must remain unchanged during execution.
Six semantic/domain guards accompany the native profile. All 383 developer
tests pass locally on Windows and Linux; those tests are separate from the
native fixture count.

## Remaining acceptance work

These are valid, manually constructed meshless actor graphs with no collider
and no actor children. The original event routines execute, but their geometry
branches are inactive. Natural actor construction and encounters, persistent
histories, active geometry/collision, animation, rendering, audio and original
PS1 scheduling/timing still need reviewed comparisons.

The canonical game and original NPC behavior are unchanged. C recovery stays
at 194,212 / 199,912 bytes (97.15%), with nine assembly functions and 24 inherited
unused-storage explanations. The catalogue retains 40 provisional groups,
35 groups with every listed core function in C and zero whole-group acceptances.
Ten developer capabilities and three optional mods retain their separate
counts. This analysis makes no model API calls and adds no generative AI to the
original game.
