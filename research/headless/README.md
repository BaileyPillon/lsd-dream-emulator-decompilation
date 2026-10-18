# Isolated PS1 replay host

`ReplayColdStart.cs` is the optional Windows frontend built by
[`tools/replay_cold_start_headless.py`](../../tools/replay_cold_start_headless.py).
It runs the supplied BizHawk PS1 core with recorded controller inputs and
exports complete game-output observations for comparison.

See [the replay guide](../../docs/HEADLESS_REPLAY.md) for prerequisites, verified
profiles, image/audio boundaries and reproduction. The canonical game build
and original NPC behavior remain in the matching C project. No emulator binary,
game data or BIOS is included here.
