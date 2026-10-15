# Typed render-position query result

`func_8004CC74` now uses the existing `func_8004C1C0_out_t` result record
instead of a second opaque buffer with an unused four-byte tail. The complete
505,856-byte executable still matches the canonical image. This improves an
existing C function; it recovers no additional assembly bytes.

## Record and call-chain evidence

The canonical render-context vtable binds slot `0x10C` to `func_8004C158`,
which calls the resolver at slot `0x110`, `func_8004C1C0`. The caller passes
its result buffer through that chain. The resolver's existing C definition
describes a 44-byte record whose last member is at offset `0x28`.

| Caller input | Record member | Offset |
| --- | --- | ---: |
| Local signed X cell | `dx` | `0x02` |
| Local signed Z cell | `dz` | `0x03` |
| Selected marker/index, currently named `divisor` | `divisor` | `0x28` |

The bounds predicate receives the address of `dx`, retaining its original
two-byte input representation. The neighbor-slot calculations use the same
signed word at `0x28`. The old `pad2` member at `0x2C` has no corresponding
resolver output and is removed with the redundant buffer type.

The earlier [position composition](RENDER_POSITION.md) already checks this
lookup chain, its canonical bindings and the complete guarded output record.
That bounded evidence is unchanged; this cleanup adds no native fixture or
whole-feature acceptance claim.

## Actual compiler allocation and complete build

Two fresh traces observe the bundled compiler's allocator calls for the
complete translation unit, using its normal G8 settings:

| Source form | Requested local bytes | Allocated local extent | Complete function frame |
| --- | ---: | ---: | ---: |
| Previous opaque buffer | 48 | 48 | 80 |
| Existing typed result | 44 | 48 | 80 |

The compiler rounds the real result record to the same local extent. No
source tail is needed to obtain that allocation. Each traced compilation
produces exactly the same complete assembly as its own normal compilation;
the traces preserve the compiler, producer, configuration and source inputs.

A separate link retaining sized ELF symbols confirms the entire 196-byte
`func_8004CC74` at `0x8004CC74`, including its 80-byte frame. Converting that
ELF back to a binary reproduces both the normal candidate image and the
canonical executable. The regular project build also matches the canonical
SHA-1 `76322eeade5ebb22dca57fdeac7d68c30f06308d`.

Source and evidence hashes are in
[render-query-record-checks.json](render-query-record-checks.json). Private
compiler traces and executable artifacts are excluded from the repository.
No compiler flags, physical-register bindings or assembly substitutions were
introduced. This establishes a cleaner matching source representation; it
does not establish the original author's exact type declaration.

## Progress accounting

This buffer was absent from the previous
[28-function storage audit](SOURCE_LAYOUT_EXPANDED.md). Finding and resolving
this additional redundant tail does not reduce that audit's 24 unresolved
inherited functions. That audit remains non-exhaustive.

Before and after this change, C coverage is 194,212 / 199,912 bytes (97.15%),
with nine assembly fallbacks, 35 / 40 listed-core C groups, 22 / 107 bounded
NPC callback profiles and zero independently accepted whole feature groups
or whole NPC encounters. Original NPC behavior, developer analysis tools and
optional mods retain their separate accounting. This is no additional
gameplay run, source-recovery percentage or Bevy-port change.
