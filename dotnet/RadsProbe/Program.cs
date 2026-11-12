// RadsProbe: can a value of our own hold rads, lower maximum health, and be lowered again? (docs/research/rads-probe.md)
//
// FO4SFRadsProbe.esm (master Starfield.esm only; adds records, overrides none):
//   AVIF  FO4SF_Rads         our own actor value, on the pattern of dotnet/NewGame's seven S.P.E.C.I.A.L. values
//                            (name, abbreviation, type, default, min, max, flags). Default 0, 0 to 1000.
//   MGEF  FO4SF_RadsEffect   the rads effect: archetype ValueModifier on FO4SF_Rads (the actor value in DATA word 14), a copy of
//                            the vanilla DamageHealthContact (its flags kept, Detrimental included). The spell uses it at +100.
//   SPEL  FO4SF_RadsSpell    "FO4SF Rads": a copy of the vanilla DamageHealthSpell, one entry: FO4SF_RadsEffect, magnitude +100
//   ALCH  FO4SF_RadAway      the consumable "RadAway" (Medicine), a copy of a vanilla medicine's shell. Two shapes:
//                            mirror: its own MGEF FO4SF_RadAwayEffect (a copy of a vanilla restore-Health effect, NOT Detrimental,
//                            from an ingestible or, when no ingestible has one, from a spell) at +200: the plugin then holds two MGEF;
//                            fallback (no restore effect found anywhere): the rads effect shared at -200: one MGEF.
//   ALCH  FO4SF_RadDose      the test item "Rad Dose" (Medicine, a copy of the same template): one entry, FO4SF_RadsEffect at +100
//   QUST  FO4SF_RadsHandQuest    the by-hand mode (FAL-273): start game enabled, no console: gives three RadAway and three Rad Dose
//                            and shows every change of the rads on screen; script FO4SF_RadsHandQuest, four properties: RadsAV,
//                            HealthAV, RadAway, RadDose. The idle FO4SF_RadsProbeQuest below is untouched by it.
//   AVIF flags DefaultToZero | DamageIsPositive (bit 26): with the effect's Detrimental the engine's sign rule leaves +100 as
//                            +100, and the non-Detrimental +200 of the mirror lowers the value.
//   QUST  FO4SF_RadsProbeQuest   start game enabled, stages 10 / 20 / 30 / 40 / 50, script FO4SF_RadsProbeQuest with four
//                            properties (RadsAV, HealthAV, RadsSpell, RadAway) and a fifth, ControlSpell, only with --control-spell
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
//                                                    [--restore-spell <SPEL edid>] [--control-spell <SPEL edid>]
//        RadsProbe check <plugin> <Starfield.esm> [same options]     exit 1 on a mismatch
//        RadsProbe fixture <out dir> [--restore aid|spell|none]   a synthetic Starfield.esm holding the AVIF and the template records
//                                                    looked up (restore: where the Health restore effect lives; none: the fallback)
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
    var cSpell = "";
    Opt("--control-spell", ref cSpell);
    var rSpell = "";
    Opt("--restore-spell", ref rSpell);
    var restoreMode = "aid";
    Opt("--restore", ref restoreMode);
    var tpl = new RadsProbe.Templates(tSpell, tAid, cSpell, rSpell);
    if (rest.Count == 3 && rest[0] == "build") return RadsProbe.Build(rest[1], rest[2], health, type, tpl);
    if (rest.Count == 3 && rest[0] == "check") return RadsProbe.Check(rest[1], rest[2], health, type, tpl);
    if (rest.Count == 2 && rest[0] == "fixture") return RadsProbe.Fixture(rest[1], restoreMode);
}
catch (RadsProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: RadsProbe build <Starfield.esm> <out dir> [--health <edid>] [--type <avif type>] [--template-spell <edid>] [--template-aid <edid>] [--control-spell <edid>] | " +
                        "check <plugin> <Starfield.esm> [same options] | fixture <out dir>");
return 2;

static class RadsProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFRadsProbe.esm");

    const uint AvifId = 0x800, EffectId = 0x801, SpellId = 0x802, RadAwayId = 0x803, QuestId = 0x804, RadAwayEffectId = 0x805, DoseId = 0x806, HandQuestId = 0x807;
    const string AvifEdid = "FO4SF_Rads", EffectEdid = "FO4SF_RadsEffect", SpellEdid = "FO4SF_RadsSpell", RadAwayEdid = "FO4SF_RadAway", RadAwayEffectEdid = "FO4SF_RadAwayEffect",
        QuestEdid = "FO4SF_RadsProbeQuest", Script = "FO4SF_RadsProbeQuest",
        DoseEdid = "FO4SF_RadDose", HandQuestEdid = "FO4SF_RadsHandQuest", HandScript = "FO4SF_RadsHandQuest";
    const string PreferredSpell = "DamageHealthSpell";
    const float SpellMagnitude = 100f, RadAwayMagnitude = -200f, RadAwayMirrorMagnitude = 200f, DoseMagnitude = 100f, RadsMax = 1000f;
    static readonly ushort[] Stages = { 10, 20, 30, 40, 50 };
    // the script's property names, in the order the writer adds them
    static readonly string[] PropNames = { "RadsAV", "HealthAV", "RadsSpell", "RadAway", "ControlSpell" };   // the fifth only with --control-spell
    static readonly string[] HandPropNames = { "RadsAV", "HealthAV", "RadAway", "RadDose" };

    public record Templates(string SpellEdid, string AidEdid, string ControlSpell = "", string RestoreSpell = "");

    /// <summary>The vanilla records the effect, the spell and RadAway are copied from (null: none found, minimal record).</summary>
    public record Found(ISpellGetter? Spell, IMagicEffectGetter? Effect, IIngestibleGetter? Aid, string Level, IMagicEffectGetter? AidEffect = null, IEffectGetter? AidEntry = null)
    {
        /// <summary>RadAway gets an effect of its own, the copy of its template's (a restore pattern); else it shares the spell's.</summary>
        public bool Mirror => Aid != null && AidEffect != null;
    }

    static Found FindTemplates(IStarfieldModGetter sf, Templates t, FormKey healthKey)
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
        else if (sf.Spells.Where(sp => string.Equals(sp.EditorID, PreferredSpell, StringComparison.OrdinalIgnoreCase)).ToList() is { Count: 1 } pref && EffectOf(pref[0]) is { } prefEffect)
        {
            // Fourth game session (FAL-213): the vanilla DamageHealthSpell moved Health from a quest script's Cast and the copies of
            // an artifact power (a Starborn power with a cost, another equip type) did not. Its one effect, DamageHealthContact, is
            // all zero but the actor value and a few trailing words, so only the actor value changes for ours.
            spell = pref[0]; effect = prefEffect; level = "preferred";
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
        IMagicEffectGetter? aidEffect = null;
        IEffectGetter? aidEntry = null;
        if (t.AidEdid != "")
        {
            aid = One(sf.Ingestibles, t.AidEdid, "ALCH");
            aidEffect = aid.Effects.Count == 1 && aid.Effects[0].BaseEffect.FormKey is { } afk && mgefs.TryGetValue(afk, out var am) ? am : null;
            aidEntry = aid.Effects[0];
        }
        else
        {
            // a restore pattern first: an ingestible whose one entry has duration 0 and whose effect is a value modifier on Health
            // that is not Detrimental (the mirror of the spell: on a damage-is-positive value it lowers the number); else any
            // single-effect medicine, instant first (the old shell, the effect then shared with the spell)
            var singles = sf.Ingestibles.Where(i => i.Effects.Count == 1 && i.Addiction.IsNull).OrderBy(i => i.FormKey.ID).ToList();
            foreach (var i in singles)
            {
                if (i.Effects[0].BaseEffect.FormKey is { } fk && mgefs.TryGetValue(fk, out var m) && m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier &&
                    m.SecondActorValue.FormKey == healthKey && !m.Flags.HasFlag(MagicEffect.Flag.Detrimental) && i.Effects[0].Data?.Duration == 0)
                { aid = i; aidEffect = m; aidEntry = i.Effects[0]; break; }
            }
            if (aid == null)
            {
                var meds = singles.Where(i => i.Flags.HasFlag(Ingestible.Flag.Medicine) && i.MajorFlags.HasFlag(Ingestible.MajorFlag.Medicine)).ToList();
                aid = meds.FirstOrDefault(i => i.Effects[0].Data?.Duration == 0) ?? meds.FirstOrDefault();
            }
        }
        // No restore ingestible (the real Starfield.esm has exactly one Health ingestible, ShipRepairKit, entry duration 10): the
        // restore effect comes from a SPELL's entry instead (--restore-spell, else Dueling_RestoreHealth_Spell, else the first
        // single-effect spell with a non-Detrimental Health value modifier and an entry of duration 0), and goes into the shell.
        if (aid != null && aidEffect == null && t.AidEdid == "")
        {
            bool Restore(ISpellGetter sp) => sp.Effects.Count == 1 && sp.Effects[0].Data?.Duration == 0 && EffectOf(sp) is { } m &&
                m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && m.SecondActorValue.FormKey == healthKey && !m.Flags.HasFlag(MagicEffect.Flag.Detrimental);
            ISpellGetter? rs = null;
            if (t.RestoreSpell != "") rs = One(sf.Spells, t.RestoreSpell, "SPEL");
            else rs = sf.Spells.Where(sp => string.Equals(sp.EditorID, "Dueling_RestoreHealth_Spell", StringComparison.OrdinalIgnoreCase)).FirstOrDefault(Restore)
                      ?? sf.Spells.Where(Restore).OrderBy(sp => sp.FormKey.ID).FirstOrDefault();
            if (rs != null)
            {
                aidEffect = EffectOf(rs) ?? throw new Refusal($"{rs.EditorID} has not exactly one effect with a record in Starfield.esm");
                aidEntry = rs.Effects[0];
            }
        }
        return new Found(spell, effect, aid, level, aidEffect, aidEntry);
    }

    /// <summary>A copy of a vanilla value-modifier effect for one of our values: only the actor value changes (and the editor id and
    /// name); the template's own flags are kept; conditions, scripts, keywords, resist and skill values are cleared.</summary>
    static MagicEffect CopyEffect(IMagicEffectGetter tm, uint id, string edid, string name, string description, FormKey av)
    {
        var e = (MagicEffect)tm.Duplicate(Own(id), new MagicEffect.TranslationMask(defaultOn: true));
        e.EditorID = edid;
        e.Name = name;
        e.Description = description;
        var arch = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);   // the association stays empty
        e.Archetype = arch;
        e.VirtualMachineAdapter = null;
        e.Conditions.Clear();
        e.Keywords = null;
        e.MagicSkill.SetToNull();
        e.ResistValue.SetToNull();
        e.SecondActorValue.SetTo(av);
        e.ThirdActorValue.SetToNull();
        e.CounterEffects.Clear();
        return e;
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

    // Fifth game session (FAL-213): Detrimental kept on the effect and the value flagged "damage is positive" (bit 26, Fallout 4's own
    // way of declaring Rads); by the owner PC's reading the engine negates a magnitude when exactly one of the two is set, so
    // the spell's +100 stays +100 and a restore-pattern effect (not Detrimental) of +200 lowers the value by 200.
    static ActorValueInformation.Flag AvifFlags => ActorValueInformation.Flag.DefaultToZero | ActorValueInformation.Flag.DamageIsPositive;

    // ---------------------------------------------------------------- build

    public static int Build(string templatePath, string outDir, string healthEdid, string typeName, Templates tpl)
    {
        var avType = ParseType(typeName);
        using var sf = OpenTemplate(templatePath);
        var health = One(sf.ActorValueInformation, healthEdid, "AVIF");
        var found = FindTemplates(sf, tpl, health.FormKey);
        Console.WriteLine($"templates ({found.Level}): SPEL {Name(found.Spell)}, MGEF {Name(found.Effect)}, ALCH {Name(found.Aid)}{(found.Mirror ? $", RadAway MGEF {Name(found.AidEffect)}" : ", RadAway shares the spell's effect")}");
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
            // Flags kept as the template's, Detrimental included (fifth session): the vanilla damage spell lands once and stays; the
            // sign comes from the value's own damage-is-positive flag (AvifFlags).
            effect = CopyEffect(found.Effect, EffectId, EffectEdid, "FO4SF Rads", "Rads of the FO4SF probe.", avif.FormKey);
        }
        else
        {
            effect = new MagicEffect(Own(EffectId), Release)
            {
                EditorID = EffectEdid, Name = "FO4SF Rads", Archetype = arch,
                CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea,
            };
            effect.SecondActorValue.SetTo(avif.FormKey);
        }
        mod.MagicEffects.Add(effect);

        Effect Entry(float magnitude, IEffectGetter? from, FormKey? baseEffect = null) => new()
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(baseEffect ?? effect.FormKey),
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
            if (found.Mirror)
            {
                // RadAway's own effect: a copy of the template's restore effect (not Detrimental), pointed at our value; on a
                // damage-is-positive value its +200 should lower the number by 200 (the owner PC's reading of the sign rule)
                var radEffect = CopyEffect(found.AidEffect!, RadAwayEffectId, RadAwayEffectEdid, "FO4SF RadAway", "Lowers FO4SF Rads.", avif.FormKey);
                mod.MagicEffects.Add(radEffect);
                radAway.Effects.Add(Entry(RadAwayMirrorMagnitude, found.AidEntry ?? found.Aid.Effects[0], radEffect.FormKey));
            }
            else radAway.Effects.Add(Entry(RadAwayMagnitude, found.Aid.Effects[0]));
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

        // the by-hand test item: the same template as RadAway, the same effect, +100 instead of -200
        Ingestible dose;
        if (found.Aid != null)
        {
            dose = (Ingestible)found.Aid.Duplicate(Own(DoseId), new Ingestible.TranslationMask(defaultOn: true));
            dose.EditorID = DoseEdid;
            dose.Name = "Rad Dose";
            dose.Description = "Raises FO4SF Rads by 100. A test item.";
            dose.VirtualMachineAdapter = null;
            dose.Keywords = null;
            dose.Addiction.SetToNull();
            dose.AddictionChance = 0f;
            dose.AddictionName = null;
            dose.Effects.Clear();
            dose.Effects.Add(Entry(DoseMagnitude, found.Aid.Effects[0]));
        }
        else
        {
            dose = new Ingestible(Own(DoseId), Release)
            {
                EditorID = DoseEdid, Name = "Rad Dose", Weight = 0.5f, Value = 10, Flags = Ingestible.Flag.Medicine,
                MajorFlags = Ingestible.MajorFlag.Medicine,
            };
            dose.Effects.Add(Entry(DoseMagnitude, null));
        }
        mod.Ingestibles.Add(dose);

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
        if (tpl.ControlSpell != "")          // stage 50: a vanilla instant value effect on Health, cast from the same script (second control)
            script.Properties.Add(Prop(PropNames[4], One(sf.Spells, tpl.ControlSpell, "SPEL").FormKey));
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        mod.Quests.Add(quest);

        var handQuest = new Quest(Own(HandQuestId), Release)
        {
            EditorID = HandQuestEdid, Name = "FO4SF rads by hand", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        handQuest.Stages.Add(new QuestStage { Index = 10 });
        var handScript = new ScriptEntry { Name = HandScript, Flags = ScriptEntry.Flag.Local };
        handScript.Properties.Add(Prop(HandPropNames[0], avif.FormKey));
        handScript.Properties.Add(Prop(HandPropNames[1], health.FormKey));
        handScript.Properties.Add(Prop(HandPropNames[2], radAway.FormKey));
        handScript.Properties.Add(Prop(HandPropNames[3], dose.FormKey));
        handQuest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        handQuest.VirtualMachineAdapter.Scripts.Add(handScript);
        mod.Quests.Add(handQuest);
        mod.ModHeader.Stats.NextFormID = 0x808;      // 0x805 is RadAway's own effect (only built with the mirror), 0x806 the Rad Dose, 0x807 the hand quest

        Write(mod, outDir, SfEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): AVIF {AvifEdid} {avif.FormKey} ({avType}, 0 to {RadsMax}), " +
                          $"MGEF {EffectEdid}, SPEL {SpellEdid} (+{SpellMagnitude}), ALCH {RadAwayEdid} ({(found.Mirror ? RadAwayMirrorMagnitude : RadAwayMagnitude):+0;-0}), ALCH {DoseEdid} (+{DoseMagnitude}), " +
                          $"QUST {HandQuestEdid}, QUST {QuestEdid} stages [{string.Join(",", Stages)}], HealthAV = {health.EditorID} {health.FormKey}");
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
        var found = FindTemplates(sf, tpl, health.FormKey);
        Console.WriteLine($"templates ({found.Level}): SPEL {Name(found.Spell)}, MGEF {Name(found.Effect)}, ALCH {Name(found.Aid)}{(found.Mirror ? $", RadAway MGEF {Name(found.AidEffect)}" : ", RadAway shares the spell's effect")}");
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

        var effect = mod.MagicEffects.FirstOrDefault(m => m.FormKey == Own(EffectId));
        Need(mod.MagicEffects.Count == (found.Mirror ? 2 : 1), $"the plugin does not hold exactly {(found.Mirror ? 2 : 1)} MGEF (the rads effect{(found.Mirror ? " and RadAway's" : "")})");
        Need(effect != null && effect.EditorID == EffectEdid, "our rads MGEF is missing");
        if (effect != null)
        {
            var arch = effect.Archetype as IMagicEffectArchetypeGetter;
            Need(arch != null, "the MGEF archetype is not a plain value modifier archetype");
            Console.WriteLine($"  MGEF {effect.EditorID} {effect.FormKey} archetype {arch?.Type} actor value (DATA word 14) {effect.SecondActorValue.FormKey} association {arch?.Association.FormKey} cast {effect.CastType} target {effect.TargetType} flags {effect.Flags}");
            Need(arch?.Type == MagicEffectArchetype.TypeEnum.ValueModifier, "the MGEF archetype is not ValueModifier");
            Need(effect.SecondActorValue.FormKey == Own(AvifId), "the MGEF's actor value (SecondActorValue, DATA word 14) is not FO4SF_Rads: the engine would read a null actor value at Spell.Cast");
            Need(arch?.Association.IsNull != false, "the MGEF's archetype association (DATA word 0) is set: vanilla value modifiers leave it empty");
            Need(effect.ResistValue.IsNull && effect.MagicSkill.IsNull && effect.ThirdActorValue.IsNull, "the MGEF still names a resist, skill or third actor value");
            var tm = found.Effect;
            if (tm == null) Need(effect.CastType == CastType.FireAndForget && effect.TargetType == TargetType.Self, "the MGEF is not FireAndForget / Self");
            else
            {
                Need(effect.CastType == tm.CastType && effect.TargetType == tm.TargetType && effect.Flags == tm.Flags, $"the MGEF's cast type, target or flags differ from its template {tm.EditorID}");
                Need(effect.Sounds.Count == tm.Sounds.Count && effect.Components.Count == tm.Components.Count, $"the MGEF's sounds or components differ from its template {tm.EditorID}");
                Need(effect.Conditions.Count == 0 && effect.VirtualMachineAdapter == null && (effect.Keywords?.Count ?? 0) == 0, "the MGEF still carries conditions, a script or keywords of its template");
            }
        }

        void Entry(IReadOnlyList<IEffectGetter> list, float magnitude, string what, uint effectId = EffectId)
        {
            Need(list.Count == 1 && list[0].BaseEffect.FormKey == Own(effectId) && list[0].Data?.Magnitude == magnitude && list[0].Data?.Duration == 0,
                 $"{what} is not one entry of {Own(effectId)} at {magnitude}, duration 0");
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
        Need(mod.Ingestibles.Count() == 2, "not exactly two ALCH (RadAway and the Rad Dose)");
        var radAway = mod.Ingestibles.FirstOrDefault(i => i.FormKey == Own(RadAwayId));
        Need(radAway?.FormKey == Own(RadAwayId) && radAway.EditorID == RadAwayEdid && radAway.Name?.String == "RadAway", "not exactly our ALCH named RadAway");
        if (radAway != null)
        {
            Console.WriteLine($"  ALCH {radAway.EditorID} {radAway.FormKey} \"{radAway.Name?.String}\" flags {radAway.Flags}, {radAway.Effects.Count} effect(s) at {string.Join(",", radAway.Effects.Select(e => e.Data?.Magnitude))}");
            if (found.Mirror)
            {
                Entry(radAway.Effects.ToList(), RadAwayMirrorMagnitude, "RadAway", RadAwayEffectId);
                var re = mod.MagicEffects.FirstOrDefault(m => m.FormKey == Own(RadAwayEffectId));
                Need(re != null && re.EditorID == RadAwayEffectEdid, "RadAway's own MGEF is missing");
                if (re != null)
                {
                    var ra = found.AidEffect!;
                    Console.WriteLine($"  MGEF {re.EditorID} {re.FormKey} (RadAway's, copy of {ra.EditorID} {ra.FormKey}) actor value {re.SecondActorValue.FormKey} flags {re.Flags}");
                    Need(re.SecondActorValue.FormKey == Own(AvifId), "RadAway's MGEF actor value (DATA word 14) is not FO4SF_Rads");
                    Need(re.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && (re.Archetype as IMagicEffectArchetypeGetter)?.Association.IsNull != false, "RadAway's MGEF is not a plain value modifier with an empty association");
                    Need(re.Flags == ra.Flags && re.CastType == ra.CastType && re.TargetType == ra.TargetType, $"RadAway's MGEF cast type, target or flags differ from its template {ra.EditorID}");
                    Need(re.Conditions.Count == 0 && re.VirtualMachineAdapter == null && (re.Keywords?.Count ?? 0) == 0 && re.ResistValue.IsNull && re.MagicSkill.IsNull && re.ThirdActorValue.IsNull, "RadAway's MGEF still carries conditions, a script, keywords or a resist, skill or third value of its template");
                }
            }
            else Entry(radAway.Effects.ToList(), RadAwayMagnitude, "RadAway");
            var ta = found.Aid;
            if (ta != null)
            {
                Need(radAway.Model?.File.GivenPath == ta.Model?.File.GivenPath && radAway.Flags == ta.Flags && radAway.MajorFlags == ta.MajorFlags, $"RadAway's model or flags differ from its template {ta.EditorID}");
                Need(radAway.Addiction.IsNull && radAway.VirtualMachineAdapter == null && (radAway.Keywords?.Count ?? 0) == 0 && radAway.Effects.All(e => e.Conditions.Count == 0), "RadAway still carries an addiction, a script, keywords or conditions of its template");
            }
        }

        var dose = mod.Ingestibles.FirstOrDefault(i => i.FormKey == Own(DoseId));
        Need(dose?.EditorID == DoseEdid && dose.Name?.String == "Rad Dose", "no ALCH named Rad Dose (FO4SF_RadDose)");
        if (dose != null)
        {
            Console.WriteLine($"  ALCH {dose.EditorID} {dose.FormKey} \"{dose.Name?.String}\" flags {dose.Flags}, {dose.Effects.Count} effect(s) at {string.Join(",", dose.Effects.Select(e => e.Data?.Magnitude))}");
            Entry(dose.Effects.ToList(), DoseMagnitude, "the Rad Dose");
            var td = found.Aid;
            if (td != null)
            {
                Need(dose.Model?.File.GivenPath == td.Model?.File.GivenPath && dose.Flags == td.Flags && dose.MajorFlags == td.MajorFlags, $"the Rad Dose's model or flags differ from its template {td.EditorID}");
                Need(dose.Addiction.IsNull && dose.VirtualMachineAdapter == null && (dose.Keywords?.Count ?? 0) == 0 && dose.Effects.All(e => e.Conditions.Count == 0), "the Rad Dose still carries an addiction, a script, keywords or conditions of its template");
            }
        }

        Need(mod.Quests.Count() == 2, "not exactly two QUST (the probe's and the by-hand one)");
        var hand = mod.Quests.FirstOrDefault(q => q.FormKey == Own(HandQuestId));
        Need(hand?.EditorID == HandQuestEdid, "no QUST FO4SF_RadsHandQuest");
        if (hand != null)
        {
            var hs = hand.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            var hp = hs.Count == 1 ? hs[0].Properties.OfType<ScriptObjectProperty>().ToDictionary(p => p.Name, p => p.Object.FormKey) : new();
            Console.WriteLine($"  QUST {hand.EditorID} flags {hand.Data?.Flags} scripts [{string.Join(", ", hs.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(hand.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "the by-hand QUST is not start game enabled");
            Need(hs.Count == 1 && hs[0].Name == HandScript && hs[0].Properties.Count == HandPropNames.Length, $"the by-hand QUST script is not {HandScript} with exactly {HandPropNames.Length} properties");
            void HP(string name, FormKey want) => Need(hp.TryGetValue(name, out var fk) && fk == want, $"by-hand property {name} is not {want}");
            HP(HandPropNames[0], Own(AvifId));
            HP(HandPropNames[1], health.FormKey);
            HP(HandPropNames[2], Own(RadAwayId));
            HP(HandPropNames[3], Own(DoseId));
        }
        var quest = mod.Quests.FirstOrDefault(q => q.FormKey == Own(QuestId));
        Need(quest?.FormKey == Own(QuestId) && quest.EditorID == QuestEdid, "not exactly our QUST");
        if (quest != null)
        {
            var wantProps = PropNames.Length - (tpl.ControlSpell != "" ? 0 : 1);
            var scripts = quest.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            var props = scripts.Count == 1 ? scripts[0].Properties.OfType<ScriptObjectProperty>().ToDictionary(p => p.Name, p => p.Object.FormKey) : new();
            Console.WriteLine($"  QUST {quest.EditorID} flags {quest.Data?.Flags} stages [{string.Join(",", quest.Stages.Select(s => s.Index))}] scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(quest.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "QUST is not start game enabled");
            Need(quest.Stages.Select(s => s.Index).SequenceEqual(Stages), "QUST stages are not 10, 20, 30, 40, 50");
            Need(scripts.Count == 1 && scripts[0].Name == Script && scripts[0].Properties.Count == wantProps, $"QUST script is not {Script} with exactly {wantProps} properties");
            void P(string name, FormKey want) => Need(props.TryGetValue(name, out var fk) && fk == want, $"property {name} is not {want}");
            P(PropNames[0], Own(AvifId));
            P(PropNames[1], health.FormKey);
            P(PropNames[2], Own(SpellId));
            P(PropNames[3], Own(RadAwayId));
            if (tpl.ControlSpell != "") P(PropNames[4], One(sf.Spells, tpl.ControlSpell, "SPEL").FormKey);
            foreach (var kv in props) Console.WriteLine($"    property {kv.Key} = {kv.Value}");
        }
        var kinds = mod.EnumerateMajorRecords().GroupBy(r => r.GetType().Name.Replace("BinaryOverlay", "")).Select(g => $"{g.Key} {g.Count()}");
        Console.WriteLine($"  records: {string.Join(", ", kinds)}");
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture

    public static int Fixture(string outDir, string restore = "aid")
    {
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0x00A02D), Release) { EditorID = "Health", Name = "Health" });
        mod.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0x00A02E), Release) { EditorID = "SynthOther", Name = "Other" });
        var synthArch = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
        var synthMgef = new MagicEffect(new FormKey(SfEsm, 0x00A100), Release)
        {
            EditorID = "SynthValueEffect", Name = "Synth", CastType = CastType.FireAndForget, TargetType = TargetType.Self,
            Flags = MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration, Archetype = synthArch,       // a template with the flag that would negate
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(new FormKey(SfEsm, 0x00A200)) },
        };
        synthMgef.SecondActorValue.SetTo(new FormKey(SfEsm, 0x00A02E));            // the template's own actor value (replaced by ours)
        if (restore != "aid" && restore != "spell" && restore != "none") throw new Refusal("fixture --restore is aid, spell or none");
        if (restore != "none")                 // a Health restore effect: carried by an ingestible (aid), or only by a spell (spell: the real file's case)
        {
            var restoreArch = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
            var restoreMgef = new MagicEffect(new FormKey(SfEsm, 0x00A104), Release)
            {
                EditorID = "SynthRestoreHealthEffect", Name = "Synth restore", CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.HideInUI, Archetype = restoreArch,
            };
            restoreMgef.SecondActorValue.SetTo(new FormKey(SfEsm, 0x00A02D));          // Health
            mod.MagicEffects.Add(restoreMgef);
            var restoreEntry = new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(restoreMgef.FormKey), Data = new EffectData { Magnitude = 25f, Duration = 0 }, MAGF = 4, EFIF = 5, MUID = 6 };
            if (restore == "aid")
            {
                var restoreAid = new Ingestible(new FormKey(SfEsm, 0x00A105), Release)
                {
                    EditorID = "SynthRestoreHealthAid", Name = "Synth stim", Flags = Ingestible.Flag.Medicine, MajorFlags = Ingestible.MajorFlag.Medicine,
                };
                restoreAid.Effects.Add(restoreEntry);
                mod.Ingestibles.Add(restoreAid);
            }
            else
            {
                var restoreSpell = new Spell(new FormKey(SfEsm, 0x00A106), Release)
                {
                    EditorID = "SynthRestoreSpell", Name = "Synth restore spell", Type = Spell.SpellType.Spell, CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                };
                restoreSpell.Effects.Add(restoreEntry);
                mod.Spells.Add(restoreSpell);
            }
        }
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
        var dmgSpell = new Spell(new FormKey(SfEsm, 0x00A103), Release)
        {
            EditorID = PreferredSpell, Name = "Synth damage", Type = Spell.SpellType.Spell, CastType = CastType.FireAndForget, TargetType = TargetType.Self,
            Flags = Spell.Flag.ManualCostCalc,
        };
        dmgSpell.EquipmentType.SetTo(new FormKey(SfEsm, 0x00A301));
        dmgSpell.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(synthMgef.FormKey), Data = new EffectData { Magnitude = 40f }, MAGF = 70, EFIF = 80, MUID = 90 });
        mod.Spells.Add(dmgSpell);
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
