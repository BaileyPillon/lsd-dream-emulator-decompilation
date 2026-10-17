# Complete software movie decoding

All **39 routed movie payloads** in the verified Japanese reference decode
completely through the recorded local FFmpeg backend. A second pass streams
the raw YUV and PCM bytes into Python and verifies every packet hash.
This extends the [structural inventory](MOVIE_INVENTORY.md) to decoded content.

| Measured output | Verified total |
| --- | ---: |
| Movie payloads | 39 / 39 |
| Decoded video frames | 22,382 |
| Decoded video bytes | 2,578,406,400 |
| Decoded XA audio packets | 27,921 |
| Audio sample frames, summed across mono and stereo files | 56,415,744 |
| Decoded signed 16-bit PCM bytes | 225,154,944 |
| Missing or extra decoded packets | 0 |
| Decoder failures or nonempty error logs | 0 |

These are software-decoder results. They do not establish native PlayStation
MDEC/GPU pixel equivalence, audio mixing, playback cadence, controller skips,
I/O failures or natural startup/special-day/ending coverage. The earlier
[startup replay](MOVIE_PLAYBACK.md) retains its own bounded runtime scope.
Matching C remains **197,172 / 199,912 bytes (98.63%)**; no original feature or
NPC encounter is accepted by this study. The separate Bevy/Rust port is unchanged.

## Reproduce the corpus check

Use Python 3.10 or later, your verified Japanese Mode2/2352 CUE/BIN, and local
`ffmpeg` and `ffprobe` executables from the same installation. The decoder must
support the `psxstr` demuxer, MDEC video, XA ADPCM, rawvideo, PCM and framehash
output. The recorded run uses FFmpeg 9.0.1 on Windows; other decoder versions
have not been established to produce identical output hashes.

```sh
python tools/decode_movies.py \
  --cue /private/LSD-Japanese.cue \
  --ffmpeg /local/ffmpeg \
  --ffprobe /local/ffprobe \
  --output .decomp-lab/movie-decode-new \
  --workers 2
```

On Windows, supply paths to the local `.exe` files. The tool installs nothing
and makes no model/API calls. It uses one or two workers and starts only its
own decoder processes, hidden and below normal priority on Windows. It does
not control a running emulator.

The supported input is one Mode2/2352 track starting at index zero, containing
the canonical `SLPS_015.56` executable. The default
[catalogue](movie-inventory-checks.json) describes the 39 audited extents.
The tool checks the canonical executable, complete source-disc hashes, extent
bounds, repeated XA subheaders and every original 2,336-byte sector payload.
It relies on the earlier catalogue's path/LBA binding; it does not independently
reconstruct the disc's namespace.

Choose a new output directory outside the checkout or under `.decomp-lab/`.
An existing directory is rejected before media loading or decoder execution.
The raw-sector copies occupy **526,927,968 bytes**, plus logs and frame hashes.
They include original CD headers and subheaders, without synthesizing a raw
header around an extracted payload. No decoded frame or audio file is saved
by the corpus-check command.

Each private movie directory retains `input.raw.str`, probe results, process
arguments, logs, decoded frame hashes and a summary. The top-level report
records input, producer and backend identities, complete totals, failures and
preservation checks. Producer source snapshots are retained with that run.
Keep these directories private: they contain original movie sectors.

## What is checked

Every movie must expose exactly one 320 × 240 MDEC video stream and one XA
audio stream. The recorded video format is 8-bit YUV 4:2:0 (`yuvj420p`),
115,200 bytes per frame. Audio stays at 37,800 Hz with its original channels;
no resampling, cropping or shortest-stream truncation is requested.

`ASMK.STR` contains 63 mono XA sectors, producing 4,032 sample frames per
packet. The other 38 movies contain 27,858 stereo sectors, producing 2,016
sample frames per packet. Both forms produce 8,064 PCM bytes per packet.
The summed sample-frame total mixes these channel layouts and is not the
number of individual channel samples.

FFmpeg runs with CPU flags disabled, one codec thread per stream, bitexact
flags and strict error handling. The parser requires decoded `rawvideo` and
`pcm_s16le` streams; an encoded stream copy cannot satisfy the check. It
requires the exact expected packet counts, continuous per-stream timestamps,
valid SHA-256 values, expected durations and exact decoded packet sizes.
Missing frames, repeated/reordered timestamps, extra streams and truncated
PCM are failures even if the decoder process exits successfully.

The demuxer's nominal video time base is `1/15`. Its generated timestamps do
not prove the original game's display cadence, sector scheduling or MDEC/GPU
timing. Original frame thresholds are not applied to the offline decode:
every encoded tail frame is retained, including the previously documented
special-day cutoff exceptions.

All 193 zero-data filler sectors remain in the raw copies. The fortieth STR
record, `/CDI/ZDUMMY/ZDUMMY.STR`, is a separate 61,937,664-byte data file. It is
preserved and hashed by the inventory and complete-disc comparison; it is
excluded from the 39-movie decoding denominator.

## Independent raw-byte check

A separately retained audit producer repeats each video decode to rawvideo
stdout and each audio decode to signed 16-bit PCM stdout. Python reads each
expected packet size, hashes the actual bytes with `hashlib.sha256`, and
compares the result with the first pass's framehash record. It rejects short
packets, extra trailing output, decoder failures and nonempty error logs.
All **50,303** packet hashes agree.

This pass uses its own CSV reader and does not import the public tool's
framehash parser. It also hashes the concatenated raw video and PCM streams
for each movie. Those stream hashes differ in meaning from the first pass's
ordered-digest hashes, which hash the binary packet digests rather than the
media bytes. Both types are labelled in the public metadata.

The hashing implementation and output format are separate; the decoder
implementation is the same FFmpeg backend. This does not constitute a second
independent codec or a native PS1 decoding comparison.

## Evidence and remaining work

[Decode metadata](movie-decode-checks.json) records per-file counts and
aggregate hashes, backend binaries and seven media DLLs, producer dependencies,
catalogue identity and hashes of both retained private reports. No original
sectors, decoded media, emulator states or BIOS are published.

All **392 game build inputs** retain their prior hashes. The original and
rebuilt complete 648,088,896-byte BIN files still share SHA-256
`cbf377af3e9207964f11044202eb5ecec2594a3c96e0919f7aa807d328654e61`.
The canonical executable and frozen project objective are unchanged.

The two remaining collision assembly functions, original storage explanations,
native decoder/output equivalence, natural movie histories, skip/error paths,
timing and whole-feature acceptance remain open. Software decoding extends
the existing analysis capability; it adds no gameplay mod or original NPC AI.

The parser and preservation tests use owned synthetic packet records and raw
sectors, with no original disc, FFmpeg installation or SDK requirement:

```sh
python -m unittest discover -s tests -v
```

The format reference is FFmpeg's pinned
[`psxstr` demuxer](https://github.com/FFmpeg/FFmpeg/blob/e9b3c55fe0321915a70f44f30b276ef2afdc3a0c/libavformat/psxstr.c).
That reference explains the container; its revision is not asserted to be the
source revision of the installed FFmpeg build. The exact installed binaries
and decoder output hashes identify the executed backend.
