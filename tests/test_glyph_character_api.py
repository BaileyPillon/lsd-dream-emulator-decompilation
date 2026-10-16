"""Synthetic character arithmetic and private-output custody; no game files."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from research.glyph_character import verify as glyph


class GlyphCharacterTests(unittest.TestCase):
    def case(self,**changes):
        return dict(dict(kind='virtual-set-get',code=0,character=31,seed=0,segment=0),**changes)

    def test_byte_conversion_and_uv_wrap_keep_all_other_object_bytes(self):
        table = 0x8006EC74
        template = struct.pack('<HHII',65530,65535,8,8)
        for code,value in ((-2147483648,0),(-1,255),(127,127),(128,128),(255,255),(256,0),(257,1),(2147483647,255)):
            with self.subTest(code=code):
                case = self.case(code=code)
                before = bytes(glyph.fixture(case,table))
                after,result = glyph.expected(case,table,template)
                self.assertEqual(result,value)
                self.assertEqual(after[0xC8],value)
                self.assertEqual(after[0x92],(250+(value % 32)*8) % 256)
                self.assertEqual(after[0x93],(255+(value // 32)*8) % 256)
                self.assertTrue(all(a == b for i,(a,b) in enumerate(zip(before,after)) if i not in (0x92,0x93,0xC8)))

    def test_getters_preserve_buffers_and_return_unsigned_bytes(self):
        for kind in ('direct-getter','virtual-getter'):
            for value in (0,127,128,255):
                with self.subTest(kind=kind,value=value):
                    case = self.case(kind=kind,character=value,code=-1)
                    after,result = glyph.expected(case,0x8006EC74,bytes(12))
                    self.assertEqual(after,bytes(glyph.fixture(case,0x8006EC74)))
                    self.assertEqual(result,value)

    def test_fixture_domain_covers_bytes_word_edges_and_all_three_address_aliases(self):
        cases = list(glyph.cases())
        self.assertEqual(len(cases),4656)
        self.assertEqual(len({tuple(sorted(case.items())) for case in cases}),4656)
        for kind in ('direct-getter','virtual-getter'):
            self.assertEqual({case['character'] for case in cases if case['kind'] == kind},set(range(256)))
        self.assertEqual({case['segment'] for case in cases},{0,0x80000000,0xA0000000})
        codes = {case['code'] for case in cases if case['kind'] == 'virtual-set-get'}
        self.assertTrue({-2147483648,-1,256,257,65535,65536,2147483647}.issubset(codes))

    def test_existing_output_is_preserved_before_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root/'.decomp-lab'/'prior'
            output.mkdir(parents=True)
            prior = output/'evidence.json'
            prior.write_bytes(b'prior evidence')
            with patch.object(glyph,'ROOT',root),patch.object(glyph,'verify') as verify,contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(glyph.main(['--output',str(output)]),2)
                verify.assert_not_called()
            self.assertEqual(prior.read_bytes(),b'prior evidence')

    def test_public_and_lab_root_outputs_are_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(glyph,'ROOT',Path(folder)), \
                patch.object(glyph,'verify') as verify,contextlib.redirect_stderr(io.StringIO()):
            for path in ('public','.decomp-lab'):
                with self.subTest(path=path):
                    self.assertEqual(glyph.main(['--output',path]),2)
                    verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
