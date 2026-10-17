# Grid C candidates through native SDK and streaming code

This is the historical comparison of two rejected candidates. The later
[matching grid-window recovery](GRID_MATCHING_C.md) satisfies complete-image
equality and replaces the assembly fallback. The reproduction commands below
refer to the assembly-based source at commit
`7415704a4f473def92ced9daa4400cf4ba6e7615`.

The two unaccepted `func_8004C6A8` source forms now have a reproducible comparison
through the existing eleven-function [native GTE composition](RENDER_GTE.md).
The canonical game retains assembly. The edge candidate still differs in eight
bytes across two instruction words; the cell-reuse alternative differs in
seven bytes across four words. Neither is matching C.

## What the comparison establishes

`tools/verify_render_grid_candidates.py` loads complete, current workbench
builds. It verifies their source and artifact digests, requires a sized
660-byte ELF function, and rejects image length changes or any altered byte
outside that function. Each positive VM starts with its complete qualified
image, and the routine bytes and packed rotation table are rechecked afterward.

Each image executes the grid routine, actual world/slot lookup, original
`RotMatrix`, original `ApplyMatrixLV`, and actual rectangle building, row
splitting and slot selection. These functions have no output stubs. Reviewed
COP2 transfers invoke the pinned Nymashock core for both MVMVA commands;
MAC, IR, flags and command cost are checked against independent integer models.
Every command request executes in the native core; no hardware-command cache
is used. This is a reuse of the established native composition for two C
candidates, rather than a newly recovered SDK implementation.

The checks compare whole guarded graph buffers, ordered dependency arguments,
query output, the matrix and its projected vector, template bytes, stack guards
and saved registers. All candidate instruction words that differ from the
original must execute. Private fault controls must execute their changed word
and produce incorrect graph or projected-matrix bytes; a trace-only difference
or an exception is insufficient.

## Input domain

The retained 13,230 original native-GTE graph inputs are repeated for both
candidates. An extension defines 11,550 additional inputs:

| Dimension | Values |
| --- | --- |
| Selected world labels | All seven labels |
| Yaw words | Eleven interval-edge and signed-angle cases |
| Long projection distances | Ten signed-word boundaries, including `INT_MIN` and `INT_MAX` |
| Width and height | `(1,1)`, `(20,20)`, `(21,19)`, `(0,0)`, `(-3,4)` |
| Address aliases | Physical, KSEG0 and KSEG1 |

Valid world positions, cell boundaries, pitch/roll, slot permutation, initial
buffer contents and radii of 1, 4 or 9 also vary deterministically. Projection
is derived from the real rotation-table arithmetic and long-vector split,
rather than supplied independently of the input distance.

Uniqueness is checked from the actual initialized buffers, pointers, template
and width/height argument words. A change to an unused case flag is not a new
fixture. The ten extension distances are disjoint from the retained graph
profile; the full input identities must also be disjoint at runtime. These
are constructed analysis graphs, not additional player scenarios or features.

## Recorded result

All **24,780 distinct inputs per image** passed: 13,230 retained inputs and
11,550 inputs added to this native-GTE graph profile. The original and both
compiled C images completed **74,340 positive executions** with identical
graph/trace digests. The native core executed **148,690 commands**, including
ten commands for the five fault controls and excluding its identity self-check.
All eleven routines were observed in each positive image.

| Decision/output | Inputs per image |
| --- | ---: |
| Longitudinal grid | 15,288 |
| Transverse grid | 9,492 |
| One emitted rectangle | 9,699 |
| Two emitted rectangles | 8,478 |
| Three emitted rectangles | 4,284 |
| Four emitted rectangles | 2,319 |

Both changed edge instructions executed 6,510 times. In the cell-reuse image,
both changed coordinate loads executed 24,780 times and both changed
longitudinal instructions executed 9,990 times. Four candidate faults produced
wrong graph buffers; the separate SDK high-part fault produced a wrong
projected matrix. Each changed control word executed in its detecting input.

Three further compiler studies recorded 86 qualified compilations over 80
distinct source texts, including repeated controls. They tested actual
halfword-origin boundaries, consumed orientation/origin records, and a consumed
inclusive-offset helper. None improved the retained seven-byte minimum. Those
compiler observations add no native behavior claim of their own.

The tooling suite passed **557 tests with two expected skips** on Windows
Python 3.14 and WSL Python 3.13. All 392 protected game build inputs and the
canonical executable remain unchanged. The C count stays **194,212 / 199,912
bytes (97.15%)**, with nine assembly functions and 24 inherited unused-storage
explanations still open. Bounded NPC coverage remains 28 / 107; whole-feature
and whole-encounter acceptance remain zero. The new checker belongs to the
existing developer-analysis capability; it adds no original game feature,
optional mod or new capability category.

[grid-native-composition-checks.json](grid-native-composition-checks.json)
records hashes, counts, controls and the unchanged before/after inventory.

## Reproduce

Use the matching compiler environment and a current canonical build. Prepare
each complete source unit in a fresh private directory:

```bash
python research/render_grid/prepare_candidate.py --variant edge \
  --output .decomp-lab/grid-sdk-edge-source-new
python tools/decomp_workbench.py check \
  --source src/scene/render_context.c \
  --candidate .decomp-lab/grid-sdk-edge-source-new/render_context.c \
  --function func_8004C6A8 --output .decomp-lab/grid-sdk-edge-build-new

python research/render_grid/prepare_candidate.py --variant cell-reuse \
  --output .decomp-lab/grid-sdk-cell-source-new
python tools/decomp_workbench.py check \
  --source src/scene/render_context.c \
  --candidate .decomp-lab/grid-sdk-cell-source-new/render_context.c \
  --function func_8004C6A8 --output .decomp-lab/grid-sdk-cell-build-new
```

Each workbench command currently returns exit code **1**, reporting eight or
seven differences. That is an expected matching-gate failure, not acceptance.
Keep the source, comparison JSON, complete image and diagnostic ELF together.

Build a new private Windows bridge using the
[native GTE instructions](RENDER_GTE.md#reproduce-locally). Then run inside WSL/Linux,
supplying the Windows path to the pinned local BizHawk runtime:

```bash
python tools/verify_render_grid_candidates.py \
  --edge-build .decomp-lab/grid-sdk-edge-build-new \
  --cell-build .decomp-lab/grid-sdk-cell-build-new \
  --bridge .decomp-lab/grid-sdk-bridge-new.exe \
  --runtime 'C:/Tools/BizHawk-2.11.1' \
  --output .decomp-lab/grid-sdk-candidates-new.json
```

Output and log names must be new and private. Public tests use synthetic data
and do not require the game, an emulator or Unicorn. The native run requires
the optional pinned analysis dependencies and the original local game inputs.

## Remaining recovery work

The source gate still requires complete executable equality without padding,
physical-register binding, copied assembly or instruction substitution.
The extension provides bounded evidence about the existing C candidates; it
does not resolve their arithmetic/allocation differences or establish natural
scene ownership, rendering, audio, input reachability, full PS1 CPU timing or
whole-feature acceptance. C recovery and the separate Bevy port retain their
own counts. Original NPC AI and AI-assisted developer tools remain separate.
