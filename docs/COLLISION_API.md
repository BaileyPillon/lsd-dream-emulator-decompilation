# Collision query interface

The primitive query now has one shared declaration for its original pointer
arguments. The scene-node caller uses a four-byte nearest distance and a
six-byte contact point. Both regular and fresh 306-object builds reproduce the
complete canonical executable. No assembly function is promoted by this change.

## Argument and storage recovery

`func_8001F8B8` receives these arguments in order:

| Argument | Recovered role |
| --- | --- |
| `void *model` | Model containing the geometry and primitive list |
| `s32 *nearest` | Distance output, initialized to `INT_MAX` before traversal |
| `vec3d_16_t *hit` | Three signed halfwords written for the nearest accepted hit |
| `s32 *height` | Optional signed-word output relative to the primitive's minimum Y |
| `const vec3d_16_t *start` | Three signed halfwords for the segment start |
| `const vec3d_16_t *end` | Three signed halfwords for the segment end |

The prior local declaration represented the height pointer as an integer.
The same analysis caller compiles with that declaration but produces pointer
conversion and discarded-`const` warnings. It compiles without warnings through
the shared header; both versions emit identical 76-byte code. This corrects
the source contract while preserving original behavior.

The already-recovered scene-node caller, `func_8001E7BC`, retains eight-byte SDK
buffers for its transforms and passes their six-byte XYZ prefixes to collision.
Its contact and distance locals now reflect the actual six-byte and four-byte
outputs. Five isolated complete builds qualify these type changes separately;
the caller's complete 720-byte function remains identical to the original.
The final shared declaration also passes regular and fresh complete builds.

## Compiled-caller comparison

An analysis-only C caller packages these six arguments. Twenty-one target ABI
assertions check signed widths, coordinate layout, SDK buffer prefixes and
request offsets. This caller is excluded from the game build.

All **12,696 distinct initialized inputs** pass both direct original execution
and the compiled typed caller, for **25,392 positive executions**. This reuses
the established primitive-query domain: supported triangle/quad layouts,
expanded-boundary edges, forward/reverse/zero-length segments, empty/repeated/
stacked/reversed primitives, optional height and three address aliases. It adds
a compiled interface path; it does not add 12,696 new gameplay scenarios.

The original primitive routine, decoder, cross product, square and square-root
methods execute without output substitutions. Positive runs make 59,376 native
GTE commands and 33,888 leading-sign-bit queries through the checked Nymashock
bridge. Full model/request/output buffers and return values agree with the
independent model. Saved registers, GP, stack restoration and the lower stack
guard are checked. Four faults independently redirect the height, nearest,
start or hit field; every changed load executes and changes a checked result.

These constructed queries do not execute the scene-node caller, establish
natural scene reachability, test input/output aliasing, cover every geometry
case or validate PS1 timing. The [primitive C candidate](../research/collision/README.md)
still differs in 22 executable bytes. Its 1,944-byte code is unchanged by the
shared point alias and endpoint qualifiers and remains unaccepted.

C recovery stays at 194,212 / 199,912 bytes (97.15%), with nine assembly
functions and 24 inherited storage explanations. Bounded NPC profiles remain
34 / 107; whole-feature and whole-encounter acceptance remain zero. Original
NPC AI, analysis tools, optional mods and the separate Bevy port keep their
existing counts. No model API is called by this verifier.

## Reproduce

Use the [matching toolchain](../README.md#build-the-matching-executable), a
current canonical build, `requirements-analysis.txt`, and a checked bridge
built as described in the [GTE audit](RENDER_GTE.md):

```bash
ninja check
python research/collision_api/verify.py \
  --output .decomp-lab/collision-api-new \
  --bridge .decomp-lab/collision-bridge-new/bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'
python -m unittest discover -s tests
```

Choose a fresh private directory. Existing evidence and destinations outside
`.decomp-lab` are rejected before game inputs load. The
[evidence metadata](collision-api-checks.json) records the compiled caller,
original ranges, measured controls, source hashes and build comparisons.
Game images, generated code, full buffers and compiler outputs remain private.

## Shared bounds accessor declaration

The October 17 supplement fixes a C function-type mismatch for the already
recovered `get_source_vertices` at `0x8001F50C`. Its definition previously
declared no arguments, while the caller declared two. The shared declaration
in `file/tmd_prim.h` now names the model and index, and the definition explicitly
ignores both. The canonical caller includes that same header.

| Original direct call | Model argument | Index argument |
| --- | --- | --- |
| `0x8001DC00` | Transform's model value | Zero |
| `0x8001DEE8` | Transform's model value | Loop index |
| `0x8001DFDC` | Transform's model value | Loop index |

The original 16-byte accessor constructs the shared bounds address and returns;
it reads neither argument. This recovers a consistent interface for these
observed calls, without making the scratch buffer model-specific or accepting
an exhaustive indirect-call graph.

Regular and fresh **306-object** builds still reproduce the complete original
executable. Compiling the old no-argument definition against the shared header
now produces a conflicting-type error. This target-compiler control protects
the source contract; it changes no native instructions or recovered C count.

The unaccepted overlap fragment also uses the canonical six-argument primitive
pointer declaration. At this interface checkpoint its complete candidate image
was byte-identical to the earlier tested 148-byte nonmatch, and its 796-byte
function remained unaccepted. The later [control-flow study](OVERLAP_CONTROL_FLOW.md)
retains that interface and improves the source candidate to 26 differing bytes.
[source-bounds-abi-checks.json](source-bounds-abi-checks.json) pins
the compiler control, both builds and source/code identities. Earlier evidence
metadata remains frozen; no new native input domain or runtime acceptance is
counted.
