# Nymashock state diagnosis

The eight decoded state bytes that varied in the recorded Japanese cold boots
belong to unused storage in Nymashock's native `"CD"` media-type label. This
diagnosis identifies the field and how its unused bytes enter saved memory.
The original byte comparisons still fail: no bytes are masked, no state is
normalized, and no whole feature group is accepted by this result.

[nymashock-state-checks.json](nymashock-state-checks.json) records the core,
sources, diagnostic reports, experiments and before/after measurements. The
earlier [Japanese edition report](JAPANESE_EDITION.md) and its metadata retain
the result before this field was identified.

## Native field and copy path

The checked binary is the Windows BizHawk 2.11.1 Nymashock core,
`dll/shock.wbx.zst`, with SHA-256
`5c6fe90fadd670318ca74993911b171e15b167c7f2e1e88bf66de4661fc24126`.
Its decompressed ELF retains symbols. Waterbox saves dirty visible memory
pages in address order; omitted pages are not reconstructed from assumed
zero bytes. The diagnostic follows the saved native pointer graph:

```text
Mednafen::MDFNGameInfo -> MDFNGI.RMD -> RMD_Layout.MediaTypes[0].Name
```

| Field in the recorded states | Native address or object offset |
| --- | --- |
| Game-info pointer / object | `0x36f0029a9f0` / `0x36f0029a850` |
| RMD layout / first media-type name | `0x36f0080f980` / `0x36f0080fc00` |
| Short-string size flag, text and terminator | Object bytes 0–3: `04 43 44 00` |
| Unused short-string storage | Object bytes 4–23 |
| Observed eight varying bytes | Object bytes 16–23, addresses `0x36f0080fc10`–`0x36f0080fc17` |

`InitCd` constructs the short string with three stores at
`0x36f00068a35`, `0x36f00068a3a` and `0x36f00068a41`. These initialize
the size flag, two characters and terminator. Both native vector insertion
paths copy all 24 object bytes; the slow path copies the final eight bytes
at `0x36f002563b7` / `0x36f002563bb`. The untouched storage travels with
the label into the saved heap page. The earlier contents of the temporary's
unused bytes have not been traced further.

The loaded instructions agree with BizHawk's
[CD initialization](https://github.com/TASEmulators/BizHawk/blob/2.11.1/waterbox/nyma/cdrom.cpp),
Mednafen's pinned
[RMD types](https://github.com/TASEmulators/mednafen/blob/382ff1b8d293c9a862497706808cbb79b2cecbfb/src/git.h),
LLVM 18.1.8's
[short-string representation](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.8/libcxx/include/string),
and Waterbox's
[memory serializer](https://github.com/TASEmulators/BizHawk/blob/2.11.1/waterbox/waterboxhost/src/memory_block/mod.rs).
The analysis uses the actual binary as well as those sources.

## Recorded checks and limits

The diagnostic checks 44 checkpoint pairs from 82 distinct saved states:

| Recorded comparison | Checkpoint pairs | Decoded pairs with eight differences |
| --- | ---: | ---: |
| Initial original/rebuild cold boots | 6 | 6 |
| Current original/rebuild cold boots | 6 | 0 |
| Current same-original cold repeat | 6 | 6 |
| Initial shared-state play | 13 | 0 |
| Current shared-state play | 13 | 0 |

All differences in the 12 nonidentical decoded pairs map to the same unused
label storage. Input-state hashes remain unchanged. A real saved pair produces
the same decoded hashes and diagnosis with Windows Python 3.14's standard
Zstandard decoder and Linux Python 3.13 with `zstandard==0.25.0`.

Twelve additional synthetic tests distinguish unused storage from a changed
game-state byte, active label changes, invalid roots or vector extents,
invisible and absent pages, truncation and an unknown core. All **175** tooling
tests pass locally on both platforms. Fixtures contain no captured game or
emulator bytes.

This extends developer capability A004 (runtime comparison). It does not
change the strict comparator or emulator, establish launch identity for older
manifests, or cover additional gameplay scenarios. Other core versions and
platforms require a separately validated profile.

## Run the read-only diagnostic

Use Python 3.14, or install `requirements-analysis.txt` in your analysis
environment. Supply two private states and the checked Windows core file:

```bash
python tools/inspect_nymashock_state.py \
  --original /private/original/frame-1800.State \
  --rebuilt /private/repeated/frame-1800.State \
  --core /private/BizHawk/dll/shock.wbx.zst \
  --output .decomp-lab/nymashock-state-new.json
```

The output must be new. The report retains complete decoded hashes, all byte
difference counts, unclassified differences and the native field addresses.
Input files are read only; there are no model API calls.

## Source recovery and counts

Another bounds-predicate experiment attempted 168 forms: 132 compiled and
36 failed because of C89 declaration placement. Repairing those declarations
made all 36 compile. Across both batches there were 204 compiler invocations,
168 successful comparisons and no exact match. The closest preserved bounded
candidate still differs in 38 bytes; compiler flags and game source are
unchanged.

Before and after this supplement, matching game C is **194,884 / 199,912 bytes
(97.48%)**, six known game functions remain in assembly, and the inventory has
40 provisional groups, 35 with all listed core functions in C and zero whole
groups independently accepted. NPC counts remain 107 C callbacks and 11 with
bounded native checks; developer capabilities remain 10 and optional mods 3.
The official exhaustive feature total remains unknown. The current complete
505,856-byte executable still equals the canonical input byte for byte.
