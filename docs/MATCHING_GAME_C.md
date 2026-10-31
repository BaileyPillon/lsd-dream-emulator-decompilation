# Complete matching game-code C

On October 30, 2026, the two remaining game assembly functions were replaced
with C adapted from the completed CC0
[brian-oblivion/lsddecomp](https://github.com/brian-oblivion/lsddecomp) project.
A clean rebuild of all **306 configured objects** reproduces the canonical
505,856-byte Japanese executable byte for byte.

**199,912 / 199,912 counted game-function bytes now compile from C.**
SDK code and handwritten startup remain separate: this denominator excludes
147,880 SDK text bytes and 188 startup bytes. This milestone does not claim
that every function in Sony's libraries is C or that the game's original
source declarations have been uniquely recovered.

[Machine-readable evidence](matching-game-c-completion-checks.json) records the
source hashes, full candidate comparisons, clean build, compiler identity,
current feature anchors and unchanged runtime gates.

## Source rule and compatibility storage

The owner explicitly approved documented upstream stack-layout padding:
“Allow documented upstream stack-layout padding.” This supersedes the
no-padding restriction in the retained, historical
[frozen objective](../PROJECT_OBJECTIVE.md). All complete-executable, asset,
behavior, playable-build and runtime comparison requirements remain in force.
Instruction substitution and embedded copies of the original assembly are
still excluded as ways to raise the C count.

The conventional matching-C milestone includes the following explicit layout
workarounds. They preserve the original compiled stack layout; they do not add
game behavior or increase the original machine code's stack footprint.

| Function | Compatibility storage | Provenance |
| --- | ---: | --- |
| `func_8001DDF4` | 24 unused bytes | Upstream hull reconstruction |
| `func_8001F8B8` | 16-byte unused vector and one unused 4-byte distance slot | Upstream face-ray reconstruction |
| `debug_file_driver_unk15` | 64 unused bytes | Inherited source |
| `debug_file_driver_open` | 64 unused bytes | Inherited source |
| `cd_file_driver_read_sectors` | 2,048 unused bytes | Inherited source |

The original authors' purposes or declarations for those unused regions are
not established. The earlier [compiler census](UNUSED_LOCAL_CENSUS.md), rejected
padding-free candidates and failed comparisons remain preserved as historical
research. Compiler warnings about the intentionally unused compatibility
locals are expected. The original first-cursor and unsupported-packet quirks
also remain unchanged.

## Integrated functions

| Original address | Function | Matched text bytes |
| --- | --- | ---: |
| `0x8001DDF4` | Hull against model faces | 796 |
| `0x8001F8B8` | Segment against primitive faces | 1,944 |

Each candidate separately produced a complete canonical executable before
promotion. The combined build then matched, followed by the clean rebuild.
The clean command selected only rules whose outputs lie under `build/`;
original assembly generation and source inputs were preserved.

The adaptations retain the original control flow, signed arithmetic,
halfword narrowing, SDK calls and expanded face-box acceptance. Their complete
function bytes and complete executable bytes agree with the original.
No instructions were patched after compilation.

The source is pinned to upstream commit
`90a398e4f429b4371be05648605fc198b9efb395`, specifically
`SceneNode__RaycastHullAgainstFaces` in `src/graphics/scene_node.c` and
`TmdModel__RaycastFaces` in `src/graphics/tmd_model.c`. Local names and types
were adapted to this project's existing interfaces. See
[attribution](../NOTICES.md) and the retained [CC0 text](../LICENSES/CC0-1.0.txt).

## Before and after

| Measure | Before the original request | Before this integration | Current |
| --- | ---: | ---: | ---: |
| Matching game C bytes | 169,540 | 197,172 | 199,912 |
| C percentage, corrected 199,912-byte denominator | 84.81% | 98.63% | 100% |
| Remaining game assembly functions | 63 | 2 | 0 |
| Provisional groups with listed core functions in C | 16 / 40 | 38 / 40 | 40 / 40 |
| Groups with listed core and shared-support functions in C | 0 / 40 | 6 / 40 | 40 / 40 |
| Original NPC callback bodies in C | 105 / 107 | 107 / 107 | 107 / 107 |
| Original groups present in the matching build | 40 | 40 | 40 |
| Independently accepted whole feature groups | 0 | 0 | 0 |

The original baseline used a 199,672-byte denominator. The later
[240-byte formatter classification](SAVE_LABEL.md) explains the corrected
denominator above; the baseline itself remains unchanged.

This integration adds **2,740 compiled C bytes**. Since the original request,
the corrected numerator has increased by **30,372 bytes**. These are source
reconstruction measurements. The matching build already inherited the original
game behavior in C plus assembly; no new original gameplay feature is claimed.

The exhaustive feature total is still unknown. Forty is the existing
provisional grouping, not an official count of everything in LSD. All listed
source dependencies being C does not establish exhaustive call-graph closure.
Historical inventory values remain intact; the current overlay is additive.

## Play and remaining verification

The existing matching-disc player remains usable. The newly compiled
executable is identical to the executable already stored in that immutable
disc, so rebuilding or duplicating the disc is unnecessary. No assets, player
saves, emulator UI, Bevy source or legacy checkout were changed.

The [cooperative year recorder](COOPERATIVE_FRAME_WAITS.md) subsequently completed
the separate [original/rebuilt natural-year comparison](NATURAL_YEAR_ENDING.md).
All retained observations agree across 365 completed days and the declared
12,000-frame ending window. That scoped result has its own runtime evidence.
Whole NPC encounters, complete native movie playback, rare input/card/error
branches, full history/content review and original-hardware timing retain their
existing gates. Original NPC behavior, separate AI-assisted development tools
and optional mods remain distinct.

The frozen objective's remaining completion requirements still apply. The
overall reverse-engineering and parity goal is unfinished.
