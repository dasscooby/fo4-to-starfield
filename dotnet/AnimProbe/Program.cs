// AnimProbe: variant A of the Vault 111 animation experiment, the vanilla control (docs/research/anim-probe.md, FAL-489).
//
// FO4SFAnimProbe.esm (master Starfield.esm only; adds one record, overrides none):
//   QUST  FO4SF_AnimProbeQuest   start game enabled, stages 10 20 21..28 30 40 60, script FO4SF_AnimProbeQuest, NO properties
// The quest's script spawns the VANILLA activator ACTI 001CCAC2 of Starfield.esm with PlaceAtMe and talks to it; nothing of ours
// is attached to that activator, so the plugin carries no ACTI, no REFR and no cell. build checks that Starfield.esm really has
// that ACTI with an animation graph component naming activatorstategraph01 and refuses otherwise.
// The local id is the script's (tests/test_anim_probe.py compares).
//
// usage: AnimProbe build <Starfield.esm> <out dir>
//        AnimProbe check <plugin> <Starfield.esm>      exit 1 on a mismatch
//        AnimProbe fixture <out dir>                   a synthetic Starfield.esm holding the vanilla ACTI looked up
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    if (rest.Count == 3 && rest[0] == "build") return AnimProbe.Build(rest[1], rest[2]);
    if (rest.Count == 3 && rest[0] == "check") return AnimProbe.Check(rest[1], rest[2]);
    if (rest.Count == 2 && rest[0] == "fixture") return AnimProbe.Fixture(rest[1]);
}
catch (AnimProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: AnimProbe build <Starfield.esm> <out dir> | check <plugin> <Starfield.esm> | fixture <out dir>");
return 2;

static class AnimProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFAnimProbe.esm");

    // the layout (scripts/newgame/FO4SF_AnimProbeQuest.psc carries the same ids)
    const uint QuestId = 0x800, ActiId = 0x1CCAC2;
    const string QuestEdid = "FO4SF_AnimProbeQuest", Script = "FO4SF_AnimProbeQuest", GraphWord = "activatorstategraph01";
    static readonly ushort[] Stages = { 10, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 40, 60 };

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    // the vanilla activator the quest spawns: it must exist and name the graph, or the control is not the control
    static IActivatorGetter VanillaActi(IStarfieldModGetter sf, out IAnimationGraphComponentGetter graph)
    {
        var acti = sf.Activators.FirstOrDefault(a => a.FormKey == Sf(ActiId))
                   ?? throw new Refusal($"no ACTI {ActiId:X6} in Starfield.esm (the vanilla control the probe spawns)");
        graph = acti.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault()
                ?? throw new Refusal($"ACTI {ActiId:X6} {acti.EditorID} has no animation graph component");
        if (graph.ANAM == null || !graph.ANAM.Contains(GraphWord, StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"ACTI {ActiId:X6} {acti.EditorID} names graph {graph.ANAM}, not {GraphWord}");
        return acti;
    }

    static Quest MakeQuest()
    {
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF animation probe", FormVersion = 581, Version2 = 12,
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

    public static int Build(string templatePath, string outDir)
    {
        using var sf = OpenTemplate(templatePath);
        var acti = VanillaActi(sf, out var graph);
        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";
        mod.Quests.Add(MakeQuest());
        mod.ModHeader.Stats.NextFormID = 0x801;
        // nothing of ours points into Starfield.esm: name the master anyway (the check asserts it)
        mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} stages [{string.Join(",", Stages)}]");
        Console.WriteLine($"vanilla control: ACTI {ActiId:X6} {acti.EditorID} model {acti.Model?.File} ANAM {graph.ANAM} BNAM {graph.BNAM} CNAM {graph.CNAM}");
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

    public static int Check(string pluginPath, string templatePath)
    {
        using var sf = OpenTemplate(templatePath);
        var acti = VanillaActi(sf, out var graph);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Console.WriteLine($"vanilla control in {templatePath}: ACTI {ActiId:X6} {acti.EditorID} model {acti.Model?.File} ANAM {graph.ANAM} BNAM {graph.BNAM} CNAM {graph.CNAM}");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm }), "masters are not exactly [Starfield.esm]");
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");
        Need(mod.EnumerateMajorRecords().Count() == 1, "not exactly one record (the quest)");
        Need(!mod.Cells.Records.Any() && !mod.Activators.Any(), "the plugin carries a cell or an ACTI (it must not)");
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
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture

    public static int Fixture(string outDir)
    {
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var acti = new Mutagen.Bethesda.Starfield.Activator(Sf(ActiId), Release) { EditorID = "IndIntAddonArtifactHolder01", Model = new Model { File = "Props\\ArtifactHolder\\ArtifactHolder01.nif" } };
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
