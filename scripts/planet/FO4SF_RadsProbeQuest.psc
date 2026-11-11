Scriptname FO4SF_RadsProbeQuest extends Quest
{The rads base probe (fo4-to-starfield, docs/research/rads-probe.md). Attached to QUST FO4SF_RadsProbeQuest of
 FO4SFRadsProbe.esm: start game enabled, stages 10 / 20 / 30 / 40, four properties (the forms the writer,
 dotnet/RadsProbe, fills in: our actor value, Starfield's Health, our spell, our RadAway). The owner sets a stage from
 the console; the script polls the stage once a second (it does not rely on OnStageSet, whose behaviour is unresolved:
 docs/questprobe/engine-questions.md E2) and runs each step once:
   stage 10  the CONTROL (vanilla Health +10 with ModValue, read, -10, read), then our value written with a number that
             is not zero (SetValue 50, read) and back to 0 (SetValue 0, read): does our own actor value take a number
   stage 20  rads to 100     (the spell, once: effect +100)
   stage 30  rads to 300     (the spell, twice: +200)
   stage 40  RadAway         (AddItem + EquipItem: its effect should lower the value by 200, so 100 left)
   stage 50  the SECOND CONTROL: a vanilla spell (property ControlSpell, named when the plugin is built) is cast on the player
             and Health read before and 3 s after. Tells "our effect is wrong" from "Cast from a quest script applies no value
             modifier at all". Not run when the property is None.
 After the effect has had 3 s the script reads the value, FORCES the step's number when the effect did not give it, by the
 difference (Actor.ModValue of want minus have; SetValue only when ModValue is not declared; logged fix forced=true how=<call>,
 so the route is still tested), then applies the ROUTE: a permanent modifier on Health
 of minus one tenth of the rads (ModValue on the difference to what it applied before), and reads again 3 s later.
 Each reading logs our value, the player's health (GetValue), its base value and maximum when the game declares those,
 and the ids of the active magic effects on the player (to see whether Starfield's own radiation acts in our world).
 One line per finding in the user log "FO4SFRadsProbe" (My Games\Starfield\Logs\Script\User\FO4SFRadsProbe.0.log):
   FO4SFRADS rt=<real time s> <event> key=value ... end=true
 (form ids as Papyrus prints them: signed decimal, "none" for None; the reader, src/fo4sf/rads/probe_log.py, ignores
 case; a line without end=true was cut). Nothing is judged in game.
 The optional readings are lines that begin with ";OPT <Base.Name> ": scripts/planet/make_rads_probe.py stage checks
 each name against Starfield's base scripts and compiles it on its own, keeps the ones that compile and reports every
 one that does not (the reading then logs "na"). As committed, none is on: this file compiles alone.}

ActorValue Property RadsAV Auto Const Mandatory
ActorValue Property HealthAV Auto Const Mandatory
Spell Property RadsSpell Auto Const Mandatory
Form Property RadAway Auto Const Mandatory
Spell Property ControlSpell Auto Const    ; stage 50 only: a vanilla instant value effect on Health (second control); None when not given

; ---------------------------------------------------------------- the numbers

int Version = 1
string LogName = "FO4SFRadsProbe"
string ProbePlugin = "FO4SFRadsProbe.esm"
float ControlDelta = 10.0   ; the control: Health +10, read, -10, read
float WriteTest = 50.0     ; stage 10: a number that is not zero, written to our value and read
float PenaltyPerRad = 0.1   ; the route: Health loses one tenth of the rads (100 rads: 10, 300 rads: 30)

int TIMER_POLL = 1
int TIMER_SETTLE = 100      ; + the stage: the effect has had its time
int TIMER_FINAL = 200       ; + the stage: three seconds after the route
float POLL_S = 1.0
float SETTLE_S = 3.0
float Applied = 0.0         ; the route's modifier on Health now (zero or negative)
bool Done10 = false
bool Done20 = false
bool Done30 = false
bool Done40 = false
bool Done50 = false

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin))
    Trace("start rads_av=" + Id(RadsAV) + " health_av=" + Id(HealthAV) + " spell=" + Id(RadsSpell) + " radaway=" + Id(RadAway) + " penalty=" + PenaltyPerRad)
    Reading("start", 0)
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {A user log is open only in the game session that opened it (assumed): when a write fails, as after a save is loaded
     again, the log is opened once more and the line written again. Every line ends with end=true.}
    string line = "FO4SFRADS rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

string Function Id(Form f)
    {"<signed decimal form id>" or "none".}
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

; ---------------------------------------------------------------- readings

string Function BaseHealth(Actor p)
    string s = "na"
;OPT Actor.GetBaseValue     s = "" + p.GetBaseValue(HealthAV)
    return s
EndFunction

string Function MaxHealth(Actor p)
    string s = "na"
;OPT Actor.GetValueMax     s = "" + p.GetValueMax(HealthAV)
    return s
EndFunction

string Function EffectIds(Actor p)
    {The ids of the magic effects active on the player, comma separated; "none" when there are none, "na" when the game
     declares no way to list them.}
    string s = "na"
;OPT Actor.GetActiveEffects     s = ""
;OPT Actor.GetActiveEffects     ActiveMagicEffect[] fxa = p.GetActiveEffects()
;OPT Actor.GetActiveEffects     int ia = 0
;OPT Actor.GetActiveEffects     while fxa && ia < fxa.Length && ia < 40
;OPT Actor.GetActiveEffects         if ia > 0
;OPT Actor.GetActiveEffects             s += ","
;OPT Actor.GetActiveEffects         endif
;OPT Actor.GetActiveEffects         s += Id(fxa[ia].GetBaseObject())
;OPT Actor.GetActiveEffects         ia += 1
;OPT Actor.GetActiveEffects     endwhile
;OPT Actor.GetActiveMagicEffects     s = ""
;OPT Actor.GetActiveMagicEffects     ActiveMagicEffect[] fxb = p.GetActiveMagicEffects()
;OPT Actor.GetActiveMagicEffects     int ib = 0
;OPT Actor.GetActiveMagicEffects     while fxb && ib < fxb.Length && ib < 40
;OPT Actor.GetActiveMagicEffects         if ib > 0
;OPT Actor.GetActiveMagicEffects             s += ","
;OPT Actor.GetActiveMagicEffects         endif
;OPT Actor.GetActiveMagicEffects         s += Id(fxb[ib].GetBaseObject())
;OPT Actor.GetActiveMagicEffects         ib += 1
;OPT Actor.GetActiveMagicEffects     endwhile
    if s == ""
        s = "none"
    endif
    return s
EndFunction

Function Reading(string when, int stage)
    {One state line: our value, Health (GetValue), its base and maximum, the route's modifier, the active effect ids.}
    Actor p = Game.GetPlayer()
    Trace("state stage=" + stage + " when=" + when + " rads=" + p.GetValue(RadsAV) + " health=" + p.GetValue(HealthAV) + " base=" + BaseHealth(p) + " max=" + MaxHealth(p) + " applied=" + Applied + " fx=" + EffectIds(p))
EndFunction

; ---------------------------------------------------------------- the route and the control

bool Function ModHealth(Actor p, float delta)
    {Health's permanent modifier moved by delta (Actor.ModValue); false when the game declares no such call.}
    bool ok = false
;OPT Actor.ModValue     p.ModValue(HealthAV, delta)
;OPT Actor.ModValue     ok = true
    return ok
EndFunction

Function Control(Actor p)
    {The control: a vanilla actor value set and read in the same step. Health +ControlDelta with the very call the route
     uses, read, then -ControlDelta, read. If this does not move Health, nothing about the route can be judged.}
    float before = p.GetValue(HealthAV)
    bool called = ModHealth(p, ControlDelta)
    float after = p.GetValue(HealthAV)
    bool back = ModHealth(p, -1.0 * ControlDelta)
    float restored = p.GetValue(HealthAV)
    Trace("control av=" + Id(HealthAV) + " delta=" + ControlDelta + " called=" + called + " before=" + before + " after=" + after + " restored=" + restored + " undone=" + back)
EndFunction

bool Function ModRads(Actor p, float delta)
    {Our value moved by delta with Actor.ModValue; false when the game declares no such call (then the caller falls back to SetValue).}
    bool ok = false
;OPT Actor.ModValue     p.ModValue(RadsAV, delta)
;OPT Actor.ModValue     ok = true
    return ok
EndFunction

Function ApplyRoute(Actor p)
    float rads = p.GetValue(RadsAV)
    bool clamped = false
    if rads < 0.0
        ; the engine does not enforce the value's minimum for a change made by an effect (fourth session: -59,900): clamp at 0
        ; before the route, or a negative number would raise Health
        p.SetValue(RadsAV, 0.0)
        rads = 0.0
        clamped = true
    endif
    int pen = (rads * PenaltyPerRad) as int
    float want = -1.0 * pen
    float delta = want - Applied
    bool ok = true
    if delta != 0.0
        ok = ModHealth(p, delta)
        if ok
            Applied = want
        endif
    endif
    Trace("route rads=" + rads + " want=" + want + " delta=" + delta + " applied=" + Applied + " ok=" + ok + " clamped=" + clamped)
EndFunction

; ---------------------------------------------------------------- poll and steps

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID >= TIMER_FINAL
        Reading("final", aiTimerID - TIMER_FINAL)
    elseif aiTimerID == TIMER_SETTLE + 50
        VSettle(Game.GetPlayer())
    elseif aiTimerID >= TIMER_SETTLE
        Settle(aiTimerID - TIMER_SETTLE)
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    if !Done10 && GetStageDone(10)
        Done10 = true
        Step10(p)
    endif
    if !Done20 && GetStageDone(20)
        Done20 = true
        Step20(p)
    endif
    if !Done30 && GetStageDone(30)
        Done30 = true
        Step30(p)
    endif
    if !Done40 && GetStageDone(40)
        Done40 = true
        Step40(p)
    endif
    if !Done50 && GetStageDone(50)
        Done50 = true
        Step50(p)
    endif
EndFunction

float Function Expected(int stage)
    if stage == 20
        return 100.0
    elseif stage == 30
        return 300.0
    elseif stage == 40
        return 100.0
    endif
    return 0.0
EndFunction

Function Step10(Actor p)
    Trace("step stage=10 call=SetValue expect=0")
    Reading("before", 10)
    Control(p)
    p.SetValue(RadsAV, WriteTest)
    Trace("set stage=10 wrote=" + WriteTest + " read=" + p.GetValue(RadsAV))
    p.SetValue(RadsAV, 0.0)
    Trace("set stage=10 wrote=0.0 read=" + p.GetValue(RadsAV))
    Reading("now", 10)
    StartTimer(SETTLE_S, TIMER_SETTLE + 10)
EndFunction

Function Step20(Actor p)
    Trace("step stage=20 call=Cast expect=100")
    Reading("before", 20)
    RadsSpell.Cast(p, p)
    Reading("now", 20)
    StartTimer(SETTLE_S, TIMER_SETTLE + 20)
EndFunction

Function Step30(Actor p)
    Trace("step stage=30 call=Cast+Cast expect=300")
    Reading("before", 30)
    RadsSpell.Cast(p, p)
    RadsSpell.Cast(p, p)
    Reading("now", 30)
    StartTimer(SETTLE_S, TIMER_SETTLE + 30)
EndFunction

float RadsBefore40 = 0.0

Function Step40(Actor p)
    Trace("step stage=40 call=EquipItem expect=100")
    RadsBefore40 = p.GetValue(RadsAV)
    Reading("before", 40)
    p.AddItem(RadAway, 1, true)
    ; Seventh session: RadAway moved nothing and the log could not say whether the item was used up. The count after AddItem and
    ; after the settle time separates "not consumed" from "consumed, effect inert".
    Trace("item stage=40 when=added count=" + p.GetItemCount(RadAway))
    p.EquipItem(RadAway, false, true)
    Trace("item stage=40 when=now count=" + p.GetItemCount(RadAway))
    Reading("now", 40)
    StartTimer(SETTLE_S, TIMER_SETTLE + 40)
EndFunction

Function Settle(int stage)
    {The effect has had its time: read, force the step's value when the effect did not give it, apply the route, read.}
    Actor p = Game.GetPlayer()
    Reading("settled", stage)
    if stage == 40
        Trace("item stage=40 when=settled count=" + p.GetItemCount(RadAway))
    endif
    float want = Expected(stage)
    float have = p.GetValue(RadsAV)
    if stage == 40
        ; Eighth session: the item is consumed and its effect is inert on our value. RadAway's route is therefore the script:
        ; when the item's own effect left the value where it was, take 200 off with ModValue, clamped at 0 (the sign rule and the
        ; call are proven by the force). item_had is the item's own result, before this; the reader judges the item on it.
        float itemHad = have
        float dRad = -200.0
        if have + dRad < 0.0
            dRad = 0.0 - have
        endif
        bool moved = false
        if have == RadsBefore40
            moved = ModRads(p, dRad)
        endif
        Trace("radaway stage=40 item_had=" + itemHad + " before=" + RadsBefore40 + " route=script applied=" + moved + " delta=" + dRad + " now=" + p.GetValue(RadsAV))
        have = p.GetValue(RadsAV)
    endif
    if have != want
        ; Sixth session: SetValue wrote the base while the cast's change sat apart from it (300 stored, SetValue 100 read 400). A
        ; correction by the difference reaches want whichever of the two the call moves; SetValue only when there is no ModValue.
        string how = "ModValue"
        if !ModRads(p, want - have)
            how = "SetValue"
            p.SetValue(RadsAV, want)
        endif
        Trace("fix stage=" + stage + " forced=true want=" + want + " had=" + have + " now=" + p.GetValue(RadsAV) + " how=" + how)
    else
        Trace("fix stage=" + stage + " forced=false want=" + want + " had=" + have + " now=" + have)
    endif
    ApplyRoute(p)
    Reading("routed", stage)
    StartTimer(SETTLE_S, TIMER_FINAL + stage)
EndFunction

float VBefore = 0.0

Function Step50(Actor p)
    Trace("step stage=50 call=CastVanilla spell=" + Id(ControlSpell))
    VBefore = p.GetValue(HealthAV)
    Reading("before", 50)
    if ControlSpell == None
        Trace("vcontrol spell=none before=" + VBefore + " after=" + VBefore + " cast=false")
        return
    endif
    ControlSpell.Cast(p, p)
    Reading("now", 50)
    StartTimer(SETTLE_S, TIMER_SETTLE + 50)
EndFunction

Function VSettle(Actor p)
    {Three seconds after the vanilla cast: Health read again; one vcontrol line.}
    float after = p.GetValue(HealthAV)
    Reading("settled", 50)
    Trace("vcontrol spell=" + Id(ControlSpell) + " before=" + VBefore + " after=" + after + " cast=true")
EndFunction
