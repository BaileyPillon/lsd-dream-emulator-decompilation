"""GDB backend for the exact bundled i386 GCC 2.6.3 compiler."""
import hashlib
import json
import os
from pathlib import Path

import gdb

COMPILER_SHA256 = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
compiler = Path(gdb.current_progspace().filename).resolve(strict=True)
if hashlib.sha256(compiler.read_bytes()).hexdigest() != COMPILER_SHA256:
    raise RuntimeError('Unsupported compiler; do not decode its allocation tables.')

TARGET = os.environ['LSD_GLOBAL_TRACE_FUNCTION']
local_events = []
equivalence_events = []
allocation_events = []
comparison_events = []
exit_code = None


def integer(address, width=4, signed=True):
    return int.from_bytes(gdb.selected_inferior().read_memory(address, width).tobytes(),
                          'little', signed=signed)


def scalar(name):
    return integer(int(gdb.parse_and_eval('(char *)&' + name)))


def array(name, index, width=4):
    return integer((scalar(name) & 0xffffffff) + index * width, width)


def selected_function():
    return gdb.parse_and_eval('(char *)*(unsigned int *)&current_function_name').string() == TARGET


def pseudo_state(include_registers=False):
    maximum = scalar('max_regno')
    if not 71 <= maximum <= 65536:
        raise RuntimeError('Invalid pseudo-register table length.')
    state = {str(i): {'references': array('reg_n_refs', i),
                     'sets': array('reg_n_sets', i, 2),
                     'live_length': array('reg_live_length', i),
                     'calls_crossed': array('reg_n_calls_crossed', i)}
             for i in range(71, maximum)}
    # local_alloc initializes this table after update_equiv_regs returns.
    if include_registers:
        for pseudo, item in state.items():
            item['hard_register'] = array('reg_renumber', int(pseudo), 2)
    return state


class LocalReturned(gdb.FinishBreakpoint):
    def __init__(self, event, include_registers):
        super().__init__(internal=True)
        self.event = event
        self.include_registers = include_registers

    def stop(self):
        self.event['after'] = pseudo_state(self.include_registers)
        return False


class LocalEntered(gdb.Breakpoint):
    def __init__(self, name, events):
        super().__init__('*' + name, internal=True)
        self.events = events
        self.include_registers = name == 'local_alloc'

    def stop(self):
        if selected_function():
            event = {'sequence': len(self.events), 'before': pseudo_state()}
            self.events.append(event)
            LocalReturned(event, self.include_registers)
        return False


def allocno_state(number):
    if not 0 <= number < scalar('max_allocno'):
        raise RuntimeError('Invalid global allocation number.')
    pseudo = array('allocno_reg', number)
    return {'allocno': number, 'pseudo': pseudo,
            'references': array('allocno_n_refs', number),
            'live_length': array('allocno_live_length', number),
            'calls_crossed': array('allocno_calls_crossed', number),
            'size': array('allocno_size', number),
            'hard_register': array('reg_renumber', pseudo, 2)}


class GlobalReturned(gdb.FinishBreakpoint):
    def __init__(self, event):
        super().__init__(internal=True)
        self.event = event

    def stop(self):
        self.event['hard_register_after'] = array('reg_renumber', self.event['pseudo'], 2)
        return False


class GlobalEntered(gdb.Breakpoint):
    def __init__(self):
        super().__init__('*find_reg', internal=True)

    def stop(self):
        if selected_function():
            sp = int(gdb.parse_and_eval('$esp'))
            event = allocno_state(integer(sp + 4))
            event.update(sequence=len(allocation_events),
                         alternate_class=integer(sp + 12),
                         accept_call_clobbered=integer(sp + 16),
                         retrying=integer(sp + 20))
            allocation_events.append(event)
            GlobalReturned(event)
        return False


class ComparisonReturned(gdb.FinishBreakpoint):
    def __init__(self, event):
        super().__init__(internal=True)
        self.event = event

    def stop(self):
        result = int(gdb.parse_and_eval('$eax')) & 0xffffffff
        self.event['returned_comparison'] = result - 0x100000000 if result & 0x80000000 else result
        return False


class ComparisonEntered(gdb.Breakpoint):
    def __init__(self):
        super().__init__('*allocno_compare', internal=True)

    def stop(self):
        if selected_function():
            sp = int(gdb.parse_and_eval('$esp'))
            event = {'sequence': len(comparison_events),
                     'left': allocno_state(integer(integer(sp + 4, signed=False))),
                     'right': allocno_state(integer(integer(sp + 8, signed=False)))}
            comparison_events.append(event)
            ComparisonReturned(event)
        return False


def exited(event):
    global exit_code
    exit_code = getattr(event, 'exit_code', None)


gdb.execute('set pagination off')
gdb.execute('set confirm off')
gdb.events.exited.connect(exited)
LocalEntered('local_alloc', local_events)
LocalEntered('update_equiv_regs', equivalence_events)
GlobalEntered()
ComparisonEntered()
gdb.execute('run')
with Path(os.environ['LSD_GLOBAL_TRACE_REPORT']).open('x', encoding='utf-8') as destination:
    json.dump({'target': TARGET, 'compiler_exited': gdb.selected_inferior().pid == 0,
               'compiler_exit_code': exit_code, 'local_events': local_events,
               'equivalence_events': equivalence_events,
               'allocation_events': allocation_events, 'comparison_events': comparison_events,
               'normal_debugger_breakpoint_machinery': True,
               'explicit_inferior_memory_writes_or_opcode_substitutions': False,
               'extra_inferior_functions_invoked': False}, destination, indent=2)
    destination.write('\n')
