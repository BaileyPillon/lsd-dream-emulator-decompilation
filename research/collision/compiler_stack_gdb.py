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
outer_events = []
outer_errors = []
inline_errors = []
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


def rtl_name(address):
    table = int(gdb.parse_and_eval('(char *)&rtx_name'))
    name = word(table + 4 * (word(address) & 65535)) & 0xffffffff
    return gdb.parse_and_eval('(char *)' + str(name)).string()


def returned_stack_slot(address):
    """Decode the exact compiler's MEM(REG + byte offset), without calling it."""
    if rtl_name(address) != 'mem':
        raise ValueError('Outer allocator did not return a memory slot.')
    base = word(address + 4) & 0xffffffff
    offset = 0
    if rtl_name(base) == 'plus':
        left = word(base + 4) & 0xffffffff
        right = word(base + 8) & 0xffffffff
        if rtl_name(left) != 'reg' or rtl_name(right) != 'const_int':
            raise ValueError('Unsupported outer stack-slot address.')
        base, offset = left, word(right + 4)
    if rtl_name(base) != 'reg':
        raise ValueError('Outer stack slot has no virtual base register.')
    return {'base_register': word(base + 4), 'offset': offset}


def inline_storage_origin(allocator, requested_size):
    """Decode the two pinned copy_rtx_and_substitute allocation branches."""
    if allocator != 'assign_stack_temp':
        return None
    older = gdb.newest_frame().older()
    if older is None:
        return None
    pc = int(older.pc())
    branches = {0x080EE093: ('incoming_argument_block', 67),
                0x080EDFA5: ('inlined_local_frame', 68)}
    if older.name() != 'copy_rtx_and_substitute':
        if pc in branches:
            raise ValueError('Inline allocation return PC has an unexpected caller.')
        return None
    if pc not in branches:
        raise ValueError('Unknown inline stack allocation branch.')
    frame = int(older.read_register('ebp'))
    original = word(frame + 8) & 0xffffffff
    if rtl_name(original) != 'reg':
        raise ValueError('Inline allocation source is not a virtual register.')
    kind, number = branches[pc]
    incoming = symbol_word('virtual_incoming_args_rtx') & 0xffffffff
    local = symbol_word('virtual_stack_vars_rtx') & 0xffffffff
    if (rtl_name(incoming) != 'reg' or rtl_name(local) != 'reg'
            or word(incoming + 4) != 67 or word(local + 4) != 68
            or word(original + 4) != number):
        raise ValueError('Inline allocation branch and virtual-register identity disagree.')
    mapping = word(frame + 12) & 0xffffffff
    declaration = word(mapping + 4) & 0xffffffff
    identifier = word(declaration + 0x20) & 0xffffffff
    if not identifier:
        raise ValueError('Inline allocation has no callee name.')
    callee = gdb.parse_and_eval('(char *)' + str(word(identifier + 0x10) & 0xffffffff)).string()
    saved = word(declaration + 0x48) & 0xffffffff
    frame_size, argument_size = word(declaration + 0x44), word(saved + 0x24)
    expected_size = argument_size if kind == 'incoming_argument_block' else frame_size
    if min(frame_size, argument_size) < 0 or requested_size != expected_size:
        raise ValueError('Inline allocation size disagrees with callee metadata.')
    return {'kind': kind, 'virtual_register': number, 'caller_return_pc': hex(pc),
            'callee': callee, 'callee_frame_size': frame_size,
            'callee_argument_size': argument_size}


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
        result = int(gdb.parse_and_eval('$eax')) & 0xffffffff
        self.event['returned_rtx'] = hex(result)
        if self.event['inline_storage_origin'] is not None:
            try:
                self.event['inline_storage_slot'] = returned_stack_slot(result)
            except Exception as error:
                inline_errors.append(str(error))
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
            'inline_storage_origin': None, 'inline_storage_slot': None,
        }
        try:
            event['inline_storage_origin'] = inline_storage_origin(self.name, event['size'])
        except Exception as error:
            inline_errors.append(str(error))
        events.append(event)
        AllocationReturned(event)
        return False


class OuterReturned(gdb.FinishBreakpoint):
    def __init__(self, event):
        super().__init__(internal=True)
        self.event = event

    def stop(self):
        try:
            result = int(gdb.parse_and_eval('$eax')) & 0xffffffff
            self.event['returned_rtx'] = hex(result)
            self.event['returned_slot'] = returned_stack_slot(result)
            self.event['active_function_frame_after'] = symbol_word('frame_offset')
            self.event['completed'] = True
        except Exception as error:
            outer_errors.append(str(error))
        return False

    def out_of_scope(self):
        outer_errors.append('Outer allocator did not return.')


class OuterEntered(gdb.Breakpoint):
    def __init__(self):
        super().__init__('*assign_outer_stack_local', internal=True)

    def stop(self):
        stack = int(gdb.parse_and_eval('$esp'))
        event = {
            'sequence': len(outer_events), 'allocator': 'assign_outer_stack_local',
            'active_function': function_name(),
            'owner_context': hex(word(stack + 16) & 0xffffffff),
            'mode_number': word(stack + 4), 'size': word(stack + 8),
            'alignment': word(stack + 12),
            # This global describes the active nested function, not the owner.
            'active_function_frame_before': symbol_word('frame_offset'),
            'call_stack': call_stack(), 'completed': False,
        }
        outer_events.append(event)
        OuterReturned(event)
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
OuterEntered()
gdb.execute('run')
with open(os.environ['LSD_STACK_TRACE_REPORT'], 'x', encoding='utf-8') as destination:
    json.dump({'schema_version': 4, 'compiler_sha256': COMPILER_SHA256,
               'compiler_exited': gdb.selected_inferior().pid == 0,
               'compiler_exit_code': exit_code, 'allocation_events': events,
               'outer_allocation_events': outer_events,
               'outer_allocation_errors': outer_errors,
               'inline_allocation_errors': inline_errors,
               'normal_debugger_breakpoint_machinery': True,
               'explicit_inferior_memory_writes_or_opcode_substitutions': False,
               'extra_inferior_functions_invoked': False}, destination, indent=2)
    destination.write('\n')
print('Observed stack allocation events:', len(events))
print('Observed outer-scope allocation events:', len(outer_events))
