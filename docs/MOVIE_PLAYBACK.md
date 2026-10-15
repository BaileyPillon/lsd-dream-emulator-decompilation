# Startup movie playback and viewport layout

One neutral trajectory now compares the original and rebuilt Japanese-labelled
discs for **9,000 emulator frames** from the same frozen BIOS state. Both
captures have **9,001 per-frame observations**, including a SHA-256 of the
complete **1 MiB GPU memory** at every boundary. All recorded fields and GPU
hashes agree.

The 32 checkpoints also agree in full 2 MiB main RAM, full GPU memory, PNGs,
and every save-state ZIP member payload. ZIP wrapper timestamps are separate
from emulated state. Complete 16-bit stereo PCM and WAV bytes agree across
**6,633,245 stereo sample frames at 44,100 Hz**. No state bytes are masked.

This is one shared-state startup history, not uninterrupted cold boot, all
movies, skip/error/disabled branches, every host-displayed frame, original
hardware timing, or whole-feature acceptance. It makes no instruction-entry
claim. The original NPC and optional AI/mod tracks remain separate.

## Observed lifetimes

| Movie | First active frame | First inactive frame after | Requested cutoff | Maximum accepted frame ID sampled while streaming |
| --- | ---: | ---: | ---: | ---: |
| `/CDI/ETC/ASMK.STR` | 950 | 1320 | 90 | 89 |
| `/CDI/ETC/OPENINGG.STR` | 1632 | 5842 | 1046 | 1045 |
| `/CDI/ETC/OPENINGG.STR`, repeated | 6678 | Still active at 9000 | 1046 | 573 |

The first two lifetimes include contiguous sampled counters from zero,
completion flags, decode completion, and removal of the active movie pointer.
The third is partial. These are two distinct movies with bounded playback
observations, not two fully accepted original features or all 39 movies.

The recorded CD-file blocks identify `ASMK.STR;1` at LBA 21120 and
`OPENINGG.STR;1` at LBA 87656. Their logical sizes correspond to 1008 and
10560 sectors of 2048 bytes. These match the audited mixed files, whose dumps
retain 2336 bytes per sector. The verifier checks the native filename, BCD
location, and size against the recorded resource, as well as the requested
cutoff. Bytes after a filename's NUL remain in the raw trace and comparison.

During setup, the logo stream initially has a size-derived threshold of 100,
and the opening has 1052. Playback replaces these with 90 and 1046. A raw
counter word can still contain 4096 before stream initialization. The recorder
preserves these words; the reader classifies them as setup, not consumed frames.
Stopped streams retain their last accepted ID below the requested threshold.

The native caller can decode a returned buffer before handling stream
completion. These observations do not identify the final displayed image with
an encoded frame ID. See the [structural movie audit](MOVIE_INVENTORY.md) for
all routes, encoded counts, and the original nonuniform cutoff margins.

## Matching viewport type

The movie allocator's 12-byte record contains signed 16-bit **x/y coordinates**
followed by signed 32-bit **width/height**, at offsets 0, 2, 4, and 8. Source
consumers read the coordinate halves and dimensions at those offsets. In this
history the source viewport is `(640, 0, 320, 240)`, while decoding advances
through 16-pixel strips.

`mdec_movie_viewport_t` replaces the opaque three-word record. The complete
candidate translation unit produces the entire canonical 505,856-byte image,
and the standard build also remains canonical. This clarifies an existing C
function; it adds **zero recovered C bytes**. The allocator's inherited eight-byte
stack region remains unexplained among the 24 source-layout requirements.

## Repeat the capture and comparison

Build with `ninja check` in the configured Linux/WSL environment. On Windows,
supply the verified original and separately rebuilt CUEs, BizHawk 2.11.1, the
three BIOS inputs used by runtime pinning, a suitable shared BIOS starting
state, and a new workspace outside Git:

```powershell
python tools/capture_movie_playback.py `
  --workspace D:/QA/movie-pair-new `
  --original-cue D:/Private/original.cue `
  --rebuilt-cue D:/Private/rebuilt.cue `
  --emulator-root D:/Tools/BizHawk-2.11.1 `
  --bios-root D:/Private/BIOS `
  --state D:/Private/shared-bios.State `
  --frames 9000
```

The launcher verifies both disc executables, pins inputs before execution, and
runs hidden owned instances sequentially. It uses fresh isolated SaveRAM and
preserves any owned exit saves under each capture. Existing play sessions and
user profiles are not changed. Desktop sound is disabled; core audio is recorded.
Process identities and observed exit codes are retained.

```powershell
python tools/compare_movie_playback.py `
  --original D:/QA/movie-pair-new/original `
  --rebuilt D:/QA/movie-pair-new/rebuilt `
  --frames 9000 `
  --output .decomp-lab/movie-pair-new.json
```

The comparator requires the current supported observer, complete consecutive
rows, aligned neutral inputs, valid native pointers/vtables, matching pinned
inputs, scheduled/transition checkpoints, and finalized PCM. At every GPU dump,
it independently verifies the per-frame hash against all captured GPU bytes.
Reports require new private paths. Equality returns 0, recorded differences 1,
and invalid input 2. Setup, streaming, stopped, and partial lifetimes remain
distinct. The profile supports the logo and seven opening routes; it does not
infer ambiguous event filenames from a shared cutoff.

[Playback metadata](movie-playback-checks.json) pins the executed observer,
launcher, comparator, full private report, inputs, checkpoints, source change,
and unchanged recovery counts. Images, movie/audio payloads, and native states
remain private. The earlier recorder/API failure is retained as rejected evidence.

The GPU hash uses BizHawk's documented [memory Lua API](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Client.Common/lua/CommonLibs/MemoryLuaLibrary.cs)
and its [complete-region SHA-256 implementation](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Client.Common/Api/Classes/MemoryApi.cs).
The API result is checked against independently hashed checkpoint dumps.
