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

## Engine entries and stop timer

The compact observer now watches all 107 original callback PCs and eight
separate engine methods. The original and rebuilt discs each produce 68,030
entries in the retained 30,000-step route: 65,330 engine-method entries and
the same 2,700 registered Buddha callbacks. These are observations of existing
code, not new callbacks or gameplay features.

At step 5,407 the original instruction trace enters `entity_enable_link` from
`entity_check_interaction`, then `entity_start_behaviour` from
`entity_check_link_trigger`, followed by the tick and first callback. At step
22,580 it enters `entity_disable_link` from `entity_check_interaction_range`
and `entity_stop_behaviour` from that disable method. The original indirect
call instructions and all eight complete method spans are checked against
the executable. Disabled context payload remains uninterpreted.

The stop predicate reads property byte four through an unsigned-byte pointer.
The source table stores Buddha's value as signed `-76`; its consumer reads
`180`. Types at least ten request a stop when the interaction timer **equals**
the unsigned value times 15. Thus this instance stops at timer 2,700. The
preceding rooted checkpoint has timer 2,700 and an enabled context; the next
has timer 2,701 and a disabled context. These units are engine updates, not
rendered frames or seconds.

`tools/inventory_entities.py` keeps every original signed property and adds
`consumer_views.interaction_stop` to each of the 130 byte-checked records.
The view distinguishes timer equality, nonzero/zero proximity results with a
nonzero range field, and types that make no direct disable request in this
predicate. It does not model the separate event-video check or other shutdown
paths. No game declaration, property byte, callback or instruction changes.

Three new cold runs compare original/observer, rebuilt/observer and
original/distributed outputs against the retained recording. Each checks
30,001 GPU/frame observations, 5,033 complete RAM hashes, all 158 selected
complete RAM/GPU/RGB checkpoints and the complete 88,457,172-byte PCM stream.
The two observer entry logs also agree byte for byte. Four actual native
control runs reject one-bit changes to owned reference GPU, RAM, RGB and PCM
data; original reference files remain unchanged.

The published compact C# source has exactly the bytes used by the full runs.
The packaged Python entry point also passes a 6,000-step replay, with the same
89 original callbacks and engine log as the independently prepared prefix.
These are two lengths of one route and seed history. Complete emulator state,
unseen branches, all content, visibility and audio causality, and hardware
timing remain open. Whole NPC encounter and whole feature acceptance stay zero.

### Compact recording

Use 64-bit Windows, .NET Framework 4.8, a stable .NET SDK, an existing verified
NPC history and a compatible catalogue-observer runtime/profile. The ordinary
matching-C build and its freshness checks stay in the supported Linux/WSL
workflow. This Windows tool checks the canonical complete image and original
table/target bytes; it accepts no C source promotion.

```powershell
python tools/record_npc_activation.py `
  --reference D:/QA/verified-npc-original `
  --runtime D:/QA/catalogue-runtime/host `
  --observer-profile .decomp-lab/catalogue-observer/profile.json `
  --workspace D:/QA/compact-activation-original
```

Use `--cue` for a rebuilt disc with identical complete track bytes and layout.
For a distributed control, supply the qualified stock runtime and `--stock`
instead of an observer profile. An optional `--frames` prefix must end at a
retained raw checkpoint.

Each workspace has an owned small host and directory junctions to the supplied
runtime's `dll` and `gamedb` directories. Passing runs write entry logs, hashes
and reports; they save no duplicate audio, PNGs or raw RAM/GPU/RGB. A failed
byte comparison retains its actual buffer. A 64 MiB output review threshold
stops only the owned process and retains partial evidence. Existing output is
never overwritten. Supplied sources, reference files, game/BIOS inputs and
runtime libraries are fully hashed before and after execution.

This is optional developer analysis, separate from original NPC AI and gameplay
mods. It calls no model service. The
[validation metadata](npc-native-activation-checks.json) records source pins,
native observations, controls and unchanged C/feature counts.

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
and three identified inherited storage explanations remain. The inventory stays at 40
provisional feature groups, 38 with listed core C, and 41 of 107 callbacks
with bounded profiles. The exhaustive feature total remains unknown. No whole
NPC encounter or feature group is accepted; the 10 developer-capability
categories and three optional mods are unchanged. This strengthens one natural
history without changing original game behavior, gameplay mods or the Bevy port.
