# Entry scanner method-return candidate

The retained [`entry-method-return.c`](../research/source_layout/entry-method-return.c)
reduces the complete executable's differences from **20 to 6 bytes** for
`dream_generation_find_entry`. The scanner remains 444 bytes and now uses the
original 80-byte frame. It remains outside the canonical game build: the
remaining differences fail the exact source-recovery gate.

## Source hypothesis and remaining differences

The [entry scanner investigation](GENERATION_ENTRIES.md) established a ten-byte
placement/style packet and the real owner method at virtual slot `0xE8`.
The scalar candidate used a 72-byte frame. This candidate retrieves the same
method through an inline getter returning a one-field, four-byte record;
the caller consumes that method to convert the packet to world coordinates.
Every field supplies an actual call value. It adds no packet fields, unused
storage, instruction substitution, or register binding.

The return form increases this candidate's stack allocation by eight bytes
under the original compiler. It does not establish that the original author
used this type or helper. GCC retains a method-word store that is absent from
the original instructions.

| Instruction address | Original | Retained candidate |
| --- | --- | --- |
| `0x80055718` | No operation | Prepare packet argument in `a2` |
| `0x80055720` | Prepare packet argument in `a2`, in the call delay slot | Store the selected method at `sp + 0x20`, in the call delay slot |

These two instruction words account for all six differing bytes. The complete
image remains 505,856 bytes; every byte outside this 444-byte scanner agrees
with the canonical executable. The next source task is to explain the original
lifetime without this extra store while preserving the original scheduling.

## Verification and limits

A finite compiler study qualified 28 complete ELF functions: one scalar
control and 27 method-record/union forms. The named assigned-record form and
slot-copy forms reach six differences; initialized-record forms retain eight.
None is exact. The retained public fragment was also compiled as a complete
source unit rather than accepted from a standalone text-section comparison.

The original and the complete retained candidate each pass the existing
**4,116 native fixtures** through the actual scanner, owner wrapper and world
converter. Each image executes 12,844 calls to each transform routine. Six
deliberate faults are detected with measured execution of their changed
instructions. Comparisons include full owner, grid, output, query, distance
and entry buffers, ordered ten-byte packet reads, return/index effects,
restored stack and saved registers. No dependency outputs are substituted.

These are the existing fixture inputs reused for a closer candidate. They do
not add distinct original-game scenarios or NPC callback coverage. Natural
construction, per-map parameter provenance, nonzero style selectors, spawning,
lifetimes, rendering/audio and PS1 CPU timing remain outside this profile.
The running player is not used or changed by these checks.

**No C bytes, original features, or whole encounters are accepted by this
change.** Compiled C remains 194,212 / 199,912 (97.15%), with nine assembly
functions and 24 inherited storage explanations still open. The original game,
optional mods, AI-assisted development tools and the separate Bevy port retain
their existing boundaries. These comparisons invoke no model API.

## Reproduce

After a current matching build, prepare a fresh complete source unit containing
only this fragment's replacement for the scanner inclusion:

```bash
python - <<'PY'
from pathlib import Path

destination = Path('.decomp-lab/entry-method-new')
destination.mkdir()
source = Path('src/dream/dream_generation_post.c').read_text()
marker = 'INCLUDE_ASM("asm/nonmatchings/dream/dream_generation_post", dream_generation_find_entry);'
if source.count(marker) != 1:
    raise ValueError('Expected exactly one scanner inclusion.')
fragment = Path('research/source_layout/entry-method-return.c').read_text()
(destination / 'dream_generation_post.c').write_text(source.replace(marker, fragment, 1))
PY

python tools/decomp_workbench.py check \
  --source src/dream/dream_generation_post.c \
  --candidate .decomp-lab/entry-method-new/dream_generation_post.c \
  --function dream_generation_find_entry \
  --output .decomp-lab/entry-method-new/build
```

The comparison intentionally exits nonzero because six bytes still differ.
Inspect `comparison.json` and the sized-function diagnostics before the
optional native check, which requires the documented WSL analysis dependencies:

```bash
python tools/verify_generation_entries.py \
  --candidate .decomp-lab/entry-method-new/build/candidate.exe \
  --output .decomp-lab/entry-method-native-new.json
```

[generation-entry-method-checks.json](generation-entry-method-checks.json)
records compiler/source identities, qualified source observations, the complete
image comparison and bounded native evidence. It preserves the earlier
[entry evidence](generation-entry-checks.json) as a separate historical result.
