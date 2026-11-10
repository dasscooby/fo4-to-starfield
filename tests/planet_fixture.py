"""A synthetic stand-in for Starfield.esm's galaxy records (tests only; no game data): the keywords, the Universe
location, a Sol-like star with its system location, two bodies in Sol (a planet and its moon, ids 3 and 6) and Sol
locations up to YNAM 7, a Jemison-like planet (components, master worldspaces, biomes with fauna and flora, a unique
space cell, the body fields) and its planet / orbit / surface locations, laid out like the real records
(docs/planet/planet-probe.md). With census=True also the records the census and the probe world
read: LC172World (an overlay world on a Mars stand-in, its persistent COC marker 0010238E and a coc cell
LC172Ext01), OverlayBlockLC172World, LC172WorldLocation, NewAtlantis (Jemison, a coc cell), TempJemisonWorld, the
three bases the probe places and Mars's planet record. probe_plugin() writes FO4SFPlanetProbe.esm the way
dotnet/PlanetProbe lays it out, raw, for the raw check. Field values are made up."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.planet import esm, records  # noqa: E402

SOL_SYSTEM = 0x0
JEMISON_SYSTEM = 0x0001E0C2
JEMISON_PLANET = 2
SOL_STAR = 0x0001D000
SOL_LOCATION = 0x00018000
JEMISON = 0x0005E400
NEW_ATLANTIS = 0x0001251B
EARTH, LUNA = 0x0005E401, 0x0005E402            # Sol's bodies: (0, 0, 3) and its moon (0, 3, 6)
SOL_FREE_ID = 8                                 # one above the largest Sol id in use: the YNAM 7 location


def z(t):
    return esm.zbytes(t)


def comp(name, *subs):
    return [(b"BFCB", z(name))] + list(subs) + [(b"BFCE", b"")]


def keyword_records():
    out = [esm.Record(b"KYWD", fid, [(b"EDID", z(name))], version=0x246) for name, fid in records.KEYWORDS.items()]
    out.append(esm.Record(b"KYWD", 0x00169593, [(b"EDID", z("PlanetTypeRocky"))], version=0x246))
    return out


def star():
    data = struct.pack("<I", 3) + b"Sol\0" + struct.pack("<I", 3) + b"G2\0" + bytes(40)
    subs = [(b"EDID", z("Sol"))]
    subs += comp("BGSStarDataComponent_Component", (b"DATA", data))
    subs += comp("TESFullName_Component", (b"FULL", struct.pack("<I", 0x1234)))
    subs += [(b"ANAM", z("Sol")), (b"BNAM", struct.pack("<3f", 10.0, -5.0, 2.0)), (b"ONAM", bytes(8)),
             (b"DNAM", struct.pack("<I", SOL_SYSTEM)), (b"ENAM", bytes([255, 240, 200, 0])),
             (b"PNAM", struct.pack("<I", 0x00012345)), (b"HNAM", struct.pack("<I", 0x00012346)),
             (b"WED0", bytes(20))]
    return esm.Record(b"STDT", SOL_STAR, subs, flags=1 << 29, version=0x245, vc=0x2034C1, unknown=3)


def other_star():
    subs = [(b"EDID", z("AlphaCentauri")), (b"ANAM", z("Alpha Centauri")),
            (b"BNAM", struct.pack("<3f", 12.5, -3.0, 2.5)), (b"DNAM", struct.pack("<I", JEMISON_SYSTEM))]
    return esm.Record(b"STDT", 0x0001D001, subs, version=0x245)


def biome(fid, fauna=(), flora=()):
    b = {"biome": fid, "chance": 50.0, "unknown": 0xDEADBEEF, "resource_generation": 0, "fauna": list(fauna),
         "keywords": [0x00169593], "flora_entry_size": 9,
         "flora": [struct.pack("<IIB", f, 0x00055555, 3) for f in flora], "extra": [bytes(range(16))]}
    return records.pack_biome(b)


def planet(houdini=2048):
    subs = [(b"EDID", z("JemisonPlanetData"))]
    subs += comp("TESPlanetModel_Component", (b"MODL", z("Data/Meshes/Planets/Houdini/jemison.nif")),
                 (b"FLLD", struct.pack("<I", 1)))
    subs += comp("BGSKeywordForm_Component", (b"KSIZ", struct.pack("<I", 1)), (b"KWDA", struct.pack("<I", 0x00169593)))
    subs += comp("TESFullName_Component", (b"FULL", struct.pack("<I", 0xA682)))
    subs += comp("HoudiniData_Component", (b"PCCC", bytes((i * 7) & 0xFF for i in range(houdini))))
    subs += [(b"CNAM", records.pack_worldspaces([(0.1, 0.2, NEW_ATLANTIS), (-0.3, 0.4, 0x00012520)])),
             (b"EOVR", struct.pack("<ddIB", 0.5, 0.5, 0x00012521, 1)),
             (b"PPBD", biome(0x0007F88A, fauna=(0x001D06EE, 0x001D06EF), flora=(0x00044444,))),
             (b"PPBD", biome(0x000FD00D)),
             (b"FNAM", struct.pack("<I", 0x001679E8)), (b"GNAM", struct.pack("<f", 0.63)),
             (b"BDST", b""), (b"ANAM", z("Jemison")), (b"CNAM", b"\x02"),
             (b"DNAM", struct.pack("<I", 14) + b"JemisonOrbit\0\0" + b"\x01"),
             (b"ENAM", struct.pack("<6d4f2B6x", 1e9, 1e9, 1.1e9, 0.01, 0.0, 0.5, 0.2, 0.0012, 0.0, 0.0, 1, 0)),
             (b"FNAM", struct.pack("<d3f4x", 0.5, 5.4e24, 6100.0, 0.91)),
             (b"GNAM", struct.pack("<III", JEMISON_SYSTEM, 0, JEMISON_PLANET)),
             (b"HNAM", bytes(40)), (b"INAM", bytes(16)), (b"KNAM", bytes(29)), (b"NNAM", struct.pack("<I", 1)),
             (b"BDED", b""), (b"TEMP", struct.pack("<f", 22.0)), (b"DENS", struct.pack("<f", 5.5)),
             (b"PHLA", struct.pack("<f", 100.0)), (b"RSCS", struct.pack("<i", 12345))]
    return esm.Record(b"PNDT", JEMISON, subs, flags=esm.COMPRESSED, version=0x245, vc=0x2034C1, unknown=8)


def body(fid, edid, name, galaxy):
    """A minimal planet record: the body markers, its name and GNAM (system, parent, planet; None: no GNAM)."""
    gnam = [(b"GNAM", struct.pack("<III", *galaxy))] if galaxy is not None else []
    return esm.Record(b"PNDT", fid, [(b"EDID", z(edid)), (b"BDST", b""), (b"ANAM", z(name)), (b"CNAM", b"\x02")]
                      + gnam + [(b"BDED", b"")], version=0x245)


def sol_bodies():
    return [body(EARTH, "EarthPlanetData", "Earth", (SOL_SYSTEM, 0, 3)),
            body(LUNA, "LunaPlanetData", "Luna", (SOL_SYSTEM, 3, 6))]


def location(fid, edid, keywords, parent, x, y, data=b"\0\0\0\0\xff\x05\x00\x32"):
    return esm.Record(b"LCTN", fid, [(b"EDID", z(edid)), (b"FULL", struct.pack("<I", fid)),
                                     (b"KSIZ", struct.pack("<I", len(keywords))),
                                     (b"KWDA", struct.pack(f"<{len(keywords)}I", *keywords)),
                                     (b"DATA", data), (b"PNAM", struct.pack("<I", parent)),
                                     (b"XNAM", struct.pack("<i", x)), (b"YNAM", struct.pack("<i", y))],
                      version=0x246)


def locations():
    k = records.KEYWORDS
    return [esm.Record(b"LCTN", records.UNIVERSE, [(b"EDID", z("Universe"))], version=0x246),
            location(SOL_LOCATION, "SSol", [k["LocTypeStarSystem"]], records.UNIVERSE, SOL_SYSTEM, 0,
                     data=b"\0\0\0\0\xff\x01\x00\x0a"),
            location(0x00018010, "SSol_PEarth", [k["LocTypePlanet"], k["LocTypeMajorOrbital"]], SOL_LOCATION,
                     SOL_SYSTEM, 3),
            location(0x00018011, "SSol_PEarth_PLuna", [k["LocTypeMoon"], k["LocTypeMajorOrbital"]], 0x00018010,
                     SOL_SYSTEM, 6),
            location(0x00018012, "SSol_PBelt_Orbit", [k["LocTypeOrbit"]], SOL_LOCATION, SOL_SYSTEM, 7),
            location(0x00018001, "SAlphaCentauri", [k["LocTypeStarSystem"]], records.UNIVERSE, JEMISON_SYSTEM, 0),
            location(0x00018002, "SAlphaCentauri_PJemison", [k["LocTypePlanet"], k["LocTypeMajorOrbital"]],
                     0x00018001, JEMISON_SYSTEM, JEMISON_PLANET, data=b"\0\0\0\0\xff\x02\x00\x0b"),
            location(0x00018003, "SAlphaCentauri_PJemison_Orbit", [k["LocTypeOrbit"]], 0x00018002, JEMISON_SYSTEM,
                     JEMISON_PLANET, data=b"\0\0\0\0\xff\x03\x00\x0c"),
            location(0x00018004, "SAlphaCentauri_PJemison_Surface", [k["LocTypeSurface"]], 0x00018002,
                     JEMISON_SYSTEM, JEMISON_PLANET, data=b"\0\0\0\0\xff\x04\x00\x0d")]


def write_starfield(path, houdini=2048, census=False):
    """A Starfield.esm stand-in at path (localized, no masters, like the real file). Returns the writer."""
    w = esm.PluginWriter([], esm.ESM | esm.LOCALIZED)
    for r in keyword_records() + locations() + [planet(houdini)] + sol_bodies() + [star(), other_star()]:
        w.add(r)
    if not census:
        w.write(path)
        return w
    for r in census_records():
        w.add(r)
    with open(path, "wb") as f:
        f.write(w.to_bytes() + esm.group_bytes("WRLD", census_worlds()))
    return w


# ------------------------------------------------------------------------------------------------ worlds (census)
LC172 = 0x02DF8C
LC172_PCELL, LC172_EXT, LC172_EXT_COC, LC172_ACTOR, LC172_LINKED = 0x3807C0, 0x3807C1, 0x3807C2, 0x3807C3, 0x3807C4
LC172_LOC, LC172_BLOCK = 0x3807BE, 0x102382
LC172_COC_POS = (37.4, 57.2, 7.6)
MARS = 0x03F59A
MARS_SURFACE = 0x01B736
MARS_SYSTEM, MARS_PLANET_ID = 0, 4
NA_PCELL, NA_EXT, NA_COC = 0x3807D0, 0x3807D1, 0x3807D2
TEMP_JEMISON, TJ_PCELL, TJ_EXT, TJ_COC = 0x00012345, 0x3807E0, 0x3807E1, 0x3807E2
NA_BIOME = 0x0007F88A                      # one of the fixture Jemison's biomes


def placed(sig, fid, base, pos, rot=(0.0, 0.0, 0.0), edid=None, persistent=False, xlcn=None, xlrl=None, flags=0):
    subs = [(b"EDID", z(edid))] if edid else []
    subs.append((b"NAME", struct.pack("<I", base)))
    if xlcn is not None:
        subs.append((b"XLCN", struct.pack("<I", xlcn)))
    if xlrl is not None:
        subs.append((b"XLRL", struct.pack("<I", xlrl)))
    subs.append((b"DATA", struct.pack("<6f", *pos, *rot)))
    return esm.Record(sig, fid, subs, flags=(esm.PERSISTENT if persistent else 0) | flags)


def cell(fid, grid=None, edid=None):
    subs = [(b"EDID", z(edid))] if edid else []
    subs.append((b"DATA", struct.pack("<H", 2)))
    if grid is not None:
        subs.append((b"XCLC", struct.pack("<iiI", grid[0], grid[1], 0)))
    return esm.Record(b"CELL", fid, subs)


def world_group(world, persistent_cell=None, persistent=(), cells=()):
    """One world in a WRLD top group: the WRLD record, then its children group (type 1): the persistent cell with
    its persistent references (types 6 / 8), then each exterior cell in a block and sub-block (types 4 / 5) with
    its temporary references (types 6 / 9); a cell given as (cell, temporary, persistent) also holds a persistent group
    (type 8, before the temporary one)."""
    def lab(fid):
        return struct.pack("<I", fid)
    inner = b""
    if persistent_cell is not None:
        inner += persistent_cell.to_bytes()
        kids = esm.group_bytes(lab(persistent_cell.formid), b"".join(r.to_bytes() for r in persistent), 8)
        inner += esm.group_bytes(lab(persistent_cell.formid), kids, 6)
    for c, refs, *more in cells:
        body = c.to_bytes()
        kids = b""
        if more and more[0]:
            kids += esm.group_bytes(lab(c.formid), b"".join(r.to_bytes() for r in more[0]), 8)
        if refs:
            kids += esm.group_bytes(lab(c.formid), b"".join(r.to_bytes() for r in refs), 9)
        if kids:
            body += esm.group_bytes(lab(c.formid), kids, 6)
        inner += esm.group_bytes(b"\0\0\0\0", esm.group_bytes(b"\0\0\0\0", body, 5), 4)
    return world.to_bytes() + esm.group_bytes(lab(world.formid), inner, 1)


def overlay_world(fid, edid, system, planet_id, block, location, climate=0x0024E982, biome=0x000AAAAA):
    subs = [(b"EDID", z(edid))]
    subs += comp("BGSWorldSpaceOverlay_Component", (b"SNAM", struct.pack("<i", system)),
                 (b"PNAM", struct.pack("<i", planet_id)), (b"BNAM", struct.pack("<I", block)))
    subs += [(b"FULL", struct.pack("<I", fid)), (b"XLCN", struct.pack("<I", location)),
             (b"BNAM", struct.pack("<I", biome)), (b"CNAM", struct.pack("<I", climate)),
             (b"DATA", b"\x01"), (b"FNAM", b"\x00")]
    return esm.Record(b"WRLD", fid, subs, version=0x246)


def census_worlds():
    """The WRLD top group's payload: LC172World, NewAtlantis, TempJemisonWorld."""
    xm, coc, npc = 0x00003B, 0x000032, 0x2B211C
    lc172 = overlay_world(LC172, "LC172World", MARS_SYSTEM, MARS_PLANET_ID, LC172_BLOCK, LC172_LOC)
    pcell = cell(LC172_PCELL)
    pers = [placed(b"REFR", 0x10238E, coc, LC172_COC_POS, persistent=True),
            placed(b"REFR", LC172_LINKED, xm, (10.0, 10.0, 5.0), persistent=True, xlcn=LC172_LOC)]
    ext = cell(LC172_EXT, (0, 0), "LC172Ext01")
    temp = [placed(b"REFR", LC172_EXT_COC, coc, (20.0, 20.0, 5.0)),
            placed(b"ACHR", LC172_ACTOR, npc, (25.0, 25.0, 5.0), xlcn=LC172_LOC)]
    na = overlay_world(NEW_ATLANTIS, "NewAtlantis", JEMISON_SYSTEM, JEMISON_PLANET, 0x102399, 0x3807D9,
                       biome=NA_BIOME)
    tj = esm.Record(b"WRLD", TEMP_JEMISON, [(b"EDID", z("TempJemisonWorld")), (b"CNAM", struct.pack("<I", 0x24E983)),
                                            (b"DATA", b"\x01")], version=0x246)
    return (world_group(lc172, pcell, pers, [(ext, temp), (cell(0x3807C5, (1, 0)), [])])
            + world_group(na, cell(NA_PCELL), [], [(cell(NA_EXT, (2, 3), "NewAtlanticExt01"),
                                                    [placed(b"REFR", NA_COC, coc, (250.0, 330.0, 9.0))])])
            + world_group(tj, cell(TJ_PCELL), [], [(cell(TJ_EXT, (0, 0), "TempJemisonExt"),
                                                    [placed(b"REFR", TJ_COC, coc, (50.0, 50.0, 2.0))])]))


def census_records():
    """The flat records the census reads besides the galaxy: the block, LC172WorldLocation (one LCPR row: the linked
    persistent marker), the three bases and a Mars planet registering LC172World."""
    k = records.KEYWORDS
    block = esm.Record(b"SFBK", LC172_BLOCK, [(b"EDID", z("OverlayBlockLC172World")),
                                              (b"ANAM", z("Data\\TERRAIN\\LC172World.btd")),
                                              (b"DNAM", struct.pack("<2I", 3, 3)), (b"FNAM", bytes(18)),
                                              (b"INAM", b"\x00"), (b"HNAM", struct.pack("<h", 0))])
    loc = esm.Record(b"LCTN", LC172_LOC, [(b"EDID", z("LC172WorldLocation")), (b"FULL", struct.pack("<I", 7)),
                                          (b"KSIZ", struct.pack("<I", 1)), (b"KWDA", struct.pack("<I", k["LocTypeOverlay"])),
                                          (b"LCPR", struct.pack("<IIhhI", LC172_LINKED, LC172, 0, 0, 0xFFFFFFFF)),
                                          (b"DATA", b"\0\0\0\0\xff\x05\x00\x32"),
                                          (b"PNAM", struct.pack("<I", MARS_SURFACE))], version=0x246)
    bases = [esm.Record(b"STAT", 0x00003B, [(b"EDID", z("XMarker"))]),
             esm.Record(b"STAT", 0x000032, [(b"EDID", z("COCMarkerHeading"))]),
             esm.Record(b"NPC_", 0x2B211C, [(b"EDID", z("EncCitizen01Template"))])]
    mars = esm.Record(b"PNDT", MARS, [(b"EDID", z("MarsPlanetData")),
                                      (b"CNAM", records.pack_worldspaces([(-0.0431, -0.0879, LC172)])),
                                      (b"BDST", b""), (b"ANAM", z("Mars")),
                                      (b"GNAM", struct.pack("<III", MARS_SYSTEM, 0, MARS_PLANET_ID)),
                                      (b"BDED", b"")], version=0x245)
    return [block, loc] + bases + [mars]


def write_creation(path, system_id=0x0001F0F0, position=(40.0, 40.0, 4.0), bodies=(), overrides=(), own_index=None,
                   overlay=None):
    """A built-in Creation stand-in (SFBGS*.esm) adding one star, and the bodies [(EditorID, name, (system, parent,
    planet), or None for no GNAM)] as its own records (0x801 on; own_index: their form ids' top byte, as SFBGS003.esm
    writes FD); overrides: the form ids of locations() it overrides, each with one more keyword (as SFBGS00D.esm
    overrides SAlgorab); overlay: (EditorID, system, planet id) of an overlay world of its own (0x8F0)."""
    w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    w.add(esm.Record(b"STDT", w.own(0x800), [(b"EDID", z("CreationStar")), (b"ANAM", z("Creation Star")),
                                             (b"BNAM", struct.pack("<3f", *position)),
                                             (b"DNAM", struct.pack("<I", system_id))], version=0x245))
    for i, (edid, name, galaxy) in enumerate(bodies, 1):
        w.add(body(w.own(0x800 + i) if own_index is None else own_index << 24 | 0x800 + i, edid, name, galaxy))
    for fid in overrides:
        rec = next(r for r in locations() if r.formid == fid)
        kws = records.keywords_of(rec) + [0x00061990]
        rec.subs = [(s, struct.pack("<I", len(kws)) if s == b"KSIZ" else struct.pack(f"<{len(kws)}I", *kws)
                     if s == b"KWDA" else d) for s, d in rec.subs]
        w.add(rec)
    if overlay is None:
        w.write(path)
        return
    world = overlay_world(w.own(0x8F0), *overlay, block=0, location=0)
    with open(path, "wb") as f:
        f.write(w.to_bytes() + esm.group_bytes("WRLD", world_group(world)))


# ------------------------------------------------------------------------------------------------ the probe plugin
def probe_plugin(path, prm, change=None):
    """FO4SFPlanetProbe.esm as dotnet/PlanetProbe writes it (src/fo4sf/planet/probe.py layout), from params.
    change(kind, record_or_list) may edit a record (kind "block", "location", "world", "cell", "ref:<tag>",
    "quest") before it is written; returning False drops it."""
    from fo4sf.planet import probe
    masters = prm["masters"]
    me = len(masters) << 24

    def own(local):
        return me | local

    def key(k):
        local, plugin = k.split(":")
        idx = [m.lower() for m in masters].index(plugin.lower())
        return (idx << 24) | int(local, 16)

    def edit(kind, rec):
        if change is None:
            return rec
        return None if change(kind, rec) is False else rec

    planet_idx = [m.lower() for m in masters].index(prm["planet_plugin"].lower())
    b = prm["block"]
    block = edit("block", esm.Record(b"SFBK", own(b["id"]), [
        (b"EDID", z(b["edid"])), (b"ANAM", z(b["anam"])), (b"DNAM", struct.pack("<2I", b["dnam"], b["dnam"])),
        (b"FNAM", struct.pack(f"<{len(b['fnam'])}H", *b["fnam"])), (b"INAM", bytes([b["inam"]])),
        (b"HNAM", struct.pack("<h", b["hnam"]))]))
    linked = [r for r in prm["refs"] if r["linked"]]
    rows = b"".join(struct.pack("<IIhhI", own(r["id"]), own(prm["world"]["id"]), r["cell"][1], r["cell"][0],
                                0xFFFFFFFF) for r in linked)
    loc_subs = [(b"EDID", z(prm["location"]["edid"])), (b"FULL", z(prm["location"]["name"])),
                (b"KSIZ", struct.pack("<I", 1)), (b"KWDA", struct.pack("<I", key(prm["keyword_overlay"]))),
                (b"DATA", b"\0\0\0\0\xff\x05\x00\x32"),
                (b"PNAM", struct.pack("<I", (planet_idx << 24) | prm["surface_location"]))]
    if rows:
        loc_subs.append((b"LCPR", rows))
    location = edit("location", esm.Record(b"LCTN", own(prm["location"]["id"]), loc_subs, version=0x246))
    w = prm["world"]
    wsubs = [(b"EDID", z(w["edid"]))]
    wsubs += comp("BGSWorldSpaceOverlay_Component", (b"SNAM", struct.pack("<i", prm["system_id"])),
                  (b"PNAM", struct.pack("<i", prm["planet_id"])), (b"BNAM", struct.pack("<I", own(b["id"]))))
    wsubs += [(b"FULL", z(w["name"])), (b"XLCN", struct.pack("<I", own(prm["location"]["id"])))]
    if prm.get("world_biome"):
        wsubs.append((b"BNAM", struct.pack("<I", key(prm["world_biome"]))))
    wsubs += [(b"CNAM", struct.pack("<I", 0x0024E982)), (b"DATA", b"\x01"), (b"FNAM", b"\x00")]
    world = edit("world", esm.Record(b"WRLD", own(w["id"]), wsubs, version=0x246))
    pcell = edit("cell", cell(own(prm["persistent_cell"])))
    pers, temp, ext = [], {}, {}
    for r in prm["refs"]:
        rec = placed(r["kind"].encode(), own(r["id"]), key(r["base"]), tuple(r["pos"]), tuple(r["rot"]),
                     edid=r["edid"] or None, persistent=r["persistent"],
                     xlcn=own(prm["location"]["id"]) if r["linked"] else None)
        rec = edit("ref:" + r["tag"], rec)
        if rec is None:
            continue
        if r.get("exterior_persistent"):
            ext.setdefault(tuple(r["cell"]), []).append(rec)
        elif r["persistent"]:
            pers.append(rec)
        else:
            temp.setdefault(tuple(r["cell"]), []).append(rec)
    cells = []
    for x, y in probe.cells():
        edid = prm["spawn"]["edid"] if [x, y] == list(prm["spawn"]["cell"]) else None
        cells.append((cell(own(probe.cell_id(x, y)), (x, y), edid), temp.get((x, y), []), ext.get((x, y), [])))
    q = prm["quest"]
    name = q["script"].encode("cp1252")
    vmad = struct.pack("<hhH", 6, 2, 1) + struct.pack("<H", len(name)) + name + b"\x00" + struct.pack("<H", 0)
    vmad += b"\x03\x00\x00\x00\x00\x00"                # the quest fragment part (not read)
    quest = edit("quest", esm.Record(b"QUST", own(q["id"]), [
        (b"EDID", z(q["edid"])), (b"VMAD", vmad), (b"FULL", z(q["name"])), (b"DNAM", struct.pack("<HB", 1, 30))]))
    wr = esm.PluginWriter(masters, esm.ESM)
    for rec in (block, location, quest):
        if rec is not None:
            wr.add(rec)
    body = world_group(world, pcell, pers, cells) if world is not None else b""
    with open(path, "wb") as f:
        f.write(wr.to_bytes() + (esm.group_bytes("WRLD", body) if body else b""))
