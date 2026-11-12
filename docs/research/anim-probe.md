# Animation probe, variant A (the vanilla control)

Task: FAL-489 (Vault 111 exit, step 1 of the experiment in the issue document `vault111-anim-experiment`). Status: built offline (no Starfield.esm, no ContentResources.zip, no Papyrus compiler, no game on the build box); **run in game twice on the PC, 12 Nov** (reported in the section "What the two PC sessions showed" below, with its limits).

## The question
Does `ObjectReference.PlayAnimation` work on a pure-vanilla activator in our setup, and which animation events arrive in Papyrus? If
this sends nothing, the whole path is closed and variant D (our converted model on an activator graph) is moot.

## What the PC found before (Claude, 12 Nov, run of the `--graphs` probe at #744/#745)
Mechanism M2 (sequences kept in the model) is out: no model read carries `NiControllerSequence`. M1 (rig + `.af`/`.afx` under an
activator graph) is how the game does it. The clean pattern is ACTI `001CCAC2` `IndIntAddonArtifactHolder01`: graph
`activatorstategraph01.agx`, its own `skeleton.rig`, a CNAM folder with `statea_idle.af`, `statea_play.afx` and the rest. The `.afx`
of a clip carries its sound events (`<audio><frame>1</frame><foley>QST_MQ202_ArtifactHolder_Open</foley></audio>`).

## What is built
| Piece | Where |
|---|---|
| Plugin writer (build, check, fixture) | `dotnet/AnimProbe` |
| Quest script | `scripts/newgame/FO4SF_AnimProbeQuest.psc` |
| Stage (precheck, stage, log) | `scripts/newgame/make_anim_probe.py` |
| Ride-along installer, own record `Data\FO4SFAnimProbe.install.json` | `scripts/newgame/anim_probe_install.py` |
| Log reader | `src/fo4sf/anim_probe_log.py` |
| Tests | `tests/test_anim_probe.py`, `tests/test_anim_probe_install.py` |

`FO4SFAnimProbe.esm`: master `Starfield.esm` only; ONE record, QUST `FO4SF_AnimProbeQuest` (0x800; start game enabled, stages below, script
`FO4SF_AnimProbeQuest`, no properties). No ACTI, no REFR, no cell, nothing overridden: `check` asserts all of it. `build` also reads
the given `Starfield.esm` and refuses unless ACTI `001CCAC2` is there and its animation graph component names `activatorstategraph01`.

**Deviation from the request, and why.** The request was "one placed copy of ACTI `001CCAC2` in a cell I can reach". The kit does not place a
reference in a cell: the quest **spawns** the vanilla activator with `PlaceAtMe` 2.5 m in front of the player, wherever the player stands.
That needs no cell record, no override of the port's Vault 111 cell and no `FO4Port.esm` master (the workshop probe's rule: a core cell is
never overridden), and the test script lives on the quest, so nothing of ours is attached to the vanilla object (the control stays pure).
The cost: a spawned reference is not a placed one. The workshop probe showed the two can differ (a spawned bench gave no prompt, a placed one
did). So a result here is "a spawned vanilla activator plays and sends events". If it does not, the follow-up variant A2 places the reference
in a cell (`FO4Port.esm` master, an override of the port's cell) before anything is concluded about the path.

## The session (set stages from the console; the plugin's load index, two hex digits, then `000800`)
The console does not know the quest by its editor id: use `setstage <index>000800 <n>`. The script polls once a second.

| Stage | What it does |
|---|---|
| 10 | spawn the vanilla ACTI (persistent), move it ahead (`MoveTo` is optional), read it, register for 22 event names from it, log each call's return |
| 20 | register again (the log shows the returns) |
| 21 to 28 | `PlayAnimation` with one name each: `Play01`, `StateA_Play`, `Trans01`, `Play02`, `TurnOn`, `TurnOff`, `StateB_Play`, `Trans02`; then 15 s of listening: every event that arrives is a line, `quiet` says none came |
| 30 | `Activate(player)` by script (does its own activation play something and send events?) |
| 40 | a reading of the reference now |
| 60 | `Disable` and `Delete` (the delete is optional) the spawned reference |

Registered event names (22): `Trans01 Done StateA_Idle StateA_Play StateB_Idle StateB_Play Play01..Play04 Trans02 TurnOn TurnOff Reset
TransitionComplete AnimFinish EndAnim Stage4 KlaxonStop IdleStop IsOn IsOff`. One `PlayAnimation` name per stage, never the wait form.
Set each of stages 21 to 28 only after the last one's `quiet` / `listened` line is in the log (15 s): one listening window is open at a time. Each logged event carries the stage whose window was open (`stage=0` when none was: registration and spawn events are listed apart and never count for a name).
**Screenshot before and after each of stages 21 to 28** (does the object move?): Papyrus cannot read that. The user log
`My Games\Starfield\Logs\Script\User\FO4SFAnim.0.log` says what each call returned and which events came.

**With script logging off** (variant A's first session, 12 Nov: no user log was written) the same findings show on screen as short
notifications beginning `AP `: `REG s10 22/22 true` (register calls that returned true), `PLAY s21 Play01 ok=true`, `EV Trans01 w21` (an event; `w` = the
open window's stage, `w0` = none), `W s21 quiet` / `W s21 heard 2` (the window closed), `ACTIVATE s30`. A notification lasts a few seconds: read them
from a screenshot or a video; the `W` line closes each 15 s window. Turning script logging on (the launcher setting) still gives the full log.

Read it with `python scripts\newgame\make_anim_probe.py log`: verdict `EVENTS ARRIVE` (a true `PlayAnimation` and an event inside that name's own window), `PLAY, NO EVENTS`, `NO PLAY` or `INCONCLUSIVE`
(exit 0 when the activator was spawned). THROWAWAY STATE ONLY, NO SAVE (the spawned reference is persistent).

## Staging (on the PC)
    python scripts\newgame\make_anim_probe.py precheck
    python scripts\newgame\make_anim_probe.py stage --out <new folder>
    python scripts\newgame\anim_probe_install.py install --dir <that folder> --starfield <game dir>    (game closed, the owner's word)
    python scripts\newgame\anim_probe_install.py uninstall --starfield <game dir>

`precheck` looks every native up in `ContentResources.zip` (inheritance followed) and says whether `RegisterForAnimationEvent` declares a
return value; `stage` compiles the script with Starfield's compiler, keeping each optional line that compiles, and keeps the register call in
the shape the game declares (bool return, or the `;VOID` lines: the log then says `ok=void`).

## Before the sessions: not run, unread (as of the offline build, 12 Nov)
At the offline build nothing had run against the game. These were unread then: the Papyrus compile; whether `ObjectReference.PlayAnimation` returns a bool in Starfield; whether `RegisterForAnimationEvent(ObjectReference, string)` is the signature; whether a quest can register for events from another reference; whether `PlayAnimation` takes a graph event name or a clip name (stages 21 to 28 send both kinds on purpose); the stage and event lists were guesses from the `.agx` reads of #744/#745. The PC reports below touch some of these; read them there, not here.

## What the two PC sessions showed (Claude, 12 Nov, reviewed heads 319b4e55 and 9865544b)
Source: the PC comments on #746 (session 1 at 06:15 UTC, session 2 at 06:55 UTC). A spawned reference, not a placed one, in both.

**Session 1** (script logging off, so no user log; one screenshot before and one about 17 s after each stage). A spawned vanilla `001CCAC2` showed its own prompt "DISPLAY / ACTIVATE [E]". Object after each call: `Play01` open; `StateA_Play` open (no change); `Trans01` open (no change); `Play02` closed; `TurnOn` closed (no change); `TurnOff` open; `StateB_Play` closed; `Trans02` closed (no change); script `Activate(player)` open; disable and delete, gone. No crash, no save written.

**Session 2** (script logging still off; the `AP` notices, seven screenshots per stage at about 1, 3, 6, 9, 15, 17 and 20 s):
- `REG S10 22/22 TRUE`: all 22 register calls returned true.
- Five play names returned true (`PLAY ... OK=TRUE` seen): `Play01`, `StateA_Play`, `Play02`, `TurnOff`, `StateB_Play`.
- `Play01`, `Play02`, `TurnOff`, `StateB_Play` (the four that moved the object), and the script `Activate(player)` (`ACTIVATE S30`), each delivered three events and `Done`: a transition event (`Trans01` or `Trans02`), a state event (`IsOff` or `IsOn`), and `Done`. The opening ones were `Trans01`, `IsOff`, `Done`; the closing ones `Trans02`, `IsOn`, `Done`.
- `StateA_Play` returned true and delivered `Trans01`, `IsOff`, `Done`, while the object stayed open (it was already open after `Play01`).
- For the play names `Trans01`, `TurnOn` and `Trans02` (stages 23, 25, 28) no `PLAY` notice was seen in any of the seven shots, not even `OK=FALSE`, and no events. The screen cannot say whether those calls returned false or the notice was not shown.
- Event times were not measured in variant A (the notices queue on screen).
- No `W` (window closed) notice was caught in any stage, at 15, 17 or 20 s.

So, read from the screen: a script's `PlayAnimation` moved the spawned vanilla object for four names, and an event `Done` followed each move. No summary stronger than that is claimed. Still unread in variant A: the script log (each call's return, every event line), event times, the three silent names, a placed reference, the `W` notice.

Two readings of the notices, for the next session: a **false** `PlayAnimation` should show as a notice `AP PLAY s<N> <name> ok=False` (the script says it for every call, true or false; the game prints the bool in capitals on screen, as `OK=TRUE` in session 2). That was not seen for any name: for three names no `PLAY` notice was seen at all (above). The notices queue on screen rather than replace one another: the session 2 comment says so (that is why event times were not measured), and the PC reports up to three visible at once (relayed 12 Nov in FAL-506; the screenshots themselves are not in this repository). An earlier version of this card said a later notice replaces the earlier one; that was wrong. No `W` notice was caught in any shot. A notification is not a log: use script logging for a count and for times.
