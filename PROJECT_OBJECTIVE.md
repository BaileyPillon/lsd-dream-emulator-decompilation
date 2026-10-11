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
  restatement rather than a rerun. Current C recovery is 194,884 / 199,912;
  six known remaining game assembly functions still require recovery after
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
