// Plugin writer for converted assets (S2 -> WP-08 / WP-10).
//   dotnet run -- <output dir> <manifest.json> [cell.json ...]
// Creates FO4Port.esm with one STAT per converted item and, for each cell export from dotnet/Fo4Export, an interior cell
// "FO4Port_<cell>" holding every reference whose model was converted, placed at the Fallout 4 position / 70 (metres), same rotation
// (radians) and scale. Initially-disabled FO4 references stay initially disabled.
//
// FormIDs are STABLE: <output dir>/formids.json maps an identity key to its FormID and is reused on every run, so adding or
// removing assets never renumbers existing records (saves and cross-references keep working). Keys:
//   STAT:<editor id>   CELL:<cell name>   REFR:<cell name>:<source FO4 FormKey>   (lights and COC markers use their source ref)
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const float UnitsPerMetre = 70f;
const uint FirstId = 0x800;
var outDir = args[0];
Directory.CreateDirectory(outDir);

var modKey = ModKey.FromNameAndExtension("FO4Port.esm");
var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
var release = StarfieldRelease.Starfield;
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

// ---- stable FormID map ------------------------------------------------------------------------------------------------
var mapPath = Path.Combine(outDir, "formids.json");
var ids = File.Exists(mapPath)
    ? JsonSerializer.Deserialize<Dictionary<string, uint>>(File.ReadAllText(mapPath))!
    : new Dictionary<string, uint>();
var next = ids.Count == 0 ? FirstId : ids.Values.Max() + 1;
var usedThisRun = new HashSet<string>();
FormKey Id(string key)
{
    if (!usedThisRun.Add(key)) throw new InvalidOperationException($"duplicate identity key {key}");
    if (!ids.TryGetValue(key, out var v)) { v = next++; ids[key] = v; }
    return new FormKey(modKey, v);
}

// ---- statics ----------------------------------------------------------------------------------------------------------
var items = new List<(string editorId, string model, string source)>();
using (var doc = JsonDocument.Parse(File.ReadAllText(args[1])))
    foreach (var it in doc.RootElement.GetProperty("items").EnumerateArray())
        items.Add((it.GetProperty("editor_id").GetString()!, it.GetProperty("model").GetString()!, it.GetProperty("source").GetString()!));

var bySource = new Dictionary<string, Static>(StringComparer.OrdinalIgnoreCase);
foreach (var (editorId, model, source) in items)
{
    var stat = new Static(Id("STAT:" + editorId), release) { EditorID = editorId, Model = new Model { File = model } };
    mod.Statics.Add(stat);
    bySource[source.Replace('/', '\\')] = stat;
}
Console.WriteLine($"{items.Count} statics");

// ---- cells ------------------------------------------------------------------------------------------------------------
P3Float Pos(JsonElement p) => new(p[0].GetSingle() / UnitsPerMetre, p[1].GetSingle() / UnitsPerMetre, p[2].GetSingle() / UnitsPerMetre);
P3Float Rot(JsonElement o) => new(o[0].GetSingle(), o[1].GetSingle(), o[2].GetSingle());

foreach (var cellPath in args.Skip(2))
{
    using var cdoc = JsonDocument.Parse(File.ReadAllText(cellPath));
    var root = cdoc.RootElement;
    var cellName = "FO4Port_" + root.GetProperty("cell").GetString();
    var cell = new Cell(Id("CELL:" + cellName), release) { EditorID = cellName, Flags = Cell.Flag.IsInteriorCell };
    var ltHex = Environment.GetEnvironmentVariable("LIGHTING_TEMPLATE") ?? "06BCF8";   // KreetBase01LGTtemplate (underground)
    cell.LightingTemplate.SetTo(new FormKey(sfEsm, Convert.ToUInt32(ltHex, 16)));
    var cocMarker = new FormKey(sfEsm, 0x000032);                                        // COCMarkerHeading
    var omni = new FormKey(sfEsm, 0x0027BB);                                             // LGT_SpaceStation_Omni_NS_Cool_001_1k
    var lit = new List<P3Float>();
    int lights = 0, placed = 0, skipped = 0, disabled = 0;
    foreach (var r in root.GetProperty("refs").EnumerateArray())
    {
        var src = r.GetProperty("formkey").GetString()!;
        var model = r.GetProperty("model").GetString() ?? "";
        PlacedObject? obj = null;
        if (r.GetProperty("base_editor_id").GetString() == "COCMarkerHeading")            // arrival point for `coc`
        {
            obj = new PlacedObject(Id($"REFR:{cellName}:{src}"), release)
                { Base = new FormLinkNullable<IPlaceableObjectGetter>(cocMarker), Position = Pos(r.GetProperty("pos")), Rotation = Rot(r.GetProperty("rot")) };
        }
        else if (r.GetProperty("type").GetString() == "Light")
        {
            var pos = Pos(r.GetProperty("pos"));
            if (lit.Any(q => Math.Abs(q.X - pos.X) < 5 && Math.Abs(q.Y - pos.Y) < 5 && Math.Abs(q.Z - pos.Z) < 5)) continue;
            lit.Add(pos);
            obj = new PlacedObject(Id($"REFR:{cellName}:{src}"), release) { Base = new FormLinkNullable<IPlaceableObjectGetter>(omni), Position = pos };
            lights++;
        }
        else
        {
            if (model.Length == 0 || !bySource.TryGetValue("meshes\\" + model.TrimStart('\\'), out var stat)) { skipped++; continue; }
            obj = new PlacedObject(Id($"REFR:{cellName}:{src}"), release)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(stat.FormKey),
                Position = Pos(r.GetProperty("pos")),
                Rotation = Rot(r.GetProperty("rot")),
            };
            var scale = r.GetProperty("scale").GetSingle();
            if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
            placed++;
        }
        if (r.TryGetProperty("disabled", out var dis) && dis.GetInt32() != 0)
        {
            obj.MajorRecordFlagsRaw |= 0x800;                                              // Initially Disabled, as in FO4
            disabled++;
        }
        cell.Temporary.Add(obj);
    }
    var cid = cell.FormKey.ID;
    var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
    var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
    sub.Cells.Add(cell);
    block.SubBlocks.Add(sub);
    mod.Cells.Records.Add(block);
    Console.WriteLine($"cell {cellName} {cell.FormKey}: placed {placed} references + {lights} lights ({disabled} initially disabled), skipped {skipped}");
}

mod.ModHeader.Stats.NextFormID = next;
var path = Path.Combine(outDir, modKey.FileName);
var sfData = Environment.GetEnvironmentVariable("STARFIELD_DATA") ?? throw new InvalidOperationException("set STARFIELD_DATA to the Starfield Data folder");
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full))
    .Write();
File.WriteAllText(mapPath, JsonSerializer.Serialize(ids.OrderBy(kv => kv.Value).ToDictionary(kv => kv.Key, kv => kv.Value),
    new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes); {ids.Count} stable FormIDs in {mapPath}");
