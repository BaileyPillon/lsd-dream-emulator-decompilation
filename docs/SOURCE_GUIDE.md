# Reading and maintaining the source

The source reconstructs the original game's native program in C. The main
engineering constraint is a complete, byte-identical executable built with the
pinned GCC 2.6.3 and assembler configuration. Changes to names, types, layout or
control flow must retain that result.

## Start with a call path

| Concern | Read in this order |
| --- | --- |
| Main game loop | [Game flow](../src/game/game_flow.c), then the selected menu, movie or dream screen |
| Dream lifecycle | [Session](../src/dream/dream_session.c), [dream state](../src/dream/dream_sys.c), [map scene](../src/scene/map_scene.c) |
| Asset/path selection | [Path selection](../src/utils/cd_paths.c), [path cursor](../src/dream/dream_session_path.c), [file buffer](../src/file/file_buf.h) |
| Sound-bank lifetime | [Sound object](../src/sound/sound.c), [sound layout](../src/sound/sound.h) |
| Music playback | [BGM](../src/sound/bgm.c), [sequence file](../src/sound/seq_file.c), then the referenced SDK routines |
| Ownership and events | [Base interface](../src/base/base.h), then the concrete object's constructor, notification handler and cleanup |

Headers are generally beside their implementation under `src/`. They describe
the recovered object layout and dispatch interface. Shared primitive types and
SDK declarations live under `include/`. The [function index](../research/original-functions.json)
connects recovered names to original addresses, extents and hashes.

## Object model and ownership

Objects begin with a vtable pointer. The common prefix provides destruction,
construction, cleanup, attachment and notification operations. Concrete tables
retain the original slot order and native object type words.

Before editing a lifecycle, follow both ownership and notifications:

1. Find the factory and the constructor selected through its vtable.
2. Identify allocations, copied paths, attached children and callbacks.
3. Follow the corresponding cleanup and destructor in their original order.
4. Check the callers that consume the method's return register.

For example, a sound object owns its copied VAB path while the asynchronous
header request is outstanding. The header-completion branch schedules the body
and releases that path. Its eventual cleanup releases retained bank storage and
participates in the shared SPU shutdown decision. These lifetimes explain why
an otherwise tidy reordering can change the original program.

`Destroy`, `Cleanup`, `Detach` and a disabled callback describe different
operations. A detached object can still be owned elsewhere. A payload found at
an old address does not by itself establish a live object; use the recorded
[lifecycle evidence](NPC_LIFETIME.md) when making runtime claims.

## Naming and comments

- Keep exported function names and module prefixes stable. Research tools,
  symbol metadata and earlier reports use those identifiers.
- Use descriptive local names such as `sequence_id`, `program_index` and
  `path_buffer`. Follow the surrounding recovered interfaces for parameter and
  member conventions (`This`, `FrameSyncMode`, `m_GraphicsCtx`).
- Name a recovered field for an observed use. For example, `m_VabId` is passed
  to SDK VAB operations and `m_TransferPending` gates transfer completion.
- Retain address-derived or `Unk` names when the complete role is unresolved.
  Record the known offset, width and consumer instead of inventing a meaning.
- Explain ownership, ordering, representation and original quirks in comments.
  A comment should help a reviewer decide whether a change is safe.
- Preserve original strings and data exactly, including their terminators and
  placement. Human-facing spelling inside the original binary is game data.

Recovered descriptive names are maintenance labels. They do not establish the
original developers' spelling or declarations.

## Types and the native ABI

Retain signedness, integer width, structure offsets, vtable slots and callback
argument order. Several interfaces still store native addresses in `s32` or
use partially recovered virtual-call signatures. Naming the data does not
complete those interfaces' type recovery.

GCC 2.6.3 rejects repeated typedefs and unnamed parameters in definitions.
Shared tagged-type forward declarations belong in [forward.h](../include/forward.h).
Use an existing named structure definition when its layout is established.
Verify a proposed pointer or `const` refinement across its callers before
changing the declaration.

The [matching-C policy](MATCHING_GAME_C.md) permits documented upstream
compiler-layout compatibility storage. Keep its provenance and annotations.
Original failure paths, unused parameters, explicit casts and unusual loop
shapes may be needed to preserve the executable. The normal build still emits
inherited interface warnings; this pass does not suppress them or claim a
warning-free source tree.

## Formatting and review scope

[EditorConfig](../.editorconfig) sets UTF-8, LF endings and basic indentation.
The existing [clang-format configuration](../.clang-format) describes C layout;
apply formatting to the code being reviewed. Avoid mixing an unrelated
whole-tree formatting rewrite into an interface or behavior investigation.

Keep a change focused enough that a reviewer can follow every changed
declaration and its consumers. Small helpers are appropriate when they preserve
the native result and clarify a real boundary. New layers, wrappers and macros
need an implementation reason.

## Validate the complete result

Follow [CONTRIBUTING.md](../CONTRIBUTING.md) to establish a canonical baseline,
compare a candidate translation unit, refresh the standard build and run the
tooling tests. Use the existing pinned toolchain; a modern compiler build is
not the matching gate.

```sh
ninja check
python tools/progress.py --json
python -m unittest discover -s tests -v
```

Require all expected objects, current input hashes and the original executable
SHA-1. Retain the before/after source and comparison evidence. A source cleanup
does not add recovered game bytes or establish additional gameplay acceptance.

The [2026-11-01 maintenance record](SOURCE_MAINTENANCE.md) shows this process for
the current readability pass. The [verification index](VERIFICATION_INDEX.md)
links earlier component and runtime studies.
