# Bounds return values and coordinate types

The 108-byte `func_8004CD38` remains assembly. **66 further C source forms have
no exact match**; the best still differs at 38 byte positions. These source
experiments add no recovered C bytes or original gameplay cases.

The [original bounds profile](RENDER_BOUNDS.md) already checks the predicate's
signed coordinates, mixed-width limits, inclusive edges and data-read order.
Its original and closest compiled candidate agree on 4,648 bounded fixtures.
The remaining source problem includes the return-value and bounds-pointer
lifetimes: the original starts by preserving the bounds pointer in another
argument register and retains its result in the return register throughout.
The closest C candidate allocates those values differently and moves its
result into the return register at the end. Both have zero-byte stack frames.

## Additional source experiments

| Qualified C family | Forms | Result |
| --- | ---: | --- |
| Byte records/byte bitfields, enum results and ordinary C `register` declarations | 46 | Two emitted outputs; no match |
| Returned GNU C statement blocks, with and without a result cast | 4 | Same two outputs as their corresponding earlier bodies |
| Direct conditional results with real minimum/coordinate argument reuse | 16 | No match; best difference in this family is 83 bytes |
| Total | 66 | Eight distinct outputs; overall best remains 38 bytes |

Twenty-five of these forms emit exactly the earlier closest candidate's text.
Ordinary `register` declarations do not bind variables to physical registers.
The experiments do not change canonical compiler flags, add unused padding,
inject register interference or edit instructions to manufacture a match.

Six separate C++ diagnostics compare ordinary bodies and the historical
[GNU named-return extension](https://gcc.gnu.org/onlinedocs/gcc-2.95.3/gcc_5.html).
These are isolated bodies with equivalent primitive typedefs. All emit
120-byte functions that remain 93 bytes different from the original. Named
returns reproduce the corresponding ordinary C++ output; they do not improve
the match. The retained compiler accepts the syntax, but the linked manual is
a later historical reference, not a claim about the original game's source.
These diagnostics do not establish C++ translation-unit compatibility or C
recovery.

Sixteen packed-word bitfield ideas were attempted using two attribute
placements. Both placements were rejected by the retained C parser. Those
32 failed compiler attempts are excluded from the 66 qualified C forms. The
sixteen ideas remain unqualified; their behavioral hypotheses are not ruled
out by a parser failure.

## Qualification and current gates

An independent audit rehashes each source, complete linked function text,
binary and producer input. It checks ELF32 little-endian MIPS identity,
function address/size, complete text-section equality and the absence of other
emitted functions. It recomputes every difference against the original 108
bytes. No selected instruction subset or register renaming is counted as an
exact match. [bounds-source-types-checks.json](bounds-source-types-checks.json)
pins the reports and audit; raw game code and generated binaries stay private.

The standard executable remains byte-identical to the original. Its 391 build
input hashes and the retained clean build's 363 source-input hashes are
unchanged. C recovery stays at 194,212 / 199,912 bytes (97.15%), with nine
assembly functions and 24 inherited unused-storage explanations. Bounded NPC
coverage remains 20 / 107; whole-feature acceptance remains zero. Developer
capabilities and optional mods retain their separate counts.

The tested type and return-expression forms do not explain the original
allocation. Further work needs evidence for the source's actual value
lifetimes and interface, followed by complete translation-unit and executable
equality. Existing behavior agreement does not resolve that source gate.
