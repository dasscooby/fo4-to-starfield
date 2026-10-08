// Export Fallout 4 interior-cell placements to JSON (input for the cell converter).
//   dotnet run -- <Fallout4.esm> list <substring>          list interior cells whose EditorID contains <substring>
//   dotnet run -- <Fallout4.esm> export <EditorID> <out.json>
// Each reference: base record type + EditorID + model path, position (game units), rotation (radians), scale.
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;

if (args.Length < 3 || (args[1] != "list" && args[1] != "export") || (args[1] == "export" && args.Length < 4))
{
    Console.Error.WriteLine("usage: <Fallout4.esm> list <substr> | export <EditorID> <out.json>");
    Environment.ExitCode = 1;
    return;
}
using var mod = Fallout4Mod.CreateFromBinaryOverlay(args[0], Fallout4Release.Fallout4);
var cache = mod.ToImmutableLinkCache();

IEnumerable<ICellGetter> InteriorCells() =>
    mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells);

if (args[1] == "list")
{
    foreach (var c in InteriorCells().Where(c => (c.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)))
        Console.WriteLine($"{c.EditorID}  {c.FormKey}  refs={c.Temporary.Count + c.Persistent.Count}");
    return;
}

var cell = InteriorCells().First(c => string.Equals(c.EditorID, args[2], StringComparison.OrdinalIgnoreCase));
var refs = new List<object>();
var deferred = new List<object>();
var byType = new Dictionary<string, int>();
var persistentKeys = cell.Persistent.Select(r => r.FormKey).ToHashSet();
foreach (var placed in cell.Temporary.Concat(cell.Persistent))
{
    if (placed is IPlacedNpcGetter npc)
    {
        deferred.Add(ReferenceExport.BuildActor(npc, persistentKeys.Contains(npc.FormKey)));
        continue;
    }
    if (placed is not IPlacedObjectGetter r)
    {
        deferred.Add(new { formkey = placed.FormKey.ToString(), type = placed.GetType().Name.Replace("BinaryOverlay", ""),
            reason = "placement_type_not_implemented" });
        continue;
    }
    string type = "?", baseEid = "", model = "";
    if (r.Base.TryResolve(cache, out var baseRec))
    {
        type = baseRec.GetType().Name.Replace("BinaryOverlay", "");
        baseEid = baseRec.EditorID ?? "";
        if (baseRec is IModeledGetter m && m.Model?.File != null) model = m.Model.File.ToString();
    }
    byType[type] = byType.GetValueOrDefault(type) + 1;
    refs.Add(ReferenceExport.Build(r, type, baseEid, model, persistentKeys.Contains(r.FormKey)));
}
File.WriteAllText(args[3], JsonSerializer.Serialize(new { schema_version = 2, cell = cell.EditorID, formkey = cell.FormKey.ToString(), refs,
    deferred_refs = deferred },
    new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"{cell.EditorID}: {refs.Count} references -> {args[3]}");
Console.WriteLine($"{deferred.Count} deferred placements retained for future translators");
foreach (var kv in byType.OrderByDescending(k => k.Value)) Console.WriteLine($"  {kv.Key}: {kv.Value}");
