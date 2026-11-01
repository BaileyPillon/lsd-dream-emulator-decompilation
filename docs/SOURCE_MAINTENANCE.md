# Source maintenance: 2026-11-01

This pass improves the readability and navigation of the matching C project.
Original game behavior, exported function names, structure sizes, vtable order,
storage widths, compiler-layout annotations and proprietary inputs are preserved.

## Code changes

| Area | Maintenance change |
| --- | --- |
| Game flow | Name screen factory/run arguments and the owned dream session; document original factory failure and teardown contracts. |
| Dream sessions | Name notification sources, codes and map indices; explain masked native sender types and graphics-context boundaries. |
| Path selection | Name RNG selections, path offsets, texture variant counts and the two-phase path cursor. Preserve the number and order of RNG calls. |
| BGM | Name path-address arguments and sequence state; distinguish an attempted open from a successful SDK result. |
| SEQ files | Name the inherited file driver and temporary path buffer; document completion-flag ownership. |
| Sound banks | Name program/tone storage, VAB identity, readiness, pending transfer, owned path storage and pitch offset. |

The identifier pass touches **33 function definitions** and names seven sound
fields from their direct SDK consumers and allocation/release paths. A separate
BGM field becomes `m_OpenState`, with its corrected `0x1A` offset annotation.
The value `2` means an open was attempted; the original routine still reports
success after `SsSeqOpen` returns `-1`.

BGM now uses the existing-width named readiness and VAB-ID fields instead of
duplicating their byte offsets. The actual stored widths and native layout are
unchanged. Remaining unresolved field and function names retain their original
labels; inherited interface warnings remain visible.

## Project navigation

The repository overview is reduced from 687 to 170 lines. Build instructions,
current source status, upstream attribution and licensing remain prominent.
The detailed evidence narrative is retained in the
[verification index](VERIFICATION_INDEX.md), with relocated links.

The [source guide](SOURCE_GUIDE.md) documents reading paths, object ownership,
naming, ABI constraints and review expectations. EditorConfig makes encoding
and indentation consistent for future edits.

## Verification and limits

[source-maintenance-checks.json](source-maintenance-checks.json) records source
hashes, changed modules, the baseline revision and matching-build evidence.
The full executable is compared against the canonical 505,856-byte Japanese
reference, not only the functions edited in this pass.

The baseline and refined build both contain all 306 expected objects and
**199,912 / 199,912 counted game-function bytes in C**. The executable SHA-1
remains `76322eeade5ebb22dca57fdeac7d68c30f06308d`, with SHA-256
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.

This is an incremental rebuild of the affected translation units, followed by
the complete linked-image check. It is not a new clean-room reconstruction or
an additional gameplay campaign. Matching-C coverage, whole-feature acceptance
and original NPC acceptance counts do not change. The Bevy port and legacy
checkout are separate and remain untouched.
