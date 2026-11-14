Scriptname FO4SF_MapMarkers extends Quest
{Puts the Commonwealth's map markers into the world the player walks in (fo4-to-starfield, docs/terrain/map-markers.md
 "Markers in the merged world"). The markers are persistent references of FO4TerrainCore.esm's overlay world, and a
 persistent reference of that world stays at its LOCAL position in the base world (door probe (a), 16 Oct; the
 mission's actors, 18 Oct), while the player walks in a world made at run time (FF0054C8 in the mission log) that
 places the core's records at local + the merge offset: no icon showed (owner, 19 Oct, v6). Every Interval seconds,
 with the player outdoors inside the overlay's merged extent, each marker that is not at its merged spot in the
 player's world is enabled and moved there (MoveTo onto the player with the difference as the offset, the form
 FO4SF_LoadDoor and the mission's Relocate use, but keeping the reference's own rotation: the list also holds the
 landing spot's pad, whose facing is the ship's). The player is read again before every move, and a pass stops once
 they are indoors, in another world or outside the extent. A reference the game will not move (the landing pad) is
 left alone for the rest of the session. Every move goes to the user log "fo4sf_map"
 (My Games\Starfield\Logs\Script\User\fo4sf_map.0.log). The map lists only the markers that are in a world when
 the player enters it, and these are moved in after, so once every marker is in place the first quest reloads the
 world once, behind a black screen (HopMarker).}

ObjectReference[] Property Markers Auto Const Mandatory
{The core's MapMarker references (dotnet/MapMarkers fills them from the core plugin), then the plugin's own: its
 markers (--extra) and the landing spot's pad, trigger, marker and heading (--landing).}

float[] Property LocalX Auto Const Mandatory
float[] Property LocalY Auto Const Mandatory
float[] Property LocalZ Auto Const Mandatory
{Each marker's written (local) position, so the target does not depend on where a marker was last moved to.}

float Property MergeOffsetX = -1200.0 Auto Const
float Property MergeOffsetY = -2700.0 Auto Const
{vmad_patch.MERGE_MEASURED (measured in game); z unchanged.}

float Property MinX = -4400.0 Auto Const
float Property MaxX = 2000.0 Auto Const
float Property MinY = -5900.0 Auto Const
float Property MaxY = 500.0 Auto Const
{The overlay's merged extent (local -3200..3200 m + the merge offset). Coordinates alone cannot tell two exterior
 worlds apart: a player standing outdoors in another world inside this box would pull the markers there.}

float Property Tolerance = 5.0 Auto Const
{A marker within this many units of its merged spot (x, y), in the player's world, counts as placed.}

float Property ZTolerance = 0.05 Auto Const
{The same for height: a save made before a build that lifted LocalZ holds the markers at the old height, and the
 moved markers' saved positions outlive the records (docs/JOURNAL.md, changed references); a marker more than this
 far from its LocalZ is moved again. Half the lift step: dotnet/MapMarkers accepts --z-lift in steps of 0.1 m only,
 so any change between builds is at least 0.1 m and is seen, while a landed move (within 0.01 m, fo4sf_map.0.log
 22 Oct) is not moved again.}

float Property SameWorld = 100000.0 Auto Const
{GetDistance above this means the marker is in another world (it reads float max there, 18 Oct).}

float Property Interval = 2.0 Auto Const

int Property MaxMoves = 40 Auto Const
{Stop moving after this many moves in one game session (a move that never lands would otherwise repeat every
 Interval). The count is saved state; it starts over when a build changes the markers' count or their height (budgetN,
 budgetZ), so a later lift reaches a save whose budget an earlier placement spent (Codex on #483), and at every game
 session (NewSession), so markers a session left in the wrong place are put right in the next one.}

int Property LandingPadID = 0x007145 Auto Const
{ShipLandingMarker_80m_Large (Starfield.esm), the landing spot's pad. dotnet/MapMarkers lists the landing spot last, as
 pad, trigger, marker, heading, all four in one quest, so the pad is fourth from its quest's end and the marker two
 places after it.}

bool Property ShowLandingMarker = True Auto Const
{True (the default): ShowLanding discovers the landing marker and shows it on the star map, once per session (the build before 14 Nov).
 False: ShowLanding does nothing and the marker stays as the plugin wrote it. dotnet/MapMarkers --landing-undiscovered writes it false on every
 quest and the marker's flags without Discovered, because no script can clear Discovered (SetMarkerDiscovered takes no argument; PC read of the
 Papyrus sources, 14 Nov 2026), so the plugin has to start it undiscovered when a build wants it found later (FAL-489, the Vault 111 exit).}

bool Property BorderSignal = True Auto Const
{Write "border=off" / "border=on" to this log when the player enters or leaves our world, for the SFSE plugin
 FO4SFBorder (sfse/FO4SFBorder/README.md), which turns the game's border regions off only while the line says off.}

ObjectReference Property HopMarker Auto Const
{The reload's stop: the marker in this plugin's own small interior (dotnet/MapMarkers --reload, FO4SF_MapMarkersHop), on
 the first quest only. The map lists only the markers that are in a world when the player enters it, and these are moved
 in after: no marker showed on the map or could be discovered by walking past it until a trip to Cydonia and back
 (owner, 2026-10-31), and the world keeps them meanwhile (the same instance and no marker moved again after such a trip,
 fo4sf_map.0.log 24 Oct). So once every quest's markers are in place and some went in after the player entered, the
 first quest takes the player here and straight back to the same spot with the screen black, at most HopLimit times a
 session; only in our world as Border learns it, so only with BorderSignal on. None: never.}

float Property HopDelay = 10.0 Auto Const
{Seconds the player must have been outdoors in that world first: a start that places them in steps is done by then (the
 new game's arrival SetPosition, then its landing check 3 s later: FO4SF_NewGameQuest.psc CheckLanding).}

float Property HopWait = 10.0 Auto Const
{Seconds each leg of the reload waits for the player to arrive (Utility.Wait: a loading screen does not count).}

int Property HopLimit = 1 Auto Const
{Reloads per game session: one that does not help (a world made again on the way back moves every marker in again)
 would otherwise repeat.}

bool Property HoldDark = True Auto Const
{The first quest keeps the screen black from an arrival until its reload is back, so the first map the player opens
 lists every marker (option A put to the owner, 2026-10-31): it fades out at its first marker that comes in late
 within HoldWindow seconds of the player entering the world, and the reload's way back fades in. False: the reload
 only (a short blink).}

float Property HoldWindow = 15.0 Auto Const
{Seconds after the player entered the world in which a late marker still starts the hold; later, they are playing. The
 new game's ride lands at its anchor, off the map, and on the arrival 4.3 s later; the first quest's first move came
 7.2 s after the ride (31 Oct retest: rt 125.8, 130.1, 133.0).}

float Property HoldMax = 60.0 Auto Const
{The longest hold, in seconds: the screen comes back then even without the reload (31 Oct retest: the reload was back
 about 14 s after the last marker went in, about 35 s after the arrival).}

string LogName = "fo4sf_map"
; the border signal's state: -1 none written this session, 0 off (our world), 1 on; ourWorld is the player's world
; seen while in one of the core's cells (the runtime instance changes every launch, so it is learned, not a property)
int border = -1
WorldSpace ourWorld = None
float lastRealTime = -1.0
int moves = 0
; the build the move budget was spent on: the marker count and LocalZ[0] (every lift changes it). Const properties
; read the installed records, these two the save, so a new build differs on the first pass after it.
int budgetN = -1
float budgetZ = 0.0
; this game session (Place's own clock, as Border keeps its own): the references the game refused to move, and whether
; the landing marker was shown on the star map
float placeRealTime = -1.0
bool[] refused
bool landingShown = False
; the reload (docs/terrain/map-markers.md "Reload"): settledWorld is the world this quest's markers all stood in at its
; last full pass (None while any was off), probeAt the next one a pass checks from then on, seenWorld the world of its last
; outdoor pass (the player came out, or changed worlds, when it differs) and late whether a marker went into that world
; after the player entered it. The first quest also keeps when they entered, its reloads this session, and the way back
; (saved, so a save made at the stop still brings the player back: being in the stop's cell is what says they are there)
WorldSpace settledWorld = None
int probeAt = 0
WorldSpace seenWorld = None
bool late = False
float enteredAt = 0.0
int hops = 0
bool waitLogged = False
bool travelLogged = False
int hopAnchor = -1
; the dark hold (first quest): on since holdAt; held once per entry into a world
bool holding = False
bool heldEntry = False
float holdAt = 0.0
float hopX = 0.0
float hopY = 0.0
float hopZ = 0.0
float hopA = 0.0
WorldSpace hopWorld = None
int lowId = -1

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init markers=" + Markers.Length)
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    StartTimer(Interval, 1)
EndEvent

; Every save load starts a new session, for Place (the move budget, the refused list, the landing) and for Border (the
; log opened again, the signal written again). The clocks alone miss a launch whose first pass reads a later real time
; than the save's last one (Codex on #570: saved 20 s, first pass at 90 s), so the load clears them. OnPlayerLoadGame
; is declared on Actor (PC read, 19 Oct: docs/newgame/vault111-start.md); the mission's keeper registers the same way.
Event Actor.OnPlayerLoadGame(Actor akSender)
    placeRealTime = 0.0                                       ; NewSession: unset, so a new session
    lastRealTime = 1000000000.0                               ; Border: any clock is below it, so a new session
EndEvent

Function ResetBudget()
    if Markers.Length > 0 && (budgetN != Markers.Length || budgetZ != LocalZ[0])
        Trace("budget reset for markers=" + Markers.Length + " z0=" + LocalZ[0] + " (was " + budgetN + " / " + budgetZ + ", moves=" + moves + ")")
        budgetN = Markers.Length
        budgetZ = LocalZ[0]
        moves = 0
        refused = new bool[128]                                 ; a new build can list other references at those places
        landingShown = False
        settledWorld = None
    endif
EndFunction

; A new game session (the real-time clock starts over at every launch, as Border reads it): the move budget starts over,
; and so does the list of references the game refused to move. A save from before this script had these variables
; brings them in unset (0.0 or the initial -1.0), so either one counts as a new session and the list is made; a save
; load sets 0.0 (OnPlayerLoadGame).
bool Function NewSession()
    float rt = Utility.GetCurrentRealTime()
    bool fresh = placeRealTime <= 0.0 || rt < placeRealTime
    if fresh
        Debug.OpenUserLog(LogName)                              ; a load in a new launch runs no OnInit to open it
        lastRealTime = 1000000000.0                             ; Border starts over too: an old save's first load had no event
        RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")  ; a save from before the registration ran OnInit
        if moves > 0
            Trace("session: move budget starts over (was moves=" + moves + ")")
        endif
        moves = 0
        refused = new bool[128]                                 ; a quest lists at most PerQuest (dotnet/MapMarkers)
        landingShown = False
        settledWorld = None                                     ; a load can bring the markers back to their own world
        seenWorld = None
        late = False
        hops = 0
        waitLogged = False
        travelLogged = False
        if holding
            Game.FadeOutGame(False, True, 0.0, 0.5, False)      ; a load ends a hold (its loading screen may fade in too)
            holding = False
        endif
        heldEntry = False
    endif
    placeRealTime = rt
    return fresh
EndFunction

; Once per session and quest, what Border's guards read: a coc session from the main menu at Red Rocket wrote no border
; line in 240 s while "moved 9" lines kept coming (Review, 2026-10-28), and the log could not say whether 0x800 ticked
; or its Markers[0] was None.
Function SessionLine(Actor player)
    ObjectReference first = None
    if Markers.Length > 0
        first = Markers[0]
    endif
    Trace("session id=" + GetFormID() + " signal=" + SignalQuest() + " enabled=" + BorderSignal + " markers=" + Markers.Length + " first=" + first + " interior=" + player.IsInInterior())
EndFunction

; The landing spot's map marker, found after its pad, is marked discovered and shown on the star map, so the planet
; map can offer it as a place to land (owner, 2026-10-28: Mars's map had no Commonwealth location; a vanilla landing
; site is discovered when the player lands there). Once per session, wherever the player is; one reference read per
; quest, so the border signal is not held up.
Function ShowLanding()
    if landingShown
        return
    endif
    landingShown = True
    if !ShowLandingMarker
        return
    endif
    int i = Markers.Length - 4
    if i < 0
        return
    endif
    ObjectReference pad = Markers[i]
    ObjectReference marker = Markers[i + 2]
    if pad != None && marker != None && pad.GetBaseObject() == Game.GetForm(LandingPadID)
        marker.SetMarkerDiscovered()
        marker.SetMarkerVisibleOnStarMap(True)
        Trace("landing marker " + (i + 2) + " discovered and shown on the star map")
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == 1
        Place(Game.GetPlayer())
        StartTimer(Interval, 1)
    endif
EndEvent

Function Place(Actor player)
    if NewSession()                                           ; first, so the log is open for every line after it
        SessionLine(player)
    endif
    ResetBudget()
    Border(player)
    ShowLanding()
    if player.IsInInterior()
        if HopMarker != None && player.GetParentCell() == HopMarker.GetParentCell()
            ComeBack(player)                                  ; the stop has no door: anyone in it goes back (first quest)
        endif
        Release("the player went indoors")
        seenWorld = None                                      ; when they come out, the world loads with what is in it
        late = False
        return
    endif
    WorldSpace w = player.GetWorldSpace()
    if w != seenWorld
        seenWorld = w                                         ; came out, or into another world, since the last pass
        late = False
        enteredAt = Utility.GetCurrentRealTime()
        heldEntry = False
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    bool inside = !(px < MinX || px > MaxX || py < MinY || py > MaxY)
    if holding
        HoldCheck(player, inside && w == ourWorld)            ; before any return: the hold never outlives its reasons
    endif
    if !inside
        return
    endif
    if settledWorld == w && Probe(player)
        Reload(player, w)                                     ; all in place: the first quest may reload the world
        return
    endif
    settledWorld = None
    int moved = 0
    int i = 0
    while i < Markers.Length && moves < MaxMoves              ; the budget holds per move, not per batch
        ObjectReference m = Markers[i]
        if m != None && !refused[i]
            float x = LocalX[i] + MergeOffsetX
            float y = LocalY[i] + MergeOffsetY
            float z = LocalZ[i]
            float before = player.GetDistance(m)                ; float max: another world
            ; in another world it moves wherever it stands there, so its position is not read: each read is a call the
            ; game answers about once a frame (a 100-marker quest placed a marker every 0.45 s, fo4sf_map.0.log 31 Oct)
            bool off = before > SameWorld
            float ex = 0.0
            float ey = 0.0
            float ez = 0.0
            if !off
                ex = m.GetPositionX() - x
                ey = m.GetPositionY() - y
                ez = m.GetPositionZ() - z
                off = ex * ex + ey * ey > Tolerance * Tolerance || ez * ez > ZTolerance * ZTolerance
            endif
            if off
                ; the player as they are now, just before the move: a load door can take them away while a pass runs,
                ; and a pass that read them once put about 300 markers into Vault 95 at the target plus the trip and
                ; spent every budget (PC, 2026-10-24 10:24, fo4sf_map.0.log)
                if player.IsInInterior() || player.GetWorldSpace() != w
                    Trace("pass stopped at " + i + ": the player went indoors or to another world")
                    return
                endif
                if holding
                    HoldCheck(player, w == ourWorld)                  ; a pass can run for seconds: checked between moves too
                endif
                px = player.GetPositionX()
                py = player.GetPositionY()
                float pz = player.GetPositionZ()
                if px < MinX || px > MaxX || py < MinY || py > MaxY
                    return
                endif
                m.Enable(False)
                m.MoveTo(player, x - px, y - py, z - pz, False, False)   ; no match-rotation: keep the record's
                moves += 1
                moved += 1
                float d = player.GetDistance(m)
                if d > SameWorld
                    ; still in its own world after a move to the player: the game refused it ("cannot be moved", the
                    ; landing pad, 2026-10-24), unless the player left. Not tried again this session (it spent its
                    ; quest's whole budget). A move that works lands in the player's world at once (d 0.8 to 2.9 km on
                    ; the PC, 2026-10-28); asking for an unchanged position too never held for the pad there (18 and 27
                    ; "cannot be moved" in two runs, no refused line), so the line says where it stands after the move
                    if player.IsInInterior() || player.GetWorldSpace() != w
                        Trace("pass stopped after moving " + i + ": the player went indoors or to another world")
                        return
                    endif
                    refused[i] = True
                    Trace("refused " + i + ": still in its own world after the move, at " + m.GetPositionX() + " " + m.GetPositionY() + "; not moved again this session")
                else
                    ; a move onto a walking player lands off by their steps in between (z 0.4 off, then moved again:
                    ; 475 moves for 313 markers, fo4sf_map.0.log 31 Oct): set the spot itself, now in the player's world
                    m.SetPosition(x, y, z)
                    if before > SameWorld
                        late = True                             ; it came into the world after the player did
                        if !heldEntry && HoldDark && BorderSignal && HopMarker != None && hops < HopLimit && w == ourWorld && Utility.GetCurrentRealTime() - enteredAt < HoldWindow
                            Hold()
                        endif
                    endif
                    Trace("moved " + i + " to " + m.GetPositionX() + " " + m.GetPositionY() + " " + m.GetPositionZ() + " target " + x + " " + y + " " + z + " before=" + before + " off=" + ex + " " + ey + " " + ez + " d=" + d + " moves=" + moves)
                endif
            endif
        endif
        i += 1
    endwhile
    if i >= Markers.Length && moved == 0
        settledWorld = w                                      ; every marker in place: from now on one a pass is read
        Reload(player, w)
    elseif moves >= MaxMoves
        Reload(player, w)                                     ; out of moves: nothing more moves this session (Ready)
    endif
EndFunction

; Only the first quest (0x800) writes the signal: every quest of the plugin runs this script, and only the first one's
; Markers[0] is a core marker (dotnet/MapMarkers lists the core's markers first; the extra and landing records that fill
; the later quests are this plugin's own), so a later quest would read the plugin's index as the core's and write
; border=on (PC, 2026-10-24: on/on/off/on within 0.8 s on the first load at Red Rocket). Low 12 bits, so a light
; plugin's FE-prefixed (negative) id gives the same answer.
bool Function SignalQuest()
    int low = QuestLow()
    return low == 2048
EndFunction

; The quest's FormID, low 12 bits (2048 for 0x800, 2049 for 0x801, ...), on every log line so the quests can be told apart.
int Function QuestLow()
    if lowId < 0                                           ; once: every line asks, and each GetFormID is a call
        int low = GetFormID() % 4096
        if low < 0
            low += 4096
        endif
        lowId = low
    endif
    return lowId
EndFunction

; In our world: the player's cell is one of the core's own cells (the runtime instance keeps the core's cell ids:
; docs/terrain/door-rounds.md), or the player is outdoors in the same world as when they last were (the generated
; land past our cells). Indoors keeps the last state, so a door out lands with the border already off.
Function Border(Actor player)
    if !BorderSignal || !SignalQuest() || Markers.Length == 0 || Markers[0] == None
        return
    endif
    float rt = Utility.GetCurrentRealTime()
    if rt < lastRealTime                                      ; a new game session: the plugin skips old lines
        Debug.OpenUserLog(LogName)
        border = -1
        ourWorld = None
    endif
    lastRealTime = rt
    if player.IsInInterior()
        return
    endif
    int core = Markers[0].GetFormID() / 16777216
    Cell c = player.GetParentCell()
    WorldSpace w = player.GetWorldSpace()
    int want = 1
    if c != None && c.GetFormID() / 16777216 == core
        ourWorld = w
        want = 0
    elseif ourWorld != None && w == ourWorld
        want = 0
    endif
    if want != border
        border = want
        if want == 0
            Trace("border=off cell=" + c + " world=" + w)
        else
            Trace("border=on cell=" + c + " world=" + w)
        endif
    endif
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MAP rt=" + Utility.GetCurrentRealTime() + " q=" + QuestLow() + " " + msg)
EndFunction

; Once every marker of this quest stood in the player's world at a full pass, a pass reads one of them, in turn, instead of
; all four reads a marker: they leave it when a save loads (a new session starts a full pass anyway) or a world is made
; again, and one found off starts a full pass. A marker refused this session counts as in place.
bool Function Probe(Actor player)
    int n = Markers.Length
    int tries = 0
    while tries < n
        int i = probeAt % n                                    ; a new build can list fewer markers
        probeAt = (i + 1) % n
        tries += 1
        ObjectReference m = Markers[i]
        if m != None && !refused[i]
            if player.GetDistance(m) > SameWorld
                return False
            endif
            float ex = m.GetPositionX() - (LocalX[i] + MergeOffsetX)
            float ey = m.GetPositionY() - (LocalY[i] + MergeOffsetY)
            float ez = m.GetPositionZ() - LocalZ[i]
            return !(ex * ex + ey * ey > Tolerance * Tolerance || ez * ez > ZTolerance * ZTolerance)
        endif
    endwhile
    return True
EndFunction

; What the first quest asks of every quest before a reload: done in this world (every marker in place at the last full
; pass, or the session's moves spent: nothing more moves then), and whether any went in after the player entered it.
bool Function Ready(WorldSpace w)
    return settledWorld == w || moves >= MaxMoves
EndFunction

bool Function IsLate()
    return late
EndFunction

; After a reload: the player entered the world again, with every marker already in it.
Function Reentered(WorldSpace w)
    seenWorld = w
    late = False
EndFunction

; The first quest only (HopMarker): once every quest is Ready in the player's world, which is ours (Border's), and some
; marker went in after the player entered it, HopDelay seconds after they did, out of combat and scenes and with the
; movement controls on, the player goes to the stop and comes back to the same spot behind a black screen, so the world
; loads again with the markers in it (the owner's trip to Cydonia and back did the same, 2026-10-31). The quests are this
; one and the ones after it (dotnet/MapMarkers numbers them from 0x800 up, with nothing else between).
Function Reload(Actor player, WorldSpace w)
    if HopMarker == None || hops >= HopLimit || w != ourWorld
        return
    endif
    bool anyLate = False
    int id = GetFormID()
    int k = 0
    FO4SF_MapMarkers q = self
    while q != None
        if !q.Ready(w)
            return
        endif
        if q.IsLate()
            anyLate = True
        endif
        k += 1
        q = Game.GetForm(id + k) as FO4SF_MapMarkers
    endwhile
    if !travelLogged
        travelLogged = True
        FastTravelLine("all " + k + " quests' markers in place or out of moves, some after the player came: " + anyLate)
    endif
    if !anyLate || Utility.GetCurrentRealTime() - enteredAt < HopDelay
        return
    endif
    if player.IsInCombat() || player.IsInScene() || !Game.IsMovementControlsEnabled() || player.IsDead() || player.GetSitState() != 0
        Release("the reload waits")
        if !waitLogged
            waitLogged = True
            Trace("reload waits: combat=" + player.IsInCombat() + " scene=" + player.IsInScene() + " movement=" + Game.IsMovementControlsEnabled() + " dead=" + player.IsDead() + " sit=" + player.GetSitState())
        endif
        return
    endif
    int a = 0                                                 ; the way back: a marker of this quest in the player's world
    while a < Markers.Length && (Markers[a] == None || refused[a] || player.GetDistance(Markers[a]) > SameWorld)
        a += 1                                                ; (a quest out of moves may have some still in their own)
    endwhile
    hops += 1
    if a >= Markers.Length
        Trace("reload " + hops + " skipped: no marker of this quest in the player's world to come back by")
        Release("the reload was skipped")
        return
    endif
    Game.FadeOutGame(True, True, 0.0, 0.5, True)
    Utility.Wait(0.5)
    ; the player as they are now, with the screen black and just before the move: w was read when this pass began, and a
    ; load door or a fast travel can take them away while a pass runs (review of #624); the way back is read here, so it
    ; is a spot in w. A reload called off is not tried again: going indoors and out loads the world again anyway
    hopX = player.GetPositionX()
    hopY = player.GetPositionY()
    hopZ = player.GetPositionZ()
    hopA = player.GetAngleZ()
    if player.IsInInterior() || player.GetWorldSpace() != w || hopX < MinX || hopX > MaxX || hopY < MinY || hopY > MaxY
        holding = False
        Game.FadeOutGame(False, True, 0.0, 0.5, False)
        Trace("reload " + hops + " called off: the player went indoors, to another world or off the map")
        return
    endif
    hopAnchor = a
    hopWorld = w
    player.MoveTo(HopMarker)
    Trace("reload " + hops + ": out to " + HopMarker + " and back to " + hopX + " " + hopY + " " + hopZ + " in " + w)
    float waited = 0.0
    while !player.IsInInterior() && waited < HopWait
        Utility.Wait(0.25)
        waited += 0.25
    endwhile
    Trace("reload " + hops + ": at the stop=" + player.IsInInterior() + " cell=" + player.GetParentCell() + " after " + waited + " s")
    ComeBack(player)
    k = 0
    q = self
    while q != None                                           ; every quest: the player entered again
        q.Reentered(w)
        k += 1
        q = Game.GetForm(id + k) as FO4SF_MapMarkers
    endwhile
    enteredAt = Utility.GetCurrentRealTime()
    FastTravelLine("after reload " + hops)
EndFunction

; Back from the stop to where the reload began: MoveTo the anchor marker (in that world at its merged spot) with the
; difference as the offset, twice at most; once outside with the 3D in, SetPosition there if the move landed more than
; 2 m off (a SetPosition in the MoveTo's own tick is ignored: FO4SF_NewGameQuest.psc FinishSurface), the facing back,
; and the screen in. Also from the first quest's next pass for a player still at the stop (a save made there).
Function ComeBack(Actor player)
    if holding
        Trace("dark hold ends with the reload after " + (Utility.GetCurrentRealTime() - holdAt) + " s")
        holding = False                                       ; every way out of here fades in
    endif
    if hopAnchor < 0 || hopAnchor >= Markers.Length || Markers[hopAnchor] == None
        Trace("reload: no way back (anchor " + hopAnchor + " of " + Markers.Length + ")")
        Game.FadeOutGame(False, True, 0.0, 0.5, False)
        return
    endif
    ObjectReference anchor = Markers[hopAnchor]
    float ax = LocalX[hopAnchor] + MergeOffsetX
    float ay = LocalY[hopAnchor] + MergeOffsetY
    float az = LocalZ[hopAnchor]
    int tries = 0
    while player.IsInInterior() && tries < 2
        player.MoveTo(anchor, hopX - ax, hopY - ay, hopZ - az, False, False)
        tries += 1
        float gone = 0.0
        while player.IsInInterior() && gone < HopWait
            Utility.Wait(0.25)
            gone += 0.25
        endwhile
    endwhile
    if player.IsInInterior()
        Game.FadeOutGame(False, True, 0.0, 0.5, False)
        Trace("reload " + hops + ": still at the stop after " + tries + " moves back; the next pass tries again")
        return
    endif
    float loaded = 0.0
    while !player.Is3DLoaded() && loaded < HopWait
        Utility.Wait(0.25)
        loaded += 0.25
    endwhile
    Utility.Wait(0.5)
    ; the spot is one in hopWorld: if the trip made the world again (or a save made at the stop loads in a new launch,
    ; whose world is another instance), the anchor went back to its own world and the move lands by it there, which
    ; the spot would only send off by the merge offset, so only the same world is set
    WorldSpace back = player.GetWorldSpace()
    float dx = player.GetPositionX() - hopX
    float dy = player.GetPositionY() - hopY
    bool snapped = back == hopWorld && dx * dx + dy * dy > 4.0
    if snapped
        player.SetPosition(hopX, hopY, hopZ)
    endif
    player.SetAngle(0.0, 0.0, hopA)
    Game.FadeOutGame(False, True, 0.0, 0.5, False)
    Trace("reload " + hops + " back: moves=" + tries + " set=" + snapped + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " world=" + back + " same=" + (back == hopWorld))
EndFunction

; The dark hold (HoldDark): the screen black from an arrival until the reload is back, so the map is never opened before.
Function Hold()
    heldEntry = True
    holding = True
    holdAt = Utility.GetCurrentRealTime()
    Game.FadeOutGame(True, True, 0.0, 0.5, True)
    Trace("dark hold: markers coming in " + (holdAt - enteredAt) + " s after the player entered the world")
EndFunction

; A hold ends with the reload (ComeBack), or here: past HoldMax seconds, off the map or out of our world (no reload
; comes there), and whenever the reload would wait: in a fight, dead, seated, in a scene or without movement controls.
Function HoldCheck(Actor player, bool ours)
    float held = Utility.GetCurrentRealTime() - holdAt
    if held > HoldMax
        Release("no reload after " + held + " s")
    elseif !ours
        Release("the player left the map or our world")
    elseif player.IsInCombat() || player.IsDead() || player.IsInScene() || player.GetSitState() != 0 || !Game.IsMovementControlsEnabled()
        Release("combat=" + player.IsInCombat() + " dead=" + player.IsDead() + " scene=" + player.IsInScene() + " sit=" + player.GetSitState() + " movement=" + Game.IsMovementControlsEnabled())
    endif
EndFunction

Function Release(string why)
    if holding
        holding = False
        Game.FadeOutGame(False, True, 0.0, 0.5, False)
        Trace("dark hold released: " + why)
    endif
EndFunction

; What the map and fast travel go by (owner, 2026-10-31: nothing on the map, no fast travel to it): the game's two
; switches, and the quest's first marker's own state.
Function FastTravelLine(string when)
    ObjectReference m = None
    if Markers.Length > 0
        m = Markers[0]
    endif
    if m == None
        return
    endif
    Trace("fast travel, " + when + ": enabled=" + Game.IsFastTravelEnabled() + " controls=" + Game.IsFastTravelControlsEnabled() + " marker 0 visible=" + m.IsMapMarkerVisible() + " can=" + m.CanFastTravelToMarker())
EndFunction
