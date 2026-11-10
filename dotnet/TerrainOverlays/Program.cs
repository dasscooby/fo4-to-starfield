// Commonwealth terrain as one or more Starfield overlay worldspaces (docs/terrain/commonwealth-scale.md).
//   dotnet run -- <Starfield.esm> <staging dir>
// Reads <staging dir>/overlays_params.json (written by scripts/terrain/make_cw_overlays.py build) and writes
//   <plugin>        master Starfield.esm, own FormIDs from 0x800 (the anchors first, one per overlay, so plan.json can
//                   name them before the plugin exists), nothing shared with FO4Port.esm
//   <mars plugin>   when params hold "mars": override of MarsPlanetData that appends one PNDT CNAM entry per overlay
// Nothing is deployed.
//
// Per overlay (the records of experiment 2b, docs/terrain/overlay-records.md, once per tile):
//   SFBK <world>Block      copy of OverlayBlockLC172World (102382): ANAM = the tile's BTD, DNAM n x n, ENAM = shared
//                          height range, FNAM = one raw u16 per BTD cell (SW-corner sample), INAM/HNAM alignment
//   LCTN <world>Location   copy of LC172WorldLocation (3807BE): keyword LocTypeOverlay, parent SSol_PMars_Surface; one
//                          per overlay (the CK warns when two overlays share a location). Duplicate clears LCSR/LCID
//                          (LC172's map-marker chain); MapMarker REFRs (params "map_markers", else one at the COC)
//                          are restored after doors/lights (docs/terrain/map-markers.md).
//   WRLD <world>           copy of LC172World (02DF8C) minus cells/offsets/location; overlay component -> the SFBK;
//                          object bounds = the BTD; every exterior cell of the BTD (empty), the COC cell with a
//                          COCMarkerHeading 2 m above the ground, a persistent XMarker anchor in the persistent cell.
//                          Optional params "world_data": {"small_world": false, "hnam": 5} changes LC172World's DATA
//                          SmallWorld flag and its 1-byte HNAM (docs/terrain/border.md: NewAtlantis's values; whether
//                          they stop "BOUNDARY REACHED" is not yet proven, the repeat test there decides)
// PNDT CNAM entries store latitude first, then longitude (radians; Earth overlays sit at their real cities). Mutagen
// 0.55 names the first value Longitude and the second Latitude, so the params' latitude goes into .Longitude.
//
// Optional "objects": "objects.json" (core64c, docs/terrain/core64c.md, written by scripts/terrain/make_core64c.py stage):
// converted Fallout 4 models as STAT (or rigged DOOR) records and their references in one overlay's exterior cells,
// {"world": <overlay world EditorID>, "bases": [{"edid", "model", "door"?}], "refs": [{"src", "base", "cell", "pos",
// "rot", "scale", "disabled"}]} (metres, radians), as dotnet/TerrainExp2's objects mode. Their FormIDs come after every
// overlay record, so the terrain records, the anchors and the Mars plugin keep the FormIDs they have without objects;
// <staging dir>/formids.json lists the new ones. objects.json may also promote placed references to native records
// (make_core64c.py stage --cluster): "containers" (CONT), "items" (MISC), "activators" (ACTI), "terminals" (TERM,
// each with its own TMLM menu), "workshops" (ACTI build stations, docs/terrain/stations.md) and "flora" (FLOR harvest
// plants cloned from FloraMaizeCrop01, docs/terrain/flora.md), each entry in its source's original REFR slot
// (ReferenceIdentityPlan), the new CONT, MISC, ACTI, TERM + TMLM, then the workshops' ACTI and flora FLOR records
// after every reserved REFR; formids.json "containers", "items", "activators", "terminals", "workshops" and "flora" map
// each source to {"base", "ref"} (a terminal also to its "menu"). "benches" keep their slot on the VANILLA Starfield
// bench of their kind (no record of our own); formids.json "benches" maps each to {"base": "<6 hex>:Starfield.esm",
// "ref", "kind"}.
// objects.json may also hold "lights" and "light_bases" (exterior lights, docs/terrain/exterior-lights.md: written by
// make_core64c.py stage from make_cluster.py lights): FO4 Light references, which core64c never placed and which therefore
// own no reserved slot. Their REFRs take NEW FormIDs after every other record of the plugin (the reserved REFRs, the
// CONT, MISC, ACTI and TERM bases, the TMLM menus and the NAVMs), in "lights" order, then one LIGH per FO4 base (a copy of LGT_Interior_Omni_NS_Warm_004_2k,
// 12A74B:Starfield.esm, with the mapped fields), so a build with lights keeps every FormID of the build without them.
// objects.json may also hold "doors" (scripted load doors, docs/terrain/scripted-doors.md: written by make_core64c.py
// stage from make_cluster.py doors): FO4 exterior load doors whose destination lies in a converted interior. The door
// REFR keeps its slot (as every promoted class) and carries a VMAD attaching FO4SF_LoadDoor (scripts/door_bridge, PR
// #243) with the edited properties DestinationPlugin (string), DestinationId (int, the interior arrival marker's
// plugin-local id), DestinationX / DestinationY / DestinationZ (float, that marker's position: destination.arrival,
// interior coordinates) and UseDestinationPosition (bool, true: Codex's PR #291 applies the coordinates with
// SetPosition after the MoveTo only when it is true); its base is one ACTI per FO4
// door base (the converted door mesh, FULL the entry's name, PNAM / FNAM / JNAM as the activators'). Each door also
// places an exterior ARRIVAL marker (XMarker 00003B:Starfield.esm at the FO4 arrival point) where the interior door's
// MoveTo lands the player: PERSISTENT (0x400) in the world's persistent cell, beside the anchor, because a temporary
// reference of an unloaded cell does not resolve through Game.GetFormFromFile from inside (door_trip_sdm_1018) and
// vanilla keeps every persistent worldspace reference there (Starfield.esm 16,057 of 16,057, Fallout4.esm 33,571 of
// 33,571). The markers take NEW FormIDs after every other record of the plugin (the lights included), in "doors"
// order, then the door ACTIs in first-use order, so a build with doors keeps every FormID of the build without them;
// formids.json "doors" maps each source to {"base", "ref", "arrival"}.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;
using StarfieldActivator = Mutagen.Bethesda.Starfield.Activator;   // not System.Activator (implicit usings)

var sfPath = args[0];
var outDir = args[1];
var prm = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, "overlays_params.json"))).RootElement;
bool Has(JsonElement e, string k) => e.TryGetProperty(k, out var v) && v.ValueKind is not (JsonValueKind.Null or JsonValueKind.False);

var sfData = Path.GetDirectoryName(Path.GetFullPath(sfPath))!;
var release = StarfieldRelease.Starfield;
var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, release);

var templateWorld = sf.Worldspaces.First(w => w.FormKey.ID == 0x02DF8C);                                   // LC172World (Mars)
var templateBlock = sf.EnumerateMajorRecords<ISurfaceBlockGetter>().First(b => b.FormKey.ID == 0x102382);   // OverlayBlockLC172World
var templateLoc = sf.Locations.First(l => l.FormKey.ID == 0x3807BE);                                        // LC172WorldLocation

var modKey = ModKey.FromNameAndExtension(prm.GetProperty("plugin").GetString()!);
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
var overlays = prm.GetProperty("overlays").EnumerateArray().ToList();

// anchors take the first FormIDs, in params order (plan.json names them as 0x800 + index)
uint next = 0x800;
foreach (var o in overlays)
{
    uint want = o.GetProperty("anchor").GetProperty("form_id").GetUInt32();
    if (want != next) throw new InvalidDataException($"anchor form_id 0x{want:X} out of order (expected 0x{next:X})");
    next++;
}
FormKey NewKey() => new(modKey, next++);

float hmin = prm.GetProperty("hmin").GetSingle(), hmax = prm.GetProperty("hmax").GetSingle();
bool absolute = prm.GetProperty("alignment").GetString() == "absolute";
short hnam = prm.GetProperty("hnam").GetInt16();
var worlds = new List<(Worldspace World, JsonElement Params)>();
var cellsOf = new Dictionary<string, Dictionary<(int, int), Cell>>();
int idx = 0;
foreach (var o in overlays)
{
    string world = o.GetProperty("world").GetString()!;
    int n = o.GetProperty("n").GetInt32(), cmin = o.GetProperty("cell_min").GetInt32(), cmax = o.GetProperty("cell_max").GetInt32();

    var block = (SurfaceBlock)templateBlock.Duplicate(NewKey());
    block.EditorID = o.GetProperty("block").GetString();
    block.ANAM = o.GetProperty("btd_path").GetString();
    block.DNAM = new SurfaceBlockIntItem { First = (uint)n, Second = (uint)n };
    // ENAM holds two floats; Mutagen 0.55 types them as uint, so pass the IEEE bits
    block.ENAM = new SurfaceBlockFloatItem { First = BitConverter.SingleToUInt32Bits(hmin), Second = BitConverter.SingleToUInt32Bits(hmax) };
    var fnam = o.GetProperty("fnam").EnumerateArray().Select(e => (ushort)e.GetInt32()).ToArray();
    if (fnam.Length != n * n) throw new InvalidDataException($"{world}: fnam has {fnam.Length} values, DNAM needs {n * n}");
    block.FNAM = fnam.SelectMany(v => new[] { (byte)(v & 0xFF), (byte)(v >> 8) }).ToArray();
    block.INAM = (byte)(absolute ? 1 : 0);
    block.HNAM = unchecked((ushort)hnam);
    block.Components.Clear();                                                // drop BlockEditorMetaData (CK bookkeeping)
    mod.SurfaceBlocks.Add(block);

    var loc = (Location)templateLoc.Duplicate(NewKey());
    loc.EditorID = o.GetProperty("location").GetString();
    loc.Name = $"Commonwealth {o.GetProperty("tag").GetString()} (FO4 terrain)";
    loc.MasterSpecialReferences?.Clear();
    loc.MasterInitiallyDisabledReferences?.Clear();
    loc.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(new FormKey(sfEsm, 0x2CA99D)) };
    loc.ParentLocation.SetTo(new FormKey(sfEsm, 0x01B736));                  // SSol_PMars_Surface
    mod.Locations.Add(loc);

    var w = (Worldspace)templateWorld.Duplicate(NewKey());
    w.EditorID = world;
    w.Name = $"Commonwealth {o.GetProperty("tag").GetString()} (FO4 terrain)";
    w.SubCells.Clear();
    w.TopCell = null;
    w.OffsetData = null;
    w.CellSizeData = null;
    if (prm.TryGetProperty("world_data", out var wd) && wd.ValueKind == JsonValueKind.Object)
    {
        if (wd.TryGetProperty("small_world", out var sw) && sw.ValueKind == JsonValueKind.False)
            w.Flags = (w.Flags ?? 0) & ~Worldspace.Flag.SmallWorld;
        if (wd.TryGetProperty("hnam", out var wh))
            w.HNAM = new MemorySlice<byte>(new byte[] { checked((byte)wh.GetInt32()) });
    }
    w.Location.SetTo(loc.FormKey);
    w.Components.OfType<WorldSpaceOverlayComponent>().First().SurfaceBlock.SetTo(block.FormKey);
    // object bounds are raw metres; Mutagen shows them divided by 4096
    float bmin = o.GetProperty("bounds_min_m").GetSingle() / 4096f, bmax = o.GetProperty("bounds_max_m").GetSingle() / 4096f;
    w.ObjectBoundsMin = new P2Float(bmin, bmin);
    w.ObjectBoundsMax = new P2Float(bmax, bmax);

    var spawn = o.GetProperty("spawn").EnumerateArray().Select(e => e.GetSingle()).ToArray();
    var spawnCell = o.GetProperty("spawn_cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
    string coc = o.GetProperty("coc").GetString()!;
    var blocks = new Dictionary<(int, int), WorldspaceBlock>();
    var subs = new Dictionary<(int, int), WorldspaceSubBlock>();
    var cellAt = cellsOf[world] = new Dictionary<(int, int), Cell>();
    for (int x = cmin; x <= cmax; x++)
        for (int y = cmin; y <= cmax; y++)
        {
            var c = new Cell(NewKey(), release) { Grid = new CellGrid { Point = new P2Int(x, y) } };
            cellAt[(x, y)] = c;
            if (x == spawnCell[0] && y == spawnCell[1])
            {
                c.EditorID = coc;
                c.Temporary.Add(new PlacedObject(NewKey(), release)
                {
                    EditorID = coc + "Marker",
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x000032)),   // COCMarkerHeading
                    Position = new P3Float(spawn[0], spawn[1], spawn[2]),
                    Rotation = new P3Float(0, 0, 0),
                });
            }
            int bx = (int)Math.Floor(x / 32.0), by = (int)Math.Floor(y / 32.0), sx = (int)Math.Floor(x / 8.0), sy = (int)Math.Floor(y / 8.0);
            if (!blocks.TryGetValue((bx, by), out var blk)) { blk = new WorldspaceBlock { BlockNumberX = (short)bx, BlockNumberY = (short)by, GroupType = GroupTypeEnum.ExteriorCellBlock }; blocks[(bx, by)] = blk; w.SubCells.Add(blk); }
            if (!subs.TryGetValue((sx, sy), out var sub)) { sub = new WorldspaceSubBlock { BlockNumberX = (short)sx, BlockNumberY = (short)sy, GroupType = GroupTypeEnum.ExteriorCellSubBlock }; subs[(sx, sy)] = sub; blk.Items.Add(sub); }
            sub.Items.Add(c);
        }
    w.TopCell = new Cell(NewKey(), release) { Flags = Cell.Flag.HasWater };   // persistent top cell (as experiments 1 and 2)
    var a = o.GetProperty("anchor");
    var p = a.GetProperty("local").EnumerateArray().Select(e => e.GetSingle()).ToArray();
    var anchor = new PlacedObject(new FormKey(modKey, a.GetProperty("form_id").GetUInt32()), release)
    {
        EditorID = a.GetProperty("edid").GetString(),
        Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x00003B)),            // XMarker
        Position = new P3Float(p[0], p[1], p[2]),
        Rotation = new P3Float(0, 0, 0),
    };
    anchor.MajorRecordFlagsRaw |= 0x400;                                     // Persistent
    w.TopCell.Persistent.Add(anchor);
    mod.Worldspaces.Add(w);
    worlds.Add((w, o));
    Console.WriteLine($"  {world}: WRLD {w.FormKey}, SFBK {block.FormKey} -> {block.ANAM}, LCTN {loc.FormKey}, anchor {anchor.FormKey} at ({p[0]}, {p[1]}, {p[2]}), " +
                      $"{(cmax - cmin + 1) * (cmax - cmin + 1)} cells {cmin}..{cmax}, COC {coc} in ({spawnCell[0]}, {spawnCell[1]})");
    idx++;
}
int nStat = 0, nMstt = 0, nDoor = 0, nOpenDoor = 0, nRef = 0, nDisabled = 0, nNav = 0, nNavTri = 0, nNavLink = 0, nNavDoor = 0, nCont = 0, nMisc = 0,
    nActi = 0, nTerm = 0, nWkshp = 0, nFlor = 0, nBench = 0;
var refIds = new Dictionary<string, string>();                 // placed reference source -> this plugin's id (6 hex)
Dictionary<string, object>? ids = null;                        // formids.json
Dictionary<(int, int), Cell>? objCells = null;                 // the objects' overlay cells
string? objWorld = null;
string[] lightSources = Array.Empty<string>();                 // exterior lights: written after everything else
JsonElement? lightsJson = null, lightBasesJson = null;
// scripted load doors: the REFRs are placed with the objects (reserved slots); their ACTI bases and arrival markers
// are allocated after the lights
var doorEntries = new List<(string Src, PlacedObject Obj, string Edid, string Model, string Name, int[] ArrivalCell, float[] ArrivalPos, float[] ArrivalRot, JsonElement? Anim)>();
var doorIds = new Dictionary<string, object>();
var doorRefIds = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);   // door source -> its REFR id: a navmesh door triangle may name it
if (Has(prm, "objects"))
{
    // core64c: converted FO4 models and their references, allocated after every overlay record
    using var odoc = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, prm.GetProperty("objects").GetString()!)));
    var o = odoc.RootElement;
    var referenceSources = ReferenceIdentityPlan.Order(o);
    lightSources = ReferenceIdentityPlan.Lights(o, referenceSources);           // refused before anything is written
    if (lightSources.Length > 0)
    {
        lightsJson = o.GetProperty("lights").Clone();
        lightBasesJson = o.GetProperty("light_bases").Clone();
    }
    string world = o.TryGetProperty("world", out var wj) ? wj.GetString()! : worlds[0].World.EditorID!;
    if (!cellsOf.TryGetValue(world, out var cellAt)) throw new InvalidDataException($"objects.json names world {world}, not an overlay of these params");
    objCells = cellAt; objWorld = world;
    var baseKeys = new List<FormKey>();
    var baseIds = new Dictionary<string, string>();
    var doorBases = new HashSet<int>();                                     // base indices written as rigged DOOR
    foreach (var b in o.GetProperty("bases").EnumerateArray())
    {
        var edid = b.GetProperty("edid").GetString()!;
        var model = b.GetProperty("model").GetString()!;
        if (b.TryGetProperty("door", out var d) && d.ValueKind == JsonValueKind.Object)
        {
            // hinged door rigged like the vanilla template door (as PluginSpike and TerrainExp2): graph, skeleton, bounds
            var rec = new Door(NewKey(), release)
            {
                EditorID = edid, Model = new Model { File = model }, Name = "Door",
                SoundLevel = SoundLevel.Normal, FacingAxisOverride = Door.FacingAxisOverrideEnum.BasedOnBounds,
            };
            if (d.TryGetProperty("bounds", out var bj))
                rec.ObjectBounds = new ObjectBounds
                {
                    First = new P3Float(bj[0][0].GetSingle(), bj[0][1].GetSingle(), bj[0][2].GetSingle()),
                    Second = new P3Float(bj[1][0].GetSingle(), bj[1][1].GetSingle(), bj[1][2].GetSingle()),
                };
            rec.Components.Add(new AnimationGraphComponent
            {
                ANAM = d.GetProperty("anim_graph").GetString(), BNAM = d.GetProperty("skeleton").GetString(),
                CNAM = d.GetProperty("animations").GetString(),
            });
            mod.Doors.Add(rec);
            doorBases.Add(baseKeys.Count);
            baseKeys.Add(rec.FormKey);
            nDoor++;
        }
        else
        {
            if (b.TryGetProperty("movable", out _))
            {
                // FAL-171: a loose item converted with a dynamic body (manifest "movable") is a MoveableStatic outdoors as in
                // PluginSpike (DATA 4); a Static never simulates, so it could not be carried
                var ms = new MoveableStatic(NewKey(), release) { EditorID = edid, Model = new Model { File = model }, DATA = 4 };
                mod.MoveableStatics.Add(ms);
                baseKeys.Add(ms.FormKey);
                nMstt++;
            }
            else
            {
                var stat = new Static(NewKey(), release) { EditorID = edid, Model = new Model { File = model } };
                mod.Statics.Add(stat);
                baseKeys.Add(stat.FormKey);
                nStat++;
            }
        }
        baseIds[edid] = baseKeys[^1].ID.ToString("X6");
    }
    // Reserve every original slot, including references promoted out of "refs".
    // A later neighbour must not inherit the promoted source's saved-game ID.
    var referenceKeys = referenceSources.ToDictionary(src => src, _ => NewKey(), StringComparer.OrdinalIgnoreCase);
    foreach (var r in o.GetProperty("refs").EnumerateArray())
    {
        float[] V(string k) => r.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
        var cxy = r.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
        if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"reference {r.GetProperty("src").GetString()} in cell ({cxy[0]}, {cxy[1]}) outside {world}'s cells");
        var pos = V("pos");
        var rot = V("rot");
        var obj = new PlacedObject(referenceKeys[r.GetProperty("src").GetString()!], release)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(baseKeys[r.GetProperty("base").GetInt32()]),
            Position = new P3Float(pos[0], pos[1], pos[2]),
            Rotation = new P3Float(rot[0], rot[1], rot[2]),
        };
        var scale = r.GetProperty("scale").GetSingle();
        if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
        if (r.GetProperty("disabled").GetBoolean())
        {
            obj.MajorRecordFlagsRaw |= 0x800;                                // Initially Disabled, as in FO4
            nDisabled++;
        }
        // FO4's "open by default" on a rigged door (exterior.place): a doorway FO4 shows open starts open, as PluginSpike
        // writes it on the interiors (Red Rocket 056332 and 056333)
        if (r.TryGetProperty("open_by_default", out var obd) && obd.ValueKind == JsonValueKind.True
            && doorBases.Contains(r.GetProperty("base").GetInt32()))
        {
            obj.OpenByDefault = true;
            nOpenDoor++;
        }
        cell.Temporary.Add(obj);
        refIds[r.GetProperty("src").GetString()!] = obj.FormKey.ID.ToString("X6");
        nRef++;
    }
    // R05 (docs/slice/r05-cluster-plan.md): "containers", interactive objects of the cluster, each a native CONT base
    // with the converted model and a vanilla inventory, and one temporary REFR in its original identity slot.
    // Only the new CONT bases are allocated after every STAT / DOOR and every reserved REFR above.
    // ({"src", "edid", "model", "name", "items": [{"form": "Starfield.esm:00000F", "count": 25}], "cell", "pos",
    // "rot", "scale", "reference_index"}; the source leaves "refs", but its original index is retained).
    var contIds = new Dictionary<string, object>();
    var contByEdid = new Dictionary<string, Container>(StringComparer.OrdinalIgnoreCase);   // one CONT per FO4 base: entries of one base share an edid
    var contSig = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);        // its model, name and inventory: every entry must agree
    static string ContainerSignature(JsonElement c)
    {
        var items = c.GetProperty("items").EnumerateArray()
            .Select(it => $"{it.GetProperty("form").GetString()!.ToLowerInvariant()}x{it.GetProperty("count").GetInt32()}")
            .OrderBy(x => x, StringComparer.Ordinal);
        return $"{c.GetProperty("model").GetString()!.ToLowerInvariant()}|{c.GetProperty("name").GetString()}|{string.Join(",", items)}";
    }
    if (o.TryGetProperty("containers", out var conts))
    {
        foreach (var c in conts.EnumerateArray())
        {
            float[] V(string k) => c.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
            var cxy = c.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
            if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
                throw new InvalidDataException($"container {c.GetProperty("src").GetString()} in cell ({cxy[0]}, {cxy[1]}) outside {world}'s cells");
            var edid = c.GetProperty("edid").GetString()!;
            var cmodel = c.GetProperty("model").GetString()!;
            if (!contByEdid.TryGetValue(edid, out var cont))
            {
                cont = new Container(NewKey(), release)
                {
                    EditorID = edid, Model = new Model { File = cmodel },
                    Name = c.GetProperty("name").GetString(),
                    Items = new ExtendedList<ContainerEntry>(),                    // null by default in Mutagen 0.55
                };
                foreach (var it in c.GetProperty("items").EnumerateArray())
                {
                    var form = it.GetProperty("form").GetString()!;                 // "<plugin>:<6 hex>"
                    var colon = form.IndexOf(':');
                    var fk = new FormKey(ModKey.FromNameAndExtension(form[..colon]), Convert.ToUInt32(form[(colon + 1)..], 16));
                    cont.Items.Add(new ContainerEntry
                    {
                        Item = new ContainerItem { Item = new FormLink<IItemGetter>(fk), Count = it.GetProperty("count").GetInt32() },
                    });
                }
                mod.Containers.Add(cont);
                contByEdid[edid] = cont;
                contSig[edid] = ContainerSignature(c);
            }
            else if (contSig[edid] != ContainerSignature(c))
                // a shared record carries one model, name and inventory; a different one under the same edid would be
                // silently lost (Codex's review of #167): the build stops instead
                throw new InvalidDataException($"container {edid}: {c.GetProperty("src").GetString()} asks for {ContainerSignature(c)} but the shared record is {contSig[edid]}");
            var pos = V("pos");
            var rot = V("rot");
            var obj = new PlacedObject(referenceKeys[c.GetProperty("src").GetString()!], release)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(cont.FormKey),
                Position = new P3Float(pos[0], pos[1], pos[2]),
                Rotation = new P3Float(rot[0], rot[1], rot[2]),
            };
            var scale = c.GetProperty("scale").GetSingle();
            if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
            cell.Temporary.Add(obj);
            nRef++;
            contIds[c.GetProperty("src").GetString()!] = new Dictionary<string, string>
            {
                ["base"] = cont.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6"),
            };
            if (contByEdid.Count <= 8 || nRef % 500 == 0)
                Console.WriteLine($"  container {cont.EditorID} {cont.FormKey} ({cont.Items.Count} items) -> REFR {obj.FormKey} in cell ({cxy[0]}, {cxy[1]})");
        }
    }
    // Loose items (docs/terrain/commonwealth-build-plan.md section 3): "items", FO4 MiscItem / Ingestible references
    // promoted exactly as containers: one native MISC base per edid (one per FO4 base; every entry of an edid must
    // agree on model, name, value and weight) and one temporary REFR in the source's original identity slot (reserved
    // above together with the containers'). The new MISC bases are allocated after every reserved REFR and CONT base.
    // ({"src", "edid", "model", "name", "value", "weight", "cell", "pos", "rot", "scale", "reference_index"}; Mutagen
    // 0.55.0-alpha.67 MiscItem: Model, Name, Value (int), Weight (float), read off the package by reflection.)
    var itemIds = new Dictionary<string, object>();
    var miscByEdid = new Dictionary<string, MiscItem>(StringComparer.OrdinalIgnoreCase);
    var miscSig = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    static string ItemSignature(JsonElement c) =>
        $"{c.GetProperty("model").GetString()!.ToLowerInvariant()}|{c.GetProperty("name").GetString()}|" +
        $"{c.GetProperty("value").GetInt32()}|{BitConverter.SingleToUInt32Bits(c.GetProperty("weight").GetSingle()):X8}";
    if (o.TryGetProperty("items", out var itemsJ))
    {
        foreach (var c in itemsJ.EnumerateArray())
        {
            float[] V(string k) => c.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
            var src = c.GetProperty("src").GetString()!;
            var cxy = c.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
            if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
                throw new InvalidDataException($"item {src} in cell ({cxy[0]}, {cxy[1]}) outside {world}'s cells");
            var edid = c.GetProperty("edid").GetString()!;
            if (!miscByEdid.TryGetValue(edid, out var misc))
            {
                var name = c.GetProperty("name").GetString();
                int value = c.GetProperty("value").GetInt32();
                float weight = c.GetProperty("weight").GetSingle();
                if (string.IsNullOrWhiteSpace(name) || value < 0 || !float.IsFinite(weight) || weight < 0)
                    throw new InvalidDataException($"item {src}: needs a name, a value >= 0 and a weight >= 0");
                misc = new MiscItem(NewKey(), release)
                {
                    EditorID = edid, Model = new Model { File = c.GetProperty("model").GetString()! },
                    Name = name, Value = value, Weight = weight,
                };
                mod.MiscItems.Add(misc);
                miscByEdid[edid] = misc;
                miscSig[edid] = ItemSignature(c);
            }
            else if (miscSig[edid] != ItemSignature(c))
                // one shared record carries one model, name, value and weight (as containers, Codex's review of #167)
                throw new InvalidDataException($"item {edid}: {src} asks for {ItemSignature(c)} but the shared record is {miscSig[edid]}");
            var pos = V("pos");
            var rot = V("rot");
            var obj = new PlacedObject(referenceKeys[src], release)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(misc.FormKey),
                Position = new P3Float(pos[0], pos[1], pos[2]),
                Rotation = new P3Float(rot[0], rot[1], rot[2]),
            };
            var scale = c.GetProperty("scale").GetSingle();
            if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
            cell.Temporary.Add(obj);
            nRef++;
            itemIds[src] = new Dictionary<string, string>
            {
                ["base"] = misc.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6"),
            };
            if (itemIds.Count <= 8 || itemIds.Count % 500 == 0)
                Console.WriteLine($"  item {misc.EditorID} {misc.FormKey} ('{misc.Name}', value {misc.Value}, weight {misc.Weight}) -> REFR {obj.FormKey} in cell ({cxy[0]}, {cxy[1]})");
        }
    }
    // Activators and terminals (docs/terrain/commonwealth-build-plan.md section 3), promoted exactly as containers and
    // items: one temporary REFR in the source's original identity slot (reserved above with the others) on one shared
    // native base per edid, every entry of an edid agreeing on what that base carries.
    //   "activators": FO4 Activator -> ACTI with the converted model and the name ({"src", "edid", "model", "name" (null:
    //                 no FULL, as an FO4 activator without one), "cell", "pos", "rot", "scale", "reference_index"})
    //   "terminals":  FO4 Terminal -> TERM with the converted model and the name, DNAM = its own TMLM menu (allocated
    //                 right after it): the name and one body text, the entry's "body" (one line), no menu item
    //                 ({"src", "edid", "menu_edid", "model", "name", "body", "cell", ...})
    // New ACTI bases follow every MISC, then each TERM with its TMLM. Mutagen 0.55.0-alpha.67, read off the package by
    // reflection: Activator Name / Model; Terminal Name / Model / Menu / Background; TerminalMenu Name / ShowBodyText /
    // MenuButtonStyle / Style / INAM / BodyTexts (TerminalMenuBodyText Text / UseTemplatedText) / MenuItems. The TMLM
    // mirrors vanilla RI04_NyxProgram_Menu_Camden (0788A8:Starfield.esm: TMVT 1 = Document, DNAM 0, SNAM 0 = Windows,
    // one BTXT, TPLT 0, no item); the TERM's NAM1 = Default (2) as the vanilla terminals.
    PlacedObject PlacePromoted(JsonElement c, FormKey baseKey, string what)
    {
        var src = c.GetProperty("src").GetString()!;
        var cxy = c.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
        if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"{what} {src} in cell ({cxy[0]}, {cxy[1]}) outside {world}'s cells");
        float[] V(string k) => c.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
        var pos = V("pos");
        var rot = V("rot");
        var obj = new PlacedObject(referenceKeys[src], release)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(baseKey),
            Position = new P3Float(pos[0], pos[1], pos[2]),
            Rotation = new P3Float(rot[0], rot[1], rot[2]),
        };
        var scale = c.GetProperty("scale").GetSingle();
        if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
        cell.Temporary.Add(obj);
        nRef++;
        return obj;
    }
    static string? OneLine(JsonElement c, string k, bool optional)
    {
        var v = c.GetProperty(k);
        if (optional && v.ValueKind == JsonValueKind.Null) return null;
        var t = v.GetString();
        if (string.IsNullOrWhiteSpace(t) || t.Contains('\n') || t.Contains('\r'))
            throw new InvalidDataException($"{c.GetProperty("src").GetString()}: {k} {v} is not one non-empty line");
        return t;
    }
    var actiIds = new Dictionary<string, object>();
    var actiBySrc = new Dictionary<string, PlacedObject>(StringComparer.OrdinalIgnoreCase);
    var actiByEdid = new Dictionary<string, StarfieldActivator>(StringComparer.OrdinalIgnoreCase);
    var actiSig = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    if (o.TryGetProperty("activators", out var actisJ))
    {
        foreach (var c in actisJ.EnumerateArray())
        {
            var src = c.GetProperty("src").GetString()!;
            var edid = c.GetProperty("edid").GetString()!;
            var model = c.GetProperty("model").GetString()!;
            var name = OneLine(c, "name", optional: true);
            var sig = $"{model.ToLowerInvariant()}|{(name == null ? "<none>" : "=" + name)}";
            if (!actiByEdid.TryGetValue(edid, out var acti))
            {
                // PNAM / FNAM / JNAM as the vanilla majority (Starfield.esm, 1,463 ACTI read raw in the review of #241):
                // marker colour bytes CC 4C 33 00 in 1,347 (Mutagen writes the alpha last), flags 0 in 1,412,
                // activation angle 360 in 1,453
                acti = new StarfieldActivator(NewKey(), release)
                {
                    EditorID = edid, Model = new Model { File = model }, MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
                    Flags = (StarfieldActivator.Flag)0, ActivationAngle = 360,
                };
                if (name != null) acti.Name = name;
                mod.Activators.Add(acti);
                actiByEdid[edid] = acti;
                actiSig[edid] = sig;
            }
            else if (actiSig[edid] != sig)
                throw new InvalidDataException($"activator {edid}: {src} asks for {sig} but the shared record is {actiSig[edid]}");
            var obj = PlacePromoted(c, acti.FormKey, "activator");
            actiBySrc[src] = obj;
            actiIds[src] = new Dictionary<string, string> { ["base"] = acti.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6") };
            if (actiIds.Count <= 8 || actiIds.Count % 500 == 0)
                Console.WriteLine($"  activator {acti.EditorID} {acti.FormKey} ('{acti.Name?.String}') -> REFR {obj.FormKey}");
        }
    }
    var termIds = new Dictionary<string, object>();
    var termByEdid = new Dictionary<string, (Terminal Term, TerminalMenu Menu)>(StringComparer.OrdinalIgnoreCase);
    var termSig = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    var menuEdids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    // Every vanilla TERM is also furniture: the review of #241 read Starfield.esm's 368 raw (MNAM, WBDT, XMRK, PNAM /
    // FNAM / JNAM / GNAM and keywords in all, an animation graph and SNAM in 367, FTMP in 365); a TERM without them has no
    // vanilla precedent. Each new TERM therefore carries the furniture block of one vanilla standing terminal, as the
    // doors carry a vanilla rig: OE_AustinF_DeployMicrobe_Terminal (0155A2:Starfield.esm: FTMP 0FFAD2, XMRK
    // furn_human_standingterminal.nif, one SNAM marker, MNAM 40000001 = HasModel + InteractionPoint0, WBDT 00, PNAM /
    // FNAM / JNAM / GNAM, 5 keywords and the HybridStateGraph01 animation graph; that marker model, keyword set and
    // FTMP are the vanilla majority, 184 / 184 / 182 of 368). Its EDID, bounds, model, name, menu and VMAD
    // (TerminalScript) are not copied. Whether the player enters terminal mode stays unresolved until the activate step.
    ITerminalGetter? termTemplate = null;
    static MemorySlice<byte>? Bytes(ReadOnlyMemorySlice<byte>? s) => s is { } v ? new MemorySlice<byte>(v.ToArray()) : default(MemorySlice<byte>?);
    void Furnish(Terminal term, ITerminalGetter t)
    {
        term.FurnitureTemplate.SetTo(t.FurnitureTemplate.FormKeyNullable);
        term.MarkerModel = t.MarkerModel;
        term.MarkerParameters = t.MarkerParameters?.Select(p => p.DeepCopy()).ToExtendedList();
        term.MarkerFlags = t.MarkerFlags;
        term.WorkbenchData = Bytes(t.WorkbenchData);
        term.PNAM = Bytes(t.PNAM); term.FNAM = Bytes(t.FNAM); term.JNAM = Bytes(t.JNAM); term.GNAM = Bytes(t.GNAM);
        term.Keywords = t.Keywords?.Select(k => (IFormLinkGetter<IKeywordGetter>)new FormLink<IKeywordGetter>(k.FormKey)).ToExtendedList();
        foreach (var g in t.Components.OfType<IAnimationGraphComponentGetter>()) term.Components.Add(g.DeepCopy());
    }
    if (o.TryGetProperty("terminals", out var termsJ))
    {
        if (termsJ.GetArrayLength() > 0)
            termTemplate = sf.Terminals.FirstOrDefault(t => t.FormKey == new FormKey(sfEsm, 0x0155A2))
                ?? throw new InvalidDataException("terminals: the template terminal 0155A2:Starfield.esm (OE_AustinF_DeployMicrobe_Terminal) is missing");
        foreach (var c in termsJ.EnumerateArray())
        {
            var src = c.GetProperty("src").GetString()!;
            var edid = c.GetProperty("edid").GetString()!;
            var menuEdid = c.GetProperty("menu_edid").GetString()!;
            var model = c.GetProperty("model").GetString()!;
            var name = OneLine(c, "name", optional: false)!;
            var body = OneLine(c, "body", optional: false)!;
            var sig = $"{model.ToLowerInvariant()}|{menuEdid.ToLowerInvariant()}|{name}|{body}";
            if (!termByEdid.TryGetValue(edid, out var tm))
            {
                if (!menuEdids.Add(menuEdid))
                    throw new InvalidDataException($"terminal {edid}: menu {menuEdid} already belongs to another terminal");
                var term = new Terminal(NewKey(), release)
                {
                    EditorID = edid, Model = new Model { File = model }, Name = name,
                    Background = Terminal.BackgroundType.Default,
                };
                Furnish(term, termTemplate!);
                var menu = new TerminalMenu(NewKey(), release)
                {
                    EditorID = menuEdid, Name = name, INAM = string.Empty,
                    ShowBodyText = TerminalMenu.ShowBodyTextOption.Document,
                    MenuButtonStyle = (TerminalMenu.MenuButtonStyleOption)0,
                    Style = TerminalMenu.StyleOption.Windows,
                    BodyTexts = new ExtendedList<TerminalMenuBodyText> { new TerminalMenuBodyText { Text = body, UseTemplatedText = false } },
                    MenuItems = new ExtendedList<TerminalMenuItem>(),
                };
                term.Menu.SetTo(menu.FormKey);
                mod.Terminals.Add(term);
                mod.TerminalMenus.Add(menu);
                termByEdid[edid] = tm = (term, menu);
                termSig[edid] = sig;
            }
            else if (termSig[edid] != sig)
                throw new InvalidDataException($"terminal {edid}: {src} asks for {sig} but the shared record is {termSig[edid]}");
            var obj = PlacePromoted(c, tm.Term.FormKey, "terminal");
            termIds[src] = new Dictionary<string, string>
            {
                ["base"] = tm.Term.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6"),
                ["menu"] = tm.Menu.FormKey.ID.ToString("X6"),
            };
            if (termIds.Count <= 8 || termIds.Count % 500 == 0)
                Console.WriteLine($"  terminal {tm.Term.EditorID} {tm.Term.FormKey} ('{tm.Term.Name?.String}', menu {tm.Menu.FormKey}) -> REFR {obj.FormKey}");
        }
    }
    // Workshops (docs/terrain/stations.md): FO4's settlement workshops (CONT WorkshopWorkbench and its NonSettlement
    // twin, both with the workshopscript VMAD) become the build station Starfield ships pre-placed, in the pattern of
    // OutpostPlayerHouseActivator (00024DC7: no script, WorkshopKeyword + OutpostCategory* keywords, PRPS
    // OutpostBuildAreaRadius; placed in the Neon exterior as Neon_PlayerCrateWorkshopRef): one ACTI per FO4 base with the
    // converted workbench model, FULL the entry's name, the keywords WorkshopKeyword (00054BA7) then the OutpostCategory*
    // keywords 00024DC7 carries, in its order (read from the master, never typed), PRPS OutpostBuildAreaRadius (AVIF
    // 00063FC5) = the entry's radius (metres), no VMAD; the REFR temporary in its slot, as every promoted class.
    // ({"src", "edid", "model", "name", "radius", "cell", "pos", "rot", "scale", "reference_index"}; Mutagen
    // 0.55.0-alpha.67 Activator: Keywords, Properties [ObjectProperty { ActorValue, Value, CurveTable }].)
    // The new ACTI bases follow the TERM + TMLM block.
    var wkshpIds = new Dictionary<string, object>();
    var wkshpByEdid = new Dictionary<string, StarfieldActivator>(StringComparer.OrdinalIgnoreCase);
    var wkshpSig = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    if (o.TryGetProperty("workshops", out var wkshpJ))
    {
        List<IFormLinkGetter<IKeywordGetter>> stationKeywords = new();
        FormKey radiusAv = default;
        if (wkshpJ.GetArrayLength() > 0)
        {
            var house = sf.Activators.FirstOrDefault(x => x.FormKey == new FormKey(sfEsm, 0x024DC7))
                ?? throw new InvalidDataException("workshops: the template activator 00024DC7 (OutpostPlayerHouseActivator) is missing from the master");
            var kwEdid = sf.Keywords.ToDictionary(k => k.FormKey, k => k.EditorID ?? "");
            var workshopKw = new FormKey(sfEsm, 0x054BA7);
            if (!kwEdid.TryGetValue(workshopKw, out var kwName) || kwName != "WorkshopKeyword")
                throw new InvalidDataException("workshops: KYWD 00054BA7 of the master is not WorkshopKeyword");
            var av = sf.ActorValueInformation.FirstOrDefault(x => x.FormKey == new FormKey(sfEsm, 0x063FC5));
            if (av == null || av.EditorID != "OutpostBuildAreaRadius")
                throw new InvalidDataException("workshops: AVIF 00063FC5 of the master is not OutpostBuildAreaRadius");
            radiusAv = av.FormKey;
            var categories = (house.Keywords ?? Enumerable.Empty<IFormLinkGetter<IKeywordGetter>>())
                .Where(k => kwEdid.TryGetValue(k.FormKey, out var n) && n.StartsWith("OutpostCategory", StringComparison.Ordinal)).ToList();
            if (categories.Count == 0)
                throw new InvalidDataException("workshops: OutpostPlayerHouseActivator carries no OutpostCategory keyword");
            stationKeywords.Add(new FormLink<IKeywordGetter>(workshopKw));
            stationKeywords.AddRange(categories.Select(k => (IFormLinkGetter<IKeywordGetter>)new FormLink<IKeywordGetter>(k.FormKey)));
            Console.WriteLine($"  workshops: keywords {string.Join(", ", stationKeywords.Select(k => kwEdid[k.FormKey]))}; PRPS {av.EditorID}");
        }
        foreach (var c in wkshpJ.EnumerateArray())
        {
            var src = c.GetProperty("src").GetString()!;
            var edid = c.GetProperty("edid").GetString()!;
            var model = c.GetProperty("model").GetString()!;
            var name = OneLine(c, "name", optional: false)!;
            var radius = c.GetProperty("radius").GetSingle();
            if (!float.IsFinite(radius) || radius <= 0)
                throw new InvalidDataException($"workshop {src}: radius {radius} is not a finite number > 0");
            var sig = $"{model.ToLowerInvariant()}|{name}|{BitConverter.SingleToUInt32Bits(radius):X8}";
            if (!wkshpByEdid.TryGetValue(edid, out var acti))
            {
                acti = new StarfieldActivator(NewKey(), release)
                {
                    EditorID = edid, Model = new Model { File = model }, Name = name,
                    MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),     // as the activators above
                    Flags = (StarfieldActivator.Flag)0, ActivationAngle = 360,
                    Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>>(stationKeywords),
                    Properties = new ExtendedList<ObjectProperty>
                    {
                        new ObjectProperty { ActorValue = new FormLink<IActorValueInformationGetter>(radiusAv), Value = radius },
                    },
                };
                mod.Activators.Add(acti);
                wkshpByEdid[edid] = acti;
                wkshpSig[edid] = sig;
            }
            else if (wkshpSig[edid] != sig)
                throw new InvalidDataException($"workshop {edid}: {src} asks for {sig} but the shared record is {wkshpSig[edid]}");
            var obj = PlacePromoted(c, acti.FormKey, "workshop");
            wkshpIds[src] = new Dictionary<string, string> { ["base"] = acti.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6") };
            Console.WriteLine($"  workshop {acti.EditorID} {acti.FormKey} ('{acti.Name?.String}', radius {radius} m) -> REFR {obj.FormKey} in cell ({c.GetProperty("cell")[0]}, {c.GetProperty("cell")[1]})");
        }
    }
    // Flora (docs/terrain/flora.md): FO4 Flora -> native Starfield FLOR, one base per FO4 base, cloned from
    // FloraMaizeCrop01 (000EC886: keywords FloraTypeOrganic + OutpostCanDomesticate, PFIG OrgCommonNutrient_Seed,
    // PNAM/FNAM/JNAM/PFPC/PRPS of the crop template). Mutagen 0.55.0-alpha.67 Flora.Ingredient writes PFIG
    // (default seed and a custom MISC both serialize; a STAT ingredient is refused before publication). Duplicate
    // of the maize crop keeps the rest of the harvest fields, then we set EditorID, Name, Model, Ingredient.
    // ({"src", "edid", "model", "name", "ingredient", "cell", "pos", "rot", "scale", "reference_index"}.)
    var florIds = new Dictionary<string, object>();
    var florByEdid = new Dictionary<string, Flora>(StringComparer.OrdinalIgnoreCase);
    var florSig = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    if (o.TryGetProperty("flora", out var florJ))
    {
        IFloraGetter? florTemplate = null;
        var defaultIng = new FormKey(sfEsm, 0x260DF2);
        if (florJ.GetArrayLength() > 0)
            florTemplate = sf.Florae.FirstOrDefault(x => x.FormKey == new FormKey(sfEsm, 0x0EC886))
                ?? throw new InvalidDataException("flora: the template FLOR 000EC886 (FloraMaizeCrop01) is missing from the master");
        foreach (var c in florJ.EnumerateArray())
        {
            var src = c.GetProperty("src").GetString()!;
            var edid = c.GetProperty("edid").GetString()!;
            var model = c.GetProperty("model").GetString()!;
            var name = OneLine(c, "name", optional: false)!;
            var ingStr = c.GetProperty("ingredient").GetString() ?? "";
            var colon = ingStr.IndexOf(':');
            if (colon < 1 || !uint.TryParse(ingStr[..colon], System.Globalization.NumberStyles.HexNumber, null, out var ingId)
                || !string.Equals(ingStr[(colon + 1)..], sfEsm.FileName.String, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"flora {src}: ingredient '{ingStr}' is not a Starfield.esm formkey (hex:Starfield.esm)");
            var ingKey = new FormKey(sfEsm, ingId);
            if (sf.MiscItems.FirstOrDefault(x => x.FormKey == ingKey) is null
                && sf.LeveledItems.FirstOrDefault(x => x.FormKey == ingKey) is null)
                throw new InvalidDataException($"flora {src}: ingredient {ingStr} is not a MISC or LVLI of the master");
            var sig = $"{model.ToLowerInvariant()}|{name}|{ingStr.ToLowerInvariant()}";
            if (!florByEdid.TryGetValue(edid, out var flor))
            {
                flor = (Flora)florTemplate!.Duplicate(NewKey());
                flor.EditorID = edid;
                flor.Name = name;
                flor.Model = new Model { File = model };
                var ingProp = typeof(Flora).GetProperty("Ingredient");
                if (ingProp != null)
                {
                    var link = ingProp.GetValue(flor);
                    var setTo = link?.GetType().GetMethod("SetTo", new[] { typeof(FormKey) });
                    setTo?.Invoke(link, new object[] { ingKey });
                }
                else if (ingKey != defaultIng)
                    throw new InvalidDataException($"flora {edid}: Mutagen Flora has no Ingredient property; cannot write non-default PFIG {ingStr}");
                mod.Florae.Add(flor);
                florByEdid[edid] = flor;
                florSig[edid] = sig;
            }
            else if (florSig[edid] != sig)
                throw new InvalidDataException($"flora {edid}: {src} asks for {sig} but the shared record is {florSig[edid]}");
            var obj = PlacePromoted(c, flor.FormKey, "flora");
            florIds[src] = new Dictionary<string, string> { ["base"] = flor.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6") };
            if (florIds.Count <= 8 || florIds.Count % 500 == 0)
                Console.WriteLine($"  flora {flor.EditorID} {flor.FormKey} ('{flor.Name?.String}', {ingStr}) -> REFR {obj.FormKey}");
        }
    }
    // Benches (docs/terrain/stations.md): FO4 crafting stations keep their REFR slot and take the VANILLA Starfield bench
    // of their kind as base (WorkbenchWeapon 2B6A63, WorkbenchArmor 2B6A62, WorkbenchChem 2B6A61, WorkbenchFood 2B6A65:
    // the same WBDT bench type as FO4's bench and, armor / chem / cooking, the same recipe keyword id), so no record of
    // ours is added and no FormID moves. ({"src", "kind", "vanilla", "cell", "pos", "rot", "scale", "reference_index"}.)
    // Refused: a kind outside the four, a vanilla id that is not that kind's, one that is not a FURN of the master, or a
    // FURN without a bench type (WBDT 0: no crafting menu).
    var benchIds = new Dictionary<string, object>();
    if (o.TryGetProperty("benches", out var benchJ))
    {
        var benchKinds = new Dictionary<string, uint> { ["weapon"] = 0x2B6A63, ["armor"] = 0x2B6A62, ["chem"] = 0x2B6A61, ["cooking"] = 0x2B6A65 };
        var furnOk = new Dictionary<uint, string>();
        foreach (var c in benchJ.EnumerateArray())
        {
            var src = c.GetProperty("src").GetString()!;
            var kind = c.GetProperty("kind").GetString() ?? "";
            var vanilla = c.GetProperty("vanilla").GetString() ?? "";
            if (!benchKinds.TryGetValue(kind, out var want))
                throw new InvalidDataException($"bench {src}: kind '{kind}' is not weapon / armor / chem / cooking");
            var colon = vanilla.IndexOf(':');
            if (colon < 1 || !uint.TryParse(vanilla[..colon], System.Globalization.NumberStyles.HexNumber, null, out var id)
                || !string.Equals(vanilla[(colon + 1)..], sfEsm.FileName.String, StringComparison.OrdinalIgnoreCase) || id != want)
                throw new InvalidDataException($"bench {src}: vanilla '{vanilla}' is not the {kind} bench {want:X6}:{sfEsm.FileName}");
            if (!furnOk.ContainsKey(id))
            {
                var furn = sf.Furniture.FirstOrDefault(f => f.FormKey == new FormKey(sfEsm, id))
                    ?? throw new InvalidDataException($"bench {src}: {vanilla} is not a FURN of the master");
                if ((furn.BenchType ?? Furniture.BenchTypes.None) == Furniture.BenchTypes.None)
                    throw new InvalidDataException($"bench {src}: {vanilla} ({furn.EditorID}) has no bench type (WBDT 0): not a crafting station");
                furnOk[id] = furn.EditorID ?? "";
                Console.WriteLine($"  bench kind {kind}: vanilla FURN {furn.FormKey} {furn.EditorID} ({furn.BenchType})");
            }
            var obj = PlacePromoted(c, new FormKey(sfEsm, id), "bench");
            benchIds[src] = new Dictionary<string, string> { ["base"] = vanilla, ["ref"] = obj.FormKey.ID.ToString("X6"), ["kind"] = kind };
            nBench++;
            if (nBench <= 8 || nBench % 100 == 0)
                Console.WriteLine($"  bench {kind} {src} -> REFR {obj.FormKey} on {vanilla}");
        }
    }
    // Scripted load doors (docs/terrain/scripted-doors.md): FO4 exterior load doors into converted interiors
    // ({"src", "edid", "model", "name", "destination": {"plugin", "id", "ref", "cell"}, "arrival": {"pos", "rot", "cell"},
    // "cell", "pos", "rot", "scale", "reference_index"}). The REFR is placed here, temporary in its reserved slot, with
    // the VMAD (Mutagen 0.55.0-alpha.67 VirtualMachineAdapter, version 6 / object format 2, one local ScriptEntry
    // FO4SF_LoadDoor, ScriptStringProperty DestinationPlugin + ScriptIntProperty DestinationId + ScriptFloatProperty
    // DestinationX / Y / Z (destination.arrival.pos: the interior marker's position) + ScriptBoolProperty
    // UseDestinationPosition (true: the script ignores the three floats otherwise), all Edited: the layout of
    // Starfield.esm's own REFR VMADs, read back raw by the design pass). Its ACTI base (one per edid: entries of an
    // edid must agree on model and name) and its arrival marker are allocated after the lights, below; the base link
    // is set then. Refused: a destination that is not a plugin file name with an id in 1..0xFFFFFF or whose arrival
    // position is not three finite numbers, two doors sharing one destination, an arrival marker outside the overlay's
    // cells.
    if (o.TryGetProperty("doors", out var doorsJ))
    {
        var doorSig = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var destSeen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var c in doorsJ.EnumerateArray())
        {
            var src = c.GetProperty("src").GetString()!;
            var edid = c.GetProperty("edid").GetString()!;
            var model = c.GetProperty("model").GetString()!;
            var name = OneLine(c, "name", optional: false)!;
            var dest = c.GetProperty("destination");
            var plugin = dest.GetProperty("plugin").GetString() ?? "";
            if (string.IsNullOrWhiteSpace(plugin) || plugin.IndexOfAny(new[] { '\\', '/', '\n', '\r' }) >= 0)
                throw new InvalidDataException($"door {src}: destination plugin '{plugin}' is not a plugin file name");
            if (!dest.GetProperty("id").TryGetInt32(out var destId) || destId <= 0 || destId > 0xFFFFFF)
                throw new InvalidDataException($"door {src}: destination id {dest.GetProperty("id")} is not a plugin-local id in 1..0xFFFFFF");
            if (!destSeen.Add($"{plugin}:{destId:X6}"))
                throw new InvalidDataException($"door {src}: destination {plugin}:{destId:X6} already belongs to another door");
            var destPos = dest.GetProperty("arrival").GetProperty("pos").EnumerateArray().Select(e => e.GetSingle()).ToArray();
            if (destPos.Length != 3 || destPos.Any(v => !float.IsFinite(v)))
                throw new InvalidDataException($"door {src}: destination arrival position is not three finite numbers");
            var sig = $"{model.ToLowerInvariant()}|{name}";
            if (doorSig.TryGetValue(edid, out var have))
            {
                if (have != sig) throw new InvalidDataException($"door {edid}: {src} asks for {sig} but the shared record is {have}");
            }
            else doorSig[edid] = sig;
            var arr = c.GetProperty("arrival");
            float[] A(string k) => arr.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
            var acell = arr.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
            if (!cellAt.ContainsKey((acell[0], acell[1])))
                throw new InvalidDataException($"door {src}: arrival marker in cell ({acell[0]}, {acell[1]}) outside {world}'s cells");
            var obj = PlacePromoted(c, FormKey.Null, "door");                   // the ACTI base is linked after the lights
            // step C (make_core64c.py stage --animated-doors, docs/spikes/load-door-animations.md): "anim" makes the base a
            // rigged DOOR and the script FO4SF_AnimatedLoadDoor (FO4SF_LoadDoor's properties plus OpenSeconds); without
            // it nothing here changes
            JsonElement? anim = c.TryGetProperty("anim", out var an) && an.ValueKind == JsonValueKind.Object ? an : null;
            var vmad = new VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
            var script = new ScriptEntry { Name = anim is null ? "FO4SF_LoadDoor" : "FO4SF_AnimatedLoadDoor", Flags = ScriptEntry.Flag.Local };
            script.Properties.Add(new ScriptStringProperty { Name = "DestinationPlugin", Flags = ScriptProperty.Flag.Edited, Data = plugin });
            script.Properties.Add(new ScriptIntProperty { Name = "DestinationId", Flags = ScriptProperty.Flag.Edited, Data = destId });
            string[] axes = { "DestinationX", "DestinationY", "DestinationZ" };
            for (int k = 0; k < 3; k++)
                script.Properties.Add(new ScriptFloatProperty { Name = axes[k], Flags = ScriptProperty.Flag.Edited, Data = destPos[k] });
            script.Properties.Add(new ScriptBoolProperty { Name = "UseDestinationPosition", Flags = ScriptProperty.Flag.Edited, Data = true });
            if (anim is JsonElement aj)
            {
                var seconds = aj.GetProperty("open_seconds").GetSingle();
                if (!float.IsFinite(seconds) || seconds < 0 || seconds > 30)
                    throw new InvalidDataException($"door {src}: open seconds {seconds} outside 0..30");
                script.Properties.Add(new ScriptFloatProperty { Name = "OpenSeconds", Flags = ScriptProperty.Flag.Edited, Data = seconds });
            }
            vmad.Scripts.Add(script);
            obj.VirtualMachineAdapter = vmad;
            doorEntries.Add((src, obj, edid, model, name, acell, A("pos"), A("rot"), anim?.Clone()));
            doorRefIds[src] = obj.FormKey.ID.ToString("X6");
        }
    }
    // Red Rocket garage button -> door (docs/terrain/garage-button.md). Vanilla DefaultActivateLinkedRefOnActivate
    // (no new .pex) + XLKR LinkCustom02 (0005D5E7). Existing ACTI REFR slots; no new FormIDs.
    var garageIds = new List<object>();
    if (o.TryGetProperty("garage_buttons", out var gbJ))
    {
        foreach (var pair in gbJ.EnumerateArray())
        {
            var buttonSrc = pair.GetProperty("button").GetString()!;
            var doorSrc = pair.GetProperty("door").GetString()!;
            if (!actiBySrc.TryGetValue(buttonSrc, out var button) || !actiBySrc.TryGetValue(doorSrc, out var door))
                throw new InvalidDataException($"garage_buttons: {buttonSrc} / {doorSrc} are not promoted activators");
            var kw = new FormKey(sfEsm, 0x5D5E7);                                  // LinkCustom02; script GetLinkedRef(LinkedRefKeyword)
            var vmad = new VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
            var script = new ScriptEntry { Name = "DefaultActivateLinkedRefOnActivate" };
            script.Properties.Add(new ScriptObjectProperty
            {
                Name = "LinkedRefKeyword", Flags = ScriptProperty.Flag.Edited,
                Object = new FormLink<IStarfieldMajorRecordGetter>(kw), Alias = -1, Unused = 0,
            });
            vmad.Scripts.Add(script);
            button.VirtualMachineAdapter = vmad;
            var link = new LinkedReferences();
            link.KeywordOrReference.SetTo(kw);
            link.Reference.SetTo(door.FormKey);
            button.LinkedReferences.Add(link);
            garageIds.Add(new Dictionary<string, string> { ["button"] = button.FormKey.ID.ToString("X6"), ["door"] = door.FormKey.ID.ToString("X6") });
            Console.WriteLine($"  garage button {buttonSrc} REFR {button.FormKey} -> door {doorSrc} REFR {door.FormKey} (DefaultActivateLinkedRefOnActivate + LinkCustom02)");
        }
    }
    nCont = contByEdid.Count; nMisc = miscByEdid.Count; nActi = actiByEdid.Count; nTerm = termByEdid.Count; nWkshp = wkshpByEdid.Count;
    nFlor = florByEdid.Count;
    ids = new Dictionary<string, object> { ["plugin"] = modKey.FileName.String, ["world"] = world, ["bases"] = baseIds, ["refs"] = refIds, ["containers"] = contIds };
    if (o.TryGetProperty("items", out _)) ids["items"] = itemIds;               // a build without items keeps its formids.json bytes
    if (o.TryGetProperty("activators", out _)) ids["activators"] = actiIds;     // (as without activators / terminals)
    if (o.TryGetProperty("terminals", out _)) ids["terminals"] = termIds;
    if (o.TryGetProperty("workshops", out _)) ids["workshops"] = wkshpIds;       // (and without workshops / benches)
    if (o.TryGetProperty("flora", out _)) ids["flora"] = florIds;
    if (o.TryGetProperty("benches", out _)) ids["benches"] = benchIds;
    if (o.TryGetProperty("doors", out _)) ids["doors"] = doorIds;               // filled after the lights
    if (garageIds.Count > 0) ids["garage_buttons"] = garageIds;
}
if (Has(prm, "navmesh"))
{
    // Commonwealth navmesh (docs/actors/navmesh-conversion.md, ported from dotnet/TerrainExp2 2026-10-15): converted
    // Fallout 4 navmeshes (src/fo4sf/navmesh.py export), one NAVM per (FO4 navmesh, Starfield cell) in that cell's
    // navmesh group, allocated after every object, plus a NAVI override (000FF1:Starfield.esm) with one NVMI per new
    // navmesh. Every field is typed in Mutagen except NVMI's Data and Unknown (raw bytes; the worldspace FormID in
    // Unknown is file-local: Starfield.esm is master 0, this plugin's records are 01xxxxxx). The four Mutagen
    // 0.55.0-alpha.67 adjustments of experiment 2d (grid lists as one raw array + Unknown3, parent coordinates
    // y-then-x, the empty MNAM, form version 581) are kept as verified there.
    using var ndoc = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, prm.GetProperty("navmesh").GetString()!)));
    var nroot = ndoc.RootElement;
    string nworld = nroot.TryGetProperty("world", out var nwj) ? nwj.GetString()! : (objWorld ?? worlds[0].World.EditorID!);
    if (!cellsOf.TryGetValue(nworld, out var navCells)) throw new InvalidDataException($"navmesh.json names world {nworld}, not an overlay of these params");
    var navWorld = worlds.First(x => x.World.EditorID == nworld).World;
    var navs = nroot.GetProperty("navmeshes").EnumerateArray().ToList();
    var navKeys = navs.Select(_ => NewKey()).ToList();
    uint worldLocal = 0x01000000u | navWorld.FormKey.ID;
    var navi = new NavigationMeshInfoMap(new FormKey(sfEsm, 0x000FF1), release)
    {
        NavMeshVersion = 17,
        PreferredPathing = new PreferredPathing(),
        FormVersion = 581,                                          // Starfield.esm, SFBGS006, BlueprintShips: 581
    };
    var navIds = new List<string>();
    for (int i = 0; i < navs.Count; i++)
    {
        var e = navs[i];
        var cxy = e.GetProperty("cell").EnumerateArray().Select(x => x.GetInt32()).ToArray();
        if (!navCells.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"navmesh {i} in cell ({cxy[0]}, {cxy[1]}) outside {nworld}'s cells");
        var grid = e.GetProperty("grid");
        float[] GF(string k) => grid.GetProperty(k).EnumerateArray().Select(x => x.GetSingle()).ToArray();
        var gsize = GF("size"); var gmin = GF("min"); var gmax = GF("max");
        var g = new NavmeshGeometry
        {
            NavmeshVersion = 17,
            CrcHash = 0xA5E9A03C,
            Parent = new WorldspaceNavmeshParent
            {
                Parent = new FormLink<IWorldspaceGetter>(navWorld.FormKey),
                // the file holds grid y, then grid x (every vanilla exterior NAVM matches its cell's XCLC that way);
                // Mutagen writes Coordinates.X first, so X takes the grid y
                Coordinates = new P2Int16((short)cxy[1], (short)cxy[0]),
            },
            GridSize = (uint)grid.GetProperty("divisor").GetInt32(),
            GridMaxDistance = new P2Float(gsize[0], gsize[1]),
            GridMin = new P3Float(gmin[0], gmin[1], gmin[2]),
            GridMax = new P3Float(gmax[0], gmax[1], gmax[2]),
            Unknown3 = 0x0008000C,                                   // the trailing 0c 00 08 00 of vanilla records
        };
        foreach (var v in e.GetProperty("vertices").EnumerateArray())
            g.Vertices.Add(new NavmeshVertex { Point = new P3Float(v[0].GetSingle(), v[1].GetSingle(), v[2].GetSingle()), Unknown = v[3].GetInt32() });
        foreach (var t in e.GetProperty("triangles").EnumerateArray())
        {
            g.Triangles.Add(new NavmeshTriangle
            {
                Vertices = new P3Int16(t[0].GetInt16(), t[1].GetInt16(), t[2].GetInt16()),
                EdgeLink_0_1 = t[3].GetInt16(), EdgeLink_1_2 = t[4].GetInt16(), EdgeLink_2_0 = t[5].GetInt16(),
                Height = t[6].GetSingle(), Unknown = (byte)t[7].GetInt32(),
                Flags = (NavmeshTriangle.Flag)t[8].GetInt32(), CoverFlags = (ushort)t[9].GetInt32(),
            });
            nNavTri++;
        }
        var merged = new List<FormKey>();
        foreach (var l in e.GetProperty("links").EnumerateArray())
        {
            var target = navKeys[l[1].GetInt32()];
            g.EdgeLinks.Add(new EdgeLink
            {
                Unknown = l[0].GetInt32(), Mesh = new FormLink<INavigationMeshGetter>(target),
                TriangleIndex = l[2].GetInt16(), Unknown2 = (sbyte)l[3].GetInt32(),
            });
            if (!merged.Contains(target)) merged.Add(target);
            nNavLink++;
        }
        var linkedDoors = new List<LinkedDoor>();
        foreach (var d in e.GetProperty("doors").EnumerateArray())
        {
            var src = d[2].GetString()!;
            // a FO4 load door promoted to a scripted door keeps its REFR id: the door triangle links to the same record
            if (!refIds.TryGetValue(src, out var doorId) && !doorRefIds.TryGetValue(src, out doorId))
                throw new InvalidDataException($"navmesh {i}: door {src} is not a placed reference of this plugin");
            var doorKey = new FormKey(modKey, Convert.ToUInt32(doorId, 16));
            g.DoorTriangles.Add(new DoorTriangle { TriangleBeforeDoor = d[0].GetInt16(), Unknown = unchecked((int)d[1].GetUInt32()), Door = new FormLink<IPlacedObjectGetter>(doorKey) });
            linkedDoors.Add(new LinkedDoor { Type = d[1].GetUInt32(), Door = new FormLink<IPlacedObjectGetter>(doorKey) });
            nNavDoor++;
        }
        foreach (var wp in e.GetProperty("waypoints").EnumerateArray())
            g.Waypoints.Add(new NavmeshWaypoint { Location = new P3Float(wp[0].GetSingle(), wp[1].GetSingle(), wp[2].GetSingle()), TriangleIndex = wp[3].GetInt16(), Unknown = wp[4].GetInt32() });
        // the grid lists with their counts as ONE raw i16 array (navmesh.grid_raw), Unknown3 the trailer (experiment 2d)
        g.GridArrays.Add(new NavmeshGridArray { GridCell = new ExtendedList<short>(grid.GetProperty("raw").EnumerateArray().Select(x => x.GetInt16())) });
        cell.NavigationMeshes.Add(new NavigationMesh(navKeys[i], release)
        {
            NavmeshGeometry = g,
            PreCutMapEntries = new ExtendedList<PreCutMapEntry>(),   // the empty MNAM every vanilla NAVM has
            FormVersion = 581,                                      // as Starfield.esm's newest NAVM and its NAVI
        });
        var nv = e.GetProperty("nvmi");
        var loc = nv.GetProperty("location").EnumerateArray().Select(x => x.GetSingle()).ToArray();
        var data = new byte[20];
        BitConverter.TryWriteBytes(data.AsSpan(0, 4), 0u);                       // flags: no outline
        BitConverter.TryWriteBytes(data.AsSpan(4, 4), loc[0]);
        BitConverter.TryWriteBytes(data.AsSpan(8, 4), loc[1]);
        BitConverter.TryWriteBytes(data.AsSpan(12, 4), loc[2]);
        BitConverter.TryWriteBytes(data.AsSpan(16, 4), 0f);
        var unk = new byte[22];                                                    // traversals 0, outline 0
        BitConverter.TryWriteBytes(unk.AsSpan(5, 4), 0xA5E9A03Cu);
        BitConverter.TryWriteBytes(unk.AsSpan(9, 4), worldLocal);
        BitConverter.TryWriteBytes(unk.AsSpan(13, 2), (short)cxy[1]);              // grid y, then x
        BitConverter.TryWriteBytes(unk.AsSpan(15, 2), (short)cxy[0]);
        unk[17] = (byte)nv.GetProperty("border").GetInt32();
        var info = new NavigationMapInfo
        {
            NavigationMesh = new FormLink<INavigationMeshGetter>(navKeys[i]),
            Data = new MemorySlice<byte>(data),
            Unknown = new MemorySlice<byte>(unk),
        };
        foreach (var m in merged) info.MergedTo.Add(new FormLink<INavigationMeshGetter>(m));
        foreach (var ld in linkedDoors) info.LinkedDoors.Add(ld);
        navi.MapInfos.Add(info);
        navIds.Add(navKeys[i].ID.ToString("X6"));
        nNav++;
    }
    mod.NavigationMeshInfoMaps.Add(navi);
    ids ??= new Dictionary<string, object> { ["plugin"] = modKey.FileName.String, ["world"] = nworld };
    ids["navmeshes"] = navIds;
    ids["navi"] = "000FF1:Starfield.esm";
}
int nLight = 0, nLightRef = 0;
if (lightsJson is JsonElement lights && lightBasesJson is JsonElement lightBases)
{
    // Exterior lights (docs/terrain/exterior-lights.md). NEW FormIDs after every record above: first the light REFRs in
    // "lights" order (the identities a save can hold), then the LIGH bases in "light_bases" order (one per FO4 base).
    // Every Starfield-only field (contact shadow component, barndoors, roundness, gobo data, area light, layer,
    // adaptive lighting, volumetric scale, the DAT2 value Mutagen calls PbrLightTemperatureK) is the vanilla template's.
    var templateLight = sf.Lights.FirstOrDefault(l => l.FormKey.ID == 0x12A74B)
        ?? throw new InvalidDataException("template light 12A74B:Starfield.esm (LGT_Interior_Omni_NS_Warm_004_2k) not in the master");
    var lightRefKeys = lightSources.Select(_ => NewKey()).ToArray();
    var lightByEdid = new Dictionary<string, Light>(StringComparer.OrdinalIgnoreCase);
    foreach (var b in lightBases.EnumerateArray())
    {
        float F(string k) => b.GetProperty(k).GetSingle();
        var rec = (Light)templateLight.Duplicate(NewKey());
        rec.EditorID = b.GetProperty("edid").GetString();
        var bb = b.GetProperty("bounds");
        rec.ObjectBounds = new ObjectBounds
        {
            First = new P3Float(bb[0][0].GetSingle(), bb[0][1].GetSingle(), bb[0][2].GetSingle()),
            Second = new P3Float(bb[1][0].GetSingle(), bb[1][1].GetSingle(), bb[1][2].GetSingle()),
        };
        rec.Time = b.GetProperty("time").GetInt32();
        rec.Radius = F("radius");                                                  // metres
        var col = b.GetProperty("color");
        rec.Color = System.Drawing.Color.FromArgb(0, col[0].GetInt32(), col[1].GetInt32(), col[2].GetInt32());
        rec.Flags = (Light.Flag)b.GetProperty("flags").GetUInt32();
        rec.Type = (Light.LightType)b.GetProperty("type").GetInt32();
        rec.FalloffExponent = F("falloff");
        rec.FOV = F("fov");
        rec.NearClip = F("near_clip");
        var fl = b.GetProperty("flicker");
        rec.FlickerPeriod = fl[0].GetSingle();
        rec.FlickerIntensityAmplitude = fl[1].GetSingle();
        rec.FlickerMovementAmplitude = fl[2].GetSingle();
        rec.FlickerEffect = (Light.FlickerEffectOption)b.GetProperty("flicker_effect").GetInt32();
        rec.PbrLuminousPowerLm = b.GetProperty("lumens").GetUInt32();
        rec.MajorRecordFlagsRaw = b.GetProperty("random_anim_start").GetBoolean() ? 0x10000 : 0;   // Random Anim Start
        rec.Components.RemoveAll(c => c is ObjectWindowFilterComponent);           // CK object-window folder (bookkeeping)
        mod.Lights.Add(rec);
        lightByEdid[rec.EditorID!] = rec;
        nLight++;
    }
    var lightIds = new Dictionary<string, Dictionary<string, string>>();
    int li = 0;
    foreach (var e in lights.EnumerateArray())
    {
        float[] V(string k) => e.GetProperty(k).EnumerateArray().Select(x => x.GetSingle()).ToArray();
        var src = e.GetProperty("src").GetString()!;
        var cxy = e.GetProperty("cell").EnumerateArray().Select(x => x.GetInt32()).ToArray();
        if (objCells == null || !objCells.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"light {src} in cell ({cxy[0]}, {cxy[1]}) outside {objWorld}'s cells");
        var rec = lightByEdid[e.GetProperty("edid").GetString()!];
        var pos = V("pos");
        var rot = V("rot");
        var obj = new PlacedObject(lightRefKeys[li++], release)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(rec.FormKey),
            Position = new P3Float(pos[0], pos[1], pos[2]),
            Rotation = new P3Float(rot[0], rot[1], rot[2]),
        };
        var scale = e.GetProperty("scale").GetSingle();
        if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
        // the FO4 reference's own DoesNotLightWater (0x100) / NeverFades (0x10000) / DoesNotLightLandscape (0x20000) bits,
        // Mutagen's PlacedObject.LightMajorFlag names in both games (ReferenceIdentityPlan.Lights refuses any other bit)
        obj.MajorRecordFlagsRaw |= (int)e.GetProperty("flags").GetUInt32();
        if (e.GetProperty("disabled").GetBoolean()) obj.MajorRecordFlagsRaw |= 0x800;   // Initially Disabled, as in FO4
        if (e.TryGetProperty("radius", out var rd) && rd.ValueKind == JsonValueKind.Number)
            obj.Radius = rd.GetSingle();                   // XRDS: the radius delta (metres), as FO4's
        if (e.TryGetProperty("lighting", out var lg) && lg.ValueKind == JsonValueKind.Object)
            obj.Lighting = new PlacedObjectLighting
            {
                Fov90PlusMinus = lg.GetProperty("fov").GetSingle(),
                Fade1PlusMinus = lg.GetProperty("fade").GetSingle(),
                EndDistanceCap = 0, ShadowDepthBias = 0,
                NearClip = lg.GetProperty("near_clip").GetSingle(),
                VolumetricIntensity = 0,
                Unknown1 = 0xABABABAB, Unknown2 = 0xABABAB00,  // the trailing bytes of 27,305 vanilla exterior light XLIGs
            };
        cell.Temporary.Add(obj);
        lightIds[src] = new Dictionary<string, string> { ["base"] = rec.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6") };
        nLightRef++;
    }
    ids!["lights"] = lightIds;
}
int nDoorActi = 0;
if (doorEntries.Count > 0)
{
    // Scripted load doors, the appended records: first one arrival XMarker REFR per door (where the interior door's
    // MoveTo lands the player: PERSISTENT, in the world's persistent cell beside the anchor, at the FO4 arrival point's
    // local position; the arrival cell was checked against the overlay above), in "doors" order, then one ACTI per
    // door edid in first-use order (the converted door mesh, FULL the name, PNAM / FNAM / JNAM as the activators:
    // the vanilla majority), and the door REFRs placed above take that ACTI as base.
    var persistentCell = worlds.First(x => x.World.EditorID == objWorld).World.TopCell!;
    var markerKeys = doorEntries.Select(_ => NewKey()).ToList();
    var doorActi = new Dictionary<string, IStarfieldMajorRecordGetter>(StringComparer.OrdinalIgnoreCase);
    for (int i = 0; i < doorEntries.Count; i++)
    {
        var d = doorEntries[i];
        if (!doorActi.TryGetValue(d.Edid, out var acti))
        {
            if (d.Anim is JsonElement aj)
            {
                // step C: the same DOOR the port writes for an animated load door (PluginSpike): rig graph, skeleton,
                // clips, bounds, the vanilla sounds and FO4's flags when the manifest has them; the same new id as the ACTI
                var door = new Door(NewKey(), release)
                {
                    EditorID = d.Edid, Model = new Model { File = d.Model }, Name = d.Name,
                    SoundLevel = SoundLevel.Normal, FacingAxisOverride = Door.FacingAxisOverrideEnum.BasedOnBounds,
                    Flags = aj.TryGetProperty("fo4_door_flags", out var ff) ? (Door.Flag)(ff.GetInt32() & 0x7E) : 0,
                };
                if (aj.TryGetProperty("bounds", out var bj))
                    door.ObjectBounds = new ObjectBounds
                    {
                        First = new P3Float(bj[0][0].GetSingle(), bj[0][1].GetSingle(), bj[0][2].GetSingle()),
                        Second = new P3Float(bj[1][0].GetSingle(), bj[1][1].GetSingle(), bj[1][2].GetSingle()),
                    };
                door.Components.Add(new AnimationGraphComponent
                {
                    ANAM = aj.GetProperty("anim_graph").GetString(), BNAM = aj.GetProperty("skeleton").GetString(),
                    CNAM = aj.GetProperty("animations").GetString(),
                });
                door.OpenSound = DoorSound(aj, "open_sound");
                door.CloseSound = DoorSound(aj, "close_sound");
                mod.Doors.Add(door);
                acti = door;
            }
            else
            {
                var a = new StarfieldActivator(NewKey(), release)
                {
                    EditorID = d.Edid, Model = new Model { File = d.Model }, Name = d.Name,
                    MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
                    Flags = (StarfieldActivator.Flag)0, ActivationAngle = 360,
                };
                mod.Activators.Add(a);
                acti = a;
            }
            doorActi[d.Edid] = acti;
            nDoorActi++;
        }
        d.Obj.Base = new FormLinkNullable<IPlaceableObjectGetter>(acti.FormKey);
        var marker = new PlacedObject(markerKeys[i], release)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x00003B)),            // XMarker
            Position = new P3Float(d.ArrivalPos[0], d.ArrivalPos[1], d.ArrivalPos[2]),
            Rotation = new P3Float(d.ArrivalRot[0], d.ArrivalRot[1], d.ArrivalRot[2]),
        };
        marker.MajorRecordFlagsRaw |= 0x400;                                     // Persistent
        persistentCell.Persistent.Add(marker);
        doorIds[d.Src] = new Dictionary<string, string>
        {
            ["base"] = acti.FormKey.ID.ToString("X6"), ["ref"] = d.Obj.FormKey.ID.ToString("X6"), ["arrival"] = marker.FormKey.ID.ToString("X6"),
        };
        Console.WriteLine($"  door {d.Src} -> REFR {d.Obj.FormKey} on {(d.Anim is null ? "ACTI" : "animated DOOR")} {acti.FormKey} {acti.EditorID} ('{d.Name}'), arrival marker {marker.FormKey} " +
                          $"persistent in {persistentCell.FormKey} (over cell ({d.ArrivalCell[0]}, {d.ArrivalCell[1]})) at ({d.ArrivalPos[0]}, {d.ArrivalPos[1]}, {d.ArrivalPos[2]})");
    }
}
// load_door_anim.py sounds on a door's "anim" (as PluginSpike's VanillaSound): WWise start / stop, optional condition
// and event mapping of Starfield.esm; null without one
static SoundReference? DoorSound(JsonElement rig, string name)
{
    if (!rig.TryGetProperty(name, out var s) || s.ValueKind != JsonValueKind.Object) return null;
    var r = new SoundReference { Start = Guid.Parse(s.GetProperty("start").GetString()!), Stop = Guid.Parse(s.GetProperty("stop").GetString()!) };
    if (s.TryGetProperty("condition", out var c) && c.GetString() is string ck) r.Condition.SetTo(FormKey.Factory(ck));
    if (s.TryGetProperty("mapping", out var m) && m.GetString() is string mk) r.EventMapping.SetTo(FormKey.Factory(mk));
    return r;
}
// Map markers (docs/terrain/map-markers.md): Duplicate LC172's persistent MapMarker REFR 003E5E12 so empty XMRK /
// FNAM 0x1B / TNAM 0x17 stay vanilla; one per entry of the overlay's "map_markers" (make_core64c stage: Red Rocket at
// the COC, Sanctuary, Vault 111, Concord), else one at the COC; fill LCSR MapMarkerRefType that the location
// Duplicate cleared (no LCID: the markers are enabled). New FormIDs after doors/lights so object IDs stay, in params order. Skip when the master has no
// 003E5E12 (synthetic identity fixture) so existing writer tests keep their FormIDs.
var srcMapMarker = sf.EnumerateMajorRecords<IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey.ID == 0x3E5E12);
int nMap = 0;
var mapIds = new Dictionary<string, string>();                               // world -> first marker (the COC one)
var mapRefIds = new Dictionary<string, Dictionary<string, string>>();        // world -> tag -> marker
if (srcMapMarker == null)
    Console.WriteLine("  map marker: template REFR 003E5E12 missing from the master; skipping");
else foreach (var (w, o) in worlds)
{
    var loc = mod.Locations.First(l => l.EditorID == o.GetProperty("location").GetString());
    var entries = new List<(string Tag, string Name, float[] Pos, int[] Cell, int? Type)>();
    if (o.TryGetProperty("map_markers", out var mj) && mj.ValueKind == JsonValueKind.Array)
        foreach (var m in mj.EnumerateArray())
            entries.Add((m.GetProperty("tag").GetString()!, m.GetProperty("name").GetString()!,
                         m.GetProperty("pos").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                         m.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray(),
                         m.TryGetProperty("type", out var tj) && tj.ValueKind == JsonValueKind.Number ? tj.GetInt32() : null));
    else
        entries.Add(("", "Red Rocket",
                     o.GetProperty("spawn").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                     o.GetProperty("spawn_cell").EnumerateArray().Select(e => e.GetInt32()).ToArray(), null));
    var tags = new Dictionary<string, string>();
    for (int i = 0; i < entries.Count; i++)
    {
        var (tag, name, pos, cell, type) = entries[i];
        var marker = (PlacedObject)srcMapMarker.Duplicate(NewKey());
        marker.EditorID = w.EditorID + "MapMarker" + (i == 0 ? "" : tag);       // the first keeps #296's EditorID
        marker.Position = new P3Float(pos[0], pos[1], pos[2]);
        marker.Rotation = new P3Float(0, 0, 0);
        // Persistent 0x400, ENABLED: LC172's 003E5E12 is 0xC00 (Initially Disabled, its quest enables it), and with
        // 0x800 kept no icon showed on the map in game (owner, 18 Oct, FO4TerrainCore fdd3f0a5); the landing-overlay
        // marker 003A866E is 0x400 (docs/terrain/map-markers.md)
        marker.MajorRecordFlagsRaw = (marker.MajorRecordFlagsRaw | 0x400) & ~0x800;
        marker.LinkedReferences?.Clear();                                    // drop LC172's XLKR into a vanilla ref
        if (marker.MapMarker != null)
        {
            marker.MapMarker.Name = name;
            // the icon: the entry's "type" (src/fo4sf/map_marker_types.json, 0-93); without one LC172's 0x17 stays
            if (type.HasValue) marker.MapMarker.Type = checked((sbyte)type.Value);
        }
        w.TopCell!.Persistent.Add(marker);
        loc.MasterSpecialReferences ??= new ExtendedList<LocationCellStaticReference>();
        loc.MasterSpecialReferences.Add(new LocationCellStaticReference
        {
            LocationRefType = new FormLink<ILocationReferenceTypeGetter>(new FormKey(sfEsm, 0x2271F)),  // MapMarkerRefType
            Marker = new FormLink<IPlacedObjectGetter>(marker.FormKey),
            Location = new FormLink<IWorldspaceGetter>(w.FormKey),
            Grid = new P2Int16((short)cell[0], (short)cell[1]),               // Mutagen writes Y then X; Unknown -1 is vanilla 0xFFFFFFFF
            Unknown = -1,
        });
        // no LCID (MasterInitiallyDisabledReferences): the marker is not initially disabled
        if (i == 0)
            mapIds[w.EditorID!] = marker.FormKey.ID.ToString("X6");
        tags[tag == "" ? "RedRocket" : tag] = marker.FormKey.ID.ToString("X6");
        nMap++;
        Console.WriteLine($"  map marker {marker.EditorID} \"{name}\" REFR {marker.FormKey} at ({pos[0]}, {pos[1]}, {pos[2]}) cell ({cell[0]}, {cell[1]}) LCSR MapMarkerRefType on {loc.EditorID}");
    }
    mapRefIds[w.EditorID!] = tags;
}
if (ids != null && mapIds.Count > 0)
{
    ids["map_markers"] = mapIds;
    ids["map_marker_refs"] = mapRefIds;
}
if (ids != null)
    File.WriteAllText(Path.Combine(outDir, "formids.json"), JsonSerializer.Serialize(ids));
mod.ModHeader.Stats.NextFormID = next;
var path = Path.Combine(outDir, modKey.FileName);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full)).Write();
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {worlds.Count} overlays, next FormID 0x{next:X}" +
                  (Has(prm, "objects") ? $"; objects: {nStat} STAT, {nMstt} MSTT, {nDoor} DOOR, {nCont} CONT, {nMisc} MISC, {nActi} ACTI, {nTerm} TERM + {nTerm} TMLM, {nWkshp} workshop ACTI, {nFlor} FLOR, {nBench} bench REFR on vanilla FURN, {nRef} REFR ({nDisabled} initially disabled, {nOpenDoor} doors open by default)" : "") +
                  (Has(prm, "navmesh") ? $"; navmesh: {nNav} NAVM, {nNavTri} triangles, {nNavLink} edge links, {nNavDoor} door triangles, NAVI override with {nNav} NVMI" : "") +
                  (nLightRef > 0 ? $"; lights: {nLight} LIGH, {nLightRef} REFR" : "") +
                  (doorEntries.Count > 0 ? $"; doors: {doorEntries.Count} scripted REFR on {nDoorActi} ACTI, {doorEntries.Count} arrival markers" : "") +
                  (nMap > 0 ? $"; map markers: {nMap}" : ""));

if (Has(prm, "mars"))
{
    var m = prm.GetProperty("mars");
    var marsKey = ModKey.FromNameAndExtension(m.GetProperty("plugin").GetString()!);
    var mars = new StarfieldMod(marsKey, release);
    mars.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var planet = (Planet)sf.Planets.First(pl => pl.EditorID == "MarsPlanetData").DeepCopy();   // same FormKey = override
    mars.Planets.Add(planet);
    foreach (var (w, o) in worlds)
        planet.MasterWorldspaces!.Add(new MasterWorldspace
        {
            Worldspace = new FormLink<IWorldspaceGetter>(w.FormKey),
            Longitude = o.GetProperty("latitude").GetDouble(),     // first f64 of the entry = latitude
            Latitude = o.GetProperty("longitude").GetDouble(),     // second f64 = longitude
        });
    mars.ModHeader.Stats.NextFormID = 0x800;
    var marsPath = Path.Combine(outDir, marsKey.FileName);
    mars.BeginWrite.ToPath(marsPath).WithLoadOrder(sfEsm, modKey)
        .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full), new KeyedMasterStyle(modKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {marsPath} ({new FileInfo(marsPath).Length:N0} bytes); Mars master worldspaces now {planet.MasterWorldspaces!.Count}");
}
