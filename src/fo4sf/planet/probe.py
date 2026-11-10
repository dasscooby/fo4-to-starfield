"""The planet probe's test world (docs/planet/planet-probe.md): the layout dotnet/PlanetProbe writes, its terrain,
the parameters file the C# tool reads, and the raw (Mutagen-independent) check of the written plugin.

FO4SFPlanetProbe.esm, masters Starfield.esm and FO4SFPlanet.esm (our planet's master, records.py):
  0x800 REFR T1  persistent XMarker in the persistent cell, no location links    our core's markers today
  0x801 REFR T2  persistent XMarker, XLCN = the probe location + an LCPR row      a fix candidate for markers
  0x802 ACHR T3  temporary citizen in the spawn cell, XLCN + LCPR row             how Bethesda's Creations place actors
  0x803 ACHR T4  persistent citizen in the persistent cell, no links             our Codsworth today
  0x804 REFR T5  temporary XMarker in the spawn cell, no links                   control: plain cell content
  0x805 ACHR T6  persistent citizen, XLCN + LCPR row                             a fix candidate for Codsworth
  0x806 REFR     the COC marker (COCMarkerHeading) in the spawn cell, 1 m above the ground, facing north
  0x807 SFBK     the overlay block: our 3 x 3-cell BTD, Absolute alignment (INAM 1, HNAM 0: BTD heights are world z)
  0x808 LCTN     the probe location: LC172WorldLocation's fields (keyword LocTypeOverlay), parent = our surface
  0x809 WRLD     a copy of LC172World: overlay component = our planet's system id (Sol's in route B), planet id
                 and block; climate kept
  0x80A CELL     the persistent cell;  0x80B..0x813  the nine exterior cells -1..1, (0, 0) = FO4SF_PlanetProbeSpawn
  0x814 QUST     FO4SF_PlanetProbe: start game enabled, script FO4SF_PlanetProbeQuest, no properties
  0x815 REFR T7  persistent XMarker stored in the spawn cell's own persistent group (run 2: FAL-192)  rank 2 of merge-diff
The citizen is Starfield.esm's EncCitizen01Template (2B211C), the calm NPC the combined-core probes placed.

Why these six (docs/planet/planet-probe.md section 2): the player plays a runtime copy of the planet's world that the
game merges the overlay into, and our persistent references stay behind in the base world (verified 29 Oct). Vanilla
LC172World's persistent COC marker moves with the merge; Bethesda's Creation worlds keep their actors in the
TEMPORARY groups of exterior cells, not flagged persistent, with XLCN and an LCPR row ("master persist location
references") on the world's location (verified: SFBGS00D.esm SFFLDR022World, 18 of 18 rows). Which of T1..T6 shows up
in the player's world, with no script moving it, is the result.

Terrain (world metres, cells -1..1, BTD sample (0, 0) at (-100, -100)): flat ground at 10 m, and a 30 x 15 m block
25 m high (x 45..75, y 80..95, top 35 m) north of the arrival, so a screenshot tells our BTD from the planet's ground.
"""
import math
import struct

import numpy as np

from . import esm
from . import records

PLUGIN = "FO4SFPlanetProbe.esm"
AUTHOR = "fo4-to-starfield PlanetProbe"
SCRIPT = "FO4SF_PlanetProbeQuest"
QUEST_EDID = "FO4SF_PlanetProbe"
QUEST_NAME = "FO4SF planet probe"
LOG_NAME = "FO4SFPlanetProbe"
LOG_PREFIX = "FO4SFPP"
WORLD_EDID = "FO4SF_PlanetProbeWorld"
WORLD_NAME = "FO4SF Planet Probe"
BLOCK_EDID = "FO4SF_PlanetProbeBlock"
LOCATION_EDID = "FO4SF_PlanetProbeLocation"
LOCATION_NAME = "FO4SF Planet Probe"
SPAWN_EDID = "FO4SF_PlanetProbeSpawn"
BTD_REL = f"Data/Terrain/{WORLD_EDID}.btd"                  # staged file (exp_install.py --pack: into Main.ba2)
BTD_ANAM = f"Data\\TERRAIN\\{WORLD_EDID}.btd"               # SFBK ANAM, as the terrain experiments write it

N = 3                                   # cells per side (LC172World's BTD is 3 x 3 cells)
CELL_MIN, CELL_MAX = -(N // 2), N - N // 2 - 1
CELL_M = 100.0
STEP_M = CELL_M / 128
ORIGIN = CELL_MIN * CELL_M
HMIN, HMAX = -500.0, 1000.0             # the height range of most vanilla BTDs (make_exp1_btd.py)
GROUND = 10.0
BLOCK_AREA = (45.0, 75.0, 80.0, 95.0)   # x0, x1, y0, y1
BLOCK_TOP = 35.0
ALIGNMENT_ABSOLUTE = 1
ALIGNMENT_RELATIVE = 0                  # INAM 0: vanilla LC overlays (stage option --alignment relative)
ALIGNMENTS = {"absolute": ALIGNMENT_ABSOLUTE, "relative": ALIGNMENT_RELATIVE}
HNAM = 0

XMARKER, COC_MARKER, CITIZEN = 0x00003B, 0x000032, 0x2B211C          # Starfield.esm
LOC_TYPE_OVERLAY = records.KEYWORDS["LocTypeOverlay"]
LC172_COC = 0x10238E                    # LC172World's persistent COC marker (merged in game, 11 Oct)
TEMPLATES = {"world": ("Starfield.esm", 0x02DF8C, "LC172World"),
             "block": ("Starfield.esm", 0x102382, "OverlayBlockLC172World"),
             "location": ("Starfield.esm", 0x3807BE, "LC172WorldLocation")}

FACE_SOUTH = math.pi                    # actors face the arrival
COC_POS = (60.0, 50.0, GROUND + 1.0)
# tag, local id, kind, EditorID, base, persistent, linked, position, z rotation
REFS = (
    ("T1", 0x800, "REFR", "FO4SF_PP_T1_Plain", XMARKER, True, False, (60.0, 50.0, GROUND), 0.0),
    ("T2", 0x801, "REFR", "FO4SF_PP_T2_Linked", XMARKER, True, True, (64.0, 50.0, GROUND), 0.0),
    ("T3", 0x802, "ACHR", "FO4SF_PP_T3_TempLinkedActor", CITIZEN, False, True, (60.0, 64.0, GROUND), FACE_SOUTH),
    ("T4", 0x803, "ACHR", "FO4SF_PP_T4_PlainActor", CITIZEN, True, False, (52.0, 62.0, GROUND), FACE_SOUTH),
    ("T5", 0x804, "REFR", "FO4SF_PP_T5_Temp", XMARKER, False, False, (56.0, 50.0, GROUND), 0.0),
    ("T6", 0x805, "ACHR", "FO4SF_PP_T6_LinkedActor", CITIZEN, True, True, (68.0, 62.0, GROUND), FACE_SOUTH),
    ("COC", 0x806, "REFR", "", COC_MARKER, False, False, COC_POS, 0.0),
    ("T7", 0x815, "REFR", "FO4SF_PP_T7_ExtPersistent", XMARKER, True, False, (72.0, 50.0, GROUND), 0.0),
)
# tags stored as a persistent child of their own exterior cell, not in the world's persistent cell (merge-diff, T7)
EXTERIOR_PERSISTENT = frozenset({"T7"})
TEST_TAGS = tuple(r[0] for r in REFS if r[0].startswith("T"))
BLOCK_ID, LOCATION_ID, WORLD_ID, PERSISTENT_CELL_ID, FIRST_CELL_ID = 0x807, 0x808, 0x809, 0x80A, 0x80B
QUEST_ID = 0x814
NEXT_ID = 0x816                         # after T7 (0x815)
# what each tag stands for (the log reader's verdict table)
MEANING = {
    "T1": "persistent marker, no links (our core's markers)",
    "T2": "persistent marker + location links",
    "T3": "temporary actor + location links (Bethesda's Creation pattern)",
    "T4": "persistent actor, no links (our Codsworth)",
    "T5": "temporary marker, no links (control: cell content)",
    "T6": "persistent actor + location links",
    "T7": "persistent marker in the spawn cell's own persistent group, no links (merge-diff rank 2)",
}
SCRIPT_IDS = {"T1Id": 0x800, "T2Id": 0x801, "T3Id": 0x802, "T4Id": 0x803, "T5Id": 0x804, "T6Id": 0x805,
              "T7Id": 0x815,
              "LocationId": LOCATION_ID, "WorldId": WORLD_ID, "MergeId": 0x800, "LC172CocId": LC172_COC,
              "PlanetLocId": records.PLANET_LOC, "SurfaceLocId": records.SURFACE_LOC, "PlanetId": records.PLANET,
              "StarSystemKwId": records.KEYWORDS["LocTypeStarSystem"],          # Starfield.esm keywords: the stage
              "MajorOrbitalKwId": records.KEYWORDS["LocTypeMajorOrbital"]}      # holds them to the census's
SCRIPT_KEYWORDS = {"StarSystemKwId": "LocTypeStarSystem", "MajorOrbitalKwId": "LocTypeMajorOrbital"}
CELL_TYPES = {1: "world", 4: "block", 5: "subblock", 6: "cell", 8: "persistent", 9: "temporary"}


class ProbeError(ValueError):
    pass


def cell_of(x, y):
    return int(math.floor(x / CELL_M)), int(math.floor(y / CELL_M))


def cells():
    """[(x, y)] in the order the C# tool writes them (x outer, y inner), local ids FIRST_CELL_ID onwards."""
    return [(x, y) for x in range(CELL_MIN, CELL_MAX + 1) for y in range(CELL_MIN, CELL_MAX + 1)]


def cell_id(x, y):
    return FIRST_CELL_ID + cells().index((x, y))


# ------------------------------------------------------------------------------------------------ terrain
def heights():
    """World heights (m) of the BTD samples [row (south first), column (west first)]."""
    x = ORIGIN + np.arange(N * 128) * STEP_M
    X, Y = np.meshgrid(x, x)
    h = np.full(X.shape, GROUND)
    x0, x1, y0, y1 = BLOCK_AREA
    h[(X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)] = BLOCK_TOP
    return h


def ground_at(x, y):
    """The ground height the layout puts at world (x, y) (exact on our sample grid)."""
    x0, x1, y0, y1 = BLOCK_AREA
    return BLOCK_TOP if x0 <= x <= x1 and y0 <= y <= y1 else GROUND


def make_btd(template):
    """Our BTD (fo4sf.btd.Btd) with the land texture table, quadrant map and weights of a vanilla template BTD
    (terrain/landingoverlay01.btd of the user's Terrain01.ba2, as make_exp1_btd.py), so only the heights are ours."""
    from .. import btd
    quad = np.tile(template.quad_map[0:1, 0:1, :], (N * 2, N * 2, 1))
    weights = np.tile(template.weights[:128, :128], (N, N))
    h = heights()
    return btd.Btd(6, HMIN, HMAX, list(template.ltex), btd.quantize(h, HMIN, HMAX), weights, quad)


# ------------------------------------------------------------------------------------------------ parameters
def key(plugin, local):
    return f"{local:06X}:{plugin}"


def params(system_id, planet_id, fnam, world_biome=None, templates=None, plugin=PLUGIN, planet_plugin=records.MASTER,
           alignment=ALIGNMENT_ABSOLUTE):
    """probe_params.json for dotnet/PlanetProbe. fnam: the SFBK FNAM values (overlay.fnam_values of the BTD).
    world_biome: (plugin, local id) of the biome the world record names, None to keep the template's.
    alignment: the SFBK INAM (ALIGNMENT_ABSOLUTE, the default, or ALIGNMENT_RELATIVE)."""
    if alignment not in ALIGNMENTS.values():
        raise ProbeError(f"alignment {alignment}: INAM 0 (relative) or 1 (absolute)")
    t = dict(TEMPLATES)
    t.update(templates or {})
    if len(fnam) != N * N:
        raise ProbeError(f"fnam has {len(fnam)} values, {N * N} expected")
    refs = [{"id": i, "tag": tag, "edid": edid, "kind": kind, "base": key("Starfield.esm", base), "persistent": pers,
             "linked": linked, "pos": list(pos), "rot": [0.0, 0.0, rz],
             "cell": list(cell_of(pos[0], pos[1])), "exterior_persistent": tag in EXTERIOR_PERSISTENT,
             "meaning": MEANING.get(tag, "arrival marker")}
            for tag, i, kind, edid, base, pers, linked, pos, rz in REFS]
    return {
        "kind": "planet_probe_params", "version": 1, "plugin": plugin, "planet_plugin": planet_plugin,
        "masters": ["Starfield.esm", planet_plugin], "author": AUTHOR,
        "system_id": system_id, "planet_id": planet_id, "surface_location": records.SURFACE_LOC,
        "templates": {k: {"key": key(p, i), "edid": e} for k, (p, i, e) in t.items()},
        "keyword_overlay": key("Starfield.esm", LOC_TYPE_OVERLAY),
        "world_biome": key(*world_biome) if world_biome else None,
        "block": {"id": BLOCK_ID, "edid": BLOCK_EDID, "anam": BTD_ANAM, "dnam": N, "fnam": [int(v) for v in fnam],
                  "inam": alignment, "hnam": HNAM},
        "location": {"id": LOCATION_ID, "edid": LOCATION_EDID, "name": LOCATION_NAME},
        "world": {"id": WORLD_ID, "edid": WORLD_EDID, "name": WORLD_NAME, "cell_min": CELL_MIN, "cell_max": CELL_MAX},
        "persistent_cell": PERSISTENT_CELL_ID, "first_cell": FIRST_CELL_ID,
        "spawn": {"cell": [0, 0], "edid": SPAWN_EDID},
        "refs": refs,
        "quest": {"id": QUEST_ID, "edid": QUEST_EDID, "name": QUEST_NAME, "script": SCRIPT},
        "next_id": NEXT_ID,
    }


# ------------------------------------------------------------------------------------------------ raw reading
def world_items(plugin, world=None):
    """Every record under the WRLD top group with its place: [{rec, world, cell, group}] where group is
    'world' (a WRLD record), 'cell' (a CELL record), 'persistent' or 'temporary' (a cell child). world (a form id)
    keeps one worldspace and skips the children of every other (a full Starfield.esm has hundreds)."""
    out = []
    for start, end in plugin.groups.get("WRLD", []):
        for top in plugin.walk(start, end, groups=set()):
            if top[0] == "REC":
                rec = plugin.record_at(top[1])
                if world is None or rec.formid == world:
                    out.append({"rec": rec, "world": rec.formid, "cell": None, "group": "world"})
                continue
            _, label, gtype, gstart, gend, _ = top
            wid = struct.unpack("<I", label)[0]
            if gtype != 1 or (world is not None and wid != world):
                continue
            stack = []                                       # (end offset, type, label) of the open groups
            for item in plugin.walk(gstart, gend):
                if item[0] == "GRUP":
                    _, lab, t, s0, e0, _ = item
                    stack = [g for g in stack if g[0] > s0 - 24]
                    stack.append((e0, t, struct.unpack("<I", lab)[0]))
                    continue
                _, off, sig, _ = item
                stack = [g for g in stack if g[0] > off]
                rec = plugin.record_at(off)
                cell = next((lab for e, t, lab in reversed(stack) if t in (6, 8, 9)), None)
                inner = stack[-1][1] if stack else 1
                group = "cell" if sig == b"CELL" else CELL_TYPES.get(inner, f"type{inner}")
                out.append({"rec": rec, "world": wid, "cell": cell, "group": group})
    return out


def component_fields(rec, name):
    """{sig: data} of one base form component block (BFCB <name> ... BFCE)."""
    for cname, start, endi in records.component_spans(rec.subs):
        if cname == name:
            return {s.decode("latin1"): d for s, d in rec.subs[start + 1:endi]}
    return None


def top_level(rec, sig):
    """A subrecord outside every component block."""
    inside = False
    sig = sig if isinstance(sig, bytes) else sig.encode("ascii")
    for s, d in rec.subs:
        if s == b"BFCB":
            inside = True
        elif s == b"BFCE":
            inside = False
        elif s == sig and not inside:
            return d
    return None


def lcpr_rows(data):
    """LCPR rows: [(ref, world/cell, grid x, grid y, unknown)] (on disk: ref, world, grid Y s16, grid X s16, u32)."""
    if data is None:
        return []
    if len(data) % 16:
        raise ProbeError(f"LCPR of {len(data)} bytes (16 per row)")
    rows = []
    for i in range(0, len(data), 16):
        ref, world, gy, gx, unk = struct.unpack_from("<IIhhI", data, i)
        rows.append((ref, world, gx, gy, unk))
    return rows


def vmad_scripts(data):
    """[(script name, property count)] of a VMAD (version i16, object format i16, script count u16, then per script a
    u16-length name, a u8 flag byte and a u16 property count; properties are not decoded: ours have none)."""
    if not data or len(data) < 6:
        return []
    count, = struct.unpack_from("<H", data, 4)
    p, out = 6, []
    for _ in range(count):
        n, = struct.unpack_from("<H", data, p)
        name = bytes(data[p + 2:p + 2 + n]).decode("cp1252", "replace")
        p += 2 + n
        props, = struct.unpack_from("<H", data, p + 1)          # after the u8 flags
        p += 3
        out.append((name, props))
        if props:
            break                                            # property layouts are not needed here
    return out


def ref_fields(rec):
    """base, position, rotation, XLCN, XLRL of a placed reference."""
    name = rec.get(b"NAME")
    data = rec.get(b"DATA")
    if name is None or data is None or len(data) < 24:
        raise ProbeError(f"{rec!r}: no NAME / 24-byte DATA")
    vals = struct.unpack_from("<6f", data)
    x = rec.get(b"XLCN")
    r = rec.get(b"XLRL")
    return {"base": struct.unpack("<I", name)[0], "pos": list(vals[:3]), "rot": list(vals[3:]),
            "xlcn": struct.unpack("<I", x)[0] if x else None, "xlrl": struct.unpack("<I", r)[0] if r else None}


def master_index(masters, name):
    """The load index of `name` in a master list (case-insensitive, as the game), None when absent."""
    low = [m.lower() for m in masters]
    return low.index(name.lower()) if name.lower() in low else None


def close(a, b, tol=1e-4):
    return all(abs(p - q) <= tol for p, q in zip(a, b)) and len(a) == len(b)


# ------------------------------------------------------------------------------------------------ check
def check_plugin(path, prm, template_masters=None):
    """Problems of the written probe plugin ([] = none) and a summary, from the raw records alone.
    template_masters: the master list expected (default prm['masters'])."""
    problems = []

    def need(ok, what):
        if not ok:
            problems.append(what)

    summary = {}
    want_masters = template_masters or prm["masters"]
    with esm.Plugin(path) as p:
        need([m.lower() for m in p.masters] == [m.lower() for m in want_masters],
             f"masters {p.masters}, expected {want_masters}")
        need(p.flags & esm.ESM, "not flagged as a master")
        need(not p.flags & esm.LOCALIZED, "flagged localized")
        me = len(p.masters) << 24
        pi = master_index(p.masters, prm["planet_plugin"])
        planet_index = pi << 24 if pi is not None else None
        own = lambda local: me | local  # noqa: E731
        flat = {}
        for g in ("SFBK", "LCTN", "QUST"):
            for r in p.records(g):
                flat.setdefault(g, []).append(r)
        items = world_items(p)
        by_id = {it["rec"].formid: it for it in items}

        # block
        blocks = flat.get("SFBK", [])
        need(len(blocks) == 1 and blocks[0].formid == own(prm["block"]["id"]), "not exactly our SFBK")
        if blocks:
            b = blocks[0]
            fn = b.get(b"FNAM") or b""
            need(esm.zstring(b.get(b"ANAM") or b"") == prm["block"]["anam"], "SFBK ANAM")
            need(b.get(b"DNAM") == struct.pack("<2I", prm["block"]["dnam"], prm["block"]["dnam"]), "SFBK DNAM")
            need(fn == struct.pack(f"<{len(prm['block']['fnam'])}H", *prm["block"]["fnam"]), "SFBK FNAM")
            need(b.get(b"INAM") == bytes([prm["block"]["inam"]]), "SFBK INAM")
            need(b.get(b"HNAM") == struct.pack("<h", prm["block"]["hnam"]), "SFBK HNAM")
            need(records.component_spans(b.subs) == [], "SFBK keeps a component (BlockEditorMetaData)")
            summary["block"] = {"formid": f"{b.formid:08X}", "edid": b.edid, "anam": esm.zstring(b.get(b"ANAM") or b""),
                                "fnam": list(struct.unpack(f"<{len(fn) // 2}H", fn))}

        # location
        locs = flat.get("LCTN", [])
        need(len(locs) == 1 and locs[0].formid == own(prm["location"]["id"]), "not exactly our LCTN")
        linked = [r for r in prm["refs"] if r["linked"]]
        if locs:
            loc = locs[0]
            parent = loc.get(b"PNAM")
            want_parent = (planet_index | prm["surface_location"]) if planet_index is not None else None
            need(parent is not None and struct.unpack("<I", parent)[0] == want_parent,
                 f"LCTN parent {parent.hex() if parent else None}, expected {want_parent}")
            need(records.keywords_of(loc) == [LOC_TYPE_OVERLAY], f"LCTN keywords {records.keywords_of(loc)}")
            for sig in (b"LCSR", b"LCID", b"LCUN", b"ACPR", b"ACSR", b"ACUN", b"LCUR", b"ACUR", b"ACEP", b"LCEP",
                        b"ACEC", b"LCEC", b"RCPR", b"RCSR", b"RCUN", b"RCUR"):
                need(loc.get(sig) is None, f"LCTN keeps {sig.decode()}")
            rows = lcpr_rows(loc.get(b"LCPR"))
            want = sorted((own(r["id"]), own(prm["world"]["id"]), r["cell"][0], r["cell"][1], 0xFFFFFFFF)
                          for r in linked)
            need(sorted(rows) == want, f"LCPR rows {rows}, expected {want}")
            summary["location"] = {"formid": f"{loc.formid:08X}", "edid": loc.edid,
                                   "parent": f"{struct.unpack('<I', parent)[0]:08X}" if parent else None,
                                   "lcpr": [[f"{a:08X}", f"{b_:08X}", gx, gy, f"{u:08X}"] for a, b_, gx, gy, u in rows],
                                   "xnam_ynam": records.location_ids(loc)}

        # world
        worlds = [it["rec"] for it in items if it["group"] == "world"]
        need(len(worlds) == 1 and worlds[0].formid == own(prm["world"]["id"]), "not exactly our WRLD")
        if worlds:
            w = worlds[0]
            ov = component_fields(w, "BGSWorldSpaceOverlay_Component")
            need(ov is not None, "WRLD has no overlay component")
            ov = ov or {}
            need(ov.get("SNAM") == struct.pack("<i", prm["system_id"]), f"overlay SNAM {ov.get('SNAM')}")
            need(ov.get("PNAM") == struct.pack("<i", prm["planet_id"]), f"overlay PNAM {ov.get('PNAM')}")
            need(ov.get("BNAM") == struct.pack("<I", own(prm["block"]["id"])), "overlay BNAM is not our block")
            xl = top_level(w, b"XLCN")
            need(xl == struct.pack("<I", own(prm["location"]["id"])), "WRLD XLCN is not our location")
            for sig in (b"OFST", b"CLSZ", b"RNAM", b"WNAM"):
                need(top_level(w, sig) is None, f"WRLD keeps {sig.decode()}")
            if prm.get("world_biome"):
                bid, bplug = prm["world_biome"].split(":")
                bidx = master_index(p.masters, bplug)
                need(bidx is not None and top_level(w, b"BNAM") == struct.pack("<I", (bidx << 24) | int(bid, 16)),
                     "WRLD biome is not the planet's")
            clim = top_level(w, b"CNAM")
            summary["world"] = {"formid": f"{w.formid:08X}", "edid": w.edid,
                                "overlay": {k: v.hex() for k, v in ov.items()},
                                "climate": f"{struct.unpack('<I', clim)[0]:08X}" if clim and len(clim) == 4 else None,
                                "biome": (top_level(w, b"BNAM") or b"").hex(),
                                "subrecords": [s.decode("latin1") for s, _ in w.subs]}

        # cells
        cell_recs = {it["rec"].formid: it for it in items if it["group"] == "cell"}
        pcell = own(prm["persistent_cell"])
        need(pcell in cell_recs and cell_recs[pcell]["world"] == own(prm["world"]["id"]), "persistent cell")
        grid = {}
        for fid, it in cell_recs.items():
            if fid == pcell:
                continue
            xc = it["rec"].get(b"XCLC")
            if xc is None or len(xc) < 8:
                problems.append(f"CELL {fid:08X} has no XCLC grid")
                continue
            grid[struct.unpack_from("<2i", xc)] = it["rec"]
        need(sorted(grid) == sorted(cells()), f"exterior cells {sorted(grid)}")
        for (x, y), c in grid.items():
            need(c.formid == own(cell_id(x, y)), f"cell ({x}, {y}) is {c.formid:08X}, expected {own(cell_id(x, y)):08X}")
        spawn = grid.get(tuple(prm["spawn"]["cell"]))
        need(spawn is not None and spawn.edid == prm["spawn"]["edid"], "spawn cell EditorID")
        need(sum(1 for c in grid.values() if c.edid) == 1, "only the spawn cell has an EditorID")

        # references
        refs_out = []
        for r in prm["refs"]:
            it = by_id.get(own(r["id"]))
            if it is None:
                problems.append(f"{r['tag']} {own(r['id']):08X} missing")
                continue
            rec = it["rec"]
            f = ref_fields(rec)
            ext = bool(r.get("exterior_persistent"))
            need(not ext or r["persistent"], f"{r['tag']} is exterior_persistent but not persistent")
            want_cell = pcell if r["persistent"] and not ext else own(cell_id(*r["cell"]))
            need(rec.sig == r["kind"].encode(), f"{r['tag']} is {rec.sig.decode()}, not {r['kind']}")
            need(it["group"] == ("persistent" if r["persistent"] else "temporary") and it["cell"] == want_cell,
                 f"{r['tag']} in {it['group']} group of {it['cell']}, expected cell {want_cell:08X}")
            need(bool(rec.flags & esm.PERSISTENT) == r["persistent"], f"{r['tag']} persistent flag {rec.flags:#x}")
            need(not rec.flags & 0x800, f"{r['tag']} initially disabled")
            bidx = master_index(p.masters, r["base"].split(":")[1])
            need(bidx is not None and f["base"] == (bidx << 24) | int(r["base"].split(":")[0], 16),
                 f"{r['tag']} base {f['base']:08X}")
            need(close(f["pos"], r["pos"]) and close(f["rot"], r["rot"]), f"{r['tag']} position {f['pos']}")
            need(f["xlcn"] == (own(prm["location"]["id"]) if r["linked"] else None), f"{r['tag']} XLCN {f['xlcn']}")
            need(f["xlrl"] is None, f"{r['tag']} has an XLRL")
            if r["edid"]:
                need(rec.edid == r["edid"], f"{r['tag']} EditorID {rec.edid!r}")
            if ext:                                      # T7: the spawn cell's persistent group, not the world's
                need(it["cell"] != pcell, f"{r['tag']} is in the world's persistent cell")
            refs_out.append({"tag": r["tag"], "formid": f"{rec.formid:08X}", "sig": rec.sig.decode(),
                             "group": it["group"], "flags": f"{rec.flags:08X}", "pos": f["pos"],
                             "xlcn": f"{f['xlcn']:08X}" if f["xlcn"] else None,
                             "subrecords": [s.decode("latin1") for s, _ in rec.subs]})
        summary["refs"] = refs_out
        extra = sorted(set(by_id) - {own(r["id"]) for r in prm["refs"]} - set(cell_recs)
                       - {own(prm["world"]["id"])})
        need(not extra, f"unexpected records in the world: {[f'{x:08X}' for x in extra]}")

        # quest
        quests = flat.get("QUST", [])
        need(len(quests) == 1 and quests[0].formid == own(prm["quest"]["id"]), "not exactly our QUST")
        if quests:
            q = quests[0]
            dn = q.get(b"DNAM") or b""
            need(len(dn) >= 2 and struct.unpack_from("<H", dn)[0] & 1, "QUST is not start game enabled")
            scripts = vmad_scripts(q.get(b"VMAD"))
            need(scripts == [(prm["quest"]["script"], 0)], f"QUST scripts {scripts}")
            summary["quest"] = {"formid": f"{q.formid:08X}", "edid": q.edid, "dnam": dn.hex(), "scripts": scripts}
        others = sorted(set(p.groups) - {"SFBK", "LCTN", "QUST", "WRLD"})
        need(not others, f"unexpected top groups {others}")
        summary["masters"] = p.masters
    return problems, summary
