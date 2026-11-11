"""Starfield 3D surface-map file contract (docs/terrain/surface-map.md). Synthetic only.

The May 2024 surface map draws the current loading zone in 3D. It is not a separate mesh we author.
World object LOD is lodsettings/<edid>.lod plus meshes/lod/generated/…_lod_0..3.nif. Converted FO4
*_lod.nif files under meshes/fo4core/lod/ are ordinary meshes, not that contract.
"""

MARS_SURFACE = 0x0001B736  # LCTN SSol_PMars_Surface; parent of FO4Core_CommonwealthLocation
MARS_PNDT = 0x0003F59A  # PNDT MarsPlanetData
OVERLAY_SNAM_SOL = 0  # WRLD overlay component, LC172 / core64k
OVERLAY_PNAM_MARS = 4
WORLD_EDID = "FO4Core_Commonwealth"
WORLD_OBJECT_LOD_PREFIX = "meshes/lod/generated/"
CONVERTED_FO4_LOD_PREFIX = "meshes/fo4core/lod/"
FO4_PER_OBJECT_LOD_PREFIX = "meshes/lod/"
FO4_LODSETTINGS_PREFIX = "lodsettings/"
FO4_LODSETTINGS_WORLDS = ("commonwealth", "diamondcity", "sanctuaryhillsworld")
LODSETTINGS_DIR = "lodsettings"


def _slash(relpath):
    return relpath.replace("\\", "/").lower().lstrip("/")


def lodsettings_rel(world_edid):
    """Vanilla path: lodsettings/<world editor id, lower case>.lod (20-byte file)."""
    if not world_edid or world_edid != world_edid.strip() or "/" in world_edid or "\\" in world_edid:
        raise ValueError("world editor id required")
    return f"{LODSETTINGS_DIR}/{world_edid.lower()}.lod"


def is_starfield_world_lod_mesh(relpath):
    """True only for CK/world object LOD meshes, not converted FO4 *_lod.nif files."""
    p = _slash(relpath)
    return p.startswith(WORLD_OBJECT_LOD_PREFIX) and any(
        p.endswith(f"_lod_{i}.nif") for i in range(4)
    )


def is_converted_fo4_lod_mesh(relpath):
    return _slash(relpath).startswith(CONVERTED_FO4_LOD_PREFIX)


def is_fo4_per_object_lod_nif(relpath):
    """FO4 meshes/lod/**/*.nif (per-object LOD models). Not Starfield generated world LOD."""
    p = _slash(relpath)
    if p.startswith(WORLD_OBJECT_LOD_PREFIX) or p.startswith(CONVERTED_FO4_LOD_PREFIX):
        return False
    return p.startswith(FO4_PER_OBJECT_LOD_PREFIX) and p.endswith(".nif")


def is_fo4_world_object_lod_tile(relpath):
    """FO4 .bto world object-LOD tile. FORMAT-GAP vs Starfield meshes/lod/generated."""
    return _slash(relpath).endswith(".bto")


def is_fo4_terrain_lod_tile(relpath):
    """FO4 .btr terrain LOD tile. Overlay BTD already has LOD0-4."""
    return _slash(relpath).endswith(".btr")


def is_fo4_lodsettings(relpath):
    """FO4 LODSettings/<world>.lod for the three worlds in Fallout4 - Meshes.ba2.

    Commonwealth is 16 bytes. Starfield overlay files share the lodsettings/ directory
    (e.g. fo4core_commonwealth.lod) and must not match.
    """
    p = _slash(relpath)
    if not (p.startswith(FO4_LODSETTINGS_PREFIX) and p.endswith(".lod")):
        return False
    world = p.rsplit("/", 1)[-1][:-4]
    return world in FO4_LODSETTINGS_WORLDS
