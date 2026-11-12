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
//                [--workbench <kywd>] [--filter <kywd|own>]   the workbench keyword and the filter chosen separately (a keyword editor id or its
//                         6 hex digits; own = a KYWD of our own with a full name, FO4SF_BPCategory); the template's stays for the one not named
//                [--variants]   with --set fo4: the junk walls 01..07, the pier shack walls and the roofs are ONE recipe each whose created
//                         object is a form list (FO4SF_BPList1.., ids 852..) of one RECIPE per variant (FO4SF_BPInner<n>, ids 860..), each
//                         making its shell, as the vanilla bed entries (co_Outpost_Furniture_BedList02_Beds: nine _Decor recipes among them)
//                [--inner same|bare]   the inner recipes' filing: same as the list recipe (default) or no workbench keyword and no filter
//                [--lead none|shells]   the form list's order: only the recipes (default) or the shells first, then the recipes (as the vanilla list)
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
    bool Flag(string name) => rest.Remove(name);
    var o = new BuildPieces.Options(Opt("--cobj") ?? BuildPieces.DefaultCobj, Opt("--shell") ?? "clone", Opt("--category") ?? "vanilla", Opt("--pieces"), Opt("--tab"), Opt("--set"), Opt("--workbench"), Opt("--filter"), Flag("--variants"), Opt("--inner") ?? "same", Opt("--lead") ?? "none");
    if (o.Lead != "none" && o.Lead != "shells") throw new BuildPieces.Refusal("--lead is none or shells");
    if (o.Set != null && !BuildPieces.Sets.ContainsKey(o.Set)) throw new BuildPieces.Refusal("--set is one of: " + string.Join(", ", BuildPieces.Sets.Keys));
    if ((o.Workbench != null || o.Filter != null) && (o.Tab != null || o.Category != "vanilla")) throw new BuildPieces.Refusal("--workbench and --filter are their own choice: not together with --tab or --category add|replace");
    if (o.Inner != "same" && o.Inner != "bare") throw new BuildPieces.Refusal("--inner is same or bare");
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
                        "check <plugin> <Starfield.esm> <core.esm> | fixture <out dir>   [--pieces a,b,c] [--shell clone|plain] [--category vanilla|add|replace] [--workbench <keyword>] [--filter <keyword|own>] [--variants] [--inner same|bare] [--lead none|shells] [--tab <structures|furniture|decorations|miscellaneous|storage|defenses|keyword editor id>] [--set fo4] [--cobj <editor id>]");
return 2;

static class BuildPieces
{
    public class Refusal(string m) : Exception(m);
    public record Options(string Cobj, string Shell, string Category, string? Pieces, string? Tab = null, string? Set = null, string? Workbench = null, string? Filter = null, bool Variants = false, string Inner = "same", string Lead = "none");
    public record Piece(int N, uint CoreId, string Edid, string Model, string Name);
    // one recipe of the menu: a single piece, or (--variants) several shells in one form list (the menu's "VARIANTS" entry); ListIdx -1 = no list
    public record Entry(int K, string Name, List<Piece> Members, int ListIdx)
    {
        public bool IsList => ListIdx >= 0;
        public FormKey Key => IsList ? Own(ListBase + (uint)ListIdx) : Own(ShellBase + (uint)(Members[0].N - 1));
        // the recipe a piece is built by: the entry's own recipe, or (in a list) the piece's own inner recipe, one per variant
        public uint RecipeId(Piece p) => IsList ? InnerBase + (uint)(p.N - 1) : RecipeBase + (uint)(K - 1);
    }

    public const string DefaultCobj = "co_Outpost_Crafting_WorkbenchIndustrialStation";
    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFBuildPieces.esm");

    // the layout (scripts/planet/FO4SF_BPQuest.psc carries the quest id; the shells and recipes are found by the game's menu)
    public const int MaxPieces = 40;                                                   // room for 40 shells and 40 recipes
    const uint QuestId = 0x800, CategoryId = 0x801, ShellBase = 0x802, RecipeBase = 0x82A, ListBase = 0x852, InnerBase = 0x860;   // RecipeBase = ShellBase + MaxPieces; InnerBase = ListBase + MaxLists: one recipe per variant of a list
    const string QuestEdid = "FO4SF_BPQuest", Script = "FO4SF_BPQuest", CategoryEdid = "FO4SF_BPCategory", CategoryName = "FO4 pieces";
    static readonly uint[] Counts = { 1, 1, 2, 2 };                       // the small cost of piece 1..4, repeating
    static uint Cost(int n) => Counts[(n - 1) % Counts.Length];
    // named sets of core statics (--set): editor ids, exact or with * ; each is tried as FO4Core_<name> first, then as written
    public static readonly Dictionary<string, string[]> Sets = new()
    {
        ["fo4"] = new[] { "junkwall01", "junkwall02", "junkwall03", "junkwall04", "junkwall05", "junkwall06", "junkwall07", "junkwallcorner01", "junkwalldoor01", "junkwallgate01",
                          "piershackwall*", "piershackroof*", "sandbagsingle01", "bedmetal01", "cafetable01", "woodcrate", "cratelarge01", "metalbarrel01" },
    };
    public const int MaxLists = 14;
    // --variants: pieces that share one recipe, by core editor id (first match wins); the shells all take the group's name
    static readonly (string Name, Regex Match)[] VariantGroups =
    {
        ("FO4 junk wall", new Regex("^(FO4Core_)?junkwall0[1-7]$", RegexOptions.IgnoreCase)),
        ("FO4 pier shack wall", new Regex("^(FO4Core_)?piershackwall", RegexOptions.IgnoreCase)),
        ("FO4 pier shack roof", new Regex("^(FO4Core_)?piershackroof", RegexOptions.IgnoreCase)),
    };
    static List<Entry> Entries(List<Piece> pieces, Options o)
    {
        var res = new List<Entry>();
        if (!o.Variants)
            return pieces.Select((p, i) => new Entry(i + 1, p.Name, new List<Piece> { p }, -1)).ToList();
        var groups = new Dictionary<string, List<Piece>>();
        var order = new List<object>();
        foreach (var p in pieces)
        {
            var g = VariantGroups.FirstOrDefault(x => x.Match.IsMatch(p.Edid));
            if (g.Name == null) { order.Add(p); continue; }
            if (!groups.TryGetValue(g.Name, out var l)) { groups[g.Name] = l = new List<Piece>(); order.Add(g.Name); }
            l.Add(p with { Name = g.Name });
        }
        int k = 0, li = 0;
        foreach (var x in order)
        {
            k++;
            if (x is Piece sp) res.Add(new Entry(k, sp.Name, new List<Piece> { sp }, -1));
            else
            {
                var m = groups[(string)x];
                res.Add(m.Count > 1 ? new Entry(k, (string)x, m, li++) : new Entry(k, m[0].Name, m, -1));
            }
        }
        if (li > MaxLists) throw new Refusal($"{li} form lists: at most {MaxLists}");
        return res;
    }
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
        var rid = Entries(pieces, o).SelectMany(e => e.Members.Select(m => (m.N, Id: e.RecipeId(m)))).ToDictionary(x => x.N, x => x.Id);
        string Q(string s) => "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        Console.WriteLine("[" + string.Join(",", pieces.Select(p => $"{{\"n\":{p.N},\"core_id\":{p.CoreId},\"edid\":{Q(p.Edid)},\"model\":{Q(p.Model)},\"name\":{Q(p.Name)},\"recipe_id\":{rid[p.N]}}}")) + "]");
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
        if (rec is IFormListGetter fli)
        {
            Console.WriteLine($"    FLST {fli.Items.Count} item(s) (a VARIANTS entry's created object):");
            foreach (var it in fli.Items) {
                var ir = sf.EnumerateMajorRecords().FirstOrDefault(r => r.FormKey == it.FormKey);
                Console.WriteLine($"      {Hex(it.FormKey)} {N(it.FormKey)} [{(ir?.GetType().Name.Replace("BinaryOverlay", "") ?? "not in this file")}]");
                if (ir is IConstructibleObjectGetter ic)   // a recipe in the list (the vanilla variants): what it makes and how it is filed
                    Console.WriteLine($"        recipe makes {Hex(ic.CreatedObject.FormKey)} {N(ic.CreatedObject.FormKey)}, workbench {(ic.WorkbenchKeyword.IsNull ? "none" : Hex(ic.WorkbenchKeyword.FormKey) + " " + N(ic.WorkbenchKeyword.FormKey))}, filters [{string.Join(", ", L(ic.RecipeFilters).Select(f => N(f.FormKey)))}], limit {(ic.MaxBuildCountGlobal.IsNull ? "none" : N(ic.MaxBuildCountGlobal.FormKey))}, sort {ic.MenuSortOrder}, components {ic.ConstructableComponents?.Count ?? 0}, conditions {ic.Conditions?.Count ?? 0}, menu art {(ic.MenuArtObject.IsNull ? "none" : N(ic.MenuArtObject.FormKey))}, description \"{ic.Description?.String}\"");
            }
        }
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
            foreach (var x in wbs.Concat(fil).DistinctBy(x => x.FormKey).OrderBy(x => x.MenuArtObject.IsNull ? 1 : 0).ThenBy(x => x.FormKey.ID).Take(3))
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

    // a keyword of Starfield.esm by short tab name, editor id or its 6 hex digits (a form id, load index ignored)
    static FormKey Kw(IStarfieldModGetter sf, string tok, string flag)
    {
        var edid = Tabs.GetValueOrDefault(tok, tok);
        var hits = Regex.IsMatch(tok, "^[0-9A-Fa-f]{6,8}$")
            ? sf.Keywords.Where(k => k.FormKey.ID == (Convert.ToUInt32(tok, 16) & 0xFFFFFF)).ToList()
            : sf.Keywords.Where(k => string.Equals(k.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} KYWD named {edid} in Starfield.esm (one needed): {flag} is {string.Join(", ", Tabs.Keys)}, a keyword editor id or its form id (6 hex digits)");
        return hits[0].FormKey;
    }

    // --tab, or --filter <keyword>: the keyword the recipes are filed under instead of the template's filters (--filter own = our own keyword, made by Build)
    static FormKey? TabKey(IStarfieldModGetter sf, Options o)
    {
        if (o.Tab != null)
        {
            var k = Kw(sf, o.Tab, "--tab");
            if (o.Category == "vanilla") throw new Refusal("--tab needs --category add or replace (vanilla keeps the template's filters)");
            return k;
        }
        return o.Filter != null && o.Filter != "own" ? Kw(sf, o.Filter, "--filter") : null;
    }
    static FormKey? WorkbenchKey(IStarfieldModGetter sf, Options o) => o.Workbench == null ? null : Kw(sf, o.Workbench, "--workbench");
    // a keyword of our own: --category add|replace without a tab, or --filter own
    static bool OwnKeyword(Options o, FormKey? tab) => o.Filter == "own" || (o.Category != "vanilla" && tab == null);

    // the keyword a recipe is filed under, as (workbench keyword, filters): --workbench / --filter choose each separately (the template's
    // stays for the one not named); --tab: replace = the tab replaces the template's workbench keyword AND its filters, add = the template's
    // workbench keyword and filters stay and the tab is appended to the filters
    static (FormKey Workbench, List<FormKey> Filters) Filing(IConstructibleObjectGetter t, Options o, FormKey? cat, FormKey? wb = null)
    {
        var tf = t.RecipeFilters.Select(f => f.FormKey).ToList();
        if (o.Workbench != null || o.Filter != null)
            return (wb ?? t.WorkbenchKeyword.FormKey, o.Filter != null ? new List<FormKey> { cat!.Value } : tf);
        if (cat == null) return (t.WorkbenchKeyword.FormKey, tf);
        if (o.Tab != null) return o.Category == "add" ? (t.WorkbenchKeyword.FormKey, tf.Append(cat.Value).ToList()) : (cat.Value, new List<FormKey> { cat.Value });
        return (t.WorkbenchKeyword.FormKey, o.Category == "add" ? tf.Append(cat.Value).ToList() : tf.Skip(1).Append(cat.Value).ToList());
    }

    // a recipe: the template's copy with the created object, a small cost and the filing of --tab/--workbench/--filter; bare = no workbench
    // keyword and no filter (an inner recipe of a variants list that is not offered by a workshop itself)
    static ConstructibleObject Recipe(IConstructibleObjectGetter t, Options o, FormKey key, string edid, FormKey made, string desc, float sort, uint cost, CostComponent comp, FormKey? cat, FormKey? wbKey, bool bare)
    {
        var rc = t.Duplicate(key);
        rc.EditorID = edid;
        rc.CreatedObject.SetTo(made);
        rc.Description = desc;
        rc.MenuSortOrder = sort;
        rc.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent>
        {
            new ConstructibleObjectComponent { Component = new FormLink<IItemGetter>(comp.Component), RequiredCount = cost },
        };
        rc.VirtualMachineAdapter = null;
        if (bare)
        {
            rc.WorkbenchKeyword.SetToNull();
            rc.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
        }
        else if (cat != null || wbKey != null)
        {
            var (wb, fl) = Filing(t, o, cat, wbKey);
            rc.WorkbenchKeyword.SetTo(wb);
            var filters = new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
            foreach (var f in fl) filters.Add(new FormLink<IKeywordGetter>(f));
            rc.RecipeFilters = filters;
        }
        return rc;
    }

    public static int Build(string sfPath, string corePath, string outDir, Options o)
    {
        using var sf = Open(sfPath);
        using var core = Open(corePath);
        var names = EditorIds(sf);
        var t = Template(sf, o.Cobj);
        var pieces = ChoosePieces(core, o);
        var entries = Entries(pieces, o);
        var comp = PickComponent(t, names);
        var made = sf.EnumerateMajorRecords().FirstOrDefault(r => r.FormKey == t.CreatedObject.FormKey);
        if (o.Shell == "clone" && made is not (IFurnitureGetter or IActivatorGetter or IStaticGetter))
            throw new Refusal($"--shell clone: the template's created object {t.CreatedObject.FormKey} is {made?.GetType().Name.Replace("BinaryOverlay", "") ?? "not in Starfield.esm"} (Furniture, Activator or Static can be copied): use --shell plain");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        FormKey? cat = TabKey(sf, o);
        var wbKey = WorkbenchKey(sf, o);
        if (OwnKeyword(o, cat))
        {
            var first = t.RecipeFilters.FirstOrDefault() ?? throw new Refusal($"{t.EditorID} has no recipe filter keyword to copy a category from");
            var kw = sf.Keywords.FirstOrDefault(k => k.FormKey == first.FormKey) ?? throw new Refusal($"the first filter {first.FormKey} is not a KYWD of Starfield.esm");
            var own = kw.Duplicate(Own(CategoryId));
            own.EditorID = CategoryEdid; own.Name = CategoryName;
            mod.Keywords.Add(own);
            cat = own.FormKey;
        }

        foreach (var p in entries.SelectMany(e => e.Members))
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
        }

        foreach (var e in entries)
        {
            if (e.IsList)
            {
                var fl = new FormList(e.Key, Release) { EditorID = $"FO4SF_BPList{e.ListIdx + 1}" };
                // the vanilla way (co_Outpost_Furniture_BedList02_Beds): the list holds one RECIPE per variant, each making one shell
                // --lead shells: the variants' own objects come first in the list, then the recipes (the vanilla list's order: a pack-in and Furniture, then recipes)
                if (o.Lead == "shells")
                    foreach (var m in e.Members) fl.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(ShellBase + (uint)(m.N - 1))));
                foreach (var m in e.Members)
                {
                    fl.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(e.RecipeId(m))));
                    mod.ConstructibleObjects.Add(Recipe(t, o, Own(e.RecipeId(m)), $"FO4SF_BPInner{m.N}", Own(ShellBase + (uint)(m.N - 1)), m.Name, t.MenuSortOrder + 100 + m.N, Cost(m.N), comp, cat, wbKey, o.Inner == "bare"));
                }
                mod.FormLists.Add(fl);
            }
            mod.ConstructibleObjects.Add(Recipe(t, o, Own(RecipeBase + (uint)(e.K - 1)), $"FO4SF_BPRecipe{e.K}", e.Key, e.Name, t.MenuSortOrder + e.K, Cost(e.K), comp, cat, wbKey, false));
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
        mod.ModHeader.Stats.NextFormID = 0x888;   // 0x852..0x85F: the form lists (MaxLists); 0x860..0x887: the recipes inside them (MaxPieces)
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
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {pieces.Count} pieces in {entries.Count} recipe(s), shell {o.Shell}, category {o.Category}{(o.Tab != null ? " tab " + o.Tab : "")}{(o.Workbench != null ? " workbench " + o.Workbench : "")}{(o.Filter != null ? " filter " + o.Filter : "")}{(o.Variants ? " variants" : "")}, template COBJ {t.EditorID} {Hex(t.FormKey)}, cost {names.GetValueOrDefault(comp.Component, "?")} x{string.Join(",", entries.Select(e => Cost(e.K)))}");
        foreach (var e in entries)
        {
            if (e.IsList) Console.WriteLine($"  recipe {e.K} {RecipeBase + e.K - 1:X6} makes form list {e.Key.ID:X6} \"{e.Name}\" of {e.Members.Count} recipes (one per shell, from {InnerBase:X6})");
            foreach (var p in e.Members) Console.WriteLine($"  piece {p.N}: shell {ShellBase + p.N - 1:X6} recipe {e.RecipeId(p):X6} <- core {p.CoreId:X6} {p.Edid} model {p.Model}");
        }
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
        var entries = Entries(pieces, o);
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
        var wbWant0 = WorkbenchKey(sf, o);
        int own = OwnKeyword(o, tabKey) ? 1 : 0;
        int lists = entries.Count(e => e.IsList);
        int inner = entries.Where(e => e.IsList).Sum(e => e.Members.Count);
        int want = 1 + pieces.Count + entries.Count + lists + inner + own;
        Need(mod.EnumerateMajorRecords().Count() == want, $"not exactly {want} records ({pieces.Count} shells, {entries.Count} COBJ, {inner} inner COBJ, {lists} form list(s), 1 QUST{(own == 0 ? "" : ", 1 KYWD")})");

        FormKey? catKey = tabKey;
        if (own == 1)
        {
            var k = mod.Keywords.FirstOrDefault(x => x.FormKey == Own(CategoryId));
            Need(k?.EditorID == CategoryEdid, $"no KYWD {CategoryEdid} at {Own(CategoryId)}");
            if (k != null) catKey = k.FormKey;
        }
        foreach (var p in entries.SelectMany(e => e.Members))
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
        }
        foreach (var e in entries)
        {
            if (e.IsList)
            {
                var fl = mod.FormLists.FirstOrDefault(x => x.FormKey == e.Key);
                Need(fl?.EditorID == $"FO4SF_BPList{e.ListIdx + 1}", $"no FLST FO4SF_BPList{e.ListIdx + 1} at {e.Key}");
                Need(fl != null && fl.Items.Select(i => i.FormKey).SequenceEqual((o.Lead == "shells" ? e.Members.Select(m => Own(ShellBase + (uint)(m.N - 1))) : Enumerable.Empty<FormKey>()).Concat(e.Members.Select(m => Own(e.RecipeId(m))))), $"form list {e.ListIdx + 1} is not the recipes of the variants [{string.Join(", ", e.Members.Select(m => m.N))}]");
                foreach (var m in e.Members)
                {
                    var ir = mod.ConstructibleObjects.FirstOrDefault(c => c.FormKey == Own(e.RecipeId(m)));
                    Need(ir?.EditorID == $"FO4SF_BPInner{m.N}", $"no COBJ FO4SF_BPInner{m.N} at {Own(e.RecipeId(m))}");
                    if (ir == null) continue;
                    Need(ir.CreatedObject.FormKey == Own(ShellBase + (uint)(m.N - 1)), $"inner recipe {m.N} does not make shell {m.N}");
                    Need(o.Inner == "bare" ? ir.WorkbenchKeyword.IsNull && ir.RecipeFilters.Count == 0 : ir.WorkbenchKeyword.FormKey == Filing(t, o, catKey, wbWant0).Workbench && ir.RecipeFilters.Select(f => f.FormKey).SequenceEqual(Filing(t, o, catKey, wbWant0).Filters), $"inner recipe {m.N} filing is not --inner {o.Inner}");
                    Need(ir.ConstructableComponents.Count == 1 && ir.ConstructableComponents[0].Component.FormKey == comp.Component && ir.ConstructableComponents[0].RequiredCount == Cost(m.N), $"inner recipe {m.N} cost is not {names.GetValueOrDefault(comp.Component, "?")} x{Cost(m.N)}");
                    Console.WriteLine($"    inner COBJ {ir.FormKey} makes {Hex(ir.CreatedObject.FormKey)}, workbench {(ir.WorkbenchKeyword.IsNull ? "none" : Hex(ir.WorkbenchKeyword.FormKey))}, filters {ir.RecipeFilters.Count}");
                }
            }
            var p = e.Members[0];
            var rc = mod.ConstructibleObjects.FirstOrDefault(c => c.FormKey == Own(RecipeBase + (uint)(e.K - 1)));
            Need(rc?.EditorID == $"FO4SF_BPRecipe{e.K}", $"no COBJ FO4SF_BPRecipe{e.K}");
            if (rc == null) continue;
            Need(rc.CreatedObject.FormKey == e.Key, $"recipe {e.K} does not make {(e.IsList ? "form list " + (e.ListIdx + 1) : "shell " + p.N)}");
            var (wbWant, filtWant) = Filing(t, o, catKey, wbWant0);
            Need(rc.WorkbenchKeyword.FormKey == wbWant, $"recipe {e.K} workbench keyword is not {Hex(wbWant)} (the template's {Hex(t.WorkbenchKeyword.FormKey)}{(o.Tab != null && o.Category == "replace" ? ", replaced by the tab" : "")})");
            Need(rc.MaxBuildCountGlobal.FormKey == t.MaxBuildCountGlobal.FormKey, $"recipe {e.K} build limit is not the template's");
            Need(rc.ConstructableComponents.Count == 1 && rc.ConstructableComponents[0].Component.FormKey == comp.Component && rc.ConstructableComponents[0].RequiredCount == Cost(e.K),
                 $"recipe {e.K} cost is not {names.GetValueOrDefault(comp.Component, "?")} x{Cost(e.K)}");
            var filters = rc.RecipeFilters.Select(f => f.FormKey).ToList();
            Need(filters.SequenceEqual(filtWant), $"recipe {e.K} filters are not [{string.Join(", ", filtWant.Select(Hex))}]");
            Console.WriteLine($"    COBJ {rc.FormKey} \"{e.Name}\" makes {Hex(rc.CreatedObject.FormKey)}, workbench {Hex(rc.WorkbenchKeyword.FormKey)}, filters [{string.Join(", ", filters.Select(Hex))}], cost {Hex(comp.Component)} x{rc.ConstructableComponents.FirstOrDefault()?.RequiredCount}, sort {rc.MenuSortOrder}");
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
        // the keywords of --set fo4's default placement (2CFDE6 workbench keyword, 06D72D filter): the fixture's names are made up, the PC reads the real ones
        sf.Keywords.Add(new Keyword(S(0x2CFDE6), Release) { EditorID = "FO4SFTestBenchKeyword" });
        sf.Keywords.Add(new Keyword(S(0x06D72D), Release) { EditorID = "FO4SFTestFilterKeyword" });
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
        // a vanilla VARIANTS entry: a recipe whose created object is a form list (read with `menu --cobj co_Outpost_Furniture_BedList02_Beds`)
        var bed1 = new Furniture(S(0x000C02), Release) { EditorID = "OutpostFurnitureBed01", Name = "Bed", Model = new Model { File = "Props\\Bed01.nif" } };
        var bed2 = new Furniture(S(0x000C03), Release) { EditorID = "OutpostFurnitureBed02", Name = "Bunk", Model = new Model { File = "Props\\Bed02.nif" } };
        sf.Furniture.Add(bed1); sf.Furniture.Add(bed2);
        var bedList = new FormList(S(0x000C10), Release) { EditorID = "OutpostFurnitureBedList02_Beds" };
        bedList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(bed1.FormKey)); bedList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(bed2.FormKey));
        // the vanilla variants are RECIPES in the list (co_Outpost_Furniture_BedList02_Decor1_01 ...), each making one object
        var cd = new ConstructibleObject(S(0x2E3010), Release) { EditorID = "co_Outpost_Furniture_BedList02_Decor1_01", MenuSortOrder = 21 };
        cd.CreatedObject.SetTo(bed2.FormKey);
        cd.WorkbenchKeyword.SetTo(wb.FormKey);
        cd.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(f1.FormKey) };
        cd.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent> { new ConstructibleObjectComponent { Component = new FormLink<IItemGetter>(ironRes.FormKey), RequiredCount = 2 } };
        sf.ConstructibleObjects.Add(cd);
        bedList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(cd.FormKey));
        sf.FormLists.Add(bedList);
        var cb = new ConstructibleObject(S(0x2E3000), Release) { EditorID = "co_Outpost_Furniture_BedList02_Beds", MenuSortOrder = 20 };
        cb.CreatedObject.SetTo(bedList.FormKey);
        cb.WorkbenchKeyword.SetTo(wb.FormKey);
        cb.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(f1.FormKey) };
        sf.ConstructibleObjects.Add(cb);
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
