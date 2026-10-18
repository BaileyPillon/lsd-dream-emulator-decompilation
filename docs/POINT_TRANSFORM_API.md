# Shared point-transform interface

`transform_local_to_world` now has one declaration shared by its definition,
the dream target-position query and link activation. Previously the definition
declared three arguments with an `s32 *` output, while both callers declared
four arguments with a `void *` output. Separate compilation hid that mismatch.

The declaration in [object_math.h](../src/base/object_math.h) expresses the
observed call contract:

```c
void transform_local_to_world(void *object, vec3d_t *world_point,
                              const void *local_point, s32 unused);
```

| Argument | Recovered role |
| --- | --- |
| `object` | Object supplying its transform through virtual-table offset `0x84` |
| `world_point` | Writable result containing three signed 32-bit coordinates |
| `local_point` | Borrowed input containing three signed 32-bit coordinates |
| `unused` | Fourth argument passed as zero by both original callers; unused by the body |

The input remains an opaque pointer because the original callers supply
interior pointers to different records. The output uses the existing
12-byte `vec3d_t`. No new buffer, padding or target compiler option is added.

The body still obtains the object's matrix, transforms one point through
`func_8001EE98` and adds the object's world position. Named `x`, `y` and `z`
output fields replace equivalent indexed word writes. Arithmetic, helper
calls, world-position reads and caller argument values retain their order.

## Qualification

Four isolated source comparisons qualified the ignored fourth parameter,
typed definition and two typed callers separately. Every linked complete
image matched the canonical 505,856-byte executable. The final shared-header
change also passes the ordinary build and a fresh, independently configured
306-object build.

The [check metadata](point-transform-api-checks.json) records source hashes,
the baseline revision and private build-report hashes. Private reports,
generated compiler output and original game inputs are not distributed.

This corrects the interface of an already recovered function. Matching C
remains 197,172 / 199,912 game-function bytes (98.63%), with two assembly
functions and two inherited unused-storage explanations still open. It adds
no NPC profile or whole-feature acceptance. Complete image equality qualifies
this source change; it does not establish exhaustive gameplay coverage.

## Reproduce

With the [matching toolchain](../README.md#build-the-matching-executable) and
your own canonical executable:

```bash
python configure.py
ninja check
python tools/progress.py --json
python -m unittest discover -s tests -v
```

For the independent build, use a separate clean checkout at the same revision,
install the same pinned toolchain and MASPSX revision, provide your executable
locally, and run the same commands without copying existing object files.
The expected executable SHA-256 is
`282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f`.

Original NPC behavior, optional analysis/modding tools and the
[Bevy/Rust port](https://github.com/BaileyPillon/lsd-dream-emulator-bevy)
retain their separate scope and progress measurements.
