// PlanetProbe: the test world of the planet probe (docs/planet/planet-probe.md), written from the probe_params.json
// that scripts/planet/make_planet_probe.py stage makes (src/fo4sf/planet/probe.py holds the layout and the raw check).
//
// FO4SFPlanetProbe.esm (masters Starfield.esm + FO4SFPlanet.esm, the planet master the stage wrote just before):
//   T1..T6   six test references around the arrival (persistent / temporary, with / without location links)
//   COC      a COCMarkerHeading in the spawn cell (coc FO4SF_PlanetProbeSpawn)
//   SFBK     the overlay block: a copy of OverlayBlockLC172World with our BTD path, DNAM, FNAM, INAM, HNAM
//   LCTN     the probe location: a copy of LC172WorldLocation without its references, keyword LocTypeOverlay, parent =
//            our planet's surface location (FO4SFPlanet.esm), one LCPR row per linked test reference
//   WRLD     a copy of LC172World (the Mars landing world the terrain experiments copied) without its cells, offset
//            tables, large references and parent; the overlay component names our planet's system id (Sol's in
//            route B, ours in route A), planet id and block;
//            the climate stays LC172's (the sky then tells whether the world record or the planet decides it)
//   CELL     the persistent cell and the exterior cells (cell_min..cell_max on both axes), spawn cell EditorID
//   QUST     start game enabled, no stages, script FO4SF_PlanetProbeQuest with no properties (the script finds every
//            reference with Game.GetFormFromFile: a script property would make a temporary reference persistent)
// Record shapes proven in game elsewhere: dotnet/TerrainExp1 (overlay WRLD + SFBK + cells + COC marker, exp1d/exp2b),
// dotnet/MapMarkers and dotnet/TerrainOverlays (LCTN rows), dotnet/Mission (persistent ACHR), dotnet/CombinedProbe
// (QUST + VMAD). New here and unverified in game: LCPR rows (Location.MasterPersistLocationReferences), XLCN on a
// placed reference (PersistentLocation), a temporary ACHR, an overlay component naming a plugin's planet (in Sol, or
// in a star system of a plugin).
//
// usage: PlanetProbe build <template plugin (Starfield.esm)> <probe_params.json> <out dir>
//        PlanetProbe check <written plugin> <template plugin> <probe_params.json>     exit 1 on a mismatch
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    if (args.Length == 4 && args[0] == "build") return PlanetProbe.Build(args[1], args[2], args[3]);
    if (args.Length == 4 && args[0] == "check") return PlanetProbe.Check(args[1], args[2], args[3]);
}
catch (PlanetProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: PlanetProbe build <Starfield.esm> <probe_params.json> <out dir> | " +
                        "PlanetProbe check <plugin> <Starfield.esm> <probe_params.json>");
return 2;

static class PlanetProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    const int Persistent = 0x400;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    // ---------------------------------------------------------------- parameters (src/fo4sf/planet/probe.py params())

    public record Ref(uint Id, string Tag, string Edid, string Kind, FormKey Base, bool Persistent, bool Linked, P3Float Pos, P3Float Rot,
        bool ExteriorPersistent = false);
    public record Params(
        ModKey Plugin, ModKey PlanetPlugin, string Author, int SystemId, int PlanetId, FormKey Surface,
        FormKey TWorld, string TWorldEdid, FormKey TBlock, string TBlockEdid, FormKey TLocation, string TLocationEdid,
        FormKey OverlayKeyword, FormKey? WorldBiome,
        uint BlockId, string BlockEdid, string Anam, int Dnam, byte[] Fnam, byte Inam, short Hnam,
        uint LocationId, string LocationEdid, string LocationName,
        uint WorldId, string WorldEdid, string WorldName, int CellMin, int CellMax,
        uint PersistentCellId, uint FirstCellId, P2Int SpawnCell, string SpawnEdid,
        List<Ref> Refs, uint QuestId, string QuestEdid, string QuestName, string Script, uint NextId);

    static FormKey Key(string s)
    {
        var i = s.IndexOf(':');
        if (i <= 0) throw new Refusal($"form key {s} is not <hex id>:<plugin>");
        return new FormKey(ModKey.FromFileName(s[(i + 1)..]), Convert.ToUInt32(s[..i], 16));
    }

    static P3Float Vec(JsonElement e)
    {
        var v = e.EnumerateArray().Select(x => x.GetSingle()).ToArray();
        if (v.Length != 3 || v.Any(f => !float.IsFinite(f))) throw new Refusal($"{e} is not three finite numbers");
        return new P3Float(v[0], v[1], v[2]);
    }

    public static Params Load(string path)
    {
        var r = JsonDocument.Parse(File.ReadAllText(path)).RootElement;
        if (r.GetProperty("kind").GetString() != "planet_probe_params") throw new Refusal($"{path} is not planet probe params");
        string S(JsonElement e, string k) => e.GetProperty(k).GetString() ?? throw new Refusal($"{k} is null");
        uint U(JsonElement e, string k) => e.GetProperty(k).GetUInt32();
        var t = r.GetProperty("templates");
        var b = r.GetProperty("block");
        var l = r.GetProperty("location");
        var w = r.GetProperty("world");
        var sp = r.GetProperty("spawn");
        var q = r.GetProperty("quest");
        var fnam = b.GetProperty("fnam").EnumerateArray().Select(x => checked((ushort)x.GetInt32())).ToArray();
        var dnam = b.GetProperty("dnam").GetInt32();
        if (fnam.Length != dnam * dnam) throw new Refusal($"fnam has {fnam.Length} values, DNAM {dnam} x {dnam} needs {dnam * dnam}");
        var refs = r.GetProperty("refs").EnumerateArray().Select(e => new Ref(
            U(e, "id"), S(e, "tag"), S(e, "edid"), S(e, "kind"), Key(S(e, "base")), e.GetProperty("persistent").GetBoolean(),
            e.GetProperty("linked").GetBoolean(), Vec(e.GetProperty("pos")), Vec(e.GetProperty("rot")),
            e.TryGetProperty("exterior_persistent", out var xp) && xp.GetBoolean())).ToList();
        var cell = sp.GetProperty("cell").EnumerateArray().Select(x => x.GetInt32()).ToArray();
        var biome = r.GetProperty("world_biome");
        return new Params(
            ModKey.FromFileName(S(r, "plugin")), ModKey.FromFileName(S(r, "planet_plugin")), S(r, "author"),
            r.GetProperty("system_id").GetInt32(), r.GetProperty("planet_id").GetInt32(),
            new FormKey(ModKey.FromFileName(S(r, "planet_plugin")), U(r, "surface_location")),
            Key(S(t.GetProperty("world"), "key")), S(t.GetProperty("world"), "edid"),
            Key(S(t.GetProperty("block"), "key")), S(t.GetProperty("block"), "edid"),
            Key(S(t.GetProperty("location"), "key")), S(t.GetProperty("location"), "edid"),
            Key(S(r, "keyword_overlay")), biome.ValueKind == JsonValueKind.Null ? null : Key(biome.GetString()!),
            U(b, "id"), S(b, "edid"), S(b, "anam"), dnam, fnam.SelectMany(v => new[] { (byte)(v & 0xFF), (byte)(v >> 8) }).ToArray(),
            checked((byte)b.GetProperty("inam").GetInt32()), checked((short)b.GetProperty("hnam").GetInt32()),
            U(l, "id"), S(l, "edid"), S(l, "name"),
            U(w, "id"), S(w, "edid"), S(w, "name"), w.GetProperty("cell_min").GetInt32(), w.GetProperty("cell_max").GetInt32(),
            U(r, "persistent_cell"), U(r, "first_cell"), new P2Int(cell[0], cell[1]), S(sp, "edid"),
            refs, U(q, "id"), S(q, "edid"), S(q, "name"), S(q, "script"), U(r, "next_id"));
    }

    static P2Int CellOf(P3Float p) => new((int)Math.Floor(p.X / 100.0), (int)Math.Floor(p.Y / 100.0));
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
    static string P(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    // the master list the plugin must carry: Starfield.esm, the template's own plugin when it is another one (the
    // cloud smoke test copies Creation records), then the planet master
    static ModKey[] LoadOrder(ModKey template, Params p) =>
        new[] { SfEsm, template, p.PlanetPlugin }.Distinct().ToArray();

    // Starfield.esm itself, or (the cloud smoke test) a Creation whose only master is Starfield.esm, a full master
    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static T Find<T>(IEnumerable<T> items, FormKey key, string edid, string what) where T : IMajorRecordGetter
    {
        var x = items.FirstOrDefault(i => i.FormKey == key) ?? throw new Refusal($"no {what} {key} in the template plugin");
        if (!string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"{what} {key} is {x.EditorID}, not {edid}");
        return x;
    }

    // ---------------------------------------------------------------- build

    public static int Build(string templatePath, string paramsPath, string outDir)
    {
        var p = Load(paramsPath);
        using var sf = OpenTemplate(templatePath);
        var tWorld = Find(sf.Worldspaces, p.TWorld, p.TWorldEdid, "WRLD");
        var tBlock = Find(sf.EnumerateMajorRecords<ISurfaceBlockGetter>(), p.TBlock, p.TBlockEdid, "SFBK");
        var tLoc = Find(sf.Locations, p.TLocation, p.TLocationEdid, "LCTN");

        var mod = new StarfieldMod(p.Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = p.Author;
        FormKey Own(uint id) => new(p.Plugin, id);

        // the overlay block
        var block = (SurfaceBlock)tBlock.Duplicate(Own(p.BlockId));
        block.EditorID = p.BlockEdid;
        block.ANAM = p.Anam;
        block.DNAM = new SurfaceBlockIntItem { First = (uint)p.Dnam, Second = (uint)p.Dnam };
        block.FNAM = p.Fnam;
        block.INAM = p.Inam;                                                          // 1 Absolute: BTD heights are world z
        block.HNAM = unchecked((ushort)p.Hnam);
        block.Components.Clear();                                                     // BlockEditorMetaData (CK bookkeeping)
        mod.SurfaceBlocks.Add(block);

        // the probe location: LC172WorldLocation's fields, none of its references
        // the copies leave the template's (localized) names behind: ours are plain strings, and reading a string table
        // is not needed then (the cloud smoke test has none)
        var loc = (Location)tLoc.Duplicate(Own(p.LocationId), new Location.TranslationMask(defaultOn: true) { Name = false });
        loc.EditorID = p.LocationEdid;
        loc.Name = p.LocationName;
        // null, not empty: an empty list is still written as an empty subrecord (seen in the smoke test)
        loc.MasterPersistLocationReferences = null;
        loc.AddedPersistLocationReferences = null;
        loc.RemovedPersistLocationReferences = null;
        loc.MasterSpecialReferences = null;
        loc.AddedSpecialReferences = null;
        loc.RemovedSpecialReferences = null;
        loc.MasterInitiallyDisabledReferences = null;
        loc.AddedInitiallyDisabledReferences = null;
        loc.MasterUniqueNpcs = null;
        loc.AddedUniqueNpcs = null;
        loc.RemovedUniqueNpcs = null;
        loc.AddedUniqueBaseForms = null;
        loc.LocationCellUniqueReferences = null;
        loc.RemovedUniqueBaseForms = null;
        loc.MasterEnablePointReferences = null;
        loc.AddedEnablePointReferences = null;
        loc.MasterWorldspaceCells.Clear();                                       // init-only list: emptied
        loc.WorldLocationMarkerRef.Clear();
        loc.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(p.OverlayKeyword) };
        loc.ParentLocation.SetTo(p.Surface);
        if (p.Refs.Any(r => r.Linked)) loc.MasterPersistLocationReferences = new ExtendedList<LocationReference>();
        mod.Locations.Add(loc);

        // the world: LC172World without its content; the overlay component names our system, planet and block
        var world = (Worldspace)tWorld.Duplicate(Own(p.WorldId), new Worldspace.TranslationMask(defaultOn: true)
        {
            Name = false,
            SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
            TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
        });
        world.EditorID = p.WorldEdid;
        world.Name = p.WorldName;
        world.SubCells.Clear();
        world.TopCell = null;
        world.OffsetData = null;
        world.CellSizeData = null;
        world.LargeReferences.Clear();
        world.Parent = null;
        world.Location.SetTo(loc.FormKey);
        if (p.WorldBiome is FormKey biome) world.Biome.SetTo(biome);
        var overlay = world.Components.OfType<WorldSpaceOverlayComponent>().SingleOrDefault()
                      ?? throw new Refusal($"{p.TWorldEdid} has no worldspace overlay component");
        if (overlay.SNAM is not { Length: 4 } || overlay.PNAM is not { Length: 4 })
            throw new Refusal($"{p.TWorldEdid}'s overlay SNAM / PNAM are not 4 bytes");
        overlay.SNAM = BitConverter.GetBytes(p.SystemId);
        overlay.PNAM = BitConverter.GetBytes(p.PlanetId);
        overlay.SurfaceBlock.SetTo(block.FormKey);

        // cells: blocks of 32, sub-blocks of 8 (dotnet/TerrainExp1)
        var cells = new Dictionary<(int, int), Cell>();
        var blocks = new Dictionary<(int, int), WorldspaceBlock>();
        var subs = new Dictionary<(int, int), WorldspaceSubBlock>();
        uint nextCell = p.FirstCellId;
        for (int x = p.CellMin; x <= p.CellMax; x++)
            for (int y = p.CellMin; y <= p.CellMax; y++)
            {
                var c = new Cell(Own(nextCell++), Release) { Grid = new CellGrid { Point = new P2Int(x, y) } };
                if (x == p.SpawnCell.X && y == p.SpawnCell.Y) c.EditorID = p.SpawnEdid;
                cells[(x, y)] = c;
                int bx = (int)Math.Floor(x / 32.0), by = (int)Math.Floor(y / 32.0), sx = (int)Math.Floor(x / 8.0), sy = (int)Math.Floor(y / 8.0);
                if (!blocks.TryGetValue((bx, by), out var blk)) { blk = new WorldspaceBlock { BlockNumberX = (short)bx, BlockNumberY = (short)by, GroupType = GroupTypeEnum.ExteriorCellBlock }; blocks[(bx, by)] = blk; world.SubCells.Add(blk); }
                if (!subs.TryGetValue((sx, sy), out var sub)) { sub = new WorldspaceSubBlock { BlockNumberX = (short)sx, BlockNumberY = (short)sy, GroupType = GroupTypeEnum.ExteriorCellSubBlock }; subs[(sx, sy)] = sub; blk.Items.Add(sub); }
                sub.Items.Add(c);
            }
        if (nextCell > p.QuestId && p.QuestId >= p.FirstCellId) throw new Refusal("the cells overrun the quest's id");
        world.TopCell = new Cell(Own(p.PersistentCellId), Release) { Flags = Cell.Flag.HasWater };   // as TerrainExp1's

        // the test references (and the COC marker)
        foreach (var r in p.Refs)
        {
            var at = CellOf(r.Pos);
            if (r.ExteriorPersistent && !r.Persistent) throw new Refusal($"{r.Tag}: exterior_persistent needs persistent");
            if ((!r.Persistent || r.ExteriorPersistent) && !cells.ContainsKey((at.X, at.Y))) throw new Refusal($"{r.Tag} at {P(r.Pos)} lies outside the cells");
            IPlaced placed;
            if (r.Kind == "REFR")
            {
                var o = new PlacedObject(Own(r.Id), Release)
                {
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(r.Base), Position = r.Pos, Rotation = r.Rot,
                };
                if (r.Edid != "") o.EditorID = r.Edid;
                if (r.Linked) o.PersistentLocation.SetTo(loc.FormKey);
                if (r.Persistent) o.MajorRecordFlagsRaw |= Persistent;
                placed = o;
            }
            else if (r.Kind == "ACHR")
            {
                var a = new PlacedNpc(Own(r.Id), Release)
                {
                    Base = new FormLink<INpcGetter>(r.Base), Position = r.Pos, Rotation = r.Rot,
                };
                if (r.Edid != "") a.EditorID = r.Edid;
                if (r.Linked) a.PersistentLocation.SetTo(loc.FormKey);
                if (r.Persistent) a.MajorRecordFlagsRaw |= Persistent;
                placed = a;
            }
            else throw new Refusal($"{r.Tag}: kind {r.Kind} (REFR or ACHR)");
            if (r.ExteriorPersistent) cells[(at.X, at.Y)].Persistent.Add(placed);        // T7: persistent child of its own exterior cell (flag 0x400 set above)
            else if (r.Persistent) world.TopCell.Persistent.Add(placed);
            else cells[(at.X, at.Y)].Temporary.Add(placed);
            if (r.Linked)
                loc.MasterPersistLocationReferences!.Add(new LocationReference
                {
                    Actor = new FormLink<IPlacedGetter>(Own(r.Id)),
                    Location = new FormLink<IComplexLocationGetter>(world.FormKey),
                    Grid = new P2Int16((short)at.X, (short)at.Y),                  // xEdit: Grid Y then X on disk (checked raw)
                    Unknown = -1,                                                 // vanilla 0xFFFFFFFF
                });
        }
        mod.Worldspaces.Add(world);

        // the probe quest (dotnet/CombinedProbe's proven shape), no properties
        var quest = new Quest(Own(p.QuestId), Release)
        {
            EditorID = p.QuestEdid, Name = p.QuestName, FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = p.Script, Flags = ScriptEntry.Flag.Local });
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = p.NextId;

        // an existing plugin stays until the write succeeds (MergeProbe)
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, p.Plugin.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        var order = LoadOrder(sf.ModKey, p);
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, p.Plugin.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(order)
                .WithKnownMasters(order.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): WRLD {world.EditorID} {world.FormKey} (copy of {tWorld.EditorID}), " +
                          $"overlay system {p.SystemId} planet {p.PlanetId} block {block.EditorID}, LCTN {loc.EditorID} parent {p.Surface} " +
                          $"({loc.MasterPersistLocationReferences?.Count ?? 0} LCPR rows), {cells.Count} cells, {p.Refs.Count} references, QUST {quest.EditorID}");
        foreach (var r in p.Refs)
            Console.WriteLine($"  {r.Tag,-4} {r.Kind} {Own(r.Id)} {r.Edid} base {r.Base} {(r.ExteriorPersistent ? "persistent in its cell" : r.Persistent ? "persistent" : "temporary")}{(r.Linked ? " + XLCN/LCPR" : "")} at {P(r.Pos)}");
        return 0;
    }

    // ---------------------------------------------------------------- check (Mutagen read-back; the raw check is probe.py)

    public static int Check(string pluginPath, string templatePath, string paramsPath)
    {
        var p = Load(paramsPath);
        using var sf = OpenTemplate(templatePath);
        var order = LoadOrder(sf.ModKey, p);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in order) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        FormKey Own(uint id) => new(p.Plugin, id);

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == p.Plugin, $"the file is {mod.ModKey}, not {p.Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(order), $"masters are not [{string.Join(", ", order)}]");

        var block = mod.EnumerateMajorRecords<ISurfaceBlockGetter>().SingleOrDefault();
        Need(block?.FormKey == Own(p.BlockId) && block.EditorID == p.BlockEdid, "not exactly our SFBK");
        if (block != null)
        {
            Console.WriteLine($"  SFBK {block.EditorID} ANAM {block.ANAM} DNAM {block.DNAM?.First}x{block.DNAM?.Second} FNAM {block.FNAM?.Length} B INAM {block.INAM} HNAM {unchecked((short)block.HNAM)}");
            Need(block.ANAM == p.Anam, "SFBK ANAM");
            Need(block.DNAM?.First == p.Dnam && block.DNAM?.Second == p.Dnam, "SFBK DNAM");
            Need(block.FNAM is { } fn && fn.ToArray().SequenceEqual(p.Fnam), "SFBK FNAM");
            Need(block.INAM == p.Inam && unchecked((short)block.HNAM) == p.Hnam, "SFBK INAM / HNAM");
        }

        var loc = mod.Locations.SingleOrDefault();
        Need(loc?.FormKey == Own(p.LocationId) && loc.EditorID == p.LocationEdid, "not exactly our LCTN");
        var linked = p.Refs.Where(r => r.Linked).ToList();
        if (loc != null)
        {
            var rows = loc.MasterPersistLocationReferences?.ToList() ?? new();
            Console.WriteLine($"  LCTN {loc.EditorID} parent {loc.ParentLocation.FormKeyNullable} keywords [{string.Join(", ", loc.Keywords?.Select(k => k.FormKey.ToString()) ?? Array.Empty<string>())}] " +
                              $"LCPR [{string.Join(", ", rows.Select(r => $"{r.Actor.FormKey} {r.Location.FormKey} ({r.Grid.X}, {r.Grid.Y}) {r.Unknown}"))}]");
            Need(loc.ParentLocation.FormKeyNullable == p.Surface, $"LCTN parent is not {p.Surface}");
            Need(loc.Keywords?.Select(k => k.FormKey).SequenceEqual(new[] { p.OverlayKeyword }) == true, "LCTN keywords are not [LocTypeOverlay]");
            Need((loc.MasterSpecialReferences?.Count ?? 0) == 0 && (loc.MasterInitiallyDisabledReferences?.Count ?? 0) == 0 &&
                 (loc.MasterUniqueNpcs?.Count ?? 0) == 0, "LCTN keeps a template reference list");
            Need(rows.Count == linked.Count, $"LCTN has {rows.Count} LCPR rows, {linked.Count} linked references");
            foreach (var r in linked)
            {
                var c = CellOf(r.Pos);
                Need(rows.Any(x => x.Actor.FormKey == Own(r.Id) && x.Location.FormKey == Own(p.WorldId) && x.Grid.X == c.X && x.Grid.Y == c.Y && x.Unknown == -1),
                     $"no LCPR row for {r.Tag}");
            }
        }

        var world = mod.Worldspaces.SingleOrDefault();
        Need(world?.FormKey == Own(p.WorldId) && world.EditorID == p.WorldEdid, "not exactly our WRLD");
        if (world != null)
        {
            var ov = world.Components.OfType<IWorldSpaceOverlayComponentGetter>().SingleOrDefault();
            int sys = ov?.SNAM is { Length: 4 } s ? BitConverter.ToInt32(s.ToArray()) : int.MinValue;
            int pl = ov?.PNAM is { Length: 4 } q ? BitConverter.ToInt32(q.ToArray()) : int.MinValue;
            Console.WriteLine($"  WRLD {world.EditorID} overlay system {sys} planet {pl} block {ov?.SurfaceBlock.FormKeyNullable} XLCN {world.Location.FormKeyNullable} climate {world.Climate.FormKeyNullable} biome {world.Biome.FormKeyNullable}");
            Need(sys == p.SystemId && pl == p.PlanetId, "overlay SNAM / PNAM are not our system and planet");
            Need(ov?.SurfaceBlock.FormKeyNullable == Own(p.BlockId), "overlay block is not ours");
            Need(world.Location.FormKeyNullable == Own(p.LocationId), "WRLD XLCN is not our location");
            Need(world.Parent == null && world.OffsetData == null && world.CellSizeData == null && (world.LargeReferences?.Count ?? 0) == 0,
                 "WRLD keeps a parent, offset table or large references");
            if (p.WorldBiome is FormKey biome) Need(world.Biome.FormKeyNullable == biome, $"WRLD biome is not {biome}");
            var top = world.TopCell;
            Need(top?.FormKey == Own(p.PersistentCellId), "persistent cell id");
            var exterior = world.SubCells.SelectMany(b => b.Items).SelectMany(sb => sb.Items).ToList();
            int n = p.CellMax - p.CellMin + 1;
            Need(exterior.Count == n * n, $"{exterior.Count} exterior cells, {n * n} expected");
            Need(exterior.Count(c => c.EditorID == p.SpawnEdid) == 1, $"one cell {p.SpawnEdid}");
            var spawn = exterior.FirstOrDefault(c => c.EditorID == p.SpawnEdid);
            Need(spawn?.Grid?.Point == p.SpawnCell, "spawn cell grid");
            foreach (var r in p.Refs)
            {
                var at = CellOf(r.Pos);
                var ownCell = exterior.FirstOrDefault(c => c.Grid?.Point == at);
                var host = r.ExteriorPersistent ? ownCell?.Persistent : r.Persistent ? top?.Persistent : ownCell?.Temporary;
                if (r.ExteriorPersistent)
                    Need(top?.Persistent.All(x => x.FormKey != Own(r.Id)) ?? true, $"{r.Tag} {Own(r.Id)} is in the world's persistent cell");
                var got = host?.FirstOrDefault(x => x.FormKey == Own(r.Id));
                Need(got != null, $"{r.Tag} {Own(r.Id)} not in its {(r.ExteriorPersistent ? "exterior persistent" : r.Persistent ? "persistent" : "temporary")} group");
                if (got == null) continue;
                Need(((got.MajorRecordFlagsRaw & Persistent) != 0) == r.Persistent, $"{r.Tag} persistent flag");
                if (r.Kind == "REFR" && got is IPlacedObjectGetter o)
                {
                    Need(o.Base.FormKey == r.Base && o.Position == r.Pos && o.Rotation == r.Rot, $"{r.Tag} base / position");
                    Need(o.PersistentLocation.FormKeyNullable == (r.Linked ? loc?.FormKey : null), $"{r.Tag} XLCN");
                    Console.WriteLine($"  {r.Tag,-4} REFR {o.FormKey} base {o.Base.FormKey} flags 0x{o.MajorRecordFlagsRaw:X} at {P(o.Position)} XLCN {o.PersistentLocation.FormKeyNullable}");
                }
                else if (r.Kind == "ACHR" && got is IPlacedNpcGetter a)
                {
                    Need(a.Base.FormKey == r.Base && a.Position == r.Pos && a.Rotation == r.Rot, $"{r.Tag} base / position");
                    Need(a.PersistentLocation.FormKeyNullable == (r.Linked ? loc?.FormKey : null), $"{r.Tag} XLCN");
                    Console.WriteLine($"  {r.Tag,-4} ACHR {a.FormKey} base {a.Base.FormKey} flags 0x{a.MajorRecordFlagsRaw:X} at {P(a.Position)} XLCN {a.PersistentLocation.FormKeyNullable}");
                }
                else Need(false, $"{r.Tag} is not a {r.Kind}");
            }
        }

        var quest = mod.Quests.SingleOrDefault();
        Need(quest?.FormKey == Own(p.QuestId) && quest.EditorID == p.QuestEdid, "not exactly our QUST");
        if (quest != null)
        {
            var scripts = quest.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Console.WriteLine($"  QUST {quest.EditorID} flags {quest.Data?.Flags} stages {quest.Stages.Count} scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(quest.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "QUST is not start game enabled");
            Need(scripts.Count == 1 && scripts[0].Name == p.Script && scripts[0].Properties.Count == 0, $"QUST script is not {p.Script} without properties");
        }
        var kinds = mod.EnumerateMajorRecords().GroupBy(r => r.GetType().Name.Replace("BinaryOverlay", "")).Select(g => $"{g.Key} {g.Count()}");
        Console.WriteLine($"  records: {string.Join(", ", kinds)}");
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }
}
