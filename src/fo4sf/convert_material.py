"""Fallout 4 .bgsm material + textures -> Starfield .mat + converted DDS files (spike S3, fidelity tier T2).

The Starfield `.mat` is a component database in JSON. We clone a vanilla single-layer PBR material read from the user's own
Creation Kit install (`Tools/ContentResources.zip`, never committed), re-point its three texture slots, set a white tint and
give every object it defines a new ID so it cannot clash with the vanilla material it was cloned from.
"""
import json
import struct
import zipfile
import zlib
from dataclasses import dataclass
from typing import Dict, Optional

TEMPLATE_MAT = "Materials/Common/Metal/MetalIronCast01.mat"      # inside ContentResources.zip
TEMPLATE_TEXTURES = {   # the three texture slots of that template (as written in the file)
    "Albedo": "Data\\Textures\\Common\\stone\\StoneMarblePolished02_color.DDS",
    "Normal": "Data\\Textures\\Common\\Concrete\\ConcretePlain02_normal.DDS",
    "Roughness": "Data\\Textures\\Common\\Concrete\\ConcretePlain02_rough.DDS",
}


@dataclass
class Bgsm:
    version: int
    tile_u: bool
    tile_v: bool
    uv_offset: tuple
    uv_scale: tuple
    diffuse: str
    normal: str
    smooth_spec: str
    greyscale: str
    envmap: str
    glow: str


def parse_bgsm(d: bytes) -> Bgsm:
    if d[:4] != b"BGSM":
        raise ValueError("not a BGSM file")
    version, tiles = struct.unpack_from("<II", d, 4)
    uo, vo, us, vs = struct.unpack_from("<4f", d, 12)
    # the texture block starts at the first length-prefixed string that ends in .dds/.tga (before it: flags/floats)
    start = None
    for off in range(8, len(d) - 8):
        ln, = struct.unpack_from("<I", d, off)
        if 4 < ln < 260 and d[off + 3 + ln] == 0 and d[off + 4:off + 3 + ln].lower().endswith((b".dds", b".tga")):
            start = off
            break
    if start is None:
        raise ValueError("no texture paths found")
    out, pos = [], start
    for _ in range(6):
        ln, = struct.unpack_from("<I", d, pos)
        out.append(d[pos + 4:pos + 4 + ln].rstrip(b"\0").decode("latin-1"))
        pos += 4 + ln
    return Bgsm(version, bool(tiles & 2), bool(tiles & 1), (uo, vo), (us, vs), *out)


def read_template(content_resources_zip: str) -> dict:
    with zipfile.ZipFile(content_resources_zip) as z:
        name = next(n for n in z.namelist() if n.lower() == TEMPLATE_MAT.lower())
        return json.loads(z.read(name).decode("utf-8-sig"))


def _new_id(old: str, salt: str) -> str:
    a, b, c = old[4:].split(":")
    return f"res:{zlib.crc32((salt + old).encode()) & 0xFFFFFFFF:08X}:{b}:{c}"


def build_mat(template: dict, name: str, albedo: str, normal: str, rough: str,
              tint=(1.0, 1.0, 1.0, 1.0), metalness: float = 0.0) -> dict:
    """Return a new .mat dict. Texture arguments are game paths like 'Data\\Textures\\...\\x_color.dds'."""
    mat = json.loads(json.dumps(template))
    defined = {o["ID"] for o in mat["Objects"] if "ID" in o}
    remap = {i: _new_id(i, name) for i in defined}
    repl = {TEMPLATE_TEXTURES["Albedo"]: albedo, TEMPLATE_TEXTURES["Normal"]: normal, TEMPLATE_TEXTURES["Roughness"]: rough}

    def walk(x):
        if isinstance(x, dict):
            for k, v in list(x.items()):
                if k == "Parent":
                    continue                        # class ids / vanilla parents stay as they are
                x[k] = walk(v)
            if x.get("Type") == "BSComponentDB::CTName" and "Name" in x.get("Data", {}):
                x["Data"]["Name"] = x["Data"]["Name"].replace("MetalIronCast01", name)
            return x
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, str):
            return remap.get(x, repl.get(x, x))
        return x

    mat = walk(mat)
    for o in mat["Objects"]:                        # base colour tint of the material object
        for c in o.get("Components", []):
            if c.get("Type") == "BSMaterial::Color" and "Value" in c.get("Data", {}) and c.get("Index") == 0 \
                    and "Edges" in o and any(cc.get("Type") == "BSMaterial::TextureSetID" for cc in o["Components"]):
                d = c["Data"]["Value"]["Data"]
                d["x"], d["y"], d["z"], d["w"] = (str(tint[0]), str(tint[1]), str(tint[2]), str(tint[3]))
    layer = mat["Summary"]["Layer1"]
    layer["Tint"] = {"w": tint[3], "x": tint[0], "y": tint[1], "z": tint[2]}
    m = layer["Textures"]["Metalness"]
    m["Replacement"] = {"w": 1, "x": metalness, "y": metalness, "z": metalness}
    m["UseReplacement"] = True
    return mat


def dump_mat(mat: dict) -> str:
    return json.dumps(mat, indent="\t", separators=(",", " : "), ensure_ascii=False)


def game_path(rel: str) -> str:
    return "Data\\" + rel.replace("/", "\\")
