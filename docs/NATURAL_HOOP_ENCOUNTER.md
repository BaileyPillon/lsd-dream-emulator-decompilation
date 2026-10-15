# Natural Hoop Girl and day-transition comparison

Original and rebuilt Japanese discs agree across a **30,000-frame** controller
scenario: approach the naturally loaded Hoop Girl, observe her registered
behavior, then retain the subsequent dream-end, movie, and chart sequence.
This extends in-game evidence; it recovers no additional C bytes and does not
accept a complete NPC encounter or feature group.

## Observed path

Both runs start from the original [window replay](NATURAL_WINDOW_LINK.md)'s
frame-2400 state, on day one in map key 12. Ordinary directional and Cross
inputs approach the existing actor. The script writes no game memory and
injects no entities, positions, or assets.

| Observation | Result in both runs |
| --- | --- |
| Existing actor | Entity 71, Hoop Girl; original-table callback `0x80062570` |
| First pre-frame activation observation | Relative frame 224 |
| Registered samples | 345 rows, frames 240 through 10,560 |
| Registered ticks | 4 through 2,068; entity/context ticks agree |
| Animation | Duration 15; sampled frame equals tick modulo duration |
| Input lock first observed | Controller frame 10,564 |
| Day progression | Stored day-of-year zero at frame 9,000, one at frame 12,000; derived day number changes from one to two |
| Later presentation | Movie imagery at frame 15,000; dream chart at frame 30,000 |

Registered rows have the expected context state 72, actor owner, callback
binding, and active flag. They cover the recorded motion and animation path.
The callback's branch at tick **2,401** was not reached before the dream ended.
Its initial RNG choice and every later branch are not accepted by these samples.

A later [earlier-start timing profile](NATURAL_HOOP_TIMING.md) reaches tick
2,498 and compares post-threshold facing/motion on both discs. That is a
separate 15,000-frame history; it does not change this profile's observations
or establish complete encounter acceptance.

The global generation variable `g_CurrentDay` remains one after the DreamSys
day field advances. These are different fields and are recorded separately.
Day numbers here apply the getter's plus-one rule to the stored field; the
observer does not trace getter entries or claim a displayed day-number UI.
Retained map/type bytes after teardown do not prove the world is still active.
The chart screenshot and compatible graph record support the later screen
observation; scanning class bytes alone is not an entry trace or proof of liveness.

## Input and output comparisons

The revised recorder explicitly clears digital inputs and logs every submitted
value. The observed controller definition contains 21 Boolean controls, four
stick axes at 128, and a disc selector at zero. The last nonzero pre-frame
game pad-held value occurs at frame 227, after requested buttons stop at 224.
These are separate controller-submission and game-poll timelines.

| Output | Exact comparison scope |
| --- | --- |
| Requested controls | All 30,000 rows |
| Submitted controls and game pad fields | All 30,000 rows and all 26 submitted values per row |
| Scene log | All 1,001 rows |
| NPC log | All 353 rows, including the 345 registered samples |
| MainRAM | All 2,097,152 bytes at eleven checkpoints, frames 0 through 30,000 in steps of 3,000 |
| Screenshots | PNG bytes at those eleven checkpoints |
| Save states | Every ZIP member payload at those eleven checkpoints, without masks |

Input manifests revalidate identical disc tracks/layout, seven runtime/core
files, three BIOS files, configuration, script, and starting state. Both owned
QA processes exited successfully. Their new external SaveRAM files were
preserved by hash in private exit directories; ordinary play saves were untouched.

Full memory between checkpoints is not captured. No audio was recorded, and
the installed core exposes no execution-hook scopes or registers. Cold boot,
direct callback entries, all NPC branches, original hardware timing, and complete
movie/chart routes remain open.

## Reproduction and progress

The [research guide](../research/npc_encounter/README.md) describes the exact
executed recorder, required warm state, input handling, and pure regression
check. [natural-hoop-encounter-checks.json](natural-hoop-encounter-checks.json)
pins the input identity, private comparison, and all output hashes. Original
game content and full captures are not distributed.

C recovery remains **194,212 / 199,912 bytes (97.15%)**, with nine assembly
functions and 24 inherited storage explanations. The 107 NPC C bodies, 20
bounded native callback profiles, 40 provisional feature groups, and zero
complete encounters/feature groups accepted retain their existing counts.
All [project completion requirements](../PROJECT_OBJECTIVE.md) remain in force.
