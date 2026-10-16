# Original actor child lifetimes

The optional `--lifetime` profile extends the
[construction checker](ACTOR_CHILD_CONSTRUCTION.md) through original guarded
reentry, destruction, repeated cleanup and reconstruction. All phases share
one actor, pool and CPU for each model and initial memory pattern. The original
constructor-only mode remains the default.

The independent ownership model checks complete actor, manager and pool buffers
at each phase. Native code performs every allocation and release through a
closed graph of [40 sized original functions](actor-child-lifetime-function-ranges.json),
with no function-output stubs. Reports retain phase hashes, allocation/release
order, lock calls and actual entered-function counts.

## Observed corpus

English-v1 and Japanese-labelled extractions each pass the complete lifetime
profile. Their 111 model payloads match, including the same 100 distinct contents.

| Measure | Per extraction |
| --- | ---: |
| Original model instances | 111 |
| Distinct model payloads | 100 |
| Initial memory patterns | 2 |
| Model/pattern fixtures | 222 |
| Consecutive lifetimes per fixture | 2 |
| Original constructor invocations | 444 |
| Child nodes constructed and destroyed | 5,104 |
| Native allocation calls | 16,200 |
| Owned release calls | 16,200 |
| Repeated NULL release calls | 888 |
| Populated-entry no-ops checked | 444 |
| Original cleanup invocations | 888 |
| Qualified original functions | 40 |
| Function-output stubs | 0 |
| Executed instruction faults detected | 5 / 5 |

Repeated cycles and separate edition runs do not add original model contents
or game features. Fault runs are excluded from positive allocation and release
totals. [actor-child-lifetime-checks.json](actor-child-lifetime-checks.json)
records the final source, backend and corpus evidence.

The constructor-only regression repeats all 222 earlier fixtures and retains
their child pointers, script-order type bytes, selection indices, allocation
requests and entered-function counts. All 640 tooling tests pass on Windows
and Linux, with two expected skips per platform. All 392 canonical game inputs
and the complete matching executable retain their hashes.

## Reproduce

Use your own extraction, a complete matching build and the isolated backend
described in the [construction guide](ACTOR_CHILD_CONSTRUCTION.md#reproduce):

```bash
.decomp-lab/actor-children-venv/bin/python tools/verify_actor_children.py \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/actor-child-lifetimes-new \
  --edition-label your-extraction-label \
  --lifetime
```

Run from the repository root in Linux/WSL. Each run makes its own fresh static
inventory and complete symbol diagnostic. The diagnostic must reproduce the
entire original executable before any sized symbol is trusted. Edition labels
are supplied provenance, not edition detection. Existing reports and external
output destinations are refused. Original images, assets and diagnostic output
remain private under `.decomp-lab`.

Synthetic ownership and profile tests need neither game data nor Unicorn:

```bash
python -m unittest tests.test_actor_child_construction -v
```

## Checked history

Each model and memory pattern runs two consecutive cycles:

1. Construct the child graph from the model's original first frame. The first
   cycle enters `func_80065E1C`; the second enters the original guarded method
   `func_80065DBC` using the state left by cleanup.
2. Reenter `func_80065DBC` while populated. It must return without allocation,
   release, lock changes or any actor/manager/pool change.
3. Invoke `func_80065F2C`. Each child releases its state, coordinate block and
   scene node, followed by the actor's type and pointer tables. The complete
   manager/pool state must match the independent free-queue model.
4. Invoke cleanup again. It must perform exactly two NULL releases and retain
   all checked buffers. The signed child count remains -1 after the terminal
   decrement; it is not normalized to zero by the checker.

The second construction uses the actor and pool exactly as native cleanup left
them. Descriptors, payloads and allocation headers are not reset between cycles.
Each cleanup must restore the pool to one free interval. Reconstructed objects
must retain bytes their constructors do not initialize.

At every checkpoint, comparisons cover all 384 guarded actor bytes, all 256
manager bytes, the complete 65,664-byte guarded pool, guarded MOS input,
model/list descriptors, SDK matrix fixture and both allocator globals. Each
host call checks return, instruction budget, stack pointer, `gp`, return address,
saved registers and red zones. The host reinitializes the caller stack between
calls; the CPU and emulated RAM remain shared through the native graphs.

## Executed fault controls

The two constructor controls remain: clearing the 300-tick child lifetime and
shifting the first SDK matrix store. Three further controls must execute and
fail their declared independent buffer comparisons:

- Replace the state pointer passed to `memory_free_mem` with NULL. The full
  pool comparison must expose the unreleased allocation.
- Redirect the selected-child clear to the counter field. The complete actor
  comparison must expose both the retained pointer and wrong final count.
- Invert the populated-entry guard. The complete actor comparison must expose
  replacement of an already allocated graph.

All altered instructions exist only in a fresh analysis VM. Canonical images,
build inputs and the running player remain unchanged. Release or lock traces
support the comparisons; they are not supplied as allocator outputs.

## Scope and remaining gates

This profile begins with supplied actor/model/list descriptors, a native pool
binding and the SDK identity table. Its children have no attached descendants,
parents or external links. The reference model rejects partial tables, aliased
or foreign pointers and populated attachments before changing its owned pool.
These are analysis-profile limits, not new validation added to the game.

The profile adds original lifetime evidence. It does not recover another
assembly function, add an NPC callback profile or accept a whole feature.
Matching C remains 195,844 / 199,912 bytes (97.97%), with five assembly functions
and 17 identified inherited storage explanations still open. Feature groups,
original NPC behavior, AI-assisted tools and optional mods keep separate counts.

Full actor/model/resource creation, cache ownership, attached descendants,
allocation failures, animation playback, rendering, natural encounters and
PS1 timing remain open. This checker makes no model API calls.
