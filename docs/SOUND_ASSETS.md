# Original sound assets and stage music

This audit accounts for the Japanese reference's 88 sound files and checks
original SDK metadata access, sequence initialization and stage-music selection.
It preserves a zero-tempo sequence and verifies the selector's separate track-C
avoidance for stage 9. Complete sound playback remains an open parity gate.

## Disc and file coverage

| Component | Observed count |
| --- | ---: |
| VH/VB bank pairs | 9 |
| SEQ files | 70 |
| Populated program IDs | 102 |
| Active tone records | 351 |
| Sample entries | 255 |
| Distinct encoded sample payload hashes | 232 |
| Encoded ADPCM blocks | 126,210 |
| Encoded sequence events, including end markers | 38,976 |
| Complete audio payload bytes | 2,235,032 |

The banks are ETCSE, AMBIENT, CARTOON, ELECTRO, ETHNOVA, HUMAN, LOVELY, SE and
STANDERD. Fourteen stage directories each contain BGA through BGE. These are
content records; they do not increase the 40 provisional feature groups.

The independent raw-disc reader walks all 683 ISO files and checks that its
audio path set, LBAs, lengths and every payload byte agree with the extraction.
It checks sync, MSF, duplicated subheaders and Mode 2/Form 1 fields for the PVD,
directories and audio extents it reads. Mixed movie sectors and ECC validation
are outside this check. The complete reference disc is 648,088,896 bytes with
SHA-256 `cbf377af3e9207964f11044202eb5ecec2594a3c96e0919f7aa807d328654e61`.
Both full-disc hashes agree before and after inspection; no payload is extracted.

Sony's [Sound Artist Tool manual, chapter 4](https://psx.arthus.net/sdk/Psy-Q/DOCS/Devrefs/Sound20.pdf)
describes SEQ sequence data, VH attributes and VB waveforms. The counts above
and the runtime details below come from this disc and its original executable.

## Sparse programs and original SDK phases

AMBIENT declares nine populated programs at IDs 0–6, 8 and 9. Its last program
uses dense tone block 8. Treating the count as the highest ID would lose that
program. The inspector checks all 128 program rows, dense tone ownership,
eight-byte sample-size units, complete VB coverage, block fields and encoded
end/loop flags. Encoded storage and tick spans do not establish heard duration.

Nine original `SsVabOpenHead` calls reproduce every VH bookkeeping byte and
preserve caller guards. This includes dense program ordinals and packed sample
end addresses. They allocate the original body lengths and leave the bank in
pending state 2. All three metadata getters reject that pending state, preserving
their output guards: 27 rejection checks across the nine banks.

The retained cold-boot captures contain ready-state SE and STANDERD banks.
Their complete runtime VH bytes, registry pointers and body lengths agree with
the original files plus the original SDK's bookkeeping. Each RAM context runs
123 getter cases: two headers, 41 programs and 80 tones. Original and rebuilt
contexts pass **246 complete 2 MiB RAM comparisons**, including stack stores,
SDK cached fields and untouched output bytes. No state bytes are masked.

Ready flag 1 does not prove DMA completion. The original `SsVabTransBody`
sets that flag after initiating a transfer; completion has a separate API.
This profile performs no waveform transfer and makes no SPU or audible-playback
acceptance claim. Earlier recorded PCM comparisons remain separate evidence.

## Preserved zero-tempo sequence

`/CDI/STG09/BGC.SEQ` is 1,500 bytes. Its initial tempo and rhythm numerator are
both zero; its SHA-256 is
`e0173bc0924dc69c73923bb054b9ceaa0ae37ea033ac6e5ec52a86c5ffe8f5c7`.
The original file remains unchanged.

After the original sequence-work initialization, 69 original `SsSeqOpen`
calls return 1. This file reaches the original division guard's BREAK
instruction at `0x8003A800`; Unicorn raises an exception there. A private
RAM-only control changes just the three tempo bytes to 500,000 and returns 1,
while preserving the zero rhythm numerator. The control does not replace or
repair the original asset. BIOS exception handling is outside this profile.

## Original stage-9 selection guard

The original `get_stage_music_path` changes random index 2 to index 3 for
stage 9. It also changes stored forced-track selection 3 to 4. Both select
BGD instead of BGC. The stored change persists: a subsequent stage-8 call
selects its track D, and a negative override-setting call preserves that choice.

The native selector matrix covers stages 0–13, all five random residue classes,
and automatic or forced choices 1–5: **420 cases**. Each case executes original
`srand` and `rand`, checks the returned path and its disc payload, and checks
the same single-call RNG advance. Stage 9 never selects C in this matrix.
Two executed instruction controls remove the respective remaps; both return
the wrong path and are rejected.

This verifies the avoidance in these constructed selector calls. Alternate
direct sequence-opening routes and complete natural game histories remain to
audit. The initializer exception alone is not evidence of a naturally reached
gameplay crash.

## Native qualification and limits

The metadata profile qualifies 22 complete original function bodies; the
selector qualifies eight. GNU symbol sizes, ELF function extents and every
instruction byte agree with the canonical executable. Every executed PC must
remain in a qualified span. There are zero original-function output stubs.
Three executed metadata faults and two executed selector faults are detected.

The two source RAM contexts come from separately pinned original/rebuilt cold
boots, sampled at relative frame 3,000 / core frame 3,001. Their complete RAM
hashes agree. Launch manifests, BIOS, emulator/core, script, configuration and
disc contents are freshly verified. Sealed RAM members are read in memory;
no historical capture or runtime directory is recreated.

Native method-entry reachability, complete MIDI event/control semantics, all
voices/envelopes/reverb, pause/resume timing, DMA completion, every track's heard
output and independent hardware comparison remain open. This adds evidence
for F030/F031 and the asset audit U002; it closes no whole feature or U003
call-graph requirement.

## Before and after this audit

| Measure | Before | After |
| --- | ---: | ---: |
| Matching C bytes / game text bytes | 197,172 / 199,912 | 197,172 / 199,912 |
| Matching C percentage | 98.6294% | 98.6294% |
| Remaining assembly functions | 2 | 2 |
| Inherited storage explanations | 3 | 3 |
| Provisional feature groups | 40 | 40 |
| Listed-core groups recovered in C | 38 | 38 |
| Accepted whole features / encounters | 0 / 0 | 0 / 0 |

The 107 original NPC callback bodies and 44 bounded NPC profiles are unchanged.
No original gameplay feature, optional mod or developer-capability category is
added. The read-only tools extend existing asset-analysis capabilities and make
zero model API calls. Original NPC AI and AI-assisted developer tools remain
separate from these original audio routines.

## Reproduce with owned inputs

```powershell
python -B tools/inventory_sound.py --layout D:\private-extraction\disc.xml --edition-label "My verified reference" --output .decomp-lab\sound-new.json
```

Exit 0 means the reviewed structures parsed without flagged headers; exit 1
retains structural failures or zero-tempo review items; exit 2 rejects inputs
or an existing output. The Japanese reference returns 1 for its preserved
zero-tempo header, with all 88 files structurally parsed.

See the [native research recipe](../research/sound_assets/README.md) for raw-disc,
metadata and selector commands. They refuse to overwrite reports. The
[machine evidence](sound-asset-checks.json) records producer hashes, original
function ranges, source identities, native outcomes and explicit unmet gates.
