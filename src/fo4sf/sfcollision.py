"""Starfield box collision (spike S6, tier T3): patch a vanilla box-collision Havok blob to a new axis-aligned box.

`bhkPhysicsSystem` holds a Havok tagfile (`TAG0`). We do not write tagfiles; we take a vanilla blob that contains a single
`hknpBoxShape` (read at run time from the user's own game archives, never committed) and overwrite the floats that depend on the
box. They were found by regressing 369 vanilla identity-rotation box blobs (6,168 bytes each) against the box centre and
half-extents: 36 words depend on the box and fit exactly (6 centre/half-size words, the 8 corner points, 6 face planes; see
docs/spikes/S6-collision.md). Six other varying words are constant/zero and the rest are mass/inertia or padding; they are left as
in the template. The vanilla body is a movable (dynamic) one, so converted objects can be pushed.
"""
import struct
from typing import Tuple

BLOB_SIZE = 6168
# offsets (bytes into the blob) -> coefficients over (cx, cy, cz, hx, hy, hz)
_V = [(1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1), (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1)]


def _build_table():
    t = {540: (0, 0, 0, 1, 0, 0), 556: (0, 0, 0, 0, 1, 0), 572: (0, 0, 0, 0, 0, 1),
         576: (1, 0, 0, 0, 0, 0), 580: (0, 1, 0, 0, 0, 0), 584: (0, 0, 1, 0, 0, 0)}
    for k, (sx, sy, sz) in enumerate(_V):                 # the 8 box corners, hkFloat3 each
        base = 592 + 12 * k
        t[base] = (1, 0, 0, sx, 0, 0)
        t[base + 4] = (0, 1, 0, 0, sy, 0)
        t[base + 8] = (0, 0, 1, 0, 0, sz)
    # six face-plane offsets
    t[700] = (-1, 0, 0, -1, 0, 0)
    t[716] = (1, 0, 0, -1, 0, 0)
    t[732] = (0, -1, 0, 0, -1, 0)
    t[748] = (0, 1, 0, 0, -1, 0)
    t[764] = (0, 0, -1, 0, 0, -1)
    t[780] = (0, 0, 1, 0, 0, -1)
    return t


LINEAR = _build_table()
MIN_HALF = 0.005


class CollisionError(ValueError):
    pass


def check_template(blob: bytes):
    if len(blob) != BLOB_SIZE or not blob.startswith(b"\x00\x00\x18\x18TAG0"):
        raise CollisionError(f"template blob is not a 6,168-byte Havok tagfile (got {len(blob)} bytes)")
    if b"hknpBoxShape" not in blob or b"hknpCompoundShape" in blob or b"hknpCompressedMeshShape" in blob:
        raise CollisionError("template blob is not a plain box shape")
    if struct.unpack_from("<3f", blob, 528) != (1.0, 0.0, 0.0) or struct.unpack_from("<3f", blob, 544) != (0.0, 1.0, 0.0) \
            or struct.unpack_from("<3f", blob, 560) != (0.0, 0.0, 1.0):
        raise CollisionError("template box is rotated; need an identity-rotation template")


def box_blob(template: bytes, center: Tuple[float, float, float], half: Tuple[float, float, float]) -> bytes:
    """Return a copy of `template` describing the axis-aligned box (centre, half-extents) in metres."""
    check_template(template)
    h = tuple(max(MIN_HALF, abs(v)) for v in half)
    feat = (*center, *h)
    out = bytearray(template)
    for off, coef in LINEAR.items():
        struct.pack_into("<f", out, off, sum(c * f for c, f in zip(coef, feat)))
    return bytes(out)


def read_box(blob: bytes):
    """Inverse of box_blob for the fields we write: (centre, half-extents) from the 8 corners."""
    pts = [struct.unpack_from("<3f", blob, 592 + 12 * k) for k in range(8)]
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    return tuple((lo[a] + hi[a]) / 2 for a in range(3)), tuple((hi[a] - lo[a]) / 2 for a in range(3))
