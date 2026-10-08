"""Decode FO4 NiTransformData curves; no target animation emission yet.

Layout follows niftools/nifxml NiKeyframeData, KeyGroup, Key and QuatKey.
Preserve tangents/TBC rather than replacing source interpolation with linear keys.
"""
import math
import struct
from .nif import NifError


def decode(data):
    offset = 0

    def take(fmt):
        nonlocal offset
        size = struct.calcsize(fmt)
        if offset + size > len(data):
            raise NifError("truncated transform curve")
        values = struct.unpack_from(fmt, data, offset)
        offset += size
        if any(isinstance(v, float) and not math.isfinite(v) for v in values):
            raise NifError("nonfinite transform curve")
        return values

    def group(dimensions):
        count, = take("<I")
        if count == 0:
            return {"interpolation": None, "keys": []}
        interpolation, = take("<I")
        if interpolation not in (1, 2, 3):
            raise NifError("unsupported transform key interpolation")
        keys = []
        for _ in range(count):
            time, = take("<f")
            key = {"time": time, "value": list(take(f"<{dimensions}f"))}
            if interpolation == 2:
                key["forward"] = list(take(f"<{dimensions}f"))
                key["backward"] = list(take(f"<{dimensions}f"))
            elif interpolation == 3:
                key["tension_bias_continuity"] = list(take("<3f"))
            keys.append(key)
        return {"interpolation": interpolation, "keys": keys}

    count, = take("<I")
    rotation = {"representation": "quaternion_wxyz", "interpolation": None, "keys": []}
    if count:
        interpolation, = take("<I")
        if interpolation == 4:
            if count != 1:
                raise NifError("XYZ rotation must have one outer key group")
            rotation = {"representation": "euler_xyz_radians", "axes": [group(1) for _ in range(3)]}
        elif interpolation in (1, 2, 3):
            rotation["interpolation"] = interpolation
            for _ in range(count):
                time, = take("<f")
                key = {"time": time, "value": list(take("<4f"))}
                if interpolation == 3:
                    key["tension_bias_continuity"] = list(take("<3f"))
                rotation["keys"].append(key)
        else:
            raise NifError("unsupported rotation interpolation")
    translation, scale = group(3), group(1)
    if offset != len(data):
        raise NifError("unparsed transform curve bytes")
    return {"rotation": rotation, "translation_source_units": translation, "scale": scale}
