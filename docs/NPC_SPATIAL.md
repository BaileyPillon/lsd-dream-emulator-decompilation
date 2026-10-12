# Original NPC spatial composition

Seven original callbacks pass **26,194 composed fixtures** through their actual
scale, rotation, translation and axis/world helpers. The run executes 22
distinct original routines and 149,580 native GTE commands. Four private faults
are detected: wrong scale destination, wrong translation destination, wrong
nudge halfword and wrong GTE shift command.

The preceding [callback profile](SCRIPTED_EXTENSION.md) records abstract
requests under explicit spatial contracts. This separate profile executes
those dependencies for Elephant, Giant Fish, Small Elephant, Bird, Rocket,
UFO and Fish. The only function-output contract retained in this profile is
the Bird's trigger ratio. Existing profiles and their scopes remain frozen;
no additional callback or whole feature is accepted.

## Executed path and observations

Original scaling calls the packed-fraction helper and updates all three pose
scale words. Original rotation converts the same fractional representation
into angle units and preserves signed remainder behavior. Translation updates
the coordinate's three position words and invalidates its cached matrix.

Forward, vertical and virtual slot `0xC8` requests execute their original local
axis wrappers, temporary-vector writer, local-to-world transform, `RotMatrix`
and `ApplyMatrixLV`, then the original translation. The composition establishes
slot `0xC8` as the local-X path in these fixtures. The original nudge write
updates the entity's low halfword at `0x48`; checking only the requested
movement amount would have missed that state change.

The checker compares every byte of the entity, dream-system, command,
linked-child, coordinate and pose buffers. It also checks ordered remaining
contract calls, RNG seed, return completion, stack restoration, saved registers
and every GTE command result. Input/unused guard bytes remain in the comparison.

The base cases include every nonnegative tick of the Fish's 24,000-tick joint
cycle plus the signed boundaries retained by the earlier profile. Added cases
start with quarter turns, mixed angles and signed angle extremes, different
scales and signed-word position boundaries. These compare actual world-space
displacements, fixed-point rounding, narrowing and wrap behavior.

The hardware adapter follows the [verified native GTE workflow](RENDER_GTE.md):
ordinary original MIPS instructions execute in Unicorn, reviewed COP2 transfers
connect them to the pinned Nymashock command implementation, and an independent
integer model checks each result. No original spatial helper's output is
substituted. This is arithmetic composition, not original PS1 CPU scheduling.

## Reproduce

Build a fresh local bridge with `tools/build_nymashock_gte_bridge.ps1` as
documented in [the GTE audit](RENDER_GTE.md). With a current canonical build and
the optional analysis dependencies, run in WSL:

```bash
python tools/verify_npc_spatial.py \
  --output .decomp-lab/npc-spatial-new.json \
  --bridge .decomp-lab/my-gte-bridge.exe \
  --runtime 'D:/Tools/BizHawk-2.11.1'
```

Use forward slashes for the Windows runtime argument through WSL. Reports and
logs require fresh private paths. Source/build/range identities, the loaded
Unicorn library/binding and bridge executable are checked during verification.
[npc-spatial-checks.json](npc-spatial-checks.json) pins the qualified current
run, producer, tests, original ranges, bridge identities and explicit limits.

Eight synthetic checks cover scale replacement, the correct translation
record, local-to-world axes, accumulated movements, signed wrapping, guard
preservation, executed-versus-contracted operations and complete phase coverage.
All 332 developer tests pass locally on Windows and Linux.

## Remaining acceptance work

Bounded callback coverage stays at 16 / 107. The 26,194 spatial fixtures are a
separate composition profile, rather than additions to the older 31,358 abstract
callback fixtures or new gameplay features. Original behavior is unchanged;
analysis makes no model API calls and optional mods remain separate.

Natural construction and encounters, persistent actor histories, collision
paths, the remaining callback dependencies, renderer/audio output and original
PS1 timing still need reviewed comparisons. Whole-callback and whole-feature
acceptance remain zero. The [source-layout correction](SOURCE_LAYOUT_EXPANDED.md)
also withdraws four padded C promotions: current source recovery is 97.15%,
with nine assembly functions and 24 inherited unused-storage explanations.
