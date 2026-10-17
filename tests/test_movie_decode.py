"""Owned decoded-packet records; no disc, FFmpeg install or game data is needed."""
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import decode_movies as tool


def framehash(channels=2):
    layout = 'mono' if channels == 1 else 'stereo'
    duration = 4032 // channels
    header = ('#format: frame checksums\n#version: 2\n#hash: SHA256\n'
              '#tb 0: 1/15\n#media_type 0: video\n#codec_id 0: rawvideo\n'
              '#dimensions 0: 320x240\n#tb 1: 1/37800\n#media_type 1: audio\n'
              '#codec_id 1: pcm_s16le\n#sample_rate 1: 37800\n'
              '#channel_layout_name 1: ' + layout + '\n')
    return header + ('0, 0, 0, 1, 115200, ' + 'a' * 64 + '\n'
                     '1, 0, 0, ' + str(duration) + ', 8064, ' + 'b' * 64 + '\n'
                     '0, 1, 1, 1, 115200, ' + 'c' * 64 + '\n'
                     '1, ' + str(duration) + ', ' + str(duration) + ', ' + str(duration) + ', 8064, ' + 'd' * 64 + '\n')


class MovieDecodeTests(unittest.TestCase):
    def parse(self, text, channels=2):
        return tool.parse_framehash(text, video_frames=2, audio_sectors=2, channels=channels)

    def test_complete_mono_and_stereo_records_have_exact_sample_and_byte_totals(self):
        for channels in (1, 2):
            with self.subTest(channels=channels):
                result = self.parse(framehash(channels), channels)
                self.assertEqual((result['video_frames'], result['video_decoded_bytes']), (2, 230400))
                self.assertEqual(result['audio_sample_frames'], 8064 // channels)
                self.assertEqual(result['audio_PCM_bytes'], 16128)
                self.assertEqual(result['unique_video_frame_digests'], 2)
                self.assertFalse(result['native_playback_cadence_verified'])

    def test_missing_video_frame_is_not_a_successful_decode(self):
        with self.assertRaisesRegex(ValueError, 'packet count'):
            self.parse('\n'.join(line for line in framehash().splitlines() if not line.startswith('0, 1,')))

    def test_missing_audio_sector_is_not_a_successful_decode(self):
        with self.assertRaisesRegex(ValueError, 'packet count'):
            self.parse('\n'.join(line for line in framehash().splitlines() if not line.startswith('1, 2016,')))

    def test_stream_copy_cannot_be_mistaken_for_decoded_pixels(self):
        with self.assertRaisesRegex(ValueError, 'decoded YUV/PCM'):
            self.parse(framehash().replace('#codec_id 0: rawvideo', '#codec_id 0: mdec'))

    def test_repeated_or_reordered_timestamps_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timestamps'):
            self.parse(framehash().replace('0, 1, 1, 1,', '0, 0, 0, 1,'))

    def test_wrong_video_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'YUV frame size'):
            self.parse(framehash().replace('115200', '115199', 1))

    def test_wrong_audio_duration_or_channel_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'PCM packet'):
            self.parse(framehash().replace('2016, 8064', '2015, 8064', 1))

    def test_invalid_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            self.parse(framehash().replace('a' * 64, 'z' * 64, 1))

    def test_duplicate_headers_and_unexpected_streams_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.parse(framehash() + '#codec_id 0: rawvideo\n')
        with self.assertRaisesRegex(ValueError, 'additional decoded stream'):
            self.parse(framehash() + '#codec_id 2: rawvideo\n')

    def test_unsupported_XA_coding_and_midstream_changes_are_rejected(self):
        movie = {'path':'/CDI/ETC/ASMK.STR', 'subheaders':[
            {'file':1, 'channel':1, 'flags':100, 'coding':16, 'sectors':2}]}
        with self.assertRaisesRegex(ValueError, '4-bit'):
            tool.audio_profile(movie)
        movie['subheaders'][0]['coding'] = 0
        movie['subheaders'].append({'file':1, 'channel':1, 'flags':228, 'coding':1, 'sectors':1})
        with self.assertRaisesRegex(ValueError, 'stable XA'):
            tool.audio_profile(movie)

    def test_existing_output_is_rejected_before_loading_media_or_starting_a_process(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'retained'
            output.mkdir()
            sentinel = output / 'keep.txt'
            sentinel.write_text('retained evidence')
            with patch.object(tool, 'disc_inputs') as inputs, patch.object(tool.subprocess, 'Popen') as process:
                with self.assertRaisesRegex(ValueError, 'new private output'):
                    tool.audit('missing.cue', 'missing.json', 'ffmpeg', 'ffprobe', output)
                inputs.assert_not_called()
                process.assert_not_called()
            self.assertEqual(sentinel.read_text(), 'retained evidence')

    def test_raw_extraction_retains_original_headers_and_payload_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            payload = bytes((1, 1, 100, 1)) * 2 + bytes(2328)
            sector = tool.SYNC + bytes((0, 2, 0, 2)) + payload
            source = folder / 'source.bin'
            source.write_bytes(sector)
            movie = {'path':'/CDI/ETC/ASMK.STR', 'lba':0, 'sectors':1,
                     'sha256':hashlib.sha256(payload).hexdigest(),
                     'subheaders':[{'file':1, 'channel':1, 'flags':100, 'coding':1, 'sectors':1}]}
            target = folder / 'owned.raw.str'
            result = tool.extract_raw(source, movie, target)
            self.assertEqual(target.read_bytes(), sector)
            self.assertEqual(source.read_bytes(), sector)
            self.assertEqual(result['sha256'], hashlib.sha256(sector).hexdigest())

    def test_raw_payload_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'source.bin'
            payload = bytes((1, 1, 100, 1)) * 2 + bytes(2328)
            source.write_bytes(tool.SYNC + bytes((0, 2, 0, 2)) + payload)
            movie = {'path':'/CDI/ETC/ASMK.STR', 'lba':0, 'sectors':1, 'sha256':'0' * 64,
                     'subheaders':[{'file':1, 'channel':1, 'flags':100, 'coding':1, 'sectors':1}]}
            before = source.read_bytes()
            with self.assertRaisesRegex(ValueError, 'payload differs'):
                tool.extract_raw(source, movie, folder / 'owned.raw.str')
            self.assertEqual(source.read_bytes(), before)

    def test_truncated_raw_extent_is_rejected_before_creating_a_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'short.bin'
            source.write_bytes(bytes(2351))
            movie = {'path':'/CDI/ETC/ASMK.STR', 'lba':0, 'sectors':1, 'sha256':'0' * 64,
                     'subheaders':[{'file':1, 'channel':1, 'flags':100, 'coding':1, 'sectors':1}]}
            target = folder / 'owned.raw.str'
            with self.assertRaisesRegex(ValueError, 'outside'):
                tool.extract_raw(source, movie, target)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
