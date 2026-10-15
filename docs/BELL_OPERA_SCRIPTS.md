# Bell Striker and Opera Singer behavior checks

Two more original callbacks have bounded native comparisons: Bell Striker and
Opera Singer. They add **17,065 distinct fixtures** to the existing scripted
verifier and raise catalogued bounded callback coverage from **20 / 107 to
22 / 107**. Both callbacks already had matching C bodies. This work recovers
no additional C bytes and accepts no whole NPC encounter or feature group.

| Original callback | Address | Bytes | Property record | New distinct fixtures |
| --- | --- | ---: | ---: | ---: |
| `entity_bell_striker` | `0x8005EBB4` | 228 | 13 | 14,640 |
| `entity_opera_singer` | `0x8005FEF8` | 132 | 38 | 2,425 |

Record indices are zero-based entries in the original 130-record entity table.
Original executable bytes and property bindings are checked before execution.
The native callbacks and original RNG run in the pinned local Unicorn backend;
a separate Python model supplies the expected state and ordered requests.
Trigger-ratio lookup and notification have explicit dependency contracts in
these two profiles. Those contracts do not execute real geometry or event
video playback.

## Preserved rules

Bell Striker always requests the trigger ratio. At timer zero it writes command
12 and increments the entity state. The zero-timer branch takes precedence over
the duration check. On other timers, reaching `duration - 1` sets the timer to
minus one. After either branch, state 36 consumes one original RNG result and
requests notification 11 only when its remainder modulo three is zero.

The fixtures distinguish entering state 36, remaining in it on a nonzero timer,
and leaving it at timer zero. They check timers around every selected duration
boundary, signed extremes, zero and negative durations, and all three RNG
remainders through five deterministic seeds. Native word wrapping is preserved
for both the state increment and duration subtraction. Synthetic extreme or
negative values are boundary fixtures, not claims about natural reachability.

Opera Singer requests the trigger ratio and writes command 1 when the signed
timer is a multiple of 120, including zero and negative multiples. Other timer
values preserve the command context. Its fixtures cover every timer from
minus 240 through 239, additional period edges and signed extremes, with five
trigger-ratio results. This callback consumes no RNG.

Each comparison checks the complete entity, dream, command-context and linked
child buffers, final RNG seed, ordered dependency requests, return address,
stack restoration and saved registers. The models do not replace the original
callbacks in the game.

## Fault controls and regression scope

Four controls for the new callbacks must be detected. All mutations exist only
in private Unicorn memory:

- Bell Striker command written to the wrong context word.
- Bell Striker reset boundary changed from `duration - 1` to `duration - 2`.
- Bell Striker RNG gate changed from state 36 to state 35.
- Opera Singer command written to the wrong context word.

The current full scripted run checks **46,047 fixtures across 16 callbacks**
and detects **18 controls**. That includes 28,982 retained fixtures for the
fourteen earlier callbacks. An initial run of the same fixture set used sixteen
controls; the final run adds the two reviewed Bell Striker controls. These runs
repeat inputs and do not multiply the distinct-fixture count.

Nine new synthetic tests check timer precedence, RNG timing, state and duration
wrapping, signed period boundaries, untouched buffers and fixture coverage.
They support the verifier; the native execution is separate evidence.

## Reproduce

With the current complete canonical build and optional analysis dependencies,
run in Linux or WSL:

```bash
python tools/verify_native_ai.py --callback scripted \
  --output .decomp-lab/my-scripted-npc-check.json
```

Use a fresh output path. The verifier checks source/build freshness, executable
and native-function hashes, property-table bindings and backend identity. It
preserves original inputs and makes no model API calls. The existing
[original NPC guide](NATIVE_AI.md) describes the dependency boundaries.

[scripted-bell-opera-checks.json](scripted-bell-opera-checks.json) pins the
executed source, native reports, property bindings, observed calls, fault
controls, test results and before/after counts. Earlier feature records remain
unchanged. C recovery remains 194,212 / 199,912 bytes (97.15%), with nine assembly
functions and 24 inherited storage explanations still unresolved.

Natural encounters, successive lifecycle histories, visible animation and
sound, complete geometry/event dependencies, PS1 timing and independently
reviewed whole-feature parity remain open. Original NPC rules, AI-assisted
developer capabilities and optional gameplay mods retain separate counts.
