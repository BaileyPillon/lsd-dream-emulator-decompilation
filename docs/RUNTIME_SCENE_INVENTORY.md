# Recorded dream-scene inventory

`tools/inventory_runtime_scene.py` reads an existing cold-start checkpoint and
reports reachable objects, reciprocal child/parent links and NPC registration.
It uses the recorded dream, session and map-scene owners. It neither controls
an emulator nor executes game code.

This closes an evidence gap between constructed NPC fixtures and the captured
playable dream: a loaded entity does not establish that its script ran.
The original `sound_entity_update` uses a **signed `state > 0`** guard.
When that guard is false, the inspector leaves the context payload uninterpreted;
old tick, owner and callback-shaped bytes are not live registration evidence.

## Observed original/rebuilt checkpoints

The retained [cold-start repeat](COLD_START.md) supplies seven checkpoint pairs.
Every pair has equal complete 2 MiB MainRAM and equal derived inventories.
No additional gameplay recording was made.

| Relative frame | Reachable objects per image | Child edges checked per image | Entity objects per image | Enabled contexts |
| --- | ---: | ---: | ---: | ---: |
| 2,689 | 2,931 | 2,941 | 0 | 0 |
| 3,000; 3,600; 4,200; 4,800; 5,400; 6,000 | 2,985 at each checkpoint | 3,010 at each checkpoint | 5 at each checkpoint | 0 |

Across both images, this checks **41,682 object observations** and **42,002
reciprocal child edges**. Repeated observations are not distinct game features
or newly recovered functions. The five entity instances at the later checkpoints
have four original table IDs:

| ID | Instances per later checkpoint | Declared callback label |
| --- | ---: | --- |
| 5 | 1 | `entity_futon` |
| 77 | 2 | `entity_bear_apartment` |
| 90 | 1 | `entity_television` |
| 91 | 1 | `entity_big_face_man_hidden` |

These are recovered source labels. Reachability does not prove screen visibility.
Both Bear instances reference the same model binding. All five behavior-active
flags and context states are zero at the sampled boundaries. This does not
establish their state between checkpoints or prove that they never ran.

## Checks and limits

The inspector revalidates the capture's pinned disc, BIOS, emulator, configuration
and observer inputs. It checks the selected native observation against complete
RAM, then follows bounded native lists from the three owners. Object-graph cycles
are valid; cycles within an individual linked list are rejected. Every observed
child edge needs a matching parent entry, including duplicate-edge multiplicity.
Each reachable vtable's first 16 bytes must match the canonical executable.
This prefix check is not verification of every vtable method or heap allocation.

The complete original 130-entry property table must agree with the current C
initializer and recorded RAM. Enabled contexts report their entity ID, owner and
callback binding; a cleared callback is separate from the declared table binding.
Registration is not evidence of an instruction entry. The report accepts no
whole NPC encounter or original feature group.

Seven corruptions of offline checkpoint copies are rejected: list cycle, missing
parent link, invalid entity ID, wrong dream owner, changed vtable prefix, changed
property byte and wrong enabled-context ID. An eighth control changes only a
disabled context's old payload and preserves the inventory. Original captures
and the running game are untouched. Twelve synthetic tests also cover signed
disabled states, graph cycles, callback clearing, pointer bounds and owner checks.

## Reproduce

Use your own supported executable, generated symbol map and a completed capture
from [the cold-start recorder](COLD_START.md). Select an unlocked dream boundary
that has a complete RAM checkpoint. Existing reports are preserved.

```powershell
python tools/inventory_runtime_scene.py `
  --capture-folder D:/QA/lsd-cold-start-new/original `
  --frame 3000 --output .decomp-lab/runtime-scene-new.json
```

[runtime-scene-checks.json](runtime-scene-checks.json) pins the executed sources,
private pair/control report and unchanged before/after counts. Matching C remains
**197,172 / 199,912 bytes (98.63%)** with two remaining assembly functions.
The inventory remains 40 provisional groups, 38 with listed core routines in C,
40 of 107 callbacks with bounded native profiles, and zero accepted whole
feature groups or NPC encounters. This adds analysis tooling within the existing
developer categories; original behavior, optional mods and the Bevy port are
unchanged. The next encounter gate needs recorded activation and execution,
followed by the relevant animation, effects, lifetime and visible-output checks.
