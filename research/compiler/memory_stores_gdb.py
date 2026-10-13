"""Read memory-store deletion decisions in the exact i386 matching compiler."""
from pathlib import Path
import hashlib
import json
import os
import gdb

SHA = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
compiler = Path(gdb.current_progspace().filename).resolve(strict=True)
assert hashlib.sha256(compiler.read_bytes()).hexdigest() == SHA
TARGET = os.environ['LSD_MEMORY_STORE_FUNCTION']
OUTPUT = Path(os.environ['LSD_MEMORY_STORE_REPORT'])
events, active = [], []
exit_code = None


def integer(address, width=4, signed=False):
    return int.from_bytes(gdb.selected_inferior().read_memory(address, width).tobytes(), 'little', signed=signed)


def address(name):
    return int(gdb.parse_and_eval('(char *)&' + name))


def global_pointer(name):
    return integer(address(name))


def table_string(name, index):
    if not 0 <= index < 256:
        raise RuntimeError('Unsupported compiler RTL table index.')
    return gdb.parse_and_eval('(char *)' + str(integer(address(name) + index * 4))).string()


def selected():
    pointer = global_pointer('current_function_name')
    return pointer != 0 and gdb.parse_and_eval('(char *)' + str(pointer)).string() == TARGET


def decode(pointer, depth=0):
    if pointer == 0:
        return None
    if depth > 4:
        return {'pointer': hex(pointer), 'depth_limit': True}
    name = table_string('rtx_name', integer(pointer, 2))
    result = {'pointer': hex(pointer), 'code': name, 'flags_raw': integer(pointer + 3, 1)}
    if name == 'reg':
        result['number'] = integer(pointer + 4)
    elif name == 'const_int':
        result['value'] = integer(pointer + 4, signed=True)
    elif name == 'mem':
        result['address'] = decode(integer(pointer + 4), depth + 1)
    elif name in ('set', 'plus'):
        result['left'] = decode(integer(pointer + 4), depth + 1)
        result['right'] = decode(integer(pointer + 8), depth + 1)
    return result


class DecisionReturned(gdb.FinishBreakpoint):
    def __init__(self, event):
        super().__init__(internal=True)
        self.event = event

    def stop(self):
        self.event['returned_dead'] = int(gdb.parse_and_eval('$eax'))
        self.event['last_mem_set_after'] = decode(global_pointer('last_mem_set'))
        assert active[-1] is self.event
        active.pop()
        return False


class DecisionEntered(gdb.Breakpoint):
    def __init__(self):
        super().__init__('*insn_dead_p', internal=True)

    def stop(self):
        if not selected():
            return False
        sp = int(gdb.parse_and_eval('$esp'))
        pointer = integer(sp + 4)
        pattern = decode(pointer)
        if pattern['code'] != 'set' or pattern['left']['code'] != 'mem':
            return False
        event = {'sequence': len(events), 'pattern': pattern,
                 'call_ok': integer(sp + 12), 'last_mem_set_before': decode(global_pointer('last_mem_set')),
                 'equality_calls': []}
        events.append(event)
        active.append(event)
        DecisionReturned(event)
        return False


class EqualReturned(gdb.FinishBreakpoint):
    def __init__(self, event):
        super().__init__(internal=True)
        self.event = event

    def stop(self):
        self.event['returned_equal'] = int(gdb.parse_and_eval('$eax'))
        return False


class EqualEntered(gdb.Breakpoint):
    def __init__(self):
        super().__init__('*rtx_equal_p', internal=True)

    def stop(self):
        if active:
            sp = int(gdb.parse_and_eval('$esp'))
            event = {'left': decode(integer(sp + 4)), 'right': decode(integer(sp + 8))}
            active[-1]['equality_calls'].append(event)
            EqualReturned(event)
        return False


def exited(event):
    global exit_code
    exit_code = getattr(event, 'exit_code', None)


gdb.execute('set pagination off')
gdb.execute('set confirm off')
gdb.events.exited.connect(exited)
DecisionEntered()
EqualEntered()
gdb.execute('run')
assert not active
with OUTPUT.open('x') as stream:
    json.dump({'target': TARGET, 'compiler_sha256': SHA,
               'compiler_exited': gdb.selected_inferior().pid == 0,
               'compiler_exit_code': exit_code, 'decisions': events,
               'normal_debugger_breakpoint_machinery': True,
               'explicit_inferior_memory_writes_or_opcode_substitutions': False,
               'extra_inferior_functions_invoked': False}, stream, indent=2)
    stream.write('\n')
