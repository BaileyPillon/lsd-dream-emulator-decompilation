# Collision fraction operands and reload lifetimes

The published `func_8001F8B8` research candidate now calculates its fixed-point
ratio from two real fraction operands. Its complete executable is unchanged:
505,856 bytes, SHA-1 `729f0d86098eca285c436a35d01374574cc8abf4`, with the same
22 differing bounding-box displacements. It remains unaccepted; the canonical
game still uses the original assembly function.

## Consumed arithmetic

The previous fragment wrote `normal.fraction = (dot, 1)` and
`numerator = (-start_dot, 1)`, then independently assigned
`ratio = (-start_dot, dot)`. Neither written fraction was read. The current
pointer helper computes their quotient:

```c
result->numerator = a->numerator * b->denominator;
result->denominator = a->denominator * b->numerator;
```

The two denominators are one at this call site. The bundled compiler folds
those multiplications and emits exactly the earlier complete candidate image.
This explains the operand stores through useful source operations without
adding storage, assembly or register bindings. The SDK vector and shared
normal/fraction union remain unchanged. This helper had appeared in an older
private workspace; publishing and qualifying it does not establish a new
algorithm discovery or recover the original author's source.

The [source recipe](../research/collision/README.md) reproduces the candidate.
Its existing bounded native fixtures apply to the same executable bytes; this
study adds no new native cases and does not rerun those fixtures.

## Actual reload locations

Three complete-unit observations use the extended
[compiler stack tracer](../research/collision/trace_compiler_stack.py). In each
case, normal compilation and observed compilation produce identical complete
assembly output. The exact bundled compiler hash and completed `alter_reg`
caller contexts are required. These are observations of the compiler, not
physical-register assignments in game source.

| Complete-unit source | Target allocator events | Reload allocations | Emitted frame |
| --- | ---: | ---: | ---: |
| Previous published fragment | 43 | 7 | 352 bytes |
| Consumed fractions, caller-owned final square | 43 | 7 | 352 bytes |
| Consumed fractions, helper-owned final square and later bounds | 42 | 7 | 336 bytes |

For the current closest candidate, source objects occupy virtual local offsets
0 through 236. Seven four-byte reload allocations then grow that area through
248, 256, 264, 272, 280, 288 and 296 bytes after alignment. The bounds object
was already allocated at virtual offsets 72 through 88. None of the reload
calls creates that early region. The 24-byte outgoing-argument area places the
candidate's bounds at SP+`0x60` and final square at SP+`0xF0`; the original uses
SP+`0xF0` for both.

Moving the final square into a scalar-return helper and declaring bounds at
their later use permits storage reuse, as the earlier
[lifetime investigation](COMPILER_LIFETIMES.md) established. The current
complete-unit control loses 16 bytes from its frame and retains 117 differing
function bytes. Its seven reload allocations start at virtual offset 220,
after the smaller source workspace. Reload is therefore not an explanation
for the original early 16-byte region in either observed source form.

## Qualified source comparisons

Every row below uses a complete translation unit, the canonical compiler flags
and a fully linked candidate executable. Function comparisons use its complete
sized MIPS ELF symbol. All fourteen source forms compile and link; none matches
the original function or the complete executable. Length differences are
reported separately from changed bytes within the common function range.

| Fraction interface | Final square | Function bytes | Changed function bytes | Frame bytes |
| --- | --- | ---: | ---: | ---: |
| Pointer operands/output | Caller | 1,944 | 22 | 352 |
| Pointer operands/output | Helper | 1,944 | 117 | 336 |
| Value operands, pointer output | Caller | 2,020 | 1,041 | 376 |
| Value operands, pointer output | Helper | 2,020 | 1,056 | 344 |
| Value operands and result | Caller | 2,044 | 1,034 | 384 |
| Value operands and result | Helper | 2,044 | 1,037 | 352 |

Eight further forms group the complete contact calculation behind a consumed
16-byte result containing the point, distance and status. Two field orders,
returned or pointer-output results, and caller-owned or helper-owned final
squares are tested. Returned results emit 2,112-byte functions; pointer-output
results emit 2,080-byte functions. Their best comparison still differs in
1,521 bytes. The real result boundary adds copies and fails to reproduce the
original layout. These are rejected source hypotheses, not substitutes for
matching C.

The pointer rows include repeated baseline/lifetime controls. The fourteen
qualified comparisons are this study's executed forms, not fourteen new
recovered algorithms. No dummy fields, physical register bindings, compiler
flag changes or instruction substitutions are used.

## Evidence and remaining work

[collision-fraction-checks.json](collision-fraction-checks.json) pins the source,
complete image comparisons, allocator records and private experiment reports.
All 392 protected build inputs remain unchanged. Current canonical C recovery
is 194,212 / 199,912 bytes (97.15%): nine assembly functions and 24 inherited
unused-storage explanations remain. Original NPC behavior, AI-assisted tools
and optional mods retain their separate counts.

The next source question is the ownership of the original early aggregate
storage. The observed late reload slots and these contact-result interfaces
do not explain it. Complete function recovery, natural collision scenes,
PS1 timing and whole-feature acceptance remain open.
