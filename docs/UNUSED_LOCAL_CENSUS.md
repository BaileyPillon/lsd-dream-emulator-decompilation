# Compiler census and the CD reader's unexplained frame

The current source-quality remainder is **three inherited functions**,
correcting the earlier count of two. The previous selected audit missed the
unused 2,048-byte `sector` array in `cd_file_driver_read_sectors`. Its purpose
in the original source is unresolved. Renaming the buffer or replacing it
with another unused record would not recover that explanation.

The complete executable still matches the original. Compiled C remains
**197,172 / 199,912 bytes (98.63%)**, including these unresolved existing C
functions. Two game functions remain in assembly. This correction changes
neither that numerator nor any original-game acceptance count.

## Compiler evidence

The new [census tool](../tools/audit_unused_locals.py) runs the exact bundled
GCC 2.6.3 over all **79 configured game C translation units**. It uses their
normal preprocessing, G0/G8 selection and compiler flags, including the
existing `-Wall`. It preserves every source/build input and the matching
executable; generated source, assembly and complete diagnostics remain private.
SDK assembly and unconfigured source files are outside this census.

The initial census emits six unused-variable warnings. Four complete-unit
controls reproduce the canonical image. Six separate removal builds then
distinguish harmless dead pointers from frame-dependent arrays. Original and
candidate function extents come from actual ELF symbols and independently
checked GNU sizes; symbolic links reproduce their complete ordinary images.

| Function | Unused declaration | Result of removing only that declaration |
| --- | --- | --- |
| `func_8004DB18` | `unk_class` pointer | Complete executable unchanged |
| `cd_file_driver_open` | `rec` pointer | Complete executable unchanged |
| `func_800563C0` | `vtable` pointer | Complete executable unchanged |
| `debug_file_driver_unk15` | 64-byte array | Function shrinks from 16 to 8 bytes; whole image differs |
| `debug_file_driver_open` | 64-byte array | Function shrinks from 16 to 8 bytes; whole image differs |
| `cd_file_driver_read_sectors` | 2,048-byte array | Same 224-byte function, but 13 executable bytes differ |

The three unused pointer declarations are removed. They need no replacement
storage and add no recovered C bytes. Their combined ordinary build and a
fresh build from **306 absent objects** both reproduce the entire original
505,856-byte executable. A repeat of the public census emits the three array
warnings, with no changed compiler settings.

All six declarations are present in the frozen imported baseline,
`16a3914b9bcb75bd94a6b983ed3a952234461625`. The CD sector declaration also
traces to [upstream commit `0233a9d3`](https://github.com/cawfee/lsd_decompiled/commit/0233a9d32bba994d67a4d401586dbc9092c1d2d8);
it was not introduced by this correction.
The earlier [28-function review](SOURCE_LAYOUT_EXPANDED.md) was selected by
source patterns and did not include this function. Its reports and the later
recoveries retain their historical scope; the latest remainder is now three.

## Why the CD buffer stays unresolved

Removing `sector` changes the original `0x838`-byte frame to `0x38`. All
thirteen differing instructions retain their original opcode and register
fields; their SP-relative displacements change by 2,048 bytes. Every byte
outside the complete 224-byte function remains canonical, but the strict
executable check still fails. The candidate is retained privately and does
not replace the matching game source.

The inherited comment explained the compiler's retained allocation, not why
the original program declared that storage. The source now makes that
distinction explicit. Further recovery must explain it through genuine data,
types or source lifetimes while retaining the complete original instructions.

The three known unexplained arrays total **2,176 declared bytes**. Their
functions span **256 compiled code bytes**. Excluding those entire spans
leaves **196,916** C bytes outside the currently identified unresolved
functions. This conservative exclusion is not a certification of all other
C source: warnings cannot reveal every unused record tail, artificial
liveness construct, alias assumption or original inline boundary.

## Reproduce

Start with the [configured matching toolchain](../CONTRIBUTING.md) and a current
complete build. From Linux/WSL, run:

```bash
ninja check
python tools/audit_unused_locals.py --output .decomp-lab/unused-census-new
```

The current expected result is 79 game C units and three unused-local
warnings. The tool rejects a wrong compiler, stale or nonmatching build,
unparsed unused-variable diagnostics, changed inputs and reused output paths.
Ten source-only tests exercise diagnostic parsing and evidence guards without
original game files or a compiler.

The audit identifies leads; a warning alone does not establish a workaround.
Use fresh complete-unit removal builds, real function extents and original
binary comparisons to investigate each finding. Do not remove retained arrays
merely to silence diagnostics.

## Other gates

Ten further hull-query source forms, including two known controls, test actual
output lifetimes around the midpoint/count operations. None matches the
original; the best hull candidate remains 26 bytes different. The primitive
query's best candidate remains 22 bytes different. Neither is promoted.

There are still 40 provisional feature groups, 38 with listed core functions
in C, 107 original NPC callbacks and 40 bounded callback profiles. Whole-NPC
and whole-feature acceptance remain zero. The complete original behavior,
asset, dispatch, disc/error and timing requirements remain open. This work
executes no new gameplay scenario and invokes no model API. The playable
build and separate Bevy repository retain their existing identities.

[Validation metadata](unused-local-census-checks.json) records the before/after
censuses, individual and combined builds, function extents, source identities
and unchanged C/feature counts. Earlier private captures and failed comparisons
remain intact.
