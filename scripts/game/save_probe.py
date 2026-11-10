#!/usr/bin/env python3
"""Read-only probe of a Starfield .sfs save: mission script state, timers and the mission actors' positions.

Usage:
    python3 scripts/game/save_probe.py <save.sfs> [--spot NAME=X,Y,Z ...] [--spots spots.json]
                                       [--plugin-index HEX] [--json out.json]

The save is opened 'rb' and handled in memory. The only file this tool ever writes is the optional
--json report (and it refuses to overwrite the save itself).

Spots (the places the actors should stand) are never built in: pass --spot NAME=X,Y,Z (repeatable) or a
small JSON file {"Preston": [x, y, z], ...}. NAME is matched, ignoring case, to an actor label
(Preston, Codsworth, raider 0..4) or, for the player, every spot is reported. Without spots the
positions are still reported, just without distances.

Exit status: 0 report written, 1 the file is not a save / is truncated / cannot be read, 2 bad arguments.

HEURISTICS. Nothing here comes from a published format description; each lookup below was worked out
from saves and is labelled in the code with "HEURISTIC". A lookup that fails is reported as "not found"
or "not decoded" in the report; it does not abort the run.
  * header strings:   the player-name string is assumed to start at byte 25 of the decompressed save, then
                      level (u32), location, play time and race as u16-length strings; the game version is
                      the first dotted number within 80 bytes after those.
  * Papyrus strings:  the string table is found by walking u16-length printable strings backwards from the
                      script name, then checked against the u32 count in front of it.
  * script type:      the (name, parent) string-index pair, a u32 member count, then (name, type) pairs.
  * instances:        records "u64 id, u32 script-name index, 00 00 FF FF, 3-byte form ref".
  * member values:    "u64 id, 0x2B, u32 count, values"; value type codes 0 (none), 2 (string index),
                      3 (int), 4 (float), 5 (bool) are decoded. Any other code (1 is an object reference,
                      and object properties are declared first in the script) has an unknown width, so that
                      member and every member after it are reported as "not decoded".
  * timers:           "u32 ms, u32 timer id, u64 instance id, five 00 bytes", ms in (0, 600000], id 1..15.
  * form-id array:    u32 count then u32 ids, found by a quest's form id (plugin index x 2^24 + local id)
                      matching an instance's 1-based ref; the plugin load index comes out of that match.
  * change forms:     "3-byte RefID, u32 flags, vsval A, B, C, A*3 bytes, B*2 bytes, 1 byte, C data bytes
                      starting with x, y, z, heading (floats)", accepted only if the floats are finite and
                      plausible. A 4-byte vsval (kind 3) is read like kind 2 (3 bytes); not verified.
  * quest stage flags: NOT decoded (the QUST change-form layout is not verified). The report says so and gives
                      `script_stage` instead: the mission script's own `applied` member, i.e. the last stage
                      the mission script applied (set on every OnStageSet). It is not the engine's stage flag.
"""
import argparse
import json
import math
import os
import re
import struct
import sys
import zlib

SCRIPT_NAME = "FO4SF_Min00Quest"
PARENT_TYPE = "Quest"
QUEST_NAME = "FO4SF_Min00"

# Plugin-local form ids of the mission plugin (from the prototype in claude/save-probe-prototype).
# They are plugin content, not a load order position: the load index is found from the save.
MISSION_QUEST_LOCAL = 0x800
KEEPER_QUEST_LOCAL = 0x814
ACTOR_LOCALS = [("Preston", 0x802)] + [("raider %d" % k, 0x803 + k) for k in range(5)] + [("Codsworth", 0x811)]
PLAYER_REFID = bytes([0x40, 0x00, 0x14])     # Starfield.esm 000014

_PRINTABLE = re.compile(rb"[\x20-\x7e]*")
_VERSION = re.compile(rb"\d+\.\d+\.\d+(?:\.\d+)?")


class SaveError(Exception):
    """The file cannot be read as a Starfield save."""


# ------------------------------------------------------------------ container


def decode_container(raw):
    """BCPS container (zlib or stored chunks) -> the plain save bytes. A plain SFS_SAVEGAME passes through."""
    if raw[:12] == b"SFS_SAVEGAME":
        return bytes(raw)
    if raw[:4] != b"BCPS":
        raise SaveError("not a Starfield save (neither a BCPS container nor SFS_SAVEGAME)")
    if len(raw) < 64:
        raise SaveError("truncated save: container header is %d bytes, 64 needed" % len(raw))
    sizes_off, = struct.unpack_from("<Q", raw, 8)
    data_off, = struct.unpack_from("<Q", raw, 24)
    total, = struct.unpack_from("<Q", raw, 32)
    chunk, = struct.unpack_from("<Q", raw, 48)
    pad, = struct.unpack_from("<Q", raw, 56)
    if chunk == 0 or total > (1 << 33):
        raise SaveError("not a usable save: implausible container header (chunk %d, size %d)" % (chunk, total))
    n = (total + chunk - 1) // chunk
    if sizes_off + 4 * n > len(raw) or data_off > len(raw):
        raise SaveError("truncated save: chunk table runs past the end of the file")
    sizes = struct.unpack_from("<%dI" % n, raw, sizes_off)
    out = bytearray()
    pos = data_off
    for i, s in enumerate(sizes):
        if pos + s > len(raw):
            raise SaveError("truncated save: chunk %d of %d needs bytes up to %d, file has %d" % (i + 1, n, pos + s, len(raw)))
        part = raw[pos:pos + s]
        want = min(chunk, total - len(out))
        if s == want:                      # stored chunk (it did not compress)
            out += part
        else:
            try:
                out += zlib.decompress(part)
            except zlib.error as e:
                raise SaveError("damaged save: chunk %d does not decompress (%s)" % (i + 1, e))
        pos += s
        if pad:
            pos = (pos + pad - 1) // pad * pad
    if len(out) != total:
        raise SaveError("damaged save: decompressed %d bytes, header says %d" % (len(out), total))
    if out[:12] != b"SFS_SAVEGAME":
        raise SaveError("not a Starfield save: container does not hold SFS_SAVEGAME")
    return bytes(out)


def load_save(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise SaveError("cannot read %s: %s" % (path, e))
    return decode_container(raw)


# ------------------------------------------------------------------ header


def parse_header(data):
    """HEURISTIC: strings start at byte 25; see the module docstring."""
    def u16s(off):
        ln, = struct.unpack_from("<H", data, off)
        if off + 2 + ln > len(data):
            raise ValueError("string runs past the end")
        s = data[off + 2:off + 2 + ln]
        if not _PRINTABLE.fullmatch(s):
            raise ValueError("string is not printable")
        return s.decode("latin-1"), off + 2 + ln
    try:
        name, o = u16s(25)
        level, = struct.unpack_from("<I", data, o)
        loc, o = u16s(o + 4)
        played, o = u16s(o)
        race, o = u16s(o)
    except (struct.error, ValueError):
        return None
    m = _VERSION.search(data, o, o + 80)
    return {"player": name, "level": level, "location": loc, "play_time": played, "race": race,
            "game_version": m.group(0).decode("ascii") if m else None}


# ------------------------------------------------------------------ Papyrus string table


def find_string_table(data, script_name):
    """HEURISTIC. Returns (strings, start offset, end offset, index of script_name) or None."""
    needle = script_name.encode("latin-1")
    lead = struct.pack("<H", len(needle))
    tried = 0
    a = data.find(needle)
    while a >= 0 and tried < 8:
        anchor = a - 2
        if anchor >= 0 and data[anchor:a] == lead:
            tried += 1
            found = _table_from_anchor(data, anchor, script_name)
            if found:
                return found
        a = data.find(needle, a + 1)
    return None


def _table_from_anchor(data, anchor, script_name):
    lo = max(0, anchor - 3_000_000)
    valid = bytearray(anchor - lo + 1)
    valid[anchor - lo] = 1
    for p in range(anchor - 2, lo - 1, -1):
        ln = data[p] | (data[p + 1] << 8)
        q = p + 2 + ln
        if q <= anchor and ln < 512 and valid[q - lo] and _PRINTABLE.fullmatch(data, p + 2, q):
            valid[p - lo] = 1
    try:
        chain0 = lo + valid.index(1)
    except ValueError:
        return None
    for cand in range(chain0, chain0 + 7, 2):      # the chain may start inside the u32 count
        if cand < 4 or cand > anchor:
            continue
        cnt, = struct.unpack_from("<I", data, cand - 4)
        if not 1 <= cnt <= 1_000_000:
            continue
        p = cand
        strs, starts = [], set()
        ok = True
        for _ in range(cnt):
            if p + 2 > len(data):
                ok = False
                break
            ln = data[p] | (data[p + 1] << 8)
            if ln >= 512 or p + 2 + ln > len(data) or not _PRINTABLE.fullmatch(data, p + 2, p + 2 + ln):
                ok = False
                break
            starts.add(p)
            strs.append(data[p + 2:p + 2 + ln].decode("latin-1"))
            p += 2 + ln
        if ok and anchor in starts:
            idx = strs.index(script_name) if script_name in strs else None
            if idx is not None:
                return strs, cand, p, idx
    return None


# ------------------------------------------------------------------ script type, instances, members


def find_type(data, strs, name_idx, parent, end):
    """HEURISTIC. -> list of (member name, declared type) or None."""
    low = {}
    for i, s in enumerate(strs):
        low.setdefault(s.lower(), i)
    if parent.lower() not in low:
        return None
    tp = data.find(struct.pack("<II", name_idx, low[parent.lower()]), end)
    if tp < 0 or tp + 12 > len(data):
        return None
    n, = struct.unpack_from("<I", data, tp + 8)
    if n > 4096 or tp + 12 + 8 * n > len(data):
        return None
    out = []
    for i in range(n):
        a, b = struct.unpack_from("<II", data, tp + 12 + 8 * i)
        if a >= len(strs) or b >= len(strs):
            return None
        out.append((strs[a], strs[b]))
    return out


def find_instances(data, name_idx, start):
    """HEURISTIC. -> list of (instance id bytes, 3-byte form ref), deduplicated by id."""
    pat = struct.pack("<I", name_idx) + b"\x00\x00\xff\xff"
    seen, out = set(), []
    pos = start
    while True:
        i = data.find(pat, pos)
        if i < 0:
            break
        pos = i + 1
        if i < 8 or i + 11 > len(data):
            continue
        iid = data[i - 8:i]
        if iid in seen:
            continue
        seen.add(iid)
        out.append((iid, data[i + 8:i + 11]))
    return out


def decode_members(data, p, members, strs):
    """Decode values from offset p. A type code of unknown width stops decoding there: that member and the
    rest are 'not decoded'. Returns a list of dicts."""
    out = []
    stop = None
    for name, declared in members:
        entry = {"name": name, "declared_type": declared, "decoded": False, "value": None}
        out.append(entry)
        if stop is not None:
            entry["note"] = "not decoded (after unknown type code %d)" % stop
            continue
        try:
            t = data[p]
            if t == 0:
                entry.update(decoded=True, value=None, note="none")
                p += 1
            elif t == 2:
                idx, = struct.unpack_from("<I", data, p + 1)
                if idx >= len(strs):
                    raise ValueError("string index out of range")
                entry.update(decoded=True, value=strs[idx])
                p += 5
            elif t == 3:
                entry.update(decoded=True, value=struct.unpack_from("<i", data, p + 1)[0])
                p += 5
            elif t == 4:
                entry.update(decoded=True, value=round(struct.unpack_from("<f", data, p + 1)[0], 6))
                p += 5
            elif t == 5:
                entry.update(decoded=True, value=bool(data[p + 1]))
                p += 2
            else:
                stop = t
                entry["note"] = "not decoded (type code %d)" % t
        except (IndexError, struct.error, ValueError):
            stop = -1
            entry["note"] = "not decoded (ran out of data)"
    return out


def read_members(data, iid, members, strs):
    """HEURISTIC. Best decoding among the places where 'iid 0x2B count' appears with the right count."""
    best, best_n = None, -1
    pos = 0
    key = iid + b"\x2b"
    while True:
        j = data.find(key, pos)
        if j < 0:
            break
        pos = j + 1
        if j + 13 > len(data):
            continue
        n, = struct.unpack_from("<I", data, j + 9)
        if n != len(members):
            continue
        got = decode_members(data, j + 13, members, strs)
        ok = sum(1 for g in got if g["decoded"])
        if ok >= best_n:
            best, best_n = got, ok
    return best


def find_timers(data, iid):
    """HEURISTIC. -> [{"timer_id", "ms_left"}]"""
    out, seen = [], set()
    pos = 0
    key = iid + b"\x00" * 5
    while True:
        j = data.find(key, pos)
        if j < 0:
            break
        pos = j + 1
        if j < 8:
            continue
        ms, tid = struct.unpack_from("<II", data, j - 8)
        if 0 < ms <= 600000 and 0 < tid < 16 and (tid, ms) not in seen:
            seen.add((tid, ms))
            out.append({"timer_id": tid, "ms_left": ms})
    return out


# ------------------------------------------------------------------ form ids and change forms


def ref_kind(ref):
    return ((ref[0] << 16) | (ref[1] << 8) | ref[2]) >> 22


def ref_value(ref):
    return (ref[0] << 16) | (ref[1] << 8) | ref[2]


def find_form_array(data, instances, local_ids, plugin_index=None):
    """HEURISTIC. -> (plugin index, array start offset, count) or None.

    A plugin index p and a local id L are right when the instance's 1-based ref r satisfies: the u32 at
    (array start + 4*(r-1)) is p<<24 | L and the u32 in front of the array start is a count >= r."""
    prefixes = [plugin_index] if plugin_index is not None else range(1, 0xFE)
    for prefix in prefixes:
        for local in local_ids:
            want = struct.pack("<I", (prefix << 24) | local)
            k = data.find(want)
            while k >= 0:
                for _iid, ref in instances:
                    if ref_kind(ref) != 0:
                        continue
                    r = ref_value(ref)
                    s = k - 4 * (r - 1)
                    if r >= 1 and s >= 8:
                        cnt, = struct.unpack_from("<I", data, s - 4)
                        if r <= cnt < 4_000_000 and s + 4 * cnt <= len(data):
                            return prefix, s, cnt
                k = data.find(want, k + 1)
    return None


def resolve_ref(data, arr_start, arr_count, ref):
    r = ref_value(ref)
    kind = r >> 22
    if kind == 0:
        if r == 0 or r > arr_count:
            return None
        return struct.unpack_from("<I", data, arr_start + 4 * (r - 1))[0]
    if kind == 1:
        return r & 0x3FFFFF
    if kind == 2:
        return 0xFF000000 | (r & 0x3FFFFF)
    return None


def refid_for(data, arr_start, arr_count, form_id):
    pat = struct.pack("<I", form_id)
    end = arr_start + 4 * arr_count
    i = data.find(pat, arr_start, end)
    while i >= 0 and (i - arr_start) % 4:
        i = data.find(pat, i + 1, end)
    if i < 0:
        return None
    r = (i - arr_start) // 4 + 1
    return bytes([(r >> 16) & 0xFF, (r >> 8) & 0xFF, r & 0xFF])


def _vsval(data, p):
    b0 = data[p]
    kind = b0 & 3
    if kind == 0:
        return b0 >> 2, p + 1
    if kind == 1:
        return (b0 | (data[p + 1] << 8)) >> 2, p + 2
    return (b0 | (data[p + 1] << 8) | (data[p + 2] << 16)) >> 2, p + 3


def find_positions(data, refbytes, limit):
    """HEURISTIC. Change forms starting with this RefID that carry a plausible position.
    -> [{"offset", "flags", "pos": (x, y, z), "heading"}]; only the region before `limit` is searched."""
    out = []
    pos = 0
    while True:
        h = data.find(refbytes, pos, limit)
        if h < 0:
            break
        pos = h + 1
        try:
            flags, = struct.unpack_from("<I", data, h + 3)
            a, p = _vsval(data, h + 7)
            b, p = _vsval(data, p)
            c, p = _vsval(data, p)
            d = p + a * 3 + b * 2 + 1
            if d + 16 > len(data) or c < 16 or a > 5000 or b > 5000:
                continue
            x, y, z, rot = struct.unpack_from("<4f", data, d)
        except (IndexError, struct.error):
            continue
        if all(math.isfinite(v) for v in (x, y, z, rot)) and 50 < abs(x) < 20000 and 50 < abs(y) < 20000 \
                and abs(z) < 3000 and abs(rot) < 7:
            out.append({"offset": h, "flags": flags, "pos": (x, y, z), "heading": rot})
    return out


# ------------------------------------------------------------------ report


def _spot_for(spots, label):
    for k, v in spots.items():
        if k.lower() == label.lower():
            return v
    return None


def _actor_entry(label, fid, hit, spot):
    x, y, z = hit["pos"]
    e = {"label": label, "form_id": "%08X" % fid if fid is not None else None,
         "pos": [round(x, 2), round(y, 2), round(z, 2)],
         "heading_rad": round(hit["heading"], 3), "heading_deg": round(math.degrees(hit["heading"]) % 360),
         "change_flags": "%08X" % hit["flags"], "spot": None, "from_spot_m": None}
    if spot:
        e["spot"] = list(spot)
        e["from_spot_m"] = round(math.dist(hit["pos"], spot), 1)
    return e


def build_report(data, spots=None, plugin_index=None, file_name=""):
    spots = spots or {}
    rep = {"file": file_name, "header": parse_header(data), "plugin_index": None, "script": None,
           "quest_stage": {"quest": QUEST_NAME, "decoded": False,
                           "note": "engine stage flags not decoded (quest change-form layout not verified); "
                                   "use script_stage"},
           "script_stage": None,
           "instances": [], "actors": [], "player": [], "warnings": []}
    w = rep["warnings"]
    if rep["header"] is None:
        w.append("header strings not decoded")

    st = find_string_table(data, SCRIPT_NAME)
    if not st:
        w.append("script %s not found in this save (mission not started, or the string table was not located)" % SCRIPT_NAME)
        _player_only(data, rep, spots, len(data))
        return rep
    strs, st_start, st_end, name_idx = st
    members = find_type(data, strs, name_idx, PARENT_TYPE, st_end)
    rep["script"] = {"name": SCRIPT_NAME, "string_table_offset": st_start, "string_count": len(strs),
                     "name_index": name_idx,
                     "members": [{"name": n, "declared_type": t} for n, t in members] if members else None}
    if not members:
        w.append("script type entry (member list) not found")
        members = []
    insts = find_instances(data, name_idx, st_end)
    if not insts:
        w.append("no script instances found")

    fa = find_form_array(data, insts, [KEEPER_QUEST_LOCAL, MISSION_QUEST_LOCAL], plugin_index) if insts else None
    arr_start = arr_count = None
    limit = len(data)
    if fa:
        rep["plugin_index"] = "%02X" % fa[0]
        _, arr_start, arr_count = fa
        limit = arr_start
        rep["form_array"] = {"offset": arr_start, "count": arr_count}
    else:
        w.append("mission plugin load index / form-id array not found")

    for iid, ref in insts:
        fid = resolve_ref(data, arr_start, arr_count, ref) if fa else None
        local = fid & 0xFFFFFF if fid is not None else None
        role = "unknown"
        if local == MISSION_QUEST_LOCAL:
            role = "mission"
        elif local == KEEPER_QUEST_LOCAL:
            role = "keeper"
        vals = read_members(data, iid, members, strs) if members else None
        rep["instances"].append({"instance_id": iid.hex(), "quest_form": "%08X" % fid if fid is not None else None,
                                 "role": role, "members": vals, "timers": find_timers(data, iid)})
        if vals is None and members:
            w.append("instance %s: member values not found" % iid.hex())
        elif vals and not all(v["decoded"] for v in vals):
            w.append("instance %s: some member values not decoded" % iid.hex())

    for inst in rep["instances"]:
        if inst["role"] == "mission" and inst["members"]:
            for m in inst["members"]:
                if m["name"].lower() == "applied" and m["decoded"]:
                    rep["script_stage"] = {"value": m["value"], "source": "mission script member `applied`",
                                           "description": "the last stage the mission script applied"}
    if fa:
        prefix = fa[0]
        for label, local in ACTOR_LOCALS:
            fid = (prefix << 24) | local
            rb = refid_for(data, arr_start, arr_count, fid)
            if rb is None:
                rep["actors"].append({"label": label, "form_id": "%08X" % fid, "found": False,
                                      "note": "not in the form-id array"})
                continue
            hits = find_positions(data, rb, limit)
            if not hits:
                rep["actors"].append({"label": label, "form_id": "%08X" % fid, "found": False,
                                      "note": "no change form with a position found"})
                continue
            rep["actors"].append(dict(_actor_entry(label, fid, hits[0], _spot_for(spots, label)), found=True,
                                      other_candidates=len(hits) - 1))
    _player_only(data, rep, spots, limit)
    return rep


def _player_only(data, rep, spots, limit):
    hits = find_positions(data, PLAYER_REFID, limit)
    if not hits:
        rep["warnings"].append("player position not found")
        return
    h = hits[0]
    e = _actor_entry("player", 0x14, h, None)
    e["from_spots_m"] = {k: round(math.dist(h["pos"], v), 1) for k, v in spots.items()}
    e["other_candidates"] = len(hits) - 1
    rep["player"].append(e)


def format_report(rep):
    L = ["FILE %s" % rep["file"]]
    h = rep["header"]
    if h:
        L.append("header: player=%r level=%d location=%r play time=%r game version=%s" % (
            h["player"], h["level"], h["location"], h["play_time"], h["game_version"] or "not found"))
    else:
        L.append("header: not decoded")
    L.append("mission plugin load index: %s" % (rep["plugin_index"] or "not found"))
    s = rep["script"]
    if s:
        L.append("script %s: %d strings, %s member variables" % (s["name"], s["string_count"],
                                                                 len(s["members"]) if s["members"] is not None else "?"))
    L.append("quest %s stage flags: %s" % (rep["quest_stage"]["quest"], rep["quest_stage"]["note"]))
    ss = rep["script_stage"]
    L.append("script_stage: %s (the last stage the mission script applied)" % (ss["value"] if ss else "not found"))
    for i in rep["instances"]:
        L.append("instance %s on quest %s (%s):" % (i["instance_id"], i["quest_form"] or "?", i["role"]))
        if i["members"] is None:
            L.append("    member values not found")
        else:
            parts = []
            for m in i["members"]:
                parts.append("%s=%r" % (m["name"], m["value"]) if m["decoded"] else "%s=<%s>" % (m["name"], m["note"]))
            L.append("    " + ", ".join(parts))
        for t in i["timers"]:
            L.append("    timer %d: %d ms left" % (t["timer_id"], t["ms_left"]))
    for a in rep["actors"] + rep["player"]:
        if a.get("found") is False:
            L.append("actor %-10s %s: %s" % (a["label"], a["form_id"], a["note"]))
            continue
        line = "actor %-10s %s pos=(%.2f, %.2f, %.2f) heading=%d deg flags=%s" % (
            a["label"], a["form_id"], a["pos"][0], a["pos"][1], a["pos"][2], a["heading_deg"], a["change_flags"])
        if a["from_spot_m"] is not None:
            line += " | %.1f m from spot (%.2f, %.2f, %.2f)" % (a["from_spot_m"], *a["spot"])
        if a.get("from_spots_m"):
            line += " | " + ", ".join("%.1f m from %s" % (d, k) for k, d in a["from_spots_m"].items())
        L.append(line)
    for w in rep["warnings"]:
        L.append("warning: %s" % w)
    return "\n".join(L)


# ------------------------------------------------------------------ command line


def _parse_spot(text):
    try:
        name, xyz = text.split("=", 1)
        x, y, z = (float(v) for v in xyz.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected NAME=X,Y,Z, got %r" % text)
    return name.strip(), (x, y, z)


def load_spots(spot_args, spots_file):
    spots = {}
    if spots_file:
        try:
            with open(spots_file, encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                x, y, z = (float(c) for c in v)
                spots[str(k)] = (x, y, z)
        except (OSError, ValueError, TypeError, AttributeError) as e:
            raise SaveError("cannot use spots file %s: %s" % (spots_file, e))
    for name, xyz in spot_args or []:
        spots[name] = xyz
    return spots


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only probe of a Starfield save (mission state, actor positions).")
    ap.add_argument("save", help="path to the .sfs save (opened read-only)")
    ap.add_argument("--spot", action="append", type=_parse_spot, metavar="NAME=X,Y,Z",
                    help="where an actor should stand; repeatable")
    ap.add_argument("--spots", metavar="FILE", help='JSON file {"Preston": [x, y, z], ...}')
    ap.add_argument("--plugin-index", metavar="HEX", help="mission plugin load index; found from the save if omitted")
    ap.add_argument("--json", metavar="OUT", help="also write the report as JSON to this file")
    args = ap.parse_args(argv)
    try:
        idx = int(args.plugin_index, 16) if args.plugin_index else None
        if idx is not None and not 0 < idx < 0xFE:
            raise ValueError
    except ValueError:
        ap.error("--plugin-index must be a hex number between 01 and FD")
    if args.json and os.path.realpath(args.json) == os.path.realpath(args.save):
        ap.error("--json would overwrite the save")
    try:
        spots = load_spots(args.spot, args.spots)
        data = load_save(args.save)
    except SaveError as e:
        print("save_probe: %s" % e, file=sys.stderr)
        return 1
    rep = build_report(data, spots, idx, os.path.basename(args.save))
    print(format_report(rep))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
