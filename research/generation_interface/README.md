# Generation structure interface observations

`inspect_objects.py` reads locally supplied, complete 2 MiB MainRAM captures.
It verifies the canonical executable and five captured code/table regions,
then reports the active generation list, receiver class, tick, mode, and
virtual update/position bindings. It executes no game code and changes no RAM.

```sh
python research/generation_interface/inspect_objects.py --ram /local/mainram-0.bin --ram /local/mainram-600.bin --output .decomp-lab/new-generation-observations.json
```

The default reference is `rom/SLPS_015.56`. Use `--reference` for another local
path to the same supported executable. The output must be a new file. Supply
captures in the order needed for your analysis; the script does not infer
their frame numbers, input history, or provenance.

The original dispatcher requires a nonnegative generation type and a positive
count. Disabled snapshots may retain a stale count or pointers; the observer
does not dereference that list. Enabled snapshots require receivers in mapped
MainRAM, within the identified 17-slot array boundary, using the original
generation class. Unknown receivers and changed code or tables fail explicitly.

These are bounded field observations. Advancing ticks alone do not trace
callback entry or establish natural construction, every mode, child lifetime,
rendering, audio, CPU timing, or complete generation parity. The observer has
no model/API dependency and is separate from original game behavior.

See [the interface recovery](../../docs/GENERATION_INTERFACE.md) for the
source corrections, original/linked comparison, and remaining compiler gap.
