# Grid compiler phases and source boundaries

The canonical `func_8004C6A8` remains assembly. The initial complete builds reproduce
the earlier candidate's eleven byte differences and a formal-argument control's
thirteen differences. Both images have the original 505,856-byte length, and every
byte outside the 660-byte function matches. Neither source form is promoted.

The new [phase reader](../research/render_grid/inspect_compiler_phases.py) follows
two qualified observations of the actual bundled GCC 2.6.3 through seven stages.
It rechecks preserved source/compiler inputs, artifact hashes, complete assembly,
register dispositions and allocation priorities before interpreting their RTL.
Its output is compiler research, not additional native gameplay coverage.

## Where the order changes

The local-capture source initially has an incoming height parameter and a local
height value. By the combine stage, its incoming parameter copy is deleted. The
remaining local capture is after `FUNCTION_BEG`. The first scheduling pass places
the lookup-buffer address ahead of that capture. Allocation, prologue insertion
and later scheduling retain this order.

The formal-argument control retains its height copy before `FUNCTION_BEG` through
global allocation. Its final height sequence saves incoming `fp`, copies height
to `fp`, then forms the buffer address, as the original does. Later phases move
the function-begin note; its final position does not prove original declarations.

| Observed value | Formal control | Local candidate |
| --- | ---: | ---: |
| Width references / compiler live length | 4 / 52 | 4 / 53 |
| Width allocation priority | 1,538 | 1,509 |
| Width assigned register | `s6` | `s7` |
| Cell-Z references / compiler live length | 5 / 65 | 5 / 65 |
| Cell-Z allocation priority | 1,538 | 1,538 |
| Cell-Z assigned register | `s7` | `s6` |
| Actual global allocator calls | 14 | 14 |
| Actual priority comparisons | 39 | 38 |
| Complete frame bytes | 152 | 152 |
| Complete-image byte differences | 13 | 11 |

The next source hypothesis must retain the incoming height boundary while
changing the scheduled width/cell-Z lifetime. Changing only final instruction
order would bypass the source gate. Both observations preserve complete normal,
observed and diagnostic assembly and actual inputs.

## Further rejected source forms

| Family | Qualified new compilations | Minimum differing text bytes |
| --- | ---: | ---: |
| Consumed window helper boundaries and typed virtual lookup | 56 | 11 |
| Signed/unsigned 32-bit extents and setter parameters | 43 | 11 |
| Rotation-subarray capture and angle-access boundaries | 34 | 11 |
| Total | 133 | 11 |

An independent pass rechecks every source hash, emitted text hash and sized ELF
function span. None has an exact selected function or complete text match. The
first extent diagnostic included unsized GNU compiler marker labels in a
conservative exact predicate. The independent pass excludes those markers and
still finds zero matches. Real emitted helpers remain separate function spans.
No padding, physical-register binding, compiler-flag change or instruction
substitution is used. These counts are source trials, not gameplay fixtures.

## Reproduce the phase journal

Prepare the published candidate with the [existing recipe](../research/render_grid/README.md).
To make the formal control, copy its complete unit into a fresh private directory
and change only the selected function's declarations:

```python
from pathlib import Path
source = Path('.decomp-lab/grid-candidate-new/render_context.c').read_bytes().decode()
old = 'void func_8004C6A8(render_context_t *This, s32 input_width, s32 input_height) {'
new = 'void func_8004C6A8(render_context_t *This, s32 width, s32 height) {'
if source.count(old) != 1:
    raise ValueError('Expected one prepared grid candidate.')
source = source.replace(old, new, 1)
source = source.replace('    s32 width = input_width;\n', '', 1)
source = source.replace('    s32 height = input_height;\n', '', 1)
output = Path('.decomp-lab/grid-formal-new')
output.mkdir(parents=True, exist_ok=False)
(output / 'render_context.c').write_bytes(source.encode())
```

With the configured WSL compiler and optional GDB, observe both complete units:

```bash
python research/compiler/trace_allocation.py \
  --source .decomp-lab/grid-candidate-new/render_context.c \
  --function func_8004C6A8 --output .decomp-lab/grid-local-trace-new
python research/compiler/trace_allocation.py \
  --source .decomp-lab/grid-formal-new/render_context.c \
  --function func_8004C6A8 --output .decomp-lab/grid-formal-trace-new
python research/render_grid/inspect_compiler_phases.py \
  --formal .decomp-lab/grid-formal-trace-new \
  --local .decomp-lab/grid-local-trace-new \
  --output .decomp-lab/grid-phase-journal-new
```

[grid-phase-checks.json](grid-phase-checks.json) records the trials, complete
builds, qualified observations and phase identities. Raw game files, generated
assembly and candidate images remain private. All 365 tooling tests pass locally.
Current matching C remains 194,212 / 199,912 (97.15%), with nine assembly functions,
24 inherited storage explanations and 35 / 40 listed-core C groups. Whole-feature
acceptance remains zero; the 16 / 107 bounded NPC count, ten developer capabilities
and three optional mods retain their separate counts.

## Inclusive-edge lifetime study

The improved [research fragment](../research/render_grid/c6a8_candidate.c) retains
formal width/height arguments and computes the inclusive far edge as
`x + (1 - width)`. Its complete 505,856-byte image differs in **eight bytes in
two instructions**. Every other executable byte matches, including the original
152-byte frame, incoming-height copy, store order and register choices. The
matching game retains its original assembly for this function.

Two fresh observations of the actual bundled compiler identify the allocation
change. Normal and observed complete assembly agree byte for byte. Diagnostic
assembly changes only compiler-option comments; register dispositions and
priority comparisons are rechecked by the existing qualified reader.

| Value | Formal arithmetic control | Improved edge expression |
| --- | ---: | ---: |
| Width references / compiler live length | 4 / 52 | 4 / 53 |
| Width priority / register | 1,538 / `s6` | 1,509 / `s7` |
| Cell-Z references / compiler live length | 5 / 65 | 5 / 65 |
| Cell-Z priority / register | 1,538 / `s7` | 1,538 / `s6` |
| Observed global allocations | 14 | 14 |
| Observed priority comparisons | 39 | 38 |

The longer width lifetime moves it below cell Z in allocation priority. The
remaining difference is the arithmetic sequence at `0x8004C7D4` and
`0x8004C7D8`:

```text
Original:  subu  v0,s5,s7     then addiu v0,v0,1
Candidate: addiu v0,s5,1      then subu  v0,v0,s7
```

These are generated instructions for comparison, never substituted to make a
source candidate match. The source gate requires the original sequence through
meaningful C while preserving the recovered allocation.

The complete improved image is checked against the original in all **74,832
existing scalar fixtures per image**. Whole guarded buffers, ordered dependency
traces, matrix/lookup data, ABI and stack guards agree with the independent
integer model. Both differing instructions execute in measured runs. Eight
separate faults in original-code copies are detected. Positive runs load the
actual compiled instructions; their initial program memory is checked against
the complete executable image.

This repeats the existing fixture classes for the new candidate. Position
lookup, `RotMatrix`, `ApplyMatrixLV` and the builder retain four explicit
contracts. It adds no new natural scene, SDK/GTE composition, framebuffer,
audio or timing acceptance, and does not waive executable equality.

Twenty-eight C unit builds, including four calibration controls, test consumed
installation results, in-place extent arithmetic, a two-word extent ABI and
halfword-height ownership. None
matches. Twenty-four complete fixed-address diagnostics finish; the four
aggregate cases move the caller's successor by eight bytes and correctly fail
that diagnostic. Their retained linked images also differ under a separate
whole-file comparison. The signed halfword read at the caller alone therefore
does not justify narrowing the callee's parameter.

A ten-minute local `decomp-permuter` run from the calibrated eight-byte seed
produces no improved output. Padding and constant-condition insertion are
disabled; stack and branch-target differences are counted. Its baseline score
of 205 is a search metric, separate from the eight differing executable bytes.
Four isolated C++ frontend experiments also have no match and are not eligible
for C recovery. Failed preparatory checks remain separate from qualified
comparisons in the [evidence metadata](grid-edge-order-checks.json).

The current C count remains **194,212 / 199,912 (97.15%)**, with nine assembly
functions, 24 inherited storage explanations and 35 / 40 listed-core C groups.
The 20 / 107 bounded NPC profiles, ten developer capability categories, three
optional mods and zero whole-feature/whole-encounter acceptance are unchanged.
This study makes no model API calls and changes no original game behavior.
