# Actor child flag checks

See [the dispatch guide](../../docs/ACTOR_CHILD_FLAGS.md) for the original
method chain, typed-call correction, fixture domains and acceptance boundary.

`consumer.c` is an analysis-only virtual caller. `abi_checks.h` checks the PS1
class layout with the original compiler. `verify.py` compiles that caller and
compares it with the original actor, scene-node and bit-setter methods:

```bash
python research/actor_children/verify.py \
  --output .decomp-lab/actor-child-flags-new
```

Use a current matching WSL/Linux build and the optional analysis dependencies.
The game build excludes the analysis caller.
