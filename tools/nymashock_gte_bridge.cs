// Compile against a local BizHawk 2.11.1 installation; no game or BIOS is loaded.
// This uses fixed, checked native symbols, not the whole PS1 CPU or its timing.
using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using BizHawk.Emulation.Cores.Waterbox;
using BizHawk.BizInvoke;

public static class NymashockGteBridge {
    static string DllRoot;
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    static readonly string[,] Files = {
        {"shock.wbx.zst", "5c6fe90fadd670318ca74993911b171e15b167c7f2e1e88bf66de4661fc24126"},
        {"BizHawk.Common.dll", "15ebdf860bc1d8d9efcaabefe1df69de0b24f31d431b558621df353882f386b9"},
        {"BizHawk.BizInvoke.dll", "36784436af64e6547a1e6155071eab104ca09d9b2d5fe1d73c7282cee500bffb"},
        {"BizHawk.Emulation.Common.dll", "f557d94912b12bde18413b60d25b3e61332b7bbfc7184349d1289d6ba9f350ee"},
        {"BizHawk.Emulation.Cores.dll", "444bc157418e9b5df5d07e987fc7ad1d2d1c6993676f5b864368027cb4f054d5"},
        {"waterboxhost.dll", "e8e47426941a710c7ceea98fb0833b8387de1952f54ca0fa40001cd494507cee"}
    };
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool SetDllDirectory(string path);
    [DllImport("kernel32.dll")] static extern UIntPtr VirtualQuery(IntPtr address, out MemoryInfo info, UIntPtr size);
    [StructLayout(LayoutKind.Sequential)] struct MemoryInfo {
        public IntPtr BaseAddress, AllocationBase;
        public uint AllocationProtect;
        public UIntPtr RegionSize;
        public uint State, Protect, Type;
    }
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void Power();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void WriteDr(uint register, uint value);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int Instruction(uint instruction);
    public sealed class Request {
        public int id { get; set; }
        public uint command { get; set; }
        public uint[] cr { get; set; }
        public int[] ir { get; set; }
        public uint? lzcs { get; set; }
    }
    public sealed class Result {
        public int id { get; set; }
        public int[] mac { get; set; }
        public int[] ir { get; set; }
        public uint flags { get; set; }
        public int command_cycles_minus_one { get; set; }
    }
    static string Hash(byte[] bytes) {
        using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }
    static void CheckFiles() {
        for (int i = 0; i < Files.GetLength(0); i++)
            if (Hash(File.ReadAllBytes(Path.Combine(DllRoot, Files[i, 0]))) != Files[i, 1])
                throw new Exception("Pinned runtime differs: " + Files[i, 0]);
    }
    static void CheckMappedCode(long address, string expected) {
        MemoryInfo info;
        if (VirtualQuery(new IntPtr(address), out info, new UIntPtr((uint)Marshal.SizeOf(typeof(MemoryInfo)))) == UIntPtr.Zero ||
            info.State != 0x1000 || (info.Protect & 0x101) != 0 ||
            address + 64 > info.BaseAddress.ToInt64() + (long)info.RegionSize.ToUInt64())
            throw new Exception("Native function mapping unavailable: " + address.ToString("x"));
        byte[] bytes = new byte[64]; Marshal.Copy(new IntPtr(address), bytes, 0, bytes.Length);
        if (Hash(bytes) != expected) throw new Exception("Native function prefix differs: " + address.ToString("x"));
    }
    // CR writes and MAC reads were inlined by this build. Reproduce only the
    // reviewed CR 0..4 mask/cache transfer; execute native WriteDR and commands.
    // All supported commands overwrite MAC1..3 and IR1..3, use null translation,
    // and reset their flags, so reset-and-restore is equivalent for this subset.
    static Result Execute(Request request, Power power, WriteDr write, Instruction instruction) {
        if (request.cr == null || request.cr.Length != 5 || request.ir == null || request.ir.Length != 3 ||
            (request.command != 0x4A41E012 && request.command != 0x4A49E012 &&
             request.command != 0x4B70000C && request.command != 0x4AA00428))
            throw new Exception("Only reviewed MVMVA, OP and SQR commands are supported");
        foreach (int value in request.ir) if (value < -32768 || value > 32767) throw new Exception("IR input must be signed 16-bit");
        power();
        for (int i = 0; i < 5; i++) {
            uint value = request.cr[i] & (i == 4 ? 0xFFFFu : 0xFFFFFFFFu);
            Marshal.WriteInt32(new IntPtr(0x36F00299BD0 + i * 4), unchecked((int)value));
            Marshal.WriteInt32(new IntPtr(0x36F00299C50 + i * 4), unchecked((int)value));
        }
        for (uint i = 0; i < 3; i++) write(i + 9, unchecked((uint)request.ir[i]));
        int cycles = instruction(request.command);
        var result = new Result { id = request.id, mac = new int[3], ir = new int[3],
            flags = unchecked((uint)Marshal.ReadInt32(new IntPtr(0x36F00299BD0 + 31 * 4))), command_cycles_minus_one = cycles };
        for (int i = 0; i < 3; i++) {
            result.mac[i] = Marshal.ReadInt32(new IntPtr(0x36F00299D60 + (i + 1) * 4));
            result.ir[i] = Marshal.ReadInt16(new IntPtr(0x36F00299D20 + (i + 1) * 2));
        }
        return result;
    }
    // ReadDR was inlined; these two addresses are checked ELF symbols. WriteDR
    // computes the actual native leading-sign-bit count, including negative inputs.
    static object LeadingBits(Request request, Power power, WriteDr write) {
        if (!request.lzcs.HasValue) throw new Exception("LZCS input is required for command zero");
        power(); write(30, request.lzcs.Value);
        return new { id = request.id,
            lzcs = unchecked((uint)Marshal.ReadInt32(new IntPtr(0x36F00299D70))),
            lzcr = unchecked((uint)Marshal.ReadInt32(new IntPtr(0x36F00299D74))) };
    }
    public static int Main(string[] args) {
        try {
            if (args.Length != 1) throw new Exception("Pass the local BizHawk 2.11.1 runtime directory");
            DllRoot = Path.Combine(Path.GetFullPath(args[0]), "dll");
            CheckFiles();
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object sender, ResolveEventArgs e) {
                string file = Path.Combine(DllRoot, new AssemblyName(e.Name).Name + ".dll");
                return File.Exists(file) ? Assembly.LoadFrom(file) : null;
            };
            if (!SetDllDirectory(DllRoot)) throw new Exception("SetDllDirectory failed");
            Run(); CheckFiles(); return 0;
        } catch (Exception error) { Console.Error.WriteLine(error); return 2; }
    }
    static void Run() {
        var options = new WaterboxOptions { Path = DllRoot, Filename = "shock.wbx", SbrkHeapSizeKB = 16384,
            SealedHeapSizeKB = 49152, InvisibleHeapSizeKB = 49152, PlainHeapSizeKB = 49152, MmapHeapSizeKB = 49152 };
        using (var host = new WaterboxHost(options)) {
            host.Enter(); try {
                CheckMappedCode(0x36F0000598C, "abfe12f29241e6037e2006819311554540671851ab767a0fef4001533d8a1206");
                CheckMappedCode(0x36F00246800, "6aed11affb1a976c51bdf9ee77e4f4b40c954602f07e10de7b30a155326d9546");
                CheckMappedCode(0x36F00246A60, "98cddfef431746eb6b863ff1975851c3b537fc0b7202176d76a591a79848bbd6");
                var adapter = CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
                var power = adapter.GetDelegateForFunctionPointer<Power>(new IntPtr(0x36F0000598C));
                var write = adapter.GetDelegateForFunctionPointer<WriteDr>(new IntPtr(0x36F00246800));
                var instruction = adapter.GetDelegateForFunctionPointer<Instruction>(new IntPtr(0x36F00246A60));
                var identity = Execute(new Request { id = 0, command = 0x4A49E012, cr = new uint[] { 4096, 0, 4096, 0, 4096 },
                    ir = new int[] { 0, 0, 12345 } }, power, write, instruction);
                if (identity.mac[0] != 0 || identity.mac[1] != 0 || identity.mac[2] != 12345 || identity.flags != 0 ||
                    identity.command_cycles_minus_one != 7) throw new Exception("Native identity self-check differs");
                Console.WriteLine("GTE_READY " + Json.Serialize(identity)); Console.Out.Flush();
                string line;
                while ((line = Console.ReadLine()) != null) {
                    var request = Json.Deserialize<Request>(line);
                    if (request == null || request.id <= 0) throw new Exception("Positive request id required");
                    var result = request.command == 0 ? LeadingBits(request, power, write) :
                        (object)Execute(request, power, write, instruction);
                    Console.WriteLine("GTE_RESULT " + Json.Serialize(result)); Console.Out.Flush();
                }
            } finally { host.Exit(); }
        }
    }
}
