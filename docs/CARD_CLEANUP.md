# Memory-card cleanup evidence

The original 148-byte `func_8004F810` passed **501 bounded fixtures** with one
explicit `memory_free_mem` stub. The existing padding-removal C candidate
passed the same 501 fixtures. Its complete executable still differs in eight
bytes, so no source replacement is accepted. The original matching C retains
its inherited eight-byte dummy local while its source explanation is studied.

## Original call and field behavior

The fields keep their existing source names in
[memory_card.h](../src/menu/card/memory_card.h). This audit establishes the
cleanup routine's operations rather than a complete interpretation of the
card object's lifetime.

| Input or operation | Observed under the explicit allocator contract |
| --- | --- |
| `m_Unk13` at offset `0x38` is zero | No release calls or object changes, even with a positive count. |
| A table is present | Release `m_Unk14` at `0x3C` first. |
| Signed `m_Unk10` at `0x2C` is nonpositive after that call | Skip entry releases; still release the table. |
| Positive count | Release the current table's entries in increasing index order. |
| Between entry releases | Reload the table pointer and signed count; later entries are read when reached. |
| Final table release | Clear `m_Unk13` after the call returns. |
| Other fields and table contents | Preserve them except for explicitly scheduled stub writes. `m_Unk14` is not cleared. |

The fixtures include null and duplicate **opaque release arguments**. They
establish arguments passed to the stub, not the native allocator's ability to
free those pointers safely. Scheduled count, table and entry changes are
adversarial dependency contracts; this audit does not claim that the original
allocator performs those writes.

| Fixture group | Distinct inputs per image |
| --- | ---: |
| Signed count boundaries and absent table | 96 |
| Opaque release arguments and segment aliases | 192 |
| Count reload after the first buffer release | 60 |
| Count reload after an entry release | 90 |
| Table reload between calls | 54 |
| Later entry reload | 6 |
| Final clear after a stub writes the table field | 3 |
| **Total** | **501** |

All guarded object/table bytes, data-access boundaries, stack restoration and
saved registers are checked. Three private mutation controls are detected:
skipping an entry, clearing the wrong object field and restoring the wrong
saved owner register. Canonical inputs and the complete matching build stay
unchanged.

## Source-layout investigation

Twenty-four used owner/index cursor records and twelve scalar inline-helper
forms compiled without an exact match. Two controls reproduce the matching
inherited source and its eight-byte-different padding removal. Every cursor
field and helper argument in the experiments contributes to the cleanup;
unused objects and artificial dead branches are not substituted for padding.

Four actual compiler traces retain 304 allocator calls across complete
translation units, with traced assembly identical to normal compilation.
For this function, the inherited dummy local reserves eight virtual local
bytes. Removing it reserves none. A two-scalar-argument inline helper also
reserves none. Returning the cursor record reserves two eight-byte slots and
retains extra memory operations. Its 40-byte final frame equals the original
frame but has different local storage, saved registers and instructions.
Frame size alone therefore does not explain the original source.

The closest tested source remains the padding-removal body: all instructions
and registers agree except for eight SP-relative displacement bytes. Passing
the bounded behavior check does not satisfy the exact executable gate or
remove the [known source-quality requirement](SOURCE_QUALITY.md).

## Reproduce

With a current matching build and the optional dependencies in
`requirements-analysis.txt`, run in Linux or WSL:

```bash
python tools/verify_card_cleanup.py \
  --output .decomp-lab/cleanup-new/report.json
```

To compare a private complete candidate image, also provide
`--candidate .decomp-lab/your-check/candidate.exe`. The image must change only
this fixed 148-byte function span. Existing reports and images outside the
private directory are rejected before execution.

[card-cleanup-checks.json](card-cleanup-checks.json) records source, tool,
compiler, candidate and private-evidence hashes without distributing game
bytes. Eleven synthetic contract and custody tests extend public CI. The
verifier makes no model API calls and extends the existing analysis workflow;
it adds no original or optional gameplay feature.

Real heap behavior, natural cleanup reachability, physical card I/O and PS1
timing remain outside this proof. C coverage remains 194,884 / 199,912 bytes;
six game functions remain in assembly and five inherited source workarounds
remain. Entire feature-group acceptance remains 0 / 40.
