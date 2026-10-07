"""Batch conversion of Fallout 4 statics read straight from the game's BA2 archives.

    src = Fo4Archives("<FO4 Data dir>")
    conv = Converter(src, staging, texconv, content_resources_zip, collision_template_nif_bytes)
    result = conv.convert_nif("meshes/setdressing/patiofurniture/chairpatio01.nif")

Each shape uses its own material; materials/textures are converted once and cached. Anything that cannot be converted falls
back to a placeholder material (tier T1) instead of failing the asset. Needs numpy and texconv.
"""
import os
import re
import shutil
import struct
import tempfile
from typing import Dict, List, Optional

from . import ba2 as ba2mod
from . import convert_material as cm
from . import convert_static, nif, sfcollision, textures


class Fo4Archives:
    def __init__(self, data_dir: str):
        self.meshes, self.materials, self.textures = [], [], []
        for fn in sorted(os.listdir(data_dir)):
            low = fn.lower()
            if not (low.endswith(".ba2") and low.startswith("fallout4 - ")):
                continue
            if "meshes" in low:
                self.meshes.append(ba2mod.Ba2(os.path.join(data_dir, fn)))
            elif "materials" in low:
                self.materials.append(ba2mod.Ba2(os.path.join(data_dir, fn)))
            elif "textures" in low:
                self.textures.append(ba2mod.Ba2(os.path.join(data_dir, fn)))

    @staticmethod
    def _read(archives, name):
        for a in archives:
            i = a.find(name)
            if i is not None:
                return a.read(i)
        return None

    def mesh(self, name):
        return self._read(self.meshes, name)

    def material(self, name):
        return self._read(self.materials, name)

    def texture(self, name):
        n = name.replace("\\", "/").lstrip("/")
        return self._read(self.textures, n if n.lower().startswith("textures/") else "textures/" + n)

    def mesh_names(self, pattern: str):
        rx = re.compile(pattern, re.I)
        out = []
        for a in self.meshes:
            out += [n for n in a.names if n.lower().endswith(".nif") and rx.search(n.replace("\\", "/"))]
        return sorted(set(out), key=str.lower)


def _plane_pair(dds: bytes, tmp: str, texconv_exe: str):
    """(R, G) uint8 planes of a DDS: native BC5, otherwise decoded through texconv."""
    h = textures.read_dds_header(dds)
    if h["dxgi"] in (83, 84) or h["fourcc"] in (b"BC5U", b"ATI2"):
        return textures.decode_bc5(dds[h["data_offset"]:], h["width"], h["height"])
    import numpy as np
    src = os.path.join(tmp, "dec_in.dds")
    open(src, "wb").write(dds)
    textures.texconv(texconv_exe, src, tmp, "R8G8B8A8_UNORM", ("-m", "1"))
    out = open(os.path.join(tmp, "dec_in.dds"), "rb").read()
    hh = textures.read_dds_header(out)
    px = np.frombuffer(out[hh["data_offset"]:hh["data_offset"] + hh["width"] * hh["height"] * 4], dtype=np.uint8)
    px = px.reshape(hh["height"], hh["width"], 4)
    return px[:, :, 0].copy(), px[:, :, 1].copy()


class Converter:
    def __init__(self, src: Fo4Archives, staging: str, texconv_exe: str, content_resources: str,
                 collision_template: Optional[bytes] = None, prefix: str = "fo4port",
                 no_collision_pattern: str = r"^meshes[\\/](architecture|interiors)[\\/]"):
        self.src, self.staging, self.texconv = src, staging, texconv_exe
        self.template_mat = cm.read_template(content_resources)
        self.collision_template = collision_template
        self.prefix = prefix
        # one AABB box is wrong for architecture (a corridor piece would become a solid block), so skip it there for now
        self.no_collision = re.compile(no_collision_pattern, re.I) if no_collision_pattern else None
        self._materials: Dict[str, Optional[str]] = {}
        self.stats = {"assets": 0, "failed": 0, "materials_ok": 0, "materials_fallback": 0}
        self.material_errors: Dict[str, str] = {}

    # -- materials ---------------------------------------------------------------------------
    def material(self, bgsm_path: str) -> Optional[str]:
        """Convert a .bgsm (once) and return its Starfield material path, or None to use the placeholder."""
        m = re.search(r"materials[\\/].*", bgsm_path, re.I)      # some NIFs store the developer's absolute build path
        bgsm_path = m.group(0) if m else bgsm_path
        key = bgsm_path.replace("/", "\\").lower()
        if key not in self._materials:
            try:
                self._materials[key] = self._convert_material(bgsm_path)
                self.stats["materials_ok"] += 1
            except Exception as e:                        # noqa: BLE001  (fallback by design; reason is recorded)
                self._materials[key] = None
                self.stats["materials_fallback"] += 1
                self.material_errors[bgsm_path] = f"{type(e).__name__}: {e}"
        return self._materials[key]

    def _convert_material(self, bgsm_path: str) -> str:
        raw = self.src.material(bgsm_path)
        if raw is None:
            raise FileNotFoundError("bgsm not in archives")
        b = cm.parse_bgsm(raw)
        if not (b.diffuse and b.normal and b.smooth_spec):
            raise ValueError("material lacks diffuse/normal/spec textures")
        rel = re.sub(r"^materials[\\/]", "", bgsm_path.replace("\\", "/"), flags=re.I)
        stem = os.path.splitext(rel)[0].lower()
        tex_rel = f"textures/{self.prefix}/{stem}"
        d, n, s = (self.src.texture(p) for p in (b.diffuse, b.normal, b.smooth_spec))
        if d is None or n is None or s is None:
            raise FileNotFoundError("texture missing from archives")
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "d.dds"), "wb").write(d)
            textures.texconv(self.texconv, os.path.join(tmp, "d.dds"), tmp, "BC1_UNORM_SRGB", ("-srgbi",))
            nr, ng = _plane_pair(n, tmp, self.texconv)
            _sr, sg = _plane_pair(s, tmp, self.texconv)
            textures.write_rg8_snorm(os.path.join(tmp, "n_in.dds"), nr, ng)
            textures.texconv(self.texconv, os.path.join(tmp, "n_in.dds"), tmp, "BC5_SNORM")
            textures.write_r8(os.path.join(tmp, "r_in.dds"), textures.roughness_from_smoothness(sg))
            textures.texconv(self.texconv, os.path.join(tmp, "r_in.dds"), tmp, "BC4_UNORM")
            for kind, fn in (("color", "d.dds"), ("normal", "n_in.dds"), ("rough", "r_in.dds")):
                dst = os.path.join(self.staging, *f"{tex_rel}_{kind}.dds".split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(tmp, fn), dst)
                out[kind] = cm.game_path(f"{tex_rel}_{kind}.dds")
        mat = cm.build_mat(self.template_mat, "FO4Port_" + os.path.basename(stem), out["color"], out["normal"], out["rough"])
        mat_rel = f"materials/{self.prefix}/{stem}.mat"
        p = os.path.join(self.staging, *mat_rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8", newline="\n").write(cm.dump_mat(mat))
        return mat_rel.replace("/", "\\")

    # -- meshes -------------------------------------------------------------------------------
    def convert_nif(self, nif_name: str) -> dict:
        res = {"nif": nif_name, "ok": False}
        try:
            raw = self.src.mesh(nif_name)
            src = nif.parse(raw)
            shapes = [s for s in nif.fo4_trishapes(src) if not s.skinned and s.positions and s.triangles]
            if not shapes:
                raise ValueError("no static BSTriShape geometry")
            mats: List[str] = []
            for s in shapes:
                path = None
                if s.shader_ref >= 0 and src.type_of(s.shader_ref) == "BSLightingShaderProperty":
                    idx, = struct.unpack_from("<i", src.blocks[s.shader_ref], 4)
                    if 0 <= idx < len(src.strings) and src.strings[idx].lower().endswith(b".bgsm"):
                        path = src.strings[idx].decode("latin-1")
                m = self.material(path) if path else None
                mats.append(m or convert_static.PLACEHOLDER_MATERIAL)
            rel = re.sub(r"^meshes[\\/]", "", nif_name.replace("\\", "/"), flags=re.I)
            out_name = f"{self.prefix}/{os.path.splitext(rel)[0].lower()}"
            arch = bool(self.no_collision and self.no_collision.search(nif_name))
            mode = "surfaces" if arch else "box"        # architecture: thin boxes behind flat surfaces; props: one AABB
            use_box = self.collision_template is not None
            files = convert_static.convert_static(raw, out_name, material_paths=mats, collision_mode=mode,
                                                  collision_template=self.collision_template)
            for relp, data in files.items():
                p = os.path.join(self.staging, *relp.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "wb").write(data)
            res.update(ok=True, out_name=out_name, shapes=len(shapes), materials=mats, collision=mode if use_box else None,
                       fallback_materials=sum(1 for m in mats if m == convert_static.PLACEHOLDER_MATERIAL))
            self.stats["assets"] += 1
        except Exception as e:                           # noqa: BLE001  (recorded per asset, batch continues)
            res["reason"] = f"{type(e).__name__}: {e}"
            self.stats["failed"] += 1
        return res
