"""Source door animation topology for planning faithful multi-part conversion.

This describes source motion branches; it does not generate animation graphs or
claim that independent leaves can share the vanilla single-hinge animation.
"""
import struct
from . import nif


def inspect(source):
    nodes = {}
    for i, block in enumerate(source.blocks):
        if source.type_of(i) == "NiNode":
            name = struct.unpack_from("<i", block)[0]
            nodes.setdefault(name, []).append(i)
    shapes = {s.block for s in nif.fo4_trishapes(source) if s.positions and s.triangles}
    world = nif.world_transforms(source)
    sequences, issues = [], []
    for i, block in enumerate(source.blocks):
        if source.type_of(i) != "NiControllerSequence":
            continue
        name, count = struct.unpack_from("<iI", block)
        if not 0 <= name < len(source.strings):
            raise nif.NifError("invalid sequence name")
        if source.strings[name] not in (b"Open", b"Close"):
            continue
        if 12 + 29 * count > len(block):
            raise nif.NifError("truncated door controlled-block list")
        targets = []
        for k in range(count):
            at = 12 + 29 * k
            interpolator, controller = struct.unpack_from("<ii", block, at)
            target_name = struct.unpack_from("<i", block, at + 9)[0]
            if not 0 <= target_name < len(source.strings):
                raise nif.NifError("invalid controlled node name")
            matches = nodes.get(target_name, [])
            if len(matches) != 1:
                issues.append({"sequence": i, "target": source.strings[target_name].decode("latin-1"),
                               "reason": "node binding absent or ambiguous"})
                continue
            node = matches[0]
            translation, rotation, scale = world(node)
            targets.append({"node": node, "name": source.strings[target_name].decode("latin-1"),
                            "interpolator": interpolator, "controller": controller,
                            "pivot_source_units": list(translation), "rotation": list(rotation), "scale": scale,
                            "shape_blocks": sorted(shapes & nif.descendants(source, node))})
        sequences.append({"block": i, "name": source.strings[name].decode("latin-1"), "targets": targets})
    hinge = nif.door_hinge(source)
    selected = shapes & nif.descendants(source, hinge[0]) if hinge else set()
    animated = {shape for seq in sequences if seq["name"] == "Open" for target in seq["targets"] for shape in target["shape_blocks"]}
    return {"sequences": sequences, "issues": issues, "single_hinge_node": hinge[0] if hinge else None,
            "single_hinge_shape_blocks": sorted(selected), "all_animated_shape_blocks": sorted(animated),
            "animated_shapes_outside_single_hinge": sorted(animated - selected),
            "requires_additional_motion_support": bool(animated - selected)}
