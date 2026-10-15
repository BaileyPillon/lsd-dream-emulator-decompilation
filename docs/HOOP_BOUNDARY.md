# Hoop Girl's observed tick boundary

The original and rebuilt Japanese discs agree through a **1,800-frame** replay
of a naturally reached Hoop Girl. Every frame is observed, including ticks
2,399 through 2,403. Her first visible facing change occurs at post-frame tick
**2,402**, following the observation at tick 2,401 that still has yaw zero.

This tightens the [earlier timing profile](NATURAL_HOOP_TIMING.md), which sampled
every 30 frames. It adds bounded natural-state evidence, not recovered C bytes
or a complete accepted encounter.

## Starting state and input

The replay loads the earlier original route's frame-12000 save state. That
route naturally approached the window, followed its link, and activated Hoop
Girl. The resumed actor is entity 71 in map 12, with matching dream ownership,
registered context 72, the original callback, and advancing entity/context
ticks. The observer checks those bindings on every frame.

All 21 Boolean controls are explicitly false. Five numeric inputs retain their
recorded baseline values. Every complete 26-value vector is logged, and every
observed game pad held/released/pressed field remains zero. There are no game
RAM, RNG, clock, actor, or position writes. Separate QA profiles preserve their
own save outputs and leave the interactive play profile untouched.

## Exact recorded boundary

| First observation at tick | Relative emulator frame | X | Z | Yaw | Animation frame |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2,399 | 1,541 | -48,128 | -70,946 | 0 | 14 |
| 2,400 | 1,546 | -48,128 | -70,976 | 0 | 0 |
| 2,401 | 1,551 | -48,128 | -71,006 | 0 | 1 |
| 2,402 | 1,556 | -48,122 | -70,977 | 2,184 | 2 |
| 2,403 | 1,561 | -48,116 | -70,948 | 2,184 | 3 |

The [Hoop Girl action](../src/scene/entity.c#L2472) tests `m_Tick >= 0x961`.
The [entity tick wrapper](../src/scene/entity.c#L653) calls its update helper
before incrementing `m_Tick`. The observed post-frame boundary is consistent
with that ordering. It does not directly count instruction or callback entries;
the checked emulator core exposes no execution-hook scope in the earlier
capability profile. A frame observation and a callback's input tick remain
different measurements.

## Comparison and limits

All 1,801 observation rows and 1,800 complete submitted vectors agree byte for
byte. At relative frames 0, 1,541, 1,546, 1,551, 1,556, 1,561, and 1,800,
all 2,097,152 MainRAM bytes, PNG bytes, and every save-state ZIP member payload
agree. No fields or bytes are masked. The pinned disc, BIOS, emulator/core,
configuration, script, and starting state are revalidated.

The original/rebuilt pair also agrees at its initial full-RAM checkpoint.
Separately, that resumed checkpoint differs from the prior route's RAM snapshot
at 645 byte positions, and its core frame counter is one higher. The recorded
actor fields agree with the prior snapshot; the cause of the complete-memory
drift remains unproven. All differences remain in the private record. This
profile does not establish uninterrupted-process identity with the prior run.

An initial recorder attempt emitted an extra TSV column because Lua's unpack
operation also returns its next index. That attempt is preserved and excluded.
The corrected single-result readers and input helper pass their synthetic Lua
checks, including the old multi-result and held-button negative controls.

The exact executed [recorder](../research/npc_encounter/hoop_boundary.lua),
[reader check](../research/npc_encounter/test_boundary.lua), and
[reproduction guide](../research/npc_encounter/README.md#hoop-girl-boundary-continuation)
are public. [hoop-boundary-checks.json](hoop-boundary-checks.json) pins the input
identity, captured output hashes, comparison, exclusions, and unchanged counts.
Game content and full captures remain private.

Cold boot, every initial RNG choice, complete construction/lifetimes, audible
output, physical hardware timing, and full-encounter acceptance remain open.
C remains **194,212 / 199,912 bytes (97.15%)**, with nine assembly functions and
24 inherited storage explanations. Whole-NPC and whole-feature acceptance
remain zero; every [completion requirement](../PROJECT_OBJECTIVE.md) is retained.
