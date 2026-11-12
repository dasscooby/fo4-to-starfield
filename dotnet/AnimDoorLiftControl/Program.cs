// AnimDoorLiftControl: two controls on two vanilla graphs nothing of ours has driven yet (docs/research/anim-doorlift-control.md, FAL-489, the
// Scribe's document vault111-gear-door rev 4 section 2c; Claude's request of 12 Nov 21:06 UTC).
//
// FO4SFAnimDoorLift.esm (master Starfield.esm only; adds two records, overrides none):
//   QUST  FO4SF_AnimDoorLiftQuest   start game enabled, stages 10 20 21..24 31..34 40 60, script FO4SF_AnimDoorLiftQuest, NO properties
//   ACTI  FO4SF_AnimDoorControl     a NEW activator that has the model, rig (BNAM) and clip folder (CNAM) of the vanilla DOOR
//                                   AK_Ext_Bld_WallA_DoorA_01_Alt02 (000AA24A) and whose animation graph is genericopenclose01 (no vanilla
//                                   record names it). The vanilla door is NOT overridden and not placed.
// The lift is the vanilla ShipQuickLift1 (00010C35), placed UNCHANGED by the quest; this tool only READS it (info / check print what the
// record is and which graph it names, so the session's card can say what was and was not the graph asked for).
//
// usage: AnimDoorLiftControl info <Starfield.esm>                                 key=value lines: the door's and the lift's facts
//        AnimDoorLiftControl build <Starfield.esm> <out dir> <graph ANAM>         the plugin; ANAM as the game stores it
//        AnimDoorLiftControl check <plugin> <Starfield.esm> <graph ANAM>          exit 1 on a mismatch
//        AnimDoorLiftControl fixture <out dir>                                    a synthetic Starfield.esm holding the DOOR and the lift
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    if (rest.Count == 2 && rest[0] == "info") return Control.Info(rest[1]);
    if (rest.Count == 4 && rest[0] == "build") return Control.Build(rest[1], rest[2], rest[3]);
    if (rest.Count == 4 && rest[0] == "check") return Control.Check(rest[1], rest[2], rest[3]);
    if (rest.Count == 2 && rest[0] == "fixture") return Control.Fixture(rest[1]);
}
catch (Control.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: AnimDoorLiftControl info <Starfield.esm> | build <Starfield.esm> <out dir> <ANAM> | check <plugin> <Starfield.esm> <ANAM> | fixture <out dir>");
return 2;

static class Control
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFAnimDoorLift.esm");

    // the layout (scripts/newgame/FO4SF_AnimDoorLiftQuest.psc carries the same ids)
    const uint QuestId = 0x800, ControlId = 0x801, DoorId = 0xAA24A, LiftId = 0x10C35;
    const string QuestEdid = "FO4SF_AnimDoorLiftQuest", ControlEdid = "FO4SF_AnimDoorControl", Script = "FO4SF_AnimDoorLiftQuest";
    const string ControlGraphWord = "genericopenclose01", DoorGraphWord = "simpleopenclose01", LiftGraphWord = "twostages";
    static readonly ushort[] Stages = { 10, 20, 21, 22, 23, 24, 31, 32, 33, 34, 40, 60 };

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    // the vanilla DOOR the control takes its model, rig and clip folder from: it must exist, carry a graph component and name SimpleOpenClose01
    static IDoorGetter Door(IStarfieldModGetter sf, out IAnimationGraphComponentGetter graph)
    {
        var door = sf.Doors.FirstOrDefault(d => d.FormKey == Sf(DoorId))
                   ?? throw new Refusal($"no DOOR {DoorId:X6} in Starfield.esm (the vanilla door the control takes its model and clips from)");
        graph = door.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault()
                ?? throw new Refusal($"DOOR {DoorId:X6} {door.EditorID} has no animation graph component (components: {Kinds(door.Components)})");
        if (graph.ANAM == null || !graph.ANAM.Contains(DoorGraphWord, StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"DOOR {DoorId:X6} {door.EditorID} names graph {graph.ANAM}, not {DoorGraphWord}");
        if (string.IsNullOrEmpty(graph.BNAM) || string.IsNullOrEmpty(graph.CNAM))
            throw new Refusal($"DOOR {DoorId:X6} {door.EditorID} has no rig (BNAM) or clip folder (CNAM) to take");
        if (door.Model?.File == null) throw new Refusal($"DOOR {DoorId:X6} {door.EditorID} has no model");
        return door;
    }

    static string Kinds(IEnumerable<IAComponentGetter> c) => string.Join(", ", c.Select(x => x.GetType().Name));

    // the lift: READ ONLY, never refused (the session places it whatever it is); what it is, and which graph it names, is printed
    static (string Type, string? Edid, string? Model, string Graph, string Components) Lift(IStarfieldModGetter sf)
    {
        var key = Sf(LiftId);
        IModelGetter? Model(IModeledGetter? m) => m?.Model;
        string G(IEnumerable<IAComponentGetter> c)
        {
            var g = c.OfType<IAnimationGraphComponentGetter>().ToList();
            return g.Count == 0 ? "no animation graph component" : string.Join(" ; ", g.Select(x => $"ANAM {x.ANAM} BNAM {x.BNAM} CNAM {x.CNAM}"));
        }
        var a = sf.Activators.FirstOrDefault(x => x.FormKey == key);
        if (a != null) return ("ACTI", a.EditorID, a.Model?.File, G(a.Components), Kinds(a.Components));
        var f = sf.Furniture.FirstOrDefault(x => x.FormKey == key);
        if (f != null) return ("FURN", f.EditorID, f.Model?.File, G(f.Components), Kinds(f.Components));
        var d = sf.Doors.FirstOrDefault(x => x.FormKey == key);
        if (d != null) return ("DOOR", d.EditorID, d.Model?.File, G(d.Components), Kinds(d.Components));
        var any = sf.EnumerateMajorRecords().FirstOrDefault(x => x.FormKey == key);
        return any == null ? ("none", null, null, "no record " + key, "") : (any.GetType().Name, any.EditorID, null, "not read for this record type", "");
    }

    static void NeedGraph(string anam)
    {
        if (!anam.Contains(ControlGraphWord, StringComparison.OrdinalIgnoreCase)) throw new Refusal($"the graph {anam} is not {ControlGraphWord}");
    }

    static Quest MakeQuest()
    {
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF door and lift control", FormVersion = 581, Version2 = 12,
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

    // a NEW activator (a DOOR record is not an ACTI, so there is nothing to duplicate): the door's model and rig and clip folder, our graph
    static Mutagen.Bethesda.Starfield.Activator MakeControl(IDoorGetter door, IAnimationGraphComponentGetter graph, string anam)
    {
        var acti = new Mutagen.Bethesda.Starfield.Activator(Own(ControlId), Release) { EditorID = ControlEdid, Model = door.Model!.DeepCopy() };
        acti.Components.Add(new AnimationGraphComponent { ANAM = anam, BNAM = graph.BNAM, CNAM = graph.CNAM });
        return acti;
    }

    static void PrintFacts(IStarfieldModGetter sf, TextWriter w)
    {
        var door = Door(sf, out var graph);
        w.WriteLine($"door_edid={door.EditorID}");
        w.WriteLine($"door_model={door.Model?.File}");
        w.WriteLine($"door_anam={graph.ANAM}");
        w.WriteLine($"door_bnam={graph.BNAM}");
        w.WriteLine($"door_cnam={graph.CNAM}");
        w.WriteLine($"door_components={Kinds(door.Components)}");
        var l = Lift(sf);
        w.WriteLine($"lift_type={l.Type}");
        w.WriteLine($"lift_edid={l.Edid}");
        w.WriteLine($"lift_model={l.Model}");
        w.WriteLine($"lift_graph={l.Graph}");
        w.WriteLine($"lift_components={l.Components}");
        w.WriteLine($"lift_names_{LiftGraphWord}={l.Graph.Contains(LiftGraphWord, StringComparison.OrdinalIgnoreCase)}");
    }

    public static int Info(string templatePath)
    {
        using var sf = OpenTemplate(templatePath);
        PrintFacts(sf, Console.Out);
        return 0;
    }

    public static int Build(string templatePath, string outDir, string anam)
    {
        NeedGraph(anam);
        using var sf = OpenTemplate(templatePath);
        var door = Door(sf, out var graph);
        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";
        mod.Quests.Add(MakeQuest());
        mod.Activators.Add(MakeControl(door, graph, anam));
        mod.ModHeader.Stats.NextFormID = 0x802;
        mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} stages [{string.Join(",", Stages)}]; ACTI {ControlId:X6} {ControlEdid}");
        Console.WriteLine($"door {DoorId:X6} {door.EditorID} model {door.Model?.File}; graph {graph.ANAM} -> {anam}; BNAM {graph.BNAM}; CNAM {graph.CNAM}");
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

    public static int Check(string pluginPath, string templatePath, string anam)
    {
        using var sf = OpenTemplate(templatePath);
        var door = Door(sf, out var dgraph);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        PrintFacts(sf, Console.Out);
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm }), "masters are not exactly [Starfield.esm]");
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");
        Need(mod.EnumerateMajorRecords().Count() == 2, "not exactly two records (the quest and the door control)");
        Need(!mod.Cells.Records.Any() && !mod.Doors.Records.Any(), "the plugin carries a cell or a DOOR");
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
            Need(string.Equals(a.Model?.File, door.Model?.File, StringComparison.OrdinalIgnoreCase), "the model is not the vanilla door's");
            Need(a.Components.Count() == 1 && g.Count == 1, "not exactly one component, the animation graph");
            if (g.Count == 1)
            {
                Need(g[0].ANAM == anam, $"graph is {g[0].ANAM}, not {anam}");
                Need(g[0].ANAM?.Contains(ControlGraphWord, StringComparison.OrdinalIgnoreCase) == true, $"the graph does not name {ControlGraphWord}");
                Need(g[0].BNAM == dgraph.BNAM, $"rig is {g[0].BNAM}, not the vanilla door's {dgraph.BNAM}");
                Need(g[0].CNAM == dgraph.CNAM, $"clip folder is {g[0].CNAM}, not the vanilla door's {dgraph.CNAM}");
            }
            Need(a.FormKey != door.FormKey, "the control has the vanilla form key");
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
        var door = new Door(Sf(DoorId), Release) { EditorID = "AK_Ext_Bld_WallA_DoorA_01_Alt02", Model = new Model { File = "Architecture\\Doors\\WallA_DoorA_01.nif" } };
        door.Components.Add(new AnimationGraphComponent
        {
            ANAM = "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx",
            BNAM = "Architecture\\Doors\\CharacterAssets\\skeleton.rig", CNAM = "Architecture\\Doors\\Animations",
        });
        mod.Doors.Add(door);
        var lift = new Mutagen.Bethesda.Starfield.Activator(Sf(LiftId), Release) { EditorID = "ShipQuickLift1", Model = new Model { File = "Ships\\QuickLift\\QuickLift1.nif" } };
        lift.Components.Add(new AnimationGraphComponent
        {
            ANAM = "AnimTextData\\Tables\\Graphs\\TwoStages.agx",
            BNAM = "Ships\\QuickLift\\CharacterAssets\\skeleton.rig", CNAM = "Ships\\QuickLift\\Animations",
        });
        mod.Activators.Add(lift);
        Directory.CreateDirectory(outDir);
        mod.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")}");
        return 0;
    }
}
