# Original model-backed draw calls

The original SDK mapper, linker and drawer now agree with scalar predictions
in **27,254 model-backed draw calls**. The profile reads all **422 model files**,
**531 TMD tables**, **13,627 object descriptors** and **119,458 source polygons**
directly from the preserved Japanese disc. Each object is tested with two
explicitly supplied opposite inspection cameras, using physical and KSEG0
pointers respectively. No original asset payload is extracted or changed.

This extends [constructed polygon/mode runs](TMD_PRIMITIVE_RUNS.md) to complete
original pools, indices, packet payloads and linked streams. It adds **zero**
matching game-C bytes, gameplay features, whole-feature acceptances or NPC
encounter acceptances. Matching game C remains 199,912 / 199,912 bytes.

## Executed results

| Measurement | Result |
| --- | ---: |
| Original model files | 422 |
| TMD tables / descriptors | 531 / 13,627 |
| Source polygon occurrences | 119,458 |
| Supplied polygon occurrences across two views | 238,916 |
| Original draw-entry calls | 27,254 |
| Actual mapper calls / linker calls | 27,254 / 27,254 |
| Original polygon setup calls | 238,746 |
| Original mode-run entries | 56,082 |
| Original drawer/helper instructions | 56,746,669 |
| Original mapper/linker instructions | 22,929,290 |
| Actual native GTE commands | 820,982 |
| Original unsupported-run returns | 16 |
| Supplied polygon occurrences skipped after those returns | 170 |
| Additional constructed early-return calls | 32 |
| New original-code faults detected | 2 |
| Prior renderer regression calls | 1,521 |

The [native report](tmd-corpus-checks.json) records executed source/backend and
bridge hashes, original function ranges, per-format counts, explicit early
returns and the private compressed journal hash. The
[regression report](tmd-corpus-regression-checks.json) retains the earlier 1,147
single-primitive/recursive calls and 374 shared-state calls under this source
version. All pass, including their twelve distinct original-code controls.
The existing [3,333-case GTE qualification](gte-packet-state-checks.json) and
installed twelve-command native host are reused unchanged.

## Exact data and native preparation

The analysis VM loads each complete original TMD container. Original
`GsMapModelingData` and `GsLinkObject4` execute before each draw. The entire
prepared input buffer is compared after each producer call with the separately
qualified scalar mapping/linking predictions. Vertex/normal pools, indices,
colors, UV/palette words, record padding and descriptor scale fields retain
their original bytes. Native pointer relocation and primitive-run header
mutations are applied to the analysis copy, as the original SDK requires.

The drawer executes original vertex/normal loading, projection, color commands,
packet assembly and ordering-table linking. Each call compares the complete
64 KiB packet arena, 4 KiB OT, 4 KiB scratchpad, 536-byte triangle and 1 KiB
quad workspaces, fixed globals, all 64 architectural GTE words, command order
and native command/data-write counts. Original mode/polygon/recursive/abort
entries, saved registers and VM bytes outside declared mutable spans are
checked. Bounded callee stack temporaries remain permitted writes without
independent byte prediction. The supplied arenas do not prove game allocator
limits, and packet-buffer equality does not establish rasterized pixels.

## Preserved early returns and a runtime tracing target

The original dispatch mask is `0xfd07`. This particular drawer does not dispatch
lit Gouraud `30/00`, `34/00`, `38/00` or `3c/00` runs (hexadecimal). Encountering
one returns from the entire invocation, retaining prior output and skipping
later polygons. The oracle preserves that behavior, including unchanged GTE
state and unstaged GPU bytes when the unsupported run is first.

The actual disc contains **43** such packets in **eight objects** across four
STG04 LBD files. Their first unsupported runs leave **85 source polygons**
unvisited, or 170 occurrences across the two views; 42 of those source polygons
are later packets rather than unsupported formats themselves. These are
reported early returns, not omitted cases or newly implemented shaders.

The reproducible [static dispatch inspector](tmd-dispatch-inspection.json) finds
seven affected objects with no tag-nonzero primary-grid references. The eighth,
`/CDI/STG04/M014.LBD`, descriptor 18, has four such references. This identifies
a concrete tracing target. It does not prove unused/collision-only roles,
natural visibility, runtime header changes or the complete in-game draw route.

Thirty-two constructed native calls test unsupported runs first and after
supported output across aliases and transparency bits. Two analysis-only
original-instruction controls redirect an unsupported mode to an unlit shader
and replace the normal pool with the vertex pool. Both return with saved
ABI/immutable-memory guards intact and both disagreements are detected.

## Camera and acceptance boundary

The caller supplies a scaled integer oblique rotation, recentering translation
and H=512. Opposite views expose ordinary face orientations while keeping the
original points and supplied projection within the bounded arenas. This is an
inspection policy, not recovered game camera/light state or authored scale.
Buffers and GTE state reset between object invocations. World-grid selection,
live caller attributes, frame-wide OT composition, dynamic lights, natural
scene history and exact GPU rasterization still require separate verification.
These fitted corpus views do not enter subdivision; the earlier constructed
profile continues to cover all eight recursive families through depth 5.
Full input-domain and hardware-timing acceptance remain open.

## Reproduce

Reuse the existing Unicorn 2.1.4 environment, pinned original disc, successful
static inventory and twelve-command host described in the
[draw-entry guide](TMD_RENDERER.md). Choose fresh output paths:

```powershell
python -B tools/verify_tmd_corpus.py --disc "D:/Games/LSD/LSD.bin" --inventory .decomp-lab/model-inventory.json --bridge .decomp-lab/gte-packets.exe --runtime "D:/tools/BizHawk-2.11.1" --output .decomp-lab/tmd-corpus
python -B tools/inspect_tmd_dispatch.py --disc "D:/Games/LSD/LSD.bin" --inventory .decomp-lab/model-inventory.json --output .decomp-lab/tmd-dispatch.json
python -B -m unittest tests.test_tmd_corpus_model tests.test_tmd_dispatch_inspector -v
```

The corpus audit has a one-hour ceiling, a one-million-instruction bound per
native call, a 1 MiB compressed per-file journal bound and 2 MiB output bound.
The public report contains hashes/counts, with private captures retained outside
Git. CI runs synthetic literal pool, dispatch-mask and early-return tests
without game assets. The separate native GTE host loads no game or BIOS and
does not attach to the player or the live year replay.

Original NPC behavior, optional mods and AI-assisted analysis remain separate.
These tools make no model API calls or gameplay changes.
