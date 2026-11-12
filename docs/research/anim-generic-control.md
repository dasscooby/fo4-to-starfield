# Generic-graph control (FAL-489)

Question: does `genericstategraph01` (Sequence Names `StateA`..`StateD`, each `_Idle` and `_Play`; `Send Event On End` = `Trans01`; no vanilla ACTI or FURN
names it) load on an object of ours, which `PlayAnimation` names does it take, which events reach Papyrus, and does the object **hold a pose between calls**?
That decides whether the Vault 111 console's four stages in a row can sit on one graph. The converted console is NOT in this kit: the control comes first (the
Scribe's `vault111-console-stages` rev 2, "The control kit"), the converted four-clip panel after it passes.

Probe kit only: nothing goes into the owner's install; Claude runs it for one session on the PC after the Courier's CLEAR. Nothing here has been run in the game.

## Labels
**Verified** = read in this tree. **Supported** = a PC report or session as Claude posted it, not replayed here. **Unread** = nobody has read it.

## What is built
- `dotnet/AnimGenericControl` (new): `FO4SFAnimGeneric.esm`, master `Starfield.esm` only, two records, overrides none. QUST `FO4SF_AnimGenericQuest` (0x800, start game
  enabled, stages 10 20 21..29 30 40 60, no properties) and ACTI `FO4SF_AnimGenericControl` (0x801): a **copy** of the vanilla holder `001CCAC2`
  (`IndIntAddonArtifactHolder01`; same model, same rig, every other field and component) under our form id, whose animation graph component names
  `genericstategraph01` and whose clip folder (CNAM) is ours. `001CCAC2` itself is not overridden (that would retarget every holder while the plugin is loaded).
  The copy changes **only** the component's ANAM and CNAM: BNAM, DNAM, ENAM and anything else it carries stay the vanilla record's, and `check` compares BNAM, DNAM and ENAM with the vanilla
  record's (the Courier's FAL-579 hold: an earlier build rebuilt the component and dropped DNAM and ENAM). Supported (Claude, PC, 12 Nov 21:37 UTC, not replayed here): the real `001CCAC2` component has ANAM, BNAM,
  CNAM only, no DNAM or ENAM, so nothing was lost on this record; the fix keeps the tool correct for a record that does carry them.
  Commands `info`, `build`, `check`, `fixture`; `build` refuses a graph that is not `genericstategraph01` and a clip folder that is the vanilla holder's; `check`
  reads the plugin back (exactly two records, own form keys, masters exactly `[Starfield.esm]`, one graph component with the given ANAM/CNAM and the vanilla rig).
- `scripts/newgame/FO4SF_AnimGenericQuest.psc` (new): variant A's quest (PR #746) with the spawn pointed at ACTI 0x801 of our plugin and the call and event lists below.
- `scripts/newgame/make_anim_generic.py` (new): `precheck`, `stage`, `log`. `stage` reads the game's archives (read only) for (1) `genericstategraph01.agx`, whose
  archive path (without `Meshes\`) becomes the ACTI's ANAM, and (2) the vanilla holder's four `.af` and four `.afx` in its CNAM folder, then writes eight clips.
  It refuses and names each file it cannot find; nothing is invented.
- `scripts/newgame/anim_generic_install.py` (new): variant A's installer on a record of its own (`FO4SFAnimGeneric.install.json`).
- Tests: `tests/test_anim_generic.py`, `tests/test_anim_generic_install.py` (synthetic fixtures only).

Reused unchanged: `make_anim_probe.py`'s precheck and register-shape helpers, `src/fo4sf/anim_probe_log.py` (the log reader), `exp_install.py`.

## The eight clips
`StateA_Idle`, `StateA_Play`, `StateB_Idle`, `StateB_Play`: the vanilla holder's four files, **copied byte for byte** (the game stores them lower case; the kit names them as the
graph's Sequence Names). `StateC_*` = A and `StateD_*` = B: the `.af` bytes are identical to A's and B's; the `.afx` has its `<tag>` and `<filename>` rewritten to the
copy's name and everything else as the vanilla file has it. That shows whether C and D **play**, not whether they look like a lid. Whether the engine cares that the name
inside an `.af` is the vanilla one is **unread**. The copied files are the game's own: the staged kit is never committed, and `plan.json` records the SHA-256 of each file copied.

## The session (one name per stage; 15 s listening each)
| stage | what |
|---|---|
| 10 | `PlaceAtMe` the control 2.5 m in front of the player (persistent), register every event |
| 20 | register every event again (each call's return is a line) |
| 21..29 | `PlayAnimation` of `Play01`, `Play02`, `Play03`, `Play04`, `Play05`, then the direct `StateC_Play`, `StateD_Play`, `StateC_Idle`, `StateD_Idle`, one per stage, then 15 s of listening |
| 30 | `Activate(player)` by script |
| 40 | a reading of the reference |
| 60 | disable and delete |

Set the next stage only after the previous window has closed (its `W sN quiet` / `W sN heard n` notice). Stages are one-shot: a stage set twice runs once.
Events registered (the Scribe's list, `Trans03` (an Exit Event of the graph's summary), and `Play05`, `TurnOn`, `TurnOff`, `Opened`, which the real links name): `Trans01`, `Done`, `Trans02`, `Trans03`, `IsOn`, `IsOff`, `AnimFinish`, `IdleStop`,
`StateA_Idle` .. `StateD_Play`, `Play01` .. `Play05`. Every call's return and every event with its time is a line in the user log `FO4SFAnimG`
(`make_anim_generic.py log` reads it); every finding also shows as an `AP ...` notice, for a session with script logging off. The log cannot say whether the object moved or
held a pose: that is a screenshot before and after each name.

**The call order (supported, Claude's read of PR #755's dump of the real `genericstategraph01.agx` on the PC, 12 Nov 20:40 UTC; not replayed here):** the links on each state carry the
events that enter it: `StateA_Play01` by `StateA_Play`, `Play01`, `TurnOff`, `TurnOn`; `StateB_Play01` by `StateB_Play`, `Play02`, `TurnOn`, `TurnOff`; the C side by `Play03`, `Play04`,
`StateC_Play`, `StateC_Idle` (and `Trans01`); the D side (two nodes under a copied C name) by `Play05`, `StateD_Play`, `StateD_Idle`; the idles by `StateA_Idle`/`StateB_Idle`, `Trans01`,
`Opened`. Conditions `StartsOff` 0/1 and `StartAltIdle` 2..10 look like a start-state variable (**unread**: whether the record can carry one; no stage option for it yet). So the calls
are `Play01` .. `Play05`, then the direct names, one stage each. What each call DOES in the game is what the session shows; the dump says which events enter which state, not that a
`PlayAnimation` of that name fires the link.

## Pass bar (the Scribe's, for the converted four-clip console on this graph; not a result)
The object spawns with no crash; `PlayAnimation` true on `StateA_Play` or `Play01`; a visible A/B pose change or a hold; `Trans01` or `Done` written after a play; `StateC_Play` or
`Play03` true (the C/D slots accept a play). If the graph does not load (false on every name, or the object is inert), stop and read `=== graph genericstategraph01.agx` in full (the
dump) before any converted kit.

## Stage and run (PC)
```
python scripts\newgame\make_anim_generic.py stage --out <dir> --starfield <Starfield.esm> --compiler <PapyrusCompiler.exe> --content-resources <ContentResources.zip>
        [--game-archive "Starfield - Meshes*.ba2" --game-archive "Starfield - Animations.ba2"]     (the defaults, next to the Starfield.esm)
python scripts\newgame\anim_generic_install.py install --dir <dir> --starfield <game dir>          (the owner's word, game closed)
python scripts\newgame\make_anim_generic.py log
python scripts\newgame\anim_generic_install.py uninstall --starfield <game dir>
```
THROWAWAY STATE ONLY, NO SAVE: the spawned reference is persistent and would stay in a save.

## What was and was not run
Run here (synthetic fixtures only): the dotnet tool's `fixture`/`info`/`build`/`check`, the stage with a fake Papyrus compiler and fake archives, the clip copies, the installer on a temp game folder.
**Not run:** the real `Starfield.esm`, the real archives (so the real `genericstategraph01.agx` path and the real vanilla clip files are unread by this tree), the real Papyrus compiler (the stager
compiles each optional line on its own), the game. Whether a graph no vanilla object uses loads on an override of ours is the question of the session. Whether `Duplicate` of the real `001CCAC2`
keeps everything the real record has is checked only against a one-component fixture here; `check` compares the component count with the real record at stage time.

## Not here
The converted four-clip console, the glass-opacity stage flag, the cog door, the lift, the pick-up object, a hybrid vanilla session (the Scribe's document).
