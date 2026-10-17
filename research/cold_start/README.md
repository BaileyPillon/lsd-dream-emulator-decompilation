# Cold-start controller observation

[observe.lua](observe.lua) records the original Japanese boot/menu/new-dream
path using ordinary emulator-local controller input. It never restores a
state, injects entities or writes PlayStation memory. The
[profile guide](../../docs/COLD_START.md) records the comparison and its limits.

`tools/capture_cold_start.py` copies this exact observer into fresh private
profiles, pins its bytes and complete launch inputs, and runs the two discs
sequentially. `tools/compare_cold_start.py` requires the observed path, native
movement changes and full checkpoint consistency. It retains raw state
differences and returns a failure result when state members disagree.

Field provenance is the canonical symbol table and these recovered interfaces:

- `src/game/game_flow.h`: global flow, graphics and dream ownership.
- `src/menu/main_menu.h`: menu type, dream binding and selected item.
- `src/dream/dream_session.h`: session type, dream binding, map and state.
- `src/scene/map_scene.h`: map-scene type.
- `src/dream/dream_sys.h`: transform, timer, input lock, map, day and new-game flag.
- `src/base/transform.c` and `src/sys/pad.h`: pose and native controller fields.

Per-frame reads are observations at emulator boundaries. Object bindings and
full RAM checks provide bounded evidence; they do not establish direct callback
entries, every rendered frame, full camera behavior or complete encounter and
feature acceptance. Keep discs, BIOS, RAM dumps, screenshots, states, PCM and
owned saves private.
