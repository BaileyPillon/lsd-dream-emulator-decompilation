// Full-buffer digests from a separate native observer; no guest memory writes.
using System;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
internal sealed class MoviePayloadTrace : IDisposable {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint Number();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Pointer();
    readonly WaterboxHost Host;
    readonly Number Count, NativeTotal, Errors, Overflow, DataBytes, Callbacks, PendingVlc, PendingBuffers;
    readonly Pointer Events, Data;
    readonly Stream File;
    readonly GZipStream Zipped;
    readonly BinaryWriter Writer;
    readonly BoundedSha256Stream Chain = new BoundedSha256Stream(32L * 1024 * 1024);
    readonly string Output;
    readonly string ReferencePath, ReferenceHash;
    string StorageMode = "direct_file";
    readonly uint[][] Previous = {new uint[43], new uint[43], new uint[43]};
    readonly uint[] Counts = new uint[3];
    byte[] Payload = new byte[0];
    uint Total;
    long RawBytes, FullPayloadBytes;
    int First = -1, Last = -1;
    bool Enabled;

    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool CreateHardLink(string newName, string existingName, IntPtr reserved);
    static string Hash(byte[] bytes) {
        using (var algorithm = SHA256.Create())
            return BitConverter.ToString(algorithm.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }
    public MoviePayloadTrace(WaterboxHost host, string output, string referenceDirectory) {
        Host = host; Output = output;
        Host.Enter();
        try {
            var adapter = CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
            Count = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadCount"));
            NativeTotal = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadTotal"));
            Errors = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadErrors"));
            Overflow = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadOverflow"));
            DataBytes = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadDataBytes"));
            Callbacks = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadCallbacks"));
            PendingVlc = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadPendingVlc"));
            PendingBuffers = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadPendingBuffers"));
            Events = adapter.GetDelegateForFunctionPointer<Pointer>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadEvents"));
            Data = adapter.GetDelegateForFunctionPointer<Pointer>(Host.GetProcAddrOrThrow("LsdGetMoviePayloadData"));
        } finally { Host.Exit(); }
        if (referenceDirectory == null) File = new FileStream(Path.Combine(output, "payload-entries.bin.gz"), FileMode.CreateNew);
        else {
            ReferencePath = Path.GetFullPath(Path.Combine(referenceDirectory, "payload-entries.bin.gz"));
            if (!System.IO.File.Exists(ReferencePath) || new FileInfo(ReferencePath).Length > 1572864 ||
                (System.IO.File.GetAttributes(ReferencePath) & FileAttributes.ReadOnly) == 0)
                throw new Exception("Replay requires a complete reviewed immutable payload journal");
            ReferenceHash = Hash(System.IO.File.ReadAllBytes(ReferencePath));
            File = new MemoryStream(new byte[1572864], 0, 1572864, true, true);
            File.SetLength(0);
            StorageMode = "bounded_generated_journal_pending_comparison";
        }
        Zipped = new GZipStream(File, CompressionLevel.Optimal, true);
        Writer = new BinaryWriter(Zipped, Encoding.UTF8, true);
        Writer.Write(Encoding.ASCII.GetBytes("LSDMOV1\0"));
    }

    public void Drain(int frame) {
        Enabled = true;
        Host.Enter();
        try {
            uint count = Count(), bytes = DataBytes();
            if (count > 16 || bytes > 1024 * 1024 || Errors() != 0 || Overflow() != 0) {
                int[] diagnostic = new int[checked((int)Math.Min(count, 16) * 43)];
                if (diagnostic.Length != 0) Marshal.Copy(Events(), diagnostic, 0, diagnostic.Length);
                System.IO.File.WriteAllText(Path.Combine(Output, "payload-error.json"), new JavaScriptSerializer().Serialize(new {
                    frame=frame, count=count, payload_bytes=bytes, errors=Errors(), overflow=Overflow(), numeric_records=diagnostic}));
                throw new Exception("Native movie payload transport reported an invalid boundary or overflow");
            }
            int[] words = new int[checked((int)count * 43)];
            if (count != 0) Marshal.Copy(Events(), words, 0, words.Length);
            if (Payload.Length < bytes) Payload = new byte[bytes];
            if (bytes != 0) Marshal.Copy(Data(), Payload, 0, (int)bytes);
            int cursor = 0;
            for (int row = 0; row < count; row++) {
                int at = row * 43;
                uint kind = unchecked((uint)words[at + 2]);
                int length = words[at + 24], offset = words[at + 25];
                if (words[at] != frame || words[at + 1] != Total + 1 || kind < 1 || kind > 3 ||
                    words[at + 39] != 0 || offset != cursor || length < 4 || length > 0x40000 || length > bytes - cursor)
                    throw new Exception("Invalid native movie payload record extent/schedule");
                byte[] hash;
                using (var algorithm = SHA256.Create()) hash = algorithm.ComputeHash(Payload, offset, length);
                byte[] numeric = new byte[172]; Buffer.BlockCopy(words, at * 4, numeric, 0, numeric.Length);
                Chain.Write(numeric, 0, numeric.Length); Chain.Write(hash, 0, hash.Length);
                byte tag = (byte)(kind - 1); Writer.Write(tag); RawBytes++;
                uint[] previous = Previous[tag];
                for (int column = 0; column < 43; column++) {
                    uint value = unchecked((uint)words[at + column]);
                    int difference = unchecked((int)(value - previous[column]));
                    uint encoded = unchecked((uint)((difference << 1) ^ (difference >> 31)));
                    while (encoded >= 128) { Writer.Write((byte)((encoded & 127) | 128)); RawBytes++; encoded >>= 7; }
                    Writer.Write((byte)encoded); RawBytes++; previous[column] = value;
                }
                Writer.Write(hash); RawBytes += hash.Length; FullPayloadBytes += length;
                cursor += length; Total++; Counts[tag]++;
                if (First < 0) First = frame;
                Last = frame;
                if (Total > 40000 || RawBytes > 32L * 1024 * 1024) throw new Exception("Movie payload journal bound exceeded");
            }
            if (cursor != bytes || Total != NativeTotal()) throw new Exception("Native movie payload events/data were lost");
        } finally { Host.Exit(); }
        if (frame % 600 == 599) {
            Writer.Flush(); Zipped.Flush();
            if (File.Length > 1572864) throw new Exception("Compressed movie payload journal bound exceeded");
        }
    }

    public void Dispose() {
        uint errors, overflow, callbacks, pendingVlc, pendingBuffers;
        Host.Enter();
        try {
            errors = Errors(); overflow = Overflow(); callbacks = Callbacks();
            pendingVlc = PendingVlc(); pendingBuffers = PendingBuffers();
        } finally { Host.Exit(); }
        try { Writer.Dispose(); Zipped.Dispose(); }
        finally {
            if (ReferencePath != null) {
                byte[] generated = ((MemoryStream)File).ToArray();
                string destination = Path.Combine(Output, "payload-entries.bin.gz");
                byte[] source = System.IO.File.ReadAllBytes(ReferencePath);
                if (Hash(source) != ReferenceHash) throw new Exception("Reviewed payload source changed during replay");
                if (generated.SequenceEqual(source)) {
                    if (!CreateHardLink(destination, ReferencePath, IntPtr.Zero))
                        throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                    StorageMode = "all_generated_compressed_bytes_equal_then_immutable_link_reused";
                } else {
                    using (var retained = new FileStream(destination, FileMode.CreateNew)) retained.Write(generated, 0, generated.Length);
                    StorageMode = "different_generated_bytes_retained_independently";
                }
            }
        }
        long compressed = File.Length; File.Dispose();
        string chain = Chain.CompleteHash(); Chain.Dispose();
        System.IO.File.WriteAllText(Path.Combine(Output, "payload-summary.json"), new JavaScriptSerializer().Serialize(new {
            schema_version=1, protocol="full_movie_payload_sha256_v1", observer_enabled=Enabled, event_numeric_words=43,
            native_event_bytes=172, frame_event_limit=16, frame_payload_limit_bytes=1024*1024,
            arm_frame=21884, entries=Total, counts=Counts, accepted_callbacks=callbacks,
            first_entry_frame=First, last_entry_frame=Last, raw_entry_bytes=RawBytes,
            compressed_entry_bytes=compressed, complete_native_payload_bytes_hashed=FullPayloadBytes,
            numeric_and_full_payload_hash_chain_sha256=chain, native_errors=errors, native_overflow=overflow,
            journal_storage_mode=StorageMode, reused_source_sha256=ReferenceHash,
            replay_compressed_bytes_generated_and_compared=ReferencePath!=null,
            pending_VLC_returns=pendingVlc, pending_RLE_buffers_without_MDEC_input=pendingBuffers,
            full_encoded_input_at_VLC_entry=true, full_RLE_at_actual_VLC_return=true, full_RLE_at_MDEC_input_entry=true,
            original_CPU_source_modified=false, game_MainRAM_or_instructions_written=false,
            original_hardware_timing_verified=false, individual_frame_GPU_presentation_accepted=false}));
        if (compressed > 1572864) throw new Exception("Final compressed movie payload journal bound exceeded");
    }
}
}
