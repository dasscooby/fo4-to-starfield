Scriptname FO4SF_WSHandQuest extends Quest
{The workshop probe by hand (fo4-to-starfield, docs/research/workshop-probe.md, "By hand"). Attached to QUST
 FO4SF_WSHandQuest (0x801 of FO4SFWorkshopProbe.esm): start game enabled, NO properties (every form is found with
 Game.GetFormFromFile). No console, no stage numbers. The quest starts with the game (load a throwaway save):
   1. 20 s after it starts it puts one "FO4SF workshop kit" (MISC 0x802, a copy of a vanilla junk item) in your
      inventory and says so on screen.
   2. DROP the kit (inventory, drop). Within a second the script sees the kit gone from your inventory and places the
      core's workshop bench 2.5 m in front of you, persistent, and gives you a new kit (the one you dropped stays on the
      floor, take it or leave it). On screen: where the bench is and what the script reads of it.
   3. You look at the bench: if the prompt reads WORKSHOP / BUILD [E] and E opens the build mode, the spawned bench is a
      workshop. If there is no prompt, the answer is no. Either way, press E on it once and write down what you saw.
   Every line on screen is also a line in the user log "FO4SFWSHand" (My Games\Starfield\Logs\Script\User\FO4SFWSHand.0.log):
   FO4SFWSHAND rt=<real time s> <event> key=value ... end=true.
 Owner kits (FAL-359 follow-up): the kit is three items, dropped one at a time: the bench kit places the core's workshop
 bench, the beacon kit places the vanilla outpost beacon (OUTPOST BEACON / BUILD [E] / RENAME, REMOVE OUTPOST [R]), the
 resource kit gives 40 Iron and 40 Aluminum (the two MISC ids the PC proved on 11 Nov) so the card needs no console. Each
 returns its kit when dropped. Lines: placed, placed_beacon, resources, say.
 Optional natives are lines that begin with ";OPT <Base.Name> ": the stager compiles each on its own (as
 FO4SF_WSProbeQuest.psc). As committed none is on: this file compiles alone.}

; ---------------------------------------------------------------- the layout (dotnet/WorkshopProbe/Program.cs)

string LogName = "FO4SFWSHand"
string ProbePlugin = "FO4SFWorkshopProbe.esm"
string CorePlugin = "FO4TerrainCore.esm"
string CorePlugin2 = "FO4TerrainCore_Mars.esm"
int KitId = 0x802           ; MISC FO4SF_WSKit: the bench
int BeaconKitId = 0x803     ; MISC FO4SF_WSBeaconKit: the outpost beacon
int ResKitId = 0x804        ; MISC FO4SF_WSResKit: gives Iron and Aluminum, then comes back
int BeaconId = 0x2C60E9     ; Starfield.esm OutpostBeaconActivator (PC survey 11 Nov)
int IronId = 0x00556E       ; Starfield.esm MISC InorgCommonIron (PC-proven 11 Nov)
int AluminumId = 0x00557D   ; Starfield.esm MISC InorgCommonAluminum (PC-proven 11 Nov)
int ResCount = 40
int BenchBaseId = 0x0A2ECD  ; the core's workshop base
int WorkshopKwId = 0x054BA7   ; KYWD of Starfield.esm
float AheadM = 2.5

; ---------------------------------------------------------------- state

int TIMER_POLL = 1
float POLL_S = 1.0
int GiveAfter = 20          ; seconds before the kit is given
int Ticks = 0
bool Given = false
int Placed = 0
int PlacedBeacons = 0
int ResGiven = 0
ObjectReference BeaconRef = None
ObjectReference BenchRef = None

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " core=" + CoreName() + " benchbase=" + Id(Game.GetFormFromFile(BenchBaseId, CoreName())) + " kit=" + Id(Game.GetFormFromFile(KitId, ProbePlugin)))
    Say("Workshop test: in 20 s you get three kits (bench, beacon, resources). Drop one to use it. Throwaway game only: do not save.")
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    {One line in the user log; on a failed write the log is opened again (as the console kit).}
    string line = "FO4SFWSHAND rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    Debug.Notification(msg)
    Trace("say text=" + msg)
EndFunction

string Function Id(Form f)
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

string Function HasWorkshopKw(ObjectReference r)
    Keyword k = Game.GetFormFromFile(WorkshopKwId, "Starfield.esm") as Keyword
    if k == None || r == None
        return "na"
    endif
    return "" + r.HasKeyword(k)
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    Form kit = Game.GetFormFromFile(KitId, ProbePlugin)
    Form bkit = Game.GetFormFromFile(BeaconKitId, ProbePlugin)
    Form rkit = Game.GetFormFromFile(ResKitId, ProbePlugin)
    Ticks += 1
    if kit == None || bkit == None || rkit == None
        if Ticks == GiveAfter
            Say("Workshop test: a kit item is not in this game (is FO4SFWorkshopProbe.esm loaded?).")
        endif
        return
    endif
    if !Given
        if Ticks >= GiveAfter
            Given = true
            p.AddItem(kit, 1, true)
            p.AddItem(bkit, 1, true)
            p.AddItem(rkit, 1, true)
            Say("You have three kits: workshop (bench), beacon (outpost beacon), resource (Iron and Aluminum). Open the inventory and DROP one: it acts where you stand.")
        endif
        return
    endif
    if p.GetItemCount(kit) < 1
        PlaceBench(p, kit)
    endif
    if p.GetItemCount(bkit) < 1
        PlaceBeacon(p, bkit)
    endif
    if p.GetItemCount(rkit) < 1
        GiveResources(p, rkit)
    endif
EndFunction

Function GiveResources(Actor p, Form rkit)
    Form iron = Game.GetFormFromFile(IronId, "Starfield.esm")
    Form alu = Game.GetFormFromFile(AluminumId, "Starfield.esm")
    p.AddItem(rkit, 1, true)
    if iron == None || alu == None
        Say("Iron or Aluminum is not in this game's Starfield.esm: nothing given.")
        return
    endif
    p.AddItem(iron, ResCount, true)
    p.AddItem(alu, ResCount, true)
    ResGiven += 1
    Trace("resources n=" + ResGiven + " iron=" + Id(iron) + " aluminum=" + Id(alu) + " count=" + ResCount + " have_iron=" + p.GetItemCount(iron) + " have_aluminum=" + p.GetItemCount(alu))
    Say("Given " + ResCount + " Iron and " + ResCount + " Aluminum (you now have " + p.GetItemCount(iron) + " and " + p.GetItemCount(alu) + ").")
EndFunction

Function PlaceBeacon(Actor p, Form bkit)
    Form base = Game.GetFormFromFile(BeaconId, "Starfield.esm")
    p.AddItem(bkit, 1, true)
    if base == None
        Say("The outpost beacon base is not in this game's Starfield.esm: no beacon placed.")
        return
    endif
    ObjectReference r = p.PlaceAtMe(base, 1, true, false, false)
    if r == None
        Say("PlaceAtMe gave no reference: no beacon placed.")
        return
    endif
    bool moved = false
;OPT ObjectReference.MoveTo     float a = p.GetAngleZ()
;OPT ObjectReference.MoveTo     r.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo     moved = true
    PlacedBeacons += 1
    BeaconRef = r
    Trace("placed_beacon n=" + PlacedBeacons + " ref=" + Id(r) + " base=" + Id(base) + " moved=" + moved + " loaded=" + r.Is3DLoaded() + " cell=" + Id(r.GetParentCell()))
    Say("Beacon " + PlacedBeacons + " placed (loaded " + r.Is3DLoaded() + "). Look at it: OUTPOST BEACON / BUILD [E]? Press E once.")
EndFunction

Function PlaceBench(Actor p, Form kit)
    Form base = Game.GetFormFromFile(BenchBaseId, CoreName())
    if base == None
        Say("The core's workshop base is not in this game (" + CoreName() + "): no bench placed.")
        p.AddItem(kit, 1, true)
        return
    endif
    ObjectReference r = p.PlaceAtMe(base, 1, true, false, false)
    if r == None
        Say("PlaceAtMe gave no reference: no bench placed.")
        p.AddItem(kit, 1, true)
        return
    endif
    bool moved = false
;OPT ObjectReference.MoveTo     if r
;OPT ObjectReference.MoveTo         float a = p.GetAngleZ()
;OPT ObjectReference.MoveTo         r.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), 0.0, false)
;OPT ObjectReference.MoveTo         moved = true
;OPT ObjectReference.MoveTo     endif
    Placed += 1
    BenchRef = r
    p.AddItem(kit, 1, true)
    Trace("placed n=" + Placed + " ref=" + Id(r) + " base=" + Id(base) + " moved=" + moved + " loaded=" + r.Is3DLoaded() + " haskw=" + HasWorkshopKw(r) + " cell=" + Id(r.GetParentCell()))
    Say("Bench " + Placed + " placed (loaded " + r.Is3DLoaded() + ", workshop keyword " + HasWorkshopKw(r) + "). Look at it: does the prompt say WORKSHOP / BUILD [E]? Press E once and write down what you saw.")
EndFunction
