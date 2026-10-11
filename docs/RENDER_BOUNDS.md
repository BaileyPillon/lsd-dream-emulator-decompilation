# Original render-context bounds predicate

`func_8004CD38` is a 108-byte function called by
[func_8004CC74](../src/scene/render_context.c) while building render-context row
data. Its original bytes pass **4,648 native fixtures with zero stubs**. Four
deliberately changed instructions are detected. The function still uses
assembly in the matching build; no C promotion is claimed.

## Recovered contract

The first argument holds a pointer to this 12-byte record:

| Offset | Field | Width and interpretation |
| --- | --- | --- |
| `0x00` | Minimum X | Signed 16-bit |
| `0x02` | Minimum Y | Signed 16-bit |
| `0x04` | Maximum X | Signed 32-bit |
| `0x08` | Maximum Y | Signed 32-bit |

The second argument points to two bytes interpreted as signed X and Y
coordinates. The result is 1 for a null bounds pointer or an outside point,
and 0 for an inside point. Minimum and maximum edges are inclusive. Reversed
intervals preserve the original comparisons.

The native data-read order is significant. A null bounds pointer reads no
coordinates. Otherwise the function reads X and its minimum, then its maximum
if the minimum passes. It reads Y and its minimum only after both X checks
pass, then Y's maximum if its minimum passes. The verifier compares each
read's address, width and order, including aliased record/coordinate inputs.

[verify_render_bounds.py](../tools/verify_render_bounds.py) covers these
distinct inputs:

| Fixture group | Cases |
| --- | ---: |
| Complete X-byte sweeps across eight bound layouts | 2,048 |
| Complete Y-byte sweeps, excluding duplicate sweep intersections | 2,040 |
| Additional cross-axis edge pairs | 314 |
| Aliased bounds fields and coordinate bytes | 144 |
| Unaligned byte pointers and cached-segment aliases | 98 |
| Null bounds with an unmapped coordinate pointer | 4 |
| Total | 4,648 |

The layouts include negative ranges, signed 16/32-bit extremes, reversed
intervals and single-edge ranges. The checks compare the result, whole guarded
input buffers, zero native writes, GP, stack, return address and saved
registers. Controls change X's sign extension, the minimum-X load's signedness,
the maximum-Y field or the maximum-X comparison's signedness. Changes exist
only in private Unicorn memory.

Native report: `.decomp-lab/render-bounds-native-proof-first.json`, SHA-256
`be8b114bec3312f41a8de9394eac23f0d2803a3e9e465076bd6891de2b0b0f45`.
Metadata is appended to [features.json](features.json).

After a current matching build, install the optional backend and choose a new
private output filename:

```bash
python -m pip install -r requirements-analysis.txt
python tools/verify_render_bounds.py \
  --output .decomp-lab/render-bounds-native-new.json
```

## C recovery and Ghidra

A source-level experiment tested 48 variants that reuse the address argument
after preserving the bounds pointer and retain narrow minimum comparisons.
Another 24 variants separated minimum reuse from coordinate promotion and
varied the X-condition structure; the best difference remained 38 bytes.
The best 108-byte candidate agrees with the original on all 4,648 fixtures,
including data-read traces and saved registers. It still differs at **38 byte
positions**, so it remains private and is not accepted into the matching build.

Candidate report: `.decomp-lab/cd38-narrow-candidate-behavior-first.json`, SHA-256
`94c67259b0946575b845c2c2170d24950a0f99048640206b5eab4988ecb8e10b`.
No compiler flags, physical-register bindings, synthetic register interference
or copied-opcode C were used. A passing behavior fixture does not meet the
exact-code requirement.

The private [Ghidra MCP](https://github.com/bethington/ghidra-mcp) project now
has the reviewed two-argument, integer-returning bounds prototype. The six
[volume API names](SDK_SIGNATURE_AUDIT.md) were also reconciled with the source
map. Its two reviewed SDK prototypes and the bounds prototype use Ghidra's
MIPS default convention, named `__stdcall` in `mips32le.cspec`. Their parameter
storage was checked against the native register contracts: bounds/point use
`a0/a1`, the volume getter uses `a0/a1/a2`, and automatic volume uses
`a0/a1/a2/a3`. This is Ghidra's MIPS convention name. Unknown-convention
warnings are cleared; the project was saved and the original native bytes
remain unchanged.

Ghidra record: `.decomp-lab/ghidra-reviewed-api-abi-reconciled-first.json`, SHA-256
`1c0c6432c286c5b516fa1f07046687846d6d0fda1a26d1b7cc369f64dc8b4d33`.

## Remaining scope

These fixtures do not cover every possible bounds record or coordinate pair,
full caller traversal, actual stage visibility, framebuffers or PS1 timing.
They add bounded evidence for render-context support in F033 without accepting
the complete rendering group. Matching C remains 194,284 / 199,912 bytes;
seven known game assembly functions and all whole-feature acceptance gates
remain open. The 107-callback NPC denominator and 6,784 NPC fixtures are
unchanged. Developer capability count remains ten; this extends existing
native-analysis and Ghidra workflows. Original gameplay and optional mods
remain separate, and this verifier makes zero model API calls.
