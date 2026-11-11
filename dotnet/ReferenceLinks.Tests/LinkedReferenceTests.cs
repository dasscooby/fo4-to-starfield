using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

public static class LinkedReferenceTests
{
    public static void Run()
    {
        var root = Environment.GetEnvironmentVariable("FO4SF_LINKED_REFERENCE_EVIDENCE")
            ?? Path.Combine(Path.GetTempPath(), "fo4sf-linked-ref-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var cases = new[] { "unplaced", "reserved", "case", "strict", "strict-allow", "report", "strict-report",
            "missing", "missing-reserved", "null", "malformed", "malformed-exported", "wrong-kind", "wrong-kind-case",
            "bad-discriminator", "wrong-discriminator-kind", "bad-keyword", "valid-keyword", "placed",
            "placed-discriminator", "enable-parent", "teleport", "duplicate-source", "duplicate-map", "duplicate-map-case" };
        var failures = new List<string>();
        foreach (var name in cases)
            try { Check(root, name); } catch (Exception e) { failures.Add(name + ": " + e.Message); }
        File.WriteAllText(Path.Combine(root, "result.json"), JsonSerializer.Serialize(new { cases, failures }));
        if (failures.Count != 0) throw new InvalidOperationException(string.Join("\n", failures));
        Console.WriteLine(cases.Length + " linked-reference CLI / typed binary controls passed; evidence: " + root);
    }

    static void Check(string root, string name)
    {
        void Need(bool ok, string why) { if (!ok) throw new InvalidOperationException(why); }
        const string childSource = "000001:Fallout4.esm", targetSource = "000002:Fallout4.esm", discriminatorSource = "000003:Fallout4.esm";
        var dir = Path.Combine(root, name);
        if (Directory.Exists(dir)) throw new InvalidOperationException("fresh evidence required");
        Directory.CreateDirectory(dir);
        var sf = ModKey.FromNameAndExtension("Starfield.esm");
        var mk = ModKey.FromNameAndExtension("Synthetic.esm");
        new StarfieldMod(sf, StarfieldRelease.Starfield).BeginWrite.ToPath(Path.Combine(dir, sf.FileName)).WithNoLoadOrder().Write();
        var mod = new StarfieldMod(mk, StarfieldRelease.Starfield);
        var cell = new Cell(new FormKey(mk, 0x800), StarfieldRelease.Starfield)
            { EditorID = "FO4Port_Test", Flags = Cell.Flag.IsInteriorCell };
        var sub = new CellSubBlock { BlockNumber = 4, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        var block = new CellBlock { BlockNumber = 8, GroupType = GroupTypeEnum.InteriorCellBlock };
        sub.Cells.Add(cell); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
        var baseKey = new FormKey(mk, 0x900);
        mod.Statics.Add(new Static(baseKey, StarfieldRelease.Starfield));
        var child = new PlacedObject(new FormKey(mk, 0x810), StarfieldRelease.Starfield);
        child.Base.SetTo(baseKey); cell.Temporary.Add(child);
        var ids = new Dictionary<string, uint> { ["CELL:FO4Port_Test"] = 0x800, ["REFR:FO4Port_Test:" + childSource] = 0x810 };
        if (name is "reserved" or "missing-reserved" or "wrong-kind" or "placed" or "placed-discriminator" or "duplicate-map-case")
            ids.Add("REFR:FO4Port_Test:" + targetSource, 0x811);
        if (name == "wrong-kind-case") ids.Add(("REFR:FO4Port_Test:" + targetSource).ToLowerInvariant(), 0x811);
        if (name is "wrong-kind" or "wrong-kind-case") mod.Statics.Add(new Static(new FormKey(mk, 0x811), StarfieldRelease.Starfield));
        if (name == "duplicate-map-case") ids.Add(("REFR:FO4Port_Test:" + targetSource).ToLowerInvariant(), 0x812);
        if (name is "placed" or "placed-discriminator")
        {
            var target = new PlacedObject(new FormKey(mk, 0x811), StarfieldRelease.Starfield);
            target.Base.SetTo(baseKey); cell.Temporary.Add(target);
        }
        if (name == "wrong-discriminator-kind")
        {
            ids.Add("REFR:FO4Port_Test:" + discriminatorSource, 0x812);
            mod.Statics.Add(new Static(new FormKey(mk, 0x812), StarfieldRelease.Starfield));
        }
        if (name == "duplicate-map") ids.Add("REFR:FO4Port_Test:" + targetSource, 0x810);
        var input = Path.Combine(dir, mk.FileName);
        mod.BeginWrite.ToPath(input).WithNoLoadOrder().Write();
        var original = File.ReadAllBytes(input);
        var idsPath = Path.Combine(dir, "formids.json");
        var idText = JsonSerializer.Serialize(ids); File.WriteAllText(idsPath, idText);
        string? targetKey = name switch { "null" => null, "malformed" or "malformed-exported" => "not-a-formkey",
            "case" => targetSource.ToLowerInvariant(), _ => targetSource };
        var discriminator = name is "bad-discriminator" or "wrong-discriminator-kind" or "bad-keyword" or "valid-keyword"
            ? discriminatorSource : name == "placed-discriminator" ? childSource : null;
        var childData = new Dictionary<string, object?> { ["formkey"] = childSource };
        if (name == "enable-parent") childData["enable_parent"] = new { reference = targetKey, flags = 0 };
        else if (name == "teleport") childData["teleport_destination"] = new { door = targetKey, transition_interior = (string?)null, flags = 0, pos = new[] { 0, 0, 0 }, rot = new[] { 0, 0, 0 } };
        else childData["linked_references"] = new[] { new { reference = targetKey, keyword_or_reference = discriminator } };
        var refs = new List<object> { childData };
        if (name is not ("missing" or "missing-reserved" or "null" or "malformed"))
            refs.Add(new { formkey = name == "malformed-exported" ? targetKey : targetSource });
        if (name == "duplicate-source") refs.Add(new { formkey = targetSource.ToLowerInvariant() });
        if (name == "wrong-discriminator-kind") refs.Add(new { formkey = discriminatorSource });
        var export = new Dictionary<string, object?> { ["cell"] = "Test", ["refs"] = refs };
        if (name is "bad-keyword" or "valid-keyword") export["referenced_keywords"] = new[] {
            new { formkey = discriminatorSource, editor_id = "SyntheticLink", type = name == "bad-keyword" ? "Location" : "None",
                type_value = name == "bad-keyword" ? 1 : 0, record_flags = 0, attraction_rule = (string?)null, color = (int[]?)null } };
        var source = Path.Combine(dir, "cell.json"); var sourceText = JsonSerializer.Serialize(export); File.WriteAllText(source, sourceText);
        var output = Path.Combine(dir, "out");
        var start = new ProcessStartInfo("dotnet") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
        foreach (var arg in new[] { typeof(Relationships).Assembly.Location, input, idsPath, output, source, "--no-markers" }) start.ArgumentList.Add(arg);
        if (name.StartsWith("strict")) start.ArgumentList.Add("--strict-activation-parents");
        if (name == "strict-allow") start.ArgumentList.Add("--allow-unresolved");
        if (name.EndsWith("report")) start.ArgumentList.Add("--report-only");
        start.Environment["STARFIELD_DATA"] = dir;
        using var process = Process.Start(start)!;
        var stdout = process.StandardOutput.ReadToEndAsync(); var stderr = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(60000)) { process.Kill(true); throw new TimeoutException(); }
        Task.WaitAll(stdout, stderr); File.WriteAllText(Path.Combine(dir, "run.log"), stdout.Result + stderr.Result);
        var warning = name is "unplaced" or "reserved" or "case" or "strict" or "strict-allow" or "report" or "strict-report"
            or "bad-discriminator" or "wrong-discriminator-kind" or "bad-keyword" or "valid-keyword";
        var refused = name is not ("unplaced" or "reserved" or "case" or "strict-allow" or "report" or "valid-keyword" or "placed" or "placed-discriminator");
        Need(refused ? process.ExitCode != 0 : process.ExitCode == 0, "unexpected exit " + process.ExitCode);
        var written = !refused && !name.EndsWith("report");
        Need(File.Exists(Path.Combine(output, mk.FileName)) == written && File.Exists(Path.Combine(output, "formids.json")) == written, "publication gate wrong");
        Need(File.ReadAllBytes(input).SequenceEqual(original) && File.ReadAllText(idsPath) == idText && File.ReadAllText(source) == sourceText, "input mutated");
        if (name is "duplicate-source" or "duplicate-map" or "duplicate-map-case")
        {
            Need(!Directory.Exists(output), "conflict mutated output before refusal");
            return;
        }
        using var report = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "relationships-report.json")));
        var warnings = report.RootElement.GetProperty("Warnings").EnumerateArray().ToArray();
        Need(warnings.Length == (warning ? 1 : 0), "warning count wrong");
        if (warning)
        {
            Need(warnings[0].GetProperty("Source").GetString() == childSource && warnings[0].GetProperty("Field").GetString() == "linked_references.reference" &&
                warnings[0].GetProperty("Target").GetString() == targetKey, "warning attribution lost");
            Need(stderr.Result.Contains(targetKey!), "stderr hides target identity");
        }
        var issues = report.RootElement.GetProperty("Issues").GetArrayLength();
        Need(issues > 0 == (refused && name is not ("strict" or "strict-report")), "blocking classification wrong");
        Need(report.RootElement.GetProperty("LinkedReferences").GetInt32() == (name is "placed" or "placed-discriminator" ? 1 : 0), "invented or omitted link");
        using var state = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "build-state.json")));
        Need(state.RootElement.GetProperty("complete").GetBoolean() == written, "completion flag wrong");
        Need(state.RootElement.GetProperty("unresolved").GetInt32() == warnings.Length + issues, "unresolved hides warnings/issues");
        if (!written) return;
        Need(state.RootElement.GetProperty("fidelity").GetString() == (name == "strict-allow" ? "partial_explicitly_allowed" : warning ? "partial_with_warnings" : "resolved_exported_relationships"), "partial behavior claimed resolved");
        var outputIds = JsonSerializer.Deserialize<Dictionary<string, uint>>(File.ReadAllText(Path.Combine(output, "formids.json")))!;
        Need(ids.All(pair => outputIds.TryGetValue(pair.Key, out var id) && id == pair.Value) && outputIds.Count == ids.Count + (name == "valid-keyword" ? 1 : 0), "source identities changed");
        var read = PluginReader.Read(Path.Combine(output, mk.FileName));
        var actual = read.Cells.Records.Single().SubBlocks.Single().Cells.Single().Temporary.OfType<IPlacedObjectGetter>().Single(r => r.FormKey == child.FormKey);
        Need(actual.Base.FormKey == baseKey && actual.EnableParent == null && actual.TeleportDestination == null && actual.LinkedReferences.Count == (name is "placed" or "placed-discriminator" ? 1 : 0), "binary behavior wrong");
        if (actual.LinkedReferences.Count == 1)
            Need(actual.LinkedReferences[0].Reference.FormKey == new FormKey(mk, 0x811) && actual.LinkedReferences[0].KeywordOrReference.FormKey == (name == "placed-discriminator" ? child.FormKey : FormKey.Null), "binary link identity wrong");
    }
}
