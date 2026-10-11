# Original card cleanup with the native pool allocator

The cleanup routine `func_8004F810` now has a bounded check that executes its
original allocator and lock helpers, with **zero function-output stubs**.
It complements the earlier [cleanup contract audit](CARD_CLEANUP.md): that
audit retains its 501 original/candidate fixtures and explicit adversarial
allocator contract. This new profile uses valid, distinct owned allocations.
The profiles answer different questions and remain separate evidence.

Both the original cleanup and its private C candidate pass the new checks.
The candidate still differs from the canonical executable in eight
SP-relative bytes. Its source explanation remains unresolved; it is not
promoted, and the inherited dummy stack padding remains in the matching source.

## Observed scope

| Check | Result |
| --- | ---: |
| Original allocator component sequences | 96 |
| Cleanup fixture layouts per image | 180 |
| Cleanup executions per image, including repeated cleanup | 360 |
| Images checked | Original and private cleanup candidate |
| Scoped original functions | 7, totaling 1,176 bytes |
| Function-output stubs | 0 |
| Private fault controls detected | 3 / 3 |
| Synthetic tooling tests passing locally | 294 on Windows; 294 on Linux |

The seven pinned ranges are:

| Function | Address | Bytes |
| --- | --- | ---: |
| `memory_set_manager` | `0x80017A9C` | 12 |
| `memory_setup_manager` | `0x80017AC8` | 108 |
| `memory_allocate_mem` | `0x80017B34` | 456 |
| `memory_free_mem` | `0x80017CFC` | 428 |
| `memory_set_lock` | `0x8001844C` | 12 |
| `memory_is_locked` | `0x80018458` | 12 |
| `func_8004F810` | `0x8004F810` | 148 |

The allocator helpers were already recovered in matching C. These checks add
behavior evidence; they do not add C bytes or newly implemented game features.
[card-heap-checks.json](card-heap-checks.json) pins the producer, native ranges,
private reports, backend diagnostics and unchanged earlier records.

## Allocator and cleanup behavior

The independent [pool model](../tools/heap_model.py) represents an ordered
partition of allocated/free intervals and a free queue. It predicts first-fit
selection, four-byte request alignment, the twelve-byte minimum payload,
the sixteen-byte split threshold, neighboring-block coalescing, queue links,
free footers and the terminal header. It retains obsolete payload and footer
bytes, including intermediate unlink writes that remain inside a merged block.
This makes the comparison stricter than checking allocation return pointers.

Component sequences cover registered-manager preference, the explicit fallback
argument when the global manager is NULL, NULL and failed allocation, split
boundaries, scanning past an undersized queue head, and generated sequences
that free only live owned allocations. Physical, KSEG0 and KSEG1 pointer forms
are checked consistently. The pinned setter instructions identify the manager
and lock globals from their actual stores through `gp`.

Cleanup fixtures cover signed counts from `INT_MIN` through eight entries,
absent tables, NULL buffers/entries, two table-allocation orders, external and
pool-allocated owner objects, fragmented pools and bounded allocation failures.
The model releases the buffer, visited entries and table in the observed order,
then clears only the table field. Counts and the buffer field are retained.
When the table is absent, cleanup skips those releases; a supplied live buffer
can remain allocated. The fixtures preserve that behavior without claiming
that every constructed failure state occurs naturally in the game.

Every fixture checks repeated cleanup. A cleared or absent table makes the
second invocation inert, despite the retained buffer pointer. Any remaining
fixture allocations are released afterward by the analysis caller; that
teardown is recorded separately from what cleanup actually freed.

The [native verifier](../tools/verify_card_heap.py) compares every byte of the
guarded manager, pool and object buffers, both globals, release order and
original lock transitions. It restricts instruction execution to the seven
verified ranges and guards data accesses. Each host-issued call checks return,
stack, `gp`, saved registers and stack red zones. Between host calls it creates
a fresh CPU and verifies that the entire two-megabyte RAM image is preserved.
Inside cleanup, all nested allocator and lock calls execute uninterrupted on
one CPU; no helper output is supplied by the host.

Three private instruction faults are detected by complete-buffer mismatches:
a changed minimum payload, an omitted free-header flag, and an omitted table
release. Canonical inputs and game source remain unchanged.

## Run locally

A current complete canonical build and your own executable are required.
Use a separate environment for this qualified backend:

```bash
python3 -m venv .decomp-lab/card-heap-venv
.decomp-lab/card-heap-venv/bin/python -m pip install \
  -r requirements.txt -r requirements-card-heap.txt
.decomp-lab/card-heap-venv/bin/python tools/verify_card_heap.py \
  --output .decomp-lab/card-heap-new.json
```

An optional `--candidate` accepts a complete private executable whose changes
are confined to the 148-byte cleanup function. The checker rejects header,
other-function and length changes. A successful bounded comparison does not
accept the candidate as matching C. Reports refuse to replace existing files
and must remain inside `.decomp-lab`.

Synthetic model, profile and custody tests need no original inputs or Unicorn:

```bash
python -m unittest tests.test_heap_model tests.test_card_heap -v
```

## Backend evidence and remaining gates

This profile is qualified with isolated `unicorn==2.1.2`; its actual loaded
library and Python binding sources are fingerprinted. The existing
`requirements-analysis.txt` environment remains unchanged.

On this host, the stock 2.1.4 backend and a source build pinned to
[Unicorn commit 7c5db941](https://github.com/unicorn-engine/unicorn/tree/7c5db94191defc1e04a4f66f4eb1220903cba837)
raise a CPU exception in the small original allocator probe. Executing at the
linked KSEG0 addresses, changing the budget mechanism, or changing execution
hooks did not resolve the stock backend's failure. These are recorded tool
limitations; their root cause is not established. The MIPS-only source build
passed its MIPS test target. Generic memory/control test targets failed and
include excluded architectures, so a passing full upstream suite is not claimed.

The model's ownership checks define the analysis profile; they are not new
validation added to LSD. Invalid or duplicate frees, overflowing requests,
OS manager allocation/failure, concurrency, physical memory cards, natural
error-path reachability and PS1 CPU timing remain outside this proof.

The accepted source measure remains **194,884 / 199,912 game bytes in C**.
Six assembly functions and five known source-padding constructs remain.
Original NPC, optional-mod and developer-capability counts are unchanged.
The inventory still has 40 provisional groups, with **0 / 40 whole groups
independently accepted at runtime**. Broader card construction, I/O/error
scenarios and exact source-layout recovery remain completion requirements.
