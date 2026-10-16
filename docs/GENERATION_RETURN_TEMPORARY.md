# Generation method-return temporary investigation

> Historical rejected hypothesis: the later
> [matching lookup recovery](GENERATION_LOOKUP_RECOVERY.md) replaces the
> dispatcher with C using a scalar return from an initialized vtable snapshot.
> The observations and counts below describe this earlier candidate.

The consumed method-return candidate remains **eight bytes different** from the
canonical executable. New compiler observations explain why this hypothesis
reserves storage and keeps a store; they do not recover the original source
lifetime or justify promotion. The matching game still uses the original
136-byte assembly dispatcher.

## Actual compiler observations

The [published fragment](../research/source_layout/structure-update-method.c)
returns and consumes a one-field method record. The complete source unit was
observed with the bundled GCC 2.6.3 compiler and canonical flags. Normal and
observed complete assembly files agree byte for byte for each observation.

| Observation | Result |
| --- | --- |
| Temporary lifetime | 39 recorded events; a four-byte returned record requests temporary storage and advances the frame allocation by eight bytes |
| Memory-store decisions | Three observed decisions, zero classified dead; the stack store survives |
| Allocation | One local allocation, one equivalence update, three global allocations, and three priority comparisons |
| Complete candidate image | 505,856 bytes; differences remain at offsets 283,840–283,843 and 283,848–283,851 |

The fragment's 40-byte frame matches the original frame size, but it stores
the returned method at `sp + 0x10`. The original does not contain that store.
The candidate also passes the position earlier instead of in the call delay
slot. A matching frame size is therefore insufficient source evidence.

Fourteen further independently qualified source forms were checked: six ways
to consume returned values, three returned-member forms for the entry scanner,
and five nested-scope/accessor forms for the update. Their complete function
and text-section comparisons have no exact match. The initial malformed
nested-scope probe was rejected before qualification and is excluded from
those fourteen. The earlier sixteen forms remain a separate frozen checkpoint.

## Bounded native comparison

The same complete eight-byte-different image was then supplied to the
[generation verifier](../tools/verify_generation_structures.py). Original and
candidate each pass 3,116 standalone fixtures and 40 consecutive-update
histories containing 480 history frames. Fifteen original routines execute;
all nine negative controls are detected. There are no function-output stubs.

Those checks cover valid manually assembled objects in all four generation
modes, eight mode-zero rate variants, and four active child layouts. They
compare the graph buffers and recorded operation/RNG order. They do not compare
every stack byte or instruction timing, construct natural object lifetimes,
or establish complete gameplay. This is separate from the older ten-byte
scalar candidate's native campaign.

## Reproduction and remaining gate

Use the [source-layout guide](../research/source_layout/README.md) to insert
the fragment into a private complete unit and run the full executable gate.
The existing [memory-store observer](../research/compiler/trace_memory_stores.py),
[allocation observer](../research/compiler/trace_allocation.py), and
[lifetime observer](../research/collision/trace_compiler_lifetimes.py) retain
actual compiler decisions without changing the resulting assembly.

[generation-return-temporary-checks.json](generation-return-temporary-checks.json)
records source/compiler identities, private report hashes, qualified forms,
native scope, and unchanged before/after counts. Raw RTL and generated assembly
stay private. No padding, dead storage, hard registers, instruction edits, or
alternate optimization settings are accepted as a replacement for the source
explanation. Every [completion requirement](../PROJECT_OBJECTIVE.md) remains open
where its full evidence is not established.
