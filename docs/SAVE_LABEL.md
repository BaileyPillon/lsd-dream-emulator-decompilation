# Original save-title recovery

`func_800507F8`, at `0x800507F8`, is now recovered as 240 bytes of matching C in
[save_label.c](../src/menu/card/save_label.c), with a shared declaration in
[save_label.h](../src/menu/card/save_label.h). The memory-card writer calls it
to select a slot label, and passes a null filename to reset the title after a
failed operation. The original executable remains byte for byte identical.

## Classification and source recovery

The old raw segment `asm/40FF8.s` contained the formatter followed by six BIOS
file wrappers: `lseek`, `close`, `delete`, `format`, `read` and `open`. Its 336
bytes had all been classified as SDK. The new source split identifies 240 bytes
as game save support and keeps the remaining 96 wrapper/padding bytes under
[psyq/card/file_io.c](../src/psyq/card/file_io.c). Wrapper assembly is regenerated
from a contributor's own executable.

| Measure | Initial publication | Current corrected classification |
| --- | ---: | ---: |
| Game bytes in C | 194,044 | 194,284 |
| Total game text bytes | 199,672 | 199,912 |
| C-byte coverage | 97.181377% | 97.184761% |
| SDK bytes excluded | 148,120 | 147,880 |
| Startup bytes excluded | 188 | 188 |
| Complete build objects | 304 | 305 |
| Previously catalogued game assembly functions remaining | 7 | 7 |

This is one new C recovery plus a correction to classification. It does not
remove one of the seven previously catalogued assembly functions. Applying the
corrected denominator to the unchanged pre-prompt C numerator gives 169,540 /
199,912 (84.807315%); that is an arithmetic restatement, not a fresh baseline
execution. Earlier reports keep their original counts and scope.

The C implementation copies the slot's two-byte label into the title template
and retains the original grouped copies. The native SDK `atoi` interprets a
leading zero as octal, so filenames ending in slot 8 or 9 use the original
adjusted conversion offset. The null-filename path copies the six-byte reset
suffix. No compiler flags or original runtime behavior were changed.

## Verification

The configured complete build reproduces all 505,856 original executable
bytes. An isolated candidate comparison also reports zero changed bytes and
the canonical SHA-1 `76322eeade5ebb22dca57fdeac7d68c30f06308d`.
A fresh clone of source commit `89a789f7d4ed5c8f58c5f92551647490984e31a1`
rebuilt all 305 objects, reproduced that same executable and remained clean in
Git. [save-label-checks.json](save-label-checks.json) records this check and the
136 passing synthetic tooling tests on both Windows and Linux.
The formatter's native 240-byte SHA-256 is
`6366aabaf1ea68aa189955760ed29e676f237ce8bbebead10131cdb91d15a5cd`.

[verify_save_label.py](../tools/verify_save_label.py) executes the original
formatter and actual SDK `atoi`/`todigit` in Unicorn, with **zero stubs**:

- 1,920 cases cover slots 1-15, all four title/filename/template alignments and
  two opaque template contents.
- 32 reset cases cover all title/template alignments and both contents.
- Entire guarded buffers, the template pointer, return address, GP, stack and
  saved registers are checked against independent byte-copy rules.
- Three deliberately wrong instructions change the slot-8/9 conversion offset,
  slot index or reset destination. All three are detected in private VM memory.

The exercised report is `.decomp-lab/save-label-native-proof-first.json`, SHA-256
`4bc06d3a294d54fd48525a335ba8ebc7850bb059141db696d76644b75b448f48`.
It records 1,952 formatter entries, 1,920 `atoi` entries and 4,608 `todigit`
entries. The report, executable and comparison outputs remain private. Public
metadata and producer hashes are appended to [features.json](features.json).
The existing Lion, Gray Man and nine scripted callback checks were rerun against
this build: all 6,784 cases and 14 negative controls passed.

After a canonical matching build, reproduce with a new private output filename:

```bash
python -m pip install -r requirements-analysis.txt
python tools/verify_save_label.py \
  --output .decomp-lab/save-label-native-new.json
```

The verifier checks current source/build inputs and original native range
hashes before and after execution. It refuses an existing output or a path
outside `.decomp-lab` and makes zero model API calls.

## Acceptance limits

These are valid-slot fixtures with independent, nonoverlapping buffers. They
do not establish natural template construction, malformed filenames,
out-of-range slots, overlapping inputs, physical card I/O, retries/error
screens, title rendering, save persistence or PS1 instruction/cycle timing.
This adds bounded support evidence for F037/F039; all 40 provisional feature
groups still await whole-feature runtime acceptance. Original NPC behavior,
AI-assisted analysis and optional gameplay mods retain separate counts.
