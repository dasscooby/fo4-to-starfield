// Inspect Starfield.esm: interior cells and their lighting templates, light records.
//   dotnet run -- <Starfield.esm> cells <substr>     interior cells (EditorID contains substr) + lighting template
//   dotnet run -- <Starfield.esm> lights <substr>    LIGH records (EditorID contains substr) + radius/colour
//   dotnet run -- <Starfield.esm> templates          lighting templates in use by interior cells (most used first)
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Starfield;

if (args.Length > 0 && args[0] == "reflect")
{
    foreach (var asm in AppDomain.CurrentDomain.GetAssemblies().Concat(new[] { typeof(Mutagen.Bethesda.Plugins.ModKey).Assembly, typeof(StarfieldMod).Assembly }).Distinct())
        foreach (var ty in asm.GetTypes().Where(x => x.Name.Contains(args[1])))
            Console.WriteLine(ty.FullName);
    return;
}
using var mod = StarfieldMod.CreateFromBinaryOverlay(args[0], StarfieldRelease.Starfield);
var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
var cache = mod.ToImmutableLinkCache();
string Name(Mutagen.Bethesda.Plugins.FormKey fk) =>
    cache.TryResolve<ILightingTemplateGetter>(fk, out var t) ? (t.EditorID ?? "") : "";

switch (args[1])
{
    case "cells":
        foreach (var c in cells.Where(c => (c.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(40))
            Console.WriteLine($"{c.EditorID}  {c.FormKey}  template={c.LightingTemplate.FormKey} {Name(c.LightingTemplate.FormKey)}  refs={c.Temporary.Count}");
        break;
    case "templates":
        foreach (var g in cells.Where(c => !c.LightingTemplate.IsNull).GroupBy(c => c.LightingTemplate.FormKey)
                     .OrderByDescending(g => g.Count()).Take(25))
            Console.WriteLine($"{g.Count(),5}  {g.Key}  {Name(g.Key)}  e.g. {g.First().EditorID}");
        break;
    case "lights":
        foreach (var l in mod.Lights.Where(l => (l.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(40))
            Console.WriteLine($"{l.EditorID}  {l.FormKey}  radius={l.Radius}  color={l.Color}  model={l.Model?.File}");
        break;
}
