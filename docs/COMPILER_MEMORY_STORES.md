# Compiler memory-store decisions

The original 88-byte bit-field helper, `func_8001EDAC`, still contains an
unexplained eight-byte local array in inherited matching C. A fully consumed
two-word work object explains the frame size, but its closest source form emits
96 bytes: the original 22 instruction words in order, plus two local stores.
Those instructions are only compared diagnostically; no code is removed or
rewritten, and the candidate is not promoted.

The helper updates one packed word and returns the replaced bits. Fifteen
current call sites use it for transform, effect and sprite flags. Finishing the
work object's reads before the external word store reduces its mismatch to
28 differing text bytes, but does not remove its two stores.

## Actual compiler observation

The [memory-store tracer](../research/compiler/trace_memory_stores.py) observes
`insn_dead_p` and its nested RTL equality comparisons in the exact bundled
i386 GCC 2.6.3. It reads SET/MEM destinations, the compiler's last stored
location and actual return values. Normal and observed complete assembly must
agree. The producer rejects unsupported compiler identities, changed inputs,
unfinished observations, debugger errors and existing evidence directories.

| Observed source | Memory-store decisions | Address-equality calls | Dead decisions |
| --- | ---: | ---: | ---: |
| Current inherited helper | 2 | 0 | 0 |
| Consumed work pair, reads completed before output store | 6 | 8 | 0 |

These are compiler calls, not counts of game instructions or gameplay cases.
The pair's local destinations are the frame base and frame base plus four;
their later stored locations differ. The actual equality returns are zero.
The historical `flow.c` rule can delete a nonvolatile store when its destination
equals the later tracked memory destination. It does not establish that these
two function-local stores can be discarded. The emitted stores remain.

An absent-function control is rejected after compilation and preserves its
diagnostics. Normal debugger breakpoint machinery may temporarily instrument
compiler memory; the backend makes no extra explicit memory writes, forces no
registers or results and invokes no extra inferior functions.

## Rejected source families

Eighteen additional fully consumed bit-range/argument-record forms have no
exact match. They remain standalone ABI hypotheses; typed callers and complete
executable equality would be required before changing the actual interface.
Earlier 23 qualified unpadded math forms and two inherited-source calibrations
are preserved separately.

Thirty-two new grid extent-word forms test four-byte width/height ownership
while preserving their numerical values. They do not improve the existing
eleven-byte best match or resolve the formal-height/width-allocation tradeoff
in [GRID_PHASES.md](GRID_PHASES.md). No grid source is promoted.

Three isolated bodies compiled with the retained C++ frontend produce the
same bytes as their C counterparts. That diagnostic uses equivalent integer
typedefs after the project's C-only boolean declarations were rejected. It is
not a complete C++ translation-unit check or matching C recovery. Failed
preprocessing, declaration-order and definition-splitting attempts remain
separate from the qualified results.

## Reproduce and continue

Run in the configured Linux/WSL environment with a selected C function that
has memory-store decisions:

```bash
python research/compiler/trace_memory_stores.py \
  --source src/base/object_math.c --function func_8001EDAC \
  --output .decomp-lab/memory-stores-new
```

Use `--compiler-mode g0` for G0 units. Outputs are private and refuse overwrite.
[compiler-memory-stores-checks.json](compiler-memory-stores-checks.json) pins
the producer, observed compiler, source trials and qualification records.
The original source, generated assembly, raw compiler traces and game inputs
remain outside the publication metadata.

Current C remains 194,212 / 199,912 (97.15%), with nine assembly functions and
24 inherited storage explanations. All 377 tooling tests pass locally. This
extends compiler analysis without new gameplay cases, source explanations,
whole-feature acceptance, NPC coverage, developer-capability or mod counts.
