# Original polygon and mode runs

The original drawer now agrees with independent complete-buffer predictions in
**374 additional calls**, processing **2,122 polygons in 1,159 mode runs**.
The earlier 1,147 single-primitive/recursive calls also pass with the extended
oracle. Together these are 1,521 constructed draw calls, with no game-code,
asset or player change and **zero** new whole-feature/NPC acceptances.

This closes a bounded verification gap between isolated polygons and shared-state
streams. It does not verify every renderer input, the original disc-model drawing
corpus, natural scenes, replacement matrices, GPU pixels or hardware timing.

## Executed evidence

| New run-profile measurement | Result |
| --- | ---: |
| Original draw-entry calls | 374 |
| Original mode-run entries | 1,159 |
| Original polygon setup calls | 2,122 |
| Submitted ordinary packets | 1,617 |
| Backface/degenerate polygons | 258 |
| Fog/depth-cue rejected polygons | 39 |
| Polygons submitting recursive packets | 156 |
| Polygons culled at recursive entry | 52 |
| Recursive body entries | 520 |
| Emitted subdivision packets | 1,560 |
| Original MIPS instructions | 836,221 |
| Actual native GTE commands | 9,888 |
| Hidden/empty invocation checks | 13 / 1 |
| New original-code faults detected | 3 |

The [run report](tmd-primitive-run-checks.json) and
[1,147-call regression report](tmd-primitive-run-regression-checks.json) pin
executed sources, the original executable, native bridge/backend, instruction
ranges, controls and private journal hashes. The original
[subdivision report](tmd-subdivision-checks.json) remains a historical checkpoint.
The separately qualified [3,333-case GTE report](gte-packet-state-checks.json)
is reused unchanged; no additional native host or game/runtime tree was needed.

The profile exercises all 13 supported format/flag pairs, 2/3/7-member repeated
runs, mixed-format streams, 64-member triangle runs, both pointer aliases,
transparency transitions, two explicit normals, distinct packet colors/UVs,
random ignored interior header halfwords, fog rejection, and culled members
before, between and after submitted members. Forty-eight seeded mixed streams
extend the fixed fixtures. Eight recursive families share buffers across members
and mode changes at subdivision limits 1–2. The retained earlier profile
continues to exercise individual recursive calls through limit 5 and all five
recursive culling directions.

## State retained between members

The SDK groups consecutive primitives by their exact mode byte. A run's first
header contains its count; interior count halfwords are ignored. The fixture
builder reproduces that layout. The profile requires compatible flags within a
same-mode run and rejects unsupported flag mixtures instead of inventing a
flag-aware linker. This is an explicit fixture-domain limit.

Run initialization and per-member projection have different write effects.
Every projected member stages the GPU length byte; a later culled member can
leave an old command byte in the next output slot. Textured lit runs initialize
RGB once at the run boundary. Resetting it for each member would add transfers
that single-polygon cases cannot reveal. RGB/SZ FIFO state, geometry references,
normal selection, output cursor, OT links and recursive workspaces remain shared
through the entire invocation, including calls that change polygon family.

The scalar model predicts the complete 64 KiB GPU arena, 4 KiB OT, 4 KiB
scratchpad, 536-byte triangle and 1 KiB quad arenas, fixed globals, all 64
architectural GTE words, command order and native command/data-write counts.
Actual original mode, polygon, recursive-wrapper/body/emitter and culling-return
entries are counted separately and compared with those predictions. Saved
registers and VM bytes outside declared mutable spans remain guarded.
Bounded callee stack temporaries are permitted writes without independent byte
prediction; supplied arena sizes do not prove the game's allocator limits.

Three analysis-only original-instruction controls break GPU cursor advancement,
the inner-loop condition and textured-run RGB initialization. All return with
saved ABI/immutable-memory guards intact and all are detected. The last control
preserves compared buffers, final GTE words and command sequence but adds a
native data write: the independent transfer counter catches it. The four prior
draw controls also pass in this profile. The regression run retains the five
prior recursive controls; there are twelve distinct original-code controls
across the two profiles.

## Reproduce

Use the existing optional Unicorn 2.1.4 environment and the twelve-command
native GTE host described in the [draw-entry guide](TMD_RENDERER.md). Each profile
requires its own fresh output directory:

```powershell
python -B tools/verify_tmd_renderer.py --executable rom/SLPS_015.56 --bridge .decomp-lab/gte-packets.exe --runtime "D:/tools/BizHawk-2.11.1" --primitive-runs --output .decomp-lab/tmd-runs
python -B tools/verify_tmd_renderer.py --executable rom/SLPS_015.56 --bridge .decomp-lab/gte-packets.exe --runtime "D:/tools/BizHawk-2.11.1" --recursive --output .decomp-lab/tmd-regression
python -B -m unittest tests.test_tmd_renderer_model tests.test_tmd_recursive_model -v
```

The two profile switches are mutually exclusive so each retains its own
15-minute/2 MiB output bounds and one-million-instruction call ceiling. Private
journals are losslessly sealed with full-hash checks and exact-path recovery.
CI runs literal packet/history tests and synthetic guarded-transfer checks
without game assets. The analysis host loads no game or BIOS and does not
attach to the player or the independent full-year replay.

Original NPC behavior, optional mods and AI-assisted tools remain separate.
This verification adds no gameplay modification or model API call.
