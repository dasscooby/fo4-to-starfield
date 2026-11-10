// MapMarkers: the plugin that puts the core's map markers into the merged world (docs/terrain/map-markers.md
// "Markers in the merged world", scripts/mapmarkers/make_map_markers.py).
//
// FO4SFMapMarkers.esm (master: the core plugin, the only file it references) holds one quest per PerQuest markers:
//   0x800  QUST FO4SF_MapMarkersQuest  start-game-enabled, no stages, carrying FO4SF_MapMarkers
//          (scripts/mapmarkers/FO4SF_MapMarkers.psc) with Markers -> the core's MapMarker REFRs (base STAT 00000010
//          of Starfield.esm) in FormID order, LocalX / LocalY / LocalZ -> their written positions, and MaxMoves ->
//          twice its marker count when that is above the script's default 40
//   0x801  FO4SF_MapMarkersQuest2, ... the next PerQuest markers, the same way. Papyrus arrays hold at most 128
//          entries when made in script; whether a plugin-filled property may hold more is unverified. Each quest
//          places its markers one at a time, a marker every 0.45 s at 100 a quest (45 s for the first placement on the
//          PC, fo4sf_map.0.log 2026-10-31; inferred: the game answers about one of the script's calls a frame), and
//          the quests run side by side, so 20 a quest.
//   and an override of every one of those REFRs (the owner's play test of 2026-10-22, docs/terrain/map-markers.md
//   "Overrides"): the map-marker flags without UseLocationName (the core copies LC172's 0x1B, and the map then
//   printed the cell's location name instead of the marker's), and the position lifted by ZLift metres (the Concord
//   arrival stood half in the ground at the sampled terrain height; the Red Rocket one dropped 1.9 m without harm).
//   LocalZ holds the lifted height, so the mover puts the marker where the override says.
// The override's containers, the core's WRLD and its persistent CELL, come along as copies that override the core's
// records too (this plugin loads after it), so a stage belongs to one core build. --world takes the WRLD copy from
// dotnet/BorderProbe's variants instead of the core (the border settling test, Interiors, 2026-10-22):
//   control  as the core (SmallWorld kept, HNAM as the core's: today's)
//   nosmall  DATA without SmallWorld, HNAM as the core's
//   city     DATA without SmallWorld, HNAM 5
// check expects the same variant (--world again) and fails any other copy.
// --extra <json> adds markers of this plugin's own (the owner's "more location markers", 2026-10-23; the rest of FO4's
// named Commonwealth markers that make_map_markers.py stage --fo4-map-markers picks, so no core rebuild): each a copy
// of the core's first marker REFR (LC172's template, as the core writes its own) at 0x900, 0x901, ... in the plugin,
// persistent in the WRLD copy's persistent cell at its local spot (z the core's BTD ground, lifted as the overrides),
// its own name, flags as the overrides'; one MapMarkerRefType LCSR row each in an override of the core's Location
// that lists the core's markers (as TerrainOverlays writes the core's own); and the quests' Markers / LocalX / Y / Z
// list them after the core's markers. check takes the same --extra and fails a plugin with any other own REFR, and a
// Location override that differs from the core's in anything but those rows. Without --extra the plugin is as before.
// --landing <json> adds a temporary ship landing spot of this plugin's own (the owner's "temp ship landing spot",
// 2026-10-23), laid out as LandingOverlay01 lands a ship (docs/terrain/map-markers.md "How a vanilla world lands a
// ship"): at 0x8F0 the pad (ShipLandingMarker_80m_Large 00007145) linked by LandingZoneTriggerKeyword to 0x8F1, the
// landing-zone trigger (landingZoneTrigger 00267F4C, LandingOverlay01's box primitive), and by
// LinkShipLandingOverlayMapMarker to 0x8F2, a "Landing Area" map marker (a copy of the core's first marker with
// LandingOverlay01's flags 0x33, type 45 and radius 100) that links to 0x8F3, an XMarkerHeading (00000034). All four
// are persistent in the WRLD copy's persistent cell at the json's positions (no lift here: make_map_markers.py
// writes them), the trigger too (LandingOverlay01's is temporary), so the quests move them with the markers; the
// Location override gets LandingOverlay01Location's three rows (MapMarkerRefType to the marker,
// ShipLandingMarkerRefType and its _Large twin to the pad) after --extra's. check takes the same --landing.
// --star-map <json> keeps "Visible on Star Map" (map-marker flag bit 4, 0x10; xEdit's SF1 definitions and the Creation Kit's
// Marker Data labels) on the markers it names and clears it on every other core override and --extra marker, so Mars's
// planet view, which stacks the markers at one spot on the globe into one icon with a list (docs/terrain/map-markers.md
// "Star map"), lists only those and the landing marker (0x33 keeps it); the surface map keeps every marker. The owner's
// pick A, 2026-10-28. strict: a name that matches no marker fails the build; otherwise the build prints it and goes on.
// check takes the same --star-map. Without it the flags stay the core's (0x13: on the star map), as before.
// --reload adds the reload's stop (FO4SF_MapMarkers.psc HopMarker): the map lists only the markers that are in a world
// when the player enters it, and the quests move them in after (owner, 2026-10-31: none showed, or could be discovered,
// until a trip to Cydonia and back), so the first quest takes the player to this plugin's own interior and back once.
// At 0x8F4 the interior CELL FO4SF_MapMarkersHop, lit as dotnet/PluginSpike's door test cell (in game, 2026-10-08:
// lighting template 006658, image space 122393, the black cube map), holding that cell's 8 x 8 m platform 050776 at 0x8F6
// and at 0x8F5 a persistent COCMarkerHeading (000032) on it, which the first quest's HopMarker names. check takes the
// same --reload.
// The quest's VMAD shape is dotnet/Bridge's (vanilla Starfield quests: version 6, object format 2, extra-bind-data
// version 3, an empty fragment script entry, object properties with alias -1; record version 581 / 12).
//
// usage: MapMarkers build --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFMapMarkers.esm] [--z-lift <m>] [--world control|nosmall|city] [--extra <json>] [--landing <json>] [--star-map <json>] [--reload]
//        MapMarkers check <plugin> <FO4TerrainCore.esm> [--z-lift <m>] [--world control|nosmall|city] [--extra <json>] [--landing <json>] [--star-map <json>] [--reload]   reads both back (exit 1 on a mismatch)
// --extra: {"markers": [{"tag", "name", "pos": [x, y, z], "cell": [x, y]}, ...]} (fo4sf.map_markers.overlay_markers
// entries: local metres, z the ground before the lift), written by make_map_markers.py stage --fo4-map-markers.
// --landing: {"landing": {"tag", "name", "pad" | "trigger" | "marker" | "heading": {"pos": [x, y, z], "rot": [x, y, z],
// "cell": [x, y]}}} (fo4sf.map_markers.landing_spot: local metres, final positions), from make_map_markers.py --landing.
// --star-map: {"names": ["Sanctuary Hills", ...], "strict": true|false} (map-marker names, as the map shows them), from
// make_map_markers.py stage (its default list, not strict, unless --star-map names others).
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const uint QuestId = 0x800, MapMarkerStat = 0x10, ExtraId = 0x900, MapMarkerRefType = 0x2271F;
const uint LandingId = 0x8F0;           // pad, trigger, marker, heading: 0x8F0..0x8F3, so the quests end below 0x8F0
const uint HopId = 0x8F4;               // --reload: the stop's CELL, its marker (0x8F5) and its floor (0x8F6)
// Starfield.esm 1.16.244, dotnet/PluginSpike's door test cell (in game, 2026-10-08)
const uint HopFloor = 0x050776, CocMarkerHeading = 0x32, HopLighting = 0x006658, HopImageSpace = 0x122393;
const string HopCell = "FO4SF_MapMarkersHop";
// Starfield.esm 1.16.244, LandingOverlay01 (docs/terrain/map-markers.md "Landing overlay")
const uint LandingPad = 0x7145, LandingTrigger = 0x267F4C, XMarkerHeading = 0x34;
const uint LandingZoneTriggerKeyword = 0x267F4D, LinkShipLandingOverlayMapMarker = 0x3A866F;
const uint ShipLandingMarkerRefType = 0x9105, ShipLandingMarkerRefTypeLarge = 0x9102;
const PlacedObjectMapMarker.Flag LandingMarkerFlags = (PlacedObjectMapMarker.Flag)0x33;
const PlacedObjectMapMarker.Flag VisibleOnStarMap = (PlacedObjectMapMarker.Flag)0x10;
const sbyte LandingMarkerType = 45;
const float LandingMarkerRadius = 100;
const int PerQuest = 20, DefaultMaxMoves = 40;
const float DefaultZLift = 2.5f;        // metres above the core's sampled terrain height (local units are metres)
const float ZLiftStep = 0.1f;           // lifts come in steps of 0.1 m: the mover's ZTolerance (0.05 m, half a step) then tells
                                        // a marker a save holds at an earlier build's height from one that landed (Codex on #483)
const string ScriptName = "FO4SF_MapMarkers";
var sfKey = ModKey.FromFileName("Starfield.esm");

static int Usage()
{
    Console.Error.WriteLine("usage: MapMarkers build --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFMapMarkers.esm] [--z-lift <m>] [--world control|nosmall|city] [--extra <json>] [--landing <json>] [--star-map <json>] [--reload] | " +
                            "MapMarkers check <plugin> <FO4TerrainCore.esm> [--z-lift <m>] [--world control|nosmall|city] [--extra <json>] [--landing <json>] [--star-map <json>] [--reload]");
    return 2;
}
if (args.Length == 0) return Usage();
string Arg(string name, string dflt) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : dflt; }
float zLift;
if (!float.TryParse(Arg("--z-lift", F(DefaultZLift)), NumberStyles.Float, CultureInfo.InvariantCulture, out zLift) || !float.IsFinite(zLift) || zLift < 0)
{
    Console.Error.WriteLine("--z-lift needs a non-negative number of metres");
    return 2;
}
if (Math.Abs(zLift / ZLiftStep - Math.Round(zLift / ZLiftStep)) > 1e-3)
{
    Console.Error.WriteLine($"--z-lift must be a multiple of {F(ZLiftStep)} m: FO4SF_MapMarkers.psc re-moves a saved marker only when its height " +
                            $"is off by more than ZTolerance ({F(ZLiftStep / 2)} m), so a smaller change between builds would never reach a save");
    return 2;
}
var world = Arg("--world", "control");
var reload = args.Contains("--reload");
if (world is not ("control" or "nosmall" or "city"))
{
    Console.Error.WriteLine($"--world {world}: want control (the core's world record), nosmall or city (dotnet/BorderProbe's variants of it)");
    return 2;
}

List<Extra> extras;
try
{
    extras = LoadExtras(Arg("--extra", ""));
}
catch (Exception e) when (e is IOException or JsonException or InvalidDataException or KeyNotFoundException or InvalidOperationException or FormatException)
{
    Console.Error.WriteLine($"--extra {Arg("--extra", "")}: {e.Message}");
    return 2;
}
Landing? landing;
try
{
    landing = LoadLanding(Arg("--landing", ""));
}
catch (Exception e) when (e is IOException or JsonException or InvalidDataException or KeyNotFoundException or InvalidOperationException or FormatException)
{
    Console.Error.WriteLine($"--landing {Arg("--landing", "")}: {e.Message}");
    return 2;
}

StarMap? starMap;
try
{
    starMap = LoadStarMap(Arg("--star-map", ""));
}
catch (Exception e) when (e is IOException or JsonException or InvalidDataException or KeyNotFoundException or InvalidOperationException or FormatException)
{
    Console.Error.WriteLine($"--star-map {Arg("--star-map", "")}: {e.Message}");
    return 2;
}

BinaryReadParameters Params(params ModKey[] full)
{
    var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
    foreach (var k in full) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
    return new BinaryReadParameters { MasterFlagsLookup = styles };
}

// the core's own MapMarker references, in FormID order
List<IPlacedObjectGetter> CoreMarkers(IStarfieldModGetter core) =>
    core.EnumerateMajorRecords<IPlacedObjectGetter>()
        .Where(r => r.FormKey.ModKey == core.ModKey && r.Base.FormKey == new FormKey(sfKey, MapMarkerStat))
        .OrderBy(r => r.FormKey.ID).ToList();

if (args[0] == "build")
{
    var outDir = Arg("--out", "");
    var corePath = Arg("--core", "");
    if (outDir == "" || corePath == "") return Usage();
    var plugin = Arg("--plugin", "FO4SFMapMarkers.esm");
    var core = StarfieldMod.CreateFromBinaryOverlay(corePath, StarfieldRelease.Starfield, Params(sfKey));
    var markers = CoreMarkers(core);
    if (markers.Count == 0)
    {
        Console.Error.WriteLine($"{corePath}: no MapMarker REFR (base Starfield.esm 00000010) of its own");
        return 1;
    }
    var modKey = ModKey.FromFileName(plugin);
    var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
    mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;     // as every plugin of ours that loads

    // the overrides: the same REFRs under the core's FormKeys, with the marker's own name shown and a lifted arrival
    var cache = core.ToImmutableLinkCache();
    var lifted = new Dictionary<FormKey, P3Float>();
    foreach (var m in markers)
    {
        var ctx = cache.ResolveContext<IPlacedObject, IPlacedObjectGetter>(m.FormKey);
        var ov = ctx.GetOrAddAsOverride(mod);
        Override(ov, zLift);
        OnStarMap(ov, starMap);
        lifted[m.FormKey] = ov.Position;
    }
    // the override's parents come along as copies of the core's worldspace and its persistent cell, with every
    // persistent reference of that cell; keep only the markers (an override of anything else is not this plugin's)
    foreach (var w in mod.Worldspaces)
    {
        w.SubCells.Clear();
        if (w.TopCell == null) continue;
        w.TopCell.Persistent.RemoveAll(r => !lifted.ContainsKey(r.FormKey));
        w.TopCell.Temporary.Clear();
    }
    foreach (var w in mod.Worldspaces) WorldVariant(w, world);       // the WRLD copy as the probe's variant

    // the plugin's own markers (--extra): copies of the core's first marker in the same persistent cell, one LCSR row
    // each in an override of the core's Location, listed after the core's markers; then the landing spot (--landing)
    var all = markers.Select(m => m.FormKey).ToList();
    if (extras.Count > 0 || landing != null)
    {
        var w = mod.Worldspaces.Single();
        var known = core.EnumerateMajorRecords().Select(r => r.EditorID).Where(e => e != null).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var coreLoc = MarkersLocation(core, markers);
        if (coreLoc == null)
        {
            Console.Error.WriteLine($"{corePath}: no Location lists the core's markers in LCSR (MapMarkerRefType): --extra and --landing need one to add rows to");
            return 1;
        }
        var loc = coreLoc.DeepCopy();                                // an override: the same FormKey, in this plugin
        mod.Locations.Add(loc);
        loc.MasterSpecialReferences ??= new ExtendedList<LocationCellStaticReference>();
        for (int i = 0; i < extras.Count; i++)
        {
            var e = extras[i];
            var edid = ExtraEditorId(w, e);
            if (known.Contains(edid))
            {
                Console.Error.WriteLine($"--extra {e.Tag}: the core already has a record {edid} (a core built with these markers needs no --extra)");
                return 1;
            }
            var r = (PlacedObject)markers[0].Duplicate(new FormKey(modKey, ExtraId + (uint)i));
            r.EditorID = edid;
            r.Position = e.Pos;
            r.Rotation = new P3Float(0, 0, 0);
            r.LinkedReferences?.Clear();
            Override(r, zLift);
            r.MapMarker!.Name = e.Name;
            if (e.Type.HasValue) r.MapMarker.Type = e.Type.Value;            // the icon from the type table; else the template's
            OnStarMap(r, starMap);
            w.TopCell!.Persistent.Add(r);
            loc.MasterSpecialReferences.Add(Row(r.FormKey, w.FormKey, e));
            lifted[r.FormKey] = r.Position;
            all.Add(r.FormKey);
        }
        if (extras.Count > 0)
            Console.WriteLine($"  {extras.Count} marker(s) of this plugin ({ExtraId:X6}..{ExtraId + extras.Count - 1:X6}) in {w.TopCell!.FormKey}, " +
                              $"LCSR rows in the override of {loc.FormKey} {loc.EditorID}");
        if (landing != null)
        {
            var pieces = LandingRecords(markers[0], modKey, w, landing);
            var taken = pieces.FirstOrDefault(r => known.Contains(r.EditorID!));
            if (taken != null)
            {
                Console.Error.WriteLine($"--landing {landing.Tag}: the core already has a record {taken.EditorID}");
                return 1;
            }
            foreach (var r in pieces)
            {
                w.TopCell!.Persistent.Add(r);
                lifted[r.FormKey] = r.Position;                      // as written: make_map_markers.py lifted what needs it
                all.Add(r.FormKey);
            }
            loc.MasterSpecialReferences.AddRange(LandingRows(modKey, w.FormKey, landing));
            Console.WriteLine($"  landing spot {landing.Tag} \"{landing.Name}\" ({LandingId:X6}..{LandingId + 3:X6}): " +
                              string.Join(", ", pieces.Select(r => $"{r.EditorID} ({F(r.Position.X)}, {F(r.Position.Y)}, {F(r.Position.Z)})")) +
                              $"; 3 LCSR rows in the override of {loc.FormKey} {loc.EditorID}");
        }
    }

    if (starMap != null)
    {
        var shown = markers.Select(m => m.MapMarker?.Name?.String).Concat(extras.Select(e => e.Name)).ToList();
        // the landing marker is always on the star map (LandingMarkerFlags), so naming it is no typo
        var unmatched = starMap.Names.Where(n => !shown.Contains(n, StringComparer.Ordinal) && n != landing?.Name).ToList();
        foreach (var n in unmatched)
            (starMap.Strict ? Console.Error : Console.Out).WriteLine($"--star-map: no marker is named \"{n}\"");
        if (starMap.Strict && unmatched.Count > 0) return 1;
        Console.WriteLine($"  star map: {shown.Count(n => n != null && starMap.Names.Contains(n))} of {shown.Count} marker(s) keep Visible on Star Map " +
                          $"(--star-map: {string.Join(", ", starMap.Names.Select(n => $"\"{n}\""))})" + (landing != null ? ", and the landing marker" : ""));
    }

    var chunks = QuestChunks(all, landing != null);
    if (QuestId + (uint)chunks.Count > LandingId)
    {
        Console.Error.WriteLine($"{all.Count} markers need {chunks.Count} quests, more than fit below {LandingId:X}");
        return 1;
    }
    for (int k = 0; k < chunks.Count; k++)
    {
        var part = chunks[k];
        var quest = new Quest(new FormKey(modKey, QuestId + (uint)k), StarfieldRelease.Starfield)
        {
            EditorID = QuestName(k), Name = "FO4SF map markers", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        var script = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        var refs = new ScriptObjectListProperty { Name = "Markers", Flags = ScriptProperty.Flag.Edited };
        foreach (var m in part)
            refs.Objects.Add(new ScriptObjectProperty
            {
                Object = new FormLink<IStarfieldMajorRecordGetter>(m), Alias = -1, Unused = 0,
            });
        script.Properties.Add(refs);
        foreach (var (name, pick) in new (string, Func<P3Float, float>)[] { ("LocalX", p => p.X), ("LocalY", p => p.Y), ("LocalZ", p => p.Z) })
        {
            var list = new ScriptFloatListProperty { Name = name, Flags = ScriptProperty.Flag.Edited };
            foreach (var m in part) list.Data.Add(pick(lifted[m]));     // the override's (or own marker's) position
            script.Properties.Add(list);
        }
        if (MaxMovesFor(part.Length) is int cap)                     // every marker may need a move, plus retries
            script.Properties.Add(new ScriptIntProperty { Name = "MaxMoves", Flags = ScriptProperty.Flag.Edited, Data = cap });
        if (reload && k == 0)                                        // the first quest does the reload
            script.Properties.Add(new ScriptObjectProperty
            {
                Name = "HopMarker", Flags = ScriptProperty.Flag.Edited,
                Object = new FormLink<IStarfieldMajorRecordGetter>(new FormKey(modKey, HopId + 1)), Alias = -1, Unused = 0,
            });
        var vmad = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        vmad.Scripts.Add(script);
        quest.VirtualMachineAdapter = vmad;
        mod.Quests.Add(quest);
    }

    if (reload)
    {
        var cell = HopRecord(modKey);
        var block = new CellBlock { BlockNumber = (int)(HopId % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((HopId / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);
    }
    mod.ModHeader.Stats.NextFormID = extras.Count > 0 ? ExtraId + (uint)extras.Count
        : reload ? HopId + 3 : landing != null ? LandingId + 4 : QuestId + (uint)chunks.Count;
    Directory.CreateDirectory(outDir);
    var path = Path.Combine(outDir, plugin);
    mod.BeginWrite.ToPath(path).WithLoadOrder(sfKey, core.ModKey)
        .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full), new KeyedMasterStyle(core.ModKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {chunks.Count} quest(s) " +
                      $"{string.Join(", ", mod.Quests.Select(q => $"{q.EditorID} {q.FormKey}"))} script {ScriptName}, " +
                      $"{markers.Count} marker(s) overridden (own name shown, lifted {F(zLift)} m), {extras.Count} of its own (--extra), " +
                      (landing != null ? $"a landing spot (--landing {landing.Tag}), " : "") +
                      (starMap != null ? $"{starMap.Names.Count} name(s) on the star map (--star-map), " : "") +
                      (reload ? $"the reload's stop {HopCell} ({HopId:X6}, its marker {HopId + 1:X6} the first quest's HopMarker), " : "") +
                      $"world copy --world {world} ({WorldDescribed(world)}):");
    foreach (var w in mod.Worldspaces)
        Console.WriteLine($"  worldspace {w.FormKey} {w.EditorID}: flags {w.Flags?.ToString() ?? "-"}, HNAM [{string.Join(", ", w.HNAM?.ToArray() ?? Array.Empty<byte>())}]");
    foreach (var m in markers)
        Console.WriteLine($"  {m.FormKey} {m.EditorID} \"{m.MapMarker?.Name}\" local ({F(m.Position.X)}, {F(m.Position.Y)}, {F(m.Position.Z)}) -> z {F(lifted[m.FormKey].Z)}");
    for (int i = 0; i < extras.Count; i++)
    {
        var e = extras[i];
        var key = new FormKey(modKey, ExtraId + (uint)i);
        Console.WriteLine($"  {key} {e.Tag} \"{e.Name}\" local ({F(e.Pos.X)}, {F(e.Pos.Y)}, {F(e.Pos.Z)}) -> z {F(lifted[key].Z)} cell ({e.CellX}, {e.CellY})");
    }
    return 0;
}

if (args[0] == "check" && args.Length >= 3)
{
    var core = StarfieldMod.CreateFromBinaryOverlay(args[2], StarfieldRelease.Starfield, Params(sfKey));
    var mod = StarfieldMod.CreateFromBinaryOverlay(args[1], StarfieldRelease.Starfield, Params(sfKey, core.ModKey));
    var problems = new List<string>();
    var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
    Console.WriteLine($"{Path.GetFileName(args[1])}: header flags {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], " +
                      $"{mod.Quests.Count} QUST");
    if (!masters.Contains(core.ModKey.FileName.String))
        problems.Add($"{core.ModKey.FileName} is not a master");
    var want = CoreMarkers(core);
    // every core marker has an override here: its name shown, Visible kept, the position lifted by zLift
    var overrides = mod.EnumerateMajorRecords<IPlacedObjectGetter>().Where(r => r.FormKey.ModKey == core.ModKey)
        .ToDictionary(r => r.FormKey);
    var expect = new Dictionary<FormKey, P3Float>();
    foreach (var m in want)
    {
        var target = Lifted(m.Position, zLift);
        expect[m.FormKey] = target;
        if (!overrides.TryGetValue(m.FormKey, out var ov))
        {
            problems.Add($"{m.FormKey} {m.EditorID} has no override");
            continue;
        }
        var flags = ov.MapMarker?.Flags;
        Console.WriteLine($"  override {ov.FormKey} \"{ov.MapMarker?.Name}\" flags {(flags.HasValue ? ((int)flags.Value).ToString("X2") : "none")} " +
                          $"at ({F(ov.Position.X)}, {F(ov.Position.Y)}, {F(ov.Position.Z)})");
        if (ov.MapMarker == null || flags == null) problems.Add($"{m.FormKey} override has no map-marker data");
        else
        {
            if (flags.Value.HasFlag(PlacedObjectMapMarker.Flag.UseLocationName)) problems.Add($"{m.FormKey} override still uses the location's name");
            if (!flags.Value.HasFlag(PlacedObjectMapMarker.Flag.Visible)) problems.Add($"{m.FormKey} override is not Visible");
            if (ov.MapMarker.Name?.String != m.MapMarker?.Name?.String) problems.Add($"{m.FormKey} override name \"{ov.MapMarker.Name}\" != \"{m.MapMarker?.Name}\"");
            var starWant = StarMapWanted(m.MapMarker?.Flags ?? 0, m.MapMarker?.Name?.String, starMap);
            if (flags.Value.HasFlag(VisibleOnStarMap) != starWant)
                problems.Add($"{m.FormKey} override \"{ov.MapMarker.Name}\" is {(starWant ? "not " : "")}on the star map ({(starMap == null ? "the core" : "--star-map")} want{(starWant ? "s" : "s it off")})");
        }
        if (ov.Position != target) problems.Add($"{m.FormKey} override at z {F(ov.Position.Z)}, not the core's {F(m.Position.Z)} lifted {F(zLift)} m");
        if ((ov.MajorRecordFlagsRaw & 0x800) != 0) problems.Add($"{m.FormKey} override is Initially Disabled");
        if (ov.Base.FormKey != m.Base.FormKey) problems.Add($"{m.FormKey} override has another base");
    }
    foreach (var extra in overrides.Keys.Except(want.Select(m => m.FormKey)))
        problems.Add($"{extra} is overridden but is not a core map marker");
    // the plugin's own markers: exactly --extra's, in order from ExtraId, each as the overrides are, in the WRLD
    // copy's persistent cell, at its local spot lifted zLift
    // the reload's stop (--reload) holds two REFRs of this plugin's own in its interior, checked with the cell below
    var hopRefs = reload ? new HashSet<FormKey> { new FormKey(mod.ModKey, HopId + 1), new FormKey(mod.ModKey, HopId + 2) } : new HashSet<FormKey>();
    var own = mod.EnumerateMajorRecords<IPlacedObjectGetter>().Where(r => r.FormKey.ModKey == mod.ModKey && !hopRefs.Contains(r.FormKey))
        .ToDictionary(r => r.FormKey);
    var ownWorld = mod.Worldspaces.FirstOrDefault();
    var persistentKeys = ownWorld?.TopCell?.Persistent.Select(r => r.FormKey).ToHashSet() ?? new HashSet<FormKey>();
    var wantKeys = want.Select(m => m.FormKey).ToList();
    for (int i = 0; i < extras.Count; i++)
    {
        var e = extras[i];
        var key = new FormKey(mod.ModKey, ExtraId + (uint)i);
        var target = Lifted(e.Pos, zLift);
        expect[key] = target;
        wantKeys.Add(key);
        if (!own.TryGetValue(key, out var r))
        {
            problems.Add($"{key} ({e.Tag} \"{e.Name}\", --extra) is missing");
            continue;
        }
        var flags = r.MapMarker?.Flags;
        if (i < 3 || i == extras.Count - 1)
            Console.WriteLine($"  own {r.FormKey} {r.EditorID} \"{r.MapMarker?.Name}\" flags {(flags.HasValue ? ((int)flags.Value).ToString("X2") : "none")} " +
                              $"at ({F(r.Position.X)}, {F(r.Position.Y)}, {F(r.Position.Z)})");
        var edid = ownWorld == null ? null : ExtraEditorId(ownWorld, e);
        if (r.EditorID != edid) problems.Add($"{key} EditorID {r.EditorID} != {edid}");
        if (r.Base.FormKey != new FormKey(sfKey, MapMarkerStat)) problems.Add($"{key} base {r.Base.FormKey} is not MapMarker {MapMarkerStat:X8}");
        if (r.MapMarker == null || flags == null) problems.Add($"{key} has no map-marker data");
        else
        {
            if (flags.Value.HasFlag(PlacedObjectMapMarker.Flag.UseLocationName)) problems.Add($"{key} uses the location's name");
            if (!flags.Value.HasFlag(PlacedObjectMapMarker.Flag.Visible)) problems.Add($"{key} is not Visible");
            if (r.MapMarker.Name?.String != e.Name) problems.Add($"{key} name \"{r.MapMarker.Name}\" != \"{e.Name}\"");
            if (e.Type.HasValue && r.MapMarker.Type != e.Type.Value) problems.Add($"{key} type {r.MapMarker.Type} != --extra's {e.Type.Value}");
            var starWant = StarMapWanted(want.Count > 0 ? want[0].MapMarker?.Flags ?? 0 : 0, e.Name, starMap);
            if (flags.Value.HasFlag(VisibleOnStarMap) != starWant)
                problems.Add($"{key} \"{e.Name}\" is {(starWant ? "not " : "")}on the star map ({(starMap == null ? "the core" : "--star-map")} want{(starWant ? "s" : "s it off")})");
        }
        if (r.Position != target) problems.Add($"{key} at ({F(r.Position.X)}, {F(r.Position.Y)}, {F(r.Position.Z)}), not --extra's ({F(e.Pos.X)}, {F(e.Pos.Y)}, {F(e.Pos.Z)}) lifted {F(zLift)} m");
        if ((r.MajorRecordFlagsRaw & 0xC00) != 0x400) problems.Add($"{key} flags {r.MajorRecordFlagsRaw:X}: not persistent and enabled");
        if (!persistentKeys.Contains(key)) problems.Add($"{key} is not in the world's persistent cell");
    }
    // the landing spot: the four records --landing builds, exactly (a copy of the core's first marker among them, so a
    // core rebuilt since the stage shows here too), in the persistent cell, listed after --extra's in the quests
    if (landing != null)
    {
        if (ownWorld == null || want.Count == 0) problems.Add("--landing: the plugin has no world copy, or the core no marker to copy");
        else
            foreach (var exp in LandingRecords(want[0], mod.ModKey, ownWorld, landing))
            {
                expect[exp.FormKey] = exp.Position;
                wantKeys.Add(exp.FormKey);
                if (!own.TryGetValue(exp.FormKey, out var r))
                {
                    problems.Add($"{exp.FormKey} {exp.EditorID} (--landing) is missing");
                    continue;
                }
                Console.WriteLine($"  landing {r.FormKey} {r.EditorID} base {r.Base.FormKey} flags {r.MajorRecordFlagsRaw:X} " +
                                  $"at ({F(r.Position.X)}, {F(r.Position.Y)}, {F(r.Position.Z)}), {r.LinkedReferences.Count} link(s)");
                if (!exp.Equals(r.DeepCopy()))
                    problems.Add($"{r.FormKey} {r.EditorID} is not the record --landing builds (another --landing, or a core rebuilt since the stage: stage again)");
                if (!persistentKeys.Contains(exp.FormKey)) problems.Add($"{exp.FormKey} is not in the world's persistent cell");
            }
    }
    // the reload's stop: with --reload exactly the cell (and its two references) the build writes, without it no cell of
    // this plugin's own (the WRLD copy's persistent cell is the core's)
    var ownCells = mod.EnumerateMajorRecords<ICellGetter>().Where(c => c.FormKey.ModKey == mod.ModKey).ToList();
    if (!reload)
    {
        if (ownCells.Count > 0) problems.Add($"{ownCells.Count} cell(s) of this plugin's own without --reload: {string.Join(", ", ownCells.Select(c => $"{c.FormKey} {c.EditorID}"))}");
    }
    else if (ownCells.Count != 1 || ownCells[0].FormKey != new FormKey(mod.ModKey, HopId))
        problems.Add($"--reload: cells [{string.Join(", ", ownCells.Select(c => $"{c.FormKey} {c.EditorID}"))}], want only {new FormKey(mod.ModKey, HopId)} {HopCell}");
    else
    {
        var hop = ownCells[0];
        var hmask = new Cell.TranslationMask(defaultOn: true)
        {
            Timestamp = false, UnknownGroupData = false, PersistentTimestamp = false, PersistentUnknownGroupData = false,
            TemporaryTimestamp = false, TemporaryUnknownGroupData = false,
        };
        Console.WriteLine($"  reload stop {hop.FormKey} {hop.EditorID}: flags {hop.Flags}, {hop.Persistent.Count} persistent / {hop.Temporary.Count} temporary reference(s): " +
                          string.Join(", ", hop.Persistent.Concat(hop.Temporary).OfType<IPlacedObjectGetter>().Select(r => $"{r.FormKey} base {r.Base.FormKey} flags {r.MajorRecordFlagsRaw:X}")));
        if (!HopRecord(mod.ModKey).DeepCopy(hmask).Equals(hop.DeepCopy(hmask)))
            problems.Add($"{hop.FormKey} {hop.EditorID} is not the stop --reload builds");
    }
    foreach (var k in own.Keys.Where(k => !expect.ContainsKey(k)).OrderBy(k => k.ID))
        problems.Add($"{k} {own[k].EditorID} is a REFR of this plugin that --extra and --landing do not list");
    if (extras.Count > 0) Console.WriteLine($"  {own.Count} marker(s) of this plugin, {extras.Count} in --extra");
    // the Location override that carries their LCSR rows: the core's record plus one MapMarkerRefType row per own
    // marker, in order; nothing else differs (it loads after the core, as the WRLD copy)
    var coreLoc = MarkersLocation(core, want);
    var locs = mod.Locations.ToList();
    if (extras.Count == 0 && landing == null)
    {
        if (locs.Count > 0) problems.Add($"{locs.Count} Location record(s) without --extra or --landing");
    }
    else if (coreLoc == null) problems.Add("no core Location lists the core's markers in LCSR");
    else if (locs.Count != 1 || locs[0].FormKey != coreLoc.FormKey)
        problems.Add($"Location records [{string.Join(", ", locs.Select(l => l.FormKey))}]: want one override of {coreLoc.FormKey} {coreLoc.EditorID}");
    else
    {
        var lmask = new Location.TranslationMask(defaultOn: true) { MasterSpecialReferences = false };
        if (!coreLoc.DeepCopy(lmask).Equals(locs[0].DeepCopy(lmask)))
            problems.Add($"{coreLoc.FormKey} Location override differs from the core's beyond its LCSR rows (a core rebuilt since the stage: stage again)");
        var rows = (locs[0].MasterSpecialReferences ?? Enumerable.Empty<ILocationCellStaticReferenceGetter>()).Select(RowKey).ToList();
        var wantRows = (coreLoc.MasterSpecialReferences ?? Enumerable.Empty<ILocationCellStaticReferenceGetter>()).Select(RowKey)
            .Concat(extras.Select((e, i) => RowKey(Row(new FormKey(mod.ModKey, ExtraId + (uint)i), ownWorld?.FormKey ?? FormKey.Null, e))))
            .Concat(landing == null ? Enumerable.Empty<(FormKey, FormKey, FormKey, P2Int16, int)>()
                : LandingRows(mod.ModKey, ownWorld?.FormKey ?? FormKey.Null, landing).Select(RowKey)).ToList();
        Console.WriteLine($"  location {locs[0].FormKey} {locs[0].EditorID}: {rows.Count} LCSR row(s), {wantRows.Count} wanted");
        if (!rows.SequenceEqual(wantRows))
            problems.Add($"{coreLoc.FormKey} LCSR rows are not the core's followed by one MapMarkerRefType row per own marker and the landing spot's three");
    }
    // the containers the overrides need, the WRLD and its persistent CELL, are copies of the core's records, and a
    // plugin that loads after the core overrides them with whatever it holds: they must match the core this plugin
    // is checked against, or a core rebuilt since the stage (a changed world flag, say) is undone by this plugin
    foreach (var w in mod.Worldspaces)
    {
        var cw = core.Worldspaces.FirstOrDefault(x => x.FormKey == w.FormKey);
        if (cw == null) { problems.Add($"{w.FormKey} worldspace is not the core's"); continue; }
        var wmask = new Worldspace.TranslationMask(defaultOn: true)
        {
            TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
            SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
            SubCellsTimestamp = false, SubCellsUnknown = false,
        };
        var wantWorld = cw.DeepCopy(wmask);
        WorldVariant(wantWorld, world);                              // the core's record as the variant asked for
        var wantName = world == "control" ? "the core's" : $"the core's with --world {world}";
        var sameWorld = wantWorld.Equals(w.DeepCopy(wmask));
        Console.WriteLine($"  worldspace {w.FormKey} {w.EditorID}: flags {w.Flags?.ToString() ?? "-"}, HNAM [{string.Join(", ", w.HNAM?.ToArray() ?? Array.Empty<byte>())}]" +
                          (sameWorld ? $", as {wantName}" : $", NOT {wantName}"));
        if (!sameWorld)
            problems.Add(world == "control"
                ? $"{w.FormKey} worldspace record differs from the core's (a core rebuilt since the stage: stage again)"
                : $"{w.FormKey} worldspace record differs from the core's with --world {world} (a stage with another --world, or a core rebuilt since it: stage again)");
        if (w.SubCells.Count > 0) problems.Add($"{w.FormKey} worldspace carries {w.SubCells.Count} sub-cell block(s)");
        if (w.TopCell == null) continue;
        if (cw.TopCell == null) { problems.Add($"{w.FormKey} has a persistent cell the core lacks"); continue; }
        var cmask = new Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false, Temporary = false, NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
            Timestamp = false, UnknownGroupData = false, PersistentTimestamp = false, PersistentUnknownGroupData = false,
            TemporaryTimestamp = false, TemporaryUnknownGroupData = false,
        };
        if (!cw.TopCell.DeepCopy(cmask).Equals(w.TopCell.DeepCopy(cmask)))
            problems.Add($"{w.TopCell.FormKey} persistent cell record differs from the core's (a core rebuilt since the stage: stage again)");
        if (w.TopCell.Temporary.Count > 0) problems.Add($"{w.TopCell.FormKey} carries {w.TopCell.Temporary.Count} temporary reference(s)");
    }
    var chunks = QuestChunks(wantKeys, landing != null);
    var quests = mod.Quests.OrderBy(x => x.FormKey.ID).ToList();
    if (quests.Count != chunks.Count)
        problems.Add($"{quests.Count} quest(s) for {wantKeys.Count} marker(s): {chunks.Count} wanted ({PerQuest} per quest)");
    for (int k = 0; k < Math.Min(quests.Count, chunks.Count); k++)
    {
        var q = quests[k];
        var part = chunks[k];
        var tag = k == 0 ? "" : $"quest {k + 1}: ";
        if (q.FormKey.ID != QuestId + (uint)k || q.EditorID != QuestName(k))
        {
            problems.Add($"quest 0x{QuestId + (uint)k:X} {QuestName(k)} missing");
            continue;
        }
        if (q.Data == null || !q.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled)) problems.Add($"{tag}the quest is not StartGameEnabled");
        var s = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
        if (s == null)
        {
            problems.Add($"{tag}script {ScriptName} not attached");
            continue;
        }
        var objs = s.Properties.OfType<IScriptObjectListPropertyGetter>().FirstOrDefault(p => p.Name == "Markers")?
            .Objects.ToList() ?? new List<IScriptObjectPropertyGetter>();
        var got = objs.Select(o => o.Object.FormKey).ToList();
        // a direct reference: alias -1, unused 0 (the quest has no aliases; an alias-encoded entry is another binding)
        foreach (var (o, j) in objs.Select((o, j) => (o, j)))
            if (o.Alias != -1 || o.Unused != 0) problems.Add($"{tag}Markers[{j}] is not a direct reference (alias {o.Alias}, unused {o.Unused})");
        Console.WriteLine($"  {tag}Markers: {(got.Count > 12 ? string.Join(", ", got.Take(6)) + $", ... {got.Count - 6} more" : string.Join(", ", got))}");
        if (!got.SequenceEqual(part))
            problems.Add($"{tag}Markers [{string.Join(", ", got)}] are not the core's MapMarker REFRs and --extra's [{string.Join(", ", part)}]");
        foreach (var (name, pick) in new (string, Func<P3Float, float>)[] { ("LocalX", p => p.X), ("LocalY", p => p.Y), ("LocalZ", p => p.Z) })
        {
            var data = s.Properties.OfType<IScriptFloatListPropertyGetter>().FirstOrDefault(p => p.Name == name)?.Data.ToList();
            Console.WriteLine($"  {tag}{name}: {(data == null ? "missing" : data.Count > 12 ? string.Join(", ", data.Take(6).Select(F)) + $", ... {data.Count - 6} more" : string.Join(", ", data.Select(F)))}");
            if (data == null || !data.SequenceEqual(part.Select(m => pick(expect[m]))))
                problems.Add($"{tag}{name} does not hold the markers' overridden positions");
        }
        var cap = s.Properties.OfType<IScriptIntPropertyGetter>().FirstOrDefault(p => p.Name == "MaxMoves")?.Data;
        if (cap != MaxMovesFor(part.Length))
            problems.Add($"{tag}MaxMoves {(cap?.ToString() ?? "default")} != {(MaxMovesFor(part.Length)?.ToString() ?? "default")}");
        // the reload's stop: on the first quest with --reload, nowhere else
        var hops = s.Properties.Where(p => p.Name == "HopMarker").ToList();
        var wantHop = reload && k == 0;
        if (hops.Count > 0 || wantHop)
            Console.WriteLine($"  {tag}HopMarker: {(hops.Count == 0 ? "missing" : string.Join(", ", hops.OfType<IScriptObjectPropertyGetter>().Select(p => $"{p.Object.FormKey} alias {p.Alias}")))}");
        if (!wantHop && hops.Count > 0)
            problems.Add($"{tag}HopMarker set{(reload ? " (only the first quest does the reload)" : " without --reload")}");
        else if (wantHop && (hops.Count != 1 || hops[0] is not IScriptObjectPropertyGetter hp
                             || hp.Object.FormKey != new FormKey(mod.ModKey, HopId + 1) || hp.Alias != -1 || hp.Unused != 0))
            problems.Add($"{tag}HopMarker is not the stop's marker {new FormKey(mod.ModKey, HopId + 1)} (a direct reference)");
    }
    foreach (var p in problems) Console.WriteLine("FAIL  " + p);
    Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
    return problems.Count == 0 ? 0 : 1;
}
return Usage();

static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
static P3Float Lifted(P3Float p, float lift) => new P3Float(p.X, p.Y, p.Z + lift);
// the override: the same record, the marker's own name on the map, enabled, lifted; everything else as the core wrote it
static void Override(IPlacedObject ov, float lift)
{
    ov.Position = Lifted(ov.Position, lift);
    ov.MajorRecordFlagsRaw = (ov.MajorRecordFlagsRaw | 0x400) & ~0x800;
    if (ov.MapMarker == null) throw new InvalidDataException($"{ov.FormKey} has no map-marker data");
    ov.MapMarker.Flags = (ov.MapMarker.Flags | PlacedObjectMapMarker.Flag.Visible) & ~PlacedObjectMapMarker.Flag.UseLocationName;
}
// --star-map: the marker keeps Visible on Star Map when the list names it, and loses it otherwise; no list, the core's flags
static void OnStarMap(IPlacedObject r, StarMap? starMap)
{
    if (starMap == null || r.MapMarker == null) return;
    r.MapMarker.Flags = starMap.Names.Contains(r.MapMarker.Name?.String ?? "")
        ? r.MapMarker.Flags | VisibleOnStarMap : r.MapMarker.Flags & ~VisibleOnStarMap;
}
static bool StarMapWanted(PlacedObjectMapMarker.Flag coreFlags, string? name, StarMap? starMap) =>
    starMap == null ? coreFlags.HasFlag(VisibleOnStarMap) : starMap.Names.Contains(name ?? "");
// the WRLD copy as dotnet/BorderProbe writes the variant: nosmall and city drop SmallWorld, city sets HNAM 5; control leaves the core's
static void WorldVariant(IWorldspace w, string variant)
{
    if (variant is "nosmall" or "city") w.Flags = (w.Flags ?? 0) & ~Worldspace.Flag.SmallWorld;
    if (variant is "city") w.HNAM = new MemorySlice<byte>(new byte[] { 5 });
}
static string WorldDescribed(string variant) => variant switch
{
    "nosmall" => "SmallWorld cleared, HNAM as the core's",
    "city" => "SmallWorld cleared, HNAM 5",
    _ => "as the core's",
};
// the core's Location whose LCSR rows name the core's markers (the one TerrainOverlays fills); null when none
static ILocationGetter? MarkersLocation(IStarfieldModGetter core, List<IPlacedObjectGetter> markers)
{
    var keys = markers.Select(m => m.FormKey).ToHashSet();
    return core.Locations.Where(l => l.FormKey.ModKey == core.ModKey && (l.MasterSpecialReferences?.Any(r => keys.Contains(r.Marker.FormKey)) ?? false))
        .OrderBy(l => l.FormKey.ID).FirstOrDefault();
}
static string ExtraEditorId(IWorldspaceGetter w, Extra e) => w.EditorID + "MapMarker" + e.Tag;    // as TerrainOverlays names the core's
// one MapMarkerRefType row, as TerrainOverlays writes the core's (Mutagen writes Grid Y then X; Unknown -1 is vanilla 0xFFFFFFFF)
static LocationCellStaticReference Row(FormKey marker, FormKey world, Extra e) => RowOf(MapMarkerRefType, marker, world, e.CellX, e.CellY);
static LocationCellStaticReference RowOf(uint refType, FormKey marker, FormKey world, short cellX, short cellY) => new()
{
    LocationRefType = new FormLink<ILocationReferenceTypeGetter>(new FormKey(ModKey.FromFileName("Starfield.esm"), refType)),
    Marker = new FormLink<IPlacedObjectGetter>(marker),
    Location = new FormLink<IWorldspaceGetter>(world),
    Grid = new P2Int16(cellX, cellY),
    Unknown = -1,
};
// LandingOverlay01Location's three rows, in its order: the marker, then the pad twice
static LocationCellStaticReference[] LandingRows(ModKey mod, FormKey world, Landing l) => new[]
{
    RowOf(MapMarkerRefType, new FormKey(mod, LandingId + 2), world, l.Marker.CellX, l.Marker.CellY),
    RowOf(ShipLandingMarkerRefType, new FormKey(mod, LandingId), world, l.Pad.CellX, l.Pad.CellY),
    RowOf(ShipLandingMarkerRefTypeLarge, new FormKey(mod, LandingId), world, l.Pad.CellX, l.Pad.CellY),
};
// the landing spot's four REFRs (pad, trigger, marker, heading), as LandingOverlay01 has them, at --landing's spots;
// the marker is a copy of the core's first marker (as --extra's) with LandingOverlay01's map-marker data
static List<PlacedObject> LandingRecords(IPlacedObjectGetter template, ModKey mod, IWorldspaceGetter w, Landing l)
{
    var sf = ModKey.FromFileName("Starfield.esm");
    FormKey Id(int k) => new FormKey(mod, LandingId + (uint)k);
    LinkedReferences Link(uint keyword, FormKey to)
    {
        var link = new LinkedReferences();
        if (keyword != 0) link.KeywordOrReference.SetTo(new FormKey(sf, keyword));
        link.Reference.SetTo(to);
        return link;
    }
    PlacedObject Placed(int k, string part, uint baseId, LandingPiece p)
    {
        var r = new PlacedObject(Id(k), StarfieldRelease.Starfield)
        {
            EditorID = w.EditorID + part + l.Tag, Position = p.Pos, Rotation = p.Rot, MajorRecordFlagsRaw = 0x400,
        };
        r.Base.SetTo(new FormKey(sf, baseId));
        return r;
    }
    var pad = Placed(0, "LandingPad", LandingPad, l.Pad);
    pad.IsLinkedRefTransient = true;
    pad.LinkedReferences.Add(Link(LandingZoneTriggerKeyword, Id(1)));
    pad.LinkedReferences.Add(Link(LinkShipLandingOverlayMapMarker, Id(2)));
    var trigger = Placed(1, "LandingZone", LandingTrigger, l.Trigger);     // persistent here, so the quests move it
    trigger.Primitive = new PlacedPrimitive                                    // LandingOverlay01's 093DCA
    {
        Type = PlacedPrimitive.TypeEnum.Box, Bounds = new P3Float(81.6183f, 81.53047f, 29.697622f),
        Color = System.Drawing.Color.FromArgb(0, 204, 76, 51), Unknown = 0.3f,
    };
    var marker = (PlacedObject)template.Duplicate(Id(2));
    marker.EditorID = w.EditorID + "LandingMapMarker" + l.Tag;
    marker.Position = l.Marker.Pos;
    marker.Rotation = l.Marker.Rot;
    marker.MajorRecordFlagsRaw = (marker.MajorRecordFlagsRaw | 0x400) & ~0x800;
    marker.LinkedReferences.Clear();
    marker.LinkedReferences.Add(Link(0, Id(3)));
    marker.IsLinkedRefTransient = true;
    marker.Radius = LandingMarkerRadius;
    if (marker.MapMarker == null) throw new InvalidDataException($"{template.FormKey} has no map-marker data");
    marker.MapMarker.Flags = LandingMarkerFlags;
    marker.MapMarker.Type = LandingMarkerType;
    marker.MapMarker.Name = l.Name;
    var heading = Placed(3, "LandingHeading", XMarkerHeading, l.Heading);
    return new List<PlacedObject> { pad, trigger, marker, heading };
}
// --reload's stop: an interior lit as dotnet/PluginSpike's door test cell, its platform, and the persistent marker the
// first quest's HopMarker names (persistent, so the property resolves while the cell is not loaded)
static Cell HopRecord(ModKey mod)
{
    var sf = ModKey.FromFileName("Starfield.esm");
    var cell = new Cell(new FormKey(mod, HopId), StarfieldRelease.Starfield) { EditorID = HopCell, Flags = Cell.Flag.IsInteriorCell };
    cell.LightingTemplate.SetTo(new FormKey(sf, HopLighting));
    cell.ImageSpace.SetTo(new FormKey(sf, HopImageSpace));
    cell.EnvironmentMap = "Data\\Textures\\cubemaps\\blackcube.dds";
    // the door test cell's spots: the platform at (-2, 0, 0) (x -2..6, top z 0), the COC marker 1.5 m in, facing +Y
    var marker = new PlacedObject(new FormKey(mod, HopId + 1), StarfieldRelease.Starfield)
    {
        EditorID = HopCell + "Marker", Position = new P3Float(-1.5f, 0, 0.1f), Rotation = new P3Float(0, 0, (float)(Math.PI / 2)),
        MajorRecordFlagsRaw = 0x400,
    };
    marker.Base.SetTo(new FormKey(sf, CocMarkerHeading));
    var floor = new PlacedObject(new FormKey(mod, HopId + 2), StarfieldRelease.Starfield)
    {
        Position = new P3Float(-2, 0, 0), Rotation = new P3Float(0, 0, 0),
    };
    floor.Base.SetTo(new FormKey(sf, HopFloor));
    cell.Persistent.Add(marker);
    cell.Temporary.Add(floor);
    return cell;
}
static (FormKey, FormKey, FormKey, P2Int16, int) RowKey(ILocationCellStaticReferenceGetter r) =>
    (r.LocationRefType.FormKey, r.Marker.FormKey, r.Location.FormKey, r.Grid, r.Unknown);
// --extra's markers in file order; "" = none. Each entry needs a tag (letters, digits, _), a name, pos [x, y, z] (finite),
// cell [x, y]; tags do not repeat.
static List<Extra> LoadExtras(string path)
{
    var list = new List<Extra>();
    if (path == "") return list;
    using var doc = JsonDocument.Parse(File.ReadAllText(path));
    foreach (var m in doc.RootElement.GetProperty("markers").EnumerateArray())
    {
        var tag = m.GetProperty("tag").GetString() ?? "";
        var name = m.GetProperty("name").GetString() ?? "";
        var pos = m.GetProperty("pos").EnumerateArray().Select(v => v.GetSingle()).ToArray();
        var cell = m.GetProperty("cell").EnumerateArray().Select(v => v.GetInt16()).ToArray();
        if (tag == "" || !tag.All(c => char.IsAsciiLetterOrDigit(c) || c == '_')) throw new InvalidDataException($"tag \"{tag}\": want letters, digits or _");
        if (name == "") throw new InvalidDataException($"{tag}: no name");
        if (pos.Length != 3 || !pos.All(float.IsFinite)) throw new InvalidDataException($"{tag}: pos needs 3 finite numbers");
        if (cell.Length != 2) throw new InvalidDataException($"{tag}: cell needs 2 numbers");
        sbyte? type = null;
        if (m.TryGetProperty("type", out var tj) && tj.ValueKind != JsonValueKind.Null)
        {
            if (tj.ValueKind != JsonValueKind.Number || !tj.TryGetSByte(out var t) || t < 10 || t > 93)
                throw new InvalidDataException($"{tag}: type wants a whole number 10-93 (0-9 are Starfield's own places)");
            type = t;
        }
        list.Add(new Extra(tag, name, new P3Float(pos[0], pos[1], pos[2]), cell[0], cell[1], type));
    }
    var dup = list.GroupBy(e => e.Tag, StringComparer.OrdinalIgnoreCase).FirstOrDefault(g => g.Count() > 1);
    if (dup != null) throw new InvalidDataException($"tag {dup.Key} repeats");
    return list;
}
// --star-map's names; "" = none. names: non-empty strings that do not repeat; strict: true or false (default false).
static StarMap? LoadStarMap(string path)
{
    if (path == "") return null;
    using var doc = JsonDocument.Parse(File.ReadAllText(path));
    var names = doc.RootElement.GetProperty("names").EnumerateArray().Select(v => v.GetString() ?? "").ToList();
    if (names.Any(n => n == "")) throw new InvalidDataException("an empty name");
    var dup = names.GroupBy(n => n, StringComparer.Ordinal).FirstOrDefault(g => g.Count() > 1);
    if (dup != null) throw new InvalidDataException($"\"{dup.Key}\" repeats");
    var strict = doc.RootElement.TryGetProperty("strict", out var s) && s.GetBoolean();
    return new StarMap(new HashSet<string>(names, StringComparer.Ordinal), strict);
}
// --landing's spot; "" = none. A tag (letters, digits, _), a name, and pad, trigger, marker, heading each with pos [x, y, z]
// and rot [x, y, z] (finite) and cell [x, y].
static Landing? LoadLanding(string path)
{
    if (path == "") return null;
    using var doc = JsonDocument.Parse(File.ReadAllText(path));
    var l = doc.RootElement.GetProperty("landing");
    var tag = l.GetProperty("tag").GetString() ?? "";
    var name = l.GetProperty("name").GetString() ?? "";
    if (tag == "" || !tag.All(c => char.IsAsciiLetterOrDigit(c) || c == '_')) throw new InvalidDataException($"tag \"{tag}\": want letters, digits or _");
    if (name == "") throw new InvalidDataException($"{tag}: no name");
    LandingPiece Piece(string part)
    {
        if (!l.TryGetProperty(part, out var p)) throw new InvalidDataException($"{tag}: no {part}");
        var pos = p.GetProperty("pos").EnumerateArray().Select(v => v.GetSingle()).ToArray();
        var rot = p.GetProperty("rot").EnumerateArray().Select(v => v.GetSingle()).ToArray();
        var cell = p.GetProperty("cell").EnumerateArray().Select(v => v.GetInt16()).ToArray();
        if (pos.Length != 3 || !pos.All(float.IsFinite)) throw new InvalidDataException($"{part}: pos needs 3 finite numbers");
        if (rot.Length != 3 || !rot.All(float.IsFinite)) throw new InvalidDataException($"{part}: rot needs 3 finite numbers");
        if (cell.Length != 2) throw new InvalidDataException($"{part}: cell needs 2 numbers");
        return new LandingPiece(new P3Float(pos[0], pos[1], pos[2]), new P3Float(rot[0], rot[1], rot[2]), cell[0], cell[1]);
    }
    return new Landing(tag, name, Piece("pad"), Piece("trigger"), Piece("marker"), Piece("heading"));
}
static string QuestName(int k) => "FO4SF_MapMarkersQuest" + (k == 0 ? "" : (k + 1).ToString(CultureInfo.InvariantCulture));
// PerQuest markers per quest, but the landing spot's four pieces (the list's last four, --landing) stay in one quest:
// the script reads the pad fourth from its quest's end and the landing marker two places after it
// (FO4SF_MapMarkers.psc ShowLanding), so a last quest of one to three entries takes the rest of the pieces from the
// quest before it
static List<T[]> QuestChunks<T>(List<T> all, bool landing)
{
    var chunks = all.Chunk(PerQuest).ToList();
    int last = chunks.Count - 1;
    if (landing && last > 0 && chunks[last].Length < 4)
    {
        var prev = chunks[last - 1];
        int keep = prev.Length - (4 - chunks[last].Length);
        chunks[last] = prev.Skip(keep).Concat(chunks[last]).ToArray();
        chunks[last - 1] = prev.Take(keep).ToArray();
    }
    return chunks;
}
// the script's own default (40) holds up to 20 markers; above that, twice the quest's markers
static int? MaxMovesFor(int n) => 2 * n > DefaultMaxMoves ? 2 * n : null;

record Extra(string Tag, string Name, P3Float Pos, short CellX, short CellY, sbyte? Type);
record LandingPiece(P3Float Pos, P3Float Rot, short CellX, short CellY);
record Landing(string Tag, string Name, LandingPiece Pad, LandingPiece Trigger, LandingPiece Marker, LandingPiece Heading);
record StarMap(HashSet<string> Names, bool Strict);
