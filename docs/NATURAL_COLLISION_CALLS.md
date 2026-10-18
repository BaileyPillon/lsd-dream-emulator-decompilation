# Natural primitive collision calls

The original opening route now has sampled call/return evidence for
`func_8001F8B8`, beyond the earlier [entry and argument-role checks](NATURAL_COLLISION_ENTRIES.md).
The verifier reconstructs actual geometry from complete main-RAM snapshots and
compares the original return, nearest distance, contact point, and optional
height with the existing fixed-point collision model. The canonical game and
its assets are unchanged.

| Observation | Result |
| --- | ---: |
| Input frames per recording | 6,000 |
| Hull / primitive entries | 194 / 643 |
| Completed primitive samples | 52 |
| Hits / misses | 19 / 33 |
| Sampled polygon visits | 924 |
| Observed model / geometry addresses | 12 / 12 |
| Samples crossing a frame boundary | 1 |
| Complete main-RAM payload per observer recording | 208 MiB |

Polygon visits and addresses are observations in this history, not unique
asset counts, object identities, or allocation generations. Five packet codes
occur: `0x21`, `0x25`, `0x29`, `0x2C`, and `0x2D`.

## What is checked

The separate native observer records all selected function entries and samples
the first two primitive invocations per observed direct-caller/model-address
pair, with one start per frame and a total limit of 64. Replaying that policy
against all 643 primitive entries selects 52 calls: 570 entries are skipped
after their key's two samples and 21 by the per-frame budget. There is no
overflow, outstanding call, nested skip, or total-limit skip.

Each 988-byte sample records architectural CPU and GTE register views, effective
call/return instruction contexts, and offsets into complete 2 MiB RAM snapshots
at entry and return. The verifier checks the original direct call and link,
actual `JR RA` and delay slot, restored stack, preserved registers, complete
callee bytes, and association with the original entry record. The fifth and
sixth arguments are read from the captured caller stack.

Geometry decoding follows the original packet layouts and declared counts.
Vertex indices, RAM ranges, alignment, output aliases, and unchanged input
buffers are checked. Unsupported packet codes are rejected because the
original decoder leaves their lengths unspecified. The independent algebraic
model retains signed word arithmetic, GTE cross-product/square semantics,
the captured SDK square-root table, and expanded polygon bounds.

Original/rebuilt sample records and complete RAM payloads agree. Every
recorded game output also agrees between original/rebuilt and observer/stock
runs: 6,001 GPU observations, 1,001 RAM observations, 52 complete checkpoints,
and 17,692,008 PCM bytes per run. An additional audit decodes the checkpoint
PNGs and checks retained producer sources and deliberately contradictory data.

The observer reads original CPU/GTE/RAM state. It does not patch game code,
inject RAM, restore a saved state, or control the user's emulator. Its core
build reuses pinned native objects and recompiles the adapter; it is not a
fresh full core build or a general runtime certification.

## Reproduce

Build the separate observer with `--collision-calls`, then record the
[sampling route](../research/headless/collision-call-opening-route.json) using
the existing method recorder and local verified game, BIOS, and media inputs.
Keep original, rebuilt, and distributed-core captures in separate directories.
The recorder preserves its source/profile snapshots with each recording.

```bash
python tools/inspect_collision_calls.py \
  --reference /path/to/original-capture \
  --candidate /path/to/rebuilt-capture \
  --output .decomp-lab/collision-calls-comparison-new.json

python tools/inspect_collision_calls.py \
  --reference /path/to/original-capture \
  --candidate /path/to/stock-capture --mode observer-output \
  --output .decomp-lab/collision-calls-stock-new.json
```

[Publication metadata](collision-call-checks.json) records hashes, counts,
controls, and the unchanged source/feature inventory. Raw game data and private
recordings are not distributed.

## Remaining gates

This checks sampled primitive calls in one route. It does not observe hull
returns, every primitive invocation, complete instruction paths, allocation
ownership, opaque CPU/GTE state, or original hardware timing. Other RAM can
change during a call through interrupt or frame activity; those changes are
not attributed solely to the primitive. Earlier observer discrepancies in
other profiles are not resolved by this result.

Matching C remains **197,172 / 199,912 bytes (98.63%)**. Both collision assembly
functions and three inherited storage explanations remain open. No new C,
whole feature, or whole NPC encounter is accepted. The provisional inventory
remains 40 groups with 38 listed-core C groups; an exhaustive original feature
total is still unknown. No gameplay change or AI model API is introduced.
