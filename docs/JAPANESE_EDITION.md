# Japanese disc verification

The October 11, 2026 supplement verifies a Japanese-labelled disc separately
from the earlier English v1 reference. The matching executable is unchanged:
505,856 bytes at LBA 24, SHA-1
`76322eeade5ebb22dca57fdeac7d68c30f06308d`. File counts and a successful replay
do not establish an exhaustive original feature inventory.

## Source and edition comparison

The source is the Japanese BIN/CUE identified by the
[Internet Archive item metadata](https://archive.org/metadata/lsddreamemulatorjapan).
The download matches its published size, SHA-1 and MD5. That provenance is not
independent authentication of an official pressing. Its 648,088,896-byte BIN has
SHA-1 `cd518b9de51e552dac0b952420bc493dcf5cfe43` and SHA-256
`cbf377af3e9207964f11044202eb5ecec2594a3c96e0919f7aa807d328654e61`.

The supplied CUE references a different BIN filename. The original CUE remains
preserved; a separate working CUE changes only that reference. The executable
was also read independently from the raw BIN before extraction.

Both freshly hashed extractions contain 683 files at identical paths and LBAs,
with the same data/mixed-sector classifications:

| Comparison | Files |
| --- | ---: |
| Identical payloads | 614 |
| Different standalone TIM images | 67 |
| Different STR records | 2 |
| Added, removed or relocated paths | 0 |

All 418 LBD files, 56 TIX containers, 70 SEQ sequences, nine VH headers, nine VB
banks, two MOM files, two TMD files and the executable agree. The changed STRs
are `/CDI/FILM/EVENT2.STR` and `/CDI/FILM/SPDAY06A.STR`. Their decoded content has
not been independently classified. The earlier English extraction still agrees
with its preserved inventory; its historical raw-disc evidence is unchanged.

Both editions have 14 stage directories and 445 populated-bank TIM records.
The texture inspector reports zero unresolved texture-bank records in each.
These counts describe selected native structures, not independently accepted
scenes or gameplay features.

`tools/inventory_disc.py` now defaults to the neutral edition label
`unspecified`. Supply `--edition-label` to record your input's provenance. A
canonical executable hash alone cannot identify translated assets.

## Complete disc reconstruction

The first MKPSXISO 2.30 reconstruction differed in eight bytes: the four-byte
EDC words in Mode2 Form2 sectors 112,583 and 181,199. Every other byte agreed.
The source words differ from MKPSXISO's regenerated words; this observation
does not explain the reason or certify their original validity.

`tools/package_disc.py` now retains a source EDC only when all preceding 2,348
sector bytes agree, the raw-sector sync and Mode2 marker are valid, both XA
subheaders agree and the Form2 flag is set. It leaves changed sector bodies,
Form1 ECC and invalid duplicate subheaders alone, and rejects writing into the
source image. Its manifest records each retained word.

The corrected reconstruction is **byte-identical across all 648,088,896 bytes**,
including both original EDC words. The executable remains canonical at LBA 24.
Synthetic controls check the guarded preservation behavior and source-image
protection. Original discs, extracted assets and rebuilt images remain private.

## Runtime scope

The recorded scenario runs 6,000 frames from the same frozen Japanese
publisher-logo state, with scripted Start/confirm and movement inputs. It
compares 100 trace samples and 13 image, full GPU-memory and saved-state
checkpoints, plus complete PCM and WAV output. The final capture shows a dream
scene; no native position or per-feature acceptance trace was recorded.

The first pair has equal recorded outputs, but its old input-manifest format
hashed Octoshock while BizHawk actually selected Nymashock. Those reports remain
preserved with that identity limitation. The launcher now explicitly selects
Nymashock and pins `shock.wbx.zst` and `waterboxhost.dll` alongside the other
emulator inputs before execution. A separate repeated pair records the current
result in [japanese-edition-checks.json](japanese-edition-checks.json). That
repeated pair agrees at all 13 checkpoints, with 4,422,823 equal stereo sample
frames at 44,100 Hz and identical complete WAV files. The current 1,800-frame
cold-boot original/rebuild pair also agrees at all six checkpoints and across
1,326,289 stereo sample frames.

The earlier 1,800-frame cold-boot pair is a separate failed state comparison.
Its images, GPU memory, traces and audio agree, but eight bytes differ in each
decoded Waterbox core snapshot. These are actual decoded differences, not ZIP
metadata or compression differences. Their field and cause remain unresolved;
no state bytes are masked. A further cold boot of the same original disc, with
the complete schema-two launch identities equal, also differs in eight decoded
bytes at each checkpoint while its visual, GPU, trace and audio outputs agree.
This demonstrates variation across the recorded original-only cold boots; it
does not identify the field, establish that it is harmless or explain its cause.
The successful original/rebuild cold pair and shared-state replay remain
separate from that investigation.

Full scene/NPC/branch coverage, independent scenario review, memory-card errors,
audio/movie event coverage and original-hardware timing remain open. Whole
feature-group acceptance remains zero.

## Source recovery and before/after counts

This supplement promotes no game function. Three further sprite-scaling
experiments made 1,190 compiler comparisons (including their separate baseline
runs); none matched, and the smallest difference remains 12 bytes. Another 96
bounds-predicate return/lifetime forms also failed to match; their smallest
difference was 83 bytes, leaving the earlier 38-byte candidate as the closest
preserved bounded candidate. Compiler flags and game source remain unchanged.

| Measure | Before this supplement | After |
| --- | ---: | ---: |
| Matching game C bytes | 194,884 / 199,912 | 194,884 / 199,912 |
| Known game assembly functions | 6 | 6 |
| Provisional original feature groups | 40 | 40 |
| Groups with all listed core functions in C | 35 | 35 |
| Whole feature groups independently accepted | 0 | 0 |
| NPC callbacks with C bodies | 107 / 107 | 107 / 107 |
| Bounded native NPC callbacks | 11 / 107 | 11 / 107 |
| AI-assisted developer capabilities | 10 | 10 |
| Optional mods | 3 | 3 |

The official exhaustive feature total remains unknown. These tool corrections
extend existing capabilities and do not add original behavior or model API
calls. Local tooling tests pass on Windows Python 3.14 and Linux Python 3.13;
the metadata retains report, producer, source and dependency hashes. Earlier
feature inventories and publication records remain unchanged.
