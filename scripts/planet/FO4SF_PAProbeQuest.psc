Scriptname FO4SF_PAProbeQuest extends Quest
{The power armor probe (fo4-to-starfield, docs/research/power-armor-probe.md). Attached to QUST FO4SF_PAProbeQuest (0x803
 of FO4SFPowerArmorProbe.esm: start game enabled, stages 10 / 20 / 30, NO properties). Every form is found with
 Game.GetFormFromFile when it is read, because a script property would make a temporary reference persistent.
 The owner sets a stage from the console; the script polls the stage once a second (it does not rely on OnStageSet,
 whose behaviour is unresolved: docs/questprobe/engine-questions.md E2) and runs each step once:
   stage 10  Actor.SwitchToPowerArmor(the suit furniture reference)     (Fallout 4's power armor entry)
   stage 20  Actor.SetRace(FO4SF_PARace, a copy of HumanRace)           (the race swap)
   stage 30  Actor.SetRace(the race the player had at the start)        (and back)
 Each step logs a reading before the call, right after it and 4 s later (the settled one). A `sit` line is logged when
 the player's furniture or sit state changes, so sitting on the vanilla control furniture shows in the log. One line per
 finding in the user log "FO4SFPAProbe" (My Games\Starfield\Logs\Script\User\FO4SFPAProbe.0.log):
   FO4SFPA rt=<real time s> <event> key=value ... end=true
 (form ids as Papyrus prints them: signed decimal, "none" for None; bools as Starfield prints them; the reader,
 src/fo4sf/powerarmor/probe_log.py, ignores case; a line without end=true was cut). Nothing is judged in game.
 The optional readings are lines that begin with ";OPT <Base.Name> ": scripts/planet/make_power_armor_probe.py stage
 checks each name against Starfield's base scripts and compiles it on its own, keeps the ones that compile, and
 reports every one that does not (the reading then logs "na"). As committed, none is on: this file compiles alone.}

; ---------------------------------------------------------------- the layout (dotnet/PowerArmorProbe/Program.cs)

int Version = 1
string LogName = "FO4SFPAProbe"
string ProbePlugin = "FO4SFPowerArmorProbe.esm"
int CellId = 0x800          ; CELL FO4SF_PAProbeCell
int SuitId = 0x801          ; FURN FO4SF_PAProbeSuit (a copy of the control furniture + FurnitureTypePowerArmor)
int RaceId = 0x802          ; RACE FO4SF_PARace (a copy of HumanRace)
int SuitRefId = 0x804       ; REFR the suit furniture
int ControlRefId = 0x805    ; REFR the vanilla control furniture

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_SETTLE = 100      ; + the stage
float POLL_S = 1.0
float SETTLE_S = 4.0
Race OrigRace = None
bool Done10 = false
bool Done20 = false
bool Done30 = false
string LastSit = ""

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    OrigRace = p.GetRace()
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin))
    Trace("start suitref=" + Id(Ref(SuitRefId)) + " controlref=" + Id(Ref(ControlRefId)) + " pa_race=" + Id(Game.GetFormFromFile(RaceId, ProbePlugin)) + " orig_race=" + Id(OrigRace))
    Reading("start", 0)
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {A user log is open only in the game session that opened it (assumed): when a write fails, as after a save is loaded
     again, the log is opened once more and the line written again. Every line ends with end=true.}
    string line = "FO4SFPA rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
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

ObjectReference Function Ref(int id)
    return Game.GetFormFromFile(id, ProbePlugin) as ObjectReference
EndFunction

; ---------------------------------------------------------------- readings

int Function WornCount(Actor p)
    {The number of armor slots with an item worn, -1 when Actor.GetWornItem is not declared or does not compile.}
    int n = -1
;OPT Actor.GetWornItem     n = 0
;OPT Actor.GetWornItem     int slot = 0
;OPT Actor.GetWornItem     while slot < 64
;OPT Actor.GetWornItem         Actor:WornItem w = p.GetWornItem(slot)
;OPT Actor.GetWornItem         if w && w.item
;OPT Actor.GetWornItem             n += 1
;OPT Actor.GetWornItem         endif
;OPT Actor.GetWornItem         slot += 1
;OPT Actor.GetWornItem     endwhile
    return n
EndFunction

string Function FurnId(Actor p)
    string s = "na"
;OPT Actor.GetFurnitureReference     s = Id(p.GetFurnitureReference())
    return s
EndFunction

string Function SitState(Actor p)
    string s = "na"
;OPT Actor.GetSitState     s = "" + p.GetSitState()
    return s
EndFunction

string Function InPowerArmor(Actor p)
    string s = "na"
;OPT Actor.IsInPowerArmor     s = "" + p.IsInPowerArmor()
    return s
EndFunction

string Function Camera()
    string s = "na"
;OPT Game.GetCameraState     s = "" + Game.GetCameraState()
    return s
EndFunction

string Function DistControl(Actor p)
    ObjectReference c = Ref(ControlRefId)
    if c == None
        return "none"
    endif
    return "" + p.GetDistance(c)
EndFunction

Function Reading(string when, int stage)
    {One state line: race, position, camera state, worn item count, IsInPowerArmor, furniture and sit state.}
    Actor p = Game.GetPlayer()
    Trace("state stage=" + stage + " when=" + when + " race=" + Id(p.GetRace()) + " cell=" + Id(p.GetParentCell()) + " pos=" + p.GetPositionX() + "," + p.GetPositionY() + "," + p.GetPositionZ() + " cam=" + Camera() + " worn=" + WornCount(p) + " inpa=" + InPowerArmor(p) + " furn=" + FurnId(p) + " sitstate=" + SitState(p) + " distc=" + DistControl(p))
EndFunction

; ---------------------------------------------------------------- poll and steps

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID >= TIMER_SETTLE
        Reading("settled", aiTimerID - TIMER_SETTLE)
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    string sit = FurnId(p) + "/" + SitState(p)
    if sit != LastSit
        LastSit = sit
        Trace("sit furn=" + FurnId(p) + " sitstate=" + SitState(p) + " distc=" + DistControl(p))
    endif
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
EndFunction

Function Step10(Actor p)
    ObjectReference suit = Ref(SuitRefId)
    Trace("step stage=10 call=SwitchToPowerArmor suitref=" + Id(suit))
    Reading("before", 10)
    if suit
        p.SwitchToPowerArmor(suit)
    endif
    Reading("now", 10)
    StartTimer(SETTLE_S, TIMER_SETTLE + 10)
EndFunction

Function Step20(Actor p)
    Race pa = Game.GetFormFromFile(RaceId, ProbePlugin) as Race
    if OrigRace == None
        OrigRace = p.GetRace()
    endif
    Trace("step stage=20 call=SetRace race=" + Id(pa) + " orig_race=" + Id(OrigRace))
    Reading("before", 20)
    if pa
        p.SetRace(pa)
    endif
    Reading("now", 20)
    StartTimer(SETTLE_S, TIMER_SETTLE + 20)
EndFunction

Function Step30(Actor p)
    Trace("step stage=30 call=SetRace race=" + Id(OrigRace) + " orig_race=" + Id(OrigRace))
    Reading("before", 30)
    if OrigRace
        p.SetRace(OrigRace)
    endif
    Reading("now", 30)
    StartTimer(SETTLE_S, TIMER_SETTLE + 30)
EndFunction
