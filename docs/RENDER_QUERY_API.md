# Render-position query interfaces

The render-position query chain now shares its existing 44-byte result record
through the header and uses accurate pointer signatures for three original
virtual methods. Regular and fresh clean builds reproduce the entire canonical
505,856-byte executable. This improves existing matching C; it adds no newly
decompiled assembly function.

## Original call contracts

The canonical `D_800866E8` table binds these methods:

| Slot | Function | Recovered interface |
| --- | --- | --- |
| `0x10C` | `func_8004C158` | Optional result buffer and optional position-pointer output; returns a cached result pointer or null |
| `0x110` | `func_8004C1C0` | Result buffer and optional three-word position; returns a status word |
| `0x114` | `func_8004C3F0` | Two-byte label output; returns the current object address as an integer word |

The wrapper writes the optional position-pointer output before resolving the
result. It returns the cached record at context offset `0xBC` when no result
buffer is requested or resolution succeeds, and null when resolution fails.
Its return value points into the context, rather than the caller's buffer.
The corrected resolver declaration removes an incompatible function-pointer
cast from this call chain.

Slot `0x114` calls `func_8004C368`, which writes two separate signed bytes.
Those bytes also form a signed halfword compared by the cached-position update
in `func_8004B5BC`. A two-byte union expresses both uses without adding storage.
The existing coordinate, transform, object and index fields retain their target
offsets; the complete record remains 44 bytes with four-byte alignment.

## Source layout and compiler allocation

`func_8004AEA4` now declares its query output with the shared result type. Its
distinct 48-byte saved builder record remains in use. `func_8004B5BC` also uses
the shared result, replacing a duplicate opaque type and giving the consumed
fields the same names as the resolver.

Two actual compiler traces observe `func_8004AEA4` in its complete translation
unit with the configured GCC 2.6.3 G8 flags:

| Source form | Saved builder | Query output requested / allocated | Complete function frame |
| --- | ---: | ---: | ---: |
| Previous source | 48 bytes | 48 / 48 bytes | 136 bytes |
| Shared query record | 48 bytes | 44 / 48 bytes | 136 bytes |

The compiler rounds the real query record to the required local extent. An
extra source tail is unnecessary. Each traced compilation produces the same
complete assembly as its own normal compilation, with the compiler and source
inputs preserved. This is a matching source representation, without a claim
that the original author used these exact type declarations.

## Validation and limits

A separate link retaining sized ELF symbols checks all seven complete affected
or dependent functions. Converting it back to a binary reproduces the canonical
image. Twenty-four assertions compiled for the target check record sizes,
alignment, field offsets and virtual-slot offsets; an intentionally incorrect
43-byte size assertion is rejected. Regular and fresh clean project builds also
match the original executable. Source, function and private-evidence hashes are
recorded in [render-query-api-checks.json](render-query-api-checks.json).

The earlier [position checks](RENDER_POSITION.md) remain bounded evidence for
the query chain. This cleanup adds no native replay, including no new replay
of slot `0x114`, and no gameplay or whole-feature acceptance.

The removed four-byte tail was outside the earlier
[selected storage audit](SOURCE_LAYOUT_EXPANDED.md). Its 24 unresolved inherited
functions remain. Before and after this change, C coverage is
194,212 / 199,912 bytes (97.15%), with nine assembly fallbacks, 35 / 40 listed-core
C groups and 24 / 107 bounded NPC callback profiles. Entire feature groups and
whole NPC encounters independently accepted remain zero. Original NPC behavior,
AI-assisted developer tools and optional mods retain separate accounting; the
Bevy repository is unchanged.
