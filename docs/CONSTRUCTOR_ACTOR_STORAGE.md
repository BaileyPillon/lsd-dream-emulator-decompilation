# Menu constructor and actor allocator storage

Two existing C functions now explain their original stack layout with consumed
method or table references. The menu constructor's unused eight-byte array and
the actor allocator's unused twelve-byte record tail are removed. Both complete
functions and both complete translation-unit images match the original.

This reduces the identified inherited storage remainder from **19 to 17**.
The affected **700 bytes already counted as C**. Matching C remains
**195,844 / 199,912 bytes (97.97%)**, with five game assembly fallbacks.

| Function | Existing C bytes | Original frame | Removed-array control frame | Matching frame |
| --- | ---: | ---: | ---: | ---: |
| `func_80051AC8` | 428 | 56 | 48 | 56 |
| `func_80065E1C` | 272 | 56 | 48 | 56 |

The baseline is `6c578784539da8b89cde4ed1b0cd1e12c109aa08`. Two of the
392 protected game inputs change; the other 390 retain their hashes. Compiler,
configuration, canonical executable and frozen objective remain unchanged.

## Values consumed by the original calls

The menu constructor snapshots the actual base `Construct` method after one
call to `base_class_get_vtable`. Its sole four-byte value supplies the original
invocation, with the same receiver address. String conversion, allocation,
installed table and final setup call retain their behavior.

The actor allocator snapshots the model's actual table for the first `Unk31`
lookup. Its sole four-byte value supplies that enumerator. The real index is
retained as a separate signed word, passed to both enumerations and used to
select the resulting child. Population, allocation failures, child creation
failures and cleanup keep their original control flow.

Both views use one-element arrays whose complete pointer values are consumed.
Target compiler assertions require each view to occupy four bytes. No unused
field, instruction substitution, physical register binding, new volatile
constraint or alternate compiler flag is introduced. This is a matching source
reconstruction; the original author's declarations remain unknown.

## Observed compiler storage

Six complete-source observations compare the baseline, removed-storage control
and matching reconstruction for each unit. Normal and instrumented complete
assembly are identical in every observation.

| Function | Baseline allocation | Removed-storage control | Matching allocation |
| --- | --- | --- | --- |
| Menu constructor | Eight-byte temporary, local area 0 to 8 | No occupied local area | Four-byte reload, local area 0 to 8; pseudo 78 |
| Actor allocator | Sixteen-byte index record | Four-byte index, final local area 8 | Four-byte index plus four-byte reload, final local area 16; pseudo 79 |

For the actor reconstruction, the index allocation advances the virtual local
area from 0 to 4; the subsequent reload advances it from 4 to 16. These are
allocator offsets, distinct from the final 56-byte frame. The reload calls occur
through `assign_stack_local`, `alter_reg` and `reload`. Pseudo IDs are observed
compiler identities rather than source bindings. Nested temporary/local calls
refer to the same allocation and are counted once.

Three constructor comparisons and five actor comparisons qualify complete
sized ELF functions at their original addresses. The matching forms pass the
complete executable gate; formatted complete source units pass it again.
The ordinary build and a fresh build with all 306 objects regenerated also
produce the canonical 505,856-byte executable.

Canonical SHA-1: `76322eeade5ebb22dca57fdeac7d68c30f06308d`.
Canonical SHA-256: `282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.

## Separate rejected assembly studies

The retained renderer and overlap studies yield no exact recovery. Thirty-seven
single-function comparisons comprise 27 borrowed-cell boundary forms, seven
wide-midpoint forms and three point-reference/value forms, including controls.
The wide workspace can reproduce the original frame size but adds instructions.
Six additional aggregate-operand forms emit and call a separate midpoint helper;
their target spans and extra functions are inspected, and they are excluded
from the single-function count. No assembly fallback is replaced by these trials.

## Counts and runtime limits

| Measure | Before | After |
| --- | ---: | ---: |
| Identified inherited storage explanations open | 19 | 17 |
| Unused declared local bytes removed here | 0 | 20 |
| Matching C game-function bytes | 195,844 / 199,912 | 195,844 / 199,912 |
| Game assembly fallbacks | 5 | 5 |
| Groups with all listed core functions in C | 37 / 40 | 37 / 40 |
| Original NPC callback C bodies | 107 / 107 | 107 / 107 |
| Bounded native NPC profiles | 36 / 107 | 36 / 107 |
| Entire feature groups independently accepted | 0 / 40 | 0 / 40 |

The seventeen-function remainder comes from the identified inherited audit;
it does not certify that every possible source issue has been found. This
checkpoint adds no native fixture domain, emulator sequence or independent
constructor/child-allocation scenario. Full ownership histories, allocation
failures, natural encounters, assets and hardware timing still need reviewed
evidence. Executable identity preserves behavior without expanding runtime
acceptance. Ten developer capability categories and three optional mods retain
their separate counts. The Bevy port and running player are unchanged.

## Reproduce

With your own supported executable and the documented toolchain:

```bash
python configure.py
ninja check
python tools/progress.py --json
python -m unittest discover -s tests -v
```

The complete-source observer accepts fresh private destinations:

```bash
python research/collision/trace_compiler_stack.py \
  --source src/menu/card/select_menu.c \
  --output .decomp-lab/select-construct-trace-new --compiler-mode g8
python research/collision/trace_compiler_stack.py \
  --source src/scene/actor.c \
  --output .decomp-lab/actor-enumerator-trace-new --compiler-mode g8
```

[constructor-actor-storage-checks.json](constructor-actor-storage-checks.json)
pins source identities, comparisons, allocator reports and validation. Original
images, ELF exports, generated assembly and full debugger traces stay private.
The [play helper](PLAYING.md) remains the launch path for the matching game.
