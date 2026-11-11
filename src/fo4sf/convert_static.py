"""Fallout 4 static NIF -> Starfield NIF + .mesh files (spike S1, fidelity tier T1: geometry + placeholder material).

    files = convert_static(open("chair.nif", "rb").read(), "fo4port/setdressing/chair")
    # {"meshes/fo4port/setdressing/chair.nif": b"...", "geometries/<20hex>/<20hex>.mesh": b"...", ...}

Unverified assumptions (see docs/RISKS.md S4): 1 Fallout 4 unit = 1/70 m, same handedness / winding / UV
convention, Z-up in both. Collision, materials and skinning are not converted yet.
"""
import hashlib
import math
import struct
from dataclasses import replace
from typing import Dict, Tuple

from . import nif as nifmod
from . import sfcollision, sfmesh, sfnif

UNIT_SCALE = 1.0 / 70.0           # Fallout 4 units -> metres (Starfield .mesh coordinates are metres)
PLACEHOLDER_MATERIAL = "Materials\\Common\\Metal\\MetalIronCast01.mat"   # vanilla material, T0 look
DYNAMIC_BSX = 0x42                 # havok + dynamic: 145 of 150 vanilla MiscItem NIFs (statics: mostly 0x2)


def require_mass_scale(scale) -> float:
    """CLI/API --mass-scale: finite and > 0. Rejects 0, negatives, nan, inf before any archive or staging I/O."""
    try:
        value = float(scale)
    except (TypeError, ValueError):
        raise ValueError("must be a finite positive number") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError("must be a finite positive number")
    return value


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def tangent_signs(positions, uvs, normals, tangents, triangles):
    """Per-vertex handedness bit (1 = positive) derived from the UV gradient; the Starfield tangent's top two
    bits are 3 for positive and 0 for negative (verified against 99% of 22k vanilla vertices)."""
    sign = [None] * len(positions)
    for a, b, c in triangles:
        if all(s is not None for s in (sign[a], sign[b], sign[c])):
            continue
        e1, e2 = _sub(positions[b], positions[a]), _sub(positions[c], positions[a])
        du1, dv1 = uvs[b][0] - uvs[a][0], uvs[b][1] - uvs[a][1]
        du2, dv2 = uvs[c][0] - uvs[a][0], uvs[c][1] - uvs[a][1]
        det = du1 * dv2 - du2 * dv1
        if abs(det) < 1e-12:
            continue
        bit = tuple((e2[k] * du1 - e1[k] * du2) / det for k in range(3))
        for v in (a, b, c):
            if sign[v] is None:
                h = _dot(_cross(normals[v], tangents[v]), bit)
                if abs(h) > 1e-12:
                    sign[v] = 1 if h > 0 else 0
    return [1 if s is None else s for s in sign]


def shape_to_mesh(shape: nifmod.Fo4Shape, unit_scale: float = UNIT_SCALE) -> sfmesh.SfMesh:
    if not math.isfinite(shape.scale) or shape.scale <= 0:
        raise nifmod.NifError(f"shape scale must be a finite positive number, got {shape.scale}")
    pts = []
    r = shape.rotation
    for x, y, z in shape.positions:
        # NIF rotation is row-major; apply scale, rotation and translation of the shape node
        px = shape.scale * (r[0] * x + r[1] * y + r[2] * z) + shape.translation[0]
        py = shape.scale * (r[3] * x + r[4] * y + r[5] * z) + shape.translation[1]
        pz = shape.scale * (r[6] * x + r[7] * y + r[8] * z) + shape.translation[2]
        pts.append((px * unit_scale, py * unit_scale, pz * unit_scale))
    if not pts or not all(math.isfinite(c) for p in pts for c in p):
        raise nifmod.NifError("shape positions are empty or non-finite after transform")
    m = sfmesh.SfMesh(version=2)
    m.scale, m.positions = sfmesh.encode_positions(pts)
    m.triangles = [tuple(t) for t in shape.triangles]
    if shape.uvs:
        m.uv1 = [(sfmesh.float_to_half(u), sfmesh.float_to_half(v)) for u, v in shape.uvs]
    def rot_dir(v):                                   # directions take the rotation only (uniform scale), renormalised
        d = (r[0] * v[0] + r[1] * v[1] + r[2] * v[2], r[3] * v[0] + r[4] * v[1] + r[5] * v[2],
             r[6] * v[0] + r[7] * v[1] + r[8] * v[2])
        ln = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5 or 1.0
        return (d[0] / ln, d[1] / ln, d[2] / ln)
    normals = [rot_dir(v) for v in shape.normals]
    tangents = [rot_dir(v) for v in shape.tangents]
    if normals:
        m.normals = [sfmesh.encode_packed(*n, w=1.0 / 3.0) for n in normals]
    if normals and tangents and shape.uvs:
        # handedness is rotation-invariant: compute it in the shape's local space
        signs = tangent_signs(shape.positions, shape.uvs, shape.normals, shape.tangents, shape.triangles)
        m.tangents = [sfmesh.encode_packed(*t, w=float(s)) for t, s in zip(tangents, signs)]
    if shape.colors:
        m.colors = [(c[2]) | (c[1] << 8) | (c[0] << 16) | (c[3] << 24) for c in shape.colors]   # RGBA -> BGRA u32
    sfmesh.build_meshlets(m)
    return m


def mesh_file_path(mesh_bytes: bytes):
    h = hashlib.sha1(mesh_bytes).hexdigest()
    return h[:20], h[20:40]


def collision_template_from_nif(sf_nif: bytes) -> bytes:
    """Pull the Havok blob out of a vanilla Starfield NIF that has plain box collision (run-time input, not committed)."""
    n = nifmod.parse(sf_nif)
    for i, b in enumerate(n.blocks):
        if n.type_of(i) == "bhkPhysicsSystem":
            size, = struct.unpack_from("<I", b, 0)
            blob = b[4:4 + size]
            sfcollision.check_template(blob)
            return blob
    raise nifmod.NifError("template NIF has no bhkPhysicsSystem")


def _rigid_ragdoll(src, objs, world, dynamic_template: bytes, motion: dict):
    """Blob of meshcollision.rigid_dynamic_body when every collision object shares ONE FO4 physics system, owns a
    different body and sits on an unscaled node; else None (the per-body path then runs, reasons in motion)."""
    from . import meshcollision
    placements, data = {}, None
    for i in objs:
        target, _, d = struct.unpack_from("<iHi", src.blocks[i], 0)
        body, = struct.unpack_from("<I", src.blocks[i], 10) if len(src.blocks[i]) >= 14 else (0,)
        if data not in (None, d) or not (0 <= target < len(src.blocks)) or body in placements:
            return None
        data = d
        tr, rot, scale = world(target)
        if abs(scale - 1.0) > 1e-3:
            return None
        placements[body] = (tuple(rot), tuple(x * UNIT_SCALE for x in tr))
    if not (0 <= data < len(src.blocks)) or src.type_of(data) != "bhkPhysicsSystem":
        return None
    n, = struct.unpack_from("<I", src.blocks[data], 0)
    try:
        return meshcollision.rigid_dynamic_body(src.blocks[data][4:4 + n], dynamic_template, placements, motion)
    except Exception as e:                               # noqa: BLE001  (falls back to the per-body path, reason kept)
        motion.setdefault("kept_static", []).append(f"rigid merge failed: {type(e).__name__}: {e}")
        return None


def fo4_native_collision(src, universal_template: bytes, report: dict = None, dynamic_template: bytes = None,
                         motion: dict = None, pose: dict = None, mass_scale: float = 1.0):
    """[Starfield single-body physics blobs], one per FO4 collision body (meshcollision.convert_bodies), or None to fall
    back. Unsupported shape classes and malformed data return None and record why. One exception, reported as
    report["skipped_parts"]: precombine debris parts in the undecoded primitive encoding (see convert_bodies) are left
    out and the rest of the model keeps its native bodies. report["mesh_fixes"]: what a mesh body needed for
    Starfield's decoder (meshcollision._emit_mesh: primitive slots replaced, FO4 section flags cleared).
    dynamic_template (a vanilla dynamic body): a model whose only collision object sits on the root node and holds
    one dynamic FO4 body becomes movable (motion["dynamic"] = kg, the single blob is that body); so does a model whose
    collision objects share one all-dynamic system (ragdoll skeleton), merged into ONE rigid body (_rigid_ragdoll,
    report["motion_note"]); dynamic bodies that can't be converted are listed in motion["kept_static"].
    pose: {node block: local transform} (nif.world_transforms local_overrides, e.g. a reference's XRGD ragdoll pose):
    every body sits on its node as posed."""
    from . import meshcollision
    objs = [i for i in range(len(src.blocks)) if src.type_of(i) == "bhkNPCollisionObject"]
    if not objs:
        return None
    motion = {} if motion is None else motion
    blobs, skipped, notes = [], [], []
    # placed=True: the game ignores the scene root's own transform (PryCatwalkStairsEnt02's 180-degree root turned the
    # converted stairs the wrong way round; FO4's precombined physics only matches without it).
    world = nifmod.world_transforms(src, placed=True, local_overrides=pose)
    rigid = _rigid_ragdoll(src, objs, world, dynamic_template, motion) if dynamic_template is not None and len(objs) > 1 else None
    if rigid is not None:                            # phase A ragdoll: one rigid movable body on the root node
        if report is not None:
            report.update(source="fo4-native", bodies=1, motion="dynamic", mass_kg=round(motion["dynamic"], 4),
                          motion_note=f"{motion['rigid_bodies']} FO4 bodies merged into one rigid movable body "
                                      "(ragdoll, breakable or hose): joints, breakage and skinning not converted yet")
        return [rigid]
    for i in objs:
        target, _, data = struct.unpack_from("<iHi", src.blocks[i], 0)
        if not (0 <= target < len(src.blocks)):
            if report is not None:
                report["fo4_collision_error"] = "collision object has no target node"
            return None
        # FO4 bhkNPCollisionObject: target, flags, data, body index. Several objects can share one system and each
        # owns one body. Shapes are in the target node's space: the body goes on a child node with that transform.
        body, = struct.unpack_from("<I", src.blocks[i], 10) if len(src.blocks[i]) >= 14 else (0,)
        tr, rot, scale = world(target)
        if abs(scale - 1.0) > 1e-3:
            if report is not None:
                report["fo4_collision_error"] = f"collision node scaled {scale:.3f} (not supported yet)"
            return None
        place = None if target == 0 else (tuple(x * UNIT_SCALE for x in tr), tuple(rot))
        shared = sum(1 for j in objs if struct.unpack_from("<iHi", src.blocks[j], 0)[2] == data)
        if not (0 <= data < len(src.blocks)) or src.type_of(data) != "bhkPhysicsSystem":
            if report is not None:
                report["fo4_collision_error"] = f"collision data is {src.type_of(data) if 0 <= data < len(src.blocks) else 'missing'}"
            return None
        n, = struct.unpack_from("<I", src.blocks[data], 0)
        try:
            # a dynamic body moves the node it is attached to: only a lone root-node body can carry the whole model
            dyn = dynamic_template if (len(objs) == 1 and target == 0) else None
            new = meshcollision.convert_bodies(src.blocks[data][4:4 + n], universal_template,
                                               select=[body] if shared > 1 else None, node_rot=tuple(rot),
                                               skipped=skipped, dynamic_template=dyn, motion=motion, notes=notes,
                                               mass_scale=mass_scale)
            node = place or ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))
            for b in new:
                if isinstance(b, tuple):                 # rotated compound instance: node transform * instance
                    blob, ti, Ri = b
                    Rn, tn = node[1], node[0]
                    R2 = tuple(sum(Rn[3 * r + k] * Ri[3 * k + c] for k in range(3)) for r in range(3) for c in range(3))
                    t2 = tuple(tn[r] + sum(Rn[3 * r + k] * ti[k] for k in range(3)) for r in range(3))
                    blobs.append((blob, t2, R2))
                else:
                    blobs.append(b if place is None else (b, place[0], place[1]))
        except Exception as e:                           # noqa: BLE001  (fallback by design, reason recorded)
            if report is not None:
                report["fo4_collision_error"] = f"{type(e).__name__}: {e}"
            return None
    if report is not None and skipped:
        report["skipped_parts"] = skipped
    if report is not None and notes:                     # what a mesh body needed for Starfield's decoder
        report["mesh_fixes"] = notes
    if report is not None and blobs:
        report["source"] = "fo4-native"
        report["bodies"] = len(blobs)
    if report is not None and motion.get("dynamic"):
        report["motion"] = "dynamic"
        report["mass_kg"] = round(motion["dynamic"], 4)
    if report is not None and motion.get("kept_static"):
        report["dynamic_kept_static"] = motion["kept_static"]
    if report is not None and motion.get("relayered"):      # frozen L_CLUTTER_NOCUT leaves written as L_STATIC
        report["relayered"] = motion["relayered"]
    return blobs or None


def fo4_mesh_collision(src, sf_mesh_template: bytes, report: dict = None):
    """Starfield collision blob made from the FO4 NIF's own mesh collision (on the root node), or None.
    FO4 bhkNPCollisionObject: target node i32, flags u16, data (bhkPhysicsSystem) i32."""
    from . import meshcollision
    for i in range(len(src.blocks)):
        if src.type_of(i) != "bhkNPCollisionObject":
            continue
        target, _, data = struct.unpack_from("<iHi", src.blocks[i], 0)
        if target != 0 or not (0 <= data < len(src.blocks)) or src.type_of(data) != "bhkPhysicsSystem":
            continue
        n, = struct.unpack_from("<I", src.blocks[data], 0)
        try:
            out = meshcollision.transplant(src.blocks[data][4:4 + n], sf_mesh_template)
        except Exception as e:                       # noqa: BLE001  (fallback by design, reason recorded)
            if report is not None:
                report["fo4_collision_error"] = f"{type(e).__name__}: {e}"
            return None
        if out is not None and report is not None:
            report["source"] = "fo4-mesh"
        return out
    return None


ANIMATED_BLOCKS = ("NiControllerManager", "NiControllerSequence")


def pose_skinned_shapes(src, shapes, report: dict = None, world=None):
    """Skinned shapes posed the way the NIF's nodes stand (fo4skin.node_world), in NIF root space with an identity shape
    transform, so the mesh lands where FO4 draws it and where its bone-node collision is (research log 2026-10-10 "FO4
    skin reader": SkeletonClothed01's root bone is turned 45 degrees from the bind pose; a vault sink's tap is stored at
    the model origin and posed on the basin rim). Normals and tangents turn with each vertex's heaviest bone. The node
    pose is the rest pose of animated NIFs too (controllers move nodes from there; the sink's tap is only right when
    posed), so they are posed as well and counted in report["skinned_posed_animated"] for the in-game check. Unreadable
    skins keep the stored positions, counted in report["skinned_kept_stored"].
    world: the nif.world_transforms lookup the bones are read from; default placed=True, the frame fo4_trishapes(placed=
    True) and fo4_native_collision use (the scene root's own transform left out), so mesh and bodies stay together.
    A reference's ragdoll pose (local_overrides) comes in the same way."""
    from . import fo4skin
    world = world or nifmod.world_transforms(src, placed=True)
    animated = any(src.type_of(i) in ANIMATED_BLOCKS for i in range(len(src.blocks)))
    out, posed, kept, odd_root = [], 0, 0, 0
    ident = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    for s in shapes:
        if not s.skinned:
            out.append(s)
            continue
        try:
            skin = fo4skin.read_skin(src, s.block)
            bones = fo4skin.node_world(src, skin, world) if skin else None
        except (nifmod.NifError, ValueError, struct.error):
            skin = bones = None
        if skin is None or bones is None:
            kept += 1
            out.append(s)
            continue
        if skin.skeleton_root not in (0, -1):            # untested case (QA on PR #45): every vanilla file checked roots at block 0
            odd_root += 1
        positions = fo4skin.pose_vertices(s.positions, skin, bones)
        rots = [r for _, r, _ in fo4skin.skin_transforms(skin, bones)]

        def turn(vecs):
            res = []
            for v, ws, ks in zip(vecs, skin.weights, skin.indices):
                r = rots[ks[max(range(len(ws)), key=lambda j: ws[j])]]
                d = (r[0] * v[0] + r[1] * v[1] + r[2] * v[2], r[3] * v[0] + r[4] * v[1] + r[5] * v[2],
                     r[6] * v[0] + r[7] * v[1] + r[8] * v[2])
                ln = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5 or 1.0
                res.append((d[0] / ln, d[1] / ln, d[2] / ln))
            return res
        out.append(replace(s, positions=positions, normals=turn(s.normals) if s.normals else s.normals,
                           tangents=turn(s.tangents) if s.tangents else s.tangents,
                           translation=(0.0, 0.0, 0.0), rotation=ident, scale=1.0))
        posed += 1
    if report is not None:
        if posed:
            report["skinned_posed"] = posed
            if animated:
                report["skinned_posed_animated"] = posed
        if kept:
            report["skinned_kept_stored"] = kept
        if odd_root:
            report["skinned_root_not_block0"] = odd_root   # posed in NIF root space anyway; flagged for the in-game look
    return out


def convert_static(fo4_nif: bytes, out_name: str, material_path: str = PLACEHOLDER_MATERIAL,
                   unit_scale: float = UNIT_SCALE, collision_template: bytes = None,
                   material_paths: list = None, collision_mode: str = "box",
                   include_skinned: bool = False, report: dict = None, sf_mesh_template: bytes = None,
                   allow_guess: bool = True, dynamic_template: bytes = None, pose: dict = None,
                   mass_scale: float = 1.0) -> Dict[str, bytes]:
    """collision_mode: "box" = one AABB on the root; "surfaces" = thin boxes behind flat surfaces, one body each.
    sf_mesh_template: a vanilla Starfield mesh-collision blob; when given, FO4's own collision mesh is transplanted
    (meshcollision.transplant) and the box methods are only the fallback.
    allow_guess=False: FO4's own collision or nothing, never a guessed box (vegetation, mounds, door frames: a box
    around them would be an invisible wall). A failed native conversion is reported as "fo4-native-failed".
    dynamic_template: FO4 loose items (one dynamic body on the root) become movable: their body goes on the root node
    and BSXFlags is 0x42 as on vanilla MiscItems; the caller places them as MoveableStatic (report["motion"]).
    pose: {node block: local transform} replacing those nodes' own transforms (ragdoll_pose.local_overrides: a placed
    reference's XRGD ragdoll pose). Shapes under those nodes, skinned shapes and collision bodies are all built in that
    pose; the result is a model for that reference only (placed_pose)."""
    mass_scale = require_mass_scale(mass_scale)
    src = nifmod.parse(fo4_nif)
    shapes = [s for s in nifmod.fo4_trishapes(src, placed=True, local_overrides=pose)
              if (include_skinned or not s.skinned) and s.positions and s.triangles]
    if not shapes:
        raise nifmod.NifError("no static BSTriShape geometry found")
    if include_skinned:                                       # node pose (or the reference's pose), as FO4 draws them
        shapes = pose_skinned_shapes(src, shapes, report, nifmod.world_transforms(src, placed=True, local_overrides=pose))
    files, static_shapes, all_pts, all_tris = {}, [], [], []
    for i, s in enumerate(shapes):
        if material_paths and material_paths[i] is None:      # caller asked to drop this shape (e.g. effect shader)
            continue
        m = shape_to_mesh(s, unit_scale)
        data = sfmesh.serialize(m)
        d, f = mesh_file_path(data)
        files[f"geometries/{d}/{f}.mesh"] = data
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        all_tris += [(a + len(all_pts), b + len(all_pts), c + len(all_pts)) for a, b, c in m.triangles]
        all_pts += pts
        sphere, box = sfnif.bounds_from_points(pts)
        name = s.name or f"Shape{i}".encode()
        static_shapes.append(sfnif.StaticShape(name, f"{d}\\{f}".encode(), len(m.triangles) * 3, len(m.positions),
                                               material_paths[i] if material_paths else material_path, sphere, box))
    node_name = out_name.rsplit("/", 1)[-1].encode()
    blob, child_blobs, bsx = None, [], None
    native, motion = None, {}
    fo4_has_collision = any(src.type_of(i) == "bhkNPCollisionObject" for i in range(len(src.blocks)))
    if sf_mesh_template is not None and collision_template is not None:
        native = fo4_native_collision(src, sf_mesh_template, report,      # FO4's own bodies as native Starfield bodies
                                      dynamic_template=dynamic_template, motion=motion,
                                      mass_scale=mass_scale,
                                      **({"pose": pose} if pose is not None else {}))
    if sf_mesh_template is not None and collision_template is not None and not fo4_has_collision:
        # FO4 gives this model no collision (rubble, debris, paper, signs, posters, plants): the player walks through
        # it there, so it gets none here either. A guessed box would be an invisible wall.
        if report is not None:
            report["source"] = "fo4-none"
    elif native and motion.get("dynamic"):
        blob, bsx = native[0], DYNAMIC_BSX           # movable: the body carries the whole model, as vanilla MiscItems
    elif native:
        child_blobs = native                         # one body per child node, as vanilla multi-body files do
    elif not allow_guess:
        if report is not None and fo4_has_collision:
            report["source"] = "fo4-native-failed"
    elif collision_template is not None and collision_mode == "surfaces":
        for c, h in sfcollision.mesh_boxes(all_pts, all_tris, report=report):
            child_blobs.append(sfcollision.box_blob(collision_template, c, h))
    elif collision_template is not None:     # T3: one axis-aligned box around all geometry
        lo = [min(p[a] for p in all_pts) for a in range(3)]
        hi = [max(p[a] for p in all_pts) for a in range(3)]
        blob = sfcollision.box_blob(collision_template, tuple((lo[a] + hi[a]) / 2 for a in range(3)),
                                    tuple((hi[a] - lo[a]) / 2 for a in range(3)))
    out = sfnif.build_static_nif(node_name, static_shapes, collision_blob=blob, child_collision_blobs=child_blobs,
                                 bsx_flags=bsx)
    files[f"meshes/{out_name}.nif"] = nifmod.serialize(out)
    return files


def convert_door(fo4_nif: bytes, out_name: str, material_paths: list, unit_scale: float = UNIT_SCALE,
                 template: dict = None, collision_template: bytes = None,
                 leaf_physics_donor: bytes = None) -> Tuple[Dict[str, bytes], tuple, tuple]:
    """FO4 hinged door -> Starfield door NIF rigged like the vanilla template door (see sfnif.DOOR_TEMPLATE).
    Shapes under the node the FO4 "Open" sequence animates become the moving leaf; everything else is the static frame.
    Geometry is re-centred on the FO4 pivot and hung under the template's hinge position, so the NIF origin moves:
    returns (files, origin_offset, bounds) where origin_offset (metres, door-local) must be added (rotated and scaled) to the
    reference position to keep the door where FO4 drew it. bounds = (min xyz, max xyz) in NIF space (for the record's OBND)."""
    template = template or sfnif.DOOR_TEMPLATE
    src = nifmod.parse(fo4_nif)
    hinge = nifmod.door_hinge(src, placed=True)
    if hinge is None:
        raise nifmod.NifError("no Open sequence / hinge node")
    moving_blocks = nifmod.descendants(src, hinge[0])
    pivot = hinge[1]
    shapes = [s for s in nifmod.fo4_trishapes(src, placed=True) if s.positions and s.triangles]
    files, static_shapes, moving_shapes, moving_pts, all_pts = {}, [], [], [], []
    for i, s in enumerate(shapes):
        if material_paths[i] is None:
            continue
        s = replace(s, translation=tuple(s.translation[a] - pivot[a] for a in range(3)))
        m = shape_to_mesh(s, unit_scale)
        data = sfmesh.serialize(m)
        d, f = mesh_file_path(data)
        files[f"geometries/{d}/{f}.mesh"] = data
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        sphere, box = sfnif.bounds_from_points(pts)
        st = sfnif.StaticShape(s.name or f"Shape{i}".encode(), f"{d}\\{f}".encode(), len(m.triangles) * 3, len(m.positions),
                               material_paths[i], sphere, box)
        all_pts += pts
        if s.block in moving_blocks:
            moving_shapes.append(st)
            moving_pts += pts
        else:
            static_shapes.append(st)
    if not moving_shapes:
        raise nifmod.NifError("door has no moving geometry")
    blob = None
    if collision_template is not None:          # box around the leaf (hinge-local): the body the player activates
        lo = [min(p[a] for p in moving_pts) for a in range(3)]
        hi = [max(p[a] for p in moving_pts) for a in range(3)]
        blob = sfcollision.box_blob(collision_template, tuple((lo[a] + hi[a]) / 2 for a in range(3)),
                                    tuple(max(sfcollision.MIN_LEAF_HALF, (hi[a] - lo[a]) / 2) for a in range(3)))
        if leaf_physics_donor is not None:      # a static body pins its node: make it keyframed like vanilla door leaves
            blob = sfcollision.keyframed(blob, leaf_physics_donor)
    out = sfnif.build_door_nif(out_name.rsplit("/", 1)[-1].encode(), static_shapes, moving_shapes, template,
                               leaf_collision=blob)
    files[f"meshes/{out_name}.nif"] = nifmod.serialize(out)
    hp = template["hinge_pos"]
    bounds = ([min(p[a] for p in all_pts) + hp[a] for a in range(3)], [max(p[a] for p in all_pts) + hp[a] for a in range(3)])
    return files, tuple(pivot[a] * unit_scale - hp[a] for a in range(3)), bounds


def frozen_door_parts(src) -> list:
    """Names of the nodes an FO4 door's "Open" sequence moves, with geometry, that are NOT below the first animated node
    (nif.door_hinge). convert_door hangs only that first node under the template's single hinge, so these parts would
    stay closed: the second leaf of a double door or shutter, the other panels of a sliding panel set. [] when the
    single hinge covers every moving shape (a door knob under its leaf) or the motion cannot be read."""
    from . import door_motion
    try:
        report = door_motion.inspect(src)
    except Exception:                                  # noqa: BLE001  (unreadable motion: keep the template door)
        return []
    outside = set(report["animated_shapes_outside_single_hinge"])
    return sorted({t["name"] for seq in report["sequences"] if seq["name"] == "Open" for t in seq["targets"]
                   if outside & set(t["shape_blocks"])})


def _apply(transform, point):
    """(t, R row-major, s) applied to a point: s * R * p + t."""
    t, r, s = transform
    return tuple(s * (r[3 * i] * point[0] + r[3 * i + 1] * point[1] + r[3 * i + 2] * point[2]) + t[i] for i in range(3))


BIND_TOLERANCE = 1e-4      # skin_to_bone entries that still count as one bind (float rounding)


def _same_bind(a, b):
    """Two (t, R, s) skin_to_bone transforms equal within BIND_TOLERANCE (relative for translation)."""
    (ta, ra, sa), (tb, rb, sb) = a, b
    scale = max(1.0, *(abs(x) for x in tuple(ta) + tuple(tb)))
    return (all(abs(x - y) <= BIND_TOLERANCE * scale for x, y in zip(ta, tb))
            and all(abs(x - y) <= BIND_TOLERANCE for x, y in zip(ra, rb)) and abs(sa - sb) <= BIND_TOLERANCE)


RIGID_SKIN_TOLERANCE = 1e-3   # weight a rigid vertex may put on other bones: half-float rounding, not a blend
# (Codex on #354: 0.995 / 0.005 across two bones was accepted and drifted 5 cm from real skinning at 10 m of travel)


def rigid_skinned_parts(src, shape, bones):
    """A skinned door shape whose every drawn vertex follows one bone fully, cut into one piece per bone and re-expressed
    in that bone's space so the rig carries each piece as an ordinary attachment: [(bone index, shape), ...] or None.
    Weight 1 on one bone makes skinning bone_world * skin_to_bone, so bone-local positions are skin_to_bone(stored) and a
    piece moves exactly as FO4 draws it, at any pose (RedRPedDoor.nif, PC check 2026-10-18: Door:0 is wholly on b_Door,
    Door:7 has 363 vertices on b_Door and 118 on b_Handle, none blended). A vertex putting more than
    RIGID_SKIN_TOLERANCE of its weight on other bones (a blend), two slots of one bone with different skin_to_bone (the
    weighted result is then not either bind; Codex on #354), a triangle across two bones or a bone outside the rig
    give None."""
    from . import fo4skin
    try:
        skin = fo4skin.read_skin(src, shape.block)
    except (nifmod.NifError, ValueError, struct.error):
        return None
    if skin is None or len(skin.weights) != len(shape.positions):
        return None
    slot_of = {}
    for v in {i for t in shape.triangles for i in t}:
        per_bone = {}                              # weights summed per bone node (two slots may name one bone)
        for w, k in zip(skin.weights[v], skin.indices[v]):
            if w:
                if not 0 <= k < len(skin.bones):
                    return None
                entry = per_bone.setdefault(skin.bones[k], [0.0, k])
                if k != entry[1] and not _same_bind(skin.skin_to_bone[k], skin.skin_to_bone[entry[1]]):
                    return None                    # one bone, two different inverse binds: one bind cannot stand in
                entry[0] += w
        total = sum(w for w, _ in per_bone.values())
        if total <= 0:
            return None
        bone = max(per_bone, key=lambda b: per_bone[b][0])
        if total - per_bone[bone][0] > RIGID_SKIN_TOLERANCE * total:     # a real blend, however small: refuse
            return None
        slot_of[v] = per_bone[bone][1]
    by_slot = {}
    for t in shape.triangles:
        slots = {slot_of[i] for i in t}
        if len(slots) != 1:
            return None
        by_slot.setdefault(slots.pop(), []).append(t)
    index = {b.get("node"): i for i, b in enumerate(bones) if b.get("node") is not None}
    if any(skin.bones[k] not in index for k in by_slot):
        return None
    parts = []
    for slot in sorted(by_slot):
        tris = by_slot[slot]
        keep = sorted({i for t in tris for i in t})
        remap = {v: n for n, v in enumerate(keep)}
        xf = skin.skin_to_bone[slot]
        r = xf[1]

        def turn(vecs):
            out = []
            for v in vecs:
                d = tuple(r[3 * a] * v[0] + r[3 * a + 1] * v[1] + r[3 * a + 2] * v[2] for a in range(3))
                ln = math.sqrt(sum(x * x for x in d)) or 1.0
                out.append(tuple(x / ln for x in d))
            return out

        def pick(values):
            return [values[v] for v in keep] if values else values
        parts.append((index[skin.bones[slot]], replace(
            shape, positions=[fo4skin.apply(xf, shape.positions[v]) for v in keep], uvs=pick(shape.uvs),
            normals=turn(pick(shape.normals)) if shape.normals else shape.normals,
            tangents=turn(pick(shape.tangents)) if shape.tangents else shape.tangents, colors=pick(shape.colors),
            triangles=[tuple(remap[i] for i in t) for t in tris],
            translation=(0.0, 0.0, 0.0), rotation=(1, 0, 0, 0, 1, 0, 0, 0, 1), scale=1.0, skinned=False)))
    return parts


def convert_multipart_door(fo4_nif: bytes, out_name: str, material_paths: list, clip_files, unit_scale: float = UNIT_SCALE,
                           collision_template: bytes = None, leaf_physics_donor: bytes = None,
                           rest_pose_check: bool = False, aliases: dict = None,
                           drop_skinned: bool = False) -> Tuple[Dict[str, bytes], dict]:
    """FO4 door whose "Open" sequence moves geometry under more than one node (frozen_door_parts: double doors,
    shutters, sliding panel sets) -> Starfield door with its OWN rig and clips, as vanilla double doors have
    (IndIntRmSmWallMid_DoorA01: one rig bone and one clip track per leaf, one keyframed body per leaf).

    Every FO4 node the door's sequences animate, and every static ancestor and shape parent, becomes a rig bone and a NIF
    node of the same name (door_rig.plan, placed: the stored root transform is left out as in game; animated bones get
    identity binds). Each moving bone that holds geometry gets its own keyframed box around that geometry (bone-local), so
    each panel's collision follows its panel. Static geometry (frames) keeps no collision, as in convert_door.
    clip_files(plan, unit_scale) -> {relative path: bytes} writes the rig and Open/Close clips (native_door.export_files
    with the external CALUMI library); they are stored next to the NIF under meshes/<out_name>/.
    material_paths: one per shape of nif.fo4_trishapes(src) with geometry, None = left out (effect shaders, markers).
    The NIF keeps FO4's origin, so the reference needs no offset. Returns (files, door) where door is the manifest entry
    (origin_offset, anim_graph, bounds, skeleton, animations, rig, animated_bones, moving_bodies, files).
    rest_pose_check: refuse a door whose Open does not start, or whose Close does not end, at the bind pose
    (door_rig.rest_pose_issue; the sliding / lifting route, which takes every NOT_HINGED_RE door).
    aliases: door_rig.plan's sequence aliases (an animated activator converted as a door, pipeline.OWN_RIG_ALIASES).
    drop_skinned: leave skinned shapes out instead of refusing the door (a rig cannot carry them); the door entry lists
    them under "dropped_skinned_shapes"."""
    from . import door_model, door_rig, native_door
    if collision_template is None or leaf_physics_donor is None:
        raise ValueError("multi-part door needs the box template and a keyframed donor body")
    src = nifmod.parse(fo4_nif)
    plan = door_rig.animated_identity_binds(door_rig.plan(src, placed=True, aliases=aliases))
    if sorted(c["name"] for c in plan["clips"]) != ["Close", "Open"]:
        raise nifmod.NifError("door needs exactly one Open and one Close sequence")   # the graph plays both
    if rest_pose_check and (issue := door_rig.rest_pose_issue(plan)):
        raise nifmod.NifError(issue)
    base = out_name.rsplit("/", 1)[-1]
    lowered = [b["name"].lower() for b in plan["bones"]] + [("FO4Port_" + base).lower()]
    if len(set(lowered)) != len(lowered):           # Bethesda node-name lookups have ignored case in earlier engines
        raise nifmod.NifError("door rig bone names collide when case is ignored")
    shapes = [s for s in nifmod.fo4_trishapes(src) if s.positions and s.triangles]
    if len(material_paths) != len(shapes):
        raise ValueError("one material entry per shape required")
    kept = {s.block: (s, m) for s, m in zip(shapes, material_paths) if m is not None}
    shape_name = lambda b, s: (s.name or f"Shape{b}".encode()).decode("latin-1")    # noqa: E731
    rebound = {}                         # piece key -> rig bone it rides rigidly (rigid_skinned_parts); one piece per bone
    for b, (s, m) in list(kept.items()):
        if s.skinned and (parts := rigid_skinned_parts(src, s, plan["bones"])) is not None:
            del kept[b]
            for k, (bone, piece) in enumerate(parts):
                key = b if len(parts) == 1 else f"{b}.{k}"
                kept[key] = (piece, m)
                rebound[key] = bone
    dropped_skinned = sorted(shape_name(b, s) for b, (s, _) in kept.items() if s.skinned)
    if dropped_skinned and not drop_skinned:
        raise nifmod.NifError("skinned door shapes cannot be rigged (blended or off-rig weights)")
    kept = {b: v for b, v in kept.items() if not v[0].skinned}
    ident = {"translation_source_units": [0.0, 0.0, 0.0], "rotation_row_major": [1, 0, 0, 0, 1, 0, 0, 0, 1], "scale": 1.0}
    pieces = {}                                    # source shape block -> its piece keys
    for key in rebound:
        pieces.setdefault(int(str(key).split(".")[0]), []).append(key)
    attachments = []
    for a in plan["attachments"]:
        if a["shape"] in pieces:
            attachments += [{**a, "shape": key, "bone": rebound[key], "local_transform": dict(ident)}
                            for key in pieces[a["shape"]]]
        elif a["shape"] in kept:
            attachments.append(a)
    plan["attachments"] = attachments
    if not plan["attachments"]:
        raise nifmod.NifError("door has no rendered geometry")
    files, sf_shapes, local_pts = {}, {}, {}
    for block, (s, material) in kept.items():
        local = replace(s, translation=(0.0, 0.0, 0.0), rotation=(1, 0, 0, 0, 1, 0, 0, 0, 1), scale=1.0)
        m = shape_to_mesh(local, unit_scale)
        data = sfmesh.serialize(m)
        d, f = mesh_file_path(data)
        files[f"geometries/{d}/{f}.mesh"] = data
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        sphere, box = sfnif.bounds_from_points(pts)
        sf_shapes[block] = sfnif.StaticShape(s.name or f"Shape{block}".encode(), f"{d}\\{f}".encode(), len(m.triangles) * 3,
                                             len(m.positions), material, sphere, box)
        local_pts[block] = pts
    bones = plan["bones"]
    world = []                                     # bone -> model-space (t metres, R, s), parents first
    for bone in bones:
        b = bone["bind"]
        w, x, y, z = b["quaternion_wxyz"]
        r = (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y), 2 * (x * y + w * z), 1 - 2 * (x * x + z * z),
             2 * (y * z - w * x), 2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y))
        local = (tuple(v * unit_scale for v in b["translation_source_units"]), r, b["scale"])
        world.append(local if bone["parent"] == -1 else nifmod._compose(world[bone["parent"]], local))
    animated = {t["node"] for clip in plan["clips"] for t in clip["tracks"]}
    moving = set()
    for i, bone in enumerate(bones):
        if bone["node"] in animated or (bone["parent"] != -1 and bone["parent"] in moving):
            moving.add(i)
    bone_pts, all_pts = {}, []
    for a in plan["attachments"]:
        lt = a["local_transform"]
        attach = (tuple(v * unit_scale for v in lt["translation_source_units"]), tuple(lt["rotation_row_major"]), lt["scale"])
        pts = [_apply(attach, p) for p in local_pts[a["shape"]]]
        all_pts += [_apply(world[a["bone"]], p) for p in pts]
        if a["bone"] in moving:
            bone_pts.setdefault(a["bone"], []).extend(pts)
    collision = {}
    for i, pts in sorted(bone_pts.items()):
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        blob = sfcollision.box_blob(collision_template, tuple((lo[k] + hi[k]) / 2 for k in range(3)),
                                    tuple(max(sfcollision.MIN_LEAF_HALF, (hi[k] - lo[k]) / 2) for k in range(3)))
        collision[bones[i]["node"]] = sfcollision.keyframed(blob, leaf_physics_donor)
    if not collision:
        raise nifmod.NifError("door has no moving geometry")
    model = door_model.build(plan, sf_shapes, unit_scale, collision, name=("FO4Port_" + base).encode())
    files[f"meshes/{out_name}.nif"] = nifmod.serialize(model)
    extra = clip_files(plan, unit_scale)
    if native_door.RIG_FILE not in extra or not any(k.startswith(native_door.CLIP_DIR + "/") for k in extra):
        raise ValueError("clip writer returned no rig or clips")
    for relative, data in extra.items():
        files[f"meshes/{out_name}/{relative}"] = data
    door = {"origin_offset": [0.0, 0.0, 0.0], "anim_graph": sfnif.DOOR_TEMPLATE["anim_graph"],
            "bounds": [[round(min(p[k] for p in all_pts), 4) for k in range(3)],
                       [round(max(p[k] for p in all_pts), 4) for k in range(3)]],
            "skeleton": f"{out_name}/{native_door.RIG_FILE}".replace("/", "\\"),
            "animations": f"{out_name}/{native_door.CLIP_DIR}".replace("/", "\\"),
            "rig": "native",
            "animated_bones": sorted({bones[i]["name"] for i in range(len(bones)) if bones[i]["node"] in animated}),
            "moving_bodies": len(collision),
            "open_motion": door_rig.open_motion(plan, unit_scale),
            "files": sorted(f"meshes/{out_name}/{relative}" for relative in extra)}
    if plan.get("ignored_tracks"):                  # shader / visibility tracks FO4 also plays: not ported, said so
        door["ignored_tracks"] = sorted({f'{t["target"]} ({t["reason"]})' for t in plan["ignored_tracks"]})
    if dropped_skinned:
        door["dropped_skinned_shapes"] = dropped_skinned
    if rebound:
        door["rebound_skinned_shapes"] = sorted({shape_name(b, kept[b][0]) for b in rebound})
        door["rebound_skinned_pieces"] = len(rebound)
    if aliases:
        door["sequence_aliases"] = dict(aliases)
    return files, door


# Grok: per-class mass scale (physics-conversion.md §4.2). Values are initial stubs from research notes;
# owner can override. Applied before Havok mass write so small items feel lighter and large props heavier.
# Synthetic tests in tests/test_mass_scale.py.
CLASS_MASS_SCALE = {
    "small_misc": 0.2,      # cans, caps, notes, keys — lighter than FO4 default
    "medium_misc": 1.0,     # books, ammo boxes
    "large_mstt": 2.0,      # crates, barrels, furniture pieces
    "weapon": 1.0,          # world-placed WEAP pickups
    "alch": 0.5,            # chems, food — typically light
    "armor": 1.5,           # armor pieces
    "ammo": 0.3,            # ammo boxes / loose
    "note": 0.1,            # notes, holotapes
    "container": 3.0,       # larger containers if treated as movable
}

def class_mass_scale(item_class: str, base_scale: float = 1.0) -> float:
    """Return mass multiplier for a classified item. Falls back to base_scale.
    item_class is a short token (small_misc, large_mstt, ...). Unknown classes keep base_scale.
    """
    if not item_class:
        return base_scale
    return CLASS_MASS_SCALE.get(item_class.lower(), base_scale)
