# Apartment Bear behavior

The original `entity_bear_apartment` callback is now the **41st of 107** with
bounded native comparisons. This adds verification evidence; matching C remains
197,172 / 199,912 game-text bytes (98.63%). Whole NPC encounters and whole feature
groups independently accepted remain zero.

The existing [animation binding](ACTOR_ANIMATIONS.md) identifies entity property
77 in Stage 0, group 8, model slot 2. The verifier uses the original 9,820-byte
MOM at offset 36,960 in `CDI/STG00/M001.LBD`, with 10-frame and 30-frame
animations. Original assets remain private and are identified by hashes.

The callback measures proximity before moving and emits command 17 with
parameter -2 when its command timer is divisible by five. At the exact end of
animation zero, it selects animation one and uses the original RNG to optionally
set state 11. State zero follows a five-turn route and continues moving; a
nonzero state follows its own two-turn route, stops at script tick 174, and
becomes state one. Script ticks, animation frames, and command timers are
separate inputs.

The [published evidence](apartment-bear-checks.json) records:

- 604 standalone cases representing 602 distinct initialized inputs, using two
  allocator-residue patterns and signed state, timer, rotation and position edges.
- Two continuous VM histories with 30 callback invocations. Only script tick and
  command timer are injected between calls; RNG, model and entity state persist.
- Thirteen separately computed hand checks that do not call the producer's
  expected-state or scheduling functions.
- Seven executed wrong-output controls, covering command selection, RNG state,
  turning, movement, stopping, animation selection and animation duration. A
  separate escaped-store control is rejected before the write.
- Thirty original function ranges entered, complete pool/model/context and
  surrounding-buffer comparisons, return/ABI/stack guards, and 490 native GTE
  commands checked against independent arithmetic. No dependency-output stubs
  or external AI model calls are used.

The fixture supplies a constructed entity/model graph and inactive sound slots;
it has no collision-stage target. Constructors, engine-driven scheduling,
animation advancement after the selected first frame, populated collision
graphs, active audio, rendering, natural encounters and PS1 timing are outside
this check. Directly invoking a callback after its active flag clears tests the
callback contract; it does not assert that the engine schedules that call.

Source hashes describe the executed local files. Five inherited dependencies
have CRLF working files and LF repository blobs; the evidence records both
hashes and verifies that line endings are their only difference. New verifier,
tests and evidence files retain LF bytes across checkouts. Generated build-map
and assembly input hashes identify private local build evidence.

Run from a current, canonical matching build with the pinned analysis backend:

```sh
python -B -m tools.verify_apartment_bear \
  --output .decomp-lab/apartment-bear-native-new \
  --resource /path/to/original/CDI/STG00/M001.LBD \
  --bridge /path/to/existing/gte-bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'
```

The output path must be fresh and private. Reuse the existing native bridge and
runtime; this check creates small reports and logs, without new recordings or
runtime copies. Original NPC behavior is separate from AI-assisted analysis and
modding tools. This profile adds no C bytes, mods, developer capability category,
whole encounter acceptance or whole-feature acceptance.
