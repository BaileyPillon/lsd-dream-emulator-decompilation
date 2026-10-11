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

The [save workflow supplement](CARD_SAVE.md) extends native evidence through
the original retry wrapper and actual SDK string/label helpers. Seven explicit
contracts cover file I/O, allocation and diagnostic output. Its independent
model, full-executable C comparison and private Ghidra metadata remain separate
from whole-feature and hardware acceptance. [card-save-checks.json](card-save-checks.json)
records the publication's source and evidence pins without game bytes.

## Save-title classification correction

The [save-title supplement](SAVE_LABEL.md) recovers `func_800507F8` in matching
C. The old 336-byte `asm/40FF8.s` segment combined this 240-byte game-support
formatter with six BIOS wrappers and their padding, totalling 96 bytes. The
whole segment had been classified as SDK. The new split counts the formatter
as game support while keeping the BIOS wrappers under `src/psyq/`.

Current game C coverage is 194,284 of 199,912 bytes, with 147,880 SDK bytes and
188 startup bytes excluded. Both the C numerator and game denominator increase
by 240 bytes; this is one recovered function and a classification correction.
The seven previously listed game assembly functions remain. The frozen initial
publication and pre-prompt reports retain their original measurements.

A matching complete build, isolated whole-executable comparison and 1,952
bounded native save-title fixtures verify the new source. The three public NPC
verifiers were rerun against the current build and passed their existing 6,784
cases. Hashes and scope are appended to [features.json](features.json). Original
inputs and reports remain private; public CI still tests synthetic fixtures.

## SDK signature and volume-API supplement

The [SDK audit](SDK_SIGNATURE_AUDIT.md) uses a pinned external catalogue to
check the ordered six-function volume region. It corrects the getter/automatic
volume names and declarations while retaining original executable equality.
The native getter passed 384 cases and three controls without stubs. Raw SDK
object and function-sized signature matches retain their different evidence
scopes and ambiguities. Historical reports remain preserved; current producer
hashes and callback rechecks are appended separately to the feature inventory.

## Render-context bounds supplement

The [bounds audit](RENDER_BOUNDS.md) verifies the original assembly function
in 4,648 native cases, including signed fields, inclusive boundaries and exact
short-circuit data-read traces. Four changed instructions are detected without
stubs. A compiled C candidate agrees on the bounded fixtures but differs at 38
byte positions and is not promoted. C coverage, NPC counts and whole-feature
acceptance are unchanged.

The private Ghidra project now reflects the reviewed SDK volume names and
three explicitly typed MIPS prototypes. Parameter storage and unchanged native
bytes were checked before saving. The project database, binary exports and C
candidate remain private; the public supplement contains metadata only.

## Rendering grid-window supplement

The [grid-window audit](RENDER_GRID.md) runs the original 660-byte helper in
74,832 scalar cases, including all angle words, with four explicit contracts
and eight detected controls. The private full C candidate gives the same
bounded results but differs in four executable bytes across two stores.
It is not promoted. Saved private Ghidra has reviewed caller/helper/builder
prototypes; their 1,232 native bytes are unchanged. Current counts and hashes
are appended separately to the inventory. Real GTE, downstream rendering
and whole-feature parity remain open.

## Rendering grid and streaming composition supplement

The [streaming composition audit](RENDER_STREAM.md) extends native execution
through the original builder, row splitter and seven-object slot selector.
It passes 45,408 bounded cases and detects four controls with three remaining
position/GTE contracts. The original table's slot binding is verified before
synthetic vtable execution. The nonmatching full C candidate passes the same
fixtures but retains four byte differences and is not promoted.

Two reviewed private Ghidra prototypes retain 460 native bytes unchanged;
parameter storage and successful saving were checked. Source/evidence pins in
[render-stream-checks.json](render-stream-checks.json) extend the publication
record without changing original feature, NPC, C or developer-capability counts.

## Rendering matching and ordered-store supplement

The [ordered-store audit](RENDER_MATCHING.md) adds executed-store observation
with immediate readback to the same 74,832 scalar fixtures. All three native
variants preserve checked final outputs. The four-byte C candidate changes
store order in 68,306 cases; a corrected full C candidate preserves it but
retains 13 executable differences. Neither is promoted.

The initial unsuccessful memory-hook method and controlled diagnostic are
preserved separately. The successful proof's hashes and 106 additional source
trials are pinned in [render-matching-checks.json](render-matching-checks.json).
Original inputs, raw reports and C candidates remain private. C, feature,
NPC, developer-capability and optional-mod counts are unchanged.

## Original sprite scaling supplement

The [sprite scaling audit](UI_SCALE.md) executes 203,472 original cases and the
same number of nonmatching C-candidate cases, with zero stubs. It checks ordered
halfword access and store readback, guarded buffers and the unused stack. Four
wrong controls alter checked outputs; 32 overlap fixtures expose the fresh Y
denominator read after X's store.

The failed global memory-hook method is preserved with an eight-run diagnostic
and producer hash. The successful verifier and private-output tests are public;
game inputs, candidate images and raw reports remain private. The full candidate
retains 12 byte differences and is not promoted. Metadata and historical count
preservation are recorded in [ui-scale-checks.json](ui-scale-checks.json).
