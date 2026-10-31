# Isolated PS1 replay host

`RecordCardDecodeCompactWindows.cs` extends the prepared-card host with lossless,
bounded native stream/VLC/MDEC entry records, using an existing qualified observer.
The [decoder guide](../../docs/NATIVE_REEL_DECODER.md) distinguishes source-prefix
attribution, MDEC input calls, full native payload hashes and frame presentation.

`RecordCardReelWindows.cs` cold-loads a separately prepared QA card through the
supported SaveRAM service, then uses the native Load UI, dream and graph/reel
route. Its [fixture and comparison guide](../../docs/CARD_REEL_PLAYBACK.md) keeps
constructed history separate from naturally earned gameplay and all-film decode.

`ReplayColdStart.cs` is the optional Windows frontend built by
[`tools/replay_cold_start_headless.py`](../../tools/replay_cold_start_headless.py).
It runs the supplied BizHawk PS1 core with recorded controller inputs and
exports complete game-output observations for comparison.

See [the replay guide](../../docs/HEADLESS_REPLAY.md) for prerequisites, verified
profiles, image/audio boundaries and reproduction. The canonical game build
and original NPC behavior remain in the matching C project. No emulator binary,
game data or BIOS is included here.

`RecordNpcHistory.cs` records a separate static controller program using the
same disc, BIOS and controller helpers. `NpcInstructionTrace.cs` optionally
reads the native observer's original NPC-entry events. The published
`buddha-timed-route.json` supplies a fixed 30,000-step route; it does not adapt
inputs from observations. See [NPC entry tracing](../../docs/NPC_ENTRY_TRACE.md)
for the separate observer build, recording commands, comparison modes and
qualified history. The default cold-start replay remains a separate command.

`RecordMovieWindows.cs` reuses the controller/disc/BIOS helpers and streamed
state-hash sink to record bounded cold-start movie windows. It hashes complete
RAM/GPU/RGB/PCM each advanced frame and retains compressed native fields. See
[cold movie playback and skips](../../docs/COLD_MOVIE_WINDOWS.md) for build
inputs, argument order, bounds and the independent Python checker. The three
qualified routes preserve the canonical game and existing player.

`RecordOpeningAttract.cs` extends the neutral cold movie observation through
repeated title-menu attract cycles, stopping after all seven opening choices
clear and a 180-frame post window. Its streaming saved-data reader and explicit
incomplete-attempt boundary are documented in
[all seven opening choices](../../docs/OPENING_ATTRACT.md).
