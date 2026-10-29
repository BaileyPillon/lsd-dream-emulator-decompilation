# Original screen allocation and destruction

The original common runner passes its create argument to the selected factory,
calls the returned receiver's Run slot at `0x44` with `(receiver, graphics, 0)`,
then its Destroy slot at `0x04`. The Run result is saved before Destroy and
returned afterward. Both known factory families use `base_class_destructor`,
which calls Cleanup at `0x0C` and releases the receiver through the real pool
allocator.

The recorded campaign passes **2,052 input profiles**: 2,016 completed
lifecycles and 36 exhaustion cases. Fifteen original routines execute; the five
contracted bodies stay separate. Three executed instruction faults are rejected.
An independent audit checks all 20 complete function spans through GNU section
and symbol records, then checks every saved case, expected buffer hash, common
runner destination, table-word read and callee-entry argument record.

The [repeatable lifecycle profile](../research/screen_lifecycle/README.md)
extends the [typed Run checks](SCREEN_RUN_INTERFACES.md). It executes the
original factories and allocator together with the original runner, Run
wrappers, table getters and destructor. The expected final manager, pool and
opaque argument buffers are computed before execution and compared in full.
Callback arguments, order, heap-lock transitions, the one receiver release,
saved registers and stack guards are checked separately.

Screen construction, graphics initialization and resource cleanup remain
explicit contracts: two constructors, two cleanup bodies and one initializer.
Each contract's complete original function is qualified and recorded, but its
body is not executed. Cleanup changes the receiver's result word and returns
an unrelated value, so a successful run must preserve the earlier Run result.

Allocation boundaries include an exact block, an absorbed small tail, the
minimum split remainder, a roomy pool, and a pool four bytes too small. The
original exhausted factory returns zero. The original runner then attempts
`lw v0, 0(s0)` with a zero receiver at `0x80026540`, before a Run or Destroy
dispatch. The bounded checker stops at that access. This is evidence of an
unchecked path, not an accepted PS1 crash or recovery scenario and not a
behavior change to the matching game.

Native indirect-call destinations and actual table-word reads are retained
alongside each case. They bind the supplied main-menu and chart factory
contexts without turning every other indirect transfer or the common view's
undeclared inherited members into resolved semantics. U003 remains open.

The profile adds no recovered game C, original feature, NPC encounter or model
API call. Natural factories and cleanup, complete screen histories, rendering,
controller reachability, hardware timing and full failure continuation remain
required for whole-feature acceptance. The [validation metadata](screen-lifecycle-checks.json)
records the executed campaign and current before/after counts.

The later [destruction interface check](SCREEN_DESTROY_INTERFACE.md) corrects
the common view's pointer-returning Destroy callback and verifies three typed
consumers in 96 supported initialized profiles. Its separate source and
native checks preserve the canonical executable; the natural-screen and
contract boundaries above remain open.

The separate [resource cleanup check](SCREEN_RESOURCE_CLEANUP.md) executes
both original Cleanup bodies and their release dependencies in 144 supplied
owned graphs, without dependency output contracts. Its different inputs do
not remove this earlier profile's contracts or establish natural setup.

The subsequent [natural title-menu history](NATURAL_MENU_LIFETIMES.md) inspects
three recorded menu generations and two selected ownership closures. It reuses
retained RAM/GPU/RGB outputs and does not remove the contracts in this earlier
execution profile or accept an entire screen feature.
