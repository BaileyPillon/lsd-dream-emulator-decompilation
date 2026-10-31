# Original virtual-table target catalogue

The [machine-readable catalogue](../research/dispatch/target-catalogue.json)
maps every nonnull callback in the 57 declared virtual tables to its complete
original function. It records **838 distinct functions**, **2,205 nonnull
bindings**, **258 null bindings**, and all **2,463 declared callback slots**.
Repeated inherited methods retain each table, field and slot binding.

This extends the [declaration inventory](NATIVE_DISPATCH.md) with function
ownership, complete spans and hashes. The target bodies occupy 108,300 bytes.
That is the extent of this index, not newly recovered C or a feature total.
The separate [107-function NPC catalogue](NPC_CATALOGUE.md) covers original
entity behavior bindings and remains a different dataset.

## Verification and use

Run in the configured Linux/WSL build environment with your own canonical
executable and a current `ninja check` build:

```bash
python tools/export_dispatch_catalogue.py \
  --output .decomp-lab/dispatch-catalogue-new
```

The exporter preserves existing evidence. It re-audits the actual source
declarations and original table words, then relinks all 306 existing objects
with symbols retained. The entire exported executable must remain canonical
before any function extent is accepted. Independent ELF extraction and GNU
sized text symbols must identify one complete owner per target. Every byte
of each target must match the original, and target ranges cannot overlap.
No extent is guessed from the next symbol or a single entry instruction.

Each target supplies its original PC, full-function hash and size, entry-word
hash, and exact table bindings. These fields let contributors prepare a
bounded analysis context, check a recovered method's owners, or select
targets for a future general dispatch recorder. An AI-assisted analysis
tool can read the same metadata locally; this command calls no model API
and changes no original NPC behavior.

The export also indexes **1,174 indirect-transfer instructions** within those
838 bodies: 1,163 `JALR` instructions linking through register 31 and 11
nonreturn `JR` instructions. It records the source register, owned delay-slot
PC and instruction hash. Standard linked transfers also retain their return
address. Ordinary `JR $ra` returns are excluded. These are static instructions;
they do not identify a runtime receiver, slot, destination or virtual-call
edge. The 11 jumps are not assumed to be calls.

An independent GNU section/symbol extraction checks all 838 complete spans,
all declared callback bindings and every transfer-site record against the
original bytes. Sixteen source-only tests reject changed function tails,
wrong table words, ambiguous or overlapping owners, inconsistent extents,
missing owned delay slots and malformed instruction encodings.
[Validation metadata](dispatch-catalogue-checks.json) pins the export and
records its scope.

## Remaining requirements

The catalogue retains its original unsupported-view metadata as historical
evidence. The later [common-prefix audit](COMMON_SCREEN_PREFIX.md) qualifies the
current `game_flow_screen_vtable_t` word layout separately and rechecks its 21
complete original target bodies using this catalogue's ELF/GNU-qualified extents.
The supported view has no concrete table binding. Four screen-specific address
slots still have no common callable signature. Other callback tables, code
outside these target bodies, actual indirect destinations, receiver ownership,
signatures and natural histories remain part of the wider dispatch review.
This catalogue cannot be passed to the NPC-only recorder; its 107-target
validation and observation limits remain unchanged.

The later [screen lifecycle profile](SCREEN_LIFECYCLE.md) supplies bounded
original factory/Run/Destroy observations for main-menu and dream-chart
receivers. It keeps constructor and cleanup contracts explicit. The common
view is not a separate complete table. Its later word-layout qualification
does not close screen-specific signatures or the broader dynamic call graph.

The contemporaneous source study also compared 14 new incoming one-word
argument views plus two controls for `func_8001DDF4`. All 16 complete linked
functions qualified, but none improved its 26-byte difference. That result
is retained as unsuccessful research; no source is promoted.

At this catalogue's original checkpoint, matching C was
**197,172 / 199,912 bytes (98.63%)**, with two assembly
functions and two inherited debug-frame explanations open. Bounded NPC
profiles remain 40 / 107, compared natural callback types remain five, and
whole-feature/whole-NPC acceptance remains zero. The export executes no game
method and establishes no new timing or gameplay parity. The playable build,
the separate Bevy repository and the user's emulator session are unchanged.
