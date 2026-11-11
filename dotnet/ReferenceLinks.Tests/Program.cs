using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

if (args.SequenceEqual(new[] { "--linked-references-only" }))
{
    LinkedReferenceTests.Run();
    return;
}
if (args.SequenceEqual(new[] { "--activation-only" }))
{
    ActivationParentTests.Run();
    return;
}
if (args.SequenceEqual(new[] { "--locks-only" }))
{
    LockTests.Run();
    return;
}
if (args.SequenceEqual(new[] { "--missing-door-cells-only" }))
{
    MissingDoorEndpointTests.Run(cellsOnly: true);
    return;
}

void Require(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
foreach (var bit in new[] { 1, 2 })
    Require(Enum.GetName(typeof(Mutagen.Bethesda.Fallout4.EnableParent.Flag), bit) == Enum.GetName(typeof(EnableParent.Flag), bit), "enable-parent flag semantics differ between games");
foreach (var bit in new[] { 1, 2, 4 })
    Require(Enum.GetName(typeof(Mutagen.Bethesda.Fallout4.TeleportDestination.Flag), bit) == Enum.GetName(typeof(TeleportDestination.Flag), bit), "teleport flag semantics differ between games");
var modKey = ModKey.FromNameAndExtension("Synthetic.esm");
FormKey Key(uint id) => new(modKey, id);
var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
var door = new Door(Key(0x900), StarfieldRelease.Starfield);
mod.Doors.Add(door);
var child = new PlacedObject(Key(0x810), StarfieldRelease.Starfield);
var parent = new PlacedObject(Key(0x811), StarfieldRelease.Starfield);
child.Base.SetTo(door.FormKey); parent.Base.SetTo(door.FormKey);
var first = new Cell(Key(0x800), StarfieldRelease.Starfield) { EditorID = "FO4Port_First", Flags = Cell.Flag.IsInteriorCell };
var second = new Cell(Key(0x801), StarfieldRelease.Starfield) { EditorID = "FO4Port_Second", Flags = Cell.Flag.IsInteriorCell };
first.Temporary.Add(child); second.Temporary.Add(parent);
var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
sub.Cells.Add(first); sub.Cells.Add(second); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
var ids = new Dictionary<string, uint> { ["CELL:FO4Port_First"] = 0x800, ["CELL:FO4Port_Second"] = 0x801,
    ["REFR:FO4Port_First:child"] = 0x810, ["REFR:FO4Port_Second:parent"] = 0x811 };
using var one = JsonDocument.Parse("""
{"cell":"First","formkey":"first-cell","refs":[{"formkey":"child","persistent":true,"open_by_default":true,
 "enable_parent":{"reference":"parent","flags":1},
 "linked_references":[{"reference":"parent","keyword_or_reference":null}],
 "teleport_destination":{"door":"parent","transition_interior":"second-cell","flags":2,"pos":[70,140,210],"rot":[0,0,1]}}]}
""");
using var two = JsonDocument.Parse("""
{"cell":"Second","formkey":"second-cell","refs":[{"formkey":"parent","persistent":false}]}
""");
var sources = new[] { one.RootElement, two.RootElement };
using var refusedTeleport = JsonDocument.Parse("""
{"cell":"First","refs":[{"formkey":"child","persistent":false,
 "teleport_destination":{"door":"parent","transition_interior":null,"flags":4,"pos":[70,140,210],"rot":[0,0,1]}}]}
""");
var refused = Relationships.Apply(mod, ids, new[] { refusedTeleport.RootElement, two.RootElement });
Require(refused.Issues.Count == 1 && refused.Teleports == 0 && child.TeleportDestination == null,
    "relative-position teleport should be refused before mutation");
Require(first.Temporary.Contains(child) && second.Temporary.Contains(parent) && first.Persistent.Count == 0 && second.Persistent.Count == 0 &&
    (child.MajorRecordFlagsRaw & 0x400) == 0 && (parent.MajorRecordFlagsRaw & 0x400) == 0,
    "refused teleport changed endpoint persistence");
var report = Relationships.Apply(mod, ids, sources);
Require(report.Issues.Count == 0, "valid cross-cell links rejected");
Require(report.EnableParents == 1 && report.LinkedReferences == 1 && report.Teleports == 1, "expected relationships missing");
Require(first.Persistent.Contains(child) && !first.Temporary.Contains(child) && (child.MajorRecordFlagsRaw & 0x400) != 0, "persistent grouping/flag not preserved");
Require(child.EnableParent!.Reference.FormKey == parent.FormKey && (uint)child.EnableParent.Flags == 1, "enable-parent identity/flags changed");
Require(child.OpenByDefault, "default-open state not preserved");
Require(child.TeleportDestination!.Door.FormKey == parent.FormKey && child.TeleportDestination.TransitionInterior.FormKey == second.FormKey, "cross-cell teleport identities wrong");
Require(child.TeleportDestination.Position.X == 1 && child.TeleportDestination.Position.Y == 2 && child.TeleportDestination.Rotation.Z == 1, "teleport units/rotation changed");
Require(second.Persistent.Contains(parent) && !second.Temporary.Contains(parent) && (parent.MajorRecordFlagsRaw & 0x400) != 0,
    "one-way teleport destination was not made persistent");
Relationships.Apply(mod, ids, sources);
Require(child.LinkedReferences.Count == 1, "reapplying duplicates linked references");
Require(first.Persistent.Count == 1 && second.Persistent.Count == 1, "reapplying duplicates persistent endpoints");

// Reserved IDs alone must not resolve missing records; they persist after removal.
ids["REFR:FO4Port_Second:absent"] = 0x812;
using var bad = JsonDocument.Parse("""
{"cell":"First","formkey":"first-cell","refs":[{"formkey":"child","enable_parent":{"reference":"absent","flags":0},
 "linked_references":[{"reference":"parent","keyword_or_reference":"unmapped-keyword"}]}]}
""");
var unresolved = Relationships.Apply(mod, ids, new[] { bad.RootElement, two.RootElement });
Require(unresolved.Issues.Count == 2, "missing parent or unmapped keyword silently accepted");
Require(child.EnableParent.Reference.FormKey == parent.FormKey, "failed resolution overwrote existing valid parent");
Require(child.LinkedReferences.Count == 1, "unsupported union created a guessed link");
using var markerChild = JsonDocument.Parse("""
{"cell":"First","formkey":"first-cell","refs":[{"formkey":"child","enable_parent":{"reference":"marker","flags":1}}]}
""");
using var markerSource = JsonDocument.Parse("""
{"cell":"Second","formkey":"second-cell","refs":[{"formkey":"parent"},
 {"formkey":"marker","type":"Static","base_editor_id":"EnableMarker","pos":[70,0,0],"rot":[0,0,0],"scale":1,"persistent":true,"disabled":2048}]}
""");
var starfield = ModKey.FromNameAndExtension("Starfield.esm");
var markerBases = new Dictionary<string, FormKey> { ["EnableMarker"] = new(starfield, 0x10D8D) };
var markerExports = new[] { markerChild.RootElement, markerSource.RootElement };
var markerReport = Relationships.Apply(mod, ids, markerExports, markerBases);
Require(markerReport.CreatedMarkers == 1 && markerReport.EnableParents == 1 && markerReport.Issues.Count == 0, "needed control marker not created/linked");
var markerKey = child.EnableParent!.Reference.FormKey;
var marker = second.Persistent.OfType<PlacedObject>().Single(r => r.FormKey == markerKey);
Require(marker.FormKey == markerKey && marker.Position.X == 1 && (marker.MajorRecordFlagsRaw & 0x800) != 0, "marker identity/units/disabled state lost");
var stable = ids["REFR:FO4Port_Second:marker"];
Require(stable > door.FormKey.ID, "new marker could collide with plugin records omitted from input map");
Relationships.Apply(mod, ids, markerExports, markerBases);
Require(ids["REFR:FO4Port_Second:marker"] == stable && second.Persistent.Count == 2, "reapplying changed marker identity or duplicated it");
using var keywordSource = JsonDocument.Parse("""
{"cell":"First","formkey":"first-cell","refs":[{"formkey":"child","linked_references":[{"reference":"parent","keyword_or_reference":"keyword-source"}]}],
 "referenced_keywords":[{"formkey":"keyword-source","editor_id":"SyntheticLink","type":"None","type_value":0,"record_flags":0,"color":[7,8,9],"attraction_rule":null,"name":"Synthetic label","notes":"Link note"}]}
""");
var keywordSources = new[] { keywordSource.RootElement, two.RootElement };
var keywordReport = Relationships.Apply(mod, ids, keywordSources);
Require(keywordReport.CreatedKeywords == 1 && keywordReport.LinkedReferences == 1 && keywordReport.Issues.Count == 0, "generic linked keyword was not translated");
var keywordKey = new FormKey(modKey, ids["KYWD:keyword-source"]);
Require(child.LinkedReferences.Any(l => l.KeywordOrReference.FormKey == keywordKey && l.Reference.FormKey == parent.FormKey), "keyword discriminator identity lost");
Require(mod.Keywords.Single().Color!.Value.G == 8, "keyword color metadata lost");
Require(mod.Keywords.Single().Name!.String == "Synthetic label" && mod.Keywords.Single().Notes == "Link note", "keyword label or notes lost");
Relationships.Apply(mod, ids, keywordSources);
Require(mod.Keywords.Count == 1 && child.LinkedReferences.Count == 2, "reapplying duplicates keyword or keyworded link");
using var specialized = JsonDocument.Parse("""
{"cell":"First","refs":[{"formkey":"child","linked_references":[{"reference":"parent","keyword_or_reference":"special"}]}],
 "referenced_keywords":[{"formkey":"special","editor_id":"QuestCategory","type":"QuestTarget","type_value":12,"record_flags":0,"color":null,"attraction_rule":null}]}
""");
var rejected = Relationships.Apply(mod, ids, new[] { specialized.RootElement, two.RootElement });
Require(rejected.Issues.Any(x => x.Field == "keyword") && !ids.ContainsKey("KYWD:special"), "specialized semantics were silently flattened into a generic keyword");
var directory = Path.Combine(Path.GetTempPath(), "fo4sf-links-" + Guid.NewGuid().ToString("N"));
using var volumeChild = JsonDocument.Parse("""
{"cell":"First","refs":[{"formkey":"child","enable_parent":{"reference":"volume","flags":1}}]}
""");
using var volumeSource = JsonDocument.Parse("""
{"cell":"Second","refs":[{"formkey":"volume","type":"Static","base_editor_id":"LightBox","pos":[0,70,0],"rot":[0,0,1],"primitive":{"bounds":[70,140,210],"color":[10,20,30,40],"unknown":0.3,"type":"Box","type_value":1}}]}
""");
var volumeBases = new Dictionary<string, FormKey> { ["LightBox"] = new(starfield, 0x1F7) };
using var missingVolume = JsonDocument.Parse("""
{"cell":"Second","refs":[{"formkey":"volume","type":"Static","base_editor_id":"LightBox","pos":[0,70,0],"rot":[0,0,1]}]}
""");
var missingVolumeReport = Relationships.Apply(mod, ids, new[] { volumeChild.RootElement, missingVolume.RootElement }, volumeBases);
Require(missingVolumeReport.Issues.Any(i => i.Field == "primitive") && !ids.ContainsKey("REFR:FO4Port_Second:volume"), "missing volume geometry created a guessed helper");
var volumeReport = Relationships.Apply(mod, ids, new[] { volumeChild.RootElement, volumeSource.RootElement }, volumeBases);
Require(volumeReport.CreatedMarkers == 1 && volumeReport.Issues.Count == 0, "LightBox not restored");
var volumeKey = child.EnableParent!.Reference.FormKey;
var restoredVolume = second.Temporary.OfType<PlacedObject>().Single(r => r.FormKey == volumeKey);
Require(restoredVolume.Primitive!.Bounds.Y == 2 && restoredVolume.Primitive.Color.A == 40 && restoredVolume.Rotation.Z == 1, "LightBox geometry/alpha/rotation lost");
// Restore the prior parent used by the existing binary assertions.
Relationships.Apply(mod, ids, markerExports, markerBases);
// Activation parents are preserved by Fo4Export, but are not translated here.
var priorLinks = child.LinkedReferences.Count;
var priorParent = child.EnableParent!.Reference.FormKey;
var priorBase = child.Base.FormKey;
var priorIds = new Dictionary<string, uint>(ids);
foreach (var metadata in new[] { "{\"flags\":129,\"parents\":[{\"reference\":\"parent\",\"delay\":0.1}]}",
                                "{\"flags\":0,\"parents\":[]}", "null", "absent" })
{
    var field = metadata == "absent" ? "" : ",\"activate_parents\":" + metadata;
    using var activationSource = JsonDocument.Parse(
        "{\"cell\":\"First\",\"refs\":[{\"formkey\":\"child\"" + field +
        "},{\"formkey\":\"unplaced-activation\"" + field + "}]}");
    var activationReport = Relationships.Apply(mod, ids, new[] { activationSource.RootElement });
    var issues = activationReport.Warnings.Where(i => i.Field == "activate_parents").ToArray();
    Require(!activationReport.Issues.Any(i => i.Field == "activate_parents"), "activation metadata blocks default output");
    if (metadata is "null" or "absent")
        Require(issues.Length == 0, "absent activation metadata invented a warning");
    else
        Require(issues.Length == 2 && issues.Select(i => i.Source).ToHashSet().SetEquals(new[] { "child", "unplaced-activation" }) &&
                issues.All(i => i.Target == null && i.Reason.Contains("translation not implemented")),
                "placed/unplaced activation metadata silently dropped or claimed translated");
    Require(activationReport.LinkedReferences == 0 && activationReport.EnableParents == 0 &&
            child.LinkedReferences.Count == priorLinks && child.EnableParent!.Reference.FormKey == priorParent &&
            child.Base.FormKey == priorBase && ids.Count == priorIds.Count && priorIds.All(i => ids[i.Key] == i.Value),
            "unsupported activation parents changed native links, bases or identities");
}
Directory.CreateDirectory(directory);
try
{
    var path = Path.Combine(directory, "Synthetic.esm");
    mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(directory)
        .WithKnownMasters(new KeyedMasterStyle(starfield, MasterStyle.Full)).Write();
    var read = PluginReader.Read(path);
    var cell = read.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).First(c => c.FormKey == first.FormKey);
    var written = cell.Persistent.OfType<IPlacedObjectGetter>().Single();
    Require(written.EnableParent!.Reference.FormKey == markerKey, "enable-parent lost in binary output");
    Require(written.TeleportDestination!.Position.Z == 3 && written.OpenByDefault, "door state lost in binary output");
    Require(written.LinkedReferences.Count == 2 && written.LinkedReferences.Any(l => l.KeywordOrReference.FormKey == keywordKey), "keyworded linked reference lost in binary output");
    Require(read.Keywords.Single().Color!.Value.G == 8, "keyword metadata lost in binary output");
    Require(read.Keywords.Single().Name!.String == "Synthetic label", "keyword name lost in binary output");
    var writtenVolume = read.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
        .SelectMany(c => c.Temporary).OfType<IPlacedObjectGetter>().Single(r => r.FormKey == volumeKey);
    Require(writtenVolume.Primitive!.Bounds.Z == 3 && writtenVolume.Primitive.Color.G == 20, "LightBox volume lost in binary output");
}
finally { Directory.Delete(directory, true); }
Console.WriteLine("Relationship translation and binary round-trip synthetic checks passed.");
NativeDoorBaseTests.Run();
MissingDoorEndpointTests.Run();
ActivationParentTests.Run();
LockTests.Run();
LinkedReferenceTests.Run();
