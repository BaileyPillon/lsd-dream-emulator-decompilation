# Natural hull call and return comparison

All **194 hull invocations** observed between frames 900 and 6,000 of the opening
route now have completed call/return records. Original and rebuilt records and
complete RAM payloads agree. The input-driven model agrees on return values,
receiver masks, hull-hit flags, contact points, and midpoint words.

This extends the earlier [primitive-call collection](COLLISION_ORDINAL_CALLS.md).
It adds no matching C bytes and accepts no whole feature or NPC encounter.

| Observation in this route | Before | After |
| --- | ---: | ---: |
| Completed natural hull samples | 0 | 194 |
| Hull return `1` / `0` | Unchecked | 21 / 173 |
| Hull calls crossing a frame boundary | Unchecked | 20 |
| Nested primitive entries correlated with hull queries | Unchecked | 484 |
| Primitive entries outside the recorded hull intervals | No return intervals | 159 |
| Matching C game bytes | 197,172 | 197,172 |
| Accepted whole-feature groups | 0 | 0 |

The 484 nested calls comprise 159 modeled midpoint queries and 325 fallback
queries, visiting 11,333 polygons. Their segment values, argument pointers,
results, nearest distances, contacts, and heights agree with the earlier
independently recorded primitive boundaries. The other 159 primitive entries
come from the two direct call sites in
[`object_math.c`](../src/base/object_math.c); they remain covered by the earlier
643-call primitive collection. They are not attributed to these hull calls.

## Observer qualification

The original hull method is entered through `JALR`. The separate observer retains
the effective target-register value, call/delay instruction and cache contexts,
link, stack, architectural CPU/GTE views, and complete 2 MiB RAM at both boundaries.
The checker requires the original complete 796-byte callee, qualified target and
return instructions, and preserved caller state. An indirect-call window does
not prove a virtual-table slot load chain.

Four ordinal phases capture **49, 49, 48, and 48** calls. Every observed hull
entry appears exactly once in each game's partition. Limits remain 64 samples
per recording, one start per frame, one pending call, and two completed records /
8 MiB of payload per frame. All loss and overflow counters are zero.

Eight observer recordings and one stock-core control retain identical game
outputs: 6,001 GPU observations, 1,001 RAM observations, 52 complete RAM/GPU/RGB
checkpoints, and 17,692,008 PCM bytes per run. An independent audit decodes all
468 PNGs, rehashes 375 retained source snapshots, and rejects ten contradictory
retained-data cases. These cases modify analysis inputs; they are not executed
game faults. An earlier observer attempt without indirect-entry context is
retained and explicitly rejected.

The updated core also reproduces the existing 52-sample primitive policy with
byte-identical events, complete RAM payloads, and recorded game outputs. Summary
counters agree; the new summary additionally includes the optional zero-valued
`ordinal_skips` counter.
Existing primitive ordinal recordings remain readable. The native build still
uses pinned cached objects plus a freshly compiled adapter; its profile retains
`runtime_verified: false` rather than certifying every core mode.

## Reproduce with local game inputs

Use the [pinned native build prerequisites](DISPATCH_ENTRY_TRACE.md). Build a
fresh separate observer with `tools/build_dispatch_observer.py --collision-calls`.
Profiles created before the indirect-entry extension must be rebuilt for new
recordings; retained recordings can still be inspected.

Prepare the four programs:

```powershell
python tools/collision_call_batches.py `
  --program research/headless/collision-hull-opening-route.json `
  --output .decomp-lab/hull-programs-new
```

Copy that prepared folder to a fresh collection as `programs`, and retain its
`plan.json` separately as `program-plan.json`. Record every phase once from the
verified original cold-capture inputs and once from the rebuilt cold-capture
inputs, using `tools/record_dispatch_history.py` with the new observer profile.
Record phase 1 again without an observer profile for the stock control. Use
distinct workspaces and keep large recordings on a data drive.

The collection manifest uses the same format as the primitive collection, with
an explicit hull function:

```json
{
  "schema_version": 1,
  "type": "ordinal_collision_recording_collection",
  "function": "func_8001DDF4",
  "ordinal_step": 4,
  "reference": ["original/phase-01", "original/phase-02", "original/phase-03", "original/phase-04"],
  "candidate": ["rebuilt/phase-01", "rebuilt/phase-02", "rebuilt/phase-03", "rebuilt/phase-04"],
  "stock": "stock/phase-01",
  "program_plan": "program-plan.json",
  "prepared_programs": "programs",
  "canonical_executable_sha256": "282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f"
}
```

Validate the actual retained collection:

```powershell
python tools/inspect_collision_call_batches.py `
  --manifest D:/private/hull-collection/collection.json `
  --output .decomp-lab/hull-comparison-new.json
```

`tools/inspect_hull_calls.py` also inspects an individual recording or compares
an original/rebuilt pair. Its `observer-output` comparison mode checks the
stock-core control. Preparation and recording alone do not establish coverage.
Media, BIOS, raw RAM, and private recordings are not distributed.

## Remaining requirements

The [matching-C gap](OVERLAP_CONTROL_FLOW.md) remains: two collision functions
still use assembly, and three inherited C storage explanations are unresolved.
C coverage remains **197,172 / 199,912 bytes (98.6294%)**. Other histories,
complete NPC encounters, resource/geometry ownership, full instruction paths,
opaque CPU/GTE state, and original-hardware timing remain open. The feature
denominator is still 40 provisional groups; the exhaustive original total is
unknown. Original behavior, optional mods, AI-assisted tools, and the Bevy port
retain separate status.

[Publication metadata](hull-call-checks.json) records the executed collection,
independent audit, compatibility check, source identities, and unchanged counts.
