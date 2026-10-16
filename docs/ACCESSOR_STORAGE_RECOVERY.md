# Matching accessor storage recovery

Three existing C functions now use consumed data views in place of inherited
unused arrays. The original instructions and complete executable are preserved.
This resolves three of the seventeen remaining inherited storage explanations,
leaving **fourteen**. Their **232 bytes already counted as C**; matching C stays
at **195,844 / 199,912 bytes (97.97%)**, with five assembly fallbacks.

| Original function | Function bytes | Removed unused array | Consumed view fields |
| --- | ---: | ---: | --- |
| `func_8001EDAC` | 88 | 8 bytes | Pointer to the packed word being read |
| `func_8001EE98` | 124 | 8 bytes | Input pointer passed to `ApplyMatrixLV` |
| `glyph_get_char` | 20 | 16 bytes | Glyph receiver pointer and unsigned character |

The four view fields hold thirteen actual data bytes in the target ABI:
three four-byte pointers and one unsigned byte. Compile-time size checks keep
those representations explicit. Every field is consumed by the original read,
SDK call or getter result. No unused field, repeated identity-wrapper chain,
physical register binding, instruction substitution, volatile constraint or
compiler-flag change is introduced.

## Observed compiler allocations

Six complete translation-unit observations cover the original source,
removed-array control and matching reconstruction for the math and glyph units.
Each ordinary compilation has identical complete assembly to its instrumented
compilation. The selected reload allocations are:

| Function | Requested bytes | Local area before / after | Reload pseudo |
| --- | ---: | ---: | ---: |
| Packed-word reader | 4 | 0 / 8 | 82 |
| Matrix input accessor | 4 | 0 / 8 | 82 |
| Glyph receiver accessor | 4 | 0 / 8 | 73 |
| Glyph character value | 1 | 8 / 16 | 76 |

The compiler rounds each request to an eight-byte local allocation. All four
requests occur through `assign_stack_local`, called by `alter_reg` during
reload. Pseudo numbers describe these observed compilations. They do not identify
the original author's declarations. The earlier arrays allocate eight, eight
and sixteen bytes before reload; removing them eliminates those allocations and
fails the complete-image gate.

The observer uses ordinary debugger breakpoints, with no explicit compiler
memory rewriting, opcode substitution or additional inferior function calls.
Nested temporary/local observations of the old arrays describe the same storage
and are not counted as separate allocations.

## Matching evidence

The three initial reconstructions each qualify as one complete sized function
at its original address and reproduce the entire executable. The final readable
math and glyph translation units independently pass the complete-image gate.
The combined promotion also preserves the ordinary build. The fresh complete
build and exact source/trace hashes are recorded in
[accessor-storage-recovery-checks.json](accessor-storage-recovery-checks.json).

The [original actor/model factory profile](ACTOR_FACTORY_OWNERSHIP.md) executes
the packed-word writer through native construction and animation initialization.
Its first campaign preceded the source cleanup; both source versions produce
the same original instruction bytes. The later campaign uses the promoted C.
Neither campaign accepts a complete game feature or natural encounter.

To inspect compiler allocations on your checkout in the configured Linux/WSL
environment with GDB:

```bash
python research/collision/trace_compiler_stack.py \
  --source src/base/object_math.c \
  --output .decomp-lab/math-accessor-allocation-new
python research/collision/trace_compiler_stack.py \
  --source src/menu/glyph.c \
  --output .decomp-lab/glyph-accessor-allocation-new
```

Whole-feature acceptance remains **0 / 40** and bounded NPC callback coverage
remains **36 / 107**. The [frozen objective](../PROJECT_OBJECTIVE.md), original
assets, playable image and separate Bevy port retain their existing boundaries.
