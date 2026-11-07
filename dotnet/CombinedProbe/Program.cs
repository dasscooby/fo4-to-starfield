// CombinedProbe: the probe plugin of the combined core's engine questions P2 to P10 (docs/spikes/combined-core-probes.md;
// the questions: research/framework/combined-core-notes/engine-feasibility.md "PC probes"; the scripts:
// scripts/combined_probes/*.psc; the stage: scripts/combined_probes/make_combined_probe.py).
//
// FO4SFCombinedProbe.esm (masters Starfield.esm + the installed FO4TerrainCore.esm; with --p3-cells also FO4Port.esm):
//   0x804  QUST FOCC_ProbeQuest       start game enabled, no stages, script FOCC_ProbeQuest with every property below;
//                                     alias 0 P9Walker (optional, allow reserved, empty) with Starfield.esm's
//                                     DefaultTraveltoLinkedRef 212FDB as its package: P9's package driver
//                                     (FOCC_P9Drive.Travel forces the actor in after setting its linked ref)
//   0x805  KYWD FOCC_Holder           the per-location datum key (P2, P3, P6)
//   0x806  LCTN FOCC_P2_Loc           parent = the core's FO4Core_CommonwealthLocation (resolved by EditorID: its id
//                                     changes with every core build, so the plugin is rebuilt with the core)
//   0x807  LCTN FOCC_P3_LocNoParent   no parent, no keywords
//   0x808  LCTN FOCC_P3_LocChained    parent = the core's location, keyword LocTypeOverlay 002CA99D (as the core's own)
//   0x809  KYWD FOCC_Route            P2's link keyword
//   0x80B  REFR FOCC_P4_SpawnMarker   persistent XMarker 00003B in the core world's persistent cell (WRLD + CELL
//                                     override copied without children: dotnet/Mission, dotnet/MergeProbe)
//   0x80C..0x80E  REFR FOCC_P8_Stage<k>Parent  persistent XMarkers; stages 1 and 2 initially disabled (0x800)
//   0x80F..0x81A  REFR FOCC_P8_Child_<k>_<j>   base --stat, persistent, enable parent = parent k (dotnet/ReferenceLinks)
//   0x81B  REFR FOCC_P9_Dest          persistent XMarker
//   0x81C  LVLN FOCC_P6_HolderList    entries --lvln-a / --lvln-b conditioned GetKeywordDataForCurrentLocation(FOCC_Holder)
//                                     == 1 / == 2 (function index 651, engine-feasibility.md)
//   0x81D  LVLN FOCC_P7_RepList       the same bases conditioned GetGlobalValue(FOCC_Rep_Test) < 8 / >= 8 (index 74)
//   0x81E  GLOB FOCC_Rep_Test         non-constant, 581/4 as the bridge's
//   0x81F  KYWD FOCC_P10_Event        the story event keyword
//   0x820  QUST FOCC_P10_Quest        not start game enabled, event Script Event (SCPT: xEdit common.pas
//                                     wbQuestEventEnum, listed for SF1), script FOCC_P10Quest
//   0x821  SMBN FOCC_P10_Branch       parent = Starfield.esm's Script Event SMEN, previous sibling = that node's last child;
//                                     one condition GetEventData(FOCC_P10_Event), copied from a vanilla Script Event node
//   0x822  SMQN FOCC_P10_QuestNode    parent = the branch, quests = [FOCC_P10_Quest]
//   0x823..0x854  GLOB FOCC_P5_G00..G49
//   0x855  GMST iFOCC_Pong            int 7: B0's plugin bridge (docs/combined-core-cpp-port.md section 4). Papyrus reads it
//                                     with Game.GetGameSettingInt (FOCC_B0.Gmst); the setting-route plugin writes it by name
//   --p3-cells: CELL overrides of FO4Port.esm's FO4Port_RedRocket01 (XLCN -> 0x807) and FO4Port_SuperDuperMart01
//               (XLCN -> 0x808), copied without children
// Record shapes verified in game come from dotnet/Bridge (GLOB, QUST + VMAD), dotnet/Mission and dotnet/MergeProbe
// (world + persistent cell override, persistent REFR), dotnet/TerrainOverlays (LCTN keywords + parent),
// dotnet/TerrainIdentityFixture (KYWD), dotnet/ReferenceLinks (EnableParent). UNVERIFIED Mutagen 0.55 Starfield APIs
// (no precedent in this repo; the first PC build is their test, and `check` reads each back): LVLN entries with
// per-entry conditions, the typed condition data classes, SMBN/SMQN/SMEN, Quest.Event, Cell.Location,
// ScriptStringProperty. They sit in the methods marked UNVERIFIED below; --skip lvln,sm leaves those records out
// (and `check` with the same --skip expects them absent) so the other probes can run while an API is fixed.
//
// usage: CombinedProbe build --sf <Starfield.esm> --core <FO4TerrainCore.esm> --out <dir> --stat <plugin:hexid>
//                            --lvln-b <plugin:hexid> [--npc Starfield.esm:2B211C] [--lvln-a Starfield.esm:2B211C]
//                            [--plugin FO4SFCombinedProbe.esm] [--world FO4Core_Commonwealth]
//                            [--location FO4Core_CommonwealthLocation] [--p3-cells --port <FO4Port.esm>] [--skip lvln,sm]
//        CombinedProbe check <plugin> --sf <Starfield.esm> --core <FO4TerrainCore.esm> (the same options)   exit 1 on a mismatch
using System.Globalization;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

if (args.Length == 0) return CombinedProbe.Usage();
try
{
    return args[0] switch
    {
        "build" => CombinedProbe.Build(CombinedProbe.Options.Parse(args, 1), CombinedProbe.Arg(args, "--out", "")),
        "check" when args.Length >= 2 => CombinedProbe.Check(args[1], CombinedProbe.Options.Parse(args, 2)),
        _ => CombinedProbe.Usage(),
    };
}
catch (CombinedProbe.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class CombinedProbe
{
    public const string Plugin = "FO4SFCombinedProbe.esm", World = "FO4Core_Commonwealth", CoreLocation = "FO4Core_CommonwealthLocation";
    public const string QuestEdid = "FOCC_ProbeQuest", QuestScript = "FOCC_ProbeQuest", P10QuestEdid = "FOCC_P10_Quest", P10Script = "FOCC_P10Quest";
    public const uint QuestId = 0x804, HolderId = 0x805, P2LocId = 0x806, P3NoParentId = 0x807, P3ChainedId = 0x808, RouteId = 0x809,
        P4MarkerId = 0x80B, P8Parent0Id = 0x80C, P8Child0Id = 0x80F, P9DestId = 0x81B, P6ListId = 0x81C, P7ListId = 0x81D, RepId = 0x81E,
        P10EventId = 0x81F, P10QuestId = 0x820, P10BranchId = 0x821, P10NodeId = 0x822, P5FirstId = 0x823, PongId = 0x855, NextId = 0x856;
    public const int P5Count = 50, P8Stages = 3, P8ChildrenPerStage = 4;
    public const uint XMarker = 0x3B, LocTypeOverlay = 0x2CA99D;                         // Starfield.esm (MergeProbe, TerrainOverlays)
    public const string DefaultNpc = "Starfield.esm:2B211C";                              // EncCitizen01Template (docs/owner/in-game-test-sheet.md)
    // P9's package driver: Starfield.esm's DefaultTraveltoLinkedRef (Travel template 2CB0, location "near linked ref"
    // with no keyword, no conditions; read from Starfield.esm 1.16.244 on the PC, 1 Nov 2026), on alias 0 of the quest
    public const uint TravelToLinkedRef = 0x212FDB, WalkerAliasId = 0;
    public const string TravelToLinkedRefEdid = "DefaultTraveltoLinkedRef", WalkerAlias = "P9Walker";
    public const AQuestAlias.Flag WalkerFlags = AQuestAlias.Flag.Optional | AQuestAlias.Flag.AllowReserved;
    public static readonly string[] P3Cells = { "FO4Port_RedRocket01", "FO4Port_SuperDuperMart01" };
    public static readonly uint[] P3CellLocations = { P3NoParentId, P3ChainedId };
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly RecordType ScriptEvent = new("SCPT");                                 // xEdit common.pas: 'Script Event' (TES5, FO4, FO76, SF1)
    public const int KeywordDataForCurrentLocation = 651, GetGlobalValue = 74;            // condition function indices, engine-feasibility.md

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/CombinedProbe/Program.cs (build | check)");
        return 2;
    }
    public static string Arg(string[] a, string name, string dflt) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : dflt; }
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
    static string Show(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    /// "<plugin>:<hex id>" -> FormKey (the form of --npc, --lvln-a, --lvln-b, --stat).
    public static FormKey Key(string s, string what)
    {
        var i = s.LastIndexOf(':');
        if (i <= 0 || i == s.Length - 1) throw new Refusal($"{what} {s}: want <plugin>:<hex id>, e.g. {DefaultNpc}");
        uint id;
        try { id = Convert.ToUInt32(s[(i + 1)..], 16); }
        catch (Exception) { throw new Refusal($"{what} {s}: the id is not hex"); }
        return new FormKey(ModKey.FromFileName(s[..i]), id);
    }

    public sealed record Options(string Sf, string Core, string? Port, string Plugin, string World, string Location,
                                 FormKey Npc, FormKey LvlnA, FormKey LvlnB, FormKey Stat, bool P3Cells, HashSet<string> Skip)
    {
        public bool Lvln => !Skip.Contains("lvln");
        public bool Sm => !Skip.Contains("sm");

        public static Options Parse(string[] a, int from)
        {
            var rest = a.Skip(from).ToArray();
            var sf = Arg(rest, "--sf", "");
            var core = Arg(rest, "--core", "");
            if (sf == "" || core == "") throw new Refusal("--sf <Starfield.esm> and --core <FO4TerrainCore.esm> are required");
            var skip = Arg(rest, "--skip", "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToHashSet();
            var unknown = skip.Except(new[] { "lvln", "sm" }).ToList();
            if (unknown.Count > 0) throw new Refusal($"--skip knows lvln and sm, not {string.Join(",", unknown)}");
            var p3 = rest.Contains("--p3-cells");
            var port = Arg(rest, "--port", "");
            if (p3 && port == "") throw new Refusal("--p3-cells needs --port <FO4Port.esm>");
            var stat = Arg(rest, "--stat", "");
            if (stat == "") throw new Refusal("--stat <plugin:hexid> is required: a visible vanilla STAT for the P8 children, picked in xSFEdit and written on the job card");
            var lvlnB = Arg(rest, "--lvln-b", "");
            if (lvlnB == "" && !skip.Contains("lvln"))
                throw new Refusal("--lvln-b <plugin:hexid> is required: a second, visually distinct vanilla NPC_ for the P6 / P7 lists (or --skip lvln)");
            var npc = Arg(rest, "--npc", DefaultNpc);
            return new Options(sf, core, p3 ? port : null, Arg(rest, "--plugin", CombinedProbe.Plugin), Arg(rest, "--world", CombinedProbe.World),
                               Arg(rest, "--location", CoreLocation), Key(npc, "--npc"), Key(Arg(rest, "--lvln-a", npc), "--lvln-a"),
                               lvlnB == "" ? FormKey.Null : Key(lvlnB, "--lvln-b"), Key(stat, "--stat"), p3, skip);
        }
    }

    // ---------------------------------------------------------------- the masters

    sealed record Masters(IStarfieldModGetter Sf, IStarfieldModGetter Core, IStarfieldModGetter? Port, ILinkCache Cache) : IDisposable
    {
        public ModKey[] Keys => Port is null ? new[] { Sf.ModKey, Core.ModKey } : new[] { Sf.ModKey, Core.ModKey, Port.ModKey };
        public void Dispose() { (Port as IDisposable)?.Dispose(); (Core as IDisposable)?.Dispose(); (Sf as IDisposable)?.Dispose(); }
    }

    static BinaryReadParameters Styles(params ModKey[] full)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in full) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    static Masters Open(Options o)
    {
        var sf = StarfieldMod.CreateFromBinaryOverlay(o.Sf, Release);
        var core = StarfieldMod.CreateFromBinaryOverlay(o.Core, Release, Styles(SfEsm));
        IStarfieldModGetter? port = o.Port is null ? null : StarfieldMod.CreateFromBinaryOverlay(o.Port, Release, Styles(SfEsm, core.ModKey));
        var mods = new List<IStarfieldModGetter> { sf, core };
        if (port is not null && mods.All(m => m.ModKey != port.ModKey)) mods.Add(port);   // the link cache refuses duplicate keys
        var cache = mods.ToImmutableLinkCache<IStarfieldMod, IStarfieldModGetter>();
        return new Masters(sf, core, port, cache);
    }

    static IWorldspaceGetter FindWorld(IStarfieldModGetter core, string edid) =>
        core.Worldspaces.FirstOrDefault(w => w.EditorID == edid && w.FormKey.ModKey == core.ModKey)
        ?? throw new Refusal($"{core.ModKey} has no worldspace {edid}");

    static ILocationGetter FindLocation(IStarfieldModGetter core, string edid) =>
        core.Locations.FirstOrDefault(l => l.EditorID == edid && l.FormKey.ModKey == core.ModKey)
        ?? throw new Refusal($"{core.ModKey} has no location {edid}");

    static ICellGetter FindCell(IStarfieldModGetter port, string edid) =>
        port.EnumerateMajorRecords<ICellGetter>().FirstOrDefault(c => c.EditorID == edid && c.FormKey.ModKey == port.ModKey)
        ?? throw new Refusal($"{port.ModKey} has no cell {edid} of its own");

    /// The vanilla base a probe spawns or places: refused when it resolves to another record type; a warning when the
    /// masters read here do not hold it at all (the synthetic masters of the offline test; the game refuses a bad
    /// link at load, and the job card asks for the id to be confirmed in xSFEdit).
    static void CheckBase<T>(Masters m, FormKey key, string what, List<string> warnings) where T : class, IStarfieldMajorRecordGetter
    {
        if (m.Cache.TryResolve<T>(key, out _)) return;
        if (m.Cache.TryResolve<IStarfieldMajorRecordGetter>(key, out var other))
            throw new Refusal($"{what} {key} is {other.GetType().Name.Replace("BinaryOverlay", "")} {other.EditorID}, not {typeof(T).Name[1..^6]}");
        if (m.Keys.Contains(key.ModKey)) warnings.Add($"{what} {key} is not in the {key.ModKey} read here: written as given");
        else warnings.Add($"{what} {key} names a plugin that is not a master here: written as given (the game must load it)");
    }

    /// Why Starfield.esm's 212FDB is not P9's package (DefaultTraveltoLinkedRef), or null when it is.
    static string? TravelProblem(Masters m) =>
        m.Cache.TryResolve<IPackageGetter>(new FormKey(SfEsm, TravelToLinkedRef), out var p) && p.EditorID == TravelToLinkedRefEdid
            ? null : $"Starfield.esm {TravelToLinkedRef:X6} is not the package {TravelToLinkedRefEdid} (P9's package driver)";

    // ---------------------------------------------------------------- build

    public static int Build(Options o, string outDir)
    {
        if (outDir == "") throw new Refusal("--out <dir> is required");
        using var m = Open(o);
        var warnings = new List<string>();
        var modKey = ModKey.FromFileName(o.Plugin);
        var mod = new StarfieldMod(modKey, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;                     // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield CombinedProbe";

        var world = FindWorld(m.Core, o.World);
        var top = world.TopCell ?? throw new Refusal($"{o.World} has no persistent cell");
        var coreLoc = FindLocation(m.Core, o.Location);
        CheckBase<INpcGetter>(m, o.Npc, "--npc", warnings);
        CheckBase<IStaticGetter>(m, o.Stat, "--stat", warnings);
        var travelProblem = TravelProblem(m);
        if (travelProblem is not null)
        {
            if (m.Cache.TryResolve<IStarfieldMajorRecordGetter>(new FormKey(SfEsm, TravelToLinkedRef), out _)) throw new Refusal(travelProblem);
            warnings.Add(travelProblem + ": not in the Starfield.esm read here, written as given");
        }
        if (o.Lvln)
        {
            CheckBase<INpcGetter>(m, o.LvlnA, "--lvln-a", warnings);
            CheckBase<INpcGetter>(m, o.LvlnB, "--lvln-b", warnings);
        }

        // keywords, locations, globals
        Keyword Kw(uint id, string edid) { var k = new Keyword(new FormKey(modKey, id), Release) { EditorID = edid }; mod.Keywords.Add(k); return k; }
        var holder = Kw(HolderId, "FOCC_Holder");
        var route = Kw(RouteId, "FOCC_Route");
        var p10Event = Kw(P10EventId, "FOCC_P10_Event");
        Location Loc(uint id, string edid, FormKey? parent, bool overlayKeyword)
        {
            var l = new Location(new FormKey(modKey, id), Release) { EditorID = edid, Name = edid };
            if (parent is { } p) l.ParentLocation.SetTo(p);
            if (overlayKeyword)
                l.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(new FormKey(SfEsm, LocTypeOverlay)) };
            mod.Locations.Add(l);
            return l;
        }
        var p2Loc = Loc(P2LocId, "FOCC_P2_Loc", coreLoc.FormKey, false);
        var p3NoParent = Loc(P3NoParentId, "FOCC_P3_LocNoParent", null, false);
        var p3Chained = Loc(P3ChainedId, "FOCC_P3_LocChained", coreLoc.FormKey, true);
        Global Glob(uint id, string edid)
        {
            var g = new Global(new FormKey(modKey, id), Release) { EditorID = edid, Data = 0f, FormVersion = 581, Version2 = 4 };
            mod.Globals.Add(g);
            return g;
        }
        var rep = Glob(RepId, "FOCC_Rep_Test");
        var p5 = Enumerable.Range(0, P5Count).Select(i => Glob(P5FirstId + (uint)i, $"FOCC_P5_G{i:D2}")).ToList();
        // B0 (docs/combined-core-cpp-port.md section 4): one game setting of ours. FOCC_B0.Gmst reads it back with
        // Game.GetGameSettingInt("iFOCC_Pong") (B0-1: 7); on the no-address bridge the plugin writes it by its name. The
        // EditorID's first letter is the setting's type, as the game reads GMST (Mutagen's GameSetting keeps it so). No
        // FormVersion is forced: the KYWD and LCTN written the same way load in game (P2, P3). UNVERIFIED: a GMST new to
        // the game (no vanilla record of that name) reaching Papyrus from a plugin; B0-1 is that test, and `check` reads
        // the record back here.
        var pong = new GameSettingInt(new FormKey(modKey, PongId), Release) { EditorID = "iFOCC_Pong", Data = 7 };
        mod.GameSettings.Add(pong);

        // the core world and its persistent cell, overridden with only our references (Mission, MergeProbe)
        var w = world.DeepCopy(new Worldspace.TranslationMask(defaultOn: true)
        {
            SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
            TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
        });
        w.SubCells.Clear();
        var cell = top.DeepCopy(new Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false, Temporary = false,
            NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
        });
        cell.Persistent.Clear();
        cell.Temporary.Clear();
        cell.NavigationMeshes.Clear();
        w.TopCell = cell;
        PlacedObject Marker(uint id, string edid, FormKey baseKey, P3Float at, bool disabled, FormKey? enableParent)
        {
            var r = new PlacedObject(new FormKey(modKey, id), Release)
            {
                EditorID = edid, Base = new FormLinkNullable<IPlaceableObjectGetter>(baseKey), Position = at, Rotation = new P3Float(0, 0, 0),
            };
            r.MajorRecordFlagsRaw |= 0x400;                                              // persistent
            if (disabled) r.MajorRecordFlagsRaw |= 0x800;                                // initially disabled
            if (enableParent is { } ep)
            {
                r.EnableParent = new EnableParent { Flags = 0 };                         // dotnet/ReferenceLinks/Relationships.cs
                r.EnableParent.Reference.SetTo(ep);
            }
            cell.Persistent.Add(r);
            return r;
        }
        var xmarker = new FormKey(SfEsm, XMarker);
        var p4Marker = Marker(P4MarkerId, "FOCC_P4_SpawnMarker", xmarker, new P3Float(0, 0, 0), false, null);
        var p8Parents = new List<PlacedObject>();
        var p8Children = new List<PlacedObject>();
        for (int k = 0; k < P8Stages; k++)
        {
            var parent = Marker(P8Parent0Id + (uint)k, $"FOCC_P8_Stage{k}Parent", xmarker, new P3Float(0, 6 * k, 0), k != 0, null);
            p8Parents.Add(parent);
            for (int j = 0; j < P8ChildrenPerStage; j++)
                p8Children.Add(Marker(P8Child0Id + (uint)(k * P8ChildrenPerStage + j), $"FOCC_P8_Child_{k}_{j}", o.Stat, new P3Float(2 * j, 6 * k, 0), false, parent.FormKey));
        }
        var p9Dest = Marker(P9DestId, "FOCC_P9_Dest", xmarker, new P3Float(0, 0, 0), false, null);
        mod.Worldspaces.Add(w);

        // the conditioned leveled lists (UNVERIFIED Mutagen API: see LeveledList below)
        LeveledNpc? p6List = null, p7List = null;
        if (o.Lvln)
        {
            p6List = LeveledList(mod, new FormKey(modKey, P6ListId), "FOCC_P6_HolderList",
                                 (o.LvlnA, KeywordDataIs(holder.FormKey, 1f)), (o.LvlnB, KeywordDataIs(holder.FormKey, 2f)));
            p7List = LeveledList(mod, new FormKey(modKey, P7ListId), "FOCC_P7_RepList",
                                 (o.LvlnA, GlobalCompare(rep.FormKey, CompareOperator.LessThan, 8f)), (o.LvlnB, GlobalCompare(rep.FormKey, CompareOperator.GreaterThanOrEqualTo, 8f)));
        }

        // the Story Manager quest and its branch (UNVERIFIED Mutagen API: see StoryManager below)
        var p10 = new Quest(new FormKey(modKey, P10QuestId), Release)
        {
            EditorID = P10QuestEdid, Name = "FOCC P10 event quest", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = 0, Priority = 30 },
        };
        p10.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        p10.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = P10Script, Flags = ScriptEntry.Flag.Local });
        string smNote = "sm skipped";
        if (o.Sm)
        {
            p10.Event = ScriptEvent;
            smNote = StoryManager(mod, m, modKey, p10.FormKey, p10Event.FormKey, warnings);
        }
        mod.Quests.Add(p10);

        // the P3 cell overrides (UNVERIFIED Mutagen API: see CellOverrides below)
        var cellNote = o.P3Cells ? CellOverrides(mod, m.Port!, modKey) : "no cell override";

        // the probe quest with every property the script declares (dotnet/Bridge, dotnet/MapMarkers shapes)
        var quest = new Quest(new FormKey(modKey, QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FOCC engine probes", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        var script = new ScriptEntry { Name = QuestScript, Flags = ScriptEntry.Flag.Local };
        ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = ScriptProperty.Flag.Edited, Object = new FormLink<IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        ScriptObjectListProperty ObjList(string name, IEnumerable<FormKey> keys)
        {
            var l = new ScriptObjectListProperty { Name = name, Flags = ScriptProperty.Flag.Edited };
            foreach (var k in keys) l.Objects.Add(Obj("", k));
            return l;
        }
        script.Properties.Add(Obj("Holder", holder.FormKey));
        script.Properties.Add(Obj("Route", route.FormKey));
        script.Properties.Add(Obj("P2Loc", p2Loc.FormKey));
        script.Properties.Add(Obj("P3LocNoParent", p3NoParent.FormKey));
        script.Properties.Add(Obj("P3LocChained", p3Chained.FormKey));
        script.Properties.Add(Obj("P4Marker", p4Marker.FormKey));
        script.Properties.Add(Obj("P4Base", o.Npc));
        script.Properties.Add(ObjList("P5Globals", p5.Select(g => g.FormKey)));
        if (p6List is not null && p7List is not null)
        {
            script.Properties.Add(Obj("P6List", p6List.FormKey));
            script.Properties.Add(Obj("P6BaseA", o.LvlnA));
            script.Properties.Add(Obj("P6BaseB", o.LvlnB));
            script.Properties.Add(Obj("P7List", p7List.FormKey));
        }
        script.Properties.Add(Obj("P7Rep", rep.FormKey));
        script.Properties.Add(ObjList("P8Parents", p8Parents.Select(r => r.FormKey)));
        script.Properties.Add(ObjList("P8Children", p8Children.Select(r => r.FormKey)));
        script.Properties.Add(Obj("P9Dest", p9Dest.FormKey));
        script.Properties.Add(Obj("P10Event", p10Event.FormKey));
        script.Properties.Add(Obj("P10Quest", p10.FormKey));
        if (o.P3Cells) script.Properties.Add(new ScriptStringProperty { Name = "Variant", Flags = ScriptProperty.Flag.Edited, Data = "p3cells" });
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        // P9's package driver: an empty alias the script fills; its package outranks the actor's own (UNVERIFIED in game)
        (quest.Aliases ??= new ExtendedList<AQuestAlias>()).Add(new QuestReferenceAlias
        {
            ID = WalkerAliasId, Name = WalkerAlias, Flags = WalkerFlags,
            PackageData = { new FormLink<IPackageGetter>(new FormKey(SfEsm, TravelToLinkedRef)) },
        });
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = NextId;

        // an existing plugin stays until the write succeeds (MergeProbe)
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, modKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, modKey.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(m.Keys).WithKnownMasters(m.Keys.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): masters [{string.Join(", ", m.Keys.Select(k => k.FileName))}]; " +
                          $"QUST {QuestEdid} {quest.FormKey} script {QuestScript} ({script.Properties.Count} properties); " +
                          $"{mod.Keywords.Count} KYWD, {mod.Locations.Count} LCTN, {mod.Globals.Count} GLOB, {mod.GameSettings.Count} GMST, {cell.Persistent.Count} REFR in " +
                          $"WRLD {w.EditorID} {w.FormKey} persistent CELL {cell.FormKey}; {(o.Lvln ? "2 LVLN" : "lvln skipped")}; " +
                          $"QUST {P10QuestEdid} {p10.FormKey} ({smNote}); {cellNote}; variant={(o.P3Cells ? "p3cells" : "default")}");
        Console.WriteLine($"  core location {o.Location} = {coreLoc.FormKey} (parent of FOCC_P2_Loc and FOCC_P3_LocChained); core world {world.FormKey}");
        Console.WriteLine($"  bases: npc {o.Npc}, lvln-a {o.LvlnA}, lvln-b {(o.LvlnB.IsNull ? "none" : o.LvlnB.ToString())}, stat {o.Stat}");
        foreach (var r in cell.Persistent.OfType<IPlacedObjectGetter>())
            Console.WriteLine($"  REFR {r.FormKey.ID:X6} {r.EditorID} base {r.Base.FormKey} flags 0x{r.MajorRecordFlagsRaw:X} at {Show(r.Position)}" +
                              (r.EnableParent is { } ep ? $" enable parent {ep.Reference.FormKey}" : ""));
        foreach (var x in warnings) Console.WriteLine("WARN  " + x);
        return 0;
    }

    // ---------------------------------------------------------------- UNVERIFIED Mutagen 0.55 Starfield APIs
    // Each method below uses a Mutagen API no code in this repo has built with (open question 2 of the probe plan).
    // A compile error on the PC lands here; `check` reads every field back so a silently wrong write is caught too.

    /// A LVLN entry condition "GetKeywordDataForCurrentLocation(keyword) == value" (function index 651).
    static Condition KeywordDataIs(FormKey keyword, float value)
    {
        var data = new GetKeywordDataForCurrentLocationConditionData();
        data.FirstParameter.Link.SetTo(keyword);
        return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = value, Data = data };
    }

    /// A LVLN entry condition "GetGlobalValue(global) <op> value" (function index 74).
    static Condition GlobalCompare(FormKey global, CompareOperator op, float value)
    {
        var data = new GetGlobalValueConditionData();
        data.FirstParameter.Link.SetTo(global);
        return new ConditionFloat { CompareOperator = op, ComparisonValue = value, Data = data };
    }

    /// A leveled NPC list of Level 1 / Count 1 entries, each with one condition (Starfield's LVLN carries CTDA per entry).
    static LeveledNpc LeveledList(StarfieldMod mod, FormKey key, string edid, params (FormKey Base, Condition Cond)[] entries)
    {
        var l = new LeveledNpc(key, Release) { EditorID = edid };
        l.Entries ??= new ExtendedList<LeveledNpcEntry>();
        foreach (var (b, c) in entries)
        {
            var e = new LeveledNpcEntry { Level = 1, Count = 1 };
            e.Reference.SetTo(b);
            e.Conditions.Add(c);
            l.Entries.Add(e);
        }
        mod.LeveledNpcs.Add(l);
        return l;
    }

    /// The condition of a read-back entry as "fn=<index> op=<op> value=<v> param=<FormKey>" (null when it has none).
    static (int Fn, CompareOperator Op, float Value, FormKey Param)? ReadCondition(ILeveledNpcEntryGetter e)
    {
        if (e.Conditions.FirstOrDefault() is not IConditionFloatGetter c) return null;
        var param = c.Data switch
        {
            IGetKeywordDataForCurrentLocationConditionDataGetter k => k.FirstParameter.Link.FormKey,
            IGetGlobalValueConditionDataGetter g => g.FirstParameter.Link.FormKey,
            _ => FormKey.Null,
        };
        return ((int)c.Data.Function, c.CompareOperator, c.ComparisonValue, param);
    }

    /// Starfield.esm's Script Event node and the last of its children (the one no sibling names as its previous node).
    static (IStoryManagerEventNodeGetter? Event, FormKey Tail) ScriptEventNode(IStarfieldModGetter sf)
    {
        var smen = sf.StoryManagerEventNodes.FirstOrDefault(n => n.Type == StoryManagerEventNode.Types.ScriptEvent);
        if (smen is null) return (null, FormKey.Null);
        var children = sf.StoryManagerBranchNodes.Cast<IAStoryManagerNodeGetter>().Concat(sf.StoryManagerQuestNodes)
            .Where(n => n.Parent.FormKeyNullable == smen.FormKey).ToList();
        var named = children.Select(c => c.PreviousSibling.FormKeyNullable ?? FormKey.Null).ToHashSet();
        var tail = children.FirstOrDefault(c => !named.Contains(c.FormKey));
        return (smen, tail?.FormKey ?? FormKey.Null);
    }

    /// The keyword filter Starfield.esm's own Script Event nodes use: conditions on any branch or quest node under the
    /// Script Event SMEN whose data is GetEventData naming one of Starfield.esm's keywords. Returns the most common
    /// (function, member) shape, one example of it with its node, and how many conditions share it; null when none.
    static (IConditionFloatGetter Cond, string Node, int Count, int Total)? EventKeywordFilter(IStarfieldModGetter sf, FormKey smen)
    {
        var nodes = sf.StoryManagerBranchNodes.Cast<IAStoryManagerNodeGetter>().Concat(sf.StoryManagerQuestNodes).ToList();
        var parent = nodes.ToDictionary(n => n.FormKey, n => n.Parent.FormKeyNullable ?? FormKey.Null);
        bool Under(FormKey k)
        {
            for (var i = 0; i < 64 && !k.IsNull; i++)
            {
                if (k == smen) return true;
                k = parent.TryGetValue(k, out var up) ? up : FormKey.Null;
            }
            return false;
        }
        var keywords = sf.Keywords.Select(k => k.FormKey).ToHashSet();
        var found = nodes.Where(n => Under(n.FormKey))
            .SelectMany(n => n.Conditions.OfType<IConditionFloatGetter>().Select(c => (Node: n, Cond: c)))
            .Where(x => x.Cond.Data is IGetEventDataConditionDataGetter d && keywords.Contains(d.Record.FormKey))
            .ToList();
        if (found.Count == 0) return null;
        var shape = found.GroupBy(x => { var d = (IGetEventDataConditionDataGetter)x.Cond.Data; return (d.Function, d.Member); })
            .OrderByDescending(g => g.Count()).First();
        var ex = shape.First();
        return (ex.Cond, $"{ex.Node.EditorID} {ex.Node.FormKey}", shape.Count(), found.Count);
    }

    /// SMBN FOCC_P10_Branch under the vanilla Script Event node (appended after its last child) and SMQN
    /// FOCC_P10_QuestNode under the branch, listing the P10 quest. Without a Script Event node in the Starfield.esm
    /// read (the synthetic master of the offline test) the branch is written as a root node, with a warning.
    /// The branch carries one condition, GetEventData naming FOCC_P10_Event, copied in shape (function, member,
    /// comparison) from Starfield.esm's own Script Event nodes. Owner's PC, 28 Oct 2026: without it, FOCC_P10_Quest
    /// started at game start, 44 s before our send, most likely from a vanilla script event no earlier node took.
    static string StoryManager(StarfieldMod mod, Masters m, ModKey modKey, FormKey quest, FormKey eventKeyword, List<string> warnings)
    {
        var (smen, tail) = ScriptEventNode(m.Sf);
        var branch = new StoryManagerBranchNode(new FormKey(modKey, P10BranchId), Release) { EditorID = "FOCC_P10_Branch" };
        var filterNote = "no condition";
        if (smen is not null)
        {
            branch.Parent.SetTo(smen.FormKey);
            if (!tail.IsNull) branch.PreviousSibling.SetTo(tail);
            var filter = EventKeywordFilter(m.Sf, smen.FormKey)
                ?? throw new Refusal($"no node under {smen.EditorID} {smen.FormKey} filters on a keyword with GetEventData: " +
                                                       "FOCC_P10_Branch would take every script event (rebuild with --skip sm to leave P10 out)");
            var src = (IGetEventDataConditionDataGetter)filter.Cond.Data;
            var data = new GetEventDataConditionData { Function = src.Function, Member = src.Member };
            data.Record.SetTo(eventKeyword);
            branch.Conditions.Add(new ConditionFloat { CompareOperator = filter.Cond.CompareOperator, ComparisonValue = filter.Cond.ComparisonValue, Data = data });
            filterNote = $"condition GetEventData {src.Function}/{src.Member} {filter.Cond.CompareOperator} {filter.Cond.ComparisonValue} " +
                         $"(shape of {filter.Count} of {filter.Total} vanilla keyword filters, e.g. {filter.Node})";
        }
        else warnings.Add($"{m.Sf.ModKey} has no Script Event SMEN: FOCC_P10_Branch written as a root node (synthetic masters only)");
        mod.StoryManagerBranchNodes.Add(branch);
        var node = new StoryManagerQuestNode(new FormKey(modKey, P10NodeId), Release) { EditorID = "FOCC_P10_QuestNode" };
        node.Parent.SetTo(branch.FormKey);
        var sq = new StoryManagerQuest();
        sq.Quest.SetTo(quest);
        node.Quests.Add(sq);
        mod.StoryManagerQuestNodes.Add(node);
        return smen is null ? "SMBN root, SMQN" : $"SMBN under {smen.EditorID} {smen.FormKey} after {(tail.IsNull ? "none" : tail.ToString())}, {filterNote}, SMQN";
    }

    /// --p3-cells: FO4Port.esm's two interiors overridden without children, each given one probe location (XLCN).
    static string CellOverrides(StarfieldMod mod, IStarfieldModGetter port, ModKey modKey)
    {
        var names = new List<string>();
        for (int i = 0; i < P3Cells.Length; i++)
        {
            var c0 = FindCell(port, P3Cells[i]);
            var c = c0.DeepCopy(new Cell.TranslationMask(defaultOn: true)
            {
                Persistent = false, Temporary = false,
                NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
            });
            c.Persistent.Clear();
            c.Temporary.Clear();
            c.NavigationMeshes.Clear();
            c.Location.SetTo(new FormKey(modKey, P3CellLocations[i]));
            var cid = c.FormKey.ID;                                                        // dotnet/PluginSpike's interior block rule
            var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
            var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
            sub.Cells.Add(c);
            block.SubBlocks.Add(sub);
            mod.Cells.Records.Add(block);
            names.Add($"{P3Cells[i]} {c.FormKey} -> 0x{P3CellLocations[i]:X}");
        }
        return "CELL overrides " + string.Join(", ", names);
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, Options o)
    {
        using var m = Open(o);
        var warnings = new List<string>();
        using var plug = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, Styles(m.Keys));
        var key = plug.ModKey;
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        FormKey K(uint id) => new(key, id);

        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        var refs = plug.Worldspaces.FirstOrDefault()?.TopCell?.Persistent.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey) ?? new();
        var cells = plug.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{plug.ModHeader.Stats.NextFormID:X}, " +
                          $"{plug.Quests.Count} QUST, {plug.Keywords.Count} KYWD, {plug.Locations.Count} LCTN, {plug.Globals.Count} GLOB, {plug.GameSettings.Count} GMST, " +
                          $"{plug.LeveledNpcs.Count} LVLN, {plug.StoryManagerBranchNodes.Count} SMBN, {plug.StoryManagerQuestNodes.Count} SMQN, " +
                          $"{plug.Worldspaces.Count} WRLD, {refs.Count} REFR, {cells.Count} CELL (interior)");
        Need(plug.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(m.Keys.Select(k => k.FileName.String)), $"masters are not [{string.Join(", ", m.Keys.Select(k => k.FileName))}]");
        Need(plug.ModHeader.Stats.NextFormID == NextId, $"next form id is 0x{plug.ModHeader.Stats.NextFormID:X}, not 0x{NextId:X}");
        CheckBase<INpcGetter>(m, o.Npc, "--npc", warnings);
        CheckBase<IStaticGetter>(m, o.Stat, "--stat", warnings);

        // keywords, locations, globals
        var kw = plug.Keywords.ToDictionary(k => k.FormKey);
        foreach (var (id, edid) in new[] { (HolderId, "FOCC_Holder"), (RouteId, "FOCC_Route"), (P10EventId, "FOCC_P10_Event") })
            Need(kw.TryGetValue(K(id), out var k) && k.EditorID == edid, $"KYWD 0x{id:X} {edid} missing");
        Need(kw.Count == 3, "not exactly 3 KYWD");
        var coreLoc = FindLocation(m.Core, o.Location);
        var locs = plug.Locations.ToDictionary(l => l.FormKey);
        Console.WriteLine($"  core location {o.Location} = {coreLoc.FormKey}; LCTN parents: " +
                          string.Join(", ", plug.Locations.Select(l => $"{l.EditorID} -> {l.ParentLocation.FormKeyNullable?.ToString() ?? "none"} kw [{string.Join(",", l.Keywords?.Select(x => x.FormKey.ToString()) ?? Array.Empty<string>())}]")));
        Need(locs.TryGetValue(K(P2LocId), out var p2) && p2.EditorID == "FOCC_P2_Loc" && p2.ParentLocation.FormKeyNullable == coreLoc.FormKey,
             $"LCTN 0x{P2LocId:X} FOCC_P2_Loc is not parented to {o.Location} {coreLoc.FormKey} (built against another core?)");
        Need(locs.TryGetValue(K(P3NoParentId), out var p3a) && p3a.EditorID == "FOCC_P3_LocNoParent" && p3a.ParentLocation.FormKeyNullable is null && (p3a.Keywords?.Count ?? 0) == 0,
             $"LCTN 0x{P3NoParentId:X} FOCC_P3_LocNoParent is not parentless and keyword-less");
        Need(locs.TryGetValue(K(P3ChainedId), out var p3b) && p3b.EditorID == "FOCC_P3_LocChained" && p3b.ParentLocation.FormKeyNullable == coreLoc.FormKey &&
             p3b.Keywords is { Count: 1 } && p3b.Keywords[0].FormKey == new FormKey(SfEsm, LocTypeOverlay),
             $"LCTN 0x{P3ChainedId:X} FOCC_P3_LocChained is not parented to {o.Location} with keyword LocTypeOverlay");
        Need(locs.Count == 3, "not exactly 3 LCTN");
        var globs = plug.Globals.ToDictionary(g => g.FormKey);
        Need(globs.TryGetValue(K(RepId), out var rep) && rep.EditorID == "FOCC_Rep_Test", $"GLOB 0x{RepId:X} FOCC_Rep_Test missing");
        for (int i = 0; i < P5Count; i++)
            Need(globs.TryGetValue(K(P5FirstId + (uint)i), out var g) && g.EditorID == $"FOCC_P5_G{i:D2}", $"GLOB FOCC_P5_G{i:D2} missing");
        Need(globs.Count == P5Count + 1, $"not exactly {P5Count + 1} GLOB");
        Need(plug.Globals.All(g => !g.MajorFlags.HasFlag(Global.MajorFlag.Constant)), "a GLOB is Constant: the console and the script could not set it");
        var pong = plug.GameSettings.FirstOrDefault(g => g.FormKey == K(PongId));
        Need(pong is IGameSettingIntGetter pongInt && pongInt.EditorID == "iFOCC_Pong" && pongInt.Data == 7,
             $"GMST 0x{PongId:X} iFOCC_Pong is not an int game setting of 7 (B0)");
        Need(plug.GameSettings.Count == 1, "not exactly 1 GMST");

        // the world override and its references
        var world = FindWorld(m.Core, o.World);
        var w = plug.Worldspaces.FirstOrDefault();
        Need(plug.Worldspaces.Count == 1 && w is not null && w.FormKey == world.FormKey && w.SubCells.Count == 0, "the WRLD override is not the core world without exterior cells");
        Need(w is not null && w.TopCell is not null && w.TopCell.FormKey == world.TopCell?.FormKey && w.TopCell.Temporary.Count == 0 && w.TopCell.NavigationMeshes.Count == 0,
             "the persistent cell override is not the core's, or carries temporary references or navmeshes");
        Need(w is null || w.TopCell is null || w.TopCell.Persistent.Count == refs.Count, "the persistent cell holds something other than our REFRs");
        var xmarker = new FormKey(SfEsm, XMarker);
        void Ref(uint id, string edid, FormKey baseKey, bool disabled, FormKey? enableParent)
        {
            if (!refs.TryGetValue(K(id), out var r)) { problems.Add($"REFR 0x{id:X} {edid} missing"); return; }
            Console.WriteLine($"  REFR {r.FormKey.ID:X6} {r.EditorID} base {r.Base.FormKey} flags 0x{r.MajorRecordFlagsRaw:X} at {Show(r.Position)}" +
                              (r.EnableParent is { } ep ? $" enable parent {ep.Reference.FormKey} flags {ep.Flags}" : ""));
            Need(r.EditorID == edid, $"REFR 0x{id:X} is {r.EditorID}, not {edid}");
            Need(r.Base.FormKey == baseKey, $"REFR {edid}: base {r.Base.FormKey}, not {baseKey}");
            Need((r.MajorRecordFlagsRaw & 0x400) != 0, $"REFR {edid} is not persistent");
            Need(((r.MajorRecordFlagsRaw & 0x800) != 0) == disabled, $"REFR {edid} initially-disabled flag is not {disabled}");
            if (enableParent is { } p) Need(r.EnableParent is not null && r.EnableParent.Reference.FormKey == p && r.EnableParent.Flags == 0, $"REFR {edid}: enable parent is not {p} with flags 0");
            else Need(r.EnableParent is null, $"REFR {edid} has an enable parent");
        }
        Ref(P4MarkerId, "FOCC_P4_SpawnMarker", xmarker, false, null);
        for (int k = 0; k < P8Stages; k++)
        {
            Ref(P8Parent0Id + (uint)k, $"FOCC_P8_Stage{k}Parent", xmarker, k != 0, null);
            for (int j = 0; j < P8ChildrenPerStage; j++)
                Ref(P8Child0Id + (uint)(k * P8ChildrenPerStage + j), $"FOCC_P8_Child_{k}_{j}", o.Stat, false, K(P8Parent0Id + (uint)k));
        }
        Ref(P9DestId, "FOCC_P9_Dest", xmarker, false, null);
        Need(refs.Count == 2 + P8Stages * (1 + P8ChildrenPerStage), $"{refs.Count} REFR, not {2 + P8Stages * (1 + P8ChildrenPerStage)}");

        // the leveled lists and their conditions (read back field by field: the API has no precedent here)
        if (o.Lvln)
        {
            CheckBase<INpcGetter>(m, o.LvlnA, "--lvln-a", warnings);
            CheckBase<INpcGetter>(m, o.LvlnB, "--lvln-b", warnings);
            var lists = plug.LeveledNpcs.ToDictionary(l => l.FormKey);
            void CheckList(uint id, string edid, (FormKey Base, int Fn, CompareOperator Op, float Value, FormKey Param)[] want)
            {
                if (!lists.TryGetValue(K(id), out var l)) { problems.Add($"LVLN 0x{id:X} {edid} missing"); return; }
                var entries = l.Entries?.ToList() ?? new List<ILeveledNpcEntryGetter>();
                Console.WriteLine($"  LVLN {l.EditorID} {l.FormKey}: " + string.Join("; ", entries.Select(e =>
                    $"{e.Reference.FormKey} L{e.Level} x{e.Count} cond " + (ReadCondition(e) is { } c ? $"fn={c.Fn} {c.Op} {F(c.Value)} param={c.Param}" : "none"))));
                Need(l.EditorID == edid, $"LVLN 0x{id:X} is {l.EditorID}, not {edid}");
                Need(entries.Count == want.Length, $"LVLN {edid} has {entries.Count} entries, not {want.Length}");
                for (int i = 0; i < Math.Min(entries.Count, want.Length); i++)
                {
                    var e = entries[i];
                    var c = ReadCondition(e);
                    Need(e.Reference.FormKey == want[i].Base && e.Level == 1 && e.Count == 1, $"LVLN {edid}[{i}] is not {want[i].Base} level 1 count 1");
                    Need(c is not null && c.Value.Fn == want[i].Fn && c.Value.Op == want[i].Op && c.Value.Value == want[i].Value && c.Value.Param == want[i].Param,
                         $"LVLN {edid}[{i}] condition is not function {want[i].Fn} {want[i].Op} {F(want[i].Value)} on {want[i].Param}");
                }
            }
            CheckList(P6ListId, "FOCC_P6_HolderList", new[]
            {
                (o.LvlnA, KeywordDataForCurrentLocation, CompareOperator.EqualTo, 1f, K(HolderId)),
                (o.LvlnB, KeywordDataForCurrentLocation, CompareOperator.EqualTo, 2f, K(HolderId)),
            });
            CheckList(P7ListId, "FOCC_P7_RepList", new[]
            {
                (o.LvlnA, GetGlobalValue, CompareOperator.LessThan, 8f, K(RepId)),
                (o.LvlnB, GetGlobalValue, CompareOperator.GreaterThanOrEqualTo, 8f, K(RepId)),
            });
            Need(lists.Count == 2, "not exactly 2 LVLN");
        }
        else Need(plug.LeveledNpcs.Count == 0, "--skip lvln but the plugin holds LVLN records");

        // the P10 quest and the Story Manager nodes
        var quests = plug.Quests.ToDictionary(q => q.FormKey);
        Need(quests.Count == 2, "not exactly 2 QUST");
        if (!quests.TryGetValue(K(P10QuestId), out var p10)) problems.Add($"QUST 0x{P10QuestId:X} {P10QuestEdid} missing");
        else
        {
            Console.WriteLine($"  QUST {p10.EditorID} flags {p10.Data?.Flags} event {p10.Event?.ToString() ?? "none"} scripts [{string.Join(",", p10.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? Array.Empty<string>())}]");
            Need(p10.EditorID == P10QuestEdid && p10.Data is not null && !p10.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled), $"{P10QuestEdid} is not a non-start-game-enabled quest");
            Need(p10.Stages.Count == 0, $"{P10QuestEdid} has stages");
            Need(p10.VirtualMachineAdapter?.Scripts.Any(s => s.Name == P10Script) == true, $"script {P10Script} not attached to {P10QuestEdid}");
            if (o.Sm) Need(p10.Event == ScriptEvent, $"{P10QuestEdid} event is {p10.Event?.ToString() ?? "none"}, not SCPT (Script Event)");
        }
        if (o.Sm)
        {
            var (smen, tail) = ScriptEventNode(m.Sf);
            var branch = plug.StoryManagerBranchNodes.FirstOrDefault(b => b.FormKey == K(P10BranchId));
            var node = plug.StoryManagerQuestNodes.FirstOrDefault(n => n.FormKey == K(P10NodeId));
            Console.WriteLine($"  SMBN {branch?.EditorID} parent {branch?.Parent.FormKeyNullable?.ToString() ?? "none"} previous {branch?.PreviousSibling.FormKeyNullable?.ToString() ?? "none"}; " +
                              $"SMQN {node?.EditorID} parent {node?.Parent.FormKeyNullable?.ToString() ?? "none"} quests [{string.Join(",", node?.Quests.Select(q => q.Quest.FormKey.ToString()) ?? Array.Empty<string>())}]; " +
                              $"vanilla Script Event node {(smen is null ? "none" : $"{smen.EditorID} {smen.FormKey}, tail {(tail.IsNull ? "none" : tail.ToString())}")}");
            Need(branch is not null && branch.EditorID == "FOCC_P10_Branch", $"SMBN 0x{P10BranchId:X} FOCC_P10_Branch missing");
            if (branch is not null)
            {
                if (smen is null) { Need(branch.Parent.FormKeyNullable is null, "SMBN has a parent but the Starfield.esm read has no Script Event node"); warnings.Add("no Script Event SMEN in the Starfield.esm read: the branch is a root node"); }
                else
                {
                    Need(branch.Parent.FormKeyNullable == smen.FormKey, $"SMBN parent is not the Script Event node {smen.FormKey}");
                    Need((branch.PreviousSibling.FormKeyNullable ?? FormKey.Null) == tail, $"SMBN previous sibling is not that node's last child {(tail.IsNull ? "none" : tail.ToString())}");
                    var cond = branch.Conditions.Count == 1 ? branch.Conditions[0] as IConditionFloatGetter : null;
                    var ev = cond?.Data as IGetEventDataConditionDataGetter;
                    var filter = EventKeywordFilter(m.Sf, smen.FormKey);
                    var ours = ev is null || cond is null ? $"none ({branch.Conditions.Count} conditions)"
                        : $"GetEventData {ev.Function}/{ev.Member} record {ev.Record.FormKey} {cond.CompareOperator} {cond.ComparisonValue}";
                    var vanilla = "none";
                    if (filter.HasValue)
                    {
                        var vf = filter.Value;
                        var vd = (IGetEventDataConditionDataGetter)vf.Cond.Data;
                        vanilla = $"{vd.Function}/{vd.Member} {vf.Cond.CompareOperator} {vf.Cond.ComparisonValue}, {vf.Count} of {vf.Total}, e.g. {vf.Node}";
                        if (ev is not null && cond is not null)
                            Need(ev.Function == vd.Function && ev.Member == vd.Member && cond.CompareOperator == vf.Cond.CompareOperator && cond.ComparisonValue == vf.Cond.ComparisonValue,
                                 "FOCC_P10_Branch's condition is not the vanilla keyword filter's shape");
                    }
                    Console.WriteLine($"  SMBN condition {ours}; vanilla keyword filter {vanilla}");
                    Need(ev is not null && ev.Record.FormKey == K(P10EventId), "FOCC_P10_Branch has no single GetEventData condition naming FOCC_P10_Event: any script event would start FOCC_P10_Quest");
                }
            }
            Need(node is not null && node.EditorID == "FOCC_P10_QuestNode" && node.Parent.FormKeyNullable == K(P10BranchId) &&
                 node.Quests.Select(q => q.Quest.FormKey).SequenceEqual(new[] { K(P10QuestId) }), $"SMQN 0x{P10NodeId:X} FOCC_P10_QuestNode under the branch listing {P10QuestEdid} missing");
            Need(plug.StoryManagerBranchNodes.Count == 1 && plug.StoryManagerQuestNodes.Count == 1 && plug.StoryManagerEventNodes.Count == 0, "SM records other than one SMBN and one SMQN");
        }
        else Need(plug.StoryManagerBranchNodes.Count == 0 && plug.StoryManagerQuestNodes.Count == 0, "--skip sm but the plugin holds SM nodes");

        // the P3 cell overrides
        if (o.P3Cells)
        {
            Need(cells.Count == P3Cells.Length, $"{cells.Count} interior CELL, not {P3Cells.Length}");
            for (int i = 0; i < P3Cells.Length; i++)
            {
                var c0 = FindCell(m.Port!, P3Cells[i]);
                var c = cells.FirstOrDefault(x => x.FormKey == c0.FormKey);
                Console.WriteLine($"  CELL {P3Cells[i]} {c0.FormKey}: {(c is null ? "not overridden" : $"location {c.Location.FormKeyNullable?.ToString() ?? "none"}, {c.Persistent.Count}+{c.Temporary.Count} refs")}");
                Need(c is not null && c.Location.FormKeyNullable == K(P3CellLocations[i]) && c.Persistent.Count == 0 && c.Temporary.Count == 0 && c.NavigationMeshes.Count == 0,
                     $"CELL {P3Cells[i]} is not overridden without children with location 0x{P3CellLocations[i]:X}");
            }
        }
        else Need(cells.Count == 0, "a CELL override without --p3-cells");

        // the probe quest and its properties
        if (!quests.TryGetValue(K(QuestId), out var q)) problems.Add($"QUST 0x{QuestId:X} {QuestEdid} missing");
        else
        {
            var v = q.VirtualMachineAdapter;
            Console.WriteLine($"  QUST {q.EditorID} flags {q.Data?.Flags} stages {q.Stages.Count} vmad ver={v?.Version} fmt={v?.ObjectFormat} ebdv={v?.ExtraBindDataVersion}");
            Need(q.EditorID == QuestEdid && q.Data is not null && q.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled) && q.Stages.Count == 0, $"{QuestEdid} is not start game enabled without stages");
            var s = v?.Scripts.FirstOrDefault(x => x.Name == QuestScript);
            if (s is null) problems.Add($"script {QuestScript} not attached");
            else
            {
                var props = s.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {s.Name}: " + string.Join(", ", s.Properties.Select(p =>
                    p is IScriptObjectPropertyGetter op ? $"{p.Name}->{op.Object.FormKey}" :
                    p is IScriptObjectListPropertyGetter lp ? $"{p.Name}[{lp.Objects.Count}]" :
                    p is IScriptStringPropertyGetter sp ? $"{p.Name}=\"{sp.Data}\"" : p.Name)));
                void Prop(string name, FormKey want)
                {
                    Need(props.TryGetValue(name, out var p) && p is IScriptObjectPropertyGetter op && op.Object.FormKey == want && op.Alias == -1 && op.Unused == 0,
                         $"property {name} does not point at {want} as a direct reference");
                }
                void PropList(string name, IEnumerable<FormKey> want)
                {
                    var got = props.TryGetValue(name, out var p) && p is IScriptObjectListPropertyGetter lp ? lp.Objects.ToList() : null;
                    Need(got is not null && got.Select(x => x.Object.FormKey).SequenceEqual(want) && got.All(x => x.Alias == -1 && x.Unused == 0),
                         $"property {name} does not list the expected records in order");
                }
                Prop("Holder", K(HolderId)); Prop("Route", K(RouteId)); Prop("P2Loc", K(P2LocId));
                Prop("P3LocNoParent", K(P3NoParentId)); Prop("P3LocChained", K(P3ChainedId));
                Prop("P4Marker", K(P4MarkerId)); Prop("P4Base", o.Npc);
                PropList("P5Globals", Enumerable.Range(0, P5Count).Select(i => K(P5FirstId + (uint)i)));
                if (o.Lvln) { Prop("P6List", K(P6ListId)); Prop("P6BaseA", o.LvlnA); Prop("P6BaseB", o.LvlnB); Prop("P7List", K(P7ListId)); }
                else Need(!props.ContainsKey("P6List") && !props.ContainsKey("P7List"), "--skip lvln but the list properties are filled");
                Prop("P7Rep", K(RepId));
                PropList("P8Parents", Enumerable.Range(0, P8Stages).Select(k => K(P8Parent0Id + (uint)k)));
                PropList("P8Children", Enumerable.Range(0, P8Stages * P8ChildrenPerStage).Select(i => K(P8Child0Id + (uint)i)));
                Prop("P9Dest", K(P9DestId)); Prop("P10Event", K(P10EventId)); Prop("P10Quest", K(P10QuestId));
                // P9's package driver: alias 0, empty, optional and allow reserved, with only DefaultTraveltoLinkedRef
                var aliases = (q.Aliases ?? new List<IAQuestAliasGetter>()).ToList();
                var walker = aliases.OfType<IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == WalkerAliasId);
                Console.WriteLine($"  aliases: " + string.Join(", ", aliases.Select(a => a is IQuestReferenceAliasGetter r
                    ? $"{r.ID} {r.Name} flags {r.Flags} packages [{string.Join(",", r.PackageData.Select(x => x.FormKey.ToString()))}]"
                    : a.GetType().Name)));
                var travelKey = new FormKey(SfEsm, TravelToLinkedRef);
                Need(aliases.Count == 1 && walker is not null && walker.Name == WalkerAlias && walker.Flags == WalkerFlags
                     && walker.ForcedReference.IsNull && walker.PackageData.Select(x => x.FormKey).SequenceEqual(new[] { travelKey }),
                     $"alias {WalkerAliasId} {WalkerAlias} (empty, optional, allow reserved, only {TravelToLinkedRefEdid} as its package) missing or different");
                if (TravelProblem(m) is string tp)
                {
                    if (m.Cache.TryResolve<IStarfieldMajorRecordGetter>(travelKey, out _)) problems.Add(tp);
                    else warnings.Add(tp + ": not in the Starfield.esm read here");
                }
                var variant = props.TryGetValue("Variant", out var vp) && vp is IScriptStringPropertyGetter vs ? vs.Data : null;
                Need(o.P3Cells ? variant == "p3cells" : variant is null, $"property Variant is {variant ?? "unset"}; the build is {(o.P3Cells ? "p3cells" : "default")}");
            }
        }
        foreach (var x in warnings) Console.WriteLine("WARN  " + x);
        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }
}
