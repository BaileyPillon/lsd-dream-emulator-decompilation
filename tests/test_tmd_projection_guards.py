"""Execute small delay-slot programs through the renderer's memory guards."""
import struct
import unittest

try:
    import unicorn
    from unicorn import mips_const as reg
except ImportError:
    unicorn = None

from tools.verify_tmd_projection import Machine


@unittest.skipUnless(unicorn, 'Optional Unicorn synthetic backend is not installed')
class ProjectionGuardTests(unittest.TestCase):
    def machine(self, slot):
        machine = Machine.__new__(Machine)
        machine.u,machine.r = unicorn,reg
        cpu = machine.cpu = unicorn.Uc(unicorn.UC_ARCH_MIPS,
            unicorn.UC_MODE_MIPS32|unicorn.UC_MODE_LITTLE_ENDIAN)
        cpu.mem_map(0,0x200000,unicorn.UC_PROT_READ|unicorn.UC_PROT_EXEC)
        cpu.mem_protect(0x120000,4096,unicorn.UC_PROT_READ|unicorn.UC_PROT_WRITE)
        words = (0x080065B3,slot,0x34020001,0x03E00008,0)
        cpu.mem_write(0x196C0,struct.pack('<5I',*words))
        cpu.mem_write(0x120100,struct.pack('<I',0x12345678))
        cpu.reg_write(reg.UC_MIPS_REG_RA,0x1FF000)
        cpu.reg_write(reg.UC_MIPS_REG_A1,0x120100)
        cpu.reg_write(reg.UC_MIPS_REG_V1,0x150000)
        machine.write_ranges = [(0x120130,0x120134)]
        machine.lower,machine.upper,machine.cop2_words = 0x196C0,0x196D4,{}
        def instruction(c,address,size,unused):
            word, = struct.unpack('<I',c.mem_read(address&0x1FFFFFFF,4))
            machine.guard_integer_memory(word)
            machine.guard_branch_delay(word,address)
        cpu.hook_add(unicorn.UC_HOOK_CODE,instruction)
        return machine

    def test_store_delay_slot_returns_with_exact_memory_change(self):
        machine = self.machine(0xACA30030)
        before = bytearray(machine.cpu.mem_read(0,0x200000))
        struct.pack_into('<I',before,0x120130,0x150000)
        machine.cpu.emu_start(0x800196C0,0x1FF000,count=20)
        self.assertEqual(machine.cpu.reg_read(reg.UC_MIPS_REG_PC),0x1FF000)
        self.assertEqual(bytes(machine.cpu.mem_read(0,0x200000)),bytes(before))

    def test_load_delay_slot_returns_and_reads_original_word(self):
        machine = self.machine(0x8CA30000)
        before = bytes(machine.cpu.mem_read(0,0x200000))
        machine.cpu.emu_start(0x800196C0,0x1FF000,count=20)
        self.assertEqual(machine.cpu.reg_read(reg.UC_MIPS_REG_PC),0x1FF000)
        self.assertEqual(machine.cpu.reg_read(reg.UC_MIPS_REG_V1),0x12345678)
        self.assertEqual(bytes(machine.cpu.mem_read(0,0x200000)),before)

    def test_forbidden_store_in_delay_slot_cannot_write(self):
        machine = self.machine(0xACA30034)
        before = bytes(machine.cpu.mem_read(0,0x200000))
        with self.assertRaisesRegex(ValueError,'left guarded spans'):
            machine.cpu.emu_start(0x800196C0,0x1FF000,count=20)
        self.assertEqual(bytes(machine.cpu.mem_read(0,0x200000)),before)

    def test_read_alignment_and_instruction_scope_are_enforced(self):
        for instruction,base,message in ((0x8CA30000,0x11FFFC,'left guarded spans'),
                (0x84A30001,0x120100,'Unaligned integer memory'),
                (0x88A30000,0x120100,'Unreviewed integer memory')):
            with self.subTest(instruction=hex(instruction)):
                machine = self.machine(instruction)
                machine.cpu.reg_write(reg.UC_MIPS_REG_A1,base)
                with self.assertRaisesRegex(ValueError,message):
                    machine.cpu.emu_start(0x800196C0,0x1FF000,count=20)


if __name__ == '__main__':
    unittest.main()
