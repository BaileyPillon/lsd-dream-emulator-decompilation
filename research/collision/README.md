# Collision recovery research

[`primitive_candidate.c`](primitive_candidate.c) reconstructs `func_8001F8B8`
in C. It is **unaccepted**: the complete private executable differs from the
canonical image in 22 bytes. The canonical game still uses its assembly.

The preceding candidate differed in 103 bytes. Moving the real bounding-box
object before the SDK workspace reproduces the original math, register choices,
frame size and contact-distance storage. The remaining 22 differences are all
bounding-box stack displacements:

| Storage | Original displacement from SP | Candidate displacement |
| --- | ---: | ---: |
| Bounds minimum X/Y/Z | `0xF0 / 0xF2 / 0xF4` | `0x60 / 0x62 / 0x64` |
| Bounds maximum X/Y/Z | `0xF6 / 0xF8 / 0xFA` | `0x66 / 0x68 / 0x6A` |
| Final square result | `0xF0` | `0xF0` |
| Contact distance | `0x100` | `0x100` |
| Complete frame size | `0x160` | `0x160` |

The original reuses the final square-result storage for the later bounds and
leaves an earlier 16-byte region without direct accesses. Recover the source
lifetimes or helper boundaries that explain that layout. Adding dummy padding,
rewriting instructions or binding physical registers does not qualify as C
recovery. The fragment's SDK vector padding is part of those established types.

The [native collision audit](../../docs/COLLISION.md) explains the preserved
behavior: halfword edge narrowing, SDK cross products and squares, signed fixed
fractions, expanded AABB acceptance, nearest-distance ties and contact height
relative to the primitive's minimum Y. The decoder ignores its incoming cursor
when its index is zero; the fragment preserves the original unspecified first
cursor rather than introducing an initialization.

## Reproduce the private build

Use the configured Linux/WSL compiler environment and a current `ninja check`
baseline. From the repository root, prepare a new full translation unit:

```bash
python - <<'PY'
from pathlib import Path
work = Path('.decomp-lab/collision-attempt-new')
work.mkdir(parents=True, exist_ok=False)
source = Path('src/file/tmd_prim_geom.c').read_text()
fragment = Path('research/collision/primitive_candidate.c').read_text()
marker = 'INCLUDE_ASM("asm/nonmatchings/file/tmd_prim_geom", func_8001F8B8);'
if source.count(marker) != 1:
    raise ValueError('Expected one current primitive assembly inclusion.')
(work / 'tmd_prim_geom.c').write_text(source.replace(marker, fragment.rstrip()), encoding='utf-8')
PY

python tools/decomp_workbench.py check \
  --source src/file/tmd_prim_geom.c \
  --candidate .decomp-lab/collision-attempt-new/tmd_prim_geom.c \
  --output .decomp-lab/collision-attempt-new/build
```

For this published fragment, the expected result is an **unsuccessful matching
gate**: exit code 1, unchanged 505,856-byte length and 22 changed bytes. The private
candidate SHA-1 is `729f0d86098eca285c436a35d01374574cc8abf4`. The canonical SHA-1
remains `76322eeade5ebb22dca57fdeac7d68c30f06308d`.

## Compare bounded behavior

Build a new local bridge as described in [the GTE audit](../../docs/RENDER_GTE.md).
With optional Unicorn installed, the paired checker uses the original dependencies
and checked native Nymashock operations:

```bash
python research/collision/compare_candidate.py \
  --candidate .decomp-lab/collision-attempt-new/build/candidate.exe \
  --output .decomp-lab/collision-attempt-new/pairs \
  --bridge .decomp-lab/collision-bridge-new/bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'

python research/collision/verify_midpoint.py \
  --output .decomp-lab/collision-midpoint-new
```

The candidate checker restricts changes to the original primitive function's
fixed byte range. It compares return values, every caller-buffer byte, GTE
register state and the ordered native command/counter requests. It preserves
the ABI and stack guards and detects a deliberate broken edge rule. Its fault
control is tied to the current candidate's instruction layout; a differently
arranged candidate requires a reviewed control before using this checker.

| Executed check | Distinct inputs or stage graphs |
| --- | ---: |
| Original/candidate primitive pairs | 12,696 |
| Additional caller-buffer overlap pairs | 1,566 |
| Original/candidate composed stage graphs | 6,912 |
| Original non-NULL clipping with midpoint output and partial overlaps | 5,400 |

The composed graphs contain 5,760 distinct final transform inputs and 1,152
repetitions. Each pair executes the original and the candidate; these executions
are repetitions of the same input, not twice as many distinct fixtures. The
midpoint audit now enters `func_8001E2E8`; a broken bisection shift is detected.
It executes no GTE operations and supplies no function-output stubs.

The [evidence metadata](../../docs/collision-recovery-checks.json) records the
complete-build comparison, source trials, private proofs and validation. Earlier
feature records remain frozen. These checks establish bounded behavior under the
explicit COP2 adapter. Natural geometry, multi-cloud encounters, unsupported
primitive codes, complete CPU timing and whole-feature acceptance remain open.
Neither research candidate nor midpoint checks increase the accepted C-byte,
original-feature, NPC, developer-capability or optional-mod counts.

## Compiler allocation traces

The [compiler-layout investigation](../../docs/COMPILER_LAYOUT.md) provides a
GDB diagnostic for the complete candidate translation unit. It observes the
actual bundled compiler's allocation calls and requires its complete assembly
to equal a normal compilation. This helps investigate the remaining bounds
storage mismatch; it does not accept the candidate or modify the matching game.

```bash
python research/collision/trace_compiler_stack.py \
  --source .decomp-lab/collision-candidate-new/tmd_prim_geom.c \
  --output .decomp-lab/collision-stack-new
```

The later [lifetime investigation](../../docs/COMPILER_LIFETIMES.md) observes
actual temporary-slot promotion, release and reuse in a selected function.
It requires the exact compiler hash and identical complete assembly output:

```bash
python research/collision/trace_compiler_lifetimes.py \
  --source .decomp-lab/collision-candidate-new/tmd_prim_geom.c \
  --function func_8001F8B8 \
  --output .decomp-lab/collision-lifetimes-new
```

The observed helper boundary permits reuse, but the source remains nonmatching.
This diagnostic adds compiler evidence without accepting original gameplay.
