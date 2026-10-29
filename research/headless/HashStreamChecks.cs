// Data-free executable fixture for the serializer sink; no game/emulator inputs.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;

namespace Lsd.Research.Headless {
internal static class HashStreamChecks {
    static string Error(Action action) {
        try {action();return "NO_EXCEPTION";}
        catch (Exception error) {return error.GetType().Name;}
    }
    public static int Main() {
        var result=new Dictionary<string,object>();
        var vectors=new List<object>();
        foreach (int length in new[]{0,1,7,64,4096}) {
            var bytes=new byte[length];
            for (int i=0;i<length;i++) bytes[i]=(byte)((i*17+13)&255);
            using (var stream=new BoundedSha256Stream(length)) {
                int middle=length/2;
                stream.Write(bytes,0,middle);
                for (int i=middle;i<length;i++) stream.WriteByte(bytes[i]);
                vectors.Add(new {length=length,position=stream.Position,hash=stream.CompleteHash()});
            }
        }
        result["vectors"]=vectors;
        using (var stream=new BoundedSha256Stream(5)) {
            stream.WriteByte(0xA5);
            stream.Write(new byte[]{0,1,2,3,4,5,6,7,8},3,4);
            stream.Write(new byte[0],0,0);
            result["offset_chunks"]=new {length=stream.Length,hash=stream.CompleteHash()};
        }
        using (var stream=new BoundedSha256Stream(128)) {
            var bytes=new byte[127];for (int i=0;i<bytes.Length;i++) bytes[i]=7;
            stream.Write(bytes,0,bytes.Length);stream.WriteByte(7);
            string overflow=Error(()=>stream.WriteByte(8));
            result["boundary"]=new {length=stream.Length,overflow=overflow,hash=stream.CompleteHash()};
        }
        using (var stream=new BoundedSha256Stream(4)) {
            var errors=new Dictionary<string,string>();
            errors["negative_limit"]=Error(()=>new BoundedSha256Stream(-1));
            errors["null"]=Error(()=>stream.Write(null,0,0));
            errors["negative_offset"]=Error(()=>stream.Write(new byte[4],-1,1));
            errors["negative_count"]=Error(()=>stream.Write(new byte[4],0,-1));
            errors["out_of_bounds"]=Error(()=>stream.Write(new byte[4],3,2));
            errors["large_count"]=Error(()=>stream.Write(new byte[4],1,Int32.MaxValue));
            errors["over_limit"]=Error(()=>stream.Write(new byte[5],0,5));
            result["validation"]=new {length_after_errors=stream.Length,errors=errors,hash=stream.CompleteHash()};
        }
        using (var stream=new BoundedSha256Stream(3)) {
            stream.Write(Encoding.ASCII.GetBytes("abc"),0,3);
            string first=stream.CompleteHash(),second=stream.CompleteHash();
            result["finalization"]=new {first=first,second=second,can_write=stream.CanWrite,
                write_error=Error(()=>stream.WriteByte(1)),length=stream.Length};
        }
        var disposed=new BoundedSha256Stream(1);disposed.Dispose();
        result["disposal"]=new {can_write=disposed.CanWrite,write_error=Error(()=>disposed.WriteByte(1)),
            hash_error=Error(()=>disposed.CompleteHash()),length_error=Error(()=>{var length=disposed.Length;})};
        using (var stream=new BoundedSha256Stream(1)) {
            stream.Flush();
            result["unsupported"]=new {can_read=stream.CanRead,can_seek=stream.CanSeek,
                read=Error(()=>stream.Read(new byte[1],0,1)),seek=Error(()=>stream.Seek(0,SeekOrigin.Begin)),
                resize=Error(()=>stream.SetLength(1)),set_position=Error(()=>stream.Position=0)};
        }
        const int chunkSize=8192,repeats=8192;
        var chunk=new byte[chunkSize];for (int i=0;i<chunk.Length;i++) chunk[i]=(byte)((i*17+13)&255);
        using (var stream=new BoundedSha256Stream((long)chunkSize*repeats)) {
            for (int i=0;i<repeats;i++) stream.Write(chunk,0,chunk.Length);
            result["large_stream"]=new {length=stream.Length,chunk_bytes=chunk.Length,
                chunk_repetitions=repeats,hash=stream.CompleteHash()};
        }
        Console.WriteLine(JsonSerializer.Serialize(result));
        return 0;
    }
}
}
