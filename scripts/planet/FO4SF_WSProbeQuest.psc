Scriptname FO4SF_WSProbeQuest extends Quest
{The workshop probe (fo4-to-starfield, docs/research/workshop-probe.md). Attached to QUST FO4SF_WSProbeQuest (0x800 of
 FO4SFWorkshopProbe.esm): start game enabled, stages set from the console, NO properties (every form is found with
 Game.GetFormFromFile at the moment it is read; a property would make a temporary reference persistent).
 The question: the PC run of 11 Nov found that a workshop placed in the core's cell (Red Rocket garage bench) opens
 Starfield's build mode on E and a bench spawned by player.placeatme does not. This finds what makes a spawned bench a
 workshop, one call at a time. The script polls the stages once a second:
   10  PlaceAtMe of the core's workshop base 2.5 m in front of the player, persistent (the BENCH)
   20  log which sub-stages follow (nothing is called)
   21 22 23 24  on the BENCH, one call each: 21 Disable + Enable, 22 Activate(player) by script, 23 SetActorOwner(player base)
               (optional), 24 StartWorkshop (optional)
   30  PlaceAtMe of the vanilla OutpostPlayerHouseActivator 0x024DC7 in front of the player (the PAD, the control: the
       invisible activator the game itself places)
   31 32 33 34 the same four calls on the PAD
   40  PlaceAtMe of the vanilla outpost beacon base whose id the stager was given (--beacon); 0 = not given, it says so
   50  a reading of every spawned reference now (the trip out of the cell and back: the poll also writes one on its own
       whenever the player's cell changes, then again 2 s and 10 s later)
   60  Disable and Delete every spawned reference
 Each stage 10 / 21..24 / 30 / 31..34 / 40 writes the reading BEFORE, the call, the reading AFTER and the reading 4 s
 later: so the log says which call changed anything. The owner presses E on the object after each stage (the PC does it by
 script) and looks at the prompt: that is not readable by Papyrus, so it is the screenshot.
 Optional readings and calls are lines that begin with ";OPT <Base.Name> ": scripts/planet/make_workshop_probe.py stage
 compiles each on its own and keeps the ones that compile (a name the base scripts do not declare logs na). As committed
 none is on: this file compiles alone. One line per finding in the user log "FO4SFWorkshop" (My Games\\Starfield\\Logs\\
 Script\\User\\FO4SFWorkshop.0.log): FO4SFWS rt=<real time s> <event> key=value ... end=true (form ids as Papyrus prints
 them: signed decimal, "none" for None).}

; ---------------------------------------------------------------- the layout (dotnet/WorkshopProbe/Program.cs)

int Version = 1
string LogName = "FO4SFWorkshop"
string ProbePlugin = "FO4SFWorkshopProbe.esm"
string CorePlugin = "FO4TerrainCore.esm"          ; the installed core; FO4TerrainCore_Mars.esm is tried when this one is absent
string CorePlugin2 = "FO4TerrainCore_Mars.esm"
int BenchBaseId = 0x0A2ECD  ; the core's workshop base FO4Core_wkshp_0c1aeb_fallout4 (local id, as the 11 Nov PC run read it)
int WorkshopKwId = 0x054BA7 ; WorkshopKeyword (Fallout 4's id; carried into the core, to be read: the log says none when it is not there)
int PadBaseId = 0x024DC7    ; Starfield.esm OutpostPlayerHouseActivator
int BeaconId = 0            ;BEACON stager substitutes the vanilla outpost beacon base id (--beacon); 0 = none
float AheadM = 2.5

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_SETTLE = 100      ; + the stage
int TIMER_ARRIVE2 = 90
int TIMER_ARRIVE10 = 91
float POLL_S = 1.0
float SETTLE_S = 4.0
int[] StageList
bool[] DoneList
ObjectReference BenchRef = None
ObjectReference PadRef = None
ObjectReference BeaconRef = None
Cell LastCell = None
Form BenchBase = None
bool CoreFound = false

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
    StageList[6] = 30
    StageList[7] = 31
    StageList[8] = 32
    StageList[9] = 33
    StageList[10] = 34
    StageList[11] = 40
    StageList[12] = 50
    BenchBase = FindBase()
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " core=" + CoreName() + " benchbase=" + Id(BenchBase) + " workshopkw=" + Id(Game.GetFormFromFile(WorkshopKwId, CoreName())) + " padbase=" + Id(Game.GetFormFromFile(PadBaseId, "Starfield.esm")) + " beaconid=" + BeaconId)
    LastCell = Game.GetPlayer().GetParentCell()
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {A user log is open only in the game session that opened it (assumed): when a write fails, as after a save is loaded
     again, the log is opened once more and the line written again. Every line ends with end=true.}
    string line = "FO4SFWS rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
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

string Function CoreName()
    if Game.IsPluginInstalled(CorePlugin)
        return CorePlugin
    endif
    return CorePlugin2
EndFunction

Form Function FindBase()
    return Game.GetFormFromFile(BenchBaseId, CoreName())
EndFunction

; ---------------------------------------------------------------- readings ("na" = the game has no such call)

string Function HasWorkshopKw(ObjectReference r)
    Form kw = Game.GetFormFromFile(WorkshopKwId, CoreName())
    Keyword k = kw as Keyword
    if k == None || r == None
        return "na"
    endif
    return "" + r.HasKeyword(k)
EndFunction

string Function WsReading(ObjectReference r)
    string s = "na"
;OPT ObjectReference.IsWorkshop     s = "" + r.IsWorkshop()
    return s
EndFunction

Function Reading(string when, int stage, string what, ObjectReference r)
    {One line: the reference, its base, 3D, keyword, disabled state, cell, position and distance to the player.}
    if r == None
        Trace("read stage=" + stage + " when=" + when + " what=" + what + " ref=none")
        return
    endif
    Actor p = Game.GetPlayer()
    Trace("read stage=" + stage + " when=" + when + " what=" + what + " ref=" + Id(r) + " base=" + Id(r.GetBaseObject()) + " loaded=" + r.Is3DLoaded() + " haskw=" + HasWorkshopKw(r) + " disabled=" + r.IsDisabled() + " ws=" + WsReading(r) + " cell=" + Id(r.GetParentCell()) + " pos=" + r.GetPositionX() + "," + r.GetPositionY() + "," + r.GetPositionZ() + " dist=" + p.GetDistance(r))
EndFunction

; ---------------------------------------------------------------- spawning

ObjectReference Function Spawn(Form base, string what, int stage)
    {PlaceAtMe the base, persistent, then 2.5 m in front of the player (MoveTo is optional: without it the object stands at the player).}
    Actor p = Game.GetPlayer()
    if base == None
        Trace("spawn stage=" + stage + " what=" + what + " base=none ref=none")
        return None
    endif
    ObjectReference r = p.PlaceAtMe(base, 1, true, false, false)
    bool moved = false
;OPT ObjectReference.MoveTo     if r
;OPT ObjectReference.MoveTo         float a = p.GetAngleZ()
;OPT ObjectReference.MoveTo         r.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo         moved = true
;OPT ObjectReference.MoveTo     endif
    Trace("spawn stage=" + stage + " what=" + what + " base=" + Id(base) + " ref=" + Id(r) + " moved=" + moved)
    Reading("now", stage, what, r)
    StartTimer(SETTLE_S, TIMER_SETTLE + stage)
    return r
EndFunction

; ---------------------------------------------------------------- poll and steps

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_ARRIVE2
        ReadAll("arrival+2s", 0)
    elseif aiTimerID == TIMER_ARRIVE10
        ReadAll("arrival+10s", 0)
    elseif aiTimerID >= TIMER_SETTLE
        int stage = aiTimerID - TIMER_SETTLE
        if stage == 10 || (stage >= 20 && stage < 30)
            Reading("settled", stage, "bench", BenchRef)
        elseif stage == 30 || (stage >= 30 && stage < 40)
            Reading("settled", stage, "pad", PadRef)
        elseif stage == 40
            Reading("settled", stage, "beacon", BeaconRef)
        endif
    endif
EndEvent

Function ReadAll(string when, int stage)
    Reading(when, stage, "bench", BenchRef)
    Reading(when, stage, "pad", PadRef)
    Reading(when, stage, "beacon", BeaconRef)
EndFunction

Function Poll()
    Cell c = Game.GetPlayer().GetParentCell()
    if c != LastCell
        LastCell = c
        Trace("cell now=" + Id(c))
        ReadAll("arrival", 0)
        StartTimer(2.0, TIMER_ARRIVE2)
        StartTimer(10.0, TIMER_ARRIVE10)
    endif
    int i = 0
    while i < StageList.Length
        if !DoneList[i] && GetStageDone(StageList[i])
            DoneList[i] = true
            Step(StageList[i])
        endif
        i += 1
    endwhile
    if GetStageDone(60) && (BenchRef != None || PadRef != None || BeaconRef != None)
        Cleanup()
    endif
EndFunction

Function Step(int stage)
    Actor p = Game.GetPlayer()
    if stage == 10
        BenchRef = Spawn(FindBase(), "bench", stage)
    elseif stage == 20
        Trace("step stage=20 calls=21:DisableEnable 22:Activate 23:SetActorOwner(opt) 24:StartWorkshop(opt) bench=" + Id(BenchRef) + " pad=" + Id(PadRef))
    elseif stage > 20 && stage < 30
        DoCall(stage - 20, stage, "bench", BenchRef)
    elseif stage == 30
        PadRef = Spawn(Game.GetFormFromFile(PadBaseId, "Starfield.esm"), "pad", stage)
    elseif stage > 30 && stage < 40
        DoCall(stage - 30, stage, "pad", PadRef)
    elseif stage == 40
        if BeaconId == 0
            Trace("step stage=40 beacon=not given (stage with --beacon <hex id of the vanilla outpost beacon base>)")
        else
            BeaconRef = Spawn(Game.GetFormFromFile(BeaconId, "Starfield.esm"), "beacon", stage)
        endif
    elseif stage == 50
        ReadAll("stage50", 50)
    endif
EndFunction

Function DoCall(int k, int stage, string what, ObjectReference r)
    {The k-th call on the reference: 1 Disable + Enable, 2 Activate by the player, 3 SetActorOwner (optional), 4 StartWorkshop (optional).}
    Actor p = Game.GetPlayer()
    if r == None
        Trace("step stage=" + stage + " call=" + k + " what=" + what + " ref=none (place it first)")
        return
    endif
    Reading("before", stage, what, r)
    string call = "na"
    if k == 1
        call = "DisableEnable"
        r.Disable(false)
        r.Enable(false)
    elseif k == 2
        call = "Activate"
        r.Activate(p, false)
    elseif k == 3
;OPT ObjectReference.SetActorOwner         call = "SetActorOwner"
;OPT ObjectReference.SetActorOwner         r.SetActorOwner(p.GetActorBase())
    elseif k == 4
;OPT ObjectReference.StartWorkshop         call = "StartWorkshop"
;OPT ObjectReference.StartWorkshop         r.StartWorkshop(true)
    endif
    Trace("step stage=" + stage + " call=" + k + " name=" + call + " what=" + what + " ref=" + Id(r))
    Reading("after", stage, what, r)
    StartTimer(SETTLE_S, TIMER_SETTLE + stage)
EndFunction

Function Cleanup()
    Trace("cleanup bench=" + Id(BenchRef) + " pad=" + Id(PadRef) + " beacon=" + Id(BeaconRef))
    Dispose(BenchRef)
    Dispose(PadRef)
    Dispose(BeaconRef)
    BenchRef = None
    PadRef = None
    BeaconRef = None
EndFunction

Function Dispose(ObjectReference r)
    if r
        r.Disable(false)
;OPT ObjectReference.Delete         r.Delete()
    endif
EndFunction
