// MarkerProbe: the map marker probe's plugin (FAL-771 / FAL-489, note sections 34 and 36).
//
// FO4SFMarkerProbe.esm (master Starfield.esm only):
//   QUST  FO4SF_MarkerProbeQuest  start game enabled, stages 10 20 30 40 50 60 70, script FO4SF_MarkerProbeQuest, NO properties
// Nothing else: the probe finds the markers it reads and moves with Game.GetFormFromFile (FO4TerrainCore.esm 0x0A775B, FO4SFMapMarkers.esm
// 0x0008F2 / 0x000900 / 0x000901), so this plugin overrides no record and masters neither of them.
//
// usage: MarkerProbe build <out dir>             writes <out dir>/FO4SFMarkerProbe.esm
//        MarkerProbe check <plugin>              exit 1 on a mismatch
//        MarkerProbe fixture <out dir>           a synthetic Starfield.esm in <out dir> (nothing else is needed)
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

if (args.Length == 2 && args[0] == "build") return MarkerProbe.Build(args[1]);
if (args.Length == 2 && args[0] == "check") return MarkerProbe.Check(args[1]);
if (args.Length == 2 && args[0] == "fixture") return MarkerProbe.Fixture(args[1]);
Console.Error.WriteLine("usage: MarkerProbe build <out dir> | check <plugin> | fixture <out dir>");
return 2;

static class MarkerProbe
{
    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFMarkerProbe.esm");

    // the layout (scripts/mapmarkers/FO4SF_MarkerProbeQuest.psc carries the same quest id and stages)
    const uint QuestId = 0x800;
    const string QuestEdid = "FO4SF_MarkerProbeQuest", Script = "FO4SF_MarkerProbeQuest";
    static readonly ushort[] Stages = { 10, 20, 30, 40, 50, 60, 70 };

    static FormKey Own(uint id) => new(Plugin, id);

    static Quest MakeQuest()
    {
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF marker probe", FormVersion = 581, Version2 = 12,
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

    public static int Build(string outDir)
    {
        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";
        mod.Quests.Add(MakeQuest());
        mod.ModHeader.Stats.NextFormID = 0x801;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, Plugin.FileName);
        // an existing plugin stays until the write succeeds; Mutagen needs the plugin's own file name, so write in a temp folder
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, Plugin.FileName);
            mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(SfEsm)
                .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full))
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid}, stages [{string.Join(",", Stages)}], script {Script}");
        return 0;
    }

    public static int Check(string pluginPath)
    {
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
        var all = mod.EnumerateMajorRecords().ToList();
        Need(all.Count == 1 && all[0].FormKey == Own(QuestId), "the plugin is not exactly the one quest 0x800");
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

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        sf.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")}");
        return 0;
    }
}
