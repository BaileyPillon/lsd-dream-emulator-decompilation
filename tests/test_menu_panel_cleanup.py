"""Keep initialized panel ownership separate from natural screen acceptance."""
import struct
import unittest

from research.screen_lifecycle import verify_panel as tool


class MenuPanelProfile(unittest.TestCase):
    def case(self, **changes):
        return dict(dict(kind='main',segment=0x80000000,seed=1,buffers=True,links=True,sound='owned_bank'), **changes)

    def panel(self, **changes):
        return dict(dict(layout='title',owns_texture=True), **changes)

    def test_incomplete_or_untyped_ownership_context_is_rejected(self):
        for panel in ({'layout':'title'},{'layout':'unknown','owns_texture':True},
                      {'layout':'title','owns_texture':1}):
            with self.subTest(panel=panel),self.assertRaises(ValueError):
                tool.validate_panel(panel)

    def test_receiver_scope_does_not_silently_include_chart_or_empty_base_resources(self):
        for case in (self.case(kind='chart'),self.case(buffers=False)):
            with self.assertRaisesRegex(ValueError,'title menu'):
                tool.Fixture(case,self.panel())

    def test_all_layout_alias_and_ownership_profiles_are_distinct(self):
        cases=list(tool.cases())
        identities={(tuple(sorted(case.items())),tuple(sorted(panel.items()))) for case,panel in cases}
        self.assertEqual(len(cases),216)
        self.assertEqual(len(identities),216)
        for layout in tool.LAYOUTS:
            for owns in (False,True):
                self.assertEqual(sum(p['layout']==layout and p['owns_texture']==owns for c,p in cases),36)

    def test_title_rows_and_shake_choices_use_the_retail_counts(self):
        fixture=tool.Fixture(self.case(),self.panel())
        self.assertEqual(len(fixture.lines),6)
        self.assertEqual(set(fixture.choices),{5})
        pool=fixture.initial['pool']
        lengths=[struct.unpack_from('<I',pool,fixture.offset(p)+0xA8)[0]>>8 &255 for p in fixture.lines]
        self.assertEqual(lengths,[5,9,4,4,5,5])
        self.assertEqual(len(fixture.choices[5]),2)

    def test_empty_panel_uses_null_arrays_and_releases_its_cursor(self):
        fixture=tool.Fixture(self.case(),self.panel(layout='empty'))
        self.assertEqual(fixture.row_arrays,[0,0,0,0])
        self.assertEqual(fixture.lines,[])
        self.assertIn(fixture.cursor,fixture.free_trace)
        self.assertEqual(fixture.get(fixture.root,0x58),0xFFFFFFFF)

    def test_zero_choice_count_does_not_invent_a_zero_byte_allocation(self):
        fixture=tool.Fixture(self.case(),self.panel(layout='mixed'))
        self.assertEqual(fixture.choices[0],[])
        self.assertEqual(fixture.choice_tables[0],0)
        self.assertEqual(set(fixture.choices),{0,2})
        self.assertEqual(fixture.get(fixture.root,0x58),2)

    def test_borrowed_font_object_and_backing_data_are_preserved(self):
        fixture=tool.Fixture(self.case(),self.panel(owns_texture=False))
        for pointer,size in ((fixture.font,0x50),(fixture.file_payloads[fixture.font],52)):
            fixture.model.owned_block(pointer)
            self.assertNotIn(pointer,fixture.free_trace)
            at=fixture.offset(pointer)
            self.assertEqual(fixture.initial['pool'][at:at+size],fixture.model.snapshot()['pool'][at:at+size])

    def test_owned_font_is_released_before_cursor_and_rows(self):
        fixture=tool.Fixture(self.case(),self.panel())
        trace=fixture.free_trace
        self.assertLess(trace.index(fixture.font),trace.index(fixture.cursor))
        self.assertLess(trace.index(fixture.cursor),trace.index(fixture.lines[0]))
        self.assertEqual(trace.count(fixture.font),1)


if __name__=='__main__':unittest.main()
