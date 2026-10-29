"""Reject stale or fabricated ownership without relying on copyrighted inputs."""
import copy
import io
import lzma
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

from tools.inspect_runtime_menu import History, ROOT_ALLOC_RETURN, inspect_snapshot, read_blob


class NativeGenerationTests(unittest.TestCase):
    def setUp(self):
        self.raw = bytearray(0x200000)
        self.executable = bytearray(0x1800)
        self.executable[:8] = b'PS-X EXE'
        struct.pack_into('<II', self.executable, 0x18, 0x80010000, 0x1000)
        self.executable[0x800:] = bytes((i * 17 + 3) & 255 for i in range(0x1000))
        self.raw[0x10000:0x11000] = self.executable[0x800:]
        self.records, self.generations = [], []
        self.pointer = 0x80012000
        self.add(1, self.pointer, 16, 1, 10, 2, 20)
        self.add(3, self.pointer, 16, 3, 30)
        self.put(self.pointer - 4, 20)

    def put(self, pointer, value):
        struct.pack_into('<I', self.raw, pointer & 0x1FFFFFFF, value)

    def add(self, ident, pointer, requested, alloc_frame, start, free_frame=None, end=None):
        self.records.append(dict(entry_id=ident, kind=5, v0=pointer, a0=requested,
            frame=alloc_frame, entry_ra=0x80010108, sequence_low=start, sequence_high=0))
        free_id = ident + 100 if end is not None else None
        if end is not None:
            self.records.append(dict(entry_id=free_id, kind=6, a0=pointer,
                entry_frame=free_frame, entry_sequence_low=end, entry_sequence_high=0))
        item = dict(id=ident, address=pointer & 0x1FFFFFFF, original_pointer=pointer,
            requested=requested, capacity=requested, allocation_frame=alloc_frame,
            start=start, end=end, free_frame=free_frame, free_id=free_id)
        self.generations.append(item)
        return item

    def history(self, frame=5):
        return History(self.raw, frame, self.executable, self.records,
                       {'allocation_generations':self.generations})

    def test_reused_address_selects_the_live_generation(self):
        history = self.history()
        self.assertEqual(history.allocation(self.pointer)['id'], 3)
        self.assertEqual(self.history(1).live, {})

    def test_equal_vtable_and_valid_header_do_not_revive_freed_storage(self):
        self.put(self.pointer, 0x80010000)
        with self.assertRaisesRegex(ValueError, 'live allocation'):
            self.history(2).allocation(self.pointer)

    def test_checkpoint_frame_edges_are_conservatively_unqualified(self):
        for frame in (1, 2, 3):
            with self.subTest(frame=frame), self.assertRaisesRegex(ValueError, 'live allocation'):
                self.history(frame).allocation(self.pointer)

    def test_factory_frame_edges_report_uncertainty_instead_of_absence(self):
        for row in self.records:
            if row['kind']==5:
                row.update(entry_ra=ROOT_ALLOC_RETURN,a0=196)
        for generation in self.generations:
            generation.update(requested=196,capacity=196)
        self.put(self.pointer-4,200)
        for frame in (1,2,3):
            report=inspect_snapshot(self.raw,frame,self.executable,self.records,b'',
                                    {'allocation_generations':self.generations})
            self.assertEqual(report['status'],'unqualified_title_menu_frame_boundary')
            self.assertNotIn('owned_allocations',report)

    def test_wrong_request_and_original_call_site_are_rejected(self):
        for size, caller in ((12, None), (16, 0x8001010C), (16, (0x80010110,0x80010120))):
            with self.subTest(size=size, caller=caller), self.assertRaises(ValueError):
                self.history().allocation(self.pointer, size, caller)

    def test_changed_or_freed_native_header_is_rejected(self):
        for header in (16, 0x40000014):
            self.put(self.pointer - 4, header)
            with self.subTest(header=header), self.assertRaisesRegex(ValueError, 'heap header'):
                self.history().allocation(self.pointer)

    def test_interior_unaligned_and_unmapped_pointers_are_rejected(self):
        for pointer in (self.pointer+4, self.pointer+1, 0x80212000, 0x12000):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                self.history().allocation(pointer)

    def test_duplicate_ownership_is_rejected(self):
        history = self.history()
        history.own(self.pointer,16,'first',0x80010108)
        with self.assertRaisesRegex(ValueError, 'alias one allocation'):
            history.own(self.pointer,16,'second',0x80010108)

    def test_changed_native_return_cannot_be_used_as_an_allocation(self):
        for key, value in (('requested',12), ('start',31), ('allocation_frame',4), ('original_pointer',self.pointer+4)):
            saved = self.generations[-1][key]
            self.generations[-1][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'native return'):
                self.history()
            self.generations[-1][key] = saved

    def test_changed_or_missing_free_does_not_close_a_generation(self):
        self.generations[0]['end'] += 1
        with self.assertRaisesRegex(ValueError, 'native free'):
            self.history()

    def test_an_open_generation_cannot_hide_a_recorded_free(self):
        self.generations[-1]['free_frame'] = 8
        with self.assertRaisesRegex(ValueError, 'open generation'):
            self.history()

    def test_duplicate_ids_and_overlapping_live_generations_are_rejected(self):
        self.generations.append(copy.deepcopy(self.generations[-1]))
        with self.assertRaisesRegex(ValueError, 'Duplicate or missing'):
            self.history()
        self.generations.pop()
        self.add(5,self.pointer,16,4,40)
        with self.assertRaisesRegex(ValueError, 'Two live generations'):
            self.history()

    def test_original_vtable_and_label_bytes_are_checked(self):
        history = self.history()
        history.immutable(0x80010000,16,'test vtable')
        self.raw[0x10004] ^= 1
        with self.assertRaisesRegex(ValueError, 'Changed original'):
            history.immutable(0x80010000,16,'test vtable')
        self.raw[0x10004] ^= 1
        self.raw[0x10020:0x10024] = b'ABC\0'
        self.executable[0x820:0x824] = b'ABC\0'
        self.assertEqual(history.string(0x80010020),b'ABC')
        self.raw[0x10021] = ord('D')
        with self.assertRaisesRegex(ValueError, 'menu label'):
            history.string(0x80010020)

    def test_truncated_ram_is_rejected(self):
        self.raw.pop()
        with self.assertRaisesRegex(ValueError, 'complete MainRAM'):
            self.history()

    def test_live_resources_do_not_imply_a_completed_lifetime(self):
        history = self.history()
        ident = history.own(self.pointer,16,'menu',0x80010108)
        closure = history.closure([ident],self.generations[-1])
        self.assertEqual(closure['status'],'open_root_generation')
        self.assertFalse(closure['all_selected_resources_released'])
        self.assertFalse(closure['release_order_checked'])

    def test_an_unowned_generation_cannot_replace_a_missing_owned_member(self):
        history=self.history()
        history.own(self.pointer,16,'menu',0x80010108)
        with self.assertRaisesRegex(ValueError,'loses or duplicates'):
            history.closure([1],self.generations[-1])

    def test_release_order_is_checked_against_native_frees(self):
        self.records, self.generations = [], []
        root = self.add(1,self.pointer,16,1,10,9,90)
        self.add(2,self.pointer+0x40,16,2,20,8,80)
        self.put(self.pointer+0x3C,20)
        history = self.history()
        history.own(self.pointer,16,'root',0x80010108)
        history.own(self.pointer+0x40,16,'child',0x80010108)
        self.assertTrue(history.closure([2,1],root)['release_order_checked'])
        with self.assertRaisesRegex(ValueError, 'release order'):
            history.closure([1,2],root)

    def test_lost_duplicated_and_outliving_resources_are_rejected(self):
        self.records, self.generations = [], []
        root = self.add(1,self.pointer,16,1,10,9,90)
        self.add(2,self.pointer+0x40,16,2,20)
        self.put(self.pointer+0x3C,20)
        history = self.history()
        history.own(self.pointer,16,'root',0x80010108)
        history.own(self.pointer+0x40,16,'child',0x80010108)
        for order in ([1], [1,1]):
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, 'loses or duplicates'):
                history.closure(order,root)
        with self.assertRaisesRegex(ValueError, 'outlives'):
            history.closure([2,1],root)


class RetainedBlobTests(unittest.TestCase):
    def test_raw_and_xz_payloads_are_bounded_without_restoration(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            raw=b'payload' * 50
            for filename,data in [('data.bin',raw),('data.xz',lzma.compress(raw))]:
                path=root/filename
                path.write_bytes(data)
                self.assertEqual(read_blob(path,len(raw)),raw)
                with self.assertRaisesRegex(ValueError,'inspection bound'):
                    read_blob(path,len(raw)-1)
            self.assertEqual(sorted(p.name for p in root.iterdir()),['data.bin','data.xz'])

    def test_exact_regular_tar_member_is_read_without_extracting_other_members(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            path=root/'retained.tar.xz'
            with tarfile.open(path,'w:xz') as archive:
                for member,data in [('other',b'other'),('../selected',b'RAM')]:
                    info=tarfile.TarInfo(member);info.size=len(data)
                    archive.addfile(info,io.BytesIO(data))
                link=tarfile.TarInfo('link');link.type=tarfile.SYMTYPE;link.linkname='../selected'
                archive.addfile(link)
            self.assertEqual(read_blob(path,3,'../selected'),b'RAM')
            for member in ('link','missing'):
                with self.subTest(member=member),self.assertRaises(ValueError):
                    read_blob(path,100,member)
            with self.assertRaisesRegex(ValueError,'bounded regular file'):
                read_blob(path,2,'../selected')
            self.assertEqual([p.name for p in root.iterdir()],['retained.tar.xz'])


if __name__ == '__main__':
    unittest.main()
