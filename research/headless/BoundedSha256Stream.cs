using System;
using System.IO;
using System.Security.Cryptography;

namespace Lsd.Research.Headless {
// Forward-only serializer sink. Retains a one-byte WriteByte buffer and digest,
// not a growing copy of the serialized state. Length/Position report bytes seen.
internal sealed class BoundedSha256Stream : Stream {
    readonly long Limit;
    readonly HashAlgorithm Algorithm;
    readonly byte[] SingleByte = new byte[1];
    long BytesWritten;
    bool Finished, Closed;
    string Digest;

    public BoundedSha256Stream(long limit) {
        if (limit < 0) throw new ArgumentOutOfRangeException(nameof(limit));
        Limit = limit;
        Algorithm = SHA256.Create();
    }
    void RequireOpen() {
        if (Closed) throw new ObjectDisposedException(nameof(BoundedSha256Stream));
    }
    void RequireWritable(int count) {
        RequireOpen();
        if (Finished) throw new InvalidOperationException("State hash is already finalized.");
        if (BytesWritten > Limit - count) throw new IOException("Serialized state exceeds its byte bound.");
    }
    public override bool CanRead { get { return false; } }
    public override bool CanSeek { get { return false; } }
    public override bool CanWrite { get { return !Closed && !Finished; } }
    public override long Length { get { RequireOpen(); return BytesWritten; } }
    public override long Position {
        get { RequireOpen(); return BytesWritten; }
        set { throw new NotSupportedException("State hashing is forward-only."); }
    }
    public override void Write(byte[] buffer, int offset, int count) {
        if (buffer == null) throw new ArgumentNullException(nameof(buffer));
        if (offset < 0 || count < 0 || offset > buffer.Length - count)
            throw new ArgumentOutOfRangeException("offset/count");
        RequireWritable(count);
        if (count != 0) Algorithm.TransformBlock(buffer, offset, count, null, 0);
        BytesWritten += count;
    }
    public override void WriteByte(byte value) {
        RequireWritable(1);
        SingleByte[0] = value;
        Algorithm.TransformBlock(SingleByte, 0, 1, null, 0);
        BytesWritten++;
    }
    public string CompleteHash() {
        RequireOpen();
        if (!Finished) {
            Algorithm.TransformFinalBlock(new byte[0], 0, 0);
            Digest = BitConverter.ToString(Algorithm.Hash).Replace("-", "").ToLowerInvariant();
            Finished = true;
        }
        return Digest;
    }
    public override void Flush() { RequireOpen(); }
    public override int Read(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
    public override long Seek(long offset, SeekOrigin origin) { throw new NotSupportedException(); }
    public override void SetLength(long value) { throw new NotSupportedException(); }
    protected override void Dispose(bool disposing) {
        if (disposing && !Closed) { Algorithm.Dispose(); Closed = true; }
        base.Dispose(disposing);
    }
}
}
