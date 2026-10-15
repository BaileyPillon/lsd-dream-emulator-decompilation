# Recorded memory-card round trip

[save.lua](save.lua) and [load.lua](load.lua) are the exact executed observers
for the [persisted-card profile](../../docs/CARD_ROUNDTRIP.md). They submit normal
controller input and read the original game; they make no game-memory writes.
The capture launcher is [tools/capture_card_roundtrip.py](../../tools/capture_card_roundtrip.py).

## Starting context

Save requires the naturally reached day-two dream chart from the original
[30,000-frame Hoop Girl route](../../docs/NATURAL_HOOP_ENCOUNTER.md), at that
route's frame 30,000. The recorded warm state is 1,147,400 bytes, SHA-256
`62992592fa8ffdd8ce730d60410a7d3bbd57be957e207a3d82c87c7f36fea686`.
The state and original content are private and are not distributed.

The observer follows the original flow, dream, graphics, and pad bindings.
It finds a unique screen record in the reviewed heap range using both dream
and graphics ownership, rather than accepting a vtable pattern alone. The
original main-menu indices are Save 2 and Load 3. Digital pulses last twelve
emulator frames with a 120-frame period; all other digital values are false,
and numeric controls retain their recorded baseline. Circle is represented by
an ASCII Lua Unicode escape to preserve its name across Windows text handling.

Load starts cold, with a copy of the saved raw card and no `--load-state`.
It uses Circle to skip startup and selects slot 01. The complete loaded buffer,
stored day, new-game flag, persisted card, and backup are checked separately
from the observed UI state. The two recorders are fixed research scenarios,
not a general navigator or an interactive game launcher.

## Evidence and preservation

The Save phase advances 2,400 frames and Load advances 6,000. Both write
`card.tsv`, `submitted.tsv`, `input-definition.tsv`, and `captures.tsv`. Native
tables and complete GPU hashes are recorded at every frame boundary. Scheduled
and card/screen-transition checkpoints preserve full RAM, GPU, PNG, and state.

Use fresh isolated QA directories. The launcher pins disc layouts/tracks,
runtime/core files, BIOS, settings, observer, and starting state. Cold Load also
retains its input card. Exit saves are moved only from the launcher's new owned
save directory into that capture after exit, with exact byte verification.
Ordinary play profiles and sessions are untouched.

The verifier checks the actual per-frame control route and native operation
flags, rereads checkpoint object words from full RAM, and compares every state
member without masks. It requires that the cold-load seed card came from the
paired save files. Missing and malformed records fail; output differences
remain differences. No audio capture or direct callback hook is used.

The [metadata](../../docs/card-roundtrip-checks.json) distinguishes the first
successful private launches, their repeated portable-launcher runs, rejected
diagnostics, synthetic tooling tests, and unchanged source/feature counts.
Raw game/save data, generated images, complete traces, and emulator states
remain private. This profile adds no generative AI or optional gameplay changes.
