// PowerArmorProbe: does Starfield still run Fallout 4's power armor path? (docs/research/power-armor-probe.md)
//
// FO4SFPowerArmorProbe.esm (master Starfield.esm only; adds records, overrides none):
//   CELL  FO4SF_PAProbeCell      an interior cell of its own (`coc FO4SF_PAProbeCell`): vanilla platform floor and lights
//                                (the constants dotnet/TestCell proved), a COC marker, the two furniture references below
//   FURN  FO4SF_PAProbeSuit      a copy of the control furniture (every field of it; the one named on the command line,
//                                NPCChairTech03_Free_270 by default) with one more keyword, FurnitureTypePowerArmor
//   REFR  suit                   FO4SF_PAProbeSuit, 2.5 m to the right of the arrival (temporary)
//   REFR  control                the vanilla control furniture itself, 2.5 m to the left (temporary): the player must
//                                be able to sit on it, or the session proves nothing
//   RACE  FO4SF_PARace           a copy of HumanRace (name replaced by a plain string)
//   QUST  FO4SF_PAProbeQuest     start game enabled, stages 10 / 20 / 30, script FO4SF_PAProbeQuest with NO properties
//                                (the script finds every form with Game.GetFormFromFile; a property would make the
//                                temporary references persistent)
// The vanilla records are found by EditorID in Starfield.esm (no FormID of Starfield.esm is assumed here except the
// TestCell ones: floor 050776, omni light 03D38C, COC marker 000032, lighting template 006658, image space 122393).
// The local ids are the script's (scripts/planet/FO4SF_PAProbeQuest.psc; tests/test_power_armor_probe.py compares).
//
// Variants (--variant race,furniture,keyword; none by default: the kit of the first PC run, 11 Nov, where stage 10 did
// nothing). The owner PC found Starfield.esm keeps Fallout 4's power armor default objects (DFOB) under the same form
// ids with an empty DATA: PowerArmorRace_DO, PowerArmorDefaultFrameFurniture_DO, PowerArmorArmorKeyword_DO. A variant
// overrides those in this plugin (a record override, no native code), each on its own so the log names which one
// SwitchToPowerArmor needs:
//   race       PowerArmorRace_DO -> FO4SF_PARace
//   furniture  PowerArmorDefaultFrameFurniture_DO -> FO4SF_PAProbeSuit, and the suit also gets isPowerArmorFrame
//   keyword    PowerArmorArmorKeyword_DO -> KYWD FO4SF_PAArmorKeyword (ours, 000807)
//   armor      PowerArmorDefaultFrameArmor_DO -> ARMO FO4SF_PAFrameArmor (ours, 000808): a copy of a plain vanilla armor
//              (--armor <editor id>, required with this variant: the tool lists candidates when it is missing) plus
//              isPowerArmorFrame, in its KWDA list and its keyword form component. The PC crash of 11 Nov (a null frame
//              armor inside the native) is why: the native takes the frame armor from this default object.
// usage: PowerArmorProbe build <Starfield.esm> <out dir> [--control <furniture editor id>] [--variant <list>] [--armor <armor editor id>] [--kw-first]
//        PowerArmorProbe check <plugin> <Starfield.esm> [--control <furniture editor id>] [--variant <list>] [--armor <armor editor id>]     exit 1 on a mismatch
//        PowerArmorProbe fixture <out dir>             a synthetic Starfield.esm holding the three records looked up
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    var control = "NPCChairTech03_Free_270";
    string Take(string flag, string dflt)
    {
        int i = rest.IndexOf(flag);
        if (i < 0) return dflt;
        if (i + 1 >= rest.Count) throw new PowerArmorProbe.Refusal($"{flag} needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }
    control = Take("--control", control);
    var armor = Take("--armor", "");
    PowerArmorProbe.KwFirst = rest.Remove("--kw-first");
    var variants = PowerArmorProbe.ParseVariants(Take("--variant", ""));
    if (rest.Count == 3 && rest[0] == "build") return PowerArmorProbe.Build(rest[1], rest[2], control, variants, armor);
    if (rest.Count == 3 && rest[0] == "check") return PowerArmorProbe.Check(rest[1], rest[2], control, variants, armor);
    if (rest.Count == 2 && rest[0] == "fixture") return PowerArmorProbe.Fixture(rest[1]);
}
catch (PowerArmorProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: PowerArmorProbe build <Starfield.esm> <out dir> [--control <edid>] [--variant race,furniture,keyword,armor] [--armor <edid>] | " +
                        "check <plugin> <Starfield.esm> [--control <edid>] [--variant ...] [--armor <edid>] | fixture <out dir>");
return 2;

static class PowerArmorProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFPowerArmorProbe.esm");

    // the layout (scripts/planet/FO4SF_PAProbeQuest.psc carries the same ids)
    const uint CellId = 0x800, SuitId = 0x801, RaceId = 0x802, QuestId = 0x803, SuitRefId = 0x804, ControlRefId = 0x805,
        CocRefId = 0x806, FirstTileId = 0x810;
    const string CellEdid = "FO4SF_PAProbeCell", SuitEdid = "FO4SF_PAProbeSuit", RaceEdid = "FO4SF_PARace",
        QuestEdid = "FO4SF_PAProbeQuest", Script = "FO4SF_PAProbeQuest";
    const string KeywordEdid = "FurnitureTypePowerArmor", HumanRaceEdid = "HumanRace", FrameKeywordEdid = "isPowerArmorFrame";
    const uint ArmorKeywordId = 0x807;
    const string ArmorKeywordEdid = "FO4SF_PAArmorKeyword";
    // --kw-first: FurnitureTypePowerArmor goes first in the suit's keyword list (PC check of 11 Nov: the copied chair's own six
    // keywords read true on the suit reference and the appended seventh, ours, read false; first is the cheap try, untested)
    public static bool KwFirst;
    const uint FrameArmorId = 0x808;
    const string FrameArmorEdid = "FO4SF_PAFrameArmor";
    // variant -> the vanilla default object it overrides
    static readonly Dictionary<string, string> Dobj = new()
    {
        ["race"] = "PowerArmorRace_DO", ["furniture"] = "PowerArmorDefaultFrameFurniture_DO", ["keyword"] = "PowerArmorArmorKeyword_DO",
        ["armor"] = "PowerArmorDefaultFrameArmor_DO",
    };
    public static List<string> ParseVariants(string list)
    {
        var v = list.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Distinct().ToList();
        var bad = v.Where(x => !Dobj.ContainsKey(x)).ToList();
        if (bad.Count > 0) throw new Refusal($"unknown variant {string.Join(", ", bad)} (race, furniture, keyword, armor)");
        return v;
    }
    static FormKey Target(string variant) => variant switch
    {
        "race" => Own(RaceId), "furniture" => Own(SuitId), "armor" => Own(FrameArmorId), _ => Own(ArmorKeywordId),
    };
    // dotnet/TestCell's vanilla forms
    const uint Floor = 0x050776, Omni = 0x03D38C, CocMarker = 0x000032, LightingTemplate = 0x006658, ImageSpace = 0x122393;
    const float Tile = 8f, LightZ = 4f;
    static readonly P3Float SuitPos = new(0, -2.5f, 0), ControlPos = new(0, 2.5f, 0), CocPos = new(-5, 0, 0.1f);
    static readonly ushort[] Stages = { 10, 20, 30 };
    const string RaceName = "FO4SF PA race";

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);
    static string F(float v) => v.ToString("0.##", CultureInfo.InvariantCulture);

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static T One<T>(IEnumerable<T> items, string edid, string what) where T : IMajorRecordGetter
    {
        var hits = items.Where(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} {what} named {edid} in Starfield.esm (one needed)");
        return hits[0];
    }

    // ---------------------------------------------------------------- build

    // the vanilla armor a frame armor copies: named with --armor; without it the tool lists what Starfield.esm has
    static IArmorGetter FrameArmorTemplate(IStarfieldModDisposableGetter sf, string armorEdid)
    {
        if (armorEdid != "") return One(sf.Armors, armorEdid, "ARMO");
        var some = sf.Armors.Where(a => a.EditorID != null).Select(a => a.EditorID!).OrderBy(x => x, StringComparer.OrdinalIgnoreCase).Take(12);
        throw new Refusal($"the armor variant copies a plain vanilla armor: name it with --armor <editor id> ({sf.Armors.Count} ARMO in Starfield.esm, " +
                          $"the first by editor ID: {string.Join(", ", some)})");
    }

    // a keyword of ours on a copied record in its KWDA list and in its keyword form component (the same two places the suit uses)
    static void AddKeywordBoth(IList<IFormLinkGetter<IKeywordGetter>> list, IList<IFormLinkGetter<IKeywordGetter>> comp, FormKey k)
    {
        if (!list.Any(x => x.FormKey == k)) list.Add(new FormLink<IKeywordGetter>(k));
        if (!comp.Any(x => x.FormKey == k)) comp.Add(new FormLink<IKeywordGetter>(k));
    }

    public static int Build(string templatePath, string outDir, string controlEdid, List<string> variants, string armorEdid = "")
    {
        using var sf = OpenTemplate(templatePath);
        var kw = One(sf.Keywords, KeywordEdid, "KYWD");
        var humanRace = One(sf.Races, HumanRaceEdid, "RACE");
        var control = One(sf.Furniture, controlEdid, "FURN");
        if (control.Keywords?.Any(k => k.FormKey == kw.FormKey) == true)
            throw new Refusal($"{controlEdid} already carries {KeywordEdid}: it is no control");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";

        // the suit furniture: the control's fields, plus the power armor keyword (nothing else differs)
        var suit = (Furniture)control.Duplicate(Own(SuitId), new Furniture.TranslationMask(defaultOn: true) { Name = false });
        suit.EditorID = SuitEdid;
        suit.Name = null;
        suit.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
        if (KwFirst) suit.Keywords.Insert(0, new FormLink<IKeywordGetter>(kw.FormKey));
        else suit.Keywords.Add(new FormLink<IKeywordGetter>(kw.FormKey));
        if (variants.Contains("furniture"))
            suit.Keywords.Add(new FormLink<IKeywordGetter>(One(sf.Keywords, FrameKeywordEdid, "KYWD").FormKey));
        // PC run of 11 Nov: `haskeyword 0003430B` on the suit reference printed 0 although the base FURN lists the keyword in
        // its KWDA, so the game does not read that list for this record. Starfield also keeps a record's keywords in a
        // keyword form component (Components): the same keywords are written there too (supported hypothesis, untested:
        // the PC compares a vanilla keyworded FURN; the script logs HasKeyword on the reference before the call)
        var comp = suit.Components.OfType<KeywordFormComponent>().FirstOrDefault();
        if (comp == null) { comp = new KeywordFormComponent(); suit.Components.Add(comp); }
        // the component is rebuilt in the list's order (FAL-342: a copy keeps the control's own component, and appending to it left
        // the power armor keyword last there under --kw-first); keywords it already held that the list lacks follow
        var held = (comp.Keywords ?? new ExtendedList<IFormLinkGetter<IKeywordGetter>>()).Select(k => k.FormKey).ToList();
        comp.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>>(
            suit.Keywords.Select(k => k.FormKey).Concat(held.Where(h => !suit.Keywords.Any(k => k.FormKey == h))).Select(k => (IFormLinkGetter<IKeywordGetter>)new FormLink<IKeywordGetter>(k)));
        mod.Furniture.Add(suit);

        var race = (Race)humanRace.Duplicate(Own(RaceId), new Race.TranslationMask(defaultOn: true) { Name = false });
        race.EditorID = RaceEdid;
        race.Name = RaceName;
        mod.Races.Add(race);

        // the frame armor of the armor variant: a copy of a plain vanilla armor plus isPowerArmorFrame
        string frameNote = "";
        if (variants.Contains("armor"))
        {
            var tmpl = FrameArmorTemplate(sf, armorEdid);
            var frameKw = One(sf.Keywords, FrameKeywordEdid, "KYWD").FormKey;
            var fa = (Armor)tmpl.Duplicate(Own(FrameArmorId), new Armor.TranslationMask(defaultOn: true) { Name = false, Description = false });
            fa.EditorID = FrameArmorEdid;
            fa.Name = null;
            fa.Description = null;
            fa.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
            var fcomp = fa.Components.OfType<KeywordFormComponent>().FirstOrDefault();
            if (fcomp == null) { fcomp = new KeywordFormComponent(); fa.Components.Add(fcomp); }
            fcomp.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
            foreach (var k in fa.Keywords) if (!fcomp.Keywords.Any(x => x.FormKey == k.FormKey)) fcomp.Keywords.Add(new FormLink<IKeywordGetter>(k.FormKey));
            AddKeywordBoth(fa.Keywords, fcomp.Keywords, frameKw);
            mod.Armors.Add(fa);
            frameNote = $"; ARMO {FrameArmorEdid} = copy of {tmpl.EditorID} {tmpl.FormKey} + {FrameKeywordEdid} {frameKw}";
        }

        // the default objects a variant overrides: the vanilla record, only its Object pointing at ours
        if (variants.Contains("keyword"))
            mod.Keywords.Add(new Keyword(Own(ArmorKeywordId), Release) { EditorID = ArmorKeywordEdid });
        foreach (var v in variants)
        {
            var d = One(sf.DefaultObjects, Dobj[v], "DFOB");
            var o = d.DeepCopy();                                        // the same FormKey: an override
            mod.DefaultObjects.Add(o);
            o.Object.SetTo(Target(v));
        }

        // the cell: platform floor, lights, COC marker, the two furniture references
        var cell = new Cell(Own(CellId), Release) { EditorID = CellEdid, Flags = Cell.Flag.IsInteriorCell };
        cell.LightingTemplate.SetTo(Sf(LightingTemplate));
        cell.ImageSpace.SetTo(Sf(ImageSpace));
        cell.EnvironmentMap = "Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds";
        uint next = FirstTileId;
        var zero = new P3Float(0, 0, 0);
        PlacedObject Ref(uint id, FormKey b, P3Float pos, P3Float rot, string? edid = null) =>
            new(Own(id), Release) { EditorID = edid, Base = new FormLinkNullable<IPlaceableObjectGetter>(b), Position = pos, Rotation = rot };
        cell.Temporary.Add(Ref(CocRefId, Sf(CocMarker), CocPos, new P3Float(0, 0, (float)(Math.PI / 2))));       // facing +X
        cell.Temporary.Add(Ref(SuitRefId, suit.FormKey, SuitPos, zero, "FO4SF_PAProbeSuitRef"));
        cell.Temporary.Add(Ref(ControlRefId, control.FormKey, ControlPos, zero, "FO4SF_PAProbeControlRef"));
        for (float x = -Tile; x <= Tile; x += Tile)
            for (float y = -Tile; y <= Tile; y += Tile) cell.Temporary.Add(Ref(next++, Sf(Floor), new P3Float(x, y, 0), zero));
        for (float x = -4; x <= 4; x += 8)
            for (float y = -4; y <= 4; y += 8) cell.Temporary.Add(Ref(next++, Sf(Omni), new P3Float(x, y, LightZ), zero));
        var cid = cell.FormKey.ID;
        var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);

        // the quest (dotnet/PlanetProbe's proven shape), three stages, no properties
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF power armor probe", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in Stages) quest.Stages.Add(new QuestStage { Index = s });
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = Script, Flags = ScriptEntry.Flag.Local });
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = next;

        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): CELL {CellEdid} {cell.FormKey}, FURN {SuitEdid} = copy of " +
                          $"{control.EditorID} {control.FormKey} + {kw.EditorID} {kw.FormKey}, control reference of {control.EditorID}, " +
                          $"RACE {RaceEdid} = copy of {humanRace.EditorID} {humanRace.FormKey}, QUST {QuestEdid} stages [{string.Join(",", Stages)}]" +
                          frameNote + (variants.Count == 0 ? "" : "; variant " + string.Join(",", variants) + ": " + string.Join(", ", variants.Select(v => $"{Dobj[v]} -> {Target(v)}"))));
        return 0;
    }

    static void Write(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        // an existing plugin stays until the write succeeds; Mutagen needs the plugin's own file name, so write in a temp folder
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray()).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check (Mutagen read-back)

    public static int Check(string pluginPath, string templatePath, string controlEdid, List<string> variants, string armorEdid = "")
    {
        using var sf = OpenTemplate(templatePath);
        var kw = One(sf.Keywords, KeywordEdid, "KYWD");
        var humanRace = One(sf.Races, HumanRaceEdid, "RACE");
        var control = One(sf.Furniture, controlEdid, "FURN");
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm }), "masters are not exactly [Starfield.esm]");

        // adds, never overrides, except the default objects of the variant: every other record carries our own FormKey
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin && r is not IDefaultObjectGetter)
            .Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");
        var armors = mod.Armors.ToList();
        Need(armors.Count == (variants.Contains("armor") ? 1 : 0), $"{armors.Count} armor(s) of ours, {(variants.Contains("armor") ? 1 : 0)} expected");
        if (variants.Contains("armor") && armors.Count == 1)
        {
            var tmpl = FrameArmorTemplate(sf, armorEdid);
            var frameKw = One(sf.Keywords, FrameKeywordEdid, "KYWD").FormKey;
            var fa = armors[0];
            var akw = fa.Keywords?.Select(k => k.FormKey).ToList() ?? new();
            var ack = fa.Components.OfType<IKeywordFormComponentGetter>().SelectMany(c => c.Keywords ?? Enumerable.Empty<IFormLinkGetter<IKeywordGetter>>()).Select(k => k.FormKey).ToList();
            Console.WriteLine($"  ARMO {fa.EditorID} {fa.FormKey} (copy of {tmpl.EditorID} {tmpl.FormKey}) keywords [{string.Join(", ", akw)}] component [{string.Join(", ", ack)}] armor rating {fa.ArmorRating}");
            Need(fa.FormKey == Own(FrameArmorId) && fa.EditorID == FrameArmorEdid, "not exactly our frame armor");
            Need(akw.Contains(frameKw) && ack.Contains(frameKw), $"the frame armor does not carry {FrameKeywordEdid} in its KWDA list and its keyword form component");
            Need((tmpl.Keywords ?? Enumerable.Empty<IFormLinkGetter<IKeywordGetter>>()).Select(k => k.FormKey).All(akw.Contains), "the frame armor lost a keyword of the armor it copies");
            Need(fa.ArmorRating == tmpl.ArmorRating && fa.Value == tmpl.Value, "the frame armor's rating or value differs from the armor it copies");
        }
        var dobjs = mod.DefaultObjects.ToList();
        Need(dobjs.Count == variants.Count, $"{dobjs.Count} default object override(s), {variants.Count} variant(s) ({string.Join(",", variants)})");
        foreach (var v in variants)
        {
            var vanilla = One(sf.DefaultObjects, Dobj[v], "DFOB");
            var got = dobjs.FirstOrDefault(d => d.FormKey == vanilla.FormKey);
            Console.WriteLine($"  DFOB {Dobj[v]} {vanilla.FormKey} Object {got?.Object.FormKeyNullable} (vanilla: {vanilla.Object.FormKeyNullable})");
            Need(got != null && got.Object.FormKeyNullable == Target(v), $"{Dobj[v]} does not point at {Target(v)}");
        }
        Need(mod.Keywords.Select(k => k.FormKey).SequenceEqual(variants.Contains("keyword") ? new[] { Own(ArmorKeywordId) } : Array.Empty<FormKey>()),
             "keywords of ours are not exactly the armor keyword of the keyword variant");

        var suit = mod.Furniture.SingleOrDefault();
        Need(suit?.FormKey == Own(SuitId) && suit.EditorID == SuitEdid, "not exactly our FURN");
        if (suit != null)
        {
            var keys = suit.Keywords?.Select(k => k.FormKey).ToList() ?? new();
            var want = (control.Keywords?.Select(k => k.FormKey) ?? Enumerable.Empty<FormKey>()).ToList();
            if (KwFirst) want.Insert(0, kw.FormKey); else want.Add(kw.FormKey);
            if (variants.Contains("furniture")) want.Add(One(sf.Keywords, FrameKeywordEdid, "KYWD").FormKey);
            Console.WriteLine($"  FURN {suit.EditorID} keywords [{string.Join(", ", keys)}] (control {control.EditorID} {control.FormKey}: {control.Keywords?.Count ?? 0} keywords) marker model {suit.MarkerModel}");
            Need(keys.SequenceEqual(want), $"FURN keywords are not the control's plus {kw.EditorID} {kw.FormKey}" + (variants.Contains("furniture") ? $" plus {FrameKeywordEdid}" : ""));
            var ck = suit.Components.OfType<IKeywordFormComponentGetter>().SelectMany(c => c.Keywords ?? Enumerable.Empty<IFormLinkGetter<IKeywordGetter>>()).Select(k => k.FormKey).ToList();
            Console.WriteLine($"  FURN keyword form component [{string.Join(", ", ck)}]");
            Need(ck.Take(want.Count).SequenceEqual(want), "the FURN's keyword form component does not start with its KWDA list, in the same order");
            Need(suit.MarkerModel == control.MarkerModel, "FURN marker model differs from the control's");
            Need((suit.MarkerParameters?.Count ?? 0) == (control.MarkerParameters?.Count ?? 0), "FURN marker parameters differ from the control's");
            Need((suit.MarkerEntryPoints?.Count ?? 0) == (control.MarkerEntryPoints?.Count ?? 0), "FURN entry points differ from the control's");
        }

        var race = mod.Races.SingleOrDefault();
        Need(race?.FormKey == Own(RaceId) && race.EditorID == RaceEdid, "not exactly our RACE");
        if (race != null) Console.WriteLine($"  RACE {race.EditorID} {race.FormKey} (copy of {humanRace.EditorID} {humanRace.FormKey}) name {race.Name?.String}");

        var cell = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).SingleOrDefault();
        Need(cell?.FormKey == Own(CellId) && cell.EditorID == CellEdid, "not exactly our CELL");
        if (cell != null)
        {
            Need(cell.Flags is { } fl && (fl & Cell.Flag.IsInteriorCell) != 0, "CELL is not an interior");
            Need(cell.Persistent.Count == 0, "CELL has persistent references (the probe's are temporary)");
            var objs = cell.Temporary.OfType<IPlacedObjectGetter>().ToDictionary(o => o.FormKey);
            void Ref(uint id, FormKey b, P3Float pos, string what)
            {
                var ok = objs.TryGetValue(Own(id), out var o);
                Need(ok && o!.Base.FormKey == b && o.Position == pos && (o.MajorRecordFlagsRaw & 0x400) == 0, what);
                if (ok) Console.WriteLine($"  REFR {o!.FormKey} {o.EditorID} base {o.Base.FormKey} at ({F(o.Position.X)}, {F(o.Position.Y)}, {F(o.Position.Z)})");
            }
            Ref(SuitRefId, Own(SuitId), SuitPos, "the suit reference (base, position, temporary)");
            Ref(ControlRefId, control.FormKey, ControlPos, "the control reference (base, position, temporary)");
            Ref(CocRefId, Sf(CocMarker), CocPos, "the COC marker");
            Console.WriteLine($"  CELL {cell.EditorID} {cell.FormKey}: {objs.Count} temporary references");
        }

        var quest = mod.Quests.SingleOrDefault();
        Need(quest?.FormKey == Own(QuestId) && quest.EditorID == QuestEdid, "not exactly our QUST");
        if (quest != null)
        {
            var scripts = quest.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Console.WriteLine($"  QUST {quest.EditorID} flags {quest.Data?.Flags} stages [{string.Join(",", quest.Stages.Select(s => s.Index))}] scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(quest.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "QUST is not start game enabled");
            Need(quest.Stages.Select(s => s.Index).SequenceEqual(Stages), "QUST stages are not 10, 20, 30");
            Need(scripts.Count == 1 && scripts[0].Name == Script && scripts[0].Properties.Count == 0, $"QUST script is not {Script} without properties");
        }
        var kinds = mod.EnumerateMajorRecords().GroupBy(r => r.GetType().Name.Replace("BinaryOverlay", "")).Select(g => $"{g.Key} {g.Count()}");
        Console.WriteLine($"  records: {string.Join(", ", kinds)}");
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture

    public static int Fixture(string outDir)
    {
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var kw = new Keyword(Sf(0x0F4A21), Release) { EditorID = KeywordEdid };
        var other = new Keyword(Sf(0x000900), Release) { EditorID = "SynthFurnitureKeyword" };
        mod.Keywords.Add(kw);
        mod.Keywords.Add(other);
        mod.Keywords.Add(new Keyword(Sf(0x15503F), Release) { EditorID = FrameKeywordEdid });
        // the three empty default objects (Starfield.esm: DATA none), under Fallout 4's form ids
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x05C254), Release) { EditorID = "PowerArmorRace_DO" });
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x22BC97), Release) { EditorID = "PowerArmorDefaultFrameFurniture_DO" });
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x140C44), Release) { EditorID = "PowerArmorArmorKeyword_DO" });
        mod.Races.Add(new Race(Sf(0x013746), Release) { EditorID = HumanRaceEdid });
        mod.Armors.Add(new Armor(Sf(0x0A0001), Release) { EditorID = "SynthPlainArmor", ArmorRating = 7, Value = 33,
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(other.FormKey) } });
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x15503E), Release) { EditorID = "PowerArmorDefaultFrameArmor_DO" });
        mod.Furniture.Add(new Furniture(Sf(0x0027D5), Release)
        {
            EditorID = "NPCChairTech03_Free_270", MarkerModel = "Markers\\FurnitureMarkers\\ChairNeutral_Free_Marker.nif",
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(other.FormKey) },
            // the real chair has a keyword form component of its own; a copy keeps it (FAL-342)
            Components = new ExtendedList<AComponent> { new KeywordFormComponent { Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(other.FormKey) } } },
            MarkerParameters = new ExtendedList<FurnitureMarkerParameters> { new FurnitureMarkerParameters { Offset = new P3Float(0, 0.12f, 0) } },
            MarkerEntryPoints = new ExtendedList<FurnitureMarkerEntryPoints> { new FurnitureMarkerEntryPoints() },
        });
        mod.Furniture.Add(new Furniture(Sf(0x0027D6), Release) { EditorID = "SynthAlreadyPowerArmor",
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(kw.FormKey) } });
        Directory.CreateDirectory(outDir);
        mod.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")}");
        return 0;
    }
}
