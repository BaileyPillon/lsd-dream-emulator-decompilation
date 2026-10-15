# Source interfaces and complete candidate diagnostics

Thirty-seven additional source forms have been requalified against complete
linked function extents. None matches the original. This investigation adds
**zero C bytes** and does not change any original-game acceptance count.

## What the source experiments establish

| Family | Qualified forms | Result |
| --- | ---: | --- |
| Two-byte short-bitfield coordinate records | 16 | Eight 104-byte and eight 108-byte functions; no match |
| Const-qualified generation method returns | 7 | All retain the 136-byte candidate's eight differences |
| Discarded generation callback results | 8 | Aggregate and scalar return declarations remain nonmatching; aggregate returns also change the callback ABI |
| Inline update helpers returning consumed objects or arguments | 4 | 144-byte or 156-byte functions; no match; original interface provenance remains unknown |
| Collision cross-product argument records | 2 | Complete units emit 1,992-byte and 1,952-byte functions instead of 1,944; neither image matches |

Four `#pragma pack` spellings compile without reducing the word-bitfield
record's four-byte extent. The accepted short-bitfield record occupies two
bytes with two-byte alignment. Those measured layouts qualify the sixteen
new coordinate forms. They do not establish that all possible packed-word
interfaces have been tested. Parser failures and the earlier failed layout
measurement are excluded from the qualified count.

The discarded aggregate-return declaration is a particularly misleading near
match: it produces a 40-byte frame and nine differing bytes, but passes a
hidden result pointer in `a0`, the receiver in `a1`, and the position in `a2`.
The original passes the receiver in `a0` and position in `a1`. That candidate
is rejected on ABI evidence; a similar frame or small byte difference cannot
establish equivalent behavior. No native-behavior acceptance is claimed for
that wrong-signature candidate.

The [eight-byte method-record candidate](GENERATION_RETURN_TEMPORARY.md) and
the [bounds source investigation](BOUNDS_SOURCE_TYPES.md) retain their earlier,
separately scoped evidence. The new forms do not resolve their source gates.

## Repeatable complete-function diagnostics

The workbench can now qualify a current assembly function while checking its
complete candidate translation unit:

```sh
python tools/decomp_workbench.py check \
  --source src/file/tmd_prim_geom.c \
  --candidate .decomp-lab/my-attempt/complete-unit.c \
  --function func_8001F8B8 \
  --output .decomp-lab/my-attempt-build
```

Use the repository's configured Linux/WSL toolchain and a fresh private output
directory. The function must belong to the selected source's current assembly
catalogue. A complete baseline build is required.

The normal candidate link retains its canonical flags. A second diagnostic
link uses the same objects, placement script, and options, removing only the
symbol-strip option. Object path spellings are retained: rewriting relative
inputs as absolute paths can make the linker include them twice. The entire
diagnostic binary must equal the normal candidate binary before its actual ELF
function symbols can be used. No instruction edits, synthetic symbols, selected
prefixes, or assumed function sizes replace that qualification.

The terminal prints a bounded summary; `comparison.json` retains the full
instruction comparison and ELF inventory privately. Exit status still follows
complete original/candidate image equality: 0 for equal, 1 for different, and
2 for an error. A matching selected function cannot override a different image.

Actual tool checks reproduce both collision forms and accept an unchanged
bounds-unit control that still includes its original assembly. The control
verifies the tool, not C recovery. Synthetic guards reject changed/appended
images, missing symbols, extra function words, incorrect source ownership,
and changed reference evidence. All 416 Python tooling tests pass locally.

[source-interface-diagnostics-checks.json](source-interface-diagnostics-checks.json)
pins the requalification, actual tool reports, source and compiler identities,
and unchanged counts. All 392 protected build inputs remain unchanged and the
standard executable remains canonical. C remains 194,212 / 199,912 bytes,
with nine assembly functions and 24 inherited storage explanations. Every
[completion requirement](../PROJECT_OBJECTIVE.md) retains its full scope.
