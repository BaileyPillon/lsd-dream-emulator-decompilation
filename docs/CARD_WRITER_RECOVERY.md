# Matching save-writer recovery

`func_8004EF6C` is now reconstructed in C in
[memory_card.c](../src/menu/card/memory_card.c). Its complete 960-byte function
matches the original. The complete standard build and a fresh clean build both
reproduce the canonical 505,856-byte Japanese executable, including its caller.
[card-writer-recovery-checks.json](card-writer-recovery-checks.json) records the
source, compiler, build and private-evidence hashes.

| Measure | Before this recovery | After |
| --- | ---: | ---: |
| Matching game C bytes | 194,884 / 199,912 | 195,844 / 199,912 |
| C-byte coverage | 97.48% | 97.97% |
| Known game assembly functions | 6 | 5 |
| Groups with every listed core function in C | 35 / 40 | 37 / 40 |
| Inherited C functions with dummy stack padding | 5 | 5 |
| Entire feature groups independently accepted | 0 / 40 | 0 / 40 |

The writer is shared by memory-card groups F037 and F038; both now have all
their listed core functions in C. These overlapping groups are a provisional
catalogue, and an official exhaustive feature count is unknown. C recovery,
whole-feature acceptance, original NPC scripts and separate analysis/modding
capabilities retain their distinct measures.

## Recovering the argument layout

The closest fixed-argument candidate had eight differing bytes. It assigned
the title to `s5` and the TIM object to `s6`; the original does the reverse.
Both use `s0` for the loaded image pointer. The mismatch affected register
allocation rather than the save-file operations.

Two complete-unit compiler traces observe the actual bundled GCC 2.6.3:
46 allocation calls, 140 priority comparisons, 48 scheduled blocks and two
equivalence updates. Each traced compiler output is byte-for-byte equal to
normal compilation. Separate RTL dumps add only compiler-option comments.

| Value | Fixed-argument candidate | Matching reconstruction |
| --- | --- | --- |
| Title | 2 references, lifetime 33, priority 606, `s5` | 2 references, lifetime 33, priority 606, `s6` |
| TIM object | Lifetime 26 doubled to 52, priority 384, `s6` | Lifetime 26 retained, priority 769, `s5` |

The local allocator doubles the fixed stack argument's lifetime estimate
because of its `REG_EQUIV` memory note. Explicit reads through the historical
GNU MIPS varargs cursor avoid that note. The cursor consumes exactly three
32-bit stack words: TIM-object address, payload address and payload size,
following four arguments in registers. The first stack word is represented
by GNU's `__builtin_va_alist` marker. The declaration and caller retain the
original physical argument layout.

This is a reconstruction for the pinned compiler and R3000 ABI. The historical
interface is described in `ginclude/va-mips.h` in the
[GNU GCC 2.6.3 source archive](https://gcc.gnu.org/pub/gcc/old-releases/gcc-2/gcc-2.6.3.tar.bz2).
The original author's declarations are unavailable; an exact executable does
not identify their source types uniquely. No compiler flags, padding,
register bindings or embedded instructions were added to obtain this match.
Both legacy and ANSI declaration forms passed complete-executable comparison;
the committed version uses the readable ANSI form.

## Verification and remaining scope

The standard and clean builds each account for all 305 objects. The clean
build starts without a build directory or copied objects. The complete
executable retains SHA-1 `76322eeade5ebb22dca57fdeac7d68c30f06308d` and SHA-256
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.

The existing [save-workflow audit](CARD_SAVE.md) was rerun against the current
build identity: 13,152 bounded cases across nine original routines passed,
and seven injected faults were detected. Seven explicit contracts still cover
file I/O, allocation and diagnostic output. These are reverified cases, not
additional independent gameplay scenarios. All 294 synthetic tooling tests
pass locally; public CI exercises those tests without original game inputs.

To repeat the matching build and bounded audit with your own executable:

```bash
python configure.py
ninja check
python tools/progress.py
python tools/verify_card_save.py --output .decomp-lab/save-writer-new.json
```

Physical memory-card I/O, natural failure/cancel paths, complete dream-state
save/load round trips, UI rendering and PS1 timing remain open. The earlier
[cleanup audit](CARD_CLEANUP.md) and [native heap audit](CARD_HEAP.md) retain
their separate scopes and the cleanup function's unresolved source padding.
