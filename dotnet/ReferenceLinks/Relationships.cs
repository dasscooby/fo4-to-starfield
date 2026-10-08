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
    public int CreatedMarkers { get; set; }
    public int UnplacedSourceReferences { get; set; }
    public List<LinkIssue> Issues { get; } = new();
}

public static class Relationships
{
    public static LinkReport Apply(StarfieldMod mod, Dictionary<string, uint> ids, IEnumerable<JsonElement> exports,
        IReadOnlyDictionary<string, FormKey>? markerBases = null)
    {
        if (ids.Values.Any(id => id == 0 || id >= 0x1000000) || ids.Values.Distinct().Count() != ids.Count)
            throw new InvalidOperationException("source map contains duplicate or invalid full-plugin FormIDs");
        var report = new LinkReport();
        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToDictionary(c => c.FormKey);
        var placed = cells.Values.SelectMany(c => c.Temporary.Concat(c.Persistent)).OfType<PlacedObject>().ToDictionary(r => r.FormKey);
        var sourceRefs = new Dictionary<string, PlacedObject>(StringComparer.OrdinalIgnoreCase);
        var sourceCells = new Dictionary<string, Cell>(StringComparer.OrdinalIgnoreCase);
        var sources = exports.ToArray();
        var occupied = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey == mod.ModKey).Select(r => r.FormKey.ID).ToHashSet();
        var next = ids.Values.Concat(occupied).DefaultIfEmpty(0x7FFu).Max() + 1;
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
                if (target == null && needed.Contains(source) && markerBases != null &&
                    reference.TryGetProperty("base_editor_id", out var baseId) &&
                    markerBases.TryGetValue(baseId.GetString() ?? "", out var markerBase) &&
                    reference.GetProperty("type").GetString() == "Static")
                {
                    if (!ids.ContainsKey(identity))
                    {
                        if (next >= 0x1000000) throw new InvalidOperationException("full plugin FormID space exhausted");
                        rid = next++; ids[identity] = rid;
                    }
                    else if (occupied.Contains(rid)) throw new InvalidOperationException($"marker identity {identity} occupies another record type");
                    target = new PlacedObject(new FormKey(mod.ModKey, rid), StarfieldRelease.Starfield)
                    {
                        Position = Pos(reference.GetProperty("pos")), Rotation = Rot(reference.GetProperty("rot")),
                    };
                    target.Base.SetTo(markerBase);
                    if (reference.TryGetProperty("disabled", out var disabled) && disabled.GetInt32() != 0)
                        target.MajorRecordFlagsRaw |= 0x800;
                    if (reference.TryGetProperty("scale", out var scale) && scale.GetSingle() != 1) target.Scale = scale.GetSingle();
                    cell.Temporary.Add(target); placed.Add(target.FormKey, target); report.CreatedMarkers++;
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
        mod.ModHeader.Stats.NextFormID = Math.Max(mod.ModHeader.Stats.NextFormID, next);
        PlacedObject? Resolve(string source, string field, string? key)
        {
            if (key != null && sourceRefs.TryGetValue(key, out var target)) return target;
            report.Issues.Add(new(source, field, key, "target reference was not placed"));
            return null;
        }
        static P3Float Pos(JsonElement e) => new(e[0].GetSingle() / 70f, e[1].GetSingle() / 70f, e[2].GetSingle() / 70f);
        static P3Float Rot(JsonElement e) => new(e[0].GetSingle(), e[1].GetSingle(), e[2].GetSingle());
        foreach (var export in sources)
        foreach (var reference in export.GetProperty("refs").EnumerateArray())
        {
            var source = reference.GetProperty("formkey").GetString()!;
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
                var resolved = Resolve(source, "linked_references.reference", link.GetProperty("reference").GetString());
                var discriminator = link.GetProperty("keyword_or_reference").GetString();
                PlacedObject? discriminatorTarget = null;
                if (discriminator != null && !sourceRefs.TryGetValue(discriminator, out discriminatorTarget))
                {
                    // The source union can be a keyword. No keyword mapping exists yet; never guess from numeric IDs.
                    report.Issues.Add(new(source, "linked_references.keyword_or_reference", discriminator, "keyword/reference union mapping is not implemented"));
                    continue;
                }
                if (resolved == null) continue;
                var translated = new LinkedReferences();
                translated.Reference.SetTo(resolved.FormKey);
                if (discriminatorTarget != null) translated.KeywordOrReference.SetTo(discriminatorTarget.FormKey);
                if (!target.LinkedReferences.Any(x => x.Reference.FormKey == resolved.FormKey &&
                    x.KeywordOrReference.FormKey == translated.KeywordOrReference.FormKey))
                    target.LinkedReferences.Add(translated);
                report.LinkedReferences++;
            }
            bool IsDoor(PlacedObject obj) => mod.Doors.Any(d => d.FormKey == obj.Base.FormKey);
            if (reference.TryGetProperty("open_by_default", out var open) && open.GetBoolean())
            {
                if (IsDoor(target)) { target.OpenByDefault = true; report.OpenState++; }
                else report.Issues.Add(new(source, "open_by_default", null, "target base is not a converted door"));
            }
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
                    report.Teleports++;
                }
            }
        }
        return report;
    }
}
