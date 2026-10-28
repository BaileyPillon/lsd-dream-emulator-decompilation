# Original sound inspection

These read-only developer tools require owned game inputs. They execute original
machine code in bounded RAM contexts; they do not modify a live emulator, save,
disc or game executable. The [audit](../../docs/SOUND_ASSETS.md) distinguishes
file structure, SDK access, original selection and audible playback.

## File structures and disc provenance

```sh
python -B tools/inventory_sound.py \
  --layout /private/extraction/disc.xml \
  --edition-label "My verified reference" \
  --output .decomp-lab/sound-new.json

python -B research/sound_assets/qualify_disc.py \
  --layout /private/extraction/disc.xml \
  --disc /private/original.bin \
  --expected-disc-sha256 COMPLETE_RAW_DISC_SHA256 \
  --output .decomp-lab/sound-disc-new.json
```

The disc reader independently walks ISO directories and compares every audio
path, extent and byte. It streams whole-disc hashes and does not write extracted
payloads. Exit 0 qualifies those identities; exit 2 rejects an input or existing
report. The supplied expected hash and edition label require separate provenance.
This tool does not authenticate a commercial edition from its filename.

## Original native routines

Use the repository's existing Linux/WSL build environment, GNU MIPS tools and
pinned Unicorn 2.1.4. Reuse an existing qualified unstripped matching ELF and one
retained complete RAM capture. These commands do not compile or link an ELF.
If no qualified ELF exists, a one-time
`python -B tools/export_dispatch_catalogue.py --output .decomp-lab/dispatch-new`
retains `candidate-symbols.elf` while verifying the complete matching image.
Reuse it thereafter; keep copyrighted data private and respect storage limits.

```sh
python -B research/sound_assets/verify.py \
  --layout /private/extraction/disc.xml \
  --elf /private/qualified/candidate-symbols.elf \
  --ram /private/recorded/mainram.bin \
  --ram-sha256 COMPLETE_RAM_SHA256 \
  --output .decomp-lab/sound-native-new.json

python -B research/sound_assets/selection.py \
  --layout /private/extraction/disc.xml \
  --elf /private/qualified/candidate-symbols.elf \
  --output .decomp-lab/sound-selection-new.json
```

For sealed RAM, replace the raw `--ram` path with its existing TAR archive and
add `--ram-member EXACT_MEMBER_NAME --archive-sha256 COMPLETE_ARCHIVE_SHA256`.
The reader verifies both complete hashes, accepts one exact regular 2 MiB member,
rejects duplicate/link/truncated targets, bounds archive expansion, and reads it
in memory. Capture origin and launch-input qualification remain separate.

The metadata command returns 1 when an original initializer fails or traps;
it preserves that observation as a review item. The selector command returns
0 only after its bounded path/RNG checks and executed faults pass. Both return
2 for invalid input or an existing output. No exit code accepts whole-game or
audio parity. Each command needs a fresh report path.

The metadata campaign models the complete VH bookkeeping and complete getter
RAM effects, executes three instruction faults, and preserves one original
zero-tempo exception plus its private tempo control. The selector campaign
executes original RNG and path routines across 420 cases, checks stored-choice
history, and rejects two executed guard faults. It performs no audio transfer.

```sh
python -B -m unittest tests.test_inventory_sound -v
```

Synthetic tests cover sparse program IDs, sample extents, encoded events,
original zero headers, path bounds, raw-sector/ISO identity failures, complete
RAM archive identity, and report preservation. Real-disc and original-function
evidence is recorded separately in
[sound-asset-checks.json](../../docs/sound-asset-checks.json); synthetic tests do
not establish original-game parity.
