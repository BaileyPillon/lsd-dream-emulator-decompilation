"""Qualify actual receiver/table/slot loads in bounded native caller context.

This reads before-instruction operands and RAM load words. It accepts only a
canonical LW/LW/JALR suffix with both MIPS load-delay gaps. An original direct
jump to a shared tail needs its captured delay slot and exact destination.
An equal table entry without that executed context never establishes an edge.
"""
from collections import Counter
import struct

from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require

EVENT_BYTES = 664
HISTORY = 16
FLOW_EXPORTS = ('LsdResetDispatchFlow', 'LsdAddDispatchFlowSite', 'LsdStartDispatchFlow',
    'LsdBeginDispatchFlowFrame', 'LsdGetDispatchFlowCount', 'LsdGetDispatchFlowTotal',
    'LsdGetDispatchFlowOverflow', 'LsdGetDispatchFlowEvents')


def flow_sites(program, executable):
    values = program['method_trace'].get('flow_sites', [])
    require(isinstance(values, list) and len(values) <= 16 and all(
        isinstance(value, str) and len(value) == 10 and value.startswith('0x')
        and all(c in '0123456789ABCDEF' for c in value[2:]) for value in values),
        'Use at most sixteen canonical hexadecimal flow call sites.')
    sites = [int(value, 16) for value in values]
    require(len(sites) == len(set(sites)), 'Flow call sites must be unique.')
    for site in sites:
        require(site % 4 == 0 and 0x8001003C <= site < 0x801FFFFC, 'Invalid flow call site window.')
        offset = executable_offset(executable, site - 60, 68)
        word = struct.unpack_from('<I', executable, offset + 60)[0]
        require(word & 0xFC1F07FF == 9 and (word >> 11) & 31 == 31,
                'A flow site must be an original JALR with the normal return register.')
    return sites


def flow_windows(program, executable):
    sites = flow_sites(program, executable)
    extra = program['method_trace'].get('flow_context_sites', [])
    require(isinstance(extra,list) and len(sites)+len(extra)<=16 and all(
        isinstance(value,str) and len(value)==10 and value.startswith('0x')
        and all(c in '0123456789ABCDEF' for c in value[2:]) for value in extra),
        'Use at most sixteen total canonical caller-context windows.')
    anchors = sites+[int(value,16) for value in extra]
    require(len(anchors)==len(set(anchors)), 'Caller-context windows must have unique anchors.')
    require(not extra or sites, 'Additional caller context requires selected original call sites.')
    for anchor in anchors:
        require(anchor%4==0 and 0x8001003C<=anchor<0x801FFFFC,'Invalid caller-context window.')
        executable_offset(executable,anchor-60,68)
    return anchors


def written_register(word):
    """Conservative decoder for the straight-line compiler suffix we accept."""
    op, rt, rd = word >> 26, (word >> 16) & 31, (word >> 11) & 31
    if op == 0 and word & 63 in (0, 2, 3, 4, 6, 7, 32, 33, 34, 35, 36, 37, 38, 39, 42, 43):
        return rd
    if op in (8, 9, 10, 11, 12, 13, 14, 15, 32, 33, 35, 36, 37):
        return rt
    if op in (40, 41, 43):
        return 0
    if op == 2:  # A non-linking direct jump can join an original shared tail.
        return 0
    raise ValueError('Unsupported instruction in a virtual load-chain suffix.')


def _last_definition(history, before, register):
    for index in range(before - 1, -1, -1):
        if not history[index][7] & 1:
            break
        if written_register(history[index][2]) == register:
            return index
    raise ValueError('A virtual load-chain definition is missing from the captured suffix.')


def prove_edge(entry, history, executable, sites, windows=None):
    windows = sites if windows is None else windows
    require(len(history) >= 5, 'Insufficient native caller history.')
    call_index = len(history) - 2
    call, delay = history[-2:]
    require(call[0] == entry['transfer_pc'] in sites and delay[0] == call[0] + 4
            and (call[2], delay[2]) == (entry['transfer_word'], entry['delay_word']),
            'Native flow transfer/delay context differs from the method entry.')
    word = call[2]
    require(word & 0xFC1F07FF == 9 and (word >> 11) & 31 == 31
            and call[3] == entry['pc'] and entry['ra'] == call[0] + 8,
            'Native JALR target operand or link differs from the observed method.')
    target_register = (word >> 21) & 31
    require(target_register != 0, 'JALR cannot use a zero target register.')
    slot_index = _last_definition(history, call_index, target_register)
    slot = history[slot_index]
    require(slot[2] >> 26 == 35 and slot_index <= call_index - 2,
            'A slot target must come from LW with its original load-delay gap.')
    slot_offset = slot[2] & 0xFFFF
    require(slot_offset in (0x44, 0x54), 'This evidence supports only Open/Read virtual slots.')
    table_register = (slot[2] >> 21) & 31
    table_index = _last_definition(history, slot_index, table_register)
    table = history[table_index]
    require(table[2] >> 26 == 35 and table[2] & 0xFFFF == 0 and table_index <= slot_index - 2,
            'A receiver table must come from LW +0 with its original load-delay gap.')
    table_pc = entry['a0_word_00']
    require(table[3] == table[5] == entry['a0'] and table[6] == slot[3] == table_pc
            and slot[5] == (table_pc + slot_offset) & 0xFFFFFFFF
            and slot[6] == entry['pc'] == entry['a0_table_word_' + f'{slot_offset:03X}'],
            'Executed receiver/table/slot load values disagree with the entry snapshots.')
    suffix = history[table_index:]
    for index, observed in enumerate(suffix):
        pc, ram_word, fetch_word, rs, rt, address, loaded, flags, sr, _ = observed
        require(flags & 1 and flags & ~7 == 0 and not sr & 0x10000,
                'The load chain lacks qualified RAM context or enables cache isolation.')
        require(any(anchor-60<=pc<=anchor+4 for anchor in windows),
                'Observed caller context lies outside the configured native windows.')
        offset = executable_offset(executable, pc, 4)
        require(ram_word == fetch_word == struct.unpack_from('<I', executable, offset)[0],
                'A RAM or effective instruction word differs from the original caller.')
        if index:
            expected = suffix[index-1][0]+4
            if index>=2 and suffix[index-2][2]>>26==2:
                jump=suffix[index-2]
                expected=((jump[0]+4)&0xF0000000)|((jump[2]&0x03FFFFFF)<<2)
            require(pc == expected, 'The load-chain PC sequence disagrees with its direct jump/delay path.')
            if suffix[index-1][2]>>26==2:
                require(fetch_word>>26!=2,'An original shared-tail jump cannot have a branch in its delay slot.')
                written_register(fetch_word)
        if index < len(suffix) - 2:
            written_register(fetch_word)
        if fetch_word >> 26 == 35:
            immediate = ((fetch_word & 0xFFFF) ^ 0x8000) - 0x8000
            require(flags & 4 and address == (rs + immediate) & 0xFFFFFFFF
                    and not address & 3 and (address & 0x1FFFFFFF) <= 0x1FFFFC,
                    'An observed LW lacks a valid aligned RAM load word.')
        else:
            require(not flags & 4 and address == loaded == 0, 'Unexpected non-LW memory observation.')
    # The delay slot executes before callee entry. It must not branch or trap.
    require(delay[2]>>26!=2,'A method JALR cannot have a direct jump in its delay slot.')
    written_register(delay[2])
    return dict(source=f'0x{call[0]:08X}', target=f"0x{entry['pc']:08X}",
        receiver=f"0x{entry['a0']:08X}", table=f'0x{table_pc:08X}', slot=f'0x{slot_offset:02X}',
        receiver_table_load=f'0x{table[0]:08X}', method_slot_load=f'0x{slot[0]:08X}')


def validate_flow(data, summary, entries, program, executable):
    sites = flow_sites(program, executable)
    windows = flow_windows(program, executable)
    require(sites, 'A flow history requires declared original call sites.')
    require(summary.get('protocol') == 1 and summary.get('event_bytes') == EVENT_BYTES
            and summary.get('history_instructions') == HISTORY
            and summary.get('entries') == summary.get('native_total') == len(entries)
            and summary.get('native_overflow') == 0 and summary.get('sites') == windows
            and summary.get('game_RAM_injected') is False and summary.get('CPU_source_modified') is False
            and summary.get('instruction_cache_peek_only') is True,
            'Native flow protocol, counts, source or overflow disagree.')
    require(len(data) == EVENT_BYTES * len(entries), 'Truncated, extra or missing native flow records.')
    edges, previous_sequence, counts = [], -1, Counter()
    for index, entry in enumerate(entries):
        words = struct.unpack_from('<166I', data, index * EVENT_BYTES)
        frame, ordinal, pc, count, low, high = words[:6]
        sequence = low | high << 32
        require(frame == entry['relative_frame'] and ordinal == index + 1 and pc == entry['pc']
                and 0 < count <= HISTORY and count == min(sequence, HISTORY) and sequence > previous_sequence,
                'Flow ordinal, target, history extent or instruction sequence differs from its entry.')
        previous_sequence = sequence
        require(not any(words[6 + count * 10:]), 'Unused native flow transport words must be zero.')
        history = [words[6 + n * 10:16 + n * 10] for n in range(count)]
        edge = prove_edge(entry, history, executable, sites, windows)
        key = (edge['source'], edge['target'], edge['table'], edge['slot'])
        counts[key] += 1
        edges.append(dict(relative_frame=frame, ordinal=ordinal, **edge))
    return dict(protocol=1, accepted_entry_slot_chains=len(edges), distinct_source_target_pairs=len(
        {(edge['source'], edge['target']) for edge in edges}),
        distinct_table_slot_edges=len({(edge['table'], edge['slot'], edge['target']) for edge in edges}),
        table_addresses=len({edge['table'] for edge in edges}),
        chains=[dict(source=key[0], target=key[1], table=key[2], slot=key[3], entries=count)
                for key, count in sorted(counts.items())],
        scope='Executed canonical before-instruction receiver/table/slot load chains for these entries; no return, completion, entire method or whole feature acceptance.'), edges
