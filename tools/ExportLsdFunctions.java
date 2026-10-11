// Export Ghidra pseudocode as analysis evidence, not accepted matching source.
// @category LSD
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;

public class ExportLsdFunctions extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("Choose a new output directory");
        Path output = Path.of(args[0]);
        Files.createDirectory(output);
        Register gp = currentProgram.getRegister("gp");
        if (gp == null) gp = currentProgram.getRegister("GP");
        if (gp == null) throw new IllegalStateException("MIPS global-pointer register is unavailable");
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (block.getStart().getAddressSpace().equals(currentProgram.getAddressFactory().getDefaultAddressSpace())) {
                currentProgram.getProgramContext().setValue(gp, block.getStart(), block.getEnd(),
                    new BigInteger("8008a808", 16));
            }
        }
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        int completed = 0, failed = 0;
        StringBuilder index = new StringBuilder("address\tname\tbody_bytes\tstatus\n");
        try {
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext() && !monitor.isCancelled()) {
                Function function = functions.next();
                String address = function.getEntryPoint().toString();
                String name = function.getName();
                DecompileResults result = decompiler.decompileFunction(function, 20, monitor);
                boolean success = result.decompileCompleted() && result.getDecompiledFunction() != null;
                if (success) {
                    Files.writeString(output.resolve(address + "_" + name.replaceAll("[^A-Za-z0-9_.-]", "_") + ".c"),
                        "/* Ghidra analysis pseudocode; not original source or a verified C replacement. */\n" +
                        result.getDecompiledFunction().getC(), StandardCharsets.UTF_8);
                    completed++;
                } else failed++;
                index.append(address).append('\t').append(name).append('\t')
                    .append(function.getBody().getNumAddresses()).append('\t')
                    .append(success ? "decompiled" : "unavailable").append('\n');
            }
            Files.writeString(output.resolve("functions.tsv"), index, StandardCharsets.UTF_8);
            println("LSD analysis pseudocode: " + completed + " exported; " + failed + " unavailable.");
        } finally {
            decompiler.dispose();
        }
    }
}
