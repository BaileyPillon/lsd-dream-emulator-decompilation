# Periodic NPC proximity and movement

This profile executes the original Bird, Minotaur and Giant Minotaur callbacks
with real distance, trigger-ratio, transform, SDK rotation and GTE code. It adds
bounded comparisons for the two Minotaur callbacks. Bird was already counted;
the new profile replaces its remaining trigger-ratio output contract.

No original behavior is added or modified. These three profiles use constructed
meshless graphs without actor children. Natural encounters and whole-callback
acceptance remain open.

## Original behavior

| Callback | Original property index | Proximity byte | Distinct initialized inputs |
| --- | ---: | ---: | ---: |
| Bird | 24 | 30 | 943 |
| Minotaur | 9 | 30 | 1,504 |
| Giant Minotaur | 10 | 60 | 181 |
| Total | | | 2,628 |

Bird refreshes its ratio and commands 7 and 8 when the signed timer is divisible
by 15. It sets scale to two, adds the fixed-point two-degree yaw increment and
moves forward by -512. Its ratio uses the position before that movement.

Minotaur refreshes its ratio on every invocation. Its period is the original
signed half of the duration word, rounded toward zero. A divisible timer writes
command 7 to 10. It then moves forward by -30. Odd durations, negative periods,
all phases of the selected periods up to 60, and signed-word edges are checked.

Giant Minotaur has its own behavior. It always clears command 4. A zero timer
writes 11 to commands 7, 12 and 17; other timers preserve those words. It moves
forward by -30 and does not call the ratio helper.

The ratio helper uses signed-word Manhattan distance on X/Z, the original
property-table radius and two successive truncating divisions. Y is ignored.
Tests cover absent dream context, the inclusive radius boundary and cases
that cross the radius during movement. The model does not merge the divisions.

## Evidence and limits

A fresh 306-object symbol link produces the complete canonical 505,856-byte
image. Sized ELF spans qualify 23 reviewed routines; 18 are entered by the
positive fixtures. All three callbacks are included in those actual entries.

The profile compares eight complete graph buffers, the RNG word, movement
scratch, ordered GTE requests/results and return, saved-register, GP and stack
guards. All 5,256 positive GTE commands execute in the pinned local Nymashock
implementation. Seven deliberate faults execute their changed instruction and
change a checked buffer: three command destinations, the distance Z field,
the ratio property byte, the movement halfword and the native GTE shift. These
controls issue 14 further GTE commands. One separate bridge startup self-check
is excluded from both totals.

The shared harness's preceding Bear/Rabbit/Acrobats/Ship profile also passes
again: 10,408 fixtures with the original checked-buffer digest unchanged.
Historical evidence remains pinned to its original producer; the new run pins
the current shared harness.

[Metadata](npc-periodic-spatial-checks.json) records source, range, table,
backend, runtime, report and log identities. Raw images, generated ELF/assembly,
buffers and faulted code remain private. The six semantic/domain unit tests use
synthetic data; their pass count is separate from native execution evidence.

Minotaur duration words producing a zero half-period, and `INT_MIN % -1`, reach
original BREAK paths. They are rejected by this normal-return profile and
remain unverified. Natural construction, repeated lifecycle histories,
collision-bearing objects, animation/render/audio output and PS1 timing also
remain outside this evidence. No whole encounter or feature group is accepted.

## Reproduce

Use a current matching build, the optional analysis dependencies and a local
bridge built as described in [RENDER_GTE.md](RENDER_GTE.md). Run from the
repository in WSL, with a fresh evidence directory inside `.decomp-lab`:

```bash
python -m tools.verify_npc_periodic_spatial \
  --output .decomp-lab/periodic-npc-new \
  --bridge .decomp-lab/my-gte-bridge.exe \
  --runtime 'D:/CodexRuntimes/lsd-emulator/BizHawk-2.11.1'
```

Set the Windows runtime argument to your own pinned BizHawk installation. The
tool requires the canonical executable and current build before execution and
rechecks source/build/backend identities afterwards.

## Progress accounting

Bounded native callback coverage rises from 32 to 34 of 107. Compiled C remains
194,212 / 199,912 bytes (97.15%); nine assembly functions and 24 inherited
storage explanations remain. Whole-feature and whole-encounter acceptance
remain zero. The provisional feature denominator remains 40 groups.

Original NPC scripts are game behavior. This verifier is a separate development
tool, makes zero model API calls and adds no optional gameplay change. The
Bevy/Rust repository is separate and unchanged.
