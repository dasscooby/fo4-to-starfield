// Plugin writer for converted assets (spike S2 -> WP-08 start).
//   dotnet run -- <output dir> [manifest.json | nif path for a single static]
// With a manifest written by scripts/convert_batch.py it creates FO4Port.esm with one STAT per converted item, in manifest
// order, so item k gets FormID (load slot << 24) | (0x800 + k). Prints the mapping.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

var outDir = args.Length > 0 ? args[0] : "out";
var arg1 = args.Length > 1 ? args[1] : "fo4port\\setdressing\\chairpatio01.nif";
Directory.CreateDirectory(outDir);

var items = new List<(string editorId, string model)>();
if (arg1.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
{
    using var doc = JsonDocument.Parse(File.ReadAllText(arg1));
    foreach (var it in doc.RootElement.GetProperty("items").EnumerateArray())
        items.Add((it.GetProperty("editor_id").GetString()!, it.GetProperty("model").GetString()!));
}
else
{
    items.Add(("FO4Port_ChairPatio01", arg1));
}

var modKey = ModKey.FromNameAndExtension("FO4Port.esm");
var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

foreach (var (editorId, model) in items)
{
    var stat = new Static(mod) { EditorID = editorId };
    mod.Statics.Add(stat);
    stat.Model = new Model { File = model };
}

var path = Path.Combine(outDir, modKey.FileName);
mod.WriteToBinary(path);
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes, {items.Count} statics)");

using var back = StarfieldMod.CreateFromBinaryOverlay(path, StarfieldRelease.Starfield);
var k = 0;
foreach (var s in back.Statics)
{
    if (k < 3 || k == items.Count - 1)
        Console.WriteLine($"  [{k}] {s.EditorID}  formKey={s.FormKey}  model={s.Model?.File}");
    k++;
}
Console.WriteLine($"read back {back.Statics.Count} statics, masters: {back.ModHeader.MasterReferences.Count}");
