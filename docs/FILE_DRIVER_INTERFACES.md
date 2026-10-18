# File-driver Open and Read interfaces

The shared file-buffer and debug-driver views now agree on the original
Open/Read calling interface. Previously the shared Read field returned
`void`, while both native implementations returned a signed word. The debug
view declared only a receiver for each method. A queued CD read compensated
with a function-pointer cast that also changed the length's signedness.

The corrected declarations are:

```c
void Open(struct file_buf *receiver, s32 resource, s32 mode, s32 flags);
s32 Read(struct file_buf *receiver, s32 destination, u32 bytes);
```

The destination remains the native signed address word, and the length is an
unsigned word. Read's return is a result word; this work does not interpret
it as bytes transferred. Existing game callers continue to ignore it. The
debug methods accept the forwarded words and ignore them, as before. No
instructions, vtable words, game behavior or assets change.

## Original dispatch

| Driver | Open slot `+0x44` | Read slot `+0x54` |
| --- | --- | --- |
| CD | `0x800272D0`, 432 bytes | `0x800276D0`, 304 bytes |
| Debug | `0x8002C3E0`, 16 bytes | `0x8002C408`, 8 bytes |

The original `file_driver_copy_vtable_slots` at `0x80026D88` copies indices
16–22 and 26–29 into resource tables, including Open and Read. The verifier
executes this routine for the common view and checks the entire guarded
destination against an independent slot-copy model. The debug-specific view
dispatches through its original table directly.

## Bounded verification

The [repeatable verifier](../research/file_driver/README.md) qualifies seven
complete original functions against the canonical executable and a matching
symbolic relink. Both independent ELF extraction and GNU sized symbols agree
on their extents. The four owned C callers compile with warnings treated as
errors; ten target layout/result assertions pass.

Each argument spans `0`, `1`, `0x7FFFFFFF`, `0x80000000` and `0xFFFFFFFF`.
The campaign covers **600 initialized cases** and **1,200 direct/typed method
runs**, plus **900 original slot-copy calls**. CD paths execute the original
lock and unlock 600 times each. It checks forwarded words, Read results,
call order, complete guarded objects/tables, lock transitions and preserved
registers/stack. Native writes outside the permitted stack, copied slots and
CD lock are rejected. No dependency-output stubs are used.

CD Open covers busy and already-open states; CD Read covers busy and closed
states. These guards avoid hardware I/O. Debug Open remains a no-op and Read
returns zero. Boundary values are not treated as valid disc paths or actual
destination buffers.

Five executed faults are detected: a wrong native return, wrong Read slot,
lost Read length, lost Open flags and omitted copied Read slot. Three negative
compiler controls reject void Read results in either view and a receiver-only
debug Open declaration. Nine source-only rejection tests run without game
files, the compiler or Unicorn.

The ordinary build and a fresh **306-object** build reproduce the complete
505,856-byte original executable. [Validation metadata](file-driver-interface-checks.json)
retains input/producer hashes and the bounded results. The static inventory
still contains 57 tables, 2,463 callback slots, 2,205 nonnull entries and 838
distinct targets.

Matching C remains **197,172 / 199,912 bytes (98.63%)**, with two assembly
functions and two inherited storage explanations open. In particular, the
64-byte empty frames in `debug_file_driver_unk15` and `debug_file_driver_open`
are not explained or credited by this correction. No full file-I/O, natural
history, disc/SDK error handling, hardware timing or whole-feature acceptance
is established. Whole-feature and whole-NPC acceptance remain zero; the
separate Bevy repository and the user's emulator session are unchanged.
