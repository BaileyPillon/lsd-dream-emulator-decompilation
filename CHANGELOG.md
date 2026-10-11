# Changelog

## Original render-context bounds verification - 2026-10-11

- Recover signed bounds fields and short-circuit data-read behavior in 4,648
  native fixtures with zero stubs and four detected negative controls.
- Compare a readable C candidate with the original across all fixtures; retain
  its 38 byte differences and leave the matching build's assembly in place.
- Reconcile six SDK names and three reviewed MIPS prototypes in the private
  Ghidra project, preserving native bytes and checking parameter storage.
- Preserve C coverage, NPC counts, whole-feature acceptance and the ten
  developer capabilities; add reusable bounds verification and output checks.

## SDK provenance and sound API audit - 2026-10-11

- Correct the call at `0x80031E94` to `SsUtAutoVol` and locate the pointer-based
  getter at `0x80031C98` using a pinned six-function SDK context.
- Add signature auditing for 72 raw SDK-labelled functions, with complete
  object/span comparisons and retained ambiguities.
- Verify the original getter in 384 native cases with zero stubs and three
  detected controls; add five synthetic catalogue/context checks.
- Preserve the executable, game C coverage and whole-feature acceptance. Add
  SDK provenance/ABI analysis as separate developer capability A010.

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
