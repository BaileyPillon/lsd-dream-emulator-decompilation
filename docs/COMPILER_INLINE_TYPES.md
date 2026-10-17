# Compiler inline-call type diagnosis

The bundled compiler can leave an aggregate helper out of line because its
argument has a different internal type node from the parameter. The new
[inline-call tracer](../research/compiler/trace_inline_calls.py) records the
executed argument gate and inline return, making that failure visible during
candidate development. It requires identical complete assembly from normal
and observed compilation.

This extends the existing compiler/candidate analysis workflow. Matching C
remains **196,504 / 199,912 bytes (98.30%)**, with four assembly functions and
two inherited storage explanations. No original feature or NPC is accepted.
[Validation metadata](compiler-inline-checks.json) records before/after counts,
executed observations and source-study qualification.

## Reproduce without game inputs

Use Linux/WSL with the existing build toolchain and GDB. The
[standalone reproducer](../research/compiler/examples/inline_type_identity.c)
contains three small source forms and is excluded from the game build:

```bash
python research/compiler/trace_inline_calls.py \
  --source research/compiler/examples/inline_type_identity.c \
  --function alias_storage_example --helper add_pair \
  --output .decomp-lab/inline-alias-new

python research/compiler/trace_inline_calls.py \
  --source research/compiler/examples/inline_type_identity.c \
  --function tagged_storage_example --helper add_pair \
  --output .decomp-lab/inline-tag-new
```

Select `constructor_example` to inspect the third form. Use a fresh output
directory for every run. `--helper` is optional; omitting it records all inline
attempts in the selected function. `--compiler-mode g0` selects the repository's
G0 profile; the default is G8.

The decoder supports the exact bundled ELF32 i386 compiler, SHA-256
`3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab`.
Another compiler requires a separately verified profile.

## Observed type-identity failure

The fraction study observes one call to `divide_fraction` in each selected
source form. The two record types have the same `BLK` mode, 32-bit alignment
and main type, but the typedef-declared object has a separate internal node.
The executed gate rejects that identity difference:

| Fraction input | Argument/parameter type nodes | Actual inline outcome |
| --- | --- | --- |
| Typedef-declared operand | Different, with a common main type | Rejected |
| Actual struct tag for storage and parameter | Identical | Inlined |
| Direct struct-tag constructor | Identical | Inlined |

The caller's storage declaration matters as well as the helper's signature.
The standalone reproducer exposes the same decision without the game's
source candidate. These observations concern this compiler and these calls;
original source recovery still requires a complete executable match.

## Reports and qualification

`inline-events.json` retains type modes, identities, UIDs, alignment, completed
returns and executed argument rejections. Other causes of failed inlining
remain explicitly unclassified. `report.json` pins the source, captured
preprocessed input, compiler, observer, configuration, GDB executable/version
and commands. GDB initialization files are disabled for the run.

The normal and observed complete assembly must be equal. Missing targets,
incomplete calls, inconsistent gate/return records, changed inputs and changed
assembly reject qualification while preserving private logs. Outputs belong
in a new directory under `.decomp-lab`.

GDB's normal breakpoint machinery may temporarily instrument compiler memory.
The backend makes no additional explicit inferior-memory writes, substitutes
no results and invokes no extra inferior functions. The diagnostic uses the
compiler and source only; it makes no model API calls.

## Source-study result

Three families attempted **42 source comparisons**: 36 produced qualified
complete functions; six retained a separate helper and were excluded. Changing
both storage and formals to the actual tag repaired qualification for all six.
The repaired value forms and returned-quotient forms still fail the native
function comparison. The best retained primitive candidate remains 22 bytes
different, entirely in bounding-box stack displacements.

These counts include repeated controls. No candidate is promoted, no new game
execution is counted and the original compiler flags remain unchanged. The
[collision source recipe](../research/collision/README.md),
[fraction study](COLLISION_FRACTIONS.md) and
[lifetime investigation](COMPILER_LIFETIMES.md) retain the remaining recovery
questions and complete-executable requirement.
