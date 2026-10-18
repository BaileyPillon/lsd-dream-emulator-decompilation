# Original file-driver slot loads

The optional caller-context trace establishes the actual virtual loads behind
all **176 CD Open/Read entries** in one 6,000-input cold boot. This advances the
[entry-only evidence](DISPATCH_ENTRY_TRACE.md): an installed slot value alone
does not establish that a caller used it.

| Measure | Entry-only checkpoint | Caller-context checkpoint |
| --- | ---: | ---: |
| Compared CD Open/Read entries | 176 | 176 |
| Observed indirect source/target pairs | 10 | 10 |
| Qualified receiver/table/slot combinations | 0 | 36 |
| Qualified table/slot/target bindings | 0 | 12 |
| Qualified executed load paths | 0 | 11 |
| New matching C bytes | 0 | 0 |
| Whole feature groups accepted | 0 | 0 |

The 36 combinations distinguish receiver address, current table address, slot
offset and target. They are observations at these entries, not 36 separately
identified object lifetimes. Six table addresses appear. Ten call sites have
eleven paths because the TIM loader reaches one shared Read call from two
predecessors. Three entries use its original direct jump and delay slot;
nine reach that call through the linear path.

## Evidence required for a slot edge

The optional native header retains the sixteen preceding CPU-hook visits for
each selected method entry. Eleven explicitly selected code windows capture
before-instruction register operands, aligned RAM load addresses and words,
the RAM instruction word and the instruction selected by a read-only cache
peek. An unchanged CPU cache miss fetches the captured RAM word. The observer
does not call the timing-changing instruction-fetch function itself.

The verifier requires all of the following in the captured path:

1. A canonical `LW +0` reads the receiver's actual table pointer.
2. A canonical `LW +0x44` or `LW +0x54` reads the observed method from that table.
3. The actual `JALR` target operand and return address agree with the method entry.
4. Both load-delay gaps, intervening register definitions, the original code
   words and the complete PC sequence agree. A shared-tail jump also needs its
   exact target and captured non-branching delay slot.
5. The loaded values agree with the receiver and table windows at entry.

Missing context, unsupported instructions, cache isolation, invalid RAM loads,
changed effective instructions, overflow and lost or repeated events fail the
check. Entry-only recordings retain their earlier zero accepted slot count.
Open/Read returns and per-request completion are outside this entry protocol.

The first caller-context cohort retained only the ten call-site windows. It
qualified 173 paths but missed three loads before the shared tail. Those
recordings and the failed inspection remain private evidence. The added
predecessor window and direct-jump checks qualify a fresh cohort; neither
missing records nor different game output is ignored.

## Runtime comparison

Three final-source cold boots use the distributed core with the original disc,
the separate flow core with that disc, and the same flow core with the rebuilt
disc. They use identical verified disc content, BIOS and 6,000 controller
inputs. The method hook arms at frame 900; the entire boot is compared.

Original/rebuilt entries and complete caller-context records agree byte for
byte. Stock/observer output and original/rebuilt output also agree on **6,001
GPU observations, 1,117 RAM hashes, 178 complete RAM/GPU/RGB checkpoints and
17,692,008 PCM bytes per run**. An independent audit checks the retained code,
loads and output bytes, decodes all 534 checkpoint PNGs, and detects sixteen
retained-data corruption controls. These controls do not execute altered
original game instructions.

The [frame-zero hook limitation](DISPATCH_ENTRY_TRACE.md#early-boot-control-and-remaining-requirements)
remains unresolved. This qualification applies to the recorded frame-900
profile; it does not establish universal observer transparency, complete
emulator-state equality or original hardware timing.

## Reproduce

Use the same pinned native checkout, verified cold-boot captures and 64-bit
Windows runtime as the [method-entry recorder](DISPATCH_ENTRY_TRACE.md).
Build a fresh, separate core in Linux/WSL:

```bash
python tools/build_dispatch_observer.py \
  --source-root /path/to/pinned-native-source \
  --output .decomp-lab/flow-observer-new --flow
```

This compiles one new adapter and relinks the qualified cached native objects.
It preserves the supplied CPU source, native checkout and existing runtime;
it is not a fresh full-core rebuild. Omitting `--flow` retains entry-only mode.
The build profile remains `runtime_verified: false`; runtime comparisons are
separate evidence.

Record a new original and rebuilt workspace, then a new original workspace
without `--observer-profile` for the distributed comparison:

```powershell
python tools/record_dispatch_history.py `
  --capture-folder D:/private/original-cold-start `
  --workspace D:/private/flow-original-new `
  --program research/headless/file-driver-flow-route.json `
  --observer-profile .decomp-lab/flow-observer-new/profile.json

python tools/inspect_dispatch_history.py `
  --reference D:/private/flow-original-new `
  --candidate D:/private/flow-rebuilt-new `
  --output .decomp-lab/flow-paired-new.json

python tools/inspect_dispatch_history.py `
  --reference D:/private/flow-stock-new `
  --candidate D:/private/flow-original-new --mode observer-output `
  --output .decomp-lab/flow-stock-new.json
```

The extension uses protocol 1, 664-byte flow events and sixteen instruction
contexts per entry. It retains the existing 4,356-byte complete-method events.
There are at most sixteen selected call/context windows and 1,024 entries per
frame. Missing flow data fails the extended mode; it never falls back to a
slot-value inference. Earlier entry-only captures remain inspectable through
their retained source and protocol identities.

## Remaining work

The later [return trace](DISPATCH_RETURNS.md) adds compared original returns
and synchronous destination data. This document retains the slot-load
checkpoint's original counts and remaining-work boundary below.

The later [compiler census](UNUSED_LOCAL_CENSUS.md) corrects the overall
inherited storage remainder to three by finding a missed CD-reader buffer.
The counts below retain this trace checkpoint's earlier selected-audit scope.

Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two assembly
functions and two inherited debug-frame explanations open. There are still
40 provisional feature groups, 38 with their listed core functions in C;
the exhaustive original feature denominator is unresolved. Whole-feature
and whole-NPC acceptance remain zero.

Returns, completed transfers, destination data, other file callbacks,
disc/error branches, the wider dispatch graph and all broader original-game
parity gates remain required. This is an analysis tool that calls no model
API. It adds no NPC or generative gameplay behavior. The matching playable
build and the separate Bevy repository retain their existing identities.

[Validation metadata](dispatch-slot-flow-checks.json) publishes source and
evidence hashes and the bounded counts. Full original code, game images,
raw flow observations and emulator captures remain private.
