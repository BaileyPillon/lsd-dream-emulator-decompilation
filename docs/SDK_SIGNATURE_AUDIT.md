# SDK signatures and the sound volume API

The note-start code called a function labelled `SsUtGetDetVVol` with four
numeric arguments. The original target at `0x80031E94` is `SsUtAutoVol`. The
getter is at `0x80031C98` and writes through two output pointers. The symbol map,
minimal SDK declarations and [sound_play_note](../src/sound/sound.c) now reflect
those roles. The executable remains byte for byte identical.

## Evidence and ambiguity

The external [Psy-Q signature catalogue](https://github.com/lab313ru/psx_psyq_signatures)
was inspected at commit `e9e46e7e133ef275a79bfce650924f98edb086bc`. SDK 3.3
`LIBSND.LIB.json` has SHA-256
`cd35240249e36ec25ad1e3ae944fe7737db436a9ad1c37b3b3deacb61fe84248`.
The catalogue stays outside the published repository.

All 608 fixed bytes match in this 676-byte region; the six labels occur at
their expected offsets in `VMANAGER.OBJ`:

| SDK function | Original address | Bytes |
| --- | --- | ---: |
| `SsUtGetDetVVol` | `0x80031C98` | 88 |
| `SsUtSetDetVVol` | `0x80031CF0` | 124 |
| `SsUtGetVVol` | `0x80031D6C` | 140 |
| `SsUtSetVVol` | `0x80031DF8` | 156 |
| `SsUtAutoVol` | `0x80031E94` | 84 |
| `SsUtAutoPan` | `0x80031EE8` | 84 |

Region SHA-256:
`8573aa478c97c2ea3cbd6dfe85f4040097d1abdcb65767f5693596ecfce33a0a`.
The 68 relocation wildcard bytes retain the catalogue's mask. A volume or pan
wrapper alone has an ambiguous pattern because its call target is wildcarded;
the ordered six-function context resolves this pair. The [archived SDK API header](https://github.com/FoxdieTeam/psyq_sdk/blob/master/psyq_4.3/include/libsnd.h)
corroborates the declarations. This is API corroboration, not proof that LSD
uses SDK 4.3.

[audit_sdk_signatures.py](../tools/audit_sdk_signatures.py) audits the four current
raw SDK-labelled segments: **72 functions / 28,944 bytes**. The SDK 3.3 graphics
and sound catalogues yield 51 complete function-sized candidate spans covering
19 functions. Fourteen functions have one candidate label in that catalogue.
There are **zero complete matching library objects** covering these raw
functions. A matching subrange does not prove its entire object's identity.

A sweep across 16 catalogue versions found only repeated no-op object patterns
in these segments. Those patterns are not accepted as symbol identities.
Missing matches do not prove game ownership. The audit retains ambiguity and
never changes source, names or classification automatically; the six volume
labels were reviewed against their larger matching context.

## Native getter verification

[verify_sound_volume.py](../tools/verify_sound_volume.py) executes the original
88-byte getter with **zero stubs**. Its 384 cases combine 32 voice inputs, two
opaque channel contents and six aligned pointer layouts. Inputs cover all 24
valid voices, invalid bounds and 16-bit truncation. Layouts include separate
and identical output pointers, preserving the sequential stores. Whole guarded
buffers, source data, return status, global pointer, GP, stack and saved
registers are compared.

Three changed instructions alter the voice bound, record stride or right-channel
offset. All are detected; changes exist only in private Unicorn memory.
Native report: `.decomp-lab/sound-volume-native-proof-first.json`, SHA-256
`56573700b1c2ba7e8c199ae80aca42aaf7d98c52a1b20bdcd4904086044a9364`.
SDK report: `.decomp-lab/sdk-audit-public-proof-first.json`, SHA-256
`275ecf5cfde6c69da5489fec14ee043d7cbde6857f7c6bc45d67f5f281b3ba84`.
Metadata and producer dependencies are appended to [features.json](features.json).

After a current matching build, supply the external catalogue and choose new
private output filenames:

```bash
python tools/audit_sdk_signatures.py --signatures /path/to/psx_psyq_signatures/330 \
  --output .decomp-lab/sdk-signatures-new.json
python -m pip install -r requirements-analysis.txt
python tools/verify_sound_volume.py \
  --output .decomp-lab/sound-volume-native-new.json
```

The tools require the canonical original and current matching build and pin
source inputs. Catalogue shapes, hashes, full lengths and ambiguity are checked;
the native verifier also checks original addresses/range hashes. Existing
evidence is preserved. Both tools make zero model API calls.

## Remaining scope

Getter fixtures do not accept automatic volume/pan ramps, natural allocation,
audible playback, SPU timing or the complete sound group. Ownership outside
these matches remains to investigate, including the graphics segment. The 72
raw functions are an SDK-labelled inventory, not a newly proven SDK total.

No game function was promoted here. C recovery remains 194,284 / 199,912 bytes,
with seven known assembly functions. The inventory remains 40 provisional
groups, 35 with listed core functions in C and zero whole-feature acceptances.
SDK provenance/ABI analysis is a separate tenth developer capability, alongside
the frozen publication's nine. Original behavior and mods retain separate
deliverables.
