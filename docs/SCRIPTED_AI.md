# Original scripted callback checks

`tools/verify_native_ai.py --callback scripted` runs original MIPS code for nine
timed and input-driven callbacks against separate Python reference rules.
The canonical game and its NPC behavior remain unchanged; the verifier is a
local developer tool and makes no model API calls.

## Measured coverage

The current report passed 4,408 cases and detected one deliberately wrong
instruction per callback. The original property table independently binds each
checked function to the listed entity record.

| Original callback | Entity record | Cases | Covered decisions |
| --- | ---: | ---: | --- |
| Bird | 24 | 42 | Signed fifteen-tick command cadence, scale/rotation and forward-motion requests |
| Rocket | 25 | 140 | Three-tick cadence and phase boundaries at ticks 100 and 300 |
| Horse | 26 | 504 | Duration-based cadence and the tick-110 lateral-motion change |
| UFO | 27 | 140 | Seventy-tick commands and vertical-motion boundaries at 100 and 301 |
| Dog | 68 | 2,880 | Original RNG, signed command cadence, actual action-pressed reads, state 0/10 transitions and stop behavior |
| Can | 83 | 240 | Fifteen-frame commands, duration equality, stopping and state update |
| Car in water | 84 | 84 | Frame boundaries 40, 45, 64 and 89, trigger ratios and stopping |
| Walking fetus | 95 | 48 | Initial/completion motion selection and variant-dependent motion |
| Jumping fetus | 96 | 330 | Original RNG motion selection, duration remainders and command payloads |

Fourteen distinct original routines actually execute. These include all nine
callbacks, the original RNG, the action-pressed getter, behavior-stop code and
two downstream animation/model flag setters. A range being hashed does not
itself establish entry or branch coverage; the report records actual entry
counts separately.

Entire entity, dream-system and command buffers are compared, along with the
final RNG seed, ordered external calls, stack restoration and saved registers.
The contracts clobber volatile registers to expose incorrect ABI assumptions.
Eight controls redirect a command store to the wrong slot. The ninth changes
the walking-fetus motion selection. Each control must disagree with its model
in a recorded fixture; changes exist only in private Unicorn memory.

## Reproduce

After a current canonical matching build, in the configured Linux/WSL environment:

```bash
python -m pip install -r requirements-analysis.txt
python tools/verify_native_ai.py --callback scripted \
  --output .decomp-lab/scripted-ai-native-new.json
```

Choose a new output filename. The verifier checks the canonical executable,
current build, function addresses, native range hashes and source dependencies
before and after execution. It also checks each original callback binding in
`g_ENTITY_TABLE` rather than relying on a source label alone.

The latest exercised report is `.decomp-lab/sound-api-scripted-proof-first.json`;
its SHA-256 is
`c78424c703fa8468514bdc95838829f6c0e76070ca313d7617ca66ef0ee67c8b`.
The report and original inputs stay private. A metadata supplement in
[features.json](features.json) records the measured counts and source hashes.
Earlier reports remain preserved. This report rechecks the current build after
the [sound API correction](SDK_SIGNATURE_AUDIT.md). The Lion and Gray Man reports were
also rerun against this snapshot, passing 1,608 and 768 cases and detecting
three and two controls respectively. The SDK/API supplement records their
hashes and source dependencies separately from the initial publication.

## Acceptance limits

These fixtures use explicit contracts for geometry/orientation, scale,
translation and motion, animation selection, trigger ratios and sound.
Behavior-stop checks use empty actor-child lists. They do not independently
verify natural encounter reachability, realistic construction/lifetime
histories, visible movement, actual audio, renderer/GTE output, zero-duration
division traps, devices or PlayStation instruction/cycle timing.

Adding these nine callbacks to the Lion and Gray Man checks increases bounded
coverage from 2 to 11 of 107 callbacks and from 2,376 to 6,784 fixture cases.
The callback extension leaves C recovery unchanged. The subsequent save-title
split corrects the game-byte classification as documented separately; the seven
known remaining game assembly functions still remain. Whole-callback acceptance
and whole-feature acceptance remain zero.
This extends an existing analysis capability; it adds no original-game or
optional gameplay feature.
