# Glyph character interface checks

See [the interface guide](../../docs/GLYPH_CHARACTER_API.md) for the recovered
signatures, compiler diagnostic, fixture domains and acceptance boundary.

`consumer.c` contains two analysis-only callers; `abi_checks.h` checks the PS1
layout with the original compiler. `verify.py` compiles these callers and
executes them with the original glyph methods in a fresh private directory:

```bash
python research/glyph_character/verify.py \
  --output .decomp-lab/glyph-character-new
```

Use the configured WSL/Linux matching toolchain and optional analysis
dependencies. The game build does not include these analysis callers.
