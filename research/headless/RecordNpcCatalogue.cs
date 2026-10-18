using System;
using System.IO;
using System.Web.Script.Serialization;

namespace Lsd.Research.Headless {
internal static class RecordNpcCatalogue {
    public static int Main(string[] args) {
        try {
            if (args.Length != 8) throw new Exception("Expected the complete recorder argument set");
            var settings = new JavaScriptSerializer().Deserialize<RecordNpcHistory.Settings>(File.ReadAllText(args[6]));
            return RecordNpcHistory.MainWithFactory(args, new NpcCatalogueFactory(settings.catalogue_pcs));
        } catch (Exception error) { Console.Error.WriteLine(error); return 2; }
    }
}
}
