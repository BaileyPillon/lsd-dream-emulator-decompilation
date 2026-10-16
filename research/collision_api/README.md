# Collision API verification

[`consumer.c`](consumer.c) is an analysis-only caller of the shared primitive
query declaration. The `LSD_COLLISION_LEGACY_DECLARATION` branch preserves the
previous declaration for a compiler diagnostic comparison. Neither branch is
linked into the game. [`abi_checks.h`](abi_checks.h) checks the target layouts.

[`verify.py`](verify.py) compiles both callers and compares the typed caller
with direct original execution and the independent collision model. It uses
the existing constructed collision domain and the checked native GTE bridge.
Four executed field-load faults must change a buffer or return value.

See [the interface record](../../docs/COLLISION_API.md) for reproduction,
counts, hashes and limits. This campaign adds no recovered C bytes, original
feature acceptance, NPC profile or gameplay replay. The primitive query's
assembly fallback remains in the matching build.
