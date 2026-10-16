# Original periodic NPC script checks

Tea Doll, Ox Cart, Kicking Man and Small Maiko add **4,935 distinct native
fixtures**, raising bounded callback coverage from **24 / 107 to 28 / 107**.
The complete scripted suite checks 122,518 fixtures across 22 callbacks,
preserves all 117,583 preceding inputs and detects 29 deliberate faults.
These callbacks already have matching C bodies. This changes neither the
original game nor its C recovery percentage.

| Original callback | Address | Complete bytes | New fixtures |
| --- | --- | ---: | ---: |
| Tea Doll: `entity_tea_doll` | `0x8005EF54` | 160 | 3,045 |
| Ox Cart: `entity_ox_cart` | `0x8005F0D8` | 208 | 1,440 |
| Kicking Man: `entity_kicking_man` | `0x80061C04` | 40 | 270 |
| Small Maiko: `entity_maiko_small` | `0x80064AA4` | 112 | 180 |

A canonical link retaining sized ELF symbols checks all four complete extents.
Their bytes agree with the original executable. The verifier also checks each
callback's bindings in the original 130-record property table before execution.

## Original behavior at the dependency boundary

Tea Doll always requests the trigger ratio and writes it to context word 4.
Timers divisible by ten request command 17 in word 7. It then requests forward
movement with raw amount -256 and mode zero. Negative timer boundaries use the
original signed division semantics.

Ox Cart also requests the ratio. Its period is the signed duration divided by
two, rounded toward zero. Remainder zero requests command 10 in word 7;
remainder three requests command 13 in word 12. It requests forward movement
with raw amount -30 and mode one. The profile excludes zero divisors and the
signed minimum-word divided by -1 trap; the model rejects those inputs
explicitly. Negative remainders follow the original word arithmetic.

Kicking Man writes context words 7, 4 and 8 to 18, 0 and -1 only at entity
**frame 30**. Fixtures deliberately vary the separate tick field to catch a
counter mix-up. The callback makes no contracted dependency call.

Small Maiko always requests scale mode one with `g_OffsetQuarter`. It requests
vertical movement with raw amount -32 and mode zero at ticks **201 through 299
inclusive**. Signed extremes and both interval edges are checked using the
original unsigned word comparison; the separate frame field is varied.

## Verification and sensitivity

The comparison checks complete entity, dream, command-context and linked-child
buffers, RNG state, ordered requests and arguments, the restored stack pointer
and saved registers. The four new callback entry counts equal their fixture counts.
All previous scripted inputs remain byte-for-byte identical under canonical
fixture serialization, with a regression check for their frozen digest.

Six additional private faults change primary or secondary command destinations,
the scale mode and the final vertical-phase boundary. All 29 controls in the
expanded suite are detected, with the changed instruction observed executing
in each detecting fixture. Faults affect private emulator memory only; the
original executable and game build remain canonical.

Trigger ratio, scale and movement remain explicit contracts for these profiles.
The checks establish the requests made by the original scripts, not their
complete visual, physical, audio or lifecycle consequences. They add no natural
encounter, emulator replay, whole NPC acceptance or entire feature acceptance.

## Reproduction and accounting

With a current matching build and the optional analysis dependencies:

```bash
python tools/verify_native_ai.py --callback scripted \
  --output .decomp-lab/periodic-scripts-new.json
```

[periodic-script-checks.json](periodic-script-checks.json) records original
function, property, source, backend and report hashes, measured requests and
before/after counts. Raw game inputs, buffers, altered instructions and native
execution artifacts remain private.

C recovery remains **194,212 / 199,912 bytes (97.15%)**, with nine assembly
fallbacks, 24 inherited storage explanations and 35 / 40 listed-core C groups.
All 107 original callbacks already have C bodies; 28 now have bounded native
comparisons. Whole encounters and entire feature groups accepted remain zero.
Original NPC behavior, AI-assisted developer tools and optional mods retain
separate accounting. The Bevy port is unchanged.
