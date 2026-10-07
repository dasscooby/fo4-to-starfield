// Plugin writer for converted assets (S2 -> WP-08 / WP-10).
//   dotnet run -- <output dir> <manifest.json> [cell.json]
// Creates FO4Port.esm with one STAT per converted item (manifest order: item k gets FormID 0x800 + k). With a cell export from
// dotnet/Fo4Export it also creates an interior cell "FO4Port_<cell>" holding every reference whose model was converted, placed at
// the Fallout 4 position converted to metres (1/70), same rotation (radians) and scale.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const float UnitsPerMetre = 70f;
var outDir = args[0];
Directory.CreateDirectory(outDir);

var items = new List<(string editorId, string model, string source)>();
using (var doc = JsonDocument.Parse(File.ReadAllText(args[1])))
    foreach (var it in doc.RootElement.GetProperty("items").EnumerateArray())
        items.Add((it.GetProperty("editor_id").GetString()!, it.GetProperty("model").GetString()!, it.GetProperty("source").GetString()!));

var modKey = ModKey.FromNameAndExtension("FO4Port.esm");
var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

var bySource = new Dictionary<string, Static>(StringComparer.OrdinalIgnoreCase);
foreach (var (editorId, model, source) in items)
{
    var stat = new Static(mod) { EditorID = editorId, Model = new Model { File = model } };
    mod.Statics.Add(stat);
    bySource[source.Replace('/', '\\')] = stat;
}
Console.WriteLine($"{items.Count} statics");

if (args.Length > 2)
{
    using var cdoc = JsonDocument.Parse(File.ReadAllText(args[2]));
    var root = cdoc.RootElement;
    var cellName = "FO4Port_" + root.GetProperty("cell").GetString();
    var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
    var cell = new Cell(mod) { EditorID = cellName, Flags = Cell.Flag.IsInteriorCell };
    // lighting: vanilla ship-interior lighting template + a vanilla neutral omni light at each (deduplicated) FO4 light position
    var ltHex = Environment.GetEnvironmentVariable("LIGHTING_TEMPLATE") ?? "06BCF8";  // KreetBase01LGTtemplate (underground)
    cell.LightingTemplate.SetTo(new FormKey(sfEsm, Convert.ToUInt32(ltHex, 16)));
    var cocMarker = new FormKey(sfEsm, 0x000032);                                  // COCMarkerHeading
    var omni = new FormKey(sfEsm, 0x0027BB);                                    // LGT_SpaceStation_Omni_NS_Cool_001_1k (8 m, dimmer)
    var lit = new List<P3Float>();
    int lights = 0;
    int placed = 0, skipped = 0;
    foreach (var r in root.GetProperty("refs").EnumerateArray())
    {
        var model = r.GetProperty("model").GetString() ?? "";
        if (r.GetProperty("base_editor_id").GetString() == "COCMarkerHeading")   // arrival point for `coc`
        {
            var cp = r.GetProperty("pos"); var cr = r.GetProperty("rot");
            cell.Temporary.Add(new PlacedObject(mod)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(cocMarker),
                Position = new P3Float(cp[0].GetSingle() / UnitsPerMetre, cp[1].GetSingle() / UnitsPerMetre, cp[2].GetSingle() / UnitsPerMetre),
                Rotation = new P3Float(cr[0].GetSingle(), cr[1].GetSingle(), cr[2].GetSingle()),
            });
            Console.WriteLine("placed COC marker");
            continue;
        }
        if (r.GetProperty("type").GetString() == "Light")
        {
            var lp = r.GetProperty("pos");
            var pos = new P3Float(lp[0].GetSingle() / UnitsPerMetre, lp[1].GetSingle() / UnitsPerMetre, lp[2].GetSingle() / UnitsPerMetre);
            if (lit.Any(q => Math.Abs(q.X - pos.X) < 5 && Math.Abs(q.Y - pos.Y) < 5 && Math.Abs(q.Z - pos.Z) < 5)) continue;
            lit.Add(pos);
            cell.Temporary.Add(new PlacedObject(mod) { Base = new FormLinkNullable<IPlaceableObjectGetter>(omni), Position = pos });
            lights++;
            continue;
        }
        if (model.Length == 0 || !bySource.TryGetValue("meshes\\" + model.TrimStart('\\'), out var stat)) { skipped++; continue; }
        var p = r.GetProperty("pos"); var o = r.GetProperty("rot");
        var obj = new PlacedObject(mod)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(stat.FormKey),
            Position = new P3Float(p[0].GetSingle() / UnitsPerMetre, p[1].GetSingle() / UnitsPerMetre, p[2].GetSingle() / UnitsPerMetre),
            Rotation = new P3Float(o[0].GetSingle(), o[1].GetSingle(), o[2].GetSingle()),
        };
        var scale = r.GetProperty("scale").GetSingle();
        if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
        cell.Temporary.Add(obj);
        placed++;
    }
    var id = cell.FormKey.ID;
    var block = new CellBlock { BlockNumber = (int)(id % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
    var sub = new CellSubBlock { BlockNumber = (int)((id / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
    sub.Cells.Add(cell);
    block.SubBlocks.Add(sub);
    mod.Cells.Records.Add(block);
    Console.WriteLine($"cell {cellName} {cell.FormKey}: placed {placed} references + {lights} lights, skipped {skipped}");
}

var path = Path.Combine(outDir, modKey.FileName);
var sfData = Environment.GetEnvironmentVariable("STARFIELD_DATA") ?? @"D:\SteamLibrary\steamapps\common\Starfield\Data";
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new Mutagen.Bethesda.Plugins.Records.KeyedMasterStyle(ModKey.FromNameAndExtension("Starfield.esm"), Mutagen.Bethesda.Plugins.MasterStyle.Full))
    .Write();
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes)");
// read-back check: scripts/recon.py scan_plugin (Mutagen's overlay needs master flag lookups once Starfield.esm is a master)
