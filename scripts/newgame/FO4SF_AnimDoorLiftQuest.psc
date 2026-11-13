Scriptname FO4SF_AnimDoorLiftQuest extends Quest
{The door and lift controls (fo4-to-starfield, docs/research/anim-doorlift-control.md, FAL-489). Attached to QUST FO4SF_AnimDoorLiftQuest
 (0x800 of FO4SFAnimDoorLift.esm): start game enabled, stages set from the console, NO properties. The full description follows as ; comments.}
; Two controls, one session. DOOR: ACTI 0x801 of FO4SFAnimDoorLift.esm, a new activator with the model, rig and clip folder of the vanilla door
; AK_Ext_Bld_WallA_DoorA_01_Alt02 (000AA24A; its Open/Close clips live on SimpleOpenClose01) whose animation graph is genericopenclose01 (no
; vanilla record names it). The vanilla door itself is never placed. LIFT: the vanilla ShipQuickLift1 (00010C35, graph twostages), placed UNCHANGED.
; The script polls the stages once a second:
;   10        place the door 4 m in front of the player, register every event name on it; a notice after EACH step (start, door placed, door moved, registered).
;             The lift is NOT touched here (the PC session of 13 Nov 00:16 UTC: one stage did both, a lift 40 m away outside the room, and then nothing showed)
;   20        register every event name again on the door and on the lift when it exists (the log shows each call's return)
;   21..24    the DOOR: Open, Close, then the direct Opened, Closed, then 15 s of listening each
;   30        place the lift: DISABLED, moved LiftAheadM in front of and LiftSideM to the right of the player (the test room is about 12 m deep), enabled only
;             after the move (NOT blocking when EnableNoWait exists), registered; a notice after each step. A lift that cannot be moved is left disabled and says so
;   31..36    the LIFT: Stage1, Stage2, Stage1NoTransition, Stage2NoTransition, then Stage1Transition and Stage2Transition (clip names, not events: expected
;             false, tried once so the log says so), then 15 s of listening each
;   40        a reading of both references now
;   60        Disable and Delete both
; One name per stage: set the next stage only after the 15 s window of the last one has closed (its "quiet" or "listened" line). An event is
; logged with label=door or label=lift and stage=<the open window's stage>, or stage=0 when no window is open. NEVER the wait form (it never
; returns when the graph sends no end event). Every log line that matters also shows as a notification beginning "AP " (Say).
; Optional natives are lines that begin with ";OPT <Base.Name> ": scripts/newgame/make_anim_doorlift.py stage compiles each on its own and keeps
; the ones that compile. ";VOID " lines are the register call's second shape (no return value). One line per finding in the user log
; "FO4SFAnimDL" (My Games\\Starfield\\Logs\\Script\\User\\FO4SFAnimDL.0.log): FO4SFANIM rt=<real time s> <event> key=value ... end=true.
; The call and event lists are the PC's read of the real graphs (Claude, #755 1bfe5534, 12 Nov 21:15 UTC; supported, not replayed here): twostages takes Stage1, Stage2,
; Stage1NoTransition, Stage2NoTransition and sends TransitionComplete; genericopenclose01 takes Open, Close and the direct Opened, Closed (states Closed, Opening, Opened,
; Closing; clip tags Open and Close). What a PlayAnimation of those names DOES in the game is what the session shows.

; ---------------------------------------------------------------- the layout (dotnet/AnimDoorLiftControl/Program.cs)

int Version = 1
string LogName = "FO4SFAnimDL"
string ProbePlugin = "FO4SFAnimDoorLift.esm"
string GamePlugin = "Starfield.esm"
int DoorControlId = 0x801   ; ACTI FO4SF_AnimDoorControl of FO4SFAnimDoorLift.esm (local id)
int LiftId = 0x10C35        ; the vanilla ShipQuickLift1, a form of Starfield.esm
float DoorAheadM = 4.0
float LiftAheadM = 5.0      ; the lift 5 m in front of the player ...
float LiftSideM = 3.0       ; ... and 3 m to the right: a guess (the test room is about 12 m deep); the lift's size is unread

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
    StageList = new int[15]
    DoneList = new bool[15]
    StageList[0] = 10
    StageList[1] = 20
    StageList[2] = 21
    StageList[3] = 22
    StageList[4] = 23
    StageList[5] = 24
    StageList[6] = 30
    StageList[7] = 31
    StageList[8] = 32
    StageList[9] = 33
    StageList[10] = 34
    StageList[11] = 35
    StageList[12] = 36
    StageList[13] = 40
    StageList[14] = 60
    DoorCalls = new string[4]
    DoorCalls[0] = "Open"
    DoorCalls[1] = "Close"
    DoorCalls[2] = "Opened"
    DoorCalls[3] = "Closed"
    LiftCalls = new string[6]
    LiftCalls[0] = "Stage1"
    LiftCalls[1] = "Stage2"
    LiftCalls[2] = "Stage1NoTransition"
    LiftCalls[3] = "Stage2NoTransition"
    LiftCalls[4] = "Stage1Transition"
    LiftCalls[5] = "Stage2Transition"
    DoorEvents = new string[8]
    DoorEvents[0] = "Opened"
    DoorEvents[1] = "Closed"
    DoorEvents[2] = "Trans01"
    DoorEvents[3] = "Done"
    DoorEvents[4] = "IsOn"
    DoorEvents[5] = "IsOff"
    DoorEvents[6] = "Open"
    DoorEvents[7] = "Close"
    LiftEvents = new string[5]
    LiftEvents[0] = "TransitionComplete"
    LiftEvents[1] = "Stage1"
    LiftEvents[2] = "Stage2"
    LiftEvents[3] = "Stage1NoTransition"
    LiftEvents[4] = "Stage2NoTransition"
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
        Trace("register stage=" + stage + " label=" + what + " ref=none (stage 10 for the door, stage 30 for the lift, first)")
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
    {Stage 10: the DOOR only. A notice after each step, so a step that never returns is the one after the last notice: start, placed, moved, registered.
     PlaceAtMe the door control (persistent), then 4 m in front of the player when MoveTo exists, then register.}
    Actor p = Game.GetPlayer()
    Say("S10 start")
    Form doorBase = Game.GetFormFromFile(DoorControlId, ProbePlugin)
    float a = p.GetAngleZ()
    bool doorMoved = false
    if doorBase == None
        Trace("spawn stage=" + stage + " label=door base=none ref=none")
        Say("S10 door base none")
        return
    endif
    DoorRef = p.PlaceAtMe(doorBase, 1, true, false, false)
    Say("S10 door placed")
;OPT ObjectReference.MoveTo     if DoorRef
;OPT ObjectReference.MoveTo         DoorRef.MoveTo(p, DoorAheadM * Math.Sin(a), DoorAheadM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo         doorMoved = true
;OPT ObjectReference.MoveTo     endif
    Say("S10 door moved=" + doorMoved)
    Trace("spawn stage=" + stage + " label=door base=" + Id(doorBase) + " ref=" + Id(DoorRef) + " moved=" + doorMoved + " persist=true")
    Reading("now", stage, "door", DoorRef)
    RegisterList(stage, "door", DoorRef, DoorEvents)
    Say("S10 done")
EndFunction

Function SpawnLift(int stage)
    {Stage 30: the LIFT, after the door's stages. PlaceAtMe it DISABLED, move it LiftAheadM in front of and LiftSideM to the right of the player, and only
     then enable it: with EnableNoWait when the game has it (it never blocks), else Enable. With no MoveTo it stays disabled (a moving platform is never left on
     the player). A notice after each step.}
    Actor p = Game.GetPlayer()
    Say("S30 start")
    Form liftBase = Game.GetFormFromFile(LiftId, GamePlugin)
    float a = p.GetAngleZ()
    bool liftMoved = false
    bool nowait = false
    if liftBase == None
        Trace("spawn stage=" + stage + " label=lift base=none ref=none")
        Say("S30 lift base none")
        return
    endif
    LiftRef = p.PlaceAtMe(liftBase, 1, true, true, false)
    Say("S30 lift placed (disabled)")
;OPT ObjectReference.MoveTo     if LiftRef
;OPT ObjectReference.MoveTo         LiftRef.MoveTo(p, LiftAheadM * Math.Sin(a) + LiftSideM * Math.Cos(a), LiftAheadM * Math.Cos(a) - LiftSideM * Math.Sin(a), 0.0, false)
;OPT ObjectReference.MoveTo         liftMoved = true
;OPT ObjectReference.MoveTo     endif
    Say("S30 lift moved=" + liftMoved)
    if LiftRef && liftMoved
;OPT ObjectReference.EnableNoWait         LiftRef.EnableNoWait(false)
;OPT ObjectReference.EnableNoWait         nowait = true
        if !nowait
            LiftRef.Enable(false)
        endif
        Say("S30 lift enabled nowait=" + nowait)
    endif
    Trace("spawn stage=" + stage + " label=lift base=" + Id(liftBase) + " ref=" + Id(LiftRef) + " moved=" + liftMoved + " enabled=" + liftMoved + " nowait=" + nowait + " persist=true")
    Reading("now", stage, "lift", LiftRef)
    RegisterList(stage, "lift", LiftRef, LiftEvents)
    Say("S30 done")
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
    elseif stage == 30
        SpawnLift(stage)
    elseif stage >= 21 && stage <= 24
        PlayOne(stage, "door", DoorRef, DoorCalls[stage - 21])
    elseif stage >= 31 && stage <= 36
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
