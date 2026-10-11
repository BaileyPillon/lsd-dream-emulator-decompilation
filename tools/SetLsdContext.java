// Establish the original PS1 global-pointer context before Ghidra analysis.
// @category LSD
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;

public class SetLsdContext extends GhidraScript {
    public void run() throws Exception {
        Register gp = currentProgram.getRegister("gp");
        if (gp == null) gp = currentProgram.getRegister("GP");
        if (gp == null) throw new IllegalStateException("MIPS global-pointer register is unavailable");
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (block.getStart().getAddressSpace().equals(currentProgram.getAddressFactory().getDefaultAddressSpace())) {
                currentProgram.getProgramContext().setValue(gp, block.getStart(), block.getEnd(),
                    new BigInteger("8008a808", 16));
            }
        }
        println("LSD original gp = 0x8008A808; analysis program: " + currentProgram.getName());
    }
}
