# Original compiler register allocation

The [allocation tracer](../research/compiler/trace_allocation.py) observes the
actual bundled compiler's local and global register decisions. It preserves
complete assembly output and checks returned decisions against the compiler's
own RTL dump. This extends the existing candidate-analysis workflow; it does
not execute the game or promote a C function.

The later [bounds source-lifetime report](BOUNDS_SOURCE_LIFETIMES.md) observes
the current 21-byte-different candidate in its complete source unit. The
38-byte candidate and coverage figures below retain their historical checkpoint;
current source counts are in the [expanded audit](SOURCE_LAYOUT_EXPANDED.md).

## Reproduce an observation

Run from the repository root in the Linux/WSL build environment with GDB and
the configured MIPS preprocessor available:

```bash
python research/compiler/trace_allocation.py \
  --source src/menu/card/memory_card.c \
  --function func_8004EF6C \
  --output .decomp-lab/writer-allocation-new
```

The default compiler mode is G8. Use `--compiler-mode g0` for G0 translation
units. A source file may be a complete private candidate unit. The output
must be a fresh directory inside `.decomp-lab`.

The producer and GDB backend both require compiler SHA-256
`3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab`.
The observer decodes that compiler's i386 tables: references, live lengths,
call counts and allocation numbers use 32-bit values; `reg_n_sets` and
`reg_renumber` use 16-bit values. It avoids reading `reg_renumber` before
`local_alloc` initializes the table.

The backend observes `local_alloc`, `update_equiv_regs`, `find_reg` and
`allocno_compare` using ordinary GDB entry/return breakpoints. It makes no
additional explicit inferior-memory writes, forces no compiler results and
calls no extra inferior functions. Normal debugger breakpoints can temporarily
instrument compiler memory.

`allocations.json` retains before/after pseudo-register state, global allocation
returns and priority comparisons. `report.json` is written only after the
compiler exits successfully, complete normal/observed assembly agrees,
register dispositions agree with the selected function's dump, all observed
priority comparisons agree with the GNU reference calculation, and input
hashes remain unchanged. Diagnostic `-da` options may change option comments;
instruction changes are rejected. Missing functions, unfinished calls and
failed checks retain their raw logs without a passed report.

The priority calculation follows [GNU GCC 2.6.3](https://gcc.gnu.org/pub/gcc/old-releases/gcc-2/gcc-2.6.3.tar.bz2)
`global.c`: `floor_log2(references) * references / live_length * 10000 * size`,
truncated to an integer, with the allocation number as the tie break. Agreement
is checked against actual returns from the bundled compiler rather than
assuming the reference source is identical to the vendor build.

## Measured runs

Five qualified runs preserve complete normal/observed assembly:

| Selected input | Local / equivalence calls | Global allocations | Priority comparisons |
| --- | ---: | ---: | ---: |
| Bounds candidate with address-word reuse | 1 / 1 | 6 | 10 |
| Bounds pointer control from the source comment | 1 / 1 | 5 | 8 |
| Matching writer in its complete translation unit | 1 / 1 | 23 | 70 |
| Synthetic scalar leaf, G0 | 1 / 1 | 0 | 0 |
| Same synthetic leaf, G8 | 1 / 1 | 0 | 0 |
| Total | 5 / 5 | 34 | 88 |

The zero-event cases are recorded explicitly. They are compiler observations,
not original game behavior fixtures. An actual absent-function control fails
qualification and retains its compiler output without a passed report.

## Bounds recovery finding

In the 108-byte, 38-difference candidate, the local allocator gives several
byte and comparison temporaries register 2 (`v0`). The global allocator then
assigns the persistent outside result to register 8 (`t0`), requiring a final
move to `v0`. Its preserved bounds pointer receives register 7 (`a3`). The
original function instead keeps the result in `v0` and the bounds pointer in
register 6 (`a2`). The pointer control has the same earlier scratch allocation,
keeps the bounds pointer in `a0` and gives its result `a3`.

This explains why swapping one declaration or the final result type cannot be
treated as sufficient evidence for the native register assignment. It does
not prove the original author's declarations or rule out other source forms.

The following private compilations were independently rechecked against their
retained source hashes and emitted function bytes:

| Source hypothesis | Compilations | Minimum differing bytes |
| --- | ---: | ---: |
| Reuse the address argument as the outside result before its null check | 18 | 90 |
| Reuse the address word with actual early return paths | 18 | 83 |
| Put the whole predicate behind a reusable inline boundary | 32 | 89 |

None of these 68 compilations matches. The existing 38-byte candidate remains
the best research starting point. No flags, physical-register bindings,
synthetic register interference, padding or copied instructions were introduced.

## Evidence and remaining scope

[compiler-allocation-checks.json](compiler-allocation-checks.json) pins the
producer, backend, guard tests, private observations and source comparisons.
Twelve new tests check custody and false-acceptance boundaries. All 306 tooling
tests pass on Windows and Linux, and the current complete 305-object game
build retains its canonical byte equality.

Matching game C remains **195,844 / 199,912 bytes (97.97%)**. Five game assembly
functions and five inherited source-padding explanations remain. The listed
core-source count stays **37 / 40** provisional groups; independently accepted
whole groups stay **0 / 40**. Original NPC callback, optional-mod and developer
capability counts are unchanged. No new original-game execution or model API
call is claimed. The earlier [bounded bounds checks](RENDER_BOUNDS.md) and
[writer recovery](CARD_WRITER_RECOVERY.md) remain separate evidence.

This tool can guide further source recovery, but exact complete-executable
matching remains the promotion gate. Asset, dispatch and reviewed natural
runtime requirements also remain open.
