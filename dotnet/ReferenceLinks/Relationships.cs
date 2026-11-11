using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Starfield;
using Noggog;

public sealed record LinkIssue(string Source, string Field, string? Target, string Reason);
public sealed class LinkReport
{
    public int Persistent { get; set; }
    public int EnableParents { get; set; }
    public int LinkedReferences { get; set; }
    public int Teleports { get; set; }
    public int OpenState { get; set; }
    public int Locks { get; set; }
    public int CreatedMarkers { get; set; }
    public int CreatedDoors { get; set; }
    public int CreatedKeywords { get; set; }
    public int UnplacedSourceReferences { get; set; }
    public List<LinkIssue> Issues { get; } = new();
    public List<LinkIssue> Warnings { get; } = new();
}

public static class Relationships
{
    // FO4 XLOC lock levels written unchanged. The values and names come from Mutagen 0.55.0-alpha.67's
    // Fallout4.LockLevel; Starfield.LockLevel has the same name at each of these values (checked in Apply and by
    // ReferenceLinks.Tests against the Fallout 4 enum). Not verified in game.
    public static readonly IReadOnlyDictionary<int, string> LockLevels = new Dictionary<int, string>
    {
        [0] = "None", [1] = "Novice1", [25] = "Novice25", [50] = "Advanced", [75] = "Expert", [100] = "Master", [255] = "RequiresKey",
    };
    // Same names exist in both enums, but each depends on something this pass does not translate, so the
    // lock would shut a door nothing in the port can open. Reported as warnings, never written.
    public static readonly IReadOnlyDictionary<int, string> RefusedLockLevels = new Dictionary<int, string>
    {
        [251] = "Barred: opened by activation from one side; activation is not translated",
        [252] = "Chained: opened by activation from one side; activation is not translated",
        [253] = "RequiresTerminal: FO4 terminals are not translated",
        [254] = "Inaccessible: whatever unlocks it in FO4 (scripts, quests) is not translated",
    };

    public static LinkReport Apply(StarfieldMod mod, Dictionary<string, uint> ids, IEnumerable<JsonElement> exports,
        IReadOnlyDictionary<string, FormKey>? markerBases = null, IStarfieldModGetter? doorMaster = null,
        IReadOnlyDictionary<string, FormKey>? missingDoorBases = null)
    {
        if (ids.Values.Any(id => id == 0 || id >= 0x1000000) || ids.Values.Distinct().Count() != ids.Count)
            throw new InvalidOperationException("source map contains duplicate or invalid full-plugin FormIDs");
        var report = new LinkReport();
        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToDictionary(c => c.FormKey);
        var placed = cells.Values.SelectMany(c => c.Temporary.Concat(c.Persistent)).OfType<PlacedObject>().ToDictionary(r => r.FormKey);
        var ownerCells = cells.Values.SelectMany(c => c.Temporary.Concat(c.Persistent).OfType<PlacedObject>()
            .Select(r => (r.FormKey, Cell: c))).ToDictionary(x => x.FormKey, x => x.Cell);
        var sourceRefs = new Dictionary<string, PlacedObject>(StringComparer.OrdinalIgnoreCase);
        var sourceCells = new Dictionary<string, Cell>(StringComparer.OrdinalIgnoreCase);
        var sources = exports.ToArray();
        // Source presence is separate from successful placement. Keep the exact
        // map identity so a reservation occupied by a different record kind is
        // never mistaken for an ordinary unconverted reference (#416).
        var exportedReferences = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var reservedReferences = new Dictionary<string, uint>(StringComparer.OrdinalIgnoreCase);
        foreach (var (identity, id) in ids.Where(pair => pair.Key.StartsWith("REFR:", StringComparison.OrdinalIgnoreCase)))
        {
            if (reservedReferences.TryGetValue(identity, out var prior) && prior != id)
                throw new InvalidOperationException($"conflicting source reference reservation {identity}");
            reservedReferences[identity] = id;
        }
        foreach (var export in sources)
        foreach (var reference in export.GetProperty("refs").EnumerateArray())
        {
            var source = reference.GetProperty("formkey").GetString()!;
            var identity = $"REFR:FO4Port_{export.GetProperty("cell").GetString()}:{source}";
            if (!exportedReferences.TryAdd(source, identity))
                throw new InvalidOperationException($"duplicate source reference {source}");
        }
        // Resolve record type from actual records, not an editor ID or a numeric
        // base link. Any local override wins, including deletion/type changes.
        var localRecords = mod.EnumerateMajorRecords().ToDictionary(r => r.FormKey);
        var doorBases = mod.Doors.Where(d => (d.MajorRecordFlagsRaw & 0x20) == 0).Select(d => d.FormKey).ToHashSet();
        if (doorMaster != null)
            foreach (var door in doorMaster.Doors)
                if (!localRecords.ContainsKey(door.FormKey) && (door.MajorRecordFlagsRaw & 0x20) == 0)
                    doorBases.Add(door.FormKey);
        var occupied = localRecords.Keys.Where(k => k.ModKey == mod.ModKey).Select(k => k.ID).ToHashSet();
        var next = ids.Values.Concat(occupied).DefaultIfEmpty(0x7FFu).Max() + 1;
        // Key identities by parsed FormKey (00A123:Fallout4.esm == 00a123:fallout4.esm; Codex on #375). Two spellings of one
        // source key reserved at different IDs corrupt the map: refused before any change, like the duplicate-ID check
        // above, so --allow-unresolved cannot publish it. A key that is merely missing stays a warning (below).
        var keyIds = new Dictionary<FormKey, uint>();
        foreach (var (identity, id) in ids)
        {
            if (!identity.StartsWith("KEYM:", StringComparison.Ordinal)) continue;
            if (!FormKey.TryFactory(identity.Substring(5), out var fk) || fk.IsNull)
                throw new InvalidOperationException("source map has an invalid key identity: " + identity);   // as Codex's #384
            if (keyIds.TryGetValue(fk, out var prior) && prior != id)
                throw new InvalidOperationException($"source map reserves key {fk} at two target IDs ({prior:X6}, {id:X6}) under differently spelled identities");
            keyIds[fk] = id;
        }
        // Explicit source-reference selections only: never infer a replacement
        // from a marker filename or silently replace an already placed base.
        var selectedDoors = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        if (missingDoorBases != null)
        {
            var allRefs = sources.SelectMany(e => e.GetProperty("refs").EnumerateArray()
                .Select(r => (Export: e, Reference: r))).ToArray();
            foreach (var selection in missingDoorBases)
            {
                if (!selectedDoors.TryAdd(selection.Key, selection.Value))
                    throw new InvalidOperationException("duplicate door source selection");
                var matches = allRefs.Where(r => string.Equals(r.Reference.GetProperty("formkey").GetString(), selection.Key, StringComparison.OrdinalIgnoreCase)).ToArray();
                if (matches.Length != 1 || !matches[0].Reference.TryGetProperty("type", out var kind) || kind.GetString() != "Door")
                    throw new InvalidOperationException("door selection requires exactly one exported Door: " + selection.Key);
                if (!doorBases.Contains(selection.Value))
                    throw new InvalidOperationException("door selection is not a resolved active DOOR: " + selection.Value);
                // An explicit endpoint request must be actionable before any
                // mutation. Partial relationship output cannot waive it.
                var cellIdentity = "CELL:FO4Port_" + matches[0].Export.GetProperty("cell").GetString();
                if (!ids.TryGetValue(cellIdentity, out var cellId) || !cells.ContainsKey(new FormKey(mod.ModKey, cellId)))
                    throw new InvalidOperationException("door selection target cell is absent: " + selection.Key + " in " + cellIdentity);
            }
        }
        var needed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var export in sources)
        foreach (var r in export.GetProperty("refs").EnumerateArray())
        {
            if (r.TryGetProperty("enable_parent", out var ep) && ep.ValueKind != JsonValueKind.Null)
                if (ep.GetProperty("reference").GetString() is string key) needed.Add(key);
            if (r.TryGetProperty("linked_references", out var lr))
                foreach (var link in lr.EnumerateArray())
                {
                    if (link.GetProperty("reference").GetString() is string key) needed.Add(key);
                    if (link.GetProperty("keyword_or_reference").GetString() is string discriminator) needed.Add(discriminator);
                }
        }
        foreach (var export in sources)
        {
            var name = "FO4Port_" + export.GetProperty("cell").GetString();
            if (!ids.TryGetValue("CELL:" + name, out var cid) || !cells.TryGetValue(new FormKey(mod.ModKey, cid), out var cell))
            {
                report.Issues.Add(new(name, "cell", null, "target cell is absent"));
                continue;
            }
            if (export.TryGetProperty("formkey", out var cellSource)) sourceCells[cellSource.GetString()!] = cell;
            foreach (var reference in export.GetProperty("refs").EnumerateArray())
            {
                var source = reference.GetProperty("formkey").GetString()!;
                var identity = $"REFR:{name}:{source}";
                ids.TryGetValue(identity, out var rid);
                placed.TryGetValue(new FormKey(mod.ModKey, rid), out var target);
                if (selectedDoors.TryGetValue(source, out var selectedBase))
                {
                    if (target != null)
                    {
                        if (target.Base.FormKey != selectedBase || ownerCells[target.FormKey] != cell ||
                            (target.MajorRecordFlagsRaw & 0x20) != 0)
                            throw new InvalidOperationException("door selection conflicts with placed reference: " + source);
                    }
                    else
                    {
                        var position = Pos(reference.GetProperty("pos"));
                        var rotation = Rot(reference.GetProperty("rot"));
                        var scale = reference.TryGetProperty("scale", out var size) ? size.GetSingle() : 1f;
                        static bool Finite(P3Float p) => float.IsFinite(p.X) && float.IsFinite(p.Y) && float.IsFinite(p.Z);
                        if (!Finite(position) || !Finite(rotation) || !float.IsFinite(scale) || scale <= 0)
                            throw new InvalidOperationException("invalid missing-door transform: " + source);
                        if (ids.ContainsKey(identity))
                        {
                            if (occupied.Contains(rid)) throw new InvalidOperationException("door reservation occupies another record: " + identity);
                        }
                        else
                        {
                            if (next >= 0x1000000) throw new InvalidOperationException("full plugin FormID space exhausted");
                            rid = next++; ids.Add(identity, rid);
                        }
                        target = new PlacedObject(new FormKey(mod.ModKey, rid), StarfieldRelease.Starfield)
                            { Position = position, Rotation = rotation };
                        target.Base.SetTo(selectedBase);
                        if (scale != 1) target.Scale = scale;
                        if (reference.TryGetProperty("disabled", out var disabledDoor) && disabledDoor.GetInt32() != 0)
                            target.MajorRecordFlagsRaw |= 0x800;
                        cell.Temporary.Add(target); placed.Add(target.FormKey, target);
                        ownerCells.Add(target.FormKey, cell); occupied.Add(rid); report.CreatedDoors++;
                    }
                    // This explicit option prepares a load-door endpoint even if
                    // its other plugin has not been linked yet. No XTEL invented.
                    MakeTeleportEndpointPersistent(target);
                }
                if (target == null && needed.Contains(source) && markerBases != null &&
                    reference.TryGetProperty("base_editor_id", out var baseId) &&
                    markerBases.TryGetValue(baseId.GetString() ?? "", out var markerBase) &&
                    reference.GetProperty("type").GetString() == "Static")
                {
                    PlacedPrimitive? primitive = null;
                    if (baseId.GetString()!.Equals("LightBox", StringComparison.OrdinalIgnoreCase))
                    {
                        if (!reference.TryGetProperty("primitive", out var volume) || volume.ValueKind == JsonValueKind.Null)
                        {
                            report.Issues.Add(new(source, "primitive", null, "LightBox requires exported volume geometry; re-export the source cell"));
                            continue;
                        }
                        var type = volume.GetProperty("type_value").GetInt32();
                        if (!Enum.IsDefined(typeof(PlacedPrimitive.TypeEnum), type) ||
                            ((PlacedPrimitive.TypeEnum)type).ToString() != volume.GetProperty("type").GetString())
                        {
                            report.Issues.Add(new(source, "primitive.type", null, "source primitive type has no verified target equivalent"));
                            continue;
                        }
                        var color = volume.GetProperty("color");
                        primitive = new PlacedPrimitive
                        {
                            Bounds = Pos(volume.GetProperty("bounds")),
                            Color = System.Drawing.Color.FromArgb(color[3].GetInt32(), color[0].GetInt32(), color[1].GetInt32(), color[2].GetInt32()),
                            Unknown = volume.GetProperty("unknown").GetSingle(), Type = (PlacedPrimitive.TypeEnum)type,
                        };
                    }
                    if (!ids.ContainsKey(identity))
                    {
                        if (next >= 0x1000000) throw new InvalidOperationException("full plugin FormID space exhausted");
                        rid = next++; ids[identity] = rid;
                    }
                    else if (occupied.Contains(rid)) throw new InvalidOperationException($"marker identity {identity} occupies another record type");
                    target = new PlacedObject(new FormKey(mod.ModKey, rid), StarfieldRelease.Starfield)
                    {
                        Position = Pos(reference.GetProperty("pos")), Rotation = Rot(reference.GetProperty("rot")),
                        Primitive = primitive,
                    };
                    target.Base.SetTo(markerBase);
                    if (reference.TryGetProperty("disabled", out var disabled) && disabled.GetInt32() != 0)
                        target.MajorRecordFlagsRaw |= 0x800;
                    if (reference.TryGetProperty("scale", out var scale) && scale.GetSingle() != 1) target.Scale = scale.GetSingle();
                    cell.Temporary.Add(target); placed.Add(target.FormKey, target);
                    ownerCells.Add(target.FormKey, cell); report.CreatedMarkers++;
                }
                if (target == null)
                {
                    report.UnplacedSourceReferences++;
                    continue;
                }
                if (!sourceRefs.TryAdd(source, target)) throw new InvalidOperationException($"duplicate source reference {source}");
                if (reference.TryGetProperty("persistent", out var persistent) && persistent.GetBoolean())
                {
                    if (cell.Temporary.Remove(target)) cell.Persistent.Add(target);
                    target.MajorRecordFlagsRaw |= 0x400;
                    report.Persistent++;
                }
            }
        }
        var usedKeywords = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var export in sources)
        foreach (var reference in export.GetProperty("refs").EnumerateArray())
            if (sourceRefs.ContainsKey(reference.GetProperty("formkey").GetString()!) && reference.TryGetProperty("linked_references", out var links))
                foreach (var link in links.EnumerateArray())
                    if (link.GetProperty("keyword_or_reference").GetString() is string key) usedKeywords.Add(key);
        var sourceKeywords = KeywordLinks.Create(mod, ids, sources, usedKeywords, occupied, ref next, report);
        mod.ModHeader.Stats.NextFormID = Math.Max(mod.ModHeader.Stats.NextFormID, next);
        PlacedObject? Resolve(string source, string field, string? key)
        {
            if (key != null && sourceRefs.TryGetValue(key, out var target)) return target;
            report.Issues.Add(new(source, field, key, "target reference was not placed"));
            return null;
        }
        PlacedObject? ResolveLinkedReference(string source, string? key)
        {
            const string field = "linked_references.reference";
            if (key != null && sourceRefs.TryGetValue(key, out var target)) return target;
            if (key != null && FormKey.TryFactory(key, out var sourceKey) && !sourceKey.IsNull &&
                exportedReferences.TryGetValue(key, out var identity))
            {
                if (reservedReferences.TryGetValue(identity, out var id) && localRecords.ContainsKey(new FormKey(mod.ModKey, id)))
                    report.Issues.Add(new(source, field, key, "target reservation is occupied by a record that is not a placed object"));
                else
                    report.Warnings.Add(new(source, field, key, $"target {key} is present in source exports but was not placed; link omitted"));
            }
            else report.Issues.Add(new(source, field, key, "target reference is absent from source exports, null or malformed"));
            return null;
        }
        static P3Float Pos(JsonElement e) => new(e[0].GetSingle() / 70f, e[1].GetSingle() / 70f, e[2].GetSingle() / 70f);
        static P3Float Rot(JsonElement e) => new(e[0].GetSingle(), e[1].GetSingle(), e[2].GetSingle());
        void MakeTeleportEndpointPersistent(PlacedObject endpoint)
        {
            // Match PluginSpike.TeleportLinks: XTEL resolution requires both
            // endpoints persistent, even if the export omitted the source flag.
            var cell = ownerCells[endpoint.FormKey];
            bool moved = cell.Temporary.Remove(endpoint);
            if (moved) cell.Persistent.Add(endpoint);
            if (moved || (endpoint.MajorRecordFlagsRaw & 0x400) == 0) report.Persistent++;
            endpoint.MajorRecordFlagsRaw |= 0x400;
        }
        void ApplyLock(string source, PlacedObject target, JsonElement data, bool isDoor)
        {
            // Doors only; a lock on any other base (containers, terminals) stays in the export.
            if (!isDoor)
            {
                report.Warnings.Add(new(source, "lock_data", null, "lock on a non-door base is not translated"));
                return;
            }
            var level = data.GetProperty("level").GetInt32();
            var flags = data.GetProperty("flags").GetUInt32();
            var sourceKey = data.TryGetProperty("key", out var keyElement) ? keyElement.GetString() : null;
            if (RefusedLockLevels.TryGetValue(level, out var refusal))
            {
                report.Warnings.Add(new(source, "lock_data.level", level.ToString(), refusal + "; lock not written"));
                return;
            }
            if (!LockLevels.TryGetValue(level, out var levelName) || Enum.GetName(typeof(LockLevel), level) != levelName)
            {
                report.Issues.Add(new(source, "lock_data.level", level.ToString(), "lock level has no verified Starfield equivalent"));
                return;
            }
            if ((flags & ~1u) != 0) // bit 1 is LeveledLock in both enums (ReferenceLinks.Tests)
            {
                report.Issues.Add(new(source, "lock_data.flags", flags.ToString(), "unsupported lock flag bits"));
                return;
            }
            Key? key = null;
            if (sourceKey != null)
            {
                // Same rule as keywords: an identity in the map AND an actual, non-deleted KEYM in the plugin.
                // FO4 keys are not converted by PluginSpike, so this normally fails; never invent a key.
                if (FormKey.TryFactory(sourceKey, out var sourceFk) && keyIds.TryGetValue(sourceFk, out var keyId))
                    key = mod.Keys.FirstOrDefault(k => k.FormKey == new FormKey(mod.ModKey, keyId) && (k.MajorRecordFlagsRaw & 0x20) == 0);
                if (key == null)
                {
                    // A warning, not an issue: keys are not converted yet, so an issue would block every real run.
                    report.Warnings.Add(new(source, "lock_data.key", sourceKey, "key does not resolve to a key record in the target plugin; lock not written"));
                    return;
                }
            }
            else if (level == 255)
            {
                report.Warnings.Add(new(source, "lock_data.key", null, "RequiresKey lock without a key would never open; lock not written"));
                return;
            }
            target.Lock = new LockData { Level = (LockLevel)level, Flags = (LockData.Flag)flags };
            if (key != null) target.Lock.Key.SetTo(key.FormKey);
            report.Locks++;
        }
        foreach (var export in sources)
        foreach (var reference in export.GetProperty("refs").EnumerateArray())
        {
            var source = reference.GetProperty("formkey").GetString()!;
            if (reference.TryGetProperty("activate_parents", out var activation) && activation.ValueKind != JsonValueKind.Null)
                report.Warnings.Add(new(source, "activate_parents", null,
                    "activation-parent flags, references and delays retained in source export; translation not implemented"));
            if (!sourceRefs.TryGetValue(source, out var target)) continue;
            if (reference.TryGetProperty("enable_parent", out var parent) && parent.ValueKind != JsonValueKind.Null)
            {
                var resolved = Resolve(source, "enable_parent", parent.GetProperty("reference").GetString());
                var flags = parent.GetProperty("flags").GetUInt32();
                if ((flags & ~3u) != 0) report.Issues.Add(new(source, "enable_parent.flags", null, "unsupported flag bits"));
                else if (resolved != null)
                {
                    target.EnableParent = new EnableParent { Flags = (EnableParent.Flag)flags };
                    target.EnableParent.Reference.SetTo(resolved.FormKey);
                    report.EnableParents++;
                }
            }
            if (reference.TryGetProperty("linked_references", out var links))
            foreach (var link in links.EnumerateArray())
            {
                var resolved = ResolveLinkedReference(source, link.GetProperty("reference").GetString());
                var discriminator = link.GetProperty("keyword_or_reference").GetString();
                PlacedObject? discriminatorTarget = null;
                Keyword? keywordTarget = null;
                if (discriminator != null && !sourceRefs.TryGetValue(discriminator, out discriminatorTarget) &&
                    !sourceKeywords.TryGetValue(discriminator, out keywordTarget))
                {
                    report.Issues.Add(new(source, "linked_references.keyword_or_reference", discriminator, "keyword/reference union target is not translated"));
                    continue;
                }
                if (resolved == null) continue;
                var translated = new LinkedReferences();
                translated.Reference.SetTo(resolved.FormKey);
                if (discriminatorTarget != null) translated.KeywordOrReference.SetTo(discriminatorTarget.FormKey);
                if (keywordTarget != null) translated.KeywordOrReference.SetTo(keywordTarget.FormKey);
                if (!target.LinkedReferences.Any(x => x.Reference.FormKey == resolved.FormKey &&
                    x.KeywordOrReference.FormKey == translated.KeywordOrReference.FormKey))
                    target.LinkedReferences.Add(translated);
                report.LinkedReferences++;
            }
            bool IsDoor(PlacedObject obj) => doorBases.Contains(obj.Base.FormKey);
            if (reference.TryGetProperty("open_by_default", out var open) && open.GetBoolean())
            {
                if (IsDoor(target)) { target.OpenByDefault = true; report.OpenState++; }
                else report.Issues.Add(new(source, "open_by_default", null, "target base is not a resolved non-deleted door"));
            }
            if (reference.TryGetProperty("lock_data", out var lockData) && lockData.ValueKind == JsonValueKind.Object)
                ApplyLock(source, target, lockData, IsDoor(target));
            if (reference.TryGetProperty("teleport_destination", out var teleport) && teleport.ValueKind != JsonValueKind.Null)
            {
                var destination = Resolve(source, "teleport_destination.door", teleport.GetProperty("door").GetString());
                var flags = teleport.GetProperty("flags").GetUInt32();
                var transitionKey = teleport.GetProperty("transition_interior").GetString();
                Cell? transition = null;
                if (transitionKey != null && !sourceCells.TryGetValue(transitionKey, out transition))
                    report.Issues.Add(new(source, "teleport_destination.transition_interior", transitionKey, "target cell was not exported/placed"));
                else if ((flags & ~7u) != 0) report.Issues.Add(new(source, "teleport_destination.flags", null, "unsupported flag bits"));
                else if ((flags & 4u) != 0) report.Issues.Add(new(source, "teleport_destination.flags", null, "relative-position teleport needs door-origin conversion; not implemented"));
                else if (destination != null)
                {
                    if (!IsDoor(target) || !IsDoor(destination))
                    {
                        report.Issues.Add(new(source, "teleport_destination", null, "source/destination target bases must both be doors"));
                        continue;
                    }
                    target.TeleportDestination = new TeleportDestination { Position = Pos(teleport.GetProperty("pos")),
                        Rotation = Rot(teleport.GetProperty("rot")), Flags = (TeleportDestination.Flag)flags };
                    target.TeleportDestination.Door.SetTo(destination.FormKey);
                    if (transition != null) target.TeleportDestination.TransitionInterior.SetTo(transition.FormKey);
                    MakeTeleportEndpointPersistent(target);
                    MakeTeleportEndpointPersistent(destination);
                    report.Teleports++;
                }
            }
        }
        return report;
    }
}
