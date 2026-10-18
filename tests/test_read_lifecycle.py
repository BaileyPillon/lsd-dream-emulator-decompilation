import copy
import unittest
from tools.inspect_read_lifecycle import analyze_read_lifecycle,READ_PC,DISPATCH_PC

def capture():
    entries=[];returns=[]
    def add(pc=READ_PC,source=0x80043184,flag=0,active=1,param=1,opened=1,busy=0,destination=0x80140000,byte_count=2048):
        n=len(entries)+1
        entry=dict(pc=pc,transfer_pc=source,relative_frame=n,a0=0x80110020,a1=destination,a2=byte_count,
            a0_word_28=flag,a0_word_0C=opened,memory_word_0=active,memory_word_1=param,memory_word_2=busy)
        returned=dict(kind=1,base_ordinal=n,entry_pc=pc,v0=0,a0=entry['a0'],a1=destination,a2=byte_count,
            entry_sequence_low=100*n,entry_sequence_high=0,sequence_low=100*n+50,sequence_high=0,
            memory_word_2=1 if flag else busy)
        entries.append(entry);returns.append(returned)
    add(pc=0x800272D0)
    add(active=0,param=0)
    add(opened=0)
    add(source=0x80043460,destination=0x80160000,byte_count=4097)
    add(source=DISPATCH_PC,flag=1)
    add(source=DISPATCH_PC,flag=1,destination=0x80160000,byte_count=4097)
    return entries,returns

class ReadLifecycleTests(unittest.TestCase):
    def test_pairs_FIFO_arguments_without_accepting_completion(self):
        report=analyze_read_lifecycle(*capture())
        self.assertEqual((report['synchronous_Read_entries'],report['framed_Read_entries'],report['logical_Read_argument_pairs']),(1,4,2))
        self.assertEqual(report['requested_byte_length_words_sum'],6145)
        self.assertFalse(report['SDK_completion_accepted'])
        self.assertFalse(report['destination_data_accepted'])
        self.assertTrue(report['all_replays_return_with_driver_busy'])
    def test_missing_return(self):
        e,r=capture()
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r[:-1])
    def test_duplicate_return(self):
        e,r=capture();r[-1]=copy.deepcopy(r[-2])
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_replay_without_origin(self):
        e,r=capture();e[2]['a0_word_28']=1;e[2]['transfer_pc']=DISPATCH_PC
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_unreplayed_origin(self):
        e,r=capture();e[-1]['a0_word_28']=0;e[-1]['transfer_pc']=0x80048B58
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_wrong_destination(self):
        e,r=capture();e[-1]['a1']+=4;r[-1]['a1']+=4
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_wrong_length(self):
        e,r=capture();e[-1]['a2']+=1;r[-1]['a2']+=1
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_reordered_FIFO(self):
        e,r=capture()
        for name in ('a1','a2'):e[-2][name],e[-1][name]=e[-1][name],e[-2][name];r[-2][name],r[-1][name]=r[-1][name],r[-2][name]
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_replay_before_origin_return(self):
        e,r=capture();r[2]['sequence_low']=r[4]['entry_sequence_low']
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_closed_replay_receiver(self):
        e,r=capture();e[-1]['a0_word_0C']=0
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_replay_already_busy(self):
        e,r=capture();e[-1]['memory_word_2']=1
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_replay_return_not_driver_busy(self):
        e,r=capture();r[-1]['memory_word_2']=0
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_unknown_mode_or_dispatch_flag(self):
        for mode,flag in ((0,1),(1,2)):
            e,r=capture();e[-1]['memory_word_0']=mode;e[-1]['a0_word_28']=flag
            with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)
    def test_nonzero_Read_status(self):
        e,r=capture();r[-1]['v0']=1
        with self.assertRaises(ValueError):analyze_read_lifecycle(e,r)

if __name__=='__main__':unittest.main()
