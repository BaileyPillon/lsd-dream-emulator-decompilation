# Original actor animation playback

The [playback checker](../tools/verify_actor_playback.py) executes the original
actor tick after real model and actor construction. It compares the complete
live object graph after selection, animation enable/pause/resume and each tick,
then completes the original destruction history. This extends the
[immediate-frame selector profile](ACTOR_ANIMATIONS.md).

Animation interpretation and tick behavior are original game code. The
[state predictor](../tools/actor_playback_model.py) and checker are separate
host analysis tools. They do not change the matching game, enable NPC
callbacks or call a model API.

## Original behavior under comparison

The original selector applies frame zero immediately and leaves its cursor at
that frame. The first active tick applies it again. For animations with two or
more frames, each active tick advances the cursor and increments the frame
counter. Processing the last frame resets the counter and cursor; the next
tick interprets frame zero. No extra frame is applied inside the wrap itself.

A one-frame animation is applied by selection, then held by active ticks.
Disabling the animation playing flag holds its counter and cursor. Actor ticks
still increment the separate age word at offset `0x24` and clear the root
coordinate's dirty flag. Resuming continues from the retained frame. These
are actor-method semantics; complete engine pause and scheduling are outside
this profile.

The original constructor leaves the actor callback disabled. The predictor
rejects enabled callbacks rather than replacing their outputs. The playback
flag changes through the original enable and disable methods. The native
checker never injects a frame counter or cursor.

## Corpus and histories

The supplied Japanese-labelled extraction contains 111 valid MOM instances,
100 distinct model contents, 122 animation instances and 4,260 script frames.
There are 4,076 distinct-content/frame-index combinations. These counts describe
data, not features. Duplicated model contents retain their original resource
and model-offset identities.

Every valid animation runs through one complete active cycle and the following
tick. After its first active tick, the checker disables animation for two actor
ticks and then resumes it. Both memory patterns run through three ownership
histories:

- An actor owns its model.
- Two successive actors borrow one retained model, exercising cleanup and reuse.
- Model-first notification destroys a borrowed actor.

The predictor freezes all expected snapshots before starting each native
history. It uses original MOM bytes, qualified original defaults and its own
allocator/object state. Native observations are never inputs to expected state.
The interpreter's full-word parent sentinels retain the
[recorded correction](actor-parent-word-checks.json).

Every action compares all live allocation capacities, including untouched
residue, complete mapped MOM bytes and the allocation manager. The observer
also checks the original frame interpreter's arguments and entry count.
Original allocator events, constructor snapshots, saved registers, stack/input
guards and complete release continue through destruction.

The ready CD-driver state, bounded pool, SDK identity matrix and zero auxiliary
constructor argument remain supplied fixture inputs. Calls execute inside
[136 qualified original function ranges](actor-playback-function-ranges.json),
bound to a symbol diagnostic whose complete binary equals the canonical
executable. No dependency-output stubs are used.

[Campaign metadata](actor-playback-checks.json) records measured results,
source/backend identities and a separate raw-layout and retained-record audit.
That audit derives tick, cursor, age, playing-state and frame-entry schedules
without importing the playback predictor or its action generator.

| Measure | Japanese-labelled extraction |
| --- | ---: |
| Complete ownership histories | 666 |
| Actor lifetimes | 888 |
| Explicit actor-method calls | 41,888 |
| Original actor tick calls | 37,008 |
| Complete live-allocation comparisons | 3,505,120 |
| Allocated payload bytes compared | 161,246,016 |
| Complete mapped MOM bytes compared | 429,618,528 |
| Completed wrong-payload histories | 24 |

The published selector profile covered 122 immediate-frame instances. The
separate two-model tick probe covered 41 frames, including three of those
immediate frames. Their union was 160 original frame instances. This campaign
extends that union to 4,260, adding 4,100 frame instances. These are bounded
data comparisons, not 4,100 new features or a whole-game parity percentage.

## Wrong-output controls

Four controls alter executed instructions to increment the frame counter by
two, hold a multi-frame animation, advance while animation is paused, or omit
the root dirty-flag clear. Each runs under both memory patterns and all three
ownership histories.

Construction and non-tick methods retain original instructions. Faults are
armed only around the explicit tick calls, with translated code invalidated
after each patch and restoration. Every qualified control must execute its
changed instruction, finish the native ownership history and expose a wrong
payload. A crash, timeout, unexecuted patch or entry-count difference alone
does not qualify. Only private VM memory is changed.

## Reproduce

Use Linux/WSL, a current matching build and your own dumpsxiso extraction.
Prepare an isolated environment for the allocator harness:

```bash
python3 -m venv .decomp-lab/actor-playback-venv
.decomp-lab/actor-playback-venv/bin/python -m pip install \
  -r requirements.txt -r requirements-card-heap.txt
.decomp-lab/actor-playback-venv/bin/python -m tools.verify_actor_playback \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/actor-playback-new \
  --edition-label your-extraction-label
```

The output must be a fresh directory inside `.decomp-lab`. Existing evidence is
preserved. Unicorn 2.1.2 is required; the newer analysis backend is not qualified
for this allocator harness. The edition label records supplied provenance and
does not detect the edition. Diagnostic images, raw assets and reports remain
private.

Synthetic tests require neither game media nor Unicorn:

```bash
python -m unittest discover -s tests -p 'test_actor_playback.py' -v
```

## Remaining gates

This profile covers script interpretation and retained actor state under
explicit calls. Enabled callbacks, natural resource loading and NPC encounters,
full engine scheduling, geometry/coordinate cache composition, rendered frames,
audio, allocation failures and PlayStation timing still require comparison.

Matching C remains 197,172 / 199,912 game-function bytes (98.63%). Two assembly
functions and two inherited unused-storage explanations remain open. The
inventory retains 40 provisional feature groups, 38 listed-core C groups,
40 bounded NPC callback profiles and zero accepted whole feature groups or
encounters. This extends an existing analysis capability; it adds no optional
gameplay mod or new original feature. The Bevy/Rust port remains separate.
