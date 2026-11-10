Scriptname FO4SF_Min00Quest extends Quest
{A cut-down "When Freedom Calls" (fo4-to-starfield, docs/mission/when-freedom-calls.md): the Concord raiders,
 Preston Garvey and the reward, driven by a one-second check instead of FO4's triggers, scenes and fragments.
 Stages: 10 started (find Preston), 20 the fight started, 30 the raiders are dead (talk to Preston), 40 talked to
 Preston (the reward), 200 complete. Every stage change and a status line every 5 s go to the user log
 "fo4sf_mission" (My Games\Starfield\Logs\Script\User\fo4sf_mission.0.log), the evidence of a run.}

Actor Property Preston Auto Const Mandatory
{Preston's placed actor (FO4SFMission.esm 0x802).}

Actor[] Property Raiders Auto Const Mandatory
{The Concord raiders' placed actors (FO4SFMission.esm 0x803 on).}

MiscObject Property Credits Auto Const Mandatory
{Starfield's credits: the reward that stands in for Fallout 4's caps.}

Actor Property Codsworth Auto Const
{Codsworth's placed actor (FO4SFMission.esm 0x811), set only on his keeper quest (FO4SF_CodsworthKeeper, 0x814); None
 on FO4SF_Min00 and in a --no-codsworth build. Not part of the mission.}

bool Property KeeperOnly = False Auto Const
{True on FO4SF_CodsworthKeeper: this instance only keeps Codsworth (enabled, put back at his merged spot, PlaceCodsworth)
 and Preston (put back at his merged spot, KeepPreston) and never runs the mission. A quest of its own because a new
 start-game-enabled quest starts on an existing save, where FO4SF_Min00 had already ended (stage 200 cancels timer 1,
 which started his timer) or ran OnQuestInit before his timer existed: the owner's save, 22 Oct, had him unmoved and no
 mission log.}

float Property MergeOffsetX = -1200.0 Auto Const
float Property MergeOffsetY = -2700.0 Auto Const
{The core world's merge offset (vmad_patch.MERGE_MEASURED, measured in game): the world the player walks in places the
 core's records at their local position + this; z unchanged. Persistent references of the core's persistent cell stay
 at their LOCAL position in the base world (probe (a), 16 Oct; in game 18 Oct: GetDistance to Preston stayed at float max
 with the player standing on his merged spot), so the quest moves its actors over (Relocate).}

float Property RelocateRadius = 800.0 Auto Const
{Move an actor only when the player stands outdoors within this many units of that actor's merged spot (its position +
 the merge offset). Coordinates alone cannot tell two exterior worlds apart; see docs/mission/when-freedom-calls.md.}

float Property RelocateGap = 1500.0 Auto Const
{...and Preston is farther than this from the player. Unmoved he reads float max (another world, 18 Oct 13:25) or about
 2,955 (the offset's length: same world at his local spot, 18 Oct 14:40); moved he is within RelocateRadius.}

float Property PrestonLocalX = -811.14 Auto Const
float Property PrestonLocalY = 1002.46 Auto Const
float Property PrestonLocalZ = 89.09 Auto Const
{Preston's spot in the plugin (ACHR 0x802, the museum door's outside arrival: points.json "preston" pos). His merged spot
 is this + the merge offset, (-2011.14, -1697.54, 89.09), where the moves put him in game 28 Oct. Fixed, so a Preston
 who drifted or was offset twice goes back to the same spot (PlacePreston). make_mission.py stage refuses a build whose
 points differ from these.}

float Property CodsworthLocalX = -1146.709 Auto Const
float Property CodsworthLocalY = 1293.837 Auto Const
float Property CodsworthLocalZ = 111.734 Auto Const
{Codsworth's spot in the plugin (ACHR 0x811, Fallout 4's ACHR 01CA7D: points.json "codsworth" pos). His merged spot is
 this + the merge offset, (-2346.709, -1406.163, 111.734), where every logged move put him (23 and 31 Oct). Fixed, as
 Preston's (PlaceCodsworth, FAL-163). make_mission.py stage refuses a build whose points differ from these.}

float Property PlaceRadius = 300.0 Auto Const
{Preston and Codsworth are placed only when the player stands outdoors within this many m of their merged spot, so they
 land in a loaded cell. PC logs of 31 Oct: moves made from 488 to 545 m away ended with cell=None and did not hold; the
 raiders' moves from 198 to 353 m away ended in a loaded cell (Surface 04000DEF) and held; Codsworth's, from 122 m,
 ended in a loaded cell (Surface 04000D30). Chosen below 353.}

float Property HoldRadius = 25.0 Auto Const
{Preston (Codsworth) counts as at his spot within this many m of it (and within RelocateGap of the player); farther, he
 is put back, except while he fights. On 31 Oct Preston stood 100 to 450 m off it and nothing moved him again. Chosen
 above FindRadius.}

int Property RewardCount = 100 Auto Const
{Fallout 4 gives 100 caps (DialogueConcordArea stage 40).}

float Property CodsworthCheck = 5.0 Auto Const
{Seconds between the keeper's relocation checks (KeepCodsworth, KeepPreston).}

int Property KeeperStatusEvery = 12 Auto Const
{The keeper logs where Preston and Codsworth are every this many checks (12 x 5 s = a minute), and at each save load.
 Chosen.}

float Property EngageRadius = 60.0 Auto Const
{The fight starts when the player comes this close (m) to a living raider, as FO4's DN092 StartCombat on its ambush.}

float Property FindRadius = 20.0 Auto Const
{...or, before the fight, comes this close (m) to Preston or activates him: the stage 10 objective ("Find the Last
 Minutemen") is met. In game 28 Oct (new game run 3) the player walked to Preston's marker and activated him five times
 at stage 10 with every raider 91 to 129 m away, past EngageRadius, so nothing started the fight. Chosen, not copied.}

float Property TalkRadius = 3.0 Auto Const
{Standing this close (m) to Preston counts as talking to him once the raiders are dead (no dialogue ported yet).}

string LogName = "fo4sf_mission"
int ticks = 0
int relocateFails = 0
int codsworthFails = 0
int prestonFails = 0
int keeperChecks = 0
int prestonMoves = 0
float prestonOff = -1.0
string prestonState = "none"
int codsworthMoves = 0
float codsworthOff = -1.0
string codsworthState = "none"
bool codsworthKept = False
int applied = 0
bool prestonFound = False

Event OnQuestInit()
    if KeeperOnly
        Trace("keeper init codsworth=" + Codsworth)
        RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
        KeepCodsworthLoad()
        return
    endif
    Debug.OpenUserLog(LogName)
    Trace("init raiders=" + Raiders.Length)
    RegisterForRemoteEvent(Preston, "OnActivate")
    Preston.IgnoreFriendlyHits(True)                     ; a stray shot in the fight must not turn him (in game 18 Oct 15:16)
    AdvanceTo(10)
    SetActive(True)                                      ; tracked, so the objectives show (in game 18 Oct: none seen)
    StartTimer(1.0, 1)
    KeepCodsworthStart()
EndEvent

Function KeepCodsworthStart()
{Starts Codsworth's own check once (review 20 Oct); also from the mission timer, for a save that ran OnQuestInit before
 this check existed.}
    if Codsworth != None && !codsworthKept
        codsworthKept = True
        StartTimer(CodsworthCheck, 2)
    endif
EndFunction

Function KeepCodsworthLoad()
{The keeper's start, at its init and on every save load: Codsworth enabled, fresh budgets of failed moves for him and
 Preston, one line each of where they are (in the log and on screen), the timer (re)started. A load also restarts a
 check that spent its budget in an earlier session. A missing Codsworth no longer stops Preston's keeping (FAL-128).}
    if Codsworth != None
        if Codsworth.IsDisabled()
            Codsworth.Enable()
            Trace("codsworth was disabled: enabled")
        endif
        codsworthFails = 0
        codsworthKept = True
    endif
    prestonFails = 0
    TracePreston("keeper load")
    Debug.Notification("FO4SF keeper: Preston " + (prestonOff as int) + " m from his spot (last: " + prestonState + ", moves " + prestonMoves + ")")
    if Codsworth != None
        TraceCodsworth("keeper load")
        Debug.Notification("FO4SF keeper: Codsworth " + (codsworthOff as int) + " m from his spot (last: " + codsworthState + ", moves " + codsworthMoves + ")")
    endif
    StartTimer(CodsworthCheck, 2)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    if KeeperOnly
        KeepCodsworthLoad()
    endif
EndEvent

Function AdvanceTo(int n)
{SetStage, then the stage's actions. In game 18 Oct the stages reached 40 but OnStageSet never ran (no "stage" line, no
 objectives, no reward), so the actions do not rely on it; it still calls Apply, and Apply runs each stage once.}
    SetStage(n)
    Apply(n)
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    Apply(auiStageID)
EndEvent

Function Apply(int auiStageID)
    if auiStageID <= applied
        return
    endif
    applied = auiStageID
    Trace("stage " + auiStageID)
    if auiStageID == 10
        SetObjectiveDisplayed(10)
        Debug.Notification("When Freedom Calls: find the Last Minutemen")
    elseif auiStageID == 20
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(85)
        Debug.Notification("When Freedom Calls: kill the raiders")
    elseif auiStageID == 30
        Preston.StopCombat()                             ; in game 18 Oct: downed in the fight, he got up and shot the player
        SetObjectiveCompleted(85)
        SetObjectiveDisplayed(86)
        Debug.Notification("When Freedom Calls: talk to Preston Garvey")
    elseif auiStageID == 40
        SetObjectiveCompleted(86)
        Game.GetPlayer().AddItem(Credits, RewardCount)
        Trace("reward credits=" + RewardCount)
    elseif auiStageID == 200
        Debug.Notification("When Freedom Calls: complete")
        CancelTimer(1)
    endif
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if akSender == Preston && akActionRef == Game.GetPlayer()
        int stage = GetStage()
        Trace("preston activated at stage " + stage)
        if stage < 20
            FoundPreston("activated")                    ; the next check starts the fight
        elseif stage == 30
            AdvanceTo(40)
        endif
    endif
EndEvent

Function FoundPreston(string how)
{The player reached Preston before the fight (activated him, or came within FindRadius): the fight starts at the next
 check, with every raider put into combat with the player. Logged once. A dead Preston is never found (his death is
 the quest's failure path).}
    if !prestonFound && !Preston.IsDead()
        prestonFound = True
        Trace("found preston " + how)
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == 2
        KeepCodsworth()
        return
    elseif aiTimerID != 1
        return
    endif
    Actor player = Game.GetPlayer()
    KeepCodsworthStart()
    if relocateFails < 10
        Relocate(player)
    endif
    int stage = GetStage()
    float dp = player.GetDistance(Preston)
    if stage < 20 && dp < FindRadius
        FoundPreston("near d=" + dp)
    endif
    bool everyone = prestonFound || stage >= 20          ; once the fight is on, no raider stands by
    int dead = 0
    bool fighting = false
    float nearest = -1.0
    int i = 0
    while i < Raiders.Length
        Actor r = Raiders[i]
        if r.IsDead()
            dead += 1
        else
            float d = player.GetDistance(r)
            if nearest < 0.0 || d < nearest
                nearest = d
            endif
            if r.GetCombatState() != 0
                fighting = true
            elseif stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()
                ; FO4's forced fight: a living raider that is not fighting is put into combat, near the player or once
                ; the fight is on (our raider never engages unprompted, npc_combat_c1)
                r.StartCombat(player)
                fighting = true
                Trace("startcombat raider " + i + " d=" + d)
            endif
        endif
        i += 1
    endwhile
    int target = NextStage(stage, dead, Raiders.Length, fighting, dp < TalkRadius, prestonFound)
    ; every stage on the way is set in order, so each one's objectives and log line happen
    while stage < target && stage < 40
        if stage < 20
            stage = 20
        elseif stage < 30
            stage = 30
        else
            stage = 40
        endif
        AdvanceTo(stage)
    endwhile
    ticks += 1
    if ticks % 5 == 0
        Trace("status stage=" + stage + " dead=" + dead + "/" + Raiders.Length + " nearest_raider=" + nearest + " preston=" + dp + " preston_off=" + prestonOff + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
    endif
    if Preston.GetCombatTarget() == player               ; he never fights the player (in game 18 Oct: "treats me like an enemy")
        Preston.StopCombat()
        Trace("preston was targeting the player: stopcombat")
    endif
    if GetStage() == 40                                  ; in game 18 Oct the status stayed at 40 after the reward: set 200
        AdvanceTo(200)
        CompleteQuest()
        Trace("complete stage=" + GetStage())
    endif
    if GetStage() < 200                                  ; stage 200 cancels the timer (Apply)
        StartTimer(1.0, 1)
    endif
EndEvent

int Function NextStage(int stage, int dead, int total, bool fighting, bool atPreston, bool found)
{The stage the encounter has reached, whoever started the fight (scripts/mission/make_mission.py next_stage is the
 same rule, tested there): the fight counts as started when a raider fights or is dead, so a quest that starts or
 reloads mid-fight, or after the raiders died between two checks, still advances, and when the player has found
 Preston (FoundPreston), even before a raider's 3D is loaded; all raiders dead is stage 30; standing at Preston after
 that is stage 40. Never goes back.}
    int s = stage
    if s < 20 && (fighting || dead > 0 || found)
        s = 20
    endif
    if s < 30 && total > 0 && dead == total
        s = 30
    endif
    if s == 30 && atPreston
        s = 40
    endif
    return s
EndFunction

Function Relocate(Actor player)
{Moves the raiders (Codsworth: KeepCodsworth) from their unmerged local position to the same spot in the merged world the
 player walks in: each actor's local position + the merge offset, z kept (MoveTo onto the player with the difference as
 the offset, the verified MoveTo form of FO4SF_LoadDoor and FO4SF_Probe; MoveOver), and puts Preston at his fixed spot
 (PlacePreston). Decided per actor and by position, every check: in game 18 Oct 14:40 the unmoved actors read a finite
 distance (same world, local spot), so "finite means reachable" skipped the move. An actor a move missed is tried
 again (Codex 5564899342), up to 10 failed moves in all. Never from an interior.}
    if player.IsInInterior()
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if PlacePreston(player, "mission")
        relocateFails += 1
    endif
    int i = 0
    while i < Raiders.Length
        if MoveOver(Raiders[i], player, px, py, pz, "raider " + i)
            relocateFails += 1
        endif
        i += 1
    endwhile
EndFunction

Function KeepCodsworth()
{Codsworth is not part of the quest, so he has his own check every CodsworthCheck seconds with its own budget of 10
 failed moves. It keeps running after stage 200, which ends the mission's timer: the player may reach Sanctuary only
 after the mission, and he goes back to his unmerged spot (in game 18 Oct 15:17; 29 Oct, within about three minutes).
 He has Preston's rule, one fixed spot (PlaceCodsworth, FAL-163); a spent budget is logged and shown on screen, and where
 he is goes to the log every KeeperStatusEvery checks. On the keeper, Preston's check runs whether or not Codsworth is
 there (FAL-128); FO4SF_Min00 (no Codsworth) on a save that ran this timer before the keeper does nothing and lets it
 end.}
    Actor player = Game.GetPlayer()
    if Codsworth != None && codsworthFails < 10
        if PlaceCodsworth(player)
            codsworthFails += 1
            if codsworthFails >= 10
                codsworthState = "gave up"
                Trace("keeper gave up codsworth fails=" + codsworthFails)
                Debug.Notification("FO4SF keeper: Codsworth not placed after 10 tries; stopped until the next load")
            endif
        endif
    endif
    if KeeperOnly
        KeepPreston(player)
        if Codsworth != None && keeperChecks % KeeperStatusEvery == 0
            TraceCodsworth("keeper status")
        endif
    endif
    if (Codsworth != None && codsworthFails < 10) || (KeeperOnly && prestonFails < 10)
        StartTimer(CodsworthCheck, 2)
    endif
EndFunction

Function KeepPreston(Actor player)
{The keeper keeps Preston at his merged spot after the mission too. Stage 200 ends the mission's 1 s check and with it
 Relocate, while in game 19 Oct he read his unmerged spot again 5 times in one session (snap-back, supported
 hypothesis: he returns to his editor location as his cell reloads). So once the mission was complete, nothing put him
 back: the owner's report of 7 Nov, "no preston garvy after misson finshes". No new placement: the same fixed spot and
 rule as the mission (PlacePreston), with its own budget of 10 failed moves; a spent budget is logged and shown on
 screen. Where he is goes to the log every KeeperStatusEvery checks.}
    if prestonFails < 10
        if PlacePreston(player, "keeper")
            prestonFails += 1
            if prestonFails >= 10
                prestonState = "gave up"
                Trace("keeper gave up preston fails=" + prestonFails)
                Debug.Notification("FO4SF keeper: Preston not placed after 10 tries; stopped until the next load")
            endif
        endif
    endif
    keeperChecks += 1
    if keeperChecks % KeeperStatusEvery == 0
        TracePreston("keeper status")
    endif
EndFunction

bool Function PlacePreston(Actor player, string who)
{Preston's fixed spot (FAL-128): PrestonLocalX/Y/Z + the merge offset, by PlaceAt. Returns True for a failed move: one
 that leaves him off his spot. The PC's 31 Oct logs: MoveOver judged "already moved" by his distance to the PLAYER (under
 RelocateGap), so a Preston who landed or wandered 100 to 450 m off his spot was never moved again, and it took his
 target from where he stood, so a moved actor could be offset a second time, about 2,955 m away (the raiders were,
 31 Oct 16:33). The state stays readable without a log: sqv shows prestonState, prestonOff and prestonMoves.}
    float tx = PrestonLocalX + MergeOffsetX
    float ty = PrestonLocalY + MergeOffsetY
    float tz = PrestonLocalZ
    prestonState = PlaceAt(Preston, "Preston", tx, ty, tz, player, who, "at the museum door")
    prestonOff = SpotOff(Preston, tx, ty, tz)
    if prestonState == "placed" || prestonState == "move failed"
        prestonMoves += 1
    endif
    return prestonState == "move failed"
EndFunction

bool Function PlaceCodsworth(Actor player)
{Codsworth's fixed spot (FAL-163): CodsworthLocalX/Y/Z + the merge offset, by PlaceAt, Preston's rule; only the keeper
 places him. Returns True for a failed move. The PC's 31 Oct logs: MoveOver moved him once per session, from 122 m, and
 never again, since under RelocateGap from the player counted as "already moved"; it moved from up to RelocateRadius
 (800) away, where Preston's moves ended with cell=None; and on 29 Oct he was back at his unmerged spot within about
 three minutes. sqv shows codsworthState, codsworthOff and codsworthMoves.}
    float tx = CodsworthLocalX + MergeOffsetX
    float ty = CodsworthLocalY + MergeOffsetY
    float tz = CodsworthLocalZ
    codsworthState = PlaceAt(Codsworth, "Codsworth", tx, ty, tz, player, "keeper", "in Sanctuary")
    codsworthOff = SpotOff(Codsworth, tx, ty, tz)
    if codsworthState == "placed" || codsworthState == "move failed"
        codsworthMoves += 1
    endif
    return codsworthState == "move failed"
EndFunction

string Function PlaceAt(Actor a, string name, float tx, float ty, float tz, Actor player, string who, string where)
{The fixed-spot rule of Preston (FAL-128) and Codsworth (FAL-163): puts the actor at its merged spot (tx, ty, tz) when it
 is not there, the player stands outdoors within PlaceRadius of it and it is not fighting. At its spot means within
 HoldRadius of it and within RelocateGap of the player. Returns the actor's state: "at spot", "off, player inside", "off,
 player away", "off, fighting", "placed", or "move failed" (a move that leaves it off its spot). Each move is logged
 ("moved <name> ... by=<who>") and shown on screen. The game prints a name as the property it matches (31 Oct:
 "moved Codsworth" from the literal "codsworth"), so make_mission.py log reads the lines case-insensitively.}
    float dp = player.GetDistance(a)                      ; float max: another world
    float off = SpotOff(a, tx, ty, tz)
    if off <= HoldRadius && dp < RelocateGap
        return "at spot"
    endif
    if player.IsInInterior()
        return "off, player inside"
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if (px - tx) * (px - tx) + (py - ty) * (py - ty) > PlaceRadius * PlaceRadius
        return "off, player away"
    endif
    if dp < RelocateGap && a.GetCombatState() != 0
        return "off, fighting"                            ; the fight moves it; it is put back once the fight is over
    endif
    Trace("world " + name + " player=" + player.GetWorldSpace() + " actor=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    a.MoveTo(player, tx - px, ty - py, tz - pz, True, False)
    float d = player.GetDistance(a)
    float after = SpotOff(a, tx, ty, tz)
    bool failed = after > HoldRadius || d >= RelocateGap
    Trace("world " + name + " after=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    Trace("moved " + name + " to " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " target " + tx + " " + ty + " " + tz + " before=" + dp + " off=" + off + " d=" + d + " failed=" + failed + " by=" + who)
    Debug.Notification("FO4SF: " + name + " put back " + where + " (" + who + ", was " + (off as int) + " m off, failed=" + failed + ")")
    if failed
        return "move failed"
    endif
    return "placed"
EndFunction

float Function SpotOff(Actor a, float tx, float ty, float tz)
{An actor's distance (m) from a point, by position only: positions cannot tell two worlds apart, so PlaceAt also wants
 it within RelocateGap of the player.}
    float ex = a.GetPositionX() - tx
    float ey = a.GetPositionY() - ty
    float ez = a.GetPositionZ() - tz
    return Math.Sqrt(ex * ex + ey * ey + ez * ez)
EndFunction

Function TracePreston(string what)
    prestonOff = SpotOff(Preston, PrestonLocalX + MergeOffsetX, PrestonLocalY + MergeOffsetY, PrestonLocalZ)
    TraceSpot(what, Preston, "preston", prestonOff, prestonState, prestonMoves, prestonFails)
EndFunction

Function TraceCodsworth(string what)
    codsworthOff = SpotOff(Codsworth, CodsworthLocalX + MergeOffsetX, CodsworthLocalY + MergeOffsetY, CodsworthLocalZ)
    TraceSpot(what, Codsworth, "codsworth", codsworthOff, codsworthState, codsworthMoves, codsworthFails)
EndFunction

Function TraceSpot(string what, Actor a, string name, float off, string spotState, int moves, int fails)
{One keeper line of where an actor is: "<what> <name> d= off= state= moves= at x y z disabled= dead= fails= player=x y z
 interior=" (keeper load / keeper status). (State is a Papyrus keyword, so the parameter is spotState.)}
    Actor player = Game.GetPlayer()
    Trace(what + " " + name + " d=" + player.GetDistance(a) + " off=" + off + " state=" + spotState + " moves=" + moves + " at " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " disabled=" + a.IsDisabled() + " dead=" + a.IsDead() + " fails=" + fails + " player=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " interior=" + player.IsInInterior())
EndFunction

bool Function MoveOver(Actor a, Actor player, float px, float py, float pz, string what)
{Moves one raider (Preston: PlacePreston; Codsworth: PlaceCodsworth) when the player is within RelocateRadius of its
 merged spot and it is still farther than RelocateGap. Returns True for a failed move: one that leaves it farther than
 RelocateGap. Its target is where the raider stands + the offset, so it moves only a raider at its unmerged spot, whose
 target is within RelocateRadius of Preston's merged spot (the plugin takes the raiders within 120 m of his spot). A
 raider already moved stands about one offset length (2,955 m) from there: the PC's 31 Oct logs (16:33, the player about
 that far south-west of them) had all five offset a second time, to (-3000..-3150, -4500..-4600) (FAL-163).}
    float before = player.GetDistance(a)                  ; float max: another world; finite: this world (the world proof)
    if before < RelocateGap
        return False                                      ; already where the player is
    endif
    float x = a.GetPositionX() + MergeOffsetX
    float y = a.GetPositionY() + MergeOffsetY
    float z = a.GetPositionZ()
    float dx = px - x
    float dy = py - y
    if dx * dx + dy * dy > RelocateRadius * RelocateRadius
        return False                                      ; the player is not at its merged spot
    endif
    float hx = x - (PrestonLocalX + MergeOffsetX)
    float hy = y - (PrestonLocalY + MergeOffsetY)
    if hx * hx + hy * hy > RelocateRadius * RelocateRadius
        return False                                      ; moved already: never offset twice
    endif
    WorldSpace wa = a.GetWorldSpace()                     ; evidence for Codex's world-identity point (#353): which
    WorldSpace wp = player.GetWorldSpace()                ; world each side is in before a move (only moves: Codex 4331303552)
    Trace("world " + what + " player=" + wp + " actor=" + wa + " cell=" + a.GetParentCell())
    a.MoveTo(player, x - px, y - py, z - pz, True, False)
    float d = player.GetDistance(a)
    bool failed = d >= RelocateGap
    Trace("world " + what + " after=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    Trace("moved " + what + " to " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " target " + x + " " + y + " " + z + " before=" + before + " d=" + d + " failed=" + failed)
    return failed
EndFunction

Function Trace(string msg)
    ; OnQuestInit's open does not survive a save load (the 21 Oct crash runs logged nothing); a no-op when already open
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
