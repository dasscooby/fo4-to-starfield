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
    case "statics":
        foreach (var s in mod.Statics.Where(s => (s.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(30))
            Console.WriteLine($"{s.EditorID}  {s.FormKey}  model={s.Model?.File}");
        break;
    case "doors":
        foreach (var d in mod.Doors.Where(d => (d.Model?.File?.ToString() ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(3))
        {
            Console.WriteLine($"== {d.EditorID} {d.FormKey} model={d.Model?.File}");
            foreach (var p in d.GetType().GetProperties())
            {
                object? v; try { v = p.GetValue(d); } catch { continue; }
                var s = v switch { null => "null", string str => str, System.Collections.IEnumerable e and not string => "[" + string.Join(", ", e.Cast<object>().Take(6)) + "]", _ => v.ToString() };
                if (s != null && s.Length > 160) s = s.Substring(0, 160);
                Console.WriteLine($"   {p.Name} = {s}");
            }
        }
        break;
    case "agc":
        foreach (var d in mod.Doors.Where(d => (d.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(int.Parse(args.Length > 3 ? args[3] : "3")))
        {
            Console.WriteLine($"== {d.EditorID} {d.FormKey} model={d.Model?.File} flags={d.Flags}");
            foreach (var c in d.Components)
                foreach (var p in c.GetType().GetProperties())
                {
                    object? v; try { v = p.GetValue(c); } catch { continue; }
                    Console.WriteLine($"   {c.GetType().Name.Replace("BinaryOverlay","")}.{p.Name} = {v}");
                }
        }
        break;
    case "celldump":
        foreach (var c in cells.Where(c => string.Equals(c.EditorID, args[2], StringComparison.OrdinalIgnoreCase)).Take(1))
            foreach (var p in c.GetType().GetProperties())
            {
                object? v; try { v = p.GetValue(c); } catch { continue; }
                if (v == null || p.Name is "Temporary" or "Persistent" or "NavigationMeshes") continue;
                var s = v.ToString() ?? ""; if (s.Length > 140) s = s.Substring(0, 140);
                Console.WriteLine($"   {p.Name} = {s}");
            }
        break;
    case "doorprops":
        foreach (var p in typeof(Mutagen.Bethesda.Starfield.Door).GetProperties()) Console.WriteLine($"{p.PropertyType} {p.Name}");
        break;
    case "imgs":
        {
            var useCount = cells.Where(c => !c.ImageSpace.IsNull).GroupBy(c => c.ImageSpace.FormKey).ToDictionary(g => g.Key, g => g.Count());
            foreach (var i in mod.ImageSpaces.OrderByDescending(i => useCount.GetValueOrDefault(i.FormKey)).Take(30))
                Console.WriteLine($"{useCount.GetValueOrDefault(i.FormKey),5}  {i.FormKey}  {i.EditorID}");
        }
        break;
    case "lights":
        foreach (var l in mod.Lights.Where(l => (l.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(40))
            Console.WriteLine($"{l.EditorID}  {l.FormKey}  radius={l.Radius}  color={l.Color}  model={l.Model?.File}");
        break;
}
