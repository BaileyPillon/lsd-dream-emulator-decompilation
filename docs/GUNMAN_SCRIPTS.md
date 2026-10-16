# Original Gunman state and effect checks

The original Gunman and Gunman Victim callbacks pass **36,338 distinct bounded
fixtures**. Fifteen scheduled histories retain buffers and RNG across another
126 callback invocations. This raises bounded callback coverage from **34 to
36 of 107**; both callbacks already have matching C bodies.

| Callback | Original property index | Standalone fixtures |
| --- | ---: | ---: |
| `entity_gunman` | 85 | 34,847 |
| `entity_gunman_victim` | 86 | 1,491 |

## Recovered script decisions

Gunman's initial state requests the shared aim-pose commands at animation
frame five. Tick equality with its duration stops animation and sets state
10 with tick -1. It returns immediately, without entering the next state's
action check in that invocation.

State 10 checks the full action-pressed word only while tick is less than ten.
A nonzero word requests aim commands and state 12; zero preserves the state.
At tick ten or later it clears the player's movement/view callbacks and enters
state 11, regardless of the action word. All four initialized move modes are
checked, including mode two's original view-mode reset.

State 11 requests orientation and forward motion before tick 30. At 30 or
later it requests aim commands and the fast color effect, then enters state
13 even if effect construction fails. State 13 requests the normal attached
effect at exactly tick 30. Before tick 90 it requests the roll update; at 90
or later it requests the shared fall commands and half-turn, draws once, and
sends notification 12 for a result divisible by five or 10 otherwise. It then
sets state 14. State 12 requests its turn before tick ten, then fall commands,
behavior stop and state one. Geometry requests are checked as calls; their
visible movement is outside this profile.

Gunman Victim stops animation before tick ten and resumes it at exactly ten.
Animation frame ten requests fall commands independently. Tick equality with
duration plus ten stops behavior and sets state one. Signed word boundaries,
including the original wrapped addition, are arithmetic diagnostics rather
than claims about naturally reachable animation durations.

The RNG group supplies one initial state for every possible first 15-bit
result. It verifies the native LCG update, result-dependent notification and
draw order. It does not enumerate all 32-bit seeds or joint encounter histories.

## Actual native effects and declared boundaries

A symbol-retaining link of the current 306 objects reproduces the complete
canonical 505,856-byte executable. Sized ELF spans qualify 26 original routines;
all 26 are entered by the positive campaign. Actual code includes both scripts,
pose helpers, animation/model flags, callback clearing, action reads, RNG,
`entity_create_effect`, color-step/activation methods, RGB copying and bit updates.

The fast activation's step is 30 and its computed life counter is eight; the
attached activation's step is ten and its computed life is 25. Tests check
signed mask division, color channels, lower flag bits, RGB bytes and preserved
alpha. Existing active effects follow the original skip behavior. Effect
ticking is not executed, so these values do not establish rendered fade timing.

Eight explicit contracts cover orientation, rotation, forward motion,
notification, sound, effect construction, effect binding and attachment.
In particular, **`effect_create` allocation and construction are contracted**
to return null or an initialized fixture. Its caller `entity_create_effect`
executes natively, including pointer installation and the color-step call.
Attachment contracts make no graph changes; the native detach helper is checked
only with an empty parent link. The original parent argument at entity offset
`0x50` is preserved as an opaque attachment target.

Five complete buffers, RNG state, ordered calls/arguments, return, GP, saved
registers and stack guards agree with the separate model. Integer-store spans
are checked by instruction decoding, including delay slots before their branch.
On this pinned local backend, a memory-write hook changed return behavior on the
first Gunman path in both new and preceding harnesses; those failed diagnostics
remain private. The final check uses no memory-write hook.

Eleven separate instruction faults execute and change checked results. A
twelfth, distinct bounds control is rejected before its out-of-profile store
executes; it is not counted as a completed behavior fault. Histories inject
tick, animation-frame and action inputs between script calls. They retain the
objects but do not simulate complete engine frames or the effect update loop.

## Reproduce and remaining gates

With a current matching build and the optional WSL analysis dependencies:

```bash
python -m tools.verify_gunman_scripts \
  --output .decomp-lab/gunman-native-new
```

Choose a fresh directory. The tool validates the output before reading game
inputs, pins its dependencies and backend, preserves failed evidence, and
rechecks the complete build afterwards. The eleven synthetic unit tests need
no original game files; their count is separate from native execution.

[gunman-script-checks.json](gunman-script-checks.json) records range, source,
table, backend, build, input and output identities. Raw executable/ELF data,
buffers and faulted instructions remain private.

Natural spawning, populated attachments, linked-effect mode, actual geometry,
effect lifetimes/rendering, sound, controller reachability and PS1 timing still
require comparison. **No whole encounter or feature group is accepted.** C
remains 194,212 / 199,912 bytes (97.15%), with nine assembly functions, 24
inherited storage explanations and 35 / 40 listed-core C groups. The 40-group
inventory, ten developer capability categories and three optional mods remain
unchanged. Original NPC behavior and this analysis tool remain separate; the
tool invokes no model API, and the Bevy port is unchanged.
