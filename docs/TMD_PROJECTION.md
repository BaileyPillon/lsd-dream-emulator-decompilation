# Original TMD projection and stateful GTE

The original 232-byte projection/culling helper at `0x800195ec` agrees with
independent predictions in **438 constructed fixtures**. Its complete scratch
buffer, packet-length byte, return value, GTE state, saved registers and the
rest of the 2 MiB analysis VM agree at every successful return. This advances
the [mapping/linking audit](MODEL_SDK_MAPPING.md) toward the original draw path.

This is a projection prepass, not the complete renderer. It adds **zero** game
C bytes, gameplay features, whole-feature acceptances or whole NPC encounters.
Matching game C remains **199,912 / 199,912 bytes**; the 40 provisional feature
groups and their remaining runtime requirements are unchanged.

## Executed evidence

| Profile | Result |
| --- | ---: |
| Native register/command cases | 3,205 |
| Architectural control/data registers | 32 / 32 |
| Qualified GTE command opcodes | 11 |
| Actual native commands in the register profile | 1,797 |
| Actual native `GTE_WriteDR` calls in that profile | 51,249 |
| Original projection calls | 438 |
| Original projection instructions | 15,308 |
| Native commands inside those original calls | 945 |
| Synthetic MIPS programs | 150 |
| Executed original-code fault controls | 3 |
| Rejected memory-access controls | 8 |

[Register evidence](gte-state-checks.json) and
[projection evidence](tmd-projection-checks.json) pin the executed sources,
compiled bridge, backend, native transcript and independent journal audit.
The native transcript remains private, following the contribution guide's
capture policy. Its compressed/decoded hashes and lengths are published. An
optional regression test replays those actual native observations through the
integer oracle when `LSD_GTE_NATIVE_TRANSCRIPT` identifies the retained file.
CI uses literal arithmetic and synthetic MIPS guard fixtures without game
assets; it does not rerun the native core or load a private transcript.

The original helper executes RTPT, NCLIP and, for accepted faces, AVSZ3. It
writes the clip flag, signed screen area, depth cue, ordering depth, projected
coordinates and ordering-table slot. Fixtures cover winding/degeneracy, fog
thresholds, signed shift counts, physical/KSEG0 data aliases, clipping and
256 seeded matrix/vector combinations. Outcomes are 51 projected, 18 projected
with a clip flag, 22 depth-cue rejected and 347 backface/degenerate returns.

Three private one-instruction mutations alter the packet-length source,
fog rejection threshold and ordering-depth shift. Each executes actual native
commands, returns with ABI/VM guards intact and produces the predicted wrong
output. A separate scalar journal audit rebuilds every complete output buffer
without calling the producer's `expected()` or `fixture()` routines. It reuses
the separately native-qualified arithmetic model and detects four actual
analysis-copy corruptions of the recorded rows.

## Native GTE boundary

The separate Windows host reuses the pinned BizHawk 2.11.1 Nymashock core. It
calls actual `GTE_Init`, `GTE_Power`, `GTE_WriteDR` and `GTE_Instruction` code.
Initialization matters: omitting reciprocal-table initialization is one of
four executed boundary controls. The other controls corrupt light-matrix
cache transfer, translation cache transfer and screen FIFO handling.

The supported commands are RTPS, RTPT, NCLIP, AVSZ3, AVSZ4, MVMVA, DPCS,
NCCS, NCCT, NCDS and NCDT. All 64 architectural register words and the native
command return are compared at each request. Tests cover sign extension,
read-only/aliased registers, FIFOs, matrix selections, translation, shift/limit
flags, 44-bit overflow, RGB limits and reciprocal lookup bins.

Control-register writes and architectural reads are inlined in this native
binary. Their cache/mask behavior is explicitly reproduced by reviewed host
code, rather than described as calls to absent native symbols. The source
reference is the pinned [Mednafen GTE implementation](https://github.com/TASEmulators/mednafen/blob/382ff1b8d293c9a862497706808cbb79b2cecbfb/src/psx/gte.cpp).
The core hash and four mapped native code-prefix hashes are checked before
execution. The bridge loads no game or BIOS and does not attach to a player
or the separate year replay.

## COP2 transport and memory guards

Unicorn executes the original integer instructions. Unsupported COP2 words
are retained in a side map and lowered only in private analysis VM memory to
NOP or guarded SW transport instructions. Their transfer/command semantics
execute through the checked native boundary; no function result is stubbed.
The executable on disk is unchanged. The synthetic profile exercises all
register transfers and 144 branch-delay programs: 112 with COP2 operations
and 32 with ordinary loads/stores.

A 12-case, game-free reproducer isolates a Unicorn 2.1.4 instrumentation
problem: a hooked load/store in a branch-to-return delay slot produces
interrupt 20. Its pinned [exception enum](https://github.com/unicorn-engine/unicorn/blob/2.1.4/qemu/target/mips/cpu.h#L1165-L1188)
identifies that value as a reserved-instruction exception. The same program
returns normally without the corresponding memory hook. This is analysis
backend evidence, not an original game fault.

This profile checks effective addresses in instruction hooks and preflights
memory operations in delay slots before their branch executes. The preflight
also avoids Unicorn executing a delay-slot store after a stop request. Eight
executed controls reject out-of-buffer reads, out-of-slot writes, unaligned
accesses and unreviewed partial loads, both normally and in delay slots; every
rejected control preserves the entire buffer. Data reads and writes retain
their narrow spans, complete outputs are compared and the rest of the VM is
hashed. Unreviewed memory encodings and link-register address bases in delay
slots are rejected. Ordinary original MIPS bytes are not patched.

## Reproduce

Use the existing optional analysis environment with Unicorn 2.1.4. The bridge
requires Windows x64, the checked BizHawk release and the installed .NET
Framework compiler/facade. Substitute the paths to that existing installation;
do not copy a full emulator tree into each study.

```powershell
./tools/build_nymashock_gte_state_bridge.ps1 -EmulatorRoot "D:/tools/BizHawk-2.11.1" -Netstandard "C:/Windows/Microsoft.NET/assembly/GAC_MSIL/netstandard/v4.0_2.0.0.0__cc7b13ffcd2ddd51/netstandard.dll" -Output .decomp-lab/gte-state.exe
python -B tools/verify_gte_state.py --bridge .decomp-lab/gte-state.exe --runtime "D:/tools/BizHawk-2.11.1" --output .decomp-lab/gte-state-profile
python -B tools/verify_tmd_projection.py --executable rom/SLPS_015.56 --bridge .decomp-lab/gte-state.exe --runtime "D:/tools/BizHawk-2.11.1" --output .decomp-lab/tmd-projection
python -B -m unittest discover -s tests -p "test_gte_*.py" -v
python -B -m unittest discover -s tests -p test_tmd_projection_guards.py -v
```

The Windows bridge can also be invoked from the existing WSL analysis
environment. Its runtime argument must remain a Windows-readable path such
as `D:/tools/BizHawk-2.11.1`. Choose fresh outputs: the tools refuse overwrites
and bound each retained profile to 4 MiB.

To replay a retained transcript locally, set `LSD_GTE_NATIVE_TRANSCRIPT` to
that profile's `transactions.jsonl.xz`, then run
`python -B -m unittest discover -s tests -p test_gte_native_transcript.py -v`.
Keep the capture outside commits; the test is skipped when no path is supplied.

## Remaining gates

The camera, matrices and vertices are supplied fixtures. These checks do not
execute the complete 3,816-byte draw routine, normal/UV/material assembly,
ordering-table submission, GPU rasterization or natural scene/NPC lifetimes.
PS1 CPU load/COP2 pipeline delays, scheduling and hardware equivalence remain
unverified. Command latency return values do not establish those properties.
Original NPC behavior and optional AI-assisted tooling remain separate; these
analysis tools make no model API calls or changes to gameplay.
