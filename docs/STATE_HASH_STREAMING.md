# Streaming emulator-state hashes

The progression recorder now hashes serialized emulator states as the core
writes them. It no longer retains a growing `MemoryStream` and a second complete
`ToArray()` copy for each hash. The two same-frame serializations, complete
SHA-256 comparison and frame-counter check remain in place. The stream also
rejects a state above 256 MiB while it is being written, before accepting the
excess bytes.

This changes research tooling only. Matching game C remains **197,172 / 199,912
bytes (98.6294%)**, with two assembly functions and three inherited storage
explanations outstanding. It accepts no original-game feature, NPC encounter,
year boundary or ending. [Evidence and source pins](state-hash-streaming-checks.json)
record the scope separately from the frozen feature snapshots.

## Native compatibility

Two integrated Nymashock checks each perform 20 serializations at frames 0, 1,
60 and 300. Each checkpoint compares the earlier buffered hash with two direct
streamed hashes and the actual progression wrapper, which serializes twice.
The first check invokes `YearProgression.StateHash`; the second invokes the
separately derived ending producer's same method. Hashes and byte counts agree,
and complete MainRAM, GPURAM and the core frame counter remain unchanged.

| Core frame | Serialized bytes | Previous state arrays: capacity plus copy |
| ---: | ---: | ---: |
| 0 | 127,067 | 364,999 |
| 1 | 270,427 | 746,291 |
| 60 | 749,659 | 1,701,387 |
| 300 | 1,822,811 | 3,726,267 |

The new sink retains one byte for `WriteByte`, its digest and the hash
provider's internal state. The core, `BinaryWriter` and runtime can allocate
their own memory; this is not a constant-memory claim about the whole emulator.
Resource observations now report process working set, private bytes, handle
count, managed heap size and the last serialized-state byte count in
`progress.json`. They do not change controller decisions or game memory.

Both checks reuse the existing managed runtime, initialized-media native core,
original Japanese disc and BIOS files. No state is loaded, no game RAM is
injected, and no player UI is controlled. The terminal process receipts record
successful exits. These short checks do not exercise the 365-day route.

## Earlier year-run failure

The preserved October 19 year verifier stopped after day 153, at input frame
2,831,400, with a Windows insufficient-system-resources `IOException` during a
disc-sector read. Its logs contain no historical memory or handle measurements.
The cause remains unestablished. Removing avoidable serialization copies is a
bounded improvement; it is not evidence that the disc-read failure is fixed.

The old source, logs and failed output remain unchanged. A new private ending
producer incorporates the streaming method and telemetry while retaining its
controller policy and state-reading methods exactly. The integrated check
qualifies that method, without restarting the full-year run or altering the
earlier [seven-day pilot](NATURAL_PROGRESSION.md), including its nine failed
cross-run complete-state comparisons.

## Sources and checks

- [BoundedSha256Stream.cs](../research/headless/BoundedSha256Stream.cs) implements
  the forward-only bounded sink.
- [RecordProgressionHistory.cs](../research/headless/RecordProgressionHistory.cs)
  uses it in the progression producer. Compile it with `BoundedSha256Stream.cs`
  and the existing `ReplayColdStart.cs` host definitions.
- [StateHashCompatibility.cs](../research/headless/StateHashCompatibility.cs)
  contains the native comparison, including the old buffered reference. Compile
  all four sources with the existing BizHawk/.NET Framework references and choose
  `Lsd.Research.Headless.StateHashCompatibility` as the entry point. Its arguments
  are managed-runtime directory, existing native-DLL directory, cue, Japanese,
  US and European BIOS paths, and a new private output directory. An optional
  final fully qualified type name selects another compiled progression producer.
  Run it in an owned, supervised host using the limits in the evidence file.
- [The data-free tests](../tests/test_streamed_state_hashes.py) compile the actual
  sink and [fixture](../research/headless/HashStreamChecks.cs) with an already
  installed .NET SDK and reference packs. They compare against independent
  Python SHA-256 expectations, including a 64 MiB stream, invalid writes, byte
  limits, finalization and disposal. They install or restore no dependencies.

Run the data-free checks with
`python -B -m unittest tests.test_streamed_state_hashes -v`. They skip explicitly
when no suitable SDK/reference pack is installed; the native checks require
separate local game, BIOS and emulator inputs.
