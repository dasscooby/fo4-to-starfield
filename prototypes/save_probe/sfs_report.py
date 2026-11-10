"""Read-only report on a Starfield save: header, mission script state, timers, and the mission actors' saved positions.

Usage: python sfs_report.py <save.sfs>
The save is opened 'rb' and decompressed in memory; nothing is written.
Heuristics (documented in the output): Papyrus string table by back-walk from the script name; change forms as
RefID(3) flags(4) vsval A, vsval B, vsval C, A*RefID(3), B*u16, 1 byte, then C bytes of data that start with x, y, z, rot.
"""
import sys
import struct
import math
from sfs_lib import decompress, hexdump

path = sys.argv[1]
data = decompress(path)
SPOT = (-2011.142822, -1697.542847, 89.085716)          # Preston's merged spot (the logged move target)
CODS_SPOT = (-2346.708984, -1406.163452, 111.734100)    # Codsworth's merged spot (the logged move target)


def u16s(off):
    ln, = struct.unpack_from("<H", data, off)
    return data[off + 2:off + 2 + ln].decode("latin-1"), off + 2 + ln


# ---------------------------------------------------------------- header
print("FILE", path.replace("\\", "/").split("/")[-1])
assert data[:12] == b"SFS_SAVEGAME"
off = 12 + 4 + 4 + 4 + 4        # header size, version, save number? (layout guessed), then strings
name, o = u16s(25)
print("header: player name=%r" % name)
level, = struct.unpack_from("<I", data, o)
loc, o2 = u16s(o + 4)
played, o3 = u16s(o2)
race, o4 = u16s(o3)
print("header: level=%d location=%r playtime=%r race=%r" % (level, loc, played, race))
gv = data.find(b"1.", o4, o4 + 80)
if gv > 0:
    print("header: game version %r" % data[gv:gv + 10].decode("latin-1"))

# ---------------------------------------------------------------- Papyrus string table
anchor = data.find(b"FO4SF_Min00Quest") - 2


def printable(b):
    return all(32 <= c < 127 for c in b)


lo = anchor - 3_000_000
valid = bytearray(anchor - lo + 1)
valid[anchor - lo] = 1
for p in range(anchor - 2, lo - 1, -1):
    ln = data[p] | (data[p + 1] << 8)
    q = p + 2 + ln
    if q <= anchor and ln < 512 and valid[q - lo] and printable(data[p + 2:q]):
        valid[p - lo] = 1
chain0 = lo + valid.index(1)
first = None
for cand in (chain0, chain0 + 2):
    cnt, = struct.unpack_from("<I", data, cand - 4)
    if 500 < cnt < 200000:
        p = cand
        ok = True
        strs = []
        for _ in range(cnt):
            ln = data[p] | (data[p + 1] << 8)
            s = data[p + 2:p + 2 + ln]
            if ln >= 512 or not printable(s):
                ok = False
                break
            strs.append(s.decode("latin-1"))
            p += 2 + ln
        if ok:
            first, count, end = cand, cnt, p
            break
assert first, "string table not found"
low = {}
for i, s in enumerate(strs):
    low.setdefault(s.lower(), i)
name_idx = low["fo4sf_min00quest"]
print("papyrus: string table at %d, %d strings; script name index %d" % (first, count, name_idx))

# ---------------------------------------------------------------- type entry
tp = data.find(struct.pack("<II", name_idx, low["quest"]), end)
nmem, = struct.unpack_from("<I", data, tp + 8)
members = []
for i in range(nmem):
    n, t = struct.unpack_from("<II", data, tp + 12 + 8 * i)
    members.append((strs[n], strs[t]))
print("papyrus: type FO4SF_Min00Quest extends Quest, %d member variables: %s" % (nmem, ", ".join("%s:%s" % m for m in members)))
has_fix = any(m[0].lower() == "keeperchecks" for m in members) and any(m[0].lower() == "prestonfails" for m in members)
print("papyrus: script build = %s" % ("FIXED 2590549e-style (has keeperChecks and prestonFails)" if has_fix else
                                     "OLD (no keeperChecks / prestonFails members)"))

# ---------------------------------------------------------------- form-id array (from the instance table refs)
inst = []
pos = end
pat = struct.pack("<I", name_idx) + b"\x00\x00\xff\xff"
while True:
    i = data.find(pat, pos)
    if i < 0:
        break
    inst.append((data[i - 8:i], data[i + 8:i + 11]))
    pos = i + 1


def find_array():
    # the two quest ids are XX000800 and XX000814; find XX by the adjacency the instance refs imply
    for prefix in range(2, 0x40):
        k = data.find(struct.pack("<I", (prefix << 24) | 0x814))
        while k >= 0:
            for iid, ref in inst:
                r = (ref[0] << 16) | (ref[1] << 8) | ref[2]
                s = k - 4 * (r - 1)
                if s > 8:
                    cnt, = struct.unpack_from("<I", data, s - 4)
                    if r <= cnt < 4_000_000 and s + 4 * cnt <= len(data):
                        return prefix, s, cnt
            k = data.find(struct.pack("<I", (prefix << 24) | 0x814), k + 1)
    return None


fa = find_array()
assert fa, "form-id array not found"
prefix, S, fcount = fa
print("forms: FO4SFMission.esm load index %02X; form-id array at %d with %d ids" % (prefix, S, fcount))


def formid(refbytes):
    r = (refbytes[0] << 16) | (refbytes[1] << 8) | refbytes[2]
    kind = r >> 22
    if kind == 0:
        return struct.unpack_from("<I", data, S + 4 * (r - 1))[0] if r else 0
    if kind == 1:
        return r & 0x3FFFFF
    if kind == 2:
        return 0xFF000000 | (r & 0x3FFFFF)
    return None


def refid(fid):
    pat = struct.pack("<I", fid)
    i = data.find(pat, S, S + 4 * fcount)
    while i >= 0 and (i - S) % 4:
        i = data.find(pat, i + 1, S + 4 * fcount)
    if i < 0:
        return None
    r = (i - S) // 4 + 1
    return bytes([(r >> 16) & 0xFF, (r >> 8) & 0xFF, r & 0xFF])


# ---------------------------------------------------------------- instances and their member values
def read_members(iid):
    j = data.find(iid + b"\x2b")
    hits = []
    while j >= 0:
        hits.append(j)
        j = data.find(iid + b"\x2b", j + 1)
    out = None
    for j in hits:
        n, = struct.unpack_from("<I", data, j + 9)
        if n != nmem:
            continue
        p = j + 13
        vals = []
        ok = True
        for k in range(n):
            t = data[p]
            if t == 0:
                vals.append(0); p += 1
            elif t == 2:
                vals.append(strs[struct.unpack_from("<I", data, p + 1)[0]]); p += 5
            elif t == 3:
                vals.append(struct.unpack_from("<i", data, p + 1)[0]); p += 5
            elif t == 4:
                vals.append(struct.unpack_from("<f", data, p + 1)[0]); p += 5
            elif t == 5:
                vals.append(bool(data[p + 1])); p += 2
            else:
                ok = False
                break
        if ok:
            out = (j, vals)
    return out


for iid, ref in inst:
    fid = formid(ref)
    got = read_members(iid)
    who = {0x800: "FO4SF_Min00 (the mission)", 0x814: "FO4SF_CodsworthKeeper (the keeper)"}.get(fid & 0xFFFFFF, "?")
    print("papyrus: instance on quest %08X %s" % (fid, who))
    if got:
        j, vals = got
        print("         " + ", ".join("%s=%r" % (members[k][0], vals[k]) for k in range(nmem)))
    else:
        print("         member values not decoded")

# ---------------------------------------------------------------- timers (pattern: ms u32, timer id u32, instance id u64)
for iid, ref in inst:
    fid = formid(ref)
    pos = 0
    while True:
        j = data.find(iid + b"\x00\x00\x00\x00\x00", pos)
        if j < 0:
            break
        ms, tid = struct.unpack_from("<II", data, j - 8)
        if 0 < ms <= 600000 and 0 < tid < 16:
            print("timers: quest %08X has timer id %d with %d ms left" % (fid, tid, ms))
        pos = j + 1


# ---------------------------------------------------------------- change forms
def vsval(p):
    b0 = data[p]
    k = b0 & 3
    if k == 0:
        return b0 >> 2, p + 1
    if k == 1:
        return (b0 | (data[p + 1] << 8)) >> 2, p + 2
    return (b0 | (data[p + 1] << 8) | (data[p + 2] << 16)) >> 2, p + 3


def change_form(rb, want_first=None):
    """Find the change form whose header starts with this RefID; returns (offset, flags, A, B, C, data offset)."""
    pos = 0
    best = []
    while True:
        h = data.find(rb, pos, S)
        if h < 0:
            break
        pos = h + 1
        flags, = struct.unpack_from("<I", data, h + 3)
        try:
            a, p = vsval(h + 7)
            b, p = vsval(p)
            c, p = vsval(p)
        except IndexError:
            continue
        d = p + a * 3 + b * 2 + 1
        if d + 16 > len(data) or c < 16 or a > 5000 or b > 5000:
            continue
        x, y, z, r = struct.unpack_from("<4f", data, d)
        if all(math.isfinite(v) for v in (x, y, z, r)) and 50 < abs(x) < 20000 and 50 < abs(y) < 20000 and abs(z) < 3000 and abs(r) < 7:
            best.append((h, flags, a, b, c, d, (x, y, z), r))
    return best


def show(label, fid, spot=None):
    rb = refid(fid)
    if not rb:
        print("actors: %-10s %08X not in the form-id array" % (label, fid))
        return None
    cf = change_form(rb)
    if not cf:
        print("actors: %-10s %08X refid %s: no change form with a position found" % (label, fid, rb.hex()))
        return None
    for h, flags, a, b, c, d, xyz, r in cf[:2]:
        extra = ""
        if spot:
            extra = "  | from its merged spot: %.1f m (dx=%+.1f dy=%+.1f dz=%+.1f)" % (
                math.dist(xyz, spot), xyz[0] - spot[0], xyz[1] - spot[1], xyz[2] - spot[2])
        print("actors: %-10s %08X pos=(%.2f, %.2f, %.2f) heading=%.3f rad (%.0f deg) flags=%08X%s" % (
            label, fid, xyz[0], xyz[1], xyz[2], r, math.degrees(r) % 360, flags, extra))
    return cf[0][6]


pre = show("Preston", (prefix << 24) | 0x802, SPOT)
for k in range(5):
    show("raider %d" % k, (prefix << 24) | (0x803 + k))
cod = show("Codsworth", (prefix << 24) | 0x811, CODS_SPOT)
# the player: RefID 40 00 14 (Starfield.esm 000014)
pl = change_form(bytes([0x40, 0x00, 0x14]))
ppos = None
for h, flags, a, b, c, d, xyz, r in pl[:3]:
    print("actors: player     00000014 pos=(%.2f, %.2f, %.2f) heading=%.3f rad (%.0f deg) flags=%08X  | from Preston's merged spot %.1f m" % (
        xyz[0], xyz[1], xyz[2], r, math.degrees(r) % 360, flags, math.dist(xyz, SPOT)))
    if ppos is None:
        ppos = xyz
if ppos and pre:
    print("derived: player to Preston %.1f m (3D); horizontal %.1f m; Preston is %+.1f m in z relative to the player" % (
        math.dist(ppos, pre), math.hypot(ppos[0] - pre[0], ppos[1] - pre[1]), pre[2] - ppos[2]))
if ppos and cod:
    print("derived: player to Codsworth %.1f m" % math.dist(ppos, cod))
