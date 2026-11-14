"""Source door animation topology for planning faithful multi-part conversion.

This describes source motion branches; it does not generate animation graphs or
claim that independent leaves can share the vanilla single-hinge animation.
"""
import struct
import base64
from . import nif, animation_curves


def sequence_timing(source, block, count):
    at = 12 + 29 * count
    if len(block) < at + 34:
        raise nif.NifError("truncated door sequence timing")
    weight, text, cycle, frequency, start, stop, manager, root, notes = struct.unpack_from("<fiIfffiiH", block, at)
    if len(block) != at + 34 + 4 * notes:
        raise nif.NifError("invalid door sequence note-array length")
    events = []
    if text != -1:
        if not 0 <= text < len(source.blocks) or source.type_of(text) != "NiTextKeyExtraData":
            raise nif.NifError("invalid door text-key link")
        data = source.blocks[text]
        num = struct.unpack_from("<I", data, 4)[0]
        if len(data) != 8 + 8 * num:
            raise nif.NifError("invalid door text-key length")
        for i in range(num):
            time, name = struct.unpack_from("<fi", data, 8 + 8 * i)
            if not 0 <= name < len(source.strings):
                raise nif.NifError("invalid door event string")
            events.append({"time": time, "text": source.strings[name].decode("latin-1")})
    if root != -1 and not 0 <= root < len(source.strings):
        raise nif.NifError("invalid door accumulation root")
    return {"weight": weight, "cycle_type": cycle, "frequency": frequency, "start": start, "stop": stop,
            "manager_block": manager, "accumulation_root": source.strings[root].decode("latin-1") if root != -1 else None,
            "text_events": events, "animation_note_blocks": list(struct.unpack_from(f"<{notes}i", block, at + 34))}


def transform_track(source, index):
    """Retain bind values, raw keys and decoded curves without resampling.

    Decoded curves still require a target animation emitter.
    Local generated reports contain source animation data and must not be published.
    """
    if index == -1:
        return None
    if not 0 <= index < len(source.blocks):
        raise nif.NifError("invalid door interpolator link")
    kind = source.type_of(index)
    if kind != "NiTransformInterpolator":
        return {"type": kind, "status": "unsupported_interpolator"}
    block = source.blocks[index]
    if len(block) < 36:
        raise nif.NifError("truncated door transform interpolator")
    values = struct.unpack_from("<8f", block)
    data = struct.unpack_from("<i", block, 32)[0]
    result = {"type": kind, "translation": list(values[:3]), "quaternion_wxyz": list(values[3:7]),
              "scale": values[7], "data_block": data, "source_keys": None}
    if data != -1:
        if not 0 <= data < len(source.blocks) or source.type_of(data) != "NiTransformData":
            raise nif.NifError("invalid door transform-data link")
        result["source_keys"] = {"type": "NiTransformData", "encoding": "base64",
                                 "data": base64.b64encode(source.blocks[data]).decode("ascii")}
        result["decoded_keys"] = animation_curves.decode(source.blocks[data])
    return result


# Controlled blocks known not to move a node. A scan of every FO4 mesh with an Open sequence (review of PR #242) found,
# besides 1313 NiTransformController + NiTransformInterpolator blocks, only shader float, alpha-test, visibility and
# particle-emitter controllers on float / bool interpolators (VltDoorRes01A's override-box shapes:
# BSLightingShaderPropertyFloatController with NiFloatInterpolator). Only these listed kinds are left out; anything else,
# a transform interpolator this code cannot sample (B-spline, blend) or an unknown type, stays a motion track, so it is
# refused later (door_clips.sample_track) instead of silently freezing that part.
NON_TRANSFORM_CONTROLLERS = frozenset((
    "BSLightingShaderPropertyFloatController", "BSLightingShaderPropertyColorController",
    "BSLightingShaderPropertyUShortController", "BSEffectShaderPropertyFloatController",
    "BSEffectShaderPropertyColorController", "BSNiAlphaPropertyTestRefController", "NiAlphaController",
    "NiVisController", "NiMaterialColorController", "NiPSysEmitterCtlr", "NiPSysEmitterSpeedCtlr"))
NON_TRANSFORM_INTERPOLATORS = frozenset(("NiFloatInterpolator", "NiBoolInterpolator", "NiBoolTimelineInterpolator",
                                         "NiPoint3Interpolator", "NiBlendFloatInterpolator", "NiBlendBoolInterpolator",
                                         "NiBlendPoint3Interpolator"))


# (target node, interpolator) an aliased clip may leave out: the Vault 111 cog door's falling paper, which Stage2 moves on
# NiPathInterpolator (PC build f8c9b95, VltGearDoor01.nif: FXPaper01 node 1372, FXPaper002 node 1397); the only aliased
# model is VltGearDoor01 (pipeline.OWN_RIG_ALIASES). Review of #329 (Codex P2): no blanket exception for other targets.
DECORATIVE_UNSAMPLED = frozenset((("FXPaper01", "NiPathInterpolator"), ("FXPaper002", "NiPathInterpolator")))
PARTICLE_SYSTEMS = frozenset(("NiParticleSystem", "NiMeshParticleSystem", "BSStripParticleSystem"))


def _non_transform(source, interpolator, controller_type):
    """Reason a controlled block does not move a node (a known shader / visibility / particle kind), or None.

    ControlledBlock layout (FO4): interpolator, controller, priority, node name, property type, controller type,
    controller id, interpolator id. A block is left out only when its interpolator (if any) is a known non-transform kind
    and its controller type is a known non-transform kind, or, with no controller type, when the interpolator is."""
    kind = source.type_of(interpolator) if 0 <= interpolator < len(source.blocks) else None
    if kind is not None and kind not in NON_TRANSFORM_INTERPOLATORS:
        return None                     # a transform interpolator, or one nobody has checked: motion
    if controller_type is None:
        return f"interpolator {kind}" if kind is not None else None
    return f"controller {controller_type}" if controller_type in NON_TRANSFORM_CONTROLLERS else None


def inspect(source, aliases=None, allowed=None):
    """aliases: {FO4 sequence name: "Open" or "Close"} for an animated object whose clips have other names (the Vault 111
    cog door VltGearDoor01 plays Stage2 to open); the aliased sequence is reported under its door name.
    allowed: the names a sequence may be reported under (bytes), default Open / Close; an animated object that is no door
    (the Vault 111 console on an activator graph, FAL-489 variant D) names its own clip slots."""
    allowed = tuple(a if isinstance(a, bytes) else a.encode("latin-1") for a in allowed) if allowed else (b"Open", b"Close")
    aliases = {k.encode("latin-1"): v.encode("latin-1") for k, v in (aliases or {}).items()}
    nodes = {}
    for i, block in enumerate(source.blocks):
        if source.type_of(i) == "NiNode":
            name = struct.unpack_from("<i", block)[0]
            nodes.setdefault(name, []).append(i)
    # particle systems (NiAVObjects, not nodes: no rig bone can carry them, and particles are not ported); an aliased
    # object's clip also drives its emitters (the cog door's Stage2: p_Dust, p_Steam, p_Sparks), left out and listed
    particles = {struct.unpack_from("<i", block)[0] for i, block in enumerate(source.blocks)
                 if source.type_of(i) in PARTICLE_SYSTEMS} if aliases else set()
    shapes = {s.block for s in nif.fo4_trishapes(source) if s.positions and s.triangles}
    world = nif.world_transforms(source)
    sequences, issues, ignored = [], [], []
    for i, block in enumerate(source.blocks):
        if source.type_of(i) != "NiControllerSequence":
            continue
        name, count = struct.unpack_from("<iI", block)
        if not 0 <= name < len(source.strings):
            raise nif.NifError("invalid sequence name")
        # an aliased object takes its clips from the aliases only; any other door from its own Open / Close
        seq_name = aliases.get(source.strings[name]) if aliases else source.strings[name]
        if seq_name not in allowed:
            continue
        if 12 + 29 * count > len(block):
            raise nif.NifError("truncated door controlled-block list")
        targets = []
        for k in range(count):
            at = 12 + 29 * k
            interpolator, controller = struct.unpack_from("<ii", block, at)
            target_name, _property_type, controller_type = struct.unpack_from("<iii", block, at + 9)
            if not 0 <= target_name < len(source.strings):
                raise nif.NifError("invalid controlled node name")
            reason = _non_transform(source, interpolator, source.strings[controller_type].decode("latin-1")
                                    if 0 <= controller_type < len(source.strings) else None)
            if reason:                 # not motion: kept out of the rig and listed, never a binding issue
                ignored.append({"sequence": i, "target": source.strings[target_name].decode("latin-1"), "reason": reason})
                continue
            kind = source.type_of(interpolator) if 0 <= interpolator < len(source.blocks) else None
            if aliases and (source.strings[target_name].decode("latin-1"), kind) in DECORATIVE_UNSAMPLED:
                # only the listed decorative targets stay at their bind pose (listed); any other track this code cannot
                # sample is still refused later (door_clips.sample_track), so no opening part is silently frozen
                ignored.append({"sequence": i, "target": source.strings[target_name].decode("latin-1"),
                                "reason": f"unsampled interpolator {kind}"})
                continue
            if target_name in particles and target_name not in nodes:
                ignored.append({"sequence": i, "target": source.strings[target_name].decode("latin-1"),
                                "reason": "particle system"})
                continue
            matches = nodes.get(target_name, [])
            if len(matches) != 1:
                issues.append({"sequence": i, "target": source.strings[target_name].decode("latin-1"),
                               "reason": "node binding absent or ambiguous"})
                continue
            node = matches[0]
            translation, rotation, scale = world(node)
            targets.append({"node": node, "name": source.strings[target_name].decode("latin-1"),
                            "interpolator": interpolator, "controller": controller,
                            "transform_track": transform_track(source, interpolator),
                            "pivot_source_units": list(translation), "rotation": list(rotation), "scale": scale,
                            "shape_blocks": sorted(shapes & nif.descendants(source, node))})
        sequences.append({"block": i, "name": seq_name.decode("latin-1"), "targets": targets,
                          "timing": sequence_timing(source, block, count)})
    hinge = nif.door_hinge(source)
    selected = shapes & nif.descendants(source, hinge[0]) if hinge else set()
    animated = {shape for seq in sequences if seq["name"] == "Open" for target in seq["targets"] for shape in target["shape_blocks"]}
    return {"sequences": sequences, "issues": issues, "ignored_targets": ignored,
            "single_hinge_node": hinge[0] if hinge else None,
            "single_hinge_shape_blocks": sorted(selected), "all_animated_shape_blocks": sorted(animated),
            "animated_shapes_outside_single_hinge": sorted(animated - selected),
            "requires_additional_motion_support": bool(animated - selected)}
