"""Owned PNG/storage fixtures and executed Windows stream-budget controls."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

from tools import compact_dispatch as tool
from tools import record_dispatch_history as legacy
from tools.build_dispatch_observer import OBSERVER, FLOW_OBSERVER, RETURN_OBSERVER, SDK_OBSERVER
from tools.build_dispatch_observer import EXPORTS, FLOW_EXPORTS, RETURN_EXPORTS, SDK_EXPORTS
from tools.build_npc_observer import UPSTREAM, MEDNAFEN, SOURCE_SHA256
from tools.record_compact_dispatch import qualify_reused_profile, QUALIFICATION
from tools.replay_cold_start_headless import select_compiler
from tools.runtime_inputs import record_file
from tools.inspect_compact_dispatch import qualify_host_sources

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.decomp-lab'

def chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)

def png(raw, width=2, height=5, header=None):
    header = header or struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

PIXELS = bytes((10, 20, 30, 40, 50, 60, 15, 25, 35, 45, 55, 65, 20, 30, 40, 50, 60, 70,
                30, 50, 70, 90, 110, 130, 255, 0, 128, 127, 128, 255))
# Hand-calculated scanlines exercise None, Sub, Up, Average and Paeth, including wraparound.
SCANLINES = bytes((0, 10, 20, 30, 40, 50, 60, 1, 15, 25, 35, 30, 30, 30, 2, 5, 5, 5, 5, 5, 5,
                   3, 20, 35, 50, 50, 55, 60, 4, 225, 206, 58, 128, 78, 125))

class CompactPngTests(unittest.TestCase):
    def test_all_standard_filters_against_hand_pixels(self):
        self.assertEqual(tool.png_rgb(png(SCANLINES), 2, 5), PIXELS)

    def test_crc_corruption_is_rejected(self):
        raw = bytearray(png(SCANLINES)); raw[45] ^= 1
        with self.assertRaises(ValueError): tool.png_rgb(bytes(raw), 2, 5)

    def test_unknown_filter_is_rejected(self):
        with self.assertRaises(ValueError): tool.png_rgb(png(bytes((5,)) + SCANLINES[1:]), 2, 5)

    def test_oversized_decompressed_pixels_are_rejected(self):
        with self.assertRaises(ValueError): tool.png_rgb(png(SCANLINES + b'X'), 2, 5)

    def test_truncated_pixels_are_rejected(self):
        with self.assertRaises(ValueError): tool.png_rgb(png(SCANLINES[:-1]), 2, 5)

    def test_unsupported_bit_depth_color_and_interlace(self):
        for depth, color, interlace in ((16, 2, 0), (8, 6, 0), (8, 2, 1)):
            with self.subTest(depth=depth, color=color, interlace=interlace), self.assertRaises(ValueError):
                tool.png_rgb(png(SCANLINES, header=struct.pack('>IIBBBBB', 2, 5, depth, color, 0, 0, interlace)), 2, 5)

    def test_dimensions_outside_producer_bound_are_rejected(self):
        for width, height in ((0, 5), (2049, 5), (2, 1025)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                tool.png_rgb(png(SCANLINES), width, height)

    def test_concatenated_zlib_stream_is_rejected(self):
        data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 5, 8, 2, 0, 0, 0))
        data += chunk(b'IDAT', zlib.compress(SCANLINES) + zlib.compress(b'extra')) + chunk(b'IEND', b'')
        with self.assertRaises(ValueError): tool.png_rgb(data, 2, 5)

class CompactArchiveTests(unittest.TestCase):
    def setUp(self):
        LAB.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='compact-storage-', dir=LAB)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archived(self):
        for name, byte in zip(tool.PAYLOADS[:2], (31, 72)):
            (self.root / name).write_bytes(bytes((byte,)) * (512 * 1024))
        return tool.archive_payloads(self.root)

    def test_two_payloads_update_the_index_and_roundtrip(self):
        metadata = self.archived()
        self.assertEqual(len(metadata), 2)
        self.assertFalse((self.root / 'payload-archives.pending.json').exists())
        for name, byte in zip(tool.PAYLOADS[:2], (31, 72)):
            self.assertFalse((self.root / name).exists())
            self.assertEqual(tool.read_payload(self.root, name), bytes((byte,)) * (512 * 1024))

    def test_a_small_payload_remains_directly_readable(self):
        (self.root / 'method-code.bin').write_bytes(b'owned-code')
        self.assertEqual(tool.archive_payloads(self.root), {})
        self.assertEqual(tool.read_payload(self.root, 'method-code.bin'), b'owned-code')

    def test_changed_compressed_bytes_are_rejected(self):
        self.archived()
        path = self.root / (tool.PAYLOADS[0] + '.xz')
        raw = bytearray(path.read_bytes()); raw[len(raw)//2] ^= 1; path.write_bytes(raw)
        with self.assertRaises(ValueError): tool.read_payload(self.root, tool.PAYLOADS[0])

    def test_both_raw_and_archived_are_rejected(self):
        self.archived()
        (self.root / tool.PAYLOADS[0]).write_bytes(b'conflicting expanded copy')
        with self.assertRaises(ValueError): tool.read_payload(self.root, tool.PAYLOADS[0])

    def test_changed_length_hash_codec_and_path_are_rejected(self):
        original = self.archived()
        for field, value in (('bytes', tool.STREAM_LIMIT + 1), ('sha256', '0' * 64), ('codec', 'other'), ('file', '../escape.xz')):
            changed = deepcopy(original); changed[tool.PAYLOADS[0]][field] = value
            (self.root / 'payload-archives.json').write_text(json.dumps(changed))
            with self.subTest(field=field), self.assertRaises(ValueError): tool.read_payload(self.root, tool.PAYLOADS[0])

    def test_shared_historical_payload_is_preserved(self):
        path = self.root / tool.PAYLOADS[0]
        path.write_bytes(b'A' * (512 * 1024))
        try: os.link(path, self.root / 'retained-link.bin')
        except OSError as error: self.skipTest(str(error))
        with self.assertRaises(ValueError): tool.archive_payloads(self.root)
        self.assertEqual(path.read_bytes(), b'A' * (512 * 1024))

    def test_existing_archive_evidence_is_preserved(self):
        self.archived()
        before = (self.root / 'payload-archives.json').read_bytes()
        with self.assertRaises(ValueError): tool.archive_payloads(self.root)
        self.assertEqual((self.root / 'payload-archives.json').read_bytes(), before)

def profile_fixture():
    qualification = json.loads(QUALIFICATION.read_text())
    headers = {k: record_file(p) for k, p in {'entry': OBSERVER, 'flow': FLOW_OBSERVER, 'return': RETURN_OBSERVER, 'sdk': SDK_OBSERVER}.items()}
    producer = dict(sha256=qualification['source_file_SHA256']['tools/build_dispatch_observer.py'])
    profile = dict(schema_version=1, status='built_separate_dispatch_observer_core', upstream_commit=UPSTREAM, mednafen_commit=MEDNAFEN,
        original_adapter_sha256=SOURCE_SHA256['shock.cpp'], existing_CPU_source_modified=False, input_files_preserved=True,
        original_game_RAM_written_by_observer=False, observer_mode='method_entries', producer_sha256=producer['sha256'],
        compressed_core=qualification['native_profile']['compressed_core'], observer_header_sha256=headers['entry']['sha256'],
        flow_header_sha256=headers['flow']['sha256'], return_header_sha256=headers['return']['sha256'], sdk_read_header_sha256=headers['sdk']['sha256'],
        flow_protocol=1, return_protocol=1, sdk_read_protocol=1, flow_event_bytes=664, flow_history_instructions=16,
        return_event_bytes=600, return_frame_payload_bytes=8*2**20, sdk_read_event_bytes=464, sdk_read_frame_payload_bytes=32*2**20,
        exported_functions=sorted(set(EXPORTS) | set(FLOW_EXPORTS) | set(RETURN_EXPORTS) | set(SDK_EXPORTS)))
    return profile, qualification, headers, producer

class ReusedObserverTests(unittest.TestCase):
    def test_current_or_one_complete_published_host_version_is_required(self):
        current = {'A.cs': 'a', 'B.cs': 'b'}
        published = {'A.cs': 'c', 'B.cs': 'd'}
        qualify_host_sources(current, current, published)
        qualify_host_sources(published, current, published)
        for value in ({'A.cs': 'a', 'B.cs': 'd'}, {'A.cs': 'a'}, {'A.cs': 'a', 'B.cs': 'b', 'C.cs': 'e'}):
            with self.subTest(value=value), self.assertRaises(ValueError): qualify_host_sources(value, current, published)

    def test_only_the_published_historical_body_and_producer_qualify(self):
        qualify_reused_profile(*profile_fixture())

    def test_changed_source_protocol_headers_and_core_are_rejected(self):
        original, qualification, headers, producer = profile_fixture()
        mutations = dict(producer_sha256='0'*64, observer_header_sha256='0'*64, existing_CPU_source_modified=True,
            original_game_RAM_written_by_observer=True, sdk_read_frame_payload_bytes=8*2**20,
            compressed_core=dict(file='shock.wbx.zst', bytes=1, sha256='0'*64), exported_functions=[])
        for field, value in mutations.items():
            profile = deepcopy(original); profile[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): qualify_reused_profile(profile, qualification, headers, producer)

    def test_current_observer_loader_does_not_accept_the_historical_producer(self):
        profile, _, _, _ = profile_fixture()
        LAB.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='historical-loader-', dir=LAB) as folder:
            path = Path(folder) / 'profile.json'; path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, 'current published source'): legacy.load_observer_profile(path)

HARNESS = r'''
using System;
using System.IO;
using Lsd.Research.Headless;
internal static class Harness {
    public static int Main(string[] args) {
        string mode=args[0], root=args[1]; Directory.CreateDirectory(root);
        if (mode=="digest") {
            byte[] bytes=new byte[16]; for(int i=0;i<16;i++) bytes[i]=(byte)i;
            var sink=new PcmDigestStream(); sink.Write(bytes,0,6); sink.Write(bytes,6,10); sink.Flush(); sink.Dispose(); sink.Dispose();
            bool rejected=false; try { sink.Write(bytes,0,1); } catch(IOException) { rejected=true; }
            for(int i=0;i<16;i++) if(bytes[i]!=i) return 9;
            Console.WriteLine(sink.Bytes+" "+sink.Digest+" "+rejected); return 0;
        }
        CaptureBudget.Initialize(root,mode!="legacy",16);
        if(mode=="budget") {
            using(var a=CaptureBudget.Open(Path.Combine(root,"a.bin"),FileMode.CreateNew))
            using(var b=CaptureBudget.Open(Path.Combine(root,"b.bin"),FileMode.CreateNew)) {
                a.Write(new byte[8],0,8); b.Write(new byte[8],0,8);
                try { b.WriteByte(1); return 8; } catch(IOException) { }
            }
            Console.WriteLine(CaptureBudget.Bytes); return 0;
        }
        if(mode=="escape") {
            try { using(var a=CaptureBudget.Open(Path.Combine(root,"..","escape.bin"),FileMode.CreateNew)) { } return 7; }
            catch(Exception) { Console.WriteLine("rejected"); return 0; }
        }
        if(mode=="existing") {
            string path=Path.Combine(root,"keep.bin"); File.WriteAllText(path,"keep");
            try { using(var a=CaptureBudget.Open(path,FileMode.CreateNew)) { } return 6; }
            catch(IOException) { Console.WriteLine(File.ReadAllText(path)); return 0; }
        }
        if(mode=="repeat") {
            try { CaptureBudget.Initialize(root,true,16); return 5; }
            catch(Exception) { Console.WriteLine("rejected"); return 0; }
        }
        if(mode=="legacy") {
            using(var a=CaptureBudget.Open(Path.Combine(root,"..","legacy.bin"),FileMode.CreateNew)) a.WriteByte(42);
            Console.WriteLine(CaptureBudget.Bytes); return 0;
        }
        return 4;
    }
}
'''

@unittest.skipUnless(os.name == 'nt', 'Executed stream helper requires the installed Windows .NET Framework.')
class CompactBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dotnet = shutil.which('dotnet') or str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'dotnet/dotnet.exe')
        if not Path(dotnet).is_file(): raise unittest.SkipTest('No installed .NET SDK; no tools are downloaded.')
        LAB.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='compact-backend-', dir=LAB)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        source = cls.root / 'Harness.cs'; source.write_text(HARNESS)
        cls.exe = cls.root / 'Harness.exe'
        compiler = select_compiler(subprocess.check_output([dotnet, '--list-sdks'], text=True))
        framework = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319'
        command = [dotnet, 'exec', str(compiler), '/nologo', '/target:exe', '/platform:x64', '/nostdlib+', '/warnaserror+',
                   '/reference:' + str(framework / 'mscorlib.dll'), '/reference:' + str(framework / 'System.dll'),
                   '/out:' + str(cls.exe), str(source), str(ROOT / 'research/headless/BoundedCapture.cs')]
        built = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if built.returncode: raise AssertionError(built.stdout + built.stderr)

    def run_mode(self, mode):
        path = self.root / mode
        run = subprocess.run([str(self.exe), mode, str(path)], capture_output=True, text=True,
                             check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return run.stdout.strip(), path

    def test_executed_budget_covers_multiple_streams_before_write(self):
        value, path = self.run_mode('budget')
        self.assertEqual(value, '16')
        self.assertEqual([(path / name).stat().st_size for name in ('a.bin', 'b.bin')], [8, 8])

    def test_executed_pcm_digest_and_count(self):
        value, _ = self.run_mode('digest')
        self.assertEqual(value, '16 ' + hashlib.sha256(bytes(range(16))).hexdigest() + ' True')

    def test_executed_escape_is_rejected_before_file_creation(self):
        value, _ = self.run_mode('escape')
        self.assertEqual(value, 'rejected'); self.assertFalse((self.root / 'escape.bin').exists())

    def test_executed_existing_output_is_preserved(self):
        value, _ = self.run_mode('existing'); self.assertEqual(value, 'keep')

    def test_executed_reinitialization_is_rejected(self):
        value, _ = self.run_mode('repeat'); self.assertEqual(value, 'rejected')

    def test_executed_legacy_mode_preserves_unbudgeted_open(self):
        value, _ = self.run_mode('legacy')
        self.assertEqual(value, '0'); self.assertEqual((self.root / 'legacy.bin').read_bytes(), b'*')

if __name__ == '__main__': unittest.main()
