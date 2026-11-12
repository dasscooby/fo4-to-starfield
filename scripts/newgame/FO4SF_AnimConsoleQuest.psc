Scriptname FO4SF_AnimConsoleQuest extends Quest
{The animation probe, variant D (fo4-to-starfield, docs/research/anim-console-probe.md, FAL-489). Attached to QUST
 FO4SF_AnimConsoleQuest (0x800 of FO4SFAnimConsole.esm): start game enabled, stages set from the console, NO properties (every
 form is found with Game.GetFormFromFile at the moment it is read; a property would make a temporary reference persistent).
 The question: does OUR console (the port's Vault 111 console base, overridden by the plugin with its own rig, its own .af / .afx
 clips and the graph component of the vanilla activator graph activatorstategraph01) answer PlayAnimation the way the vanilla
 activator did in variant A? The script spawns a copy of that base with PlaceAtMe (the override is on the base, so a spawn
 anywhere has the new model), registers for the animation events FROM it, and sends it one name per stage:
   10      PlaceAtMe of the console base 2.5 m in front of the player (persistent), reads it, registers every event name
   20      registers every event name again
   21..28  one PlayAnimation name each, then 15 s of listening. Variant A: Play01 opened the vanilla activator, Play02 closed it,
           TurnOff opened, StateB_Play closed; the rest changed nothing. The names are in that order, the four that moved first.
           Which clip our console shows for each name is the result: screenshots before and after each stage
   30      Activate(player) by script
   40      a reading of the reference now
   60      Disable and Delete the spawned reference
 One name per stage so each is its own line: set the next stage only after the 15 s window of the last one has closed (its "quiet"
 or "listened" line; the on-screen twin is "W ..."), because one window is open at a time. An event is logged with stage=<the open
 window's stage>, or stage=0 when no window is open, and with after=<seconds since that stage's PlayAnimation call>: variant A showed
 Done after a clip, so after= on Done is the clip's length as the engine plays it (the button clip should be near 0.633 s, the glass
 flip near 1.633 s: the original's own times, unread in game). NEVER the wait form.
 Every log line that matters also shows as a short on-screen notification beginning "AP " (Say), for a session with script logging off.
 Optional natives are lines that begin with ";OPT <Base.Name> ": scripts/newgame/make_anim_console.py stage compiles each on its own
 and keeps the ones that compile. ";VOID " lines are the register call's second shape (no return value): the stager keeps them
 instead of the bool-return line when the base scripts declare RegisterForAnimationEvent without a return. The ";BASE" line is the
 console base's local id in FO4Port.esm, written by the stager from the plugin tool's `info` (0 = not given: the script says so).
 One line per finding in the user log "FO4SFAnimD" (My Games\\Starfield\\Logs\\Script\\User\\FO4SFAnimD.0.log): FO4SFANIM rt=<real
 time s> <event> key=value ... end=true (form ids as Papyrus prints them: signed decimal, "none" for None).}

; ---------------------------------------------------------------- the layout (dotnet/AnimConsoleProbe/Program.cs)

int Version = 1
string LogName = "FO4SFAnimD"
string ProbePlugin = "FO4SFAnimConsole.esm"
string BasePlugin = "FO4Port.esm"
int BaseId = 0  ;BASE the console base's local id in FO4Port.esm (the stager writes it; 0 = not given)
float AheadM = 1.5      ; metres in front of the player (variant D session 2 read dist 2.5007 for 2.5: the unit is metres)
float UpM = 1.2         ; metres above the player's own height: a guess at chest height for this model, unread

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
float PlayRt = 0.0            ; real time of the open window's PlayAnimation / Activate call

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
    PlayNames[1] = "Play02"
    PlayNames[2] = "TurnOff"
    PlayNames[3] = "StateB_Play"
    PlayNames[4] = "StateA_Play"
    PlayNames[5] = "TurnOn"
    PlayNames[6] = "Trans01"
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
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " base=" + Id(Game.GetFormFromFile(BaseId, BasePlugin)) + " baseid=" + BaseId + " baseplugin=" + Game.IsPluginInstalled(BasePlugin) + " events=" + EventNames.Length + " plays=" + PlayNames.Length)
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
    float after = now - PlayRt
    Trace("event name=" + asEventName + " src=" + Id(akSource) + " stage=" + ListenStage + " since=" + (now - LastEventRt) + " after=" + after)
    Say("EV " + asEventName + " w" + ListenStage + " t" + after)
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
    Say("READ s" + stage + " " + when + " 3d=" + r.Is3DLoaded() + " off=" + r.IsDisabled() + " dist=" + p.GetDistance(r) + " dz=" + (r.GetPositionZ() - p.GetPositionZ()) + " az=" + r.GetAngleZ() + " pa=" + p.GetAngleZ())
EndFunction

Function Spawn(int stage)
    {PlaceAtMe the console base (persistent), then AheadM in front of the player and UpM above the player's height when MoveTo exists, turned to face the player when SetAngle exists, then register.}
    Actor p = Game.GetPlayer()
    Form base = None
    if BaseId != 0
        base = Game.GetFormFromFile(BaseId, BasePlugin)
    endif
    if base == None
        Trace("spawn stage=" + stage + " base=none ref=none baseid=" + BaseId + " (stage the kit with the plugin tool's info so BaseId is set, and load FO4Port.esm)")
        return
    endif
    TestRef = p.PlaceAtMe(base, 1, true, false, false)
    bool moved = false
    bool turned = false
;OPT ObjectReference.MoveTo     if TestRef
;OPT ObjectReference.MoveTo         float a = p.GetAngleZ()
;OPT ObjectReference.MoveTo         TestRef.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), UpM, false)
;OPT ObjectReference.MoveTo         moved = true
;OPT ObjectReference.MoveTo     endif
;OPT ObjectReference.SetAngle     if TestRef
;OPT ObjectReference.SetAngle         TestRef.SetAngle(0.0, 0.0, p.GetAngleZ() + 180.0)
;OPT ObjectReference.SetAngle         turned = true
;OPT ObjectReference.SetAngle     endif
    Trace("spawn stage=" + stage + " base=" + Id(base) + " ref=" + Id(TestRef) + " moved=" + moved + " turned=" + turned + " persist=true")
    Say("SPAWN s" + stage + " moved=" + moved + " turned=" + turned + " ahead=" + AheadM + " up=" + UpM)
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
    ListenStage = stage
    WindowEvents = 0
    PlayRt = Utility.GetCurrentRealTime()
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
    PlayRt = Utility.GetCurrentRealTime()
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
