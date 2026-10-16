# Original effect lifecycle and callback types

The effect's frame callback takes the effect, its attachment target and a
notification code. Expiration takes the effect and that same target pointer.
The C header now names and types both original virtual slots:

| Table offset | Callback | Arguments |
| --- | --- | --- |
| `0x98` | `effect_tick` | `effect_t *, base_class_t *, s32` |
| `0xE0` | `effect_deactivate` | `effect_t *, base_class_t *` |

Both return `void`. The frame callback uses the typed expiration slot directly.
The configured MIPS compiler checks the `0xA0` effect size, `0xF4` table size,
both offsets and compatibility with the public function prototypes. Deliberately
restoring a one-argument frame callback or an integer expiration target fails
compilation with warnings treated as errors.

## Native behavior checked

The bounded lifecycle comparison executes original instructions without
substituting any function outputs. An independent object-state model and the
existing interval/free-queue heap model predict complete buffers after every
host-issued call. Selected native call arguments and event order are compared
as well as memory, return state, stack guards, `gp` and saved registers.

| Profile | Constructed histories |
| --- | ---: |
| Owner-bound expiration, restart and detached destruction | 480 |
| Frame-phase lists containing one, two or three effects | 288 |
| Total | 768 |
| Host-issued calls | 33,192 |
| Qualified original function ranges | 79 |
| Original routines actually entered | 77 |
| External function-output contracts | 0 |
| Executed behavior faults detected | 4 |

Earlier construction checks cover 471 separate fixtures: real effect allocation,
transform buffers, reciprocal attachment lists, repeated binding, positive-life
color updates, detached destruction and bounded allocation failures. Their
65 entered routines and three instruction faults are recorded separately from
the lifecycle campaign. These are developer fixtures, not natural encounters.

The host supplies a bounded pool, source dimensions, offset values and an SDK
matrix template. Owner-bound fixtures use a partial entity with an actual
transform constructor and a real frame-phase object. Scheduler fixtures contain
effect parents only. Neither profile constructs a complete actor or stage.

## Expiration and notification

The frame-phase dispatcher sends code `2` when active, `3` while waiting and
`4` when finished. Only code `2` changes effect life or color. These codes are
distinct from the frame-phase object's incrementing phase counter.

With a positive previous life, the callback decrements life and changes the
selected RGB bytes, except in mode `9`. With a previous life of zero or less,
it decrements life and invokes expiration. Expiration removes the target from
the effect's child list and removes the reciprocal parent-list entry. It then
restores a negative color step, clears the active state and notifies the owner
with code `5` or `6`, according to the previous start mode.

Linked-effect fixtures also check lifetime division, the attached start's
additional decrement and its retained initial color. Expiration preserves the
original mode-dependent flag and color behavior. These fixtures supply linked
parameters explicitly; they do not establish their natural configuration path.

The original effect type word is `0x164`. Owner notification reaches the actor,
transform and scene-node handlers. The scene-node handler's kind byte is `0x64`,
which selects neither its `0x34` nor its `0x24` branch. This dependency executes
in the comparison even though the owner's object bytes remain unchanged.

Frame-phase histories exercise waiting, finished and active notifications,
different parent-list orders, phase-word wraparound and removal during virtual
notification. After every effect expires, a further advance must enter no
effect callback. Explicit destruction then checks the original allocator's
releases and coalescing against the complete pool, including obsolete bytes.

Four private instruction changes test sensitivity to the zero-life boundary,
waiting-mode selection, state clearing and owner notification code. Each changed
instruction executes and returns normally with an ABI check before a mismatch
is accepted. The notification-code fault changes only the checked event trace;
object-buffer equality alone would miss it.

## Evidence and remaining scope

[effect-lifecycle-checks.json](effect-lifecycle-checks.json) publishes source and
original-range identities, callback bindings, compiler checks, build results,
native counts, fault sensitivity and explicit scope. Native harness snapshots,
complete buffers, linked executable/assembly and failed diagnostic runs remain
in private local evidence as described in [provenance](PROVENANCE.md).

The native campaigns ran before the declaration edits. Their original instruction
ranges are identical to the resulting game: both the ordinary build and a fresh
306-object rebuild equal the complete canonical 505,856-byte executable. Two
game inputs change, while the other 390 retain their previous hashes. The
dispatch inventory retains the original callback addresses and table sizes.

This establishes bounded construction and lifecycle behavior. Owner-bound cases
invoke the effect callback directly; the scheduler cases exercise the original
frame-phase dispatcher with effects only. Natural NPC construction, complete
engine frames, linked-parameter provenance, rendering, audio and PS1 timing
remain open. The existing [Gunman script profile](GUNMAN_SCRIPTS.md) retains its
own contracts; this supplement does not silently expand that older report.

Matching C stays **194,212 / 199,912 bytes (97.15%)**. Nine assembly functions,
24 inherited storage explanations and the full parity requirements remain
unfinished. Bounded NPC callback coverage stays **36 / 107**, and whole-feature
and whole-encounter acceptance remain zero. The 40 provisional feature groups,
ten developer capability categories and three optional mods do not increase.
No model API is invoked, original gameplay is unchanged and the Bevy port
remains separate.
