// WorkshopProbe: what makes a placed workbench a workshop the game accepts? (docs/research/workshop-probe.md)
//
// FO4SFWorkshopProbe.esm (master Starfield.esm only; adds records, overrides none). The installed core is NOT a master:
// nothing here points at a core record, the scripts find the core's workshop base with Game.GetFormFromFile (so the
// plugin loads wherever it is put and never wants a master that is not there; the core's cells are never overridden).
//   QUST  FO4SF_WSProbeQuest   start game enabled, stages 10 12 13 20 21 22 23 24 30 31 32 33 34 40 50 60, script FO4SF_WSProbeQuest, NO properties
//   QUST  FO4SF_WSHandQuest    the by-hand mode: start game enabled, one stage, script FO4SF_WSHandQuest, NO properties
//   MISC  FO4SF_WSKit          the hand mode's item: a copy of one vanilla MISC (the one named by --item, or the first of a
//                              fixed list found in Starfield.esm), no script, renamed
// The local ids are the scripts' (tests/test_workshop_probe.py compares).
//
// usage: WorkshopProbe build <Starfield.esm> <out dir> [--item <MISC editor id>]
//        WorkshopProbe check <plugin> <Starfield.esm> [--item <MISC editor id>]     exit 1 on a mismatch
//        WorkshopProbe fixture <out dir>             a synthetic Starfield.esm holding the MISC looked up
//        WorkshopProbe survey <Starfield.esm>        read only: every record whose editor id or script name says outpost /
//                                                    beacon / workshop (type, form id, editor id, scripts): for --beacon
//        WorkshopProbe resources <Starfield.esm> [--match <regex>]   read only: the COBJ whose created object's editor id
//                                                    matches (default: Workbench|Lab|Station), its components, and the
//                                                    player.additem lines for the sum of them
using System.Globalization;
using System.Text.RegularExpressions;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string? Opt(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new WorkshopProbe.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }
    var item = Opt("--item");
    var match = Opt("--match") ?? "Workbench|Lab|Station";
    if (rest.Count == 3 && rest[0] == "build") return WorkshopProbe.Build(rest[1], rest[2], item);
    if (rest.Count == 3 && rest[0] == "check") return WorkshopProbe.Check(rest[1], rest[2], item);
    if (rest.Count == 2 && rest[0] == "fixture") return WorkshopProbe.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "survey") return WorkshopProbe.Survey(rest[1]);
    if (rest.Count == 2 && rest[0] == "resources") return WorkshopProbe.Resources(rest[1], match);
}
catch (WorkshopProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: WorkshopProbe build <Starfield.esm> <out dir> [--item <edid>] | check <plugin> <Starfield.esm> [--item <edid>] | " +
                        "fixture <out dir> | survey <Starfield.esm> | resources <Starfield.esm> [--match <regex>]");
return 2;

static class WorkshopProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFWorkshopProbe.esm");

    // the layout (scripts/planet/FO4SF_WSProbeQuest.psc and FO4SF_WSHandQuest.psc carry the same ids)
    const uint QuestId = 0x800, HandQuestId = 0x801, KitId = 0x802;
    const string QuestEdid = "FO4SF_WSProbeQuest", Script = "FO4SF_WSProbeQuest", HandQuestEdid = "FO4SF_WSHandQuest",
        HandScript = "FO4SF_WSHandQuest", KitEdid = "FO4SF_WSKit", KitName = "FO4SF workshop kit";
    static readonly ushort[] Stages = { 10, 12, 13, 20, 21, 22, 23, 24, 30, 31, 32, 33, 34, 40, 50, 60 };
    // the kit is a copy of the first of these that Starfield.esm has as a MISC; failing all, the lowest form id with a model
    static readonly string[] ItemPrefs = { "Misc_Junk_Fork", "Junk_Fork", "Misc_Fork", "Misc_Cup", "Misc_Mug" };

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static IMiscItemGetter PickItem(IStarfieldModGetter sf, string? edid)
    {
        var all = sf.MiscItems.ToList();
        if (edid != null)
        {
            var hits = all.Where(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
            if (hits.Count != 1) throw new Refusal($"{hits.Count} MISC named {edid} in Starfield.esm (one needed)");
            return hits[0];
        }
        foreach (var p in ItemPrefs)
        {
            var hit = all.FirstOrDefault(x => string.Equals(x.EditorID, p, StringComparison.OrdinalIgnoreCase));
            if (hit != null) return hit;
        }
        var any = all.Where(x => x.Model != null && !string.IsNullOrEmpty(x.EditorID)).OrderBy(x => x.FormKey.ID).FirstOrDefault();
        return any ?? throw new Refusal("no MISC with a model in Starfield.esm: name one with --item");
    }

    // ---------------------------------------------------------------- build

    static Quest MakeQuest(uint id, string edid, string name, string script, IEnumerable<ushort> stages)
    {
        var quest = new Quest(Own(id), Release)
        {
            EditorID = edid, Name = name, FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in stages) quest.Stages.Add(new QuestStage { Index = s });
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = script, Flags = ScriptEntry.Flag.Local });
        return quest;
    }

    public static int Build(string templatePath, string outDir, string? itemEdid)
    {
        using var sf = OpenTemplate(templatePath);
        var item = PickItem(sf, itemEdid);
        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";

        var kit = (MiscItem)item.Duplicate(Own(KitId), new MiscItem.TranslationMask(defaultOn: true) { Name = false });
        kit.EditorID = KitEdid;
        kit.Name = KitName;
        kit.VirtualMachineAdapter = null;                                          // the vanilla item's scripts stay with it
        mod.MiscItems.Add(kit);

        mod.Quests.Add(MakeQuest(QuestId, QuestEdid, "FO4SF workshop probe", Script, Stages));
        mod.Quests.Add(MakeQuest(HandQuestId, HandQuestEdid, "FO4SF workshop by hand", HandScript, new ushort[] { 10 }));
        mod.ModHeader.Stats.NextFormID = 0x810;
        // no record of ours points into Starfield.esm unless the copied item does: name the master anyway (the check asserts it)
        if (!mod.ModHeader.MasterReferences.Any(m => m.Master == SfEsm)) mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });

        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): MISC {KitEdid} = copy of {item.EditorID} {item.FormKey}, " +
                          $"QUST {QuestEdid} stages [{string.Join(",", Stages)}], QUST {HandQuestEdid}");
        return 0;
    }

    static void Write(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        // an existing plugin stays until the write succeeds; Mutagen needs the plugin's own file name, so write in a temp folder
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray())
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check (Mutagen read-back)

    public static int Check(string pluginPath, string templatePath, string? itemEdid)
    {
        using var sf = OpenTemplate(templatePath);
        var item = PickItem(sf, itemEdid);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm }), "masters are not exactly [Starfield.esm]");
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");
        Need(mod.EnumerateMajorRecords().Count() == 3, "not exactly three records (MISC and two QUST)");

        var kit = mod.MiscItems.SingleOrDefault();
        Need(kit?.FormKey == Own(KitId) && kit.EditorID == KitEdid, "not exactly our MISC");
        if (kit != null)
        {
            Console.WriteLine($"  MISC {kit.EditorID} {kit.FormKey} name {kit.Name?.String} (copy of {item.EditorID} {item.FormKey}) scripts {kit.VirtualMachineAdapter?.Scripts.Count ?? 0}");
            Need(kit.Name?.String == KitName, "the MISC is not renamed");
            Need((kit.VirtualMachineAdapter?.Scripts.Count ?? 0) == 0, "the MISC carries a script");
            Console.WriteLine($"  model {kit.Model?.File} (copied item {item.Model?.File})");
            Need(kit.Model?.File?.ToString() == item.Model?.File?.ToString(), "the MISC model differs from the copied item's");
        }
        void QuestCheck(uint id, string edid, string script, IEnumerable<ushort> stages)
        {
            var q = mod.Quests.FirstOrDefault(x => x.FormKey == Own(id));
            Need(q?.EditorID == edid, $"no QUST {edid}");
            if (q == null) return;
            var scripts = q.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Console.WriteLine($"  QUST {q.EditorID} flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, $"{edid} is not start game enabled");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(stages), $"{edid} stages are not [{string.Join(",", stages)}]");
            Need(scripts.Count == 1 && scripts[0].Name == script && scripts[0].Properties.Count == 0, $"{edid} script is not {script} without properties");
        }
        QuestCheck(QuestId, QuestEdid, Script, Stages);
        QuestCheck(HandQuestId, HandQuestEdid, HandScript, new ushort[] { 10 });
        var kinds = mod.EnumerateMajorRecords().GroupBy(r => r.GetType().Name.Replace("BinaryOverlay", "")).Select(g => $"{g.Key} {g.Count()}");
        Console.WriteLine($"  records: {string.Join(", ", kinds)}");
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- survey and resources (read only)

    static string Hex(FormKey k) => $"{k.ID:X6}";

    public static int Survey(string templatePath)
    {
        using var sf = OpenTemplate(templatePath);
        var rx = new Regex("outpost|beacon|workshop", RegexOptions.IgnoreCase);
        int n = 0;
        foreach (var r in sf.EnumerateMajorRecords().OrderBy(r => r.GetType().Name).ThenBy(r => r.FormKey.ID))
        {
            var scripts = (r as IScriptedGetter)?.VirtualMachineAdapter?.Scripts.Select(s => s.Name).ToList() ?? new List<string>();
            var hit = rx.IsMatch(r.EditorID ?? "") || scripts.Any(s => rx.IsMatch(s));
            if (!hit) continue;
            if (r is not (IActivatorGetter or IMiscItemGetter or IFurnitureGetter or IContainerGetter or IStaticGetter or IKeywordGetter or IQuestGetter or ITerminalGetter)) continue;
            n++;
            Console.WriteLine($"{r.GetType().Name.Replace("BinaryOverlay", "")}\t{Hex(r.FormKey)}\t{r.EditorID}\t{string.Join(",", scripts)}");
        }
        Console.WriteLine($"survey: {n} record(s)");
        return 0;
    }

    public static int Resources(string templatePath, string match)
    {
        using var sf = OpenTemplate(templatePath);
        var rx = new Regex(match, RegexOptions.IgnoreCase);
        var names = sf.EnumerateMajorRecords().Where(r => !string.IsNullOrEmpty(r.EditorID)).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.First().EditorID!);
        var total = new SortedDictionary<FormKey, uint>(Comparer<FormKey>.Create((a, b) => a.ID.CompareTo(b.ID)));
        int stations = 0;
        // a COBJ component is often a resource record (IRES), not an item: the inventory item is the MISC whose body links the
        // IRES (PC, 11 Nov: ResInorgCommonIron 0057C7 -> MISC InorgCommonIron 00556E). Map each IRES / non-item to such a MISC.
        var miscLinks = new Dictionary<FormKey, List<IMiscItemGetter>>();
        foreach (var m in sf.MiscItems)
            foreach (var l in m.EnumerateFormLinks())
                if (l.FormKey != m.FormKey) { if (!miscLinks.TryGetValue(l.FormKey, out var lst)) miscLinks[l.FormKey] = lst = new(); lst.Add(m); }
        FormKey Item(FormKey comp, out string how)
        {
            if (sf.MiscItems.Any(m => m.FormKey == comp)) { how = "item"; return comp; }
            if (!miscLinks.TryGetValue(comp, out var hits) || hits.Count == 0) { how = "no MISC links it"; return comp; }
            var want = (names.GetValueOrDefault(comp, "")).Replace("Res", "", StringComparison.Ordinal);
            var pick = hits.FirstOrDefault(m => string.Equals(m.EditorID, want, StringComparison.OrdinalIgnoreCase)) ?? hits.OrderBy(m => m.FormKey.ID).First();
            how = $"MISC {Hex(pick.FormKey)} {pick.EditorID}" + (hits.Count > 1 ? $" (of {hits.Count} that link it)" : "");
            return pick.FormKey;
        }
        foreach (var c in sf.ConstructibleObjects.OrderBy(c => c.FormKey.ID))
        {
            if (c.CreatedObject.IsNull) continue;
            var made = names.GetValueOrDefault(c.CreatedObject.FormKey, "");
            if (!rx.IsMatch(made)) continue;
            stations++;
            var comps = c.ConstructableComponents.Select(k => (k.Component.FormKey, k.RequiredCount)).ToList();
            Console.WriteLine($"COBJ {Hex(c.FormKey)} {c.EditorID}: makes {Hex(c.CreatedObject.FormKey)} {made}, workbench keyword {(c.WorkbenchKeyword.IsNull ? "none" : names.GetValueOrDefault(c.WorkbenchKeyword.FormKey, Hex(c.WorkbenchKeyword.FormKey)))}");
            foreach (var (k, count) in comps)
            {
                var it = Item(k, out var how);
                Console.WriteLine($"    {Hex(k)} {names.GetValueOrDefault(k, "?")} x{count} -> {how}");
                if (how.StartsWith("no MISC")) continue;                       // never print an additem for something that is not an item
                total[it] = Math.Max(total.GetValueOrDefault(it), count);
            }
        }
        Console.WriteLine($"resources: {stations} COBJ matching /{match}/");
        foreach (var (k, count) in total) Console.WriteLine($"player.additem {k.ID:X8} {count * 2}");
        return stations == 0 ? 1 : 0;
    }

    // ---------------------------------------------------------------- fixture

    public static int Fixture(string outDir)
    {
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.MiscItems.Add(new MiscItem(Sf(0x000A01), Release) { EditorID = "Misc_Junk_Fork", Name = "Fork", Model = new Model { File = "Props\\Fork.nif" } });
        mod.MiscItems.Add(new MiscItem(Sf(0x000A02), Release) { EditorID = "Misc_Other", Name = "Other", Model = new Model { File = "Props\\Other.nif" } });
        // the real file: the COBJ components are resource records (IRES), the inventory item is a MISC that links the IRES.
        // The fixture stands an Ingestible in for the IRES and links it from the MISC through a message field (a stand-in:
        // only the FormKey is read). Aluminum is a plain item component (the direct case).
        var ironRes = new Ingestible(Sf(0x000B11), Release) { EditorID = "ResOre_Iron" };
        var ironMisc = new MiscItem(Sf(0x000B01), Release) { EditorID = "Ore_Iron", Model = new Model { File = "Props\\Iron.nif" } };
        ironMisc.FeaturedItemMessage.SetTo(new FormKey(SfEsm, 0x000B11));
        var decoy = new MiscItem(Sf(0x000B03), Release) { EditorID = "Zzz_Decoy_Iron", Model = new Model { File = "Props\\Iron.nif" } };
        decoy.FeaturedItemMessage.SetTo(new FormKey(SfEsm, 0x000B11));
        var alum = new MiscItem(Sf(0x000B02), Release) { EditorID = "Ore_Aluminum", Model = new Model { File = "Props\\Alu.nif" } };
        mod.Ingestibles.Add(ironRes);
        mod.MiscItems.Add(ironMisc);
        mod.MiscItems.Add(decoy);
        mod.MiscItems.Add(alum);
        var bench = new Furniture(Sf(0x000C01), Release) { EditorID = "Workbench_Industrial" };
        mod.Furniture.Add(bench);
        mod.Furniture.Add(new Furniture(Sf(0x000C02), Release) { EditorID = "OutpostBeaconFurniture" });
        var cobj = new ConstructibleObject(Sf(0x000D01), Release) { EditorID = "co_Workbench_Industrial" };
        cobj.CreatedObject.SetTo(bench.FormKey);
        cobj.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent>();
        cobj.ConstructableComponents.Add(new ConstructibleObjectComponent { Component = new FormLink<IItemGetter>(alum.FormKey), RequiredCount = 4 });
        cobj.ConstructableComponents.Add(new ConstructibleObjectComponent { Component = new FormLink<IItemGetter>(ironRes.FormKey), RequiredCount = 3 });
        mod.ConstructibleObjects.Add(cobj);
        Directory.CreateDirectory(outDir);
        mod.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")}");
        return 0;
    }
}
