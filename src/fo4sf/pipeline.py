"""Batch conversion of Fallout 4 statics read straight from the game's BA2 archives.

    src = Fo4Archives("<FO4 Data dir>")
    conv = Converter(src, staging, texconv, content_resources_zip, collision_template_nif_bytes)
    result = conv.convert_nif("meshes/setdressing/patiofurniture/chairpatio01.nif")

Each shape uses its own material; materials/textures are converted once and cached. Anything that cannot be converted falls
back to a placeholder material (tier T1) instead of failing the asset. Needs numpy and texconv.
"""
import hashlib
import os
import re
import struct
import tempfile
from typing import Dict, List, Optional

from . import ba2 as ba2mod
from . import convert_material as cm
from . import convert_static, door_rig, load_door_anim, nif, sfcollision, sfmesh, sfnif, textures

DOOR_RE = re.compile(r"[\\/]doors?[\\/]|door[^\\/]*\.nif$", re.I)
NOT_HINGED_RE = re.compile(r"vault|elevator|garage|gate|hatch|slid", re.I)   # sliding / lifting doors animate differently:
# never on the hinge template; with door_anim_dll they get their own rig and FO4's keys (docs/spikes/sliding-doors.md)
# FO4 load doors never swing open into the next space: activating one teleports. A rigged swing opened onto the void behind
# the wall (Parsons: walked through the entrance door, fell to z -72), so they stay shut and solid with their native
# collision. The plugin writer (dotnet/PluginSpike) makes them DOOR records and writes the teleport link on both references
# when both ends are placed in the same build; the per-asset "load_door" entry carries the model bounds for that record.
# Animated FO4 objects that open like a door but name their clips otherwise (model basename -> {FO4 sequence: door clip}):
# the Vault 111 cog door VltGearDoor01, an Activator whose quest plays Stage2 (43.3 s: the cog rolls back and aside, the
# catwalk slides out; docs/spikes/B4-mission-anatomy.md "cog door": GO as a door rig). It gets its own rig with Stage2 as
# Open and Stage2 backwards as Close; the plugin writer makes it a DOOR as any rigged model. Its skinned shapes ride the rig
# when every vertex follows one bone (convert_static.rigid_skinned_parts); a triangle across hinged bones rides the bone with the
# smaller error within SEAM_LIMIT_M (the catwalk's WalkWay01:7, FAL-489); the rest are left out (listed in the manifest as
# dropped_skinned_shapes). If the rig fails it stays the solid static it was, never passable.
OWN_RIG_ALIASES = {"vltgeardoor01.nif": {"Stage2": "Open"}}
LOAD_DOOR_RE = re.compile(r"door[^\\/]*load[^\\/]*\.nif$|load[^\\/]*door[^\\/]*\.nif$", re.I)
# BSLightingShaderProperty flags1 bit 15 (nif.xml Fallout4ShaderPropertyFlags1 "Refraction"): heat shimmer over fires and
# machines, water streams in sinks and fountains. FO4 draws such a shape as a screen-space distortion; its texture set holds
# only the distortion normal map (Effects\SmokeVapor01Tile_n.dds in slot 0 and 1), so converted as a surface it showed that
# BC5 normal map as colour: red/green stripes on Vault 111's gear door. In the 2026-10-11 build these were 9 of 11030
# lighting shapes, all texture-set shapes; no FO4 .bgsm sets its own refraction byte.
SLSF1_REFRACTION = 0x8000
# nif.xml Fallout4ShaderPropertyFlags1 bit 4: GreyscaleToPalette_Color. The lighting shader
# samples BSShaderTextureSet slot 3 (or the BGSM greyscale string when byte 62 is set) as a colour
# ramp, using the diffuse green channel as U and GrayscaleToPaletteScale as V. Starfield has no
# matching shader, so the converter bakes the lookup into the colour map. Slot 3 is also height,
# so texture-set shapes only bake when this flag is set.
SLSF1_GREYSCALE_TO_PALETTE_COLOR = 0x10
# nif.xml FO4 BSLightingShaderProperty: after the texture-set ref come emissive/root/clamp/alpha/
# refraction/smoothness/spec, then Subsurface Rolloff, Rimlight Power, optional Backlight Power
# when rim is FLT_MAX, then Grayscale to Palette Scale.
_FO4_RIM_FLT_MAX = 3.402823e38


# nif.xml Fallout4ShaderPropertyFlags2 bit 5: Vertex_Colors. FO4 multiplies the texture alpha by the vertex alpha.
SLSF2_VERTEX_COLORS = 0x20


def vertex_alpha_scale(blk: bytes, shape) -> Optional[float]:
    """Peak vertex alpha of a lighting-shader shape as an opacity factor (0..1, in steps of 16/255), or None when the
    shape has no vertex colours or reaches full alpha; 0.0 when every vertex alpha is 0. Debris-pile floor decals (DebrisPileLargeConc01-06 Decals:10)
    peak at vertex alpha 48, so FO4 draws them as a faint overlay; the Starfield decal gets that as a fixed factor
    (the per-vertex fade at the rims is not reproduced)."""
    colors = getattr(shape, "colors", None)
    if not colors or len(blk) < 12:
        return None
    n_extra, = struct.unpack_from("<I", blk, 8)
    if len(blk) < 12 + 4 * n_extra + 12:
        return None
    flags2, = struct.unpack_from("<I", blk, 12 + 4 * n_extra + 8)
    if not flags2 & SLSF2_VERTEX_COLORS:
        return None
    peak = max(c[3] for c in colors)
    if peak >= 255:
        return None
    if peak == 0:
        return 0.0                                     # never visible in FO4: the caller skips the shape
    return max(16, min(240, (peak + 15) // 16 * 16)) / 255.0


def lighting_palette_scale(blk: bytes) -> float:
    """FO4 lighting-shader Grayscale to Palette Scale, or 1.0 when the tail is absent/unreadable."""
    if len(blk) < 16:
        return 1.0
    n_extra, = struct.unpack_from("<I", blk, 8)
    tail = 12 + 4 * n_extra + 4 + 8 + 16 + 4
    rim_off = tail + 56
    if len(blk) < rim_off + 8:
        return 1.0
    rim, = struct.unpack_from("<f", blk, rim_off)
    scale_off = rim_off + 4
    if _FO4_RIM_FLT_MAX <= rim < float("inf"):
        scale_off += 4
        if len(blk) < scale_off + 4:
            return 1.0
    scale, = struct.unpack_from("<f", blk, scale_off)
    if 0.0 <= scale <= 1.0:
        return scale
    return 1.0


def _palette_scale_ident(scale: float) -> str:
    """Lossless cache token for the clamped FO4 palette scale (IEEE float32 bits).

    `.5f` aliases distinct float32 values around 0.5 that select different palette rows.
    """
    s = max(0.0, min(1.0, float(scale)))
    return struct.pack(">f", s).hex()


class Fo4Archives:
    def __init__(self, data_dir: str, extra_dirs=()):
        """Fallout4 - *.ba2 from data_dir, then (extra_dirs, e.g. a DLC's own Data folder) every DLC*.ba2 there. Lookups
        try the base game's archives first, so a model the base game holds converts byte-identically with or without
        the DLC archives (a DLC replacing a base-game file is not followed; supported: none seen in DLCRobot or
        DLCworkshop01's own cells)."""
        self.meshes, self.materials, self.textures = [], [], []
        self._add(data_dir, lambda low: low.startswith("fallout4 - "))
        for d in extra_dirs:
            self._add(d, lambda low: low.startswith("dlc"))

    def _add(self, data_dir, wanted):
        for fn in sorted(os.listdir(data_dir)):
            low = fn.lower()
            if not (low.endswith(".ba2") and wanted(low)):
                continue
            if "meshes" in low or low.endswith(" - main.ba2"):
                self.meshes.append(ba2mod.Ba2(os.path.join(data_dir, fn)))
                if low.endswith(" - main.ba2"):       # DLC "Main" archives hold meshes and materials together
                    self.materials.append(self.meshes[-1])
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


def write_staged(path: str, data: bytes):
    """Write a staging file as a new file that replaces the old one, never in place. A staged core hard-links its Data
    tree to the conversion work folder, so an in-place write (open "wb", shutil.copy2) changes every staged build that
    shares the file (found 2026-10-21: a --resume rewrote meshes inside the v6c and v6e rollback stagings)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".fo4port-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


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
    door_anim_dll: Optional[str] = None
    # rig_load_doors: FO4 load doors whose NIF animates ("Open" sequence) are rigged like the other doors, and the rig goes
    # into their "load_door" entry as "anim" (the plugin writer then gives the load DOOR an animation graph, so the door
    # swings open before the trip; docs/spikes/load-door-animations.md). Off by default: load doors stay the graph-less
    # static doors every pinned build has. Class default so Converter.__new__ tests see it too.
    rig_load_doors: bool = False
    mass_scale: float = 1.0  # class default so Converter.__new__ tests still pass mass_scale into convert_static

    def __init__(self, src: Fo4Archives, staging: str, texconv_exe: str, content_resources: str,
                 collision_template: Optional[bytes] = None, prefix: str = "fo4port",
                 no_collision_pattern: str = r"^meshes[\\/](architecture|interiors|scol)[\\/]", rig_doors: bool = False,
                 door_physics_donor: Optional[bytes] = None, sf_mesh_template: Optional[bytes] = None,
                 dynamic_template: Optional[bytes] = None, max_texture=None, door_anim_dll: Optional[str] = None,
                 spec_mask_roughness: bool = False, mass_scale: float = 1.0, load_door_models=(), static_body_models=(),
                 no_rig_models=(), rig_load_doors: bool = False):
        self.src, self.staging, self.texconv = src, staging, texconv_exe
        self.rig_load_doors = rig_load_doors
        # load_door_models: mesh names FO4 places as a teleporting Door (a Door reference with an XTEL in the cell export,
        # convert_batch.teleport_models), load doors whatever their name: RoofHatch01 and MetalTrapdoorLadder01 match no
        # LOAD_DOOR_RE and stayed STATs nobody could activate (Museum of Witchcraft roof hatch, owner 2026-10-18)
        self.load_door_models = {n.replace("/", "\\").lower() for n in load_door_models}
        # static_body_models: mesh names that keep a static body even with dynamic_template (the outdoor core places
        # them as STAT only, never as a pickable item: cars, skeletons, cones; convert_batch.static_body_models)
        self.static_body_models = {n.replace("/", "\\").lower() for n in static_body_models}
        # no_rig_models: doors that skip their own rig as if door_anim_dll were missing (crash bisects; --no-rig-pattern)
        self.no_rig_models = {n.replace("/", "\\").lower() for n in no_rig_models}
        # spec_mask_roughness: roughness also follows FO4's specular mask (smooth-spec R), not only its gloss (G); off by
        # default so existing builds and checkpoints keep their textures (owner's Vault 111 floor report, 2026-10-17)
        self.spec_mask_roughness = spec_mask_roughness
        # door_anim_dll: the external CALUMI.Animation library (not distributed). With it, rigged doors that move more
        # than one part (frozen_door_parts) get their own rig and Open/Close clips instead of the single-hinge template,
        # and sliding / lifting / trapdoor families (NOT_HINGED_RE) get one instead of staying passable.
        self.door_anim_dll = door_anim_dll
        # dynamic_template (a vanilla dynamic convex body, meshcollision.DYNAMIC_TEMPLATE_NIF): FO4 loose items with one
        # dynamic body become movable; their result carries "movable" (plugin writer: MoveableStatic, not Static)
        self.dynamic_template = dynamic_template
        self.mass_scale = convert_static.require_mass_scale(mass_scale)
        # max_texture: optional size cap per texture kind (textures.parse_texture_caps: '1024' or 'color=1024,...'); the
        # converted DDS loses its top mip levels until it fits (textures.cap_dds). Off by default: FO4Port keeps full
        # resolution. When set, texture_log records every texture's full and written size.
        self.texture_caps = textures.parse_texture_caps(max_texture)
        self.texture_log: Dict[str, dict] = {}
        # rig_doors: hinged doors become DOOR NIFs that open (needs door_physics_donor: without a keyframed leaf body the leaf
        # is pinned and blocks the doorway). Off by default because the donor comes from the Starfield install.
        self.rig_doors = rig_doors
        self.door_physics_donor = door_physics_donor
        # vanilla Starfield mesh-collision blob: FO4's own collision meshes are transplanted (meshcollision.transplant)
        self.sf_mesh_template = sf_mesh_template   # body of a vanilla door leaf (sfcollision.physics_blob_from_nif)
        self.template_mat = cm.read_template(content_resources)
        self.collision_template = collision_template
        self.prefix = prefix
        # one AABB box is wrong for architecture (a corridor piece would become a solid block), so skip it there for now
        self.no_collision = re.compile(no_collision_pattern, re.I) if no_collision_pattern else None
        self._materials: Dict[str, Optional[str]] = {}
        self.stats = {"assets": 0, "failed": 0, "materials_ok": 0, "materials_fallback": 0}
        self.material_errors: Dict[str, str] = {}
        self._blend_cache: Dict[str, bool] = {}
        self._glass_template = None
        self._decal_template = None
        self._two_sided_template = None
        self.content_resources = content_resources
        self.neutral = self._make_neutral_material()

    def _make_neutral_material(self) -> str:
        """Plain mid-grey, flat, fairly rough material used when a shape's own material cannot be converted
        (instead of the vanilla template's marble look)."""
        import numpy as np
        stem = "_neutral"
        tex_rel = f"textures/{self.prefix}/{stem}"
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            grey = np.full((16, 16), 128, np.uint8)
            rgba = np.stack([grey, grey, grey, np.full((16, 16), 255, np.uint8)], axis=-1)
            textures.write_dds_dx10(os.path.join(tmp, "c_in.dds"), 16, 16, textures.DXGI_R8G8B8A8_UNORM, rgba.tobytes(), 4)
            textures.texconv(self.texconv, os.path.join(tmp, "c_in.dds"), tmp, "BC1_UNORM_SRGB")
            textures.write_rg8_snorm(os.path.join(tmp, "n_in.dds"), np.full((16, 16), 128, np.uint8), np.full((16, 16), 128, np.uint8))
            textures.texconv(self.texconv, os.path.join(tmp, "n_in.dds"), tmp, "BC5_SNORM")
            textures.write_r8(os.path.join(tmp, "r_in.dds"), np.full((16, 16), 190, np.uint8))
            textures.texconv(self.texconv, os.path.join(tmp, "r_in.dds"), tmp, "BC4_UNORM")
            for kind, fn in (("color", "c_in.dds"), ("normal", "n_in.dds"), ("rough", "r_in.dds")):
                dst = os.path.join(self.staging, *f"{tex_rel}_{kind}.dds".split("/"))
                with open(os.path.join(tmp, fn), "rb") as f:
                    write_staged(dst, f.read())
                out[kind] = cm.game_path(f"{tex_rel}_{kind}.dds")
        mat = cm.build_mat(self.template_mat, "FO4Port_Neutral", out["color"], out["normal"], out["rough"])
        mat_rel = f"materials/{self.prefix}/{stem}.mat"
        p = os.path.join(self.staging, *mat_rel.split("/"))
        write_staged(p, cm.dump_mat(mat).encode("utf-8"))
        return mat_rel.replace("/", "\\")

    def _publish_texture(self, src_path: str, dst: str, kind: str):
        """Copy a converted texture into the staging folder; with a cap for its kind, without the top mip levels that
        exceed it (the full size is logged either way while caps are on)."""
        cap = self.texture_caps.get(kind, 0)
        with open(src_path, "rb") as f:
            data = f.read()
        if not self.texture_caps:
            write_staged(dst, data)
            return
        out, info = textures.cap_dds(data, cap)
        write_staged(dst, out)
        rel = os.path.relpath(dst, self.staging).replace("\\", "/").lower()
        self.texture_log[rel] = {"kind": kind, "cap": cap, **info}

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
        if not (b.diffuse and b.normal):
            raise ValueError("material lacks diffuse/normal textures")
        rel = re.sub(r"^materials[\\/]", "", bgsm_path.replace("\\", "/"), flags=re.I)
        gs = b.greyscale if b.palette_color and b.greyscale else None
        return self._convert_texture_set(os.path.splitext(rel)[0].lower(), b.diffuse, b.normal, b.smooth_spec,
                                         smoothness=b.smoothness, spec_mult=b.spec_mult,
                                         alpha_test=b.alpha_test, alpha_ref=b.alpha_ref,
                                         greyscale=gs, palette_scale=b.palette_scale, two_sided=b.two_sided)

    def decal_material(self, bgsm_path: str, opacity_scale: float = 1.0) -> Optional[str]:
        """Alpha-blended FO4 material -> Starfield decal material (or None: the shape is skipped, as before decals).
        opacity_scale < 1: the shape's peak vertex alpha (see vertex_alpha_scale); the opacity map is multiplied by it
        and the material gets its own name under vadecals/aNN/, a folder no FO4 material path maps to, so it never
        shares files with the unscaled decal of this or any other .bgsm."""
        m = re.search(r"materials[\\/].*", bgsm_path, re.I)
        bgsm_path = m.group(0) if m else bgsm_path
        scaled = opacity_scale < 1.0
        key = "decal:" + bgsm_path.replace("/", "\\").lower() + (f"|a{round(opacity_scale * 255)}" if scaled else "")
        if key not in self._materials:
            try:
                raw = self.src.material(bgsm_path)
                if raw is None:
                    raise FileNotFoundError("bgsm not in archives")
                b = cm.parse_bgsm(raw)
                if not (b.diffuse and b.normal):
                    raise ValueError("material lacks diffuse/normal textures")
                rel = re.sub(r"^materials[\\/]", "", bgsm_path.replace("\\", "/"), flags=re.I)
                stem = (f"vadecals/a{round(opacity_scale * 255)}/" if scaled else "decals/") + os.path.splitext(rel)[0].lower()
                extra = {"opacity_scale": opacity_scale} if scaled else {}
                self._materials[key] = self._convert_texture_set(stem, b.diffuse, b.normal, b.smooth_spec,
                                                                 smoothness=b.smoothness, spec_mult=b.spec_mult,
                                                                 decal=True, **extra)
                self.stats["materials_ok"] += 1
            except Exception as e:                        # noqa: BLE001
                self._materials[key] = None
                self.stats["materials_fallback"] += 1
                self.material_errors[key] = f"{type(e).__name__}: {e}"
        return self._materials[key]

    def effect_decal_material(self, base: str, normal: str) -> Optional[str]:
        """FO4 effect-shader grime (wall stains, oil puddles: alpha-blended overlays drawn with BSEffectShaderProperty) ->
        Starfield decal material from the effect's base texture (its alpha is the opacity). None if it cannot convert."""
        ident = "|".join(x.replace("\\", "/").lower() for x in (base, normal))
        stem = ("fxdecals/" + os.path.splitext(re.sub(r"^textures[\\/]", "", base.replace("\\", "/"), flags=re.I))[0].lower()
                + "_" + hashlib.sha1(ident.encode()).hexdigest()[:8])
        key = "fxdecal:" + stem
        if key not in self._materials:
            try:
                self._materials[key] = self._convert_texture_set(stem, base, normal, "", decal=True)
                self.stats["materials_ok"] += 1
            except Exception as e:                        # noqa: BLE001
                self._materials[key] = None
                self.stats["materials_fallback"] += 1
                self.material_errors[key] = f"{type(e).__name__}: {e}"
        return self._materials[key]

    def texture_set_material(self, diffuse: str, normal: str, spec: str, greyscale: str = None,
                             palette_scale: float = 1.0) -> Optional[str]:
        """Material for a shape that names its textures directly (BSShaderTextureSet, no .bgsm). Cached by inputs."""
        stem = "texsets/" + re.sub(r"^textures[\\/]", "", diffuse.replace("\\", "/"), flags=re.I).lower()
        parts = [diffuse, normal, spec]
        if greyscale:
            parts.append(greyscale)
            parts.append(_palette_scale_ident(palette_scale))
        ident = "|".join(x.replace("\\", "/").lower() for x in parts)      # every input is part of identity
        stem = os.path.splitext(stem)[0] + "_" + hashlib.sha1(ident.encode()).hexdigest()[:8]
        key = "texset:" + stem
        if key not in self._materials:
            try:
                extra = {"greyscale": greyscale, "palette_scale": palette_scale} if greyscale else {}
                self._materials[key] = self._convert_texture_set(stem, diffuse, normal, spec, **extra)
                self.stats["materials_ok"] += 1
            except Exception as e:                        # noqa: BLE001
                self._materials[key] = None
                self.stats["materials_fallback"] += 1
                self.material_errors[key] = f"{type(e).__name__}: {e}"
        return self._materials[key]

    def _convert_texture_set(self, stem: str, diffuse: str, normal: str, spec: str,
                             smoothness: float = 1.0, spec_mult: float = 1.0,
                             alpha_test: bool = False, alpha_ref: int = 128, decal: bool = False,
                             greyscale: str = None, palette_scale: float = 1.0,
                             two_sided: bool = False, opacity_scale: float = 1.0) -> str:
        """FO4 diffuse / normal / smooth-spec textures -> Starfield colour / normal / rough DDS + a .mat. Spec is optional.
        decal: alpha-blended overlay; the diffuse alpha always becomes the opacity map and the .mat is cloned from the
        vanilla decal template (cm.DECAL_TEMPLATE_MAT) so it blends over the surface behind it.
        greyscale: FO4 palette texture, only when the BGSM/NIF palette flag is on. The colour map is the palette
        lookup (green of the diffuse as U, GrayscaleToPaletteScale as V) baked before BC1; a named but missing
        palette is an error, not a plain grey material.
        alpha_test with a real opacity map: clone ConduitKit01TwoSided (shader TwoSided1Layer) instead of
        the opaque metal template, which ignored the cutout and drew leaf cards as black slabs.
        two_sided is accepted for DryConverter's signature; opacity still requires alpha_test or decal
        (FO4 two-sided materials without alpha test are not cutouts).
        opacity_scale: multiplies the opacity map (decals only; a shape's peak vertex alpha, see vertex_alpha_scale)."""
        import numpy as np
        d, n = self.src.texture(diffuse), (self.src.texture(normal) if normal else None)
        s = self.src.texture(spec) if spec else None
        g = self.src.texture(greyscale) if greyscale else None
        if d is None or (n is None and not decal):         # decals (effect grime) may have no normal map: flat normal
            raise FileNotFoundError("diffuse or normal texture missing from archives")
        if greyscale and g is None:
            raise FileNotFoundError(f"palette texture missing from archives: {greyscale}")
        tex_rel = f"textures/{self.prefix}/{stem}"
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "d.dds"), "wb").write(d)
            if g is not None:
                open(os.path.join(tmp, "g.dds"), "wb").write(g)
                textures.texconv(self.texconv, os.path.join(tmp, "d.dds"), tmp, "R8G8B8A8_UNORM", ("-m", "1"))
                textures.texconv(self.texconv, os.path.join(tmp, "g.dds"), tmp, "R8G8B8A8_UNORM", ("-m", "1"))
                raw_d = open(os.path.join(tmp, "d.dds"), "rb").read()
                raw_g = open(os.path.join(tmp, "g.dds"), "rb").read()
                hd = textures.read_dds_header(raw_d)
                hg = textures.read_dds_header(raw_g)
                idx = np.frombuffer(raw_d[hd["data_offset"]:hd["data_offset"] + hd["width"] * hd["height"] * 4], np.uint8)
                idx = idx.reshape(hd["height"], hd["width"], 4).copy()
                pal = np.frombuffer(raw_g[hg["data_offset"]:hg["data_offset"] + hg["width"] * hg["height"] * 4], np.uint8)
                pal = pal.reshape(hg["height"], hg["width"], 4)
                rgb = textures.apply_greyscale_palette(idx, pal, scale=palette_scale)
                rgba = np.dstack([rgb, idx[:, :, 3]])
                textures.write_dds_dx10(os.path.join(tmp, "d.dds"), hd["width"], hd["height"],
                                        textures.DXGI_R8G8B8A8_UNORM, np.ascontiguousarray(rgba).tobytes(), 4)
            opacity = None
            if alpha_test or decal:                        # FO4 alpha is opacity only when alpha-tested or a decal
                open(os.path.join(tmp, "a.dds"), "wb").write(d)
                textures.texconv(self.texconv, os.path.join(tmp, "a.dds"), tmp, "R8G8B8A8_UNORM", ("-m", "1"))
                raw_a = open(os.path.join(tmp, "a.dds"), "rb").read()
                ha = textures.read_dds_header(raw_a)
                px = np.frombuffer(raw_a[ha["data_offset"]:ha["data_offset"] + ha["width"] * ha["height"] * 4], np.uint8)
                alpha = px.reshape(ha["height"], ha["width"], 4)[:, :, 3].copy()
                if decal or alpha.min() < 250:            # only if the texture really has a cutout
                    if opacity_scale < 1.0:
                        alpha = np.round(alpha * opacity_scale).astype(np.uint8)
                    textures.write_r8(os.path.join(tmp, "o_in.dds"), alpha)
                    textures.texconv(self.texconv, os.path.join(tmp, "o_in.dds"), tmp, "BC4_UNORM")
                    opacity = "o_in.dds"
            textures.texconv(self.texconv, os.path.join(tmp, "d.dds"), tmp, "BC1_UNORM_SRGB", ("-srgbi",))
            if n is not None:
                nr, ng = _plane_pair(n, tmp, self.texconv)
            else:                                          # flat: unorm 128 maps to signed 0
                nr = np.full((4, 4), 128, dtype=np.uint8)
                ng = np.full((4, 4), 128, dtype=np.uint8)
            textures.write_rg8_snorm(os.path.join(tmp, "n_in.dds"), nr, ng)
            textures.texconv(self.texconv, os.path.join(tmp, "n_in.dds"), tmp, "BC5_SNORM")
            if s is not None:
                sr, sg = _plane_pair(s, tmp, self.texconv)
                rough = textures.roughness_from_smoothness(sg, smoothness, spec_mult,
                                                           mask=sr if self.spec_mask_roughness else None)
            else:                                          # no spec map: uniformly fairly rough
                rough = np.full((max(4, nr.shape[0] // 4), max(4, nr.shape[1] // 4)), 190, dtype=np.uint8)
            textures.write_r8(os.path.join(tmp, "r_in.dds"), rough)
            textures.texconv(self.texconv, os.path.join(tmp, "r_in.dds"), tmp, "BC4_UNORM")
            kinds = [("color", "d.dds"), ("normal", "n_in.dds"), ("rough", "r_in.dds")] + ([("opacity", opacity)] if opacity else [])
            for kind, fn in kinds:
                dst = os.path.join(self.staging, *f"{tex_rel}_{kind}.dds".split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                self._publish_texture(os.path.join(tmp, fn), dst, kind)
                out[kind] = cm.game_path(f"{tex_rel}_{kind}.dds")
        if decal:
            if self._decal_template is None:
                self._decal_template = cm.read_template_path(self.content_resources, cm.DECAL_TEMPLATE_MAT)
            mat = cm.build_from_template(self._decal_template, "FO4Port_" + re.sub(r"[^a-z0-9]+", "_", stem),
                                         {"Albedo": out["color"], "Normal": out["normal"], "Roughness": out["rough"],
                                          "Opacity": out["opacity"]})
        elif out.get("opacity"):
            # leaf cards / vines / fences: TwoSided1Layer honours slot-2 opacity; MetalIronCast01 did not
            if self._two_sided_template is None:
                self._two_sided_template = cm.read_template_path(self.content_resources, cm.TWO_SIDED_TEMPLATE_MAT)
            mat = cm.build_from_template(self._two_sided_template, "FO4Port_" + re.sub(r"[^a-z0-9]+", "_", stem),
                                         {"Albedo": out["color"], "Normal": out["normal"], "Roughness": out["rough"],
                                          "Opacity": out["opacity"]},
                                         alpha_threshold=alpha_ref / 255.0, metalness=0.0)
        else:
            mat = cm.build_mat(self.template_mat, "FO4Port_" + re.sub(r"[^a-z0-9]+", "_", stem), out["color"], out["normal"],
                               out["rough"], opacity=out.get("opacity"), alpha_threshold=alpha_ref / 255.0)
        mat_rel = f"materials/{self.prefix}/{stem}.mat"
        p = os.path.join(self.staging, *mat_rel.split("/"))
        write_staged(p, cm.dump_mat(mat).encode("utf-8"))
        return mat_rel.replace("/", "\\")

    def glass_material(self, base: str, normal: str) -> Optional[str]:
        key = "glass:" + "|".join(x.replace("/", "\\").lower() for x in (base, normal))
        if key not in self._materials:
            try:
                self._materials[key] = self._convert_glass(base, normal)
                self.stats["materials_ok"] += 1
            except Exception as e:                        # noqa: BLE001
                self._materials[key] = None
                self.stats["materials_fallback"] += 1
                self.material_errors[key] = f"{type(e).__name__}: {e}"
        return self._materials[key]

    def _convert_glass(self, base: str, normal: str) -> str:
        import numpy as np
        d = self.src.texture(base) if base else None
        n = self.src.texture(normal) if normal else None
        if d is None:
            raise FileNotFoundError("glass base texture missing")
        rel = re.sub(r"^textures[\\/]", "", base.replace("\\", "/"), flags=re.I)
        stem = ("glass/" + os.path.splitext(rel)[0].lower() + "_"
                + hashlib.sha1((base + "|" + normal).lower().encode()).hexdigest()[:8])
        tex_rel = f"textures/{self.prefix}/{stem}"
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            if d is not None:
                open(os.path.join(tmp, "d.dds"), "wb").write(d)
                textures.texconv(self.texconv, os.path.join(tmp, "d.dds"), tmp, "BC1_UNORM_SRGB", ("-srgbi",))
                out["Albedo"] = "d.dds"
            if n is not None:
                nr, ng = _plane_pair(n, tmp, self.texconv)
                textures.write_rg8_snorm(os.path.join(tmp, "n_in.dds"), nr, ng)
                textures.texconv(self.texconv, os.path.join(tmp, "n_in.dds"), tmp, "BC5_SNORM")
                out["Normal"] = "n_in.dds"
            textures.write_r8(os.path.join(tmp, "r_in.dds"), np.full((16, 16), 25, np.uint8))   # glass: very smooth
            textures.texconv(self.texconv, os.path.join(tmp, "r_in.dds"), tmp, "BC4_UNORM")
            out["Roughness"] = "r_in.dds"
            files = {}
            for slot, fn in out.items():
                kind = {"Albedo": "color", "Normal": "normal", "Roughness": "rough"}[slot]
                dst = os.path.join(self.staging, *f"{tex_rel}_{kind}.dds".split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                self._publish_texture(os.path.join(tmp, fn), dst, kind)
                files[slot] = cm.game_path(f"{tex_rel}_{kind}.dds")
        if self._glass_template is None:
            self._glass_template = cm.read_template_path(self.content_resources, cm.GLASS_TEMPLATE_MAT)
        mat = cm.build_from_template(self._glass_template, "FO4Port_" + re.sub(r"[^a-z0-9]+", "_", stem), files,
                                     opacity_value=0.15)
        mat_rel = f"materials/{self.prefix}/{stem}.mat"
        p = os.path.join(self.staging, *mat_rel.split("/"))
        write_staged(p, cm.dump_mat(mat).encode("utf-8"))
        return mat_rel.replace("/", "\\")

    def _is_blended(self, bgsm_path: str) -> bool:
        m = re.search(r"materials[\\/].*", bgsm_path, re.I)
        key = (m.group(0) if m else bgsm_path).replace("/", "\\").lower()
        if key not in self._blend_cache:
            raw = self.src.material(key)
            try:
                b = cm.parse_bgsm(raw) if raw else None
                # blended, or a decal that is alpha-tested: FO4 draws both as overlays in its decal pass. Drawn opaque,
                # BldFloorConcDebris02Alpha (decal, alpha test ref 6, texture alpha never below 28) showed its
                # transparent texels, which are black, as hard black patches (research log 2026-10-18)
                self._blend_cache[key] = bool(b) and (b.alpha_blend or (b.decal and b.alpha_test))
            except Exception:                         # noqa: BLE001
                self._blend_cache[key] = False
        return self._blend_cache[key]

    # -- meshes -------------------------------------------------------------------------------
    def _shape_material(self, src, s) -> Optional[str]:
        """Starfield material path for one FO4 shape; None = skip the shape (effect shaders: glass, glow, frost)."""
        if s.shader_ref < 0:
            return self.neutral
        kind = src.type_of(s.shader_ref)
        if kind == "BSEffectShaderProperty":
            idx, = struct.unpack_from("<i", src.blocks[s.shader_ref], 4)
            name = src.strings[idx].decode("latin-1") if 0 <= idx < len(src.strings) else ""
            if name.lower().endswith(".bgem"):
                raw = self.src.material(name) or b""
                try:
                    base, normal = cm.parse_bgem_textures(raw)
                except ValueError:
                    base, normal = "", ""
                cubemap = b"cubemap" in raw.lower()
            else:                                       # textures stored inline in the effect block
                dds = [x.decode("latin-1") for x in re.findall(rb"[\w\\/ .-]+\.dds", src.blocks[s.shader_ref])]
                base = dds[0] if dds else ""
                normal = next((x for x in dds if x.lower().endswith("_n.dds")), "")
                cubemap = any("cubemap" in x.lower() for x in dds)
            # glass: named glass/window, or an environment-mapped effect with its own normal map (beakers, test tubes,
            # bottles: FO4's usual glass setup); never textures from the effects folder (glow, smoke, dust)
            glassy = re.search(r"glass|window", base, re.I) or (cubemap and normal)
            if glassy and not re.search(r"[\\/]effects[\\/]", base, re.I):
                return self.glass_material(base, normal)   # windows, cryo-pod glass: vanilla glass shader model
            if base and re.search(r"stain|streak|grime|leak|blood|decal", base, re.I) \
                    and not re.search(r"[\\/]effects[\\/]", base, re.I):
                return self.effect_decal_material(base, normal)   # alpha-blended grime: decal; None = skip as before
            return None                                 # other effects (glow, frost, dust, smoke, signs): skipped
        if kind != "BSLightingShaderProperty":
            return self.neutral
        blk = src.blocks[s.shader_ref]
        idx, = struct.unpack_from("<i", blk, 4)
        name = src.strings[idx] if 0 <= idx < len(src.strings) else b""
        if name.lower().endswith(b".bgsm"):
            if self._is_blended(name.decode("latin-1")):
                scale = vertex_alpha_scale(blk, s)
                if scale == 0.0:
                    return None                            # every vertex fully transparent: FO4 never shows it
                if scale is not None:                      # faded by vertex alpha (debris-pile floor decals)
                    return self.decal_material(name.decode("latin-1"), opacity_scale=scale)
                return self.decal_material(name.decode("latin-1"))   # overlay shells (cracks, grime): decal; None = skip
            return self.material(name.decode("latin-1")) or self.neutral
        # no material file: shader type, name, extra data list, controller, flags1, flags2, UV offset, UV scale, texture set
        n_extra, = struct.unpack_from("<I", blk, 8)
        flags1, = struct.unpack_from("<I", blk, 12 + 4 * n_extra + 4)
        if flags1 & SLSF1_REFRACTION:
            return None                                 # distortion only (see SLSF1_REFRACTION): skipped like effect shapes
        ts_ref, = struct.unpack_from("<i", blk, 12 + 4 * n_extra + 4 + 8 + 16)
        if not (0 <= ts_ref < len(src.blocks)) or src.type_of(ts_ref) != "BSShaderTextureSet":
            return self.neutral
        tb = src.blocks[ts_ref]
        count, = struct.unpack_from("<I", tb, 0)
        paths, p = [], 4
        for _ in range(count):
            ln, = struct.unpack_from("<I", tb, p)
            paths.append(tb[p + 4:p + 4 + ln].decode("latin-1"))
            p += 4 + ln
        diffuse = paths[0] if paths else ""
        normal = paths[1] if len(paths) > 1 else ""
        spec = paths[7] if len(paths) > 7 else ""
        if not (diffuse and normal):
            return self.neutral
        if flags1 & SLSF1_GREYSCALE_TO_PALETTE_COLOR and len(paths) > 3 and paths[3]:
            return self.texture_set_material(diffuse, normal, spec, greyscale=paths[3],
                                             palette_scale=lighting_palette_scale(blk)) or self.neutral
        return self.texture_set_material(diffuse, normal, spec) or self.neutral

    def convert_nif(self, nif_name: str, pose: Optional[dict] = None, out_suffix: str = "") -> dict:
        """pose / out_suffix: a model for one placed reference (placed_pose): the NIF's bone nodes take these local
        transforms (its XRGD ragdoll pose) and the model is written as <usual name><out_suffix>. Posed models are never
        doors (placed_pose leaves door items out)."""
        res = {"nif": nif_name, "ok": False}
        try:
            raw = self.src.mesh(nif_name)
            src = nif.parse(raw)
            # skinned props (lockers, cabinets, desks, skeletons) are converted in the NIF's node pose
            # (convert_static.pose_skinned_shapes), or in a placed reference's ragdoll pose when `pose` is given
            shapes = [s for s in nif.fo4_trishapes(src) if s.positions and s.triangles]
            if not shapes:
                raise ValueError("no static BSTriShape geometry")
            mats: List[Optional[str]] = []
            for s in shapes:
                mats.append(self._shape_material(src, s))
            if all(m is None for m in mats):
                raise ValueError("only effect-shader shapes (glass/glow), skipped")
            rel = re.sub(r"^meshes[\\/]", "", nif_name.replace("\\", "/"), flags=re.I)
            out_name = f"{self.prefix}/{os.path.splitext(rel)[0].lower()}{out_suffix.lower()}"
            arch = bool(self.no_collision and self.no_collision.search(nif_name))
            mode = "surfaces" if arch else "box"        # architecture: thin boxes behind flat surfaces; props: one AABB
            # Vegetation, mounds and door-named models (wall plugs around doorways, vault hall pieces, signs) keep FO4's
            # own collision but never get a guessed box: a box around a tree or a doorway is an invisible wall. (These
            # used to get no collision at all, so walls beside doors and grass mounds could be walked through.)
            no_guess = bool(re.search(r"[\\/]landscape[\\/](trees|plants|grass)|roots|cobweb|vines|hanging"
                                      r"|[\\/]doors?[\\/]|door[^\\/]*\.nif$", nif_name, re.I))
            load_door = bool(LOAD_DOOR_RE.search(nif_name)) or nif_name.replace("/", "\\").lower() in getattr(self, "load_door_models", ())
            if load_door:
                # bounds (metres, NIF space) for the DOOR record's OBND, like the hinged doors' "door.bounds"
                pts = [sfmesh.decode_position(p, m.scale) for m in (convert_static.shape_to_mesh(s) for s in shapes)
                       for p in m.positions]
                res["load_door"] = {"note": "static door: teleport written by the plugin writer when both ends are in the build",
                                    "bounds": [[round(min(p[a] for p in pts), 4) for a in range(3)],
                                               [round(max(p[a] for p in pts), 4) for a in range(3)]]}
            # A door leaf that animates in FO4 ("Open" sequence) but is not rigged here (sliding / vault / elevator doors,
            # or rigging failed) cannot open: keep it passable rather than a closed wall, and say so.
            seq_names = [struct.unpack_from("<i", src.blocks[i], 0)[0] for i in range(len(src.blocks))
                         if src.type_of(i) == "NiControllerSequence"]
            animated = any(0 <= s < len(src.strings) and src.strings[s] == b"Open" for s in seq_names)
            aliases = OWN_RIG_ALIASES.get(re.split(r"[\\/]", nif_name)[-1].lower())
            if aliases and not any(0 <= s < len(src.strings) and src.strings[s].decode("latin-1") in aliases for s in seq_names):
                aliases = None                           # not the model the table means (no such clip)
            anim_dll = None if nif_name.replace("/", "\\").lower() in getattr(self, "no_rig_models", ()) else self.door_anim_dll
            use_box = self.collision_template is not None
            coll_report = {}
            files = None
            # not hinged: by name (vault, elevator, garage, gate, hatch, sliding) or by its Open motion (parts that travel
            # without turning: a sliding door named like any other, RedRPedDoor.nif)
            not_hinged = bool(NOT_HINGED_RE.search(nif_name)) or (animated and pose is None and self.rig_doors
                                                                  and DOOR_RE.search(nif_name) and door_rig.slides(src))
            # a load door is rigged only with rig_load_doors; then its FO4 record, not its file name, makes it a door
            # (RoofHatch01 is placed as a teleporting Door but matches no DOOR_RE)
            rig_load = load_door and self.rig_load_doors
            doorish = bool(DOOR_RE.search(nif_name)) or rig_load
            if rig_load and not not_hinged and animated and pose is None and self.rig_doors and (
                    door_rig.slides(src) or door_rig.flips(src)):
                not_hinged = True               # a trapdoor named like a door (MetalTrapdoor01) must not swing upright
            if pose is None and self.rig_doors and self.door_physics_donor is not None and doorish and not not_hinged and not aliases and (not load_door or rig_load) and nif.door_hinge(src):
                # Parts FO4 moves outside the first animated node (second leaf, shutter, other sliding panels) cannot
                # hang under the template's single hinge: with the CALUMI library such a door gets its own rig and
                # clips (one track and one keyframed body per part, as vanilla double doors); without it the template
                # door is kept and the parts that stay closed are listed (door_frozen_parts), not silently dropped.
                frozen = convert_static.frozen_door_parts(src)
                if frozen and anim_dll:
                    try:
                        from . import native_door
                        files, res["door"] = convert_static.convert_multipart_door(
                            raw, out_name, mats, lambda plan, scale: native_door.export_files(plan, self.door_anim_dll, scale),
                            collision_template=self.collision_template, leaf_physics_donor=self.door_physics_donor)
                    except Exception as e:               # noqa: BLE001  (falls back to the template door)
                        files = None
                        res.pop("door", None)
                        res["door_error"] = f"multi-part: {type(e).__name__}: {e}"
                if files is None:
                    try:                                 # hinged door: rigged like the vanilla template door so it opens
                        files, offset, bounds = convert_static.convert_door(raw, out_name, mats,
                                                                    collision_template=self.collision_template,
                                                                    leaf_physics_donor=self.door_physics_donor)
                        t = sfnif.DOOR_TEMPLATE
                        res["door"] = {"origin_offset": [round(x, 5) for x in offset], "anim_graph": t["anim_graph"],
                                       "bounds": [[round(x, 4) for x in b] for b in bounds],
                                       "skeleton": t["skeleton"], "animations": t["animations"]}
                        if frozen:
                            res["door_frozen_parts"] = frozen
                    except Exception as e:               # noqa: BLE001  (falls back to a static door)
                        res["door_error"] = (res["door_error"] + "; " if "door_error" in res else "") + f"{type(e).__name__}: {e}"
            elif (pose is None and self.rig_doors and self.door_physics_donor is not None and anim_dll
                  and (animated or aliases) and (not load_door or rig_load)
                  and (aliases or (doorish and not_hinged))):
                # Sliding, lifting and trapdoor families (vault doors, elevator doors, hatches) cannot hang under the
                # template's vertical hinge, and no vanilla door moves like them; vanilla sliding doors play the same graph
                # (SimpleOpenClose01.agx) with their own rig and clips (docs/spikes/sliding-doors.md). So such a door gets
                # its own rig and FO4's own keys, as the multi-part doors do. Without the library, or if this fails (also
                # when its clips do not rest at the bind pose: gates keyed open), it stays passable (door_not_opening
                # below) and door_error says why.
                try:
                    from . import native_door
                    files, res["door"] = convert_static.convert_multipart_door(
                        raw, out_name, mats, lambda plan, scale: native_door.export_files(plan, self.door_anim_dll, scale),
                        collision_template=self.collision_template, leaf_physics_donor=self.door_physics_donor,
                        rest_pose_check=True, aliases=aliases, drop_skinned=bool(aliases),
                        seam_limit_m=convert_static.SEAM_LIMIT_M if aliases else None)
                except Exception as e:                   # noqa: BLE001  (falls back to the passable static door)
                    files = None
                    res.pop("door", None)
                    res["door_error"] = f"own rig: {type(e).__name__}: {e}"
            if load_door and "door" in res:
                # rig_load_doors: the rig belongs to the load door (one record: a DOOR that opens, then the trip), not to a
                # separate opening door; the plugin writer reads it from load_door.anim
                res["load_door"]["anim"] = res.pop("door")
                if res["load_door"]["anim"].get("rig") != "native":   # the template rig has a vanilla load variant
                    res["load_door"]["anim"]["xtel_anim_graph"] = load_door_anim.TEMPLATE_XTEL_GRAPH
                try:                                     # how long the FO4 door takes to open, and its sound keys
                    timing = load_door_anim.open_timing(src)
                except nif.NifError:
                    timing = None
                if timing:
                    # the template rig plays Starfield's own Open clip, not FO4's: the script must wait that clip's length
                    # (a shorter FO4 wait ends before the door is open, so the close behind the player is skipped)
                    native_rig = res["load_door"]["anim"].get("rig") == "native"
                    res["load_door"]["anim"]["open_seconds"] = (timing["seconds"] if native_rig
                                                                else load_door_anim.TEMPLATE_OPEN_SECONDS)
                    if not native_rig:
                        res["load_door"]["anim"]["fo4_open_seconds"] = timing["seconds"]
                    if timing["events"]:
                        res["load_door"]["anim"]["fo4_open_events"] = timing["events"]
            if files is None:
                if animated and not aliases and not load_door and DOOR_RE.search(nif_name):
                    use_box = False
                    res["door_not_opening"] = "open animation not ported: passable"
                files = convert_static.convert_static(raw, out_name, material_paths=mats, collision_mode=mode,
                                                      include_skinned=True, report=coll_report,
                                                      sf_mesh_template=self.sf_mesh_template if use_box else None,
                                                      collision_template=self.collision_template if use_box else None,
                                                      allow_guess=not no_guess,
                                                      dynamic_template=self.dynamic_template if use_box and nif_name.replace(
                                                          "/", "\\").lower() not in getattr(self, "static_body_models", ()) else None,
                                                      pose=pose, mass_scale=self.mass_scale)
                if coll_report.get("motion") == "dynamic":
                    res["movable"] = {"mass_kg": coll_report["mass_kg"],
                                      **({"note": coll_report["motion_note"]} if "motion_note" in coll_report else {})}
                if "door_not_opening" in res:
                    coll_report["source"] = "passable-door"   # deliberately none (see above), not a failed conversion
            for relp, data in files.items():
                p = os.path.join(self.staging, *relp.split("/"))
                write_staged(p, data)
            res.update(ok=True, out_name=out_name, shapes=len(shapes), materials=mats, collision=mode if use_box else None, collision_report=coll_report,
                       skipped_effect_shapes=sum(1 for m in mats if m is None),
                       fallback_materials=sum(1 for m in mats if m == self.neutral))
            self.stats["assets"] += 1
        except Exception as e:                           # noqa: BLE001  (recorded per asset, batch continues)
            res["reason"] = f"{type(e).__name__}: {e}"
            self.stats["failed"] += 1
        return res

    def convert_anim_object(self, nif_name: str, states: dict, foley: Optional[str] = None, out_suffix: str = "_anim",
                            swap_siblings: bool = False, idles: str = "toggle", graph: Optional[str] = None,
                            slow: Optional[dict] = None) -> dict:
        """An animated FO4 object that is no door (the Vault 111 console, FAL-489 variant D) as a model with its own rig and
        one clip per activator-graph slot, through the door path's multi-part builder: states maps FO4 sequence names to
        the Play slots (anim_object.parse_states), each Play slot also gets a one-frame Idle hold, every .afx is written in
        the vanilla shape (a sound at foley when one is named). Needs the CALUMI library and the vanilla donor body, as
        the doors do. The result's "anim" entry is the manifest (skeleton, animations, graph, clip table); "ok" False
        carries "reason". Files land in the staging folder like every conversion. idles="chain" with graph=<ANAM of genericstategraph01>
        (FAL-489, the four-state console): four Play slots and four Idle slots holding four successive poses (anim_object.add_chain_idles);
        graph defaults to the activator graph. slow={"StateC_Play": 4}: those clips run a whole factor slower (anim_object.stretch_clips)."""
        from . import anim_object, native_door
        res = {"nif": nif_name, "ok": False}
        try:
            if not self.door_anim_dll or self.door_physics_donor is None or self.collision_template is None:
                raise ValueError("needs door_anim_dll, the vanilla donor body and the collision template")
            raw = self.src.mesh(nif_name)
            src = nif.parse(raw)
            shapes = [s for s in nif.fo4_trishapes(src) if s.positions and s.triangles]
            if not shapes:
                raise ValueError("no static BSTriShape geometry")
            mats: List[Optional[str]] = [self._shape_material(src, s) for s in shapes]
            if all(m is None for m in mats):
                raise ValueError("only effect-shader shapes (glass/glow), skipped")
            rel = re.sub(r"^meshes[\\/]", "", nif_name.replace("\\", "/"), flags=re.I)
            out_name = f"{self.prefix}/{os.path.splitext(rel)[0].lower()}{out_suffix.lower()}"
            holder = {}

            def hook(plan):
                if swap_siblings:                                  # the experiment of FAL-489 session 6: the two siblings' indices exchanged
                    plan = anim_object.swap_siblings(plan)
                plan = anim_object.fill_static_tracks(plan)
                if slow:
                    plan = anim_object.stretch_clips(plan, slow)
                plan = (anim_object.add_toggle_idles(plan) if idles == "toggle" else
                        anim_object.add_chain_idles(plan) if idles == "chain" else anim_object.add_holds(plan))
                holder["plan"] = plan
                return plan

            def clip_files(plan, scale):
                return native_door.export_files(plan, self.door_anim_dll, scale, descriptors=anim_object.descriptors(plan, foley))
            files, anim = convert_static.convert_multipart_door(
                raw, out_name, mats, clip_files, collision_template=self.collision_template,
                leaf_physics_donor=self.door_physics_donor, aliases=dict(states), drop_skinned=True,
                allowed=tuple(states.values()), expect_clips=anim_object.slot_names(states, idles), plan_hook=hook,
                anim_graph=graph or anim_object.GRAPH, motion_clip=sorted(states.values())[0])
            anim["states"] = dict(states)
            anim["clips"] = anim_object.clip_table(holder["plan"], convert_static.UNIT_SCALE)
            anim["foley"] = foley or ""
            anim["swap_siblings"] = bool(swap_siblings)
            anim["idles"] = idles
            anim["slow"] = dict(slow or {})
            for relp, data in files.items():
                write_staged(os.path.join(self.staging, *relp.split("/")), data)
            res.update(ok=True, out_name=out_name, shapes=len(shapes), materials=mats, anim=anim)
            self.stats["assets"] += 1
        except Exception as e:                           # noqa: BLE001  (recorded, the stager says why)
            res["reason"] = f"{type(e).__name__}: {e}"
            self.stats["failed"] += 1
        return res
