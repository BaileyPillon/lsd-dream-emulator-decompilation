# Boatman lifecycle and Fish initialization

The compact original-engine trace distinguishes Boatman's observed stop path
from its interaction timer. It also records initialization calls that precede
the four Fish/Giant Fish instances in this controller route. Matching game
code and property bytes remain unchanged.

## Boatman's two clocks and stop path

The original property record stores interaction type `120`, so
`entity_check_interaction_range` can disable the link when its interaction
timer equals `120 * 15 = 1,800`. That rule does not describe this observed
stop. The registered behavior clock and interaction timer are separate words.

| Relative input step | Rooted Boatman context | Interaction timer | Context tick |
| --- | --- | ---: | ---: |
| 4,576 | Disabled | 116 | Uninterpreted |
| 4,577 | Enabled | 117 | 1 |
| 5,069 | Enabled | 203 | 87 |
| 5,073 | Enabled | 203 | 87 |
| 5,074 | No longer reachable | Uninterpreted | Uninterpreted |

The first original callback occurs at step 4,577, following
`entity_start_behaviour` from `entity_check_link_trigger`. The 87 callback
entries have consecutive clocks 0 through 86; the last occurs at 5,069.
At 5,074, the trace records this original path:

```text
entity_stop -> entity_disable_link -> entity_stop_behaviour
```

The disable call's saved return address identifies the original indirect call
at `0x8005D448` inside `entity_stop`. The following stop call identifies
`0x8005DA74` inside `entity_disable_link`. Both enter with an enabled,
correctly bound Boatman context at tick 87. The preceding complete checkpoint
is still reachable at 5,073; the following checkpoint is not reachable at
5,074. Former object storage is left uninterpreted.

The dream's map selector changes from 2 to 3 in the retained route. This
records selection and rooted reachability; it does not establish the exact
heap-free instant or which frame first displays the destination.

## Initialization calls and active contexts

At step 5,431, each of the three Fish owners and the Giant Fish owner records:

```text
entity_init  -> entity_disable_link -> entity_stop_behaviour
entity_start -> entity_enable_link
entity_start -> entity_start_behaviour
```

These entries have context state zero. Their payload does not supply a valid
callback clock, owner or function binding. Initialization stop calls therefore
do not establish earlier active encounters. The constructor clears context
state, and the matching `sound_entity_update` executes callbacks only when the
signed state is positive. The entry qualifier applies that signed test,
including the high-bit/nonpositive boundary.

All four instances begin registered callback execution at step 5,432. Each
has 595 consecutive observed clocks, 0 through 594, ending at step 8,996.
Later rooted checkpoints corroborate their enabled bindings and accumulated
clocks. A stop method's other downstream effects still require separate
evidence; disabled payload is never interpreted as live state.

## Compared outputs and source evidence

Three fresh cold runs use the existing
[Boatman controller route](../research/headless/boatman-approach-route.json):
original/observer, rebuilt/observer and original/distributed. Each matches the
retained reference on 9,001 complete GPU/frame observations, 1,614 complete
RAM hashes, all 205 selected complete RAM/GPU/RGB checkpoints and the complete
26,537,652-byte PCM stream. Original/rebuilt entry logs agree byte for byte.

The observer logs 15,697 entries: 13,230 engine-method entries and 2,467
registered callback entries. The new qualifier checks 10,217 engine entries
for the five observed callback instances. Other engine owners do not acquire
clock or encounter acceptance from this analysis.

The [caller catalogue](../research/headless/entity-lifecycle-callers.json)
adds metadata for four complete original functions: `entity_init`,
`entity_start`, `entity_stop` and `entity_update`. GNU `nm -S` independently
supplies their sizes and relative positions; all eight previously reviewed
engine methods agree on the translation-unit base. Complete original code
spans and saved-return call instructions are checked. No additional PC targets
or callback functions are claimed.

The read-only [entry qualifier](../tools/npc_engine_entries.py) takes parsed
native rows, byte-checked method ranges and the verified NPC catalogue.
It checks original entry/call instructions and enabled owner/ID/callback
bindings. Disabled payload returns no clock or binding. Caller names outside
the reviewed ranges remain unknown. Its output represents individual engine
entries; whole recording comparison, ordering and rooted RAM checks remain
separate requirements.

Ten source-only tests use owned PS-X fixtures for full-span identities,
signed disabled states, stale payload, mismatched enabled bindings, changed
instructions, unsupported/direct calls, malformed rows and overlapping or
unknown caller ranges. Four altered copies of actual native entries are also
rejected for inconsistent owner, callback, state and entry instruction. These
controls do not modify game RAM or the retained reference.

## Reproduce and scope

Reuse an already verified Boatman reference and the qualified catalogue
runtime/profile with the [compact recorder](NPC_LIFETIME.md#compact-recording):

```powershell
python tools/record_npc_activation.py `
  --reference D:/QA/verified-boatman-original `
  --runtime D:/QA/catalogue-runtime/host `
  --observer-profile .decomp-lab/catalogue-observer/profile.json `
  --workspace D:/QA/boatman-engine-original
```

Use a new workspace and `--cue` for a rebuilt disc with identical complete
track bytes and layout. Use the qualified distributed runtime and `--stock`
for the output control. Existing library directories are shared. Passing runs
save entry logs, hashes and reports, with no duplicate raw RAM/GPU/RGB/PNG/PCM.
The [evidence metadata](boatman-lifecycle-checks.json) records the source pins
and measured comparison boundaries. Proprietary input data remains private.

This adds zero C bytes and zero original gameplay features. Matching C remains
197,172 / 199,912 bytes (98.63%), with two assembly functions and three known
inherited storage explanations. Bounded callback profiles remain 41 / 107;
compared natural callback types remain five. The inventory stays at 40
provisional groups and 38 listed-core C groups. Accepted whole NPC encounters
and feature groups remain zero.

Further routes, seeds, branches, audiovisual causality, complete emulator state
and original hardware timing remain open. This is developer analysis of
original NPC AI, separate from gameplay mods and AI-assisted tools. No model
service is called. The playable matching build and Bevy repository remain
unchanged.
