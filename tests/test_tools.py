"""Tooling regressions. No game assets or MIPS toolchain are required."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools import compile_c, extract_executable, mod_executable, package_disc, progress, psx_image


def executable_fixture():
    data = bytearray(0x80000)
    data[:8] = b"PS-X EXE"
    struct.pack_into("<II", data, 0x18, 0x80010000, len(data) - 0x800)
    offset = psx_image.executable_offset(data, mod_executable.TIME_LIMITS_ADDRESS, 28)
    struct.pack_into("<14h", data, offset, *mod_executable.TIME_LIMITS)
    return bytes(data)


def iso_fixture(payload, sector_size=2048, data_offset=0):
    iso = bytearray(25 * sector_size)

    def put_sector(lba, data):
        start = lba * sector_size + data_offset
        iso[start:start + len(data)] = data

    def record(name, lba, size, flags=0):
        name = name.encode("ascii")
        entry = bytearray(33 + len(name) + (not len(name) % 2))
        entry[0] = len(entry)
        struct.pack_into("<I", entry, 2, lba)
        struct.pack_into(">I", entry, 6, lba)
        struct.pack_into("<I", entry, 10, size)
        struct.pack_into(">I", entry, 14, size)
        entry[25], entry[32] = flags, len(name)
        entry[33:33 + len(name)] = name
        return entry

    volume = bytearray(2048)
    volume[:7] = b"\x01CD001\x01"
    root = record("\0", 22, 2048, 2)
    volume[156:156 + len(root)] = root
    put_sector(16, volume)
    put_sector(22, record("SLPS_015.56;1", 24, len(payload)))
    put_sector(24, payload)
    return bytes(iso)


class RawDiscPreservationTests(unittest.TestCase):
    @staticmethod
    def sector(form2=True):
        data = bytearray(2352)
        data[:12] = b"\x00" + b"\xff" * 10 + b"\x00"
        data[15] = 2
        data[16:20] = data[20:24] = bytes((1, 0, 0x64 if form2 else 0x44, 0))
        data[24:2348] = b"\xa7" * (2348 - 24)
        data[-4:] = b"\x01\x02\x03\x04"
        return data

    def test_only_unchanged_valid_form2_bodies_retain_source_edc(self):
        originals = [self.sector(), self.sector(), self.sector(False), self.sector()]
        originals[3][20] ^= 1  # The duplicate XA subheader is inconsistent.
        candidates = [bytearray(data) for data in originals]
        for data in candidates:
            data[-4:] = b"\x10\x20\x30\x40"
        candidates[1][100] ^= 1  # Changed payload must keep its regenerated checksum.
        with tempfile.TemporaryDirectory() as directory:
            source, rebuilt = Path(directory) / "source.bin", Path(directory) / "rebuilt.bin"
            original_bytes = b"".join(originals)
            source.write_bytes(original_bytes)
            rebuilt.write_bytes(b"".join(candidates))
            retained = package_disc.preserve_unchanged_form2_edc(source, rebuilt)
            self.assertEqual([row["lba"] for row in retained], [0])
            self.assertEqual(rebuilt.read_bytes(), bytes(originals[0]) + b"".join(candidates[1:]))
            self.assertEqual(source.read_bytes(), original_bytes)

    def test_reference_image_cannot_be_its_own_checksum_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bin"
            original = bytes(self.sector())
            source.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "separate rebuilt"):
                package_disc.preserve_unchanged_form2_edc(source, source)
            self.assertEqual(source.read_bytes(), original)


class BuildToolsTests(unittest.TestCase):
    def test_import_has_no_filesystem_side_effect(self):
        graph = ROOT / "build.ninja"
        before = graph.stat().st_mtime_ns if graph.exists() else None
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run([sys.executable, "-c",
                            "import sys; sys.path.insert(0, sys.argv[1]); import configure",
                            str(ROOT)], cwd=folder, check=True)
            self.assertFalse((Path(folder) / "build.ninja").exists())
        self.assertEqual(graph.stat().st_mtime_ns if graph.exists() else None, before)

    def test_graph_preserves_source_and_tracks_headers(self):
        with tempfile.TemporaryDirectory() as folder:
            graph = Path(folder) / "build.ninja"
            real_includes = configure.assembly_includes
            def include_fixture(filename):
                return (["asm/nonmatchings/fixture/retained.s"] if filename == configure.c_game_targets[0]
                        else real_includes(filename))
            with patch.object(configure, "assembly_includes", side_effect=include_fixture):
                configure.generate_build(graph)
            content = graph.read_text()
        self.assertIn("command = ninja -t clean", content)
        self.assertNotIn("rm -f", content)
        self.assertNotIn("build src/start.s:", content)
        self.assertIn("depfile = $out.d", content)
        self.assertIn("restat = 1", content)
        self.assertIn("rom/SLPS_015.56", content)
        self.assertIn("asm/nonmatchings/fixture/retained.s", content)

    def test_missing_and_wrong_rom_have_actionable_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "SLPS_015.56"
            self.assertIn("Missing original executable", configure.check_rom(path))
            path.write_bytes(b"wrong game")
            self.assertIn("Wrong executable SHA-1", configure.check_rom(path))

    def test_failed_preprocessor_never_reaches_assembler(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / "assembled"
            commands = [[sys.executable, "-c", "import sys; sys.exit(17)"],
                        [sys.executable, "-c", "print('compiler')"],
                        [sys.executable, "-c", "print('maspsx')"],
                        [sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()",
                         str(sentinel)]]
            with self.assertRaises(subprocess.CalledProcessError) as result:
                compile_c.run_stages(commands)
            self.assertEqual(result.exception.returncode, 17)
            self.assertFalse(sentinel.exists())

    def test_pipeline_preserves_binary_output(self):
        commands = [[sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'a\\x00b')"]]
        commands += [[sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"]] * 3
        self.assertEqual(compile_c.run_stages(commands), b"a\0b")

    def test_stage_parser_rejects_missing_commands(self):
        with self.assertRaises(ValueError):
            compile_c.parse_stages(["--cpp", "--cc", "cc", "--maspsx", "maspsx", "--as", "as"])


class ProgressTests(unittest.TestCase):
    def test_current_source_excludes_commented_fallbacks(self):
        self.assertEqual(progress.fallback_functions('''
            // INCLUDE_ASM("old", old);
            /* INCLUDE_ASM("old", also_old); */
            INCLUDE_ASM("current", remaining);
        '''), {"remaining"})

    def test_function_sizes_aliases_and_asm_do_not_double_count(self):
        output = '''
 0 .text 00000020 00000000 00000000 00000040 2**2
00000000 g F .text 00000008 c_function
00000000 g F .text 00000008 alias
00000008 g F .text 00000000 remaining
00000010 g F .text 00000010 last_c_function
'''
        self.assertEqual(progress.parse_c_coverage(output, {"remaining"}), (24, 32))

    def test_overlap_is_rejected(self):
        output = '''
 0 .text 00000020 00000000 00000000 00000040 2**2
00000000 g F .text 00000018 first
00000010 g F .text 00000010 second
'''
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            progress.parse_c_coverage(output, set())

    def test_empty_objects_return_zero_without_division(self):
        self.assertEqual(progress.parse_c_coverage(" 0 .text 00000000 0 0 0 2**2", set()), (0, 0))

    def test_incomplete_build_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            obj = root / "build/src/one.c.o"
            obj.parent.mkdir(parents=True)
            obj.touch()
            with self.assertRaisesRegex(ValueError, "Incomplete build: 1/2"):
                progress.collect_progress(root, [("src/one.c", "C"), ("src/two.c", "C")])

    def test_sdk_units_are_excluded_by_path_and_manifest(self):
        kinds = dict(progress.build_manifest())
        self.assertEqual(kinds["asm/21180.s"], "sdk")
        self.assertEqual(kinds["src/psyq/spu/S_I.c"], "sdk")
        self.assertEqual(kinds["src/start.s"], "handwritten")

    def test_stale_build_is_distinct_from_a_current_build(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "build.ninja").touch()
            with patch.object(progress.shutil, "which", return_value="ninja"), \
                    patch.object(progress.subprocess, "run") as runner:
                runner.return_value = subprocess.CompletedProcess([], 0, "ninja: no work to do.\n")
                self.assertTrue(progress.check_build_current(folder))
                runner.return_value = subprocess.CompletedProcess([], 0, "[1/2] CC stale.o\n")
                self.assertFalse(progress.check_build_current(folder))

    def test_stale_objects_are_rejected_before_counting_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            obj = root / "build/src/one.c.o"
            obj.parent.mkdir(parents=True)
            obj.touch()
            with patch.object(progress, "check_build_current", return_value=False), \
                    self.assertRaisesRegex(ValueError, "Build is out of date"):
                progress.collect_progress(root, [("src/one.c", "C")])

    def test_environment_ninja_protects_newer_build_log_from_system_ninja(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "build.ninja").touch()
            build_log = root / ".ninja_log"
            build_log.write_bytes(b"# ninja log v7\nretained build commands\n")
            environment = root / "venv/bin"
            pinned_ninja = str(environment / "ninja")

            def locate(name, path=None):
                return pinned_ninja if path == str(environment) else "old-system-ninja"

            def inspect(command, **kwargs):
                if command[0] == "old-system-ninja":
                    build_log.write_bytes(b"# ninja log v5\n")
                    return subprocess.CompletedProcess(command, 0, "[1/2] CC already-built.o\n")
                return subprocess.CompletedProcess(command, 0, "ninja: no work to do.\n")

            with patch.object(progress.sys, "executable", str(environment / "python")), \
                    patch.object(progress.shutil, "which", side_effect=locate), \
                    patch.object(progress.subprocess, "run", side_effect=inspect):
                self.assertTrue(progress.check_build_current(root))
            self.assertEqual(build_log.read_bytes(), b"# ninja log v7\nretained build commands\n")


class DiscTests(unittest.TestCase):
    def test_iso_and_raw_sector_layouts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "LSD.bin"
            for size, offset in ((2048, 0), (2352, 16), (2352, 24)):
                with self.subTest(size=size, offset=offset):
                    image = iso_fixture(b"fixture executable", size, offset)
                    path.write_bytes(image)
                    self.assertEqual(psx_image.read_root_file(path), (b"fixture executable", 24))
                    self.assertEqual(path.read_bytes(), image)

    def test_cue_with_spaces_resolves_its_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "Dream Emulator.bin"
            binary.write_bytes(iso_fixture(b"exe", 2352, 24))
            cue = Path(folder) / "Dream Emulator.cue"
            cue.write_text('FILE "Dream Emulator.bin" BINARY\n  TRACK 01 MODE2/2352\n')
            self.assertEqual(psx_image.read_root_file(cue), (b"exe", 24))

    def test_wrong_game_is_not_extracted(self):
        with tempfile.TemporaryDirectory() as folder:
            image, output = Path(folder) / "other.bin", Path(folder) / "output.exe"
            image.write_bytes(iso_fixture(b"another executable"))
            with self.assertRaisesRegex(ValueError, "Unexpected executable SHA-1"):
                extract_executable.extract(image, output)
            self.assertFalse(output.exists())

    def test_invalid_images_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "invalid.bin"
            image.write_bytes(b"not an image")
            with self.assertRaisesRegex(ValueError, "No ISO9660"):
                psx_image.read_root_file(image)


class ModTests(unittest.TestCase):
    def setUp(self):
        self.original = executable_fixture()
        self.guard = patch.object(mod_executable, "ORIGINAL_SHA1", hashlib.sha1(self.original).hexdigest())
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def assert_only_declared_bytes_changed(self, result, manifest):
        restored = bytearray(result)
        for item in manifest["patches"]:
            offset = item["offset"]
            before = bytes.fromhex(item["before"])
            self.assertEqual(result[offset:offset + len(before)], bytes.fromhex(item["after"]))
            restored[offset:offset + len(before)] = before
        self.assertEqual(bytes(restored), self.original)
        self.assertEqual(len(result), len(self.original))
        self.assertEqual(result[:0x800], self.original[:0x800])

    def test_duration_and_passive_gray_man_preserve_all_other_bytes(self):
        result, manifest = mod_executable.create_mod(self.original, duration="2", passive_gray_man=True)
        self.assert_only_declared_bytes_changed(result, manifest)
        self.assertEqual(manifest["patches"][0]["seconds_after"], [value * 2 for value in mod_executable.TIME_LIMITS])
        self.assertFalse(manifest["gameplay_tested"])

    def test_endless_covers_initial_spawn_table_and_later_timer_queries(self):
        result, manifest = mod_executable.create_mod(self.original, endless=True)
        self.assert_only_declared_bytes_changed(result, manifest)
        offset = psx_image.executable_offset(result, mod_executable.TIME_LIMITS_ADDRESS, 28)
        self.assertEqual(struct.unpack_from("<14h", result, offset), (-1,) * 14)
        getter = psx_image.executable_offset(result, mod_executable.GET_TIME_LIMIT_ADDRESS, 24)
        self.assertEqual(result[getter:getter+24], self.original[getter:getter+24])
        self.assertEqual(manifest['patches'][0]['seconds_after'], [-1] * 14)

    def test_endless_requires_the_verified_normal_duration_table(self):
        changed = bytearray(self.original)
        offset = psx_image.executable_offset(changed, mod_executable.TIME_LIMITS_ADDRESS, 28)
        struct.pack_into('<h',changed,offset,241)
        with patch.object(mod_executable,'ORIGINAL_SHA1',hashlib.sha1(changed).hexdigest()), \
                self.assertRaisesRegex(ValueError,'stage-duration table'):
            mod_executable.create_mod(bytes(changed), endless=True)

    def test_invalid_duration_and_conflicting_options_are_rejected(self):
        for value in ("nan", "Infinity", "-2", "0", "0.000001", "1e999999", "garbage"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mod_executable.create_mod(self.original, duration=value)
        with self.assertRaises(ValueError):
            mod_executable.create_mod(self.original, duration="2", endless=True)
        with self.assertRaises(ValueError):
            mod_executable.create_mod(self.original)

    def test_unverified_base_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Base must match"):
            mod_executable.create_mod(b"wrong executable", endless=True)

    def test_output_and_manifest_never_replace_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            base, output = Path(folder) / "original.exe", Path(folder) / "mod.exe"
            base.write_bytes(self.original)
            manifest_path, manifest = mod_executable.write_mod(base, output, duration="2")
            self.assertEqual(json.loads(manifest_path.read_text()), manifest)
            first = output.read_bytes()
            with self.assertRaisesRegex(ValueError, "must be new files"):
                mod_executable.write_mod(base, output, duration="3")
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual(base.read_bytes(), self.original)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.original = executable_fixture()
        digest = hashlib.sha1(self.original).hexdigest()
        for module in (mod_executable, package_disc):
            guard = patch.object(module, "ORIGINAL_SHA1", digest)
            guard.start()
            self.addCleanup(guard.stop)

    def test_packaging_checks_executable_and_lba_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            disc, base, executable, output = [root / name for name in
                                              ("original.bin", "original.exe", "mod.exe", "mod.cue")]
            source_image = iso_fixture(self.original)
            disc.write_bytes(source_image)
            base.write_bytes(self.original)
            mod_executable.write_mod(base, executable, endless=True)

            def fake_run(command, cwd, check):
                workspace = Path(cwd)
                if command[0] == "dumpsxiso":
                    (workspace / "files").mkdir()
                    (workspace / "files/SLPS_015.56").write_bytes(self.original)
                    (workspace / "disc.xml").write_text(
                        '<iso_project><track><directory_tree><file name="SLPS_015.56" '
                        'source="files/SLPS_015.56" offs="24"/></directory_tree></track></iso_project>')
                else:
                    replacement = (workspace / "files/SLPS_015.56").read_bytes()
                    (workspace / "image.bin").write_bytes(iso_fixture(replacement))
                    (workspace / "image.cue").write_text('FILE "image.bin" BINARY\n  TRACK 01 MODE1/2048\n')
                return subprocess.CompletedProcess(command, 0)

            with patch.object(package_disc, "find_tool", side_effect=lambda name, directory: name), \
                    patch.object(package_disc.subprocess, "run", side_effect=fake_run):
                report = package_disc.package(disc, executable, output)
            self.assertTrue(report["executable_verified"])
            self.assertEqual(report["executable_lba"], 24)
            self.assertEqual(psx_image.read_root_file(output)[0], executable.read_bytes())
            self.assertEqual(disc.read_bytes(), source_image)
            self.assertFalse(list(root.glob(".lsd-disc-*")))
            with self.assertRaisesRegex(ValueError, "must be new files"):
                package_disc.package(disc, executable, output)

    def test_undeclared_changes_are_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            disc, base, executable, output = [root / name for name in
                                              ("original.bin", "original.exe", "mod.exe", "mod.cue")]
            disc.write_bytes(iso_fixture(self.original))
            base.write_bytes(self.original)
            path, manifest = mod_executable.write_mod(base, executable, endless=True)
            altered = bytearray(executable.read_bytes())
            altered[0x1000] = 1
            executable.write_bytes(altered)
            manifest["output_sha1"] = hashlib.sha1(altered).hexdigest()
            path.write_text(json.dumps(manifest))
            with patch.object(package_disc.subprocess, "run") as runner, \
                    self.assertRaisesRegex(ValueError, "outside its declared patches"):
                package_disc.package(disc, executable, output)
            runner.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
