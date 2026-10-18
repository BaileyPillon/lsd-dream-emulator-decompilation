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

## Matching a function

1. Choose an active `INCLUDE_ASM` in `src/`. Its generated assembly is under
   the folder named by the macro. Comments may contain earlier attempts;
   these remain unverified until a new build passes.
2. Translate the original instructions into C. Preserve function boundaries,
   data placement, signedness, and observable behaviour. Correct the forward
   declaration when adding typed arguments.
3. Replace that function's `INCLUDE_ASM` with C and run `python configure.py`
   to update assembly dependencies, then `ninja check`.
4. Accept the change only when the complete executable hash passes. For a
   failed match, compare the object with the generated original assembly:
   `mipsel-linux-gnu-objdump -dr build/src/scene/stage_texture.c.o`.
5. Run the tooling tests and report the function, verified hash, and coverage
   change. Do not count assembly wrappers or near matches as decompiled C.

`func_800434DC` is a small matching example. Its unsigned entry comparison
and loop structure reproduce all 23 original instructions, including GCC's
stack allocation and register choices, without inline assembly.

For AI-assisted analysis, use an isolated evidence bundle and candidate:

```bash
python tools/decomp_workbench.py context --function FUNCTION --output .decomp-lab/context-new
python tools/decomp_workbench.py check --source src/unit.c --candidate .decomp-lab/context-new/candidate.c --output .decomp-lab/check-new
```

The context command exports verified original bytes, headers, optional native
Ghidra evidence and a prompt; it does not invoke a model. The check command
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
