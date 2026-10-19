// Optional disk budget and complete PCM digest for compact, private QA captures.
using System;
using System.IO;
using System.Security.Cryptography;

namespace Lsd.Research.Headless {
internal static class CaptureBudget {
    public const long Maximum = 64L * 1024 * 1024;
    public static long Limit { get; private set; }
    public static long Bytes { get; private set; }
    public static bool Enabled { get; private set; }
    static string Root;
    public static void Initialize(string root, bool enabled, long limit = Maximum) {
        if (Root != null || limit < 1 || limit > Maximum)
            throw new Exception("Invalid or repeated capture budget initialization");
        Root = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        Enabled = enabled; Limit = limit;
    }
    public static Stream Open(string path, FileMode mode) {
        if (!Enabled) return File.Open(path, mode);
        if (Root == null || mode != FileMode.CreateNew ||
            !Path.GetFullPath(path).StartsWith(Root, StringComparison.OrdinalIgnoreCase))
            throw new Exception("Compact capture requires a fresh file under its output root");
        return new BudgetStream(File.Open(path, mode));
    }
    sealed class BudgetStream : Stream {
        readonly Stream Target;
        public BudgetStream(Stream target) { Target = target; }
        public override bool CanRead { get { return false; } }
        public override bool CanSeek { get { return false; } }
        public override bool CanWrite { get { return true; } }
        public override long Length { get { return Target.Length; } }
        public override long Position { get { return Target.Position; } set { throw new NotSupportedException(); } }
        public override void Flush() { Target.Flush(); }
        public override int Read(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
        public override long Seek(long offset, SeekOrigin origin) { throw new NotSupportedException(); }
        public override void SetLength(long value) { throw new NotSupportedException(); }
        public override void Write(byte[] buffer, int offset, int count) {
            if (count < 0 || Bytes > Limit - count)
                throw new IOException("Compact capture stream budget exhausted");
            Target.Write(buffer, offset, count); Bytes += count;
        }
        protected override void Dispose(bool disposing) {
            if (disposing) Target.Dispose();
            base.Dispose(disposing);
        }
    }
}
internal sealed class PcmDigestStream : Stream {
    readonly SHA256 Hasher = SHA256.Create();
    public long Bytes { get; private set; }
    public string Digest { get; private set; }
    bool Finished;
    public override bool CanRead { get { return false; } }
    public override bool CanSeek { get { return false; } }
    public override bool CanWrite { get { return !Finished; } }
    public override long Length { get { return Bytes; } }
    public override long Position { get { return Bytes; } set { throw new NotSupportedException(); } }
    public override void Flush() { }
    public override int Read(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
    public override long Seek(long offset, SeekOrigin origin) { throw new NotSupportedException(); }
    public override void SetLength(long value) { throw new NotSupportedException(); }
    public override void Write(byte[] buffer, int offset, int count) {
        if (Finished || count < 0) throw new IOException("Invalid PCM digest stream write");
        Hasher.TransformBlock(buffer, offset, count, buffer, offset); Bytes += count;
    }
    protected override void Dispose(bool disposing) {
        if (disposing && !Finished) {
            Hasher.TransformFinalBlock(new byte[0], 0, 0);
            Digest = BitConverter.ToString(Hasher.Hash).Replace("-", "").ToLowerInvariant();
            Finished = true; Hasher.Dispose();
        }
        base.Dispose(disposing);
    }
}
}
