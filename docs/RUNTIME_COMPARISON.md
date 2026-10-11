# Original/rebuilt runtime comparison

This developer workflow records an emulator-local input sequence, then compares
the original disc with a separately packaged matching build. It preserves the
original game and measures only the recorded scenario. Optional mods require
their own scenarios and outputs.

## Inputs and outputs

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
43 fields on every frame, including inputs, timer, locks, movement, floor,
position, scale and angles. It writes no game memory.

When `movement.tsv` is present, the comparator requires it in both runs, with
every scheduled frame and every field, and compares its complete bytes. Equal
screenshots cannot hide a changed position or an incomplete native-state trace.
Phase names describe the requested controls; the recorded state establishes
which behavior actually occurred.

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
