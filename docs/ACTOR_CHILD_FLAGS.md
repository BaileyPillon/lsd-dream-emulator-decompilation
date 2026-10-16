# Actor child flag dispatch

The actor virtual table now declares the flag argument that its original child
method receives. Previously, an ordinary two-argument C call through this slot
failed to compile. The corrected receiver and signed-word argument preserve
the complete original executable and remove the initializer's incompatible cast.

## Original call chain

Actor and entity tables bind slot `0x60` to `func_80065A5C`. It reads the signed
child count at actor offset `0x6C`, walks the pointer array at `0x70`, and passes
the complete flag word to each child's slot `0x60`. Nonpositive counts skip
the traversal. The count is read again after each child call; these fixtures
keep that count stable.

The actor builder creates scene-node children. Their default table binds this
slot to `func_8001D344`, which calls the actual `func_8001EDAC` bit setter:

- A zero argument sets bit 31 of the child's word at offset `0x10`.
- Every nonzero word, including `256` and negative values, clears that bit.
- All other bits survive. The leaf's measured return word is one if bit 31
  was previously clear, otherwise zero. The actor fan-out ignores that return.

The three original functions total 268 bytes. Their complete sized ELF spans
agree with the canonical image. Original actor, entity and scene-node tables
are pinned separately. The analysis-only 48-byte caller dispatches through the
corrected actor declaration; it is excluded from the game build. Eight target
ABI assertions check pointer width, object/table sizes and member/slot offsets.

## Populated-list comparison

| Input family | Independent case inputs | Invocations per input |
| --- | ---: | ---: |
| Direct original actor method | 5,376 | 1 |
| Compiled caller through the actor table | 5,376 | 1 |
| Compiled caller through the entity table | 5,376 | 1 |
| Direct original scene-node method | 336 | 1 |
| Repeated flag changes through the entity table | 48 | 5 |
| Total | 16,512 | 16,704 invocations |

The domain includes negative/zero counts and active counts of 1, 2, 4 and 8,
four list arrangements, duplicate children, eight initial flag words, seven
full-word arguments, three address aliases and two buffer patterns. Each
history applies `0, 1, 1, 0, -1` to the same populated graph. Root/child/list
buffers and their guards, ordered arguments, direct leaf returns and saved ABI
agree with the independent model. No function outputs are substituted.

Four isolated faults alter list stride, the zero-argument gate, the selected
flag bit or the leaf return comparison. Each changed instruction executes in
its detecting input and produces a wrong buffer or return word. Positive code
and tables remain intact.

The first checker run compared a 512-byte upper stack guard with a 1,024-byte
slice and stopped. Its producer and diagnostic are retained as excluded
instrumentation evidence. The corrected checker passes in a fresh directory;
the failed run contributes no accepted cases.

## Relation to Fox and the source-recovery goal

The earlier [Fox script profile](STATE_CYCLE_SCRIPTS.md) executes this fan-out
with an empty child list and records the requested boolean. This campaign
executes the downstream method on populated scene-node lists. It does not
invoke Fox's callback, construct a natural actor or verify visible drawing.
The previous RNG/state/movement evidence retains its own scope and contracts.

Regular and fresh clean 306-object builds reproduce the complete canonical
executable. Only the actor source/header change among 392 pinned game inputs;
the other 390 are unchanged. All 579 tooling tests pass on Windows and Linux,
with two expected skips on each.

C recovery remains 194,212 / 199,912 bytes (97.15%), with nine assembly
functions and 24 inherited storage explanations. The bit setter's inherited
unused local remains open. Listed-core C groups stay at 35 / 40, bounded NPC
callbacks at 32 / 107, and whole-feature/whole-NPC acceptance at zero. Original
NPC behavior, AI-assisted tools, optional mods and Bevy retain separate counts.

## Reproduce

With the [matching toolchain](../README.md#build-the-matching-executable), a
current canonical build and `requirements-analysis.txt` installed in WSL/Linux:

```bash
ninja check
python research/actor_children/verify.py \
  --output .decomp-lab/actor-child-flags-new
python -m unittest discover -s tests
```

Choose a fresh private output directory. The checker preserves existing
evidence and rejects public destinations before loading game inputs.
[actor-child-flag-checks.json](actor-child-flag-checks.json) records source,
function, table, caller, backend, build and measured-control hashes. Executables,
generated code, complete native graphs and compiler outputs remain private.
Natural construction/encounters, recursive children, call-time count changes,
rendering, audio and PS1 timing require separate evidence.
