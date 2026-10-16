# Bounds comparison and result ownership

The published C research fragment for `func_8004CD38` now differs from the
complete original executable in **19 bytes**, improving on the preceding
21-byte published fragment. The 19-byte form was already retained privately;
this checkpoint publishes and rechecks it. It remains unaccepted, and the
matching game continues to use the original 108-byte assembly function.

## What changed

A consumed inline comparison returns an unsigned byte for the maximum-X test.
Its result is always zero or one, so the algorithm and signed comparisons are
unchanged. The compiler now uses the original destination register for that
comparison and its following branch. The function still has 27 instructions.

The remaining allocation problem is explicit: packed X occupies `v0` in the
candidate, while the persistent outside result occupies `a3` and is copied to
`v0` at return. The original assigns packed X to `a3` and keeps the result in
`v0`. A fresh compiler observation records one local-allocation pass, one
equivalence update, six global allocations and ten priority comparisons.
Normal and observed complete assembly agree; final register dispositions and
priority calculations agree with the diagnostic dumps. No registers are bound
by the source, and canonical compiler flags are retained.

The [earlier lifetime report](BOUNDS_SOURCE_LIFETIMES.md) preserves the 21-byte
snapshot and its evidence. Its [previous source](https://github.com/BaileyPillon/lsd-dream-emulator-decompilation/blob/f6f547c8dd12b07d9c50dff2be39316efb6af090/research/render_bounds/bounds_candidate.c)
remains in Git history. Historical metadata is unchanged.

## Source experiments

This campaign records 128 isolated compiler comparisons, including eight repeated
controls. None improves on the privately retained 19-byte form.

| Family | Compiler observations |
| --- | ---: |
| Initialized local and returned result records | 34 |
| Result records initialized by member assignment | 34 |
| Incoming point-address parameter reused for the result | 14 |
| Equivalent switches, null-result guards and old-style declarations | 46 |

Twenty initialized-record variants initially failed isolated linking because
the linker setup omitted GP-relative initializer placement. All twenty retained
objects are qualified by a corrected diagnostic link, without recompilation.
Those links add no compiler observations. Their static-data reads and the
returned-record stack work do not reproduce the original function.
Five separate complete-unit compilations and three normal/observed/diagnostic
compiler runs qualify the retained candidate and allocation trace. They are
outside the table's isolated-source count.

The first publication wrapper also expected the wrong success-label spelling
after both the native comparison and compiler observer completed successfully.
Its producer and failure remain private. An independent auditor checks the
completed reports, every observed artifact and source hash; it repeats no
compiler or native executions.

## Bounded native comparison

The exact published fragment produces a 505,856-byte candidate image. All
bytes outside the sized 108-byte function remain canonical. Retaining ELF
symbols produces the same complete candidate image.

All **4,648 distinct initialized inputs** pass original execution, candidate
execution and the independent scalar model, for 9,296 positive executions.
This repeats the [existing predicate domain](RENDER_BOUNDS.md): byte sweeps,
signed extremes, reversed intervals, input aliases, unaligned coordinates,
address aliases and null bounds with an unmapped coordinate pointer.
The fixture API calls the second coordinate `y`; the renderer's shared type
names that same coordinate Z.

The comparison checks complete guarded buffers, return words, ordered memory
reads and widths, zero writes, saved registers, SP, GP and RA. Both executions
stay within the complete function. Every one of the eleven differing candidate
instruction words executes in the positive domain. Four isolated faults change
signed unpacking, a minimum load, the maximum-Z field or comparison signedness;
each altered instruction executes and produces a wrong return on an existing
input. No function outputs are substituted.

These scalar checks add no natural scene, renderer/stage composition,
framebuffer/audio or PS1 timing acceptance. No new original input domain,
matching C byte, NPC profile, feature group, optional mod or developer-capability
category is counted. Current C recovery stays at 194,212 / 199,912 bytes,
with nine assembly functions and 24 inherited storage explanations. Bounded
NPC profiles remain 34 / 107; whole-feature and whole-encounter acceptance
remain zero. Original NPC AI, analysis tools and the separate Bevy port retain
their boundaries.

## Reproduce

Follow the [research recipe](../research/render_bounds/README.md) with your
canonical executable and matching Linux/WSL toolchain. The full-image build
must retain its expected unsuccessful matching gate: exit code 1 and 19 changed
bytes. The subsequent native comparison requires `requirements-analysis.txt`.
It preserves existing evidence, rejects public output destinations and checks
the complete candidate against its sized ELF before execution.

[bounds-narrow-comparison-checks.json](bounds-narrow-comparison-checks.json)
records source hashes, complete-image comparisons, source trials, actual
compiler observations and measured controls. Game images, generated code,
full buffers, compiler products and failed attempts stay private.
