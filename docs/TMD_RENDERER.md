# Original TMD draw-entry profile

The original 3,816-byte drawer at `0x80018464` agrees with scalar predictions
in **884 constructed calls**. Unlike the earlier projection-only profile,
these calls execute original vertex loading, coordinate writing, normal/color
processing, UV copying, fog-dependent palette adjustment and ordering-table
submission together. No function result is stubbed.

This remains a bounded renderer profile. It supplies one linked primitive per
call, camera/light state and output storage. Recursive clipping, replacement
matrices, multiple-primitive runs, the disc-model corpus, GPU pixels, natural
scenes and PS1 timing still need wider verification. It adds **zero** game C
bytes, gameplay features, whole-feature acceptances or whole NPC encounters.
Matching game C remains **199,912 / 199,912 bytes**.

## Executed evidence

| Check | Result |
| --- | ---: |
| Complete original draw-entry calls | 884 |
| Packets submitted | 624 |
| Fog/depth-cue rejections | 208 |
| Backface/degenerate returns | 26 |
| Hidden-object returns | 13 |
| Empty-geometry returns | 13 |
| Original instructions, including called helpers | 410,977 |
| Actual native GTE commands in those calls | 3,444 |
| Original-code output faults detected | 4 |
| Literal partial-transfer programs | 32 |
| Forbidden partial transfers rejected without memory changes | 32 |
| Stateful native GTE cases, including DPCT | 3,333 |
| Qualified command opcodes | 12 |

The [draw report](tmd-renderer-checks.json) and
[extended GTE report](gte-packet-state-checks.json) pin the actual sources,
original function hash, analysis backend, compiled bridge and private journal
hashes. Journals remain outside commits under the contribution policy.

The format/flag pairs are `20/00`, `20/04`, `21/01`, `24/00`, `25/01`,
`28/00`, `29/01`, `2c/00`, `2d/01`, `31/01`, `35/01`, `39/01` and
`3d/01` (hexadecimal). Each has transparency-bit variants, physical/KSEG0
pointer aliases, four object-attribute/light-mode combinations and four fog
values. Separate fixtures exercise hidden, empty, backface and degenerate
returns. These are supported branches of this particular drawer, not every
TMD encoding or every rendering path in the game.

## Comparison boundary

Unicorn executes the original integer instructions. COP2 words retain the
earlier profile's explicit transport to actual native GTE transfers and
commands. The already adapted projection helper is preserved when the rest
of the draw cluster is adapted; processing its transport words again would
discard their original COP2 identities. A failed private probe caught that
overlap before renderer results were accepted.

The scalar oracle constructs expected packet fields and buffer mutations
without executing the original MIPS. Register arithmetic uses the separately
native-qualified integer GTE model. The native host still uses reviewed host
code for inlined CR transfers and architectural reads; it calls actual native
initialization, power, data writes and commands. This establishes agreement
with the pinned emulator core, rather than independent PS1 hardware accuracy.

Every successful call compares complete GPU, ordering-table, 4 KiB scratchpad,
triangle/quad clipping-storage and fixed-global buffers. All 64 GTE register
words, command order and native command/data-write counters agree. Scratchpad
pointers use the original `0x1f800000` address and its KSEG0 alias. SP, GP, RA
and saved S/FP registers are checked. All 2 MiB VM bytes outside declared
mutable spans are hashed; callee stack temporaries inside the bounded frame
are permitted writes and are **not** independently byte-predicted.

Partial MIPS loads/stores use conservative aligned-word address guards.
Game-free fixtures execute LWL, LWR, SWL and SWR at all four byte offsets,
both normally and in branch delay slots. Literal register and complete-VM
results agree; all 32 corresponding forbidden-access controls leave memory
unchanged. Instruction guards preflight delay slots, preserving the earlier
Unicorn memory-hook workaround.

Four private original-instruction mutations change packet length, the raw
texture flag, the bounding-box endpoint and the OT link mask. Every mutation
returns with saved-register/immutable-VM guards intact, retains the predicted
GTE state and counters, and produces a detected buffer disagreement. These
are executed controls, not hypothetical checks.

## Preserved original behavior

The bounding-box helper at `0x8001a268` seeds its bounds from the first
projected vertex and loops up to an endpoint that excludes the final supplied
vertex. For the literal triangle with projected coordinates `(-8,-8)`,
`(8,-8)`, `(-8,8)`, its bounds are `(-8,-8,8,-8)`. The oracle preserves that
loop bound. Changing it to include the final vertex is one of the detected
controls; no game-source fix is made.

DPCT consumes three FIFO colors while retaining RGB's CODE byte and the
architectural RGB register. The extended native qualification adds 128
shift/limit/random-state cases to the prior 3,205. All 3,333 pass, alongside
the four existing native-boundary fault controls. The pinned
[Mednafen source](https://github.com/TASEmulators/mednafen/blob/382ff1b8d293c9a862497706808cbb79b2cecbfb/src/psx/gte.cpp)
is the implementation reference; hardware timing remains a separate gate.

## Reproduce

Reuse the existing optional Unicorn 2.1.4 environment and BizHawk 2.11.1
installation. Compile a fresh analysis host containing DPCT support; the old
eleven-command host deliberately rejects that command.

```powershell
./tools/build_nymashock_gte_state_bridge.ps1 -EmulatorRoot "D:/tools/BizHawk-2.11.1" -Netstandard "C:/Windows/Microsoft.NET/assembly/GAC_MSIL/netstandard/v4.0_2.0.0.0__cc7b13ffcd2ddd51/netstandard.dll" -Output .decomp-lab/gte-packets.exe
python -B tools/verify_gte_state.py --bridge .decomp-lab/gte-packets.exe --runtime "D:/tools/BizHawk-2.11.1" --include-dpct --output .decomp-lab/gte-packet-state
python -B tools/verify_tmd_renderer.py --executable rom/SLPS_015.56 --bridge .decomp-lab/gte-packets.exe --runtime "D:/tools/BizHawk-2.11.1" --output .decomp-lab/tmd-draw
python -B -m unittest tests.test_gte_state_model tests.test_tmd_renderer_model -v
```

Choose new output paths. The draw profile has a 15-minute ceiling, 50,000
instructions per call and a 2 MiB retained-output bound. The Windows host can
be called from the existing WSL environment using a Windows-readable runtime
path. It loads no game or BIOS and does not attach to the player or the
separate year replay. CI runs literal arithmetic and synthetic partial-transfer
fixtures without game assets; it does not rerun the private native profiles.

Original NPC behavior and optional AI-assisted analysis/modding remain
separate. These tools make no model API calls or gameplay changes.
