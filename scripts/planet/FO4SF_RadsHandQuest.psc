Scriptname FO4SF_RadsHandQuest extends Quest
{The rads probe by hand (fo4-to-starfield, docs/research/rads-probe.md, "By hand"). Attached to QUST FO4SF_RadsHandQuest of
 FO4SFRadsProbe.esm: start game enabled, four properties (our actor value, Starfield's Health, our RadAway, our Rad Dose).
 No console, no stage numbers: the first time the quest runs it puts three RadAway and three Rad Dose in the player's
 inventory, and from then on EVERY change of our rads value shows on screen as a notification:
     "Rads 100, max health 190"       (max health is the game's maximum reading when it has one, else "health N")
 The owner uses a Rad Dose from the inventory (rads +100) or a RadAway (rads -200, never below 0). The route of the rads
 probe is applied here too: Health carries minus one tenth of the rads (a permanent modifier, Actor.ModValue).
 When an item was used and our value did not move as it should within 3 s, the script says so on screen
 ("Rad Dose used, but rads stayed 0 (expected 100). Setting 100") and sets the value itself, so the owner still sees the
 health route work and the log says which part failed. Nothing here needs the quest to be set to a stage; the probe's
 own quest (FO4SF_RadsProbeQuest) sits idle until a stage is set.
 Every notification and every finding is also one line in the user log "FO4SFRadsHand"
 (My Games\Starfield\Logs\Script\User\FO4SFRadsHand.0.log): FO4SFRADSHAND rt=<s> <event> key=value ... end=true.
 Optional readings are lines that begin with ";OPT <Base.Name> ": scripts/planet/make_rads_probe.py stage compiles each on
 its own and keeps the ones that compile (as in FO4SF_RadsProbeQuest.psc). As committed none is on: this file compiles
 alone.}

ActorValue Property RadsAV Auto Const Mandatory
ActorValue Property HealthAV Auto Const Mandatory
Form Property RadAway Auto Const Mandatory
Form Property RadDose Auto Const Mandatory

; ---------------------------------------------------------------- the numbers

string LogName = "FO4SFRadsHand"
int GiveCount = 3
float DoseMagnitude = 100.0
float RadAwayMagnitude = -200.0
float RadsMaxValue = 1000.0
float PenaltyPerRad = 0.1   ; as the probe: Health loses one tenth of the rads

int TIMER_POLL = 1
int TIMER_SETTLE = 2
float POLL_S = 1.0
float SETTLE_S = 3.0

float LastRads = 0.0        ; the value the player's screen last showed
float Applied = 0.0         ; the route's modifier on Health now (zero or negative)
int LastDose = 0
int LastAway = 0
bool Settling = false
float WantRads = 0.0
string UsedWhat = ""
float LastUseRT = 0.0       ; real time of the latest use: the settle waits SETTLE_S after it

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    Trace("init quest=" + GetFormID() + " rads=" + p.GetValue(RadsAV) + " dose=" + Id(RadDose) + " radaway=" + Id(RadAway))
    p.AddItem(RadAway, GiveCount, true)
    p.AddItem(RadDose, GiveCount, true)
    LastRads = p.GetValue(RadsAV)
    LastDose = p.GetItemCount(RadDose)
    LastAway = p.GetItemCount(RadAway)
    Say("Rads kit: " + GiveCount + " RadAway and " + GiveCount + " Rad Dose added. Use a Rad Dose to raise rads, a RadAway to lower them.")
    Say(Describe(p))
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {One line in the user log; a log is open only in the session that opened it (assumed), so on a failed write it is opened again.}
    string line = "FO4SFRADSHAND rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    {The on-screen message, and the same text in the log.}
    Debug.Notification(msg)
    Trace("say text=" + msg)
EndFunction

string Function Id(Form f)
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

; ---------------------------------------------------------------- readings

string Function MaxText(Actor p)
    {"max health N" when the game has a maximum reading, else "health N" (the current value, said so).}
    string s = "health " + p.GetValue(HealthAV)
;OPT Actor.GetValueMax     s = "max health " + p.GetValueMax(HealthAV)
    return s
EndFunction

string Function Describe(Actor p)
    return "Rads " + (p.GetValue(RadsAV) as int) + ", " + MaxText(p)
EndFunction

bool Function ModHealth(Actor p, float delta)
    {Health's permanent modifier moved by delta; false when the game declares no such call.}
    bool ok = false
;OPT Actor.ModValue     p.ModValue(HealthAV, delta)
;OPT Actor.ModValue     ok = true
    return ok
EndFunction

Function ApplyRoute(Actor p)
    float rads = p.GetValue(RadsAV)
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
    Trace("route rads=" + rads + " want=" + want + " delta=" + delta + " applied=" + Applied + " ok=" + ok)
EndFunction

float Function Clamp(float v)
    if v < 0.0
        return 0.0
    endif
    if v > RadsMaxValue
        return RadsMaxValue
    endif
    return v
EndFunction

; ---------------------------------------------------------------- poll

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_SETTLE
        Settle()
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    int dose = p.GetItemCount(RadDose)
    int away = p.GetItemCount(RadAway)
    if dose < LastDose || away < LastAway
        ; an item used while an earlier use is still settling adds to the target (it is never dropped)
        float want = LastRads
        string what = ""
        if Settling
            want = WantRads
            what = UsedWhat + " + "
        endif
        if dose < LastDose
            want += DoseMagnitude * (LastDose - dose)
            what = what + "Rad Dose"
        endif
        if away < LastAway
            want += RadAwayMagnitude * (LastAway - away)
            what = what + "RadAway"
        endif
        WantRads = Clamp(want)
        UsedWhat = what
        LastUseRT = Utility.GetCurrentRealTime()
        Trace("used what=" + what + " from=" + LastRads + " want=" + WantRads + " pending=" + Settling)
        if !Settling
            Settling = true
            StartTimer(SETTLE_S, TIMER_SETTLE)
        endif
    endif
    LastDose = dose
    LastAway = away
    float rads = p.GetValue(RadsAV)
    if rads < 0.0 || rads > RadsMaxValue
        ; the PC run of the probe (FAL-213) saw an ingestible's effect applied once per frame: rads at -59,700. The AVIF's min and
        ; max are not enforced for a value changed that way, so the script keeps it in range itself (never routed, never shown).
        Trace("range rads=" + rads + " clamped=" + Clamp(rads))
        p.SetValue(RadsAV, Clamp(rads))
        rads = Clamp(rads)
    endif
    if Settling
        ; an item was just used: its effect is still working (it may run every frame for a moment). Nothing is shown or routed
        ; until the settle has read the value, so the owner sees one message with the final number, not a run of huge ones.
        return
    endif
    if rads != LastRads
        ApplyRoute(p)
        Say(Describe(p))
        LastRads = rads
    endif
EndFunction

Function Settle()
    {An item was used 3 s ago: did our value move as the effect says? When not, say so and set it, so the health route is still shown.}
    Actor p = Game.GetPlayer()
    float wait = LastUseRT + SETTLE_S - Utility.GetCurrentRealTime()
    if wait > 0.2
        StartTimer(wait, TIMER_SETTLE)       ; another item was used meanwhile: give it its full time
        return
    endif
    float have = p.GetValue(RadsAV)
    Settling = false
    if have == WantRads
        Trace("settle used=" + UsedWhat + " ok=true want=" + WantRads + " had=" + have)
    else
        Say(UsedWhat + " used: the effect left rads at " + (have as int) + ", expected " + (WantRads as int) + ". Setting " + (WantRads as int))
        Trace("settle used=" + UsedWhat + " ok=false want=" + WantRads + " had=" + have)
        p.SetValue(RadsAV, WantRads)
    endif
EndFunction
