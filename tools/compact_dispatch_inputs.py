"""Canonical selection inputs shared by compact recording and inspection."""
import json
from pathlib import Path

import configure
from research.compiler.compare_function import CANONICAL_SHA256
from tools import record_dispatch_history as legacy
from tools.compact_dispatch import sha
from tools.dispatch_trace import supplemental_profile, verified_selection
from tools.dispatch_returns import verified_return_selection
from tools.dispatch_flow import flow_windows
from tools.inventory_vtables import parse_symbols
from tools.replay_cold_start_headless import require
from tools.sdk_reads import RANGES, verified_sdk_selection

ROOT = Path(__file__).resolve().parents[1]

def selection_paths(program):
    require(program['method_trace'].get('sdk_reads') is True
            and not any(program['method_trace'].get(k) for k in ('heap_lifetime', 'cd_recovery', 'collision_calls')),
            'Compact SDK recording currently uses the original six-target SDK interface.')
    ranges, proof, _, _ = supplemental_profile(program)
    return dict(executable=ROOT / configure.ROM, catalogue=legacy.CATALOGUE_FILE,
                catalogue_provenance=legacy.CATALOGUE_PROVENANCE, ranges=ROOT / ranges,
                ranges_provenance=ROOT / proof, return_provenance=legacy.RETURN_PROVENANCE,
                sdk_ranges=RANGES, symbols=ROOT / configure.MAP_FILE,
                undefined_functions=ROOT / configure.UNDEF_FUNCS, undefined_symbols=ROOT / configure.UNDEF_SYMS)

def context(program, files):
    game = files['executable']
    require(sha(game) == CANONICAL_SHA256, 'Compact history requires the complete canonical executable.')
    selected = verified_selection(program, json.loads(files['catalogue']), json.loads(files['catalogue_provenance']),
        files['catalogue'], game, json.loads(files['ranges']), json.loads(files['ranges_provenance']), files['ranges'])
    returns = verified_return_selection(program, selected, game, json.loads(files['return_provenance']), files['return_provenance'])
    require(returns is not None, 'Require original Read/helper return selection.')
    returns['sdk_targets'] = verified_sdk_selection(program, game, json.loads(files['sdk_ranges']))
    require(returns['sdk_targets'] is not None, 'Require original SDK call/return selection.')
    symbols = parse_symbols(files['symbols'].decode(), [files[k].decode() for k in ('undefined_functions', 'undefined_symbols')])
    names = program['method_trace']['memory_symbols']
    require(all(name in symbols and symbols[name] % 4 == 0 and 0x80010000 <= symbols[name] <= 0x801ffffc for name in names),
            'A compact history memory symbol lacks an original address.')
    return dict(selected=selected, return_trace=returns, flow_sites=flow_windows(program, game),
                dispatch_targets=[dict(pc=pc, bytes=row['function_bytes']) for pc, row in selected.items()],
                dispatch_words=[symbols[name] for name in names])
