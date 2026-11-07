Scriptname FOCC_ProbeQuest extends Quest
{The combined core's engine probes P2 to P10 (fo4-to-starfield, docs/spikes/combined-core-probes.md; the questions are
 research/framework/combined-core-notes/engine-feasibility.md "PC probes"). Attached to QUST FOCC_ProbeQuest (0x804 of
 FO4SFCombinedProbe.esm, start game enabled, no stages; dotnet/CombinedProbe fills every property). The console
 reaches it through the global functions of FOCC_Probe.psc (cgf "FOCC_Probe.<name>" ...), which resolve this quest by
 Game.GetFormFromFile and call the functions below. Every finding is one line of the user log "focc"
 (My Games\Starfield\Logs\Script\User\focc.0.log) in the fixed form
   FOCC rt=<real time s> <probe> <event> key=value key=value ...
 (ids as Papyrus prints them: signed decimal; floats with six decimals; bools True/False), which
 src/fo4sf/combined/probes.py parses. Nothing here is judged in game: the lines are the evidence.}

; ---------------------------------------------------------------- properties the builder fills (dotnet/CombinedProbe)

Keyword Property Holder Auto Const Mandatory
{KYWD FOCC_Holder (0x805): the keyword whose per-location datum P2, P3 and P6 set and read.}

Keyword Property Route Auto Const Mandatory
{KYWD FOCC_Route (0x809): the link keyword of P2's AddLinkedLocation.}

Location Property P2Loc Auto Const Mandatory
{LCTN FOCC_P2_Loc (0x806, local id 2054): parent = the core's Commonwealth location.}

Location Property P3LocNoParent Auto Const Mandatory
{LCTN FOCC_P3_LocNoParent (0x807, local id 2055): no parent, no keywords.}

Location Property P3LocChained Auto Const Mandatory
{LCTN FOCC_P3_LocChained (0x808, local id 2056): parent = the core's location, keyword LocTypeOverlay; P2's link target.}

ObjectReference Property P4Marker Auto Const Mandatory
{REFR FOCC_P4_SpawnMarker (0x80B): persistent XMarker in the core world's persistent cell.}

Form Property P4Base Auto Const Mandatory
{The NPC_ the P4 cycles place (--npc; the vanilla citizen 002B211C of the test sheet by default). Declared as Form
 because PlaceAtMe takes a Form: no actor-base or leveled-list base script is needed at compile time.}

GlobalVariable[] Property P5Globals Auto Const Mandatory
{GLOB FOCC_P5_G00..G49 (0x823..0x854): the 50 "places" P5 ticks over.}

Form Property P6List Auto Const Mandatory
{LVLN FOCC_P6_HolderList (0x81C): entries conditioned on GetKeywordDataForCurrentLocation(Holder) == 1 / == 2.}

Form Property P6BaseA Auto Const Mandatory
Form Property P6BaseB Auto Const Mandatory
{The two NPC_ bases of the P6 and P7 lists (--lvln-a, --lvln-b), to name which one a spawn resolved to.}

GlobalVariable Property P7Rep Auto Const Mandatory
{GLOB FOCC_Rep_Test (0x81E): the reputation tier the P7 list's conditions read (GetGlobalValue < 8 / >= 8).}

Form Property P7List Auto Const Mandatory
{LVLN FOCC_P7_RepList (0x81D).}

ObjectReference[] Property P8Parents Auto Const Mandatory
{REFR FOCC_P8_Stage0Parent..2 (0x80C..0x80E): the three enable parents (stages 1 and 2 initially disabled).}

ObjectReference[] Property P8Children Auto Const Mandatory
{REFR FOCC_P8_Child_<k>_<j> (0x80F..0x81A), stage-major: children 4k..4k+3 belong to parent k.}

ObjectReference Property P9Dest Auto Const Mandatory
{REFR FOCC_P9_Dest (0x81B): the long-route destination marker.}

Keyword Property P10Event Auto Const Mandatory
{KYWD FOCC_P10_Event (0x81F): the story event keyword FOCC_Probe.P10Send sends.}

Quest Property P10Quest Auto Const Mandatory
{QUST FOCC_P10_Quest (0x820, local id 2080): the quest the Story Manager branch should start.}

string Property Variant = "default" Auto Const
{"default" or "p3cells" (the --p3-cells build): logged in the init line so the checker knows which half of P3 ran.}

; ---------------------------------------------------------------- state

string LogName = "focc"

; P4
int p4Cycle = 0
int p4Cycles = 0
float p4Settle = 8.0
int p4Placed = 0
int p4Deleted = 0
ObjectReference[] p4Spawned

; P5
int p5TickCount = 0
int p5Ticks = 0

; P9
ObjectReference p9Actor = None
float p9Elapsed = 0.0
float p9StartRT = 0.0
float p9Seconds = 0.0

int TIMER_P4_PLACE = 4
int TIMER_P4_SETTLE = 14
int TIMER_P5 = 5
int TIMER_P9 = 9
float P9_SAMPLE = 2.0

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init variant=" + Variant + " quest=" + GetFormID())
EndEvent

Function Trace(string msg)
    Debug.TraceUser(LogName, "FOCC rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction

string Function Id(Form f)
    {"<signed decimal form id>" or "none".}
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

Function Hello()
    {Runtime ids of every probe record, so a log reader can map them to the plugin-local ids.}
    Trace("hello quest=" + GetFormID() + " holder=" + Id(Holder) + " route=" + Id(Route) + " p2loc=" + Id(P2Loc) + " p3a=" + Id(P3LocNoParent) + " p3b=" + Id(P3LocChained))
    Trace("hello p4marker=" + Id(P4Marker) + " p4base=" + Id(P4Base) + " p5globals=" + P5Globals.Length + " p6list=" + Id(P6List) + " p6a=" + Id(P6BaseA) + " p6b=" + Id(P6BaseB))
    Trace("hello p7rep=" + Id(P7Rep) + " p7list=" + Id(P7List) + " p8parents=" + P8Parents.Length + " p8children=" + P8Children.Length + " p9dest=" + Id(P9Dest) + " p10event=" + Id(P10Event) + " p10quest=" + Id(P10Quest))
EndFunction

; ---------------------------------------------------------------- P2: keyword data persistence, linked locations

Function P2Set(float v)
    if P2Loc == None || Holder == None
        Trace("p2 refused loc=" + Id(P2Loc) + " holder=" + Id(Holder))
        return
    endif
    P2Loc.SetKeywordData(Holder, v)
    Trace("p2 set loc=" + P2Loc.GetFormID() + " local=2054 value=" + v + " readback=" + P2Loc.GetKeywordData(Holder) + " holder=" + Id(Holder))
EndFunction

Function P2Read()
    if P2Loc == None || Holder == None
        Trace("p2 refused loc=" + Id(P2Loc) + " holder=" + Id(Holder))
        return
    endif
    Trace("p2 read loc=" + P2Loc.GetFormID() + " local=2054 value=" + P2Loc.GetKeywordData(Holder) + " holder=" + Id(Holder))
EndFunction

Function P2Link()
    if P2Loc == None || P3LocChained == None || Route == None
        Trace("p2 refused loc=" + Id(P2Loc) + " target=" + Id(P3LocChained) + " route=" + Id(Route))
        return
    endif
    P2Loc.AddLinkedLocation(P3LocChained, Route)
    Trace("p2 link a=" + P2Loc.GetFormID() + " b=" + P3LocChained.GetFormID() + " linked=" + P2Loc.IsLinkedLocation(P3LocChained, Route) + " route=" + Id(Route))
EndFunction

Function P2LinkRead()
    if P2Loc == None || P3LocChained == None || Route == None
        Trace("p2 refused loc=" + Id(P2Loc) + " target=" + Id(P3LocChained) + " route=" + Id(Route))
        return
    endif
    Trace("p2 linkread a=" + P2Loc.GetFormID() + " b=" + P3LocChained.GetFormID() + " linked=" + P2Loc.IsLinkedLocation(P3LocChained, Route) + " route=" + Id(Route))
EndFunction

; ---------------------------------------------------------------- P3: unparented vs chained location, current location of a cell

Function P3Set(float a, float b)
    if P3LocNoParent == None || P3LocChained == None || Holder == None
        Trace("p3 refused a=" + Id(P3LocNoParent) + " b=" + Id(P3LocChained) + " holder=" + Id(Holder))
        return
    endif
    P3LocNoParent.SetKeywordData(Holder, a)
    P3LocChained.SetKeywordData(Holder, b)
    Trace("p3 set a=" + P3LocNoParent.GetFormID() + " va=" + a + " ra=" + P3LocNoParent.GetKeywordData(Holder) + " b=" + P3LocChained.GetFormID() + " vb=" + b + " rb=" + P3LocChained.GetKeywordData(Holder) + " holder=" + Id(Holder))
EndFunction

Function P3Read()
    if P3LocNoParent == None || P3LocChained == None || Holder == None
        Trace("p3 refused a=" + Id(P3LocNoParent) + " b=" + Id(P3LocChained) + " holder=" + Id(Holder))
        return
    endif
    Trace("p3 read a=" + P3LocNoParent.GetFormID() + " ra=" + P3LocNoParent.GetKeywordData(Holder) + " b=" + P3LocChained.GetFormID() + " rb=" + P3LocChained.GetKeywordData(Holder) + " holder=" + Id(Holder))
EndFunction

Function Where()
    {The player's cell and current location, and which probe location (plugin-local id) the location is.
     GetFormEditorID is DebugOnly and asked last, as FO4SF_Probe.Where does.}
    Actor p = Game.GetPlayer()
    Cell c = p.GetParentCell()
    Location l = p.GetCurrentLocation()
    string line = "where cell=" + Id(c) + " loc=" + Id(l)
    if l == None
        line += " local=none"
    elseif l == P3LocNoParent
        line += " local=2055"
    elseif l == P3LocChained
        line += " local=2056"
    elseif l == P2Loc
        line += " local=2054"
    else
        line += " local=other"
    endif
    string cellName = ""
    string port = "none"
    if c != None
        ; port=True: Game.GetFormFromFile finds this very cell at its plugin-local id in FO4Port.esm, so the id in cell=
        ; is FO4Port.esm's in this run and not another plugin's in that load slot (Codex review of #560: the stage's
        ; offline_check.txt proves the source FormKeys, not the run's load order). The local id is the low 24 bits of a
        ; full plugin's id; the modulo is negative for a load index of 0x80 or more or a light plugin, and then nothing
        ; is claimed (port=none).
        int local = c.GetFormID() % 16777216
        if local > 0
            port = "" + (Game.GetFormFromFile(local, "FO4Port.esm") == (c as Form))
        endif
        cellName = c.GetFormEditorID()
    endif
    Trace(line + " cellname=" + cellName + " port=" + port)
EndFunction

; ---------------------------------------------------------------- P4: materialize / dissolve cycles

Function P4Run(int cycles, float settle)
    if P4Marker == None || P4Base == None
        Trace("p4 refused marker=" + Id(P4Marker) + " base=" + Id(P4Base))
        return
    endif
    if p4Cycles > 0 && p4Cycle < p4Cycles
        Trace("p4 refused running=True")
        return
    endif
    Actor player = Game.GetPlayer()
    ; the marker is a persistent reference of the overlay world: it reads its local position until it is moved
    ; into the player's merged world (FO4SF_MapMarkers pattern; docs/terrain/map-markers.md)
    P4Marker.MoveTo(player, 10.0, 0.0, 0.0, True, False)
    p4Cycles = cycles
    p4Cycle = 0
    p4Settle = settle
    p4Placed = 0
    p4Deleted = 0
    p4Spawned = new ObjectReference[3]
    Trace("p4 start cycles=" + cycles + " settle=" + settle + " marker=" + P4Marker.GetFormID() + " base=" + Id(P4Base) + " pos=" + P4Marker.GetPositionX() + " " + P4Marker.GetPositionY() + " " + P4Marker.GetPositionZ() + " mode=placeatme")
    StartTimer(0.1, TIMER_P4_PLACE)
EndFunction

Function P4Place()
    int placed = 0
    int i = 0
    while i < 3
        ObjectReference r = P4Marker.PlaceAtMe(P4Base, 1, False, False)
        p4Spawned[i] = r
        if r != None
            placed += 1
        endif
        i += 1
    endwhile
    p4Placed += placed
    StartTimer(p4Settle, TIMER_P4_SETTLE)
EndFunction

Function P4Dissolve()
    int loaded = 0
    int deleted = 0
    int placed = 0
    int i = 0
    while i < 3
        ObjectReference r = p4Spawned[i]
        if r != None
            placed += 1
            if r.Is3DLoaded()
                loaded += 1
            endif
            r.Disable(False)
            r.Delete()
            deleted += 1
            p4Spawned[i] = None
        endif
        i += 1
    endwhile
    p4Deleted += deleted
    p4Cycle += 1
    Trace("p4 cycle n=" + p4Cycle + " placed=" + placed + " loaded=" + loaded + " deleted=" + deleted + " mode=placeatme")
    if p4Cycle < p4Cycles
        StartTimer(0.5, TIMER_P4_PLACE)
    else
        Trace("p4 done cycles=" + p4Cycle + " placed=" + p4Placed + " deleted=" + p4Deleted)
    endif
EndFunction

; ---------------------------------------------------------------- P5: script tick over 50 places

Function P5Tick(int ticks)
    if P5Globals == None || P5Globals.Length == 0
        Trace("p5 refused globals=0")
        return
    endif
    p5Ticks = ticks
    p5TickCount = 0
    Trace("p5 start ticks=" + ticks + " places=" + P5Globals.Length + " first=" + Id(P5Globals[0]) + " last=" + Id(P5Globals[P5Globals.Length - 1]))
    StartTimer(0.1, TIMER_P5)
EndFunction

Function P5One()
    float t0 = Utility.GetCurrentRealTime()
    float sum = 0.0
    int i = 0
    int n = P5Globals.Length
    while i < n
        GlobalVariable g = P5Globals[i]
        float v = g.GetValue()
        v = v * 0.97 + i
        g.SetValue(v)
        sum += v
        i += 1
    endwhile
    float ms = (Utility.GetCurrentRealTime() - t0) * 1000.0
    p5TickCount += 1
    Trace("p5 tick n=" + p5TickCount + " places=" + n + " ms=" + ms + " sum=" + sum)
    if p5TickCount < p5Ticks
        StartTimer(0.5, TIMER_P5)
    else
        Trace("p5 done ticks=" + p5TickCount)
    endif
EndFunction

; ---------------------------------------------------------------- P6 / P7: conditioned leveled lists

string Function BaseName(Form b)
    {Which list entry a spawned actor's base is: "a", "b" or "other" (the runtime id is logged beside it).}
    if b == None
        return "none"
    elseif b == P6BaseA
        return "a"
    elseif b == P6BaseB
        return "b"
    endif
    return "other"
EndFunction

Function SpawnTrials(string probe, string head, Form list, int trials)
    Actor player = Game.GetPlayer()
    int k = 0
    while k < trials
        k += 1
        ObjectReference r = player.PlaceAtMe(list, 1, False, False)
        if r == None
            Trace(probe + " " + head + " trial=" + k + " base=none baselocal=none")
        else
            Form b = r.GetBaseObject()
            Trace(probe + " " + head + " trial=" + k + " base=" + Id(b) + " baselocal=" + BaseName(b))
            r.Disable(False)
            r.Delete()
        endif
    endwhile
EndFunction

Function P6(float datum, int trials)
    if P6List == None || Holder == None
        Trace("p6 refused list=" + Id(P6List) + " holder=" + Id(Holder))
        return
    endif
    Location l = Game.GetPlayer().GetCurrentLocation()
    if l == None
        Trace("p6 refused loc=none")
        return
    endif
    l.SetKeywordData(Holder, datum)
    string head = "datum=" + datum + " loc=" + l.GetFormID() + " readback=" + l.GetKeywordData(Holder) + " list=" + Id(P6List) + " holder=" + Id(Holder)
    SpawnTrials("p6", head, P6List, trials)
    ; the player's current location may be the core's shared overlay location: leave no datum behind
    l.SetKeywordData(Holder, 0.0)
    Trace("p6 reset loc=" + l.GetFormID() + " readback=" + l.GetKeywordData(Holder))
EndFunction

Function P7(float tier, int trials)
    if P7List == None || P7Rep == None
        Trace("p7 refused list=" + Id(P7List) + " rep=" + Id(P7Rep))
        return
    endif
    P7Rep.SetValue(tier)
    string head = "tier=" + tier + " glob=" + P7Rep.GetValue() + " list=" + Id(P7List) + " rep=" + Id(P7Rep)
    SpawnTrials("p7", head, P7List, trials)
EndFunction

; ---------------------------------------------------------------- P8: enable-parent stage swap

bool Function P8Ready()
    if P8Parents == None || P8Children == None
        Trace("p8 refused parents=none")
        return False
    endif
    if P8Parents.Length != 3 || P8Children.Length != 12
        Trace("p8 refused parents=" + P8Parents.Length + " children=" + P8Children.Length)
        return False
    endif
    return True
EndFunction

Function P8Move()
    if !P8Ready()
        return
    endif
    Actor player = Game.GetPlayer()
    int k = 0
    while k < 3
        ObjectReference stageParent = P8Parents[k]
        stageParent.MoveTo(player, 0.0, 6.0 * k, 0.0, True, False)
        int j = 0
        while j < 4
            P8Children[4 * k + j].MoveTo(player, 2.0 * j, 6.0 * k, 0.0, True, False)
            j += 1
        endwhile
        Trace("p8 move stage=" + k + " parent=" + stageParent.GetFormID() + " pos=" + stageParent.GetPositionX() + " " + stageParent.GetPositionY() + " " + stageParent.GetPositionZ())
        k += 1
    endwhile
EndFunction

Function P8Stage(int s)
    if !P8Ready()
        return
    endif
    int k = 0
    while k < 3
        if k == s
            P8Parents[k].Enable(False)
        else
            P8Parents[k].Disable(False)
        endif
        k += 1
    endwhile
    Utility.Wait(1.0)
    Trace("p8 stage=" + s)
    k = 0
    while k < 3
        bool parentDisabled = P8Parents[k].IsDisabled()
        int j = 0
        while j < 4
            Trace("p8 child stage=" + k + " j=" + j + " id=" + P8Children[4 * k + j].GetFormID() + " disabled=" + P8Children[4 * k + j].IsDisabled() + " parent_disabled=" + parentDisabled)
            j += 1
        endwhile
        k += 1
    endwhile
EndFunction

; ---------------------------------------------------------------- P9: long-route pathing tracker

Function P9PlaceDest(float dx, float dy)
    if P9Dest == None
        Trace("p9 refused dest=none")
        return
    endif
    P9Dest.MoveTo(Game.GetPlayer(), dx, dy, 0.0, True, False)
    ; On the ground, not at the player's height: P9Track measures the 3D distance, and on 1 Nov the 435 m link rung's
    ; actor stood 1.7 m from the marker across the ground and 26.8 m under it, where the land falls (#663 review).
    float before = P9Dest.GetPositionZ()
    P9Dest.MoveToNearestNavmeshLocation()
    Trace("p9 dest id=" + P9Dest.GetFormID() + " pos=" + P9Dest.GetPositionX() + " " + P9Dest.GetPositionY() + " " + P9Dest.GetPositionZ() + " snapped_dz=" + (P9Dest.GetPositionZ() - before))
EndFunction

Function P9Track(int actorId, float seconds)
    ObjectReference a = Game.GetForm(actorId) as ObjectReference
    if a == None || P9Dest == None
        Trace("p9 refused actor=" + actorId + " ref=none dest=" + Id(P9Dest))
        return
    endif
    p9Actor = a
    p9Seconds = seconds
    p9Elapsed = 0.0
    p9StartRT = Utility.GetCurrentRealTime()
    Trace("p9 start actor=" + a.GetFormID() + " seconds=" + seconds + " dist=" + a.GetDistance(P9Dest))
    P9Sample()
EndFunction

Function P9Sample()
    ObjectReference a = p9Actor
    p9Elapsed = Utility.GetCurrentRealTime() - p9StartRT   ; real seconds: a late timer must not stretch the deadline
    float dist = a.GetDistance(P9Dest)
    ; package= and player_m=: what the actor ran and how far the player was, every sample (1 Nov 2026: loaded actors
    ; stood still 95-200 s mid-route with nothing else in the log, #644); dist= stays last (the sessions read it)
    Actor act = a as Actor
    Package pk = None
    if act != None
        pk = act.GetCurrentPackage()
    endif
    Trace("p9 sample t=" + p9Elapsed + " actor=" + a.GetFormID() + " pos=" + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " cell=" + Id(a.GetParentCell()) + " loaded=" + a.Is3DLoaded() + " package=" + Id(pk) + " player_m=" + a.GetDistance(Game.GetPlayer()) + " dist=" + dist)
    if dist < 10.0 || p9Elapsed >= p9Seconds
        Trace("p9 done t=" + p9Elapsed + " dist=" + dist)
        p9Actor = None
        return
    endif
    StartTimer(P9_SAMPLE, TIMER_P9)
EndFunction

; ---------------------------------------------------------------- P10: story event plumbing

Function P10State()
    if P10Quest == None
        Trace("p10 refused quest=none")
        return
    endif
    Trace("p10 state id=" + P10Quest.GetFormID() + " local=2080 running=" + P10Quest.IsRunning())
EndFunction

; ---------------------------------------------------------------- timers: each step in its own frame

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_P4_PLACE
        P4Place()
    elseif aiTimerID == TIMER_P4_SETTLE
        P4Dissolve()
    elseif aiTimerID == TIMER_P5
        P5One()
    elseif aiTimerID == TIMER_P9
        if p9Actor != None
            P9Sample()
        endif
    endif
EndEvent
