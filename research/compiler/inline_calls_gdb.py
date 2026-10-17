"""GDB-only inline-call observer for the pinned ELF32 i386 GCC 2.6.3.

Normal breakpoint machinery may temporarily instrument compiler memory. This
backend makes no additional explicit inferior-memory writes, substitutes no
opcodes or results, and invokes no extra inferior functions.
"""
import gdb
import hashlib
import json
import os
from pathlib import Path

COMPILER_SHA256 = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
compiler = Path(gdb.current_progspace().filename).resolve(strict=True)
if hashlib.sha256(compiler.read_bytes()).hexdigest() != COMPILER_SHA256:
    raise RuntimeError('Unsupported compiler for inline argument decoding.')
target = os.environ['LSD_INLINE_TARGET']
helper = os.environ.get('LSD_INLINE_HELPER') or None
events, active = [], []
exit_code = None


def integer(address, width=4):
    return int.from_bytes(gdb.selected_inferior().read_memory(address, width).tobytes(), 'little')


def string(pointer):
    return gdb.parse_and_eval('(char *)' + str(pointer)).string(encoding='utf-8', errors='replace') if pointer else None


def global_pointer(name):
    return integer(int(gdb.parse_and_eval('(char *)&' + name)))


def table_string(table, index):
    if not 0 <= index < 256:
        raise RuntimeError('Compiler table index is outside the supported profile.')
    base = int(gdb.parse_and_eval('(char *)&' + table))
    if table == 'tree_code_name':
        base = integer(base)
    return string(integer(base + 4 * index))


def decl_name(declaration):
    identifier = integer(declaration + 0x20)
    return string(integer(identifier + 0x10)) if identifier else None


def type_info(pointer):
    if not pointer:
        raise RuntimeError('Missing compiler type node.')
    return dict(pointer=hex(pointer), code=table_string('tree_code_name', integer(pointer + 8, 1)),
                mode=table_string('mode_name', integer(pointer + 0x1D, 1)),
                readonly=bool(integer(pointer + 8) & 0x2000), volatile=bool(integer(pointer + 8) & 0x1000),
                main_variant=hex(integer(pointer + 0x44)), uid=integer(pointer + 0x18),
                alignment=integer(pointer + 0x20))


class Returned(gdb.FinishBreakpoint):
    def __init__(self, context):
        super().__init__(internal=True)
        self.context = context

    def stop(self):
        if not active or active[-1] is not self.context:
            raise RuntimeError('Inline-call observations are incomplete or out of order.')
        event = self.context['event']
        if event is not None:
            event['return_value'] = hex(int(gdb.parse_and_eval('$eax')) & 0xFFFFFFFF)
            event['completed'] = True
        active.pop()
        return False


class Entered(gdb.Breakpoint):
    def __init__(self):
        super().__init__('*expand_inline_function', internal=True)

    def stop(self):
        stack = int(gdb.parse_and_eval('$esp'))
        declaration, actual = integer(stack + 4), integer(stack + 8)
        name = decl_name(declaration)
        caller = string(global_pointer('current_function_name'))
        event = None
        if caller == target and (helper is None or name == helper):
            formal = integer(declaration + 0x28)
            arguments = []
            while formal:
                if len(arguments) >= 32:
                    raise RuntimeError('Inline argument list exceeds the supported diagnostic bound.')
                arg = dict(name=decl_name(formal), formal_node=hex(formal),
                           formal_type=type_info(integer(formal + 4)),
                           promoted_type=type_info(integer(formal + 0x30)))
                if actual:
                    expression = integer(actual + 0x10)
                    arg['actual_type'] = type_info(integer(expression + 4))
                    arg['same_type_identity'] = integer(formal + 4) == integer(expression + 4)
                    actual = integer(actual)
                else:
                    arg['missing_actual'] = True
                arguments.append(arg)
                formal = integer(formal)
            event = dict(sequence=len(events), function=name, caller=caller, arguments=arguments,
                         rejections=[], completed=False)
            events.append(event)
        context = {'event': event}
        active.append(context)
        Returned(context)
        return False


class Rejected(gdb.Breakpoint):
    def __init__(self):
        # Both mode and BLK identity failures converge here in the pinned binary.
        super().__init__('*0x080ebd75', internal=True)

    def stop(self):
        if not active:
            raise RuntimeError('Argument gate observed without an active inline call.')
        event = active[-1]['event']
        if event is None:
            return False
        frame = int(gdb.parse_and_eval('$ebp'))
        formal = integer(frame - 0xC0)
        expression = integer(frame - 0x24)
        formal_type = type_info(integer(formal + 4))
        promoted_type = type_info(integer(formal + 0x30))
        actual_type = type_info(integer(expression + 4))
        reason = ('argument_mode_mismatch' if promoted_type['mode'] != actual_type['mode']
                  else 'BLK_type_identity_mismatch' if promoted_type['mode'] == 'BLK'
                  and formal_type['pointer'] != actual_type['pointer'] else None)
        event['rejections'].append(dict(gate='argument_mode_or_BLK_type_identity',
            formal_node=hex(formal), argument=decl_name(formal), reason=reason,
            formal_type=formal_type, promoted_type=promoted_type, actual_type=actual_type))
        return False


def exited(event):
    global exit_code
    exit_code = getattr(event, 'exit_code', None)


gdb.execute('set pagination off')
gdb.execute('set confirm off')
gdb.events.exited.connect(exited)
Entered()
Rejected()
gdb.execute('run')
with Path(os.environ['LSD_INLINE_REPORT']).open('x', encoding='utf-8') as stream:
    json.dump(dict(schema_version=1, target=target, helper=helper,
        compiler_sha256=COMPILER_SHA256, compiler_exited=gdb.selected_inferior().pid == 0,
        compiler_exit_code=exit_code, call_stack_balanced=not active, events=events,
        normal_debugger_breakpoint_machinery=True,
        explicit_inferior_memory_writes_or_opcode_substitutions=False,
        extra_inferior_functions_invoked=False), stream, indent=2)
    stream.write('\n')
print('Observed selected inline calls:', len(events))
