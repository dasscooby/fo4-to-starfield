// Mission: a cut-down "When Freedom Calls" (docs/spikes/B4-mission-anatomy.md, docs/mission/when-freedom-calls.md) as
// one Starfield plugin on top of the converted Commonwealth core and the converted raider. Claude's project.
//
//   points <Fallout4.esm> <out points.json> [--radius 120] [--max 8]
//        reads Fallout 4 only: where the Museum of Freedom's front door puts the player outside (the XTEL arrival of
//        the interior door in ConcordMuseum01 00017DF7 that leads to the Commonwealth), the Concord raiders around it
//        (placed ACHRs whose base EditorID contains "Raider", enabled at start, within --radius m of that point),
//        Preston's name (NPC_ 00019FD9) and the Min00 texts the plugin shows (quest name, objectives 10 / 85 / 86);
//        and Codsworth's Sanctuary placement (ACHR 0001CA7D of NPC_ 000179FF, in the world's persistent cell).
//        Positions in metres in the core's frame: FO4 position / 70 (make_core64c.py: "position = FO4 position / 70").
//   write <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> <points.json> <out dir> [--plugin FO4SFMission.esm]
//         [--world FO4Core_Commonwealth] [--no-alias] [--codsworth-body OutpostRobotMiniBotA_Garden] [--no-codsworth] [--codsworth-model <mesh under Meshes>]
//         [--merge-offset x,y]
//        the plugin: Preston (NPC_, a copy of the raider plugin's calm probe FO4_LvlRaider_Calm under Preston's name,
//        Essential and Unique), the raiders and Preston as persistent ACHRs in the core world's persistent cell (a
//        WRLD + persistent CELL override of the core, holding only our references), each at its points.json position +
//        the merge offset (default -1200,-2700: MergeX/MergeY), z kept, so its editor location is its spot in the world
//        the player walks in (FAL-179; docs/mission/when-freedom-calls.md, "Merged-frame ACHRs"), and the quest FO4SF_Min00
//        (start game enabled; stages 10 / 20 / 30 / 40 / 200; objectives 10 / 85 / 86) carrying the script
//        FO4SF_Min00Quest (scripts/mission/FO4SF_Min00Quest.psc) with its properties. --no-alias drops the Preston
//        reference alias and the objective targets (no quest markers): the fallback when the alias is suspected.
//        Codsworth (ROADMAP B2 stretch; a Mr. Handy has no Starfield skeleton): a copy of the Starfield robot NPC_
//        named by --codsworth-body under his name, Essential and Unique, without its factions and scripts, placed
//        persistent at his Fallout 4 spot in Sanctuary, kept by the quest FO4SF_CodsworthKeeper (start game enabled; the
//        same script with KeeperOnly). --no-codsworth leaves him and his keeper out.
//   check <plugin> <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> --points <points.json> [--merge-offset x,y]
//         [--no-alias] [--no-codsworth] [--codsworth-model <mesh>]
//        --codsworth-model: his own model, ARMA FO4_AA_Codsworth (a copy of AA_MiniBotA_Gardening with that mesh) in
//        ARMO FO4_Skin_Codsworth (a copy of Skin_MiniBotA_Gardening with only it), set as his skin (WNAM); check requires them
//        reads the plugin back and checks every record and link the script and the quest rely on (exit 1 on a problem),
//        and every ACHR's FormID, EditorID, position (points.json + the merge offset) and rotation against points.json.
//   npcs <plugin.esm> <fo4 | sf> <regex>
//        read only: every NPC_ whose EditorID, name or race EditorID matches the regex (case-insensitive): FormKey,
//        EditorID, name, race; for fo4 also each placed ACHR of it in the Commonwealth (core frame, FO4 / 70) and in
//        interior cells. Finds Codsworth's placement and a Starfield robot body to stand in for him (ROADMAP B2).
//   quests <Starfield.esm> [faction regex]  (read only: QuestType keywords with counts and examples, matching factions)
//   infos <Starfield.esm> <regex | wem:hex,hex...>  (read only: the INFOs whose id, EditorIDs or conditions match (first 12), with their
//        DIAL's type fields, response WEMFile values and conditions, so Codsworth's lines copy the vanilla pattern)
//   selftest <scratch dir>
//        synthetic masters (a Starfield.esm with the Credits MISC, a core with the world, a raider plugin with the calm
//        probe) and a synthetic points.json; write + check against them. No game file is read.
// Nothing is deployed and no game file is written.
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Starfield.Assets;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Strings;
using Noggog;
using F4 = Mutagen.Bethesda.Fallout4;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) return Mission.Usage();
try
{
    return args[0] switch
    {
        "points" when args.Length >= 3 => Mission.Points(args[1], args[2], Mission.Opt(args, "--radius", 120f), (int)Mission.Opt(args, "--max", 8f)),
        "write" when args.Length >= 6 => Mission.Write(args[1], args[2], args[3], args[4], args[5], Mission.Arg(args, "--plugin", Mission.Plugin),
                                                       Mission.Arg(args, "--world", Mission.World), !args.Contains("--no-alias"),
                                                       args.Contains("--no-codsworth") ? null : Mission.Arg(args, "--codsworth-body", Mission.CodsworthBody),
                                                       Mission.ArgOrNull(args, "--codsworth-model"), Mission.ArgOrNull(args, "--codsworth-voice"),
                                                       Mission.MergeOpt(args)),
        "check" when args.Length >= 5 => Mission.Check(args[1], args[2], args[3], args[4], !args.Contains("--no-alias"), !args.Contains("--no-codsworth"),
                                                       Mission.ArgOrNull(args, "--codsworth-model"), Mission.ArgOrNull(args, "--codsworth-voice"),
                                                       Mission.ArgOrNull(args, "--points"), Mission.MergeOpt(args)),
        "npcs" when args.Length >= 4 => Mission.Npcs(args[1], args[2], args[3]),
        "quests" when args.Length >= 2 => Mission.Quests(args[1], args.Length >= 3 ? args[2] : "."),
        "infos" when args.Length >= 3 => Mission.Infos(args[1], args[2]),
        "selftest" when args.Length >= 2 => Mission.SelfTest(args[1]),
        _ => Mission.Usage(),
    };
}
catch (Mission.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class Mission
{
    public const string Plugin = "FO4SFMission.esm", World = "FO4Core_Commonwealth";
    public const string QuestEdid = "FO4SF_Min00", ScriptName = "FO4SF_Min00Quest", PrestonEdid = "FO4_PrestonGarvey";
    public const uint QuestId = 0x800, PrestonNpcId = 0x801, PrestonRefId = 0x802, FirstRaiderRefId = 0x803;
    public const uint CalmProbeId = 0xF04801, RaiderId = 0xF04800;        // FO4ActorRaider.esm (docs/actors/raider-conversion.md)
    public const uint CreditsId = 0x00000F;                                // Starfield.esm MISC "Credits"
    // QTYP: the Missions-tab category. In game 18 Oct the quest ran to stage 40 but never showed there; it had none.
    // `quests` on the PC: 118 vanilla quests carry QuestTypeSideQuest 047600 (e.g. FFNeonZ09 "Balancing the Books").
    public const uint QuestTypeSideId = 0x047600; public const string QuestTypeSideEdid = "QuestTypeSideQuest";
    public const uint MuseumCell = 0x017DF7, Commonwealth = 0x00003C, PrestonFo4 = 0x019FD9, Min00 = 0x1A001C;
    public const int PrestonAlias = 0;
    // Preston's side: a faction of ours, Ally to the player's. In game 18 and 19 Oct he still turned on the player after
    // the fight: without factions he is only neutral, so IgnoreFriendlyHits never applies to the player's stray hits.
    // PlayerFaction 01C21C is verified (docs/actors/raider-conversion.md: SpacerFaction lists it as Enemy).
    public const uint MinutemenFactionId = 0x81F, PlayerFactionId = 0x01C21C;
    public const string MinutemenFactionEdid = "FO4SF_MinutemenFaction", PlayerFactionEdid = "PlayerFaction";
    // Codsworth: his FO4 ACHR and NPC_; ours after the raiders' range (0x803 .. 0x80F); the body from the PC's npcs
    // lookup (Starfield.esm 04297C OutpostRobotMiniBotA_Garden "Garden Mini Bot", MiniBotARace: a hovering robot)
    public const uint CodsworthFo4Ref = 0x01CA7D, CodsworthFo4Npc = 0x0179FF, CodsworthNpcId = 0x810, CodsworthRefId = 0x811;
    public const string CodsworthEdid = "FO4_Codsworth", CodsworthBody = "OutpostRobotMiniBotA_Garden";
    // his own model (Codsworth thread, PR #361): an ARMA copied from the mini bot's with the FO4 mesh, a skin ARMO with
    // only that ARMA, set as his WNAM. Ids follow the ACHR.
    public const uint CodsworthArmaId = 0x812, CodsworthSkinId = 0x813, MiniBotArmaId = 0x081886, MiniBotSkinId = 0x3FFD3A;
    // his keeper (22 Oct): a quest of its own, start game enabled, carrying FO4SF_Min00Quest with KeeperOnly. A new
    // start-game-enabled quest starts on a save made before it existed, where FO4SF_Min00 had already ended (stage 200
    // cancels the timer that started his) or ran OnQuestInit before his timer existed; nothing else runs on such a save.
    public const uint KeeperQuestId = 0x814;
    public const string KeeperEdid = "FO4SF_CodsworthKeeper";
    // his voice (Codsworth thread, PR #361): a Hello DIAL in the mission quest with one INFO per FO4 line, said by him
    // only. Each response's WEMFile names its .wem: verified on the PC, all 20 starfield.esm\robotminibota\*.wem names
    // are the WEMFile (8 lowercase hex digits) of an INFO, e.g. BE_KT03's Hellos (DIAL 025C46, Misc / Hello, flags Random).
    public const uint CodsworthDialId = 0x820, FirstCodsworthInfoId = 0x821;
    public const string CodsworthDialEdid = "FO4SF_CodsworthHellos";
    public const string CodsworthArmaEdid = "FO4_AA_Codsworth", CodsworthSkinEdid = "FO4_Skin_Codsworth",
                        MiniBotArmaEdid = "AA_MiniBotA_Gardening", MiniBotSkinEdid = "Skin_MiniBotA_Gardening";
    // the stages and objectives the script drives (FO4SF_Min00Quest.psc); objective indices are Min00's own
    public static readonly ushort[] Stages = { 10, 20, 30, 40, 200 };
    public static readonly (ushort Index, string Fallback, bool TargetsPreston)[] Objectives =
    {
        (10, "Find the Last Minutemen", true), (85, "Kill the Raiders", false), (86, "Talk to Preston Garvey", true),
    };
    public const float Units = 70f;                                       // FO4 units per metre
    // the core's merge offset (vmad_patch.MERGE_MEASURED; FO4SF_Min00Quest.psc MergeOffsetX/Y): the world the player walks
    // in draws the core's exterior cells at local + this. Our persistent references are not merged (they stay at their
    // written position: door probe (a), 18 and 31 Oct logs), so the ACHRs are written at local + this once (FAL-179).
    public const float MergeX = -1200f, MergeY = -2700f;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/Mission/Program.cs (points | write | check | npcs | quests | infos | selftest)");
        return 2;
    }
    public static string? ArgOrNull(string[] a, string name) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
    public static string Arg(string[] a, string name, string dflt) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : dflt; }
    public static float Opt(string[] a, string name, float dflt) => float.Parse(Arg(a, name, dflt.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
    /// --merge-offset x,y (metres), what write adds to points.json's positions and check expects; MergeX,MergeY when absent
    public static (float X, float Y) MergeOpt(string[] a)
    {
        var s = ArgOrNull(a, "--merge-offset");
        if (s is null) return (MergeX, MergeY);
        var v = s.Split(',');
        if (v.Length != 2) throw new Refusal($"--merge-offset {s}: give x,y");
        return (float.Parse(v[0], CultureInfo.InvariantCulture), float.Parse(v[1], CultureInfo.InvariantCulture));
    }
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
    static bool Near(P3Float a, float x, float y, float z, float tol = 0.01f) =>
        MathF.Abs(a.X - x) <= tol && MathF.Abs(a.Y - y) <= tol && MathF.Abs(a.Z - z) <= tol;

    // ---------------------------------------------------------------- quests (read only)

    /// Which QuestType keyword (QTYP) Starfield's quests carry, with counts and examples, and the factions whose EDID
    /// matches the pattern: in game 18 Oct the mission ran to stage 40 but never showed in the Missions tab (it has no
    /// quest type), and Preston (no factions) turned on the player.
    public static int Quests(string sfPath, string factionPattern)
    {
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var cache = sf.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        string Kw(FormKey fk) => fk.IsNull ? "-" : cache.TryResolve<SF.IKeywordGetter>(fk, out var k) ? $"{k.EditorID}({fk.ID:X6})" : $"?{fk.ID:X6}";
        foreach (var g in sf.Quests.GroupBy(q => (Kw(q.QuestType.FormKey), Kw(q.QuestGroup.FormKey))).OrderByDescending(g => g.Count()))
        {
            var ex = g.Where(q => q.Name?.String is { Length: > 0 }).Take(4).Select(q => $"{q.EditorID} '{q.Name?.String}' flags={q.Data?.Flags} obj={q.Objectives.Count}");
            Console.WriteLine($"QTYP {g.Key.Item1} group {g.Key.Item2}: {g.Count()} quests; e.g. {string.Join("; ", ex)}");
        }
        var rx = new System.Text.RegularExpressions.Regex(factionPattern, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        foreach (var f in sf.Factions.Where(f => f.EditorID is not null && rx.IsMatch(f.EditorID)).Take(40))
            Console.WriteLine($"FACT {f.FormKey.ID:X6} {f.EditorID} relations={f.Relations.Count}");
        return 0;
    }

    // ---------------------------------------------------------------- infos (read only)

    public static int Infos(string sfPath, string voicePattern)
    {
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var cache = sf.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        // "wem:000e6020,001e1d64" matches INFOs by a response's WEMFile instead (are vanilla voice files named by it?)
        var wems = voicePattern.StartsWith("wem:") ? voicePattern[4..].Split(',').Select(w => Convert.ToUInt32(w, 16)).ToHashSet() : null;
        var rx = new System.Text.RegularExpressions.Regex(wems is null ? voicePattern : "^$", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        string Ed(FormKey fk) => fk.IsNull ? "-" : cache.TryResolve<IMajorRecordGetter>(fk, out var r) ? $"{r.EditorID}({fk.ID:X6})" : $"?{fk.ID:X6}";
        int n = 0;
        foreach (var t in sf.Quests.SelectMany(q => q.DialogTopics))
            foreach (var info in t.Responses)
            {
                var text = string.Join(" | ", info.Responses.Select(r => $"wem={r.WEMFile:X8} emo={Ed(r.Emotion.FormKey)} '{r.ResponseText?.String}'"));
                var conds = string.Join("; ", info.Conditions.Select(c => $"{c.Data.GetType().Name.Replace("ConditionData", "")} {c.CompareOperator} {(c as SF.IConditionFloatGetter)?.ComparisonValue} runon={c.Data.RunOnType} flags={c.Flags} " +
                                                                         string.Join(",", c.Data.GetType().GetProperties().Where(p => p.Name.EndsWith("Parameter") || p.Name.Contains("OrList")).Select(p => $"{p.Name}={(p.GetValue(c.Data) is IFormLinkOrIndexGetter<IMajorRecordGetter> l ? Ed(l.Link.FormKey) : p.GetValue(c.Data) is { } v && v.GetType().GetProperty("Link")?.GetValue(v) is IFormLinkGetter fl ? Ed(fl.FormKey) : p.GetValue(c.Data))}"))));
                if (wems is not null ? !info.Responses.Any(r => wems.Contains(r.WEMFile)) : !rx.IsMatch(conds) && !rx.IsMatch(t.EditorID ?? "") && !rx.IsMatch(info.EditorID ?? "") && !rx.IsMatch(info.FormKey.ID.ToString("X6"))) continue;
                if (n++ >= 12) continue;
                Console.WriteLine($"INFO {info.FormKey.ID:X6} {info.EditorID} flags={info.Flags?.Flags} speaker={Ed(info.Speaker.FormKey)} [{text}] conds [{conds}]");
                Console.WriteLine($"  DIAL {t.FormKey.ID:X6} {t.EditorID} quest={Ed(t.Quest.FormKey)} category={t.Category} subtype={t.Subtype} name={t.SubtypeName} topicflags={t.TopicFlags} priority={t.Priority} branch={Ed(t.Branch.FormKey)} infos={t.Responses.Count}");
            }
        Console.WriteLine($"{n} INFO(s) matched (the first 12 printed)");
        return 0;
    }

    // ---------------------------------------------------------------- npcs (read only)

    public static int Npcs(string path, string game, string pattern)
    {
        var rx = new System.Text.RegularExpressions.Regex(pattern, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        bool Hit(params string?[] xs) => xs.Any(x => x is not null && rx.IsMatch(x));
        int n = 0;
        if (game == "sf")
        {
            using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(path, SF.StarfieldRelease.Starfield);
            var cache = sf.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
            foreach (var npc in sf.Npcs)
            {
                var race = cache.TryResolve<SF.IRaceGetter>(npc.Race.FormKey, out var r) ? r.EditorID : null;
                if (!Hit(npc.EditorID, npc.Name?.String, race)) continue;
                Console.WriteLine($"NPC_ {npc.FormKey.ID:X6} {npc.EditorID} name='{npc.Name?.String}' race={race} " +
                                  $"template={npc.DefaultTemplate.FormKey.ID:X6} factions={npc.Factions.Count}");
                n++;
            }
        }
        else if (game == "fo4")
        {
            using var fo4 = F4.Fallout4Mod.CreateFromBinaryOverlay(path, F4.Fallout4Release.Fallout4);
            var cache = fo4.ToImmutableLinkCache<F4.IFallout4Mod, F4.IFallout4ModGetter>();
            var hits = new Dictionary<FormKey, string>();
            foreach (var npc in fo4.Npcs)
            {
                var race = cache.TryResolve<F4.IRaceGetter>(npc.Race.FormKey, out var r) ? r.EditorID : null;
                if (!Hit(npc.EditorID, npc.Name?.String, race)) continue;
                Console.WriteLine($"NPC_ {npc.FormKey.ID:X6} {npc.EditorID} name='{npc.Name?.String}' race={race}");
                hits[npc.FormKey] = npc.EditorID ?? "";
                n++;
            }
            void Refs(F4.ICellGetter c, string where, bool exterior)
            {
                foreach (var p in c.Persistent.Concat(c.Temporary).OfType<F4.IPlacedNpcGetter>())
                {
                    if (!hits.TryGetValue(p.Base.FormKey, out var edid)) continue;
                    var q = p.Position;
                    var pos = exterior ? $"core ({F(q.X / Units)}, {F(q.Y / Units)}, {F(q.Z / Units)})" : $"fo4 ({F(q.X)}, {F(q.Y)}, {F(q.Z)})";
                    Console.WriteLine($"  ACHR {p.FormKey.ID:X6} of {edid} in {where} {pos} rot z {F(p.Rotation.Z)} flags 0x{p.MajorRecordFlagsRaw:X}");
                }
            }
            var world = fo4.Worldspaces.FirstOrDefault(w => w.FormKey.ID == Commonwealth);
            if (world is not null)
            {
                if (world.TopCell is { } top) Refs(top, "Commonwealth persistent", true);
                foreach (var b in world.SubCells) foreach (var s in b.Items) foreach (var c in s.Items) Refs(c, $"Commonwealth ({c.Grid?.Point.X}, {c.Grid?.Point.Y})", true);
            }
            foreach (var b in fo4.Cells) foreach (var s in b.SubBlocks) foreach (var c in s.Cells) Refs(c, $"interior {c.EditorID}", false);
        }
        else throw new Refusal("game must be fo4 or sf");
        Console.WriteLine($"{n} NPC_ matched /{pattern}/ in {Path.GetFileName(path)}");
        return 0;
    }

    // ---------------------------------------------------------------- points (Fallout 4, read only)

    public static int Points(string fo4Path, string outPath, float radius, int max)
    {
        using var fo4 = F4.Fallout4Mod.CreateFromBinaryOverlay(fo4Path, F4.Fallout4Release.Fallout4);
        var cache = fo4.ToImmutableLinkCache<F4.IFallout4Mod, F4.IFallout4ModGetter>();
        var fo4Key = fo4.ModKey;
        var world = fo4.Worldspaces.FirstOrDefault(w => w.FormKey.ID == Commonwealth)
                    ?? throw new Refusal("no Commonwealth worldspace 00003C in " + fo4Path);
        // every placed reference of the Commonwealth (persistent cell and exterior cells) by FormKey
        var placed = new Dictionary<FormKey, F4.IPlacedGetter>();
        void Add(F4.ICellGetter? c)
        {
            if (c is null) return;
            foreach (var p in c.Persistent) placed[p.FormKey] = p;
            foreach (var p in c.Temporary) placed[p.FormKey] = p;
        }
        Add(world.TopCell);
        foreach (var b in world.SubCells) foreach (var s in b.Items) foreach (var c in s.Items) Add(c);

        var museum = fo4.EnumerateMajorRecords<F4.ICellGetter>().FirstOrDefault(c => c.FormKey.ID == MuseumCell && c.FormKey.ModKey == fo4Key)
                     ?? throw new Refusal("no ConcordMuseum01 cell 00017DF7");
        var doors = museum.Persistent.Concat(museum.Temporary).OfType<F4.IPlacedObjectGetter>()
            .Where(d => d.TeleportDestination is { } t && placed.ContainsKey(t.Door.FormKey)).ToList();
        if (doors.Count == 0) throw new Refusal("ConcordMuseum01 has no door to the Commonwealth");
        // the front door: the interior door whose exterior twin is the lowest (the balcony door is a floor up)
        var front = doors.OrderBy(d => (placed[d.TeleportDestination!.Door.FormKey] as F4.IPlacedObjectGetter)?.Position.Z ?? 0f).First();
        var arrival = front.TeleportDestination!.Position;
        var arrivalRot = front.TeleportDestination!.Rotation;
        float ax = arrival.X / Units, ay = arrival.Y / Units, az = arrival.Z / Units;

        var raiders = new List<(float D, F4.IPlacedNpcGetter R, string BaseEdid)>();
        foreach (var p in placed.Values.OfType<F4.IPlacedNpcGetter>())
        {
            if ((p.MajorRecordFlagsRaw & 0x800) != 0) continue;   // initially disabled: a later wave
            if (!cache.TryResolve<F4.INpcGetter>(p.Base.FormKey, out var b) || b.EditorID is null) continue;
            if (!b.EditorID.Contains("Raider", StringComparison.OrdinalIgnoreCase)) continue;
            if (IsCorpse(b.EditorID, p.MajorRecordFlagsRaw)) continue;               // a dead-body loot placement, not a fighter
            var q = p.Position;
            float d = MathF.Sqrt(MathF.Pow(q.X / Units - ax, 2) + MathF.Pow(q.Y / Units - ay, 2));
            if (d <= radius) raiders.Add((d, p, b.EditorID));
        }
        raiders = raiders.OrderBy(r => r.D).Take(max).ToList();
        if (raiders.Count == 0) throw new Refusal($"no enabled raider within {radius} m of the museum door");

        string Text(ITranslatedStringGetter? s, string dflt) => string.IsNullOrWhiteSpace(s?.String) ? dflt : StripTokens(s!.String!);
        cache.TryResolve<F4.INpcGetter>(new FormKey(fo4Key, PrestonFo4), out var preston);
        cache.TryResolve<F4.IQuestGetter>(new FormKey(fo4Key, Min00), out var min00);
        var objectives = new Dictionary<string, string>();
        foreach (var o in Objectives)
            objectives[o.Index.ToString(CultureInfo.InvariantCulture)] =
                Text(min00?.Objectives.FirstOrDefault(x => x.Index == o.Index)?.DisplayText, o.Fallback);

        object? codsworth = null;
        if (placed.TryGetValue(new FormKey(fo4Key, CodsworthFo4Ref), out var cw) && cw is F4.IPlacedNpcGetter cn &&
            cn.Base.FormKey == new FormKey(fo4Key, CodsworthFo4Npc))
        {
            cache.TryResolve<F4.INpcGetter>(cn.Base.FormKey, out var cb);
            codsworth = new Dictionary<string, object?>
            {
                ["src"] = $"{cn.FormKey.ID:X6}", ["name"] = Text(cb?.Name, "Codsworth"),
                ["pos"] = new[] { cn.Position.X / Units, cn.Position.Y / Units, cn.Position.Z / Units },
                ["rot"] = new[] { cn.Rotation.X, cn.Rotation.Y, cn.Rotation.Z },
            };
        }
        var doc = new Dictionary<string, object?>
        {
            ["source"] = Path.GetFileName(fo4Path),
            ["frame"] = "metres, FO4 position / 70 (the core's local frame); rotation in radians as stored",
            ["quest_name"] = Text(min00?.Name, "When Freedom Calls"),
            ["preston_name"] = Text(preston?.Name, "Preston Garvey"),
            ["objectives"] = objectives,
            ["preston"] = new Dictionary<string, object?>
            {
                ["src"] = $"{front.FormKey.ID:X6}:XTEL", ["pos"] = new[] { ax, ay, az },
                ["rot"] = new[] { arrivalRot.X, arrivalRot.Y, arrivalRot.Z },
            },
            ["raiders"] = raiders.Select(r => (object)new Dictionary<string, object?>
            {
                ["src"] = $"{r.R.FormKey.ID:X6}", ["edid"] = r.R.EditorID ?? "", ["base"] = r.BaseEdid, ["dist_m"] = MathF.Round(r.D, 2),
                ["pos"] = new[] { r.R.Position.X / Units, r.R.Position.Y / Units, r.R.Position.Z / Units },
                ["rot"] = new[] { r.R.Rotation.X, r.R.Rotation.Y, r.R.Rotation.Z },
            }).ToList(),
            ["codsworth"] = codsworth,
        };
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"wrote {outPath}: museum door {front.FormKey.ID:X6} -> arrival ({F(ax)}, {F(ay)}, {F(az)}) m; " +
                          $"{raiders.Count} raider(s): " + string.Join(", ", raiders.Select(r => $"{r.R.FormKey.ID:X6} {r.R.EditorID} {r.BaseEdid} {F(r.D)} m")) +
                          (codsworth is null ? "; no Codsworth ACHR 01CA7D" : $"; Codsworth {CodsworthFo4Ref:X6}"));
        return 0;
    }

    /// FO4 places dead raiders as loot (Loot_CorpseRaiderMale01, ACHR flag 0x200 Starts Dead): they are not fighters.
    public static bool IsCorpse(string baseEdid, int flags) =>
        (flags & 0x200) != 0 || baseEdid.StartsWith("Loot_", StringComparison.OrdinalIgnoreCase) ||
        baseEdid.Contains("Corpse", StringComparison.OrdinalIgnoreCase);

    /// Min00's texts carry FO4 text-replacement tokens ("Kill the Raiders (<Global=MQ102FirstRaiderCount>/<Global=...>)")
    /// naming globals this plugin does not have; the tokens and a bracket left empty by them are dropped.
    public static string StripTokens(string text)
    {
        var t = System.Text.RegularExpressions.Regex.Replace(text, @"<[A-Za-z]+=[^>]*>", "");
        t = System.Text.RegularExpressions.Regex.Replace(t, @"\(\s*/?\s*\)", "");
        return System.Text.RegularExpressions.Regex.Replace(t, @"\s{2,}", " ").Trim();
    }

    // ---------------------------------------------------------------- write (Starfield)

    sealed record Masters(SF.IStarfieldModGetter Sf, SF.IStarfieldModGetter Core, SF.IStarfieldModGetter Raider, ILinkCache Cache) : IDisposable
    {
        public void Dispose() { (Raider as IDisposable)?.Dispose(); (Core as IDisposable)?.Dispose(); (Sf as IDisposable)?.Dispose(); }
    }

    static BinaryReadParameters Styles(params ModKey[] full)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in full) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    static Masters Open(string sfPath, string corePath, string raiderPath)
    {
        var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield, Styles(SfEsm));
        var raider = SF.StarfieldMod.CreateFromBinaryOverlay(raiderPath, SF.StarfieldRelease.Starfield, Styles(SfEsm));
        var cache = new SF.IStarfieldModGetter[] { sf, core, raider }.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        return new Masters(sf, core, raider, cache);
    }

    static SF.IWorldspaceGetter FindWorld(SF.IStarfieldModGetter core, string edid) =>
        core.Worldspaces.FirstOrDefault(w => w.EditorID == edid && w.FormKey.ModKey == core.ModKey)
        ?? throw new Refusal($"{core.ModKey} has no worldspace {edid}");

    static float[] Floats(JsonElement e) => e.EnumerateArray().Select(x => x.GetSingle()).ToArray();

    public static int Write(string sfPath, string corePath, string raiderPath, string pointsPath, string outDir, string plugin,
                            string worldEdid, bool alias, string? codsworthBody = CodsworthBody, string? codsworthModel = null,
                            string? codsworthVoice = null, (float X, float Y)? merge = null)
    {
        var (mx, my) = merge ?? (MergeX, MergeY);
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        using var m = Open(sfPath, corePath, raiderPath);
        var modKey = ModKey.FromFileName(plugin);
        var mod = new SF.StarfieldMod(modKey, SF.StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield Mission";

        // the links the script needs, each checked by type and EditorID before anything is written
        if (!m.Cache.TryResolve<SF.IMiscItemGetter>(new FormKey(SfEsm, CreditsId), out var credits) || credits.EditorID != "Credits")
            throw new Refusal("Starfield.esm 00000F is not the MISC Credits");
        if (!m.Cache.TryResolve<SF.IKeywordGetter>(new FormKey(SfEsm, QuestTypeSideId), out var qtyp) || qtyp.EditorID != QuestTypeSideEdid)
            throw new Refusal($"Starfield.esm {QuestTypeSideId:X6} is not the KYWD {QuestTypeSideEdid}");
        if (!m.Cache.TryResolve<SF.IFactionGetter>(new FormKey(SfEsm, PlayerFactionId), out var playerFaction) || playerFaction.EditorID != PlayerFactionEdid)
            throw new Refusal($"Starfield.esm {PlayerFactionId:X6} is not the FACT {PlayerFactionEdid}");
        var calm = m.Raider.Npcs.FirstOrDefault(n => n.FormKey.ID == CalmProbeId && n.EditorID == "FO4_LvlRaider_Calm")
                   ?? throw new Refusal($"{m.Raider.ModKey} has no F04801 FO4_LvlRaider_Calm");
        var raiderNpc = m.Raider.Npcs.FirstOrDefault(n => n.FormKey.ID == RaiderId && n.EditorID == "FO4_LvlRaider")
                        ?? throw new Refusal($"{m.Raider.ModKey} has no F04800 FO4_LvlRaider");
        var world = FindWorld(m.Core, worldEdid);
        var top = world.TopCell ?? throw new Refusal($"{worldEdid} has no persistent cell");

        // Preston: the calm probe under Preston's name, in our faction only, which is Ally to the player's
        var minutemen = new SF.Faction(new FormKey(modKey, MinutemenFactionId), SF.StarfieldRelease.Starfield) { EditorID = MinutemenFactionEdid };
        minutemen.Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(playerFaction.FormKey), Reaction = SF.CombatReaction.Ally });
        mod.Factions.Add(minutemen);
        var npc = (SF.Npc)calm.Duplicate(new FormKey(modKey, PrestonNpcId));
        npc.EditorID = PrestonEdid;
        npc.Name = pts.GetProperty("preston_name").GetString();
        npc.Flags = (npc.Flags | SF.Npc.Flag.Essential | SF.Npc.Flag.Unique) & ~SF.Npc.Flag.Respawn;
        npc.Factions.Clear();
        npc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(minutemen.FormKey), Rank = 0 });
        mod.Npcs.Add(npc);

        // the world and its persistent cell, overridden with only our references (vanilla keeps every persistent
        // worldspace reference there; TerrainOverlays puts the door arrival markers there for the same reason). Not an
        // exterior cell of the core: an add-on's override of one broke the core's coc (15 Oct, verified twice), and a
        // temporary actor there could not be a script property or the alias's forced reference while its cell is unloaded.
        // Each ACHR is written at its points.json position (the core's local frame) + the merge offset: the engine leaves
        // our persistent references at their written position, so that is its editor location in the world the player
        // walks in, where its AI and its returns take it (31 Oct: raiders back at their written position in the player's
        // world; Codsworth's saved heading is the bearing to his written position). Offsetting a reference the engine
        // also merges would offset it twice, as MoveOver did on 31 Oct (FAL-179).
        var w = (SF.Worldspace)world.DeepCopy();
        w.SubCells.Clear();
        var cell = (SF.Cell)top.DeepCopy();
        cell.Persistent.Clear();
        cell.Temporary.Clear();
        cell.NavigationMeshes.Clear();
        w.TopCell = cell;
        SF.PlacedNpc Ach(uint id, FormKey baseKey, string edid, JsonElement e)
        {
            var p = Floats(e.GetProperty("pos"));
            var r = Floats(e.GetProperty("rot"));
            var a = new SF.PlacedNpc(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
            {
                EditorID = edid, Base = new FormLink<SF.INpcGetter>(baseKey),
                Position = new P3Float(p[0] + mx, p[1] + my, p[2]), Rotation = new P3Float(r[0], r[1], r[2]),
            };
            a.MajorRecordFlagsRaw |= 0x400;                                  // Persistent
            cell.Persistent.Add(a);
            return a;
        }
        var prestonRef = Ach(PrestonRefId, npc.FormKey, "FO4SF_Min00_PrestonREF", pts.GetProperty("preston"));
        var raiderRefs = new List<SF.PlacedNpc>();
        uint next = FirstRaiderRefId;
        foreach (var r in pts.GetProperty("raiders").EnumerateArray())
            raiderRefs.Add(Ach(next++, raiderNpc.FormKey, $"FO4SF_Min00_Raider_{r.GetProperty("src").GetString()}", r));
        if (next > CodsworthNpcId) throw new Refusal($"{raiderRefs.Count} raiders overrun 0x{CodsworthNpcId:X} (Codsworth's id)");
        SF.Npc? cods = null;
        SF.PlacedNpc? codsRef = null;
        if (codsworthBody is not null)
        {
            if (!pts.TryGetProperty("codsworth", out var cj) || cj.ValueKind != JsonValueKind.Object)
                throw new Refusal("points.json has no codsworth (rerun points, or write --no-codsworth)");
            var body = m.Sf.Npcs.FirstOrDefault(n => n.EditorID == codsworthBody)
                       ?? throw new Refusal($"Starfield.esm has no NPC_ {codsworthBody} (the Codsworth body)");
            cods = (SF.Npc)body.Duplicate(new FormKey(modKey, CodsworthNpcId));
            cods.EditorID = CodsworthEdid;
            cods.Name = cj.GetProperty("name").GetString();
            cods.Flags = (cods.Flags | SF.Npc.Flag.Essential | SF.Npc.Flag.Unique) & ~SF.Npc.Flag.Respawn;
            cods.Factions.Clear();                                          // nothing makes him hostile or an outpost worker
            cods.VirtualMachineAdapter = null;                              // the outpost bot's scripts expect an outpost
            if (codsworthModel is not null)
            {
                var aa = m.Sf.ArmorAddons.FirstOrDefault(x => x.FormKey == new FormKey(SfEsm, MiniBotArmaId) && x.EditorID == MiniBotArmaEdid)
                         ?? throw new Refusal($"Starfield.esm {MiniBotArmaId:X6} is not the ARMA {MiniBotArmaEdid}");
                var sk = m.Sf.Armors.FirstOrDefault(x => x.FormKey == new FormKey(SfEsm, MiniBotSkinId) && x.EditorID == MiniBotSkinEdid)
                         ?? throw new Refusal($"Starfield.esm {MiniBotSkinId:X6} is not the ARMO {MiniBotSkinEdid}");
                var arma = (SF.ArmorAddon)aa.Duplicate(new FormKey(modKey, CodsworthArmaId));
                arma.EditorID = CodsworthArmaEdid;
                int set = 0;
                foreach (var g in new[] { arma.WorldModel?.Male, arma.WorldModel?.Female })
                    if (g?.File?.GivenPath is { Length: > 0 } given)                 // only the models the mini bot has
                        { g.File = new AssetLink<StarfieldModelAssetType>(ModelPath(given, codsworthModel)); set++; }
                if (set == 0) throw new Refusal($"{MiniBotArmaEdid} has no world model to replace");
                var skin = (SF.Armor)sk.Duplicate(new FormKey(modKey, CodsworthSkinId));
                skin.EditorID = CodsworthSkinEdid;
                var entry = new SF.ArmorAddonModel
                {
                    AddonIndex = skin.Armatures.FirstOrDefault()?.AddonIndex ?? 0,      // the mini bot's first entry's index
                    ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(arma.FormKey),
                };
                skin.Armatures.Clear();
                skin.Armatures.Add(entry);
                cods.Skin.SetTo(skin.FormKey);
                mod.ArmorAddons.Add(arma);
                mod.Armors.Add(skin);
            }
            mod.Npcs.Add(cods);
            codsRef = Ach(CodsworthRefId, cods.FormKey, "FO4SF_CodsworthREF", cj);
        }
        mod.Worldspaces.Add(w);

        // the quest
        var objText = pts.GetProperty("objectives");
        var quest = new SF.Quest(new FormKey(modKey, QuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = QuestEdid, Name = pts.GetProperty("quest_name").GetString(), FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.RunOnce | SF.Quest.Flag.DisplaysInHud, Priority = 50 },
        };
        quest.QuestType.SetTo(qtyp.FormKey);
        foreach (var s in Stages)
        {
            var st = new SF.QuestStage { Index = s };
            if (s == 200) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
            quest.Stages.Add(st);
        }
        foreach (var o in Objectives)
        {
            var obj = new SF.QuestObjective { Index = o.Index, DisplayText = objText.GetProperty(o.Index.ToString(CultureInfo.InvariantCulture)).GetString() };
            if (alias && o.TargetsPreston) obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = PrestonAlias });
            quest.Objectives.Add(obj);
        }
        if (alias)
            (quest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = PrestonAlias, Name = "PrestonGarvey", ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(prestonRef.FormKey),
            });
        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        void MissionProps(SF.ScriptEntry e)                             // built fresh per script: ScriptProperty has no DeepCopy
        {
            e.Properties.Add(Obj("Preston", prestonRef.FormKey));
            var list = new SF.ScriptObjectListProperty { Name = "Raiders", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var r in raiderRefs) list.Objects.Add(Obj("", r.FormKey));
            e.Properties.Add(list);
            e.Properties.Add(Obj("Credits", credits.FormKey));
        }
        MissionProps(script);
        SF.QuestAdapter Adapter(SF.ScriptEntry entry)
        {
            var vm = new SF.QuestAdapter
            {
                Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
                Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
            };
            vm.Scripts.Add(entry);
            return vm;
        }
        quest.VirtualMachineAdapter = Adapter(script);
        SF.Quest? keeper = null;                                        // Codsworth is moved by his keeper only
        if (codsRef is not null)
        {
            keeper = new SF.Quest(new FormKey(modKey, KeeperQuestId), SF.StarfieldRelease.Starfield)
            {
                EditorID = KeeperEdid, FormVersion = 581, Version2 = 12,
                Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled, Priority = 50 },
            };
            var ks = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
            MissionProps(ks);                                           // the Mandatory ones, as the mission's
            ks.Properties.Add(Obj("Codsworth", codsRef.FormKey));
            ks.Properties.Add(new SF.ScriptBoolProperty { Name = "KeeperOnly", Flags = SF.ScriptProperty.Flag.Edited, Data = true });
            keeper.VirtualMachineAdapter = Adapter(ks);
        }
        var lines = codsworthVoice is null ? [] : VoiceLines(codsworthVoice);
        if (lines.Count > 0)
        {
            if (cods is null) throw new Refusal("--codsworth-voice needs Codsworth (drop --no-codsworth)");
            var dial = new SF.DialogTopic(new FormKey(modKey, CodsworthDialId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthDialEdid, Quest = new FormLink<SF.IQuestGetter>(quest.FormKey), Priority = 50,
                Category = SF.DialogTopic.CategoryEnum.Misc, Subtype = SF.DialogTopic.SubtypeEnum.Hello,
                SubtypeName = SF.DialogTopic.SubtypeNameEnum.Hello,
            };
            uint id = FirstCodsworthInfoId;
            foreach (var l in lines)
            {
                var info = new SF.DialogResponses(new FormKey(modKey, id++), SF.StarfieldRelease.Starfield)
                {
                    EditorID = $"FO4SF_Codsworth_{l.Fo4Info}_{l.Response}",
                    Flags = new SF.DialogResponseFlags { Flags = (short)SF.DialogResponses.Flag.Random },   // as vanilla's mini bot Hellos (BE_KT03)
                };
                info.Responses.Add(new SF.DialogResponse { ResponseText = l.Text, WEMFile = l.Wem });
                info.Conditions.AddRange(VoiceConditions(cods.FormKey, l.Sex));
                dial.Responses.Add(info);
                (dial.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(info.FormKey));
            }
            quest.DialogTopics.Add(dial);
        }
        mod.Quests.Add(quest);
        if (keeper is not null) mod.Quests.Add(keeper);

        mod.ModHeader.Stats.NextFormID = Math.Max(MinutemenFactionId + 1, lines.Count > 0 ? FirstCodsworthInfoId + (uint)lines.Count
                                       : cods is null ? next : codsworthModel is null ? CodsworthRefId + 1 : CodsworthSkinId + 1);
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, plugin);
        var lo = new[] { SfEsm, m.Core.ModKey, m.Raider.ModKey };
        mod.BeginWrite.ToPath(path).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} {quest.FormKey} \"{quest.Name}\" " +
                          $"({Stages.Length} stages, {quest.Objectives.Count} objectives, {(alias ? "alias PrestonGarvey" : "no alias")}); " +
                          $"NPC_ {PrestonEdid} {npc.FormKey} \"{npc.Name}\"; ACHR Preston {prestonRef.FormKey} at {Show(prestonRef.Position)}; " +
                          $"{raiderRefs.Count} raider ACHR(s) of {raiderNpc.EditorID}; " +
                          (cods is null ? "no Codsworth; " : $"NPC_ {CodsworthEdid} {cods.FormKey} \"{cods.Name}\" body {codsworthBody}, ACHR {codsRef!.FormKey} at {Show(codsRef.Position)}" +
                                            (codsworthModel is null ? "; " : $", skin {CodsworthSkinEdid} model {codsworthModel}; ")) +
                          $"WRLD {w.EditorID} {w.FormKey} persistent CELL {cell.FormKey} overridden; ACHRs at points.json + ({F(mx)}, {F(my)})");
        return 0;
    }

    static string Show(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    // ---------------------------------------------------------------- check

    public record VoiceLine(string Fo4Info, int Response, string Text, uint Wem, string? Sex);

    /// voice.json from make_mission.py stage: [{"info", "response", "text", "wem" (8 hex digits), "sex" (male, female or null)}]
    public static List<VoiceLine> VoiceLines(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var lines = doc.RootElement.EnumerateArray().Select(e => new VoiceLine(
            e.GetProperty("info").GetString()!, e.GetProperty("response").GetInt32(), e.GetProperty("text").GetString()!,
            uint.Parse(e.GetProperty("wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture),
            e.TryGetProperty("sex", out var sx) && sx.ValueKind == JsonValueKind.String ? sx.GetString() : null)).ToList();
        if (lines.Count == 0 || lines.Count > 0x7D0) throw new Refusal($"{path}: {lines.Count} voice lines");
        if (lines.Select(l => l.Wem).Distinct().Count() != lines.Count) throw new Refusal($"{path}: two lines share a wem id");
        if (lines.Any(l => string.IsNullOrWhiteSpace(l.Text) || l.Sex is not (null or "male" or "female"))) throw new Refusal($"{path}: a line has no text or a bad sex");
        return lines;
    }

    /// Said by Codsworth only (GetIsID on the subject); "sir" lines to a male player, "mum" lines to a female one
    /// (GetIsSex on the target, the player he greets).
    public static List<SF.Condition> VoiceConditions(FormKey codsworth, string? sex)
    {
        var id = new SF.GetIsIDConditionData { RunOnType = SF.Condition.RunOnType.Subject };
        id.FirstParameter.Link.SetTo(codsworth);
        var list = new List<SF.Condition> { new SF.ConditionFloat { CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 1, Data = id } };
        if (sex is not null)
            list.Add(new SF.ConditionFloat
            {
                CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 1,
                Data = new SF.GetIsSexConditionData { RunOnType = SF.Condition.RunOnType.Target, FirstParameter = sex == "male" ? MaleFemaleGender.Male : MaleFemaleGender.Female },
            });
        return list;
    }

    static string CondSig(SF.IConditionGetter c)
    {
        string param = c.Data switch
        {
            SF.IGetIsIDConditionDataGetter g => g.FirstParameter.Link.FormKey.ToString(),
            SF.IGetIsSexConditionDataGetter g => g.FirstParameter.ToString(),
            _ => "unsupported",
        };
        return $"{c.Data.GetType().Name.Replace("BinaryOverlay", "")} {c.Data.RunOnType} {c.CompareOperator} {(c as SF.IConditionFloatGetter)?.ComparisonValue} {c.Flags} {param}";
    }

    /// The model path written the way the vanilla one is: with its "Meshes\" prefix when it has one (rel is relative to
    /// Data\Meshes).
    public static string ModelPath(string vanilla, string rel)
    {
        rel = rel.Replace('/', '\\').TrimStart('\\');
        if (rel.StartsWith("meshes\\", StringComparison.OrdinalIgnoreCase)) rel = rel[7..];
        return vanilla.StartsWith("meshes\\", StringComparison.OrdinalIgnoreCase) ? vanilla[..7] + rel : rel;
    }

    public static int Check(string pluginPath, string sfPath, string corePath, string raiderPath, bool alias, bool codsworth = true,
                            string? codsworthModel = null, string? codsworthVoice = null, string? pointsPath = null,
                            (float X, float Y)? merge = null)
    {
        using var m = Open(sfPath, corePath, raiderPath);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Styles(SfEsm, m.Core.ModKey, m.Raider.ModKey));
        var key = plug.ModKey;
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{plug.ModHeader.Stats.NextFormID:X}, " +
                          $"{plug.Quests.Count} QUST, {plug.Npcs.Count} NPC_, {plug.Worldspaces.Count} WRLD");
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master (every plugin of ours that loads is)");
        Need(masters.SequenceEqual(new[] { "Starfield.esm", m.Core.ModKey.FileName.String, m.Raider.ModKey.FileName.String }), "masters are not Starfield, core, raider");

        var npc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, PrestonNpcId));
        var minutemen = plug.Factions.FirstOrDefault(f => f.FormKey == new FormKey(key, MinutemenFactionId));
        Need(minutemen is { EditorID: MinutemenFactionEdid } && minutemen.Relations.Count == 1 &&
             minutemen.Relations[0].Target.FormKey == new FormKey(SfEsm, PlayerFactionId) && minutemen.Relations[0].Reaction == SF.CombatReaction.Ally,
             $"FACT 0x{MinutemenFactionId:X} is not {MinutemenFactionEdid} with the one relation Ally to PlayerFaction");
        Need(npc is { EditorID: PrestonEdid } && npc.Flags.HasFlag(SF.Npc.Flag.Essential) && npc.Factions.Count == 1 &&
             npc.Factions[0].Faction.FormKey == minutemen?.FormKey,
             $"NPC_ 0x801 is not an essential FO4_PrestonGarvey in {MinutemenFactionEdid} only");

        var world = FindWorld(m.Core, World);
        var w = plug.Worldspaces.FirstOrDefault();
        Need(w is not null && w.FormKey == world.FormKey && w.SubCells.Count == 0, "the WRLD override is not the core world without exterior cells");
        var cell = w?.TopCell;
        Need(cell is not null && cell.FormKey == world.TopCell?.FormKey, "the persistent cell override is not the core's");
        var refs = cell?.Persistent.OfType<SF.IPlacedNpcGetter>().ToList() ?? new();
        Need(cell is null || cell.Persistent.Count == refs.Count, "the persistent cell holds something other than our ACHRs");
        foreach (var r in refs)
        {
            Console.WriteLine($"  ACHR {r.FormKey.ID:X6} {r.EditorID} base {r.Base.FormKey} at {Show(r.Position)} flags 0x{r.MajorRecordFlagsRaw:X}");
            Need((r.MajorRecordFlagsRaw & 0x400) != 0, $"ACHR {r.FormKey.ID:X6} is not persistent");
            Need(m.Cache.TryResolve<SF.INpcGetter>(r.Base.FormKey, out _) || r.Base.FormKey.ModKey == key, $"ACHR {r.FormKey.ID:X6}: base {r.Base.FormKey} does not resolve");
        }
        var preston = refs.FirstOrDefault(r => r.FormKey.ID == PrestonRefId);
        Need(preston is not null && preston.Base.FormKey == npc?.FormKey, "ACHR 0x802 is not Preston");
        var raiders = refs.Where(r => r.FormKey.ID >= FirstRaiderRefId && r.FormKey.ID < CodsworthNpcId).ToList();
        var cods = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, CodsworthNpcId));
        var codsRef = refs.FirstOrDefault(r => r.FormKey.ID == CodsworthRefId);
        if (!codsworth) Need(cods is null && codsRef is null, "a --no-codsworth build carries Codsworth");
        else
        {
            Console.WriteLine($"  NPC_ {cods?.EditorID} \"{cods?.Name?.String}\" race {cods?.Race.FormKey} factions {cods?.Factions.Count} scripts {(cods?.VirtualMachineAdapter is null ? 0 : 1)}");
            Need(cods is { EditorID: CodsworthEdid } && cods.Flags.HasFlag(SF.Npc.Flag.Essential) && cods.Flags.HasFlag(SF.Npc.Flag.Unique) &&
                 !cods.Flags.HasFlag(SF.Npc.Flag.Respawn) && cods.Factions.Count == 0 &&
                 cods.VirtualMachineAdapter is null && !string.IsNullOrWhiteSpace(cods.Name?.String),
                 "NPC_ 0x810 is not an essential, unique, non-respawning, named FO4_Codsworth without factions and scripts");
            Need(cods is not null && m.Cache.TryResolve<SF.IRaceGetter>(cods.Race.FormKey, out _), "Codsworth's race does not resolve");
            Need(codsRef is not null && codsRef.Base.FormKey == cods?.FormKey, "ACHR 0x811 is not Codsworth");
        }
        var arma = plug.ArmorAddons.FirstOrDefault(x => x.FormKey == new FormKey(key, CodsworthArmaId));
        var skin = plug.Armors.FirstOrDefault(x => x.FormKey == new FormKey(key, CodsworthSkinId));
        if (codsworth && codsworthModel is not null)
        {
            var files = new[] { arma?.WorldModel?.Male, arma?.WorldModel?.Female }.Select(g => g?.File?.GivenPath).OfType<string>().Where(f => f.Length > 0).ToList();
            Console.WriteLine($"  ARMA {arma?.EditorID} race {arma?.Race.FormKey} models [{string.Join(", ", files)}]; ARMO {skin?.EditorID} " +
                              $"armatures [{string.Join(", ", skin?.Armatures.Select(x => x.ArmorAddon.FormKey.ToString()) ?? [])}]");
            Need(arma is { EditorID: CodsworthArmaEdid } && files.Count > 0 &&
                 files.All(f => string.Equals(ModelPath("", f), ModelPath("", codsworthModel), StringComparison.OrdinalIgnoreCase)),
                 $"ARMA 0x{CodsworthArmaId:X} is not {CodsworthArmaEdid} with the model {codsworthModel}");
            Need(arma is not null && m.Cache.TryResolve<SF.IRaceGetter>(arma.Race.FormKey, out _), "Codsworth's ARMA race does not resolve");
            Need(skin is { EditorID: CodsworthSkinEdid } && skin.Armatures.Count == 1 && skin.Armatures[0].ArmorAddon.FormKey == arma?.FormKey,
                 $"ARMO 0x{CodsworthSkinId:X} is not {CodsworthSkinEdid} with only his ARMA");
            Need(cods?.Skin.FormKey == skin?.FormKey && skin is not null, "Codsworth's skin (WNAM) is not his ARMO");
        }
        else Need(arma is null && skin is null && (cods is null || cods.Skin.FormKey != new FormKey(key, CodsworthSkinId)),
                  "a build without --codsworth-model carries Codsworth's ARMA or ARMO");
        Need(refs.All(r => r.FormKey.ID < CodsworthNpcId || r.FormKey.ID == CodsworthRefId), "an ACHR outside Preston, the raiders and Codsworth");
        Need(raiders.Count > 0 && raiders.All(r => r.Base.FormKey == new FormKey(m.Raider.ModKey, RaiderId)), "no raider ACHR on FO4_LvlRaider");

        // the merged frame (FAL-179): each ACHR keeps its FormID and EditorID and stands at its points.json position + the
        // merge offset (z and rotation as in points.json); a local-frame or doubly offset ACHR is a problem
        if (pointsPath is null) problems.Add("no --points: the ACHR positions cannot be checked against points.json");
        else
        {
            var (mx, my) = merge ?? (MergeX, MergeY);
            var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
            Console.WriteLine($"  frame: ACHRs at points.json + the merge offset ({F(mx)}, {F(my)}), z kept");
            void At(uint id, string edid, JsonElement e)
            {
                var p = Floats(e.GetProperty("pos"));
                var r = Floats(e.GetProperty("rot"));
                var a = refs.FirstOrDefault(x => x.FormKey.ID == id);
                Need(a is not null && a.EditorID == edid && Near(a.Position, p[0] + mx, p[1] + my, p[2]) && Near(a.Rotation, r[0], r[1], r[2]),
                     $"ACHR {id:X6} is not {edid} at points.json ({F(p[0])}, {F(p[1])}, {F(p[2])}) + the merge offset = " +
                     $"({F(p[0] + mx)}, {F(p[1] + my)}, {F(p[2])}) with its rotation" + (a is null ? " (missing)" : $" (is {a.EditorID} at {Show(a.Position)})"));
            }
            At(PrestonRefId, "FO4SF_Min00_PrestonREF", pts.GetProperty("preston"));
            var rj = pts.GetProperty("raiders").EnumerateArray().ToList();
            Need(raiders.Count == rj.Count, $"{raiders.Count} raider ACHR(s), points.json has {rj.Count}");
            for (int i = 0; i < rj.Count; i++)
                At(FirstRaiderRefId + (uint)i, $"FO4SF_Min00_Raider_{rj[i].GetProperty("src").GetString()}", rj[i]);
            if (codsworth)
            {
                if (pts.TryGetProperty("codsworth", out var cj) && cj.ValueKind == JsonValueKind.Object) At(CodsworthRefId, "FO4SF_CodsworthREF", cj);
                else problems.Add("points.json has no codsworth");
            }
        }

        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("no QUST 0x800");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} \"{q.Name?.String}\" flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] " +
                              $"objectives [{string.Join("; ", q.Objectives.Select(o => $"{o.Index} \"{o.DisplayText?.String}\" targets {o.Targets.Count}"))}] aliases {q.Aliases?.Count ?? 0}");
            Need(q.EditorID == QuestEdid && q.Data is not null && q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled), "the quest is not FO4SF_Min00, start game enabled");
            Need(q.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"the quest's QuestType is not {QuestTypeSideEdid} (it would not show in the Missions tab)");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), "stages differ from the script's");
            var dials = q.DialogTopics.ToList();
            if (codsworthVoice is null) Need(dials.Count == 0, "a build without --codsworth-voice carries dialogue");
            else
            {
                var want = VoiceLines(codsworthVoice);
                var dial = dials.FirstOrDefault(d => d.FormKey == new FormKey(key, CodsworthDialId));
                Console.WriteLine($"  DIAL {dial?.EditorID} {dial?.Category}/{dial?.Subtype}/{dial?.SubtypeName} infos {dial?.Responses.Count}; " +
                                  $"first: {string.Join(" | ", dial?.Responses.Take(2).Select(i => $"{i.FormKey.ID:X6} wem {i.Responses.FirstOrDefault()?.WEMFile:x8} '{i.Responses.FirstOrDefault()?.ResponseText?.String}' conds {i.Conditions.Count}") ?? [])}");
                Need(dials.Count == 1 && dial is { EditorID: CodsworthDialEdid, Subtype: SF.DialogTopic.SubtypeEnum.Hello, SubtypeName: SF.DialogTopic.SubtypeNameEnum.Hello }
                     && dial.Quest.FormKey == q.FormKey, $"DIAL 0x{CodsworthDialId:X} is not his Hello topic in the quest");
                var infos = dial?.Responses.ToList() ?? [];
                Need(infos.Count == want.Count && (dial!.TopicInfoList ?? []).Select(t => t.FormKey).SequenceEqual(infos.Select(i => i.FormKey)), "his INFOs differ from voice.json or the topic's list");
                for (int i = 0; i < Math.Min(infos.Count, want.Count); i++)
                {
                    var info = infos[i];
                    var r = info.Responses.Count == 1 ? info.Responses[0] : null;
                    // the whole condition list, in order: kind, run-on, operator, value, flags (OR grouping) and parameter (Codex 5565463917)
                    bool condsOk = cods is not null && info.Conditions.Select(CondSig).SequenceEqual(VoiceConditions(cods.FormKey, want[i].Sex).Select(CondSig));
                    Need(info.FormKey.ID == FirstCodsworthInfoId + i && r is not null && r.WEMFile == want[i].Wem && r.ResponseText?.String == want[i].Text
                         && condsOk, $"INFO 0x{FirstCodsworthInfoId + i:X} is not line {want[i].Fo4Info}_{want[i].Response} (text, wem, conditions: said by Codsworth, sex)");
                }
            }
            Need(q.Stages.LastOrDefault()?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 200 does not complete the quest");
            Need(q.Objectives.Select(o => o.Index).SequenceEqual(Objectives.Select(o => o.Index)), "objectives differ from the script's");
            Need(q.Objectives.All(o => !string.IsNullOrWhiteSpace(o.DisplayText?.String) && !o.DisplayText!.String!.Contains('<')), "an objective has no text or an FO4 text token");
            if (alias)
            {
                var al = (q.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == PrestonAlias);
                Need(al is not null && al.ForcedReference.FormKey == preston?.FormKey, "alias 0 is not forced to Preston's ACHR");
                Need(q.Objectives.Where((o, i) => Objectives[i].TargetsPreston).All(o => o.Targets.Count == 1 && o.Targets[0].AliasID == PrestonAlias),
                     "Preston's objectives do not target alias 0");
            }
            else Need((q.Aliases?.Count ?? 0) == 0 && q.Objectives.All(o => o.Targets.Count == 0), "--no-alias build carries an alias or a target");
            var s = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (s is null) problems.Add($"script {ScriptName} not attached");
            else
            {
                var props = s.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {s.Name}: " + string.Join(", ", props.Keys));
                Need(props.TryGetValue("Preston", out var pp) && pp is SF.IScriptObjectPropertyGetter po && po.Object.FormKey == preston?.FormKey, "property Preston");
                Need(props.TryGetValue("Credits", out var cp) && cp is SF.IScriptObjectPropertyGetter co && co.Object.FormKey == new FormKey(SfEsm, CreditsId), "property Credits");
                Need(props.TryGetValue("Raiders", out var rp) && rp is SF.IScriptObjectListPropertyGetter rl &&
                     rl.Objects.Select(o => o.Object.FormKey).SequenceEqual(raiders.Select(r => r.FormKey)), "property Raiders lists the raider ACHRs in order");
                Need(!props.ContainsKey("Codsworth") && !props.ContainsKey("KeeperOnly"), "FO4SF_Min00 sets Codsworth or KeeperOnly (his keeper quest moves him)");
            }
        }
        var kq = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, KeeperQuestId));
        if (!codsworth) Need(kq is null, $"a --no-codsworth build carries {KeeperEdid}");
        else if (kq is null) problems.Add($"no QUST 0x{KeeperQuestId:X} {KeeperEdid} (Codsworth would stay unmoved on an existing save)");
        else
        {
            Console.WriteLine($"  QUST {kq.EditorID} flags {kq.Data?.Flags} stages {kq.Stages.Count}");
            Need(kq.EditorID == KeeperEdid && kq.Data is not null && kq.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled)
                 && !kq.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce), $"{KeeperEdid} is not start game enabled (or is run once)");
            var ks = kq.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (ks is null) problems.Add($"script {ScriptName} not attached to {KeeperEdid}");
            else
            {
                var props = ks.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {ks.Name} on {KeeperEdid}: " + string.Join(", ", props.Keys));
                Need(props.TryGetValue("Codsworth", out var wp) && wp is SF.IScriptObjectPropertyGetter wo && wo.Object.FormKey == codsRef?.FormKey,
                     "property Codsworth is not his ACHR (the keeper moves him into the merged world)");
                Need(props.TryGetValue("KeeperOnly", out var kp) && kp is SF.IScriptBoolPropertyGetter kb && kb.Data,
                     "property KeeperOnly is not True (the keeper would run the mission)");
                Need(props.TryGetValue("Preston", out var pp) && pp is SF.IScriptObjectPropertyGetter po && po.Object.FormKey == preston?.FormKey
                     && props.ContainsKey("Raiders") && props.ContainsKey("Credits"), "the keeper lacks a Mandatory property");
            }
        }
        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- selftest (synthetic masters only)

    public static int SelfTest(string dir)
    {
        Directory.CreateDirectory(dir);
        var rel = SF.StarfieldRelease.Starfield;
        // a stand-in Starfield.esm: the Credits MISC at 00000F
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.MiscItems.Add(new SF.MiscItem(new FormKey(SfEsm, CreditsId), rel) { EditorID = "Credits" });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, QuestTypeSideId), rel) { EditorID = QuestTypeSideEdid });
        // the Codsworth body: a robot with a race, a faction and a script, which the copy must drop (race kept)
        var race = new SF.Race(new FormKey(SfEsm, 0x900), rel) { EditorID = "MiniBotARace" };
        sf.Races.Add(race);
        var faction = new SF.Faction(new FormKey(SfEsm, 0x901), rel) { EditorID = "OutpostFaction" };
        sf.Factions.Add(faction);
        sf.Factions.Add(new SF.Faction(new FormKey(SfEsm, PlayerFactionId), rel) { EditorID = PlayerFactionEdid });
        var bot = new SF.Npc(new FormKey(SfEsm, 0x902), rel) { EditorID = CodsworthBody, Name = "Garden Mini Bot", Race = new FormLink<SF.IRaceGetter>(race.FormKey) };
        bot.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(faction.FormKey), Rank = 0 });
        bot.VirtualMachineAdapter = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
        bot.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = "OutpostBotScript" });
        sf.Npcs.Add(bot);
        // the mini bot's look: an ARMA with a model and the skin ARMO that lists it (Codsworth's own model is copied from them)
        var aa = new SF.ArmorAddon(new FormKey(SfEsm, MiniBotArmaId), rel) { EditorID = MiniBotArmaEdid, Race = new FormLinkNullable<SF.IRaceGetter>(race.FormKey) };
        aa.WorldModel = new GenderedItem<SF.Model?>(new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Meshes\\Actors\\MiniBot\\MiniBotA.nif") }, null);
        sf.ArmorAddons.Add(aa);
        var sk = new SF.Armor(new FormKey(SfEsm, MiniBotSkinId), rel) { EditorID = MiniBotSkinEdid };
        sk.Armatures.Add(new SF.ArmorAddonModel { AddonIndex = 0, ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(aa.FormKey) });
        sk.Armatures.Add(new SF.ArmorAddonModel { AddonIndex = 1, ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(aa.FormKey) });
        sf.Armors.Add(sk);
        bot.Skin.SetTo(sk.FormKey);
        sf.ModHeader.Stats.NextFormID = 0x800;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        // a core with the world and its persistent cell (holding one marker of its own, which the override must drop)
        var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
        var core = new SF.StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var world = new SF.Worldspace(new FormKey(coreKey, 0x803), rel) { EditorID = World };
        world.TopCell = new SF.Cell(new FormKey(coreKey, 0x900), rel) { Flags = SF.Cell.Flag.HasWater };
        world.TopCell.Persistent.Add(new SF.PlacedObject(new FormKey(coreKey, 0x800), rel) { EditorID = "Anchor" });
        core.Worldspaces.Add(world);
        core.ModHeader.Stats.NextFormID = 0x901;
        var corePath = Path.Combine(dir, coreKey.FileName);
        core.BeginWrite.ToPath(corePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        // a raider plugin with the conversion and the calm probe
        var raiderKey = ModKey.FromFileName("FO4ActorRaider.esm");
        var raider = new SF.StarfieldMod(raiderKey, rel);
        raider.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, RaiderId), rel) { EditorID = "FO4_LvlRaider", Name = "Raider", Flags = SF.Npc.Flag.Respawn });
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, CalmProbeId), rel) { EditorID = "FO4_LvlRaider_Calm", Name = "Raider", Flags = SF.Npc.Flag.Respawn });
        raider.ModHeader.Stats.NextFormID = 0xF04802;
        var raiderPath = Path.Combine(dir, raiderKey.FileName);
        raider.BeginWrite.ToPath(raiderPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        // points as `points` writes them
        var pointsPath = Path.Combine(dir, "points.json");
        File.WriteAllText(pointsPath, """
        {"quest_name": "When Freedom Calls", "preston_name": "Preston Garvey",
         "objectives": {"10": "Find the Last Minutemen", "85": "Kill the Raiders", "86": "Talk to Preston Garvey"},
         "preston": {"src": "01E2EA:XTEL", "pos": [-880.5, 1050.25, 90.0], "rot": [0, 0, 1.5]},
         "raiders": [{"src": "046458", "pos": [-829.06, 1008.31, 88.09], "rot": [0, 0, 0.5]},
                     {"src": "046459", "pos": [-835.0, 1012.0, 88.5], "rot": [0, 0, 0.0]}],
         "codsworth": {"src": "01CA7D", "name": "Codsworth", "pos": [-1146.709, 1293.837, 111.734], "rot": [0, 0, 2.356]}}
        """);
        // every check reads the ACHRs against these points (FAL-179); merge null is the measured offset, as write's default
        int Chk(string plugin, bool alias, bool codsworth = true, string? model = null, string? voice = null, (float X, float Y)? merge = null) =>
            Check(plugin, sfPath, corePath, raiderPath, alias, codsworth, model, voice, pointsPath, merge);
        var outDir = Path.Combine(dir, "out");
        foreach (var alias in new[] { true, false })
        {
            var o = Path.Combine(outDir, alias ? "alias" : "noalias");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, alias);
            if (rc != 0) return rc;
            rc = Chk(Path.Combine(o, Plugin), alias);
            if (rc != 0) return rc;
        }
        {   // the fallback without Codsworth still writes and checks
            var o = Path.Combine(outDir, "nocodsworth");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, null);
            if (rc == 0) rc = Chk(Path.Combine(o, Plugin), true, false);
            if (rc != 0) return rc;
            if (Chk(Path.Combine(o, Plugin), true, true) == 0)
                { Console.WriteLine("FAIL  check passed a build without Codsworth when he was expected"); return 1; }
        }
        {   // Codsworth's own model: written, checked, and a model build is not a plain one (nor the other way round)
            var o = Path.Combine(outDir, "model");
            const string model = "fo4port\\actors\\codsworth\\codsworth.nif";
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, CodsworthBody, model);
            if (rc == 0) rc = Chk(Path.Combine(o, Plugin), true, true, model);
            if (rc != 0) return rc;
            if (Chk(Path.Combine(o, Plugin), true, true) == 0)
                { Console.WriteLine("FAIL  check passed a model build as a plain one"); return 1; }
            if (Chk(Path.Combine(outDir, "alias", Plugin), true, true, model) == 0)
                { Console.WriteLine("FAIL  check passed a plain build as a model one"); return 1; }
            {   // Codex 5565181946: the same file name in another folder is not his model
                var mod = SF.StarfieldMod.CreateFromBinary(Path.Combine(o, Plugin), rel, Styles(SfEsm, coreKey, raiderKey));
                mod.ArmorAddons.First().WorldModel!.Male!.File = new AssetLink<StarfieldModelAssetType>("Meshes\\Elsewhere\\" + model);
                var md = Path.Combine(outDir, "model_moved");
                Directory.CreateDirectory(md);
                var lo = new[] { SfEsm, coreKey, raiderKey };
                mod.BeginWrite.ToPath(Path.Combine(md, Plugin)).WithLoadOrder(lo)
                    .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
                if (Chk(Path.Combine(md, Plugin), true, true, model) == 0)
                    { Console.WriteLine("FAIL  check passed his model in another folder"); return 1; }
                Console.WriteLine("mutation rejected: model in another folder");
            }
            if (ModelPath("Meshes\\Actors\\x.nif", "Meshes\\" + model) != "Meshes\\" + model || ModelPath("Actors\\x.nif", model) != model)
                { Console.WriteLine("FAIL  ModelPath does not follow the vanilla prefix"); return 1; }
        }
        {   // his voice: a Hello DIAL with one INFO per line, said by him, "sir"/"mum" lines by the player's sex
            var voice = Path.Combine(dir, "voice.json");
            File.WriteAllText(voice, """
                [{"info": "000F1F6E", "response": 1, "text": "Yes?", "wem": "00F4C001", "sex": null},
                 {"info": "000F1F78", "response": 1, "text": "Sir?", "wem": "00F4C002", "sex": "male"},
                 {"info": "000F1F80", "response": 1, "text": "Mum?", "wem": "00F4C003", "sex": "female"}]
                """);
            var o = Path.Combine(outDir, "voice");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, CodsworthBody, null, voice);
            if (rc == 0) rc = Chk(Path.Combine(o, Plugin), true, true, null, voice);
            if (rc != 0) return rc;
            if (Chk(Path.Combine(o, Plugin), true, true) == 0)
                { Console.WriteLine("FAIL  check passed a voice build as a plain one"); return 1; }
            if (Chk(Path.Combine(outDir, "alias", Plugin), true, true, null, voice) == 0)
                { Console.WriteLine("FAIL  check passed a plain build as a voice one"); return 1; }
            var voiceMutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
            {
                ("a line's wem changed", m => m.Quests.First().DialogTopics[0].Responses[1].Responses[0].WEMFile = 0x00F4C009),
                ("a line said by anyone", m => m.Quests.First().DialogTopics[0].Responses[0].Conditions.Clear()),
                ("a sir line for either sex", m => m.Quests.First().DialogTopics[0].Responses[1].Conditions.RemoveAt(1)),
                ("a line's text changed", m => m.Quests.First().DialogTopics[0].Responses[2].Responses[0].ResponseText = "Sir?"),
                ("said by anyone but him", m => m.Quests.First().DialogTopics[0].Responses[0].Conditions[0].CompareOperator = SF.CompareOperator.NotEqualTo),
                ("sex read on the speaker", m => m.Quests.First().DialogTopics[0].Responses[1].Conditions[1].Data.RunOnType = SF.Condition.RunOnType.Subject),
                ("sex value 0", m => ((SF.ConditionFloat)m.Quests.First().DialogTopics[0].Responses[1].Conditions[1]).ComparisonValue = 0),
                ("sex operator NotEqualTo", m => m.Quests.First().DialogTopics[0].Responses[2].Conditions[1].CompareOperator = SF.CompareOperator.NotEqualTo),
                ("conditions ORed", m => m.Quests.First().DialogTopics[0].Responses[1].Conditions[0].Flags = SF.Condition.Flag.OR),
            };
            foreach (var (name, edit) in voiceMutations)
            {
                var mod = SF.StarfieldMod.CreateFromBinary(Path.Combine(o, Plugin), rel, Styles(SfEsm, coreKey, raiderKey));
                edit(mod);
                var md = Path.Combine(outDir, "voice_mutated");
                Directory.CreateDirectory(md);
                var lo = new[] { SfEsm, coreKey, raiderKey };
                mod.BeginWrite.ToPath(Path.Combine(md, Plugin)).WithLoadOrder(lo)
                    .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
                if (Chk(Path.Combine(md, Plugin), true, true, null, voice) == 0)
                    { Console.WriteLine($"FAIL  check passed a mutation: {name}"); return 1; }
                Console.WriteLine($"mutation rejected: {name}");
            }
        }
        {   // the merged frame (FAL-179): every ACHR at points.json + the merge offset. check refuses a merged build read as
            // a local-frame one, a check without points, and each mutation below; a build written with --merge-offset 0,0
            // (the local frame, as before FAL-179) checks with that offset only
            var merged = Path.Combine(outDir, "alias", Plugin);
            if (Chk(merged, true, merge: (0f, 0f)) == 0)
                { Console.WriteLine("FAIL  check passed a merged build as a local-frame one"); return 1; }
            if (Check(merged, sfPath, corePath, raiderPath, true) == 0)
                { Console.WriteLine("FAIL  check passed without points.json"); return 1; }
            var lf = Path.Combine(outDir, "localframe");
            int lrc = Write(sfPath, corePath, raiderPath, pointsPath, lf, Plugin, World, true, merge: (0f, 0f));
            if (lrc == 0) lrc = Chk(Path.Combine(lf, Plugin), true, merge: (0f, 0f));
            if (lrc != 0) return lrc;
            if (Chk(Path.Combine(lf, Plugin), true) == 0)
                { Console.WriteLine("FAIL  check passed a local-frame build as a merged one"); return 1; }
            static SF.PlacedNpc AchOf(SF.StarfieldMod m, uint id) =>
                m.Worldspaces.First().TopCell!.Persistent.OfType<SF.PlacedNpc>().First(r => r.FormKey.ID == id);
            static void ShiftAch(SF.StarfieldMod m, uint id, int k)
            {
                var r = AchOf(m, id);
                r.Position = new P3Float(r.Position.X + k * MergeX, r.Position.Y + k * MergeY, r.Position.Z);
            }
            var frameMutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
            {
                ("every ACHR in the local frame", m => { foreach (var id in new[] { PrestonRefId, FirstRaiderRefId, FirstRaiderRefId + 1, CodsworthRefId }) ShiftAch(m, id, -1); }),
                ("Preston offset twice", m => ShiftAch(m, PrestonRefId, 1)),
                ("a raider in the local frame", m => ShiftAch(m, FirstRaiderRefId + 1, -1)),
                ("Codsworth offset twice", m => ShiftAch(m, CodsworthRefId, 1)),
                ("Preston's z moved", m => { var r = AchOf(m, PrestonRefId); r.Position = new P3Float(r.Position.X, r.Position.Y, r.Position.Z + 5); }),
                ("Preston turned", m => { var r = AchOf(m, PrestonRefId); r.Rotation = new P3Float(r.Rotation.X, r.Rotation.Y, r.Rotation.Z + 1); }),
                ("two raiders swapped", m => { var a = AchOf(m, FirstRaiderRefId); var b = AchOf(m, FirstRaiderRefId + 1); (a.Position, b.Position) = (b.Position, a.Position); }),
                ("Preston's EditorID changed", m => AchOf(m, PrestonRefId).EditorID = "FO4SF_Min00_Preston"),
            };
            foreach (var (fname, fedit) in frameMutations)
            {
                var fmod = SF.StarfieldMod.CreateFromBinary(merged, rel, Styles(SfEsm, coreKey, raiderKey));
                fedit(fmod);
                var fd = Path.Combine(outDir, "frame_mutated");
                Directory.CreateDirectory(fd);
                var flo = new[] { SfEsm, coreKey, raiderKey };
                fmod.BeginWrite.ToPath(Path.Combine(fd, Plugin)).WithLoadOrder(flo)
                    .WithKnownMasters(flo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
                if (Chk(Path.Combine(fd, Plugin), true) == 0)
                    { Console.WriteLine($"FAIL  check passed a mutation: {fname}"); return 1; }
                Console.WriteLine($"mutation rejected: {fname}");
            }
        }
        // mutations of the default output, each of which check must reject (Codex review 5564480667)
        static SF.Quest Keeper(SF.StarfieldMod m) => m.Quests[new FormKey(m.ModKey, KeeperQuestId)];
        var good = Path.Combine(outDir, "alias", Plugin);
        var mutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
        {
            ("Codsworth NPC_ and ACHR removed", m =>
            {
                m.Npcs.Remove(new FormKey(m.ModKey, CodsworthNpcId));
                m.Worldspaces.First().TopCell!.Persistent.RemoveAll(r => r.FormKey.ID == CodsworthRefId);
            }),
            ("Codsworth ACHR removed", m => m.Worldspaces.First().TopCell!.Persistent.RemoveAll(r => r.FormKey.ID == CodsworthRefId)),
            ("Codsworth not Essential", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags &= ~SF.Npc.Flag.Essential),
            ("Codsworth not Unique", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags &= ~SF.Npc.Flag.Unique),
            ("Codsworth respawns", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags |= SF.Npc.Flag.Respawn),
            ("Codsworth script property removed", m => Keeper(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "Codsworth")),
            ("keeper quest removed", m => m.Quests.Remove(new FormKey(m.ModKey, KeeperQuestId))),
            ("keeper not start game enabled", m => Keeper(m).Data!.Flags &= ~SF.Quest.Flag.StartGameEnabled),
            ("keeper runs the mission", m => ((SF.ScriptBoolProperty)Keeper(m).VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "KeeperOnly")).Data = false),
            ("Codsworth also set on the mission", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.Add(new SF.ScriptObjectProperty
            {
                Name = "Codsworth", Flags = SF.ScriptProperty.Flag.Edited, Alias = -1,
                Object = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(m.ModKey, CodsworthRefId)),
            })),
            ("Codsworth has a faction", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Factions.Add(
                new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(new FormKey(SfEsm, 0x901)) })),
            ("quest has no QuestType", m => m.Quests.First().QuestType.Clear()),
            ("Preston without the Minutemen faction", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].Factions.Clear()),
            ("Minutemen only Friend to the player", m => m.Factions[new FormKey(m.ModKey, MinutemenFactionId)].Relations[0].Reaction = SF.CombatReaction.Friend),
            ("Minutemen Ally to another faction", m => m.Factions[new FormKey(m.ModKey, MinutemenFactionId)].Relations[0].Target.SetTo(new FormKey(SfEsm, 0x901))),
        };
        foreach (var (name, edit) in mutations)
        {
            var mod = SF.StarfieldMod.CreateFromBinary(good, rel, Styles(SfEsm, coreKey, raiderKey));
            edit(mod);
            var md = Path.Combine(outDir, "mutated");
            Directory.CreateDirectory(md);
            var mp = Path.Combine(md, Plugin);
            var lo = new[] { SfEsm, coreKey, raiderKey };
            mod.BeginWrite.ToPath(mp).WithLoadOrder(lo).WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
            if (Chk(mp, true, true) == 0)
                { Console.WriteLine($"FAIL  check passed a mutated plugin: {name}"); return 1; }
            Console.WriteLine($"mutation rejected: {name}");
        }
        if (StripTokens("Kill the Raiders (<Global=MQ102FirstRaiderCount>/<Global=MQ102FirstRaiderTotal>)") != "Kill the Raiders")
            { Console.WriteLine("FAIL  StripTokens"); return 1; }
        if (!IsCorpse("Loot_CorpseRaiderMale01", 0) || !IsCorpse("LvlRaider", 0x200) || IsCorpse("LvlRaider", 0x400))
            { Console.WriteLine("FAIL  IsCorpse"); return 1; }
        Console.WriteLine("selftest pass");
        return 0;
    }
}
