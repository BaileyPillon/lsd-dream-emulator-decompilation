# Original/rebuilt runtime comparison

The [persisted-card profile](CARD_ROUNDTRIP.md) adds a separate 2,400-frame
Save pair and 6,000-frame cold-Load pair. All 34 RAM/GPU/image/state checkpoints
and persisted card files agree, and the complete 1,792-byte game save buffer is
restored after restart. Its fixed recorders, isolated capture command and
dedicated comparator preserve the distinction between a warm starting Save,
cold boot for Load, repeated checks, and whole-card/feature acceptance.

The [empty-card Load investigation](EMPTY_CARD_LOAD.md) adds an explicit
not-found case. Its game buffers and controller records agree, but eight
core-state bytes differ. The [accessor extension](NYMASHOCK_STATE.md#empty-card-extension-and-native-accessors)
locates all eight in the emulator's unused media-label capacity, confirms the
same difference with repeated boots of each disc, and executes the original
string accessors. The full-state gate remains unsuccessful; these observations
do not extend the successful round-trip result to all card paths.

This developer workflow records an emulator-local input sequence, then compares
the original disc with a separately packaged matching build. It preserves the
original game and measures only the recorded scenario. Optional mods require
their own scenarios and outputs.

## Inputs and outputs

The [startup movie profile](MOVIE_PLAYBACK.md) is a separate recorder and
comparator. It preserves a full GPU-memory SHA-256 at every observed frame,
native movie/stream words, controlled neutral inputs, complete checkpoint state,
and PCM. Use its dedicated launcher to isolate SaveRAM and its dedicated
comparator to distinguish stream setup from playback. Its one shared-state
trajectory does not accept all movies, startup branches, or whole-game parity.

`tools/start_runtime_qa.ps1` freezes the Lua script and optional starting state,
then hashes the CUE layout and all referenced binary tracks, the emulator/core
files, all three regional BIOS files, and a snapshot of the launch settings.
These identities are written before launch. BizHawk's mutable configuration
file is separate from the frozen configuration input. Equivalent JSON member
order and different track filenames are normalized; different values, content,
track order or directives are rejected.

Each run uses a new output directory. The launch helper starts BizHawk hidden
at below-normal priority, without sending keyboard input to another window.
Its temporary QA environment variables are restored after launch. Desktop
sound is disabled; `-CaptureAudio` requests core audio through BizHawk's WAV
writer. The dump frame limit finalizes the WAV before the Lua script exits.

The comparator requires completed runs, the expected checkpoint set and
matching traces. It compares PNG bytes, full GPU-memory bytes, and every
save-state ZIP member payload. ZIP wrapper timestamps can differ. When audio
was requested, it also requires valid, nonempty 16-bit PCM WAVs and compares
channel count, rate, width, sample count and PCM bytes. Truncated captures and
changed input files fail. Legacy runs without input manifests are labeled
explicitly and cannot be described as having verified launch inputs.

## Running a pair

Build with `ninja check`, then package the matching executable into a new disc
using `tools/package_disc.py`. Use the same scenario, frame count and starting
state for both runs. For example, in PowerShell:

```powershell
.\tools\start_runtime_qa.ps1 -EmulatorRoot 'C:\Tools\BizHawk' `
  -BiosRoot 'C:\Private\PSX-BIOS' -Cue 'C:\Games\LSD\original.cue' `
  -Output 'D:\QA\lsd-original-new' -Scenario play -Frames 6000 `
  -LoadState 'D:\QA\lsd-boot\frame-1800.State' -CaptureAudio
.\tools\start_runtime_qa.ps1 -EmulatorRoot 'C:\Tools\BizHawk' `
  -BiosRoot 'C:\Private\PSX-BIOS' -Cue 'D:\QA\lsd-rebuilt.cue' `
  -Output 'D:\QA\lsd-rebuilt-new' -Scenario play -Frames 6000 `
  -LoadState 'D:\QA\lsd-boot\frame-1800.State' -CaptureAudio
```

`-EmulatorRoot` and `-BiosRoot` are required; choose your installed tool and
firmware directories. Set `-Python` if Python is not on PATH. Wait for both `completed.txt` files and emulator exit so the WAV
headers are finalized, then compare into a new result file:

```powershell
python tools/compare_runtime.py --original 'D:\QA\lsd-original-new' `
  --rebuilt 'D:\QA\lsd-rebuilt-new' `
  --output '.decomp-lab\runtime-comparison-new.json'
```

`boot` is a separate scenario and can start cold without `-LoadState`.
`play` follows the scripted menu/movement sequence in `tools/runtime_smoke.lua`;
it is not a general game-playing agent.

For a saved in-dream state, `-Script tools/runtime_movement_probe.lua` selects
a separate read-only native-state probe. Pass an absolute script path when
launching outside the repository. The helper freezes and hashes the selected
script just like the default script. The probe validates the original game-flow
and dream-system virtual tables before following their pointers and records
47 fields on every frame, including inputs, timer, locks, movement, floor,
position, scale, angles and the original pad's held/pressed/released masks.
It also validates the original pad virtual table. It writes no game memory.

When `movement.tsv` is present, the comparator requires it in both runs, with
every scheduled frame and every field, and compares its complete bytes. Equal
screenshots cannot hide a changed position or an incomplete native-state trace.
Phase names describe the requested controls; the recorded state establishes
which behavior actually occurred. Historical complete 43-field captures are
still supported; both sides must use the same complete header. Phase summaries
separate requested controls, the three original input guards, and native pad
observations. Repeated edge samples are counted as frames, not distinct events.
The current probe uses twelve-frame pulses every twenty emulator frames; see
the [controller-poll evidence](MOVEMENT_PARITY.md) for the measured shorter
pulses that missed native polls or never reached a held-input command.

## Current evidence and limits

`.decomp-lab/runtime-pinned-audio-play-comparison.json` records a successful
6,000-frame pair with 100 trace samples and 13 image/GPU/state checkpoints.
It also records identical 4,422,823 stereo sample frames at 44,100 Hz, with
7,732,155 nonzero channel samples. PCM SHA-256:
`91dbf5893683e4fa916985d7dcf9c26c379c3197b5f09e137259044fd8e3c994`.
The complete WAV files are byte-identical too. The input manifests verified
the original and rebuilt track contents and the remaining launch identities.

That earlier comparison uses English v1 assets with the canonical Japanese
executable. Its historical reports remain preserved. Their schema-one launch
manifests omitted the actual Nymashock core and Waterbox host binary hashes;
the current comparator labels that identity incomplete. This replay does not
establish every scene/NPC/state/RNG branch, every sound/movie event,
memory-card error, or original hardware timing. The feature inventory keeps
entire feature-group acceptance separate from this successful replay.

The corrected native movement pair is
`.decomp-lab/runtime-movement-0209-comparison.json`. It compares 1,800 additional
frames from the same frozen in-dream state, six image/GPU/state checkpoints,
1,800 complete native-state records per run and 1,326,847 stereo PCM sample
frames. All recorded outputs agree. Walking forwards/backwards, turning,
looking, left/right movement states and tapped inputs are observed in stage 3;
this does not cover every stage, surface, NPC, control mode or movement branch.
The first diagnostic probe's mislabeled scale-as-position columns are preserved
in its private outputs and are not used as position evidence.

## Japanese edition and actual core identity

The [Japanese edition supplement](JAPANESE_EDITION.md) records a separate
6,000-frame replay with Japanese assets and the original Japanese starting
state. The current launcher explicitly selects Nymashock, whose native core
is `dll/shock.wbx.zst`, and hashes it and `dll/waterboxhost.dll` before launch.
Schema-two manifests require both binary identities and the explicit core
selection. Older schema-one manifests remain readable, with an explicit
`legacy_core_identity_incomplete` status and `inputs_verified: false`.

No comparison masks decoded state bytes. The initial Japanese cold-boot pair
has eight differing bytes in each decoded Waterbox snapshot despite equal
visual, GPU, trace and audio outputs. The repeated schema-two original/rebuild
cold pair agrees, but a further same-original cold boot has the eight decoded
differences again. The field was unresolved at that checkpoint. The schema-two
6,000-frame shared-state pair agrees at every recorded checkpoint and across
all 4,422,823 stereo PCM sample frames. Report hashes and these separate
results are in [japanese-edition-checks.json](japanese-edition-checks.json).

The later [Japanese movement supplement](MOVEMENT_PARITY.md) adds four
shared-state pairs, totaling 9,000 emulator frames and 27 checkpoints per side.
Original native pad fields distinguish missed one-frame pulses, pressed-only
eight-frame pulses and effective twelve-frame pulses. All recorded native,
image, GPU, state and PCM outputs agree; whole-feature acceptance remains open.

The later [Nymashock state diagnosis](NYMASHOCK_STATE.md) follows the actual
native pointer graph and identifies all eight varying bytes as unused storage
in the short `"CD"` media-type label. Its native insertion path copies those
bytes with the full 24-byte object. The read-only tool checks 44 checkpoint
pairs without masking, normalization or changes to this strict comparator.
The 12 nonidentical decoded comparisons remain nonidentical. This explains
the observed host field; it does not accept further gameplay scenarios or
repair the older incomplete launch identities.

The separate [native world-position composition](RENDER_POSITION.md) executes
the original lookup chain with grid generation and streaming under two GTE
contracts. It strengthens bounded native behavior evidence; it does not
replace paired emulator runs, scene coverage or original-hardware timing.

The later [rotation composition](RENDER_ROTATION.md) executes the original
SDK helper with the canonical table, leaving one `ApplyMatrixLV` hardware
contract. Its native fixtures strengthen rotation/streaming evidence while
paired emulator scenes and actual GTE/timing acceptance remain separate.

The subsequent [native GTE composition](RENDER_GTE.md) executes original
`ApplyMatrixLV` using the checked Nymashock command routines and an explicit
COP2 transfer adapter. The eleven-function chain now has zero function-output
stubs across its 13,230 distinct fixtures. Bounded MAC, IR and flag arithmetic
is verified on that core; complete PS1 CPU scheduling, original hardware and
paired natural-scene comparisons remain separate gates.

## October 15 matching-build replay

A fresh 1,800-frame original/rebuilt replay starts from the same preserved
in-dream state and exercises looking, turning, shoulder inputs, walking, running,
release gaps, and repeated button presses. The recorded movement table has 47
columns per frame, including 43 MainRAM-derived values and four timeline/input
columns. Native pad held/pressed/released state is included.

All recorded tables, six PNG/GPU/save-state checkpoints, and the captured stereo
PCM agree. The audio contains 1,326,847 stereo sample frames at 44.1 kHz and
16 bits, with 2,651,450 nonzero channel samples. Both runs have verified schema-2
input manifests, identical disc contents/layout, BIOS and core identities,
configuration, script, and starting state. The current executable is canonical.

[play-build-checks.json](play-build-checks.json) pins this bounded result and
the isolated [interactive play launcher](PLAYING.md). A saved-state replay is
separate from cold-boot determinism, natural encounters, physical card behavior,
and acceptance of complete feature groups. Those gates remain open.

## Natural window-link scenario

The [window integration profile](NATURAL_WINDOW_LINK.md) compares 2,400 frames
of ordinary controller input, registered window behavior, a map transition, and
subsequent updates. All controller and NPC/scene rows agree, as do full MainRAM,
PNG bytes, and every save-state member payload at five checkpoints. This profile
does not capture separate GPU dumps or audio and does not use this guide's
standard trace format; its private comparison producer is pinned in the profile
metadata. Direct callback entries and whole-feature acceptance remain open.

## Natural Hoop Girl and later screens

The [Hoop Girl profile](NATURAL_HOOP_ENCOUNTER.md) extends a controller-only
scenario to 30,000 frames, registered NPC ticks, a day-field change, movie
imagery, and the dream chart. All submitted controller values, recorded game
pad fields, NPC/scene tables, and eleven full memory/image/save-state checkpoint
pairs agree. The revised recorder explicitly clears digital buttons and records
numeric baselines. This warm-state scenario captures no audio and ends the
dream before the NPC's tick-2,401 branch; complete encounter and feature
acceptance remain open.

## Preserve the saved-state observation boundary

The [synchronous replay investigation](STATE_REPLAY_BOUNDARY.md) reproduces the
earlier Hoop Girl resume's extra observed frame and 645 changed RAM bytes.
Loading the same state from Lua before the observer starts preserves the source
frame, full RAM and every state-member payload. A new 1,800-frame original/rebuilt
pair agrees on all observations and seven complete checkpoints.

Use `tools/capture_state_replay.py` with a self-contained observer and a fresh
workspace. It pins the complete generated script and state, stages isolated save
paths, and runs both discs in sequence. The launcher captures outputs; the
profile-specific comparison remains necessary. This one warm-state result
does not close cold-boot, full encounter, content, audio or timing gates.
