# Original locomotive script checks

The original Factory, Kyoto and Natural locomotive callbacks pass **70,345
distinct bounded fixtures**. Fourteen scheduled histories retain buffers and
RNG across another **192 script invocations**. Bounded callback coverage rises
from **36 to 39 of 107**; all three callbacks already had matching C bodies.

| Callback | Original property index | Standalone fixtures |
| --- | ---: | ---: |
| `entity_locomotive_factory` | 41 | 66,012 |
| `entity_locomotive_kyoto` | 49 | 3,182 |
| `entity_locomotive_natural` | 111 | 1,151 |

These are checks of existing original behavior. Matching C remains **196,504 /
199,912 bytes (98.30%)**, with four game assembly fallbacks and two inherited
storage explanations. The 40 provisional feature groups, 37 listed-core C
groups, ten developer capability categories and three optional mods retain
their separate counts. **No whole encounter or feature group is accepted.**

## Factory and shared movement

At tick zero, Factory draws once and selects state ten through fourteen. It
uses the common movement script when state is below fourteen or tick is below
320. State fourteen at tick 320 or later instead draws and requests scaling
every fourth tick; higher states have no operation in that branch.

The scale argument starts twelve bytes into `g_EntityOffsetScratch`, a
22-byte array. The randomized halfword belongs to the separate two-byte
`g_EntityOffsetScratchDenom` immediately after it. The check compares the
entire array and denominator separately, and records all twelve bytes passed
to the scale contract. A deliberate store into the array is detected even
though it stays inside mapped memory.

The native RNG runs for one initial seed producing each possible first
15-bit result at both draw sites. Deduplication leaves 32,762 scale fixtures
in that group's report because six identical initialized inputs already
appear in the denominator group; all 32,768 results are covered. This does
not enumerate every 32-bit seed, paired draws or natural encounter history.

The common script clears command slot four, handles the original context
mode six, and requests turns in three inclusive tick windows. Factory's
windows start at 3000, 3341 and 3698. It requests forward movement at -256;
tick 500 disables links/behavior and sets state one when the common path is
selected. Natural's common path uses different windows and completion ticks.

## Kyoto action and link sequence

A triggered state-zero callback sets state ten and tick zero, then requests
forward motion. It does not run the action branch in that same invocation.
State ten checks the full action word at every tick **except exactly ten**.
A nonzero action requests the link pose and quarter-turn, clears the player's
movement callback, and sets state eleven and tick zero. At exactly tick ten
it sends link notification ten instead.

The link-pose argument is the original transform pointer plus `0x38` when
the entity's full active word is nonzero, and null otherwise. State eleven
requests that pose on every invocation and notifies at exactly tick 100.
Forward motion at -256 follows every Kyoto path, including untriggered paths.

All four initial movement-callback modes are checked. The native clear call
uses argument zero, so it preserves the view callback. Initial movement mode
two additionally executes the original view-mode reset. Geometry requests
and notifications are checked as calls; they do not execute a world link.

## Natural pause and original mood calculation

At tick zero, the original mood-average, chart-combination and color lookup
routines execute. The check observes both returned mood averages and the
returned color. Pink selects state eleven; other colors preserve the prior
state. Signed byte thresholds, division toward zero, zero-count fallback,
contribution combination and wrapped native addition have separate fixtures.

Every nonzero state takes the pause branch from tick 2160. Exactly 2160 stops
animation and writes the three stop commands. Ticks 2550 through 2559 request
the later pose; exactly 2560 resumes animation and changes context mode to
one. Ticks 2561 and 2562 do not request movement. The common path resumes at
2563, with vertical movement from 2801 and link-disable completion at 4000.
State zero follows the earlier common path, whose completion at 2180 changes
the next invocation's branch. Scheduled histories preserve this transition.

## Execution boundary and reproducibility

A symbol-retaining diagnostic link reproduces the complete canonical
505,856-byte executable. Sized ELF spans qualify 21 original functions, and
all 21 execute in the positive campaign. The profile uses the original
virtual-table and property-table bindings. Native code includes the scripts,
shared movement decisions, RNG, empty-child link-disable chain, animation
flags, player action/callback methods and full mood-to-color chain.

Seven explicit contracts cover rotation, scale, forward/vertical motion,
link pose, notification and sound. Link-disable fixtures have no child nodes.
Complete entity, dream, command, transform and five data buffers, RNG state,
ordered calls/arguments, returned mood values, return, GP, saved registers
and stack guards agree with the independent model. Store spans are decoded
from integer instructions; delay slots are checked before the branch. The
profile uses no memory-write hook.

Twenty-one separate instruction faults execute and change checked results.
Two further bounds controls are rejected before their escaped stores execute,
including a branch delay slot. They are counted separately from completed
behavior faults. All changes exist only in private emulation memory.

With a current matching build and the optional WSL analysis dependencies:

```bash
python -m tools.verify_locomotive_scripts \
  --output .decomp-lab/locomotive-native-new
```

Choose a fresh output directory. `--smoke` omits the two exhaustive RNG
domains and does not reproduce the published campaign. The 27 regression
tests need no original game files or optional native backend:

```bash
python -m unittest tests.test_locomotive_scripts -v
```

[locomotive-script-checks.json](locomotive-script-checks.json) records source,
range, data, property table, backend, build, input/output and fault identities.
Original images, diagnostic ELF files and complete fixture buffers stay private.
Histories explicitly inject tick/action inputs between script invocations;
they do not step complete engine frames. Natural construction, populated child
graphs, geometry/collision, visible motion, linked scene transitions, rendering,
sound, controller reachability and PS1 timing still require comparison.

Original NPC behavior and this analysis tool remain separate. The tool invokes
no model API, changes no original behavior and does not modify the Bevy port.
