# Matching C recovery of the level-model loader

`func_8004BE54` is now recovered as **600 bytes of matching C** in
[render_context.c](../src/scene/render_context.c). Both the isolated complete
candidate and the standard build reproduce all **505,856 executable bytes**
of `SLPS_015.56`. A fresh copy of the source and pinned toolchain also builds
all 305 objects from scratch and produces the same executable.

Game C recovery advances from **194,284 / 199,912 (97.18%)** to
**194,884 / 199,912 (97.48%)**. Six known game functions remain in assembly.
The original executable, data and behavior remain unchanged. Recorded hashes
and fixed before/after counts are in
[lbd-recovery-checks.json](lbd-recovery-checks.json).

## What resolved the match

The earlier [loader audit](LBD_PIPELINE.md) established tile decoding, TMD
construction, native allocation, SDK linking and destruction on the local
level corpus. Its original C candidate passed those bounded comparisons but
retained 118 executable-byte differences.

The new typed-source search reduced that to eight differing bytes. It combines
an explicit continuation flag read, separate scope for descriptor assignment,
and X/Y/Z angle stores using the verified query callback declaration. Capturing
the grid address before clearing the file size resolves the initial load/store
sequence. Writing the continuation address as offset plus table base resolves
the final pointer-addition order.

The first phase evaluated 576 source forms; the second found the exact match
on its fourth form. Compiler flags stayed unchanged. No instruction patching,
physical-register binding, volatile access or artificial stack padding was
used. The typed payload and slot views describe observed field offsets, and
the constructor uses the existing 16-byte `tmd_model_arg_t` interface.

## Verification

The complete candidate was linked against the entire baseline and had zero
length or byte differences. After promotion, the standard build and a separate
clean source copy both match SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d`. The clean copy starts with no objects;
its installed MASPSX dependency is pinned to the same verified revision.

The promoted build passes the reusable native loader audit on all **418 local
LBD files**, first loading and then reloading through the real destructor.
The matched body and reference execute **1,672 loader runs**, with zero
dependency stubs, one explicit ready-CD state contract and five detected
output faults. Their full instruction bodies are now identical, rather than
merely agreeing on selected outputs. All 155 tooling tests pass locally on
Windows and Linux.

This accepts the C recovery of this function. It does not accept the entire
rendering feature: original Japanese-disc asset coverage, cold/pending CD I/O,
caller node ownership, GPU drawing and hardware timing still need separate
evidence. The prior audit's bounds and edition distinction remain in force.

## Fixed feature boundary

The feature denominator remains the same provisional 40 groups; an official
exhaustive feature count is unknown. Groups with all listed core functions in
C remain **35 / 40**, and whole-feature runtime acceptance remains **0 / 40**.
The same 107 original NPC callbacks have C bodies, 11 have bounded execution
evidence, developer capabilities remain ten, and optional mods remain three.
Original NPC behavior and separate AI-assisted tools remain distinct.

The unchanged pre-prompt C numerator was 169,540 bytes. Under the corrected
199,912-byte denominator, that is 84.81%; the current result is 97.48%.
That correction is an arithmetic restatement of the frozen baseline, not a
new run of its original source.
