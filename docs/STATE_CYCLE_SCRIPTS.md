# Original NPC state and cycle scripts

Buddha, Fox, Soldier and Balloon add **155,597 bounded native fixtures**,
raising callback coverage from **28 / 107 to 32 / 107**. The expanded scripted
suite checks **278,115 fixtures across 26 callbacks**, preserves all 122,518
preceding inputs and detects 37 deliberate faults. All four callbacks already
have matching C bodies; this comparison changes no original game behavior or
matching-C recovery count.

| Callback | Address | Complete bytes | Added fixtures |
| --- | --- | ---: | ---: |
| `entity_buddha` | `0x8005EFF4` | 228 | 35,693 |
| `entity_fox` | `0x8005ED30` | 496 | 100,656 |
| `entity_soldier` | `0x80060148` | 356 | 19,008 |
| `entity_balloon` | `0x8005FEC8` | 48 | 240 |

A fresh symbol-retaining link of the current 306 objects reproduces the
complete canonical executable. Each sized ELF function agrees with its
original image span. The checker also verifies the original property-table
bindings at indices 20, 16, 40 and 37 respectively.

## Original behavior at the declared dependency boundary

Buddha draws once at tick zero. A result divisible by seven requests scale
mode one with `g_OffsetOneTwoOne`. Every timer divisible by four requests the
trigger ratio, writes it to context word 4 and requests command 28 in word 7.
Forward movement with raw amount -100 and mode zero follows those operations.
Negative timers and noninitial ticks are included.

Fox can replace any initial state with state 11 on an odd tick-zero draw.
State zero requests forward amount -90 before tick 64. At tick 64, another
draw selects a positive or negative quarter-turn, followed by the upward
translation request. Later ticks request lateral amount -374 with a random
binary mode. State 11 requests a quarter-turn on multiples of five, forward
amount -2048, and an actor-child flag equal to whether the next draw is
divisible by seven. Other states make no further request. Tick-zero state
changes can therefore consume two draws in one callback.

The actor-child flag call executes the actual 132-byte `func_80065A5C` fan-out
method, rather than replacing its result. These fixtures have an empty actor
child list, so they verify the boolean argument and the empty traversal. They
do not establish its effect on nonempty actor children or assign a visual
meaning to that flag.

Soldier requests the ratio and commands on timer multiples of seven: word 7
receives 3, and words 9 and 10 receive 64. Exact ticks 200, 400, 600 and 800
select turns; tick 800 also resets the tick field to -1. Lateral amount -30
is always requested. A nonzero **32-bit word at entity offset `0x28`** adds
vertical amount -200. Inputs include `0x10000` and the signed word extremes,
which distinguish a full-word test from a low-halfword test. The separate
entity frame and nudge fields are not substituted for that word.

Balloon always requests vertical amount -90 and mode zero. Its checked tick,
frame, state and timer variations preserve entity/context bytes and RNG state.

## Coverage and sensitivity

The new RNG domains include one initial LCG state for every original 15-bit
first result in Buddha's initial phase and three Fox phases: initial state
selection, tick-64 turning and state-11 child flag selection. Subsequent draws
are checked in order against the original LCG. This is not an exhaustive
enumeration of joint RNG histories or all 32-bit seeds.

Complete entity, dream, command-context and linked-entity buffers, RNG state,
ordered calls and arguments, stack restoration and saved registers agree with
the separate models. Input identities include initialized buffers, callback,
RNG state and the explicitly supplied trigger-ratio contract value. All earlier
case records retain their frozen serialization and digest.

Eight new controls alter command destinations, initial scale mode, motion
amounts, Fox's state and child-flag gates, or Soldier's word-load width.
All 37 controls in the expanded suite are detected, with the changed instruction
observed in each detecting input. Changes affect separate private Unicorn
memories; positive instructions and the canonical executable are unchanged.

Geometry, movement, rotation, scale, ratio, sound and other existing script
dependencies retain explicit contracts. The suite's 32 native function ranges
are an inventory; actual entry counts are recorded separately. These are
constructed script checks, not natural encounters, actor construction, complete
lifetime histories, rendering/GTE, audio or PS1 instruction/cycle timing.

## Reproduce and account for progress

With a current matching build and the optional analysis dependencies:

```bash
python tools/verify_native_ai.py --callback scripted \
  --output .decomp-lab/state-cycle-scripts-new.json
```

[state-cycle-script-checks.json](state-cycle-script-checks.json) records source,
function, property, backend and report hashes, measured requests, detected
controls and unchanged source/feature counts. Raw inputs, generated code,
executable images and native buffers stay private.

C remains **194,212 / 199,912 bytes (97.15%)**: nine assembly functions,
24 inherited storage explanations and 35 / 40 listed-core C groups. All 107
original callbacks have C bodies; 32 now have bounded native comparisons.
Whole NPC encounters and entire feature groups accepted remain zero. Developer
capabilities stay at ten categories and optional mods at three. Original AI,
AI-assisted tools and the separate Bevy port retain distinct accounting.
