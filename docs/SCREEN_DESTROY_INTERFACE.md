# Screen destruction callback interface

The common screen view declared its `0x04` Destroy callback as returning
`void`. Both known runnable screen tables instead bind
`base_class_destructor`, whose declared return type is `base_class_t *`.
The common view now uses that same callback type, and `run_screen` passes
the receiver as a base-class pointer.

The original destructor calls Cleanup, releases the receiver through the
pool allocator, and returns NULL. The game continues to preserve and return
the earlier Run result. The complete 505,856-byte executable remains
identical to the canonical game.

| Supported view | Original receiver table | Destroy word |
| --- | --- | --- |
| Common / main menu | `0x80086B60` | `0x80086B64` |
| Common / dream chart | `0x80087AAC` | `0x80087AB0` |

Both words contain `0x80017EB0`, the original base destructor. The
[three analysis callers](../research/screen_lifecycle/destroy_consumer.c)
consume its pointer return. The common caller fails with a void-value
diagnostic against the earlier declaration. All three now compile with
warnings treated as errors and produce identical complete 48-byte bodies.
Four target assertions check pointer width and each Destroy-slot offset.

The [bounded interface checker](../research/screen_lifecycle/verify_destroy.py)
passes **96 supported typed profiles**: 24 each for common/main,
common/chart, main/main and chart/chart. They cover three RAM aliases, two
initial memory patterns and four successful pool shapes. The original
factories, destructor and pool routines execute; full expected manager,
pool and opaque argument buffers, receiver forwarding, saved registers,
stack guards, return value and release protocol are checked. Cleanup returns
an unrelated V0 so it cannot supply the destructor's expected NULL result.

Three wrong-slot controls execute a changed analysis-caller instruction,
dispatch Cleanup directly, return its unrelated value and omit pool release.
All three are rejected. An independent audit checks 20 complete original
function spans, all three complete callers and every supported case and
expected buffer hash. Earlier cross-concrete-type prefix-only probes are
excluded from these C-interface counts.

The two constructors and two cleanup bodies remain explicit output
contracts. Graphics initialization is not reached. Natural construction,
resource cleanup, rendering, input, timing and whole-screen acceptance
remain open. The common view's opaque inherited slots and other factory
interface warnings remain separate recovery work.

[Validation metadata](screen-destroy-interface-checks.json) records the
source hashes, qualified original functions, backend and bounds. Matching C
remains **197,172 / 199,912 bytes (98.6294%)**, with two game assembly
functions and three inherited storage explanations. The inventory retains
40 provisional feature groups and zero accepted whole features. This
interface correction adds no original gameplay or model-service call.
