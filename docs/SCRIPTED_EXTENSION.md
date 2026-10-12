# Additional original NPC callback evidence

Five additional original callbacks now pass bounded native comparisons:
Elephant, Small Elephant, Fish, Giant Fish and Airship. Together with the
previous nine scripted callbacks, the extended verifier passes 28,982 fixtures
and detects 14 deliberately broken controls. Fresh Lion and Gray Man runs add
1,608 and 768 fixtures, bringing current bounded coverage to **16 / 107
callbacks and 31,358 fixtures**. Whole-callback and whole-feature acceptance
remain zero.

These are checks of the game's existing scripted behavior. They add no NPC,
generative AI, gameplay mod or model API call. The developer models and native
runner remain separate from the canonical game's C and assembly sources.
[scripted-extension-checks.json](scripted-extension-checks.json) pins the
producer, current reports, callback identities and explicit limits.

## What executed

| Original callback | Native property-table record | Fixtures | Checked behavior |
| --- | ---: | ---: | --- |
| Elephant | 8 | 9 | Scale mode 1 with `g_OffsetTwo`, followed by the original translation request. |
| Small Elephant | 109 | 9 | Scale mode 1 with `g_OffsetHalf`, then forward-motion amount -10. |
| Fish | 35 | 24,015 | Signed periodic direction decisions and translation windows. |
| Giant Fish | 118 | 9 | Scale mode 1 with `g_OffsetSix`, preserving all checked object/context bytes. |
| Airship | 103 | 532 | Original RNG, state selection, rotation/vertical windows, link notification and linked-child animation requests. |

All 19 pinned routines in the extended scripted profile actually enter native
code. They include the 14 callbacks, RNG, action getter, stop routine and two
flag setters. A new guard rejects any dependency contract that would intercept
a routine claimed as native. Range hashes and a catalogued method alone do not
prove execution; entry counts and actual call/state observations are retained.

The verifier compares complete entity, dream-system, command and linked-child
buffers, RNG seed, ordered calls, return completion, stack restoration and saved
registers. The linked child is a valid synthetic entity object, distinct from
the parent. Its animation operation remains an explicit contract. Contracts
clobber volatile registers so incorrect calling assumptions fail.

## Fish periodic decisions

The original uses tick remainders with periods 6, 12, 64 and 500. Their joint
period is 24,000. The fixtures execute every nonnegative tick in that complete
period, plus 15 signed boundaries and repetitions including `INT_MIN`, -1,
24,000, 24,001 and `INT_MAX`.

The six-tick decision selects vertical requests of -64 or +64. The twelve-tick
decision selects -64 or +64 through virtual slot `0xC8`; its complete spatial
meaning remains unaccepted. The 64-tick decision selects forward requests of
-128 or +128. Remainders below 32 in the 500-tick cycle request
`g_MoveDown64Then32`; remainders 32 through 63 request `g_MoveUp64`.

Negative C remainders differ from Python's positive-modulus result. The
independent model uses truncation toward zero. The original/model comparisons
preserve the resulting negative-tick requests. This covers the nonnegative
joint command phases for the supplied context and signed edge decisions;
geometry, rendered movement and all entity contexts are separate work.

## Airship state and linked-child decisions

At tick 700, the original RNG result modulo 3 selects state 11 only when it is
zero. In that state, rotation and vertical amount +30 occur before tick 1,020;
tick 930 sends link notification 10. Other states can request motion blend
`(4, 0)` on the linked child at ticks 100 and 800 when the RNG remainder modulo
5 is zero. Forward amount -30 follows all branches.

The 532 fixtures cross those boundaries with four starting states and seven
RNG seeds. Actual native observations include 70 RNG calls, 12 linked-child
blend requests, seven link notifications and 115 rotation/vertical requests.
Those are recorded calls under contracts, rather than proof of visible
animation, completed links or natural encounter reachability.

## Reproduce and interpret the counts

With a current `ninja check` build and the optional dependencies installed,
use a fresh private report path:

```bash
python tools/verify_native_ai.py --callback scripted \
  --output .decomp-lab/scripted-check-new.json
```

The extended producer verifies original property-table bindings and canonical
function hashes before running. It hashes the actual loaded Unicorn library
and Python binding before and after execution, in addition to checking producer
and game/build identities. The recorded scripted profile uses Unicorn 2.1.4;
the separately qualified card-heap environment remains unchanged.

Ten new synthetic checks cover signed remainders, cycle completeness, decision
boundaries, linked-child identity, original scale requests, native/contract
overlap and backend identities. All 324 developer tests pass on Windows and
Linux. These CI fixtures contain no original game inputs.

| Measure | Before this supplement | After |
| --- | ---: | ---: |
| Original callbacks with C bodies | 107 / 107 | 107 / 107 |
| Callbacks with bounded native comparisons | 11 / 107 | 16 / 107 |
| Bounded callback fixtures in current profiles | 6,784 | 31,358 |
| Matching game C bytes | 195,844 / 199,912 | 195,844 / 199,912 |
| Provisional original feature groups | 40 | 40 |
| Whole groups independently accepted | 0 | 0 |
| AI-assisted developer capabilities / optional mods | 10 / 3 | 10 / 3 |

The official exhaustive feature total remains unknown. The before-prompt
source and feature measurements remain frozen in the
[feature inventory](FEATURE_INVENTORY.md); this table measures the current
supplement's narrower native-check change.

## Remaining work

Ninety-one catalogued callbacks still lack this bounded native profile.
Natural construction, nonempty actor-child lists, state histories, callback
reachability, geometry/GTE, visible motion, actual sound, zero-duration traps,
devices and PS1 instruction/cycle timing remain outside these checks. The
scripted profile retains 13 explicit dependency contracts. C recovery still
requires five assembly functions and five inherited padding explanations.
None of those requirements is replaced by the callback count.
