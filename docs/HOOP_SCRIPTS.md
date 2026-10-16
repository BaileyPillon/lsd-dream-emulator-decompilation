# Original Hoop Girl behavior checks

Hoop Girl and Giant Hoop Girl add **71,536 distinct native fixtures** and
raise bounded callback coverage from **22 / 107 to 24 / 107**. Both callbacks
already had matching C bodies. The complete scripted suite now checks
117,583 fixtures across eighteen callbacks and detects 23 deliberate faults.
This adds no recovered C bytes or accepted whole NPC encounter.

| Callback | Address | Bytes | Property record | New distinct fixtures |
| --- | --- | ---: | ---: | ---: |
| `entity_hoop_girl` | `0x80062570` | 240 | 71 | 35,768 |
| `entity_hoop_girl_giant` | `0x80064CA4` | 72 | 108 | 35,768 |

Property indices are zero-based entries in the original 130-record table.
A fresh link retaining sized ELF symbols verifies both complete callback
extents and reproduces the canonical executable. Original bytes and property
bindings are checked again before native execution.

## Original rules and request order

The regular callback always requests the trigger ratio and writes its result
to context word 4. A zero context timer resets command word 7 to zero and
consumes one original `rand()` result. Its remainder modulo three selects a
raw `axis_c8` request amount of 0, 51,200 or 102,400, with mode zero. Nonzero
timers preserve the command and RNG state.

At entity tick **2,401 and above**, it calls the original facing helper with
`(entity, dream, 1, 0, 0)`. Negative ticks and tick 2,400 skip that request.
The callback then requests forward motion with raw amount -30 and mode zero.
The giant callback executes the real regular callback first, then requests
scale mode 1 with the original `g_OffsetSix` vector.

These are exact arguments at the dependency boundary. The movement, facing
and scaling implementations are contracted here; their downstream narrowing,
transforms, geometry and visible results are not established by this profile.

## Native fixtures and fault sensitivity

Each callback has 3,000 boundary fixtures and 32,768 RNG fixtures, with no
duplicate complete inputs. Boundaries include signed timer/tick extremes,
ticks 2,399 through 2,402, several trigger-ratio results and preserved states.
The RNG fixtures select one initial seed for every possible original 15-bit
result at timer zero and tick 2,401. They cover all 32,768 returned values,
rather than every possible 32-bit seed or successive RNG history.

| Measured native entry, per callback profile | Regular profile | Giant profile |
| --- | ---: | ---: |
| Regular callback | 35,768 | 35,768 |
| Giant callback | 0 | 35,768 |
| Original RNG | 33,368 | 33,368 |

The comparison checks complete guarded entity, dream, command-context and
child buffers, RNG state, ordered calls and arguments, stack guards and saved
registers. The regular profile exercises four explicit dependency contracts;
the giant adds scaling as a fifth. Its parent callback is native code, not a
contract. The full eighteen-callback campaign retains its existing contracts.

Five new private instruction faults change the command destination, zero-timer
RNG gate, initial axis amount, facing threshold and giant scale mode. All are
detected, alongside the preceding eighteen controls. The existing 46,047
scripted fixtures retain exactly their previous inputs and are rerun as
regression checks; they are not counted as new scenarios.

## Relationship to the earlier encounter observation

The [controller-only Hoop route](NATURAL_HOOP_TIMING.md) already records 417
registered Hoop Girl samples and brackets the facing threshold. The native
profile directly checks the callback branch and initial RNG choices under
explicit contracts. It adds no emulator frames, natural giant encounter or
complete geometry, animation, sound or lifecycle history. Whole-encounter
and whole-feature acceptance remain zero.

## Reproduction and source accounting

After a current matching build and the optional analysis dependencies, run:

```bash
python tools/verify_native_ai.py --callback scripted \
  --output .decomp-lab/hoop-scripts-new.json
```

[hoop-script-checks.json](hoop-script-checks.json) records callback, source,
backend and report hashes, case counts and before/after measurements. Raw
game inputs, buffers, compiler artifacts and altered instructions stay private.

C remains 194,212 / 199,912 bytes (97.15%), with nine assembly functions and
24 inherited storage explanations. The 107 existing C callback bodies,
35 / 40 listed-core C groups, ten developer-capability categories and three
optional mods are unchanged. Original NPC behavior, AI-assisted analysis tools
and optional gameplay changes retain separate accounting. This verifier makes
zero model API calls and changes no original runtime behavior.
