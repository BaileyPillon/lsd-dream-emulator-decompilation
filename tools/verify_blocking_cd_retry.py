"""Qualify original blocking CD retries from canonical native call/return records.

Failed snapshots verify only the SDK-reported written prefix. Unwritten tails
are retained by hash and never accepted as transferred disc data. Original Read
returns remain status words, not byte counts. This is a bounded scenario proof.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compact_dispatch import sha
from tools.dispatch_returns import Form1Disc, bcd_lba, sequence, _frame
from tools.inspect_compact_dispatch import inspect_details
from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require, write_json

def tray_window(program, frames):
    actions = {'Open Tray': [], 'Close Tray': []}
    start = 1
    for segment in program['segments']:
        require('Reset' not in segment['pressed'], 'Blocking retry qualification must recover without Reset.')
        for name in actions:
            if name in segment['pressed'] and start <= frames:
                require(segment['until'] == start, 'Tray actions must have one explicit submitted input frame.')
                actions[name].append(start)
        start = segment['until'] + 1
    require(all(len(v) == 1 for v in actions.values())
            and program['controller']['axes'].get('Disk Index') == 0, 'Require one tray-open/close pair on disc index zero.')
    opened, closed = actions['Open Tray'][0], actions['Close Tray'][0]
    require(program['method_trace']['arm_frame'] < opened < closed < frames, 'Tray interruption lies outside its qualified window.')
    return opened, closed

def verify_transfers(records, payload, summary, stream):
    disc = Form1Disc(stream)
    timeline = sorted((sequence(row, prefix), phase, row) for row in records
                      for prefix, phase in (('entry_', 0), ('', 1)))
    position = pending = None
    entry_positions, endings, sync_errors, seeks, rejected = {}, [], [], [], []
    busy = 0
    for seq, phase, row in timeline:
        kind = row['kind']
        if phase == 0:
            if kind == 1:
                require(pending is None and row['a0'] > 0 and row['a2'] == 0x80, 'Overlapping or unsupported SDK request.')
                entry_positions[row['entry_id']] = position
            continue
        if kind == 3 and row['a0'] == 2 and row['v0'] == 1:
            require(pending is None and row['arg_readable'] == 1 and row['a1'] != 0, 'Setloc lacks its observed original argument.')
            position = bcd_lba(row['arg_word_0'])
            seeks.append(dict(entry_id=row['entry_id'], lba=position, sequence=seq))
        elif kind == 4 and row['v0'] == 5:
            require(pending is None, 'CdSync error overlaps an unclassified SDK transfer.')
            position = None
            sync_errors.append(row['entry_id'])
        elif kind == 1:
            require(row['v0'] in (0, 1), 'Unsupported original SDK request result.')
            if row['v0'] == 0:
                rejected.append(row['entry_id'])
            else:
                require(entry_positions[row['entry_id']] is not None, 'SDK request has no observed logical position.')
                require((row['sdk_word_1'], row['sdk_word_2'], row['sdk_word_4'], row['sdk_word_5']) ==
                        (row['a0'], row['a1'], 0x80, 512), 'SDK backend differs from original request arguments.')
                pending = dict(request_id=row['entry_id'], lba=entry_positions[row['entry_id']], sectors=row['a0'],
                               destination=row['a1'], request_frame=row['entry_frame'])
        require((row['transfer_id'], row['transfer_sectors'], row['transfer_mode']) ==
                ((pending['request_id'], pending['sectors'], 0x80) if pending else (0, 0, 0)), 'SDK pending transfer identity differs.')
        if kind == 2:
            require(pending is not None, 'SDK poll has no original pending request.')
            if 0 < row['v0'] < 0x80000000:
                busy += 1
                require(row['buffer_status'] == row['buffer_bytes'] == row['buffer_address'] == 0, 'Busy SDK poll claims completed data.')
                continue
            require(row['v0'] in (0, 0xffffffff), 'Unsupported original terminal SDK result.')
            success = row['v0'] == 0
            require((row['buffer_status'], row['buffer_address'], row['buffer_bytes']) ==
                    (1 if success else 5, pending['destination'], pending['sectors'] * 2048), 'Successful/failed RAM snapshots are confused.')
            require((row['sdk_word_1'], row['sdk_word_2'], row['sdk_word_4'], row['sdk_word_5']) ==
                    (pending['sectors'], pending['destination'], 0x80, 512), 'Terminal SDK backend metadata differs.')
            written = row['sdk_word_3'] - pending['destination']
            require(0 <= written <= row['buffer_bytes'] and written % 2048 == 0, 'SDK written prefix escapes its sector window.')
            data = payload[row['buffer_offset']:row['buffer_offset'] + row['buffer_bytes']]
            require(len(data) == row['buffer_bytes'], 'Terminal SDK snapshot is incomplete.')
            require(not success or written == row['buffer_bytes'], 'Successful SDK result lacks a complete write cursor.')
            require(data[:written] == disc.extent(pending['lba'], written), 'SDK written prefix differs from the observed disc sectors.')
            endings.append({**pending, 'terminal_id': row['entry_id'], 'terminal_frame': row['frame'], 'success': success,
                            'requested_bytes': len(data), 'written_prefix_bytes': written,
                            'full_snapshot_sha256': sha(data), 'verified_prefix_sha256': sha(data[:written])})
            position = pending['lba'] + pending['sectors'] if success else None
            pending = None
        else:
            require(row['buffer_status'] == row['buffer_bytes'] == row['buffer_address'] == 0, 'A non-poll SDK boundary claims read data.')
    require(pending is None and sum(r['success'] for r in endings) == summary['completions']
            and sum(not r['success'] for r in endings) == summary['failed_transfers']
            and summary['unassociated_polls'] == summary['overlapping_requests'] == 0, 'SDK terminal totals or pending state disagree.')
    return dict(endings=endings, sync_error_ids=sync_errors, seek_calls=seeks, rejected_request_ids=rejected, busy_polls=busy)

def helper_calls(executable, settings):
    start, size = settings['helper_pc'], settings['helper_bytes']
    offset = executable_offset(executable, start, size)
    targets = {row['pc']: row['kind'] for row in settings['sdk_targets']}
    calls = {}
    for index, (word,) in enumerate(struct.iter_unpack('<I', executable[offset:offset + size])):
        if word >> 26 != 3:
            continue
        pc = start + index * 4
        target = ((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2)
        if target in targets:
            kind = targets[target]
            require(kind not in calls, 'Helper has ambiguous direct SDK call sites.')
            calls[kind] = pc
    require(set(calls) == {1, 2, 3, 4} and calls[1] == settings['request_call'] and calls[2] == settings['poll_call'],
            'Complete canonical helper SDK call-site selection differs.')
    return calls, _frame(executable, start, size)

def link_helpers(returns, return_payload, sdk, sdk_payload, transfers, settings, executable, opened, closed):
    calls, frame_bytes = helper_calls(executable, settings)
    setup = executable_offset(executable, calls[3] - 8, 4)
    word = struct.unpack_from('<I', executable, setup)[0]
    require(word >> 16 == 0x2605 and word & 0x8000 == 0, 'Canonical helper lacks its original a1 receiver-relative Setloc argument.')
    location_offset = word & 0xffff
    by_id, sdk_by_id = ({r['entry_id']: r for r in rows} for rows in (returns, sdk))
    endings = {r['request_id']: r for r in transfers['endings']}
    helpers, failed_helper_ids, retry_edges, rejected_setloc = [], [], [], []
    covered_failures, covered_sync_errors = set(), set()
    for helper in (r for r in returns if r['kind'] == 2):
        start, stop = sequence(helper, 'entry_'), sequence(helper)
        inside = sorted((r for r in sdk if start < sequence(r, 'entry_') < sequence(r) < stop), key=lambda r: sequence(r, 'entry_'))
        requests, polls = ([r for r in inside if r['kind'] == kind] for kind in (1, 2))
        require(len(requests) == helper['read_request_entries'] >= 1
                and len(polls) == helper['read_poll_entries'] == helper['read_poll_returns'] >= 1, 'Helper and SDK request/poll counts differ.')
        for row in inside:
            require(row['kind'] in calls and row['entry_ra'] == calls[row['kind']] + 8 and row['entry_jump_pc'] == calls[row['kind']]
                    and row['entry_sp'] == helper['entry_sp'] - frame_bytes, 'An SDK call escapes its canonical helper call/stack boundary.')
            if row['kind'] == 3:
                require(row['a0'] == 2 and row['a1'] == helper['a0'] + location_offset
                        and row['a2'] == 0 and row['v0'] in (0, 1) and row['arg_readable'] == 1,
                        'Helper Setloc invocation or acknowledgement is unqualified.')
                if row['v0'] == 0:
                    later = [r for r in inside if sequence(r, 'entry_') > sequence(row)]
                    require(later and (later[0]['kind'], later[0]['v0']) == (4, 5),
                            'Rejected helper Setloc does not reach the observed CdSync error before retry.')
                    rejected_setloc.append(dict(helper_entry_id=helper['entry_id'], setloc_id=row['entry_id'], sync_error_id=later[0]['entry_id']))
            if row['kind'] == 4:
                require(row['a0'] == 0, 'Helper changed its original blocking CdSync mode.')
        require(all((r['a0'], r['a1'], r['a2']) == (helper['a2'] >> 11, helper['a1'], 0x80) for r in requests),
                'Blocking reissue changed original count, destination or mode.')
        require(sequence(requests[-1], 'entry_') == sequence(helper, 'request_') and sequence(polls[-1]) == sequence(helper, 'poll_')
                and (polls[-1]['frame'], polls[-1]['timestamp'], polls[-1]['v0']) ==
                    (helper['last_poll_frame'], helper['last_poll_timestamp'], helper['last_poll_value']), 'Final helper request/poll identity differs.')
        require(all(r['v0'] == 1 and r['entry_id'] in endings for r in requests), 'A blocking request lacks an accepted terminal transfer.')
        chain = [endings[r['entry_id']] for r in requests]
        require(all(not r['success'] for r in chain[:-1]) and chain[-1]['success']
                and all((r['lba'], r['sectors'], r['destination']) == (chain[0]['lba'], chain[0]['sectors'], chain[0]['destination']) for r in chain),
                'Blocking helper has a changed seek/reissue or returns before its final successful transfer.')
        require(all(bcd_lba(r['arg_word_0']) == chain[0]['lba'] for r in inside if r['kind'] == 3),
                'A requestless Setloc/CdSync retry changed the original logical position.')
        errors = [r for r in inside if (r['kind'] == 2 and r['v0'] == 0xffffffff) or (r['kind'] == 4 and r['v0'] == 5)]
        for error in errors:
            later = [r for r in inside if sequence(r, 'entry_') > sequence(error)]
            require(later and (later[0]['kind'], later[0]['a0'], later[0]['entry_jump_pc']) == (3, 2, calls[3]),
                    'Failed blocking SDK boundary does not retry through its original Setloc call.')
            retry_edges.append(dict(helper_entry_id=helper['entry_id'], error_id=error['entry_id'],
                                    error_kind=error['kind'], next_setloc_id=later[0]['entry_id']))
            (covered_failures if error['kind'] == 2 else covered_sync_errors).add(error['entry_id'])
        final = sdk_by_id[chain[-1]['terminal_id']]
        require(final is polls[-1], 'Final blocking success differs from the original final helper poll.')
        parent = by_id[helper['parent_id']]
        left = sdk_payload[final['buffer_offset']:final['buffer_offset'] + final['buffer_bytes']]
        middle = return_payload[helper['buffer_offset']:helper['buffer_offset'] + helper['buffer_bytes']]
        right = return_payload[parent['buffer_offset']:parent['buffer_offset'] + parent['buffer_bytes']]
        require(left == middle == right, 'Successful SDK/helper/enclosing Read buffers differ.')
        if len(chain) > 1:
            require(helper['entry_frame'] < opened <= chain[0]['terminal_frame'] < closed < chain[-1]['terminal_frame'] <= helper['frame'],
                    'Interrupted blocking helper does not enclose the declared tray failure and recovery.')
            failed_helper_ids.append(helper['entry_id'])
        helpers.append(dict(entry_id=helper['entry_id'], entry_frame=helper['entry_frame'], return_frame=helper['frame'],
                            request_count=len(requests), poll_count=len(polls), failed_transfers=len(chain)-1,
                            first_request_id=chain[0]['request_id'], successful_request_id=chain[-1]['request_id'],
                            completion_id=chain[-1]['terminal_id'], completion_frame=chain[-1]['terminal_frame'],
                            lba=chain[-1]['lba'], sectors=chain[-1]['sectors'], bytes=len(left), final_data_sha256=sha(left)))
    require(len(failed_helper_ids) == 1 and covered_failures == {r['terminal_id'] for r in transfers['endings'] if not r['success']}
            and covered_sync_errors == set(transfers['sync_error_ids']) and not transfers['rejected_request_ids'],
            'SDK failures are not all associated with the one original blocking retry episode.')
    return dict(helpers=helpers, interrupted_helper_ids=failed_helper_ids, canonical_call_sites={str(k): f'0x{v:08X}' for k, v in calls.items()},
                original_helper_frame_bytes=frame_bytes, Setloc_receiver_offset=location_offset,
                error_to_setloc_edges=retry_edges, rejected_setloc_to_sync_errors=rejected_setloc,
                failed_buffer_tails_accepted=False, status_words_treated_as_byte_counts=False)

def inspect(folder):
    data = inspect_details(folder)
    require(data['report']['observing'], 'Blocking retry qualification requires the original native observer.')
    opened, closed = tray_window(data['program'], data['settings']['frames'])
    disc = Path(data['run']['source_manifest']['disc']['tracks'][0]['path'])
    with disc.open('rb') as stream:
        transfers = verify_transfers(data['sdk'], data['sdk_payload'], data['sdk_summary'], stream)
    require(transfers['sync_error_ids'] and any(not r['success'] for r in transfers['endings']), 'Both original error paths were not observed.')
    linked = link_helpers(data['returns'], data['return_payload'], data['sdk'], data['sdk_payload'], transfers,
                          data['settings']['return_trace'], data['executable'], opened, closed)
    success = [r for r in transfers['endings'] if r['success']]
    failed = [r for r in transfers['endings'] if not r['success']]
    return dict(status='qualified_original_blocking_cd_retry', open_frame=opened, close_frame=closed,
                compact_history=data['report'], successful_transfers=len(success), failed_transfers=len(failed),
                successful_sector_bytes_compared=sum(r['written_prefix_bytes'] for r in success),
                failed_written_prefix_bytes_compared=sum(r['written_prefix_bytes'] for r in failed),
                CdSync_error_returns=len(transfers['sync_error_ids']), blocking_retry=linked,
                transfer_history=transfers, new_C_bytes=0, whole_feature_groups_accepted=0,
                scope='Canonical native boundaries and actual disc data for this controller-only retry episode. No whole-method, whole-game, complete-state or hardware-timing acceptance.')

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect(args.folder)
        if args.output is not None: write_json(args.output, report)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(status='rejected', error=str(error))), file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in report.items() if k not in ('transfer_history', 'compact_history', 'blocking_retry')}
                     | {'helpers': report['blocking_retry']['helpers']}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
