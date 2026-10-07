// Spike S2: can Mutagen's Starfield library write a plugin?
// Writes FO4Port.esm with one STAT that points at the converted chair mesh, then reads it back.
// usage: dotnet run -- <output dir> [nif path used by the STAT, relative to Data/meshes]
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

var outDir = args.Length > 0 ? args[0] : "out";
var nifPath = args.Length > 1 ? args[1] : "fo4port\\setdressing\\chairpatio01.nif";
Directory.CreateDirectory(outDir);

var modKey = ModKey.FromNameAndExtension("FO4Port.esm");
var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

var stat = new Static(mod) { EditorID = "FO4Port_ChairPatio01" };
mod.Statics.Add(stat);
stat.Model = new Model { File = nifPath };

var path = Path.Combine(outDir, modKey.FileName);
mod.WriteToBinary(path);
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length} bytes)");

using var back = StarfieldMod.CreateFromBinaryOverlay(path, StarfieldRelease.Starfield);
foreach (var s in back.Statics)
    Console.WriteLine($"read back: {s.EditorID}  formKey={s.FormKey}  model={s.Model?.File}");
Console.WriteLine($"masters: {back.ModHeader.MasterReferences.Count}, records: {back.Statics.Count}");
