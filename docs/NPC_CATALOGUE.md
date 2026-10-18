# Original NPC callback catalogue

The [exporter](../tools/export_npc_catalogue.py) produces a checked inventory
of all **107 original NPC callback functions**, including their complete code
ranges, hashes and entity-table bindings. The
[published catalogue](../research/headless/npc-callback-catalogue.json) contains
metadata only. Its names are recovered source labels.

This supplies a common target inventory for native observers and human or
AI-assisted analysis. The [history recorder](NPC_ENTRY_TRACE.md) preserves
its selected-PC trace, and the optional [catalogue mode](NPC_CATALOGUE_TRACE.md)
records the complete target set in a second log. Creating a catalogue
executes no game callback and changes no original NPC behavior.

## Verified coverage

| Static inventory | Count |
| --- | ---: |
| Original entity property records | 130 |
| Nonnull callback slots | 111 |
| Null callback slots | 19 |
| Distinct callback functions | 107 |
| Complete callback code bytes | 29,232 |

Several entity records share one callback. Slot counts, function counts and
code bytes therefore describe different parts of the same original game;
none is an exhaustive gameplay-feature count.

For every callback, the catalogue records its original PC, entity IDs,
actual function length, full-function SHA-256, entry-instruction SHA-256 and
ELF section. The exported JSON contains no instruction bytes or game assets.

The producer reuses the **306 current build objects** and performs a private
diagnostic link with symbol stripping removed. It compares the entire
505,856-byte allocated image with the canonical executable before inspecting
any callback. Compiler options and the standard build outputs stay unchanged.
This is a symbol-preserving relink, not a fresh C compilation.

The ELF parser requires an actual sized function symbol at each original
address. A separate GNU `nm -S` result must agree on every address and length.
Every complete function span must equal the canonical bytes. The exporter
rejects overlapping ranges and ambiguous PC names; it does not estimate an
extent from the next label or accept a matching entry instruction alone.

The existing entity audit independently compares the full property table and
callback bindings against the C initializer. Source files, cached objects,
linker scripts, executables and native tools are hashed before and after the
export. The main build must remain current throughout.

## Reproduce

Use the [matching Linux/WSL toolchain](../README.md#build-the-matching-executable)
and a current canonical build. Run from the repository root:

```bash
ninja check
python tools/export_npc_catalogue.py \
  --output .decomp-lab/npc-catalogue-new
```

The output directory must be fresh and private. It retains `catalogue.json`,
the complete symbolic ELF, allocated executable, linker map, link log,
GNU symbols and provenance report. These local artifacts can contain the
original game and are excluded from Git.

Thirteen source-only tests use owned ELF/PS-X fixtures. They check changed
function tails, independent-symbol disagreement, missing/duplicate symbols,
stripped ELF, wrong PCs, ambiguous bindings, invalid IDs, overlapping ranges,
payload bounds and preservation of earlier evidence. They require no original
game inputs. The [evidence summary](npc-catalogue-checks.json) records the
actual full-game export and its separate raw-symbol audit.

## Scope and remaining work

The 29,232 bytes were already part of the recovered original NPC code; this
export adds **zero C bytes**. Matching C remains **197,172 / 199,912 bytes
(98.63%)**, with two game assembly functions and two inherited storage
explanations remaining. Original NPC callbacks with C bodies remain 107 / 107,
bounded callback profiles remain 40 / 107. At catalogue publication, compared
natural histories covered three callback types. The later
[catalogue observer](NPC_CATALOGUE_TRACE.md) brings that measure to five.
Whole-NPC and whole-feature acceptance remain zero.

Continue using this verified target set to record additional original callbacks,
retain complete runtime identity and output comparisons, and corroborate each
instance's registration, clock and activation history.
Natural encounters, branches, visible effects and timing still need evidence.
The [playable build](PLAYING.md), optional mods and separate Bevy port are
unchanged. The exporter invokes no model API and adds no AI behavior to the game.
