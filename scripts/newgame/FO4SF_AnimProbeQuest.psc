Scriptname FO4SF_AnimProbeQuest extends Quest
{The animation probe, variant A, the vanilla control (fo4-to-starfield, docs/research/anim-probe.md, FAL-489). Attached to QUST
 FO4SF_AnimProbeQuest (0x800 of FO4SFAnimProbe.esm): start game enabled, stages set from the console, NO properties (every form
 is found with Game.GetFormFromFile at the moment it is read; a property would make a temporary reference persistent).
 The question: does ObjectReference.PlayAnimation work on a pure-vanilla activator in our setup, and which animation events
 arrive in Papyrus? The activator is ACTI 001CCAC2 of Starfield.esm (IndIntAddonArtifactHolder01: activatorstategraph01.agx, its
 own skeleton.rig, a CNAM folder with statea_idle.af and the rest). Nothing of ours is attached to it; this quest spawns it,
 registers for events FROM it, and sends it event names, one per stage. The script polls the stages once a second:
   10      PlaceAtMe of the vanilla activator 2.5 m in front of the player (persistent), then registers every event name
   20      registers every event name again (the log shows each call's return)
   21..28  one PlayAnimation name each (the PLAY list below), then 15 s of listening: every event that arrives is a line, and
           a line "quiet" says none came in the last 15 s
   30      Activate(player) by script: whether the activator's own activation plays something and sends events
   40      a reading of the reference now
   60      Disable and Delete the spawned reference
 One name per stage so each is its own line. NEVER the wait form (it never returns when the graph sends no end event).
 Optional natives are lines that begin with ";OPT <Base.Name> ": scripts/newgame/make_anim_probe.py stage compiles each on its own
 and keeps the ones that compile. ";VOID " lines are the register call's second shape (no return value): the stager keeps them
 instead of the bool-return line when the base scripts declare RegisterForAnimationEvent without a return. One line per finding in the user log "FO4SFAnim" (My Games\\Starfield\\Logs\\Script\\User\\
 FO4SFAnim.0.log): FO4SFANIM rt=<real time s> <event> key=value ... end=true (form ids as Papyrus prints them: signed decimal,
 "none" for None).}

; ---------------------------------------------------------------- the layout (dotnet/AnimProbe/Program.cs)

int Version = 1
string LogName = "FO4SFAnim"
string ProbePlugin = "FO4SFAnimProbe.esm"
int ActiId = 0x1CCAC2        ; ACTI IndIntAddonArtifactHolder01 of Starfield.esm (local id; Starfield.esm is load index 0)
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
int CurrentStage = 0
float LastEventRt = 0.0

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[13]
    DoneList = new bool[13]
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
    StageList[10] = 30
    StageList[11] = 40
    StageList[12] = 60
    PlayNames = new string[8]
    PlayNames[0] = "Play01"
    PlayNames[1] = "StateA_Play"
    PlayNames[2] = "Trans01"
    PlayNames[3] = "Play02"
    PlayNames[4] = "TurnOn"
    PlayNames[5] = "TurnOff"
    PlayNames[6] = "StateB_Play"
    PlayNames[7] = "Trans02"
    EventNames = new string[22]
    EventNames[0] = "Trans01"
    EventNames[1] = "Done"
    EventNames[2] = "StateA_Idle"
    EventNames[3] = "StateA_Play"
    EventNames[4] = "StateB_Idle"
    EventNames[5] = "StateB_Play"
    EventNames[6] = "Play01"
    EventNames[7] = "Play02"
    EventNames[8] = "Play03"
    EventNames[9] = "Play04"
    EventNames[10] = "Trans02"
    EventNames[11] = "TurnOn"
    EventNames[12] = "TurnOff"
    EventNames[13] = "Reset"
    EventNames[14] = "TransitionComplete"
    EventNames[15] = "AnimFinish"
    EventNames[16] = "EndAnim"
    EventNames[17] = "Stage4"
    EventNames[18] = "KlaxonStop"
    EventNames[19] = "IdleStop"
    EventNames[20] = "IsOn"
    EventNames[21] = "IsOff"
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " acti=" + Id(Game.GetFormFromFile(ActiId, "Starfield.esm")) + " events=" + EventNames.Length + " plays=" + PlayNames.Length)
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
    Trace("event name=" + asEventName + " src=" + Id(akSource) + " stage=" + CurrentStage + " since=" + (now - LastEventRt))
    LastEventRt = now
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
    while i < EventNames.Length
        string res = Reg(TestRef, EventNames[i])
        Trace("register stage=" + stage + " name=" + EventNames[i] + " ref=" + Id(TestRef) + " ok=" + res)
        i += 1
    endwhile
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
    {PlaceAtMe the vanilla activator (persistent), then 2.5 m in front of the player when MoveTo exists, then register.}
    Actor p = Game.GetPlayer()
    Form base = Game.GetFormFromFile(ActiId, "Starfield.esm")
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
        float quiet = Utility.GetCurrentRealTime() - LastEventRt
        if LastEventRt == 0.0 || quiet >= LISTEN_S - 0.5
            Trace("quiet stage=" + stage + " seconds=" + LISTEN_S)
        else
            Trace("listened stage=" + stage + " last_event_s_ago=" + quiet)
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
    CurrentStage = stage
    if stage == 10
        Spawn(stage)
    elseif stage == 20
        RegisterAll(stage)
    elseif stage >= 21 && stage <= 28
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
    bool ok = TestRef.PlayAnimation(n)
    Trace("play stage=" + stage + " name=" + n + " ref=" + Id(TestRef) + " ok=" + ok)
    StartTimer(LISTEN_S, TIMER_QUIET + stage)
EndFunction

Function ActivateOnce(int stage)
    if TestRef == None
        Trace("step stage=" + stage + " call=Activate ref=none (place it first)")
        return
    endif
    Reading("before", stage, TestRef)
    TestRef.Activate(Game.GetPlayer(), false)
    Trace("step stage=" + stage + " call=Activate ref=" + Id(TestRef))
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
