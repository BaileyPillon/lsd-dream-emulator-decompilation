# Original model vertex decoding

The Japanese-disc audit checks **119,458 polygon packets** in **422 model-bearing
files** against the original `func_80020050` instructions. Every compared signed
XYZ point, vertex count, next cursor and enumeration index agrees. All caller
registers and checked memory guards survive. This closes the vertex-reference
decoding check; rendering and whole-feature acceptance remain separate.

[Machine evidence](model-packet-decoding-checks.json) records the input, executed
tool and backend hashes, checks and remaining limits. The game build stays at
199,912 / 199,912 matching C bytes. No game behavior or optional mod is added.

## Corpus and results

| Encoded occurrences | Count |
| --- | ---: |
| LBD files | 418 |
| Standalone MOM / TMD files | 2 / 2 |
| TMD object tables, including embedded MOMs | 531 |
| Object descriptors | 13,627 |
| Vertex / normal records | 191,582 / 134,340 |
| Triangle / quad packets | 18,161 / 101,297 |
| Vertex references compared | 459,671 |
| Actual mode bytes / flag bytes | 23 / 3 |
| Original decoder calls, including end guards | 133,085 |
| Original decoder instructions executed | 14,309,500 |
| Unresolved files or decoder disagreements | 0 |

Counts describe visits to encoded content. Repeated model data in different
files is counted again. Aliased offsets within an MML library are walked once
and their reference multiplicity is retained. These counts are neither unique
models nor additional player features. Normal records are counted structurally;
their interpretation is not part of this check.

## What was compared

`inventory_model_packets.py` reads the verified raw disc directly. Its bounded
Mode 2/Form 1 reader checks sector sync, MSF, mode, duplicate subheaders and ISO
directory bounds. Mixed-sector movies may be listed but are rejected by the
Form 1 file reader. Complete disc hashes are checked before and after reading.
The reader does not independently check EDC/ECC; the complete expected hash
qualifies this particular input.

`tmd_packets.py` bounds each TMD/MOM/LBD container, object table, vertex array
and primitive payload. It derives packet lengths and index offsets from mode
bits and gradation flags. It does not trust the first two packet bytes: native
mapping can repurpose that header halfword. All referenced vertex indices must
fall within their descriptor.

`verify_model_packets.py` loads the canonical executable into a dedicated 2 MiB
Unicorn 2.1.4 analysis VM. It executes only the qualified 1,152-byte original
reader. Each fixture contains the actual vertex and packet bytes, a supplied
mapped descriptor and guarded output slots. The original mapper and renderer
are not executed by this profile; their validation is separate.

Every polygon is enumerated in order. The first call receives an invalid cursor
and index zero, requiring the original reader to select the geometry's initial
packet. Later calls consume the actual returned cursor. Full point buffers,
count/index slots, return values, saved registers, SP/GP/RA and caller stack are
checked at each return. Inputs are read-only, every data access is bounded, and
the complete VM outside exact output slots and the original 24-byte callee
frame is hashed at every object boundary. Triangle calls must preserve the
unused fourth point. End guards must preserve all output slots.

An independent literal fixture table exercises all 32 supported modes with
flags 0, 4 and 255 through physical and KSEG0 data aliases: **192 fixtures**,
**576 end-guard calls** and **six zero-count calls**. Extreme signed halfwords,
distinct eight-byte vertex records and deliberately invalid header lengths
make width, stride and cursor errors visible. Actual corpus geometry uses
physical data addresses; the alias comparison is confined to the fixtures.

Two controls change only a private analysis VM's original instructions: a
vertex-index load uses the wrong halfword offset, and vertex addressing uses a
four-byte stride. Both instructions execute, both calls return with ABI and
input guards intact, and both produce coordinate disagreements detected by the
oracle. A crash does not count as detection. No original-function output is
stubbed.

The closed run completed in 159 seconds. Its 13,627 per-object records occupy
94,028 compressed bytes. A separate streaming review rechecked the complete
journal hash and counts. No model payload, RAM dump, emulator installation or
disc copy was written.

## Reproduce

Use your own disc with the exact expected full-file SHA-256 and an existing
environment satisfying `requirements-analysis.txt`. Create `.decomp-lab` if
needed and choose unused report/output paths:

```powershell
python tools/inventory_model_packets.py --disc "D:\private\LSD-Japan.bin" --expected-disc-sha256 YOUR_COMPLETE_DISC_SHA256 --edition-label "My verified Japanese disc" --output .decomp-lab/model-packets.json
python tools/verify_model_packets.py --disc "D:\private\LSD-Japan.bin" --inventory .decomp-lab/model-packets.json --output .decomp-lab/model-packet-native
```

The edition label is supplied by the caller. A matching executable alone does
not establish asset edition. Existing reports are preserved, assets are read
without extraction, and the native output directory is bounded to 4 MiB.
Data-free tests cover malformed sectors, container limits, independent packet
layouts, signed coordinates, cursor chaining and vertex bounds:

```powershell
python -B -m unittest tests.test_disc_files tests.test_tmd_packets -v
```

## Remaining work

The separate [SDK mapping/linking audit](MODEL_SDK_MAPPING.md) now verifies
original pointer relocation, descriptor binding, primitive cursor walks and
mode-run headers across all 531 TMD tables. It preserves this decoder
profile's scope and its remaining rendering requirements.

This is functional decoder agreement on supplied mapped geometry. Native
normal-index, UV/palette, lighting, material and GPU packet semantics remain
open, as do full scene loading, rendering, PS1 device timing and natural
collision histories. All 40 provisional original feature groups and all 107
original NPC callbacks retain their separate acceptance gates. This audit
accepts zero whole feature groups and adds zero recovered C bytes.

These are optional analysis tools. They make no model API calls and do not
change the original NPC scripts, game executable or assets. AI-assisted use of
the reports belongs to the tooling track, separate from original game behavior.
