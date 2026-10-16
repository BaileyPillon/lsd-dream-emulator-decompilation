# Matching generation dispatch and entry scanning

Two original generation functions now compile from C with every instruction
matching the Japanese executable. Standard and fresh 306-object builds reproduce
the complete 505,856-byte image. The recovery adds **580 C bytes** and removes
two assembly fallbacks.

| Function | Original address | Recovered bytes | Stack frame |
| --- | --- | ---: | ---: |
| `dream_generation_find_entry` | `0x80055620` | 444 | 80 bytes |
| `dream_generation_update_structure_entities` | `0x80054C74` | 136 | 40 bytes |

The complete executable retains SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d` and SHA-256
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.
The source baseline is commit `8369e3574adae246dec8113101e630b1e5175f55`.
Only the two generation C units change among the 392 protected build inputs;
the other 390 retain their hashes. Compiler, flags and link configuration stay
the same.

## Recovered source lifetime

Both loops read an object's actual vtable through an initialized four-byte
snapshot, then return the selected callback as a scalar function pointer.
The scanner reads slot `0xE8`; the structure updater reads the typed `Update`
slot at `0xEC`. The callback receives its original arguments.

Each snapshot contains exactly one vtable address. Its sole array element is
consumed by the lookup; all four bytes contribute to the real method call.
The scanner's placement/style packet remains ten bytes. The updater forwards
the caller's existing three-word position pointer. There are no extra packet
fields, unused arrays, hard register bindings or instruction substitutions.

The earlier aggregate-return hypotheses reserved the original frames but
retained a method-word store absent from the executable. Returning a scalar
from the initialized vtable view recovers the original frame and instruction
scheduling together. The scanner also naturally uses the original register for
its method load and indirect call.

Actual GCC 2.6.3 allocator observations distinguish this from merely requesting
unused storage:

| Observation | Scanner | Structure updater |
| --- | --- | --- |
| Direct scalar control's virtual local area | 16 bytes | 0 bytes |
| Real packet allocation | 10 bytes, rounded to 16 | None |
| Matching source's additional reload allocation | 4 bytes, local area 16 to 24 | 4 bytes, local area 0 to 8 |
| Observed reload pseudo | 117 | 78 |
| Final matching frame | 80 bytes | 40 bytes |

The four-byte allocations occur through `assign_stack_local`, called by
`alter_reg` during `reload`. The observation does not identify a particular
source field as either pseudo. In the scanner trace, the nested temporary/local
allocator calls describe the same ten-byte packet allocation and are counted
once. Normal and traced complete assembly agree for both matching candidates
and both scalar controls. The debugger uses ordinary breakpoints; the observer
does not explicitly rewrite compiler memory, force return values or patch
instructions.

This is a readable matching reconstruction. The original author's exact C
spelling and helper organization remain unknown.

## Verification

An independent artifact pass requalifies **105 compiler observations** across
six source families, including eleven repeated controls: 98 raw source hashes
and ten distinct function images. Each ELF observation contains one complete
sized function at the original address. Five subsequent readable complete-unit
checks also match the entire image. These are compiler observations, not new
gameplay scenarios.

The existing native profiles were run against the original and exact complete
candidates before promotion, then repeated against the promoted canonical build:

| Profile | Retained inputs per image | Original routines entered | Executed fault controls |
| --- | --- | ---: | ---: |
| Entry selection and world conversion | 4,116 cases | 3 | 6 |
| Structure updates and mode-zero effects | 3,116 cases plus 40 histories containing 480 update frames | 15 | 9 |

The entry profile checks all 56 original entries in fourteen stage tables,
ordered ten-byte packet reads, full retained buffers, returns, indices and ABI.
The structure profile checks all eight mode-zero rate variants and four active
child layouts, ordered rotations/translations/resets, sprite scaling, RNG,
buffers and ABI. Every fault control measures execution of its altered
instruction. Neither profile substitutes dependency outputs. See the earlier
[entry investigation](GENERATION_ENTRIES.md) and
[structure effects profile](GENERATION_EFFECTS.md) for their detailed domains.

Both verifiers now qualify the original routines through the pinned executable
ranges without requiring the obsolete generated assembly files for these two
recovered functions.

## Progress and remaining scope

| Measure | Before | After |
| --- | ---: | ---: |
| Matching C game-function bytes | 194,212 / 199,912 (97.15%) | 194,792 / 199,912 (97.44%) |
| Game assembly fallbacks | 9 | 7 |
| Groups with all listed core functions in C | 35 / 40 | 37 / 40 |
| Inherited unused-storage explanations still open | 24 | 24 |
| Original NPC callback C bodies | 107 / 107 | 107 / 107 |
| Bounded native NPC profiles | 36 / 107 | 36 / 107 |
| Entire feature groups independently accepted | 0 / 40 | 0 / 40 |

The forty groups are provisional; an official exhaustive feature total is
unknown. The original game's functionality was already retained by the matching
C-plus-assembly build. These two source recoveries add no new original gameplay
feature, distinct native fixture domain or accepted whole encounter.

Natural construction and parameter provenance, dynamic list changes during
callbacks, sound/entity spawning, lifetime histories, rendering/audio and PS1
timing remain broader verification requirements. The local player is not used
or changed by these checks. No new emulator play sequence is claimed.

The [play helper](PLAYING.md) remains available for the matching game. The ten
developer capability categories and three optional mods keep their existing
counts. No model API is called, and the separate Bevy/Rust port
is unchanged. The frozen [project objective](../PROJECT_OBJECTIVE.md) and all
its completion requirements are retained.

## Reproduce

With your own supported executable and the documented build environment:

```bash
python configure.py
ninja check
python tools/progress.py --json
python tools/decomp_workbench.py catalog
python tools/verify_generation_entries.py --output .decomp-lab/entry-recovered-new.json
python tools/verify_generation_structures.py --output .decomp-lab/structures-recovered-new.json
python -m unittest discover -s tests -v
```

The native commands require the documented WSL analysis dependencies. Choose
fresh report paths. Tooling tests use synthetic inputs and do not certify
gameplay parity. A normal clean rebuild should reproduce the same executable.

[generation-lookup-recovery-checks.json](generation-lookup-recovery-checks.json)
publishes identities, counts and scope. Original images, complete candidate
executables, generated assembly, ELF exports, native buffers and debugger traces
remain private. Earlier nonmatching reports are preserved as historical evidence.
