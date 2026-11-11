// BuildPieces: Fallout 4 pieces in Starfield's outpost build menu (docs/research/build-pieces.md)
//
// FO4SFBuildPieces.esm (master Starfield.esm only; adds records, overrides none). The installed core is NOT a master: a piece's
// shell takes the MODEL PATH of a core STAT (read from the core plugin at build time, a string), so nothing in the plugin points
// at a core record; the quest script finds the same statics with Game.GetFormFromFile and logs whether they are there.
//   QUST  FO4SF_BPQuest        start game enabled, one stage, script FO4SF_BPQuest, NO properties
//   KYWD  FO4SF_BPCategory     only with --category add|replace: a copy of the template recipe's first filter keyword, renamed
//   <shell> x P (3 or 4)       FO4SF_BPShell1..: the buildable. --shell clone: a copy of the template COBJ's created object
//                              (whatever the real file makes buildable stays), script cleared, model and name replaced;
//                              --shell plain: a new Activator with the model and name only
//   COBJ  x P                  FO4SF_BPRecipe1..: a copy of the template COBJ (default co_Outpost_Crafting_WorkbenchIndustrialStation
//                              2E2F2C: workbench keyword, filters, build limit, sound and art are inherited), created object = the
//                              shell, one component (Iron when the template has it, else its first) x 1,1,2,2, own sort order
// The local ids are the script's and the stager's (tests/test_build_pieces.py compares).
//
// usage: BuildPieces menu <Starfield.esm> [--cobj <editor id>]      read only: how a COBJ gets into the menu
//        BuildPieces core <core.esm> [--pieces a,b,c]               read only: the statics a build would use
//        BuildPieces pieces <core.esm> [--pieces a,b,c]             the same choice as JSON (the stager reads it)
//        BuildPieces build <Starfield.esm> <core.esm> <out dir> [--pieces ..] [--shell clone|plain] [--category vanilla|add|replace] [--cobj ..]
//        BuildPieces check <plugin> <Starfield.esm> <core.esm> [same options]     exit 1 on a mismatch
//        BuildPieces fixture <out dir>              a synthetic Starfield.esm and core (out/Starfield.esm, out/FO4TerrainCore.esm)
using System.Text;
using System.Text.RegularExpressions;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Strings;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string? Opt(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new BuildPieces.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }
    var o = new BuildPieces.Options(Opt("--cobj") ?? BuildPieces.DefaultCobj, Opt("--shell") ?? "clone", Opt("--category") ?? "vanilla", Opt("--pieces"), Opt("--tab"), Opt("--set"));
    if (o.Set != null && !BuildPieces.Sets.ContainsKey(o.Set)) throw new BuildPieces.Refusal("--set is one of: " + string.Join(", ", BuildPieces.Sets.Keys));
    if (o.Shell != "clone" && o.Shell != "plain") throw new BuildPieces.Refusal("--shell is clone or plain");
    if (o.Category != "vanilla" && o.Category != "add" && o.Category != "replace") throw new BuildPieces.Refusal("--category is vanilla, add or replace");
    if (rest.Count == 2 && rest[0] == "menu") return BuildPieces.Menu(rest[1], o);
    if (rest.Count == 2 && rest[0] == "core") return BuildPieces.Core(rest[1], o);
    if (rest.Count == 2 && rest[0] == "pieces") return BuildPieces.PiecesJson(rest[1], o);
    if (rest.Count == 4 && rest[0] == "build") return BuildPieces.Build(rest[1], rest[2], rest[3], o);
    if (rest.Count == 4 && rest[0] == "check") return BuildPieces.Check(rest[1], rest[2], rest[3], o);
    if (rest.Count == 2 && rest[0] == "fixture") return BuildPieces.Fixture(rest[1]);
}
catch (BuildPieces.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: BuildPieces menu <Starfield.esm> | core <core.esm> | pieces <core.esm> | build <Starfield.esm> <core.esm> <out dir> | " +
                        "check <plugin> <Starfield.esm> <core.esm> | fixture <out dir>   [--pieces a,b,c] [--shell clone|plain] [--category vanilla|add|replace] [--tab <structures|furniture|decorations|miscellaneous|storage|defenses|keyword editor id>] [--set fo4] [--cobj <editor id>]");
return 2;

static class BuildPieces
{
    public class Refusal(string m) : Exception(m);
    public record Options(string Cobj, string Shell, string Category, string? Pieces, string? Tab = null, string? Set = null);
    public record Piece(int N, uint CoreId, string Edid, string Model, string Name);

    public const string DefaultCobj = "co_Outpost_Crafting_WorkbenchIndustrialStation";
    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFBuildPieces.esm");

    // the layout (scripts/planet/FO4SF_BPQuest.psc carries the quest id; the shells and recipes are found by the game's menu)
    public const int MaxPieces = 40;                                                   // room for 40 shells and 40 recipes
    const uint QuestId = 0x800, CategoryId = 0x801, ShellBase = 0x802, RecipeBase = 0x82A;   // RecipeBase = ShellBase + MaxPieces
    const string QuestEdid = "FO4SF_BPQuest", Script = "FO4SF_BPQuest", CategoryEdid = "FO4SF_BPCategory", CategoryName = "FO4 pieces";
    static readonly uint[] Counts = { 1, 1, 2, 2 };                       // the small cost of piece 1..4, repeating
    static uint Cost(int n) => Counts[(n - 1) % Counts.Length];
    // named sets of core statics (--set): editor ids, exact or with * ; each is tried as FO4Core_<name> first, then as written
    public static readonly Dictionary<string, string[]> Sets = new()
    {
        ["fo4"] = new[] { "junkwall01", "junkwall02", "junkwall03", "junkwall04", "junkwall05", "junkwall06", "junkwall07", "junkwallcorner01", "junkwalldoor01", "junkwallgate01",
                          "piershackwall*", "piershackroof*", "sandbagsingle01", "bedmetal01", "cafetable01", "woodcrate", "cratelarge01", "metalbarrel01" },
    };
    static readonly Dictionary<string, string> Tabs = new(StringComparer.OrdinalIgnoreCase)
    {
        ["structures"] = "OutpostCategoryStructures", ["furniture"] = "OutpostCategoryFurniture", ["decorations"] = "OutpostCategoryDecorations",
        ["miscellaneous"] = "OutpostCategoryMiscellaneous", ["storage"] = "OutpostCategoryStorage", ["defenses"] = "OutpostCategoryDefenses",
    };
    static Regex Glob(string g) => new("^" + Regex.Escape(g).Replace("\\*", ".*") + "$", RegexOptions.IgnoreCase);
    // statics that are not worth building: collision, markers, lods, helpers
    static readonly Regex Skip = new("collision|marker|lod|trigger|invisible|navcut|blocker|dummy|helper|portal|sound|light", RegexOptions.IgnoreCase);

    static FormKey Own(uint id) => new(Plugin, id);
    static IEnumerable<T> L<T>(IEnumerable<T>? x) => x ?? Enumerable.Empty<T>();
    static string Hex(FormKey k) => $"{k.ID:X6}";

    // ---------------------------------------------------------------- reading

    // the master names of a plugin, read from its TES4 record (a core may master plugins of the game: each needs a style to open)
    static List<string> MasterNames(string path)
    {
        using var f = File.OpenRead(path);
        var h = new byte[24];
        if (f.Read(h, 0, 24) != 24 || Encoding.ASCII.GetString(h, 0, 4) != "TES4") throw new Refusal($"{path} is not a plugin (no TES4 record)");
        int size = BitConverter.ToInt32(h, 4);
        var data = new byte[size];
        f.ReadExactly(data, 0, size);
        var names = new List<string>();
        for (int p = 0; p + 6 <= size;)
        {
            string sig = Encoding.ASCII.GetString(data, p, 4);
            int len = BitConverter.ToUInt16(data, p + 4);
            p += 6;
            if (sig == "MAST") names.Add(Encoding.UTF8.GetString(data, p, Math.Max(0, len - 1)));
            p += len;
        }
        return names;
    }

    static IStarfieldModDisposableGetter Open(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        foreach (var m in MasterNames(path)) styles.Set(new KeyedMasterStyle(ModKey.FromFileName(m), MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static IConstructibleObjectGetter Template(IStarfieldModGetter sf, string edid)
    {
        var hits = sf.ConstructibleObjects.Where(c => string.Equals(c.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} COBJ named {edid} in Starfield.esm (one needed): name one with --cobj");
        return hits[0];
    }

    static Dictionary<FormKey, string> EditorIds(IStarfieldModGetter m) =>
        m.EnumerateMajorRecords().Where(r => !string.IsNullOrEmpty(r.EditorID)).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.First().EditorID!);

    static string Stem(string model) => Path.GetFileNameWithoutExtension(model.Replace('\\', '/').Split('/').Last());

    // the statics a build uses: --pieces (editor ids, exact or with *) and/or --set (a named list, missing names are reported and skipped),
    // else the first four (by form id) with a model of their own; 3 to MaxPieces
    static List<Piece> ChoosePieces(IStarfieldModGetter core, Options o)
    {
        var all = core.Statics.Where(s => s.Model != null && !string.IsNullOrEmpty(s.Model.File.ToString()) && !string.IsNullOrEmpty(s.EditorID))
                              .OrderBy(s => s.FormKey.ID).ToList();
        var pick = new List<IStaticGetter>();
        void Add(IStaticGetter s) { if (!pick.Any(x => x.FormKey == s.FormKey)) pick.Add(s); }
        if (o.Set != null)
            foreach (var w in Sets[o.Set])
            {
                var hits = all.Where(s => Glob("FO4Core_" + w).IsMatch(s.EditorID!)).ToList();
                if (hits.Count == 0) hits = all.Where(s => Glob(w).IsMatch(s.EditorID!)).ToList();
                if (hits.Count == 0) Console.Error.WriteLine($"set {o.Set}: no STAT with a model named {w} (or FO4Core_{w}) in the core, skipped");
                if (!w.Contains('*') && hits.Count > 1) throw new Refusal($"{hits.Count} STAT with a model named {w} in the core (one needed)");
                foreach (var h in hits) Add(h);
            }
        if (o.Pieces != null)
            foreach (var w in o.Pieces.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                var hits = all.Where(s => Glob(w).IsMatch(s.EditorID!)).ToList();
                if (hits.Count == 0 || (!w.Contains('*') && hits.Count != 1)) throw new Refusal($"{hits.Count} STAT with a model named {w} in the core (one needed): see `core`");
                foreach (var h in hits) Add(h);
            }
        if (o.Set == null && o.Pieces == null)
        {
            var models = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var s in all)
            {
                var model = s.Model!.File.ToString()!;
                if (Skip.IsMatch(s.EditorID!) || Skip.IsMatch(model) || !models.Add(model)) continue;
                pick.Add(s);
                if (pick.Count == 4) break;
            }
        }
        if (pick.Count > MaxPieces)
        {
            if (o.Pieces != null) throw new Refusal($"{pick.Count} piece(s) chosen: at most {MaxPieces}");
            Console.Error.WriteLine($"set {o.Set}: {pick.Count} statics, only the first {MaxPieces} are used");
            pick = pick.Take(MaxPieces).ToList();
        }
        if (pick.Count < 3) throw new Refusal($"{pick.Count} piece(s) chosen: between 3 and {MaxPieces} are needed (the core has {all.Count} STAT with a model)");
        return pick.Select((s, i) => new Piece(i + 1, s.FormKey.ID, s.EditorID!, s.Model!.File.ToString()!, $"FO4 {Stem(s.Model!.File.ToString()!)}")).ToList();
    }

    public static int Core(string corePath, Options o)
    {
        using var core = Open(corePath);
        var n = 0;
        foreach (var s in core.Statics.OrderBy(s => s.FormKey.ID))
        {
            if (s.Model == null || string.IsNullOrEmpty(s.EditorID)) continue;
            n++;
            if (n <= 60) Console.WriteLine($"STAT\t{Hex(s.FormKey)}\t{s.EditorID}\t{s.Model.File}");
        }
        Console.WriteLine($"core: {n} STAT with a model" + (n > 60 ? " (first 60 shown)" : ""));
        var pieces = ChoosePieces(core, o);
        foreach (var p in pieces) Console.WriteLine($"piece {p.N}: core {p.CoreId:X6} {p.Edid} model {p.Model} name \"{p.Name}\"");
        return 0;
    }

    public static int PiecesJson(string corePath, Options o)
    {
        using var core = Open(corePath);
        var pieces = ChoosePieces(core, o);
        string Q(string s) => "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        Console.WriteLine("[" + string.Join(",", pieces.Select(p => $"{{\"n\":{p.N},\"core_id\":{p.CoreId},\"edid\":{Q(p.Edid)},\"model\":{Q(p.Model)},\"name\":{Q(p.Name)}}}")) + "]");
        return 0;
    }

    // ---------------------------------------------------------------- menu (read only): how a COBJ gets into the menu

    public static int Menu(string sfPath, Options o)
    {
        using var sf = Open(sfPath);
        var names = EditorIds(sf);
        string N(FormKey k) => names.GetValueOrDefault(k, "?");
        var c = Template(sf, o.Cobj);
        Console.WriteLine($"COBJ {Hex(c.FormKey)} {c.EditorID}");
        var made = c.CreatedObject.FormKey;
        var rec = sf.EnumerateMajorRecords().FirstOrDefault(r => r.FormKey == made);
        Console.WriteLine($"  created object {Hex(made)} {N(made)} type {rec?.GetType().Name.Replace("BinaryOverlay", "") ?? "not in this file"}");
        if (rec is IFurnitureGetter fu) Console.WriteLine($"    FURN bench {fu.BenchType}, keywords [{string.Join(", ", fu.Keywords?.Select(k => N(k.FormKey)) ?? Enumerable.Empty<string>())}], model {fu.Model?.File}, scripts [{string.Join(", ", fu.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? Array.Empty<string>())}], components {fu.Components?.Count ?? 0}");
        if (rec is IActivatorGetter ac) Console.WriteLine($"    ACTI keywords [{string.Join(", ", ac.Keywords?.Select(k => N(k.FormKey)) ?? Enumerable.Empty<string>())}], model {ac.Model?.File}, scripts [{string.Join(", ", ac.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? Array.Empty<string>())}], components {ac.Components?.Count ?? 0}");
        // where a station's picture comes from is not known offline: print every set field of the created object and of the COBJ,
        // and the records that the art-like ones (icon, image, art, material, texture, menu, preview) point to
        var byKey = sf.EnumerateMajorRecords().GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.First());
        if (rec != null) Dump("created object", rec, names, byKey);
        Dump("COBJ", c, names, byKey);
        Console.WriteLine($"  workbench keyword {Hex(c.WorkbenchKeyword.FormKey)} {N(c.WorkbenchKeyword.FormKey)}");
        Console.WriteLine($"  recipe filters [{string.Join(", ", L(c.RecipeFilters).Select(f => $"{Hex(f.FormKey)} {N(f.FormKey)}"))}]");
        Console.WriteLine($"  instantiation filter {(c.InstantiationFilterKeyword.IsNull ? "none" : N(c.InstantiationFilterKeyword.FormKey))}");
        Console.WriteLine($"  build limit (max build count global) {(c.MaxBuildCountGlobal.IsNull ? "none" : Hex(c.MaxBuildCountGlobal.FormKey) + " " + N(c.MaxBuildCountGlobal.FormKey))}");
        Console.WriteLine($"  menu sort order {c.MenuSortOrder}, tier {c.Tier}, amount {c.AmountProduced}, value {c.Value}, flags {c.Flags}, learn {c.LearnMethod}, conditions {c.Conditions?.Count ?? 0}, required perks {c.RequiredPerks?.Count ?? 0}");
        Console.WriteLine($"  menu art {(c.MenuArtObject.IsNull ? "none" : N(c.MenuArtObject.FormKey))}, description \"{c.Description?.String}\"");
        foreach (var k in L(c.ConstructableComponents)) Console.WriteLine($"  component {Hex(k.Component.FormKey)} {N(k.Component.FormKey)} x{k.RequiredCount}");
        // every recipe under the same workbench keyword: which filter says which tab
        Console.WriteLine($"recipes under the same workbench keyword ({N(c.WorkbenchKeyword.FormKey)}):");
        foreach (var x in sf.ConstructibleObjects.Where(x => x.WorkbenchKeyword.FormKey == c.WorkbenchKeyword.FormKey).OrderBy(x => x.FormKey.ID))
            Console.WriteLine($"  {Hex(x.FormKey)} {x.EditorID}: makes {N(x.CreatedObject.FormKey)}, filters [{string.Join(", ", L(x.RecipeFilters).Select(f => N(f.FormKey)))}], limit {(x.MaxBuildCountGlobal.IsNull ? "none" : N(x.MaxBuildCountGlobal.FormKey))}, sort {x.MenuSortOrder}");
        var rx = new Regex("OutpostCategory|OutpostFilter|OutpostBuild|OutpostRecipe", RegexOptions.IgnoreCase);
        var kws = sf.Keywords.Where(k => rx.IsMatch(k.EditorID ?? "")).OrderBy(k => k.FormKey.ID).ToList();
        Console.WriteLine($"outpost category / filter keywords: {kws.Count}");
        foreach (var k in kws.Take(80)) Console.WriteLine($"  KYWD {Hex(k.FormKey)} {k.EditorID}");
        // the tabs: how many recipes sit under each category keyword as workbench keyword / as a filter, and a few with menu art as templates
        Console.WriteLine("tabs (OutpostCategory keywords): recipes by workbench keyword / by filter; samples have menu art first");
        foreach (var k in kws.Where(k => (k.EditorID ?? "").StartsWith("OutpostCategory", StringComparison.OrdinalIgnoreCase)))
        {
            var wbs = sf.ConstructibleObjects.Where(x => x.WorkbenchKeyword.FormKey == k.FormKey).ToList();
            var fil = sf.ConstructibleObjects.Where(x => L(x.RecipeFilters).Any(f => f.FormKey == k.FormKey)).ToList();
            Console.WriteLine($"  {Hex(k.FormKey)} {k.EditorID}: {wbs.Count} / {fil.Count}");
            foreach (var x in wbs.Concat(fil).Distinct().OrderBy(x => x.MenuArtObject.IsNull ? 1 : 0).ThenBy(x => x.FormKey.ID).Take(3))
                Console.WriteLine($"    sample {Hex(x.FormKey)} {x.EditorID}: makes {N(x.CreatedObject.FormKey)}, filters [{string.Join(", ", L(x.RecipeFilters).Select(f => N(f.FormKey)))}], menu art {(x.MenuArtObject.IsNull ? "none" : N(x.MenuArtObject.FormKey))}, limit {(x.MaxBuildCountGlobal.IsNull ? "none" : N(x.MaxBuildCountGlobal.FormKey))}");
        }
        return 0;
    }

    static readonly Regex ArtLike = new("icon|image|art|material|texture|menuart|preview|thumb|hud|workshop|display|picture", RegexOptions.IgnoreCase);

    // every set public property of a record (name = value; form links by editor id; lists by count), then the records the art-like links point to
    static void Dump(string label, object rec, Dictionary<FormKey, string> names, Dictionary<FormKey, IMajorRecordGetter> byKey, int depth = 0)
    {
        var pad = new string(' ', 4 + depth * 2);
        Console.WriteLine($"{new string(' ', 2 + depth * 2)}fields of {label} ({rec.GetType().Name.Replace("BinaryOverlay", "")}):");
        var follow = new List<(string, IMajorRecordGetter)>();
        foreach (var pr in rec.GetType().GetProperties().OrderBy(x => x.Name))
        {
            if (pr.GetIndexParameters().Length > 0 || pr.Name is "EditorID" or "FormKey" or "FormVersion" or "VersionControl" or "Version2" or "StaticRegistration" or "IsCompressed" or "IsDeleted" or "MajorFlags" or "MajorRecordFlagsRaw" or "DirtinessScale" or "ObjectBounds" or "AmountProduced" or "Tier" or "Value") continue;
            object? v;
            try { v = pr.GetValue(rec); } catch { continue; }
            if (v == null) continue;
            string text;
            if (v is IFormLinkGetter fl)
            {
                if (fl.IsNull) continue;
                text = $"{Hex(fl.FormKey)} {names.GetValueOrDefault(fl.FormKey, "?")}" + (byKey.TryGetValue(fl.FormKey, out var tr) ? $" [{tr.GetType().Name.Replace("BinaryOverlay", "")}]" : "");
                if (ArtLike.IsMatch(pr.Name) && byKey.TryGetValue(fl.FormKey, out var target)) follow.Add((pr.Name, target));
            }
            else if (v is ITranslatedStringGetter ts) { if (string.IsNullOrEmpty(ts.String)) continue; text = "\"" + ts.String + "\""; }
            else if (v is IModelGetter md) text = "model " + md.File;
            else if (v is string str) { if (str.Length == 0) continue; text = "\"" + str + "\""; }
            else if (v is System.Collections.IEnumerable en && v is not string)
            {
                var n = 0; foreach (var _ in en) n++;
                if (n == 0) continue;
                text = $"{n} item(s)";
            }
            else text = v.ToString() ?? "";
            if (text.Length > 140) text = text[..140] + "...";
            Console.WriteLine($"{pad}{pr.Name} = {text}{(ArtLike.IsMatch(pr.Name) ? "   <- art-like" : "")}");
        }
        if (depth == 0) foreach (var (nm, tr) in follow) Dump($"{nm} target {names.GetValueOrDefault(tr.FormKey, "?")}", tr, names, byKey, depth + 1);
    }

    // ---------------------------------------------------------------- build

    static CostComponent PickComponent(IConstructibleObjectGetter t, Dictionary<FormKey, string> names)
    {
        if (t.ConstructableComponents.Count == 0) throw new Refusal($"{t.EditorID} has no components: nothing to copy a cost from");
        var iron = t.ConstructableComponents.FirstOrDefault(k => names.GetValueOrDefault(k.Component.FormKey, "").Contains("Iron", StringComparison.OrdinalIgnoreCase));
        return new CostComponent((iron ?? t.ConstructableComponents[0]).Component.FormKey);
    }
    record CostComponent(FormKey Component);

    // --tab: a vanilla outpost category keyword (a short name or an editor id) that the recipes are filed under instead of our own keyword
    static FormKey? TabKey(IStarfieldModGetter sf, Options o)
    {
        if (o.Tab == null) return null;
        var edid = Tabs.GetValueOrDefault(o.Tab, o.Tab);
        var hits = sf.Keywords.Where(k => string.Equals(k.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} KYWD named {edid} in Starfield.esm (one needed): --tab is {string.Join(", ", Tabs.Keys)} or a keyword editor id");
        if (o.Category == "vanilla") throw new Refusal("--tab needs --category add or replace (vanilla keeps the template's filters)");
        return hits[0].FormKey;
    }

    // the keyword a recipe is filed under, as (workbench keyword, filters): replace = the tab replaces the template's workbench keyword AND
    // its filters; add = the template's workbench keyword and filters stay and the tab is appended to the filters
    static (FormKey Workbench, List<FormKey> Filters) Filing(IConstructibleObjectGetter t, Options o, FormKey? cat)
    {
        var tf = t.RecipeFilters.Select(f => f.FormKey).ToList();
        if (cat == null) return (t.WorkbenchKeyword.FormKey, tf);
        if (o.Tab != null) return o.Category == "add" ? (t.WorkbenchKeyword.FormKey, tf.Append(cat.Value).ToList()) : (cat.Value, new List<FormKey> { cat.Value });
        return (t.WorkbenchKeyword.FormKey, o.Category == "add" ? tf.Append(cat.Value).ToList() : tf.Skip(1).Append(cat.Value).ToList());
    }

    public static int Build(string sfPath, string corePath, string outDir, Options o)
    {
        using var sf = Open(sfPath);
        using var core = Open(corePath);
        var names = EditorIds(sf);
        var t = Template(sf, o.Cobj);
        var pieces = ChoosePieces(core, o);
        var comp = PickComponent(t, names);
        var made = sf.EnumerateMajorRecords().FirstOrDefault(r => r.FormKey == t.CreatedObject.FormKey);
        if (o.Shell == "clone" && made is not (IFurnitureGetter or IActivatorGetter or IStaticGetter))
            throw new Refusal($"--shell clone: the template's created object {t.CreatedObject.FormKey} is {made?.GetType().Name.Replace("BinaryOverlay", "") ?? "not in Starfield.esm"} (Furniture, Activator or Static can be copied): use --shell plain");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        FormKey? cat = TabKey(sf, o);
        if (o.Category != "vanilla" && cat == null)
        {
            var first = t.RecipeFilters.FirstOrDefault() ?? throw new Refusal($"{t.EditorID} has no recipe filter keyword to copy a category from");
            var kw = sf.Keywords.FirstOrDefault(k => k.FormKey == first.FormKey) ?? throw new Refusal($"the first filter {first.FormKey} is not a KYWD of Starfield.esm");
            var own = kw.Duplicate(Own(CategoryId));
            own.EditorID = CategoryEdid; own.Name = CategoryName;
            mod.Keywords.Add(own);
            cat = own.FormKey;
        }

        foreach (var p in pieces)
        {
            var shellKey = Own(ShellBase + (uint)(p.N - 1));
            switch (o.Shell == "clone" ? made : null)
            {
                case IFurnitureGetter f:
                    var f2 = f.Duplicate(shellKey);
                    f2.EditorID = $"FO4SF_BPShell{p.N}"; f2.Name = p.Name; f2.Model = new Model { File = p.Model }; f2.VirtualMachineAdapter = null;
                    mod.Furniture.Add(f2);
                    break;
                case IActivatorGetter a:
                    var a2 = a.Duplicate(shellKey);
                    a2.EditorID = $"FO4SF_BPShell{p.N}"; a2.Name = p.Name; a2.Model = new Model { File = p.Model }; a2.VirtualMachineAdapter = null;
                    mod.Activators.Add(a2);
                    break;
                case IStaticGetter s:
                    var s2 = s.Duplicate(shellKey);
                    s2.EditorID = $"FO4SF_BPShell{p.N}"; s2.Name = p.Name; s2.Model = new Model { File = p.Model }; s2.VirtualMachineAdapter = null;
                    mod.Statics.Add(s2);
                    break;
                default:
                    mod.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(shellKey, Release) { EditorID = $"FO4SF_BPShell{p.N}", Name = p.Name, Model = new Model { File = p.Model } });
                    break;
            }
            var rc = t.Duplicate(Own(RecipeBase + (uint)(p.N - 1)));
            rc.EditorID = $"FO4SF_BPRecipe{p.N}";
            rc.CreatedObject.SetTo(shellKey);
            rc.Description = p.Name;
            rc.MenuSortOrder = t.MenuSortOrder + p.N;
            rc.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent>
            {
                new ConstructibleObjectComponent { Component = new FormLink<IItemGetter>(comp.Component), RequiredCount = Cost(p.N) },
            };
            rc.VirtualMachineAdapter = null;
            if (cat != null)
            {
                var (wb, fl) = Filing(t, o, cat);
                rc.WorkbenchKeyword.SetTo(wb);
                var filters = new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
                foreach (var f in fl) filters.Add(new FormLink<IKeywordGetter>(f));
                rc.RecipeFilters = filters;
            }
            mod.ConstructibleObjects.Add(rc);
        }

        var q = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF build pieces", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        q.Stages.Add(new QuestStage { Index = 10 });
        q.VirtualMachineAdapter = new QuestAdapter { Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3, Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local } };
        q.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = Script, Flags = ScriptEntry.Flag.Local });
        mod.Quests.Add(q);
        mod.ModHeader.Stats.NextFormID = 0x860;
        if (!mod.ModHeader.MasterReferences.Any(m => m.Master == SfEsm)) mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, Plugin.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, Plugin.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full))
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally { if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true); }
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {pieces.Count} pieces, shell {o.Shell}, category {o.Category}{(o.Tab != null ? " tab " + o.Tab : "")}, template COBJ {t.EditorID} {Hex(t.FormKey)}, cost {names.GetValueOrDefault(comp.Component, "?")} x{string.Join(",", Enumerable.Range(1, pieces.Count).Select(i => Cost(i)))}");
        foreach (var p in pieces) Console.WriteLine($"  piece {p.N}: shell {ShellBase + p.N - 1:X6} recipe {RecipeBase + p.N - 1:X6} <- core {p.CoreId:X6} {p.Edid} model {p.Model}");
        return 0;
    }

    // ---------------------------------------------------------------- check (Mutagen read-back)

    public static int Check(string pluginPath, string sfPath, string corePath, Options o)
    {
        using var sf = Open(sfPath);
        using var core = Open(corePath);
        var t = Template(sf, o.Cobj);
        var names = EditorIds(sf);
        var pieces = ChoosePieces(core, o);
        var comp = PickComponent(t, names);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm }), "masters are not exactly [Starfield.esm] (the core must not be a master)");
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");
        var tabKey = TabKey(sf, o);
        int own = o.Category == "vanilla" || tabKey != null ? 0 : 1;
        int want = 1 + pieces.Count * 2 + own;
        Need(mod.EnumerateMajorRecords().Count() == want, $"not exactly {want} records ({pieces.Count} shells, {pieces.Count} COBJ, 1 QUST{(own == 0 ? "" : ", 1 KYWD")})");

        FormKey? catKey = tabKey;
        if (own == 1)
        {
            var k = mod.Keywords.FirstOrDefault(x => x.FormKey == Own(CategoryId));
            Need(k?.EditorID == CategoryEdid, $"no KYWD {CategoryEdid} at {Own(CategoryId)}");
            if (k != null) catKey = k.FormKey;
        }
        foreach (var p in pieces)
        {
            var shellKey = Own(ShellBase + (uint)(p.N - 1));
            var shell = mod.EnumerateMajorRecords().FirstOrDefault(r => r.FormKey == shellKey);
            Need(shell?.EditorID == $"FO4SF_BPShell{p.N}", $"no shell FO4SF_BPShell{p.N} at {shellKey}");
            string model = "", name = "";
            int scripts = 0;
            switch (shell)
            {
                case IFurnitureGetter f: model = f.Model?.File.ToString() ?? ""; name = f.Name?.String ?? ""; scripts = f.VirtualMachineAdapter?.Scripts.Count ?? 0; break;
                case IActivatorGetter a: model = a.Model?.File.ToString() ?? ""; name = a.Name?.String ?? ""; scripts = a.VirtualMachineAdapter?.Scripts.Count ?? 0; break;
                case IStaticGetter s: model = s.Model?.File.ToString() ?? ""; name = s.Name?.String ?? ""; scripts = s.VirtualMachineAdapter?.Scripts.Count ?? 0; break;
                default: if (shell != null) Need(false, $"shell {p.N} is a {shell.GetType().Name}"); break;
            }
            Console.WriteLine($"  piece {p.N}: shell {shell?.GetType().Name.Replace("BinaryOverlay", "")} {shellKey} \"{name}\" model {model} (core {p.CoreId:X6} {p.Edid})");
            Need(model == p.Model, $"shell {p.N} model {model} is not the core static's {p.Model}");
            Need(name == p.Name, $"shell {p.N} name {name} is not {p.Name}");
            Need(scripts == 0, $"shell {p.N} carries a script");
            if (o.Shell == "plain") Need(shell is IActivatorGetter, $"shell {p.N} is not an Activator");
            var rc = mod.ConstructibleObjects.FirstOrDefault(c => c.FormKey == Own(RecipeBase + (uint)(p.N - 1)));
            Need(rc?.EditorID == $"FO4SF_BPRecipe{p.N}", $"no COBJ FO4SF_BPRecipe{p.N}");
            if (rc == null) continue;
            Need(rc.CreatedObject.FormKey == shellKey, $"recipe {p.N} does not make shell {p.N}");
            var (wbWant, filtWant) = Filing(t, o, catKey);
            Need(rc.WorkbenchKeyword.FormKey == wbWant, $"recipe {p.N} workbench keyword is not {Hex(wbWant)} (the template's {Hex(t.WorkbenchKeyword.FormKey)}{(o.Tab != null && o.Category == "replace" ? ", replaced by the tab" : "")})");
            Need(rc.MaxBuildCountGlobal.FormKey == t.MaxBuildCountGlobal.FormKey, $"recipe {p.N} build limit is not the template's");
            Need(rc.ConstructableComponents.Count == 1 && rc.ConstructableComponents[0].Component.FormKey == comp.Component && rc.ConstructableComponents[0].RequiredCount == Cost(p.N),
                 $"recipe {p.N} cost is not {names.GetValueOrDefault(comp.Component, "?")} x{Cost(p.N)}");
            var filters = rc.RecipeFilters.Select(f => f.FormKey).ToList();
            Need(filters.SequenceEqual(filtWant), $"recipe {p.N} filters are not [{string.Join(", ", filtWant.Select(Hex))}]");
            Console.WriteLine($"    COBJ {rc.FormKey} makes {Hex(rc.CreatedObject.FormKey)}, workbench {Hex(rc.WorkbenchKeyword.FormKey)}, filters [{string.Join(", ", filters.Select(Hex))}], cost {Hex(comp.Component)} x{rc.ConstructableComponents.FirstOrDefault()?.RequiredCount}, sort {rc.MenuSortOrder}");
        }
        var qq = mod.Quests.FirstOrDefault(x => x.FormKey == Own(QuestId));
        Need(qq?.EditorID == QuestEdid, $"no QUST {QuestEdid}");
        if (qq != null)
        {
            var sc = qq.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Need(qq.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "the quest is not start game enabled");
            Need(sc.Count == 1 && sc[0].Name == Script && sc[0].Properties.Count == 0, $"the quest script is not {Script} without properties");
        }
        var kinds = mod.EnumerateMajorRecords().GroupBy(r => r.GetType().Name.Replace("BinaryOverlay", "")).Select(g => $"{g.Key} {g.Count()}");
        Console.WriteLine($"  records: {string.Join(", ", kinds)}");
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        FormKey S(uint id) => new(SfEsm, id);
        var wb = new Keyword(S(0x000E01), Release) { EditorID = "OutpostCategoryCrafting" };
        var f1 = new Keyword(S(0x000E02), Release) { EditorID = "OutpostFilterCraftingStations" };
        var f2 = new Keyword(S(0x000E03), Release) { EditorID = "OutpostFilterCraftingAll" };
        sf.Keywords.Add(wb); sf.Keywords.Add(f1); sf.Keywords.Add(f2);
        uint tabId = 0x000E20;
        foreach (var kv in Tabs.Values) sf.Keywords.Add(new Keyword(S(tabId++), Release) { EditorID = kv });   // OutpostCategoryStructures .. Defenses
        var limit = new Global(S(0x000E10), Release) { EditorID = "OutpostStationLimit" };
        sf.Globals.Add(limit);
        var ironRes = new Ingestible(S(0x000B11), Release) { EditorID = "ResOre_Iron" };
        var alumRes = new Ingestible(S(0x000B12), Release) { EditorID = "ResOre_Aluminum" };
        sf.Ingestibles.Add(ironRes); sf.Ingestibles.Add(alumRes);
        var bench = new Furniture(S(0x000C01), Release) { EditorID = "Workbench_Industrial", Name = "Industrial Workbench", Model = new Model { File = "Props\\Bench.nif" } };
        sf.Furniture.Add(bench);
        var c = new ConstructibleObject(S(0x2E2F2C), Release) { EditorID = DefaultCobj, MenuSortOrder = 10 };
        c.CreatedObject.SetTo(bench.FormKey);
        c.WorkbenchKeyword.SetTo(wb.FormKey);
        c.MaxBuildCountGlobal.SetTo(limit.FormKey);
        c.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(f1.FormKey), new FormLink<IKeywordGetter>(f2.FormKey) };
        c.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent>
        {
            new ConstructibleObjectComponent { Component = new FormLink<IItemGetter>(alumRes.FormKey), RequiredCount = 4 },
            new ConstructibleObjectComponent { Component = new FormLink<IItemGetter>(ironRes.FormKey), RequiredCount = 3 },
        };
        sf.ConstructibleObjects.Add(c);
        var path = Path.Combine(outDir, "Starfield.esm");
        sf.BeginWrite.ToPath(path).WithNoLoadOrder().Write();

        var core = new StarfieldMod(ModKey.FromFileName("FO4TerrainCore.esm"), Release);
        core.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        void St(uint id, string edid, string model) =>
            core.Statics.Add(new Static(new FormKey(core.ModKey, id), Release) { EditorID = edid, Model = new Model { File = model } });
        St(0x0A2001, "FO4Core_stat_000a01_fallout4", "Architecture\\Industrial\\IndWallCollisionBlock01.nif");   // skipped by the default choice (collision)
        St(0x0A2002, "FO4Core_stat_000a02_fallout4", "Props\\Crate01.nif");
        St(0x0A2003, "FO4Core_stat_000a03_fallout4", "Props\\Barrel02.nif");
        St(0x0A2004, "FO4Core_stat_000a04_fallout4", "Props\\Barrel02.nif");                                   // a second use of one model: skipped
        St(0x0A2005, "FO4Core_stat_000a05_fallout4", "Architecture\\Wall\\ConcreteWall01.nif");
        St(0x0A2006, "FO4Core_stat_000a06_fallout4", "Props\\Locker03.nif");
        St(0x0A2007, "FO4Core_stat_000a07_fallout4", "Props\\Sign09.nif");
        St(0x0A2010, "FO4Core_junkwall01", "Architecture\\Junk\\JunkWall01.nif");                     // the named set (--set fo4)
        St(0x0A2011, "FO4Core_junkwall02", "Architecture\\Junk\\JunkWall02.nif");
        St(0x0A2012, "FO4Core_piershackwall01", "Architecture\\Pier\\PierShackWall01.nif");          // a * entry
        St(0x0A2013, "FO4Core_piershackwall02", "Architecture\\Pier\\PierShackWall02.nif");
        St(0x0A2014, "FO4Core_woodcrate", "Props\\WoodCrate.nif");
        core.BeginWrite.ToPath(Path.Combine(outDir, "FO4TerrainCore.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {path} and {Path.Combine(outDir, "FO4TerrainCore.esm")}");
        return 0;
    }
}
