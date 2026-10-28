# Original screen lifecycle verification

This profile composes the original `run_screen`, main-menu and dream-chart
factories, Run methods, base destructor and pool allocator. It checks the
result saved across destruction, receiver/argument forwarding, exact call
order, allocation/free behavior, and complete guarded memory buffers.

The two constructors, two cleanup methods and graphics initializer are five
explicit output contracts. Their original complete bodies are identified and
hashed but do not execute. This profile therefore leaves natural construction,
resource cleanup, graphics, input, timing and whole-screen acceptance open.

From the repository root in the supported Linux/WSL build environment:

```bash
python research/screen_lifecycle/verify.py --output .decomp-lab/screen-lifecycle-new
```

Use the isolated `unicorn==2.1.2` backend qualified by
`requirements-card-heap.txt`; keep other analysis environments unchanged.
The current complete matching build and GNU MIPS tools are required. The
checker reuses its existing 306 objects and makes one symbolic link whose
complete exported executable must remain canonical. GNU sized symbols and
independent ELF extraction must agree for every complete scoped function.

The interval/free-queue prediction is computed before guest execution. It
includes stale payload bytes, so omitting destruction cannot make the expected
heap adapt to the observed call stream. Contracts clobber caller-saved
registers and return unrelated values; cleanup also changes the result field.
The real runner must preserve the earlier Run result across those changes.

Cases cover both factories, signed result boundaries, chart-flag boundaries,
two initial memory patterns, four successful pool shapes and an undersized
pool. Nine address profiles cover every pair of object/create/graphics RAM
aliases. They do not exhaust every three-way alias combination. Exhaustion
uses one result/flag configuration because those contracts are never reached.

On exhaustion, a separate original factory call must return zero. The original
runner then attempts its word read through address zero at `0x80026540`.
The checker stops at that observed access; it does not predict the subsequent
PS1 exception, RAM-vector contents, crash, recovery or hardware behavior.

Three private instruction changes must execute and be rejected: discard the
saved Run result, omit Destroy, and change the forwarded Run mode. The checker
retains a compact per-case journal, hashes, backend identity and witnesses;
it creates no disc, emulator clone, RAM capture or model-service request.

Indirect-call records distinguish `pre_delay_arguments` from `entry_arguments`
observed when the target is entered. The Run call sets its third argument in
the delay slot; using the earlier register snapshot would misreport its mode.

See [the findings](../../docs/SCREEN_LIFECYCLE.md) for the recorded campaign
and its remaining evidence limits.

The separate [typed Destroy check](../../docs/SCREEN_DESTROY_INTERFACE.md)
compiles three pointer-returning consumers with warnings treated as errors:

```bash
python research/screen_lifecycle/verify_destroy.py --output .decomp-lab/screen-destroy-new
```

It checks 96 supported initialized profiles through the original factories,
destructor and pool release, with constructor/cleanup output contracts and
three executed wrong-slot controls. It uses the same isolated backend and
does not count cross-concrete-type prefix probes as supported C calls.
