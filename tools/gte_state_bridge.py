"""Bounded client and explicit COP2 transfer boundary for the native GTE host."""
from collections import Counter
import os
from pathlib import Path
import queue
import struct
import subprocess
import threading
import time

from tools.gte_state_model import require, signed, unsigned


class NativeStateBridge:
    def __init__(self, executable, runtime, error_log, fault='', exchange=None):
        import json
        self.json, self.exchange = json, exchange
        self.executable = Path(executable).resolve()
        require(self.executable.is_file(), 'Compile a fresh native state bridge first.')
        self.errors = Path(error_log).open('x', encoding='utf-8')
        command = [str(self.executable), str(runtime)] + ([fault] if fault else [])
        options = dict(creationflags=subprocess.CREATE_NO_WINDOW) if os.name == 'nt' else {}
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.errors, text=True, bufsize=1, **options)
        self.lines = queue.Queue(maxsize=64)
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()
        self.id, self.startup_bytes, self.state = 0, 0, None
        try:
            ready = self._read('GTE_STATE_READY ')
            require(ready['id'] == 0 and ready['cr'] == ready['dr'] == [0]*32
                    and ready['native_commands'] == ready['native_data_writes'] == 0,
                    'Native GTE initial architectural state differs.')
            self.state = ready
        except BaseException:
            self.close()
            raise

    def _pump(self):
        try:
            while True:
                line = self.process.stdout.readline(65538)
                if not line:
                    break
                if len(line) > 65536 or not line.endswith('\n'):
                    self.lines.put(ValueError('Native GTE output line exceeds its bound.'))
                    break
                self.lines.put(line)
        except (OSError, ValueError) as error:
            self.lines.put(error)
        finally:
            self.lines.put(None)

    def _read(self, prefix):
        deadline = time.monotonic()+30
        while True:
            try:
                line = self.lines.get(timeout=max(0.001, deadline-time.monotonic()))
            except queue.Empty as error:
                raise ValueError('Native GTE response exceeded its 30-second bound.') from error
            if isinstance(line, Exception):
                raise ValueError('Native GTE output reader failed.') from line
            require(line is not None, 'Native state bridge ended before its response; inspect retained stderr.')
            if line.startswith(prefix):
                return self.json.loads(line[len(prefix):])
            self.startup_bytes += len(line.encode())
            require(self.startup_bytes <= 65536, 'Native startup output exceeds its bound.')

    def request(self, reset=False, writes=(), command=None):
        require(type(reset) is bool and len(writes) <= 1024, 'Invalid bounded native state request.')
        self.id += 1
        request = dict(id=self.id, reset=reset, writes=[list(row) for row in writes], command=command)
        encoded = self.json.dumps(request, separators=(',', ':'))+'\n'
        require(len(encoded.encode()) <= 65536, 'Native state request exceeds its byte bound.')
        self.process.stdin.write(encoded)
        self.process.stdin.flush()
        observed = self._read('GTE_STATE ')
        require(observed.get('id') == self.id and set(observed) == {'id', 'cr', 'dr',
            'command_cycles_minus_one', 'native_data_writes', 'native_commands'}, 'Native response schema/id differs.')
        require(all(type(observed[k]) is list and len(observed[k]) == 32
            and all(type(v) is int and 0 <= v <= 0xFFFFFFFF for v in observed[k]) for k in ('cr', 'dr')),
            'Native register snapshot is not 64 complete unsigned words.')
        for key in ('native_data_writes', 'native_commands'):
            require(type(observed[key]) is int and observed[key] >= self.state[key], 'Native counters regressed.')
        require((observed['command_cycles_minus_one'] is None) == (command is None), 'Native command result missing or extra.')
        if self.exchange:
            self.exchange(request, observed)
        self.state = observed
        return {key:value for key, value in observed.items() if key != 'id'}

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=30)
            code = -1
        self.thread.join(timeout=1)
        self.process.stdout.close()
        self.errors.close()
        require(code == 0, 'Native state bridge did not close successfully; stderr retained.')


class Cop2StateAdapter:
    """Actual native commands; explicit architectural loads/stores and delays.

    Integer branch instructions still execute in Unicorn. A COP2 delay-slot
    adaptation resumes at their independently decoded target. Branches inside
    delay slots, branch-likely and coprocessor branches are rejected.
    """
    def __init__(self, bridge, read_word, write_word):
        self.bridge, self.read_word, self.write_word = bridge, read_word, write_word
        self.pending, self.delay, self.counts = [], None, Counter()

    def reset(self, writes):
        self.pending, self.delay = [], None
        return self.bridge.request(True, writes)

    def flush(self, command=None):
        if self.pending or command is not None:
            self.bridge.request(False, self.pending, command)
            self.pending = []
        return self.bridge.state

    @staticmethod
    def branch_target(word, address, get_register):
        op, rs, rt = word >> 26, word >> 21 & 31, word >> 16 & 31
        after = unsigned(address+8)
        if op in (2, 3):
            return unsigned(((address+4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2))
        if op == 0 and word & 63 in (8, 9):
            return unsigned(get_register(rs))
        if op == 1:
            require(rt in (0, 1, 16, 17), 'Unreviewed REGIMM branch variant.')
            taken = signed(get_register(rs)) < 0 if rt in (0, 16) else signed(get_register(rs)) >= 0
        elif op == 4:
            taken = unsigned(get_register(rs)) == unsigned(get_register(rt))
        elif op == 5:
            taken = unsigned(get_register(rs)) != unsigned(get_register(rt))
        elif op == 6:
            taken = signed(get_register(rs)) <= 0
        elif op == 7:
            taken = signed(get_register(rs)) > 0
        else:
            require(op not in (20, 21, 22, 23) and not (op in (16, 17, 18, 19) and rs == 8),
                    'Unreviewed likely/coprocessor branch.')
            return None
        return unsigned(address+4+(signed(word, 16) << 2)) if taken else after

    def step(self, word, address, get_register, set_register, set_pc):
        delay = self.delay if self.delay is not None and self.delay[0] == address else None
        self.delay = None
        op, rs, rt, rd = word >> 26, word >> 21 & 31, word >> 16 & 31, word >> 11 & 31
        handled = op in (0x32, 0x3A) or op == 0x12
        if not handled:
            target = self.branch_target(word, address, get_register)
            require(not (delay is not None and target is not None), 'Branch inside a delay slot is outside scope.')
            if target is not None:
                self.delay = (unsigned(address+4), target)
            return False
        if op in (0x32, 0x3A):
            at = unsigned(get_register(rs)+signed(word, 16))
            require(at % 4 == 0, 'Unaligned COP2 memory transfer.')
            if op == 0x32:
                self.pending.append((1, rt, self.read_word(at)))
                self.counts['lwc2'] += 1
            else:
                self.write_word(at, self.flush()['dr'][rt])
                self.counts['swc2'] += 1
        elif rs >= 16:
            self.flush(word)
            self.counts['command'] += 1
        else:
            require(word & 0x7FF == 0 and rs in (0, 2, 4, 6), 'Unreviewed COP2 register encoding.')
            if rs in (4, 6):
                self.pending.append((0 if rs == 6 else 1, rd, unsigned(get_register(rt))))
            else:
                set_register(rt, self.flush()['cr' if rs == 2 else 'dr'][rd])
            self.counts[{0:'mfc2', 2:'cfc2', 4:'mtc2', 6:'ctc2'}[rs]] += 1
        require(len(self.pending) <= 1024, 'Pending COP2 transfers exceed their bound.')
        if delay is not None:
            self.counts['cop2_delay_slots'] += 1
        set_pc(delay[1] if delay is not None else unsigned(address+4))
        return True
