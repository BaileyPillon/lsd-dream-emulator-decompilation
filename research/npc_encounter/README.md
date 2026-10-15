# Recorded Hoop Girl and day-transition scenario

[observe.lua](observe.lua) is the exact script used for the
[30,000-frame original/rebuilt comparison](../../docs/NATURAL_HOOP_ENCOUNTER.md).
It drives ordinary controller inputs and reads MainRAM. It never writes game
memory or injects actors. It is a research scenario outside the matching build.

## Required local inputs

- The supported Japanese disc, canonical executable, and local BIOS files.
- The pinned BizHawk 2.11.1/Nymashock runtime recorded in the check metadata.
- The original window replay's frame-2400 save state: 1,220,532 bytes, SHA-256
  `8eb0bdd463e2deecaacc3f67f40429958b0a28e669bd8d38bb65c867f38297b6`.
- A new QA directory with its own configuration and save paths, separate from
  ordinary play. The recorded runs started with empty external QA SaveRAM.

The state is not distributed. This scenario expects map key 12 and its existing
Hoop Girl record at physical RAM `0x001C5DCC`, entity ID 71. It is not a general
navigator, a cold boot, or a game launcher. Use [PLAYING.md](../../docs/PLAYING.md)
for ordinary play.

The [QA helper](../../tools/start_runtime_qa.ps1) supports `-Script`, `-LoadState`,
`-Scenario play`, and `-Frames 30000`. Keep its runtime/save paths isolated.
The recorded pair used a private Python launcher with explicit private paths;
the PowerShell helper was not used for this pair. No execution-policy change
is required. The script reads `LSD_QA_OUTPUT` and `LSD_QA_FRAMES`.

## Controller fidelity

The recorder explicitly sets every digital control to false before adding that
frame's requested buttons. It records the starting controller definition and
every submitted value. Digital inputs use `joypad.set`; numeric values use
`joypad.setanalog`. The numeric controls retain their recorded starting values;
they are not inferred from their names. In this profile they were four stick
axes at 128 and a disc selector at zero, alongside 21 Boolean controls.

`submitted.tsv` also records the game's pre-frame pad held, released, and pressed
fields. Those are separate observations from the submitted input vector.
Numeric autoholds are cleared before exit, without advancing another frame.
See BizHawk's [Lua API](https://tasvideos.org/Bizhawk/LuaFunctions) and
[the 2.11.1 implementation](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Client.Common/lua/CommonLibs/JoypadLuaLibrary.cs).

The older expression `is_boolean and false or value` can preserve a true value
in Lua. This scenario uses an explicit conditional. Its
[standalone regression check](test_neutral.lua) extracts the actual production
helper and checks five input shapes plus the old expression as a failing control:

```sh
lua5.4 research/npc_encounter/test_neutral.lua
```

Run from the repository root. This pure helper check does not load a game or
call emulator APIs. It is separate from the Python tooling CI suite.

## Outputs and interpretation

The controller log has 30,000 rows; submitted values have another 30,000 rows.
Scene/NPC fields are sampled every 30 emulator frames. Full MainRAM, PNGs, and
save states are captured at zero and each 3,000-frame checkpoint. A completion
marker is written only after the requested loop finishes.

Actor vtable bytes alone do not establish liveness. Registered samples also
require the expected entity ID, dream owner, context state/owner, callback
binding, and advancing ticks. `dream_object_layout_valid` means the retained
DreamSys layout passed the observer's checks; it does not prove an active world
after the dream ends. Raw game content and captures stay private.

## Earlier window-to-Hoop route

[window_hoop_chain.lua](window_hoop_chain.lua) is the exact script from the
[15,000-frame timing follow-up](../../docs/NATURAL_HOOP_TIMING.md). It uses the
same explicit neutralization and complete input logging, first targeting the
window in map 3 and then Hoop Girl in map 12. After Hoop Girl activates, it
requests no further buttons. The original recorder above remains unchanged.

This route requires the original Japanese play run's frame-4800 state, not
the later frame-2400 window-result state used above. Its size and SHA-256 are
recorded in [the timing metadata](../../docs/natural-hoop-timing-checks.json).
The recorded frame limit is 15,000, with six full checkpoints every 3,000 frames.
Use fresh isolated QA/save directories and the same pinned runtime/input rules.

The existing pure check can extract the helper from this script too:

```sh
lua5.4 research/npc_encounter/test_neutral.lua research/npc_encounter/window_hoop_chain.lua
```

Registered post-threshold fields are observed; direct instruction entries,
every RNG choice, complete encounters, audio, and cold boot are not accepted.

## Hoop Girl boundary continuation

[hoop_boundary.lua](hoop_boundary.lua) is the exact corrected recorder from the
[frame-level boundary comparison](../../docs/HOOP_BOUNDARY.md). It requires
the earlier route's **frame-12000** save state, whose identity is recorded in
[hoop-boundary-checks.json](../../docs/hoop-boundary-checks.json). The original
route reached and activated this actor through ordinary controller inputs.

Run for 1,800 frames in fresh isolated original/rebuilt QA profiles with the
same verified Japanese content, runtime, BIOS, configuration, and state. All
Boolean inputs are false; numeric values retain their recorded baseline.
The recorder checks the specific state's actor and context bindings every
frame. It rejects a different layout instead of scanning for a substitute.

The observer writes `boundary.tsv` and all input values in `submitted.tsv`.
It captures complete MainRAM, PNG, and state files at zero, the first observed
ticks 2,399 through 2,403, and the final frame. `captures.tsv` identifies those
seven checkpoints. The pure helper checks run without a game:

```sh
lua5.4 research/npc_encounter/test_neutral.lua research/npc_encounter/hoop_boundary.lua
lua5.4 research/npc_encounter/test_boundary.lua
```

The earlier route's RAM snapshot and the resumed initial snapshot differ by
645 bytes, while the new original/rebuilt pair agrees completely. Preserve
that distinction when interpreting continuation. The first malformed-column
attempt is excluded. This remains a warm-state boundary observation without
direct callback tracing, complete encounters, or audible-output acceptance.
