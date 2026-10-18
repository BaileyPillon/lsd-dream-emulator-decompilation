# CD driver declarations and read arguments

The CD driver now declares thirteen internal functions before their first use,
with the return and parameter types of their actual definitions. The blocking
reader also has a complete prototype, and its SDK request explicitly takes a
destination pointer. These are matching C source repairs: the complete original
executable is unchanged.

Previously, the compiler inferred `int` returns for functions that later
returned pointers or `void`. It also diagnosed a pointer passed to the SDK
request's incorrectly integer-typed destination. Forward declarations now
agree with the definitions; the original word-address interface makes its
conversion to a data pointer explicit at the read boundary.

| Measure | Before | After |
| --- | ---: | ---: |
| Ordinary compiler warnings in this C unit | 64 | 3 |
| Internal functions first called without a declaration | 13 | 0 |
| Complete executable bytes | 505,856 | 505,856 |
| Differing executable bytes | 0 | 0 |
| New recovered C bytes | 0 | 0 |
| Whole feature groups accepted | 0 | 0 |

The warning count uses the ordinary bundled compiler and its unchanged
`-Wall` options. The linker's separate RWX-segment warning is excluded. This
is a count for `src/file/cd_file_driver.c`, not a project-wide warning audit.

The three remaining warnings are retained:

- `request` may be used uninitialized in `cd_file_driver_unk26`;
- the frame-setup callback has an incompatible pointer-type diagnostic;
- the synchronous reader's inherited 2 KB `sector` array is unused.

They require further source and call-site investigation. No initialization,
callback cast or replacement storage is added to silence them. The array
remains one of the [three known storage explanations](UNUSED_LOCAL_CENSUS.md).
Removing compiler diagnostics is not an exhaustive source-quality certificate.

## Original argument roles

`cd_file_driver_read_sectors` takes a file receiver, destination pointer and
unsigned byte length, returning a signed status word. Its sector count remains
`bytes >> 11`. The SDK request retains its signed count and mode words, with a
pointer for the destination. Its original request, retry, polling and close
operations remain unchanged.

The [previous return trace](DISPATCH_RETURNS.md) separately recorded fourteen
natural synchronous requests and compared their complete buffers with the
disc. That evidence supports these argument roles; it is not recounted as new
runtime coverage here. A zero Read result remains a status word, not a count
of bytes transferred. Asynchronous completion and disc/SDK error acceptance
remain open.

## Validation and source study

Four isolated complete-unit builds cover the old declaration control, the
typed read boundary, the added forward declarations and the final source
candidate. All reproduce the canonical 505,856-byte executable. The promoted
source also passes an ordinary build and a fresh build with all 306 objects
absent beforehand. Only this C file changes among the 392 protected game-build
inputs; the other 391 retain their hashes. Compiler options, executable,
assets and the frozen objective retain their identities.

The existing file-driver check is repeated on the current build: 600 bounded
cases through original methods and compiled C callers, five executed fault
controls and three rejected header controls. Those are existing initialized
input domains, not new disc requests or natural histories. Both Windows and
Linux tooling suites pass 1,054 tests with two expected skips each.

The parallel hull-source investigation independently qualifies sixteen complete
function comparisons with GNU tools: twelve new two-word output-object forms
and four repeated controls. Four earlier forms rejected by the legacy C89
parser remain recorded separately. None matches; the best hull candidate
still differs by 26 executable bytes. No collision candidate is promoted.

A fresh upstream check pins the same commit,
`90a398e4f429b4371be05648605fc198b9efb395`. Its
[hull function](https://github.com/brian-oblivion/lsddecomp/blob/90a398e4f429b4371be05648605fc198b9efb395/src/graphics/scene_node.c)
retains an explicitly unused 24-byte array, and its
[primitive function](https://github.com/brian-oblivion/lsddecomp/blob/90a398e4f429b4371be05648605fc198b9efb395/src/graphics/tmd_model.c)
retains an unused vector and distance-array element. Its complete-decompilation
claim therefore does not close this project's padding-free source gates.
No additional upstream game source is imported by this change.

## Current boundary

Matching C remains **197,172 / 199,912 bytes (98.63%)**. The two collision
assembly functions and three inherited storage explanations remain open.
There are still 40 provisional feature groups, 38 with their listed core
functions in C, and zero whole-feature or whole-NPC acceptances. The exhaustive
original feature count is unknown.

The playable matching build and the separate Bevy port retain their existing
identities. This change adds no gameplay, NPC or AI behavior and calls no model
API. [Validation metadata](cd-driver-declarations-checks.json) records source,
build and evidence hashes; original game bytes and private captures remain
outside the repository.
