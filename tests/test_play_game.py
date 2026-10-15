"""Exercise play preparation and changed-input refusal without game files."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import play_game


class PlayProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = b'PS-X EXE' + bytes(505856 - 8)
        (self.root / 'build').mkdir()
        (self.root / 'build/SLPS015.56').write_bytes(self.payload)
        self.cue = self.root / 'game with spaces.cue'
        self.cue.write_text('FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n')
        (self.root / 'game.bin').write_bytes(b'owned synthetic disc')
        self.emulator = self.root / 'emulator'
        for name in ('EmuHawk.exe', 'EmuHawk.exe.config', 'dll/BizHawk.Emulation.Cores.dll',
                     'dll/BizHawk.Emulation.Common.dll', 'dll/octoshock.dll',
                     'dll/shock.wbx.zst', 'dll/waterboxhost.dll'):
            destination = self.emulator / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b'owned fixture: ' + name.encode())
        self.bios = self.root / 'bios'
        self.bios.mkdir()
        (self.bios / 'scph5500.bin').write_bytes(bytes(524288))
        self.profile = self.root / 'play profile'
        for replacement in (patch.object(play_game, 'ROOT', self.root),
                            patch.object(play_game, 'ORIGINAL_SHA1', hashlib.sha1(self.payload).hexdigest()),
                            patch.object(play_game, 'read_root_file', return_value=(self.payload, 24))):
            replacement.start()
            self.addCleanup(replacement.stop)

    def prepare(self):
        return play_game.prepare(self.cue, self.emulator, self.bios, self.profile)

    def test_existing_profile_and_card_are_preserved(self):
        self.profile.mkdir()
        card = self.profile / 'keep.mcr'
        card.write_bytes(b'keep existing card')
        with self.assertRaisesRegex(ValueError, 'never replaced'):
            self.prepare()
        self.assertEqual(card.read_bytes(), b'keep existing card')
        self.assertEqual(list(self.profile.iterdir()), [card])

    def test_different_disc_executable_is_rejected_before_creating_profile(self):
        with patch.object(play_game, 'read_root_file', return_value=(b'different executable', 24)):
            with self.assertRaisesRegex(ValueError, 'differs'):
                self.prepare()
        self.assertFalse(self.profile.exists())

    def test_nonmatching_build_is_rejected(self):
        (self.root / 'build/SLPS015.56').write_bytes(b'unsupported build')
        with self.assertRaisesRegex(ValueError, 'canonical executable'):
            self.prepare()
        self.assertFalse(self.profile.exists())

    def test_changed_disc_bios_and_runtime_prevent_launch(self):
        manifest = self.prepare()
        for entry in (manifest['inputs']['disc'], manifest['inputs']['bios'],
                      manifest['inputs']['emulator'][0]):
            path = Path(entry['path'])
            before = path.read_bytes()
            path.write_bytes(before + b'changed')
            with patch.object(play_game.sys, 'platform', 'win32'), patch.object(play_game.subprocess, 'Popen') as process:
                with self.assertRaisesRegex(ValueError, 'input changed'):
                    play_game.launch(self.profile)
                process.assert_not_called()
            path.write_bytes(before)

    def test_preparation_never_launches_and_relaunch_rechecks_disc(self):
        with patch.object(play_game.subprocess, 'Popen') as process:
            manifest = self.prepare()
            process.assert_not_called()
        self.assertFalse(manifest['runtime_observed'])
        self.assertFalse(manifest['whole_game_parity_accepted'])
        config = json.loads((self.profile / 'config.json').read_text())
        self.assertTrue(config['SoundEnabledNormal'])
        for entry in config['PathEntries']['Paths']:
            self.assertTrue(Path(entry['Path']).is_relative_to(self.profile.resolve()))
        with patch.object(play_game.sys, 'platform', 'win32'), patch.object(play_game.subprocess, 'Popen') as process:
            with patch.object(play_game, 'read_root_file', return_value=(b'changed read-back', 24)):
                with self.assertRaisesRegex(ValueError, 'read-back'):
                    play_game.launch(self.profile)
            process.assert_not_called()
            process.return_value = Mock(pid=12345)
            report = play_game.launch(self.profile)
            command = process.call_args.args[0]
        self.assertEqual(command, [str((self.emulator / 'EmuHawk.exe').resolve()), '--config',
                                  str((self.profile / 'config.json').resolve()), '--gdi', str(self.cue.resolve())])
        self.assertEqual(report['pid'], 12345)
        self.assertFalse(report['runtime_observed'])

    def test_changed_secondary_track_prevents_launch(self):
        second = self.root / 'second.bin'
        second.write_bytes(b'owned second track')
        self.cue.write_text('FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n'
                            'FILE "second.bin" BINARY\n  TRACK 02 AUDIO\n')
        manifest = self.prepare()
        self.assertEqual(len(manifest['inputs']['additional_disc_tracks']), 1)
        second.write_bytes(b'changed track')
        with patch.object(play_game.sys, 'platform', 'win32'), patch.object(play_game.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(ValueError, 'input changed'):
                play_game.launch(self.profile)
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
