// A dedicated analysis host for the pinned Nymashock GTE, without a game/BIOS.
// Native WriteDR and command execution are retained. The inlined CR cache
// transfer and architectural reads are reviewed against the pinned gte.cpp.
using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using BizHawk.Emulation.Cores.Waterbox;
using BizHawk.BizInvoke;

public static class NymashockGteStateBridge {
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    static string DllRoot, Fault;
    const long CR = 0x36F00299BD0, Matrices = 0x36F00299C50, CV = 0x36F00299CA0;
    const long Vectors = 0x36F00299D00, RGB = 0x36F00299D18, OTZ = 0x36F00299D1C;
    const long IR = 0x36F00299D20, XY = 0x36F00299D30, Z = 0x36F00299D40;
    const long RGBFifo = 0x36F00299D48, MAC = 0x36F00299D60;
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
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void NativeVoid();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void NativeWrite(uint register, uint value);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int NativeCommand(uint command);
    public sealed class Request {
        public int id { get; set; }
        public bool reset { get; set; }
        // Each write is [0=CR or 1=DR, register number, unsigned word].
        public uint[][] writes { get; set; }
        public uint? command { get; set; }
    }
    public sealed class Snapshot {
        public int id { get; set; }
        public uint[] cr { get; set; }
        public uint[] dr { get; set; }
        public int? command_cycles_minus_one { get; set; }
        public long native_data_writes { get; set; }
        public long native_commands { get; set; }
    }
    static long NativeDataWrites, NativeCommands;
    static uint U32(long address) { return unchecked((uint)Marshal.ReadInt32(new IntPtr(address))); }
    static uint S16(long address) { return unchecked((uint)(int)Marshal.ReadInt16(new IntPtr(address))); }
    static uint U16(long address) { return unchecked((ushort)Marshal.ReadInt16(new IntPtr(address))); }
    static void Put32(long address, uint value) { Marshal.WriteInt32(new IntPtr(address), unchecked((int)value)); }
    static void Put16(long address, uint value) { Marshal.WriteInt16(new IntPtr(address), unchecked((short)value)); }
    static string Hash(byte[] value) {
        using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(value)).Replace("-", "").ToLowerInvariant();
    }
    static void CheckFiles() {
        for (int i = 0; i < Files.GetLength(0); i++)
            if (Hash(File.ReadAllBytes(Path.Combine(DllRoot, Files[i, 0]))) != Files[i, 1])
                throw new Exception("Pinned runtime differs: " + Files[i, 0]);
    }
    static void CheckMapping(long address, int size) {
        MemoryInfo info;
        if (VirtualQuery(new IntPtr(address), out info, new UIntPtr((uint)Marshal.SizeOf(typeof(MemoryInfo)))) == UIntPtr.Zero ||
            info.State != 0x1000 || (info.Protect & 0x101) != 0 ||
            address + size > info.BaseAddress.ToInt64() + (long)info.RegionSize.ToUInt64())
            throw new Exception("Pinned native mapping unavailable: " + address.ToString("x"));
    }
    static void CheckCode(long address, string expected) {
        CheckMapping(address, 64);
        byte[] code = new byte[64]; Marshal.Copy(new IntPtr(address), code, 0, code.Length);
        if (Hash(code) != expected) throw new Exception("Pinned native function prefix differs");
    }
    static void WriteControl(uint register, uint value) {
        uint mask = register == 4 || register == 12 || register == 20 || register == 26 ||
                    register == 27 || register == 29 || register == 30 ? 0xFFFFu : 0xFFFFFFFFu;
        uint word = value & mask;
        Put32(CR + 4*register, (U32(CR + 4*register) & ~mask) | word);
        if (register < 24) {
            uint block = register / 8, field = register % 8;
            if (field < 5) {
                if (!(Fault == "wrong-light-cache" && block == 1))
                    Put32(Matrices + 20*block + 4*field, word);
            } else if (!(Fault == "wrong-translation-cache" && register == 5)) {
                Put32(CV + 16*block + 4*(field-5), word);
            }
            return;
        }
        switch (register) {
            case 24: Put32(0x36F00299CE0, word); break;
            case 25: Put32(0x36F00299CE4, word); break;
            case 26: Put16(0x36F00299CE8, word); break;
            case 27: Put16(0x36F00299CEA, word); break;
            case 28: Put32(0x36F00299CEC, word); break;
            case 29: Put16(0x36F00299CF0, word); break;
            case 30: Put16(0x36F00299CF2, word); break;
            case 31: Put32(CR+124, (word & 0x7FFFF000u) | ((word & 0x7F87E000u) != 0 ? 0x80000000u : 0)); break;
        }
    }
    static uint ReadControl(int register) {
        if (register == 4 || register == 12 || register == 20) return S16(CR+4*register);
        switch (register) {
            case 24: return U32(0x36F00299CE0);
            case 25: return U32(0x36F00299CE4);
            case 26: return S16(0x36F00299CE8);
            case 27: return S16(0x36F00299CEA);
            case 28: return U32(0x36F00299CEC);
            case 29: return S16(0x36F00299CF0);
            case 30: return S16(0x36F00299CF2);
            default: return U32(CR+4*register);
        }
    }
    static uint ReadData(int register) {
        if (register <= 5) return register % 2 == 0 ? U32(Vectors+4*register) : S16(Vectors+4*register);
        if (register == 6) return U32(RGB);
        if (register == 7) return U16(OTZ);
        if (register <= 11) return S16(IR+2*(register-8));
        if (register <= 15) return U32(XY+4*(register-12));
        if (register <= 19) return U16(Z+2*(register-16));
        if (register <= 22) return U32(RGBFifo+4*(register-20));
        if (register == 23) return U32(0x36F00299D78);
        if (register <= 27) return U32(MAC+4*(register-24));
        if (register <= 29) {
            uint packed = 0;
            for (int i = 0; i < 3; i++) {
                int component = Marshal.ReadInt16(new IntPtr(IR+2*(i+1))) >> 7;
                packed |= (uint)Math.Max(0, Math.Min(31, component)) << (5*i);
            }
            return packed;
        }
        return U32(register == 30 ? 0x36F00299D70 : 0x36F00299D74);
    }
    static Snapshot State(int id, int? cycles) {
        var state = new Snapshot { id=id, cr=new uint[32], dr=new uint[32], command_cycles_minus_one=cycles,
            native_data_writes=NativeDataWrites, native_commands=NativeCommands };
        for (int i = 0; i < 32; i++) { state.cr[i]=ReadControl(i); state.dr[i]=ReadData(i); }
        return state;
    }
    static bool Supported(uint command) {
        if ((command & 0xFE000000u) != 0x4A000000u) return false;
        switch (command & 63) {
            case 1: case 6: case 0x10: case 0x12: case 0x13: case 0x16:
            case 0x1B: case 0x2D: case 0x2E: case 0x30: case 0x3F: return true;
            default: return false;
        }
    }
    static void Run() {
        var options = new WaterboxOptions { Path=DllRoot, Filename="shock.wbx", SbrkHeapSizeKB=16384,
            SealedHeapSizeKB=49152, InvisibleHeapSizeKB=49152, PlainHeapSizeKB=49152, MmapHeapSizeKB=49152 };
        using (var host = new WaterboxHost(options)) {
            host.Enter(); try {
                CheckCode(0x36F00005918, "46d61c4e6ae5fb58193e3fce7a4365bb2fa496162a0fd074d95a8e3db30a6ba5");
                CheckCode(0x36F0000598C, "abfe12f29241e6037e2006819311554540671851ab767a0fef4001533d8a1206");
                CheckCode(0x36F00246800, "6aed11affb1a976c51bdf9ee77e4f4b40c954602f07e10de7b30a155326d9546");
                CheckCode(0x36F00246A60, "98cddfef431746eb6b863ff1975851c3b537fc0b7202176d76a591a79848bbd6");
                CheckMapping(CR, 0x1B0);
                var adapter = CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
                var init = adapter.GetDelegateForFunctionPointer<NativeVoid>(new IntPtr(0x36F00005918));
                var power = adapter.GetDelegateForFunctionPointer<NativeVoid>(new IntPtr(0x36F0000598C));
                var write = adapter.GetDelegateForFunctionPointer<NativeWrite>(new IntPtr(0x36F00246800));
                var command = adapter.GetDelegateForFunctionPointer<NativeCommand>(new IntPtr(0x36F00246A60));
                if (Fault != "skip-reciprocal-init") init();
                power();
                Console.WriteLine("GTE_STATE_READY " + Json.Serialize(State(0, null))); Console.Out.Flush();
                string line; int previous=0;
                while ((line=Console.ReadLine()) != null) {
                    if (line.Length > 65536) throw new Exception("Request exceeds byte bound");
                    Request request = Json.Deserialize<Request>(line);
                    if (request == null || request.id <= previous || request.writes == null || request.writes.Length > 1024 ||
                        (request.command.HasValue && !Supported(request.command.Value)))
                        throw new Exception("Invalid bounded state request");
                    previous=request.id;
                    if (request.reset) power();
                    foreach (uint[] operation in request.writes) {
                        if (operation == null || operation.Length != 3 || operation[0] > 1 || operation[1] >= 32)
                            throw new Exception("Invalid register write");
                        if (operation[0] == 0) WriteControl(operation[1], operation[2]);
                        else {
                            write(Fault == "wrong-screen-fifo" && operation[1] == 15 ? 14u : operation[1], operation[2]);
                            NativeDataWrites++;
                        }
                    }
                    int? cycles=null;
                    if (request.command.HasValue) { cycles=command(request.command.Value); NativeCommands++; }
                    Console.WriteLine("GTE_STATE " + Json.Serialize(State(request.id, cycles))); Console.Out.Flush();
                }
            } finally { host.Exit(); }
        }
    }
    public static int Main(string[] args) {
        try {
            if (args.Length < 1 || args.Length > 2 || !BitConverter.IsLittleEndian)
                throw new Exception("Pass the existing runtime and optional qualification control");
            Fault=args.Length == 2 ? args[1] : "";
            if (Fault != "" && Fault != "wrong-light-cache" && Fault != "wrong-translation-cache" &&
                Fault != "wrong-screen-fifo" && Fault != "skip-reciprocal-init")
                throw new Exception("Unknown qualification control");
            DllRoot=Path.Combine(Path.GetFullPath(args[0]), "dll");
            CheckFiles();
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object sender, ResolveEventArgs e) {
                string path=Path.Combine(DllRoot, new AssemblyName(e.Name).Name+".dll");
                return File.Exists(path) ? Assembly.LoadFrom(path) : null;
            };
            if (!SetDllDirectory(DllRoot)) throw new Exception("SetDllDirectory failed");
            Run(); CheckFiles(); return 0;
        } catch (Exception error) { Console.Error.WriteLine(error); return 2; }
    }
}
