Scriptname FO4SF_PAHandQuest extends Quest
{The power armor probe by hand (fo4-to-starfield, docs/research/power-armor-probe.md, "By hand"). Attached to QUST
 FO4SF_PAHandQuest (0x807) of FO4SFPowerArmorProbe.esm: start game enabled, NO properties (every form is found with
 Game.GetFormFromFile, as in FO4SF_PAProbeQuest: a property would make the temporary references persistent).
 No console, no stage numbers. The quest starts with the game (load a throwaway save that is already in the world):
   1. 30 s after it starts it says on screen that it will move you into the test room, and does (ObjectReference.MoveTo
      on the arrival marker). When the game has no such call it says on screen to type  coc FO4SF_PAProbeCell  instead.
   2. In the room it tells you what stands where: the vanilla chair to the left (the CONTROL) and the suit furniture to
      the right (a copy of that chair with the keyword FurnitureTypePowerArmor and nothing else different).
   3. Every change of the furniture the player is on is said on screen (control: sitting works; suit: what the engine did
      on activating it).
   4. Walking up to the suit (within 2 units), or 60 s in the room, runs the probe's question, Actor.SwitchToPowerArmor
      on the suit furniture, and the answer comes on screen after 1 s and again after 4 s: IsInPowerArmor, the furniture
      the player is on and its sit state, the camera state, the race, the number of armor slots worn. A reading the game
      has no call for says so in plain words.
 Everything said on screen is also one line in the user log "FO4SFPAHand" (My Games\Starfield\Logs\Script\User\
 FO4SFPAHand.0.log): FO4SFPAHAND rt=<real time s> <event> key=value ... end=true. The race swap of the probe's stage 20 is
 NOT in the hand version (it can break a save): it stays with the console probe.
 Optional readings are lines that begin with ";OPT <Base.Name> ": scripts/planet/make_power_armor_probe.py stage compiles
 each on its own and keeps the ones that compile (as FO4SF_PAProbeQuest.psc). As committed none is on: this file compiles alone.}

; ---------------------------------------------------------------- the layout (dotnet/PowerArmorProbe/Program.cs)

string LogName = "FO4SFPAHand"
string ProbePlugin = "FO4SFPowerArmorProbe.esm"
int CellId = 0x800          ; CELL FO4SF_PAProbeCell
int SuitRefId = 0x804       ; REFR the suit furniture
int ControlRefId = 0x805    ; REFR the vanilla control furniture
int CocRefId = 0x806        ; REFR the arrival marker

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_READ1 = 2
int TIMER_READ2 = 3
float POLL_S = 1.0
float READ1_S = 1.0
float READ2_S = 4.0
int StartAfter = 30         ; poll ticks (seconds) before the move into the room
float NearSuit = 2.0
int RoomLimit = 60          ; seconds in the room before the call is made anyway
int Ticks = 0
int InRoom = 0              ; seconds in the room
bool Moved = false
bool Announced = false
bool Called = false
string LastFurn = "none"
Race StartRace = None

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    StartRace = p.GetRace()
    Trace("init quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " suitref=" + Id(Ref(SuitRefId)) + " controlref=" + Id(Ref(ControlRefId)) + " cocref=" + Id(Ref(CocRefId)))
    Say("Power armor test: in 30 s you are moved into a small test room. Throwaway game only: do not save.")
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {One line in the user log; a log is open only in the session that opened it (assumed), so on a failed write it is opened again.}
    string line = "FO4SFPAHAND rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    {The on-screen message, and the same text in the log.}
    Debug.Notification(msg)
    Trace("say text=" + msg)
EndFunction

string Function Id(Form f)
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

ObjectReference Function Ref(int id)
    return Game.GetFormFromFile(id, ProbePlugin) as ObjectReference
EndFunction

; ---------------------------------------------------------------- readings ("na" = the game has no such call)

string Function FurnId(Actor p)
    string s = "na"
;OPT Actor.GetFurnitureReference     s = Id(p.GetFurnitureReference())
    return s
EndFunction

string Function SitState(Actor p)
    string s = "na"
;OPT Actor.GetSitState     s = "" + p.GetSitState()
    return s
EndFunction

string Function InPowerArmor(Actor p)
    string s = "na"
;OPT Actor.IsInPowerArmor     s = "" + p.IsInPowerArmor()
    return s
EndFunction

string Function Camera()
    string s = "na"
;OPT Game.GetCameraState     s = "" + Game.GetCameraState()
    return s
EndFunction

int Function WornCount(Actor p)
    int n = -1
;OPT Actor.GetWornItem     n = 0
;OPT Actor.GetWornItem     int slot = 0
;OPT Actor.GetWornItem     while slot < 64
;OPT Actor.GetWornItem         Actor:WornItem w = p.GetWornItem(slot)
;OPT Actor.GetWornItem         if w && w.item
;OPT Actor.GetWornItem             n += 1
;OPT Actor.GetWornItem         endif
;OPT Actor.GetWornItem         slot += 1
;OPT Actor.GetWornItem     endwhile
    return n
EndFunction

bool Function MoveIn(Actor p)
    {The player moved onto the arrival marker; false when the game declares no such call.}
    bool ok = false
;OPT ObjectReference.MoveTo     ObjectReference coc = Ref(CocRefId)
;OPT ObjectReference.MoveTo     if coc
;OPT ObjectReference.MoveTo         p.MoveTo(coc)
;OPT ObjectReference.MoveTo         ok = true
;OPT ObjectReference.MoveTo     endif
    return ok
EndFunction

string Function Na(string v, string what)
    {The reading as words for the screen.}
    if v == "na"
        return what + ": not in this game's scripts"
    endif
    return what + " " + v
EndFunction

string Function Wording(string suffix)
    {The state after the call: IsInPowerArmor, furniture and sit state, camera, race, worn armor.}
    Actor p = Game.GetPlayer()
    string race = "race unchanged"
    if p.GetRace() != StartRace
        race = "race is now " + Id(p.GetRace())
    endif
    string worn = "worn armor slots not readable"
    int n = WornCount(p)
    if n >= 0
        worn = "worn armor slots " + n
    endif
    return "Suit " + suffix + ": " + Na(InPowerArmor(p), "in power armor") + "; " + Na(FurnId(p), "furniture") + "; " + Na(SitState(p), "sit state") + "; " + Na(Camera(), "camera") + "; " + race + "; " + worn
EndFunction

; ---------------------------------------------------------------- poll

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_READ1
        Say(Wording("1 s after the call"))
    elseif aiTimerID == TIMER_READ2
        Say(Wording("4 s after the call"))
        Say("Test over. Write down what you saw, then quit without saving.")
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    Ticks += 1
    if !Moved
        if Ticks >= StartAfter
            Moved = true
            if MoveIn(p)
                Say("Moving you into the test room.")
            else
                Say("This game has no move call for scripts: open the console and type  coc FO4SF_PAProbeCell")
            endif
        endif
        return
    endif
    Cell room = Game.GetFormFromFile(CellId, ProbePlugin) as Cell
    if room == None || p.GetParentCell() != room
        return
    endif
    InRoom += 1
    if !Announced
        Announced = true
        Say("Test room: the vanilla chair is on your left (the control), the suit furniture on your right. Sit on the left one first, stand up, then walk up to the right one.")
    endif
    string furn = FurnId(p)
    if furn != LastFurn
        string before = LastFurn
        LastFurn = furn
        if furn == Id(Ref(ControlRefId))
            Say("You are on the control chair (furniture " + furn + ", sit state " + SitState(p) + "). Sitting works here.")
        elseif furn == Id(Ref(SuitRefId))
            Say("You are on the SUIT furniture " + furn + ", sit state " + SitState(p) + ", in power armor: " + InPowerArmor(p))
        elseif furn == "na"
            Say("The game cannot say which furniture you are on; watch the screen instead.")
        elseif before != "none" && before != "na"
            Say("You left the furniture " + before + ".")
        endif
    endif
    ObjectReference suit = Ref(SuitRefId)
    if !Called && suit
        if p.GetDistance(suit) < NearSuit
            Called = true
            Say("You walked up to the suit: calling SwitchToPowerArmor on it now.")
            p.SwitchToPowerArmor(suit)
            StartTimer(READ1_S, TIMER_READ1)
            StartTimer(READ2_S, TIMER_READ2)
        elseif InRoom >= RoomLimit
            Called = true
            Say("60 s in the room: calling SwitchToPowerArmor on the suit now.")
            p.SwitchToPowerArmor(suit)
            StartTimer(READ1_S, TIMER_READ1)
            StartTimer(READ2_S, TIMER_READ2)
        endif
    endif
EndFunction
