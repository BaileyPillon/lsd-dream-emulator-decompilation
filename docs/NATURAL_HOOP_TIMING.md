# Earlier window route and Hoop Girl's timed motion

An earlier original-game state leaves enough time to observe Hoop Girl beyond
tick **2,401**. Original and rebuilt Japanese discs agree across this
**15,000-frame** route: finish the existing map load, approach the window, follow
its link, approach Hoop Girl, and remain neutral through her later motion and
the dream's end.

This supplements the [30,000-frame profile](NATURAL_HOOP_ENCOUNTER.md), whose
later starting state ran out of dream time first. Its frozen results remain
unchanged. Neither profile accepts a complete encounter or feature group.

## Recorded observations

The original frame-4800 state starts with map key 3 retained, dream timer 742,
limit 3,600, and input locked while the existing transition completes. The
script waits, approaches the naturally loaded window, and switches its target
to the existing Hoop Girl after the link reaches map key 12. No game RAM,
actor, clock, RNG state, or position is injected.

| Observation | Same result in both runs |
| --- | --- |
| Registered window samples | Five; entity 75, expected owner and callback `0x800628D4` |
| Hoop Girl control release | First observed at controller frame 1,553 |
| Registered Hoop Girl samples | 417; entity 71, expected owner and callback `0x80062570` |
| Last sample before threshold | Frame 13,530; tick 2,396; X = -48,128; pose yaw = 0 |
| First sample after threshold | Frame 13,560; tick 2,402; X = -48,122; pose yaw = 2,184 |
| Post-threshold samples | 17, through tick 2,498 at frame 14,040 |
| Animation | Every recorded Hoop Girl frame equals tick modulo duration 15 |

The [recovered callback](../src/scene/entity.c#L2472) applies its facing helper
from tick 2,401 onward. The adjacent samples bracket that condition and show
the corresponding facing/motion change. They do not directly trace a branch
instruction, identify every intermediate frame, or check every initial RNG
choice. Advancing context/entity ticks, owner and callback bindings strengthen
these field observations; a vtable scan alone is insufficient liveness evidence.

## Exact comparison

All 15,000 requested-input rows, 15,000 complete submitted vectors and game-pad
rows, 501 scene rows, and 452 NPC rows agree byte for byte. At frames 0, 3,000,
6,000, 9,000, 12,000, and 15,000, all 2,097,152 MainRAM bytes, PNG bytes, and
every save-state ZIP member payload agree without masks. Full memory was not
captured at the tick-2,401 boundary itself.

Input manifests revalidate the same starting state, script, disc contents and
layout, BIOS, runtime/core files, and configuration. Both owned QA processes
exited successfully. Their save outputs were preserved separately from
ordinary play. No audio was captured, and no execution-hook scope is available.
Cold boot, complete NPC construction/lifetime and RNG histories, physical
hardware timing, and full-feature acceptance remain open.

## Reproduce and interpret

The [research guide](../research/npc_encounter/README.md#earlier-window-to-hoop-route)
describes the exact executed script and required private state.
[natural-hoop-timing-checks.json](natural-hoop-timing-checks.json) pins inputs,
recorded outputs, observations, comparison producer, and unchanged before/after
counts. Game content and full captures remain private.

This extends the recorded natural timing coverage. C remains **194,212 /
199,912 bytes (97.15%)**, with nine assembly functions and 24 inherited storage
explanations. Complete NPC/feature acceptance remains zero. All
[project completion requirements](../PROJECT_OBJECTIVE.md) are preserved.
