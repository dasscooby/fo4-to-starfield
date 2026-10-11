"""Fallout 4 skinning: read a skinned BSTriShape's skin and pose its vertices by linear blend skinning.

    n = nif.parse(data)
    for s in nif.fo4_trishapes(n):
        skin = fo4skin.read_skin(n, s.block)          # None for an unskinned shape
        if skin:
            posed = fo4skin.pose_vertices(s.positions, skin, fo4skin.node_world(n, skin))

Transforms use nif.py's convention: (t, R as a row-major 9-tuple, s) with v' = s * R * v + t.

Layouts (BS 130). Evidence: docs/ai/research-log.md, 2026-10-10 "FO4 skin reader".
  BSSkin::Instance  i32 skeleton root (block ptr), i32 bone data (block ref), u32 bone count N, N x i32 bone nodes
                    (block ptrs), u32 count M, then M x 3 f32. M is 0 or N; vanilla FO4 has M = N only in FaceGen
                    heads, every vector (0, 1, 1). Kept as `extra`; meaning unresolved.
  BSSkin::BoneData  u32 bone count N, then N x 68 bytes: bounding sphere (centre xyz, radius; bone space), rotation
                    9 x f32 (row-major, same as NiAVObject), translation 3 x f32, scale f32. The transform maps skin
                    (shape) space into the bone's space; slot k matches bone k of the instance.
  Vertex skin data  when the vertex attributes (descriptor >> 44) have VF_SKIN (0x40): at byte
                    ((descriptor >> 28) & 0xF) * 4 of each vertex, 4 x f16 weights then 4 x u8 bone slots.

The NIF's own node pose is not always the bind pose (SkeletonClothed01: the root bone is turned 45 degrees), so
node_world(...) poses the mesh the way the NIF's nodes (and its ragdoll bodies) stand, which can differ from the stored
positions.
"""
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .nif import VF_SKIN, NifError, NifFile, _compose, world_transforms

SHAPE_TYPES = ("BSTriShape", "BSSubIndexTriShape", "BSMeshLODTriShape")
BONE_ENTRY = 68                      # sphere 16 + rotation 36 + translation 12 + scale 4
IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0), 1.0)

Transform = Tuple[tuple, tuple, float]


@dataclass
class Fo4Skin:
    shape: int                       # BSTriShape block index
    instance: int                    # BSSkin::Instance block index
    data: int                        # BSSkin::BoneData block index
    skeleton_root: int               # block index the instance points to (-1 if none)
    bones: List[int]                 # bone node block indices, in skin slot order
    bone_names: List[bytes]
    skin_to_bone: List[Transform]    # per slot: skin (shape) space -> bone space
    bounds: List[tuple]              # per slot: bounding sphere (cx, cy, cz, radius), bone space
    weights: List[tuple]             # per vertex: 4 weights (half-float precision)
    indices: List[tuple]             # per vertex: 4 bone slots
    extra: List[tuple] = field(default_factory=list)   # the instance's trailing Vector3s (FaceGen: (0, 1, 1) per bone)


def read_instance(blk: bytes):
    """(skeleton root, bone data ref, bone node refs, trailing Vector3s) of a BSSkin::Instance block."""
    root, data, nbones = struct.unpack_from("<iiI", blk, 0)
    p = 12 + 4 * nbones
    if p + 4 > len(blk):
        raise NifError(f"BSSkin::Instance: {nbones} bones run past the block ({len(blk)} bytes)")
    bones = list(struct.unpack_from(f"<{nbones}i", blk, 12))
    nextra, = struct.unpack_from("<I", blk, p)
    if p + 4 + 12 * nextra != len(blk):
        raise NifError(f"BSSkin::Instance: size {len(blk)} != {p + 4} + 12 * {nextra}")
    extra = [struct.unpack_from("<3f", blk, p + 4 + 12 * k) for k in range(nextra)]
    return root, data, bones, extra


def read_bone_data(blk: bytes):
    """(bounding spheres, skin-to-bone transforms) of a BSSkin::BoneData block, one entry per bone slot."""
    nbones, = struct.unpack_from("<I", blk, 0)
    if 4 + BONE_ENTRY * nbones != len(blk):
        raise NifError(f"BSSkin::BoneData: size {len(blk)} != 4 + {BONE_ENTRY} * {nbones}")
    bounds, xforms = [], []
    for k in range(nbones):
        o = 4 + BONE_ENTRY * k
        bounds.append(struct.unpack_from("<4f", blk, o))
        rot = struct.unpack_from("<9f", blk, o + 16)
        tr = struct.unpack_from("<3f", blk, o + 52)
        scale, = struct.unpack_from("<f", blk, o + 64)
        xforms.append((tr, rot, scale))
    return bounds, xforms


def _shape_header(blk: bytes):
    """(skin ref, vertex descriptor, vertex count, vertex data offset) of a BS 130 BSTriShape-family block."""
    _, nextra = struct.unpack_from("<iI", blk, 0)
    p = 8 + 4 * nextra + 8 + 52 + 4 + 16     # extra refs, controller + flags, transform, collision, bounding sphere
    skin, = struct.unpack_from("<i", blk, p)
    desc, = struct.unpack_from("<Q", blk, p + 12)
    ntri, nvert, dsize = struct.unpack_from("<IHI", blk, p + 20)
    vsize = (desc & 0xF) * 4
    if dsize and dsize != vsize * nvert + ntri * 6:
        raise NifError(f"vertex data size {dsize} != {vsize}*{nvert}+{ntri}*6")
    return skin, desc, (nvert if dsize else 0), p + 30


def read_vertex_skin(blk: bytes):
    """(weights, bone slots) per vertex of a skinned BSTriShape-family block (BS 130); ([], []) when not skinned."""
    _, desc, nvert, p = _shape_header(blk)
    if not (desc >> 44) & VF_SKIN:
        return [], []
    vsize = (desc & 0xF) * 4
    off = ((desc >> 28) & 0xF) * 4
    if off < 8 or off + 12 > vsize:
        raise NifError(f"skin data offset {off} does not fit a {vsize}-byte vertex")
    weights, indices = [], []
    for v in range(nvert):
        q = p + v * vsize + off
        weights.append(struct.unpack_from("<4e", blk, q))
        indices.append(tuple(blk[q + 8:q + 12]))
    return weights, indices


def _block_name(n: NifFile, i: int) -> bytes:
    if not (0 <= i < len(n.blocks)) or len(n.blocks[i]) < 4:
        return b""
    si, = struct.unpack_from("<i", n.blocks[i], 0)
    return n.strings[si] if 0 <= si < len(n.strings) else b""


def read_skin(n: NifFile, shape: int) -> Optional[Fo4Skin]:
    """The skin of FO4 shape block `shape`, or None when it has no skin (no skin ref or no VF_SKIN vertex flag)."""
    if n.bs_version != 130:
        raise NifError(f"read_skin needs BS 130, got {n.bs_version}")
    if n.type_of(shape) not in SHAPE_TYPES:
        raise NifError(f"block {shape} is {n.type_of(shape)}, not a BSTriShape")
    blk = n.blocks[shape]
    skin_ref, desc, _, _ = _shape_header(blk)
    if skin_ref < 0 or not (desc >> 44) & VF_SKIN:
        return None
    if not (0 <= skin_ref < len(n.blocks)) or n.type_of(skin_ref) != "BSSkin::Instance":
        kind = n.type_of(skin_ref) if 0 <= skin_ref < len(n.blocks) else "out of range"
        raise NifError(f"block {shape}: skin ref {skin_ref} is {kind}, not BSSkin::Instance")
    root, data, bones, extra = read_instance(n.blocks[skin_ref])
    if not (0 <= data < len(n.blocks)) or n.type_of(data) != "BSSkin::BoneData":
        raise NifError(f"block {skin_ref}: bone data ref {data} is not BSSkin::BoneData")
    bounds, xforms = read_bone_data(n.blocks[data])
    if len(xforms) != len(bones):
        raise NifError(f"block {skin_ref}: {len(bones)} bones but bone data {data} has {len(xforms)}")
    weights, indices = read_vertex_skin(blk)
    for v, (ws, idx) in enumerate(zip(weights, indices)):
        used = [k for w, k in zip(ws, idx) if w != 0.0] or idx[:1]       # a weightless vertex follows its first slot
        if max(used) >= len(bones):
            raise NifError(f"block {shape}: vertex {v} uses bone slot {max(used)} of {len(bones)}")
    return Fo4Skin(shape, skin_ref, data, root, bones, [_block_name(n, b) for b in bones], xforms, bounds,
                   weights, indices, extra)


def invert(xf: Transform) -> Transform:
    """Inverse of (t, R, s) for an orthonormal R and a non-zero uniform scale."""
    t, r, s = xf
    rt = (r[0], r[3], r[6], r[1], r[4], r[7], r[2], r[5], r[8])
    k = 1.0 / s
    return tuple(-k * (rt[3 * a] * t[0] + rt[3 * a + 1] * t[1] + rt[3 * a + 2] * t[2]) for a in range(3)), rt, k


def apply(xf: Transform, v) -> tuple:
    t, r, s = xf
    return tuple(s * (r[3 * a] * v[0] + r[3 * a + 1] * v[1] + r[3 * a + 2] * v[2]) + t[a] for a in range(3))


def node_world(n: NifFile, skin: Fo4Skin) -> List[Transform]:
    """World transforms of the skin's bone nodes as stored in the NIF (one per slot, nif.world_transforms)."""
    world = world_transforms(n)
    out = []
    for k, b in enumerate(skin.bones):
        if not (0 <= b < len(n.blocks)) or not n.type_of(b).endswith("Node"):
            raise NifError(f"skin {skin.instance}: bone slot {k} -> block {b} is not a node")
        out.append(world(b))
    return out


def bind_world(skin: Fo4Skin, shape_world: Transform = IDENTITY) -> List[Transform]:
    """Bone world transforms of the bind pose: shape_world * inverse(skin_to_bone). Posing with these returns
    shape_world applied to the stored positions."""
    return [_compose(shape_world, invert(sb)) for sb in skin.skin_to_bone]


def skin_transforms(skin: Fo4Skin, bone_world: Sequence[Transform]) -> List[Transform]:
    """Per slot: bone_world * skin_to_bone, the transform that slot applies to a stored (skin space) position."""
    if len(bone_world) != len(skin.bones):
        raise ValueError(f"{len(bone_world)} bone transforms for {len(skin.bones)} bones")
    return [_compose(bw, sb) for bw, sb in zip(bone_world, skin.skin_to_bone)]


def pose_vertices(positions, skin: Fo4Skin, bone_world: Sequence[Transform], normalize: bool = True) -> List[tuple]:
    """Linear blend skinning: sum over a vertex's slots of weight * (bone_world[slot] * skin_to_bone[slot])(position).
    `positions` are the shape's stored positions (skin space); `bone_world` holds one transform per bone slot in the
    output space (node_world for the NIF's own pose). normalize divides by the vertex's weight sum (f16 weights sum to
    1 only within rounding). A vertex with no weight at all follows its first slot (vanilla FO4 has 57 such vertices
    in 11 shapes, none used by a triangle)."""
    if len(positions) != len(skin.weights):
        raise ValueError(f"{len(positions)} positions for {len(skin.weights)} skinned vertices")
    mats = []
    for t, r, s in skin_transforms(skin, bone_world):
        mats.append((s * r[0], s * r[1], s * r[2], t[0], s * r[3], s * r[4], s * r[5], t[1],
                     s * r[6], s * r[7], s * r[8], t[2]))
    out = []
    for p, ws, ks in zip(positions, skin.weights, skin.indices):
        if not any(ws):
            ws, ks = (1.0,), ks[:1]
        x = y = z = total = 0.0
        px, py, pz = p
        for w, k in zip(ws, ks):
            if w == 0.0:
                continue
            m = mats[k]
            x += w * (m[0] * px + m[1] * py + m[2] * pz + m[3])
            y += w * (m[4] * px + m[5] * py + m[6] * pz + m[7])
            z += w * (m[8] * px + m[9] * py + m[10] * pz + m[11])
            total += w
        if normalize:
            x, y, z = x / total, y / total, z / total
        out.append((x, y, z))
    return out
