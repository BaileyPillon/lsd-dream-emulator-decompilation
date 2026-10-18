"""Owned instruction fixtures for observed virtual load-chain acceptance."""
from copy import deepcopy
import json
import struct
import unittest

from tools import dispatch_flow as flow
from tests.test_npc_catalogue import executable


class DispatchFlowTests(unittest.TestCase):
    def setUp(self):
        self.base = 0x80010080
        self.call = self.base + 16
        self.receiver, self.table, self.target = 0x80040000, 0x80050000, 0x80010100
        # lw v0,0(s0); nop; lw v0,0x44(v0); nop; jalr v0; move a3,zero
        self.words = [0x8E020000, 0, 0x8C420044, 0, 0x0040F809, 0x00003821]
        body = bytearray(0x200)
        struct.pack_into('<6I', body, 0x80, *self.words)
        self.image = executable(bytes(body))
        self.entry = dict(relative_frame=3, pc=self.target, a0=self.receiver,
            a0_word_00=self.table, a0_table_word_044=self.target,
            transfer_pc=self.call, delay_pc=self.call + 4, ra=self.call + 8,
            transfer_word=self.words[-2], delay_word=self.words[-1])
        self.history = []
        for i, word in enumerate(self.words):
            rs = self.receiver if i == 0 else self.table if i == 2 else self.target if i == 4 else 0
            flags = 5 if i in (0, 2) else 1
            address = self.receiver if i == 0 else self.table + 0x44 if i == 2 else 0
            loaded = self.table if i == 0 else self.target if i == 2 else 0
            self.history.append([self.base + i * 4, word, word, rs, 0, address, loaded, flags, 0, i])
        self.program = dict(method_trace=dict(flow_sites=[f'0x{self.call:08X}']))
        self.summary = dict(protocol=1,event_bytes=664,history_instructions=16,entries=1,native_total=1,
            native_overflow=0,sites=[self.call],game_RAM_injected=False,CPU_source_modified=False,
            instruction_cache_peek_only=True)

    def pack(self, history=None, **header):
        history = self.history if history is None else history
        values = dict(frame=3,ordinal=1,pc=self.target,count=len(history),low=len(history),high=0)
        values.update(header)
        words = list(values.values()) + [value for instruction in history for value in instruction]
        return struct.pack('<166I', *words, *([0] * (166 - len(words))))

    def validate(self, data=None, summary=None, entries=None):
        return flow.validate_flow(self.pack() if data is None else data,
            self.summary if summary is None else summary,[self.entry] if entries is None else entries,
            self.program,self.image)

    def test_actual_load_chain_accepts_one_entry_and_one_edge(self):
        report, edges = self.validate()
        self.assertEqual(report['accepted_entry_slot_chains'],1)
        self.assertEqual(report['distinct_table_slot_edges'],1)
        self.assertEqual(edges[0]['receiver'],f'0x{self.receiver:08X}')

    def test_read_slot_is_accepted_with_its_actual_load_word(self):
        self.words[2] = 0x8C420054
        self.history[2][1:3] = [self.words[2]] * 2
        self.history[2][5] = self.table + 0x54
        self.entry['a0_table_word_054'] = self.entry.pop('a0_table_word_044')
        image = bytearray(self.image);struct.pack_into('<I',image,0x800+0x88,self.words[2]);self.image=bytes(image)
        self.assertEqual(self.validate()[1][0]['slot'],'0x54')

    def shared_tail(self):
        self.call=self.base+64
        jump=0x08000000|((self.call>>2)&0x03FFFFFF)
        old=self.history
        self.history=deepcopy(old[:3])+[
            [self.base+12,jump,jump,0,0,0,0,1,0,3],
            [self.base+16,0,0,0,0,0,0,1,0,4],
            [self.call,old[4][1],old[4][2],self.target,0,0,0,1,0,5],
            [self.call+4,old[5][1],old[5][2],0,0,0,0,1,0,6]]
        image=bytearray(self.image)
        for record in self.history:struct.pack_into('<I',image,0x800+record[0]-0x80010000,record[1])
        self.image=bytes(image)
        self.entry.update(transfer_pc=self.call,delay_pc=self.call+4,ra=self.call+8)
        self.program['method_trace'].update(flow_sites=[f'0x{self.call:08X}'],flow_context_sites=[f'0x{self.base+12:08X}'])
        self.summary['sites']=[self.call,self.base+12]

    def test_original_shared_tail_jump_needs_both_captured_loads_and_exact_delay_path(self):
        self.shared_tail()
        self.assertEqual(self.validate()[0]['accepted_entry_slot_chains'],1)
        self.history[4][0]+=4
        with self.assertRaises(ValueError):self.validate()

    def test_canonical_jump_to_another_destination_cannot_prove_this_observed_path(self):
        self.shared_tail()
        changed=self.history[3][1]^1;self.history[3][1:3]=[changed,changed]
        image=bytearray(self.image);struct.pack_into('<I',image,0x800+0x8C,changed);self.image=bytes(image)
        with self.assertRaisesRegex(ValueError,'PC sequence'):self.validate()

    def test_undeclared_or_duplicate_extra_context_cannot_be_claimed(self):
        self.shared_tail()
        self.program['method_trace'].pop('flow_context_sites');self.summary['sites']=[self.call]
        with self.assertRaisesRegex(ValueError,'configured native windows'):self.validate()
        for values in ([f'0x{self.call:08X}'],['0x80010001'],[self.call]):
            self.program['method_trace']['flow_context_sites']=values
            with self.subTest(values=values),self.assertRaises(ValueError):flow.flow_windows(self.program,self.image)

    def test_a_branch_in_a_shared_tail_jump_delay_slot_is_rejected(self):
        self.shared_tail()
        changed=0x0040F809;self.history[4][1:3]=[changed,changed]
        image=bytearray(self.image);struct.pack_into('<I',image,0x800+0x90,changed);self.image=bytes(image)
        with self.assertRaisesRegex(ValueError,'Unsupported instruction'):self.validate()

    def test_a_branch_in_the_final_JALR_delay_slot_is_rejected(self):
        changed=0x08004000|((self.target>>2)&0x03FFFFFF)
        self.history[-1][1:3]=[changed,changed];self.entry['delay_word']=changed
        image=bytearray(self.image);struct.pack_into('<I',image,0x800+0x94,changed);self.image=bytes(image)
        with self.assertRaisesRegex(ValueError,'JALR cannot'):self.validate()

    def test_cache_hit_is_accepted_only_when_effective_and_RAM_words_agree(self):
        for record in self.history:record[7] |= 2
        self.validate()
        self.history[0][2] ^= 4
        with self.assertRaises(ValueError):self.validate()

    def test_equal_entry_slot_does_not_replace_executed_load_evidence(self):
        self.history[2][6] ^= 4
        with self.assertRaisesRegex(ValueError,'load values'):self.validate()

    def test_wrong_receiver_table_address_and_target_operands_are_rejected(self):
        for index,column in ((0,3),(0,5),(0,6),(2,3),(2,5),(2,6),(4,3)):
            history=deepcopy(self.history);history[index][column]^=4
            with self.subTest(index=index,column=column),self.assertRaises(ValueError):self.validate(self.pack(history))

    def test_changed_instruction_including_delay_slot_is_rejected(self):
        for index in range(6):
            history=deepcopy(self.history);history[index][1]^=4
            with self.subTest(index=index),self.assertRaises(ValueError):self.validate(self.pack(history))

    def test_unsupported_or_clobbering_intermediate_instruction_is_rejected(self):
        for word in (0x0C004000,0x24020000,0x0000000D):
            history=deepcopy(self.history);history[3][1:3]=[word,word]
            with self.subTest(word=word),self.assertRaises(ValueError):self.validate(self.pack(history))

    def test_original_load_delay_gaps_are_required(self):
        for index in (1,3):
            history=deepcopy(self.history);history.pop(index)
            with self.subTest(index=index),self.assertRaises(ValueError):self.validate(self.pack(history))

    def test_missing_capture_load_validity_or_cache_isolation_rejects_the_edge(self):
        for index,column,value in ((0,7,0),(2,7,1),(0,8,0x10000),(2,7,13)):
            history=deepcopy(self.history);history[index][column]=value
            with self.subTest(index=index,column=column),self.assertRaises(ValueError):self.validate(self.pack(history))

    def test_branch_or_nonconsecutive_PC_cannot_be_hidden_in_the_suffix(self):
        history=deepcopy(self.history);history[1][0]+=4
        with self.assertRaises(ValueError):self.validate(self.pack(history))

    def test_wrong_frame_ordinal_target_or_sequence_is_rejected(self):
        for key,value in (('frame',4),('ordinal',2),('pc',self.target+4),('low',1),('count',0)):
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(self.pack(**{key:value}))

    def test_missing_truncated_extra_and_duplicate_events_are_rejected(self):
        data=self.pack()
        for changed in (b'',data[:-4],data+b'\0'*4,data+data):
            with self.subTest(bytes=len(changed)),self.assertRaises(ValueError):self.validate(changed)

    def test_unused_transport_tail_must_be_zero(self):
        data=bytearray(self.pack());data[-1]=1
        with self.assertRaisesRegex(ValueError,'Unused'):self.validate(bytes(data))

    def test_native_summary_cannot_hide_overflow_lost_entries_or_protocol_changes(self):
        for key,value in (('native_overflow',1),('native_total',2),('event_bytes',660),('protocol',2),
                          ('sites',[]),('game_RAM_injected',True),('CPU_source_modified',True)):
            summary=dict(self.summary,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(summary=summary)

    def test_only_canonical_unique_JALR_sites_are_selected(self):
        self.assertEqual(flow.flow_sites(self.program,self.image),[self.call])
        for values in ([f'0x{self.call:08X}']*2,['0x80010000'],[self.call],['0x80010091'],['0x8001008c']):
            with self.subTest(values=values),self.assertRaises(ValueError):
                flow.flow_sites(dict(method_trace=dict(flow_sites=values)),self.image)

    def test_lost_load_chain_or_plain_equal_table_cannot_prove_an_edge(self):
        for index in (0,2):
            history=deepcopy(self.history);history[index][1:3]=[0,0];history[index][7]=1
            with self.subTest(index=index),self.assertRaises(ValueError):self.validate(self.pack(history))


if __name__ == '__main__':
    unittest.main()
