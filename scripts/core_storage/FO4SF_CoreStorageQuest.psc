Scriptname FO4SF_CoreStorageQuest extends Quest
{The core storage probe (fo4-to-starfield, FAL-208; dotnet/CoreStorage). Attached to QUST FO4SF_CoreStorageProbe (0x802 of
 FO4SFCoreStorage.esm: start game enabled, no stages, NO properties). Every form is found with Game.GetFormFromFile at
 the moment it is read, because a script property would make a temporary reference persistent and spoil the test.
 CS_P (0x800) is a persistent XMarker in the persistent group of the core's spawn cell FO4Core_RedRocketSpawn, CS_T (0x801)
 a temporary one in its temporary group. The script watches the player once a second; each arrival (another worldspace,
 another interior cell, or a jump of more than 500 m) gets four readings, 2, 10, 30 and 60 s later: the player and each
 of the two references. One line per finding in the user log "FO4SFCoreStorage"
 (My Games\Starfield\Logs\Script\User\FO4SFCoreStorage.0.log), in the fixed form
   FO4SFCS rt=<real time s> <event> key=value key=value ...
 (form ids as Papyrus prints them: signed decimal, "none" for None; bools as Starfield prints them, true / false;
 literal text may come back in another case). Nothing is judged in game: the lines are the evidence.
 Verdicts (PC session): CS_T not found = cell not loaded (not a failure); CS_T found and CS_P with the player = PASS;
 CS_T found and CS_P left behind or not found = FAIL.}

string LogName = "FO4SFCoreStorage"
string Plugin = "FO4SFCoreStorage.esm"
int PersistentId = 0x800    ; REFR FO4SF_CS_P: persistent XMarker in the spawn cell's persistent group (marker + 4 m)
int TemporaryId = 0x801     ; REFR FO4SF_CS_T: temporary XMarker in the spawn cell's temporary group (marker + 8 m)

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

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(Plugin))
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {Re-opens the log and writes the line again when a write fails (the log is open only in the session that opened it).}
    string line = "FO4SFCS rt=" + Utility.GetCurrentRealTime() + " " + msg
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
        Trace("arrive n=" + Arrivals + " world=" + Id(w) + " cell=" + Id(c) + " x=" + x + " y=" + y + " z=" + p.GetPositionZ())
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
    Trace("player n=" + n + " at=" + at + " world=" + Id(p.GetWorldSpace()) + " cell=" + Id(p.GetParentCell()) + " x=" + p.GetPositionX() + " y=" + p.GetPositionY() + " z=" + p.GetPositionZ())
    RefLine(n, at, "CS_P", PersistentId, p)
    RefLine(n, at, "CS_T", TemporaryId, p)
EndFunction

Function RefLine(int n, int at, string tag, int localId, Actor p)
    string line = "ref n=" + n + " at=" + at + " tag=" + tag + " local=" + localId + " plugin=" + Plugin
    if !Game.IsPluginInstalled(Plugin)
        Trace(line + " installed=False")
        return
    endif
    ObjectReference r = Game.GetFormFromFile(localId, Plugin) as ObjectReference
    if r == None
        Trace(line + " found=False")
        return
    endif
    WorldSpace rw = r.GetWorldSpace()
    Trace(line + " found=True id=" + r.GetFormID() + " world=" + Id(rw) + " cell=" + Id(r.GetParentCell()) + " x=" + r.GetPositionX() + " y=" + r.GetPositionY() + " z=" + r.GetPositionZ() + " loaded=" + r.Is3DLoaded() + " disabled=" + r.IsDisabled() + " dist=" + r.GetDistance(p) + " sameworld=" + (rw == p.GetWorldSpace()))
EndFunction
