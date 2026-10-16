# Original actor child construction

The [native checker](../tools/verify_actor_children.py) runs each bounded model's
first frame through the original child enumerator, pool allocator, scene-node
constructor, transform constructors and SDK coordinate initializer. Its closed
graph contains 22 sized original functions and supplies no function outputs.
The [reference model](../tools/actor_child_model.py) independently predicts the
complete actor, manager and pool buffers, including guards and retained bytes.

This extends the earlier [populated child flag checks](ACTOR_CHILD_FLAGS.md).
Those checks supplied populated child objects. This profile constructs those
objects through original code, starting from supplied actor/model/list
descriptors, an unlocked pool and the SDK identity-matrix table. Full actor
creation, resource ownership and natural encounters remain separate gates.

The later optional [lifetime profile](ACTOR_CHILD_LIFETIMES.md) adds destruction,
repeated cleanup and guarded reconstruction on the same actor and pool. This
constructor-only profile and its earlier measurements remain separate evidence.

## Observed corpus

English-v1 and Japanese-labelled extractions each pass the complete profile:

| Measure | Per extraction |
| --- | ---: |
| Original model instances | 111 |
| Distinct model payload hashes | 100 |
| Initial memory patterns | 2 |
| Positive construction executions | 222 |
| Child nodes constructed | 2,552 |
| Native allocation calls | 8,100 |
| Entered original functions | 22 |
| Dependency output stubs | 0 |
| Executed instruction faults detected | 2 / 2 |

The runs are separate edition checks of the same model corpus, not 222 original
models or 200 distinct contents. A changed lifetime store and a changed SDK
matrix store each execute 29 times in their negative-control run. The controls
are excluded from the positive execution, child and allocation totals.

## Reproduce

First build the canonical executable using the [matching toolchain](../README.md#build-the-matching-executable).
Use your own [disc extraction](ASSET_INVENTORY.md) and a separate environment:

```bash
python3 -m venv .decomp-lab/actor-children-venv
.decomp-lab/actor-children-venv/bin/python -m pip install \
  -r requirements.txt -r requirements-card-heap.txt
.decomp-lab/actor-children-venv/bin/python tools/verify_actor_children.py \
  --layout /path/to/extraction/disc.xml \
  --output .decomp-lab/actor-children-new \
  --edition-label your-extraction-label
```

Run from the repository root on Linux/WSL. Keep the existing analysis
environment unchanged. The CLI requires isolated Unicorn 2.1.2 and probes the
pinned Ninja version before any build dry run. The pinned Ninja package's
documented build suffix is accepted and recorded. An older Ninja can invalidate
a newer build log even during a dry run, so the checker refuses it first.

`--edition-label` is a supplied provenance label; it does not detect a disc's
edition. The report hashes the extraction XML, each selected source file and
every model instance. English and Japanese extractions require separate runs.
Duplicate model instances and distinct content hashes are counted separately.

Choose a fresh directory inside `.decomp-lab`. The checker refuses existing or
external destinations before reading original inputs. It writes its own fresh
animation inventory, diagnostic ELF, diagnostic executable, per-case reports
and final `report.json`. Failed runs retain their evidence and `failure.json`.
These outputs contain private original data and remain excluded from Git.

Synthetic tests require neither game files nor Unicorn:

```bash
python -m unittest tests.test_actor_child_construction -v
```

## What executes and what is checked

The checker links all current canonical objects with the existing linker flags
and script, removing only the strip flag for its private diagnostic. It requires
the complete diagnostic executable to equal the canonical executable before
parsing any function symbol. Each of the
[22 function ranges](actor-child-construction-function-ranges.json) must then
have the exact sized ELF extent, address and canonical bytes. Execution outside
this closed set fails; no callback or allocator result is supplied by the host.

A fresh CPU is created for each model and memory pattern. RAM and CPU state
persist through manager setup and the single uninterrupted child-construction
graph. Each host-issued call checks return, instruction budget, stack pointer,
`gp`, return address, saved registers and stack red zones. Native reads and
writes must remain inside their declared buffers or original read-only data.

Every model is tested with two initial memory patterns: a repeated nonzero byte
and distinct address-dependent bytes. The independent interval/free-queue model
predicts allocation order and complete manager/pool contents. The comparison
covers all 384 actor bytes, all 256 manager bytes and the complete 65,664-byte
guarded pool. Model/list descriptors, guarded MOS input, the SDK matrix fixture
and both allocator globals are also checked. Untouched object payload bytes,
including stale allocator residue, must remain unchanged.

The first frame follows the original enumerator's arithmetic: MOS base plus
16 plus four times the animation count. It does not follow the animation offset
table for this constructor path. The static inventory separately validates that
table and all bounded model references. Missing references, unresolved files,
rejected signatures and unsupported positive profiles stop the complete-corpus
run rather than being skipped.

Enumeration preserves script order. Primitive records can rewind the output
cursor and later declarations can overwrite earlier type bytes. The first pass
counts primitive records to obtain the selection key; it does not take the
largest key. Tests retain these behaviors, signed rational arithmetic and
halfword narrowing. Zero/wrapping child counts, searches outside the owned type
buffer and allocation exhaustion remain outside this successful profile.

Two private instruction faults must execute and fail the independent full-pool
comparison: clearing the 300-tick child lifetime and shifting the first SDK
matrix store. These changes exist only in a new analysis VM's memory. They do
not modify the game, build inputs, original images or the user's player.

## Evidence boundaries

The SDK matrix table is an initialized fixture; this profile does not execute
`GsInit3D` or prove hardware initialization. Actor/model/list descriptors and
the pool binding are also supplied inputs. The original constructors perform
the child, coordinate and state allocations and initialization.

This check adds behavior evidence and a reproducible contributor tool. It does
not recover an additional assembly function, add an NPC callback profile or
accept a complete feature. Matching C remains 195,844 / 199,912 bytes (97.97%),
with five assembly fallbacks and 17 identified inherited storage explanations.
The feature inventory remains 40 provisional groups, with no whole-feature or
whole-encounter acceptance. Original NPC behavior, AI-assisted tools and optional
mods retain separate counts. This checker makes no model API calls.

Allocation failures, destruction/resource-cache ownership, animation playback,
rendering, natural encounters and PS1 timing still require evidence.
