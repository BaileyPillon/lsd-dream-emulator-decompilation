# LSD reverse-engineering objective

> Publication note: this is a frozen local research snapshot. Private
> `.decomp-lab` evidence is excluded; see [provenance](docs/PROVENANCE.md).

Recover the original PS1 game in maintainable, matching C, with its original
NPC scripts, complete asset and behavior evidence, and repeatable runtime
comparison. Provide useful AI-assisted analysis and modding tools alongside
the matching game. Optional gameplay changes have a separate build and do not
count toward original parity.

## Reference and fixed baseline

- Canonical executable: `SLPS_015.56`, 505,856 bytes; SHA-1
  `76322eeade5ebb22dca57fdeac7d68c30f06308d`.
- Pre-prompt source snapshot: `.decomp-lab/prompt-baseline.json`, captured
  2026-10-10T21:28:43Z. The upstream commit identifies the checkout's ancestry;
  this snapshot also preserves the prior local source changes.
- Verified pre-prompt build: 297 objects, 169,540 of 199,672 game text bytes in
  C (84.909251%), with 63 game functions retained in assembly.
- Later classification correction: [docs/SAVE_LABEL.md](docs/SAVE_LABEL.md)
  separates a 240-byte game-support formatter from an SDK-labelled segment.
  The original baseline remains frozen. With the corrected denominator its
  unchanged C numerator is 169,540 / 199,912 (84.807315%), an arithmetic
  restatement rather than a rerun. Current C recovery is 195,844 / 199,912;
  five known remaining game assembly functions still require recovery after
  the [level-model loader recovery](docs/LBD_RECOVERY.md).
- Feature denominator: the same provisional 40 groups in
  [docs/features.json](docs/features.json) for both measurements. Five recorded
  inventory gaps remain; U006 records the user's resolved distinction between
  original NPC behavior and separate AI-assisted development tools.
- The initial local disc is labelled `LSD - Dream Emulator (English v1)`. Its executable
  matches the canonical hash; its translated assets are a separate edition
  boundary. Runtime comparisons must use identical disc assets and BIOS.
- A later [Japanese disc verification](docs/JAPANESE_EDITION.md) records a
  separate Japanese-labelled source, complete disc byte identity, an edition
  comparison and bounded replay evidence. It preserves the earlier English
  records and leaves exhaustive content and cold-boot state acceptance open.

## Completion requirements

1. All remaining game `INCLUDE_ASM` functions recovered in C. No padding,
   instruction substitution, or embedded copies of their assembly to raise
   the count. Original SDK and hardware instructions remain explicitly
   accounted for.
   The [source-quality audit](docs/SOURCE_QUALITY.md) identifies five already-C
   functions with inherited dummy stack padding. Their source explanations
   also require recovery; they are separate from the five assembly fallbacks.
2. A clean complete build produces the canonical executable byte for byte.
   Each promoted source change retains a private comparison record.
3. Asset/resource and command tables are classified, virtual-call dependencies
   are audited, and the inventory's U001-U006 scope gaps are resolved.
4. The enumerated input, movement, links, generation, NPC behavior, UI, music,
   movie, save/card/error and ending scenarios have reviewed comparison
   evidence. Original and rebuilt runs use the same state, seed, inputs,
   emulator, BIOS and assets. A boot observation alone is not acceptance.
5. Before/after reports distinguish inherited original behavior, C recovery,
   independently tested behavior, optional mods and AI-assisted tooling.
6. Requested tools have documented actual applicability and evidence of use.
   Tool incompatibility must not be hidden by mislabelling the game's binary.

## Work coordination

Use private `.decomp-lab` candidates and `tools/decomp_workbench.py check`.
Promote only complete-executable matches. Before changing shared build outputs,
coordinate with any workers using the baseline objects. Keep the original disc,
BIOS, source baseline and unrelated analysis services intact.

Current evidence and source progress are recorded in `docs/features.json`,
`.decomp-lab` comparison reports and build logs. This objective is unfinished
until every completion requirement is met.

The [matching writer recovery](docs/CARD_WRITER_RECOVERY.md) adds 960 C bytes
and preserves standard and clean-build equality. Groups F037 and F038 now
have all listed core functions in C; the provisional core-source count is
37 / 40. Five inherited source-padding explanations and whole-feature runtime
acceptance still require recovery.
## Source-layout correction and current gates

The [expanded audit](docs/SOURCE_LAYOUT_EXPANDED.md) supersedes the earlier
selected five-function source-workaround count. Four padded promotions are
withdrawn and retained as unaccepted research. Current compiled C is
194,212 / 199,912 (97.15%), with nine game assembly functions, 24 inherited
unused-storage explanations and 35 / 40 listed-core C groups. Standard and
fresh clean builds remain canonical. No completion requirement is relaxed.
The [spatial composition](docs/NPC_SPATIAL.md) adds original transform/SDK/GTE
execution for seven callbacks; whole-feature and whole-callback acceptance
remain zero.

The [generation structure profile](docs/GENERATION_STRUCTURES.md) now executes
eleven original routines and checks 1,116 fixtures per original/candidate image.
Actual dispatch, position replacement and mode 3 sprite RNG/scaling agree,
but the scalar C candidate still has ten stack-layout differences. No original
feature, C function or whole NPC is accepted; source and runtime gates remain
separate.

The [mode 0 extension](docs/GENERATION_EFFECTS.md) executes all eight rate
variants and four active child layouts through fifteen original routines,
including consecutive graph updates and periodic resets. Construction,
natural histories and the exact C-frame explanation remain incomplete.

The [entry scanner profile](docs/GENERATION_ENTRIES.md) checks all 56 original
stage records through actual world-coordinate conversion. Its ten-byte packet,
strict range/index semantics and native word arithmetic are verified on bounded
fixtures; twenty source-layout differences and natural spawn/lifetime paths
still require recovery.
