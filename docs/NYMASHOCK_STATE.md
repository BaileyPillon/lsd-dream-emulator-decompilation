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

## Empty-card extension and native accessors

The October 15 extension applies the earlier field diagnosis to the two new
empty-card Load captures. All **32 checkpoint pairs** (64 snapshots) have eight
decoded differences at the same emulator guest addresses above. These are
Waterbox addresses, separate from PlayStation RAM and Windows process memory.
The symbolic owner chain, live `CD` text, vector extents and `Virtual CD Drive`
label agree in every snapshot. Both observed 24-byte string objects are retained
by hash; later checkpoints repeat those two exact object inputs.

This extends the October 11 diagnosis; identifying the field is not a new
discovery. The new execution evidence covers the bundled libc++ accessors:

| Actual ELF method | Address | Symbol bytes |
| --- | --- | ---: |
| `std::__1::basic_string<char>::c_str() const` | `0x36f0001b540` | 34 |
| `std::__1::basic_string<char>::size() const` | `0x36f0001bc90` | 100 |

Unicorn 2.1.4 executes their unchanged x86-64 instructions and real helper
calls against copies of the captured object and ELF memory. The harness
requires a normal return, preserved saved registers and stack, no writes
outside its private stack, no object mutation, and no reads outside the object
and stack. Neither method reads unused object bytes 4–23. `c_str()` returns
the live character pointer; the harness then reads its `CD\0` bytes. `size()`
returns two. This is native emulator-code analysis, not execution of a new
PlayStation game routine.

Twelve calls cover both unique objects: the two baseline methods, both methods
after changing unused bytes 16–23 in private copies, `size()` after changing
the live size to three, and `c_str()` after changing the first character to
`X`. The length and character controls change the observed result as expected;
capacity changes do not. No instructions or saved input files are changed.
Other consumers and earlier allocator contents remain outside this evidence.

Two further one-frame pairs boot the original disc twice and the rebuilt disc
twice. Each reproduces the eight-byte difference, so changing between the
two discs is not necessary to produce it. These controls share their disc
within each pair; output labels and launch order still differ. They are
initialization controls, with no gameplay acceptance. A previously successful
persisted-card Load pair is also checked as an equal-state control: all archive
members agree, and it is not classified as a differing label.

The existing structural diagnostic and the ELF-derived reader independently
agree on all decoded hashes and difference counts. The raw archive comparator
is included without changes. The empty-card comparator still reports failure;
no masking, normalization or new runtime-profile acceptance is introduced.

Install `requirements-analysis.txt` in the qualified Linux/WSL environment,
then use the existing command with explicit execution and controls:

```bash
python tools/inspect_nymashock_state.py \
  --original /private/empty-card/original/frame-0.State \
  --rebuilt /private/empty-card/rebuilt/frame-0.State \
  --core /private/BizHawk/dll/shock.wbx.zst \
  --execute-accessors --controls \
  --output .decomp-lab/nymashock-accessors-new.json
```

Without the new flags, the earlier structural interface and report remain
available. Exit status zero means the diagnosis completed, not that the
states match. Execution reports explicitly retain `parity_profile_accepted:
false`, complete state hashes, all differing addresses and the raw comparison.
Only the pinned Windows core is qualified. The tests use synthetic fixtures
and need no emulator, game, firmware or optional native backend.

[Extension metadata](emulator-state-checks.json) records the captures, actual
accessor calls, controls, private evidence hashes and unchanged before/after
counts. The new 22 tests bring the full tooling suite to **510**, passing on
Windows Python 3.14 and Linux Python 3.13. Current C remains **194,212 / 199,912
bytes (97.15%)**, with nine assembly functions, 24 inherited storage
explanations, 35 / 40 listed-core C groups, 20 / 107 bounded NPC profiles and
zero whole-feature or whole-encounter acceptance. Developer capability A004
is extended; category and mod counts remain ten and three. No model API is
called. The historical October 11 counts and metadata above remain a separate
snapshot.
