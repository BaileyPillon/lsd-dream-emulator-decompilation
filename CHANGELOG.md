# Changelog

## Initial publication - 2026-10-11

- Continue the upstream decompilation with its full existing Git history.
- Recover additional dream, scene, rendering, file, menu and sound code in
  matching C; the verified snapshot has 194,044 of 199,672 game function bytes
  in C and seven remaining game assembly functions.
- Repair build setup, dependency tracking, error propagation and progress
  reporting. Pin the build dependencies and MASPSX revision.
- Add executable extraction, isolated candidate comparison, original asset
  and dispatch inventories, bounded native NPC checks and recorded replay
  comparison tools, with 134 synthetic-fixture tests.
- Add separately packaged exploration mods with byte-range manifests and
  documented verification limits.
- Publish contributor guidance, a provisional feature catalogue and explicit
  distinctions between original behavior, analysis tools and optional mods.

End-to-end parity remains unfinished. Detailed evidence and limitations are
recorded in the documentation; private game inputs and captures are excluded.
