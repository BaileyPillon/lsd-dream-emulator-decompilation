# Original sprite scaling audit

The original `func_8004441C` passes **203,472 bounded native cases** and four
deliberately wrong controls without external stubs. A full C translation-unit
candidate passes the same fixtures but differs in **12 executable bytes across
four instructions**. The canonical build retains the original assembly.

The recorded hashes, scopes and fixed before/after counts are in
[ui-scale-checks.json](ui-scale-checks.json). This extends UI evidence without
adding an original feature, C promotion, NPC callback, developer capability or
whole-feature acceptance.

## Recovered behavior

The 560-byte leaf receives the sprite, a mode word and four signed halfwords:
X numerator/denominator followed by Y numerator/denominator. The original
sprite vtable at `0x8006F2C4`, slot `0x48`, points to this routine. It writes the
scale halfwords at sprite offsets `0x60` and `0x62`.

For each nonzero denominator, the fixed-point ratio is:

```text
4096 * trunc(numerator / denominator)
    + trunc(4096 * signed_remainder(numerator, denominator) / denominator)
```

Nonzero mode replaces each scale with the ratio narrowed to signed 16 bits,
capped above at 30,000. A zero denominator selects 4,096 in that replacement
branch. There is no lower clamp.

Zero mode tests `old_scale + signed16(ratio) < 30001`. If true, it stores the
low halfword of `old_scale + ratio`. Otherwise it stores 1 if either input
halfword for that axis was negative, or 30,000 if neither was negative. The
negative flag is an OR of the two signs, including when both are negative.

A skipped division leaves its incoming `T1` or `T2` value available. Increment
mode can consume that value. Silently initializing those ratios to zero would
change native behavior. The fixtures seed the registers explicitly; this is
machine-state evidence, not a claim that such inputs form a portable C API.

## Input overlap and observation order

The X denominator stays cached. In replacement mode the routine reads Y's
denominator again **after writing X's scale**. If the input record overlaps the
sprite, that write can change the second denominator test. Caching Y's initial
denominator changes the final output in 32 of the recorded overlap fixtures.

One synthetic witness places the input record at sprite offset `0x5A`, with
fractions `(1, 1, 7, 0)` and incoming Y ratio `0x1234`. X becomes 4,096, making
the overlapping Y denominator nonzero; Y then becomes 4,660. A cached zero
denominator would instead produce Y = 4,096. These are synthetic dependency
fixtures; normal gameplay reachability remains to establish.

The verifier decodes executed halfword reads and stores, then checks each
store by readback at the following instruction. It compares their order and
widths, both complete guarded buffers, the unused stack region, stack pointer,
GP, RA and saved registers.

An initial global Unicorn memory-write hook caused the stack-restoration
instruction to execute twice after a store in a jump delay slot. An eight-run
diagnostic isolated this instrumentation failure: unhooked and read-only runs
passed; the two replacement-mode runs with the write hook failed. Those logs
and the failed producer remain private and hash-pinned separately. The
successful audit uses instruction observation and readback.

## Coverage and C matching

| Fixture family | Cases |
| --- | ---: |
| Every signed 16-bit numerator, paired across both axes, in both modes | 131,072 |
| Every denominator word, with one mode per word | 65,536 |
| Signed edges and incoming-register values | 4,560 |
| Overlapping records and cached-segment aliases | 2,304 |
| Total original cases | 203,472 |

The controls reject a cached Y denominator, zeroed incoming X ratio, a
subtracted X sum and an incorrect replacement clamp. Each changes a checked
output. The candidate adds another 203,472 native runs, for 406,944 original
and candidate runs in total.

The candidate naturally allocates the original 16-byte stack frame. It uses
no padding, embedded assembly or physical register binding. Its remaining
differences are operand order in two additions and scheduling of Y's scale
load relative to a shift. They still prevent complete-executable equality.
108 additional independent-axis and typed-access helper trials, plus one
baseline reproduction, produced no exact match with the canonical flags.

## Reproduce locally

After preparing the current complete canonical build and installing the
optional dependencies in `requirements-analysis.txt`, run in Linux or WSL:

```bash
python tools/verify_ui_scale.py --output .decomp-lab/my-ui-scale-check.json
```

The report must have a new path inside `.decomp-lab`; existing evidence and
public destinations are rejected before game inputs are loaded. The tool
makes no model API calls and modifies no original game files.

This MIPS32 functional audit does not emulate PS1 load-delay timing, bus
faults, interrupts, GPU drawing, controller flow or complete menu behavior.
Full C recovery, virtual-call closure and whole-feature acceptance remain open.
