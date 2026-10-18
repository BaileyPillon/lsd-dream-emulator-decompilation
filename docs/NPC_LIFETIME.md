# Recorded NPC activation and shutdown

The offline [lifetime inspector](../tools/inspect_npc_lifetime.py) distinguishes
an enabled NPC context, a disabled entity still attached to the scene, and
storage that is no longer reachable from the current game owners. It reads
verified recordings; it does not control an emulator, inject game RAM or call
a model service. Original NPC AI and this optional analysis tool remain separate.

## Observed Buddha history

Two new controller-only cold boots repeat the
[qualified instruction-entry history](NPC_ENTRY_TRACE.md), using the original
and matching rebuilt Japanese discs with the same separate observer core.
The [new checkpoint program](../research/headless/buddha-lifetime-route.json)
adds 33 complete checkpoints. Its expanded controller TSV is unchanged:
SHA-256 `c33fdd031c9a04809c1093067d7d197adf0270d8baa6c6f737c7c7504b23672b`.
This is the same route and seed history, with closer observations.

Both recordings show the original Buddha instance at `0x801CF954`, table
ID 20, with callback `0x8005EFF4`:

| Checked boundary | Observation in both recordings |
| --- | --- |
| 5,406 → 5,407 | Disabled context becomes enabled; first original callback entry has tick zero. The post-step context tick is one. |
| 22,574 | Last callback entry, tick 2,699; post-step context remains enabled with tick 2,700. |
| 22,579 → 22,580 | Context becomes disabled and the behavior-active flag clears. The entity remains reachable. |
| 24,600; 24,664 | Entity is still reachable at the first checkpoint and absent from the followed graph at the second. The unlinking boundary lies within that interval. |

These frame labels count individual core advances from this recording's cold
boot. They do not establish wall-clock or original-hardware timing. The last
callback entry and context shutdown are six advances apart in this history.

The inspector follows the original game-flow global at `0x8008AC20` and its
dream member. It validates reachable vtable prefixes against the executable,
reciprocal child/parent links, the complete original entity property table,
entity ownership and enabled-context binding and clock. It inspects 130
selected snapshots per run after the observer's arm boundary. It never treats
an old callback-shaped word in disabled or unreachable storage as a live context.
Clock corroboration in this inspector requires graph reachability first; the
shared recording validator still requires at least one corroborating original
context. Enabled state is checked against the recorded entity ID plus one,
rather than a Buddha-specific state value.

## Comparison evidence

The strict, same-runtime original/rebuilt comparison passes:

- 30,001 native frame/GPU observations and 5,033 complete-RAM hash samples per run.
- 158 selected complete RAM/GPU/raw RGB checkpoints per run.
- 88,457,172 bytes of complete stereo PCM per run, identical between runs.
- 2,700 original instruction entries per run, with identical complete logs.
- All 130 inspected lifecycle snapshots and their transition windows agree.

A separate audit checks the unchanged controller history, all frame observations,
5,003 shared RAM samples, all 125 earlier raw checkpoints and complete PCM
against the retained earlier observer recording. It independently decodes all
316 new PNGs with Pillow; every decoded image equals its raw RGB buffer. The
public recording comparer checks PNG containers and raw RGB, rather than
decoding PNG pixels itself.

Eight altered copies of native RAM are rejected: invalid flow pointer, wrong
flow type, wrong dream member, missing reciprocal parent, invalid entity ID,
wrong enabled-context ID, wrong context owner and changed original property.
Two further in-memory controls change disabled payload and unreachable former
storage; both preserve the inspection result. Original captures are untouched.
Seventeen source-only tests use owned synthetic data for these boundaries,
address reuse, signed disabled states, sampled transition intervals and report
preservation. Five further frozen-recording tests cover rooted clock gating,
mandatory corroboration, Boolean guard results and entity-specific context IDs.
[`npc-lifetime-checks.json`](npc-lifetime-checks.json) pins the
published sources and retained private evidence. Game data is not published.
The record distinguishes committed Git-source hashes from exact local file
hashes; inherited game-source line endings are preserved.

## Reproduce

Prepare your own verified launch captures and separate observer profile with
the [NPC recording workflow](NPC_ENTRY_TRACE.md). Choose fresh workspaces:

```powershell
python tools/record_npc_history.py `
  --capture-folder D:/QA/cold-start/original `
  --observer-profile .decomp-lab/npc-observer-new/profile.json `
  --program research/headless/buddha-lifetime-route.json `
  --workspace D:/QA/npc-lifetime-original-new

python tools/record_npc_history.py `
  --capture-folder D:/QA/cold-start/rebuilt `
  --observer-profile .decomp-lab/npc-observer-new/profile.json `
  --program research/headless/buddha-lifetime-route.json `
  --workspace D:/QA/npc-lifetime-rebuilt-new

python tools/compare_npc_history.py `
  --reference D:/QA/npc-lifetime-original-new `
  --candidate D:/QA/npc-lifetime-rebuilt-new `
  --output .decomp-lab/npc-lifetime-pair-new.json

python tools/inspect_npc_lifetime.py `
  --recording D:/QA/npc-lifetime-original-new `
  --output .decomp-lab/npc-lifetime-original-new.json
```

Run the inspector separately on the rebuilt recording as well. It requires a
completed, verified observer history with qualified original entries and
preserves existing output files. It launches no emulator or external service.

## Remaining requirements

Reachability from these owners does not prove heap allocation lifetime or
screen visibility. Sampled checkpoints do not establish every intervening
state. This one recorded history does not qualify other seeds, NPCs, branches,
effects or complete-state and hardware-timing parity.

Matching C stays **197,172 / 199,912 bytes (98.63%)**: two assembly functions
and two inherited storage explanations remain. The inventory stays at 40
provisional feature groups, 38 with listed core C, and 40 of 107 callbacks
with bounded profiles. The exhaustive feature total remains unknown. No whole
NPC encounter or feature group is accepted; the 10 developer-capability
categories and three optional mods are unchanged. This strengthens one natural
history without changing original game behavior, gameplay mods or the Bevy port.
