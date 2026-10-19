# Screen Run callback interfaces

The UI, main-menu and dream-chart tables declare their `0x44` Run callback
with its original three arguments and signed-word return. Previously the UI
view discarded the return type, and the main-menu and chart views declared
only a receiver. A contributor could not compile a typed call that consumed
the screen result. The original matching game already forwarded these values
through its separate common-screen view.

The corrected views take `(receiver, graphics_context, mode)`. The UI method
and common runner now forward the graphics context as a pointer. The
main-menu initializer uses the corrected callback type, and both obsolete
one-line UI-method declarations are removed. Existing table offsets and
original game behavior are preserved.

## Original bindings and result ownership

| Receiver table | Original Run slot | Original method |
| --- | --- | --- |
| UI screen | `0x8006E774` | `func_8003C1DC` |
| Main menu | `0x80086BA4` | `func_8003C1DC` |
| Dream chart | `0x80087AF0` | `func_80058390` |

`func_8003C1DC` forwards all three arguments through the original timer table,
then reads the result word at receiver offset `0x38`. The chart wrapper calls
that UI method, then returns 2 when its flag at `0x238` is nonzero; otherwise
it returns its result word at `0x38`. Both reads occur after initialization.
The original function extents and table prefixes are hash-qualified against
a complete unstripped ELF whose exported executable is canonical.

The three known `run_screen` calls in `game_flow_execute_main_menu` pass the
chart factory, main-menu factory and chart factory, respectively. Their
concrete Run bindings are the main-menu and chart entries above. This identifies those Run
targets; it does not close factory failure paths, destruction or every other
indirect call in the game.

## Verification

The exact [three-call consumer](../research/screen_run/consumer.c) failed with
three void-return diagnostics before this correction. It now compiles with
warnings treated as errors using the matching compiler. Eight target layout
assertions check pointer width, all four Run-slot views and both result/flag
offsets. The three complete caller bodies are independently extracted from
their linked ELF.

The [repeatable interface check](../research/screen_run/README.md) covers
**1,890 distinct initialized inputs**: 378 each for UI and main-menu views,
and 1,134 for the chart. Direct original methods and compiled callers perform
**3,780 positive executions**. It checks full guarded object buffers, all
three forwarded arguments, call order, return words and saved registers.
Three executed instruction faults each produce a wrong return. An independent
audit reconstructs the fixture/model digest and replays three positive fault
witnesses and three altered witnesses; these six executions are separate
from the positive campaign and add no new fixture inputs.

Graphics initialization (`func_8003E10C`) is **one explicit output contract**.
It checks its arguments, updates the supplied result and chart flag, clobbers
caller-saved registers and returns an unrelated V0. Its original body is not
executed. Natural initialization, factories, rendering, timing and full-screen
acceptance remain open. No model service is called.

The standard build and a fresh **306-object** build both reproduce the entire
505,856-byte canonical executable. [Validation metadata](screen-run-interface-checks.json)
records source hashes, original ranges, bounded results, the contract and
before/after counts. Matching C remains **196,504 / 199,912 bytes (98.30%)**,
with four assembly functions and two inherited storage explanations. Bounded
NPC profiles remain 39 / 107; whole-feature and whole-encounter acceptance
remain zero. The separate Bevy repository is unchanged.

The later [screen lifecycle profile](SCREEN_LIFECYCLE.md) executes the original
factories, runner, destructor and allocator together. It retains explicit
constructor, graphics-initializer and cleanup contracts; natural setup and
resource cleanup are still open. Its separate campaign and current source
counts are recorded in [lifecycle metadata](screen-lifecycle-checks.json).
