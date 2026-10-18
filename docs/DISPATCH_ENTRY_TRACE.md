# Original method-entry recording

The separate method observer records original CD Open and Read entries during
a fixed 6,000-input cold boot. Original and rebuilt recordings agree on all
**176 entries**: 64 Open and 112 Read observations at ten original `JALR`
source/destination pairs. The observed counts include queue processing and
are not counts of completed file transfers. The two watched debug methods
have no entries in this route.

Three fresh runs use the distributed core with the original disc, the method
core with the original disc, and that same method core with the rebuilt disc.
The qualified profile arms at relative frame **900**, before the first watched
entry at frame **967**. Comparisons cover the entire boot: **6,001 GPU
observations, 1,117 RAM hashes, 178 complete RAM/GPU/RGB checkpoints and
17,692,008 PCM bytes per run**. The original/rebuilt entry records also agree
word for word. A separate Pillow pass decodes all 534 PNGs and checks their
pixels against the retained raw RGB.

## What the observer records

Each event retains A0–A3, RA, SP, timestamp, the preceding two instruction
PCs/words and the complete loaded callee bytes at entry. All observed callee
bytes match their qualified original spans. Read has three arguments; its
captured A3 word is not interpreted as a fourth parameter. Return values and
per-request completion are outside this entry-only observation.

The observer also snapshots an eleven-word RAM window at A0, a 35-word RAM
window at its first word, and four explicitly selected original globals.
These are bounded raw windows, not inferred object/table extents. The current
profile records `g_CdFrameActive`, `g_CdFrameParam`, `g_CdReadBusy` and
`g_CdLocked`. Names are recovered analysis labels.

| Observed path | Open entries | Read entries |
| --- | ---: | ---: |
| Synchronous | 14 | 14 |
| Framed, queued | 25 | 49 |
| Framed, direct | 25 | 49 |

Six resource-table addresses appear in the receiver snapshots. At every entry,
their `+0x44` or `+0x54` word contains the observed CD method, differing from
that slot's static executable value. This supplies evidence of installed
driver methods. It does not prove a caller loaded a specific slot merely
because that slot contains the destination; accepted receiver/slot edges
remain zero pending the wider data-flow review.

The CD driver uses a raw `s32` table and is outside the 57 typed-table bindings
in the [declared dispatch catalogue](DISPATCH_CATALOGUE.md). Its Open/Read
ranges come from the separately qualified [file-driver interface evidence](FILE_DRIVER_INTERFACES.md).
The selector checks both provenance records and every selected full-function
hash. It retains their distinct sources rather than adding these methods to
the original 838-target catalogue.

## Reproduce

Build in the pinned Linux/WSL native checkout documented by the
[NPC entry setup](NPC_ENTRY_TRACE.md), with a fresh separate output directory:

```bash
python tools/build_dispatch_observer.py \
  --source-root /path/to/pinned-native-source \
  --output .decomp-lab/method-observer-new
```

The native build compiles one new adapter and relinks the qualified cached
objects. It preserves the supplied source, CPU code, existing core and
cached objects. Its build profile remains `runtime_verified: false`; the
separate runtime comparisons provide qualification for this controller profile.

Record from 64-bit Windows using your verified cold-boot capture's local
disc, BIOS and distributed runtime:

```powershell
python tools/record_dispatch_history.py `
  --capture-folder D:/private/original-cold-start `
  --workspace D:/private/method-original-new `
  --observer-profile .decomp-lab/method-observer-new/profile.json
```

Repeat for the rebuilt disc. Record the original again without
`--observer-profile` for the distributed-core comparison. Use a fresh
workspace each time; all program, compiler, host, core and source identities
are frozen alongside their copies.

```powershell
python tools/inspect_dispatch_history.py `
  --reference D:/private/method-original-new `
  --candidate D:/private/method-rebuilt-new `
  --output .decomp-lab/method-original-rebuilt-new.json

python tools/inspect_dispatch_history.py `
  --reference D:/private/method-stock-new `
  --candidate D:/private/method-original-new `
  --mode observer-output `
  --output .decomp-lab/method-stock-observer-new.json
```

The observer accepts at most 16 qualified functions of at most 4,096 bytes
each and 1,024 entries per frame. Overflow, lost native totals, inconsistent
transport layouts, changed complete code or changed retained inputs fail
verification. These analysis limits do not restrict the original game.
Original code windows and raw observations remain private.

## Early-boot control and remaining requirements

Activating this core's CPU hook at frame zero fails the strict stock RAM
comparison: the 6,000-input profile differs at its frame-216 RAM sample.
Three 300-input controls sample RAM every step and retain a complete
frame-216 checkpoint. Early activation changes RAM at frames 211, 215, 216,
218, 219 and 220, with seven differing bytes at the retained checkpoint;
the same method core armed at frame 300 matches the stock control throughout.
GPU and complete PCM agree in those controls. The precise CPU/BIOS cause
remains open. The failed recordings are retained, and no comparison tolerance
is relaxed. The frame-900 profile passes the full comparisons, including the
early-boot RAM observations.

The method core, recorder and build profile are separate from the NPC tools.
This is optional analysis tooling: it calls no model API, injects no game
RAM, restores no state and controls no user emulator window. It adds no
generative behavior or gameplay changes. The retained early-hook failure
also prevents a general claim that every observer activation is noninvasive.

[Validation metadata](dispatch-entry-trace-checks.json) records the source and
capture identities, comparisons, independent audit and corruption controls.
Matching C remains **197,172 / 199,912 bytes (98.63%)**. Both assembly functions
and both inherited debug-frame explanations remain open. Bounded NPC profiles
remain 40 / 107, compared natural callback types remain five, and whole-feature
and whole-NPC acceptance remain zero. Complete disc/error behavior, returns,
destinations, hardware timing and the broader gameplay requirements still
need evidence. The separate Bevy port and the user's running game are unchanged.
