# Overlap source recovery

> Historical checkpoint: the later
> [result-lifetime study](OVERLAP_RESULT_LIFETIMES.md) reduces the current
> candidate to 148 differing bytes and a 176-byte frame. The measurements below
> retain this earlier 170-byte snapshot and its separate evidence.

The unaccepted C candidate for `func_8001DDF4` uses two six-byte midpoint
objects. It agrees with the original on 6,912 paired collision graphs, including
complete caller buffers, ABI checks and ordered native GTE results. Its complete
executable still differs in 170 bytes, all within the original 796-byte function.
The canonical game retains assembly; no C function or whole feature is promoted.

## Actual midpoint storage

The input begins with a four-byte path count followed by eight six-byte points
per 48-byte cloud record. The coarse pass averages points 0/2 and 4/6, producing
exactly two three-halfword points. Clipping and primitive decoding consume those
twelve bytes. The fallback tests corner segments 1 and 2 of each cloud record.
It preserves the original strict contact-height test, source mask and path mask.

`class_FA50_is_active` returns the global enumeration count; it ignores the model
argument. `get_source_vertices` returns the shared bounds; it ignores the index.
These checks preserve that behavior rather than assuming per-instance bounds.
The [original collision audit](COLLISION.md) documents the native dependencies
and the contact-height convention.

An older private register-lifetime candidate declared forty bytes of midpoint
storage, although only twelve were consumed. Its unexplained 28-byte tail is not
accepted as a source explanation. The published fragment declares
`func_8001E2E8_pt_t points[2]` and uses an unsigned mask word. It adds no padding,
physical-register binding or instruction substitutions.

| Measure | Original | Published candidate |
| --- | ---: | ---: |
| Function bytes | 796 | 796 |
| Complete frame bytes | 176 | 152 |
| Midpoint bytes consumed | 12 | 12 |
| Complete executable bytes | 505,856 | 505,856 |
| Bytes different from the canonical image | 0 | 170 |

## Native paired comparison

The checker runs the original and the compiled candidate with their original
collision, transform and SDK dependencies. Fifteen routines are actually entered
per image; the curated ranges also include a midpoint helper that this profile
does not enter. It supplies no function-output stubs.

The 6,912 parameter graphs produce 5,760 distinct final inputs and 1,152 repeated
inputs. Each graph runs in both images, so those paired executions are not extra
distinct fixtures. The checks compare the full 6,144-byte caller buffer, return
values, saved registers, stack guards, GTE state and ordered native events.
Both images together issue 22,032 native OP/SQR commands and 12,960 leading-bit
requests before controls through the checked Nymashock core and explicit COP2
transfer adapter.

One deliberate fault changes the strict height boundary from 513 to 512 in both
candidate locations. The independent composed model detects the fault. The
coarse-path changed instruction executes once; the fallback location is patched
but is not entered by that control. Its three commands and two leading-bit
requests are recorded separately from the paired comparisons.

An initial run used an older bridge restricted to MVMVA and failed on OP. Its
failure logs are retained. The successful run uses a fresh build of the current
bridge, with executable, source, runtime/core and backend identities recorded.
Source, candidate, canonical build and dependency hashes remain unchanged.

These are bounded manual geometry graphs. Natural scenes and model histories,
all geometry/alias combinations, complete PS1 CPU timing and whole-feature
acceptance remain open. This profile adds no NPC callback acceptance.

## Compiler observations

Twenty-seven qualified source forms use the twelve-byte midpoint layout: a
baseline, 24 pointer-stream variants and two typed-point forms. None matches.
Three earlier complete builds and the published fragment's complete build
retain their separate length and byte comparisons.

The actual bundled GCC 2.6.3 stack trace observes 106 allocation calls across
the complete translation unit. For this function, the twelve-byte object rounds
to sixteen bytes of virtual local area. The trace reports both the temporary
request and its underlying local allocation; they are one allocation, not two.
The maximum virtual area is 88 bytes, with 24 bytes of outgoing argument storage
and 40 saved-register bytes producing the candidate's 152-byte frame.

The independent allocation diagnostic qualifies one local allocation, one
equivalence update, 26 global allocations and 91 priority comparisons. Normal,
observed and diagnostic complete assembly agree, as do register dispositions
and reference priorities. These observations explain the candidate's emitted
layout without accepting it as the original source.

## Reproduce

With your own canonical executable, a current WSL build and the optional native
checker dependencies, run from the repository root:

```bash
python research/collision/prepare_overlap_candidate.py \
  --output .decomp-lab/overlap-candidate-new
python tools/decomp_workbench.py check \
  --source src/base/transform.c \
  --candidate .decomp-lab/overlap-candidate-new/transform.c \
  --output .decomp-lab/overlap-candidate-new/build
```

The current matching gate should fail with exit code 1: the complete image has
its original length but 148 differing bytes. The earlier fragment at commit
`dacecb8995f393a69367b260b6252b80adbf7be6` reproduces the historical 170-byte
result. Build a current bridge as described
in [the GTE audit](RENDER_GTE.md), then run:

```bash
python research/collision/compare_overlap_candidate.py \
  --candidate .decomp-lab/overlap-candidate-new/build/candidate.exe \
  --output .decomp-lab/overlap-candidate-new/pairs \
  --bridge .decomp-lab/collision-bridge-new/bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'
```

The [evidence metadata](overlap-recovery-checks.json) pins source, complete-build,
compiler and native reports. Raw game inputs, buffers, generated assembly,
candidate executables and faulted code remain private. All 360 tooling tests
pass locally; the canonical 305-object build remains exact at 194,212 / 199,912
C bytes (97.15%), with nine assembly functions and 24 inherited storage
explanations. Original feature, NPC, analysis-tool and optional-mod counts are
unchanged.
