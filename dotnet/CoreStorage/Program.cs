// CoreStorage: does a persistent reference of an ADD-ON plugin that sits in the core's own exterior cell (its persistent
// group) stay with the player in the played world, the way temporary cell content of a loaded core cell does?
// (FAL-208; research FAL-207 run-2 section 3, FAL-188 "pc-probe-run2".) Probe run 2 could not say: its spawn cell
// never loaded (T7 and the cell control T5 both "not loaded"), so the test moves to a core exterior cell known to load.
//
// FO4SFCoreStorage.esm, masters Starfield.esm + the installed FO4TerrainCore.esm (--core):
//   WRLD  an override of the core's world carrying ONE exterior cell: the override of CELL FO4Core_RedRocketSpawn (record
//         only, as MergeProbe / SliceDoor's CellOnly). The world's own SubCells are never cleared after the cell is in:
//         the cell's override lives in them. No persistent cell, no other cell.
//   0x800 REFR FO4SF_CS_P  XMarker 00003B, flag 0x400, in the spawn cell's PERSISTENT group, at the COC marker + (4, 0, 0)
//   0x801 REFR FO4SF_CS_T  XMarker 00003B, temporary, in the spawn cell's TEMPORARY group, at the COC marker + (8, 0, 0)
//   0x802 QUST FO4SF_CoreStorageProbe  start game enabled, no stages, script FO4SF_CoreStorageQuest, NO properties (the script
//         finds both references with Game.GetFormFromFile: a property would make CS_T persistent and spoil the test)
// In game: `coc FO4Core_RedRocketSpawn` with the roofs on screen; the script's user log FO4SFCoreStorage.0.log holds
// "FO4SFCS rt=<s> ..." lines 2, 10, 30 and 60 s after the arrival.
//
// usage: CoreStorage build --sf <Starfield.esm> --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFCoreStorage.esm]
//        CoreStorage check <plugin> --sf <Starfield.esm> --core <FO4TerrainCore.esm>      exit 1 on a mismatch
//        CoreStorage fixture <dir>      synthetic Starfield.esm and FO4TerrainCore.esm for tests/test_core_storage.py
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    if (args.Length >= 2 && args[0] == "fixture") return CoreStorage.Fixture(args[1]);
    if (args.Length >= 1 && args[0] == "build") return CoreStorage.Build(args);
    if (args.Length >= 2 && args[0] == "check") return CoreStorage.Check(args);
}
catch (CoreStorage.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: CoreStorage build --sf <Starfield.esm> --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFCoreStorage.esm] | " +
                        "CoreStorage check <plugin> --sf <Starfield.esm> --core <FO4TerrainCore.esm> | CoreStorage fixture <dir>");
return 2;

static class CoreStorage
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    const uint PersistentId = 0x800, TemporaryId = 0x801, QuestId = 0x802, XMarker = 0x3B;
    const string CellEdid = "FO4Core_RedRocketSpawn", MarkerEdid = "FO4Core_RedRocketSpawnMarker";
    const string PersistentEdid = "FO4SF_CS_P", TemporaryEdid = "FO4SF_CS_T", QuestEdid = "FO4SF_CoreStorageProbe", Script = "FO4SF_CoreStorageQuest";
    const float PersistentDx = 4f, TemporaryDx = 8f;
    const int Persistent = 0x400, Disabled = 0x800;
    static readonly ModKey SfKey = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreKey = ModKey.FromFileName("FO4TerrainCore.esm");

    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
    static string P(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";
    static bool Finite(P3Float p) => float.IsFinite(p.X) && float.IsFinite(p.Y) && float.IsFinite(p.Z);

    static string Arg(string[] a, string name, string dflt)
    {
        var i = Array.IndexOf(a, name);
        return i >= 0 && i + 1 < a.Length ? a[i + 1] : dflt;
    }

    static Cache<IModMasterStyledGetter, ModKey> Styles()
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfKey, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreKey, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter Open(string path) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = Styles() });

    // the core's world, the block / sub block / cell of the spawn cell, and the COC marker's position
    record Spawn(IWorldspaceGetter World, IWorldspaceBlockGetter Block, IWorldspaceSubBlockGetter Sub, ICellGetter Cell, P3Float Marker);

    static Spawn FindSpawn(IStarfieldModGetter core)
    {
        var found = new List<Spawn>();
        foreach (var w in core.Worldspaces.Where(w => w.FormKey.ModKey == core.ModKey))
            foreach (var bk in w.SubCells)
                foreach (var sb in bk.Items)
                    foreach (var c in sb.Items)
                        if (c.EditorID == CellEdid) found.Add(new Spawn(w, bk, sb, c, default));
        if (found.Count != 1) throw new Refusal($"{found.Count} CELL {CellEdid} in {core.ModKey}'s own worldspaces (want exactly 1)");
        var s = found[0];
        var marker = s.Cell.Persistent.Concat(s.Cell.Temporary).OfType<IPlacedObjectGetter>().FirstOrDefault(r => r.EditorID == MarkerEdid)
                     ?? s.World.TopCell?.Persistent.OfType<IPlacedObjectGetter>().FirstOrDefault(r => r.EditorID == MarkerEdid)
                     ?? throw new Refusal($"no REFR {MarkerEdid} in {CellEdid} or in {s.World.EditorID}'s persistent cell");
        if (!Finite(marker.Position)) throw new Refusal($"{MarkerEdid} at {P(marker.Position)} is not a finite position");
        return s with { Marker = marker.Position };
    }

    static Cell CellOnly(ICellGetter c)
    {
        var copy = c.DeepCopy(new Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false,
            Temporary = false,
            NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
        });
        copy.Persistent.Clear();
        copy.Temporary.Clear();
        copy.NavigationMeshes.Clear();
        return copy;
    }

    static PlacedObject Probe(ModKey mod, uint id, string edid, P3Float at, bool persistent)
    {
        var o = new PlacedObject(new FormKey(mod, id), Release)
        {
            EditorID = edid,
            Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(SfKey, XMarker)),
            Position = at,
            Rotation = new P3Float(0, 0, 0),
        };
        if (persistent) o.MajorRecordFlagsRaw |= Persistent;
        return o;
    }

    static P3Float At(P3Float marker, float dx) => new(marker.X + dx, marker.Y, marker.Z);

    public static int Build(string[] a)
    {
        var sfPath = Arg(a, "--sf", ""); var corePath = Arg(a, "--core", ""); var outDir = Arg(a, "--out", "");
        if (sfPath == "" || corePath == "" || outDir == "") throw new Refusal("--sf, --core and --out are required");
        var modKey = ModKey.FromFileName(Arg(a, "--plugin", "FO4SFCoreStorage.esm"));
        using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, Release);
        if (sf.ModKey != SfKey) throw new Refusal($"--sf is {sf.ModKey}, not {SfKey}");
        using var core = Open(corePath);
        if (core.ModKey != CoreKey) throw new Refusal($"--core is {core.ModKey}, not {CoreKey}");
        var s = FindSpawn(core);

        var mod = new StarfieldMod(modKey, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;     // as every plugin of ours that loads

        // the world record alone (a plain DeepCopy would materialise the core's 648,358 references); its SubCells stay as
        // they come out of the mask (empty) and receive the one cell below: never SubCells.Clear() after that
        var w = s.World.DeepCopy(new Worldspace.TranslationMask(defaultOn: true)
        {
            SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
            TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
        });
        var cell = CellOnly(s.Cell);
        var cp = Probe(modKey, PersistentId, PersistentEdid, At(s.Marker, PersistentDx), true);
        var ct = Probe(modKey, TemporaryId, TemporaryEdid, At(s.Marker, TemporaryDx), false);
        cell.Persistent.Add(cp);
        cell.Temporary.Add(ct);
        var blk = new WorldspaceBlock { BlockNumberX = s.Block.BlockNumberX, BlockNumberY = s.Block.BlockNumberY, GroupType = s.Block.GroupType };
        var sub = new WorldspaceSubBlock { BlockNumberX = s.Sub.BlockNumberX, BlockNumberY = s.Sub.BlockNumberY, GroupType = s.Sub.GroupType };
        sub.Items.Add(cell);
        blk.Items.Add(sub);
        w.SubCells.Add(blk);
        mod.Worldspaces.Add(w);

        // the quest (dotnet/PlanetProbe's proven shape), no properties
        var quest = new Quest(new FormKey(modKey, QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF Core Storage", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = Script, Flags = ScriptEntry.Flag.Local });
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = QuestId + 1;

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, modKey.FileName);
        // an existing plugin stays until the write succeeds; Mutagen needs the plugin's own file name, so write in a temp folder
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        var order = new[] { SfKey, CoreKey };
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, modKey.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(order)
                .WithKnownMasters(order.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): spawn cell {CellEdid} {s.Cell.FormKey} grid {s.Cell.Grid?.Point} in {s.World.EditorID} {s.World.FormKey}");
        Console.WriteLine($"  {PersistentEdid} {cp.FormKey} persistent at {P(cp.Position)}, {TemporaryEdid} {ct.FormKey} temporary at {P(ct.Position)} (COC marker {P(s.Marker)} + ({F(PersistentDx)} / {F(TemporaryDx)}, 0, 0))");
        return 0;
    }

    public static int Check(string[] a)
    {
        var sfPath = Arg(a, "--sf", ""); var corePath = Arg(a, "--core", "");
        if (sfPath == "" || corePath == "") throw new Refusal("--sf and --core are required");
        using var core = Open(corePath);
        var s = FindSpawn(core);
        using var mod = Open(a[1]);
        var problems = new List<string>();
        void Need(bool ok, string msg) { if (!ok) problems.Add(msg); }
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
        Console.WriteLine($"{Path.GetFileName(a[1])}: header flags {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], {mod.Worldspaces.Count} WRLD");
        Need(masters.SequenceEqual(new[] { SfKey.FileName.String, CoreKey.FileName.String }), $"masters are not exactly [{SfKey.FileName}, {CoreKey.FileName}]");
        Need(mod.Worldspaces.Count == 1, "not exactly one WRLD");
        var w = mod.Worldspaces.FirstOrDefault();
        if (w == null || w.FormKey != s.World.FormKey) Need(false, $"the WRLD is not an override of {s.World.FormKey}");
        else
        {
            Need(w.TopCell == null, "the WRLD override carries a persistent cell");
            var cells = w.SubCells.SelectMany(b => b.Items).SelectMany(x => x.Items).ToList();
            Need(cells.Count == 1, $"the WRLD override carries {cells.Count} exterior cells (want exactly the spawn cell)");
            var c = cells.FirstOrDefault();
            if (c != null)
            {
                Need(c.FormKey == s.Cell.FormKey, $"the cell {c.FormKey} is not the core's {CellEdid} {s.Cell.FormKey}");
                Need(c.EditorID == CellEdid, $"the cell's EditorID is {c.EditorID}, not {CellEdid}");
                Need(c.Grid?.Point == s.Cell.Grid?.Point, $"the cell's grid {c.Grid?.Point} differs from the core's {s.Cell.Grid?.Point}");
                Need(c.MajorRecordFlagsRaw == s.Cell.MajorRecordFlagsRaw, $"the cell's flags 0x{c.MajorRecordFlagsRaw:X} differ from the core's 0x{s.Cell.MajorRecordFlagsRaw:X}");
                Need(c.NavigationMeshes.Count == 0, "the cell carries navigation meshes");
                void One(IReadOnlyList<IPlacedGetter> group, string which, uint id, string edid, float dx, bool persistent)
                {
                    var refs = group.OfType<IPlacedObjectGetter>().ToList();
                    Need(group.Count == 1 && refs.Count == 1, $"the cell's {which} group does not hold exactly {edid}");
                    var r = refs.FirstOrDefault();
                    if (r == null) return;
                    Console.WriteLine($"  {r.FormKey} {r.EditorID} base {r.Base.FormKey} flags 0x{r.MajorRecordFlagsRaw:X} in {which} at {P(r.Position)}");
                    Need(r.FormKey.ModKey == mod.ModKey && r.FormKey.ID == id && r.EditorID == edid, $"the {which} reference is not {edid} 0x{id:X}");
                    Need(r.Base.FormKey == new FormKey(SfKey, XMarker), $"{edid}'s base is not XMarker 00003B");
                    Need((r.MajorRecordFlagsRaw & (Persistent | Disabled)) == (persistent ? Persistent : 0), $"{edid} is not {(persistent ? "persistent" : "temporary")} and enabled");
                    Need(Finite(r.Position) && r.Position == At(s.Marker, dx), $"{edid} is at {P(r.Position)}, not {P(At(s.Marker, dx))} (COC marker + ({F(dx)}, 0, 0))");
                }
                One(c.Persistent.ToList(), "Persistent", PersistentId, PersistentEdid, PersistentDx, true);
                One(c.Temporary.ToList(), "Temporary", TemporaryId, TemporaryEdid, TemporaryDx, false);
            }
        }
        var q = mod.Quests.SingleOrDefault();
        Need(q?.FormKey == new FormKey(mod.ModKey, QuestId) && q.EditorID == QuestEdid, "not exactly our QUST");
        if (q != null)
        {
            var scripts = q.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Console.WriteLine($"  QUST {q.EditorID} flags {q.Data?.Flags} stages {q.Stages.Count} scripts [{string.Join(", ", scripts.Select(x => $"{x.Name} ({x.Properties.Count} properties)"))}]");
            Need(q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "QUST is not start game enabled");
            Need(scripts.Count == 1 && scripts[0].Name == Script && scripts[0].Properties.Count == 0, $"QUST script is not {Script} without properties");
        }
        var kinds = mod.EnumerateMajorRecords().Select(r => r.GetType().Name.Replace("BinaryOverlay", "")).GroupBy(n => n).Select(g => $"{g.Key} {g.Count()}");
        Console.WriteLine($"  records: {string.Join(", ", kinds)}");
        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // synthetic masters: a Starfield.esm stand-in and a core with a world whose exterior cell (-10, 11) is the spawn cell
    public static int Fixture(string dir)
    {
        Directory.CreateDirectory(dir);
        var sf = new StarfieldMod(SfKey, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        sf.ModHeader.Stats.NextFormID = 0x800;
        sf.BeginWrite.ToPath(Path.Combine(dir, SfKey.FileName)).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        var core = new StarfieldMod(CoreKey, Release);
        core.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var world = new Worldspace(new FormKey(CoreKey, 0x803), Release) { EditorID = "SyntheticCoreWorld", Name = "Core" };
        world.TopCell = new Cell(new FormKey(CoreKey, 0x900), Release);
        world.TopCell.Persistent.Add(new PlacedObject(new FormKey(CoreKey, 0x800), Release) { EditorID = "SyntheticAnchor" });
        var spawn = new Cell(new FormKey(CoreKey, 0x901), Release) { EditorID = CellEdid, Grid = new CellGrid { Point = new P2Int(-10, 11) } };
        spawn.Temporary.Add(new PlacedObject(new FormKey(CoreKey, 0x801), Release)
        {
            EditorID = MarkerEdid, Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(SfKey, 0x32)),
            Position = new P3Float(-989.257f, 1146.514f, 107.143f), Rotation = new P3Float(0, 0, 0),
        });
        var other = new Cell(new FormKey(CoreKey, 0x902), Release) { EditorID = "SyntheticOtherCell", Grid = new CellGrid { Point = new P2Int(-9, 11) } };
        var blk = new WorldspaceBlock { BlockNumberX = -1, BlockNumberY = 0, GroupType = GroupTypeEnum.ExteriorCellBlock };
        var sub = new WorldspaceSubBlock { BlockNumberX = -2, BlockNumberY = 1, GroupType = GroupTypeEnum.ExteriorCellSubBlock };
        sub.Items.Add(spawn);
        sub.Items.Add(other);
        blk.Items.Add(sub);
        world.SubCells.Add(blk);
        core.Worldspaces.Add(world);
        core.ModHeader.Stats.NextFormID = 0x903;
        core.BeginWrite.ToPath(Path.Combine(dir, CoreKey.FileName)).WithLoadOrder(SfKey)
            .WithKnownMasters(new KeyedMasterStyle(SfKey, MasterStyle.Full)).Write();
        Console.WriteLine($"wrote {SfKey}, {CoreKey} in {dir}");
        return 0;
    }
}
