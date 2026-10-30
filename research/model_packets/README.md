# Model packet audit

The public tools inspect a caller-owned raw disc and compare vertex decoding
with the original PS1 instructions. [Results and scope](../../docs/MODEL_PACKET_DECODING.md)
explain the fixture boundary, complete corpus counts and unverified rendering
semantics. No game assets or native capture payloads are included here.

`layout-fixtures.json` is an independent literal table for signed-coordinate,
header, mode and gradation checks. The production parser derives its offsets
from field groups. Keep the literal fixtures independent when changing the
parser, and retain the executed wrong-offset and wrong-stride controls.

Run reports and per-object journals stay in a fresh private output directory.
Reuse an existing analysis environment and raw disc. Do not extract another
asset tree, copy a runtime or regenerate retained evidence just to inspect it.
