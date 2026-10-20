# Captured collision exception contexts

The 20 retained cross-frame hull replay failures now have checked interrupt
register contexts and compatible functional instruction paths. They remain
**20 strict failures**. This diagnostic identifies evidence of intervening
execution; it does not deliver an interrupt, reproduce device scheduling, or
turn those calls into passing comparisons.

Matching C remains **197,172 / 199,912 bytes (98.6294%)**, with two assembly
functions and three inherited storage explanations still open. Whole-feature
and whole-NPC acceptance remain zero. The matching playable build and the
separate Bevy port are unchanged.

| Retained opening-route observation | Result |
| --- | ---: |
| Existing hull calls inspected | 194 |
| Previously passing full-state functional calls | 174 |
| Affected calls replayed with the diagnostic | 20 |
| Consistent captured interrupt contexts with compatible functional PCs | 20 |
| Contexts with a branch delay | 1 |
| Strict failures retained | 20 |
| New controller histories / expanded RAM bytes written | 0 / 0 |
| New matching C bytes / accepted whole features | 0 / 0 |

## What the recorded fields establish

The optional diagnostic binds the observer profile to the retained CPU source
and header at Mednafen commit
[`382ff1b8d293c9a862497706808cbb79b2cecbfb`](https://github.com/TASEmulators/mednafen/tree/382ff1b8d293c9a862497706808cbb79b2cecbfb).
Both source hashes must match; a modified or ambiguous profile is rejected.
These are the pinned core's rules, rather than a general hardware certification.

Its [exception routine](https://github.com/TASEmulators/mednafen/blob/382ff1b8d293c9a862497706808cbb79b2cecbfb/src/psx/cpu.cpp#L529-L567)
records the exception code in CAUSE bits 2–6, branch state in bits 30–31,
and instruction-derived CE bits. EPC points to the preceding branch when
the branch-delay bit is set. The
[CPU declaration](https://github.com/TASEmulators/mednafen/blob/382ff1b8d293c9a862497706808cbb79b2cecbfb/src/psx/cpu.h#L206)
assigns interrupt exception code zero.

All 20 affected calls record a changed EPC, exception code zero, and returned
K0 equal to EPC. Their CE fields agree with the qualified original instruction
at the interrupted PC. A bounded observer finds that PC on the functional
execution path. The interrupted functions are `func_8001F8B8` in 12 calls,
`func_80020050` in six, and `OuterProduct10` and `func_8001ECFC` in one each.
These are locations within existing calls, not additional game features.

## Timing remains underdetermined

In the branch-delay case, a separate observer retains the complete bounded
functional PC sequence. Its 192 delay-slot occurrences include **144 taken
branches and 48 fallthroughs**. The captured taken bit is compatible with 144
occurrences. Flipping that bit in a copied analysis record leaves 48 other
compatible occurrences. This ambiguity is preserved; it is not presented as a
detected fault or a uniquely identified interrupt cycle.

The observer retains at most 16 detailed PC windows per call while counting
every occurrence and branch outcome. Register jumps in a delay context are
explicitly unreviewed. A compatible path does not identify the interrupt
device, native cache entry, pipeline state, or the actual cycle of delivery.

The RAM differences also extend beyond low kernel memory. Every affected
call has **15–142 differing bytes at RAM offsets at or above `0x10000`**;
all 20 touch the word at `0x8006D358`. The private write catalogue retains
every changed word and nearby linker labels. A nearby label is a locator,
not established memory ownership or proof that a particular handler ran.
Ignoring low kernel memory alone would not reproduce these states.

## Reproduce with qualified local recordings

The existing [functional replayer](NATURAL_COLLISION_REPLAY.md) adds an opt-in
flag; its full RAM, 35 exposed CPU words, 64 GTE views and instruction-count
comparisons remain unchanged:

```sh
python tools/replay_collision_calls.py \
  --collection /private/hull-collection/collection.json \
  --bridge /private/gte-bridge.exe \
  --runtime 'D:/Private/BizHawk-2.11.1' \
  --lab-root /private/artifacts \
  --output /private/artifacts/hull-exception-new \
  --trace-exceptions
```

Normal capture qualification still applies. For the archived local evidence,
the executed investigation verified four complete XZ streams before replay
and read their RAM in memory. It did not expand the captures or record another
route. Existing sealed archives should be reused, rather than regenerating
historical recordings.

The two diagnostic studies retain byte-identical GTE request/result streams.
Their complete host logs differ in one `MemoryBlock` startup line; that byte
inequality and both original logs remain preserved. No log lines are normalized.

An ordinary/observed control preserves complete RAM, exposed CPU/GTE values
and instruction counts. A separate PC observer checks the complete branch
window totals. Copied-record controls reject incompatible CE, K0, exception
code, unvisited EPC and CPU-source provenance. The valid alternative branch
context remains explicitly underdetermined. Original records and instructions
are unchanged.

## Remaining work

Recover the original interrupt/callback execution and device-event evidence
needed for cross-frame replay; a register explanation cannot replace it.
Continue the two matching C reconstructions and require complete executable
equality before promotion. Other routes, content ownership, complete NPC
encounters, opaque state and original-hardware timing remain open.

This extends existing developer analysis tooling. Original NPC behavior,
optional mods, AI-assisted tools and the Bevy port retain separate counts.
No model API is called and no gameplay modification is added.

[Validation metadata](collision-exception-checks.json) binds the source,
retained comparisons, independent observer and unchanged game counts.
