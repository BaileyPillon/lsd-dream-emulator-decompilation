# Changelog

## Save-title recovery - 2026-10-11

- Recover the original 240-byte save-title formatter in matching C and give
  its callers a shared typed declaration.
- Separate the formatter from six BIOS file wrappers. Correct the game/SDK
  classification to 194,284 of 199,912 game bytes in C; preserve the original
  publication measurements. The seven known game assembly functions remain.
- Verify the complete canonical executable and 1,952 native formatter cases
  using the actual SDK conversion routines, with zero stubs and three detected
  negative controls. Recheck all 6,784 existing bounded NPC fixtures.
- Add a reusable local save-title verifier with evidence-preserving output
  checks. Full save/card and whole-feature runtime acceptance remain open.

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
