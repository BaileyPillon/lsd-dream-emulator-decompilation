// Host-side waits belong between emulated frames; this class never touches a core.
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

namespace Lsd.Research.Headless {
internal sealed class CooperativeFrameWait {
    internal sealed class Result {
        public string Token;
        public long ElapsedMilliseconds;
        public bool StopRequested, TimedOut;
    }

    readonly string request, acknowledgment, stop;
    readonly int pollMilliseconds, maximumMilliseconds;

    public bool RequestPending { get { return File.Exists(request); } }

    public CooperativeFrameWait(string folder, int maximumMilliseconds, int pollMilliseconds = 100) {
        if (maximumMilliseconds < 1) throw new ArgumentOutOfRangeException("maximumMilliseconds");
        if (pollMilliseconds < 1 || pollMilliseconds > maximumMilliseconds)
            throw new ArgumentOutOfRangeException("pollMilliseconds");
        request = Path.Combine(folder, "HOST-WAIT");
        acknowledgment = Path.Combine(folder, "HOST-WAIT-ACK");
        stop = Path.Combine(folder, "STOP");
        this.maximumMilliseconds = maximumMilliseconds;
        this.pollMilliseconds = pollMilliseconds;
    }

    string ReadRequest() {
        if (!File.Exists(request)) return null;
        try {
            using (var stream = new FileStream(request, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete)) {
                if (stream.Length < 1 || stream.Length > 128) throw new IOException("Invalid host-wait token length");
                var bytes = new byte[128];
                int count = stream.Read(bytes, 0, bytes.Length);
                string token = Encoding.ASCII.GetString(bytes, 0, count);
                foreach (char value in token)
                    if (!(value >= 'a' && value <= 'z') && !(value >= 'A' && value <= 'Z')
                        && !(value >= '0' && value <= '9') && value != '-')
                        throw new IOException("Invalid host-wait token character");
                if (count == 0 || stream.ReadByte() != -1) throw new IOException("Host-wait request changed during read");
                return token;
            }
        } catch (FileNotFoundException) { return null; }
    }

    // onWaiting must finish its state observation before the acknowledgment is visible.
    // onResumed runs before the caller may advance the next emulated frame.
    public Result WaitIfRequested(Action<string> onWaiting, Action<Result> onResumed) {
        if (onWaiting == null) throw new ArgumentNullException("onWaiting");
        if (onResumed == null) throw new ArgumentNullException("onResumed");
        string token = ReadRequest();
        if (token == null || File.Exists(stop)) return null;
        if (File.Exists(acknowledgment)) throw new IOException("Stale host-wait acknowledgment");
        bool ownsAcknowledgment = false;
        try {
            onWaiting(token);
            using (var stream = new FileStream(acknowledgment, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) {
                ownsAcknowledgment = true;
                byte[] bytes = Encoding.ASCII.GetBytes(token);
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush();
            }
            var clock = Stopwatch.StartNew();
            var result = new Result { Token = token };
            while (true) {
                result.StopRequested = File.Exists(stop);
                result.TimedOut = clock.ElapsedMilliseconds >= maximumMilliseconds;
                if (result.StopRequested || result.TimedOut) break;
                string current = ReadRequest();
                if (current == null) break;
                if (current != token) throw new IOException("Host-wait token changed before release");
                Thread.Sleep(Math.Min(pollMilliseconds,
                    Math.Max(1, maximumMilliseconds - (int)clock.ElapsedMilliseconds)));
            }
            result.ElapsedMilliseconds = clock.ElapsedMilliseconds;
            onResumed(result);
            return result;
        } finally {
            if (ownsAcknowledgment) File.Delete(acknowledgment);
        }
    }
}
}
