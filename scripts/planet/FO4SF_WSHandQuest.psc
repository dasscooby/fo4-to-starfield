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
 Optional natives are lines that begin with ";OPT <Base.Name> ": the stager compiles each on its own (as
 FO4SF_WSProbeQuest.psc). As committed none is on: this file compiles alone.}

; ---------------------------------------------------------------- the layout (dotnet/WorkshopProbe/Program.cs)

string LogName = "FO4SFWSHand"
string ProbePlugin = "FO4SFWorkshopProbe.esm"
string CorePlugin = "FO4TerrainCore.esm"
string CorePlugin2 = "FO4TerrainCore_Mars.esm"
int KitId = 0x802           ; MISC FO4SF_WSKit
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
ObjectReference BenchRef = None

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(ProbePlugin) + " core=" + CoreName() + " benchbase=" + Id(Game.GetFormFromFile(BenchBaseId, CoreName())) + " kit=" + Id(Game.GetFormFromFile(KitId, ProbePlugin)))
    Say("Workshop test: in 20 s you get a 'FO4SF workshop kit'. Drop it to put the bench in front of you. Throwaway game only: do not save.")
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
    Ticks += 1
    if kit == None
        if Ticks == GiveAfter
            Say("Workshop test: the kit item is not in this game (is FO4SFWorkshopProbe.esm loaded?).")
        endif
        return
    endif
    if !Given
        if Ticks >= GiveAfter
            Given = true
            p.AddItem(kit, 1, true)
            Say("You have a 'FO4SF workshop kit'. Open the inventory and DROP it: the bench appears 2.5 m in front of you.")
        endif
        return
    endif
    if p.GetItemCount(kit) < 1
        PlaceBench(p, kit)
    endif
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
