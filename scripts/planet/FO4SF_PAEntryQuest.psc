Scriptname FO4SF_PAEntryQuest extends Quest
{The power armor ENTRY by script (fo4-to-starfield, FAL-361, piece B of FAL-359; docs/research/power-armor-probe.md, "Entry by script").
 Attached to QUST FO4SF_PAEntryQuest (0x809) of FO4SFPowerArmorProbe.esm: start game enabled, NO properties (every form is found with
 Game.GetFormFromFile, as in FO4SF_PAHandQuest). No console, no stage numbers. Load a throwaway save that is already in the world:
   1. 30 s after it starts it says on screen that it will move you into the test room, and does (ObjectReference.MoveTo on the
      persistent arrival marker). When the game has no such call it says to type  coc FO4SF_PAProbeCell.
   2. In the room: the ENTRY chair (FURN FO4SF_PAEntryFurn, a copy of the vanilla chair with no keyword) stands 3 units ahead of the
      arrival; the vanilla chair on the left is the EXIT.
   3. Sitting on the entry chair puts the suit on after 2 s, in three moves, each said on screen: AddItem + EquipItem of our
      frame and two pieces (ARMO FO4SF_PAFrame, FO4SF_PAPieceHelm, FO4SF_PAPieceTorso, for HumanRace), and SetValue of our value
      FO4SF_PAInPowerArmor (AVIF) to 1. THE RACE IS NOT SWAPPED: the PC run of #733 showed the copied race has no skin (only the head
      is drawn) and refuses every armature. The state is read 1 s and 4 s later and the screen says whether it all held.
   4. Sitting on the vanilla chair (or 120 s in the suit) takes it off: the value to 0, the pieces unequipped and removed;
      again read 1 s and 4 s later.
 Everything said on screen is also one line in the user log "FO4SFPAEntry" (My Games\Starfield\Logs\Script\User\FO4SFPAEntry.0.log):
 FO4SFPAENTRY rt=<real time s> <event> key=value ... end=true. Optional readings are lines that begin with ";OPT <Base.Name> ":
 scripts/planet/make_power_armor_probe.py stage compiles each on its own and keeps the ones that compile (as FO4SF_PAHandQuest.psc);
 as committed none is on and this file compiles alone. What this does NOT do: no climb-in animation, no HUD, no Starfield power armor
 state (the keyword furniture of the console probe did nothing); the look is the pieces' art, none unless the stage was given one.}

; ---------------------------------------------------------------- the layout (dotnet/PowerArmorProbe/Program.cs)

string LogName = "FO4SFPAEntry"
string ProbePlugin = "FO4SFPowerArmorProbe.esm"
int CellId = 0x800          ; CELL FO4SF_PAProbeCell
int KitRaceId = 0x802       ; RACE FO4SF_PARace, a copy of HumanRace: only logged at init, never set (the swap removed the body)
int ControlRefId = 0x805    ; REFR the vanilla chair: the EXIT
int ArrivalRefId = 0x808    ; REFR the arrival XMarker (persistent)
int EntryRefId = 0x80B      ; REFR the entry chair (FURN FO4SF_PAEntryFurn)
int InPaId = 0x80C          ; AVIF FO4SF_PAInPowerArmor
int FrameId = 0x80D         ; ARMO FO4SF_PAFrame
int PieceHelmId = 0x80E     ; ARMO FO4SF_PAPieceHelm
int PieceTorsoId = 0x80F    ; ARMO FO4SF_PAPieceTorso

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
int TIMER_ENTER = 2
int TIMER_READ1 = 3
int TIMER_READ2 = 4
int TIMER_EXIT = 5
int TIMER_XREAD1 = 6
int TIMER_XREAD2 = 7
float POLL_S = 1.0
float SETTLE_S = 2.0
float READ1_S = 1.0
float READ2_S = 4.0
int StartAfter = 30         ; poll ticks (seconds) before the move into the room
float NearChair = 1.5       ; a seated player is 0.12 units from the chair (the console probe's control)
int SuitLimit = 120         ; seconds in the suit before it is taken off anyway
int Ticks = 0
int InSuitSeconds = 0
int Cycle = 0
int Phase = 0               ; 0 outside, 1 entry pending, 2 in the suit, 3 exit pending
bool Moved = false
bool Announced = false
bool FallbackEntryUsed = false
string LastSitText = "0"
Race StartRace = None
Form[] SavedWorn = None     ; what the player wore at entry (up to 64 distinct items), re-equipped at the exit
int SavedCount = 0          ; how many items the player's OnItemUnequipped reported while the suit went on
bool Recording = false      ; true from just before the equips until 1 s after
bool WatchOn = false        ; true when the registration for the player's OnItemUnequipped compiled in

; ---------------------------------------------------------------- init

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    StartRace = p.GetRace()
    SavedWorn = new Form[64]
    Trace("init quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " startrace=" + Id(StartRace) + " kitrace=" + Id(Game.GetFormFromFile(KitRaceId, ProbePlugin)) + " entryref=" + Id(Ref(EntryRefId)) + " controlref=" + Id(Ref(ControlRefId)) + " arrivalref=" + Id(Ref(ArrivalRefId)) + " frame=" + Id(Game.GetFormFromFile(FrameId, ProbePlugin)) + " inpa=" + Id(Game.GetFormFromFile(InPaId, ProbePlugin)))
    Say("Power armor entry test: in 30 s you are moved into a small test room. Throwaway game only: do not save.")
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {One line in the user log; a log is open only in the session that opened it (assumed), so on a failed write it is opened again.}
    string line = "FO4SFPAENTRY rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
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

string Function Id(Form thing)
    if thing == None
        return "none"
    endif
    return "" + thing.GetFormID()
EndFunction

Form Function Thing(int localId)
    return Game.GetFormFromFile(localId, ProbePlugin)
EndFunction

ObjectReference Function Ref(int localId)
    return Game.GetFormFromFile(localId, ProbePlugin) as ObjectReference
EndFunction

; ---------------------------------------------------------------- readings ("na" / -1 = the game has no such call)

string Function SitState(Actor p)
    string s = "na"
;OPT Actor.GetSitState     s = "" + p.GetSitState()
    return s
EndFunction

float Function PaValue(Actor p)
    {The player's value of ours; -999.0 when the game has no such call.}
    float v = -999.0
;OPT Actor.GetValue     ActorValue inPa = Thing(InPaId) as ActorValue
;OPT Actor.GetValue     if inPa
;OPT Actor.GetValue         v = p.GetValue(inPa)
;OPT Actor.GetValue     endif
    return v
EndFunction

Function SetPaValue(Actor p, float amount)
;OPT Actor.SetValue     ActorValue inPa = Thing(InPaId) as ActorValue
;OPT Actor.SetValue     if inPa
;OPT Actor.SetValue         p.SetValue(inPa, amount)
;OPT Actor.SetValue     endif
EndFunction

int Function EquippedCount(Actor p)
    {How many of the frame and the two pieces the player has equipped; -1 when the game has no such call.}
    int n = -1
;OPT Actor.IsEquipped     n = 0
;OPT Actor.IsEquipped     if p.IsEquipped(Thing(FrameId))
;OPT Actor.IsEquipped         n += 1
;OPT Actor.IsEquipped     endif
;OPT Actor.IsEquipped     if p.IsEquipped(Thing(PieceHelmId))
;OPT Actor.IsEquipped         n += 1
;OPT Actor.IsEquipped     endif
;OPT Actor.IsEquipped     if p.IsEquipped(Thing(PieceTorsoId))
;OPT Actor.IsEquipped         n += 1
;OPT Actor.IsEquipped     endif
    return n
EndFunction

int Function HeldCount(Actor p)
    {How many of the frame and the two pieces are in the player's bag (0 to 3).}
    int n = 0
    if p.GetItemCount(Thing(FrameId)) > 0
        n += 1
    endif
    if p.GetItemCount(Thing(PieceHelmId)) > 0
        n += 1
    endif
    if p.GetItemCount(Thing(PieceTorsoId)) > 0
        n += 1
    endif
    return n
EndFunction

bool Function IsSaved(Form aForm, int aCount)
    int i = 0
    while i < aCount
        if SavedWorn[i] == aForm
            return true
        endif
        i += 1
    endwhile
    return false
EndFunction

bool Function IsOurs(Form aForm)
    return aForm == Thing(FrameId) || aForm == Thing(PieceHelmId) || aForm == Thing(PieceTorsoId)
EndFunction

; What the player wore is learned from the game's own events (PC run of #733 at 8fe7c27e: Starfield's Actor has no GetWornItem):
; just before our three EquipItem calls the script listens to the player's OnItemUnequipped and records every base object that
; comes off while the suit goes on (ours excluded); the exit equips those again. Both lines are guesses (;OPT): the registration
; and the handler each compile on their own. Without them nothing is recorded and the screen says so.
Function WatchWorn(Actor p)
;OPT ScriptObject.RegisterForRemoteEvent     RegisterForRemoteEvent(p, "OnItemUnequipped")
;OPT ScriptObject.RegisterForRemoteEvent     WatchOn = true
EndFunction

;OPT Actor.OnItemUnequipped Event Actor.OnItemUnequipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
;OPT Actor.OnItemUnequipped     if Recording && akBaseObject && SavedCount < 64 && !IsOurs(akBaseObject) && !IsSaved(akBaseObject, SavedCount)
;OPT Actor.OnItemUnequipped         SavedWorn[SavedCount] = akBaseObject
;OPT Actor.OnItemUnequipped         SavedCount += 1
;OPT Actor.OnItemUnequipped         Trace("unequipped item=" + Id(akBaseObject))
;OPT Actor.OnItemUnequipped     endif
;OPT Actor.OnItemUnequipped EndEvent

Function RestoreWorn(Actor p)
    {Equips again what the unequipped events recorded (an item already worn stays as it is).}
    int i = 0
    while i < SavedCount
        if SavedWorn[i]
            p.EquipItem(SavedWorn[i], false, true)
        endif
        i += 1
    endwhile
EndFunction

bool Function MoveIn(Actor p)
    {The player moved onto the arrival marker; false when the game declares no such call.}
    bool ok = false
;OPT ObjectReference.MoveTo     ObjectReference coc = Ref(ArrivalRefId)
;OPT ObjectReference.MoveTo     if coc
;OPT ObjectReference.MoveTo         p.MoveTo(coc)
;OPT ObjectReference.MoveTo         ok = true
;OPT ObjectReference.MoveTo     endif
    return ok
EndFunction

string Function NaF(float v, string what)
    {The value reading as words for the screen.}
    if v == -999.0
        return what + ": not in this game's scripts"
    endif
    return what + " " + v
EndFunction

string Function Na(string v, string what)
    {The reading as words for the screen.}
    if v == "na"
        return what + ": not in this game's scripts"
    endif
    return what + " " + v
EndFunction

string Function StateText(string suffix)
    {The state: race (kit or not), items in the bag, items equipped, the value, the sit state.}
    Actor p = Game.GetPlayer()
    string raceText = "race unchanged"
    if p.GetRace() != StartRace
        raceText = "race CHANGED (" + Id(p.GetRace()) + ")"
    endif
    string worn = "equipped: not in this game's scripts"
    int n = EquippedCount(p)
    if n >= 0
        worn = "equipped " + n + " of 3"
    endif
    return suffix + ": " + raceText + "; in bag " + HeldCount(p) + " of 3; " + worn + "; " + NaF(PaValue(p), "in power armor value") + "; " + Na(SitState(p), "sit state")
EndFunction

; ---------------------------------------------------------------- the entry and the exit

Function PutOn()
    Actor p = Game.GetPlayer()
    Trace("enter cycle=" + Cycle + " " + StateText("before"))
    SavedCount = 0
    WatchWorn(p)
    if !WatchOn
        Trace("watch=na (the unequipped event is not in this game's scripts): nothing will be put back at the exit")
        Say("The game gives no word of what comes off: your own gear will not be put back at the exit.")
    endif
    Recording = true
    p.AddItem(Thing(FrameId), 1, true)
    p.AddItem(Thing(PieceHelmId), 1, true)
    p.AddItem(Thing(PieceTorsoId), 1, true)
    p.EquipItem(Thing(FrameId), false, true)
    p.EquipItem(Thing(PieceHelmId), false, true)
    p.EquipItem(Thing(PieceTorsoId), false, true)
    SetPaValue(p, 1.0)
    Phase = 2
    InSuitSeconds = 0
    Say("Suit ON requested: frame and two pieces added and equipped, value set (the race is not touched). Reading it back...")
    StartTimer(READ1_S, TIMER_READ1)
    StartTimer(READ2_S, TIMER_READ2)
EndFunction

Function TakeOff()
    Actor p = Game.GetPlayer()
    Trace("exit cycle=" + Cycle + " " + StateText("before"))
    SetPaValue(p, 0.0)
    p.UnequipItem(Thing(FrameId), false, true)
    p.UnequipItem(Thing(PieceHelmId), false, true)
    p.UnequipItem(Thing(PieceTorsoId), false, true)
    p.RemoveItem(Thing(FrameId), 1, true)
    p.RemoveItem(Thing(PieceHelmId), 1, true)
    p.RemoveItem(Thing(PieceTorsoId), 1, true)
    RestoreWorn(p)
    Trace("restored worn=" + SavedCount + " watch=" + WatchOn)
    Phase = 0
    Say("Suit OFF requested: value cleared, pieces unequipped and removed, your " + SavedCount + " pieces of gear put back. Reading it back...")
    StartTimer(READ1_S, TIMER_XREAD1)
    StartTimer(READ2_S, TIMER_XREAD2)
EndFunction

Function EntryVerdict()
    {Did all four things hold 4 s after the entry? The screen says which did not.}
    Actor p = Game.GetPlayer()
    string missing = ""
    if p.GetRace() != StartRace
        missing += " race-changed"
    endif
    if HeldCount(p) < 3
        missing += " items-in-bag"
    endif
    if EquippedCount(p) >= 0 && EquippedCount(p) < 3
        missing += " items-equipped"
    endif
    if PaValue(p) > -998.0 && PaValue(p) < 0.5
        missing += " value"
    endif
    if missing == ""
        Say("Result: the suit is ON. Pieces and value hold, race untouched. Look at the character in first person (F) and third person.")
    else
        Say("Result: the suit is only partly on. Did not hold:" + missing + ". Write down what you see.")
    endif
EndFunction

Function ExitVerdict()
    {Did everything go back 4 s after the exit?}
    Actor p = Game.GetPlayer()
    string left = ""
    if p.GetRace() != StartRace
        left += " race-changed"
    endif
    if HeldCount(p) > 0
        left += " items-in-bag"
    endif
    if EquippedCount(p) > 0
        left += " items-equipped"
    endif
    if PaValue(p) > 0.5
        left += " value"
    endif
    if left == ""
        Say("Result: the suit is OFF. Pieces and value are back as they were. Sit on the new chair to do it again, or quit without saving.")
    else
        Say("Result: the exit did NOT undo everything. Still set:" + left + ". Write down what you see.")
    endif
EndFunction

; ---------------------------------------------------------------- poll

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_ENTER
        PutOn()
    elseif aiTimerID == TIMER_EXIT
        TakeOff()
    elseif aiTimerID == TIMER_READ1
        Recording = false
        Trace("saved worn=" + SavedCount + " watch=" + WatchOn)
        Say(StateText("Suit 1 s after the entry") + "; your gear that came off: " + SavedCount)
    elseif aiTimerID == TIMER_READ2
        Say(StateText("Suit 4 s after the entry"))
        EntryVerdict()
    elseif aiTimerID == TIMER_XREAD1
        Say(StateText("1 s after the exit"))
    elseif aiTimerID == TIMER_XREAD2
        Say(StateText("4 s after the exit"))
        ExitVerdict()
        Cycle += 1
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
    if !Announced
        Announced = true
        Say("Test room: the ENTRY chair is 3 units ahead of you. Sit on it and the suit goes on. The vanilla chair on your left is the EXIT: sit on it to take the suit off.")
    endif
    string sitText = SitState(p)
    if sitText != LastSitText
        LastSitText = sitText
        Trace("sit state=" + sitText + " phase=" + Phase)
    endif
    ObjectReference entryChair = Ref(EntryRefId)
    ObjectReference exitChair = Ref(ControlRefId)
    if entryChair == None || exitChair == None
        return
    endif
    if Phase == 0
        if sitText == "3" && p.GetDistance(entryChair) < NearChair
            Phase = 1
            Say("You sat on the entry chair (sit state 3): the suit goes on in 2 s.")
            StartTimer(SETTLE_S, TIMER_ENTER)
        elseif sitText == "na" && !FallbackEntryUsed && p.GetDistance(entryChair) < NearChair
            ; no sit state in this game's scripts: the first walk up to the chair is the trigger, once
            FallbackEntryUsed = true
            Phase = 1
            Say("You are at the entry chair (sit state not readable): the suit goes on in 2 s.")
            StartTimer(SETTLE_S, TIMER_ENTER)
        endif
    elseif Phase == 2
        InSuitSeconds += 1
        if sitText == "3" && p.GetDistance(exitChair) < NearChair
            Phase = 3
            Say("You sat on the exit chair (sit state 3): the suit comes off in 2 s.")
            StartTimer(SETTLE_S, TIMER_EXIT)
        elseif InSuitSeconds >= SuitLimit
            Phase = 3
            Say("120 s in the suit: taking it off now.")
            StartTimer(READ1_S, TIMER_EXIT)
        endif
    endif
EndFunction
