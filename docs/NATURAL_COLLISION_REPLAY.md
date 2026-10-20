# Natural collision replay calibration

The collision replayer executes original MIPS from retained natural call-entry
snapshots and compares its result with the captured return. It checks complete
2 MiB RAM, all 35 CPU registers exposed by the functional backend, all 64
architectural GTE register views, and the recorded instruction count. Every
difference remains in the result.

This extends the [194-call hull boundary comparison](HULL_CALLS.md). It uses the
existing recordings and creates private analysis reports, without controlling
the running game or recording another controller history. Matching C remains
**197,172 / 199,912 bytes (98.6294%)**, with two assembly functions and three
unresolved inherited storage explanations.

## Verified route

| Observation | Result |
| --- | ---: |
| Original hull calls replayed | 194 |
| Calls matching full RAM, 35 CPU words, 64 GTE views and instruction count | 174 |
| Calls retaining comparison failures | 20 |
| Calls matching all 64 GTE views | 194 |
| Nested original primitive calls executed | 484 |
| Native OP / SQR / LZCS operations | 11,333 / 5,714 / 5,714 |
| New matching C bytes / accepted whole-feature groups | 0 / 0 |

All 20 failures span a frame boundary. Their CPU differences are in `K0`, and
the captured `K0` equals the captured exception PC. Their original instruction
spans are longer, and kernel RAM differs. These observations are consistent
with interrupt activity that the functional replayer does not schedule. The
failures are retained; those RAM regions and registers are never excluded.

The later [exception-context investigation](COLLISION_EXCEPTIONS.md) checks
the pinned core's CAUSE encoding and original instruction PCs for all 20
affected calls. One branch context has 144 compatible taken occurrences and
48 alternative fallthrough occurrences. All 20 also have RAM differences
beyond low kernel memory. The diagnostic preserves the same strict failures;
interrupt delivery, callback execution and device scheduling still require
recovery.

The earlier geometry inspector independently reconstructs the same 484 nested
queries and 11,333 polygon visits. Addresses and visits are observations in one
history, rather than unique assets, NPCs or game features.

## State and execution boundaries

The observer supplies 37 architectural CPU words. Unicorn exposes the 32 GPRs,
LO, HI and status register used here; CAUSE and EPC remain unmeasured by the
replayer. A pending load in the caller's delay slot is rejected because its
pipeline state is not reconstructed. General PS1 load-delay behavior, caches,
device scheduling, interrupts and original-hardware timing remain open.

GTE OP, SQR and LZCS operations use the checked native Nymashock bridge. The
adapter carries forward unchanged captured views, applies reviewed register
transfers and derives IRGB/ORGB readback from IR1..3. It does not restore the
complete native GTE or its opaque execution state. The report distinguishes
these views from a full native state replay.

Execution stays within complete, hash-qualified original function ranges.
The canonical executable, current matching build, retained capture payloads,
verifier sources and bridge are checked. Each completed machine releases its
instruction callback. Output must be a fresh private directory outside the
retained recordings.

## Reproduce with local inputs

Use a current matching build and the optional dependencies in
`requirements-analysis.txt`. Compile the native bridge using the instructions
in [RENDER_GTE.md](RENDER_GTE.md). The verified execution uses WSL Python with
Windows executable interoperation and a local BizHawk 2.11.1 installation.

From the checkout root in WSL:

```bash
python tools/replay_collision_calls.py \
  --collection /path/to/hull-collection/collection.json \
  --bridge /path/to/private/gte-bridge.exe \
  --runtime 'D:/Private/BizHawk-2.11.1' \
  --lab-root /path/to/private-artifacts \
  --output /path/to/private-artifacts/hull-replay-new
```

The artifact root must already exist. Pass the runtime directory in Windows
form to the Windows bridge. The default collection side is `reference`;
`--side candidate` selects the retained rebuilt recordings. Alternatively,
repeat `--recording /path/to/recording` for individual captures.

`--max-calls N` limits execution and reports how many captured calls were
skipped. All declared recordings are still inspected. A limited passing result
establishes calibration only for its selected calls.

`--trace-exceptions` adds pinned-core CP0 interpretation and bounded functional
PC observations. It rejects unsupported observer CPU-source provenance and
does not alter the state comparison or deliver interrupts. See
[captured exception contexts](COLLISION_EXCEPTIONS.md) for the verified scope.

The command writes per-call differences, capture-inspection summaries, an
ordered native-command log and a pinned aggregate report. Exit codes are:

- `0`: every selected call agrees on the measured state and instruction count.
- `1`: replay completed with retained call differences. The verified complete
  194-call route has this result because 20 calls differ.
- `2`: inputs or execution prerequisites could not be qualified.

Original disc data, executables, BIOS, RAM snapshots and native-command logs
remain private. C promotion continues to require the existing complete-image
matching gate.

## Validation and source investigation

Synthetic tests execute generic MIPS instructions without game or BIOS data.
They check virtual-PC preservation across COP2 transfers and nested JAL,
hidden stack writes, kernel scratch-register comparison, unfinished calls and
unreviewed control transfers. Input tests reject incomplete state, escaping
collection paths and output inside retained recordings. A runner fixture
checks a one-call limit across four recordings without overwriting inspections.
The Ubuntu/Python 3.13 CI job installs the pinned optional Unicorn backend so
the MIPS cases execute there.

Three additional private controls use actual native GTE operations and change
one executed instruction in an isolated replay. A stack store changes four
data bytes while leaving measured CPU/GTE results intact; a `K1` change alters
the compared register; replacing SQR with OP changes data, CPU and GTE views.
Each is detected beyond its known code-patch bytes. Canonical and retained
capture files remain unchanged.

The compiler study also checks 21 source forms, including three controls.
An evaluated expression keeps a real 16-byte inline argument block alive, but
the reference variants emit a pointer store into the original unused region.
None matches. Three GDB lifetime observations preserve complete ordinary
compiler assembly, without forcing allocation decisions or modifying the
compiler. This narrows the remaining source explanation and adds no C bytes.

[Publication metadata](natural-collision-replay-checks.json) binds the sources,
native calibration, controls and compiler observations. Original behavior,
optional mods, AI-assisted development tools and the Bevy port retain separate
counts. No whole feature, whole NPC encounter or full-game parity is accepted
by this calibration.
