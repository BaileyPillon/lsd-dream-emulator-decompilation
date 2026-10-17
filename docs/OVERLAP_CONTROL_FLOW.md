# Closer hull/face collision reconstruction

The unaccepted [`func_8001DDF4` research fragment](../research/collision/overlap_candidate.c)
now differs from the complete executable in **26 bytes**, down from 148. Its
796-byte extent and original 176-byte frame agree. All remaining differing
instructions have the original opcode and register fields; their SP-relative
offsets are 24 bytes too early. The strict complete-image comparison still
fails and the matching game retains assembly.

[Recorded checks](overlap-control-flow-checks.json) separate the compiler
comparisons, actual allocator observations and repeated bounded native inputs.

| Measure | Previous published candidate | Current candidate |
| --- | ---: | ---: |
| Complete function bytes | 796 | 796 |
| Stack frame bytes | 176 | 176 |
| Midpoint payload bytes | 12 | 12 |
| Complete executable bytes | 505,856 | 505,856 |
| Strict differing executable bytes | 148 | 26 |
| Accepted matching C bytes from this study | 0 | 0 |

Matching game C remains **197,172 / 199,912 bytes (98.63%)**, with two assembly
functions, two inherited storage explanations and 38 / 40 provisional groups
whose listed core functions are in C. Whole feature and NPC encounter
acceptance remain separate and unfinished.

## Source and the remaining layout

The loop/control-flow body was adapted from
[SceneNode__RaycastHullAgainstFaces](https://github.com/brian-oblivion/lsddecomp/blob/90a398e4f429b4371be05648605fc198b9efb395/src/graphics/scene_node.c)
at commit `90a398e4f429b4371be05648605fc198b9efb395`. That original project code
is covered by its [CC0 dedication](https://github.com/brian-oblivion/lsddecomp/blob/90a398e4f429b4371be05648605fc198b9efb395/LICENSE).
The downloaded file was checked against the pinned Git blob hash. Its explicit
unused 24-byte array was removed; it was not imported into this project.

Without unused storage, the adapted body has a 152-byte frame and 48 differing
bytes. Applying this project's existing consumed source-count and bounds-pointer
views restores the 176-byte frame and reduces the difference to 26. Every view
member supplies a real lookup result. The existing pointer ABI, call order,
height gates and centre/fallback behavior are preserved.

Two actual compiler traces distinguish these forms. Both allocate the midpoint
payload first, followed by the address-taken nearest/height words. The direct
form then has eight four-byte reload requests; the lookup-view form has eleven.
Those requests are rounded to eight-byte slots. The three additional slots
occur late, after the original reload region, rather than before the scalar
words where the original needs 24 bytes. Normal and observed complete assembly
agree in both traces. These are compiler observations, not PS1 runtime coverage.

Thirty-seven complete linked-function comparisons also test declared lookup
records, output arguments and fully consumed six-input query records. They
introduce no unused fields or changed compiler flags, but none matches the
complete executable. A matching frame alone is insufficient. No displacement
normalization, instruction replacement or physical register binding is used
to pass the gate.

## Bounded native comparison

All **6,912 existing graph pairs** pass through original collision, transform
and SDK routines using the pinned native GTE bridge, with zero function-output
stubs. These repeat **5,760 distinct final inputs** and **1,152 duplicate final
inputs**. They do not add a new original input domain.

The checks compare complete 6,144-byte caller buffers, returns, preserved ABI,
stack guards, final GTE state and ordered native command results. The positive
pairs issue 22,032 OP/SQR commands and 12,960 leading-bit requests across both
images. The height-boundary fault is detected after its changed instruction
executes. Additional witnesses from the same domain establish execution of all
26 remaining mismatched instructions; their counts are recorded separately.

These fixtures do not establish natural encounter reachability, full scene
lifetime, PS1 instruction timing or whole-feature acceptance. The running game
profile and separate Bevy/Rust repository are unchanged.

## Reproduce

With a current matching build and the documented toolchain, run from the
repository root in Linux/WSL:

```bash
python research/collision/prepare_overlap_candidate.py \
  --output .decomp-lab/overlap-new
python tools/decomp_workbench.py check \
  --source src/base/transform.c \
  --candidate .decomp-lab/overlap-new/transform.c \
  --function func_8001DDF4 \
  --output .decomp-lab/overlap-new/build
```

Expected gate result: **exit code 1**, 505,856 executable bytes, zero length
difference and 26 differing bytes. Retain the unsuccessful result. The existing
[native comparison recipe](OVERLAP_RECOVERY.md#reproduce) accepts that complete
candidate image. It must not replace the canonical game until every byte
matches and the source explanation is reviewed.
