"""Starfield map-marker LCSR layout (docs/terrain/map-markers.md).

Map markers are REFR of STAT MapMarker (00000010) with an empty XMRK. A Location points at them with LCSR
(MasterSpecialReferences) in a 5 x u32 stride and usually LCID (MasterInitiallyDisabledReferences) = that REFR.
Synthetic only: no game files.
"""
import json
import math
import os
import struct

MAPMARKER_STAT = 0x00000010
MAPMARKER_REF_TYPE = 0x0002271F
SHIP_LANDING_MARKER_REF_TYPE = 0x00009105
SHIP_LANDING_MARKER_REF_TYPE_LARGE = 0x00009102
LOC_TYPE_OVERLAY = 0x002CA99D

# LC172WorldLocation 003807BE, Starfield.esm 1.16.244 (raw LCSR / LCID walk).
LC172_WORLD = 0x0002DF8C
LC172_LOCATION = 0x003807BE
LC172_MAP_MARKER = 0x003E5E12
LC172_FNAM = 0x1B
LC172_TNAM = 0x17     # the vanilla template's type (its world's own agency landmark); the writers overwrite it per marker
LANDMARK_SNOW_GLOBE_REF_TYPE = 0x00009A42

# Starfield's surface map draws a marker's icon from its type: a position 0-93 in a fixed list inside the map screen.
# 0-9 are emblems of Starfield's own places. The FO4 type (TNAM, the export's type_id) -> that number table is data:
# src/fo4sf/map_marker_types.json, one reason per row.
SF_TYPE_MAX = 93
SF_TYPE_OWN_PLACES = range(10)
MAP_MARKER_TYPES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_marker_types.json")


def load_type_table(path=MAP_MARKER_TYPES_JSON):
    """The type table as {"by_fo4": {fo4 id: row}, "default": sf number, "fixed": {tag: FO4 id}}; every number is checked
    to lie in 0-93 and outside 0-9."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    by_fo4 = {}
    for row in doc["types"]:
        if row["fo4_id"] in by_fo4:
            raise ValueError(f"map marker type table: FO4 type {row['fo4_id']} twice")
        by_fo4[row["fo4_id"]] = row
    default = doc["default"]["sf_type"]
    for n in [default] + [r["sf_type"] for r in by_fo4.values()] + [r["sf_type"] for r in doc["fixed_markers"].values()]:
        if not (isinstance(n, int) and 0 <= n <= SF_TYPE_MAX and n not in SF_TYPE_OWN_PLACES):
            raise ValueError(f"map marker type table: Starfield type {n!r} is not in 10-{SF_TYPE_MAX}")
    return {"by_fo4": by_fo4, "default": default, "fixed": {t: r["sf_type"] for t, r in doc["fixed_markers"].items()}}


_TYPE_TABLE = None


def _table():
    global _TYPE_TABLE
    if _TYPE_TABLE is None:
        _TYPE_TABLE = load_type_table()
    return _TYPE_TABLE


def starfield_type(fo4_type_id, table=None):
    """The Starfield icon number for an FO4 marker type id (None or an unlisted id: the table's default)."""
    table = table or _table()
    row = table["by_fo4"].get(fo4_type_id)
    return row["sf_type"] if row else table["default"]


def fixed_marker_type(tag):
    """The Starfield icon number of one of the core's fixed four (COMMONWEALTH_MARKERS) by tag."""
    table = _table()
    return table["fixed"].get(tag, table["default"])


def type_counts(entries):
    """{Starfield icon number: how many of these overlay_markers entries carry it}, by number."""
    counts = {}
    for e in entries:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    return dict(sorted(counts.items()))


def format_type_counts(entries):
    """A small table of type_counts: number, count."""
    rows = type_counts(entries)
    return "  Starfield type  markers\n" + "\n".join(f"  {t:>14}  {n:>7}" for t, n in rows.items())


LCSR_STRIDE = 20
LCSR_PAD = 0
LCSR_TAIL = 0xFFFFFFFF


def parse_lcsr(data):
    """Decode an LCSR payload into dicts {lcrt, refr, wrld, pad, tail}."""
    if len(data) % LCSR_STRIDE:
        raise ValueError(f"LCSR length {len(data)} is not a multiple of {LCSR_STRIDE}")
    out = []
    for i in range(0, len(data), LCSR_STRIDE):
        lcrt, refr, wrld, pad, tail = struct.unpack_from("<5I", data, i)
        out.append({"lcrt": lcrt, "refr": refr, "wrld": wrld, "pad": pad, "tail": tail})
    return out


def pack_lcsr(entries):
    """Encode LCSR dicts (parse_lcsr output, or lcrt/refr/wrld with default pad/tail)."""
    chunks = []
    for e in entries:
        chunks.append(struct.pack(
            "<5I",
            e["lcrt"],
            e["refr"],
            e["wrld"],
            e.get("pad", LCSR_PAD),
            e.get("tail", LCSR_TAIL),
        ))
    return b"".join(chunks)


def map_marker_lcsr(refr, wrld):
    """One MapMarkerRefType LCSR row for a marker REFR in wrld."""
    return pack_lcsr([{"lcrt": MAPMARKER_REF_TYPE, "refr": refr, "wrld": wrld}])


# Commonwealth map markers of the core overlay (docs/terrain/map-markers.md, "Commonwealth markers"). FO4 positions in
# FO4 units from Fallout4.esm (the landmarks scripts/terrain/make_cw_overlays.py already uses: the Sanctuary, Vault 111
# and Concord map-marker REFRs). Red Rocket sits on the COC arrival (the flat vertex at the station), so its icon and
# the tested spawn are one place. The overlay's local frame is the CW frame: position = FO4 position / 70.
FO4_UNITS_PER_M = 70.0
COMMONWEALTH_MARKERS = (
    # (tag, map name, FO4 source REFR, FO4 x, FO4 y); None position = the COC arrival
    ("RedRocket", "Red Rocket Truck Stop", 0x000211C0, None, None),
    ("Sanctuary", "Sanctuary Hills", 0x00072A48, -80768.19, 88174.80),
    ("Vault111", "Vault 111", 0x0009F272, -89271.98, 91369.30),
    ("Concord", "Concord", 0x00082138, -60286.01, 72977.79),
)
EDGE_KEEP_M = 200.0     # two cells inside the overlay, as the ray plans keep their probes


def sf_cell(x, y, cell_m=100.0):
    return [int(math.floor(x / cell_m)), int(math.floor(y / cell_m))]


def overlay_markers(spawn, bounds_m, ground, markers=COMMONWEALTH_MARKERS, keep=EDGE_KEEP_M):
    """The overlay's "map_markers" params entries: {tag, name, src, pos [x, y, z], cell}, local metres.

    spawn: the COC marker position (x, y, z); bounds_m: (min, max) of the overlay's square in local metres; ground:
    f(x, y) -> terrain height (the BTD). A marker outside the overlay (less than `keep` from its edge) raises: the core
    always contains these four, and a silent drop would ship a map without one of them."""
    lo, hi = bounds_m
    out = []
    for tag, name, src, fx, fy, *rest in markers:
        if fx is None:
            x, y, z = (float(v) for v in spawn)
        else:
            x, y = fx / FO4_UNITS_PER_M, fy / FO4_UNITS_PER_M
            if not (lo + keep <= x <= hi - keep and lo + keep <= y <= hi - keep):
                raise ValueError(f"map marker {tag} at ({x:.1f}, {y:.1f}) m is not {keep:.0f} m inside the overlay "
                                 f"[{lo}, {hi}]")
            z = float(ground(x, y))
        # an exported marker carries its FO4 type id as a sixth element; the core's fixed four are typed by tag
        sf_type = starfield_type(rest[0]) if rest else fixed_marker_type(tag)
        out.append({"tag": tag, "name": name, "src": f"{src:06X}:Fallout4.esm",
                    "pos": [round(x, 4), round(y, 4), round(z, 4)], "cell": sf_cell(x, y), "type": sf_type})
    if len({m["tag"] for m in out}) != len(out):
        raise ValueError("map marker tags repeat")
    return out


def load_fo4_markers(doc):
    """The rows of a Fo4Land export-mapmarkers document (dotnet/Fo4Land/MapMarkersExport.cs) as overlay_markers
    tuples (tag, name, src, FO4 x, FO4 y, FO4 type id or None), FormID order. A marker without a name is left out (no label to show), and
    so are the core's fixed four (COMMONWEALTH_MARKERS, by source REFR): they stay first, as written before. Returns
    (markers, left out: [{"src", "editor_id", "type_id", "reason"}])."""
    if doc.get("world") != "Commonwealth":
        raise ValueError(f"map markers export of world {doc.get('world')!r}, not Commonwealth")
    fixed = {m[2] for m in COMMONWEALTH_MARKERS}
    out, left = [], []
    for r in doc.get("markers") or []:
        fid = int(r["fid"], 16)
        src = f"{fid:06X}:{doc.get('plugin', 'Fallout4.esm')}"
        who = {"src": src, "editor_id": r.get("editor_id"), "type_id": r.get("type_id")}   # to find a place that went missing
        if fid in fixed:
            left.append(dict(who, reason="one of the core's fixed markers"))
        elif not r.get("name"):
            left.append(dict(who, reason="no name"))
        elif r.get("pos") is None or len(r["pos"]) < 2 or not all(math.isfinite(v) for v in r["pos"][:2]):
            left.append(dict(who, reason="no finite position"))
        else:
            out.append((f"M{fid:06X}", r["name"], fid, float(r["pos"][0]), float(r["pos"][1]), r.get("type_id")))
    return out, left


NEAR_FIXED_M = 100.0    # an exported marker this close to a fixed one, with its name, is that place's second icon


def extra_markers(markers, bounds_m, ground, keep=EDGE_KEEP_M, fixed=(), near_m=NEAR_FIXED_M):
    """overlay_markers for exported markers (load_fo4_markers): a marker less than `keep` inside the overlay is left
    out with its reason instead of stopping the build (the core covers only part of the Commonwealth), and so is one
    within `near_m` of a fixed entry with the same name (overlay_markers output: Red Rocket's sits on the COC arrival,
    not on FO4's own Red Rocket marker, so that one would draw a second icon there), and so is one within `near_m` of an
    earlier kept marker with the same name (FO4's USS Constitution has two markers 4 m apart where the ship comes to
    rest, 1F2637 and 074BE0: one icon is enough). A differently named place close by (the Museum of Freedom in Concord)
    is its own location and stays, and so is a same-named one farther off (FO4's two "Cave" markers, 390 m apart).
    Returns (entries, left out: [{"src", "reason"}])."""
    lo, hi = bounds_m
    inside, left = [], []
    for tag, name, src, fx, fy, *rest in markers:
        x, y = fx / FO4_UNITS_PER_M, fy / FO4_UNITS_PER_M
        near = next((f for f in fixed if f["name"].casefold() == name.casefold()
                     and math.hypot(f["pos"][0] - x, f["pos"][1] - y) < near_m), None)
        twin = next((k for k in inside if k[1].casefold() == name.casefold()
                     and math.hypot(k[3] / FO4_UNITS_PER_M - x, k[4] / FO4_UNITS_PER_M - y) < near_m), None)
        if not (lo + keep <= x <= hi - keep and lo + keep <= y <= hi - keep):
            left.append({"src": f"{src:06X}:Fallout4.esm", "reason": f"outside the overlay ({x:.1f}, {y:.1f}) m"})
        elif near is not None:
            left.append({"src": f"{src:06X}:Fallout4.esm", "reason": f"{name}: within {near_m:.0f} m of the fixed "
                         f"marker {near['tag']}"})
        elif twin is not None:
            left.append({"src": f"{src:06X}:Fallout4.esm", "reason": f"{name}: within {near_m:.0f} m of the kept "
                         f"marker {twin[0]}"})
        else:
            inside.append((tag, name, src, fx, fy, *rest))
    return overlay_markers(None, bounds_m, ground, markers=inside, keep=keep), left


# A ship landing spot as LandingOverlay01 (Starfield.esm 1.16.244, SfInspect landing on the PC, 2026-10-23;
# docs/terrain/map-markers.md "How a vanilla world lands a ship"): (position, rotation) of its pad 093DC9, its
# landing-zone trigger 093DCA, its "Landing Area" map marker 3A866E and the XMarkerHeading 3A8670 that marker links to
LANDING_OVERLAY01 = {
    "pad": ((49.773224, 51.7724, 4.653347), (0.0, 0.0, 6.138185)),
    "trigger": ((49.37545, 52.24151, 12.682769), (0.0, 0.0, 6.1381845)),
    "marker": ((49.277767, 40.811398, 13.383609), (0.0, 0.0, 0.0)),
    "heading": ((87.82548, 78.992676, 5.156708), (0.0, 0.0, 3.7151914)),
}
LANDING_KEEP_M = 100.0  # the pad's box is about 82 m across: the whole spot stays a cell inside the overlay


def landing_spot(x, y, bounds_m, ground, lift, tag="RedRocketNorth", name="Landing Area", keep=LANDING_KEEP_M):
    """dotnet/MapMarkers --landing's spot for a pad at local (x, y): LandingOverlay01's four references moved by the
    same offset, its rotations kept. The pad, and so the trigger and the marker above it, take the ground height at
    (x, y) (LandingOverlay01's pad sits on its ground); the heading takes its own ground plus `lift`, as the markers'
    arrivals do. Raises ValueError for a pad less than `keep` inside the overlay."""
    lo, hi = bounds_m
    if not (lo + keep <= x <= hi - keep and lo + keep <= y <= hi - keep):
        raise ValueError(f"the pad at ({x:.1f}, {y:.1f}) m is less than {keep:.0f} m inside the overlay ({lo}..{hi} m)")
    (px, py, pz), _ = LANDING_OVERLAY01["pad"]
    dz = float(ground(x, y)) - pz
    spot = {"tag": tag, "name": name}
    for part, ((vx, vy, vz), rot) in LANDING_OVERLAY01.items():
        sx, sy = x + vx - px, y + vy - py
        sz = float(ground(sx, sy)) + lift if part == "heading" else vz + dz
        spot[part] = {"pos": [round(sx, 4), round(sy, 4), round(sz, 4)], "rot": list(rot), "cell": sf_cell(sx, sy)}
    return spot
