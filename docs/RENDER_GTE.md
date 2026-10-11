# Original matrix application through native Nymashock GTE

The original 352-byte SDK `ApplyMatrixLV` passes **109,501 distinct guarded
fixtures**, using actual commands from the checked BizHawk 2.11.1 Nymashock
core. The complete lookup/rotation/vector/grid/stream chain executes **eleven
original functions, 3,564 MIPS bytes, in 13,230 distinct cases with zero
function-output stubs**. This removes the remaining `ApplyMatrixLV` contract
from the earlier [rotation audit](RENDER_ROTATION.md).

The checked native core executes **245,470 MVMVA commands**, plus one identity
self-check. An independent log audit verifies every ordered request and MAC,
IR and flag response; there are 8,982 distinct command inputs. Command counts
include repetitions and four fault controls, while fixture counts describe
distinct complete guarded inputs. No function is promoted to C and no whole
original feature is accepted. [render-gte-checks.json](render-gte-checks.json)
pins the proof, audit, code, build and unchanged before/after counts.

## Executed code and explicit transfer boundary

Unicorn executes the original MIPS loads, signed-vector decomposition,
branches, shifts, additions, output stores and pointer return. A reviewed
instruction adapter handles this helper's 19 COP2 operations: five `ctc2`,
six `mtc2`, six `mfc2` and two MVMVA commands. It advances those instructions
without changing their original bytes or replacing the function's result.

The separate Windows bridge mounts its own Waterbox host. It checks the
compressed core and five runtime-library hashes, verifies mapped function
prefixes and invokes the actual native `GTE_Power`, `GTE_WriteDR` and
`GTE_Instruction` routines through BizHawk's calling-convention adapter.
The core's compressed SHA-256 is
`5c6fe90fadd670318ca74993911b171e15b167c7f2e1e88bf66de4661fc24126`.
Different binaries are rejected. No game, BIOS, emulator window or full
PlayStation CPU is loaded by that bridge.

Control-register writes and MAC reads are inlined in this binary. The bridge
explicitly reproduces only the reviewed CR0..4 mask/cache transfer and reads
MAC1..3; IR writes and matrix commands execute the native routines. Both
supported commands use the rotation matrix, IR1..3, null translation and
signed IR limits. Each overwrites its outputs and resets flags, making a
reset-and-restore operation equivalent for this restricted command subset.
Unreviewed opcodes, register numbers and MVMVA field combinations are rejected.

The source context is the [Mednafen GTE implementation](https://github.com/TASEmulators/mednafen/blob/382ff1b8d293c9a862497706808cbb79b2cecbfb/src/psx/gte.cpp)
at BizHawk's tagged submodule commit. The host and delegate boundary follows
[WaterboxHost](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Emulation.Cores/Waterbox/WaterboxHost.cs).
The locally checked binary remains the execution authority. The first native
identity attempt produced correct values but failed a cycle assertion:
`GTE_Instruction` returns its command latency minus one, so the observed
return is **7**. The initial compiler-reference failure and both failed
cycle-assertion runs are preserved. That return does not verify CPU scheduling.

## Recovered arithmetic and bounded coverage

Each signed long-vector component is split into signed high and low parts
at bit 15. The helper retains 32-bit negation and the GTE's 16-bit IR narrowing,
including `INT_MIN` and large-component wrap behavior. The first command
uses unshifted matrix products; the second shifts products by 12. The helper
combines their signed MAC results as high times eight plus low, modulo 32 bits.
It does not substitute ideal floating-point rotation or a single long dot
product.

The independent model checks MAC narrowing before signed IR saturation and
the individual limit flags. In this null-translation, signed-halfword subset,
partial sums cannot reach the 44-bit accumulator limits; 32-bit MAC wrapping
is still exercised. IR3 saturation alone does not set the summary flag.
All recorded command results agree with both the producer's model and the
separate integer log audit.

| Fixture group | Distinct original-helper cases |
| --- | ---: |
| Seven matrices crossed with 25 signed long boundaries on each vector axis | 109,375 |
| Overlapping matrix/vector/output buffers and three address aliases | 126 |
| **Total** | **109,501** |

The matrices include identity, zero, a quarter turn, mixed fractional terms
and signed-halfword extremes. Vector cases cover sign changes, fixed-point
remainders, high-part boundaries, IR narrowing and signed-long extremes.
Overlapping inputs are decoded from the actual initialized buffer before
modeling output; declared case values are not assumed to survive overlap.
Every run checks the complete buffer, return pointer, stack guards and saved
ABI. This is bounded coverage, not every matrix/vector combination.

The composition uses real `RotMatrix` coefficients and the actual rotated
`(0, 0, distance)` vector. Earlier independent projection fixtures are not
carried forward as artificial outputs. Seven world labels, nine cell pairs,
five yaw cases, seven signed distances, two slot permutations and three
address aliases produce 13,230 distinct complete input graphs. The run records
7,938 longitudinal and 5,292 transverse decisions, emitting one, two or three
rectangles. All guarded object buffers, matrix/info/template outputs and
native call traces agree with the independent position, rotation, vector and
rectangle models.

Fault controls change high-part scaling, negative-high reflection and the
low-part command's shift. A fourth changes high-Z scaling through the full
eleven-function composition. All four are detected; only the verifier's own
Unicorn memory changes. Original game/SDK inputs and checked runtime libraries
are preserved.

## Reproduce locally

Build the matching game and install `requirements-analysis.txt` in WSL/Linux.
On Windows, supply a local BizHawk 2.11.1 directory and an installed .NET
Framework-compatible `netstandard.dll` reference facade. For example:

```powershell
.\tools\build_nymashock_gte_bridge.ps1 `
  -EmulatorRoot 'C:\Tools\BizHawk-2.11.1' `
  -Netstandard 'C:\Windows\Microsoft.NET\assembly\GAC_MSIL\netstandard\v4.0_2.0.0.0__cc7b13ffcd2ddd51\netstandard.dll' `
  -Output '.decomp-lab\nymashock-gte-new.exe'
```

The facade must exist on your machine; the script does not download or install
it. Compilation uses the installed x64 .NET Framework compiler and preserves
existing outputs. Then run inside WSL with the Windows runtime path:

```bash
python tools/verify_render_gte.py \
  --bridge .decomp-lab/nymashock-gte-new.exe \
  --runtime 'C:/Tools/BizHawk-2.11.1' \
  --output .decomp-lab/render-gte-native-new.json
```

The bridge, report and detailed command logs remain private. New output names
are required. Public tests use synthetic arithmetic, buffer and protocol
fixtures and require no emulator or game files. All **215** local tooling
tests pass on Windows Python 3.14 and Linux Python 3.13. The supplied tools
make no model API calls and extend the existing analysis workflow; original
NPC behavior and optional gameplay mods remain separate.

## Unchanged counts and remaining gates

Matching game C remains **194,884 / 199,912 bytes (97.48%)**, with six known
game functions in assembly. The inventory retains 40 provisional groups,
35 with all listed core functions in C, and zero independently accepted whole
groups. NPC counts remain 107 callbacks in C and 11 with bounded checks;
developer capabilities remain 10 and optional mods 3. The exhaustive original
feature total remains unknown.

This removes function-output contracts from the reviewed composition and
verifies its commands on one pinned software GTE implementation. Full PS1
CPU execution, load delays, cycle scheduling, original hardware, natural
level ownership and encounter reachability, scene/framebuffer output and
independently reviewed feature scenarios remain separate requirements.
