# Source and evidence provenance

## Repository ancestry

- Upstream: [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled).
- Imported upstream commit: `16a3914b9bcb75bd94a6b983ed3a952234461625`.
- Upstream history and authorship are retained. The publication adds the current
  C recovery and reusable tooling in a separate commit.
- [FirecatFG/lsddecomp](https://github.com/FirecatFG/lsddecomp) is acknowledged
  for original-toolchain identification and early segment research.

## Target identity

The target is the original Japanese PlayStation executable `SLPS_015.56`:

| Property | Value |
| --- | --- |
| Architecture | Little-endian R3000 MIPS-I |
| File size | 505,856 bytes |
| SHA-1 | `76322eeade5ebb22dca57fdeac7d68c30f06308d` |
| SHA-256 | `282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f` |

The local disc used for recorded emulator comparisons was an English-v1 asset
edition with this same canonical executable. Its translated assets are a
separate edition boundary. Those results compare original and rebuilt code
using the same assets and BIOS; they do not establish equivalence to every
Japanese-disc asset or hardware configuration.

## Publication boundary

The October 11, 2026 feature inventory is a frozen report of local checks,
not an independently rerun result supplied by GitHub CI. References beneath
`.decomp-lab/` identify private evidence artifacts and are deliberately not
published. Ghidra databases, copyrighted inputs, full binary/context exports,
raw emulator captures and local service configuration stay outside Git.
Absolute paths in the published inventory have been replaced with logical
artifact references; their recorded content hashes remain unchanged.

Build and tooling instructions are reusable. A contributor with the required
original inputs can generate new matching-build, asset, NPC and replay reports
using the documented tools. Public CI runs the synthetic-fixture tests only.
The publication checkout's clean build and tooling checks are summarized in
[publication-checks.json](publication-checks.json); this contains metadata,
not game input or output bytes.

The feature catalogue records C recovery, inherited C-plus-assembly behavior,
bounded native checks and whole-feature runtime acceptance separately. It does
not claim a developer-official feature total or completed end-to-end parity.
