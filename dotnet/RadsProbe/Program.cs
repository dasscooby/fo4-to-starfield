// RadsProbe: can a value of our own hold rads, lower maximum health, and be lowered again? (docs/research/rads-probe.md)
//
// FO4SFRadsProbe.esm (master Starfield.esm only; adds records, overrides none):
//   AVIF  FO4SF_Rads         our own actor value, on the pattern of dotnet/NewGame's seven S.P.E.C.I.A.L. values
//                            (name, abbreviation, type, default, min, max, flags). Default 0, 0 to 1000.
//   MGEF  FO4SF_RadsEffect   one effect: archetype ValueModifier on FO4SF_Rads, self, instant. The ONE effect: the spell
//                            below uses it at +100, RadAway at -200 (the magnitude lives in the effect entry, not here).
//   SPEL  FO4SF_RadsSpell    "FO4SF Rads": FireAndForget, Self, one effect entry: FO4SF_RadsEffect, magnitude +100
//   ALCH  FO4SF_RadAway      the consumable "RadAway" (Medicine): one effect entry: FO4SF_RadsEffect, magnitude -200
//   QUST  FO4SF_RadsProbeQuest   start game enabled, stages 10 / 20 / 30 / 40, script FO4SF_RadsProbeQuest with four
//                            properties: RadsAV (ours), HealthAV (Starfield's, found by EditorID), RadsSpell, RadAway
// No hazard record (no writer exists for one). The route from rads to maximum health is the SCRIPT's (a permanent modifier
// on Health, set from the rads each step): no native code, no perk entry point. The alternatives not taken are in
// docs/research/rads-probe.md. The script reaches every form through its four properties;
// tests/test_rads_probe.py checks the properties' names against the constants here.
//
// The effect, the spell and RadAway are written as COPIES of vanilla records (found in Starfield.esm by what they are,
// or by --template-spell / --template-aid): the first session (FAL-213) crashed the game on Spell.Cast with a spell and
// effect written from nothing (a null read inside the engine), and a vanilla SPEL always carries fields (equip type,
// effect ids, description) that a from-nothing one lacks. Only what must differ is changed: editor id, name, the
// effect's actor value and magnitude; conditions, scripts, keywords and the effect's resist/skill values are cleared.
// No template found: the minimal record is written and the build says so (plan.json keeps it).
//
// usage: RadsProbe build <Starfield.esm> <out dir> [--health <AVIF editor id>] [--type <AVIF type>] [--template-spell <edid>] [--template-aid <edid>]
//        RadsProbe check <plugin> <Starfield.esm> [same options]     exit 1 on a mismatch
//        RadsProbe fixture <out dir>             a synthetic Starfield.esm holding the AVIF and the template records looked up
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    var health = "Health";
    var type = "Variable";
    bool Opt(string name, ref string into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return false;
        if (i + 1 >= rest.Count) throw new RadsProbe.Refusal($"{name} needs a value");
        into = rest[i + 1];
        rest.RemoveRange(i, 2);
        return true;
    }
    var tSpell = "";
    var tAid = "";
    Opt("--health", ref health);
    Opt("--type", ref type);
    Opt("--template-spell", ref tSpell);
    Opt("--template-aid", ref tAid);
    var tpl = new RadsProbe.Templates(tSpell, tAid);
    if (rest.Count == 3 && rest[0] == "build") return RadsProbe.Build(rest[1], rest[2], health, type, tpl);
    if (rest.Count == 3 && rest[0] == "check") return RadsProbe.Check(rest[1], rest[2], health, type, tpl);
    if (rest.Count == 2 && rest[0] == "fixture") return RadsProbe.Fixture(rest[1]);
}
catch (RadsProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: RadsProbe build <Starfield.esm> <out dir> [--health <edid>] [--type <avif type>] [--template-spell <edid>] [--template-aid <edid>] | " +
                        "check <plugin> <Starfield.esm> [same options] | fixture <out dir>");
return 2;

static class RadsProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFRadsProbe.esm");

    const uint AvifId = 0x800, EffectId = 0x801, SpellId = 0x802, RadAwayId = 0x803, QuestId = 0x804;
    const string AvifEdid = "FO4SF_Rads", EffectEdid = "FO4SF_RadsEffect", SpellEdid = "FO4SF_RadsSpell", RadAwayEdid = "FO4SF_RadAway",
        QuestEdid = "FO4SF_RadsProbeQuest", Script = "FO4SF_RadsProbeQuest";
    const float SpellMagnitude = 100f, RadAwayMagnitude = -200f, RadsMax = 1000f;
    static readonly ushort[] Stages = { 10, 20, 30, 40 };
    // the script's property names, in the order the writer adds them
    static readonly string[] PropNames = { "RadsAV", "HealthAV", "RadsSpell", "RadAway" };

    public record Templates(string SpellEdid, string AidEdid);

    /// <summary>The vanilla records the effect, the spell and RadAway are copied from (null: none found, minimal record).</summary>
    public record Found(ISpellGetter? Spell, IMagicEffectGetter? Effect, IIngestibleGetter? Aid, string Level);

    static Found FindTemplates(IStarfieldModGetter sf, Templates t)
    {
        var mgefs = sf.MagicEffects.ToDictionary(m => m.FormKey);
        bool ValueMod(IMagicEffectGetter m, bool strict) =>
            m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier &&
            (!strict || (m.CastType == CastType.FireAndForget && m.TargetType == TargetType.Self && m.Flags.HasFlag(MagicEffect.Flag.NoDuration)));
        IMagicEffectGetter? EffectOf(ISpellGetter sp) =>
            sp.Effects.Count == 1 && sp.Effects[0].BaseEffect.FormKey is { } fk && mgefs.TryGetValue(fk, out var m) ? m : null;
        ISpellGetter? spell = null;
        IMagicEffectGetter? effect = null;
        string level = "none";
        if (t.SpellEdid != "")
        {
            spell = One(sf.Spells, t.SpellEdid, "SPEL");
            effect = EffectOf(spell) ?? throw new Refusal($"{t.SpellEdid} has not exactly one effect with a record in Starfield.esm");
            level = "named";
        }
        else
        {
            foreach (var strict in new[] { true, false })
            {
                var hit = sf.Spells.Where(sp => sp.Type == Spell.SpellType.Spell && sp.CastType == CastType.FireAndForget && sp.TargetType == TargetType.Self)
                    .OrderBy(sp => sp.FormKey.ID).FirstOrDefault(sp => EffectOf(sp) is { } m && ValueMod(m, strict));
                if (hit != null) { spell = hit; effect = EffectOf(hit); level = strict ? "strict" : "relaxed"; break; }
            }
        }
        IIngestibleGetter? aid = null;
        if (t.AidEdid != "") aid = One(sf.Ingestibles, t.AidEdid, "ALCH");
        else aid = sf.Ingestibles.OrderBy(i => i.FormKey.ID).FirstOrDefault(i => i.Flags.HasFlag(Ingestible.Flag.Medicine) && i.MajorFlags.HasFlag(Ingestible.MajorFlag.Medicine) && i.Effects.Count == 1 && i.Addiction.IsNull);
        return new Found(spell, effect, aid, level);
    }

    static string Name(IMajorRecordGetter? r) => r == null ? "none (minimal record)" : $"{r.EditorID} {r.FormKey}";

    static FormKey Own(uint id) => new(Plugin, id);

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

    static ActorValueInformation.Types ParseType(string s) =>
        Enum.TryParse<ActorValueInformation.Types>(s, true, out var t) ? t
            : throw new Refusal($"--type {s} is not an AVIF type ({string.Join(", ", Enum.GetNames<ActorValueInformation.Types>())})");

    static ActorValueInformation.Flag AvifFlags => ActorValueInformation.Flag.DefaultToZero;

    // ---------------------------------------------------------------- build

    public static int Build(string templatePath, string outDir, string healthEdid, string typeName, Templates tpl)
    {
        var avType = ParseType(typeName);
        using var sf = OpenTemplate(templatePath);
        var health = One(sf.ActorValueInformation, healthEdid, "AVIF");
        var found = FindTemplates(sf, tpl);
        Console.WriteLine($"templates ({found.Level}): SPEL {Name(found.Spell)}, MGEF {Name(found.Effect)}, ALCH {Name(found.Aid)}");
        if (health.FormKey.ModKey != SfEsm) throw new Refusal($"{healthEdid} is not Starfield.esm's");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";

        var avif = new ActorValueInformation(Own(AvifId), Release)
        {
            EditorID = AvifEdid, Name = "Rads", Abbreviation = "Rad", Type = avType, DefaultValue = 0f, Min = 0f, Max = RadsMax, Flags = AvifFlags,
        };
        mod.ActorValueInformation.Add(avif);

        var arch = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
        // The actor value of a value modifier is the MGEF's SecondActorValue (DATA word 14: 321 of Starfield.esm's 853 effects
        // carry one there; word 0, the archetype's association, is the associated item and is empty in every vanilla effect).
        // The first two game sessions (FAL-213) wrote it into the association and crashed the engine at Spell.Cast: it
        // reads the actor value, finds null, and reads that null's flags.
        MagicEffect effect;
        if (found.Effect != null)
        {
            effect = (MagicEffect)found.Effect.Duplicate(Own(EffectId), new MagicEffect.TranslationMask(defaultOn: true));
            effect.EditorID = EffectEdid;
            effect.Name = "FO4SF Rads";
            effect.Description = "Rads of the FO4SF probe.";
            effect.Archetype = arch;
            effect.VirtualMachineAdapter = null;
            effect.Conditions.Clear();
            effect.Keywords = null;
            effect.MagicSkill.SetToNull();
            effect.ResistValue.SetToNull();
            effect.SecondActorValue.SetTo(avif.FormKey);
            effect.Flags &= ~MagicEffect.Flag.Detrimental;     // the engine negates the magnitude when exactly one of the effect's Detrimental flag and the actor value's damage-is-positive flag is set; neither is set here, so +100 stays +100
            effect.ThirdActorValue.SetToNull();
            effect.CounterEffects.Clear();
        }
        else
        {
            effect = new MagicEffect(Own(EffectId), Release)
            {
                EditorID = EffectEdid, Name = "FO4SF Rads", Archetype = arch,
                CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea,
            };
            effect.SecondActorValue.SetTo(avif.FormKey);
        }
        mod.MagicEffects.Add(effect);

        Effect Entry(float magnitude, IEffectGetter? from) => new()
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(effect.FormKey),
            Data = new EffectData { Magnitude = magnitude, Area = 0, Duration = 0 },
            MAGF = from?.MAGF, EFIF = from?.EFIF, MUID = from?.MUID,       // the template's ids, as a vanilla entry carries them
        };
        Spell spell;
        if (found.Spell != null)
        {
            spell = (Spell)found.Spell.Duplicate(Own(SpellId), new Spell.TranslationMask(defaultOn: true));
            spell.EditorID = SpellEdid;
            spell.Name = "FO4SF Rads";
            spell.Description = "Raises FO4SF Rads by 100.";
            spell.VirtualMachineAdapter = null;
            spell.Keywords = null;
            spell.Effects.Clear();
            spell.Effects.Add(Entry(SpellMagnitude, found.Spell.Effects[0]));
        }
        else
        {
            spell = new Spell(Own(SpellId), Release)
            {
                EditorID = SpellEdid, Name = "FO4SF Rads", Type = Spell.SpellType.Spell, CastType = CastType.FireAndForget,
                TargetType = TargetType.Self, Flags = Spell.Flag.ManualCostCalc,
            };
            spell.Effects.Add(Entry(SpellMagnitude, null));
        }
        mod.Spells.Add(spell);

        Ingestible radAway;
        if (found.Aid != null)
        {
            radAway = (Ingestible)found.Aid.Duplicate(Own(RadAwayId), new Ingestible.TranslationMask(defaultOn: true));
            radAway.EditorID = RadAwayEdid;
            radAway.Name = "RadAway";
            radAway.Description = "Lowers FO4SF Rads by 200.";
            radAway.VirtualMachineAdapter = null;
            radAway.Keywords = null;
            radAway.Addiction.SetToNull();
            radAway.AddictionChance = 0f;
            radAway.AddictionName = null;
            radAway.Effects.Clear();
            radAway.Effects.Add(Entry(RadAwayMagnitude, found.Aid.Effects[0]));
        }
        else
        {
            radAway = new Ingestible(Own(RadAwayId), Release)
            {
                EditorID = RadAwayEdid, Name = "RadAway", Weight = 0.5f, Value = 10, Flags = Ingestible.Flag.Medicine,
                MajorFlags = Ingestible.MajorFlag.Medicine,
            };
            radAway.Effects.Add(Entry(RadAwayMagnitude, null));
        }
        mod.Ingestibles.Add(radAway);

        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF rads probe", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in Stages) quest.Stages.Add(new QuestStage { Index = s });
        var script = new ScriptEntry { Name = Script, Flags = ScriptEntry.Flag.Local };
        ScriptObjectProperty Prop(string name, FormKey fk) => new()
        {
            Name = name, Flags = ScriptProperty.Flag.Edited, Object = new FormLink<IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        script.Properties.Add(Prop(PropNames[0], avif.FormKey));
        script.Properties.Add(Prop(PropNames[1], health.FormKey));
        script.Properties.Add(Prop(PropNames[2], spell.FormKey));
        script.Properties.Add(Prop(PropNames[3], radAway.FormKey));
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = 0x805;

        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): AVIF {AvifEdid} {avif.FormKey} ({avType}, 0 to {RadsMax}), " +
                          $"MGEF {EffectEdid}, SPEL {SpellEdid} (+{SpellMagnitude}), ALCH {RadAwayEdid} ({RadAwayMagnitude}), " +
                          $"QUST {QuestEdid} stages [{string.Join(",", Stages)}], HealthAV = {health.EditorID} {health.FormKey}");
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

    public static int Check(string pluginPath, string templatePath, string healthEdid, string typeName, Templates tpl)
    {
        var avType = ParseType(typeName);
        using var sf = OpenTemplate(templatePath);
        var health = One(sf.ActorValueInformation, healthEdid, "AVIF");
        var found = FindTemplates(sf, tpl);
        Console.WriteLine($"templates ({found.Level}): SPEL {Name(found.Spell)}, MGEF {Name(found.Effect)}, ALCH {Name(found.Aid)}");
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
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"records of another plugin (overrides): {string.Join(", ", foreign)}");

        var avif = mod.ActorValueInformation.SingleOrDefault();
        Need(avif?.FormKey == Own(AvifId) && avif.EditorID == AvifEdid, "not exactly our AVIF");
        if (avif != null)
        {
            Console.WriteLine($"  AVIF {avif.EditorID} {avif.FormKey} type {avif.Type} default {avif.DefaultValue} min {avif.Min} max {avif.Max} flags {avif.Flags}");
            Need(avif.Type == avType && avif.DefaultValue == 0f && avif.Min == 0f && avif.Max == RadsMax && avif.Flags == AvifFlags,
                 $"the AVIF is not a {avType}, default 0, 0 to {RadsMax}, flags {AvifFlags}");
        }

        var effect = mod.MagicEffects.SingleOrDefault();
        Need(effect?.FormKey == Own(EffectId) && effect.EditorID == EffectEdid, "not exactly one MGEF, ours");
        if (effect != null)
        {
            var arch = effect.Archetype as IMagicEffectArchetypeGetter;
            Need(arch != null, "the MGEF archetype is not a plain value modifier archetype");
            Console.WriteLine($"  MGEF {effect.EditorID} {effect.FormKey} archetype {arch?.Type} actor value (DATA word 14) {effect.SecondActorValue.FormKey} association {arch?.Association.FormKey} cast {effect.CastType} target {effect.TargetType} flags {effect.Flags}");
            Need(arch?.Type == MagicEffectArchetype.TypeEnum.ValueModifier, "the MGEF archetype is not ValueModifier");
            Need(effect.SecondActorValue.FormKey == Own(AvifId), "the MGEF's actor value (SecondActorValue, DATA word 14) is not FO4SF_Rads: the engine would read a null actor value at Spell.Cast");
            Need(arch?.Association.IsNull != false, "the MGEF's archetype association (DATA word 0) is set: vanilla value modifiers leave it empty");
            Need(!effect.Flags.HasFlag(MagicEffect.Flag.Detrimental), "the MGEF is Detrimental: with the actor value's flags the engine would negate +100");
            Need(effect.ResistValue.IsNull && effect.MagicSkill.IsNull && effect.ThirdActorValue.IsNull, "the MGEF still names a resist, skill or third actor value");
            var tm = found.Effect;
            if (tm == null) Need(effect.CastType == CastType.FireAndForget && effect.TargetType == TargetType.Self, "the MGEF is not FireAndForget / Self");
            else
            {
                Need(effect.CastType == tm.CastType && effect.TargetType == tm.TargetType && effect.Flags == (tm.Flags & ~MagicEffect.Flag.Detrimental), $"the MGEF's cast type, target or flags (other than Detrimental, cleared on purpose) differ from its template {tm.EditorID}");
                Need(effect.Sounds.Count == tm.Sounds.Count && effect.Components.Count == tm.Components.Count, $"the MGEF's sounds or components differ from its template {tm.EditorID}");
                Need(effect.Conditions.Count == 0 && effect.VirtualMachineAdapter == null && (effect.Keywords?.Count ?? 0) == 0, "the MGEF still carries conditions, a script or keywords of its template");
            }
        }

        void Entry(IReadOnlyList<IEffectGetter> list, float magnitude, string what)
        {
            Need(list.Count == 1 && list[0].BaseEffect.FormKey == Own(EffectId) && list[0].Data?.Magnitude == magnitude && list[0].Data?.Duration == 0,
                 $"{what} is not one entry of FO4SF_RadsEffect at {magnitude}, duration 0");
        }
        var spell = mod.Spells.SingleOrDefault();
        Need(spell?.FormKey == Own(SpellId) && spell.EditorID == SpellEdid, "not exactly our SPEL");
        if (spell != null)
        {
            Console.WriteLine($"  SPEL {spell.EditorID} {spell.FormKey} {spell.Type} cast {spell.CastType} target {spell.TargetType}, {spell.Effects.Count} effect(s) at {string.Join(",", spell.Effects.Select(e => e.Data?.Magnitude))}");
            Entry(spell.Effects.ToList(), SpellMagnitude, "the spell");
            var ts = found.Spell;
            if (ts == null) Need(spell.CastType == CastType.FireAndForget && spell.TargetType == TargetType.Self, "the spell is not FireAndForget / Self");
            else
            {
                Need(spell.EquipmentType.FormKey == ts.EquipmentType.FormKey && spell.CastType == ts.CastType && spell.TargetType == ts.TargetType && spell.Type == ts.Type && spell.Flags == ts.Flags,
                     $"the spell's equip type, cast type, target, type or flags differ from its template {ts.EditorID}");
                var e0 = spell.Effects.FirstOrDefault();
                Need(e0 != null && e0.MAGF == ts.Effects[0].MAGF && e0.EFIF == ts.Effects[0].EFIF && e0.MUID == ts.Effects[0].MUID, "the spell's effect entry ids (MAGF, EFIF, MUID) are not its template's");
                Need(spell.Effects.All(e => e.Conditions.Count == 0) && spell.VirtualMachineAdapter == null && (spell.Keywords?.Count ?? 0) == 0, "the spell still carries conditions, a script or keywords of its template");
            }
        }
        var radAway = mod.Ingestibles.SingleOrDefault();
        Need(radAway?.FormKey == Own(RadAwayId) && radAway.EditorID == RadAwayEdid && radAway.Name?.String == "RadAway", "not exactly our ALCH named RadAway");
        if (radAway != null)
        {
            Console.WriteLine($"  ALCH {radAway.EditorID} {radAway.FormKey} \"{radAway.Name?.String}\" flags {radAway.Flags}, {radAway.Effects.Count} effect(s) at {string.Join(",", radAway.Effects.Select(e => e.Data?.Magnitude))}");
            Entry(radAway.Effects.ToList(), RadAwayMagnitude, "RadAway");
            var ta = found.Aid;
            if (ta != null)
            {
                Need(radAway.Model?.File.GivenPath == ta.Model?.File.GivenPath && radAway.Flags == ta.Flags && radAway.MajorFlags == ta.MajorFlags, $"RadAway's model or flags differ from its template {ta.EditorID}");
                Need(radAway.Addiction.IsNull && radAway.VirtualMachineAdapter == null && (radAway.Keywords?.Count ?? 0) == 0 && radAway.Effects.All(e => e.Conditions.Count == 0), "RadAway still carries an addiction, a script, keywords or conditions of its template");
            }
        }

        var quest = mod.Quests.SingleOrDefault();
        Need(quest?.FormKey == Own(QuestId) && quest.EditorID == QuestEdid, "not exactly our QUST");
        if (quest != null)
        {
            var scripts = quest.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            var props = scripts.Count == 1 ? scripts[0].Properties.OfType<ScriptObjectProperty>().ToDictionary(p => p.Name, p => p.Object.FormKey) : new();
            Console.WriteLine($"  QUST {quest.EditorID} flags {quest.Data?.Flags} stages [{string.Join(",", quest.Stages.Select(s => s.Index))}] scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(quest.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "QUST is not start game enabled");
            Need(quest.Stages.Select(s => s.Index).SequenceEqual(Stages), "QUST stages are not 10, 20, 30, 40");
            Need(scripts.Count == 1 && scripts[0].Name == Script && scripts[0].Properties.Count == PropNames.Length, $"QUST script is not {Script} with exactly {PropNames.Length} properties");
            void P(string name, FormKey want) => Need(props.TryGetValue(name, out var fk) && fk == want, $"property {name} is not {want}");
            P(PropNames[0], Own(AvifId));
            P(PropNames[1], health.FormKey);
            P(PropNames[2], Own(SpellId));
            P(PropNames[3], Own(RadAwayId));
            foreach (var kv in props) Console.WriteLine($"    property {kv.Key} = {kv.Value}");
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
        mod.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0x00A02D), Release) { EditorID = "Health", Name = "Health" });
        mod.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0x00A02E), Release) { EditorID = "SynthOther", Name = "Other" });
        var synthArch = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
        var synthMgef = new MagicEffect(new FormKey(SfEsm, 0x00A100), Release)
        {
            EditorID = "SynthValueEffect", Name = "Synth", CastType = CastType.FireAndForget, TargetType = TargetType.Self,
            Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.Detrimental, Archetype = synthArch,       // a template with the flag that would negate
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(new FormKey(SfEsm, 0x00A200)) },
        };
        synthMgef.SecondActorValue.SetTo(new FormKey(SfEsm, 0x00A02E));            // the template's own actor value (replaced by ours)
        synthMgef.ResistValue.SetTo(new FormKey(SfEsm, 0x00A02E));
        mod.MagicEffects.Add(synthMgef);
        mod.Keywords.Add(new Keyword(new FormKey(SfEsm, 0x00A200), Release) { EditorID = "SynthKeyword" });
        var synthSpell = new Spell(new FormKey(SfEsm, 0x00A101), Release)
        {
            EditorID = "SynthSelfSpell", Name = "Synth spell", Type = Spell.SpellType.Spell, CastType = CastType.FireAndForget, TargetType = TargetType.Self,
            Flags = Spell.Flag.ManualCostCalc, Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(new FormKey(SfEsm, 0x00A200)) },
        };
        synthSpell.EquipmentType.SetTo(new FormKey(SfEsm, 0x00A300));
        synthSpell.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(synthMgef.FormKey), Data = new EffectData { Magnitude = 5f }, MAGF = 7, EFIF = 8, MUID = 9 });
        mod.Spells.Add(synthSpell);
        var synthAid = new Ingestible(new FormKey(SfEsm, 0x00A102), Release)
        {
            EditorID = "SynthAid", Name = "Synth aid", Flags = Ingestible.Flag.Medicine, MajorFlags = Ingestible.MajorFlag.Medicine,
        };
        synthAid.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(synthMgef.FormKey), Data = new EffectData { Magnitude = 5f }, MAGF = 1, EFIF = 2, MUID = 3 });
        mod.Ingestibles.Add(synthAid);
        Directory.CreateDirectory(outDir);
        mod.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")}");
        return 0;
    }
}
