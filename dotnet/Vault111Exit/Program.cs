// Vault111Exit: the ride-along kit for Vault 111's exit sequence (FAL-461; document `vault111-exit-sequence` on that task).
//
// FO4SFVault111Exit.esm (master flag, so the installers that take .esm install it; masters: Starfield.esm, FO4Port.esm). Adds, overrides one cell:
//   QUST  FO4SF_V111Exit            0x800  stages 5 10 20 30 (order of the sequence), script FO4SF_V111Exit, NO properties
//   MISC  FO4SF_V111PipBoyToken     0x801  the player's proof of having taken the Pip-Boy
//   ACTI  FO4SF_V111PipBoyPickup    0x802  script FO4SF_V111PipBoyPickup, no properties
//   ACTI  FO4SF_V111DoorTerminal    0x803  script FO4SF_V111DoorTerminal; properties CogDoorId (int) and DoorPlugin (string)
//   REFR  0x804 pickup, 0x805 terminal: temporary children of an override of the port's cell (a deep copy without children)
// Positions, models and the cog door id come from a params file (the NewGame points step reads them from the port):
//   {"plugin":"FO4SFVault111Exit.esm","cell":"FO4Port_Vault111Cryo",
//    "pickup":{"pos":[x,y,z],"rot":[x,y,z],"base_edid":"<port base editor id>","name":"Pip-Boy"},
//    "terminal":{"pos":[..],"rot":[..],"base_edid":"<port base editor id>","name":"Door control"},
// A spot names its mesh with "model" (a path) or "base_edid" (the model of that base record in FO4Port.esm, read at build time).
//    "cog_door":{"plugin":"FO4Port.esm","id":"<hex>"}}
//
// usage: Vault111Exit build <params.json> <Starfield.esm> <FO4Port.esm> <out dir>
//        Vault111Exit check <plugin> <params.json> <Starfield.esm> <FO4Port.esm>     exit 1 on a mismatch
//        Vault111Exit scan <FO4Port.esm> <cell editor id>   read only: the cell's references whose base editor id mentions
//                                                           PipBoy, Console, Terminal or GearDoor: ref, base, model, position, rot
//        Vault111Exit fixture <out dir>     a synthetic Starfield.esm and FO4Port.esm (+ params.json) for the tests
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;
using StarfieldActivator = Mutagen.Bethesda.Starfield.Activator;   // not System.Activator (implicit usings)

try
{
    if (args.Length == 5 && args[0] == "build") return Kit.Build(args[1], args[2], args[3], args[4]);
    if (args.Length == 5 && args[0] == "check") return Kit.Check(args[1], args[2], args[3], args[4]);
    if (args.Length == 3 && args[0] == "scan") return Kit.Scan(args[1], args[2]);
    if (args.Length == 2 && args[0] == "fixture") return Kit.Fixture(args[1]);
}
catch (Kit.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: Vault111Exit build <params.json> <Starfield.esm> <FO4Port.esm> <out dir> | check <plugin> <params.json> <Starfield.esm> <FO4Port.esm> | scan <FO4Port.esm> <cell> | fixture <out dir>");
return 2;

static class Kit
{
    public class Refusal(string m) : Exception(m);

    // the script's ids (tests/test_vault111_exit.py compares)
    public const uint QuestId = 0x800, TokenId = 0x801, PickupBaseId = 0x802, TerminalBaseId = 0x803, PickupRefId = 0x804, TerminalRefId = 0x805;
    public const string QuestEdid = "FO4SF_V111Exit", TokenEdid = "FO4SF_V111PipBoyToken", PickupEdid = "FO4SF_V111PipBoyPickup", TerminalEdid = "FO4SF_V111DoorTerminal";
    public static readonly ushort[] Stages = { 5, 10, 20, 30 };
    static readonly ModKey Sf = ModKey.FromFileName("Starfield.esm"), PortKey = ModKey.FromFileName("FO4Port.esm");
    const StarfieldRelease Release = StarfieldRelease.Starfield;

    record Spot(P3Float Pos, P3Float Rot, string? Model, string? BaseEdid, string Name);
    record Params(string Plugin, string Cell, Spot Pickup, Spot Terminal, string DoorPlugin, int DoorId);

    static P3Float P3(JsonElement e) { var f = e.EnumerateArray().Select(x => x.GetSingle()).ToArray(); if (f.Length != 3) throw new Refusal("a position needs 3 numbers"); return new P3Float(f[0], f[1], f[2]); }

    static Spot ReadSpot(JsonElement e, string what)
    {
        string? Opt(string k) => e.TryGetProperty(k, out var v) && v.GetString() is { Length: > 0 } s ? s : null;
        string Str(string k) => Opt(k) ?? throw new Refusal($"{what}.{k} is missing or empty");
        var rot = e.TryGetProperty("rot", out var r) ? P3(r) : new P3Float(0, 0, 0);
        if (Opt("model") == null && Opt("base_edid") == null) throw new Refusal($"{what}.model or {what}.base_edid is needed");
        return new Spot(P3(e.GetProperty("pos")), rot, Opt("model"), Opt("base_edid"), Str("name"));
    }

    static Params Read(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var p = doc.RootElement;
        var cog = p.GetProperty("cog_door");
        var plugin = p.GetProperty("plugin").GetString()!;
        if (!plugin.EndsWith(".esm", StringComparison.OrdinalIgnoreCase)) throw new Refusal("plugin must be an .esm (the installers take .esm)");
        int id = Convert.ToInt32(cog.GetProperty("id").GetString(), 16);
        if (id <= 0 || id > 0x00FFFFFF) throw new Refusal("cog_door.id is not a plugin-local id");
        return new Params(plugin, p.GetProperty("cell").GetString()!, ReadSpot(p.GetProperty("pickup"), "pickup"), ReadSpot(p.GetProperty("terminal"), "terminal"),
                          cog.GetProperty("plugin").GetString()!, id);
    }

    static Cache<IModMasterStyledGetter, ModKey> Styles(params ModKey[] masters)
    {
        var c = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var m in masters) c.Set(new KeyedMasterStyle(m, MasterStyle.Full));
        return c;
    }

    static IStarfieldModDisposableGetter Open(string path, params ModKey[] masters) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = Styles(masters),
        });

    /// <summary>The spot's mesh: its "model", else the model of the port base named by "base_edid".</summary>
    static string ModelOf(IStarfieldModGetter port, Spot s)
    {
        if (s.Model != null) return s.Model;
        foreach (var r in port.EnumerateMajorRecords())
            if (r.EditorID == s.BaseEdid && r is IModeledGetter m && m.Model != null)
                return m.Model.File.ToString().Replace('/', '\\');
        throw new Refusal($"no base {s.BaseEdid} with a model in {port.ModKey}");
    }

    static ICellGetter FindCell(IStarfieldModGetter port, string edid) =>
        port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).FirstOrDefault(c => c.EditorID == edid)
        ?? throw new Refusal($"no CELL {edid} in {port.ModKey}");

    static Cell CellOnly(ICellGetter c)
    {
        var copy = c.DeepCopy(new Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false, Temporary = false,
            NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
        });
        copy.Persistent.Clear(); copy.Temporary.Clear(); copy.NavigationMeshes.Clear();
        return copy;
    }

    /// <summary>Mutagen stores a model path as "Meshes/<path>" with forward slashes.</summary>
    static string MeshPath(string m)
    {
        m = m.Replace('\\', '/');
        return m.StartsWith("Meshes/", StringComparison.OrdinalIgnoreCase) ? m : "Meshes/" + m;
    }

    static ScriptEntry Script(string name) => new() { Name = name, Flags = ScriptEntry.Flag.Local };

    public static int Build(string paramsPath, string sfPath, string portPath, string outDir)
    {
        var p = Read(paramsPath);
        using var sf = Open(sfPath);
        using var port = Open(portPath, Sf);
        var modKey = ModKey.FromFileName(p.Plugin);
        var mod = new StarfieldMod(modKey, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        FormKey Own(uint id) => new(modKey, id);

        var q = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "Vault 111 exit", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in Stages) q.Stages.Add(new QuestStage { Index = s });
        q.VirtualMachineAdapter = new QuestAdapter { Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3, Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local } };
        q.VirtualMachineAdapter.Scripts.Add(Script(QuestEdid));
        mod.Quests.Add(q);

        mod.MiscItems.Add(new MiscItem(Own(TokenId), Release) { EditorID = TokenEdid, Name = "Pip-Boy 3000 Mark IV", Value = 0, Weight = 0 });

        StarfieldActivator Acti(uint id, string edid, Spot s, ScriptEntry script)
        {
            var model = ModelOf(port, s);
            var a = new StarfieldActivator(Own(id), Release)
            {
                EditorID = edid, Name = s.Name, Model = new Model { File = model },
                Flags = (StarfieldActivator.Flag)0, ActivationAngle = 360,
                VirtualMachineAdapter = new VirtualMachineAdapter { Version = 6, ObjectFormat = 2 },
            };
            a.VirtualMachineAdapter.Scripts.Add(script);
            return a;
        }
        var terminalScript = Script(TerminalEdid);
        terminalScript.Properties.Add(new ScriptIntProperty { Name = "CogDoorId", Flags = ScriptProperty.Flag.Edited, Data = p.DoorId });
        terminalScript.Properties.Add(new ScriptStringProperty { Name = "DoorPlugin", Flags = ScriptProperty.Flag.Edited, Data = p.DoorPlugin });
        mod.Activators.Add(Acti(PickupBaseId, PickupEdid, p.Pickup, Script(PickupEdid)));
        mod.Activators.Add(Acti(TerminalBaseId, TerminalEdid, p.Terminal, terminalScript));

        var c0 = FindCell(port, p.Cell);
        var cell = CellOnly(c0);
        PlacedObject Ref(uint id, string edid, uint baseId, Spot s) => new(Own(id), Release)
        {
            EditorID = edid, Base = new FormLinkNullable<IPlaceableObjectGetter>(Own(baseId)), Position = s.Pos, Rotation = s.Rot,
        };
        cell.Temporary.Add(Ref(PickupRefId, "FO4SF_V111PipBoyPickupREF", PickupBaseId, p.Pickup));
        cell.Temporary.Add(Ref(TerminalRefId, "FO4SF_V111DoorTerminalREF", TerminalBaseId, p.Terminal));
        var n = cell.FormKey.ID;
        var block = new CellBlock { BlockNumber = (int)(n % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((n / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);

        mod.ModHeader.Stats.NextFormID = PickupRefId + 2;
        foreach (var m in new[] { Sf, PortKey }) if (!mod.ModHeader.MasterReferences.Any(r => r.Master == m)) mod.ModHeader.MasterReferences.Add(new MasterReference { Master = m });

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, modKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, modKey.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(Sf, PortKey)
                .WithKnownMasters(new KeyedMasterStyle(Sf, MasterStyle.Full), new KeyedMasterStyle(PortKey, MasterStyle.Full))
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally { if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true); }
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): pickup model {ModelOf(port, p.Pickup)}, terminal model {ModelOf(port, p.Terminal)}, cell {cell.FormKey} {p.Cell}, pickup at {p.Pickup.Pos}, terminal at {p.Terminal.Pos}, cog door {p.DoorPlugin}:{p.DoorId:X6}");
        return 0;
    }

    public static int Check(string pluginPath, string paramsPath, string sfPath, string portPath)
    {
        var p = Read(paramsPath);
        using var sf = Open(sfPath);
        using var port = Open(portPath, Sf);
        var modKey = ModKey.FromFileName(p.Plugin);
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = Styles(Sf, PortKey),
        });
        var bad = new List<string>();
        void Need(bool ok, string what) { if (!ok) bad.Add(what); }
        FormKey Own(uint id) => new(modKey, id);

        Need((mod.ModHeader.Flags & StarfieldModHeader.HeaderFlag.Master) != 0, "the plugin has no master flag");
        Need(mod.ModKey == modKey, $"file is {mod.ModKey}, params say {modKey}");
        Need(mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).SequenceEqual(new[] { "Starfield.esm", "FO4Port.esm" }),
             "masters are not exactly Starfield.esm, FO4Port.esm: " + string.Join(", ", mod.ModHeader.MasterReferences.Select(m => m.Master)));
        var quest = mod.Quests.SingleOrDefault();
        Need(mod.Quests.Count == 1 && quest!.FormKey == Own(QuestId) && quest.EditorID == QuestEdid, "the one QUST is not FO4SF_V111Exit at 0x800");
        Need(quest != null && quest.Stages.Select(s => s.Index).SequenceEqual(Stages), "quest stages are not 5 10 20 30");
        Need(quest?.VirtualMachineAdapter?.Scripts.Count == 1 && quest.VirtualMachineAdapter.Scripts[0].Name == QuestEdid && quest.VirtualMachineAdapter.Scripts[0].Properties.Count == 0,
             "the quest script is not FO4SF_V111Exit with no properties");
        Need(mod.MiscItems.Count == 1 && mod.MiscItems.First().FormKey == Own(TokenId), "the one MISC is not the token at 0x801");
        Need(mod.Activators.Count == 2, "there are not exactly 2 ACTI");
        foreach (var (id, edid, spot) in new[] { (PickupBaseId, PickupEdid, p.Pickup), (TerminalBaseId, TerminalEdid, p.Terminal) })
        {
            var a = mod.Activators.FirstOrDefault(x => x.FormKey == Own(id));
            Need(a != null && a.EditorID == edid, $"no ACTI {edid} at {id:X}");
            Need(a?.Model?.File.ToString() == MeshPath(ModelOf(port, spot)), $"{edid} model is {a?.Model?.File}, not {ModelOf(port, spot)}");
            Need(a?.VirtualMachineAdapter?.Scripts.Count == 1 && a.VirtualMachineAdapter.Scripts[0].Name == edid, $"{edid} has not exactly its own script");
        }
        var ts = mod.Activators.FirstOrDefault(x => x.FormKey == Own(TerminalBaseId))?.VirtualMachineAdapter?.Scripts.FirstOrDefault();
        Need(ts?.Properties.OfType<IScriptIntPropertyGetter>().Any(x => x.Name == "CogDoorId" && x.Data == p.DoorId) == true, "terminal CogDoorId differs from params");
        Need(ts?.Properties.OfType<IScriptStringPropertyGetter>().Any(x => x.Name == "DoorPlugin" && x.Data == p.DoorPlugin) == true, "terminal DoorPlugin differs from params");
        var c0 = FindCell(port, p.Cell);
        Need(mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Count() == 1, "there is not exactly 1 CELL");
        var cell = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).FirstOrDefault();
        Need(cell != null && cell.FormKey == c0.FormKey, $"the CELL override is {cell?.FormKey}, the port's {p.Cell} is {c0.FormKey}");
        Need(cell != null && cell.Persistent.Count == 0 && cell.Temporary.Count == 2, "the cell override does not hold exactly 2 temporary children");
        foreach (var (id, baseId, spot) in new[] { (PickupRefId, PickupBaseId, p.Pickup), (TerminalRefId, TerminalBaseId, p.Terminal) })
        {
            var r = cell?.Temporary.OfType<IPlacedObjectGetter>().FirstOrDefault(x => x.FormKey == Own(id));
            Need(r != null && r.Base.FormKey == Own(baseId), $"REFR {id:X} is missing or on another base");
            Need(r != null && r.Position.Equals(spot.Pos), $"REFR {id:X} is not at {spot.Pos}");
            Need(r != null && (r.MajorRecordFlagsRaw & 0x400) == 0, $"REFR {id:X} is persistent (the kit's refs are temporary)");
        }
        foreach (var b in bad) Console.Error.WriteLine("MISMATCH " + b);
        if (bad.Count == 0) Console.WriteLine($"ok {pluginPath}: quest, token, 2 activators, {p.Cell} override with 2 temporary refs, masters exact");
        return bad.Count == 0 ? 0 : 1;
    }

    public static int Scan(string portPath, string cellEdid)
    {
        using var port = Open(portPath, Sf);
        var cell = FindCell(port, cellEdid);
        var bases = new Dictionary<FormKey, (string Edid, string Model)>();
        foreach (var r in port.EnumerateMajorRecords())
            if (r is IModeledGetter m && r.EditorID != null) bases[r.FormKey] = (r.EditorID, m.Model?.File.ToString() ?? "");
        int n = 0;
        foreach (var r in cell.Persistent.Concat(cell.Temporary).OfType<IPlacedObjectGetter>())
        {
            if (!bases.TryGetValue(r.Base.FormKey, out var b)) continue;
            if (!new[] { "pipboy", "console", "terminal", "geardoor" }.Any(k => b.Edid.Contains(k, StringComparison.OrdinalIgnoreCase))) continue;
            Console.WriteLine($"ref {r.FormKey.ID:X6} {(r.MajorRecordFlagsRaw & 0x400) != 0} base {b.Edid} model {b.Model} pos {r.Position} rot {r.Rotation}");
            n++;
        }
        Console.WriteLine($"{n} references in {cellEdid} {cell.FormKey}");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        new StarfieldMod(Sf, Release) { ModHeader = { Flags = StarfieldModHeader.HeaderFlag.Master } }
            .BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        var port = new StarfieldMod(PortKey, Release);
        port.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var cell = new Cell(new FormKey(PortKey, 0x001234), Release) { EditorID = "FO4Port_Vault111Cryo", Name = "Vault 111" };
        var n = cell.FormKey.ID;
        var block = new CellBlock { BlockNumber = (int)(n % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((n / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell); block.SubBlocks.Add(sub); port.Cells.Records.Add(block);
        port.Statics.Add(new Static(new FormKey(PortKey, 0x001616), Release) { EditorID = "FO4Port_FixturePipboyGround", Model = new Model { File = "Meshes\\fixture\\pipboyground.nif" } });
        port.Statics.Add(new Static(new FormKey(PortKey, 0x00138B), Release) { EditorID = "FO4Port_FixtureConsole", Model = new Model { File = "Meshes\\fixture\\console.nif" } });
        port.ModHeader.MasterReferences.Add(new MasterReference { Master = Sf });
        port.BeginWrite.ToPath(Path.Combine(outDir, "FO4Port.esm")).WithLoadOrder(Sf)
            .WithKnownMasters(new KeyedMasterStyle(Sf, MasterStyle.Full)).WithMastersListContent(MastersListContentOption.NoCheck).Write();
        File.WriteAllText(Path.Combine(outDir, "params.json"), JsonSerializer.Serialize(new
        {
            plugin = "FO4SFVault111Exit.esm", cell = "FO4Port_Vault111Cryo",
            pickup = new { pos = new[] { 10.5f, 20.25f, 1.5f }, rot = new[] { 0f, 0f, 0.5f }, base_edid = "FO4Port_FixturePipboyGround", name = "Pip-Boy" },
            terminal = new { pos = new[] { 30f, 40f, 1.25f }, rot = new[] { 0f, 0f, 1f }, base_edid = "FO4Port_FixtureConsole", name = "Door control" },
            cog_door = new { plugin = "FO4Port.esm", id = "000C0D" },
        }));
        Console.WriteLine($"wrote {outDir}/Starfield.esm, FO4Port.esm, params.json");
        return 0;
    }
}
