Scriptname FO4SF_PlanetProbeQuest extends Quest
{The planet probe (fo4-to-starfield, docs/planet/planet-probe.md). Attached to QUST FO4SF_PlanetProbe (0x814 of
 FO4SFPlanetProbe.esm: start game enabled, no stages, NO properties). Every form is found with Game.GetFormFromFile at
 the moment it is read, because a script property would make a temporary test reference persistent and spoil the
 test. The script watches the player once a second; each arrival (another worldspace, another interior cell, or a
 jump of more than 500 m) gets four readings, 2, 10, 30 and 60 s later: the player, the planet the game says the
 player is on, every test reference and the probe location. One line per finding in the user log "FO4SFPlanetProbe"
 (My Games\Starfield\Logs\Script\User\FO4SFPlanetProbe.0.log), in the fixed form
   FO4SFPP rt=<real time s> <event> key=value key=value ...
 (form ids as Papyrus prints them: signed decimal, "none" for None; bools as Starfield prints them, true / false;
 literal text may come back in another case), which src/fo4sf/planet/probe_log.py reads, ignoring case. Nothing is
 judged in game: the lines are the evidence.
 The local ids below are src/fo4sf/planet/probe.py's layout (tests/test_planet_probe.py compares the two).}

; ---------------------------------------------------------------- the layout (src/fo4sf/planet/probe.py)

int Version = 2             ; 2: the chain line asks IsChild both ways and lists each location's parents
string LogName = "FO4SFPlanetProbe"
string ProbePlugin = "FO4SFPlanetProbe.esm"
string PlanetPlugin = "FO4SFPlanet.esm"
string MergePlugin = "FO4SFMergeProbe.esm"

int T1Id = 0x800            ; REFR persistent XMarker, no location links (our core's markers)
int T2Id = 0x801            ; REFR persistent XMarker + XLCN + LCPR row
int T3Id = 0x802            ; ACHR temporary citizen in the spawn cell + XLCN + LCPR row (Bethesda's Creations)
int T4Id = 0x803            ; ACHR persistent citizen, no links (our Codsworth)
int T5Id = 0x804            ; REFR temporary XMarker in the spawn cell, no links (plain cell content)
int T6Id = 0x805            ; ACHR persistent citizen + XLCN + LCPR row
int T7Id = 0x815            ; REFR persistent XMarker in the spawn cell's own persistent group, no links (run 2)
int LocationId = 0x808      ; LCTN FO4SF_PlanetProbeLocation
int WorldId = 0x809         ; WRLD FO4SF_PlanetProbeWorld
int MergeId = 0x800         ; REFR FO4SF_MergeProbeMarker of FO4SFMergeProbe.esm (in LC172World's persistent cell)
int LC172CocId = 0x10238E   ; REFR LC172World's persistent COC marker (Starfield.esm): the merge moved it on 11 Oct
int PlanetLocId = 0x802     ; LCTN our planet (FO4SFPlanet.esm)
int SurfaceLocId = 0x804    ; LCTN our planet's surface (FO4SFPlanet.esm)
int PlanetId = 0x805        ; PNDT our planet (FO4SFPlanet.esm)
int StarSystemKwId = 0x149F     ; KYWD LocTypeStarSystem (Starfield.esm; the stage checks it against the census)
int MajorOrbitalKwId = 0x70A54  ; KYWD LocTypeMajorOrbital (Starfield.esm; the same)

; ---------------------------------------------------------------- state

string[] Tags
int[] Ids
string[] Plugins
WorldSpace ProbeWorld = None
Location ProbeLoc = None
Location SurfaceLoc = None
Location PlanetLoc = None
Planet ProbePlanet = None

int TIMER_POLL = 1
float POLL_S = 1.0
float JUMP_M = 500.0
bool Started = false
WorldSpace LastWorld = None
Cell LastCell = None
float LastX = 0.0
float LastY = 0.0
int Arrivals = 0
float ArrivalRT = 0.0
int NextReading = 4

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    Tags = new string[9]
    Ids = new int[9]
    Plugins = new string[9]
    SetRef(0, "T1", T1Id, ProbePlugin)
    SetRef(1, "T2", T2Id, ProbePlugin)
    SetRef(2, "T3", T3Id, ProbePlugin)
    SetRef(3, "T4", T4Id, ProbePlugin)
    SetRef(4, "T5", T5Id, ProbePlugin)
    SetRef(5, "T6", T6Id, ProbePlugin)
    SetRef(6, "MERGE", MergeId, MergePlugin)
    SetRef(7, "LC172COC", LC172CocId, "Starfield.esm")
    SetRef(8, "T7", T7Id, ProbePlugin)
    if Game.IsPluginInstalled(ProbePlugin)
        ProbeWorld = Game.GetFormFromFile(WorldId, ProbePlugin) as WorldSpace
        ProbeLoc = Game.GetFormFromFile(LocationId, ProbePlugin) as Location
    endif
    if Game.IsPluginInstalled(PlanetPlugin)
        ProbePlanet = Game.GetFormFromFile(PlanetId, PlanetPlugin) as Planet
        SurfaceLoc = Game.GetFormFromFile(SurfaceLocId, PlanetPlugin) as Location
        PlanetLoc = Game.GetFormFromFile(PlanetLocId, PlanetPlugin) as Location
    endif
    Trace("init version=" + Version + " quest=" + GetFormID() + " world=" + Id(ProbeWorld) + " loc=" + Id(ProbeLoc) + " planet=" + Id(ProbePlanet) + " surface=" + Id(SurfaceLoc) + " planetloc=" + Id(PlanetLoc) + " merge=" + Game.IsPluginInstalled(MergePlugin))
    Chain()
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function SetRef(int i, string tag, int id, string plugin)
    Tags[i] = tag
    Ids[i] = id
    Plugins[i] = plugin
EndFunction

Function Trace(string msg)
    {A user log is open only in the game session that opened it (Skyrim and Fallout 4; assumed here): when a write
     fails, as after a save is loaded again, the log is opened once more and the line written again.}
    string line = "FO4SFPP rt=" + Utility.GetCurrentRealTime() + " " + msg
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

string Function IdList(Location[] a)
    {The array's ids joined by commas, in its order ("<id>,<id>,..."), or "none" when it is empty or None.}
    if !a || a.Length == 0
        return "none"
    endif
    string s = Id(a[0])
    int i = 1
    while i < a.Length
        s += "," + Id(a[i])
        i += 1
    endwhile
    return s
EndFunction

Function Chain()
    {The location chain and the planet as the game resolves them, once at the start. Each IsChild is asked both ways,
     <caller>_ischild_<argument>: Starfield's Location.psc says IsChild "Returns whether the other location is a
     child of this one" (the parent asks), and ObjectReference.IsInLocation uses it so, but some vanilla quest
     scripts call it the other way (the child asks), so the log holds both and the parent lists settle it. Version 1
     asked the child only. probe_parents, surface_parents and planet_parents list every parent the game gives each
     of our three locations (GetParentLocations with no keyword, in the order it returns them; every vanilla call
     passes a keyword, so this form is untried). planet_systems, probe_orbitals and probe_systems ask the way
     SQ_ParentScript does for a planet's and a site's location (with LocTypeStarSystem or LocTypeMajorOrbital). The
     line ends with end=true, so the reader can tell a whole line from a cut one.}
    string line = "chain"
    if ProbeLoc != None && SurfaceLoc != None
        line += " surface_ischild_probe=" + SurfaceLoc.IsChild(ProbeLoc) + " probe_ischild_surface=" + ProbeLoc.IsChild(SurfaceLoc)
    endif
    if SurfaceLoc != None && PlanetLoc != None
        line += " planet_ischild_surface=" + PlanetLoc.IsChild(SurfaceLoc) + " surface_ischild_planet=" + SurfaceLoc.IsChild(PlanetLoc)
    endif
    Keyword starSystem = Game.GetFormFromFile(StarSystemKwId, "Starfield.esm") as Keyword
    Keyword majorOrbital = Game.GetFormFromFile(MajorOrbitalKwId, "Starfield.esm") as Keyword
    if ProbeLoc != None
        line += " probe_parents=" + IdList(ProbeLoc.GetParentLocations()) + " probe_planet=" + Id(ProbeLoc.GetCurrentPlanet())
        if majorOrbital != None
            line += " probe_orbitals=" + IdList(ProbeLoc.GetParentLocations(majorOrbital))
        endif
        if starSystem != None
            line += " probe_systems=" + IdList(ProbeLoc.GetParentLocations(starSystem))
        endif
    endif
    if SurfaceLoc != None
        line += " surface_parents=" + IdList(SurfaceLoc.GetParentLocations()) + " surface_planet=" + Id(SurfaceLoc.GetCurrentPlanet())
    endif
    if PlanetLoc != None
        line += " planet_parents=" + IdList(PlanetLoc.GetParentLocations())
        if starSystem != None
            line += " planet_systems=" + IdList(PlanetLoc.GetParentLocations(starSystem))
        endif
    endif
    if ProbePlanet != None
        line += " planet_location=" + Id(ProbePlanet.GetLocation()) + " gravity=" + ProbePlanet.GetGravity() + " day=" + ProbePlanet.GetDayLength() + " temp=" + ProbePlanet.GetTemperature()
    endif
    Trace(line + " end=true")
EndFunction

; ---------------------------------------------------------------- the watch

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    WorldSpace w = p.GetWorldSpace()
    Cell c = p.GetParentCell()
    float x = p.GetPositionX()
    float y = p.GetPositionY()
    float now = Utility.GetCurrentRealTime()
    bool moved = false
    if !Started
        moved = true
    elseif w != LastWorld
        moved = true
    elseif w == None && c != LastCell
        moved = true
    elseif (x - LastX) * (x - LastX) + (y - LastY) * (y - LastY) > JUMP_M * JUMP_M
        moved = true
    endif
    if moved
        Arrivals += 1
        ArrivalRT = now
        NextReading = 0
        Trace("arrive n=" + Arrivals + " world=" + Id(w) + " cell=" + Id(c) + " x=" + x + " y=" + y + " z=" + p.GetPositionZ() + " probeworld=" + (w != None && w == ProbeWorld))
    endif
    Started = true
    LastWorld = w
    LastCell = c
    LastX = x
    LastY = y
    if NextReading < 4
        float due = ReadingAt(NextReading)
        if now - ArrivalRT >= due
            Reading(Arrivals, due as int)
            NextReading += 1
        endif
    endif
EndFunction

float Function ReadingAt(int k)
    if k == 0
        return 2.0
    elseif k == 1
        return 10.0
    elseif k == 2
        return 30.0
    endif
    return 60.0
EndFunction

Function Reading(int n, int at)
    Actor p = Game.GetPlayer()
    WorldSpace w = p.GetWorldSpace()
    Location l = p.GetCurrentLocation()
    Planet pl = p.GetCurrentPlanet()
    Trace("player n=" + n + " at=" + at + " world=" + Id(w) + " cell=" + Id(p.GetParentCell()) + " loc=" + Id(l) + " planet=" + Id(pl) + " x=" + p.GetPositionX() + " y=" + p.GetPositionY() + " z=" + p.GetPositionZ() + " ourplanet=" + (pl != None && pl == ProbePlanet) + " probeloc=" + (l != None && l == ProbeLoc) + " probeworld=" + (w != None && w == ProbeWorld))
    if pl != None
        Trace("planet n=" + n + " at=" + at + " id=" + pl.GetFormID() + " gravity=" + pl.GetGravity() + " day=" + pl.GetDayLength() + " temp=" + pl.GetTemperature() + " pressure=" + pl.GetPressure() + " type=" + Id(pl.GetType()) + " atmos=" + Id(pl.GetAtmosphereType()) + " loc=" + Id(pl.GetLocation()))
    endif
    int i = 0
    while i < Tags.Length
        RefLine(n, at, i, p)
        i += 1
    endwhile
    if ProbeLoc != None
        Trace("location n=" + n + " at=" + at + " tag=probe id=" + ProbeLoc.GetFormID() + " loaded=" + ProbeLoc.IsLoaded() + " actors=" + ProbeLoc.CountActors())
    endif
EndFunction

Function RefLine(int n, int at, int i, Actor p)
    string line = "ref n=" + n + " at=" + at + " tag=" + Tags[i] + " local=" + Ids[i] + " plugin=" + Plugins[i]
    if !Game.IsPluginInstalled(Plugins[i])
        Trace(line + " installed=False")
        return
    endif
    ObjectReference r = Game.GetFormFromFile(Ids[i], Plugins[i]) as ObjectReference
    if r == None
        Trace(line + " found=False")
        return
    endif
    WorldSpace rw = r.GetWorldSpace()
    Trace(line + " found=True id=" + r.GetFormID() + " world=" + Id(rw) + " cell=" + Id(r.GetParentCell()) + " loc=" + Id(r.GetCurrentLocation()) + " editorloc=" + Id(r.GetEditorLocation()) + " x=" + r.GetPositionX() + " y=" + r.GetPositionY() + " z=" + r.GetPositionZ() + " loaded=" + r.Is3DLoaded() + " disabled=" + r.IsDisabled() + " dist=" + r.GetDistance(p) + " sameworld=" + (rw == p.GetWorldSpace()) + " actor=" + ((r as Actor) != None))
EndFunction
