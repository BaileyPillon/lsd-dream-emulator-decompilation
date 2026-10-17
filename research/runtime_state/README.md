# Emulator label-storage research

This directory contains a host-side construction reproducer and a small patch
for the BizHawk 2.11.1 Nymashock adapter. The patch constructs persistent media
records in place before assigning their original labels, flags and values.

- [Construction reproducer](label_construction.cpp): no game, BIOS or emulator
  inputs; emits the actual before/move-after object bytes as JSON lines.
- [Upstream patch](bizhawk-2.11.1-label-initialization.patch): applies to
  `TASEmulators/BizHawk` commit `bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5`.
- [Build, validation and scope](../../docs/EMULATOR_LABEL_INITIALIZATION.md).

The reproducer is excluded from the matching game build. Original PS1 code,
the normal play profile, NPC behavior and matching-C counts retain their
existing boundaries. Rebuilt emulator profiles have separate input identities;
earlier distributed-core state-comparison failures remain retained evidence.
