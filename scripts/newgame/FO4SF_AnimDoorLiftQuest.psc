Scriptname FO4SF_AnimDoorLiftQuest extends Quest
{The door and lift controls (fo4-to-starfield, docs/research/anim-doorlift-control.md, FAL-489). Attached to QUST FO4SF_AnimDoorLiftQuest
 (0x800 of FO4SFAnimDoorLift.esm): start game enabled, stages set from the console, NO properties. The full description follows as ; comments.}
; Two controls, one session. DOOR: ACTI 0x801 of FO4SFAnimDoorLift.esm, a new activator with the model, rig and clip folder of the vanilla door
; AK_Ext_Bld_WallA_DoorA_01_Alt02 (000AA24A; its Open/Close clips live on SimpleOpenClose01) whose animation graph is genericopenclose01 (no
; vanilla record names it). The vanilla door itself is never placed. LIFT: the vanilla ShipQuickLift1 (00010C35, graph twostages), placed UNCHANGED.
; The script polls the stages once a second:
;   10        place the door 4 m in front of the player and the lift LIFT_M in front, DISABLED until it has been moved there (a lift that
;             cannot be moved away is left disabled and says so: it is never left standing on the player), then register every event name
;   20        register every event name again on both (the log shows each call's return)
;   21..24    the DOOR: Open, Close, StateA_Play, StateB_Play (the last two matter when Open and Close both returned false), then 15 s of listening
;   31..34    the LIFT: Stage1, Stage1Transition, Stage2, Stage2Transition, then 15 s of listening
;   40        a reading of both references now
;   60        Disable and Delete both
; One name per stage: set the next stage only after the 15 s window of the last one has closed (its "quiet" or "listened" line). An event is
; logged with label=door or label=lift and stage=<the open window's stage>, or stage=0 when no window is open. NEVER the wait form (it never
; returns when the graph sends no end event). Every log line that matters also shows as a notification beginning "AP " (Say).
; Optional natives are lines that begin with ";OPT <Base.Name> ": scripts/newgame/make_anim_doorlift.py stage compiles each on its own and keeps
; the ones that compile. ";VOID " lines are the register call's second shape (no return value). One line per finding in the user log
; "FO4SFAnimDL" (My Games\\Starfield\\Logs\\Script\\User\\FO4SFAnimDL.0.log): FO4SFANIM rt=<real time s> <event> key=value ... end=true.
; Which events the lift's graph sends is UNREAD here (the dump of twostages was not read when this was written): its list is the call names
; plus Done and Trans01, and is to be replaced by what the dump shows.

; ---------------------------------------------------------------- the layout (dotnet/AnimDoorLiftControl/Program.cs)

int Version = 1
string LogName = "FO4SFAnimDL"
string ProbePlugin = "FO4SFAnimDoorLift.esm"
string GamePlugin = "Starfield.esm"
int DoorControlId = 0x801   ; ACTI FO4SF_AnimDoorControl of FO4SFAnimDoorLift.esm (local id)
int LiftId = 0x10C35        ; the vanilla ShipQuickLift1, a form of Starfield.esm
float DoorAheadM = 4.0
float LiftM = 40.0

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_QUIET = 100       ; + the stage
float POLL_S = 1.0
float LISTEN_S = 15.0
int[] StageList
bool[] DoneList
string[] DoorEvents
string[] LiftEvents
string[] DoorCalls
string[] LiftCalls
ObjectReference DoorRef = None
ObjectReference LiftRef = None
int ListenStage = 0         ; the play stage whose 15 s window is open; 0 = none (an event then is logged stage=0: outside any window)
int WindowEvents = 0        ; events that arrived in the open window
float LastEventRt = 0.0

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[12]
    DoneList = new bool[12]
    StageList[0] = 10
    StageList[1] = 20
    StageList[2] = 21
    StageList[3] = 22
    StageList[4] = 23
    StageList[5] = 24
    StageList[6] = 31
    StageList[7] = 32
    StageList[8] = 33
    StageList[9] = 34
    StageList[10] = 40
    StageList[11] = 60
    DoorCalls = new string[4]
    DoorCalls[0] = "Open"
    DoorCalls[1] = "Close"
    DoorCalls[2] = "StateA_Play"
    DoorCalls[3] = "StateB_Play"
    LiftCalls = new string[4]
    LiftCalls[0] = "Stage1"
    LiftCalls[1] = "Stage1Transition"
    LiftCalls[2] = "Stage2"
    LiftCalls[3] = "Stage2Transition"
    DoorEvents = new string[10]
    DoorEvents[0] = "Open"
    DoorEvents[1] = "Close"
    DoorEvents[2] = "Trans01"
    DoorEvents[3] = "IsOn"
    DoorEvents[4] = "IsOff"
    DoorEvents[5] = "Done"
    DoorEvents[6] = "StateA_Play"
    DoorEvents[7] = "StateB_Play"
    DoorEvents[8] = "StateA_Idle"
    DoorEvents[9] = "StateB_Idle"
    LiftEvents = new string[6]
    LiftEvents[0] = "Stage1"
    LiftEvents[1] = "Stage1Transition"
    LiftEvents[2] = "Stage2"
    LiftEvents[3] = "Stage2Transition"
    LiftEvents[4] = "Done"
    LiftEvents[5] = "Trans01"
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " doorcontrol=" + Id(Game.GetFormFromFile(DoorControlId, ProbePlugin)) + " lift=" + Id(Game.GetFormFromFile(LiftId, GamePlugin)) + " doorevents=" + DoorEvents.Length + " liftevents=" + LiftEvents.Length)
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {A user log is open only in the game session that opened it (assumed): when a write fails, as after a save is loaded
     again, the log is opened once more and the line written again. Every line ends with end=true.}
    string line = "FO4SFANIM rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    {The on-screen twin of a log line, for a session with script logging off: a short Debug.Notification. Prefixes: REG n/m, PLAY sN
     name ok=..., EV name wN (an event, w = the open window's stage, w0 = none), W sN quiet / W sN heard n (a window closed).}
    Debug.Notification("AP " + msg)
EndFunction

string Function Id(Form f)
    {"<signed decimal form id>" or "none".}
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

string Function Label(ObjectReference r)
    if r == None
        return "none"
    endif
    if r == DoorRef
        return "door"
    endif
    if r == LiftRef
        return "lift"
    endif
    return "other"
EndFunction

; ---------------------------------------------------------------- the animation events

Event OnAnimationEvent(ObjectReference akSource, string asEventName)
    float now = Utility.GetCurrentRealTime()
    Trace("event name=" + asEventName + " label=" + Label(akSource) + " src=" + Id(akSource) + " stage=" + ListenStage + " since=" + (now - LastEventRt))
    Say("EV " + Label(akSource) + " " + asEventName + " w" + ListenStage)
    LastEventRt = now
    if ListenStage != 0
        WindowEvents += 1
    endif
EndEvent

string Function Reg(ObjectReference r, string n)
    {The register call's return as text, "true" / "false". When the game's script declares no return value the stager drops the
     return line and keeps the ";VOID " lines (the log then says ok=void).}
    return "" + RegisterForAnimationEvent(r, n)
;VOID     RegisterForAnimationEvent(r, n)
;VOID     return "void"
EndFunction

Function RegisterList(int stage, string what, ObjectReference r, string[] names)
    if r == None
        Trace("register stage=" + stage + " label=" + what + " ref=none (stage 10 first)")
        return
    endif
    int i = 0
    int okCount = 0
    while i < names.Length
        string res = Reg(r, names[i])
        Trace("register stage=" + stage + " label=" + what + " name=" + names[i] + " ref=" + Id(r) + " ok=" + res)
        if res == "true"
            okCount += 1
        endif
        i += 1
    endwhile
    Say("REG " + what + " s" + stage + " " + okCount + "/" + names.Length + " true")
EndFunction

; ---------------------------------------------------------------- readings and spawning

Function Reading(string when, int stage, string what, ObjectReference r)
    {One line: the reference, its base, 3D, disabled state, cell, position and distance to the player.}
    if r == None
        Trace("read stage=" + stage + " label=" + what + " when=" + when + " ref=none")
        return
    endif
    Actor p = Game.GetPlayer()
    Trace("read stage=" + stage + " label=" + what + " when=" + when + " ref=" + Id(r) + " base=" + Id(r.GetBaseObject()) + " loaded=" + r.Is3DLoaded() + " disabled=" + r.IsDisabled() + " cell=" + Id(r.GetParentCell()) + " pos=" + r.GetPositionX() + "," + r.GetPositionY() + "," + r.GetPositionZ() + " dist=" + p.GetDistance(r))
EndFunction

Function Spawn(int stage)
    {PlaceAtMe the door control (persistent), then 4 m in front of the player when MoveTo exists. The lift is placed DISABLED, moved LIFT_M
     in front of the player and only then enabled: when MoveTo does not exist it stays disabled (a moving platform is never left on the player).}
    Actor p = Game.GetPlayer()
    Form doorBase = Game.GetFormFromFile(DoorControlId, ProbePlugin)
    Form liftBase = Game.GetFormFromFile(LiftId, GamePlugin)
    float a = p.GetAngleZ()
    bool doorMoved = false
    bool liftMoved = false
    if doorBase == None
        Trace("spawn stage=" + stage + " label=door base=none ref=none")
    else
        DoorRef = p.PlaceAtMe(doorBase, 1, true, false, false)
;OPT ObjectReference.MoveTo         if DoorRef
;OPT ObjectReference.MoveTo             DoorRef.MoveTo(p, DoorAheadM * Math.Sin(a), DoorAheadM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo             doorMoved = true
;OPT ObjectReference.MoveTo         endif
        Trace("spawn stage=" + stage + " label=door base=" + Id(doorBase) + " ref=" + Id(DoorRef) + " moved=" + doorMoved + " persist=true")
    endif
    if liftBase == None
        Trace("spawn stage=" + stage + " label=lift base=none ref=none")
    else
        LiftRef = p.PlaceAtMe(liftBase, 1, true, true, false)
;OPT ObjectReference.MoveTo         if LiftRef
;OPT ObjectReference.MoveTo             LiftRef.MoveTo(p, LiftM * Math.Sin(a), LiftM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo             liftMoved = true
;OPT ObjectReference.MoveTo         endif
        if LiftRef && liftMoved
            LiftRef.Enable(false)
        endif
        Trace("spawn stage=" + stage + " label=lift base=" + Id(liftBase) + " ref=" + Id(LiftRef) + " moved=" + liftMoved + " enabled=" + (liftMoved) + " persist=true")
    endif
    Reading("now", stage, "door", DoorRef)
    Reading("now", stage, "lift", LiftRef)
    RegisterList(stage, "door", DoorRef, DoorEvents)
    RegisterList(stage, "lift", LiftRef, LiftEvents)
EndFunction

; ---------------------------------------------------------------- poll and steps

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID >= TIMER_QUIET
        int stage = aiTimerID - TIMER_QUIET
        if WindowEvents == 0
            Trace("quiet stage=" + stage + " seconds=" + LISTEN_S)
            Say("W s" + stage + " quiet")
        else
            Trace("listened stage=" + stage + " events=" + WindowEvents + " seconds=" + LISTEN_S)
            Say("W s" + stage + " heard " + WindowEvents)
        endif
        if ListenStage == stage
            ListenStage = 0
        endif
        if stage < 30
            Reading("settled", stage, "door", DoorRef)
        else
            Reading("settled", stage, "lift", LiftRef)
        endif
    endif
EndEvent

Function Poll()
    int i = 0
    while i < StageList.Length
        if !DoneList[i] && GetStageDone(StageList[i])
            DoneList[i] = true
            Step(StageList[i])
        endif
        i += 1
    endwhile
EndFunction

Function Step(int stage)
    if stage == 10
        Spawn(stage)
    elseif stage == 20
        RegisterList(stage, "door", DoorRef, DoorEvents)
        RegisterList(stage, "lift", LiftRef, LiftEvents)
    elseif stage >= 21 && stage <= 24
        PlayOne(stage, "door", DoorRef, DoorCalls[stage - 21])
    elseif stage >= 31 && stage <= 34
        PlayOne(stage, "lift", LiftRef, LiftCalls[stage - 31])
    elseif stage == 40
        Reading("stage40", stage, "door", DoorRef)
        Reading("stage40", stage, "lift", LiftRef)
    elseif stage == 60
        Cleanup()
    endif
EndFunction

Function PlayOne(int stage, string what, ObjectReference r, string n)
    {One PlayAnimation name: the reading before, the call and its return, then LISTEN_S of listening (events arrive in OnAnimationEvent). Never the wait form.}
    if r == None
        Trace("play stage=" + stage + " label=" + what + " name=" + n + " ref=none (place it first)")
        return
    endif
    Reading("before", stage, what, r)
    ListenStage = stage
    WindowEvents = 0
    bool ok = r.PlayAnimation(n)
    Trace("play stage=" + stage + " label=" + what + " name=" + n + " ref=" + Id(r) + " ok=" + ok)
    Say("PLAY " + what + " s" + stage + " " + n + " ok=" + ok)
    StartTimer(LISTEN_S, TIMER_QUIET + stage)
EndFunction

Function Cleanup()
    Trace("cleanup door=" + Id(DoorRef) + " lift=" + Id(LiftRef))
    if DoorRef
        DoorRef.Disable(false)
;OPT ObjectReference.Delete         DoorRef.Delete()
    endif
    if LiftRef
        LiftRef.Disable(false)
;OPT ObjectReference.Delete         LiftRef.Delete()
    endif
    DoorRef = None
    LiftRef = None
EndFunction
