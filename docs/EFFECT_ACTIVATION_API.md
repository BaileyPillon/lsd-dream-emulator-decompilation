# Original effect activation interface

The original effect start methods forward four arguments: the effect, an
attachment target, a color variant and a mode. The activation method returns
the selected variant. Its former one-argument declaration required casts at
both start sites and concealed this interface from the C type checker.

The recovered declarations name and type these three original slots:

| Offset in `g_EFFECT_VTABLE` | Callback | Return type |
| --- | --- | --- |
| `0xD4` | `effect_start` | `void` |
| `0xD8` | `effect_start_attached` | `void` |
| `0xDC` | `effect_activate` | `s32` |

Each takes `(effect_t *, base_class_t *, s32, s32)`. Both activation callers
now use the typed slot directly. A forward struct tag keeps these declarations
compatible with the original GCC 2.6.3 compiler without repeated typedefs.

## Attachment target and callers

Entity offset `0x50` is now `base_class_t *m_EffectTarget`. The former integer
name, `m_EffectColor`, obscured an object pointer. The inherited scene-node
constructor clears this cache; `func_800570B4` stores an attached object there
when its type's low nibble is five, and the detach path clears it.

Five effect-start sites use that target: Airplane, both Gunman start modes,
Hidden Big Face Man and Gray Man. The activation routine forwards it to
`Attach(effect, target)`. The base implementation adds the target to the
effect's child list and calls the target's `AddParent` method. `Target` names
this verified argument without assuming a complete scene graph relationship.

The MIPS compiler checks the actual structure sizes and slot offsets:
`effect_t` is `0xA0` bytes, `entity_t` is `0x108`, the effect table is `0xF4`,
and the target remains at entity offset `0x50`. Two private declaration
regressions deliberately restore a one-argument activation slot or an integer
target. Both fail compilation with warnings treated as errors.

## Validation and remaining scope

[effect-activation-api-checks.json](effect-activation-api-checks.json) records
the before/after source identities, original slot bindings, compiler layout
checks, build comparisons, dispatch audit and bounded native replay.
The ordinary build and a complete clean rebuild retain the canonical
505,856-byte executable. Four game inputs change; the other 388 keep their
previous hashes.

The replay reuses the [Gunman campaign](GUNMAN_SCRIPTS.md): 36,338 standalone
fixtures and 15 scheduled histories containing 126 further invocations.
Twenty-six original routines execute; eleven measured instruction faults and
the separate pre-execution bounds control remain effective. These are existing
inputs rerun against the corrected source declarations. They add no distinct
original-game scenario or callback profile. Allocation/construction,
attachment, geometry, notification and sound retain the declared contracts.

Full natural attachment graphs, all four NPC encounters, effect lifetimes,
rendering/audio, controller reachability and PS1 timing still need comparison.
Static type recovery and a matching executable leave those runtime gates open.

Matching C remains **194,212 / 199,912 bytes (97.15%)**, with nine assembly
functions, 24 inherited storage explanations and 35 / 40 listed-core C groups.
Bounded NPC coverage stays **36 / 107**; whole-feature and whole-encounter
acceptance remain zero. The 40 provisional feature groups, ten developer
capability categories and three optional mods are unchanged. Original NPC
behavior, AI-assisted tooling and the separate Bevy port retain their existing
boundaries.
