# Doors: how they animate in each game (research, 2026-10-08)

**Status: not implemented.** Converted doors are static and have no collision (so they never block a room).

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
