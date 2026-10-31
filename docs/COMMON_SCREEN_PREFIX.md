# Shared runnable-screen prefix

The common menu/chart view previously exposed Destroy and Run around a 60-byte
opaque gap. It now names every word through Run at `0x44`. Ten inherited base
methods become callable through this view: Attach, Detach, DetachAll,
IterChildren, AddParent, RemoveParent, ClearParents, IterParents, Notify and Nop.
The complete executable remains identical to the canonical game.

Construct, Cleanup, OnNotify and Initialize retain explicit `u32` address words
in the common view. Their concrete contracts differ or still require review;
the word map does not invent a common C signature. The `0x3C` word is null in
both supported tables. Concrete interfaces remain the place to call their
screen-specific methods. These declarations describe the native PS1 ABI and
do not establish portable C object aliasing or original source-level types.

| Evidence | Main menu | Dream chart |
| --- | --- | --- |
| Original table | `0x80086B60` | `0x80087AAC` |
| Complete shared prefix | 72 bytes | 72 bytes |
| Nonnull callback words in prefix | 16 | 16 |
| Destroy | `base_class_destructor` | `base_class_destructor` |
| Run | `func_8003C1DC` | `func_80058390` |

The [checker](../tools/inspect_screen_prefix.py) reads every original prefix word,
compares the concrete declarations, and independently reads the shared base
table words. All 32 concrete callback bindings resolve to 21 distinct complete
functions, totaling 2,376 bytes. Every byte is rechecked against the original
executable. Function extents come from the earlier independently ELF/GNU-qualified
[catalogue](DISPATCH_CATALOGUE.md); this check does not infer new extents or
perform a fresh symbolic link. The catalogue's historical unsupported-view
record remains preserved.

The declaration inventory now exports `unbound_type_views`. These describe
supported layouts without asserting a concrete table symbol. They do not add
to the existing 57 concrete tables, 2,463 callback slots, 2,205 nonnull bindings
or 838 distinct targets. Existing unsupported layouts remain explicit failures.

## Compiler and entry evidence

The [analysis consumers](../research/screen_lifecycle/prefix_consumer.c) compile
with the original compiler and warnings treated as errors. Forty-four target
assertions check pointer width, the 72-byte extent, all 18 common offsets and
12 matching offsets in each concrete screen. Ten assignments to real base
functions check callback types without pointer casts. Four negative compilation
controls reject attempts to call the family-specific address words.

The [entry checker](../research/screen_lifecycle/verify_prefix.py) executes the
ten compiled consumers in 180 initialized profiles: both screen tables and all
nine receiver/table RAM-alias pairs. Argument aliases follow one specified
rotation, rather than all three-way combinations. Actual target-entry PCs and
forwarded arguments agree with the original table words, and receiver, argument
and table buffers remain unchanged. Ten executed wrong-slot controls are rejected.
The isolated Unicorn 2.1.2 backend is pinned in the validation metadata.

**Original method bodies and returns do not execute in this entry-only check.**
It does not prove attachment-graph behavior, object lifetime, construction,
rendering, input, timing, natural screen behavior or whole-feature parity. The
earlier [Run](SCREEN_RUN_INTERFACES.md), [Destroy](SCREEN_DESTROY_INTERFACE.md),
[cleanup](SCREEN_RESOURCE_CLEANUP.md) and [natural menu](NATURAL_MENU_LIFETIMES.md)
profiles retain their separate scopes.

The first analysis attempt reached all 180 positive entries, then stopped while
selecting a fault instruction: a stack restore shared a callback-load offset.
It is retained as an incomplete attempt. The completed checker also qualifies
the indirect target register when selecting the load. Its second run supplies
the passing evidence and all ten fault witnesses; the incomplete run adds no
accepted profiles.

## Reproduce locally

With the configured matching build and canonical executable in the supported
WSL/Linux environment:

```sh
python -B tools/inspect_screen_prefix.py --output .decomp-lab/prefix-audit-new.json
```

Use the existing isolated Unicorn 2.1.2 environment for the entry check, keeping
the pinned build Ninja on PATH:

```sh
python -B research/screen_lifecycle/verify_prefix.py --output .decomp-lab/prefix-entry-new
```

Both commands preserve existing output paths. Synthetic tests require no game
files, compiler or Unicorn installation:

```sh
python -B -m unittest tests.test_inventory_vtables tests.test_screen_prefix -v
```

[Validation metadata](common-screen-prefix-checks.json) pins producers, sources,
compiler output, original targets and the bounded evidence. Matching C remains
199,912 / 199,912 counted game bytes, with zero game assembly fallbacks. The
inventory remains 40 provisional feature groups and 107 original NPC callbacks
in C. This adds zero original gameplay features, whole-feature acceptances,
whole-NPC acceptances, optional mods or model API calls. The supported playable
build, original assets, saves and other projects are preserved. U003 remains
open for the wider dispatch and signature review.
