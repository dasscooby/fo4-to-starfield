Scriptname FO4SF_PlayerFurnQuest extends Quest
{The player-furniture control kit, variant P (fo4-to-starfield, docs/research/player-furniture-kit.md, FAL-518; design: the Scribe's
 document vault111-player-furniture rev 6, section 4). Attached to QUST FO4SF_PlayerFurnQuest (0x800 of FO4SFPlayerFurn.esm): start game
 enabled, stages set from the console, NO properties (every form is found with Game.GetFormFromFile at the moment it is read; a property
 would make a temporary reference persistent).
 The question: does Activate(player) on a SPAWNED copy of a vanilla play-once furniture put the player into its pose, and what ends it
 (which events arrive in Papyrus, at what time)? Four vanilla FURN of Starfield.esm, in the design's order: PowerCycle 03607F,
 COM_Quest_Andreja_Q01_SecretPanel 0FEBB0, NPCIDCardReader 00A329, Scenes_MQ101_HellerTechReaderPickUp 24E491. Nothing of ours is attached
 to them, no override, no FO4Port master. The script polls the stages once a second:
   10..13  PlaceAtMe one furniture (10 PowerCycle, 11 SecretPanel, 12 NPCIDCardReader, 13 HellerTechReaderPickUp), persistent, 2.5 m in front
           of the player, at the player's height, upright, turned to face the player; notice with 3D loaded and distance
   20..23  USE that furniture (20 for the one spawned by 10, 21 for 11, ...): the 15 s guard timer first, then an InputEnableLayer and
           DisablePlayerControls(), then furniture.Activate(player) as the game's own SBPowerCollectionActivatorScript does; then 15 s of
           logging with times. One furniture at a time: set the next use stage after the SAFE (or EXIT OK / STILL IN) notice of the last one
   40      a reading of every spawned reference now
   60      release the layer, Disable and Delete every spawned reference
 Guards against stranding the player (all required): (1) the 15 s timer started BEFORE the layer exists releases the layer whatever
 happened; (2) if GetSitState is not 0 at 15 s the furniture is activated once more (the game's own way out, MQ101Script) and a notice
 says so; 3 s later a player still not at 0 gets the furniture Disabled; (3) stage 60 releases the layer and deletes every spawned reference;
 the layer is also released at once on Actor.OnGetUp / ObjectReference.OnExitFurniture. NEVER the wait form of PlayAnimation (no PlayAnimation
 at all: the player clip is the furniture's own), no SnapIntoInteraction, no PlayerPathToFurniture, no FurnitureForce1stPerson stamped.
 Every line that matters also shows as a short on-screen notification beginning "PF " (Say), because script logging is off on the PC.
 Optional natives are lines that begin with ";OPT <Base.Name> ": scripts/newgame/make_player_furn.py stage compiles each on its own and keeps
 the ones that compile (the event handlers are optional lines named after their event). ";VOID " lines are the register call's second shape.
 One line per finding in the user log "FO4SFPFurn" (My Games/Starfield/Logs/Script/User/FO4SFPFurn.0.log): FO4SFPFURN rt=<real time s> <event>
 key=value ... end=true (form ids as Papyrus prints them: signed decimal, "none" for None). t= is seconds since the use began.}

; ---------------------------------------------------------------- the layout (dotnet/PlayerFurn/Program.cs)

int Version = 1
string LogName = "FO4SFPFurn"
string ProbePlugin = "FO4SFPlayerFurn.esm"
float AheadM = 2.5

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_SAFETY = 200      ; + the furniture index 0..3
int TIMER_SIT = 210         ; + the furniture index
int TIMER_RECHECK = 220     ; + the furniture index
float POLL_S = 1.0
float GUARD_S = 15.0
float SIT_S = 0.5
float RECHECK_S = 3.0
int SIT_TICKS = 30          ; 30 x 0.5 s = 15 s of GetSitState lines
int[] StageList
bool[] DoneList
int[] FurnIds
string[] FurnNames
string[] AnimNames
ObjectReference[] Spawned
InputEnableLayer Hold = None
ObjectReference FurnRef = None
bool UseOpen = false        ; a use began and its 15 s guard has not closed it yet
bool AnimRegistered = false
bool Inside = false         ; only logged: set by the sit / enter events, cleared by the get up / exit events
bool ScaleKnown = false
float SavedScale = 1.0
float UseStartRt = 0.0
int CurIdx = -1
int SitTicks = 0
int LastSit = -1

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[10]
    DoneList = new bool[10]
    StageList[0] = 10
    StageList[1] = 11
    StageList[2] = 12
    StageList[3] = 13
    StageList[4] = 20
    StageList[5] = 21
    StageList[6] = 22
    StageList[7] = 23
    StageList[8] = 40
    StageList[9] = 60
    FurnIds = new int[4]
    FurnIds[0] = 0x03607F       ; FURN PowerCycle
    FurnIds[1] = 0x0FEBB0       ; FURN COM_Quest_Andreja_Q01_SecretPanel
    FurnIds[2] = 0x00A329       ; FURN NPCIDCardReader
    FurnIds[3] = 0x24E491       ; FURN Scenes_MQ101_HellerTechReaderPickUp
    FurnNames = new string[4]
    FurnNames[0] = "PowerCycle"
    FurnNames[1] = "SecretPanel"
    FurnNames[2] = "IDCardReader"
    FurnNames[3] = "HellerTechReader"
    AnimNames = new string[10]
    AnimNames[0] = "IdleChairSitting"
    AnimNames[1] = "AnimationComplete"
    AnimNames[2] = "IdleStop"
    AnimNames[3] = "pipboyIdleRoot"     ; the Fallout 4 names: logged to see that they do NOT arrive
    AnimNames[4] = "On"
    AnimNames[5] = "Play01"
    AnimNames[6] = "Off"
    AnimNames[7] = "Done"
    AnimNames[8] = "Trans01"
    AnimNames[9] = "AnimFinish"
    Spawned = new ObjectReference[4]
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " furn=" + FurnIds.Length + " anim=" + AnimNames.Length)
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {A user log is open only in the game session that opened it (assumed): when a write fails, as after a save is loaded
     again, the log is opened once more and the line written again. Every line ends with end=true.}
    string line = "FO4SFPFURN rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    {The on-screen twin of a log line (script logging is off on the PC): a short Debug.Notification the person at the keyboard can
     read. Prefix "PF ". Seconds t= are since the use began.}
    Debug.Notification("PF " + msg)
EndFunction

string Function Id(Form f)
    {"<signed decimal form id>" or "none".}
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

float Function SinceUse()
    return Utility.GetCurrentRealTime() - UseStartRt
EndFunction

; ---------------------------------------------------------------- the events

Event OnAnimationEvent(ObjectReference akSource, string asEventName)
    Trace("event name=" + asEventName + " src=" + Id(akSource) + " use=" + CurIdx + " t=" + SinceUse())
    Say("EV " + asEventName + " t=" + SinceUse())
EndEvent

;OPT Actor.OnGetUp Event Actor.OnGetUp(Actor akSender, ObjectReference akFurniture)
;OPT Actor.OnGetUp     Inside = false
;OPT Actor.OnGetUp     Trace("event name=OnGetUp furn=" + Id(akFurniture) + " use=" + CurIdx + " t=" + SinceUse())
;OPT Actor.OnGetUp     Say("GETUP t=" + SinceUse())
;OPT Actor.OnGetUp     EndUse("getup")
;OPT Actor.OnGetUp EndEvent

;OPT Actor.OnSit Event Actor.OnSit(Actor akSender, ObjectReference akFurniture)
;OPT Actor.OnSit     Inside = true
;OPT Actor.OnSit     Trace("event name=OnSit furn=" + Id(akFurniture) + " use=" + CurIdx + " t=" + SinceUse())
;OPT Actor.OnSit     Say("SIT t=" + SinceUse())
;OPT Actor.OnSit EndEvent

;OPT ObjectReference.OnEnterFurniture Event ObjectReference.OnEnterFurniture(ObjectReference akSender, ObjectReference akActionRef)
;OPT ObjectReference.OnEnterFurniture     Inside = true
;OPT ObjectReference.OnEnterFurniture     Trace("event name=OnEnterFurniture furn=" + Id(akSender) + " actor=" + Id(akActionRef) + " use=" + CurIdx + " t=" + SinceUse())
;OPT ObjectReference.OnEnterFurniture     Say("ENTER t=" + SinceUse())
;OPT ObjectReference.OnEnterFurniture EndEvent

;OPT ObjectReference.OnExitFurniture Event ObjectReference.OnExitFurniture(ObjectReference akSender, ObjectReference akActionRef)
;OPT ObjectReference.OnExitFurniture     Inside = false
;OPT ObjectReference.OnExitFurniture     Trace("event name=OnExitFurniture furn=" + Id(akSender) + " actor=" + Id(akActionRef) + " use=" + CurIdx + " t=" + SinceUse())
;OPT ObjectReference.OnExitFurniture     Say("EXIT t=" + SinceUse())
;OPT ObjectReference.OnExitFurniture     EndUse("exit")
;OPT ObjectReference.OnExitFurniture EndEvent

string Function Reg(ObjectReference r, string n)
    {The register call's return as text, "true" / "false". When the game's script declares no return value the stager drops the
     return line and keeps the ";VOID " lines (the log then says ok=void).}
    return "" + RegisterForAnimationEvent(r, n)
;VOID     RegisterForAnimationEvent(r, n)
;VOID     return "void"
EndFunction

Function RegisterAnim(Actor p)
    {Each of the player's animation names, one line with the call's return; one notice with the count that returned true.}
    int i = 0
    int okCount = 0
    while i < AnimNames.Length
        string res = Reg(p, AnimNames[i])
        Trace("register name=" + AnimNames[i] + " ref=player ok=" + res)
        if res == "true"
            okCount += 1
        endif
        i += 1
    endwhile
    AnimRegistered = true
    Say("REG " + okCount + "/" + AnimNames.Length + " true")
EndFunction

; ---------------------------------------------------------------- readings and spawning

Function Reading(string when, int stage, int idx)
    {One line: the reference, its base, 3D, disabled state, position and distance to the player, height difference and both headings.}
    ObjectReference r = Spawned[idx]
    if r == None
        Trace("read stage=" + stage + " when=" + when + " name=" + FurnNames[idx] + " ref=none")
        return
    endif
    Actor p = Game.GetPlayer()
    Trace("read stage=" + stage + " when=" + when + " name=" + FurnNames[idx] + " ref=" + Id(r) + " base=" + Id(r.GetBaseObject()) + " loaded=" + r.Is3DLoaded() + " disabled=" + r.IsDisabled() + " pos=" + r.GetPositionX() + "," + r.GetPositionY() + "," + r.GetPositionZ() + " dist=" + p.GetDistance(r) + " dz=" + (r.GetPositionZ() - p.GetPositionZ()) + " furnang=" + r.GetAngleZ() + " playerang=" + p.GetAngleZ() + " sit=" + p.GetSitState())
EndFunction

Function Spawn(int stage, int idx)
    {PlaceAtMe the vanilla furniture (persistent), then 2.5 m in front of the player at the player's height when MoveTo exists
     (z offset 0), turned to face the player (upright: pitch and roll 0) when SetAngle exists. Never at the player's feet.}
    Actor p = Game.GetPlayer()
    Form base = Game.GetFormFromFile(FurnIds[idx], "Starfield.esm")
    if base == None
        Trace("spawn stage=" + stage + " name=" + FurnNames[idx] + " base=none ref=none")
        Say("S" + stage + " " + FurnNames[idx] + " no base")
        return
    endif
    ObjectReference r = p.PlaceAtMe(base, 1, true, false, false)
    Spawned[idx] = r
    bool moved = false
    bool turned = false
;OPT ObjectReference.MoveTo     if r
;OPT ObjectReference.MoveTo         float a = p.GetAngleZ()
;OPT ObjectReference.MoveTo         r.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo         moved = true
;OPT ObjectReference.MoveTo     endif
;OPT ObjectReference.SetAngle     if r
;OPT ObjectReference.SetAngle         r.SetAngle(0.0, 0.0, p.GetAngleZ() + 180.0)
;OPT ObjectReference.SetAngle         turned = true
;OPT ObjectReference.SetAngle     endif
    Trace("spawn stage=" + stage + " name=" + FurnNames[idx] + " base=" + Id(base) + " ref=" + Id(r) + " moved=" + moved + " turned=" + turned + " persist=true")
    Reading("now", stage, idx)
    if r
        Say("S" + stage + " " + FurnNames[idx] + " 3D=" + r.Is3DLoaded() + " D=" + p.GetDistance(r))
    else
        Say("S" + stage + " " + FurnNames[idx] + " no ref")
    endif
EndFunction

; ---------------------------------------------------------------- poll and steps

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID >= TIMER_RECHECK
        Recheck(aiTimerID - TIMER_RECHECK)
    elseif aiTimerID >= TIMER_SIT
        SitTick(aiTimerID - TIMER_SIT)
    elseif aiTimerID >= TIMER_SAFETY
        Guard(aiTimerID - TIMER_SAFETY)
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
    if stage >= 10 && stage <= 13
        Spawn(stage, stage - 10)
    elseif stage >= 20 && stage <= 23
        UseFurniture(stage, stage - 20)
    elseif stage == 40
        ReadAll(stage)
    elseif stage == 60
        Cleanup()
    endif
EndFunction

Function ReadAll(int stage)
    int i = 0
    while i < Spawned.Length
        Reading("stage40", stage, i)
        i += 1
    endwhile
    Say("S" + stage + " read, see the log")
EndFunction

; ---------------------------------------------------------------- the use and its guards

Function UseFurniture(int stage, int idx)
    {The guard timer FIRST, then the layer, then Activate(player). Never waits on E, never plays an animation.}
    if UseOpen
        Trace("use stage=" + stage + " name=" + FurnNames[idx] + " busy=true open=" + CurIdx)
        Say("U" + stage + " BUSY: wait for SAFE")
        return
    endif
    ObjectReference r = Spawned[idx]
    if r == None
        Trace("use stage=" + stage + " name=" + FurnNames[idx] + " ref=none (set " + (stage - 10) + " first)")
        Say("U" + stage + " no ref: set " + (stage - 10) + " first")
        return
    endif
    Actor p = Game.GetPlayer()
    UseOpen = true
    CurIdx = idx
    FurnRef = r
    Inside = false
    SitTicks = 0
    LastSit = -1
    UseStartRt = Utility.GetCurrentRealTime()
    StartTimer(GUARD_S, TIMER_SAFETY + idx)            ; the safety, started before anything that can strand the player
    StartTimer(SIT_S, TIMER_SIT + idx)
    Trace("use stage=" + stage + " name=" + FurnNames[idx] + " guard=" + GUARD_S + " sit0=" + p.GetSitState())
    if !AnimRegistered
        RegisterAnim(p)
    endif
    RegisterForRemoteEvent(p, "OnGetUp")
    RegisterForRemoteEvent(p, "OnSit")
    RegisterForRemoteEvent(r, "OnEnterFurniture")
    RegisterForRemoteEvent(r, "OnExitFurniture")
    Reading("before", stage, idx)
    SaveScale(p)
    Say("U" + stage + " " + FurnNames[idx] + " 3D=" + r.Is3DLoaded() + " D=" + p.GetDistance(r))
    Hold = InputEnableLayer.Create()
    Hold.DisablePlayerControls()
    Trace("layer created=" + (Hold != None))
    r.Activate(p, false)                               ; "put player in furniture" (SBPowerCollectionActivatorScript)
    Trace("step stage=" + stage + " call=Activate name=" + FurnNames[idx] + " ref=" + Id(r) + " t=" + SinceUse())
    Say("ACTIVATE s" + stage)
EndFunction

Function SitTick(int idx)
    {GetSitState every 0.5 s for 15 s: a one-shot use may never reach state 3, and that is a result.}
    if idx != CurIdx || SitTicks >= SIT_TICKS
        return
    endif
    SitTicks += 1
    int s = Game.GetPlayer().GetSitState()
    Trace("sit use=" + idx + " n=" + SitTicks + " state=" + s + " inside=" + Inside + " t=" + SinceUse())
    if s != LastSit
        Say("SIT STATE " + s + " t=" + SinceUse())
        LastSit = s
    endif
    if SitTicks < SIT_TICKS
        StartTimer(SIT_S, TIMER_SIT + idx)
    endif
EndFunction

Function ReleaseHold(string why)
    {Enable the controls and delete the layer; nothing happens when there is none (the call is safe to repeat).}
    if Hold != None
        Hold.EnablePlayerControls()
        Hold.Delete()
        Hold = None
        Trace("hold released why=" + why + " t=" + SinceUse())
        Say("HOLD OFF " + why)
    else
        Trace("hold none why=" + why)
    endif
EndFunction

Function SaveScale(Actor p)
    {The player's scale before the use (FurnitureScaleActorToOne is on two of the four: the secret panel and the ID reader): restored when the use ends.}
    SavedScale = 1.0
    ScaleKnown = false
;OPT ObjectReference.GetScale     SavedScale = p.GetScale()
;OPT ObjectReference.GetScale     ScaleKnown = true
EndFunction

Function RestoreScale(Actor p)
;OPT ObjectReference.SetScale     if ScaleKnown && p.GetScale() != SavedScale
;OPT ObjectReference.SetScale         p.SetScale(SavedScale)
;OPT ObjectReference.SetScale         Trace("scale restored to " + SavedScale)
;OPT ObjectReference.SetScale     endif
EndFunction

Function EndUse(string why)
    {The furniture's own end (Actor.OnGetUp or ObjectReference.OnExitFurniture): controls back at once, layer deleted. The guard
     timer still runs to its end (and logs); the spawned reference stays until stage 60.}
    ReleaseHold(why)
    RestoreScale(Game.GetPlayer())
    Trace("end why=" + why + " use=" + CurIdx + " t=" + SinceUse())
EndFunction

Function Guard(int idx)
    {15 s after the use began, whatever happened: layer released; a player still not at sit state 0 gets Activate once more (the
     game's own way out, MQ101Script) and the recheck follows.}
    if idx != CurIdx
        return
    endif
    Actor p = Game.GetPlayer()
    int s = p.GetSitState()
    Trace("guard use=" + idx + " name=" + FurnNames[idx] + " sit=" + s + " inside=" + Inside + " hold=" + (Hold != None) + " t=" + SinceUse())
    ReleaseHold("timer")
    RestoreScale(p)
    if s != 0 && FurnRef != None
        FurnRef.Activate(p, false)
        Trace("exit activate use=" + idx + " sit=" + s)
        Say("EXIT ACTIVATE sit=" + s)
        StartTimer(RECHECK_S, TIMER_RECHECK + idx)
    else
        Say("SAFE sit=" + s)
        UseOpen = false
    endif
EndFunction

Function Recheck(int idx)
    {3 s after the exit Activate: a player still not at sit state 0 gets the furniture disabled (often lets go of the actor).}
    if idx != CurIdx
        return
    endif
    int s = Game.GetPlayer().GetSitState()
    Trace("recheck use=" + idx + " sit=" + s + " inside=" + Inside + " t=" + SinceUse())
    if s != 0 && FurnRef != None
        FurnRef.Disable(false)
        Trace("furniture disabled use=" + idx)
        Say("STILL IN sit=" + s + ": FURN DISABLED")
    else
        Say("EXIT OK sit=" + s)
    endif
    UseOpen = false
EndFunction

Function Cleanup()
    {Stage 60: the layer released and every spawned reference disabled and (when Delete exists) deleted.}
    Trace("cleanup")
    ReleaseHold("stage60")
    RestoreScale(Game.GetPlayer())
    int i = 0
    while i < Spawned.Length
        if Spawned[i]
            Spawned[i].Disable(false)
;OPT ObjectReference.Delete             Spawned[i].Delete()
            Spawned[i] = None
        endif
        i += 1
    endwhile
    FurnRef = None
    UseOpen = false
    Say("CLEAN")
EndFunction
