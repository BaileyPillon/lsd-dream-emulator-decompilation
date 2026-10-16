# Matching input storage recovery

Six existing C functions now retain their original stack layouts through
consumed input references. Five unused eight-byte arrays and the spawn key's
fourteen-byte unused tail are removed: **54 declared bytes** in total. The
identified inherited storage remainder falls from **14 to 8**.

Their **1,796 function bytes already counted as C**. Matching C remains
**195,844 / 199,912 bytes (97.97%)**, with five game assembly functions still
requiring recovery. This source cleanup adds no game feature or runtime
acceptance. The original author's exact declarations remain unknown.

| Function | Function / frame bytes | Consumed input |
| --- | ---: | --- |
| `memory_card_wait_event` | 148 / 56 | Pointer to the event handle passed to `TestEvent` |
| `func_8004F810` | 148 / 40 | First buffer pointer passed to the allocator's release method |
| `func_8004FBE4` | 576 / 56 | The same release argument during terminal state cleanup |
| `func_8004564C` | 272 / 40 | Original movie viewport pointer |
| `graph_screen_setup_video_event` | 224 / 8 | Pointer to the recorded history cell being compared |
| `generate_initial_spawn` | 428 / 48 | Pointer to the signed two-byte lookup key |

Every new view contains one actual four-byte pointer, checked at compilation
and consumed by an existing read, allocation/release argument or viewport
access. The spawn key now contains only the two bytes its helper writes. Its
separate input reference supplies the real lookup read. No unused record field,
repeated identity-wrapper chain, physical register binding, volatile constraint,
instruction substitution or compiler-flag change is introduced.

## Compiler observations

Twelve complete translation-unit observations compare the original source,
removed-storage control and matching reconstruction for the four affected
units. Every ordinary compilation has identical complete assembly to its
instrumented compilation. The observer makes no explicit compiler-memory
rewrites, opcode substitutions or additional inferior function calls.

| Function | Reload request | Local area before / after | Reload pseudo |
| --- | ---: | ---: | ---: |
| Event poll | 4 bytes | 0 / 8 | 82 |
| Card buffer cleanup | 4 bytes | 0 / 8 | 76 |
| Card state cleanup | 4 bytes | 0 / 8 | 108 |
| Movie viewport | 4 bytes | 0 / 8 | 77 |
| Recorded event cell | 4 bytes | 0 / 8 | 90 |
| Spawn key read | 4 bytes | 2 / 16 | 98 |

Each request comes from `assign_stack_local`, called by `alter_reg` during
reload. The spawn function first allocates its two-byte key, then aligns and
allocates the pointer reload, ending at sixteen local bytes. Pseudo numbers
describe the observed compiler runs, rather than original source declarations.
Nested temporary/local reports for the old arrays describe the same storage
and are not counted twice.

The recorded-event predicate schedules its stack adjustment at offset twelve, in the
first branch's delay slot. Frame metadata therefore decodes actual stack
adjustments throughout the qualified function, without assuming its first
instruction allocates the frame.

## Complete function and executable evidence

Each readable translation unit reproduces the full original executable. An
unstripped diagnostic must reproduce the same complete image before its sized
function symbols are trusted. All six complete, relocated function spans then
match the original bytes at their original addresses.

The isolated card-state function has three relocation-byte differences. Its
complete translation-unit link has zero differences; these results remain
separate in the evidence. An isolated link's jump-table placement does not
invalidate a fully qualified complete-image match, nor does an isolated
function match replace the complete-image gate.

The combined ordinary build, fresh complete build, compiler traces and native
card cleanup regression are recorded in
[input-storage-recovery-checks.json](input-storage-recovery-checks.json).
Original executable/asset inputs, raw compiler output, diagnostic ELF files and
native buffers remain private. Earlier dated reports are retained.

To inspect current compiler allocation in the configured Linux/WSL environment
with GDB:

```bash
python research/collision/trace_compiler_stack.py \
  --source src/menu/card/memory_card.c \
  --output .decomp-lab/card-input-allocation-new
```

The native heap profile checks its existing constructed ownership inputs,
complete manager/pool/object buffers and executed controls. It does not accept
physical card operations, natural error/cancel histories, BIOS event timing,
movie playback, rendered graph history or natural spawn histories.

Two additional source studies retain failed matching gates: 41 renderer
comparisons and 15 collision-pointer comparisons produce no exact source match.
The original assembly fallbacks remain. Bounded NPC coverage stays **36 / 107**,
whole-feature acceptance stays **0 / 40**, and all requirements in the
[frozen objective](../PROJECT_OBJECTIVE.md) remain in force. Original game
behavior, AI-assisted analysis/modding and the separate Bevy port remain distinct.
