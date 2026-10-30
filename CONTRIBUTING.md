# Contributing

Start with [the README](README.md) for setup and [the roadmap](docs/ROADMAP.md)
for open work. Pull requests should target `main`. Keep original-game recovery,
developer tooling and optional mods explicit in the change description.

For tooling or documentation work, run `python -m unittest discover -s tests -v`;
those tests need no original game inputs. Use the issue templates for build
problems and executable-grounded research findings. Preserve upstream
attribution and [third-party notices](NOTICES.md), and keep proprietary inputs,
private analysis exports and emulator captures outside commits.

Establish a verified baseline before changing game code:

```bash
source .venv/bin/activate
python configure.py doctor
python configure.py
ninja check
python tools/progress.py --json > build/progress-before.json
```

The supported executable SHA-1 is
`76322eeade5ebb22dca57fdeac7d68c30f06308d`. The build uses GCC 2.6.3,
MASPSX's ASPSX 2.21 mode, and the pinned disassembler dependencies. Reuse
these versions when comparing instructions.

## Studying and refining recovered C

All counted game functions now have matching C bodies. Start with an open
behavior, asset, type or source-explanation question from the roadmap, then
identify its function in `src/`. The [original function index](research/original-functions.json)
provides verified names, extents and hashes for context export. Its 2,082
entries include SDK routines and are not a count of game functions or features.

1. Establish the canonical baseline above and export context for the selected
   function. Recovered C needs no old private assembly catalog.
2. Check original instructions, callees, types, signed widths, field offsets
   and ownership. Comments and pseudocode are analysis, not original declarations.
3. Refine the complete translation unit in an isolated candidate. Preserve
   other functions, original control flow and data placement.
4. Use the candidate check below, optionally with `--function FUNCTION` for
   complete linked-function diagnostics. Accept only a whole-executable match;
   a matching individual function cannot override a changed executable.
5. Run the tooling tests, refresh the standard build and retain the comparison
   evidence. Report source understanding and runtime observations separately;
   a refinement of existing C does not add recovered bytes or game features.

The owner's [current source policy](docs/MATCHING_GAME_C.md) allows documented
upstream stack-layout compatibility storage. Preserve its annotations and
provenance. Arbitrary unused padding, inline assembly, embedded instruction
bytes and instruction substitution are not a route to an accepted C change.

`func_800434DC` is a small matching example. Its unsigned entry comparison
and loop structure reproduce all 23 original instructions, including GCC's
stack allocation and register choices, without inline assembly.

The [compiler census](docs/UNUSED_LOCAL_CENSUS.md) collects unused-local
diagnostics across every configured game C unit using the normal compiler
flags. Treat warnings as leads: verify complete removal builds before cleanup,
and preserve the explicitly documented compatibility storage unless a reviewed
replacement retains the complete executable match.

For AI-assisted analysis, use an isolated evidence bundle and candidate:

```bash
python tools/decomp_workbench.py context --function func_80020050 --output .decomp-lab/context-new
python tools/decomp_workbench.py check --source src/file/tmd_prim_geom.c --candidate .decomp-lab/context-new/candidate.c --function func_80020050 --output .decomp-lab/check-new
```

The context command exports verified original bytes, headers, optional native
Ghidra evidence and a prompt; it does not invoke a model. For recovered C it
uses the public index and GNU MIPS objdump, checking every printed instruction
word against the original executable. [The recovered-C workflow](docs/RECOVERED_C_CONTEXT.md)
describes its evidence and limits. The check command
uses the unit's configured compiler mode and preserves the standard build.
Promote a candidate only after the complete executable matches. The
AI-assisted tools do not change the canonical game or count as NPC features.

To inspect native dispatch declarations, run:

```bash
python tools/inventory_vtables.py --output .decomp-lab/native-tables-new.json
```

The audit checks original words, explicit C initializers, table boundaries and
source hashes. [Native dispatch](docs/NATIVE_DISPATCH.md) distinguishes static
bindings from inferred signatures and remaining call-site closure. Preserve
original callback bindings when improving names and types.

The [screen lifecycle checker](research/screen_lifecycle/README.md) composes
original factories, Run methods, destruction and pool release. It records the
explicit setup/cleanup contracts and stops at the original runner's observed
zero-receiver access on exhaustion. Keep these bounded observations separate
from natural screen histories and accepted PS1 fault behavior.

The optional [return and buffer observer](docs/DISPATCH_RETURNS.md) follows
original method returns and checks synchronous destinations against a verified
private disc. Keep recorded returns, asynchronous completion and whole-feature
acceptance separate. Its owned source-only fixtures require no game assets.

[Native animation auditing](docs/NATIVE_ANIMATIONS.md) measures original
model/animation records and references separately from feature counts.
[Original NPC auditing](docs/NATIVE_AI.md) checks signed property bytes and
callback bindings against the current C table:

```bash
python tools/inventory_entities.py --output .decomp-lab/native-entities-new.json
```

Keep callback-slot counts, distinct function counts and runtime branch coverage
separate. Names in recovered source are labels, not proof of an encounter's
appearance or every behavior branch.

[Runtime comparison](docs/RUNTIME_COMPARISON.md) explains how to freeze
replay inputs and compare frames, GPU memory, state payloads and PCM audio.
Use new output directories for each run and comparison; retain failed runs
as evidence. A matching replay establishes only the recorded scenario.

For controller-only NPC histories, use the optional
[instruction-entry workflow](docs/NPC_ENTRY_TRACE.md). Keep its observer build
and explicit cross-core output comparison separate from the matching game
and default strict runtime comparisons. Retain source snapshots and failed
controls; report one recorded history without counting it as a whole NPC class.

The [original NPC catalogue](docs/NPC_CATALOGUE.md) exports complete verified
callback ranges from a current matching build. Use its actual ELF/GNU extents
and original hashes for observer targets; preserve the full-image check and
keep the generated executable and ELF private.

For several callback types in one route, use the optional
[catalogue observer](docs/NPC_CATALOGUE_TRACE.md). Build and record with
`--catalogue`, then compare original/rebuilt output and explicitly compare
stock/observer output. Retain the independent selected-PC trace. Distinguish
registered dispatches from nested function entries and unresolved contexts;
corroborate each instance's clock through rooted RAM snapshots.

Use the offline [NPC lifetime inspector](docs/NPC_LIFETIME.md) to distinguish
enabled registration, disabled contexts and scene reachability in verified
recordings. Preserve sampled transition intervals; do not interpret disabled
payload or former object storage as live behavior.

The [compact engine observer](docs/NPC_LIFETIME.md#engine-entries-and-stop-timer)
can compare another controller replay with that verified history while sharing
the installed runtime. It retains entry logs and comparison hashes rather
than duplicate raw buffers or audio. Build freshness remains a separate WSL
check. Keep signed property storage distinct from the native consumer views
exported by `tools/inventory_entities.py`.

For concurrent instances of one callback, declare every owner and entry window
in the [multi-instance profile](docs/NPC_MULTI_INSTANCE.md). Each owner needs
independent RAM clock evidence. Keep default single-instance checks strict;
do not silently accept tick resets or omit an instance with an incomplete clock.

## Build and tooling changes

```bash
python -m unittest discover -s tests -v
```

Tests use synthetic executables and disc images. They must not require game
files, install dependencies, or write into the checkout's original disc.
Game code changes also require `ninja check`; passing tooling tests alone
does not prove that the game matches or runs correctly.

The build tracks C headers and included assembly. After editing the split
configuration or symbols, use `ninja split` or `ninja resplit`. `resplit`
recreates the generated `asm/` tree; handwritten assembly belongs in `src/`.
`ninja clean` preserves source inputs. A subsequent build should regenerate
its outputs and pass the same original hash.

GCC 2.6.3 rejects repeated typedefs and unnamed parameters in definitions.
Put shared forward declarations in `include/forward.h`, define an already
declared tagged type with `struct name { ... };`, and give unused parameters
a name. Some inherited vtable types remain approximate and produce warnings;
the executable hash is the matching gate.

Keep gameplay changes in the separate mod workflow. Add verified patch
ranges, tests that reject an incorrect base and preserve all other bytes,
and a precise description of the behaviour and any gameplay testing.

Commit source, configuration, documentation, and tests. Generated assembly,
original game files, built executables/discs, virtual environments, and local
experiments are ignored and should remain outside contributions.
