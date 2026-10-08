using System.Text.Json;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Noggog;

var modKey = ModKey.FromNameAndExtension("Synthetic.esm");
FormKey Key(uint id) => new(modKey, id);
void Require(bool condition, string message)
{
    if (!condition) throw new InvalidOperationException(message);
}
var r = new PlacedObject(Key(0x801), Fallout4Release.Fallout4)
{
    MajorRecordFlagsRaw = 0x800 | 0x400,
    Position = new P3Float(70, 140, 210), Rotation = new P3Float(0, 0, 1),
    Scale = 2, OpenByDefault = true,
    EnableParent = new EnableParent { Flags = (EnableParent.Flag)1 },
    TeleportDestination = new TeleportDestination { Position = new P3Float(1, 2, 3), Flags = (TeleportDestination.Flag)1 },
    Ownership = new Ownership { NoCrime = true },
    Lock = new LockData { Level = (LockLevel)25, Flags = (LockData.Flag)1 },
};
r.Base.SetTo(Key(0x802));
r.Ownership.Owner.SetTo(Key(0x808));
r.Lock.Key.SetTo(Key(0x809));
r.EnableParent.Reference.SetTo(Key(0x803));
r.TeleportDestination.Door.SetTo(Key(0x804));
r.TeleportDestination.TransitionInterior.SetTo(Key(0x805));
var link = new LinkedReferences();
link.KeywordOrReference.SetTo(Key(0x806));
link.Reference.SetTo(Key(0x807));
r.LinkedReferences.Add(link);
using var json = JsonDocument.Parse(JsonSerializer.Serialize(ReferenceExport.Build(r, "Door", "SyntheticDoor", "synthetic.nif", true)));
var o = json.RootElement;
Require(o.GetProperty("type").GetString() == "Door", "original base type lost");
Require(o.GetProperty("base_formkey").GetString() == Key(0x802).ToString(), "base identity lost");
Require(o.GetProperty("disabled").GetInt32() == 0x800, "disabled compatibility changed");
Require(o.GetProperty("record_flags").GetInt32() == 0xC00, "raw flags lost");
Require(o.GetProperty("persistent").GetBoolean(), "persistent placement lost");
Require(o.GetProperty("open_by_default").GetBoolean(), "open state lost");
Require(o.GetProperty("pos")[0].GetSingle() == 70 && o.GetProperty("scale").GetSingle() == 2, "source units/scale changed");
Require(o.GetProperty("enable_parent").GetProperty("reference").GetString() == Key(0x803).ToString(), "enable parent lost");
Require(o.GetProperty("linked_references")[0].GetProperty("reference").GetString() == Key(0x807).ToString(), "linked reference lost");
Require(o.GetProperty("teleport_destination").GetProperty("door").GetString() == Key(0x804).ToString(), "teleport target lost");
Require(o.GetProperty("ownership").GetProperty("owner").GetString() == Key(0x808).ToString(), "ownership lost");
Require(o.GetProperty("lock_data").GetProperty("key").GetString() == Key(0x809).ToString(), "lock key lost");
var empty = new PlacedObject(Key(0x900), Fallout4Release.Fallout4);
using var absent = JsonDocument.Parse(JsonSerializer.Serialize(ReferenceExport.Build(empty, "?", "", "", false)));
Require(absent.RootElement.GetProperty("base_formkey").ValueKind == JsonValueKind.Null, "null base invented");
Require(absent.RootElement.GetProperty("enable_parent").ValueKind == JsonValueKind.Null, "null parent invented");
Require(absent.RootElement.GetProperty("linked_references").GetArrayLength() == 0, "empty links invented");
Require(absent.RootElement.GetProperty("scale").GetSingle() == 1, "default scale changed");
var actor = new PlacedNpc(Key(0xA00), Fallout4Release.Fallout4) { Position = new P3Float(10, 20, 30), MajorRecordFlagsRaw = 0x800 };
actor.Base.SetTo(Key(0xA01));
using var actorJson = JsonDocument.Parse(JsonSerializer.Serialize(ReferenceExport.BuildActor(actor, true)));
Require(actorJson.RootElement.GetProperty("base_formkey").GetString() == Key(0xA01).ToString(), "deferred actor base lost");
Require(actorJson.RootElement.GetProperty("pos")[1].GetSingle() == 20, "deferred actor position lost");
Require(actorJson.RootElement.GetProperty("disabled").GetInt32() == 0x800, "deferred actor flags lost");
Console.WriteLine("Reference export synthetic relationship/state checks passed.");
var keyword = new Keyword(Key(0xB00), Fallout4Release.Fallout4)
    { EditorID = "SyntheticLink", Type = Keyword.TypeEnum.None, Color = System.Drawing.Color.FromArgb(10, 20, 30), Name = "Synthetic name" };
using var keywordJson = JsonDocument.Parse(JsonSerializer.Serialize(KeywordExport.Build(keyword)));
Require(keywordJson.RootElement.GetProperty("formkey").GetString() == keyword.FormKey.ToString(), "keyword identity lost");
Require(keywordJson.RootElement.GetProperty("type").GetString() == "None" && keywordJson.RootElement.GetProperty("color")[1].GetInt32() == 20, "keyword metadata changed");
Require(keywordJson.RootElement.GetProperty("name").GetString() == "Synthetic name", "keyword name lost");
