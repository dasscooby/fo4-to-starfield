Scriptname FO4SF_AnimConsoleFourQuest extends Quest
{The converted console on four states (fo4-to-starfield, docs/research/anim-console-four.md, FAL-489): attached to QUST FO4SF_AnimConsoleFourQuest, stages set from the console. The full description follows as ; comments.}
; The converted Vault 111 console (the port's console base, overridden by FO4SFAnimConsoleFour.esm with its own rig, eight .af / .afx clips and the
; graph component of genericstategraph01) plays each of the graph's four states in turn, so each state shows ITS OWN pose. The generic control
; (#756, PC 12 Nov 22:35 UTC) showed genericstategraph01 loads on an object of ours, Play01..Play04 and the direct StateC_Play return true and
; StateA_Idle..StateD_Idle hold; there C and D were copies of A and B, so they looked alike. Here they are four different poses (the card says
; which). The script spawns a copy of the base with PlaceAtMe (the override is on the base) and registers for the animation events from it:
;   10      PlaceAtMe of the console base AheadM in front of the player and UpM above the player's height, turned to face the player when
;           SetAngle compiles (persistent), reads it, registers every event name
;   11      a SECOND copy SideM to the player's right of the first, turned a quarter circle from it: one shot shows the front and the side
;   20      registers every event name again on every copy
;   21..24  PlayAnimation Play01, Play02, Play03, Play04 (the numbered calls), then 15 s of listening each
;   25..28  PlayAnimation StateA_Idle, StateB_Idle, StateC_Idle, StateD_Idle (the direct calls: each jumps to that state and holds its pose)
;   29      PlayAnimation StateD_Play (the spare play slot: a one-frame hold of the last pose, nothing should move)
;   40      a reading of the reference now
;   60      Disable and Delete the spawned references
; Every play stage calls the name on EVERY copy that exists (the side copy too), logs each return, shows the return as a notification AT ONCE
; (nothing is shown before it) and shows it again every 2 s for 6 s, so a shot 1.2 s or 3 s after the console line still holds it; when the 15 s
; window closes one notice says which call it was, what it returned and how many events came in. One name per stage: set the next stage only after
; the window of the last one has closed (the "W s<stage> <name> ..." notice), because one window is open at a time. An event is logged with
; stage=<the open window's stage>, or stage=0 when no window is open, and with after=<seconds since that stage's PlayAnimation call>. NEVER the
; wait form. Every log line that matters also shows as a short on-screen notification beginning "AP " (Say), for a session with script logging off.
; Optional natives are lines that begin with ";OPT <Base.Name> ": scripts/newgame/make_anim_console_four.py stage compiles each on its own and
; keeps the ones that compile. ";VOID " lines are the register call's second shape (no return value). The ";BASE" line is the console base's local
; id in FO4Port.esm, written by the stager from the plugin tool's `info`. One line per finding in the user log "FO4SFAnimF" (My Games\\Starfield\\Logs\\
; Script\\User\\FO4SFAnimF.0.log): FO4SFANIM rt=<real time s> <event> key=value ... end=true (form ids as Papyrus prints them).

; ---------------------------------------------------------------- the layout (dotnet/AnimConsoleFour/Program.cs)

int Version = 1
string LogName = "FO4SFAnimF"
string ProbePlugin = "FO4SFAnimConsoleFour.esm"
string BasePlugin = "FO4Port.esm"
int BaseId = 0  ;BASE the console base's local id in FO4Port.esm (the stager writes it; 0 = not given)
float AheadM = 1.5      ; metres in front of the player (variant D session 2 read dist 2.5007 for 2.5: the unit is metres)
float SideM = 0.9       ; metres to the player's right for the second copy (stage 11), a guess for a clear side view
float UpM = 1.2         ; metres above the player's own height: a guess at chest height for this model, unread

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_QUIET = 100       ; + the stage: the window of that play stage closes
int TIMER_RESAY = 200       ; the return notice shown again
float POLL_S = 1.0
float LISTEN_S = 15.0
float RESAY_S = 2.0         ; the return notice is shown again every RESAY_S seconds, RESAY_TIMES times
int RESAY_TIMES = 3
int[] StageList
bool[] DoneList
string[] EventNames
string[] PlayNames
ObjectReference TestRef = None
ObjectReference TestRef2 = None   ; the side copy (stage 11)
string ListenName = ""      ; the name called in the open window
string ListenOk = ""         ; what that call returned, "true" / "false" (copies joined with "/")
string LastPlayLine = ""     ; the return notice, shown again by TIMER_RESAY
int ResayLeft = 0
float FirstDoneAfter = -1.0  ; seconds from the call to the first Done of the open window, -1 = none yet
int ListenStage = 0         ; the play stage whose 15 s window is open; 0 = none (an event then is logged stage=0: outside any window)
int WindowEvents = 0        ; events that arrived in the open window
float LastEventRt = 0.0
float PlayRt = 0.0            ; real time of the open window's PlayAnimation / Activate call

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[14]
    DoneList = new bool[14]
    StageList[0] = 10
    StageList[1] = 11
    StageList[2] = 20
    StageList[3] = 21
    StageList[4] = 22
    StageList[5] = 23
    StageList[6] = 24
    StageList[7] = 25
    StageList[8] = 26
    StageList[9] = 27
    StageList[10] = 28
    StageList[11] = 29
    StageList[12] = 40
    StageList[13] = 60
    PlayNames = new string[9]
    PlayNames[0] = "Play01"
    PlayNames[1] = "Play02"
    PlayNames[2] = "Play03"
    PlayNames[3] = "Play04"
    PlayNames[4] = "StateA_Idle"
    PlayNames[5] = "StateB_Idle"
    PlayNames[6] = "StateC_Idle"
    PlayNames[7] = "StateD_Idle"
    PlayNames[8] = "StateD_Play"
    EventNames = new string[24]
    EventNames[0] = "Trans01"
    EventNames[1] = "Trans02"
    EventNames[2] = "Trans03"
    EventNames[3] = "Done"
    EventNames[4] = "IsOn"
    EventNames[5] = "IsOff"
    EventNames[6] = "Play01"
    EventNames[7] = "Play02"
    EventNames[8] = "Play03"
    EventNames[9] = "Play04"
    EventNames[10] = "Play05"
    EventNames[11] = "StateA_Idle"
    EventNames[12] = "StateA_Play"
    EventNames[13] = "StateB_Idle"
    EventNames[14] = "StateB_Play"
    EventNames[15] = "StateC_Idle"
    EventNames[16] = "StateC_Play"
    EventNames[17] = "StateD_Idle"
    EventNames[18] = "StateD_Play"
    EventNames[19] = "TurnOn"
    EventNames[20] = "TurnOff"
    EventNames[21] = "Opened"
    EventNames[22] = "Stage4"
    EventNames[23] = "TransitionComplete"
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
     event, w = the open window's stage, w0 = none), W sN <name> ok=.. quiet / heard n (a window closed).}
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
    if akSource != TestRef2
        Say("EV " + asEventName + " w" + ListenStage + " t" + after)
    endif
    LastEventRt = now
    if ListenStage != 0
        WindowEvents += 1
        if asEventName == "Done" && FirstDoneAfter < 0.0
            FirstDoneAfter = after
        endif
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
    RegisterRef(stage, TestRef)
    RegisterRef(stage, TestRef2)
EndFunction

Function RegisterRef(int stage, ObjectReference r)
    if r == None
        Trace("register stage=" + stage + " ref=none (stage 10 first)")
        return
    endif
    int i = 0
    int okCount = 0
    while i < EventNames.Length
        string res = Reg(r, EventNames[i])
        Trace("register stage=" + stage + " name=" + EventNames[i] + " ref=" + Id(r) + " ok=" + res)
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
    if when != "before"
        Say("READ s" + stage + " " + when + " 3d=" + r.Is3DLoaded() + " off=" + r.IsDisabled() + " dist=" + p.GetDistance(r) + " dz=" + (r.GetPositionZ() - p.GetPositionZ()) + " az=" + r.GetAngleZ() + " pa=" + p.GetAngleZ())
    endif
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

Function SpawnSide(int stage)
    {A second copy of the console 0.9 m to the player's right of the first, turned a quarter circle from the first, for a side view.}
    Actor p = Game.GetPlayer()
    Form base = None
    if BaseId != 0
        base = Game.GetFormFromFile(BaseId, BasePlugin)
    endif
    if base == None || TestRef == None
        Trace("spawnside stage=" + stage + " needs stage 10 first (base=" + Id(base) + " first=" + Id(TestRef) + ")")
        return
    endif
    TestRef2 = p.PlaceAtMe(base, 1, true, false, false)
    bool moved = false
    bool turned = false
;OPT ObjectReference.MoveTo     if TestRef2
;OPT ObjectReference.MoveTo         float a = p.GetAngleZ()
;OPT ObjectReference.MoveTo         TestRef2.MoveTo(p, AheadM * Math.Sin(a) + SideM * Math.Cos(a), AheadM * Math.Cos(a) - SideM * Math.Sin(a), UpM, false)
;OPT ObjectReference.MoveTo         moved = true
;OPT ObjectReference.MoveTo     endif
;OPT ObjectReference.SetAngle     if TestRef2
;OPT ObjectReference.SetAngle         TestRef2.SetAngle(0.0, 0.0, p.GetAngleZ() + 270.0)
;OPT ObjectReference.SetAngle         turned = true
;OPT ObjectReference.SetAngle     endif
    Trace("spawnside stage=" + stage + " ref=" + Id(TestRef2) + " moved=" + moved + " turned=" + turned + " side=" + SideM)
    Say("SIDE s" + stage + " moved=" + moved + " turned=" + turned + " side=" + SideM)
    Reading("side", stage, TestRef2)
    RegisterRef(stage, TestRef2)
EndFunction

; ---------------------------------------------------------------- poll and steps

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_RESAY
        if ResayLeft > 0
            ResayLeft -= 1
            Say(LastPlayLine + " (again)")
            if ResayLeft > 0
                StartTimer(RESAY_S, TIMER_RESAY)
            endif
        endif
    elseif aiTimerID >= TIMER_QUIET
        int stage = aiTimerID - TIMER_QUIET
        if WindowEvents == 0
            Trace("quiet stage=" + stage + " seconds=" + LISTEN_S)
            Say("W s" + stage + " " + ListenName + " ok=" + ListenOk + " quiet")
        else
            Trace("listened stage=" + stage + " events=" + WindowEvents + " seconds=" + LISTEN_S)
            Say("W s" + stage + " " + ListenName + " ok=" + ListenOk + " heard " + WindowEvents)
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
    elseif stage == 11
        SpawnSide(stage)
    elseif stage == 20
        RegisterAll(stage)
    elseif stage >= 21 && stage <= 29
        PlayOne(stage, PlayNames[stage - 21])
    elseif stage == 40
        Reading("stage40", stage, TestRef)
        Reading("stage40", stage, TestRef2)
    elseif stage == 60
        Cleanup()
    endif
EndFunction

Function PlayOne(int stage, string n)
    {One PlayAnimation name on every copy that exists: the reading before (logged only, nothing on screen), the call, its return shown AT ONCE and
     again every RESAY_S seconds RESAY_TIMES times, then LISTEN_S of listening (events arrive in OnAnimationEvent). Never the wait form.}
    if TestRef == None
        Trace("play stage=" + stage + " name=" + n + " ref=none (place it first)")
        return
    endif
    Reading("before", stage, TestRef)
    Reading("before", stage, TestRef2)
    ListenStage = stage
    ListenName = n
    WindowEvents = 0
    FirstDoneAfter = -1.0
    PlayRt = Utility.GetCurrentRealTime()
    bool ok = TestRef.PlayAnimation(n)
    ListenOk = "" + ok
    Trace("play stage=" + stage + " name=" + n + " ref=" + Id(TestRef) + " ok=" + ok)
    if TestRef2
        bool ok2 = TestRef2.PlayAnimation(n)
        ListenOk = ListenOk + "/" + ok2
        Trace("play stage=" + stage + " name=" + n + " ref=" + Id(TestRef2) + " ok=" + ok2)
    endif
    LastPlayLine = "PLAY s" + stage + " " + n + " ok=" + ListenOk
    Say(LastPlayLine)
    ResayLeft = RESAY_TIMES
    StartTimer(RESAY_S, TIMER_RESAY)
    StartTimer(LISTEN_S, TIMER_QUIET + stage)
EndFunction

Function Cleanup()
    Trace("cleanup ref=" + Id(TestRef))
    if TestRef
        TestRef.Disable(false)
;OPT ObjectReference.Delete         TestRef.Delete()
    endif
    TestRef = None
    if TestRef2
        TestRef2.Disable(false)
;OPT ObjectReference.Delete         TestRef2.Delete()
    endif
    TestRef2 = None
EndFunction
