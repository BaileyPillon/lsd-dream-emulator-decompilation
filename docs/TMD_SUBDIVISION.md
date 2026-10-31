# Original recursive polygon subdivision

The draw-entry comparison now passes **1,147 constructed calls**, including
263 recursive cases beyond the earlier 884-call profile. Original F3, F4, G3,
G4, FT3, FT4, GT3 and GT4 code executes through subdivision depths 1–5.
Complete packet, ordering-table, context and supplied workspace buffers agree
with scalar predictions, along with GTE state, commands and saved registers.

This advances renderer verification without changing game C or the player.
It accepts **zero** whole gameplay features or NPC encounters. The later
[primitive-run profile](TMD_PRIMITIVE_RUNS.md) adds bounded shared-state runs.
Original model-corpus drawing, replacement matrices, natural scenes, GPU
rasterization and PS1 timing remain open. The fixtures do not establish the full
input domain of every recursive routine.

## Executed results

| Measurement | Result |
| --- | ---: |
| Original draw-entry calls | 1,147 |
| Earlier single-primitive cases retained | 884 |
| Additional recursive cases | 263 |
| Original MIPS instructions | 1,977,904 |
| Actual native GTE commands | 12,356 |
| Recursive body entries | 5,215 |
| Emitted subdivision packets | 15,648 |
| Recursive cases that submit packets | 198 |
| Recursive cases culled before subdivision | 65 |
| Subdivision families | 8 |
| Tested subdivision limits | 1–5 |
| Original-code fault controls detected | 9: four prior, five recursive |

The [machine-readable report](tmd-subdivision-checks.json) records per-family
and depth counts, qualified original ranges, source/backend hashes, controls
and the private journal hash. The prior [3,333-case GTE qualification](gte-packet-state-checks.json)
remains unchanged. Subdivision requires only RTPT from that already-qualified
command set, so the existing native host and installed emulator are reused.

The recursive cases include physical/KSEG0 pointers, transparency, fog,
canonical and deliberately constructed high-byte OT heads, odd coordinates,
raw-texture flags and the original division-limit override. Five separately
observed return sites distinguish near, right, left, bottom and top culling.
Actual recursive body and packet-emitter entries agree with the scalar counts.

## Preserved implementation details

Triangles visit recursive children in a different order from their final
four leaf emissions. The oracle preserves both orders and their resulting OT
links. Gouraud colors and UV bytes use original integer interpolation; stale
unused alpha and padding bytes retain their workspace history. Original
saved return addresses in recursive workspaces are independently predicted
from checked shader/recursive JAL sites, rather than omitted from comparison.

The flat F4 routine computes its center from two already rounded edge
midpoints. G4, FT4 and GT4 compute a four-corner average. These differ for odd
coordinates, and the fixtures preserve that distinction. Projection batches
and depth-field stores also differ between families; the model retains those
differences rather than replacing them with one idealized tessellator.

The recursive emitters OR packet length into the old OT head, whereas the
ordinary submission path masks the pointer portion. Synthetic high-byte
heads intentionally expose that difference. Such a constructed head is not
claimed to represent a valid game history. The earlier bounding-box endpoint
quirk is preserved as well.

All 64 architectural GTE words, command order and native data-write/command
counters are compared after each original draw call. The recursive model
shares the separately native-qualified integer GTE arithmetic. It does not
execute original MIPS or provide stubs for original function results.
The native host still uses reviewed host transfers for inlined architectural
CR/cache access; this is agreement with the pinned emulator core, rather
than independent hardware validation.

The analysis VM compares the entire 64 KiB GPU arena, 4 KiB OT, 4 KiB
scratchpad, 536-byte triangle arena, 1 KiB quad arena and fixed-global outputs.
These are declared supplied analysis arenas, not an inferred proof of every
real game's allocator limit. All VM bytes outside declared mutable spans are
hashed, and SP/GP/RA/saved S/FP values are checked. Bounded callee stack
temporaries remain permitted writes without independent byte prediction.

The five recursive controls mutate a midpoint destination, a color average,
a quad-center average, emitted packet length and the near threshold. Each
executes original code and returns with ABI/immutable-VM guards intact; every
output disagreement is detected. The near-threshold control also changes
the observed branch/command counts, as expected.

## Reproduce

Use the existing optional Unicorn 2.1.4 environment, qualified twelve-command
native host and BizHawk 2.11.1 installation. The [draw-entry guide](TMD_RENDERER.md)
documents host compilation. Choose a fresh output path:

```powershell
python -B tools/verify_tmd_renderer.py --executable rom/SLPS_015.56 --bridge .decomp-lab/gte-packets.exe --runtime "D:/tools/BizHawk-2.11.1" --recursive --output .decomp-lab/tmd-subdivision
python -B -m unittest tests.test_tmd_renderer_model tests.test_tmd_recursive_model -v
```

The profile retains its 15-minute/2 MiB output bounds and permits at most one
million instructions per call. The GTE host loads no game or BIOS and does
not attach to the player or the separate year replay. CI uses literal models
and synthetic memory-transfer fixtures without original game inputs. Captures
stay private under the contribution policy; superseded journals have verified
lossless retention and exact-path restoration.

Original NPC behavior and optional AI-assisted analysis/modding remain
separate. This profile makes no model API calls or gameplay modifications.
