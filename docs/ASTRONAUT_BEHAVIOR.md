# Original Astronaut behavior

The original `entity_astronaut` callback now has a bounded native profile for
its mood, proximity, timer, movement and animation-stop behavior. All **21**
declared original functions execute in the positive campaign. Spatial requests
run through the original transform helpers, `RotMatrix`, `ApplyMatrixLV` and
the pinned native GTE bridge, with **zero dependency-output stubs**.

| Evidence | Verified count |
| --- | ---: |
| Distinct initialized standalone fixtures | 2,748 |
| Scheduled script histories | 2 |
| Script invocations within those histories | 17 |
| Additional independent, hand-predicted inputs | 14 |
| Complete original functions qualified and entered | 21 |
| Positive native GTE commands, including histories | 2,790 |
| Completed instruction faults detected after execution | 7 |
| Escaped stores rejected before execution | 1 |

This adds one bounded original callback profile: **39 → 40 / 107**. The callback
already has matching C, so matching game C remains **197,172 / 199,912 bytes
(98.63%)**. Whole NPC encounters and whole feature groups remain unaccepted.
The 40 provisional feature groups and 40 profiled callbacks are different
denominators. The separate Bevy/Rust port is unchanged.

## Recovered script decisions

The callback reads the original dream color only when **the command timer
(`context[1]`) is zero**. This is not a test of the entity tick. Pink changes the entity state
to 100 before the remaining decisions in that same invocation. The original
mood averaging, contribution combination and color-table lookup execute;
signed bytes, signed sums, zero-count fallback and native word boundaries
have separate fixtures.

Trigger ratio is then calculated through the original property, distance and
position methods and written to command slot four. It is measured before
movement. Radius-boundary cases check this ordering, including a move that
crosses from outside the radius to inside it.

| State | Entity tick | Observed decision |
| --- | --- | --- |
| Zero | Below 1200 | Request forward motion at +50 |
| Zero | 1200 or later, except exactly 2400 | Request forward motion at -50 |
| Zero | Exactly 2400 | Write tick -1 and return without movement |
| Nonzero | Below 100 | Request forward motion at +50 |
| Nonzero | 100–249 | Add the original unrotated vector `(0, 64, -64)` |
| Nonzero | Exactly 250 | Stop animation and write -2 to command slot seven |
| Nonzero | 251–260 | Preserve position and orientation |
| Nonzero | 261–567 | Move backward, then set the original absolute yaw |
| Nonzero | Exactly 568 | Preserve position and orientation |
| Nonzero | 569 or later | Set the original absolute pitch/yaw/roll |

In state zero, command timer multiples of ten write 5 and -2 to slots seven
and eight. Nonzero states make these periodic writes only below tick 250.
Negative signed timer multiples are included. A nonzero state is not limited
to the value 100 in these constructed fixtures.

The later orientations use the original fractional degree records and native
fixed-point conversion. They replace the angles rather than accumulating
another turn. Movement from 261 through 567 uses the prior pose before that
invocation's rotation. The scheduled pink-state history checks this ordering
across consecutive calls.

## Comparison method

The Python oracle predicts complete entity, dream, command, coordinate, pose,
player-coordinate, root and retained inert-child buffers before native execution.
It also predicts ordered calls and arguments, mood/ratio returns, native GTE
requests and results, the unchanged RNG seed and final movement scratch bytes.
Saved registers, GP, return, stack restoration and stack guards are checked.

Movement's inner coordinate-update call receives a temporary vector on the
native stack. The observer checks its payload and guarded stack role; it does
not claim that an internal stack address is portable across runs. The original
direct-translation and rotation data pointers are checked against their bound
objects. No state bytes are removed from the compared object buffers.

Seven private instruction faults change command placement, motion thresholds,
the late movement window, exit orientation, animation-stop storage or the GTE
shift. Every changed instruction executes and changes a checked output. The
separate escaped-store control is rejected before its destination changes;
it is not counted as a completed behavior fault. Integer and `SWC2` store spans
are checked, including branch delay slots before their branch executes.

The independent audit checks every complete sized ELF span against the
canonical executable. It then predicts 14 additional identity-pose cases with
explicit position, angle, animation and command values, without calling the
producer's expected-output function. These are distinct initialized inputs,
not another run of the same standalone corpus.

## Reproduce

Use the configured WSL build environment, optional analysis dependencies and
a local bridge built as described in [RENDER_GTE.md](RENDER_GTE.md):

```bash
python -m tools.verify_astronaut \
  --output .decomp-lab/astronaut-new \
  --bridge .decomp-lab/my-gte-bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'
```

Use your pinned runtime location and a fresh private output directory. The
tool requires a current canonical build and checks source/build/backend
identities afterwards. [Metadata](astronaut-checks.json) records original
function/data/property identities, producer dependencies, the native bridge,
runtime files observed at publication and both retained private report hashes.
No original images, emulator states or extracted assets are published.

Dependency hashes identify the executed working copy. Some inherited helpers
use CRLF locally; their LF Git blob hashes are recorded separately. The new
profile and range file match Git bytes exactly. Executable comparisons retain
every original byte.

The 21 regression tests use owned fixtures and require no original game or
optional native backend:

```bash
python -m unittest tests.test_astronaut -v
```

## Remaining scope

The fixtures have meshless transforms and no collision/link target. The
histories preserve buffers between callbacks while explicitly injecting tick
and command-timer values; they do not step complete engine frames. Natural
construction, encounters, populated collision/child graphs, complete animation
playback, rendering, audio, controller reachability and original PS1 timing
remain open. Function entry counts are not exhaustive branch coverage.

Apartment Bear's animation-switch and model fixture remain separate work and
are not counted by this profile. The two remaining collision C recoveries and
two inherited storage explanations also remain required. This developer tool
makes no model API calls, changes no original NPC behavior and adds no mod.
