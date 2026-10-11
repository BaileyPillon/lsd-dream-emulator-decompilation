# Optional exploration mods

Original NPC behavior and game logic remain in the canonical matching build.
`tools/mod_executable.py` writes a separate executable and a byte-range manifest;
`tools/package_disc.py` packages that executable into a new BIN/CUE. These outputs
are optional gameplay changes. They do not increase original-game parity, the
40 provisional original feature groups, or the nine analysis-tool capabilities.

Three options are implemented: a stage-duration multiplier, endless stage
timers, and a passive Gray Man. The latest evidence independently checks one
of them, endless timers. The other two have patch checks and need emulator
behavior checks. A fresh output's creation manifest says `gameplay_tested: false`;
later runtime evidence is stored separately and does not rewrite that manifest.

## Endless timer correction

The first implementation returned -1 from `get_stage_time_limit` at
`0x8005BB14`. Native initial-spawn generation reads `STAGE_TIME_LIMITS` directly
on both its mood-selected and random-fallback paths. It therefore retained a
finite initial timer despite the getter patch. A preserved 6,000-frame replay
of this earlier mod had the same 3,600-tick first-dream limit as the original.
All 13 captured screenshots and GPU snapshots also matched in that sequence.

The corrected mod sets all fourteen signed 16-bit entries at `0x80087F14` to
-1. This changes 28 executable bytes and leaves the original setter and getter
code intact. The native setter preserves negative values; it converts positive
seconds to game ticks by multiplying by 15. Each resulting BIN differs from
the owned reference in just the corresponding executable sector, including
that sector's error-correction bytes. All other raw sectors match.

## Bounded verification

The native consumer report is
`.decomp-lab/root-work/timer-mod-native-consumer-proof-second.json`.
It records 165 executions across the original, earlier mod, and corrected mod:
fourteen getter entries, fourteen setter cases, and 27 initial-spawn choices
per executable. Actual original spawn tables, RNG, and penalty updates execute;
the mood classifier has an explicit selected-stage/coordinate contract.
Full output buffers, chosen stage, RNG state, penalty, stack, and saved registers
are compared. Both original initial-spawn branches receive -1 in the correction.
This second native report reran the unchanged fixtures after the byte-neutral
actor callback declaration correction. The first report remains preserved.

The emulator report is
`.decomp-lab/root-work/optional-timer-runtime-evidence-second.json`.
It retains the first report and freshly rechecks its artifacts, launch inputs,
22 native-proof dependencies at that frozen source snapshot, and exact
changed-sector payloads. The later native report separately pins the current
source and canonical build; the emulator replay itself was not repeated.
Both long runs complete 27,000 frames from a cold boot with identical BIOS,
emulator, configuration, input script, and disc layout. Their track contents
differ only because of the declared executable patch and sector error correction.
The observation script writes no game RAM and captures no audio.

| Observation | Original | Corrected endless mod |
| --- | --- | --- |
| Initial first-dream time limit | 3,600 ticks | -1 |
| First reaches the ordinary limit | Relative frame 22,126 | Continues |
| First advances to day 1 | Relative frame 22,427 | Remains on day 0 |
| End of the 27,000-frame replay | Day 1; timer 52 | Day 0; timer 4,550 |

The tracked fields other than the intentional limit change agree until frame
22,131, when the original begins its timeout transition. Screenshots and full
GPU snapshots match at 39 of the 48 checkpoints; later differences are the
expected consequence of the original ending its dream. The report preserves
every raw timer row, checkpoint, and launch-input identity.

This is acceptance of the timer change within the named native fixtures and
one first-dream replay. It does not establish all dream paths, Gray Man
encounters, save/card behavior, endings, original Japanese asset behavior,
hardware timing, or full original-game feature acceptance. Falls, flashbacks,
and other events can still end an endless-timer dream.
