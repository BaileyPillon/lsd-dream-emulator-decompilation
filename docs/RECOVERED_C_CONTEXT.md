# Analysis context after complete matching C

All counted game functions have C bodies. Analysis still needs original
instructions, complete function extents, current declarations and repeatable
candidate comparisons. These developer tools support that work without adding
AI behavior to the original game or invoking a model API.

## Export and compare

Use the supported Linux/WSL environment with GNU MIPS binutils and the verified
canonical executable. For a candidate comparison, first establish a current
complete build with `ninja check`.

```bash
python tools/decomp_workbench.py context \
  --function func_80020050 --output .decomp-lab/context-new
python tools/decomp_workbench.py check \
  --source src/file/tmd_prim_geom.c \
  --candidate .decomp-lab/context-new/candidate.c \
  --function func_80020050 --output .decomp-lab/check-new
```

Choose fresh output directories. The context contains the complete candidate
translation unit, recursively resolved headers, verified original disassembly,
the original function's bytes, provenance hashes and a prompt. Existing private
Ghidra analysis is included when available and labelled fallible. Context export
does not establish a compiler match or execute gameplay.

The selected function must have exactly one configured game-C definition.
An original SDK range alone is not a configured game-C analysis target. Missing
or ambiguous ranges and definitions fail rather than selecting a neighbor or
inventing an extent. The optional `check --function` diagnostic now accepts
recovered C as well as active assembly. Its result cannot override the complete
executable gate.

## Public original-range evidence

The [function index](../research/original-functions.json) contains **2,082 unique
sized text symbols**, including SDK functions. It contains names, load addresses,
file offsets, lengths and SHA-256 hashes, with no instruction bytes. Its count
is not the number of game functions, recovered features or accepted behaviors.

The exporter retained symbols in an isolated link and verified that the entire
resulting executable equalled the canonical original. Each range then required
the same address and size from the actual ELF symbol and GNU `nm`, plus complete
function-byte equality with the original executable. Zero-sized labels do not
gain guessed extents from the next symbol. Ambiguous names are excluded and
reported; this qualified export had none.

For recovered C, context export verifies the full original executable, checks
the selected range's hash and PS-X address mapping, and disassembles only that
range with GNU MIPS objdump. Every printed address and little-endian instruction
word must agree with the original, including zero words. Disassembler mnemonics
remain analysis. `original.s` is an inspection artifact, not a build input.

No old `.decomp-lab/remaining-game-functions.json` is needed for this route.
Active assembly retains its original verified assembly route; the saved private
catalog remains a compatibility fallback for older checkouts without the index.

To reproduce the public metadata from a current matching build:

```bash
python tools/export_function_ranges.py --output .decomp-lab/ranges-new
```

Review its original-functions.json and report before updating the tracked index.
Keep the diagnostic ELF, map, executable, symbols and raw context private.
Preserve game inputs and do not overwrite earlier evidence. The exporter checks
all captured source, header, object, executable and native-tool identities before
and after the link. Full input receipts remain private; the public index records
the complete-image qualification and diagnostic hashes.

## Source policy and scope

The generated prompt follows the owner's [current matching-C rule](MATCHING_GAME_C.md):
documented upstream compatibility storage is permitted with its provenance.
Arbitrary padding, inline assembly, embedded instruction bytes, instruction
substitution and changed behavior are excluded as ways to obtain a match.
The historical frozen objective is retained; its old no-padding wording does
not silently override the revised rule.

This repairs the existing A001 context-export and A002 candidate-check
capabilities. It adds no new capability count, C byte, game feature, original
NPC callback or whole-feature acceptance. Native NPC behavior and optional
modifications remain separate. [Validation evidence](recovered-c-context-checks.json)
records the fresh-context regression, canonical candidate and failure controls.
