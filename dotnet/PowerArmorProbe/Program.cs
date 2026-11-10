// PowerArmorProbe: does Starfield still run Fallout 4's power armor path? (docs/research/power-armor-probe.md)
//
// FO4SFPowerArmorProbe.esm (master Starfield.esm only; adds records, overrides none):
//   CELL  FO4SF_PAProbeCell      an interior cell of its own (`coc FO4SF_PAProbeCell`): vanilla platform floor and lights
//                                (the constants dotnet/TestCell proved), a COC marker, the two furniture references below
//   FURN  FO4SF_PAProbeSuit      a copy of the control furniture (every field of it; the one named on the command line,
//                                NPCChairTech03_Free_270 by default) with one more keyword, FurnitureTypePowerArmor
//   REFR  suit                   FO4SF_PAProbeSuit, 2.5 m to the right of the arrival (temporary)
//   REFR  control                the vanilla control furniture itself, 2.5 m to the left (temporary): the player must
//                                be able to sit on it, or the session proves nothing
//   RACE  FO4SF_PARace           a copy of HumanRace (name replaced by a plain string)
//   QUST  FO4SF_PAProbeQuest     start game enabled, stages 10 / 20 / 30, script FO4SF_PAProbeQuest with NO properties
//                                (the script finds every form with Game.GetFormFromFile; a property would make the
//                                temporary references persistent)
// The vanilla records are found by EditorID in Starfield.esm (no FormID of Starfield.esm is assumed here except the
// TestCell ones: floor 050776, omni light 03D38C, COC marker 000032, lighting template 006658, image space 122393).
// The local ids are the script's (scripts/planet/FO4SF_PAProbeQuest.psc; tests/test_power_armor_probe.py compares).
//
// usage: PowerArmorProbe build <Starfield.esm> <out dir> [--control <furniture editor id>]
//        PowerArmorProbe check <plugin> <Starfield.esm> [--control <furniture editor id>]     exit 1 on a mismatch
//        PowerArmorProbe fixture <out dir>             a synthetic Starfield.esm holding the three records looked up
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    var control = "NPCChairTech03_Free_270";
    int i = rest.IndexOf("--control");
    if (i >= 0)
    {
        if (i + 1 >= rest.Count) throw new PowerArmorProbe.Refusal("--control needs an editor ID");
        control = rest[i + 1];
        rest.RemoveRange(i, 2);
    }
    if (rest.Count == 3 && rest[0] == "build") return PowerArmorProbe.Build(rest[1], rest[2], control);
    if (rest.Count == 3 && rest[0] == "check") return PowerArmorProbe.Check(rest[1], rest[2], control);
    if (rest.Count == 2 && rest[0] == "fixture") return PowerArmorProbe.Fixture(rest[1]);
}
catch (PowerArmorProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: PowerArmorProbe build <Starfield.esm> <out dir> [--control <edid>] | " +
                        "check <plugin> <Starfield.esm> [--control <edid>] | fixture <out dir>");
return 2;

static class PowerArmorProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFPowerArmorProbe.esm");

    // the layout (scripts/planet/FO4SF_PAProbeQuest.psc carries the same ids)
    const uint CellId = 0x800, SuitId = 0x801, RaceId = 0x802, QuestId = 0x803, SuitRefId = 0x804, ControlRefId = 0x805,
        CocRefId = 0x806, FirstTileId = 0x810;
    const string CellEdid = "FO4SF_PAProbeCell", SuitEdid = "FO4SF_PAProbeSuit", RaceEdid = "FO4SF_PARace",
        QuestEdid = "FO4SF_PAProbeQuest", Script = "FO4SF_PAProbeQuest";
    const string KeywordEdid = "FurnitureTypePowerArmor", HumanRaceEdid = "HumanRace";
    // dotnet/TestCell's vanilla forms
    const uint Floor = 0x050776, Omni = 0x03D38C, CocMarker = 0x000032, LightingTemplate = 0x006658, ImageSpace = 0x122393;
    const float Tile = 8f, LightZ = 4f;
    static readonly P3Float SuitPos = new(0, -2.5f, 0), ControlPos = new(0, 2.5f, 0), CocPos = new(-5, 0, 0.1f);
    static readonly ushort[] Stages = { 10, 20, 30 };
    const string RaceName = "FO4SF PA race";

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);
    static string F(float v) => v.ToString("0.##", CultureInfo.InvariantCulture);

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static T One<T>(IEnumerable<T> items, string edid, string what) where T : IMajorRecordGetter
    {
        var hits = items.Where(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} {what} named {edid} in Starfield.esm (one needed)");
        return hits[0];
    }

    // ---------------------------------------------------------------- build

    public static int Build(string templatePath, string outDir, string controlEdid)
    {
        using var sf = OpenTemplate(templatePath);
        var kw = One(sf.Keywords, KeywordEdid, "KYWD");
        var humanRace = One(sf.Races, HumanRaceEdid, "RACE");
        var control = One(sf.Furniture, controlEdid, "FURN");
        if (control.Keywords?.Any(k => k.FormKey == kw.FormKey) == true)
            throw new Refusal($"{controlEdid} already carries {KeywordEdid}: it is no control");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";

        // the suit furniture: the control's fields, plus the power armor keyword (nothing else differs)
        var suit = (Furniture)control.Duplicate(Own(SuitId), new Furniture.TranslationMask(defaultOn: true) { Name = false });
        suit.EditorID = SuitEdid;
        suit.Name = null;
        suit.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
        suit.Keywords.Add(new FormLink<IKeywordGetter>(kw.FormKey));
        mod.Furniture.Add(suit);

        var race = (Race)humanRace.Duplicate(Own(RaceId), new Race.TranslationMask(defaultOn: true) { Name = false });
        race.EditorID = RaceEdid;
        race.Name = RaceName;
        mod.Races.Add(race);

        // the cell: platform floor, lights, COC marker, the two furniture references
        var cell = new Cell(Own(CellId), Release) { EditorID = CellEdid, Flags = Cell.Flag.IsInteriorCell };
        cell.LightingTemplate.SetTo(Sf(LightingTemplate));
        cell.ImageSpace.SetTo(Sf(ImageSpace));
        cell.EnvironmentMap = "Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds";
        uint next = FirstTileId;
        var zero = new P3Float(0, 0, 0);
        PlacedObject Ref(uint id, FormKey b, P3Float pos, P3Float rot, string? edid = null) =>
            new(Own(id), Release) { EditorID = edid, Base = new FormLinkNullable<IPlaceableObjectGetter>(b), Position = pos, Rotation = rot };
        cell.Temporary.Add(Ref(CocRefId, Sf(CocMarker), CocPos, new P3Float(0, 0, (float)(Math.PI / 2))));       // facing +X
        cell.Temporary.Add(Ref(SuitRefId, suit.FormKey, SuitPos, zero, "FO4SF_PAProbeSuitRef"));
        cell.Temporary.Add(Ref(ControlRefId, control.FormKey, ControlPos, zero, "FO4SF_PAProbeControlRef"));
        for (float x = -Tile; x <= Tile; x += Tile)
            for (float y = -Tile; y <= Tile; y += Tile) cell.Temporary.Add(Ref(next++, Sf(Floor), new P3Float(x, y, 0), zero));
        for (float x = -4; x <= 4; x += 8)
            for (float y = -4; y <= 4; y += 8) cell.Temporary.Add(Ref(next++, Sf(Omni), new P3Float(x, y, LightZ), zero));
        var cid = cell.FormKey.ID;
        var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);

        // the quest (dotnet/PlanetProbe's proven shape), three stages, no properties
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF power armor probe", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in Stages) quest.Stages.Add(new QuestStage { Index = s });
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = Script, Flags = ScriptEntry.Flag.Local });
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = next;

        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): CELL {CellEdid} {cell.FormKey}, FURN {SuitEdid} = copy of " +
                          $"{control.EditorID} {control.FormKey} + {kw.EditorID} {kw.FormKey}, control reference of {control.EditorID}, " +
                          $"RACE {RaceEdid} = copy of {humanRace.EditorID} {humanRace.FormKey}, QUST {QuestEdid} stages [{string.Join(",", Stages)}]");
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
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray()).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check (Mutagen read-back)

    public static int Check(string pluginPath, string templatePath, string controlEdid)
    {
        using var sf = OpenTemplate(templatePath);
        var kw = One(sf.Keywords, KeywordEdid, "KYWD");
        var humanRace = One(sf.Races, HumanRaceEdid, "RACE");
        var control = One(sf.Furniture, controlEdid, "FURN");
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

        // adds, never overrides: every record carries our own plugin's FormKey
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");

        var suit = mod.Furniture.SingleOrDefault();
        Need(suit?.FormKey == Own(SuitId) && suit.EditorID == SuitEdid, "not exactly our FURN");
        if (suit != null)
        {
            var keys = suit.Keywords?.Select(k => k.FormKey).ToList() ?? new();
            var want = (control.Keywords?.Select(k => k.FormKey) ?? Enumerable.Empty<FormKey>()).Append(kw.FormKey).ToList();
            Console.WriteLine($"  FURN {suit.EditorID} keywords [{string.Join(", ", keys)}] (control {control.EditorID} {control.FormKey}: {control.Keywords?.Count ?? 0} keywords) marker model {suit.MarkerModel}");
            Need(keys.SequenceEqual(want), $"FURN keywords are not the control's plus {kw.EditorID} {kw.FormKey}");
            Need(suit.MarkerModel == control.MarkerModel, "FURN marker model differs from the control's");
            Need((suit.MarkerParameters?.Count ?? 0) == (control.MarkerParameters?.Count ?? 0), "FURN marker parameters differ from the control's");
            Need((suit.MarkerEntryPoints?.Count ?? 0) == (control.MarkerEntryPoints?.Count ?? 0), "FURN entry points differ from the control's");
        }

        var race = mod.Races.SingleOrDefault();
        Need(race?.FormKey == Own(RaceId) && race.EditorID == RaceEdid, "not exactly our RACE");
        if (race != null) Console.WriteLine($"  RACE {race.EditorID} {race.FormKey} (copy of {humanRace.EditorID} {humanRace.FormKey}) name {race.Name?.String}");

        var cell = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).SingleOrDefault();
        Need(cell?.FormKey == Own(CellId) && cell.EditorID == CellEdid, "not exactly our CELL");
        if (cell != null)
        {
            Need(cell.Flags is { } fl && (fl & Cell.Flag.IsInteriorCell) != 0, "CELL is not an interior");
            Need(cell.Persistent.Count == 0, "CELL has persistent references (the probe's are temporary)");
            var objs = cell.Temporary.OfType<IPlacedObjectGetter>().ToDictionary(o => o.FormKey);
            void Ref(uint id, FormKey b, P3Float pos, string what)
            {
                var ok = objs.TryGetValue(Own(id), out var o);
                Need(ok && o!.Base.FormKey == b && o.Position == pos && (o.MajorRecordFlagsRaw & 0x400) == 0, what);
                if (ok) Console.WriteLine($"  REFR {o!.FormKey} {o.EditorID} base {o.Base.FormKey} at ({F(o.Position.X)}, {F(o.Position.Y)}, {F(o.Position.Z)})");
            }
            Ref(SuitRefId, Own(SuitId), SuitPos, "the suit reference (base, position, temporary)");
            Ref(ControlRefId, control.FormKey, ControlPos, "the control reference (base, position, temporary)");
            Ref(CocRefId, Sf(CocMarker), CocPos, "the COC marker");
            Console.WriteLine($"  CELL {cell.EditorID} {cell.FormKey}: {objs.Count} temporary references");
        }

        var quest = mod.Quests.SingleOrDefault();
        Need(quest?.FormKey == Own(QuestId) && quest.EditorID == QuestEdid, "not exactly our QUST");
        if (quest != null)
        {
            var scripts = quest.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Console.WriteLine($"  QUST {quest.EditorID} flags {quest.Data?.Flags} stages [{string.Join(",", quest.Stages.Select(s => s.Index))}] scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(quest.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "QUST is not start game enabled");
            Need(quest.Stages.Select(s => s.Index).SequenceEqual(Stages), "QUST stages are not 10, 20, 30");
            Need(scripts.Count == 1 && scripts[0].Name == Script && scripts[0].Properties.Count == 0, $"QUST script is not {Script} without properties");
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
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var kw = new Keyword(Sf(0x0F4A21), Release) { EditorID = KeywordEdid };
        var other = new Keyword(Sf(0x000900), Release) { EditorID = "SynthFurnitureKeyword" };
        mod.Keywords.Add(kw);
        mod.Keywords.Add(other);
        mod.Races.Add(new Race(Sf(0x013746), Release) { EditorID = HumanRaceEdid });
        mod.Furniture.Add(new Furniture(Sf(0x0027D5), Release)
        {
            EditorID = "NPCChairTech03_Free_270", MarkerModel = "Markers\\FurnitureMarkers\\ChairNeutral_Free_Marker.nif",
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(other.FormKey) },
            MarkerParameters = new ExtendedList<FurnitureMarkerParameters> { new FurnitureMarkerParameters { Offset = new P3Float(0, 0.12f, 0) } },
            MarkerEntryPoints = new ExtendedList<FurnitureMarkerEntryPoints> { new FurnitureMarkerEntryPoints() },
        });
        mod.Furniture.Add(new Furniture(Sf(0x0027D6), Release) { EditorID = "SynthAlreadyPowerArmor",
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(kw.FormKey) } });
        Directory.CreateDirectory(outDir);
        mod.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")}");
        return 0;
    }
}
