# Original disc assets

The initial local reference is labelled **English v1**. Its executable is the canonical
Japanese executable; translated assets define the edition used for comparison.
The original and rebuilt raw BIN files both have SHA-1
`C30299AFCB9CF3373A22F1292847266655E20686`, covering the entire 648,088,896-byte
disc image. This establishes byte identity for the reference edition.

The later [Japanese edition supplement](JAPANESE_EDITION.md) independently
hashes both extractions, finds 614 identical and 69 different file payloads,
and reproduces the separate Japanese-labelled raw disc byte for byte. This
original English inventory and its evidence remain preserved.

An isolated dumpsxiso extraction contains **683 filesystem files**:

| Extension / role | Files |
| --- | ---: |
| LBD map/object chunks | 418 |
| Standalone TIM images | 75 |
| SEQ music sequences | 70 |
| TIX stage texture containers | 56 |
| STR records | 40 |
| VB sample banks | 9 |
| VH sound-bank headers | 9 |
| TMD model files | 2 |
| MOM model containers | 2 |
| SYSTEM.CNF | 1 |
| Canonical executable | 1 |

There are **14 stage directories**, each with four TIX files and five SEQ files.
The 56 TIX files contain **445 TIM records** in their populated texture banks.
The native offset tables, bank extents, palette blocks and image rectangles
have been inspected. These are records, not additional player features or a
claim that every texture has been independently seen at runtime.

There are 39 mixed-sector STR files and one data-sector STR record. Movie
records must retain their XA sector layout. A generic 2,048-byte ISO read is
not a substitute for dumpsxiso's mixed extraction or the complete BIN hash.
The [movie audit](MOVIE_INVENTORY.md) now checks all 22,382 encoded frames and
the original path/threshold helpers. It preserves three nonuniform frame-count
margins and the nonzero data-sector STR; decoded audio/video and natural movie
playback remain open.

## Native texture structure

`func_80043200` reads a 36-byte stage header: bank count, four offset slots,
and four byte-size slots. Populated banks contain the count/offset table
consumed by `func_80043CB8`. Its offsets select TIMs interpreted by
`tim_get_info` and the original `GsGetTimInfo` SDK routine.

The last TIM in `/CDI/STG12/TEXD.TIX` declares an image block 192 bytes shorter
than its rectangle. The native SDK ignores that image length word and uses
the rectangle and pixel pointer; the physical bank contains the required
pixels. The inspector records both extents and preserves the original bytes.

## Repeatable inspection

```powershell
python tools/inventory_disc.py --layout D:\private-extraction\disc.xml --edition-label "My verified disc edition" --output .decomp-lab\assets-new.json
```

The tool reads files, checks paths remain within the extraction, streams
hashes, checks the canonical executable and saves a new report. It refuses
to replace an existing report. Current private evidence is
`.decomp-lab/disc-asset-inventory-current.json`; copyrighted files stay outside
tracked deliverables. LBD/MOM structures, model commands, audio/movie decoding
and content-to-runtime coverage still need semantic auditing.
The edition label is caller-supplied and defaults to `unspecified`; executable
identity alone does not establish the asset edition.

## Japanese sound supplement, 2026-10-28

The [sound audit](SOUND_ASSETS.md) independently binds all nine VH/VB pairs and
70 SEQ files to the Japanese raw disc. It accounts for 102 populated program
IDs, 351 tones, 255 samples and 38,976 encoded sequence events. Original SDK
metadata access and stage-9 track avoidance are checked separately from audio
transfer and heard playback. The original zero-tempo STG09/BGC.SEQ is preserved.
These content records add no game features; the original English snapshot above
remains unchanged. [Machine evidence](sound-asset-checks.json) records the
complete input identities, original-code qualification and remaining gates.
