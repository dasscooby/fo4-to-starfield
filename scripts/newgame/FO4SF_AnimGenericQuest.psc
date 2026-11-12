Scriptname FO4SF_AnimGenericQuest extends Quest
{The generic-graph control (fo4-to-starfield, docs/research/anim-generic-control.md, FAL-489). Attached to QUST FO4SF_AnimGenericQuest
 (0x800 of FO4SFAnimGeneric.esm): start game enabled, stages set from the console, NO properties. The full description follows as ; comments.}
; The question: does a graph no vanilla object uses, genericstategraph01 (Sequence Names StateA..StateD, each _Idle and _Play; Send Event
; On End Trans01), load on an object of ours, which PlayAnimation names does it take, which events reach Papyrus, and does the object HOLD a
; pose between calls? The object is ACTI 0x801 of FO4SFAnimGeneric.esm: a COPY of the vanilla activator 001CCAC2 (IndIntAddonArtifactHolder01,
; same model and rig) whose animation graph component names genericstategraph01 and whose clip folder is ours, eight clips: StateA_Idle,
; StateA_Play, StateB_Idle, StateB_Play (copies of the vanilla holder's four) and StateC_* = A, StateD_* = B. The script polls the stages
; once a second:
;   10      PlaceAtMe of the control 2.5 m in front of the player (persistent), then registers every event name
;   20      registers every event name again (the log shows each call's return)
;   21..29  one PlayAnimation name each (the PLAY list below), then 15 s of listening: every event that arrives is a line, and a line
;           "quiet" says none came in the last 15 s
;   30      Activate(player) by script
;   40      a reading of the reference now
;   60      Disable and Delete the spawned reference
; One name per stage: set the next stage only after the 15 s window of the last one has closed (its "quiet" or "listened" line). An event
; is logged with stage=<the open window's stage>, or stage=0 when no window is open. NEVER the wait form (it never returns when the graph
; sends no end event). Every log line that matters also shows as a notification beginning "AP " (Say), for a session with script logging off.
; Optional natives are lines that begin with ";OPT <Base.Name> ": scripts/newgame/make_anim_generic.py stage compiles each on its own and
; keeps the ones that compile. The PLAY list is the order the PC read from genericstategraph01's links (Claude, #755, 12 Nov 20:40 UTC): Play01..Play05
; (the events that enter the A, B, C and D sides), then the direct StateC_Play, StateD_Play, StateC_Idle, StateD_Idle. ";VOID " lines are the register call's second shape (no return value). One line per finding in the user log
; "FO4SFAnimG" (My Games\Starfield\Logs\Script\User\FO4SFAnimG.0.log): FO4SFANIM rt=<real time s> <event> key=value ... end=true.

; ---------------------------------------------------------------- the layout (dotnet/AnimGenericControl/Program.cs)

int Version = 1
string LogName = "FO4SFAnimG"
string ProbePlugin = "FO4SFAnimGeneric.esm"
int ControlId = 0x801       ; ACTI FO4SF_AnimGenericControl of FO4SFAnimGeneric.esm (local id): a copy of the vanilla holder 001CCAC2 on genericstategraph01
float AheadM = 2.5

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_QUIET = 100       ; + the stage
float POLL_S = 1.0
float LISTEN_S = 15.0
int[] StageList
bool[] DoneList
string[] EventNames
string[] PlayNames
ObjectReference TestRef = None
int ListenStage = 0         ; the play stage whose 15 s window is open; 0 = none (an event then is logged stage=0: outside any window)
int WindowEvents = 0        ; events that arrived in the open window
float LastEventRt = 0.0

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[14]
    DoneList = new bool[14]
    StageList[0] = 10
    StageList[1] = 20
    StageList[2] = 21
    StageList[3] = 22
    StageList[4] = 23
    StageList[5] = 24
    StageList[6] = 25
    StageList[7] = 26
    StageList[8] = 27
    StageList[9] = 28
    StageList[10] = 29
    StageList[11] = 30
    StageList[12] = 40
    StageList[13] = 60
    PlayNames = new string[9]
    PlayNames[0] = "Play01"
    PlayNames[1] = "Play02"
    PlayNames[2] = "Play03"
    PlayNames[3] = "Play04"
    PlayNames[4] = "Play05"
    PlayNames[5] = "StateC_Play"
    PlayNames[6] = "StateD_Play"
    PlayNames[7] = "StateC_Idle"
    PlayNames[8] = "StateD_Idle"
    EventNames = new string[24]
    EventNames[0] = "Trans01"
    EventNames[1] = "Done"
    EventNames[2] = "Trans02"
    EventNames[3] = "Trans03"
    EventNames[4] = "IsOn"
    EventNames[5] = "IsOff"
    EventNames[6] = "AnimFinish"
    EventNames[7] = "IdleStop"
    EventNames[8] = "StateA_Idle"
    EventNames[9] = "StateA_Play"
    EventNames[10] = "StateB_Idle"
    EventNames[11] = "StateB_Play"
    EventNames[12] = "StateC_Idle"
    EventNames[13] = "StateC_Play"
    EventNames[14] = "StateD_Idle"
    EventNames[15] = "StateD_Play"
    EventNames[16] = "Play01"
    EventNames[17] = "Play02"
    EventNames[18] = "Play03"
    EventNames[19] = "Play04"
    EventNames[20] = "Play05"
    EventNames[21] = "TurnOn"
    EventNames[22] = "TurnOff"
    EventNames[23] = "Opened"
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " control=" + Id(Game.GetFormFromFile(ControlId, ProbePlugin)) + " events=" + EventNames.Length + " plays=" + PlayNames.Length)
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
    {The on-screen twin of a log line, for a session with script logging off (variant A ran so, 12 Nov): a short Debug.Notification
     the person at the keyboard can read. Prefixes: REG n/m (register calls that returned true), PLAY sN name ok=..., EV name wN (an
     event, w = the open window's stage, w0 = none), W sN quiet / W sN heard n (a window closed).}
    Debug.Notification("AP " + msg)
EndFunction

string Function Id(Form f)
    {"<signed decimal form id>" or "none".}
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

; ---------------------------------------------------------------- the animation events

Event OnAnimationEvent(ObjectReference akSource, string asEventName)
    float now = Utility.GetCurrentRealTime()
    Trace("event name=" + asEventName + " src=" + Id(akSource) + " stage=" + ListenStage + " since=" + (now - LastEventRt))
    Say("EV " + asEventName + " w" + ListenStage)
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

Function RegisterAll(int stage)
    if TestRef == None
        Trace("register stage=" + stage + " ref=none (stage 10 first)")
        return
    endif
    int i = 0
    int okCount = 0
    while i < EventNames.Length
        string res = Reg(TestRef, EventNames[i])
        Trace("register stage=" + stage + " name=" + EventNames[i] + " ref=" + Id(TestRef) + " ok=" + res)
        if res == "true"
            okCount += 1
        endif
        i += 1
    endwhile
    Say("REG s" + stage + " " + okCount + "/" + EventNames.Length + " true")
EndFunction

; ---------------------------------------------------------------- readings and spawning

Function Reading(string when, int stage, ObjectReference r)
    {One line: the reference, its base, 3D, disabled state, cell, position and distance to the player.}
    if r == None
        Trace("read stage=" + stage + " when=" + when + " ref=none")
        return
    endif
    Actor p = Game.GetPlayer()
    Trace("read stage=" + stage + " when=" + when + " ref=" + Id(r) + " base=" + Id(r.GetBaseObject()) + " loaded=" + r.Is3DLoaded() + " disabled=" + r.IsDisabled() + " cell=" + Id(r.GetParentCell()) + " pos=" + r.GetPositionX() + "," + r.GetPositionY() + "," + r.GetPositionZ() + " dist=" + p.GetDistance(r))
EndFunction

Function Spawn(int stage)
    {PlaceAtMe the control activator (persistent), then 2.5 m in front of the player when MoveTo exists, then register.}
    Actor p = Game.GetPlayer()
    Form base = Game.GetFormFromFile(ControlId, ProbePlugin)
    if base == None
        Trace("spawn stage=" + stage + " base=none ref=none")
        return
    endif
    TestRef = p.PlaceAtMe(base, 1, true, false, false)
    bool moved = false
;OPT ObjectReference.MoveTo     if TestRef
;OPT ObjectReference.MoveTo         float a = p.GetAngleZ()
;OPT ObjectReference.MoveTo         TestRef.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo         moved = true
;OPT ObjectReference.MoveTo     endif
    Trace("spawn stage=" + stage + " base=" + Id(base) + " ref=" + Id(TestRef) + " moved=" + moved + " persist=true")
    Reading("now", stage, TestRef)
    RegisterAll(stage)
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
        Reading("settled", stage, TestRef)
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
        RegisterAll(stage)
    elseif stage >= 21 && stage <= 29
        PlayOne(stage, PlayNames[stage - 21])
    elseif stage == 30
        ActivateOnce(stage)
    elseif stage == 40
        Reading("stage40", stage, TestRef)
    elseif stage == 60
        Cleanup()
    endif
EndFunction

Function PlayOne(int stage, string n)
    {One PlayAnimation name: the reading before, the call and its return, then LISTEN_S of listening (events arrive in OnAnimationEvent). Never the wait form.}
    if TestRef == None
        Trace("play stage=" + stage + " name=" + n + " ref=none (place it first)")
        return
    endif
    Reading("before", stage, TestRef)
    ListenStage = stage
    WindowEvents = 0
    bool ok = TestRef.PlayAnimation(n)
    Trace("play stage=" + stage + " name=" + n + " ref=" + Id(TestRef) + " ok=" + ok)
    Say("PLAY s" + stage + " " + n + " ok=" + ok)
    StartTimer(LISTEN_S, TIMER_QUIET + stage)
EndFunction

Function ActivateOnce(int stage)
    if TestRef == None
        Trace("step stage=" + stage + " call=Activate ref=none (place it first)")
        return
    endif
    Reading("before", stage, TestRef)
    ListenStage = stage
    WindowEvents = 0
    TestRef.Activate(Game.GetPlayer(), false)
    Trace("step stage=" + stage + " call=Activate ref=" + Id(TestRef))
    Say("ACTIVATE s" + stage)
    StartTimer(LISTEN_S, TIMER_QUIET + stage)
EndFunction

Function Cleanup()
    Trace("cleanup ref=" + Id(TestRef))
    if TestRef
        TestRef.Disable(false)
;OPT ObjectReference.Delete         TestRef.Delete()
    endif
    TestRef = None
EndFunction
