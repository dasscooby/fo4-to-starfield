// CogDoorProbe: the Vault 111 cog door's install route and its SetOpen fallback (FAL-756 / FAL-489, Plan B step 1).
//
// FO4SFCogDoor.esm (masters Starfield.esm + FO4Port.esm, in that order):
//   DOOR  (full kit only) an OVERRIDE of the DOOR base of the placed cog door reference (default FO4Port.esm 00126D): the record as it is,
//         its model replaced by the converted door on a NEW model path (so nothing archived is replaced), its AnimationGraphComponent
//         keeping the base's own ANAM (the door graph) with BNAM / CNAM pointing at the new rig and clip folder
//   QUST  FO4SF_CogDoorQuest  start game enabled, stages 10 20 30 40 50, script FO4SF_CogDoorQuest, NO properties
// "--control" writes the quest alone (no DOOR override): the installed port's own door answers the same SetOpen quest, the
// control for step 1.
//
// usage: CogDoorProbe info  <FO4Port.esm> <Starfield.esm> [--ref <hex id>]      read only: the reference's DOOR base, model, graph component
//        CogDoorProbe build <FO4Port.esm> <Starfield.esm> <out dir> --model <path below Meshes> --rig <BNAM> --anims <CNAM> [--ref <hex id>]
//        CogDoorProbe build <FO4Port.esm> <Starfield.esm> <out dir> --control [--ref <hex id>]
//        CogDoorProbe check <plugin> <FO4Port.esm> <Starfield.esm> (--model <..> --rig <..> --anims <..> | --control) [--ref <hex id>]   exit 1 on a mismatch
//        CogDoorProbe fixture <out dir>     a synthetic Starfield.esm and FO4Port.esm (one cell, one DOOR, one reference) in <out dir>
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
        if (i + 1 >= rest.Count) throw new CogDoorProbe.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }
    bool Flag(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return false;
        rest.RemoveAt(i);
        return true;
    }
    var refText = Opt("--ref") ?? CogDoorProbe.DefaultRef;
    var model = Opt("--model");
    var rig = Opt("--rig");
    var anims = Opt("--anims");
    var control = Flag("--control");
    if (control && (model != null || rig != null || anims != null))
        throw new CogDoorProbe.Refusal("--control writes no DOOR override: leave --model / --rig / --anims out");
    if (!control && (rest.Count == 4 && (rest[0] == "build" || rest[0] == "check")) && (model == null || rig == null || anims == null))
        throw new CogDoorProbe.Refusal("the full kit needs --model, --rig and --anims (or --control for the quest alone)");
    var refId = CogDoorProbe.ParseRef(refText);
    if (rest.Count == 3 && rest[0] == "info") return CogDoorProbe.Info(rest[1], rest[2], refId);
    if (rest.Count == 4 && rest[0] == "build") return CogDoorProbe.Build(rest[1], rest[2], rest[3], refId, control ? null : (model!, rig!, anims!));
    if (rest.Count == 4 && rest[0] == "check") return CogDoorProbe.Check(rest[1], rest[2], rest[3], refId, control ? null : (model!, rig!, anims!));
    if (rest.Count == 2 && rest[0] == "fixture") return CogDoorProbe.Fixture(rest[1]);
}
catch (CogDoorProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: CogDoorProbe info <FO4Port.esm> <Starfield.esm> [--ref H] | build <FO4Port.esm> <Starfield.esm> <out dir> (--model M --rig R --anims A | --control) [--ref H] | " +
                        "check <plugin> <FO4Port.esm> <Starfield.esm> (--model M --rig R --anims A | --control) [--ref H] | fixture <out dir>");
return 2;

static class CogDoorProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    public const string DefaultRef = "00126D";
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey PortEsm = ModKey.FromFileName("FO4Port.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFCogDoor.esm");

    // the layout (scripts/newgame/FO4SF_CogDoorQuest.psc carries the same quest id and stages)
    const uint QuestId = 0x800;
    const string QuestEdid = "FO4SF_CogDoorQuest", Script = "FO4SF_CogDoorQuest";
    static readonly ushort[] Stages = { 10, 20, 30, 40, 50 };

    static FormKey Own(uint id) => new(Plugin, id);

    public static uint ParseRef(string text)
    {
        var t = text.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? text[2..] : text;
        if (t.Length is < 1 or > 6 || !uint.TryParse(t, System.Globalization.NumberStyles.HexNumber, null, out var id) || id == 0)
            throw new Refusal($"--ref {text} is not a local form id (one to six hex digits, not zero)");
        return id;
    }

    static Cache<IModMasterStyledGetter, ModKey> Styles()
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(PortEsm, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter Open(string path) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = Styles() });

    /// <summary>The DOOR the placed reference (a local id of FO4Port.esm) stands on; refuses when the reference is missing or its base is not a DOOR of FO4Port.esm.</summary>
    static IDoorGetter FindBase(IStarfieldModGetter port, uint refId, out FormKey baseKey)
    {
        var refs = port.EnumerateMajorRecords<IPlacedObjectGetter>().Where(r => r.FormKey.ModKey == port.ModKey && r.FormKey.ID == refId).ToList();
        if (refs.Count != 1) throw new Refusal($"{refs.Count} placed references with local id {refId:X6} in {port.ModKey} (one needed)");
        var key = refs[0].Base.FormKey;
        baseKey = key;
        if (key.ModKey != port.ModKey)
            throw new Refusal($"the reference {refId:X6} stands on {key}, which is not a record of {port.ModKey}: an override needs that record's own plugin as a master");
        var doors = port.Doors.Where(d => d.FormKey == key).ToList();
        if (doors.Count != 1) throw new Refusal($"the base {key} of reference {refId:X6} is not a DOOR of {port.ModKey} ({doors.Count} DOOR records)");
        return doors[0];
    }

    static string Show(IDoorGetter d)
    {
        var g = d.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault();
        return $"DOOR {d.FormKey} {d.EditorID} name '{d.Name?.String}' model {d.Model?.File} graph component " +
               (g == null ? "none" : $"ANAM {g.ANAM} BNAM {g.BNAM} CNAM {g.CNAM}");
    }

    public static int Info(string portPath, string sfPath, uint refId)
    {
        using var port = Open(portPath);
        var d = FindBase(port, refId, out var key);
        Console.WriteLine($"REF {refId:X6} base {key}");
        Console.WriteLine(Show(d));
        Console.WriteLine($"BASE_ID 0x{d.FormKey.ID:X6}");
        Console.WriteLine($"MODEL {d.Model?.File}");
        Console.WriteLine($"GRAPH_ANAM {d.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault()?.ANAM}");
        return 0;
    }

    static Quest MakeQuest()
    {
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF cog door probe", FormVersion = 581, Version2 = 12,
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

    public static int Build(string portPath, string sfPath, string outDir, uint refId, (string Model, string Rig, string Anims)? files)
    {
        using var port = Open(portPath);
        var baseRec = FindBase(port, refId, out _);
        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";
        if (files is { } f)
        {
            var graph = baseRec.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault()
                ?? throw new Refusal($"{baseRec.FormKey} has no animation graph component: its door graph (ANAM) is the one the override keeps");
            var ov = baseRec.DeepCopy();                                           // an override: the same form key, FO4Port.esm
            ov.Model ??= new Model();
            ov.Model.File = f.Model;
            foreach (var old in ov.Components.OfType<AnimationGraphComponent>().ToList()) ov.Components.Remove(old);
            ov.Components.Add(new AnimationGraphComponent { ANAM = graph.ANAM, BNAM = f.Rig, CNAM = f.Anims });
            mod.Doors.Add(ov);
        }
        mod.Quests.Add(MakeQuest());
        mod.ModHeader.Stats.NextFormID = 0x801;
        Write(mod, outDir, SfEsm, PortEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): " + (files is null ? "control, the quest alone" : $"override of {Show(baseRec)}"));
        if (files is { } g) Console.WriteLine($"now model {g.Model}, graph component ANAM {baseRec.Components.OfType<IAnimationGraphComponentGetter>().First().ANAM} BNAM {g.Rig} CNAM {g.Anims}");
        Console.WriteLine($"BASE_ID 0x{baseRec.FormKey.ID:X6}");
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
            foreach (var m in masters)
                if (!mod.ModHeader.MasterReferences.Any(r => r.Master == m)) mod.ModHeader.MasterReferences.Add(new MasterReference { Master = m });
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

    public static int Check(string pluginPath, string portPath, string sfPath, uint refId, (string Model, string Rig, string Anims)? files)
    {
        using var port = Open(portPath);
        var baseRec = FindBase(port, refId, out _);
        using var mod = Open(pluginPath);
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm, PortEsm }), "masters are not exactly [Starfield.esm, FO4Port.esm]");
        var all = mod.EnumerateMajorRecords().ToList();
        var want = files is null ? 1 : 2;
        Need(all.Count == want, files is null ? "not exactly one record (the quest)" : "not exactly two records (the DOOR override and the quest)");
        var own = all.Where(r => r.FormKey.ModKey == Plugin).Select(r => r.FormKey).ToList();
        Need(own.Count == 1 && own[0] == Own(QuestId), "records of ours are not exactly the quest 0x800");
        if (files is null)
            Need(!mod.Doors.Any(), "the control holds a DOOR record: it must be the quest alone");
        else
        {
            var ovr = mod.Doors.FirstOrDefault();
            Need(mod.Doors.Count() == 1 && ovr != null && ovr.FormKey == baseRec.FormKey, $"the DOOR is not an override of {baseRec.FormKey}");
            if (ovr != null)
            {
                Console.WriteLine("  override: " + Show(ovr));
                var baseGraph = baseRec.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault();
                Need(ovr.EditorID == baseRec.EditorID, "the override's EditorID changed");
                Need(ovr.Name?.String == baseRec.Name?.String, "the override's name changed (the prompt must stay)");
                Need(ovr.Flags == baseRec.Flags, "the override's flags changed");
                Need(Equals(ovr.OpenSound, baseRec.OpenSound) && Equals(ovr.CloseSound, baseRec.CloseSound), "the override's sounds changed");
                var wantModel = new Model { File = files.Value.Model }.File.ToString();                 // Mutagen files a model path as Meshes/<path>
                Need(ovr.Model?.File?.ToString() == wantModel, $"the model is not {wantModel}");
                Need(ovr.Model?.File?.ToString() != baseRec.Model?.File?.ToString(), "the model path is the port's own: the override would shadow an archived file, not use a new path");
                var g = ovr.Components.OfType<IAnimationGraphComponentGetter>().ToList();
                Need(g.Count == 1 && baseGraph != null && g[0].ANAM == baseGraph.ANAM && g[0].BNAM == files.Value.Rig && g[0].CNAM == files.Value.Anims,
                     "the animation graph component is not (the base's door graph, the new rig, the new clip folder) exactly once");
                Need(ovr.Components.Count() == baseRec.Components.Count(), "the override dropped or added another component");
            }
        }
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
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        sf.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        var port = new StarfieldMod(PortEsm, Release);
        port.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var door = new Door(new FormKey(PortEsm, 0x00DEF9), Release)
        {
            EditorID = "FO4Port_door_vltgeardoor01", Name = "Door", Model = new Model { File = "fo4port\\interiors\\vault\\doors\\vltgeardoor\\vltgeardoor01.nif" },
        };
        door.Components.Add(new AnimationGraphComponent
        {
            ANAM = "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx",
            BNAM = "fo4port\\interiors\\vault\\doors\\vltgeardoor\\vltgeardoor01\\characterassets\\skeleton.rig",
            CNAM = "fo4port\\interiors\\vault\\doors\\vltgeardoor\\vltgeardoor01\\animations",
        });
        port.Doors.Add(door);
        var cell = new Cell(new FormKey(PortEsm, 0x0016D8), Release) { EditorID = "FO4Port_Vault111Cryo", Flags = Cell.Flag.IsInteriorCell };
        cell.Temporary.Add(new PlacedObject(new FormKey(PortEsm, 0x00126D), Release) { Base = new FormLink<IPlaceableObjectGetter>(door.FormKey) });
        var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        port.Cells.Records.Add(block);
        port.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
        port.BeginWrite.ToPath(Path.Combine(outDir, "FO4Port.esm")).WithLoadOrder(SfEsm)
            .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).WithMastersListContent(MastersListContentOption.NoCheck).Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")} and {Path.Combine(outDir, "FO4Port.esm")}");
        return 0;
    }
}
