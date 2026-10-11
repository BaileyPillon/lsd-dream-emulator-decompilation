# Original save workflow checks

The save wrapper, file writer, path builder, title formatter and native SDK
string/conversion helpers have passed **13,152 bounded native cases** against
independent byte and I/O rules. Seven deliberately wrong instructions were
detected. The writer remains in assembly: a full translation-unit C candidate
still differs from the canonical executable in **eight byte positions**.

This supports F037 (save/load) and the title-related parts of F039. It accepts
neither entire feature group. Game C recovery remains 194,284 / 199,912 bytes;
seven known game assembly functions and all whole-feature acceptance gates
remain open. Original behavior, optional mods and development tools remain
separate.

## Recovered native contract

`memory_card_write_file` formats the slot title, then calls `func_8004EF6C`
until it succeeds or has made **11 attempts**. It narrows the icon argument to
one byte before each call. After exhaustion it resets the title through the
native formatter and returns zero.

The writer builds `bu00:` for port zero and `bu10:` for any nonzero port,
deletes the previous file, and opens a new file with flags
`(((size + 0x21FF) >> 13) << 16) | 0x200`. This includes the 512-byte header
when reserving 8 KiB blocks. A failed create prints a diagnostic and returns
zero. A successful create is closed and reopened with mode 2; a failed reopen
also returns zero.

On success, it allocates 512 bytes and constructs:

| Offset | Native operation |
| --- | --- |
| `0x00–0x01` | Write the two magic bytes `SC`. |
| `0x02` | Store the low byte of `icons + 0x10`. |
| `0x03` | Store the low byte of `(size + 0x1FFF) >> 13`. |
| `0x04` | Copy the title and its NUL using native `strcpy`. |
| `0x60` | Copy 32 palette bytes from image offset `0x14`. |
| `0x80`, `0x100`, `0x180` | Copy three 128-byte icon frames from image offsets `0x40`, `0xC0`, `0x140`. |

The image pointer is read from texture-object offset `0x10` before allocation.
All three frames are copied regardless of how many are written. Other header
bytes retain their initial allocation contents. The first write is
`((icons & 255) + 1) * 128` bytes; the payload write rounds its size up to 128
bytes. The header is freed before the payload write, then the file is closed.

The original routine ignores delete, close and write return values. In the
exercised failures, a write returning `-1`, zero or a short length still leads
to success and prevents the wrapper from retrying. That observed behavior is
preserved by the matching game. Allocator failure and unbounded title/icon
inputs are outside these checks.

## Native proof

Nine pinned native functions execute: the wrapper, writer, path builder,
`func_800507F8`, `atoi`, `todigit`, `strcpy`, `strcat` and `strlen`. Only
`delete`, `open`, `close`, `write`, `printf`, `memory_allocate_mem` and
`memory_free_mem` are stubbed. These seven contracts deliberately overwrite
volatile registers. Execution outside the reviewed call graph is rejected.

| Fixture group | Cases |
| --- | ---: |
| Successful saves: all 15 slots, four port values, three icon counts, padding/block sizes, alignments and initial contents | 11,520 |
| Create/reopen retries and title cleanup | 1,152 |
| Ignored delete, close and combined write results, including zero icons | 96 |
| Cached/uncached segment aliases | 48 |
| Wrapper icon argument width, including high argument bits | 256 |
| Additional 16 KiB payload block boundary | 72 |
| Separate first/second write failures and short writes | 8 |
| **Total** | **13,152** |

There are 12,832 success and 320 failure cases, with 21,632 native writer
entries. The model compares every guarded object, filename, title, texture,
image, payload, header and template buffer; forwarded writer arguments; file
paths, modes, descriptors and complete write bytes; return value; attempt
count; template pointer; stack guards/arguments; GP, RA and saved registers.

Controls change the retry limit, create flags, header length, payload padding,
icon argument width, palette source or failure-label reset. All seven are
detected. The private report is
`.decomp-lab/card-save-native-proof-first.json`, SHA-256
`dc5853f4e9aa1fbdaf04398e0799806577ce7969e8b911f835e80f1fda701fc5`.

With a current matching build and `requirements-analysis.txt` installed:

```bash
python tools/verify_card_save.py \
  --output .decomp-lab/card-save-native-new.json
```

Reports stay private and existing evidence is preserved. The public tooling
tests require synthetic fixtures only.

## C recovery and Ghidra metadata

The full C candidate preserves all other executable bytes but swaps the saved
registers used for the title pointer and texture object. Its 960-byte writer
has eight differing bytes across six instructions. Local compiler dumps show
that scheduling changes the recorded live lengths from title/texture 48/31
instructions to 33/52, after which the title is allocated first. Twenty-four
file-creation/helper variants and four error-flow variants do not close the
gap. These attempts use canonical flags without physical register bindings,
padding or behavior changes.

The full-executable comparison is retained at
`.decomp-lab/card-save-workflow-build-first/comparison.json`. Its candidate
SHA-1 is `7ee3eafe9f0a3b425aa0f8845cff889189acc54d`; this is **not** the
canonical SHA-1 `76322eeade5ebb22dca57fdeac7d68c30f06308d`.

That candidate also passes all 13,152 original workflow fixtures against the
same independent byte/I/O model, including argument forwarding and ABI.
This bounded behavior agreement does not meet the exact-byte acceptance gate.
Evidence: `.decomp-lab/card-save-candidate-behavior-second.json`, SHA-256
`bcbe2de843aeec1739a2dd43a5197bab67e4c14934d55acb80794d008d5d152d`.

The private Ghidra project now has reviewed prototypes for the wrapper,
writer and path builder. The first two have four register arguments and three
stack arguments; the wrapper's icon input uses `a3:1`, while the writer's
uses `a3:4`. All other arguments use four-byte storage. The MIPS `__stdcall`
convention and actual argument locations are checked. Saving these metadata
changes preserves the entire 1,268-byte native region. Evidence:
`.decomp-lab/ghidra-card-save-api-reconciled-third.json`, SHA-256
`b726cb4f5e1b51307db3771d6c64b0cf1912cd8c9f2e04165d7a7dfaac0fadd4`.

These synthetic checks do not establish physical card I/O, allocator
behavior/failure, malformed names, oversized icon counts, aliased buffers,
menu/error rendering, persisted saves, complete dream-state restoration or
PS1 timing. Full feature and whole-game acceptance remain unproven.
