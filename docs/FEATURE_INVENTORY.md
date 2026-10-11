# LSD feature inventory

> Publication note: this is a frozen local research snapshot. Private
> `.decomp-lab` evidence is excluded; see [provenance](PROVENANCE.md).

The current catalogue contains **40 provisional behavior/system groups**. This is an executable-grounded inventory, not a developer-official exhaustive total. Stage, asset and NPC variant counts are measured separately.

The matching baseline already preserved the original behavior in C plus assembly. C recovery measures source reconstruction; runtime acceptance measures reviewed coverage of the specified scenarios.

## Recovery baseline and publication snapshot

Before is pinned to `2026-10-10T21:28:43.894064+00:00`. After is the verified source/build snapshot at `2026-10-11T04:38:49.950521+00:00`, with 304 objects and canonical SHA-1 `76322eeade5ebb22dca57fdeac7d68c30f06308d`. Both columns use the same feature denominator.

| Measure | Before | After |
| --- | ---: | ---: |
| Catalogued original feature groups present in matching C plus assembly | 40 | 40 |
| Groups with every listed core function in C | 16 | 35 |
| Groups with listed core and shared support in C | 0 | 6 |
| Entire feature groups independently accepted at runtime | 0 | 0 |
| Game code bytes recovered in C | 84.91% | 97.18% |
| Remaining game assembly functions | 63 | 7 |
| Original native behavior callbacks in C | 105 / 107 | 107 / 107 |
| Separately implemented AI-assisted developer capabilities | 0 | 9 |

107 of 107 distinct NPC callbacks have C bodies. The entity table contains 130 records, including 111 script slots and 19 null slots; these are content dimensions. Original NPC behavior belongs to the canonical game. AI-assisted context export, native analysis, isolated matching and replay comparison are separate developer tools and do not change the canonical runtime.

The [original NPC audit](NATIVE_AI.md) byte-checked all 130 property records and callback bindings at `0x80089EA4`. Signed mood, interaction, link and event fields match the C initializer. This verifies static original data; callback state/RNG/input branches remain separate runtime requirements. Evidence: `.decomp-lab/native-entity-inventory-twenty-third.json`.

The optional native NPC verifier passed 1,608 original `entity_lion` cases and detected 3 deliberately wrong controls. Native entry execution is measured separately from the byte inventory, with explicit external-call contracts. This bounded result extends one developer capability and leaves whole-callback/feature acceptance at zero. [Scope and usage](NATIVE_AI.md). Evidence: `.decomp-lab/native-lion-verification-fourth.json`.

The optional native NPC verifier passed 768 original `entity_gray_man` cases and detected 2 deliberately wrong controls. Native entry execution is measured separately from the byte inventory, with explicit external-call contracts. This bounded result extends one developer capability and leaves whole-callback/feature acceptance at zero. [Scope and usage](NATIVE_AI.md). Evidence: `.decomp-lab/native-gray-man-verification-second.json`.

The original and rebuilt discs matched for a 6000-frame scripted play sequence at 13 checkpoints: the frame trace, PNGs, full GPU memory and every save-state member payload were equal. Save-state archive wrappers differ. Evidence: `.decomp-lab/runtime-pinned-audio-play-comparison.json`.

The comparator verified the frozen disc layout/content, emulator/core binaries, BIOS files, launch settings, script and starting state against both input manifests.

The recorded audio also matched: 4,422,823 sample frames, 2 channels, 44,100 Hz and 16-bit PCM, with 7,732,155 nonzero channel samples. This verifies non-silent captured output for the sequence, not every music track or sound event.

This limited sequence does not cover every feature branch, content item, audio event or card error. Full feature scenarios remain unaccepted.

An additional 1800-frame movement replay matched 43 native input/player-state fields each frame (77,400 field values per run), plus 6 image/GPU/state checkpoints. This covers the recorded turning, looking, movement and input phases in one stage; entire feature groups remain unaccepted. [Replay details](RUNTIME_COMPARISON.md). Evidence: `.decomp-lab/runtime-movement-0209-comparison.json`.

The reference extraction contains 683 files across 14 stage directories. Its texture containers contain 445 TIM records. [Asset inventory](ASSET_INVENTORY.md) documents counts, native structures and the preserved original length-field anomaly; semantic and runtime content auditing remain open.

The [native dispatch audit](NATIVE_DISPATCH.md) checked 57 declared virtual tables, including 29 C initializers, against original executable words. Their 2205 non-null declared callback slots refer to 838 distinct addresses. These are dispatch dimensions, separate from NPC callback and game-feature counts; call-site closure and semantic signatures remain open. Evidence: `.decomp-lab/native-vtable-inventory-twenty-third.json`.

The [native animation audit](NATIVE_ANIMATIONS.md) inspected 420 original MOM/LBD files: 111 model instances contain 122 animations, 4260 frames and 26797 records. Unique content comprises 100 model hashes and 108 animations. These structural content counts do not establish playback or add game features. Evidence: `.decomp-lab/native-animation-lbd-inventory-twenty-third.json`.

The same audit bounded 418 of 418 LBD files, 167,200 grid cells and 270 additional tile records. Its 98 streamed libraries contain 109 model references, with 0 unresolved structures/reference associations. This closes the audited static LBD/MML-to-MOM associations; primitive payloads, collision data and runtime reachability remain separate requirements.

## Feature groups

| ID | Behavior/system group | Core C before / after | Primary source | Remaining runtime scenario |
| --- | --- | --- | --- | --- |
| F001 | Startup logos and randomized opening | complete / complete | [src/dream/dream_session_path.c](../src/dream/dream_session_path.c#L13) | Cold boot each opening selection; compare frame order, skip behavior, timing and audio. |
| F002 | Title menu, day display and mode selection | partial / complete | [src/game/game_flow.c](../src/game/game_flow.c#L139) | Exercise every menu item, confirm/back and disabled state from new and progressed saves. |
| F003 | 365-day progression and year ending | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1003) | Replay days 364, 365 and new-year day 1; compare counters, history and ending trigger. |
| F004 | New-game state and reset | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1015) | Create new games and trigger reset endings; compare the entire save block. |
| F005 | Dream-session and map lifecycle | complete / complete | [src/dream/dream_session.c](../src/dream/dream_session.c#L101) | Run repeated dreams and stage changes; compare result codes and resource lifetimes. |
| F006 | Walking, running, strafing and looking | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L685) | Replay held/tapped inputs; compare positions, camera angles, step lengths and action edges frame by frame. |
| F007 | Input suspension and scripted camera/movement takeover | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1266) | Trigger each takeover mode; compare lock duration, camera path and control recovery. |
| F008 | Transforms, collision and floor-surface response | partial / partial | [src/base/transform.c](../src/base/transform.c#L21) | Walk into walls, stairs, edges and each surface class; compare decisions, positions and floor effects. |
| F009 | Stage grids, chunk traversal and placed objects | partial / complete | [src/scene/link.c](../src/scene/link.c#L416) | Visit every stage and grid boundary, including vertical maps; compare geometry, placement and reloads. |
| F010 | Touch-wall dynamic and fixed links | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1090) | Touch fixed/ordinary walls at eligible/ineligible ticks; compare destination, spawn, penalty and transition. |
| F011 | Facing-sensitive tunnel links | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1136) | Approach tunnels both ways and at angle boundaries; compare acceptance and destination pose. |
| F012 | Instant teleporters and time bonus | partial / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1178) | Test every enabled/disabled condition; compare destination, pose, bonus and repeat triggers. |
| F013 | Staircase links | partial / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1232) | Enter staircases both ways and at angle boundaries; compare transforms, movement and destination. |
| F014 | Link-transition choreography | partial / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L950) | Compare each link kind frame by frame: fades, lock, result and actor handoff. |
| F015 | Dream timeouts and ending/reset encounters | partial / complete | [src/dream/dream_session.c](../src/dream/dream_session.c#L273) | Compare timeout frames for all 14 durations and encounter exits with/without flashback. |
| F016 | Dream mood accumulation, wrap and color classification | partial / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1551) | Replay known contributions and boundary values; compare axes, chart entry and color. |
| F017 | Dream-chart history display | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1455) | Compare charts at 0, 1, 99, 100, 101 and wrapped days, including newest-point highlight. |
| F018 | Mood-dependent initial stage and spawn | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1455) | Start matched/unmatched moods with fixed RNG; compare map, chunk, pose and limit. |
| F019 | Navigation and encounter unlock score | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1743) | Replay challenges/encounters around thresholds; compare flags, score, penalties and gated options. |
| F020 | Flashback recording, recall and loss | partial / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1636) | Fill/replace/replay slots, meet Gray Man, return to normal play; compare slot bytes and day restoration. |
| F021 | Special-day films and still screens | complete / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1074) | Cover all schedule slots/variant classes; compare asset, duration, day and chart behavior. |
| F022 | Chart-triggered bonus video reel | complete / complete | [src/game/game_flow.c](../src/game/game_flow.c#L139) | Compare histories with missing/all cells: unlock, highlights, reel order and replay suppression. |
| F023 | Day-dependent stage texture variants | partial / complete | [src/scene/map_scene.c](../src/scene/map_scene.c#L100) | Compare every stage at days 1,10,11,20,21,30,31,41 with fixed RNG: bank, palette and upload. |
| F024 | Procedural dream structures and palette seeding | partial / complete | [src/dream/dream_generation.c](../src/dream/dream_generation.c#L61) | Replay modes/daily boundaries with fixed seed; compare structures, transforms, colors and lifetime. |
| F025 | Distance-driven generated ambient encounters/effects | partial / complete | [src/dream/dream_generation.c](../src/dream/dream_generation.c#L74) | Cross activation/deactivation radii for all entries/modes; compare slot reuse, sound, effects and record markers. |
| F026 | NPC perception, triggers and behavior lifecycle | complete / complete | [src/base/object_math.c](../src/base/object_math.c#L128) | Test every trigger class at range/facing/time bounds; compare activation, callbacks, flags and events. |
| F027 | Original scripted NPC and moving-object behavior catalog | partial / complete | [src/scene/entity.c](../src/scene/entity.c#L2355) | Instantiate every record, covering callback state/RNG/input branches; compare poses, motion, sound, control and result events. |
| F028 | Encounter effects on mood, score, links and cinematics | partial / complete | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1090) | Trigger each event class in normal/flashback mode; compare affected counters, flags and destinations. |
| F029 | Actor model assembly and animation scripts | partial / complete | [src/file/model_part.c](../src/file/model_part.c#L5) | Compare each animation, wrap/stop and multipart failure path: transforms/frame timing. |
| F030 | Randomized stage music and soundtrack bank | complete / complete | [src/sound/bgm.c](../src/sound/bgm.c#L86) | Cover banks/tracks and stage-nine remap; compare sequence, timing, volume and pause/resume. |
| F031 | Encounter sound effects and command scheduler | partial / complete | [src/sound/sound.c](../src/sound/sound.c#L170) | Compare all commands, simultaneous notes, mute/restore and load completion: events and mixed output. |
| F032 | Streaming video playback | complete / complete | [src/file/cd_stream.c](../src/file/cd_stream.c#L5) | Play each referenced movie with normal/skipped playback; compare frames, audio alignment and return time. |
| F033 | Original 3D rendering and model geometry | partial / partial | [src/base/render_sort.c](../src/base/render_sort.c#L36) | Compare framebuffers for every primitive/material, near-plane edge, light and stage. |
| F034 | Color overlays, flashes, borders and shake | partial / complete | [src/dream/dream_generation_post.c](../src/dream/dream_generation_post.c#L250) | Compare start/stop, RGB wrapping, multiple attached effects, borders and shake on/off frame by frame. |
| F035 | Menu transitions, selection and sprites | partial / partial | [src/menu/sprite.c](../src/menu/sprite.c#L96) | Compare every screen, held/edge input, idle timeout, confirm/back and transitions. |
| F036 | Text, glyphs, labels and decimal formatting | partial / complete | [src/menu/glyph.c](../src/menu/glyph.c#L151) | Compare glyph banks, empty/long strings, spacing/color and day labels 1,10,100,365. |
| F037 | Memory-card save and load of dream state | partial / partial | [src/dream/dream_sys.c](../src/dream/dream_sys.c#L1023) | Compare save payload, label/icon, restored counters/recall/options from progressed states. |
| F038 | Memory-card file management and error flow | partial / partial | [src/menu/card/memory_card.c](../src/menu/card/memory_card.c#L88) | Compare isolated empty/full/corrupt/no-card/unplug/cancel cases: screens, file lists and card bytes. |
| F039 | Save comment/name entry | partial / complete | [src/menu/card/comment_input.c](../src/menu/card/comment_input.c#L8) | Enter/erase/replace/cancel at string bounds; compare bytes, cursor, glyphs and saved label. |
| F040 | Disc reads and resource decoding | partial / complete | [src/file/cd_file_driver.c](../src/file/cd_file_driver.c#L651) | Compare all referenced resources plus seek/cache/read/reset/error paths: bytes, completion ordering and uploads. |

## Remaining scope

The [ordered-store audit](RENDER_MATCHING.md) executes three variants over the
same 74,832 scalar fixtures. It rejects the four-byte candidate's internal
write order in 68,306 cases; the corrected candidate preserves that order but
differs in 13 executable bytes. This refines F033 evidence without a C promotion
or change to original/NPC, tool-capability or whole-feature counts.

The [grid and streaming composition](RENDER_STREAM.md) checks 45,408 bounded
cases through four original functions, with four detected controls and three
position/GTE contracts. The actual builder, row splitter and object selector
now execute; the same full C candidate still differs in four bytes. This
extends F033 evidence without changing game C, original/NPC, tool-capability
or whole-feature counts.

The [grid-window supplement](RENDER_GRID.md) verifies the original renderer
helper in 74,832 bounded cases with eight detected controls and four explicit
dependencies. The closest full C candidate agrees on those fixtures but has
four differing bytes and remains private. This extends F033 evidence with
unchanged game C, original/NPC, tool-capability and whole-feature counts.

The [save workflow supplement](CARD_SAVE.md) checks the original retry wrapper,
writer, path builder, title formatter and SDK string/conversion routines in
13,152 bounded cases. Seven I/O/allocation/diagnostic contracts remain explicit.
This extends evidence for F037/F039; it adds no original feature, C promotion,
whole-feature acceptance or developer capability. The writer's full C candidate
still differs in eight bytes. Physical card I/O and complete save round trips
remain open.

The [render-context bounds supplement](RENDER_BOUNDS.md) adds 4,648 original
native cases and four detected controls with zero stubs. A C candidate agrees
on those fixtures but still has 38 byte differences and remains private.
This adds bounded evidence for F033 without a C promotion or whole-feature
acceptance. The original/NPC counts and ten developer capabilities are unchanged.

The [SDK and sound API supplement](SDK_SIGNATURE_AUDIT.md) corrects a misleading
volume label using a matching 676-byte SDK context. The actual getter passes
384 native cases and three controls with no stubs. The 72 raw SDK-labelled
functions remain a scoped inventory with ambiguous signature matches. Game C
coverage and the 40-group denominator are unchanged. Developer capability A010
brings the current count from the frozen nine to ten, with zero model API calls.
This adds evidence for F031 without accepting its entire group.

The [save-title supplement](SAVE_LABEL.md) recovers one additional 240-byte
game-support function formerly hidden inside a raw SDK-labelled segment.
Current matching C bytes are **194,284 / 199,912 (97.18%)**, with 305 build
objects. The same corrected denominator applied to the preserved pre-prompt C
numerator gives 169,540 / 199,912 (84.81%); this is an arithmetic restatement,
not a rerun of the baseline. The frozen table above retains its original scope.
The seven previously counted assembly functions remain.

The formatter passed 1,952 bounded native cases and three negative controls
using the actual SDK conversion code, with no stubs. This is additional evidence
for save-title support in F037/F039, not acceptance of those entire groups.
The 40 provisional groups, 35 groups with listed core functions in C and zero
whole-feature acceptances remain unchanged. The current build also passed fresh
runs of the existing 6,784 bounded NPC fixtures. Metadata is appended to
[features.json](features.json), preserving the earlier records.

The [scripted callback supplement](SCRIPTED_AI.md), recorded after the frozen
publication snapshot, adds nine original callbacks with 4,408 bounded native
cases and nine detected controls. Together with the existing Lion and Gray Man
checks, this yields 11 of 107 callbacks and 6,784 cases. It does not change the
40-group denominator, C-recovery counts or zero whole-feature acceptance.

Asset/command records, virtual-call closure, rare state/RNG/save/error branches, hardware timing and audio coverage remain to audit. [features.json](features.json) preserves requirements, dependencies, immutable before statuses, current source hashes and runtime evidence. Five inventory gaps remain open; U006 records the user's resolved separation of original behavior from AI tooling.

A core-C count is based on actual configured definitions and live assembly inclusions. Shared support follows explicit dependencies and does not claim exhaustive call-graph closure. Optional gameplay mods have their own outputs and do not count toward original parity.

The [sprite scaling supplement](UI_SCALE.md) adds 203,472 original native cases
and the same number of candidate runs, with zero stubs and four detected
output controls. It preserves the Y denominator read after X's store and
incoming-register behavior for skipped divisions. The full C candidate still
differs in 12 executable bytes; 108 additional source trials found no exact
match. This extends bounded UI evidence without changing C, original feature,
NPC, developer-capability, optional-mod or whole-feature acceptance counts.
