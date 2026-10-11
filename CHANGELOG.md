# Changelog

## Native behavior verification extension - 2026-10-11

- Add bounded native/reference checks for nine original timed and input-driven
  callbacks, including the Dog's action/RNG state changes.
- Pass 4,408 cases and detect nine deliberately wrong instructions; extend
  combined bounded coverage to 11 of 107 callbacks and 6,784 fixture cases.
- Preserve original behavior, matching C coverage and whole-feature acceptance
  status. Motion, animation-selection and sound contracts remain explicit.

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
