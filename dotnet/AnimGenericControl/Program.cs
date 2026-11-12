// AnimGenericControl: the control for the Vault 111 console's four stages in a row (docs/research/anim-generic-control.md, FAL-489,
// the Scribe's document vault111-console-stages rev 2).
//
// FO4SFAnimGeneric.esm (master Starfield.esm only; adds two records, overrides none):
//   QUST  FO4SF_AnimGenericQuest   start game enabled, stages 10 20 21..29 30 40 60, script FO4SF_AnimGenericQuest, NO properties
//   ACTI  FO4SF_AnimGenericControl a COPY of the vanilla activator 001CCAC2 (IndIntAddonArtifactHolder01) with a new form id and editor
//                                  id, whose animation graph component names genericstategraph01 (no vanilla record does) and whose
//                                  CNAM folder is ours; model, rig (BNAM) and every other field are the vanilla record's
// The vanilla activator is NOT overridden (that would retarget every holder in the game while the plugin is loaded).
// The ids are the script's (tests/test_anim_generic.py compares).
//
// usage: AnimGenericControl info <Starfield.esm>                                  key=value lines of the vanilla control
//        AnimGenericControl build <Starfield.esm> <out dir> <graph ANAM> <CNAM>   the plugin; ANAM/CNAM as the game stores them
//        AnimGenericControl check <plugin> <Starfield.esm> <graph ANAM> <CNAM>    exit 1 on a mismatch
//        AnimGenericControl fixture <out dir>                                     a synthetic Starfield.esm holding the vanilla ACTI
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    if (rest.Count == 2 && rest[0] == "info") return Control.Info(rest[1]);
    if (rest.Count == 5 && rest[0] == "build") return Control.Build(rest[1], rest[2], rest[3], rest[4]);
    if (rest.Count == 5 && rest[0] == "check") return Control.Check(rest[1], rest[2], rest[3], rest[4]);
    if (rest.Count == 2 && rest[0] == "fixture") return Control.Fixture(rest[1]);
}
catch (Control.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: AnimGenericControl info <Starfield.esm> | build <Starfield.esm> <out dir> <ANAM> <CNAM> | check <plugin> <Starfield.esm> <ANAM> <CNAM> | fixture <out dir>");
return 2;

static class Control
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFAnimGeneric.esm");

    // the layout (scripts/newgame/FO4SF_AnimGenericQuest.psc carries the same ids)
    const uint QuestId = 0x800, ControlId = 0x801, VanillaId = 0x1CCAC2;
    const string QuestEdid = "FO4SF_AnimGenericQuest", ControlEdid = "FO4SF_AnimGenericControl", Script = "FO4SF_AnimGenericQuest";
    const string VanillaGraphWord = "activatorstategraph01", ControlGraphWord = "genericstategraph01";
    static readonly ushort[] Stages = { 10, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 40, 60 };

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    // the vanilla activator the control is copied from: it must exist and name the activator graph, or it is not the control we mean
    static IActivatorGetter Vanilla(IStarfieldModGetter sf, out IAnimationGraphComponentGetter graph)
    {
        var acti = sf.Activators.FirstOrDefault(a => a.FormKey == Sf(VanillaId))
                   ?? throw new Refusal($"no ACTI {VanillaId:X6} in Starfield.esm (the vanilla holder the control is copied from)");
        graph = acti.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault()
                ?? throw new Refusal($"ACTI {VanillaId:X6} {acti.EditorID} has no animation graph component");
        if (graph.ANAM == null || !graph.ANAM.Contains(VanillaGraphWord, StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"ACTI {VanillaId:X6} {acti.EditorID} names graph {graph.ANAM}, not {VanillaGraphWord}");
        if (string.IsNullOrEmpty(graph.BNAM) || string.IsNullOrEmpty(graph.CNAM))
            throw new Refusal($"ACTI {VanillaId:X6} {acti.EditorID} has no rig (BNAM) or clip folder (CNAM) to copy");
        return acti;
    }

    static void NeedGraph(string anam, string cnam)
    {
        if (!anam.Contains(ControlGraphWord, StringComparison.OrdinalIgnoreCase)) throw new Refusal($"the graph {anam} is not {ControlGraphWord}");
        if (string.IsNullOrWhiteSpace(cnam) || cnam.Contains("ArtifactHolder", StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"the clip folder {cnam} must be our own, not the vanilla holder's");
    }

    static Quest MakeQuest()
    {
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF generic graph control", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in Stages) quest.Stages.Add(new QuestStage { Index = s });
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = Script, Flags = ScriptEntry.Flag.Local });
        return quest;
    }

    // a copy of the vanilla record under our form key: every field and component the vanilla one has, but the graph component
    static Mutagen.Bethesda.Starfield.Activator MakeControl(IActivatorGetter vanilla, string anam, string cnam, string vanillaBnam)
    {
        var copy = vanilla.Duplicate(Own(ControlId));
        copy.EditorID = ControlEdid;
        foreach (var old in copy.Components.OfType<AnimationGraphComponent>().ToList()) copy.Components.Remove(old);
        copy.Components.Add(new AnimationGraphComponent { ANAM = anam, BNAM = vanillaBnam, CNAM = cnam });
        return copy;
    }

    public static int Info(string templatePath)
    {
        using var sf = OpenTemplate(templatePath);
        var acti = Vanilla(sf, out var graph);
        Console.WriteLine($"edid={acti.EditorID}");
        Console.WriteLine($"model={acti.Model?.File}");
        Console.WriteLine($"anam={graph.ANAM}");
        Console.WriteLine($"bnam={graph.BNAM}");
        Console.WriteLine($"cnam={graph.CNAM}");
        Console.WriteLine($"components={acti.Components.Count()}");
        return 0;
    }

    public static int Build(string templatePath, string outDir, string anam, string cnam)
    {
        NeedGraph(anam, cnam);
        using var sf = OpenTemplate(templatePath);
        var vanilla = Vanilla(sf, out var graph);
        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";
        mod.Quests.Add(MakeQuest());
        mod.Activators.Add(MakeControl(vanilla, anam, cnam, graph.BNAM!));
        mod.ModHeader.Stats.NextFormID = 0x802;
        // the copy points into Starfield.esm (keywords, sounds, ...): name the master (the check asserts exactly this one)
        mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} stages [{string.Join(",", Stages)}]; ACTI {ControlId:X6} {ControlEdid}");
        Console.WriteLine($"copied from ACTI {VanillaId:X6} {vanilla.EditorID} model {vanilla.Model?.File}; graph {graph.ANAM} -> {anam}; BNAM {graph.BNAM}; CNAM {graph.CNAM} -> {cnam}");
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

    public static int Check(string pluginPath, string templatePath, string anam, string cnam)
    {
        using var sf = OpenTemplate(templatePath);
        var vanilla = Vanilla(sf, out var vgraph);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Console.WriteLine($"vanilla holder in {templatePath}: ACTI {VanillaId:X6} {vanilla.EditorID} model {vanilla.Model?.File} ANAM {vgraph.ANAM} BNAM {vgraph.BNAM} CNAM {vgraph.CNAM}");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm }), "masters are not exactly [Starfield.esm]");
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");
        Need(mod.EnumerateMajorRecords().Count() == 2, "not exactly two records (the quest and the control activator)");
        Need(!mod.Cells.Records.Any(), "the plugin carries a cell");
        var q = mod.Quests.FirstOrDefault(x => x.FormKey == Own(QuestId));
        Need(q?.EditorID == QuestEdid, $"no QUST {QuestEdid}");
        if (q != null)
        {
            var scripts = q.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Console.WriteLine($"  QUST {q.EditorID} flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "the quest is not start game enabled");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), $"stages are not [{string.Join(",", Stages)}]");
            Need(scripts.Count == 1 && scripts[0].Name == Script && scripts[0].Properties.Count == 0, $"script is not {Script} without properties");
        }
        var a = mod.Activators.FirstOrDefault(x => x.FormKey == Own(ControlId));
        Need(mod.Activators.Count() == 1 && a != null, $"no single ACTI {ControlId:X6}");
        if (a != null)
        {
            var g = a.Components.OfType<IAnimationGraphComponentGetter>().ToList();
            Console.WriteLine($"  ACTI {a.EditorID} model {a.Model?.File} components {a.Components.Count()} graph {(g.Count == 1 ? $"ANAM {g[0].ANAM} BNAM {g[0].BNAM} CNAM {g[0].CNAM}" : $"{g.Count} graph components")}");
            Need(a.EditorID == ControlEdid, $"the ACTI is {a.EditorID}, not {ControlEdid}");
            Need(string.Equals(a.Model?.File, vanilla.Model?.File, StringComparison.OrdinalIgnoreCase), "the model is not the vanilla holder's");
            Need(g.Count == 1, "not exactly one animation graph component");
            if (g.Count == 1)
            {
                Need(g[0].ANAM == anam, $"graph is {g[0].ANAM}, not {anam}");
                Need(g[0].ANAM?.Contains(ControlGraphWord, StringComparison.OrdinalIgnoreCase) == true, $"the graph does not name {ControlGraphWord}");
                Need(g[0].BNAM == vgraph.BNAM, $"rig is {g[0].BNAM}, not the vanilla holder's {vgraph.BNAM}");
                Need(g[0].CNAM == cnam, $"clip folder is {g[0].CNAM}, not {cnam}");
                Need(g[0].CNAM != vgraph.CNAM, "the clip folder is still the vanilla holder's");
            }
            Need(a.Components.Count() == vanilla.Components.Count(), $"{a.Components.Count()} components, the vanilla holder has {vanilla.Components.Count()}");
            Need(a.FormKey != vanilla.FormKey, "the control has the vanilla form key (it would be an override)");
        }
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture

    public static int Fixture(string outDir)
    {
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var acti = new Mutagen.Bethesda.Starfield.Activator(Sf(VanillaId), Release) { EditorID = "IndIntAddonArtifactHolder01", Model = new Model { File = "Props\\ArtifactHolder\\ArtifactHolder01.nif" } };
        acti.Components.Add(new AnimationGraphComponent
        {
            ANAM = "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx",
            BNAM = "Props\\ArtifactHolder\\CharacterAssets\\skeleton.rig", CNAM = "Props\\ArtifactHolder\\Animations",
        });
        mod.Activators.Add(acti);
        Directory.CreateDirectory(outDir);
        mod.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")}");
        return 0;
    }
}
