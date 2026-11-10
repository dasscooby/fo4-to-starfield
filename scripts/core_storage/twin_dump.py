"""The override beside its twin (FAL-273 item 3, #707): what does FO4SFCoreStorage.esm write for the core's world and spawn
cell that the core itself does not, subrecord by subrecord and group by group. Raw bytes only: no Mutagen, no game.

usage: python scripts/core_storage/twin_dump.py <FO4SFCoreStorage.esm> <FO4TerrainCore.esm> [--edid FO4Core_RedRocketSpawn]
                                                [--out <report.txt>] [--bytes 24]

For each override record of the plugin that names a record of the core (a form id whose load index is the core's own: the
WRLD and the CELL) the report prints, from the plugin and from the core:
  * where it sits: the chain of enclosing GRUPs (type and label) from the top of the file;
  * the record header: flags, version, version-control info, data size, compressed or not;
  * every subrecord side by side: signature, size, the first bytes as hex, and one verdict:
        same | differs (size or bytes) | ONLY IN THE CORE (the override lost it) | only in the override
  * for the core's cell: its child groups (persistent, temporary: how many records of each signature), which an override
    that carries its own children sits beside; for the plugin the same list.
The report holds record bytes of the game: it stays on the PC, only the verdicts and offsets go to Git. Whether a difference
is the cause of the crash of #707 is for the reader of the report to say (read of 0x1f0 at Starfield.exe+0x41efd6 on a worker
thread, 32 s after the arrival, with this plugin and not without it); this tool only shows the differences.
"""
import argparse
import mmap
import struct
import sys
import zlib

COMPRESSED = 0x00040000
GROUP_NAMES = {0: "top", 1: "world children", 2: "interior block", 3: "interior sub-block", 4: "exterior block",
               5: "exterior sub-block", 6: "cell children", 7: "topic children", 8: "cell persistent children",
               9: "cell temporary children", 10: "cell visible-distant children"}


class Rec:
    """One record: its place (the GRUP chain), header fields and subrecords [(signature, bytes)]."""

    def __init__(self, sig, flags, form, vc, version, size, chain, body, offset):
        self.sig, self.flags, self.form, self.vc, self.version, self.size = sig, flags, form, vc, version, size
        self.chain, self.offset = chain, offset
        self.compressed = bool(flags & COMPRESSED)
        self.error = ""
        self.subs = []
        try:
            raw = body
            if self.compressed:
                raw = zlib.decompress(body[4:])
            self.subs = parse_subrecords(raw)
        except Exception as e:      # an unreadable body is reported, not hidden
            self.error = f"{type(e).__name__}: {e}"

    @property
    def edid(self):
        for s, b in self.subs:
            if s == b"EDID":
                return b.rstrip(b"\0").decode("latin-1")
        return ""


def parse_subrecords(raw):
    out, pos, big = [], 0, None
    while pos + 6 <= len(raw):
        sig = raw[pos:pos + 4]
        n = struct.unpack_from("<H", raw, pos + 4)[0]
        if sig == b"XXXX":
            big = struct.unpack_from("<I", raw, pos + 6)[0]
            pos += 6 + n
            continue
        if big is not None:
            n, big = big, None
        out.append((sig, bytes(raw[pos + 6:pos + 6 + n])))
        pos += 6 + n
    if pos != len(raw):
        raise ValueError(f"{len(raw) - pos} bytes after the last subrecord")
    return out


def masters(data):
    size = struct.unpack_from("<I", data, 4)[0]
    body, pos, out = data[24:24 + size], 0, []
    while pos + 6 <= len(body):
        sig, n = body[pos:pos + 4], struct.unpack_from("<H", body, pos + 4)[0]
        if sig == b"MAST":
            out.append(bytes(body[pos + 6:pos + 6 + n]).rstrip(b"\0").decode("latin-1"))
        pos += 6 + n
    return out


def walk(data, want=None, skip_types=()):
    """Yield every record (Rec) of a plugin, depth first, with the GRUP chain that encloses it. want: a set of
    (signature, object id) or a predicate(sig, form): only those records are decoded, every other one is skipped by its size
    (a 600 MB core is walked in seconds). skip_types: GRUP types whose content is not entered."""
    stack = [(0, len(data), ())]
    while stack:
        pos, end, chain = stack.pop()
        pending = []
        while pos < end:
            sig, size = bytes(data[pos:pos + 4]), struct.unpack_from("<I", data, pos + 4)[0]
            if sig == b"GRUP":
                label = bytes(data[pos + 8:pos + 12])
                gtype = struct.unpack_from("<I", data, pos + 12)[0]
                if gtype not in skip_types and size >= 24:
                    pending.append((pos + 24, pos + size, chain + ((gtype, label),)))
                pos += size
                continue
            flags, form, vc, version = struct.unpack_from("<IIIH", data, pos + 8)
            if want is None or want(sig, form):
                yield Rec(sig, flags, form, vc, version, size, chain, bytes(data[pos + 24:pos + 24 + size]), pos)
            pos += 24 + size
        stack.extend(reversed(pending))


def child_inventory(data, cell_form):
    """{GRUP type: {signature: count}} of the groups that belong to the cell (children of CELL cell_form)."""
    out, stack = {}, [(0, len(data))]
    while stack:
        pos, end = stack.pop()
        while pos < end:
            sig, size = bytes(data[pos:pos + 4]), struct.unpack_from("<I", data, pos + 4)[0]
            if sig == b"GRUP":
                label = struct.unpack_from("<I", data, pos + 8)[0]
                gtype = struct.unpack_from("<I", data, pos + 12)[0]
                if gtype == 6 and label == cell_form:
                    tally(data, pos + 24, pos + size, out)
                elif gtype in (0, 1, 4, 5):
                    stack.append((pos + 24, pos + size))
                pos += size
            else:
                pos += 24 + size
    return out


def tally(data, pos, end, out):
    while pos < end:
        sig, size = bytes(data[pos:pos + 4]), struct.unpack_from("<I", data, pos + 4)[0]
        if sig == b"GRUP":
            gtype = struct.unpack_from("<I", data, pos + 12)[0]
            seen = out.setdefault(gtype, {})
            inner = pos + 24
            while inner < pos + size:
                s2, n2 = bytes(data[inner:inner + 4]), struct.unpack_from("<I", data, inner + 4)[0]
                if s2 == b"GRUP":
                    inner += n2
                    continue
                seen[s2.decode("latin-1")] = seen.get(s2.decode("latin-1"), 0) + 1
                inner += 24 + n2
            pos += size
        else:
            pos += 24 + size


def chain_text(chain):
    return " > ".join(f"GRUP {GROUP_NAMES.get(t, t)} {lab.hex() if t not in (1, 6, 8, 9) else '%08X' % struct.unpack('<I', lab)[0]}" for t, lab in chain) or "(top level)"


def hexhead(b, n):
    return b[:n].hex(" ") + (" ..." if len(b) > n else "")


def compare(core_rec, over_rec, nbytes):
    """The side-by-side lines of two records and the list of verdicts that are differences."""
    lines, diffs = [], []
    cs, os_ = core_rec.subs, over_rec.subs
    used = set()
    for sig, b in cs:
        match = next((i for i, (s2, b2) in enumerate(os_) if s2 == sig and i not in used), None)
        if match is None:
            lines.append(f"  {sig.decode('latin-1')}  core {len(b):>6} B  {hexhead(b, nbytes)}   ->  ONLY IN THE CORE (the override lost it)")
            diffs.append(f"{sig.decode('latin-1')} only in the core")
            continue
        used.add(match)
        b2 = os_[match][1]
        if b == b2:
            lines.append(f"  {sig.decode('latin-1')}  {len(b):>6} B  same")
        else:
            at = next((i for i in range(min(len(b), len(b2))) if b[i] != b2[i]), min(len(b), len(b2)))
            lines.append(f"  {sig.decode('latin-1')}  core {len(b):>6} B  override {len(b2):>6} B  differs at byte {at}: core {hexhead(b[at:], nbytes)} | override {hexhead(b2[at:], nbytes)}")
            diffs.append(f"{sig.decode('latin-1')} differs at byte {at}")
    for i, (sig, b) in enumerate(os_):
        if i not in used:
            lines.append(f"  {sig.decode('latin-1')}  override {len(b):>6} B  {hexhead(b, nbytes)}   ->  only in the override")
            diffs.append(f"{sig.decode('latin-1')} only in the override")
    shared = {s for s, _ in cs} & {s for s, _ in os_}
    if [s for s, _ in cs if s in shared] != [s for s, _ in os_ if s in shared]:
        diffs.append("subrecord order differs")
        lines.append("  (subrecord order differs: core " + " ".join(s.decode("latin-1") for s, _ in cs) + " | override " + " ".join(s.decode("latin-1") for s, _ in os_) + ")")
    return lines, diffs


def header_text(r):
    return (f"flags 0x{r.flags:08X}{' (compressed)' if r.compressed else ''}  version {r.version}  vc 0x{r.vc:08X}  "
            f"data {r.size} B  at offset {r.offset}  in {chain_text(r.chain)}")


def report(plugin_path, core_path, edid="FO4Core_RedRocketSpawn", nbytes=24):
    with open(plugin_path, "rb") as f, open(core_path, "rb") as g:
        pm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        cm = mmap.mmap(g.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            return _report(pm, cm, plugin_path, core_path, edid, nbytes)
        finally:
            pm.close()
            cm.close()


def _report(pdata, cdata, plugin_path, core_path, edid, nbytes):
    out, summary = [], []
    pmast = masters(pdata)
    core_name = core_path.replace("\\", "/").rsplit("/", 1)[-1]
    idx = next((i for i, m in enumerate(pmast) if m.lower() == core_name.lower()), None)
    out.append(f"plugin {plugin_path.replace(chr(92), '/').rsplit('/', 1)[-1]}: masters {pmast}")
    if idx is None:
        out.append(f"the core {core_name} is not among the plugin's masters: nothing to compare")
        return out, ["the core is not a master of the plugin"]
    # the plugin's own records of the core's forms (load index = the core's index among the masters)
    overrides = list(walk(pdata, want=lambda sig, form: form >> 24 == idx and sig in (b"WRLD", b"CELL")))
    out.append(f"override records of the core in the plugin: {[(r.sig.decode(), '%06X' % (r.form & 0xFFFFFF)) for r in overrides]}")
    if not overrides:
        return out, ["the plugin has no WRLD or CELL of the core"]
    own = {(r.sig, r.form & 0xFFFFFF) for r in overrides}
    own_index = len(masters(cdata))          # the core's own records carry the load index after its masters
    twins = {(r.sig, r.form & 0xFFFFFF): r for r in walk(cdata, want=lambda sig, form: (sig, form & 0xFFFFFF) in own and form >> 24 == own_index)}
    for over in overrides:
        key = (over.sig, over.form & 0xFFFFFF)
        core = twins.get(key)
        out.append("")
        out.append(f"== {over.sig.decode()} {key[1]:06X}  EDID plugin '{over.edid}'  core '{core.edid if core else '?'}'")
        if over.error:
            out.append(f"  the plugin's record could not be read: {over.error}")
            summary.append(f"{over.sig.decode()}: unreadable in the plugin")
            continue
        out.append("  plugin: " + header_text(over))
        if core is None:
            out.append("  the core has no such record: the override is of a form the core does not hold")
            summary.append(f"{over.sig.decode()} {key[1]:06X}: no twin in the core")
            continue
        out.append("  core:   " + header_text(core))
        if core.error:
            out.append(f"  the core's record could not be read: {core.error}")
            summary.append(f"{over.sig.decode()}: unreadable in the core")
            continue
        diffs = []
        if (core.flags & ~COMPRESSED) != (over.flags & ~COMPRESSED):
            diffs.append(f"flags 0x{core.flags:08X} vs 0x{over.flags:08X}")
        if core.version != over.version:
            diffs.append(f"record version {core.version} vs {over.version}")
        if core.vc != over.vc:
            diffs.append(f"version-control info 0x{core.vc:08X} vs 0x{over.vc:08X}")
        lines, sdiffs = compare(core, over, nbytes)
        out.extend(lines)
        diffs.extend(sdiffs)
        if over.sig == b"CELL":
            out.append("  children, core:     " + inventory_text(child_inventory(cdata, core.form)))
            out.append("  children, override: " + inventory_text(child_inventory(pdata, over.form)))
        summary.append(f"{over.sig.decode()} {key[1]:06X}: " + ("; ".join(diffs) if diffs else "no difference in header or subrecords"))
    return out, summary


def inventory_text(inv):
    if not inv:
        return "no child groups"
    return "; ".join(f"{GROUP_NAMES.get(t, t)}: " + (", ".join(f"{s} x{n}" for s, n in sorted(v.items())) or "empty") for t, v in sorted(inv.items()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plugin")
    ap.add_argument("core")
    ap.add_argument("--edid", default="FO4Core_RedRocketSpawn")
    ap.add_argument("--out", default="")
    ap.add_argument("--bytes", type=int, default=24)
    a = ap.parse_args(argv)
    lines, summary = report(a.plugin, a.core, a.edid, a.bytes)
    lines += ["", "VERDICTS (differences between each override and its twin in the core):"] + [f"  {s}" for s in summary]
    text = "\n".join(lines) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {a.out} ({len(lines)} lines)")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
