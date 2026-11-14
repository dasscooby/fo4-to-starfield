Scriptname FO4SF_BPQuest extends Quest
{Fallout 4 build pieces in the outpost build menu (fo4-to-starfield, docs/research/build-pieces.md). Attached to QUST
 FO4SF_BPQuest (0x800 of FO4SFBuildPieces.esm): start game enabled, NO properties (every form is found with
 Game.GetFormFromFile, as FO4SF_WSHandQuest finds the bench). The pieces themselves are records of the plugin (shells
 0x802.., recipes 0x82A..; up to 40 of each): this script only READS and says what it finds, so a missing piece is visible without the menu.
   init        what is installed: the plugin, the core (FO4TerrainCore.esm, else the _Mars core), and for each piece the
               shell and the recipe of the plugin and the core static the shell's model was taken from
   ready       20 s later: the same counts, on screen (Debug.Notification) and in the log
 Log: My Games\Starfield\Logs\Script\User\FO4SFBP.0.log, lines "FO4SFBP rt=<real time s> <event> key=value ... end=true".
 The core ids are the stager's (make_build_pieces.py stage puts them in at the ;COREIDS line of LoadIds): as committed there are none
 and the log says so.}

; ---------------------------------------------------------------- the layout (dotnet/BuildPieces/Program.cs)

string LogName = "FO4SFBP"
string BpPlugin = "FO4SFBuildPieces.esm"
string CorePlugin = "FO4TerrainCore.esm"
string CorePlugin2 = "FO4TerrainCore_Mars.esm"
int ShellBase = 0x802
int[] CoreIds ;the stager's ids, filled in LoadIds
int[] RecipeIds ;the recipe of each piece (an entry's own, or with variants the piece's own inner recipe), filled in LoadIds

int TIMER_READY = 1
float ReadyS = 20.0

Event OnInit()
    Debug.OpenUserLog(LogName)
    LoadIds()
    Trace("init quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(BpPlugin) + " core=" + CoreName())
    Report("init")
    StartTimer(ReadyS, TIMER_READY)
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_READY
        int Found = Report("ready")
        Debug.Notification("FO4SF build pieces: " + Found + " found. Open the build menu at a workshop (CRAFTING tab).")
    endif
EndEvent

Function Trace(string msg)
    {One line in the user log; on a failed write the log is opened again.}
    string line = "FO4SFBP rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

string Function Id(Form Fm)
    if Fm == None
        return "none"
    endif
    return "" + Fm.GetFormID()
EndFunction

string Function CoreName()
    if Game.IsPluginInstalled(CorePlugin)
        return CorePlugin
    endif
    return CorePlugin2
EndFunction

Function LoadIds()
    {The core ids and the recipe ids of the pieces, one array line each; the stager replaces the next line with them (none as committed).}
    CoreIds = new int[0]
    RecipeIds = new int[0]
    ;COREIDS
EndFunction

int Function Report(string When)
    {One line per piece the stager named (a core id other than 0): shell, recipe and core static found or none. Returns the number
     of pieces whose shell AND recipe are found; the "found" line also says how many were named.}
    int Found = 0
    int Named = 0
    int N = 1
    while N <= CoreIds.Length
        int Cid = CoreIds[N - 1]
        if Cid != 0
            Named += 1
            Form ShellF = Game.GetFormFromFile(ShellBase + N - 1, BpPlugin)
            Form RecipeF = Game.GetFormFromFile(RecipeIds[N - 1], BpPlugin)
            Form CoreF = Game.GetFormFromFile(Cid, CoreName())
            Trace("piece when=" + When + " n=" + N + " shell=" + Id(ShellF) + " recipe=" + Id(RecipeF) + " coreid=" + Cid + " core=" + Id(CoreF))
            if ShellF != None && RecipeF != None
                Found += 1
            endif
        endif
        N += 1
    endwhile
    Trace("found when=" + When + " pieces=" + Found + " named=" + Named)
    return Found
EndFunction
