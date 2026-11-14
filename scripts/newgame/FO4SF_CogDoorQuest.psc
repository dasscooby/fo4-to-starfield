Scriptname FO4SF_CogDoorQuest extends Quest
{The Vault 111 cog door SetOpen fallback (fo4-to-starfield, FAL-756 / FAL-489 Plan B): attached to QUST FO4SF_CogDoorQuest, stages set from the console. The full description follows as ; comments.}
; Plan B step 0 (PC, 14 Nov 2026) showed the placed cog door (REFR 00126D of FO4Port.esm) shows no prompt and does nothing on E from the
; ramp end, 6 m away: a player cannot stand where activation could work. The shipped new-game quest opens it by script (SetOpen(True)), so
; this probe does the same on its own, with a read of the open state before and after and a timed log:
; 10      read the reference: base, 3D loaded, open state, cell, position, distance from the player (no change made)
; 20      SetOpen(true), then the open state again and every PollS seconds for WatchS seconds
; 30      SetOpen(false), the same watch
; 40      Activate(player) by script (what `prid 00126D` then `activate player` does from the console), the same watch
; 50      read again (no change made)
; Set the next stage only after the watch of the last one has closed (its "watch done" line). The kit holds this quest with the DOOR
; override of the cog door's base on a new model path (the install route) or, built with --control, with the quest alone (the installed
; port's own door answers the same stages). The door clip runs 43.3 s: keep the console CLOSED through the watch (the clock stops while
; it is open), and shoot the door from the same spot as step 0.
; NO properties (the reference is found with Game.GetFormFromFile at the moment it is read; a property would make a temporary reference
; persistent). The ";REF" line is the reference's local id in FO4Port.esm, written by the stager.
; One line per finding in the user log "FO4SFCogDoor" (My Games\Starfield\Logs\Script\User\FO4SFCogDoor.0.log):
; FO4SFDOOR rt=<real time s> <event> key=value ... end=true. Every finding also shows on screen as a notification beginning "AP ".

; ---------------------------------------------------------------- the layout (dotnet/CogDoorProbe/Program.cs)

int Version = 1
string LogName = "FO4SFCogDoor"
string ProbePlugin = "FO4SFCogDoor.esm"
string RefPlugin = "FO4Port.esm"
int RefId = 0  ;REF the cog door reference's local id in FO4Port.esm (the stager writes it; 0 = not given)
float PollS = 2.0
float WatchS = 60.0

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_WATCH = 2
int[] StageList
bool[] DoneList
int WatchStage = 0          ; the stage whose watch is open, 0 = none
float WatchStartRt = 0.0
int LastState = -99

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[5]
    DoneList = new bool[5]
    StageList[0] = 10
    StageList[1] = 20
    StageList[2] = 30
    StageList[3] = 40
    StageList[4] = 50
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " refid=" + RefId + " refplugin=" + Game.IsPluginInstalled(RefPlugin) + " ref=" + Id(DoorRef()))
    StartTimer(1.0, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {A user log is open only in the game session that opened it (assumed): when a write fails, as after a save is loaded again, the log is opened once more and the line written again. Every line ends with end=true.}
    string line = "FO4SFDOOR rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    {The on-screen twin of a log line, for a session with script logging off.}
    Debug.Notification("AP " + msg)
EndFunction

string Function Id(Form f)
    {"<signed decimal form id>" or "none".}
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

ObjectReference Function DoorRef()
    {The cog door reference, or None when RefId is 0 or the reference does not resolve.}
    if RefId == 0
        return None
    endif
    return Game.GetFormFromFile(RefId, RefPlugin) as ObjectReference
EndFunction

; ---------------------------------------------------------------- stages

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(1.0, TIMER_POLL)
    elseif aiTimerID == TIMER_WATCH
        Watch()
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
    ObjectReference d = DoorRef()
    if d == None
        Trace("stage=" + stage + " ref=none refid=" + RefId + " (stage the kit so RefId is set, and load FO4Port.esm)")
        Say("S" + stage + " ref=none")
        return
    endif
    if stage == 10 || stage == 50
        Reading("read", stage, d)
    elseif stage == 20
        d.SetOpen(true)
        Trace("setopen stage=" + stage + " value=true")
        Reading("after", stage, d)
        BeginWatch(stage, d)
    elseif stage == 30
        d.SetOpen(false)
        Trace("setopen stage=" + stage + " value=false")
        Reading("after", stage, d)
        BeginWatch(stage, d)
    elseif stage == 40
        Actor p = Game.GetPlayer()
        d.Activate(p, false)
        Trace("activate stage=" + stage + " by=player")
        Reading("after", stage, d)
        BeginWatch(stage, d)
    endif
EndFunction

Function Reading(string when, int stage, ObjectReference d)
    int state = d.GetOpenState()
    Actor p = Game.GetPlayer()
    Trace("read stage=" + stage + " when=" + when + " ref=" + Id(d) + " base=" + Id(d.GetBaseObject()) + " loaded=" + d.Is3DLoaded() + " openstate=" + state + " cell=" + Id(d.GetParentCell()) + " pos=" + d.GetPositionX() + "," + d.GetPositionY() + "," + d.GetPositionZ() + " dist=" + p.GetDistance(d))
    Say("S" + stage + " " + when + " state=" + state + " 3d=" + d.Is3DLoaded() + " dist=" + p.GetDistance(d))
EndFunction

Function BeginWatch(int stage, ObjectReference d)
    WatchStage = stage
    WatchStartRt = Utility.GetCurrentRealTime()
    LastState = d.GetOpenState()
    StartTimer(PollS, TIMER_WATCH)
EndFunction

Function Watch()
    ObjectReference d = DoorRef()
    if d == None || WatchStage == 0
        return
    endif
    float after = Utility.GetCurrentRealTime() - WatchStartRt
    int state = d.GetOpenState()
    string changed = ""
    if state != LastState
        changed = " changed=true from=" + LastState
        LastState = state
        Say("S" + WatchStage + " t" + after + " state=" + state)
    endif
    Trace("watch stage=" + WatchStage + " after=" + after + " openstate=" + state + changed)
    if after >= WatchS
        Trace("watch done stage=" + WatchStage + " seconds=" + after + " openstate=" + state)
        Say("S" + WatchStage + " watch done state=" + state)
        WatchStage = 0
    else
        StartTimer(PollS, TIMER_WATCH)
    endif
EndFunction
