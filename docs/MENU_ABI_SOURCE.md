# Menu storage and compiler ABI research

Twenty-seven additional menu C forms remain nonmatching. Twelve isolated ABI
diagnostics also produce no matching function. The canonical game sources and
compiler settings are unchanged. Matching C remains **194,212 / 199,912 bytes
(97.15%)**, with nine assembly functions and 24 inherited storage explanations
still unresolved.

Hashes, retained diagnostics and unchanged before/after measurements are recorded
in [menu-abi-source-checks.json](menu-abi-source-checks.json). This research adds no
original gameplay case, C promotion or whole-feature acceptance.

## Fully consumed menu objects

The new forms use eight-byte coordinate and effect-size objects: nested records,
record assignment, compound construction, initialized blocks and a union with a
64-bit packed representation. Every payload contains the two actual words;
there is no added unused coordinate or padding. An independent audit links the
retained objects and checks all 27 complete function/text spans against the
compiler-only results.

The best layout candidate still differs in 20 bytes and uses a 72-byte frame;
the original uses 88 bytes. The best acceptance candidate differs in 16 bytes
and uses a 56-byte frame; the original uses 64 bytes. The unexplained differences
are sixteen and eight frame bytes respectively.

An initial source guard accidentally examined existing record-layout padding
in the shared declaration prefix. That attempt stopped before compilation. Its
diagnostic is retained separately; the corrected guard inspects only the new
declarations and function body.

## Isolated ABI settings

The bundled compiler's default settings reproduce the explicit canonical
`-mno-abicalls` output for all four tested routines. Explicit `-mabicalls` introduces
global-pointer setup and changes call sequences. It does not explain the original
unused stack allocation.

| Routine | Original bytes / frame | Canonical unpadded bytes / frame | Explicit ABI calls bytes / frame |
| --- | ---: | ---: | ---: |
| Bit-field replacement, `func_8001EDAC` | 88 / 8 | 76 / 0 | 88 / 0 |
| Menu layout, `func_8003D73C` | 580 / 88 | 580 / 72 | 684 / 80 |
| Menu acceptance, `func_8003DAD4` | 472 / 64 | 472 / 56 | 564 / 64 |

The 88-byte leaf result has global-pointer instructions instead of the original
stack allocation. The acceptance result reaches the original frame size but
changes the function by 457 bytes. Neither is a match.

The fourth routine, `func_8001EE98`, retains a 40-byte unpadded canonical frame
instead of the original 48 bytes. Its explicit ABI-call object cannot link with
the supplied symbol definitions: `R_MIPS_CALL16` exceeds the relocation range.
That attempt remains excluded from complete linked-span qualification. Eleven
of the twelve diagnostics have independently checked complete linked spans.
No diagnostic changes the project's canonical settings.

Five additional packed-word declaration probes remain excluded from C candidate
counts. Two fail parsing; three fail the required two-byte layout check, including
one ignored attribute. A parsed declaration alone does not establish the required
record layout. Earlier excluded packed-word ideas remain unpromoted.

## Reusable function comparison

[compare_function.py](../research/compiler/compare_function.py) reads complete,
sized functions from linked MIPS ELFs and records their byte differences privately.
It checks architecture, symbol addresses and complete file-backed extents; it
rejects unsized, stripped, truncated and relocatable inputs. The original address
and extent must come from a separately reviewed original-function inventory.

The tool reproduces two retained comparisons: the grid candidate differs in
eleven bytes across three reordered prologue instructions; the sprite candidate
differs in twelve bytes, including two swapped commutative operand pairs. These
remain nonmatching regardless of their instruction classifications.

Thirteen synthetic guards cover false prefix matches, extra section bytes,
changed lengths, reordered words, invalid ELF inputs, canonical-reference
rejection, private output paths and preservation of inputs and existing reports.
All 396 tooling tests pass locally on Windows and WSL. These are tooling tests;
no new original-game execution is claimed. NPC bounded coverage stays at 20/107,
and accepted whole-feature groups stay at 0/40 provisional groups.

The comparator extends the existing compiler-analysis capability. The ten
developer-capability categories and three optional mods retain their earlier
counts. Research reports containing raw words, linked ELFs and compiler output
remain inside `.decomp-lab`; game images remain excluded from Git. No model API
calls are made.
