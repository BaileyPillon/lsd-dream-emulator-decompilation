# Original TMD mapping and linking

The original `GsMapModelingData` and `GsLinkObject4` instructions agree with
independent predictions across **531 TMD tables, 13,627 object descriptors and
119,458 primitive packets** from the verified Japanese disc. Complete model
bytes, the supplied target object, descriptor selection, packet cursors,
saved-register ABI and memory guards agree at every return. Repeating each
operation preserves its output.

[Machine-readable evidence](model-sdk-mapping-checks.json) records the qualified
functions, analysis backend, source hashes, controls and journal hashes. This
extends the earlier [MOM mapping/lifetime profile](MODEL_MAPPING.md) to the full
model-bearing corpus, including LBD geometry and embedded MML models. It adds
asset evidence without changing the game's C, executable or assets.

| Measured item | Result |
| --- | ---: |
| Model-bearing files | 422 |
| TMD tables | 531 |
| Object descriptors | 13,627 |
| Primitive packets | 119,458 |
| Mode runs | 28,056 |
| Original mapper calls, including reentry | 1,062 |
| Original linker calls, including reentry | 27,254 |
| Original instructions in the corpus profile | 6,885,916 |
| Corpus objects with zero primitives | 0 |
| Disagreements | 0 |

Counts describe encoded occurrences, rather than unique models or additional
player features. Repeated content in separate files is counted again; aliased
MML offsets are walked once with their reference count retained.

## Recovered interface and mutations

`GsMapModelingData` at `0x80020548` receives **TMD + 4**, pointing at the flags.
It sets flag bit zero and adds the address of the first object descriptor,
**TMD + 12**, to each object's vertex, normal and primitive pointer. Counts,
scale values and all other bytes are preserved. An already-mapped flag returns
immediately. The original loop treats its object count as signed; synthetic
fixtures exercise that early return without treating negative counts as real
disc models.

`GsLinkObject4` at `0x8001ef70` receives the first descriptor, a supplied target
object and a zero-based object index. The selected descriptor address is
written at target offset eight. The linker walks the selected primitive
stream and replaces the first header halfword of each mode run with its
packet count. A transparency-bit change splits a run; a flag change alone
does not. Even a zero-primitive object writes a zero halfword at its primitive
base, which the synthetic fixtures check.

Packet strides come from the linker's switch, independently of the header's
length bytes. They differ from the collision reader's general gradation
layouts: with gradation set, modes `0x28` and `0x38` still use linker strides
of 20 and 24 bytes. The fixtures preserve this original behavior. These
observations do not establish renderer interpretation of those layouts.

## Verification boundaries

`verify_tmd_sdk.py` reuses a successful [static inventory](MODEL_PACKET_DECODING.md),
checks its source dependencies and reads the original raw disc without
extracting assets. Complete disc hashes are checked before and after the run.
The canonical executable qualifies both function ranges and their jump table.
No SDK result is stubbed.

A dedicated 2 MiB Unicorn 2.1.4 VM executes only the selected original function.
Each call has a one-million-instruction ceiling. Data accesses are bounded to
the supplied model, qualified jump table and stack; writes are restricted to
the expected pointer/header slots, target pointer and callee frame. Complete
model and target bytes are compared with the independent oracle. Every other
VM byte is hashed at every return, and the caller stack, SP, GP, RA and saved
registers are checked. The original linker's actual packet-cursor sequence is
compared with the independently planned sequence.

Literal fixtures cover **192 mode/flag/address-alias combinations**, six zero
or signed-negative count cases and two mixed-run/zero-primitive cases. They
use physical and KSEG0 data addresses, nonzero descriptor indices, distinct
metadata, invalid header length bytes and guarded payloads. Actual corpus
data uses physical addresses.

Three controls modify instructions only inside private analysis VMs: a wrong
mapping base, an incorrect run-count increment and a suppressed mode boundary.
Each changed instruction executes; every call returns with ABI, cursor and
memory guards intact; every wrong output is detected. A crash is not counted
as detection. Original files remain unchanged.

The closed corpus run took 144 seconds. Its 13,627-record journal occupies
324,664 compressed bytes. A separate streaming review checks every object in
inventory order, every table's packet total and both compressed and decoded
journal hashes.

## Reproduce

Use your own verified disc and the existing optional analysis environment from
`requirements-analysis.txt`. Reuse an unchanged successful static inventory,
or create one with `inventory_model_packets.py` as documented in the vertex
audit. Choose an unused output path beneath an existing scratch directory:

```powershell
python -B tools/verify_tmd_sdk.py --disc "D:\private\LSD-Japan.bin" --inventory .decomp-lab/model-packets.json --output .decomp-lab/tmd-sdk
python -B -m unittest tests.test_tmd_sdk_model -v
```

The verifier refuses existing output directories. Its retained reports are
bounded to 4 MiB; the decoded journal is bounded to 8 MiB. It writes no model
payload, RAM dump, emulator installation or disc copy. Data-free tests cover
literal packet strides, pointer bases, early returns, run boundaries,
descriptor selection, reentry and malformed-input rejection.

## Remaining gates

This is functional SDK agreement on supplied model buffers. Normal-index,
UV/palette, material, lighting and GPU rasterization semantics remain open,
as do complete scene histories, PS1 hardware timing, unsupported SDK error
paths and natural NPC encounters. Existing source-recovery counts and all
40 provisional feature groups are unchanged. This profile accepts **zero**
whole features or NPC encounters and adds **zero** recovered C bytes.

The [original vertex decoder profile](MODEL_PACKET_DECODING.md) remains a
separate check. Neither profile substitutes for rendering acceptance.
AI-assisted analysis can consume these reports through the tooling track;
these tools make no model API calls or changes to original NPC behavior.
