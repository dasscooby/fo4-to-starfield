# Decisions (local AI team)

Format: date, decision, why, alternatives considered.

## 2026-10-16 FO4 "open by default" is written on converted doors; FO4 locks are not (Claude, proposed)
PluginSpike sets `OpenByDefault` (`ONAM`) on every placed reference of an animated, non-load DOOR base whose FO4
reference is open by default (pinned cells: 47 hinged-door refs; 68 with the sliding doors), so a doorway FO4 shows open
starts open instead of shut (review of PR #242). FO4 lock data (13 / 23 refs; Vault 111 levels 253 / 254) is counted
per cell and not written: the keys, terminals and quests that open those doors are not in the build, so a ported lock
would shut a door nothing can open. Alternatives: port locks with their levels (blocks routes until terminals and keys
exist), leave both out (FO4-open doorways become shut doors that a never-played rig must open). The route planner
already treats open-by-default doors as open (`scripts/game/routes.py` `moves_aside`).

## 2026-10-16 Sliding, lifting and trapdoor FO4 doors get their own rig, not a vanilla sliding template (Claude, proposed)
FO4 door models matching `NOT_HINGED_RE` (vault, elevator, hatch, ...) that are not load doors are converted like the
multi-part doors (`convert_multipart_door`: one rig bone per FO4 node, FO4's own Open / Close keys written with CALUMI, a
keyframed box per moving part) on the vanilla graph `SimpleOpenClose01.agx`, when `--door-anim-dll` is given; without
it they stay passable. Why: all 123 vanilla door rigs were read back; sliding and lifting doors use the same graph as
hinged ones and carry their motion in their own rig and clips, but none moves like the FO4 doors: no vanilla rig
drops a panel straight down or splits two panels up and down (the vault doors' lower panel drops 0.98 m; the nearest,
a NASA prototype door, moves two panels 0.52 m down and 0.52 m sideways) and the vanilla sliding pairs travel 1.00 / 1.50 / 4.00 m
against FO4's 0.64-0.91 m. A template would leave a panel shut or push it 0.09-0.36 m into the wall; FO4's keys give
the exact travel and timing. Alternatives: `ElvGen_ExSm_DoorInner01` as a template for the elevator doors (9-56 % too
far), `StsGenIntRmSmWallMid_DoorD01` for the vault doors (upper panel only, the lower one would block), keeping them
passable (the owner's row 1). Risk shared with #79: our rig and clips have not played in game. Evidence:
docs/spikes/sliding-doors.md.

## 2026-10-12 Multi-part FO4 doors get their own rig and clips; single-part doors stay on the Akila template (Claude, proposed)
A rigged FO4 door whose `Open` sequence moves geometry outside its first node (second leaf, shutter panel, sliding
panel set, latches) is converted with one rig bone per FO4 node, its own `Open`/`Close` clips written with the external
CALUMI library from FO4's own keys (tracks for animated bones only, keyed from the bind), one keyframed box per moving
part, and a DOOR record whose BNAM / CNAM point at those files (graph unchanged: `SimpleOpenClose01.agx`). Doors with one
moving part keep the verified template path. Why: the template rig's clip has one track, so a second part cannot move
under it; vanilla double doors (`IndIntRmSmWallMid_DoorA01`) are built exactly this way; FO4's keys give the right
pivots, angles, slides and timing for every part. Keeping single-part doors on the template keeps what already works
in game while the native rig is unverified. Alternatives: a vanilla two-leaf template (fixed hinge spacing and swing
that FO4 doors do not share), one DOOR reference per leaf on the Akila template (needs activate-parent links, and the
mirrored leaf would swing the wrong way), leaving the extra parts static (the bug). Evidence: docs/ai/research-log.md
2026-10-12; docs/spikes/WP-doors-research.md "Multi-part doors".

## 2026-10-11 FO4 navmesh: one Starfield NAVM per (FO4 navmesh, 100 m cell) and a NAVI holding only our entries (Claude)
Every Fallout 4 navmesh is cut at Starfield's cell lines into one NAVM per cell it touches (cut points keyed so both
sides are bit-identical; new links along the lines; FO4's own portals kept as links); the plugin carries a NAVI override
(`000FF1:Starfield.esm`) with one NVMI per new navmesh (no outline, no traversals). Why: FO4's portals overlap only in
part, so keeping its navmeshes avoids re-meshing; Red Rocket's navmesh stays one record (a walk on it needs no links and
no NAVI, the cleanest first test); every official plugin ships a partial NAVI the same way. Alternatives: one merged
navmesh per cell (re-weld partial portals), no NAVI (cross-navmesh paths probably fail), a full NAVI copy (53.9 MB,
overriding every vanilla entry), CK generation (not FO4's navmesh; owner time). Evidence:
docs/actors/navmesh-conversion.md.

## 2026-10-12 Terrain test travel: every teleport at most 2 cells per axis, terrain waypoints instead of hops (Claude, proposed)
Plans for the terrain runner keep every teleport within 200 m along each axis (at most 2 Starfield cells whatever the
overlay's merge offset): legs longer than 185 m get open terrain waypoints that are judged like the probes, and
`hop_m` 200 stays as a safety net. Why: in the overlay runs so far, teleports of at most 2 cells per axis landed 144 of
145 times and those of 3 or more relocated the player ("Boundary Reached") or hung 11 of 28 times
(`scripts/terrain/teleport_audit.py`, **supported**); distance alone does not separate them. Waypoints rather than
hops, because the runner's step timeout (150 + 90 s per point) does not count hops. Alternatives: `hop_m` 200 alone
(core64c's entry 1 would run past its timeout), splitting entries (at best 79 s of margin), per-axis hops in the
runner (a runner change, not on the integration branch). Evidence: docs/terrain/core64c.md "Teleport rule".

## 2026-10-12 Whole-core objects: one archive below 4 GiB with capped textures, not a region split (Claude, proposed)
core64c selects 649,596 convertible Fallout4.esm exterior references of the 64-cell core and places the 648,358 whose
models convert (1,238 belong to the 118 models that do not) in core64's plugin, and ships every
converted file in one stored `<plugin> - Main.ba2`, with converted textures capped per kind by dropping top mip levels
(color 1024, normal 512, rough 256, opacity 512 px; `convert_batch.py --max-texture`, off by default). Why: every large
vanilla archive stops just below 4 GiB (whether the engine reads past it is unresolved); full resolution needs about
8.5 GiB; the runner's installer packs one archive; the 11,769 models share 2,632 materials over the whole map, so a
split into 15 regions of 1.6 km would need 28.8 GiB and its four central regions would still exceed 4 GiB each; C:
has too little room for a full-resolution build plus its temporary archive. Alternatives: cap 512 everywhere (1.66
GiB, blurrier albedo), one plugin's Main + Textures archive plus a carrier plugin at full resolution (needs a
per-plugin installer and an in-game check), region plugins (above). Evidence: docs/terrain/core64c.md.

## 2026-10-11 Commonwealth terrain: one large overlay, a grid of overlays as fallback (Claude, proposed)
Plan the whole-map terrain as one overlay worldspace holding the playable Commonwealth plus 1 to 2.5 km around it
(64 to 90 Starfield cells, Absolute alignment), registered on a hidden host planet at a measured lat/long; fall back
to a grid of 14-cell overlays generated edge to edge if large overlays fail in game. Why: one landing is 100 cells
(game terrain width, 5-cell buffer), so the full 114-cell LAND grid never fits; a single overlay has no seams, while
every overlay seam has a 1-cell merge ring of unknown behaviour; both are built by the same generator
(`scripts/terrain/make_cw_overlays.py`). Alternatives: a custom planet surface made of our blocks (exact far terrain,
but four unknown height / blend rules and a planet to build), static mesh tiles (exact, but new collision, material
and LOD pipelines). Gates: an uncompressed rerun of exp2b (exp2b3) must read our BTD heights (exp2b's packed BTD
read flat at its minimum; cause unresolved, packing is one hypothesis), then exp3 (2 x 2 grid: seams, where the tiles
sit, measured from heights since our anchors do not merge), then a 64-cell core overlay. Evidence:
docs/terrain/commonwealth-scale.md.

## 2026-10-11 FO4 terrain heights: own Python reader following fo4land, Mutagen as the cross-check (Claude)
`src/fo4sf/fo4land.py` reads LAND/VHGT with the algorithm of fo76utils `fo4land` (MIT); `dotnet/Fo4Land` decodes the
same cells through Mutagen as a second, independent parse. Why: fo4land needs scons + a C++ compiler, which this
machine lacks and the rules forbid installing; its output is 16-bit normalised (0.81-unit step for the Commonwealth)
and drops the shared 33rd edge vertex we need for seam checks; Python fits the converter and unittest stack.
Alternatives: build fo4land (blocked), Mutagen only (C# outside the Python pipeline), extend Codex's Fo4Export
(not ours). Evidence: docs/terrain/source-patch.md.

## 2026-10-09 Enforce local concurrency with a proxy, not with prompts
OpenCode has no cross-agent concurrency limit for a provider. A small stdlib-Python proxy (:1235) in front of
LM Studio (:1234) admits at most 1 inference request at a time after a resource check, queues the rest, and logs
every decision to SQLite. Agents get per-agent model aliases so usage is attributed without OpenCode changes.
Alternatives: LM Studio's own parallel-request setting (no resource checks, no attribution); an OpenCode plugin
(more coupling to an evolving plugin API).

## 2026-10-09 Thresholds adjusted for a resident model and for game tests
The owner's starting thresholds (70 / 85 / 95 VRAM / 90 RAM) apply as given to RAM. For VRAM, a loaded model
permanently holds most of the 12 GB, so with a model resident the restrict level starts at 92% (block stays 95%).
While Starfield runs, local inference is blocked (`game_blocks_inference`): measured 2026-10-09 with the game in
Parsons: VRAM 83%, GPU 99%, RAM 85%, which leaves no room for a model and would distort game tests. All values
are in tools/ai-team/config.json and are starting points to adjust from observed behaviour.

## 2026-10-09 One model, aliases per agent
One loaded model is shared by all local agents (12 GB VRAM cannot hold two). The alias decides only attribution.

## 2026-10-09 Lead does not edit code
The Lead's `edit` permission is limited to docs/ai/**; implementation happens in the implementation agent's own
worktree. `subagent_depth: 1` and `task: deny` on the specialists prevent delegation chains.

## 2026-10-09 Local model: Qwen3-14B Q4_K_M
Chosen by Claude and Codex on #32 (owner asked the agents to decide; Grok not yet answered). Fits the 12 GB card
fully with a 16K context; the 30B-A3B coder model is tested only if 14B fails the tool-calling eval, and only with the
game closed (it needs CPU offload). File: lmstudio-community/Qwen3-14B-GGUF, Qwen3-14B-Q4_K_M.gguf, 9,001,753,376
bytes, SHA-256 712c0791...c58555 (matches Hugging Face). Downloaded with curl because `lms get` stalled at 0 bytes.

## 2026-10-09 Lead may wake idle remote agents (owner request)
The owner asked the local Lead to start Codex and Grok itself. `tools/ai-team/wake_agent.py` forks the agent's most
recent session (full history, new session id) and runs one headless turn with the Lead's brief (`codex exec fork`,
`grok -c --fork-session -p`). Forking avoids writing into a session file an open window may hold; nothing is typed into
any window. Deterministic guards: refuses if the agent was active in the last 10 min (two writers in one repo) or
was woken in the last 30 min (their usage comes from the owner's plans); every attempt is logged (wakes.jsonl).
Alternatives: keystrokes into the agents' terminals (focus stealing, wrong-window risk); GitHub comments only (agents
don't poll while idle).

## 2026-10-10 Movable FO4 objects: MoveableStatic records and one rigid body per multi-body system
- Decision: FO4 dynamic bodies convert to Starfield MoveableStatic records (never MiscItem: no inventory, no value, no
  pickup prompt) with vanilla-derived dynamic Havok bodies; a multi-body all-dynamic FO4 system (ragdoll skeleton,
  breakable, hose-and-tank) becomes ONE rigid compound body with the system's total mass ("phase A"), and systems with
  any anchored body stay static.
- Why: pushable objects are FO4 gameplay; MoveableStatic is how Starfield itself places pushable set dressing (431 in
  Starfield.esm); a rigid merge unblocks doorways today while constraints (joints) are a separate format job.
- Alternatives: MiscItem (adds pickup/inventory semantics FO4 statics don't have); leaving them static (blocks doors,
  silently changes gameplay); converting constraints first (weeks; the Vault 114 door needed a fix now). Breakables
  (`*Dest` models) are included in the merge without a check that their union matches the intact mesh: open.
## 2026-10-10 Load-door teleports are written by the plugin writer, not left to the ReferenceLinks post-pass
PluginSpike decides each manifest item's base record type; an XTEL is only valid between DOOR references, and both ends
are only known once every cell of the build is placed. So PluginSpike makes `load_door` items DOOR records and writes
the XTEL for each pair placed in the same build (dotnet/PluginSpike/TeleportLinks.cs), moving both ends to the
persistent group. Codex's ReferenceLinks post-pass (Relationships.Apply) writes the same link when it runs afterwards
(same values, idempotent) and still reports the unresolved ones. Alternatives: ReferenceLinks only (the STAT -> DOOR
change is PluginSpike's anyway, and every build would need the second pass); a DOOR for every FO4 Door base (fake doors,
hatches and trapdoors would become activatable with no destination).
## 2026-10-10 Place models without the NIF scene root's own transform
The converter, the route planner and the collision reader compose a model's node transforms from the children of the
scene root, not from the root itself (`nif.world_transforms(placed=True)`): the engine replaces the root's transform
with the reference's, so a rotation stored on the FO4 root is not applied in game. Why: `PryCatwalkStairsEnt02` has a
180-degree root; converting it with the root turned the stairs the wrong way round (Prydwen routes 20/28/29 fell, 19/27/30
never reached their start), and FO4's own precombined physics matches 89 placements of 15 rooted models only without
the root (docs/ai/research-log.md, 2026-10-10). Alternatives: apply the root as the file stores it (what we did; wrong
for 44 of 4,014 converted models, 232 placements); apply it only to models outside precombines (no evidence that the
engine does, and the stairs are not precombined). The default `world_transforms()` keeps the file's own composition for
tools that want the file as stored (door rig/motion modules, oracles).

## 2026-10-11 Converted actors: own identity, inherited Starfield behaviour (Claude)
A converted Fallout 4 NPC_ keeps what makes it that actor: its name, faction intent, weapon, death loot and combat
style intent. It inherits behaviour from a vanilla Starfield template of the same role through the ACBS template flags:
traits, stats, AI data and packages, attack data, keywords, scripts, and template slots 13 / 14. The first record
(`FO4_LvlRaider`, docs/actors/raider-conversion.md) templates directly on NPC_ records (EncSpacer01Template,
EncSpacerFaceM01), not on the leveled lists, so its look and level are the same in every test.
Why: Starfield runs the actor with its own systems (reaction radii, combat AI, faces), and the plugin stays small
(547 B). The behaviour template can be swapped without touching the identity, and a failure in the vanilla control
cell points at the record, not at the world.
Alternatives considered:
- Copying every FO4 field: FO4 AI semantics differ (hostility through aggression rather than faction relations), and
  FO4 faces and outfits need the skinning milestones.
- Duplicating a vanilla NPC_ (DeepCopy): carries the vanilla identity, and so hides what the conversion contributes.
- Templating on LvlSpacer / LCharSpacer: random per spawn, and the spawn may get a generated base that `GetIsID` does
  not confirm (N0_ptr_lvl).
Note (2026-10-12): the death item and combat style are written as the record's own, but under xEdit's Skyrim / FO4
template semantics (a supported hypothesis for Starfield) they go with Traits and AI Data, both inherited, so they are
probably overridden (docs/actors/raider-conversion.md section 3). Every converted NPC_ also carries PRPS, STON, PRON and
EDCT and form version 581, as all 7,131 vanilla NPC_ do (copied from the templates it inherits from).

## 2026-10-12 Converted actors are tested calm against calm, hostile against hostile (Claude)
A commanded walk (PathToRef, SetPlayerTeammate) of a converted actor is tested on a calm probe: the conversion without
factions, written into the same plugin (`FO4_LvlRaider_Calm`). Its FAILs are gated by the calm vanilla actor of N0 and
its PASS is credited to the command only when its own baseline stayed away. The hostile conversion is judged without a
command against the vanilla actor it inherits its behaviour from (N2b: both baselines). The runner measures the approach
from the spawn read as well as from t0, and every N2 test waits for the first one's spawn (`requires` DECIDED).
Why: QA on PR #75. With the hostile raider, combat AI would drive any walk, so a PASS said nothing about the command
and a raider holding its firing distance would have read as a conversion failure against a calm control; StartCombat
on an actor that is already hostile cannot be told from its own hostility; and t0 comes after the player moved to B.
Alternatives considered:
- A hostile vanilla control (the Spacer) for each command: also fair, but every test would then measure combat
  pursuit, not the command, twice the launches for one question.
- Console commands that calm the spawned raider (StopCombat, faction changes): unverified in Starfield, and they would
  add untested console lines to the step.
- tcai (combat AI off): global, and it would differ from N0's conditions.

## 2026-10-12 NPC navigation control N0b: the walk judged from t0 on a 24 m pair, P = pair - 6 m (Claude, proposed)
N0 replaced by N0b in QASmoke: A (5.5, -4.5, 0) -> B (-12, 12, 0), 24.05 m, chosen by
`scripts/actors/navmesh_points.py`; the commanded walk is measured from t0 (new plan keys `precommand_m` 3 m,
`arrive_progress` P; runner feature `npc_t0`): PASS = within 3 m of the player after coming P = 18 m closer than at
t0, or 18 m closer at the end; 3 m of approach before the command makes it INCONCLUSIVE PRECOMMAND; a baseline FAILs
WANDER on 18 m between any two reads; two citizen baselines; the control gate pairs a control with the baselines of its
own queue. Commands PathToRef and StartCombat on the calm citizen, the hostile Spacer as a baseline; N1 / N2 re-planned
with the rule of their own pairs, queued only once `npc_control.py ready` says N0b's controls passed. Why: N0's
actors came 5-9 m towards the old B whatever was typed (the 5 m rule passed wander), and the first N0b plan (18 m north
pair, 12 m, the integration-1012 judge unchanged) still let pre-command wander count: that judge's pre-command guard
is min_progress (12 m) and an arrival needs no progress after the command (verifier of PR #77); actors on record moved
up to 14.1 m from t0 and walked up to 9.5 m towards the player before the command (docs/actors/npc-navigation.md 5.3).
Alternatives: keep the 18 m pair with the new judge (P 12 m: below the 14.1 m move on record); a baseline-relative
judge (PASS only a margin beyond the same actor's measured baseline): needs several baselines per actor and pair to
mean anything; the 18 m pair with a 12 m rule and no runner change: refuted by the finding above.

## 2026-10-12 Fallout 4 marker load doors become the vanilla automatic cave door; experiment plugins load after their masters (Claude)
A Fallout 4 load door whose model is an editor marker (`AutoloadDoor` 01ED77, `AutoLoadMarker01.nif`, Automatic) is
written as a reference of Starfield's own `AutoloadDoor_Cave` (24F9CE): same name, flag and marker (the Starfield marker
is the FO4 one at 1/70, so the FO4 scale carries over), persistent, XTEL to the other end; an exterior end goes into the
worldspace's persistent cell, as all 45 vanilla overlay-world references of that door and all 345 worldspace XTEL
references do. The first one is the Red Rocket cave (docs/slice/redrocket-door.md), in a small link plugin that
masters FO4Port.esm and the terrain experiment instead of changing either. Because the runner's deploy activates
FO4Port.esm after an experiment's plugins on every launch, cycle.ps1 now runs `exp_install.py order` before the launch:
every plugin the experiment installed moves after its masters (runner feature `plugin_order`).
Why: the converter never places marker models, so both ends were missing; vanilla uses this exact door and layout for
its planet caves, which keeps the unknowns to our overlay's merge, not to the door record.
Alternatives: a converted FO4Port load door base (a visible door with an E prompt the cave never had); a new DOOR
copying 24F9CE without its environment script (a configuration vanilla never uses); placing the doors in FO4Port.esm or
FO4TerrainExp2.esm (would change the pinned build or a measured experiment); leaving the plugin before its master (in
Fallout 4 / Skyrim a load crash; in Starfield untested).

## 2026-10-12 door_trip: a door "does not work" only from a stand in its range; a PASS needs the walk-in (Claude)
After QA on PR #78: FAIL NOLOAD needs the player standing (settled) within the door's range (`activate_m`, 3 m) with
no load and GetInCell not saying the far side; a player never in range is INCONCLUSIVE NOREACH, a contradiction
INCONCLUSIVE CELLREAD. The step reads the position after every walk step and before E or the last-try teleport, so a
load that no HUD screenshot caught is counted and never followed by a teleport to the other side's coordinates. A
trip that loaded only from the last-try teleport is INCONCLUSIVE NEARONLY, because the owner's slice means walking in.
Before `load` the player is moved back to the coc arrival, so the position shows the reload by itself.
Why: a wrong FAIL on the slice's main question costs more than a retry; the HUD sampling (one screenshot about 1.5 s
after each 500 ms step) can miss a short loading screen, and the old step then teleported into the void.
Alternatives: keep NOLOAD on "near the start, no loading screen" (refuted by QA's synthetic cases); detect loads by
comparing screenshots (fragile at night and in caves); PASS with a NEAR class (the report's tally counts every PASS as
one, so the caveat would vanish from the summary).

## 2026-10-13 Movable tests: only the walk passes; furniture the walk did not reach is ELEVATED; the impulse is a diagnostic (Claude)
A movable test asks whether the player pushes the item, so only the walk passes it. A walk whose closest approach came
within reach and left the item in place is FAIL NOTMOVED. When planned (`--impulse`), `ApplyHavokImpulse` on the
confirmed selection (dv 1.5, 6, 24 m/s times its mass) follows: an impulse that moves the item only adds "the body is
simulated" to the detail, FAIL STUCK when nothing moves it. An item more than 0.5 m above the player's highest feet read
that the walk came no closer than 0.5 m to (or more than 1.8 m above them) is INCONCLUSIVE ELEVATED (final, never
counted by the circuit breaker). The converter keeps FO4's masses and bodies unchanged for now. A vanilla-controlled
queue (`movable_control_1013b`, QASmoke) compares our items with vanilla items of the same size, and the book and the
box again at 5 kg (`SetRigidBodyMass`, judged only when `GetMass` reads 5 kg back), before any converter change.
Why: the cigarette pack lay on a desk the walk stopped 0.67 m short of, and three flat books were walked over
(research-log 2026-10-13); every motion, layer and flag field matches vanilla items. Six inconclusive results in a row
switched the movable kind off for about 610 tests. The first version of this decision passed an item the walk could
not push as PASS IMPULSE and made every item 0.5 m up ELEVATED; the verifier of PR #110 showed that the impulse ladder
cancels the mass by construction (it would hide exactly the failure FO4's heavier items could cause) and that the pin
box of batch_full 0100, 0.81 m up, lay where the walk passed 0.26 m from it and did not move.
Alternatives: lighten FO4's masses now (2-10 times Starfield's for small items; unresolved whether mass is the cause:
the 25 kg book moved, the 50 kg box 0100 did not); a separate non-PASS class for "simulated but not pushed" (the detail
carries it, and NOTMOVED keeps the class every earlier report used); plan only items the walk can push (needs each
item's height and floor, and the batch would still not know whether a skipped item's body moves); MiscItem records
(pick-up and inventory semantics FO4 statics never had, decisions 2026-10-10).
## 2026-10-13 Codex: verified private evidence capsules before cleanup (#105)

Keep native screenshots and compact reports/source pins together in private lossless capsules,
with a per-file SHA-256 manifest and an external whole-capsule hash/index. Reopen and verify every
member plus the unchanged source before publication; never overwrite an existing archive. Linked
paths and restore-manifest aliases refuse archiving. Reclaim only explicitly identified inactive,
regenerable owned outputs after verification; retain cleanup receipts. Active/pinned campaigns and
unresolved configuration recovery stay in place. A second local volume is not an offsite backup.
Alternatives rejected: unverified moves, age-based screenshot deletion, lossy originals, or putting
private archives/game assets in Git. [Procedure](../testing/progress-storage.md).

## 2026-10-13 Stairs routes are walked offline before they go to the game (Claude; amended after QA on PR #111)
`scripts/game/routes.py` writes a stairs route only for a lane that an offline player walk (`src/fo4sf/walksim.py`)
climbs over FO4's own collision of the stair and its neighbours: a free start, no lift through a floor, at least 80 %
of the flight, no drop within 0.5 m past the end; otherwise the stair is skipped with the reason. References are placed
Z first (R = Rx(-x) Ry(-y) Rz(-z)), as FO4's precombined physics shows. What the walk cannot vouch for is written on
the route instead of hidden: `helper_crossing` (the walk meets a converted stair helper coming up through a floor at a
place the converter's flattening moved) and `movable_near` (movable objects the walk leaves out); a lane that would
touch a movable object is the last choice; `--probes-out` plans probes around each helper crossing. Planned routes for
an unchanged build go into their own folder (`testqueue.py plan --routes-dir`), never into the pinned staging, and a
queue keeps its own copy of the route files it uses (with their sha256).
Why: most stairs FAILs in batch_full and supervised_1011 were routes the player could not walk in Fallout 4 either (a
start wedged between a wall and a rail, against fallen floor chunks or rebar, a walk 2 m past a top that ends in a
collapsed floor, a 0.15 m "flight"), while the converted collision equals FO4's except the flattened helpers
([docs/testing/stairs-routes.md](../testing/stairs-routes.md)). A FAIL must point at the port, not at the test. But
0002 / 0003 stopped at a converted helper's slab crossing that the walk climbs (cause unresolved), so a route the walk
passes is not a route the port passes: the planner names such places and the queue tests them. The walk gives the
game's verdict on 59 of 64 recorded stairs results, 57 also at the same place (`scripts/game/stairs_calib.py`).
Alternatives: keep one centre-line route per stair and read every FAIL by hand (each costs a game run and an offline
analysis); hand-written skip lists for the library and Fort Hagen (do not carry to new cells); start every route from
the top floor and walk down (does not test climbing, the owner's complaint); skip every route through a helper crossing
(would drop the very tests that decide whether the converter's flattening is at fault); change the converter now (not
before the probes say the crossing is the cause).

## 2026-10-14 Codex: Windows read sharing during source fingerprints (#117)

Acquire an existing read-only Windows file handle sharing only reads, then retain it
through digest and metadata verification. Refuse incompatible writers/mappings and
do not fall back to permissive sharing. This closes the same-size/equal-metadata
race without changing persisted identities or reading every archive twice. Preserve
the immutable-source contract across the conversion run; POSIX metadata checks remain
best effort. Alternatives rejected: accepting a green retry of the intermittent test,
timestamp-only detection, or claiming that two hashes create an atomic snapshot.
[Contract, evidence and limits](../testing/archive-fingerprints.md).

## 2026-10-15 Codex: bridge publication and activation keep write-ahead ownership (#124)

Reuse the existing exclusive validated publisher and packed-resource verifier.
Record file intent before publication, confirmation afterward, and exact current
profile/activation bytes before changing Plugins.txt. Ambiguous or changed targets
keep a retryable journal; complete legacy ownership remains compatible. Cleanup
must be profile-bound and idempotent when a restored inactive line is already
present. Integrate Claude's bridge-last order caller without replacing its policy.
Alternatives rejected: direct final-path copies, minting identity from a copied
file without checking its source, or erasing an incomplete journal with untracked
artifacts still present. [Recovery boundaries](../testing/bridge-recovery.md).

## 2026-10-15 — Codex: reserve FormIDs before plugin publication (#132)

Persist the complete plain JSON identity map through a flushed same-directory
temporary file and replacement before PluginSpike writes its plugin. A map error
must not publish new plugin bytes. A subsequent plugin error keeps reservations,
including unused keys, so a retry cannot reassign them by conversion order.
Saving the map afterward left a synthetic plugin with no map on write failure;
rolling reservations back would permit ID reuse after interrupted builds.
This assumes one writer and an immutable input map during the run. It does not
make the plugin itself transactional, provide concurrent-writer exclusion or
claim power-loss durability/savegame acceptance. Complete build/deploy recovery
remains a separate control.

- 2026-10-15 (Claude): the Commonwealth is built from the existing 64 x 64 core (terrain + all 648,358 exterior statics already placed), not by adding cells: next come doors/interiors, semantic object classes via the R05 promotion path with ids retained (#150), navmesh per R06, actors, environment. One plugin for the exterior, interiors stay in FO4Port.esm. Alternatives considered: regional plugins (unneeded: the record count is far under the 16.7 M FormID space), a wider overlay (the playable area already fits). docs/terrain/commonwealth-build-plan.md.
- 2026-10-16 (Claude): FO4 settlement workshops become native ACTI build stations in the vanilla pre-placed pattern (OutpostPlayerHouseActivator 00024DC7: WorkshopKeyword + its OutpostCategory keywords read from the master, PRPS OutpostBuildAreaRadius 250, no VMAD; temporary REFR in the original slot), and FO4 crafting benches bind their REFR to the vanilla Starfield bench of their kind (weapon 2B6A63, armor 2B6A62, chem 2B6A61, cooking 2B6A65) with no record of ours; power armor stations stay statics. Why: build mode and the crafting menu are engine behaviour of these records (no script), the vanilla bench carries the animation and menu a converted mesh cannot yet, and a vanilla base keeps every FormID. Alternatives considered: the outpost beacon ACTI 2C60E9 (needs its quest script's mandatory properties), an outpost beacon pack-in (creates an overlay instance, unverified on ours), our own FURN with the FO4 mesh (second step: the animation over a boneless model is unresolved). docs/terrain/stations.md.

## 2026-10-16 Converted compressed meshes must pass the decoder simulation (Claude)
- Decision: src/fo4sf/meshcheck.py (CLI scripts/oracles/collision_mesh_keys.py) walks every compressed mesh of a
  converted NIF as Starfield's hknp decoder does and a build with violations is not deployed. The converter writes
  what vanilla meshes have and nothing else: one SIMD leaf per primitive, primitive slots the decoder cannot type
  replaced by a neighbour copy, FO4's special-primitive section flag cleared, primitiveStoresIsFlatConvex 0xFF; every
  other FO4 byte is copied as before (docs/ai/research-log.md 2026-10-16).
- Why: the owner's crashes since 10-12 are this decoder reading our per-triangle SIMD keys as primitives (vault_cart_01:
  key 79 + 1 -> primitive 40 of 40). Vanilla gives one invariant set to test against (837 of 837 meshes).
- Alternatives: dropping bodies with FO4 special primitives (loses the precombines' collision), re-encoding the trees
  (no vanilla evidence that the engine wants anything but what it has), leaving the flat-convex byte at FO4's 0 (a
  code path no vanilla asset exercises).
- 2026-10-16 (Claude): FO4 exterior load doors into the converted interiors become scripted doors (docs/terrain/scripted-doors.md): every record stays temporary on the exterior side (the overlay merge), the door REFR keeps its slot on an ACTI with the converted door mesh and carries the FO4SF_LoadDoor VMAD (PR #243: DestinationPlugin + DestinationId, resolved at run time, no master link between the plugins), each side gets an arrival XMarker at the FO4 XTEL point (exterior: temporary, appended after the lights with the ACTIs; interior: persistent, so it resolves from outside). The exterior side is written by Mutagen (its VMAD bytes equal the raw codec's and vanilla's), the interior side by a raw record-level patch of a copy of the pinned FO4Port.esm (scripts/terrain/vmad_patch.py), proved by a byte diff of every other record. Alternatives rejected: a vanilla XTEL door (persistent references read unmerged, 4 in-game runs); MoveTo onto the interior door itself (temporary: unresolvable from outside, and the player would land in the mesh); rewriting FO4Port.esm with Mutagen (no byte-level proof that nothing else moved); allocating the door ACTIs with the other promoted bases (would shift every NAVM and light id of core64i). Open until Step 0 runs in game: whether a temporary exterior marker resolves from inside (else a persistent twin plus the (-1200, -2700) offset).

### 2026-10-16 - preserve door-stage inputs before output (Codex)

A hard-linked README/report can overwrite the pinned source through the new
folder. Exclude generated names and replace generated files atomically; checking
an older hard-linked report must also detach it. Refuse any existing selected
REFR VMAD before changing the plugin, rather than erase or implicitly merge
unreviewed behavior. Validate marker-map collisions and disjoint output paths
before copying. Full-directory transactional publication remains separate.

- 2026-10-17 (Claude): the door return trip, writer side (docs/terrain/scripted-doors.md "Return trip"). Step 0 answered in game: the temporary exterior marker 0A76FD does not resolve from inside (door_trip_sdm_1018, `FO4SF_LoadDoor refused`), and a MoveTo onto a persistent overlay reference lands at its unmerged position, from where a setpos to the merged one stands on the overlay (probe (e)). So each exterior arrival marker itself becomes persistent (flag 0x400, same id: the slot and append rules of #272 and formids.json stay as they were) in the overlay world's persistent cell beside the anchor, and both door VMADs gain DestinationX / Y / Z (float, edited; the names of Codex's draft PR #291): the exterior door the interior marker's position, the interior door the exterior marker's merged position = local + overlays_params planet_target_cell x 100 m, refused unless it equals the measured (-1200, -2700, 0). Why the world's persistent cell and not the exterior cell's persistent children: the only persistent overlay reference seen to resolve and MoveTo in game is the anchor there, and vanilla keeps every persistent worldspace reference there (Starfield.esm 16,057 of 16,057, Fallout4.esm 33,571 of 33,571; 0 in an exterior cell's persistent children; read raw with C:\Modding\scratch\doorreturn\survey_persistent.py). Alternatives rejected: a persistent twin beside the temporary marker (a fourth id per door for no use: nothing resolves the temporary one); a marker written at local + offset (supported, not run: the MoveTo lands at the written position in the unmerged instance, 2.95 km from the door's terrain there, and the position leaves the overlay's cells); the offset as a bare constant (it follows the overlay's registration: a build registered elsewhere is refused until measured).
- 2026-10-17 (Claude): both door VMADs now carry `UseDestinationPosition` (bool, edited, true) as the sixth property, right after DestinationZ (docs/terrain/scripted-doors.md "Restage with the bool"). Why: PR #291's FO4SF_LoadDoor applies DestinationX/Y/Z with SetPosition only when that bool is true (zero is a valid coordinate, so the values cannot be the switch), so the five-property VMADs staged earlier the same day would have kept the plain MoveTo and ignored the coordinates. The reader (`vmad_patch.load_door_target`, hence `check_port` and `make_core64c.door_record_problems`) refuses floats without the bool, a false bool and the bool without floats; the two-property door stays valid. #291's psc declares the bool before the floats: the names and types match, the order differs, and Papyrus binds VMAD properties by name, so the reader takes both orders and the writer keeps the sixth position. terrain_core64l and integ_1018_doors2 were regenerated (265 of 265, 49 of 49; formids, objects and plan byte-identical to core64k). Alternative rejected: leaving the bool out (the psc defaults it to False, so the coordinates would never be applied).
- 2026-10-17 (Claude): exterior light lumens scaled 0.375 as a raw patch (terrain_core64l_l125) pending the owner's night check; the build default stays 333 until then. Alternatives: a full rebuild with --lumens-per-m2 125 (hours); a patch plugin (a second master). docs/terrain/exterior-lights.md "Calibration (17 Oct)".


## 2026-10-15 Claude: the leader's state is an append-only ledger; GitHub stays the human-readable bus

The leader core (`src/fo4sf/core/`, to be built per [leader-core.md](leader-core.md)) keeps one append-only
`leader/ledger.jsonl` of typed events beside the test queues; current state is a fold over it, and existing records
(queue `results.jsonl`/`state.json`, deploy and install manifests, watchdog state) are imported as events, never
rewritten. `SKIPPED` and `CIRCUIT_BROKEN` are terminal but undecided outcomes; only an `IN_GAME` `PASS` on the pinned
build verifies a capability. Why: the 2026-10-14 power cut and the #84 controller races both came from state spread
over labels, prose and per-queue files; a fold over a ledger resumes without guessing, a truncated last line is the
worst crash case, and the work-period report generated from the fold cannot drift from the state. Alternatives:
a SQLite store like `guardian.db` (harder to diff and attach as evidence; a crash mid-write is worse than a
truncated JSON line); GitHub labels as the state (not machine-checkable, no history of who held the controller);
rewriting old queue results into a new format (would touch original campaign evidence).

## 2026-10-16 Claude-cloud: the controller lease is a file beside the ledger, consulted only behind an opt-in switch

`src/fo4sf/core/controller.py` keeps the lease in `<leader>/controller.json` and writes every claim, renewal and
release to the ledger first (the ledger is the record; the file is the cache the PowerShell scripts read through
`scripts/game/lease.py`). `testqueue.py run`, `cycle.ps1` and `watchdog.ps1` consult it only when `FO4SF_LEASE_DIR`
(the watchdog: `lease_dir` in `watchdog.json`) is set; unset, every script behaves as before, so the owner's PC does
not change until the PC session turns the switch on in a window it watches. Why: the live runner, the chain and the
watchdog are the PC session's, and a cloud session cannot test them against the game; a default-off switch lets the
code merge and be read without a behaviour change. An expired lease is ambiguous and refuses every claim but the
holder's own or a forced one with a reason, because a crash leaves exactly that state and the ledger must say who took
over and why. Alternatives: a lock file alone (no record of who held it and no expiry: the #84 race again); a fold of
the ledger in PowerShell (duplicated logic in two languages); a key in the PC's `config.toml` (not in git, and the
runner reads none today); shipping the wiring on by default (would change the next chain on the PC untested).

## 2026-10-16 Claude-cloud: the preflight gate reads through a probe, refuses on UNKNOWN, and ships off

`src/fo4sf/core/preflight.py` keeps every check pure (a probe object supplies the readings; the runner's
`PreflightProbe` reads the PC, the tests a fake), so the Windows-only readings never enter the core and every check
has a synthetic PASS and FAIL. A reading the probe cannot give is UNKNOWN and refuses like FAIL, as the owner's brief
asks; that includes a game version nobody pinned yet, so turning the gate on is a deliberate step by the PC session
(pin the version, set `--preflight`). Why a probe and not direct reads: the same functions must run on Linux CI and on
the PC, and a check that raises must become one UNKNOWN line, not a crash of the runner. Alternatives: a PowerShell
preflight in cycle.ps1 (not testable here, and the runner needs the result in its log and the ledger); making the
gate always-on (would refuse every current queue, none pins a game version); verifying the absolute load index
against the game's implicit plugins (which of them the owner's install loads is unresolved: left as a note).

## 2026-10-16 Claude-cloud: task cards and worker results are validated data; a lost attempt expires, never vanishes

`src/fo4sf/core/tasks.py` and `worker.py` make the §4 card and the worker's result typed records the ledger checks
before it takes them (an undecided outcome never completes, a PASS or FAIL carries evidence, only an IN_GAME PASS
may claim `verified`, one attempt at a time, dependencies by PASS), and `Worker.expire` turns an attempt past its
timeout into an INCONCLUSIVE result that says so. Why: the brief's cards were prose, and the two failure modes of
the last weeks were a result nobody could trace to evidence and a run nobody could tell apart from a lost one; data
with rules closes both. Alternatives: free-form result dicts (what the queue rows are today; the importer keeps
reading those unchanged); a scheduler that retries on its own (a retry is a decision the leader records, not a loop).

## 2026-10-16 Claude-cloud: the core carries one reference matrix, in #102's Z-first order, and leaves the old copies in place

`src/fo4sf/core/adapters/transform.py` is the core's only `ref_matrix` (`R = Rx(-x) Ry(-y) Rz(-z)`, the order PR #102
verified on 146,463 of 146,728 tilted precombined references and on 52 of 52 core64c readings); a parity test pins
where the two Python copies agree (`routes.py` everywhere, `exterior.py` on heading-only rotations) and where they do
not. `exterior.ref_matrix` and `PluginSpike.RotateOffset` stay X first on purpose: switching either moves every
tilted placement or every rigged door hinge, which is a re-staged build, a rebuilt plugin and re-pinned campaigns,
so each is its own PR by the PC session (leader-core.md §9 lists the cost). Why not fix them now: a cloud session
cannot rebuild or re-pin, and a silently changed `objects.json` would invalidate pinned evidence. Alternatives:
one shared function imported by both scripts today (ties `scripts/game` to `fo4sf.core` before the PC session has
decided the import path); keeping the order as a parameter (two orders in the core is the bug #102 found).

## 2026-10-18 Claude-cloud: SetRigidBodyMass tests when GetMass cannot be read
- **Decision:** a movable_control test with `set_mass_kg` whose GetMass probe answers "No script named ..." is judged
  on a move only. PASS WALKED or PASS IMPULSE stands, with "mass not read back" in the detail. No move stays
  INCONCLUSIVE MASS.
- **Why:** in movable_1019c, `cf "ObjectReference.GetMass"` answered "No script named ObjectReference is attached to
  the object" (**verified**), so the old rule ("judged only when GetMass reads the mass set back") would leave every
  5 kg test unjudged forever. The set mass can only have made the body lighter or left it unchanged:
  - A move shows the body moves at a mass no higher than its own.
  - No move cannot tell a mass that did not take from a heavy body, which is the verifier's "thinness, not mass"
    concern on PR #110, so a non-move is still not judged.
- **Alternatives:**
  - Drop the 5 kg tests: this loses the one comparison that can show mass is the cause.
  - Judge both ways: this risks a false "mass is not the cause".
  - Find another GetMass route: none is known (no console command; the CallFunction route refuses).
- Taken under the owner's standing rule (2026-10-18 03:56Z) that threads take their recommended option on reversible
  choices.

## 2026-10-18: interior usable objects reuse the exterior promotion rules (Claude-cloud)
- Decision: FO4Port.esm promotes containers, inventory items, activators and terminals with the core's make_cluster rules
  and tables, through an optional promote.json PluginSpike reads (docs/terrain/port-promotions.md).
- Why: the owner found these unusable indoors (18 Oct); the exterior path is already verified in game.
- Alternatives: a Python record patch of the pinned plugin (vmad_patch style): rejected, new record types would need a
  hand-written layout Mutagen already writes; copying the table logic into C#: rejected, two rule sets would drift.

## 2026-10-19 Claude-cloud: all interiors go into one cumulative FO4Port.esm, every earlier id kept
- **Decision:** the remaining interiors are converted in staged batches (docs/terrain/interior-batches.md), each a
  new full FO4Port.esm = the installed port's cells + every batch so far. PluginSpike is seeded with the installed
  port's formids.json, and `vmad_patch.py port --keep-markers` re-applies the installed scripted doors with their
  marker ids; `interior_batch.py compare` fails a batch that renumbers or drops an installed id.
- **Why:** the installed core's exterior doors name FO4Port.esm marker ids (00E175..00E183); a grown port that moved
  them would break those doors, and saves hold port ids. One plugin keeps the owner's load order unchanged and lets
  interior-to-interior doors across batches link by XTEL in one build.
- **Alternatives:** one plugin per batch (FO4PortB01.esm ...): independent rollbacks, but nine more plugins, duplicated
  bases or a master chain, and cross-batch door links between plugins; a rebuild of the core with every door per
  batch: forbidden while the v6e test runs, and it is the door gate's own step.

## 2026-10-20 Claude-cloud: one location per FO4 location, rooted in FO4Port.esm, leveling from the encounter zone
- **Decision:** PluginSpike writes one Starfield LCTN per Fallout 4 LCTN, shared by the cells that name it (one per
  cell when the cell has no XLCN), keyed `LCTN:FO4Port_<FO4 LCTN editor id>` so the chained formids.json fixes its
  FormID on first use; every converted cell gets XLCN. All of them are parented to one root LCTN inside FO4Port.esm,
  `FO4Port_InteriorsLocation`, whose parent is `SSol_PMars_Surface` 01B736:Starfield.esm. The FO4 encounter zone's
  level band and its four flags fold into the LCTN's owner data (levels clamped to 127); no keywords are written;
  CELL bit 0x10000 ("Use Location as Name") stays off unless the per-cell setting `LOCATION_AS_NAME` is "1". The
  FO4 data comes from Fo4Export (schema 3 exports; a `locations` mode writes a sidecar for the 16 pinned base
  exports). docs/terrain/interior-batches.md "Locations".
- **Why:** interiors.md C4 and C10 decided that FO4's levels and cleared state are per location, and in FO4 both live
  on the LCTN and its ECZN: a per-cell location would split Vault 81 and Parsons State into three places each that the
  combined core (which keys places by FO4 LCTN editor id) would have to re-merge. A root in FO4Port.esm keeps the
  plugin's masters at Starfield.esm alone, so every earlier FormID and the installed core's door markers stay as they
  are; re-pointing the root later is a one-record change.
- **Alternatives:** parent = the overlay location `FO4CW_CommonwealthLocation` in FO4TerrainCore.esm (interiors.md's
  supported default): rejected, FO4Port.esm would have to master the core, reversing the build order and breaking the
  "no plugin masters the other" rule the door wiring relies on; whether a chain that bypasses the overlay satisfies the
  cleared-state system is an in-game test. Per-cell locations only: rejected above. Replicating FO4's parent chain
  (CommonwealthLocation ...): nothing consumes it yet; the export keeps `parent_chain` for the core's region derivation.
  Carrying FO4's LocType keywords: no verified Starfield mapping, kept in the export for a later pass. Inheriting a
  missing zone's leveling from the nearest FO4 ancestor: no evidence Starfield resolves it the same way; left null.

## 2026-10-20 Claude-cloud: textures beyond one archive ride empty companion plugins, full masters for now
- **Decision:** `interior_batch.py build` packs the textures into as many DDS archives as fit under 90% of the
  4,095 MiB limit (`plan_parts`: case-insensitive path order, greedy, a file never split, a file keeps the part the
  `--prev` batch gave it while that part has room, the previous batch's packed/loose ratio widens the cap). Part 0
  stays `FO4Port - Textures.ba2`; part k is `FO4PortTextures<k+1> - Textures.ba2` next to `FO4PortTextures<k+1>.esm`,
  an empty full-master plugin (42 bytes, byte for byte Mutagen alpha.67's output for a record-less master: **verified**
  in a probe, pinned in `tests/test_interior_census.py`), listed in Plugins.txt right after FO4Port.esm. The
  companions and their archives are pinned, successor-verified and never archived, like the port's own archives.
  docs/terrain/interior-batches.md "Pack".
- **Why:** batch 4's Textures.ba2 is 3,590,442,691 bytes (**verified**) and grows about 5% per batch, so the single
  archive reaches the limit around batch 7, and whether the engine reads a larger one is unresolved (X3). The game
  loads `<plugin> - Textures.ba2` for a loaded plugin (**verified** for FO4Port.esm and the vanilla SFBGS003 / 00D
  pairs); an empty plugin is the smallest carrier of that name. Full master because X2's rule keeps every new plugin's
  type a recorded choice checked in game before release: a small or medium master has never been loaded by this
  project (S2 verified only a Mutagen full master, docs/spikes/S2-S4-S9), and a record-less plugin gains nothing from
  the smaller type but a load-order slot. The in-game test that would allow the smaller type: the companion rewritten
  as a small or medium master, a texture only its archive holds rendering after `coc` (interior-batches.md PC tests);
  the choice is fixed once released.
- **Alternatives:** numbered archives of one plugin (`FO4Port - Textures02.ba2`): the executable holds a
  `%s%s%02u.ba2` pattern (core64c.md) but no installed plugin uses it, so it is a second unverified mechanism; a
  smaller texture set (`--max-texture` caps as the core uses): changes every converted texture and the pinned
  batches; a plugin per batch: rejected on 2026-10-19 (ids and doors). Planning by packed size (pack, measure, split,
  repack): gigabytes of Archive2 time per attempt; the loose-bytes plan with the measured ratio is conservative and
  deterministic.
- **Open:** deploy_starfield.py installs FO4Port.esm and its two archives only; a batch with companions is installed by
  hand from result.json `install` until the installer learns the list.

## 2026-10-20 Claude-cloud: a batch pins the game files it read and refuses a chain built from other ones
- **Decision:** result.json `sources` holds the sha256 and size of Fallout4.esm and of each DLC plugin a cell is
  exported from, and the size and mtime of every BA2 under `--fo4-data` and `--dlc-data`. A `--prev`, or a `--base`
  that is a batch's own stage, with other pins is refused; `--allow-source-change` overrides and is recorded.
- **Why:** X8 (precedents Q4): the chained batches reuse the previous batch's exports and converted models, so a
  changed Fallout4.esm or BA2 would silently mix two game versions in one port. Hashing the BA2s (some 30 GB) would
  take longer than the convert step, so they are pinned by size and mtime; the plugins are hashed (seconds).
- **Alternatives:** hash everything (too slow per batch); refuse nothing and only record (the mix would go unnoticed
  until a model looks wrong in game); pin the installed doors staging too (it predates the pins; a base without a
  record is accepted, said so in the doc).

## 2026-10-20 Claude-cloud: the texture plan replans on an over-limit part; a source pinned for the first time is not a change
- **Decision:** `interior_batch.py pack` packs a part that came out at or over the 4,095 MiB limit again, replanned
  with the packed/loose ratio that attempt measured (always above the one planned with: an over-limit part packed
  more than cap times ratio bytes), repacking only the parts whose file list changed, up to three attempts
  (`steps.pack.attempts`); `--pack-ratio R` overrides the `--prev`'s measured ratio (`steps.pack.ratio_source`). A
  measured ratio above 1 is kept, not clamped to 1. `plan_parts` never returns an empty part: one the previous
  assignment emptied is dropped and the parts after it move down (their files count as moved). `source_changes`
  counts a pin whose value changed or that is gone; a plugin or BA2 pinned for the first time is listed under
  `steps.sources.added` and never refused. Review findings on #396, docs/terrain/interior-batches.md "Replanning"
  and "Sources".
- **Why:** the ratio is measured on the previous batch's parts, never on the files the batch adds, so a batch whose
  new textures pack worse could exceed the limit after hours of Archive2 time, and a failed batch is no `--prev`:
  the chain had no recovery path but editing result.json. Repacking only changed parts bounds the extra Archive2
  time to the parts that moved. An empty middle part (every file of it gone from the work staging) would have been
  packed from a link tree never made: a FileNotFoundError past build()'s handler, no result.json. Batch 10 (the DLC
  cells) pins DLCRobot.esm and its BA2s for the first time; refusing it would force `--allow-source-change`, which
  would also silence a real Fallout4.esm change in that build.
- **Alternatives:** plan by packed size (pack, measure, split, repack every part): the replanning does that only
  when the plan missed; keep gaps in the companion numbering so a file never moves when a part empties (sparse
  `FO4PortTexturesN` numbers; rejected as confusing, and the case needs every file of a part gone); refuse a
  first-time pin too (the reviewed behaviour, rejected above).

## 2026-10-19 Claude-cloud: the launcher backbone wraps the existing scripts and installers
- **Decision:** `src/fo4sf/launcher/` adds a build manifest, a recipe-driven resumable build driver over the existing
  make scripts, a snapshot-and-restore that acts only through deploy_starfield.py, exp_install.py and
  bridge_install.py, and a same-ids check (raw record walk plus compare-ids). Pure Python; no C#, so no new GPL-3
  binary (docs/ai/launcher-backbone.md).
- **Why:** Grok (#381) and Codex (#382) asked for the build-and-restore spine and the determinism check before
  doors and interiors; Codex noted the ledger is not the physical restorer, so restore reuses the installers that
  already own every file. Wrapping keeps the install thread's nightly commands unchanged.
- **Alternatives:** a build graph importing the converters (rewrites the entry points); MO2 profile or Stock-Game
  copy for restore (untested at this size / too much disk); a Mutagen check in C# (needs a load order, GPL-3).
  Listed for the owner's talk in launcher-backbone.md.

## 2026-10-20: the combined core starts as a game-neutral, deterministic model in its own package (Claude-cloud)
- Decision: `src/fo4sf/combined/` holds the GAMMA-style combined core's L1 world-state model, L5 packs that only add,
  the L2 off-screen simulation seeded from (seed, hour), and a read-only Fallout 4 reader that drafts the first pack
  (docs/combined-core.md). It is separate from `src/fo4sf/core/` (the leader core) and has no engine code yet.
- Why: the owner put the combined core's systems ahead of the single-game mode's extras (2026-10-19 23:24Z, CC-01 A,
  first on the Commonwealth). Getting the state shape, pack rules and save replay right before any Papyrus or SFSE work
  avoids a rebuild when the other worlds arrive; determinism lets a player's save be replayed offline in tests.
- Alternatives: Papyrus-first prototype on the PC (rejected: the PC is busy with the v6e test and Papyrus cannot be
  unit-tested on CI); reusing Sim Settlements 2 or Workshop Framework code (rejected: their permissions forbid
  conversion; design question CC-04); one shared `core` package (rejected: build orchestration and game runtime would
  drift into each other).

## 2026-10-20: the combined core's game-facing state is a small view the save keeps, the rest a sidecar (Claude-cloud)
- Decision: M2 adds `adapter.py` (a record plan and a minimal-writes view: one FOCC_ keyword datum per place for its
  holder, one global per faction for its reputation tier, globals for play settings) and `sidecar.py` (a checksummed
  per-save file the SFSE plugin would mirror). One keyword per place is our choice; engine-feasibility.md sketches a
  single FOCC_Holder keyword with a datum per location, and probe P2 decides between them.
- Why: SFSE has no co-save today, so the bulk state needs its own file per save, while conditions, dialogue and leveled
  lists must read holders and reputation without SFSE (design CC-02, option C').
- Alternatives: everything in Papyrus (save bloat, the Warzones lesson); everything in the sidecar (a broken SFSE after a
  patch would leave the game blind to territory instead of frozen).

## 2026-10-19: the Fallout 4 new game is its own plugin, resolving the port and core at run time (Claude-cloud)
- Decision: FO4SFNewGame.esm (master Starfield.esm only) holds the start quest; it finds Vault 111 and the core's exit
  anchor with Game.GetFormFromFile on stable plugin-local ids, and stops MQ00 and MQ101 from Papyrus instead of editing
  them (docs/newgame/vault111-start.md).
- Why: the mission plugin is under test; ids in FO4Port and the core are stable, so the start survives their rebuilds;
  stopping quests edits no Starfield record and goes away with the plugin.
- Alternatives: changes to FO4SFMission.esm (rejected: it is under test); mastering the port and core with our own
  markers (rejected: a rebuild after every build); overriding MQ101 or GLOB MQ101Debug (kept as the documented
  fallbacks, `--mq101debug`, for the owner's talk).

## 2026-10-28: the new game overrides no record; the quest writes MQ101Debug = 2 after the hold-off (Claude-cloud)
- Decision: FO4SFNewGame.esm carries no GLOB override (newgame_v9). Starfield's intro places the player; right after
  hold-off pass 1 has stopped MQ101, our quest writes 2 into MQ101Debug with SetValueInt and logs the write. The
  owner's NG-2 (we set the debug global ourselves) stands, at the one moment it is safe. The guard also needs MQ101
  running, so a session started with coc from the main menu stands down. The precheck follows each script's `extends`
  chain, so SPECIAL stages again (docs/newgame/vault111-start.md sections 1, 2 and 11).
- Why: the owner's second new game (28 Oct, newgame_v8, override 2) never left its loading screen. MQ101's stage 0 runs
  the entry whose MQ101Debug condition matches, and that entry's fragment is what moves the player into the game (the
  intro's entry 2 moves the player to CharGenStartMarker and waits for the 3D). No entry matches 2, so nobody moved the
  player, and our quest's OnQuestInit only runs after that first load. 2 is the value the main quests' developer
  skip-start stages write (a normal intro leaves 0); writing it after the stop opens PEO_SustenanceAllowed, whose
  normal route (MQ101 stage 310) a held-off intro never reaches. A coc session from the main menu never starts MQ101,
  and Install's map test (28 Oct) showed the old guard moving such a character into the vault.
- Alternatives: `--mq101debug 8` (SKK's New Atlantis start, a value an entry matches; not usable with this guard,
  since entry 8 sets MQ101 to 500 and 1310 itself);
  overriding StartupQuest_DO with our own controller quest that moves the player and never starts MQ101 (No Ship Fast
  Start's shape; a record override and more code, held for the owner if the hold-off path fails); any unmatched
  override (rejected: it hangs the load).

## 2026-10-28: the new game overrides MQ101Debug to 2, the value that starts Starfield's opening inert (Claude-cloud; superseded the same day by the entry above: 2 hangs the first load)
- Decision: FO4SFNewGame.esm keeps the one GLOB override (the owner's NG-2, we set the debug global ourselves) but
  writes 2, not 10; the guard's day limit is one game day; the guard logs every reading and the global as the game read
  it (docs/newgame/vault111-start.md sections 2 and 10).
- Why: the owner's first new game (28 Oct) landed in Starfield's pirate fight with no cutscene and our quest stood
  down. MQ101's stage 0 picks its start by MQ101Debug (records, 21 Oct; fragments, 19 Oct): 0 the intro, 1 and 3 to 10
  developer starts (10 is the pirate fight: stages 210 and 250), any other value only a conditionless entry that ghosts
  three NPCs. Vanilla never writes 10 (MQ00's stage 10 is no start-up stage), so the 19 Oct premise was wrong. 2 is what
  MQ102 to MQ305 write once the intro is over and keeps PEO_SustenanceAllowed's "MQ101Debug != 0" open. Starfield's
  clock starts at 8:00, so GameDaysPassed reads 0.3335 a second into a new game and the old 0.25 limit stood every new
  game down.
- Alternatives: no override and a script write after the hold-off (rejected for now: Starfield's intro then starts its
  scene, locks controls, hides the HUD and wipes the inventory before the hold-off kills it a second or two in; kept as
  `--no-mq101debug`); the old 10 (kept as `--mq101debug 10` only to reproduce the run); overriding MQ101's record (C,
  owner's word only).

## 2026-10-19: load doors open before the trip on Starfield's terms (Claude-cloud)
- Decision: a load door gets a rig the way ordinary doors do (its own FO4 NIF, or its non-load twin's rig when the
  bounds match) and stays ONE DOOR record that opens and then travels; scripted doors wait for the open in a child
  script (FO4SF_AnimatedLoadDoor extends FO4SF_LoadDoor). Every switch is off by default (docs/spikes/load-door-animations.md).
- Why: the owner's phase 2 (doors with enter and exit animations); Starfield's own visible load doors animate, and its
  own animations come first (owner 2026-10-19). A child script leaves the FO4SF_LoadDoor contract the passing round
  trips use untouched.
- Alternatives:
  - A separate opening door beside each load door: rejected, two records per door and a prompt clash.
  - A fade or sound only: rejected, it is not the animation the owner asked for.
  - Changing FO4SF_LoadDoor itself: rejected while v6e's test runs on it.
  - Moving the core's exterior ACTI to a DOOR now: deferred until the v6e test is done (the bugs thread owns that path).

## 2026-10-20: one stable DOOR base per converted model and FO4 name (Claude-cloud)
- **Decision:** PluginSpike's DoorNames.cs gives each FO4 name of a converted door model its own DOOR base, under the
  identity `DOOR:<editor id>|name:<name>`, and moves that name's references to it. The model's own base
  `DOOR:<editor id>` keeps the name "Door" and the references without a usable FO4 name, and it is emitted even when
  no reference uses it. Copies keep the base's open and own-rig roles.
- **Why:** the first version gave the model base the name most of its references had. Codex showed on #400 (review
  5580232495) that a grown export with the same formids.json flips the winner. Old references then move to another
  base, and a published base gets another name, while every REFR ID stays the same. Bases and their names are what
  saves and other plugins see, so they must not depend on reference counts. The fix was confirmed in review 5581794458.
- **Alternatives:**
  - Keep the election and record each base's owner name in formids.json. This adds a map entry that is not a record,
    and a new name can still win the election.
  - Name the model base after the first name in ordinal order. A new name that sorts earlier still flips it.
- **Boundary:** this is not a migration. A plugin or map built with the 4f0ad57 election is not compatible with it,
  but no staged or installed build used that version. Not verified in game.

## 2026-10-25: travel narrowed, two play modes, succession and ghouls (the owner's calls, Claude-cloud)
- **Decision (owner, given to Codex on 25 October, confirmed to Claude on 28 October):**
  - **Travel:** a modest outskirts expansion, with limited generated areas that are made once and kept. The player
    gets there by a corridor, or by picking an allowed spot on the map within a distance cap. Longer trips go by
    vertibird or other transport, with settlement-based range and paid travel priced by distance. Continuous walking
    between regions is deferred until every planned location is in.
  - **Modes:** Warfare picks a faction and one of its starting bases. Survival picks story on or off, and a faction or
    solo start. Some settings are fixed per save.
  - **Warfare death:** the player continues as another member of the faction. The same character is not revived.
  - **Ghouls:** ghoul play is wanted for Warfare and for Survival with the story off.
  - **Gameplay:** no language model, AI server or online inference. FO76 content follows FO4's single-player rules.
  - **Platform and shipping:** we stay on Starfield. Support mods may ship separately later.
- **Why:** these narrow the travel research (`docs/research/framework/travel-and-runtime-risks-oct25.md` on draft
  #553) and the Route C travel map to something deliverable. The owner confirmed that Codex's record of them is
  correct (28 October, project thread).
- **Open:** exact ranges and costs, generation timing, which destinations are allowed, and what replacing a member
  means for progression.

## 2026-10-28: Claude works alone after Codex and Grok leave; the review rule stays (Claude-cloud)
- **Decision:** the owner's Codex and Grok subscriptions end a week or two after Claude's next renewal. After that,
  Claude is the only worker, possibly for some months. The merge rule does not change: CI must be green and an
  independent review must pass on the current head. Once Codex and Grok are gone, the independent review comes from
  a fresh Claude session that did not write the change.
- **Why:** the owner said to keep the same rules (28 October). A review by the author is not independent.
- **Alternatives:**
  - CI alone: rejected, because the owner keeps the rules.
  - A local model as reviewer: deferred. The owner may buy a Mac Studio for a local coding assistant, but the
    purchase is uncertain. It would not run the game, so game tests stay on the Windows PC.

## 2026-10-28: the in-game world simulation is a C++ port inside the SFSE plugin; Python stays the reference (Claude-cloud)
- **Decision:**
  - `src/fo4sf/combined/` remains the reference model, and it runs the whole Commonwealth (about 230 places, from
    the 21 October seed run) offline.
  - In game, a 20-place slice comes first.
  - When the simulation moves into the game, it is ported to C++ inside the SFSE plugin (the `sfse/FOCCSidecar/`
    stack). The port must give the same results as the Python model on shared test worlds.
  - We use no Rust, no ECS library and no separate simulation process.
  - Probes P1 to P10 (`docs/spikes/combined-core-probes.md`) run first.
- **Why:** the owner left scale and language to Claude (28 October). Codex's brief
  (`docs/research/framework/claude-reuse-decision-brief-oct25.md` on #553) asked for keep, adapt, investigate or
  defer. Nothing is measured slow, and Python never runs in the game. The open questions are save association,
  keyword-data persistence, spawning and Papyrus latency (P1, P2, P4, P5), and no language answers them. Our native
  plugins are already C++ on SFSE's own API.
- **Alternatives:**
  - Rust or an ECS library (Bevy ECS, hecs): deferred. They add a second native toolchain and a C bridge for no
    measured gain.
  - A separate process: deferred. Keeping it in step with saves and crashes is harder than keeping a table inside
    the plugin.
  - A Papyrus-only tick: kept only as the fallback if P1 fails, as a small frozen world (engine-feasibility.md).
  - Event-driven updates and interruptible actions: patterns to investigate later in our own code.
- **Boundary:** no in-game evidence yet. The settlement saturation found on the real pack was fixed offline on
  21 October ("Commonwealth-scale baseline" in `docs/combined-core.md`), and it still needs a rerun on the real pack.

## 2026-10-28: which outside tools we use (Claude-cloud)
- **Decision:**
  - **Keep:** xEdit, Mutagen, texconv, Archive2, the official Papyrus compiler and SFSE.
  - **Use when the next work needs them:** texdiag and the fo76utils NifSkope fork, as independent texture and mesh
    checks. JPEXS for the map and menu work. Cassiopeia, checking its functions before writing our own hooks.
    Spriggit, for private plugin diffs.
  - **Later, for a named job:** CommonLibSF, Champollion with B.A.E., PresentMon, Blender with Starfield Geometry
    Bridge, CKPE and Tracy. Ghidra or a debugger only on the owner's word.
  - **Not now:** Caprica, Bethesda Multitool, and the Rust, SimPy, BehaviorTree.CPP, Recast/Detour and FastNoise2
    libraries.
- **Why:** the owner asked for a verdict on the tools Codex researched
  (`docs/research/framework/modding-tool-workflows-oct25.md` on #553). Installing software on the PC is the owner's
  call, so this list installs nothing.
- **Boundary:** none of these has been tested on our build. Cassiopeia is not bundled. CommonLibSF's licence is
  checked before anything built on it ships.

## 2026-10-29: test our own star system on a small probe world before the Commonwealth moves (Claude-cloud)
- **Decision:**
  - PR 1 of the plan to strip Starfield down and give the Commonwealth its own planet is a probe kit
    (`docs/planet/planet-probe.md`). It holds our own star system and planet (FO4SFPlanet.esm, cloned from the user's
    Starfield.esm at stage time) and a 3 x 3-cell test world on that planet with six test references. It also holds
    a script that logs which of them are in the player's world.
  - The master is written with our own raw record writer (`src/fo4sf/planet/esm.py`), because Mutagen 0.55 drops
    star fields it does not know. The test world is written with Mutagen (`dotnet/PlanetProbe`), as our other worlds
    are. A raw Python check reads the three plugins this kit writes back (the master, the registration and the
    probe); the merge probe keeps MergeProbe's own Mutagen check. The stage pins all four by hash.
  - The probe rides along with the installed experiment: `scripts/planet/planet_probe_install.py` runs exp_install.py's
    code against a record of its own, so the core set is never touched.
- **Why:** our characters stay in a base world the player never plays (verified 29 Oct). Two fixes have failed, and
  two (the location links, MergeProbe) were never tried. Moving the Commonwealth first and then finding that the new
  planet has the same split would waste the biggest step of the plan. The probe tests both questions in one session.
- **Alternatives:**
  - Move the Commonwealth first and test there: rejected, because one failure would mix up several causes.
  - Write the master with Mutagen: rejected, because it would lose STDT SNAM, HNAM and WED0.
  - Use SFStarEditor: its layout was read as a reference only. Its code is CC BY-NC-SA, and none is copied.
  - A planet in Sol (route B) has Bethesda precedent. It is the fallback if our own star system does not load.
- **Boundary:** nothing has run in game. The owner's line in the Install thread stages and installs it.

## 2026-10-29: the local team runs Qwen3.6-35B-A3B at 128K; the 14B stays as a manual fallback (Claude-cloud)
- **Decision:**
  - The four local agents (`tools/ai-team/config.json`) use `qwen3.6-35b-a3b`. `load_model.py` loads it at 131072 tokens
    with memory mapping off, flash attention on and an unquantized K/V cache, all sent explicitly. `opencode.json` asks
    for the same context and a 32768-token output.
  - The 14B stays on disk and loads with its old settings (`--model qwen3-14b --context 32768 --gpu 1 --kv q8_0`). It is
    a manual fallback: `run-lead.ps1` loads only the 35B and never unloads another model.
- **Why:** the owner wants precision on very large prompts while cloud models are away. The 35B measured 83.4% RAM and
  10.9 GB VRAM at 131072 with memory mapping off, under the 90% RAM block. Its thinking takes 3,000 to 6,300 tokens per
  answer, so the output cap must not be 4,096.
- **Alternatives:**
  - Keep the 14B as the default: rejected by the owner (precision and context).
  - Quantize the K/V cache to fit more context: not done. The owner's rule is no K/V quantization without asking.
- **Boundary:** at 8K, test 1 (leader-core summary) graded 37 of 45 claims correct, 8 partly correct, none wrong. At 128K,
  test 2 passes 4 of 5 generated tests. Long-context tests 5a to 5c and test 4 (Guardian) are not yet run. RAM sits 1.6
  points under the 85% restrict level, so requests queue before the 90% block. Not merged: PR #587 waits for review and
  the owner's approval.

## 2026-10-29: our errors are told from Starfield's by a vanilla baseline; the quieting goes into the mod (Claude-cloud)
- **Decision:**
  - The owner answered the strip-down plan's questions on 29 Oct (thread "Strip down Starfield and add our own
    planet"). Pick I: the switches that quiet Starfield's own quests go straight into the mod, so there is no
    test-only profile plugin. Pick T: Install's session on the owner's PC plays the vanilla baseline.
  - `scripts/game/baseline.py` (docs/testing/baseline.md) turns off every plugin the game does not ship, keeping every
    other byte of Plugins.txt. It records the built-in plugins and Starfield.exe, and after one plain New Game it
    collects the Papyrus log and puts Plugins.txt back byte for byte. `compare` sorts a run's errors into "only ours",
    "only in the run, Starfield's own scripts", "at the same script line in both", "in both" and "only in the
    baseline" (`src/fo4sf/core/papyrus_log.py`).
  - A session counts as vanilla only when its log names none of ours, Plugins.txt shows no plugin the game does not
    ship ticked again, and SFSE wrote no log meanwhile. Otherwise its log is kept aside and the baseline gets none.
  - While a baseline is open (its note in the runner's state folder names it and its restore has not run), the test
    runner installs and launches nothing, since a launch would load our plugins into the baseline's session. A note or
    record it cannot read stops it too (the gate's "any unknown refuses"), and `prepare` reads the note the same way,
    so it never writes over the only pointer to a baseline that may be open. `prepare`, `collect` and `restore` take
    one lock in that folder, so two of them do not change one record or Plugins.txt at the same time.
  - A session of a game that changed between `prepare` and `collect` (a Steam update) is no baseline either: which
    build it ran on is not known.
  - The deployment gate gets two checks (`loaders`, `start`, docs/ai/leader-core.md section 7). Their rules are in
    `src/fo4sf/core/loadset.py`, which reads nothing, and `src/fo4sf/launcher/loadprobe.py` reads the PC for them, so
    the core still reads nothing on the PC. They refuse an `sTestFile`, a `Starfield.ccc` that lists a mod, and a
    plugin copy in `My Games\Starfield\Data`. They also refuse an unexpected override of `StartupQuest_DO`, `MQ101`
    or `MQ101Debug`. Our own start (pick F) may override `StartupQuest_DO` without a pin. One rule says what is ours,
    for plugins and for names in a log: it starts with FO4 or FOCC.
- **Why:** run 3's log (28 Oct) mixes our errors (28 from our map marker script, `FO4SF_MapMarkers.psc`) with errors
  from Starfield's own scripts (SFBGS003's shutdown script among them), and nobody knew which of Starfield's come in a
  vanilla game too. Without a baseline every one of them looks like ours. The 28 Oct pirate fight was our own
  override of `MQ101Debug`. A plugin list or start record that no one meant to test is
  cheaper to refuse before a run than to find in its log.
- **Alternatives:**
  - A test profile plugin that quiets Starfield for test runs only (pick H): the owner chose I instead.
  - Filtering the logs by hand: rejected, because it is the guessing this replaces.
  - Extending `plugin_toggle.py` to hold every plugin off: rejected, because it holds only the plugins our installers
    own, with master-chain rules the baseline does not need. The baseline turns everything off and restores the
    bytes, so a hold record would add nothing.
- **Boundary:** nothing has run on the PC. The game rewrites Plugins.txt at startup (verified,
  docs/research/framework/launcher-sources/sfstack.md). Restore therefore writes over a rewrite that ticked nothing,
  and refuses one that ticked a plugin unless `--force`. Whether the game reads a plugin copy in My Games instead of
  the one in Data is a supported hypothesis (what the loader rule implies), so the check refuses either way.

## 2026-10-29: the vault start goes 0.3 m above the pod; the ride's arrival waits a tick (Claude-cloud)
- Decision: newgame_v10 puts the player `PodLift` (0.3 m) above the pod's z and logs a `pod settle` line the first
  loaded tick after the move, moving nothing again; the elevator ride is two ticks, MoveTo first and the SetPosition on
  the merged arrival on a later tick once the player is outside and loaded, read back and tried up to three times
  (docs/newgame/vault111-start.md section 12).
- Why: the owner's third new game (28 Oct, newgame_v9) reached stage 200, but the player sank under the floor at the
  pod's own z and the game stood them on the COC marker 8 m away; on that marker they stood 0.18 m above the pod's z,
  and 0.3 m is the marker's own height. The ride's SetPosition in the MoveTo's tick was ignored, and the landing
  check's SetPosition 5.7 s later took; the load door already waits between the two.
- Alternatives: a retry MoveTo when the settle check fails (rejected for now: a second sink would show the owner two
  falls, and the game's reset to the marker already leaves them standing); the COC marker itself as the start (8 m
  from the pod; kept as what the game does on a sink).

## 2026-10-29: the guardian's RAM restrict level goes from 85% to 88% (Claude)
- Decision: `tools/ai-team/config.json` `restrict_pct` is 88 (was 85). Caution (70%) and the RAM block (90%) stay.
  `policy.py`'s built-in DEFAULTS, used only when `config.json` lacks a key, are unchanged.
- Why: the owner's choice on 29 Oct. With Qwen3.6 loaded at 128K the team PC idles at 85-88% RAM (LM Studio's engine
  alone holds ~16 GB), so the guardian held the model's own work: a PR-summary request waited 600 s and got HTTP 503 at
  RAM 87.3% (proxy.log job 66), and the next one queued at 87.0% (job 67). Loaded at 64K the same PC sat at 78% RAM idle (the README table's 79.9% is measured at load).
- Alternatives: load at 64K instead (`load_model.py --context 65536`; no guardian change, but long prompts lose room);
  keep 85% (local work runs only when RAM dips under it).
- Boundary: 88% leaves two points before the 90% block. A request that is already running is not stopped when RAM rises
  (README); only new admissions are held. With no model resident, the same 88% also sets the VRAM restrict level (policy.py:53).

## 2026-10-29: our own start: the new game's quest is Starfield's startup quest (Claude-cloud)
- Decision: newgame_v11 overrides the DefaultObject `StartupQuest_DO` (Starfield.esm 00562D, MQ101 in vanilla) to name
  FO4SF_NewGame, which is no longer start-game enabled. The quest moves the player into the vault itself during the
  first load (from `OnQuestStarted`, or `OnQuestInit` if that comes first, once), fades the screen in once the player's
  3D has loaded (never before: both callers check it), and keeps the hold-off (both passes, after the move) and the
  MQ101Debug write of 2 (after pass 1). A start that is not a new game (a New Game+) or cannot move the player stands
  down and, when either reading says the game is still loading (the player's 3D not in, or no cell yet), first asks
  MQ101 to start (a request that waits for nothing, before our own stage), so that MQ101's stage 0 moves the player and
  the first load ends (unverified until a run stands down during that load; run 4 should not). The guard is days and
  level alone. The temporary-anchor mode is built only on request (`--allow-temporary-anchor`): its centering during
  that load cannot be judged, and one that moves nobody hands nothing back. This replaces the 28 Oct entry's "overrides
  no record" for the start record only; MQ101 and MQ101Debug stay untouched (docs/newgame/vault111-start.md sections 1,
  2, 3a and 13).
- Why: the owner, 29 Oct (typos fixed): "too many things are breaking because we are forcing ourselves into the
  Starfield system", and their pick F (our own start) for the strip-down. v9 and v10 let MQ101's stage 0 run and then
  undid it: they stopped the opening, restored saving and the HUD, and left the miner suit on. Owning the start removes
  all of that, and no save should ever start our quest. Shipped precedent: Roleplayers' Alternate Start (its startup
  quest moves the player from `OnQuestStarted` and fades in once its start cell has loaded) and No Ship Fast Start
  override the same record. The first fresh review of 29 Oct on #588 found the fade could fire under the loading screen
  and two paths that could still leave the first load hanging: the fade and the one-reading stand-down are fixed, and
  the temporary-anchor path is gated (built only on request). The second found the hand back's effect stated as fact and
  a stalled hand back invisible in the log: it is labelled, the request no longer waits, and the log reader and the
  timer's wait now show it.
- Alternatives: keep stopping MQ101 (newgame_v10; the way back if run 4 fails, by restaging main d9958261); a stage 0
  fragment on our quest, the way MQ101 moves its player (held: a fragment script and more records, for if neither start
  event fires during the load); `Game.FastTravel` instead of MoveTo (the precedent's call; not taken: MoveTo with the
  pod's offset is what run 3 and the map test verified, and MQ101's own intro moves its player with MoveTo during this
  load); moving the player to MQ101's own `CharGenStartMarker` before the hand back, so that load ends whatever MQ101
  does (held: no run has stood down during the load yet; the next step if a hand back ever leaves the loading screen
  up); overriding MQ101 or MQ00 (option C: rejected, it edits Starfield's quests).
- Boundary: not run in game. Which start events fire during the load, what ends the loading screen on 1.16.244 (the
  move, or the fade call) and what the player wears without MQ101 stay open until run 4 (section 13); whether a hand
  back moves the player stays open until a run stands down during the load.

## 2026-10-29: the unattended Lead runs no QA reviews (Claude-cloud)
- Decision: the prompt in `tools/ai-team/run-lead.ps1` no longer gives the unattended Lead the QA task (needs-qa PRs
  through fo4-qa, verdicts as `QA (local):`); it says fo4-qa is not called in those sessions. Research, the status
  refresh and the one comment on #32 stay. `opencode.json`, the fo4-lead and fo4-qa agent files and AGENTS.md are
  unchanged, so interactive sessions keep fo4-qa.
- Why: the owner's pick in the thread on 29 Oct, sent with the 128K reload ("128k and drop QA").
- Alternatives: keep QA and treat its verdicts as drafts for a fresh Claude review to weigh (the owner's other option;
  not taken).
- Boundary: a text change, not yet run from the PC checkout; the first unattended session is the check. No merge gate
  changes: a PR still needs a fresh Claude review and green CI, and the unattended Lead does not merge.

## 2026-10-29: Guardian's VRAM restrict with a resident model goes from 92% to 94% (Claude-cloud)
- Decision: `vram_restrict_with_model_pct` goes from 92 to 94 in `tools/ai-team/config.json`, and the matching default in
  `tools/ai-team/guardian/policy.py` moves with it. `vram_block_pct` stays 95. The model stays loaded at 128K (131072
  context), as the owner asked on 29 Oct ("128k and drop QA").
- Why: after its first request, LM Studio keeps GPU working memory reserved while the model sits idle. With the 128K
  load, VRAM reads 92.5% (11.36 of 12.28 GB) with nothing running, so Guardian held every request from the unattended
  Lead at the 92% line and refused them after the 600 s queue wait (HTTP 503). Cycle 2 never reached the model.
- Alternatives: reload at 64K, which brings VRAM to about 85% with no config change but gives up the 128K. The owner
  chose 128K with the 94% line on the decision card.
- Boundary: the 95% block still refuses new work above 95%, so this lets the 128K load in without removing the limit.
  Applying it restarts Guardian, which drops its queued and running jobs. Restart run-lead after, since its failure
  backoff resets on restart.

## 2026-10-29: our planet goes in Sol, under Sol's own system location; the probe asks the location chain both ways round (Claude-cloud)
- Decision: the planet probe builds route B by default (`stage --system sol`; route A stays as `--system own`).
  FO4SFPlanet.esm adds our planet (a Jemison clone) to Sol with Sol's system id (its star's DNAM, read at stage time)
  and the first planet id free in Sol: one more than the largest body id, location YNAM and overlay world planet id
  there, across Starfield.esm and every other plugin in Data, overrides too (an id that reads negative is taken for
  unset and not counted: our convention), held to Data again by `check --data` and by the install. Its planet
  location names Sol's own system location as its parent. No star, no system location and no override of a
  Starfield record. Version 2 of the probe script asks IsChild both ways round and lists the parents of each of our
  three locations (GetParentLocations, with no keyword and the keyword lookups SQ_ParentScript uses), ending the line
  with `end=true`; the reader calls a link broken only when every reading of it says so, notes readings that
  disagree, a cut line and that a version 1 line settles nothing, and leaves the 3.4e38 distance of another
  worldspace out of the table (docs/planet/planet-probe.md sections 3a, 5 and 8).
- Why: the owner's pick B, 29 Oct (typos fixed): "B, but in the end there should be no other planets". Run 1 (route
  A) showed that our planet loads from our records, so the open question is Sol, not the planet record. Run 1's chain
  line read false and false, but version 1 asked IsChild one way only, on the child, and which way IsChild reads is
  unresolved: Starfield's Location.psc says it "Returns whether the other location is a child of this one" (the
  parent asks), while some vanilla quest scripts (MQ204's, UC04's) call it on the child. Taking the planet id at stage
  time keeps a Creation or mod that adds a body to Sol from colliding with ours.
- Alternatives: a fixed planet id (rejected: a plugin that adds a body to Sol would collide); taking over Starfield's
  Earth (the plan's option C, not picked); our own star system (route A, run 1's: kept as the fallback); a system
  location of our own in Sol (rejected: it would give Sol two system locations).
  The first 29 Oct entry's "Bethesda precedent" for route B is softer than it read: the Creations add bodies to
  vanilla systems, but all four are body type 4 and none is a planet with a surface.
- Boundary: offline only (synthetic masters and the Creations' records, in the cloud). Whether the game takes a
  plugin's planet in Sol, whether the free id is what it expects, and what the chain really is wait for run 2 on the
  owner's line. The orbit stays Jemison's (next to Mars) for the probe; for the final planet the owner picked Earth's
  orbit (29 Oct, "A").
  Hiding the other planets (the owner's X) is separate work.

## 2026-10-29: the local provider's header timeout goes to 900 s (Claude-cloud)
- Decision: `provider.guardian.options.headerTimeout` in `opencode.json` goes from OpenCode's default 300000 ms to
  900000 ms. It sits above Guardian's `queue_wait_s` (600), so a request that Guardian holds can wait out the hold
  instead of the session dying at 5 minutes. `chunkTimeout` (300000 ms between streamed chunks) stays the default.
- Why: the first unattended Lead cycle on the 128K load failed at 16:42 local. A model call sat in Guardian's queue
  while RAM read 88.4 to 88.9% against the 88% restrict line, and OpenCode gave up after 300 s ("Provider response
  headers timed out after 300000ms"). The session ended with nothing written.
- Alternatives: 64K, which the PC reads as the only lever that moves RAM materially (about 78%). Not taken: the owner
  chose 128K with longer waits on the decision card. Shorter Guardian holds (fail fast) were not taken: they end
  sessions sooner and give no request a chance to clear.
- Boundary: at 128K RAM still sits above the 88% line, so a hold can still outlast 600 s. If the next unattended cycles
  stall, the fallback is 64K. The 88% restrict, the 95% VRAM block and Guardian's queue wait are unchanged. The test
  `test_provider_header_timeout_outlasts_guardians_queue_wait` keeps the two in order.

## 2026-10-30: the Lead works only inside its own worktree (Claude-cloud)
- Decision: `.opencode/agents/fo4-lead.md` tells the Lead to start in its worktree root, run every command there with
  plain relative paths, and never `cd` into another folder or read or write another worktree. Permissions are unchanged.
- Why: the 00:02Z cycle ran `cd` into the parent folder that holds the other worktrees. OpenCode auto-rejected
  external_directory in the unattended run, and the cycle ended after 54 s with no work. Guardian was healthy in that
  cycle (two jobs returned in 20 and 29 s), so the fault was the Lead's directory, not the queue.
- Alternatives: widen external_directory to the parent folder. Not taken: it would open the sibling worktrees to the
  Lead, and the prompt rule needs no access the Lead does not already have.
- Boundary: the rule covers the Lead only. The delegated fo4-implement, fo4-research and fo4-qa agents do not have it
  yet; if one of them hits the same rejection, the same line goes into its agent file.
  `test_the_commands_the_lead_is_told_to_run_are_allowed` checks that the prompt's example commands match the Lead's
  bash rules.

## 2026-10-29: the guardian's RAM restrict level goes from 88% to 89% (Claude)
- Decision: `tools/ai-team/config.json` `restrict_pct` is 89 (was 88). The RAM block stays at 90%; with no model
  resident the same 89% also sets the VRAM restrict level.
- Why: the owner's word on 29 Oct ("I thought you allowed more than that usage on the RAM"). The first Lead session
  after the 22:00Z restart (Qwen3.6 at 128K) failed: from 16:12 local its requests 109-114 were held at 88.4-88.9% RAM
  (proxy.log), and OpenCode gave up on a provider after 300 s without response headers, so the session ended at 42
  minutes. At 89% those requests would have been admitted. A trim loop (D:\lmstudio\tools\trim-claude-loop.ps1, every
  60 s above 86%) keeps the Claude app's working sets down at the same time.
- Alternatives: load at 64K (done in the next entry); restrict at 90% (would equal the block and remove the warning
  band); raise OpenCode's header timeout above the guardian's 600 s queue wait (done in #600).
- Boundary: one point of headroom before the 90% block; working peaks of 90.3% still block briefly.

## 2026-10-30: the local team runs the 35B at 64K, and the Lead commits only its docs (Claude)
- Decision:
  - `load_model.py` defaults to 65536 tokens (the SDK's 1 h idle TTL stays); `opencode.json` limits the four agents to
    65536 with an output limit of 16384, so OpenCode compacts a session at about 49K tokens (context minus output)
    rather than 33.5K. A 128K session by hand also needs the limits raised locally.
  - The Lead's only git write is `python -I tools/ai-team/lead_commit.py "<what changed>"` (`-I`: no script folder on
    `sys.path`, `PYTHON*` variables ignored; git runs with every `GIT_*` variable removed, `core.hooksPath` at the null
    device and `--no-verify`), which commits only `docs/ai/` (`git commit --only -- docs/ai/`) on `ai/local-lead` with a
    `Lead (local): ` subject and refuses anything else (another branch or a detached HEAD, unmerged files, a
    merge/cherry-pick/revert/rebase in progress, anything staged outside `docs/ai/`, renames counted by their source).
    `fo4-lead.md` allows exactly that command and denies `gh pr review*` and `gh pr comment*` (`gh pr review *
    --comment*` was still allowed on main; #592 only kept reviews out of the prompt).
  - Any command containing `>`, `--output` or `--no-index` is denied: `"*--output*"`, `"*--no-index*"` and `"*>*"`
    (in that order, with `"*>*"` last) are the final bash rules globally (`opencode.json`) and in all four agent
    files, after the git-specific denies #603 added (`git diff/log/show --output`, `git diff --no-index`, the
    git-diff outside-path denies, and the Lead's `gh` flag denies). OpenCode's `evaluate` takes the last matching
    rule in file order (`fromConfig` keeps the order, `merge` concatenates, and an agent file comes after the global
    block), and a redirect is matched as part of the command's text, so this blocks the plain forms `cmd > file`
    (including `2>&1`), git's `--output=<file>`, and `git diff` reading an outside file whether through `--no-index`
    or a bare absolute/`~`/`$`/`../` path (git switches to no-index on its own when a path is outside the worktree).
  - `run-lead.ps1`: the prompt points the Lead at the wrapper, asks for gh and git without pipes or redirects and for no
    `>` in comment text, and names docs-only or research issues labelled `agent:local-team` + `ready` as good tasks
    (no code changes, no fo4-implement; research and the status refresh stay, as in the #592 entry). It logs a failed
    `git pull` of main (it was sent to `$null`), skips the cycle before the pull when the Lead's worktree is not on
    `ai/local-lead` (so no other branch is rebased), and skips it after the pull while there are unmerged files.
- Why: the owner's word on 29 Oct ("you can go to 64k but you upload the permissions needed"). At 128K, with the Lead
  working, the PC sat at 87-91% RAM and 92.5% VRAM and the guardian held its requests; at 64K it sat at 78.8% RAM /
  10.6 GB VRAM idle after the load and up to 90.3% RAM / 10.85 GB VRAM while the Lead worked (job 136 held at 19:43).
  The 18:33 local cycle ran `gh issue view 29 ... 2>&1 | head -200` for #29-#32 and every one was refused at the
  `head` stage (OpenCode checks each command of a pipeline), so it could not read its issues. The session-1 edit left
  uncommitted collided with #597 on the next pull, and the pull's error was discarded. An independent review of head
  a82e55cb showed that a redirect behind an allowed `git log*` could write a Python file that `lead_commit.py` would
  import, or a git hook that its commit would run; the next check showed the same through git's `--output=<file>`
  (no `>` needed), that the subagents' own `git log*` allows came after the global deny, and that the allowed
  `git diff*` reads any file with `--no-index`.
- Alternatives:
  - No idle TTL (rejected in review: nothing would free the GPU when a game test starts; with the 64K default the
    hourly reload no longer changes the context).
  - Raw `git add docs/ai/*` / `git commit -m *` allows (rejected in review: OpenCode's wildcard also matches `-a`,
    `-f`, `--amend`, `..` and extra pathspecs).
  - Allow the read-only filters `head`, `tail`, `grep` and `wc` (rejected: with a path argument they read any file on
    the PC, which the Lead could then post on #32); the prompt asks for commands without pipes instead.
  - Keep the 32768 output limit (rejected: with it OpenCode compacts at about 33.5K, below the 46K the Lead's sessions
    reached).
- Boundary: the `>` deny also refuses a `>` inside quoted text, such as a #32 comment that says "RAM > 85%".
  fo4-implement may still edit any file through its edit permission; only the prompt keeps the unattended Lead from
  delegating to it (`task` still allows it). These are pattern rules on single command nodes, not a sandbox, and an
  independent review of head dbdac7da showed they do not make the shell safe: some command shapes and settings are
  never checked. The two-path `git diff` outside-read it found is now denied by #603's path-shape rules, but others
  remain (for example a path built by shell expansion or command substitution, tracked in #604). So the unattended
  Lead must not run on untrusted input (it reads public issues) until a check before every shell call (an OpenCode
  plugin) or a restricted OS user is in place; it stays paused until then. 64K
  makes holds rarer, not impossible (working peak 90.3%). A held streaming request whose
  connection was closed without a response (job 79 at 12:44, the 16:54 session's "socket connection was closed
  unexpectedly") is what #601 addresses; the running guardian picks #601 up when it is restarted.

## 2026-10-30: the unattended Lead's shell calls go through an exact allow-list (Claude-cloud)

- Decision: every shell call the local team makes passes `tools/ai-team/guard/allowlist.py` before it runs. The OpenCode
  plugin `.opencode/plugin/fo4-guard.js` sends the command text on stdin (no shell involved) and throws unless the
  checker exits 0. The checker accepts only the argument lists in its docstring and README section, refuses shell
  syntax, expansions and quote characters outside the allowed forms, and runs commands from the repo root only (an
  adversarial pass showed a subfolder the agents can write to would let a planted file change what an allowed command
  runs). Unattended runs (`FO4SF_UNATTENDED=1` from `run-lead.ps1`) also refuse delegation to fo4-implement. Two grants
  are narrowed: `wake_agent.py codex|grok` is refused, and `team.py *` becomes `board` and `status`.
- Why: the pattern rules leak in shapes they do not see (git's automatic no-index read outside the repo, a `$(...)`
  built after the check, a workdir pointing elsewhere), and the Lead reads public issues. An exact list refuses what it
  does not name instead of trying to name every bad shape. The owner chose A on 30 Oct: build the guard, then turn the
  Lead on.
- Alternatives: keep adding pattern denies (rejected: each new shape is a new hole, and that is how #603 came about);
  a restricted Windows user (B, the strongest boundary, but only the owner can create it; it remains an option on top);
  stay with the Lead paused (safe, but it does nothing).
- Review (30 Oct, NOT CLEAR at d0423d43, fixed in the next commit): unittest names now stop at an existing
  `tests.test_<name>` module (a longer dotted name made unittest call a non-test `main()`); the session's folder must
  be the worktree root and a workdir only absent, `.` or the root (a session opened in a subfolder ran calls there);
  OpenCode only logs a plugin that fails to load, so the plugin now adds an `X-FO4SF-Guard` header to every model
  request and the proxy refuses inference without it, and `run-lead.ps1` skips a cycle when the pull fails or the
  worktree lacks the plugin or checker; the tests now load the plugin in node. Also: the shell check runs for the
  `bash` tool only and the fo4-implement rule compares `subagent_type` exactly (a slash-command `task` and a brief
  mentioning fo4-implement were refused by mistake); quoted `& | ^ % < >`, number-shaped bare arguments and `~` after
  `=` are refused; `wake_agent.py status` and `guardian.py report --hours <n>` are allowed; the Lead's procedure no
  longer asks it to wake agents, push or open PRs (claims and labels were still asked for: fixed in the second round).
- Second round (30 Oct, an independent check of the fixes: the five findings hold, plus small items): tests/ became a
  package (a `tests` package elsewhere on sys.path won over the folder) and unittest by name runs without `-I`;
  unittest also takes one TestCase class or test method that the file defines (read from its syntax, so nothing else
  is called); an empty or `./` workdir counts as the root; tools the guard does not know (an MCP server's, a custom
  tool) are refused; `run-lead.ps1` skips when the running proxy does not refuse a request without the header (one
  started before this PR) and hands the plugin a full Python path; the Lead's procedure claims work in its #32 comment
  and leaves labels to the owner; the tests now pin every refused character, the 15 s cap, `-I`, the proxy's 403 over
  HTTP and the Windows path rules.
- Follow-up (30 Oct, the re-review at 8457816c was CLEAR with nine low notes, all taken): unittest names now accept
  unittest's skip marks on methods, `import unittest.mock` next to `import unittest`, and same-file mixin bases (a scan
  of all 704 runtime TestCase classes and the 3848 test methods defined in their bodies found none refused, and
  nothing allowed that unittest would not treat as a test; before, 15 classes with their 151 methods and 17 more
  methods, 168 names in all, were refused; the 157 test ids a class inherits stay refused and run through the class
  or the module); `-I` is refused for discovery too;
  `run-lead.ps1` resolves Python and OpenCode before it writes the pid file or sets the environment, does both inside
  its `try`, and gives a dot-sourced window its own `FO4SF_*` values back; the Lead's comment rules list everything
  OpenCode's own denies match (`-r` and `-f` in either case, `--edit-last`, `--delete-last`); the plugin tests fail
  in CI without node instead of skipping, and their timeout cases use a Python sleeper so they run on Windows too; new
  tests cover a subfolder session with a relative workdir, the exact list of known tools, the header for every agent,
  a header-bearing request reaching the model, the run-lead lines exactly, and one step looser for each allowed
  command. A second self-check then tightened what counts as a test: a name bound anywhere else in the file (in a
  block, by a `global`, an except-as or a match capture, or a star import) no longer counts; only unittest's own
  marks in their own form do (`expectedFailure(x)` returns `x`); and no mixin or case may define
  `__init_subclass__`, nor a mixin any dunder method. `run-lead.ps1` takes only files found on the path for Python
  and OpenCode (no alias or function; a `.bat` or `.cmd` matches too and then fails closed), ends a run whose pid file is deleted or taken over, and removes the pid file only while it is its own.
  The Lead and fo4-implement may not write a nested `.opencode/` folder or `opencode.json`. More tests: a program
  named by a path or with an extension, every PowerShell number form, `-I` against a `json.py` beside the checker,
  every working-directory argument name, a 1 s timeout that really takes about 1 s, and a 16 s checker past the cap.
- Second follow-up (30 Oct, the review of #606 at a0c9e48b was CLEAR with six low notes, all taken): the test-name
  rule now reads only same-file bases defined above the class (below it, `class C(Warning)` would subclass the
  builtin), counts a class-body `global`, and drops a method's marks when the class body binds `unittest` itself; it
  reads syntax only and trusts the repo's own test files, with the runtime scan as the evidence. fo4-implement may not
  write a root `opencode.jsonc` either. `run-lead.ps1` treats an empty or garbled pid file as stale (`[int]''` is 0,
  the Idle process), and one whose pid now belongs to a process that is not PowerShell, or to itself. New tests: the cycle from `$cycle++` to the launch pinned as text (each skip and its `continue`,
  the guard files read after the pull); elsewhere in the script one Start-Process-style launch, the call operator
  only on the resolved Python, no dot-source call, and no environment change but the pinned lines and the final
  restore (a regression net for reviewed edits, not a PowerShell parser); the provider address `:1235`, every agent
  model on it, and no other config or agent file in the repo that OpenCode would merge; and the reviewer's five
  test-name shapes. The Lead's prompt and agent file give the #32 comment and lead_commit forms the guard takes; the
  README says that some test modules import only under discovery. Two notes were checked and kept
  as they were: OpenCode's matcher flags are fixed per build (`s` in the 1.18.35 Linux build, `si` on Windows), and
  the plugin tests skip without node unless `CI` is set.
- PC check (30 Oct, owner's go, main a9921b46): the proxy refused a POST without the header with (403) Forbidden, and
  the plugin loaded (no load error; model requests passed the gate). With `FO4SF_PYTHON` set to the real
  `python.exe` (Python 3.14 from the install manager), `git status --short` ran and `git log -1 --format=%H` was
  refused with `shell syntax is not allowed: %`; `git rev-parse HEAD` passed the guard and OpenCode's own rules then
  refused it. With the plain `python` on that PC, the Microsoft Store alias, every call came back `no verdict from the
  guard`: Bun cannot start the alias (node can). One call, a backtick in a `--format`, also came back with no verdict
  under OpenCode while node gets the checker's refusal; not reproduced. Every case failed closed. So `run-lead.ps1`
  now passes Python's own `sys.executable` and refuses an alias, the plugin refuses an alias path with the fix, and a
  no-verdict refusal names the Python and what became of it. The Lead stays paused until the check passes with
  `run-lead.ps1`'s own resolution.
- Third follow-up (30 Oct, the review of #607 at d7890d39 was CLEAR with three low notes, all taken): the plugin no
  longer falls back to a bare `python`. It refuses every shell call while `FO4SF_PYTHON` is unset or not a full path,
  because a bare name is looked up at start, and on Windows that lookup may try the session's folder (the repo) before
  PATH. `run-lead.ps1` always passes a full path, so the unattended Lead is unchanged, and any other session sets the
  variable. The checker now prints `{"allowed": true}` with exit 0, and the plugin needs both, so a wrong program
  behind `FO4SF_PYTHON` that only exits 0 refuses too. A test covers a refusal with no usable reason.
- Lead turned on (owner's A, 18:08Z 30 Oct). Its first cycle did no work: the Lead wrote
  `python -I tools/ai-team/guardian/guardian.py status`, which the guard takes but OpenCode's rules did not (they
  allowed only the form without `-I`), and an unattended run ends at the first command its rules would ask about. The
  rules now allow both forms of each team script (the Lead's guardian, team and wake_agent reads, QA's and
  implementation's `scripts/guard.py`, and the guardian reads in `opencode.json`). A test runs every script form the
  guard takes through the rules of the agents that use it, and checks nothing wider (other scripts, `-c`, `-m`, the
  agent wakes) is allowed. The review of #618 found `scripts/guard.py*` (QA and implementation, on main and in its new
  `-I` form) let a script path run on through `guard.py` as a folder: on Windows `scripts/guard.py/../../x.py` runs
  `x.py`. Both are now the exact command, the negative checks run with both platforms' matching and cover the
  guardian's switches, extra arguments and such paths, and the guard's tests refuse `python -i` (which OpenCode's
  Windows matching cannot tell from `-I`). The Lead's file also says to write `python` and only the four git reads.
- Not yet true: the checker and plugin are tested here (`tests/test_ai_guard.py`, the plugin under node), not on the
  PC. OpenCode 1.18.35's own build was read for the hook order, the `bash` tool id and its arguments and plugin
  discovery (the review), and for `chat.headers` reaching every model request (the second round). The install must
  show, before the Lead is turned on: the agent asked to run `git log -1 --format=%H` (allowed by OpenCode's `git log*`
  rule) gets a tool error saying `guard refused the command`, `git status --short` still runs, and a POST to the
  proxy without the header fails with (403) Forbidden. A redirect such as `echo x > y` is a poor check: OpenCode's
  own rules refuse it too, so only the error's wording would show which layer did. A command typed with `!` in the
  terminal UI is not a tool call.

## 2026-10-30: one desktop menu, a guarded terminal for the local agents, and a model pick the whole team follows (Claude-cloud)

- Decision: the owner chose A, C and E on 30 Oct: OpenCode's own terminal UI on the team's agents with the guard on
  (A), one "FO4SF AI" desktop menu to start the team, open its terminal, start Claude Code, show status, pick a model
  and stop (C), and Claude-cloud builds it in the repo while the PC session only installs and tests (E). Their
  answers at 18:31Z and 18:36Z set the rest: J (the coding agent commits on its own `ai/` branch in their terminal,
  never pushes), L (the terminal has its own worktree), P (only the measured setups can be picked), Q (the guard
  checks every session, as it does now), and A (two models only: the 35B at 64K and the 14B; the 128K window is
  dropped).
  - `models.py` keeps one pick (one of the two presets in `config.json` "models", by name) in `guardian.db`. The
    guardian proxy sends every agent to the pick's model when it is a preset's, read when a request is admitted, and `terminal.ps1` and
    `run-lead.ps1` pass its limits to OpenCode through `OPENCODE_CONFIG_CONTENT`. A load takes a hold on the proxy
    (one load at a time; the proxy starts no job while it stands), refuses while a request runs, unloads the team's
    other models and the last pick, and never touches the owner's pause or stop. A failed load leaves the hold as
    "failed", and the proxy refuses requests until a load works. `run-lead.ps1` loads the pick (`models.py ensure`,
    which also reloads a model at another context) instead of matching one model name.
  - `terminal.ps1` runs in its own worktree, which goes back to main (no branch) at each start with no other terminal
    window open, carrying uncommitted edits made with no branch (an agent's branch with uncommitted edits stays, and so
    does an edit that clashes with main's newer copy of its file, on its older commit), and sets
    `FO4SF_OWNER_PRESENT=1`. With it, the guard also allows `agent_git.py`: a branch from main and commits of named
    files (literal paths) on the agent's own `ai/` branch, with no hooks, and the wrapper never pushes (the owner's J),
    and a `Lead (local): for Claude:` handoff on #32, which unattended runs cannot post. The three specialists are
    `mode: all`, so the terminal opens each of them. Skills from outside the repo stay hidden from the team, which keeps
    one skill of its own (`fo4-allowed-commands`, every example checked against the guard by a test).
  - The guard now also checks file writes: nothing outside the repo, nothing under the team's own rules, tools, skills,
    CI or git's files, no AGENTS.md, CLAUDE.md or CONTEXT.md in any folder, no OpenCode config file or config folder
    (`.opencode`, `.claude`, `.agents`, `.git`, `.github`) in any folder or spelling,
    no folder in place of a file, and only from a session at the repo root. The agents' edit rules said most of it
    already; the checker holds where a pattern misses, for the writes and commands an agent makes itself.
  - What it cannot hold in the terminal: the coding agent writes tests and runs them, and a test can run any code with
    the owner's rights (a push with their login, or a change to the guard's files in the worktree). No allow-list can
    fence a test runner, so there OpenCode asks the owner before each `python -m unittest` run (fo4-implement's and
    fo4-qa's rules) as long as the owner answers Allow once (Allow always or auto-accept stops the asking until OpenCode
    exits), the terminal does not start while the worktree has a change to a file the guard refuses an agent to write
    or is on a branch that differs from main in one, and "never pushes" in the terminal rests on the model and on the
    owner reading those prompts. The owner's own OpenCode config (~/.config/opencode) is not checked. Unattended runs
    are unchanged: they refuse fo4-implement and take no QA reviews, so no agent there writes and runs a test.
  - Delegation runs both ways through GitHub: Claude opens issues labelled `agent:local-team` and `ready` (or runs one
    `run-lead.ps1 -MaxCycles 1 -Brief` session on the PC), and the Lead's `/handoff` posts a `Lead (local): for
    Claude:` comment on #32. Claude Code's side is four skills in `.claude/skills/`.
- Why: the owner asked for a terminal to talk to the team when Claude is away, a desktop start for the team and for
  Claude Code, more models, and skills for control and delegation both ways. A pick the proxy and OpenCode both read
  replaces, for the terminal and the Lead, the hand edits of `opencode.json` that the 14B and 128K setups needed, which
  the review of #587 flagged (a plain `opencode` still has `opencode.json`'s 64K limits).
- Alternatives: the PC session building its own guard and commands (dropped by the owner's E); a web UI (`opencode
  web`, more moving parts); committing per-model `opencode.json` files (one would always be stale).
- Was not yet true at the merge: none of it had run on the PC, PowerShell 5.1 was not available here to parse the
  scripts, and the OpenCode switches (`OPENCODE_CONFIG_CONTENT`, `OPENCODE_DISABLE_EXTERNAL_SKILLS`,
  `permission.skill`, the `.opencode/commands/` and `.opencode/skills/` folders) were taken from the current OpenCode
  docs, while the PC runs 1.18.35. The install on the PC (31 Oct, at 67d5cd77) showed all of it: the menu, the
  terminal on the picked model with option 3 opening the agent asked for, a refused write to `opencode.json`, and the
  14B loaded from D: in 11 s. `opencode debug skill` lists `fo4-allowed-commands` and OpenCode's own built-in
  `customize-opencode`, which `permission.skill` (`{"*": "deny", "fo4-*": "allow"}`) denies. `python -I models.py
  list` cannot import the per-user `lmstudio` package; the menu, the terminal and `run-lead.ps1` run it without `-I`.
- Self-review (30 Oct, before the PR): a multi-agent review with a skeptic per finding confirmed 32 findings, fixed in
  the commit after the merge of #605's fixes. The main ones: a load that failed after the unload resumed the guardian
  with no model, and the load's finally overwrote a pause the owner set meanwhile (now the hold); the terminal's own
  branch stopped following main after its first commit, so guard fixes never reached it, and agent branches stacked
  (now main with no branch, and branches from main); `-Agent` opened the Lead (subagent-only mode); `/review` ran the
  tests on the wrong checkout; YAML cut descriptions at ` #32`; anyone could post a `for Claude:` handoff.
- Brought up to main after the guard's follow-ups (#606 to #608): the plugin checks a file write with the same
  checker call as a shell command (a full-path `FO4SF_PYTHON`, exit 0 together with `{"allowed": true}`);
  `terminal.ps1` resolves the real `python.exe` the way `run-lead.ps1` does and refuses the Store alias; and
  `run-lead.ps1` keeps main's single-instance check, environment restore and pinned cycle, with the pick, the session
  pid file for the menu, `-Brief` and the skip without a wait in the last cycle added. The proxy follows a pick only
  when it names a preset's model.
- Second self-check (30 Oct, after the merge): the proxy read only the guardian's config, so it had no presets and
  never followed a pick (it now reads the models from `config.json` too); `models.py pick` always loads (no
  `--no-load`, which could leave a pick that was never loaded); a written file's path takes letters, digits and
  `._@+=,-` only, with no part that starts or ends with a dot (Windows drops trailing dots and spaces, and `::$DATA`
  writes the file itself); only the coding agent commits on its own (`agent_git.py` is gone from the Lead's allow
  rules, per J, so a Lead docs commit in the terminal waits for the owner's yes at OpenCode's prompt);
  `run-lead.ps1` waits for a session one second at a time, so Ctrl+C stops it, and forgets the last cycle's session;
  and `terminal.ps1` leaves the worktree where it is while another terminal window is open on it.
- Independent review (30 Oct, https://github.com/fo4sf/fo4-to-starfield/pull/619#issuecomment-6532780527, NOT CLEAR,
  3 medium and 9 low), all taken: test runs ask the owner, the text says what the guard cannot hold, and the terminal
  refuses to start on changed guard files (1); a patch with a control character or a line break other than "\n" is
  refused and its headers are read line by line as OpenCode reads them (2); `agent_git.py branch` with an existing name
  switches back to it (3); `models.py` runs under `-I`; a refused load puts back a "failed" hold; the README says what a
  plain `opencode` keeps; a commit message needs its agent's own tag; a handoff is matched on its letters alone;
  writes named like a standard module are refused at the repo root and in `scripts/` (Python searches those first);
  the terminal checks git's exit codes; menu option 7 stops the loop before the session and checks a pid file's age;
  `/review` reads CI through `gh pr view --json statusCheckRollup`; and the tests the review found weak are fixed.

## 2026-10-30: the 35B's output limit goes from 16K to 32K tokens (owner)

- Decision: `opencode.json` and the `qwen3.6-35b` preset give the agents an output limit of 32000 tokens, OpenCode
  1.18.35's own cap (`min(limit.output, 32000)`, read from its code), at the same 64K context. The 14B keeps 8192: its
  32K window cannot spare more.
- Why: the owner's word, "We shouldn't restrict its output limit so much" (30 Oct 22:51Z). Qwen3.6 thinks before every
  answer and the thinking counts as output. In the owner's hard test that evening (find bugs in `src/fo4sf/ba2.py` and
  prove them with tests), the agent read the right files, then thought for 1,119 s and stopped at 16,377 reasoning
  tokens (finish "length"), so it wrote no answer, test or report. The model card recommends 32,768 output tokens.
- Alternatives: keep 16384 (rejected: hard tasks end before any answer); 128K context with a 32K output (left to the
  owner: room for both, but at 128K the PC idled at 85-88% RAM against 78-79% at 64K, just under the guardian's 89% hold
  line (`restrict_pct`), and sat at 92.5% VRAM while the Lead worked; the 3.5-point gap in the README's table is a load
  peak).
- Boundary: OpenCode compacts at context minus output, so a session now compacts at about 33.5K tokens instead of
  49K; the Lead's opening prompts (23-26K on 30 Oct) fit, its longer sessions (46K at 128K) compact on the way. The
  earlier entry rejected 32768 for that reason; the hard test showed the thinking room matters more. The owner also
  chose to hand the local team hard work in smaller steps. The count is the last step's tokens with its thinking, so a
  step that thinks 28K tokens on a 6K prompt compacts the session even though the next prompt is far smaller. LM Studio
  0.4.27 (the team PC, default settings, measured 30 Oct) takes a request whose prompt plus `max_tokens` passes the
  64K window: it counts the whole prompt, stops at the window with finish "length", and returns no error. So the
  compaction request after such a step (about 34K of history, 32K `max_tokens`) runs, with about 31K left for the
  summary and its thinking.

## 2026-10-30: a subagent's report survives a compaction right after it (Claude-cloud)

- Decision: `.opencode/plugin/fo4-reports.js`. When OpenCode compacts a subagent's session right after an answer that
  finished, the plugin turns off OpenCode's "Continue if you have next steps..." message for that session
  (`experimental.compaction.autocontinue`) and puts the answer back into the task tool's result
  (`tool.execute.after`), so the Lead gets the subagent's report. A compaction in the middle of a task, one after a
  step that ran out of room, and any in the owner's own session run as OpenCode makes them.
- Why: the independent re-review of #619 at 7b3cf388 (medium 2). OpenCode 1.18.35 (read from its code) checks for
  compaction after a final answer too; with no user message to replay it adds the "Continue" message, and the task tool
  returns the newest text in the subagent's session, so the Lead would get the reply to "Continue" (or, with that off
  alone, the compaction's summary) instead of the report. With 32K output and thinking counted, one long final step
  is enough to trigger it.
- Alternatives: `limit.input` with `compaction.reserved` to raise the threshold (it only makes the case rarer, and a
  prompt could then pass the window); `compaction.auto: false` (a session that fills the window would fail instead of
  compacting); a compaction prompt that copies the report (OpenCode keeps the newest messages out of the summarised
  part, so the report is often not in what the summary sees).
- Boundary: the plugin learns which sessions are subagents' from OpenCode's events; a subagent resumed with `task_id`,
  after a restart too, is known from the `session.updated` event its resume publishes. A step that ends "stop" but has a
  tool call of its own is not a finished answer (OpenCode's loop goes on after it), so its compaction is left alone. A
  result put back is always laid out again in the task tool's form around the report (the summary may quote the tags
  or have been cut), and keeps to OpenCode's tool output limits (2,000 lines, 51,200 bytes, the layout counted), as
  the result it replaces already did: the report's first whole lines, or a first line too long for that cut at a whole
  character, then a note with the task id.
  Background tasks (an experimental switch this repo does not set) are not covered. The events and hook shapes are
  1.18.35's; a newer OpenCode needs them checked again. The #619 install on the PC ran one forced case in OpenCode
  itself (31 Oct): `fo4-research` at a 12,000 token context and 3,000 output compacted after its answer, no
  "Continue" came, and the Lead got the report.
- Independent review (31 Oct, https://github.com/fo4sf/fo4-to-starfield/pull/619#issuecomment-6536474246): CLEAR at
  4c74cc41 with 7 lows, all taken in the follow-up PR: the tool-call step above, the cut and the layout fallback, the
  resume text, plugin tests that pin each check, the 89% line, terminal tests that tie each condition to its message,
  and a failed move to main that is not a clash now stops the terminal with git's own message.
- Post-merge check of #620 (31 Oct, https://github.com/fo4sf/fo4-to-starfield/pull/620#issuecomment-6536918682):
  CLEAR with 7 lows, all taken in the next follow-up: a summary that quotes the tags no longer leaves stray text (the
  layout is always rebuilt); the cut counts the layout and never goes over a limit; the terminal lists the clashing
  paths again and takes a folder that main turns into a file as a clash, while anything else (a stale `index.lock`)
  stops it with git's first line; and the tests send the compaction's own user message and pin the cut's bounds, with
  a test that git's messages carry the words the terminal reads.

## 2026-10-31: the guard waits up to 60 s for its checker, not 15 s (Claude-cloud)

- Decision: `.opencode/plugin/fo4-guard.js` waits up to 60 s for `allowlist.py`'s verdict on each call (it was 15 s).
  The variable `FO4SF_GUARD_TIMEOUT_MS` still only shortens it, for tests.
- Why: the Lead's second cycle on 30 Oct lost a post to "no verdict from the guard (...: ETIMEDOUT)" while the PC sat
  at 90-93% RAM, most likely a Python start that took more than 15 s while Windows paged (not measured). A call with
  no verdict is refused, so the guard held, but the work was lost. Put to the owner as A (60 s) or B (leave it); with
  the owner's word to keep going and save credits (31 Oct 02:20Z), it went into the #620 follow-up as A, to come out
  if the owner says B.
- Alternatives: keep 15 s (the Lead loses calls whenever RAM is high); no limit (a hung checker would hold the agent
  forever); a long-running checker process (fewer starts, but one more moving part between the agent and the guard).
- Boundary: a hung checker now holds an agent's call for 60 s before the refusal. The test runs a 16 s checker
  (allowed) and a 61 s one asked for 600 s (refused at about 60 s) side by side, so it takes about a minute.

## 2026-10-31: the 35B at 3-bit goes on trial, and the agents' terminal can run on Claude (owner)

- Decision: config.json gets a third preset, `qwen3.6-35b-q3`, the same Qwen3.6-35B-A3B at 3-bit (Unsloth
  UD-Q3_K_XL, 16.8 GB against 21.2 GB), at the same 64K context and 32K output; `qwen3.6-35b` stays the default until
  the trial passes, and the 4-bit preset then goes, back to two. And the menu's `c` opens the agents' terminal with all
  four agents on Claude Sonnet 5.5 or Haiku 5.5 (Anthropic API, the owner's key), under a $50 monthly cap that
  `.opencode/plugin/fo4-cloud-cap.js` enforces, in the owner's terminal only.
- Why: the owner, 31 Oct: the 35B at 4-bit is too much for the PC (32 GB RAM, 12 GB VRAM: 78-80% RAM idle, 87-96%
  while the Lead works, three Lead cycles in a row out of time); research put four options and the owner took the
  recommended one ("Let's go with your pick", 16:56Z). Measured on the PC the same day (64K, f16 cache, no team
  running): 71.9% RAM idle against 83.6% for the 4-bit (the model server 9.5 GB in RAM against about 15), 10.3 GB VRAM,
  26.3 tokens/s on a short prompt (4-bit: 20-25), on a 41K prompt the first token after 35.7 s (4-bit at 45K: 57 s)
  and 9.8 tokens/s (8.3), peak 73.3% RAM, and the right answer to a question on that text. Thinking off is not a
  repo setting: the API's `enable_thinking` flag is ignored and `/no_think` in the system prompt made it think longer;
  the model's prompt template in LM Studio (Enable Thinking off) is the route, set and checked on the PC. The owner has
  $200 of API credit and chose to use it on Claude for hard work or when RAM is full (17:01Z).
- Alternatives: gpt-oss-20b (the backup if the 3-bit model's tool calls or answers fall short); the 35B at 32K with
  thinking off (no download, least RAM gained); the 14B now (weaker). For Claude: an API key in an environment variable
  (every process, the unattended Lead's too, could read it; `opencode auth login` keeps it in OpenCode's own file);
  Opus (dearer; left out by the whitelist); Claude for the unattended Lead (no one watching the spend).
- With the second download LM Studio lists the two by publisher (`lmstudio-community/qwen3.6-35b-a3b`,
  `unsloth/qwen3.6-35b-a3b`), so a preset now names the `key` LM Studio loads and keeps a short `model` id that the
  proxy, the pick and the unload list use; the 4-bit's id stays `qwen3.6-35b-a3b`, the 3-bit's is `qwen3.6-35b-a3b-q3`.
- From the PR's review (Grok, 31 Oct): a pick unloads the presets' keys too (a copy loaded by hand in LM Studio's window
  has its key as its id, and would sit beside the pick), and any `id:2`, `id:3` instance of an id it unloads; and the
  proxy reads config.json's presets and agent map again when the file changes, where it read them once at start and
  sent a pick of a preset added since to the agents' map model, the one the pick had just unloaded. This PR still
  changes the proxy's code, so the PC restarts the team after the pull, before the 3-bit is picked.
- Boundary: still to measure before the 3-bit becomes the default: RAM while the Lead works, OpenCode's tool calls
  through the proxy, and the 29 Oct accuracy set. The cap counts OpenCode's price for each message, from the costs
  opencode.json gives both Claude models (1.18.35's built-in list has no Haiku 5.5, and an unpriced model counts $0, so
  the plugin refuses a model without a price), not the bill; it misses a session's title, a step stopped or failed
  mid-stream, an update two windows write at once, a step whose tally write failed, and `opencode agent create`; it
  lets running requests finish, and a message from before an OpenCode restart that grows is counted again. The
  Console's spend limit is the hard cap; on the PC, `cloud-spend.json` must show `usd` above 0 after the first Sonnet
  and Haiku messages (second review of the PR, 31 Oct).
  A throw in chat.params fails the request before it is sent (1.18.35's plugin trigger runs the hook before building
  the request); that is read from the code, not yet seen on the PC.

## 2026-10-31: Papyrus doc comments and strings stay at or under 3 KB; long notes go in ";" comments (Claude-cloud)

- Decision: every doc comment (`{...}`) and string literal in the repo's .psc files is at most 3,072 bytes, each line
  end counted as two bytes; longer notes go in `;` comments, which the compiler leaves out of the .pex.
  `tests/test_papyrus_strings.py` holds it for every .psc in the repo. FO4SF_NewGameQuest.psc's header, the one over
  the line, is cut to 1,409 bytes (the stage contract kept); the build from this change is newgame_v12, v11's records
  and code with that comment short.
- Why: newgame_v11 crashed Starfield on every launch (29 to 31 Oct) while the game loaded its data files, before the
  main menu (FO4SFBorder's log: no `post_data_load`; two of the crashes came after the local model was unloaded, one
  with 13.4 GiB free), and newgame_v10 did not. The crash dump's rax held `ell for `, exactly the bytes 4,096 to
  4,103 of that 4,196-byte doc comment (v10's: 2,745).
  So the game's script loader copies a doc comment into a 4 KB buffer and the bytes past it overwrite a pointer
  (supported hypothesis, one dump; docs/newgame/vault111-start.md section 13a).
- Alternatives: cut the comment alone, with no test (the next long comment would crash the game again, with nothing in
  CI to say why); a limit just under 4,096 (no room for a Windows checkout's two-byte line ends or a terminator; the
  longest that has loaded in game is 2,745 bytes); move the notes to the doc only (the script loses its own why).
- Boundary: the 4 KB buffer is inferred from one dump, and whether string literals go through the same buffer is not
  known (none of ours is near). If newgame_v12 dies the same way, the next suspect is the startup override record (a
  build without it tells).

## 2026-10-31: the launcher can update its own checkout from GitHub's main, fast-forward only, opt-in (Claude-cloud-2)

- Decision: a launcher setting `update` (off by default; check; pull) and a command `launcher.py update [--check]`.
  With pull, `launcher.py play` and `launcher.py gui` run `git fetch origin main` first, fast-forward the checkout they
  run from, and start the same command again on the new code (`src/fo4sf/launcher/selfupdate.py`). The checkout moves
  only when it is on main, has no uncommitted change to a tracked file, no merge, rebase, cherry-pick, revert or bisect
  in progress, and no commit GitHub's main lacks. Starfield must be closed. A refusal or a network failure prints one
  line, and the command goes on with the code it has.
- Why: the owner, 31 Oct: "a way for the launcher to auto update itself so once everything is merged, I don't need to
  tell anybody to install it". Merged work reached the PC only when somebody pulled it by hand.
- Alternatives:
  - Download a ZIP of main and copy it over the checkout: rejected. It would overwrite local edits and leave deleted
    files behind, and git already knows what changed.
  - `git pull` or `git reset --hard origin/main`: rejected. A pull can make a merge commit; a reset throws away the
    owner's or an agent's work.
  - A release channel with tagged versions: later, if outside players use the launcher. It needs a release process
    first.
  - On by default: no. The rule for the owner's PC is opt-in. `settings --set update=pull` turns it on once.
- Boundary: this updates code only; built plugins, archives and installs change only through their own steps. The
  first update has to be by hand, because the checkout that lacks this code cannot fetch it. A command that is already
  running keeps its old code until it starts again (the restart covers play and the window; the window's own Play
  button runs `play`, which updates too). Not tested on Windows yet: the PC's first `launcher.py update --check`
  shows it.

## 2026-11-01: FO4SF runs from a game folder of its own; the player's Starfield is never switched (owner, built by Claude-cloud-2)

- Decision: the owner answered the 29 Oct launcher question (switch the one install to FO4SF and back, or always
  FO4SF): "stay FO4SF all the time make a separate area then actual starfield so people can keep their own mod packs
  for that". So the launcher makes an FO4SF game folder beside the Steam install, with hard links on the same drive
  (no extra disk), the game folder's INIs copied, and only the game's own files in Data
  (`launcher.py instance plan|create`, `src/fo4sf/launcher/instance.py`). Our installers run against that folder,
  with `LOCALAPPDATA` pointed at the folder's own Plugins.txt; saves and our INI writes go to the folder's own
  `Starfield.ini`. Design, steps and PC checks: docs/ai/fo4sf-instance.md.
- Why: players keep their own Starfield mod packs untouched, and FO4SF never has to be switched in and out of the
  player's install (restore stays the tool for tests and recovery).
- Alternatives:
  - Switch the one install at start and back at quit with restore: what the owner did not pick.
  - A full copy ("Stock Game", as the MO2 and Wabbajack guides do): about 100+ GB that the D: 40 GB rule cannot
    spare; hard links cost nothing on the same drive.
  - A virtual file system (MO2's USVFS): a large dependency, and Plugins.txt still needs its own handling.
  - `sTestFile` in the folder's INI: since 1.16.236 the game writes those plugins into the shared Plugins.txt and drops
    the player's plugins it cannot find, and it caps at 10.
- Boundary: all four steps are built, behind the setting `instance` (empty by default). That includes the Plugins.txt
  swap at play, journaled, which works whether or not the game follows the `LOCALAPPDATA` variable (H2). The
  folder-INI saves and Papyrus keys rely on the game reading its folder's Starfield.ini (H3). Whether the copied folder
  starts at all (H1) is the first PC check, docs/ai/fo4sf-instance.md section 4.

## 2026-11-01: one Claude session on the PC holds every Claude role; the cloud sessions pause (owner)
- **Decision:** the handoff the owner gave a new Claude Code session on the PC on 1 Nov (written by Claude, given by
  the owner) says: "The owner ended that setup. You take over all of Claude's roles: integration, the live game on the
  PC, in-game checks, the written records, and getting PRs reviewed and merged" (that setup: many Claude project
  threads, the PC session "Install" and Claude-cloud-2). Claude-cloud-2 is paused and is
  used for research and other help; its open drafts (#647 and #660, the C++ port #649 and #651 to #654, the audio
  design #650) pass to that session. Codex finishes what it is working on (its P9 live test, #639, #641, #643, #656,
  #657, #659) and both lines of work converge for testing afterwards. The merge rule is unchanged: CI green plus an
  independent review of the exact head.
- **Why:** the owner's words, 1 Nov (fixed for typos): "Do what you think is best; let Codex finish what it's working
  on, pick your own tasks and we will converge and test both, and we will keep the cloud paused and use it for
  research and other help." (Claude's reading: many threads cost credits and left work split across sessions that
  could not see each other.)
- **Alternatives:**
  - Keep the cloud session as the author of the C++ port: rejected by the owner (paused).
  - The PC session waits for Codex before picking work: rejected; the owner said to pick our own tasks.

## 2026-11-01: the owner's strip-down and start picks, recorded (owner, 29 and 31 Oct)
- **Decision:** the owner's answers on the strip-down and next-steps plan pages (private pages; copied into the 1 Nov
  handoff), recorded here so the repo has them. Strip-down, 29 Oct (the owner: "too many things are breaking because
  we are forcing ourselves into the Starfield system"; the handoff names Fallout: London, own plugins over an
  untouched master with its own start, menu and intro, as the model): **B** our planet inside Sol, and in the end no other planets; **X** the other planets
  gone from the star map too, by overrides in our plugin; **F** our own start overriding `StartupQuest_DO` (done,
  #588); **I** the quieting switches go straight into the mod, no test profile; **N** drop the landing pad and its ship
  records; **T** a vanilla baseline New Game for comparison (`docs/testing/baseline.md`); **V** keep going on Claude's
  picks and redo what the owner changes; orbit **A**, the final planet in Earth's orbit. **K** (Claude's pick under V,
  changeable): the probe planet is a Jemison clone without alien life. The start, 31 Oct: **a** the start is chosen in
  the launcher; **f** two separate test starts, D skipping character creation only (today's quick start) and E outside
  at the Vault 111 elevator; **g** the pre-war Vault 111 (into the cryo pod, out post-war, the vault door and the
  elevator) comes after the start picker and the launcher profile work, and is not built before the owner has seen
  its design. The owner would like the GAMMA start picked in the new-game options, if the game allows it (unchecked).
- **Why:** the owner's picks; the entries of 29 Oct above already carry B, the orbit, I and T in their own words.
- **Alternatives:** keep them only on the private pages: rejected, the repo is where the team reads decisions.
