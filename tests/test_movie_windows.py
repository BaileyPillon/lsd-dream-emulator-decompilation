"""Reject broken movie timelines, misbound skips and incomplete framed buffer coverage."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import inspect_movie_windows as movie


def native(frame,active=True,closed=False):
    row={key:'0' for key in movie.FIELDS}
    row.update(relative_frame=str(frame),core_frame=str(frame+1),native_tables_ready='1',
        active_movie=str(0x800a0000) if active else '0')
    if not active:
        row.update({key:'-' for key in movie.FIELDS[6:]})
        return row
    row.update(movie_00=str(0x8006f614),stream_00=str(0x800817e0),movie_60=str(0x800b0000),
        movie_24='320',movie_28='240',movie_5c='90',stream_40='90',stream_58='20',
        stream_2c='0' if closed else '2',movie_44='1' if closed else '0',movie_48='1' if closed else '0')
    # Audited ASMK native CdlFILE layout: BCD location, logical size, filename.
    raw=struct.pack('<4BI16s',0x04,0x43,0x45,0,1008*2048,b'ASMK.STR;1')
    for offset in range(0,24,4):
        row[f'stream_{offset+12:02x}']=str(int.from_bytes(raw[offset:offset+4],'little'))
    return row


def journal(values):
    return ('\t'.join(movie.FIELDS)+'\n'+''.join('\t'.join(row[key] for key in movie.FIELDS)+'\n' for row in values)).encode()


def window_fixture():
    lines=[b'first native row\n',b'second native row\n']
    masks=[0,1]
    sizes={'MainRAM':2*0x200000,'GPURAM':2*0x100000,'RGB':2*(8+3),'PCM':4,'native':sum(map(len,lines)),'controller':8}
    hashes={key:'a'*64 for key in movie.CHANNELS}
    # Independent fixed framing, rather than using the production framing helper.
    hashes['native']=hashlib.sha256(struct.pack('<iii',0,1,len(lines[0]))+lines[0]
        +struct.pack('<iii',1,2,len(lines[1]))+lines[1]).hexdigest()
    hashes['controller']=hashlib.sha256(struct.pack('<iiii',0,1,4,0)+struct.pack('<iiii',1,2,4,1)).hexdigest()
    return dict(first_frame=0,last_frame=1,frames=2,PCM_sample_frames=1,payload_bytes=sizes,framed_sha256=hashes,
        complete_state_sha256='b'*64,final_MainRAM_sha256='c'*64,final_GPURAM_sha256='d'*64,
        final_RGB_with_dimensions_sha256='e'*64),lines,masks


class MovieWindowTests(unittest.TestCase):
    def test_controller_names_allow_culture_order_but_not_duplicates_or_changed_axes(self):
        report={'controller_buttons':sorted(movie.playback.DIGITAL_NAMES),
            'controller_neutral_axes':{key:int(value) for key,value in movie.playback.NUMERIC_NEUTRAL.items()}}
        movie.controller_schema(report)
        report['controller_buttons'].reverse()
        movie.controller_schema(report)
        for change in ('duplicate','missing','axis','boolean'):
            changed=copy.deepcopy(report)
            if change=='duplicate':
                changed['controller_buttons'][0]=changed['controller_buttons'][1]
            elif change=='missing':
                changed['controller_buttons'].pop()
            else:
                changed['controller_neutral_axes']['Disk Index']=True if change=='boolean' else 1
            with self.subTest(change=change),self.assertRaises(ValueError):
                movie.controller_schema(changed)

    def test_framing_includes_frame_core_frame_length_and_payload(self):
        raw=struct.pack('<iii',7,8,3)+b'abc'+struct.pack('<iii',8,9,0)
        self.assertEqual(movie.framed_hash([(7,8,b'abc'),(8,9,b'')]),hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(movie.framed_hash([(7,8,b'abc')]),movie.framed_hash([(8,9,b'abc')]))

    def test_all_buffer_bytes_and_independent_retained_channels(self):
        window,lines,masks=window_fixture()
        result=movie.validate_windows([window],lines,masks,2,1)
        self.assertEqual(result['MainRAM_bytes'],0x400000)
        for key in ('MainRAM','GPURAM','PCM','controller','native'):
            changed=copy.deepcopy(window)
            changed['payload_bytes'][key]-=1
            with self.subTest(key=key),self.assertRaises(ValueError):
                movie.validate_windows([changed],lines,masks,2,1)

    def test_changed_native_or_controller_payload_cannot_keep_old_hash(self):
        window,lines,masks=window_fixture()
        for changed_lines,changed_masks in (([b'changed\n',lines[1]],masks),(lines,[1,1])):
            with self.assertRaises(ValueError):
                movie.validate_windows([window],changed_lines,changed_masks,2,1)

    def test_window_gaps_truncation_bad_counts_and_missing_state_are_rejected(self):
        window,lines,masks=window_fixture()
        for change in ({'first_frame':1},{'last_frame':0},{'frames':True},{'complete_state_sha256':None},
                       {'PCM_sample_frames':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                movie.validate_windows([{**window,**change}],lines,masks,2,1)
        with self.assertRaises(ValueError):
            movie.validate_windows([window],lines,masks,2,2)

    def test_closed_stream_requires_both_flags_and_next_pointer_clear(self):
        values=[native(0),native(1,closed=True),native(2,active=False)]
        movie.native_rows(journal(values),3)
        for key,value in (('movie_44','0'),('movie_48','0'),('movie_54','1'),('stream_58','21')):
            changed=copy.deepcopy(values)
            changed[1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                movie.native_rows(journal(changed),3)
        values[2]=native(2)
        with self.assertRaises(ValueError):
            movie.native_rows(journal(values),3)

    def test_skip_pulse_is_bound_to_the_stream_and_closed_observation(self):
        values=[native(0),native(1,closed=True),*[native(frame,active=False) for frame in range(2,15)]]
        report={'last_frame':14,'mode':'skip-logo','skip_submitted_frame':1,'skip_pulse_frames':12}
        changes=b'frame\tmask\n0\t0\n1\t1\n13\t0\n'
        _,masks=movie.controller_rows(changes,report,values)
        self.assertEqual(sum(masks),12)
        for change in ({'mode':'skip-opening'},{'skip_submitted_frame':2},{'skip_pulse_frames':11},{'mode':'neutral'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                movie.controller_rows(changes,{**report,**change},values)

    def test_inactive_fields_wrong_filename_and_counter_are_rejected(self):
        for key,value in (('movie_00','1'),('movie_5c','91'),('stream_58','90'),('stream_40','91'),('stream_14','0')):
            row=native(0)
            row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                movie.native_rows(journal([row]),1)
        row=native(0,active=False)
        row['movie_44']='0'
        with self.assertRaises(ValueError):
            movie.native_rows(journal([row]),1)

    def test_frame_coverage_and_extra_columns_cannot_be_omitted(self):
        raw=journal([native(0,active=False),native(1,active=False)])
        with self.assertRaises(ValueError):
            movie.native_rows(raw,3)
        with self.assertRaises(ValueError):
            movie.native_rows(raw.replace(b'1\t2\t1',b'2\t3\t1'),2)
        with self.assertRaises(ValueError):
            movie.native_rows(raw.replace(b'watchdog_counter',b'watchdog_counter\textra'),2)

    def test_comparison_keeps_buffer_and_serialized_state_differences(self):
        base={'report':{'replayed_inputs':False,'mode':'neutral','skip_submitted_frame':-1},
            'windows':[{'complete_state_sha256':'a'*64}], 'native':[],'inputs':[], 'lifetimes':[], 'dimensions':{},
            'final_image':{'width':1,'height':1,'RGB_sha256':'c'*64},'journal_sha256':'d'*64,'report_sha256':'e'*64}
        other=copy.deepcopy(base)
        other['report']['replayed_inputs']=True
        self.assertTrue(movie.compare_data(base,other)['passed'])
        other['windows'][0]['complete_state_sha256']='b'*64
        self.assertEqual(movie.compare_data(base,other)['differences'],{'windows':True})

    def test_public_output_is_refused_before_reading_or_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            target=ROOT/'docs'/'should-never-write-movie-test.json'
            self.assertEqual(movie.main([directory,directory,'--output',str(target)]),2)
            self.assertFalse(target.exists())

    def test_invalid_deflate_is_an_invalid_recording_and_writes_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            report=dict(schema_version=1,status='opening_cleared_and_post_window_completed',mode='neutral',
                cold_start=True,restored_state=False,game_RAM_injected=False,player_UI_or_saves_accessed=False,
                hardware_timing_verified=False,whole_feature_groups_accepted=0,frames_advanced=1,last_frame=0,
                total_PCM_sample_frames=0,replayed_inputs=False,controller_buttons=list(movie.playback.DIGITAL_NAMES),
                controller_neutral_axes={key:int(value) for key,value in movie.playback.NUMERIC_NEUTRAL.items()})
            (folder/'report.json').write_text(json.dumps(report))
            # Valid gzip header followed by the forbidden DEFLATE block type 3.
            (folder/'native.tsv.gz').write_bytes(b'\x1f\x8b\x08\x00'+b'\x00'*6+b'\x07'+b'\x00'*8)
            output=folder/'new-comparison.json'
            self.assertEqual(movie.main([str(folder),str(folder),'--output',str(output)]),2)
            self.assertFalse(output.exists())


if __name__=='__main__':
    unittest.main()
