# Doors: how they animate in each game (research, 2026-10-08)

**Status: experimental, off by default** (`Converter(rig_doors=True)`). By default converted doors are static with no collision, so they never block a room.

## Fallout 4
Door NIFs (`meshes\SetDressing\Doors\*`, 28 sampled) carry their own keyframe animation:
`NiControllerManager` + `NiControllerSequence` ("Open" / "Close") + `NiMultiTargetTransformController` +
`NiTransformInterpolator`/`NiTransformData`, plus `NiTextKeyExtraData`. The moving part is a named node.

## Starfield
Door NIFs (520 in `Starfield - Meshes01.ba2`, 60 sampled) contain **no controller blocks**. They contain named nodes
(e.g. `AK_Door_Anim_02_Root`, `Hinge01_Point`, `REF_ATTACH_NODE`, `LookAtNode`) and `NiStringExtraData "sgoKeep"` tags on nodes
that must survive optimisation. The animation is attached by the **DOOR record** through an `AnimationGraphComponent`:

| Field | Example (`AK_Ext_Bld_WallA_DoorA_01_Alt02`, 0AA24A) |
|---|---|
| ANAM (graph) | `AnimTextData\Tables\Graphs\SimpleOpenClose01.agx` (shared by many doors) |
| BNAM (skeleton) | `architecture\city\akila\animated\doors\ak_ext_bld_walla_doora_01\characterassets\skeleton.rig` |
| CNAM (animations) | `architecture\city\akila\animated\doors\ak_ext_bld_walla_doora_01\animations` |

## Plan to make FO4 doors open
1. Pick a vanilla Starfield hinged door and a vanilla sliding door as templates.
2. Rebuild each FO4 door NIF as root -> `<template root node>` -> `Hinge01_Point` (placed at the FO4 animated node's pivot) ->
   geometry in the pivot's local space; tag nodes with `sgoKeep`.
3. Write a `DOOR` record with the template's `AnimationGraphComponent` (ANAM/BNAM/CNAM), open/close sounds and keywords.
4. Risk: the template's `.rig` / `.af` may encode the template's own hinge *position*, not only a rotation. Test in game; if the
   door jumps, the `.af`/`.rig` formats need decoding (no public spec known) or per-size template doors must be chosen.

## Attempt 1 (2026-10-08): rigged FO4 doors on the Akila template

Implemented:
- `nif.door_hinge` reads the node the FO4 `Open` sequence animates first (24 of the doors in our 8 cells are hinged).
- `convert_static.convert_door` and `sfnif.build_door_nif` rebuild the door as root > `AK_Door_Anim_02_Root` >
  `Hinge01_Point` (at the rig's hinge position, -0.823 / 1.698 / 0) > leaf geometry re-centred on the FO4 pivot, plus
  `REF_ATTACH_NODE` and `LookAtNode` (sgoKeep tags), a box body on the leaf, and the static frame under a `Frame` node.
- The plugin writes a `DOOR` record with the template's `AnimationGraphComponent`, real `OBND`, `SoundLevel` (DEVT) and
  `FacingAxisOverride` (trailing ANAM). The reference is shifted by `origin_offset` (door-local, rotated) so the door stays in
  its frame.

Verified in game (Hotel Rexford door 10AD60, `C:\Modding\research\s1\doortest.ps1`):
- The door sits exactly in its frame and shows **DOOR / Open (E)** ([screenshot](../media/door-rigged-prompt.jpg)).
- E toggles the state to Close and back, and the leaf body blocks the player.
- **The leaf never swings.**

What did not fix the swing: a `door` node (the rig's bone 2, child of the hinge), geometry directly on the hinge,
vanilla-like node order, `BSXFlags` 0xA, and record bounds, sound level and facing axis.

Clues:
- `skeleton.rig` is a plain bone table: 96-byte records (rotation, translation, parent index, name offset); bones are
  `AK_Door_Anim_02_Root`(-1) > `Hinge01_Point`(0) > `door`(1) > `REF_ATTACH_NODE`, `LookAtNode`, `C_..._Static_02`(2).
- FO4's rest pose for `BldWoodPDoor01` is **open**: its hinge node is rotated about 97 degrees, and the static conversion shows
  the leaf open ([screenshot](../media/door-static-restpose.jpg)). Every rigged build showed it **closed** at rest. So the
  graph probably does pose `Hinge01_Point` on load, and only the open transition does not show up.
- In the first build (`LookAtNode` directly under the hinge) the activation marker did swing aside when opened.
- With the vanilla door mesh on our record, or the vanilla DOOR 0AA24A placed in our cell, no prompt could be aimed at with
  scripted input. That test is still open.

Next: place vanilla DOOR 0AA24A somewhere easy to aim at, to confirm a vanilla door animates in our cell (lighting
template, cell flags). Then compare its node poses (`sgoKeep` nodes, open.af) with ours. Decoding `.af` is the fallback.