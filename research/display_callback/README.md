# Display callback interface check

The game installs the signed-word-returning CD tick in the display's callback
field. The shared typedef now agrees across the field, setter, virtual setter
and invocation. The original display loop discards that result.

Use the configured matching Linux/WSL build and the pinned Unicorn 2.1.2
environment from `requirements-card-heap.txt`:

```bash
python research/display_callback/verify.py \
  --output .decomp-lab/display-callback-new
```

The checker requires a current canonical 306-object build and preserves a
fresh private report. Its full symbolic executable must match the original;
the ELF parser and GNU sized symbols must agree on five complete ranges.

Three owned C callers install, invoke and clear the callback through the actual
shared header, with warnings treated as errors. Twenty-five lock/memory-lock
cases execute the original setter, CD tick and memory-lock getter. The checker
compares pointer arguments, callback status, object/table/global ownership,
return boundaries, saved registers and stack guards, without output stubs.
Three executed instruction faults and three incorrect header variants must
fail. All modified instructions stay in isolated analysis memory.

The original display-loop load/call/result-overwrite relation is checked
statically. This fixture does not execute that loop, VSync, active CD phases,
SDK callbacks, natural frames or asynchronous disc completion. The other two
qualified ranges support static review and a negative control; they are not
new positive execution coverage. See [the evidence and limits](../../docs/DISPLAY_CD_CALLBACK.md).
