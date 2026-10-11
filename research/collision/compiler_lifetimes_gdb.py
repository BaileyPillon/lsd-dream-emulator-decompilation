"""GDB-only temporary-slot observer for the exact bundled i386 GCC compiler.

Normal GDB breakpoint machinery can instrument compiler memory. This backend
makes no additional explicit inferior-memory writes or opcode substitutions,
forces no results and invokes no extra inferior functions. The heap layout is
decoded only after checking the compiler file's SHA-256.
"""

import gdb
import hashlib
import json
import os
from pathlib import Path
import re

COMPILER_SHA256 = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
compiler = Path(gdb.current_progspace().filename)
if hashlib.sha256(compiler.read_bytes()).hexdigest() != COMPILER_SHA256:
    raise ValueError('Unsupported compiler identity; reject temporary-slot decoding.')
function = os.environ['LSD_LIFETIME_FUNCTION']
if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', function):
    raise ValueError('Invalid C function name.')
events = []
errors = []
exit_code = None


def word(address, signed=True):
    raw = gdb.selected_inferior().read_memory(address, 4).tobytes()
    return int.from_bytes(raw, 'little', signed=signed)


def global_word(name, signed=True):
    return word(int(gdb.parse_and_eval('(char *)&' + name)), signed)


def current_function():
    return gdb.parse_and_eval('(char *)*(unsigned int *)&current_function_name').string()


def frames():
    result = []
    frame = gdb.newest_frame()
    while frame and len(result) < 8:
        result.append(frame.name())
        frame = frame.older()
    return result


def slots():
    address = global_word('temp_slots', False)
    result = []
    seen = set()
    while address:
        if address in seen or len(result) >= 4096:
            raise ValueError('Repeated or unbounded compiler temporary-slot list.')
        seen.add(address)
        raw = gdb.selected_inferior().read_memory(address, 32).tobytes()

        def integer(offset, signed=False):
            return int.from_bytes(raw[offset:offset + 4], 'little', signed=signed)

        result.append({
            'node': hex(address), 'slot_rtx': hex(integer(4)),
            'address_rtx': hex(integer(8)), 'size': integer(12, True),
            'rtl_expr': hex(integer(16)), 'in_use': raw[20], 'addr_taken': raw[21],
            'level': integer(24, True), 'keep': integer(28, True),
        })
        address = integer(0)
    return result


def snapshot():
    return {'level': global_word('temp_slot_level'),
            'frame_offset': global_word('frame_offset'), 'slots': slots()}


class Returned(gdb.FinishBreakpoint):
    def __init__(self, event):
        super().__init__(internal=True)
        self.event = event

    def stop(self):
        try:
            self.event['after'] = snapshot()
            if self.event['operation'] == 'assign_stack_temp':
                self.event['returned_rtx'] = hex(int(gdb.parse_and_eval('$eax')) & 0xFFFFFFFF)
        except (gdb.error, ValueError) as error:
            errors.append(str(error))
            return True
        return False

    def out_of_scope(self):
        errors.append('An observed lifetime call did not return: ' + self.event['operation'])


class Entered(gdb.Breakpoint):
    def __init__(self, name):
        self.name = name
        super().__init__('*' + name, internal=True)

    def stop(self):
        try:
            if current_function() != function:
                return False
            stack_pointer = int(gdb.parse_and_eval('$esp'))
            event = {'sequence': len(events), 'operation': self.name, 'function': function,
                     'call_stack': frames(), 'before': snapshot()}
            if self.name == 'assign_stack_temp':
                event['arguments'] = [word(stack_pointer + offset) for offset in (4, 8, 12)]
            elif self.name in ('preserve_temp_slots', 'mark_temp_addr_taken'):
                event['argument_rtx'] = hex(word(stack_pointer + 4, False))
            events.append(event)
            Returned(event)
        except (gdb.error, ValueError) as error:
            errors.append(str(error))
            return True
        return False


def exited(event):
    global exit_code
    exit_code = getattr(event, 'exit_code', None)


gdb.execute('set pagination off')
gdb.execute('set confirm off')
gdb.events.exited.connect(exited)
for operation in ('assign_stack_temp', 'preserve_temp_slots', 'mark_temp_addr_taken',
                  'pop_temp_slots', 'free_temp_slots'):
    Entered(operation)
gdb.execute('run')
with open(os.environ['LSD_LIFETIME_REPORT'], 'x', encoding='utf-8') as destination:
    json.dump({'compiler_exited': gdb.selected_inferior().pid == 0,
               'compiler_exit_code': exit_code, 'lifetime_events': events, 'trace_errors': errors,
               'normal_debugger_breakpoint_machinery': True,
               'explicit_inferior_memory_writes_or_opcode_substitutions': False,
               'extra_inferior_functions_invoked': False}, destination, indent=2)
    destination.write('\n')
print('Observed compiler lifetime events:', len(events))
