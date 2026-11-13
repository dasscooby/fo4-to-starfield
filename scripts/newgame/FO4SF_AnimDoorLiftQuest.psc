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
;   30..38    30 also polls the lift's 3D (Is3DLoaded) once a second for LIFT3D_S seconds, with a notice and a log line per second ("L3D s30 n s 3d=..").
;             PC session 13 Nov 03:15 UTC: the lift was placed, not disabled, 2.5 m ahead, and 3D=FALSE in every reading: nothing to drive. Two retries, each a stage of
;             its own, each followed by the same poll: 37 the BLOCKING Enable on the same reference (no NoWait), 38 a second lift placed ENABLED from the start (no initial
;             disable, no EnableNoWait), moved to the same spot; if its 3D loads it becomes the lift that 31..36 drive and the first one is disabled.
;   31..36    the LIFT: Stage1, Stage2, Stage1NoTransition, Stage2NoTransition, then Stage1Transition and Stage2Transition (clip names, not events: expected
;             false, tried once so the log says so), then 15 s of listening each
;   40        a reading of both references now (shown on screen as READ lines since the 13 Nov session: before, only the log had it)
;   60        Disable and Delete both
; Calls (stages 21..24 and 31..36): the poll only starts a one-shot timer per stage (TIMER_CALL + stage) and the timer makes the call. THAT DOES NOT ISOLATE A CALL
; THAT NEVER RETURNS: a native that does not return keeps this script's one stack, and every later timer event of this script (the poll, the repeats, the window)
; waits behind it (the Courier's FAL-629 hold; not run on Starfield, so whether a lift call hangs is still unread). What the kit does instead: a notice
; "C sN <name> reading" before the reading and "C sN <name> calling" before PlayAnimation, each shown twice 1.2 s apart (Utility.Wait, latent: it lets other events run)
; BEFORE the step, because nothing can repeat a notice once a step hangs. A step that hangs leaves its notice on screen for a few seconds only: a shot soon after the
; console line names it, a late one does not; with script logging on, the log's last line does PROVIDED no later stage was set and no animation event came in the 2.4 s of
; the two waits (either writes its own line after it), because PreNotice writes the same text to the user log FO4SFAnimDL
; (Trace, "notice text=<the notice>", no stage field: FO4SFANIM rt=.. notice text=C sN name reading end=true) BEFORE it shows it (the Courier's FAL-634 hold: the first version did not). The two latent waits let the poll and other timers run, so a
; stage set before the step has started may begin during them: the rule "set the next stage only after the window closed" is the person's, the script does not enforce it. The return notice PLAY and the closing notice W are shown at once and
; repeated (a timer repeats them after the step has returned). The 13 Nov shots were the last one about 20 s after the console line, the window 15 s, and a
; single notice had gone.
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
float LiftAheadM = 2.5      ; the lift 2.5 m in front of the player, between the player and the door (4 m) ...
float LIFT3D_S = 8.0       ; stage 30, 37, 38: seconds the lift's 3D is polled after the placement or the retry
float LiftSideM = 0.0       ; ... and not to the side (the PC session of 13 Nov saw nothing at 5 m ahead, 3 m right); the lift's size is unread

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_QUIET = 100       ; + the stage
int TIMER_RESAY = 200       ; the last on-screen notice shown again
int TIMER_LIFT3D = 500      ; the lift's 3D poll, one tick a second (its own id; tested before >= TIMER_CALL)
int TIMER_CALL = 400        ; + the stage: the play call of that stage (a one-shot timer: it does NOT isolate a call that never returns)
float POLL_S = 1.0
float LISTEN_S = 15.0
float CALL_DELAY_S = 0.3    ; from the poll to the call of a stage
float RESAY_S = 2.0         ; the last notice is shown again every RESAY_S seconds, RESAY_TIMES times
int RESAY_TIMES = 3
string LastLine = ""
int ResayLeft = 0
int[] StageList
bool[] DoneList
string[] DoorEvents
string[] LiftEvents
string[] DoorCalls
string[] LiftCalls
ObjectReference DoorRef = None
ObjectReference LiftRef = None
ObjectReference LiftRef2 = None       ; stage 38: the second lift, placed enabled from the start
ObjectReference Lift3DRef = None      ; the reference whose 3D is being polled
string Lift3DWhat = ""
int Lift3DLeft = 0
int Lift3DSecs = 0
int ListenStage = 0         ; the play stage whose 15 s window is open; 0 = none (an event then is logged stage=0: outside any window)
int WindowEvents = 0        ; events that arrived in the open window
float LastEventRt = 0.0

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[17]
    DoneList = new bool[17]
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
    StageList[13] = 37
    StageList[14] = 38
    StageList[15] = 40
    StageList[16] = 60
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

Function SayHold(string msg)
    {Say it now and again every RESAY_S seconds RESAY_TIMES times (a shot taken seconds later still holds it). The last notice is the one repeated.}
    LastLine = msg
    Say(msg)
    ResayLeft = RESAY_TIMES
    StartTimer(RESAY_S, TIMER_RESAY)
EndFunction

Function Reading(string when, int stage, string what, ObjectReference r)
    {One line: the reference, its base, 3D, disabled state, cell, position and distance to the player.}
    if r == None
        Trace("read stage=" + stage + " label=" + what + " when=" + when + " ref=none")
        return
    endif
    Actor p = Game.GetPlayer()
    Trace("read stage=" + stage + " label=" + what + " when=" + when + " ref=" + Id(r) + " base=" + Id(r.GetBaseObject()) + " loaded=" + r.Is3DLoaded() + " disabled=" + r.IsDisabled() + " cell=" + Id(r.GetParentCell()) + " pos=" + r.GetPositionX() + "," + r.GetPositionY() + "," + r.GetPositionZ() + " dist=" + p.GetDistance(r))
    if when != "before"
        Say("READ s" + stage + " " + what + " " + when + " 3d=" + r.Is3DLoaded() + " off=" + r.IsDisabled() + " dist=" + p.GetDistance(r) + " dz=" + (r.GetPositionZ() - p.GetPositionZ()) + " az=" + r.GetAngleZ() + " pa=" + p.GetAngleZ())
    endif
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
    Lift3DStart("s30", LiftRef)
    Say("S30 done")
EndFunction

; ---------------------------------------------------------------- poll and steps

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_RESAY
        if ResayLeft > 0
            ResayLeft -= 1
            Say(LastLine + " (again)")
            if ResayLeft > 0
                StartTimer(RESAY_S, TIMER_RESAY)
            endif
        endif
    elseif aiTimerID == TIMER_LIFT3D
        Lift3DTick()
    elseif aiTimerID >= TIMER_CALL
        CallStage(aiTimerID - TIMER_CALL)
    elseif aiTimerID >= TIMER_QUIET
        int stage = aiTimerID - TIMER_QUIET
        if WindowEvents == 0
            Trace("quiet stage=" + stage + " seconds=" + LISTEN_S)
            SayHold("W s" + stage + " quiet")
        else
            Trace("listened stage=" + stage + " events=" + WindowEvents + " seconds=" + LISTEN_S)
            SayHold("W s" + stage + " heard " + WindowEvents)
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
    elseif stage == 37
        LiftRetryEnable(stage)
    elseif stage == 38
        LiftPlaceEnabled(stage)
    elseif stage >= 21 && stage <= 24
        StartTimer(CALL_DELAY_S, TIMER_CALL + stage)
    elseif stage >= 31 && stage <= 36
        StartTimer(CALL_DELAY_S, TIMER_CALL + stage)
    elseif stage == 40
        Reading("stage40", stage, "door", DoorRef)
        Reading("stage40", stage, "lift", LiftRef)
    elseif stage == 60
        Cleanup()
    endif
EndFunction

Function PreNotice(string msg)
    {A notice before a step that may not return: shown, 1.2 s, shown again, 1.2 s (Utility.Wait is latent: the script's other events run meanwhile). Nothing can repeat it after the step has started.}
    Trace("notice text=" + msg)
    Say(msg)
    Utility.Wait(1.2)
    Say(msg + " (again)")
    Utility.Wait(1.2)
EndFunction

Function CallStage(int stage)
    {The timer of a play stage: the door's stages 21..24 and the lift's 31..36, each in its own timer event (one stack: a hung call still holds the rest).}
    if stage >= 21 && stage <= 24
        PlayOne(stage, "door", DoorRef, DoorCalls[stage - 21])
    elseif stage >= 31 && stage <= 36
        PlayOne(stage, "lift", LiftRef, LiftCalls[stage - 31])
    endif
EndFunction

Function PlayOne(int stage, string what, ObjectReference r, string n)
    {One PlayAnimation name: a notice, the reading before, a notice, the call and its return, then LISTEN_S of listening (events arrive in OnAnimationEvent). Never the wait form.}
    if r == None
        Trace("play stage=" + stage + " label=" + what + " name=" + n + " ref=none (place it first)")
        Say("C s" + stage + " " + n + " no " + what)
        return
    endif
    PreNotice("C s" + stage + " " + n + " reading")
    Reading("before", stage, what, r)
    ListenStage = stage
    WindowEvents = 0
    PreNotice("C s" + stage + " " + n + " calling")
    StartTimer(LISTEN_S, TIMER_QUIET + stage)
    bool ok = r.PlayAnimation(n)
    Trace("play stage=" + stage + " label=" + what + " name=" + n + " ref=" + Id(r) + " ok=" + ok)
    SayHold("PLAY " + what + " s" + stage + " " + n + " ok=" + ok)
EndFunction

Function Lift3DStart(string what, ObjectReference r)
    {Poll r.Is3DLoaded() once a second for LIFT3D_S seconds: a notice and a log line per tick, and the first tick now. The tick is a timer event (the poll is not blocked).
     One poll at a time: starting another replaces the first one's reference.}
    if r == None
        Say("L3D " + what + " no lift")
        return
    endif
    Lift3DRef = r
    Lift3DWhat = what
    Lift3DSecs = 0
    Lift3DLeft = LIFT3D_S as int
    Lift3DTick()
EndFunction

Function Lift3DTick()
    if Lift3DRef == None
        return
    endif
    bool loaded = Lift3DRef.Is3DLoaded()
    string line = "L3D " + Lift3DWhat + " " + Lift3DSecs + "s 3d=" + loaded + " off=" + Lift3DRef.IsDisabled() + " dist=" + Game.GetPlayer().GetDistance(Lift3DRef)
    Trace("lift3d " + Lift3DWhat + " secs=" + Lift3DSecs + " loaded=" + loaded + " ref=" + Id(Lift3DRef))
    Say(line)
    if loaded
        Lift3DLoaded()
        return
    endif
    Lift3DSecs += 1
    Lift3DLeft -= 1
    if Lift3DLeft > 0
        StartTimer(1.0, TIMER_LIFT3D)
    else
        Say("L3D " + Lift3DWhat + " 3d not loaded after " + (LIFT3D_S as int) + " s")
        Trace("lift3d " + Lift3DWhat + " not loaded after " + (LIFT3D_S as int) + " s ref=" + Id(Lift3DRef))
    endif
EndFunction

Function Lift3DLoaded()
    {The polled lift has its 3D. The second lift (stage 38) then becomes the lift the call stages drive, the first is disabled, and the events are registered on it.}
    if Lift3DWhat == "s38" && Lift3DRef != LiftRef
        if LiftRef
            LiftRef.Disable(false)
        endif
        LiftRef = Lift3DRef
        Say("L3D s38 adopted as the lift")
        RegisterList(38, "lift", LiftRef, LiftEvents)
    endif
EndFunction

Function LiftRetryEnable(int stage)
    {Stage 37: the BLOCKING Enable on the lift of stage 30, then the 3D poll. The notice comes before the call (PreNotice) because a blocking call may not return.}
    if LiftRef == None
        Say("S37 no lift (stage 30 first)")
        return
    endif
    PreNotice("S37 enable (blocking) calling")
    LiftRef.Enable(false)
    Say("S37 enable returned")
    Trace("lift retry stage=" + stage + " blocking enable returned ref=" + Id(LiftRef))
    Reading("now", stage, "lift", LiftRef)
    Lift3DStart("s37", LiftRef)
EndFunction

Function LiftPlaceEnabled(int stage)
    {Stage 38: a SECOND lift placed enabled from the start (no initial disable, no EnableNoWait), moved to the same place as the first, then the 3D poll. The
     first lift is left as it is until the second one's 3D loads (Lift3DLoaded).}
    Actor p = Game.GetPlayer()
    Form liftBase = Game.GetFormFromFile(LiftId, GamePlugin)
    float a = p.GetAngleZ()
    bool moved = false
    if liftBase == None
        Say("S38 lift base none")
        return
    endif
    LiftRef2 = p.PlaceAtMe(liftBase, 1, true, false, false)
    Say("S38 lift 2 placed (enabled)")
;OPT ObjectReference.MoveTo     if LiftRef2
;OPT ObjectReference.MoveTo         LiftRef2.MoveTo(p, LiftAheadM * Math.Sin(a) + LiftSideM * Math.Cos(a), LiftAheadM * Math.Cos(a) - LiftSideM * Math.Sin(a), 0.0, false)
;OPT ObjectReference.MoveTo         moved = true
;OPT ObjectReference.MoveTo     endif
    Say("S38 lift 2 moved=" + moved)
    Trace("lift place stage=" + stage + " second lift ref=" + Id(LiftRef2) + " moved=" + moved + " enabled=true")
    Reading("now", stage, "lift", LiftRef2)
    Lift3DStart("s38", LiftRef2)
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
    if LiftRef2 && LiftRef2 != LiftRef
        LiftRef2.Disable(false)
;OPT ObjectReference.Delete         LiftRef2.Delete()
    endif
    DoorRef = None
    LiftRef = None
    LiftRef2 = None
EndFunction
