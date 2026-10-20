"""Read-only exception evidence for the pinned PS1 functional replay.

This decodes the retained core's CP0 fields and correlates them with functional
PC observations. It neither delivers an interrupt nor changes a comparison.
In particular, a compatible PC occurrence does not identify an interrupt cycle,
device, native instruction-cache entry, or complete pipeline state.
"""
import struct

RAM_BYTES = 0x200000
CPU_SOURCE_SHA256 = '4ddd7b0192db03ed1ce81bb9b83bd92a14a0c64e6e3c1633d05cf0e7b127aad7'
CPU_HEADER_SHA256 = '9705356dbb793421017daf1755c3f3838ff5b093d6b1620410fd5c23a60c014a'
CORE_COMMIT = '382ff1b8d293c9a862497706808cbb79b2cecbfb'


def qualify_core_profile(profile):
    """Bind this optional diagnostic to the captured observer's CPU sources."""
    if (not isinstance(profile, dict) or profile.get('mednafen_commit') != CORE_COMMIT
            or profile.get('existing_CPU_source_modified') is not False
            or not isinstance(profile.get('inputs'), list)):
        raise ValueError('Exception provenance requires the unmodified pinned CPU core profile.')
    wanted = {'cpu.cpp': CPU_SOURCE_SHA256, 'cpu.h': CPU_HEADER_SHA256}
    for name, expected in wanted.items():
        records = [item for item in profile['inputs'] if isinstance(item, dict)
                   and isinstance(item.get('path'), str)
                   and item['path'].replace('\\', '/').split('/')[-1] == name]
        if len(records) != 1 or records[0].get('sha256') != expected:
            raise ValueError('Captured CPU source provenance differs: ' + name)
    return dict(mednafen_commit=CORE_COMMIT, CPU_source_sha256=CPU_SOURCE_SHA256,
                CPU_header_sha256=CPU_HEADER_SHA256)


def _u32(value):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError('Require an architectural unsigned 32-bit word.')
    return value


def _word(memory, address):
    physical = address & 0x1fffffff
    if address % 4 or physical > len(memory) - 4:
        return None
    return struct.unpack_from('<I', memory, physical)[0]


def _owner(address, functions):
    matches = [item['function'] for item in functions
               if int(item['address'], 16) <= address < int(item['address'], 16) + item['bytes']]
    return matches[0] if len(matches) == 1 else None


def _branch_plan(pc, word):
    """Only static transfers reviewed for this diagnostic; no guest execution."""
    opcode, rt = word >> 26, (word >> 16) & 31
    if opcode in (2, 3):
        return dict(kind='jump', taken_target=((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2),
                    fallthrough=(pc + 8) & 0xffffffff, conditional=False)
    if opcode in (4, 5) or (opcode in (6, 7) and rt == 0) or (opcode == 1 and rt in (0, 1, 16, 17)):
        displacement = (word & 0xffff) - (0x10000 if word & 0x8000 else 0)
        return dict(kind='conditional_branch', taken_target=(pc + 4 + displacement * 4) & 0xffffffff,
                    fallthrough=(pc + 8) & 0xffffffff, conditional=True)
    return None


def inspect_context(row, memory, functions):
    """Interpret captured registers using pinned core rules and supplied code.

    The caller qualifies original function bytes and capture provenance. The
    core's Exception() sets ExcCode at bits 2..6, BDBT at bits 30..31 and CE
    from the interrupted instruction's bits 26..27. EPC points to the branch
    when BD is set. These are the pinned implementation's rules, including its
    instruction-derived CE bits; this is not a general hardware conformance test.
    """
    if len(memory) != RAM_BYTES:
        raise ValueError('Require complete captured 2 MiB RAM.')
    entry_epc, epc, cause = (_u32(row[name]) for name in ('entry_cpu_epc', 'cpu_epc', 'cpu_cause'))
    result = dict(core_commit=CORE_COMMIT, core_CPU_source_sha256=CPU_SOURCE_SHA256,
                  entry_EPC=entry_epc, returned_EPC=epc, returned_CAUSE=cause,
                  observed_EPC_transition=entry_epc != epc, exception_code=(cause >> 2) & 31,
                  branch_delay=bool(cause & 0x80000000), branch_taken=bool(cause & 0x40000000),
                  interrupts_replayed=False, native_timing_verified=False)
    if entry_epc == epc:
        return dict(result, status='no_observed_EPC_transition', issues=[])
    if result['exception_code'] != 0:
        return dict(result, status='other_exception_transition', issues=[])
    interrupted_pc = (epc + (4 if result['branch_delay'] else 0)) & 0xffffffff
    instruction, epc_word = _word(memory, interrupted_pc), _word(memory, epc)
    owner, epc_owner = _owner(interrupted_pc, functions), _owner(epc, functions)
    issues = []
    if instruction is None or epc_word is None:
        issues.append('EPC_or_interrupted_PC_not_in_aligned_RAM')
    if owner is None or epc_owner is None:
        issues.append('EPC_or_interrupted_PC_outside_qualified_function_ranges')
    ce = cause & 0x30000000
    if instruction is not None and ce != ((instruction << 2) & 0x30000000):
        issues.append('CAUSE_CE_disagrees_with_pinned_core_instruction_rule')
    if _u32(row['cpu_gpr_26']) != epc:
        issues.append('returned_K0_does_not_equal_returned_EPC')
    if not result['branch_delay'] and result['branch_taken']:
        issues.append('taken_bit_without_branch_delay_context')
    branch = _branch_plan(epc, epc_word) if result['branch_delay'] and epc_word is not None else None
    if result['branch_delay'] and branch is None:
        issues.append('branch_delay_transfer_not_reviewed')
    if branch is not None and not branch['conditional'] and not result['branch_taken']:
        issues.append('untaken_unconditional_jump_context')
    return dict(result, status='consistent_interrupt_register_context' if not issues else 'contradictory_or_unreviewed_interrupt_context',
                interrupted_PC=interrupted_pc, interrupted_function=owner, EPC_function=epc_owner,
                instruction_word=instruction, EPC_instruction_word=epc_word, CAUSE_CE_bits=ce,
                instruction_CE_bits=None if instruction is None else (instruction << 2) & 0x30000000,
                returned_K0=row['cpu_gpr_26'], branch=branch, issues=issues)


class ExceptionTrace:
    """Keep exact occurrence totals and a bounded sample of functional PCs."""
    def __init__(self, context, *, sample_limit=16):
        if type(sample_limit) is not int or not 0 <= sample_limit <= 256:
            raise ValueError('Choose a PC-detail limit from 0 through 256.')
        self.context, self.limit = context, sample_limit
        self.previous, self.pending = None, None
        self.occurrences, self.completed, self.compatible = 0, 0, 0
        self.samples = []
        self.branch_outcomes = dict(taken_target_only=0, fallthrough_only=0,
                                    indistinguishable_target_and_fallthrough=0, other_next_PC=0,
                                    missing_preceding_branch_or_unreviewed_transfer=0)

    def observe(self, address, instruction_index):
        if self.pending is not None:
            event, self.pending = self.pending, None
            event['next_PC'] = address
            compatible = self.context['status'] == 'consistent_interrupt_register_context'
            if self.context['branch_delay']:
                branch = self.context.get('branch')
                compatible = compatible and event['preceding_PC'] == self.context['returned_EPC'] and branch is not None
                if branch is not None and event['preceding_PC'] == self.context['returned_EPC']:
                    taken, fallthrough = address == branch['taken_target'], address == branch['fallthrough']
                    category = ('indistinguishable_target_and_fallthrough' if taken and fallthrough
                                else 'taken_target_only' if taken else 'fallthrough_only' if fallthrough else 'other_next_PC')
                    self.branch_outcomes[category] += 1
                    expected = branch['taken_target'] if self.context['branch_taken'] else branch['fallthrough']
                    compatible = compatible and address == expected
                else:
                    self.branch_outcomes['missing_preceding_branch_or_unreviewed_transfer'] += 1
            event['compatible_with_captured_context'] = bool(compatible)
            self.completed += 1
            self.compatible += bool(compatible)
            if len(self.samples) < self.limit:
                self.samples.append(event)
        if self.context.get('interrupted_PC') == address:
            self.occurrences += 1
            self.pending = dict(instruction_index=instruction_index, PC=address, preceding_PC=self.previous)
        self.previous = address

    def report(self):
        return dict(captured_context=self.context, functional_PC_occurrences=self.occurrences,
                    completed_PC_occurrences=self.completed, compatible_PC_occurrences=self.compatible,
                    unfinished_PC_occurrences=self.occurrences-self.completed,
                    retained_PC_details=self.samples, omitted_PC_details=self.completed-len(self.samples),
                    branch_transfer_outcomes=dict(self.branch_outcomes) if self.context['branch_delay'] else None,
                    interrupt_cycle_identified=False, interrupt_device_identified=False,
                    opaque_pipeline_or_cache_verified=False, interrupts_replayed=False,
                    full_game_parity_accepted=False)
