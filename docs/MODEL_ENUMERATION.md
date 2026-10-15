# Matching model enumeration interfaces

The model wrapper, part-list wrapper, and part wrapper now explicitly forward
the original output-buffer and index-record arguments through their native
virtual slots. Six C/header corrections retain the complete canonical executable
byte for byte. The five functions in the checked chain already had C bodies,
so this work adds **zero recovered C bytes**.

| Function | Original span | Role |
| --- | ---: | --- |
| `func_8004497C` | 60 bytes | Object-model wrapper; forwards both arguments to the part list |
| `func_800453DC` | 76 bytes | Part-list wrapper; selects the record stream after its animation table |
| `func_80043FB0` | 52 bytes | Part wrapper; selects the record stream at its fixed offset |
| `func_80043FE4` | 392 bytes | Enumerates type records and resolves or counts index records |
| `func_8004416C` | 56 bytes | Decodes the native type, kind, flag, and record-word count |

The independently qualified complete linked spans are pinned in
[the function inventory](model-enumeration-function-ranges.json). The original
vtable words and full executable, rather than recovered declarations alone,
establish these bindings.

## Native behavior

The bounded profile executes **1,584 owned fixtures** through all five actual
original functions, including **213,984 record-decoder visits**. No dependency
outputs are substituted. It checks three entry routes, eleven counts around
byte wrapping, six signed/full-word selectors, null output/index combinations,
and physical/cached pointer aliases.

The returned count wraps to a byte, while the output buffer still receives every
eligible type. A count of 256 can therefore return zero after writing 256 bytes.
Index selection compares the full input word with an unsigned 16-bit record
key. The output index occupies four bytes; the following twelve guarded bytes
remain intact. With a null output buffer, index records are counted instead.

Full receiver, record-library, output, and index buffers are compared. The
profile also checks saved registers, stack guards, forwarding at native entry,
and original table bindings. Two deliberately altered argument-forwarding
instructions are detected after their execution is measured.

## Run the profile

After a current matching build and installation of
`requirements-analysis.txt` in the Linux/WSL environment:

```bash
python tools/verify_model_enumeration.py \
  --output .decomp-lab/model-enumeration-new.json
```

The report requires a fresh private path. It records the original ranges,
backend identity, source-input hashes, case counts, entry counts, and fault
controls. It modifies no game files and calls no AI model.

These constructed receivers do not close natural construction, allocator/actor
lifetime, rendering, PS1 load-delay/timing, or complete feature acceptance.
C coverage remains **194,212 / 199,912 (97.15%)**, with nine game assembly
functions and 24 inherited storage explanations. Bounded NPC coverage remains
20 / 107; whole-feature acceptance remains 0 / 40 provisional groups.
