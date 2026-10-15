"""GDB-only backend for the bundled ELF32 i386 GCC compiler.

Reads cdecl arguments at allocator entry and observes their return using normal
GDB breakpoint machinery. It makes no additional explicit inferior-memory
writes or opcode substitutions, forces no results and invokes no extra inferior
functions. Source translation is performed by the existing compiler.
"""

import gdb
import hashlib
import json
import os
from pathlib import Path

COMPILER_SHA256 = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
compiler = Path(gdb.current_progspace().filename).resolve(strict=True)
if hashlib.sha256(compiler.read_bytes()).hexdigest() != COMPILER_SHA256:
    raise RuntimeError('Unsupported compiler for reload argument decoding.')

events = []
exit_code = None
active_alter_calls = []


def word(address):
    memory = gdb.selected_inferior().read_memory(address, 4).tobytes()
    return int.from_bytes(memory, 'little', signed=True)


def symbol_word(name):
    return word(int(gdb.parse_and_eval('(char *)&' + name)))


def function_name():
    value = gdb.parse_and_eval('(char *)*(unsigned int *)&current_function_name')
    return value.string(encoding='utf-8', errors='replace')


def call_stack():
    frames = []
    frame = gdb.newest_frame()
    while frame and len(frames) < 7:
        frames.append(frame.name())
        frame = frame.older()
    return frames


class AlterReturned(gdb.FinishBreakpoint):
    def __init__(self, context):
        super().__init__(internal=True)
        self.context = context

    def stop(self):
        if not active_alter_calls or active_alter_calls[-1] is not self.context:
            raise RuntimeError('Reload caller observations are incomplete or out of order.')
        active_alter_calls.pop()
        self.context['completed'] = True
        return False


class AlterEntered(gdb.Breakpoint):
    def __init__(self):
        super().__init__('*alter_reg', internal=True)

    def stop(self):
        stack = int(gdb.parse_and_eval('$esp'))
        context = {'pseudo': word(stack + 4), 'from_pseudo': word(stack + 8),
                   'function': function_name(), 'completed': False}
        active_alter_calls.append(context)
        AlterReturned(context)
        return False


class AllocationReturned(gdb.FinishBreakpoint):
    def __init__(self, event):
        super().__init__(internal=True)
        self.event = event

    def stop(self):
        self.event['frame_offset_after'] = symbol_word('frame_offset')
        self.event['returned_rtx'] = hex(int(gdb.parse_and_eval('$eax')))
        return False


class AllocationEntered(gdb.Breakpoint):
    def __init__(self, name):
        self.name = name
        super().__init__('*' + name, internal=True)

    def stop(self):
        stack = int(gdb.parse_and_eval('$esp'))
        event = {
            'sequence': len(events), 'function': function_name(), 'allocator': self.name,
            'mode_number': word(stack + 4), 'size': word(stack + 8),
            'align_or_keep': word(stack + 12),
            'frame_offset_before': symbol_word('frame_offset'),
            'temp_slot_level': symbol_word('temp_slot_level'), 'call_stack': call_stack(),
            'alter_reg_context': active_alter_calls[-1] if active_alter_calls else None,
        }
        events.append(event)
        AllocationReturned(event)
        return False


def compiler_exited(event):
    global exit_code
    exit_code = getattr(event, 'exit_code', None)


gdb.execute('set pagination off')
gdb.execute('set confirm off')
gdb.events.exited.connect(compiler_exited)
AlterEntered()
AllocationEntered('assign_stack_local')
AllocationEntered('assign_stack_temp')
gdb.execute('run')
with open(os.environ['LSD_STACK_TRACE_REPORT'], 'x', encoding='utf-8') as destination:
    json.dump({'schema_version': 2,
               'compiler_exited': gdb.selected_inferior().pid == 0,
               'compiler_exit_code': exit_code, 'allocation_events': events,
               'normal_debugger_breakpoint_machinery': True,
               'explicit_inferior_memory_writes_or_opcode_substitutions': False,
               'extra_inferior_functions_invoked': False}, destination, indent=2)
    destination.write('\n')
print('Observed stack allocation events:', len(events))
