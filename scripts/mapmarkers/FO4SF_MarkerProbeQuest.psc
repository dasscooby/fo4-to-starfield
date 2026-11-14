Scriptname FO4SF_MarkerProbeQuest extends Quest
{The map marker probe (fo4-to-starfield, FAL-771 / FAL-489): attached to QUST FO4SF_MarkerProbeQuest, stages set from the console. The full description follows as ; comments.}
; The question (FAL-489 note sections 34 and 36): can the new-game exit do its map work while the player is still inside the vault cell, and
; what does Starfield offer once the first location is discovered? Nothing here is installed by a normal run; this is a session kit.
; The owner's words (14 Nov): fast travel unlocks when the first location is discovered. Every stage therefore reads Game.IsFastTravelEnabled.
; There is NO getter for "this marker is discovered" (PC read of 5,033 Starfield sources, comment d68a0c70): the reads are the proxies
; IsMapMarkerVisible and CanFastTravelToMarker, the world and position of each reference, and the player's own. What the proxies do on
; discovery is itself the measurement. The marker's own screen state (map, planet map) is read by the PC's eye and shots.
;
; The references (all found with Game.GetFormFromFile at the moment of use; the quest has NO properties: a property would make a temporary
; reference persistent), file-local ids as the plugins store them:
;   V111  FO4TerrainCore.esm 0x0A775B  the Vault 111 map marker AND the new-game exit anchor (ExitAnchorId, the same reference)
;   LAND  FO4SFMapMarkers.esm 0x0008F2 the landing marker (undiscovered only in a plugin built with --landing-undiscovered, PR 781)
;   TEST  FO4SFMapMarkers.esm 0x000900 the first plain marker of the plugin (not Vault 111), moved in stage 20
;   TEST2 FO4SFMapMarkers.esm 0x000901 the second plain marker, used by stage 70 only
; The stages (set one at a time, after the last stage's "later done" line; the console is closed between them):
; 10      baseline: read V111, LAND, TEST, TEST2 and the player; nothing changes. Stand INSIDE the vault (lift cell) for 10 to 30.
; 20      indoor placement, the one engine fact: TEST.MoveTo(V111) (the exit's own call and anchor), read; then SetPosition to the merged
;         spot (its own position before the move plus MergeX / MergeY), read at once and 2 s later. A refusal or the old world = shape A.
; 30      indoor discovery: V111.SetMarkerDiscovered() while the player is inside; read V111 and fast travel before, at once, 2 s later.
; 40      outside: the PC has gone to the Commonwealth by its normal means (coc to an exterior spot); read the four references, the player
;         and fast travel (the moved marker's world against the player's; V111's proxies). Then look at the surface map and Mars's planet map.
; 50      persistence: after a save, a quit to the menu and a load, the same reads as 40, and the same look.
; 60      landing (a build with --landing-undiscovered): read LAND, LAND.SetMarkerDiscovered(), read at once and 2 s later (the owner's
;         "first location" moment: does fast travel, a label or a landing target appear).
; 70      the variant: TEST2.AddToMap(false) instead of SetMarkerDiscovered (nothing can undo Discovered, so a different marker), read the same.
; One line per finding in the user log "FO4SFMarkerProbe" (My Games\Starfield\Logs\Script\User\FO4SFMarkerProbe.0.log):
; FO4SFMARK rt=<real time s> <event> key=value ... end=true. Every finding also shows on screen as a notification beginning "AP ".

; ---------------------------------------------------------------- the layout (dotnet/MarkerProbe/Program.cs)

int Version = 1
string LogName = "FO4SFMarkerProbe"
string ProbePlugin = "FO4SFMarkerProbe.esm"
string CorePlugin = "FO4TerrainCore.esm"
string MarkPlugin = "FO4SFMapMarkers.esm"
int V111Id = 0x0A775B
int LandId = 0x0008F2
int TestId = 0x000900
int Test2Id = 0x000901
float MergeX = -1200.0
float MergeY = -2700.0
float LaterS = 2.0

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_LATER = 2
int[] StageList
bool[] DoneList
int LaterStage = 0          ; the stage whose 2 s re-read is pending, 0 = none

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    StageList = new int[7]
    DoneList = new bool[7]
    StageList[0] = 10
    StageList[1] = 20
    StageList[2] = 30
    StageList[3] = 40
    StageList[4] = 50
    StageList[5] = 60
    StageList[6] = 70
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " core=" + Game.IsPluginInstalled(CorePlugin) + " markers=" + Game.IsPluginInstalled(MarkPlugin))
    StartTimer(1.0, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {A user log is open only in the game session that opened it (assumed): when a write fails, as after a save is loaded again, the log is opened once more and the line written again. Every line ends with end=true.}
    string line = "FO4SFMARK rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
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

ObjectReference Function RefNamed(string nm)
    {One of the four references by its short name (V111, LAND, TEST, TEST2), or None when it does not resolve.}
    if nm == "V111"
        return Game.GetFormFromFile(V111Id, CorePlugin) as ObjectReference
    elseif nm == "LAND"
        return Game.GetFormFromFile(LandId, MarkPlugin) as ObjectReference
    elseif nm == "TEST"
        return Game.GetFormFromFile(TestId, MarkPlugin) as ObjectReference
    elseif nm == "TEST2"
        return Game.GetFormFromFile(Test2Id, MarkPlugin) as ObjectReference
    endif
    return None
EndFunction

; ---------------------------------------------------------------- the reads

Function Reading(string whenText, int stage, string nm)
    {One reference: where it is, and the two proxies for its map state.}
    ObjectReference r = RefNamed(nm)
    if r == None
        Trace("read stage=" + stage + " when=" + whenText + " name=" + nm + " ref=none")
        Say("S" + stage + " " + nm + " ref=none")
        return
    endif
    bool vis = r.IsMapMarkerVisible()
    bool can = r.CanFastTravelToMarker()
    Trace("read stage=" + stage + " when=" + whenText + " name=" + nm + " ref=" + Id(r) + " world=" + Id(r.GetWorldSpace()) + " cell=" + Id(r.GetParentCell()) + " pos=" + r.GetPositionX() + "," + r.GetPositionY() + "," + r.GetPositionZ() + " visible=" + vis + " canfast=" + can)
    Say("S" + stage + " " + whenText + " " + nm + " vis=" + vis + " fast=" + can + " w=" + Id(r.GetWorldSpace()))
EndFunction

Function Fast(string whenText, int stage)
    {The player and the two fast travel reads (the owner's unlock: the first location discovered).}
    Actor p = Game.GetPlayer()
    bool enabled = Game.IsFastTravelEnabled()
    Trace("fast stage=" + stage + " when=" + whenText + " enabled=" + enabled + " controls=" + Game.IsFastTravelControlsEnabled() + " pworld=" + Id(p.GetWorldSpace()) + " pcell=" + Id(p.GetParentCell()) + " pos=" + p.GetPositionX() + "," + p.GetPositionY() + "," + p.GetPositionZ())
    Say("S" + stage + " " + whenText + " fasttravel=" + enabled + " pw=" + Id(p.GetWorldSpace()))
EndFunction

Function ReadAll(string whenText, int stage)
    Fast(whenText, stage)
    Reading(whenText, stage, "V111")
    Reading(whenText, stage, "LAND")
    Reading(whenText, stage, "TEST")
    Reading(whenText, stage, "TEST2")
EndFunction

; ---------------------------------------------------------------- stages

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(1.0, TIMER_POLL)
    elseif aiTimerID == TIMER_LATER
        Later()
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
    if stage == 10 || stage == 40 || stage == 50
        ReadAll("read", stage)
        Trace("stage done stage=" + stage)
        return
    endif
    if stage == 20
        MoveTest(stage)
        return
    endif
    if stage == 30
        Fast("before", stage)
        Reading("before", stage, "V111")
        ObjectReference v = RefNamed("V111")
        if v != None
            v.SetMarkerDiscovered()
            Trace("discovered stage=" + stage + " name=V111 call=SetMarkerDiscovered")
        endif
        Fast("after", stage)
        Reading("after", stage, "V111")
    endif
    if stage == 60
        Fast("before", stage)
        Reading("before", stage, "LAND")
        ObjectReference l = RefNamed("LAND")
        if l != None
            l.SetMarkerDiscovered()
            Trace("discovered stage=" + stage + " name=LAND call=SetMarkerDiscovered")
        endif
        Fast("after", stage)
        Reading("after", stage, "LAND")
    endif
    if stage == 70
        Fast("before", stage)
        Reading("before", stage, "TEST2")
        ObjectReference t = RefNamed("TEST2")
        if t != None
            t.AddToMap(false)
            Trace("addtomap stage=" + stage + " name=TEST2 allowfasttravel=false")
        endif
        Fast("after", stage)
        Reading("after", stage, "TEST2")
    endif
    LaterStage = stage
    StartTimer(LaterS, TIMER_LATER)
EndFunction

Function MoveTest(int stage)
    {Stage 20: the exit's own MoveTo, from inside the vault. The marker's own position before the move plus the merge offset is where
     the placement would put it.}
    ObjectReference t = RefNamed("TEST")
    ObjectReference a = RefNamed("V111")
    if t == None || a == None
        Trace("move stage=" + stage + " test=" + Id(t) + " anchor=" + Id(a) + " (a reference does not resolve: nothing moved)")
        Say("S" + stage + " reference missing: nothing moved")
        return
    endif
    float px = t.GetPositionX()
    float py = t.GetPositionY()
    float pz = t.GetPositionZ()
    Reading("before", stage, "TEST")
    t.MoveTo(a, 0.0, 0.0, 0.0, True, False)
    Trace("move stage=" + stage + " call=MoveTo anchor=" + Id(a))
    Reading("moved", stage, "TEST")
    t.SetPosition(px + MergeX, py + MergeY, pz)
    Trace("move stage=" + stage + " call=SetPosition target=" + (px + MergeX) + "," + (py + MergeY) + "," + pz)
    Reading("set", stage, "TEST")
    LaterStage = stage
    StartTimer(LaterS, TIMER_LATER)
EndFunction

Function Later()
    {The 2 s re-read of the stage that changed something.}
    int stage = LaterStage
    LaterStage = 0
    if stage == 20
        Fast("later", stage)
        Reading("later", stage, "TEST")
    elseif stage == 30
        Fast("later", stage)
        Reading("later", stage, "V111")
    elseif stage == 60
        Fast("later", stage)
        Reading("later", stage, "LAND")
    elseif stage == 70
        Fast("later", stage)
        Reading("later", stage, "TEST2")
    endif
    Trace("later done stage=" + stage)
    Say("S" + stage + " later done")
EndFunction
