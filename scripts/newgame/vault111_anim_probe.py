"""Read-only: what the installed port says about three Vault 111 references and the animation their models carry.

For each reference of FO4Port.esm (default 00126D, 00138B, 001616) it prints: the REFR (cell, base, position, flags, which
subrecords it has), the base record (type, EditorID, model path, every subrecord's signature), then reads the model
from the archives and prints: the NIF's block types, the animation clip names (NiControllerSequence), the text keys
(animation events written in the NIF), every NIF string that names a graph, clip or file (.hkx, .kf, .nif), the files
the archive holds beside the model (.hkx, .kf, .nif of the same folder), and, for each behavior graph .hkx found, its
readable strings (event and state names). Nothing is a verdict: each section says what it read and says "not found"
when the archive had nothing.

Third head: the DOOR record's ANAM (graph .agx), BNAM (.rig) and CNAM (animations folder) are opened: each file looked up as
named (no Meshes prefix), its strings printed; the folder listed and each .af / .afx / .rig / .agx under it read. The game's own
graph lives in Starfield's archives: add them with --game-archive.

Fourth head: each .agx file read also gets the values of its fields Event, Send Event On End, Enter Events, Exit Events printed
(format-blind: the strings after each field name and the raw bytes; the .agx layout is not yet read).

Also (FAL-476 second head): every subrecord of the base record is printed (signature, size, first bytes, text) and each 4-byte
one that holds a form id of this plugin is followed one hop (the DOOR record's sound and other links, with any file they
name); the Fallout 4 original of each model is looked up by the port path with its prefix removed and else by file name
(--fo4-data); and every reference whose base EditorID contains a --base-edid word (default: GearDoorConsole, PipboySkeleton,
PipboyGroundTake, VaultConsole, GearDoor) is reported like the listed ones, or the report says the port has none.

usage: python vault111_anim_probe.py --out <report.txt> [--data <Starfield Data>] [--port FO4Port.esm]
                                     [--archive <ba2> ...] [--game-archive <Starfield ba2> ...] [--fo4-data <Fallout 4 Data>] [--ref 00126D ...]
                                     [--base-edid <word> ...]
Step 0 of the animation experiment (FAL-489): `--graphs` switches to a different, read-only report of the game's own graphs
(.agx state tables, the ACTI/FURN that name them, their models); see vault111_anim_graphs.py for its arguments:
    python vault111_anim_probe.py --graphs --out <report.txt> --data <Starfield Data> --game-archive "Starfield - Animations.ba2"
                                  --game-archive "Starfield - Meshes*.ba2" [--model <meshes path> ...]
It opens the plugin and the archives read-only and writes only --out. Nothing in the game folder changes; no install.
By default the archives are every FO4Port*.ba2 in --data; --fo4-data adds Fallout4 - Meshes.ba2 and
Fallout4 - Animations.ba2 (the source models and graphs), which settles whether a clip exists in the original.
"""
import argparse
import glob
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import ba2, nif  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield\Data"
DEFAULT_REFS = ("00126D", "00138B", "001616")
FILE_WORDS = re.compile(rb"\.(hkx|kf|nif|hkt|txt)\b|graph|behavior|anim", re.I)
MAX_STRINGS = 300
ANIM_EXT = (".agx", ".rig", ".af", ".afx")      # a Starfield animation graph, skeleton rig, clip and clip events file
DEFAULT_BASE_WORDS = ("GearDoorConsole", "PipboySkeleton", "PipboyGroundTake", "VaultConsole", "GearDoor")
FO4_NAMES = ("Fallout4 - Meshes.ba2", "Fallout4 - Animations.ba2")


# ----------------------------------------------------------------------------------------------- the plugin
def index_records(plugin):
    """({form id: (offset, sig)}, {ref form id: cell record form id}) over every group of the plugin."""
    records, cell_of = {}, {}
    cell = None
    for start, end in [r for ranges in plugin.groups.values() for r in ranges]:
        for item in plugin.walk(start, end):
            if item[0] != "REC":
                continue
            _, off, sig, _depth = item
            fid = struct.unpack_from("<I", plugin.buf, off + 12)[0]
            records[fid] = (off, sig.decode("latin-1"))
            if sig == b"CELL":
                cell = fid
            elif sig in (b"REFR", b"ACHR"):
                cell_of[fid] = cell
    return records, cell_of


def find_ref(records, plugin, local):
    """The record for a local id: the plugin's own index first, then the same low 24 bits under any other index."""
    want = int(local, 16) & 0xFFFFFF
    own = (plugin.self_index << 24) | want
    if own in records:
        return own
    return next((f for f in sorted(records) if f & 0xFFFFFF == want and records[f][1] in ("REFR", "ACHR")), None)


def zstr(data):
    return data.split(b"\0", 1)[0].decode("latin-1")


def describe(plugin, records, fid):
    """Text lines about one record: type, EditorID, every subrecord (signature and size), any path-like string."""
    off, sig = records[fid]
    rec = plugin.record_at(off)
    lines = [f"{sig} {fid:08X} edid={rec.edid or '-'} flags={rec.flags:#x} "
             "subrecords=" + " ".join("%s:%d" % (s.decode("latin-1"), len(d)) for s, d in rec.subs)]
    paths = []
    for s, d in rec.subs:
        text = zstr(d)
        if len(text) >= 4 and text.isprintable() and re.search(r"\.(nif|hkx|kf|agx|rig|af|afx)\b", text, re.I):
            paths.append((s.decode("latin-1"), text))
    return rec, lines, paths


def sub_lines(rec):
    """Every subrecord: signature, size, the first 24 bytes in hex, and its text when it is printable."""
    out = []
    for sig, d in rec.subs:
        text = zstr(d)
        shown = f" text={text!r}" if len(text) >= 3 and text.isprintable() and len(text) == len(d) - 1 else ""
        out.append(f"    {sig.decode('latin-1')} {len(d)} bytes: {d[:24].hex()}{shown}")
    return out


def links(rec, records, self_fid):
    """[(subrecord signature, form id)] of the 4-byte subrecords that hold a form id of this plugin's records."""
    out = []
    for sig, d in rec.subs:
        if len(d) == 4 and sig not in (b"EDID",):
            fid = struct.unpack_from("<I", d)[0]
            if fid in records and fid != self_fid:
                out.append((sig.decode("latin-1"), fid))
    return out


def ref_line(rec):
    out = {}
    name = rec.get(b"NAME")
    if name and len(name) >= 4:
        out["base"] = struct.unpack_from("<I", name)[0]
    for sig in (b"DATA", b"XSCL", b"XESP", b"XTEL", b"XLKR", b"XPRM", b"XRNK"):
        if rec.get(sig) is not None:
            out[sig.decode()] = rec.get(sig)
    return out


def position(data):
    if data is not None and len(data) >= 24:
        x, y, z, rx, ry, rz = struct.unpack_from("<6f", data)
        return f"pos=({x:.3f}, {y:.3f}, {z:.3f}) rot=({rx:.3f}, {ry:.3f}, {rz:.3f})"
    return f"DATA {len(data) if data is not None else 'missing'} bytes"


# ----------------------------------------------------------------------------------------------- the archives
def open_archives(paths):
    out = []
    for p in paths:
        try:
            out.append((p, ba2.Ba2(p)))
        except (ba2.Ba2Error, OSError, struct.error) as e:
            out.append((p, f"unreadable: {e}"))
    return out


def lookup(archives, name):
    """(archive file name, bytes) of the entry called name: exact first, then ignoring case and slash direction (the
    archives keep each folder's own case: Fallout 4's \"Interiors\" is the port's \"interiors\")."""
    key = name.replace("/", "\\").lower()
    for path, a in archives:
        if isinstance(a, str):
            continue
        i = a.find(name)
        if i is None:
            i = next((a.find(n) for n in a.names if n.replace("/", "\\").lower() == key), None)
        if i is not None:
            return os.path.basename(path), a.read(i)
    return None


def neighbours(archives, model):
    """Archive entries of the model's folder (and the folder's Animations sibling) with a clip, graph or model extension."""
    folder = model.replace("/", "\\").lower().rsplit("\\", 1)[0]
    found = []
    for path, a in archives:
        if isinstance(a, str):
            continue
        for n in a.names:
            low = n.replace("/", "\\").lower()
            if low.startswith(folder + "\\") and low.rsplit(".", 1)[-1] in ("hkx", "kf", "nif", "hkt"):
                found.append(f"{os.path.basename(path)}: {n}")
    return sorted(set(found))


def ascii_strings(data, minimum=4):
    return [m.group().decode("latin-1") for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minimum, data)]


# ----------------------------------------------------------------------------------------------- the NIF
def read_nif(data):
    """Lines about a NIF: block type counts, clip names, text keys, graph-like strings. Parse errors fall back to strings."""
    lines, graphs = [], []
    try:
        n = nif.parse(data)
    except Exception as e:  # noqa: BLE001 - a read tool: say what failed and keep the raw string scan
        lines.append(f"  NIF not parsed ({type(e).__name__}: {e}); raw strings only")
        n = None
    if n is not None:
        counts = {}
        for i in range(len(n.blocks)):
            counts[n.type_of(i)] = counts.get(n.type_of(i), 0) + 1
        lines.append(f"  bs_version={n.bs_version} blocks={len(n.blocks)}: "
                     + ", ".join(f"{k} x{v}" for k, v in sorted(counts.items())))
        clips, keys = [], []
        for i, block in enumerate(n.blocks):
            t = n.type_of(i)
            try:
                if t == "NiControllerSequence":
                    name, count = struct.unpack_from("<iI", block)
                    clips.append(n.strings[name].decode("latin-1") if 0 <= name < len(n.strings) else f"<string {name}>")
                elif t == "NiTextKeyExtraData":
                    _name, count = struct.unpack_from("<iI", block)
                    if 12 + 8 * count <= len(block) + 4:
                        for k in range(count):
                            time, sidx = struct.unpack_from("<fi", block, 8 + 8 * k)
                            text = n.strings[sidx].decode("latin-1") if 0 <= sidx < len(n.strings) else f"<string {sidx}>"
                            keys.append(f"{time:.3f}s {text}")
                elif t == "BSBehaviorGraphExtraData":
                    name, sidx = struct.unpack_from("<ii", block)
                    graphs.append(n.strings[sidx].decode("latin-1") if 0 <= sidx < len(n.strings) else f"<string {sidx}>")
            except (struct.error, IndexError):
                lines.append(f"  block {i} {t}: could not be read")
        lines.append("  clips (NiControllerSequence): " + (", ".join(clips) if clips else "none"))
        lines.append("  text keys: " + ("; ".join(keys) if keys else "none"))
        lines.append("  behavior graph (BSBehaviorGraphExtraData): " + (", ".join(graphs) if graphs else "none"))
        words = [s.decode("latin-1") for s in n.strings if FILE_WORDS.search(s)]
        lines.append("  strings naming a graph, clip or file: " + (", ".join(words) if words else "none"))
    else:
        words = sorted({s for s in ascii_strings(data) if FILE_WORDS.search(s.encode("latin-1"))})
        lines.append("  strings naming a graph, clip or file: " + (", ".join(words[:MAX_STRINGS]) if words else "none"))
    return lines, (n, graphs)


AGX_FIELDS = ("Event", "Send Event On End", "Enter Events", "Exit Events")
AGX_SHOWN = 12       # occurrences of one field printed
AGX_AFTER = 160      # bytes after a field name that are read


def agx_pattern(field):
    """A field name as written with a space, an underscore or nothing between its words, any case, not inside a longer word."""
    words = field.split()
    return re.compile(rb"(?<![A-Za-z0-9])" + rb"[ _]?".join(re.escape(w.encode()) for w in words) + rb"(?![a-z])", re.I)


def agx_field_lines(data):
    """Values of the .agx fields Event, Send Event On End, Enter Events, Exit Events, read format-blind (the layout is unread):
    for each occurrence of a field name, the printable strings that follow it (split at control bytes) and the raw bytes.
    A bare Event hit inside another field's name (Send Event On End) is marked, not dropped."""
    out = [f"  .agx fields {', '.join(AGX_FIELDS)} (format-blind: strings after each name, then raw hex; nothing is a verdict):"]
    longer = [m.span() for other in AGX_FIELDS[1:] for m in agx_pattern(other).finditer(data)]
    for field in AGX_FIELDS:
        hits = list(agx_pattern(field).finditer(data))
        if not hits:
            out.append(f"    {field}: not found in the file")
            continue
        out.append(f"    {field}: {len(hits)} occurrence(s)" + (f", first {AGX_SHOWN} shown" if len(hits) > AGX_SHOWN else ""))
        for m in hits[:AGX_SHOWN]:
            tail = data[m.end():m.end() + AGX_AFTER]
            before = data[max(0, m.start() - 24):m.start()]
            vals = [t.decode("latin-1") for t in re.findall(rb"[\x20-\x7e]{2,}", tail)]
            ahead = [t.decode("latin-1") for t in re.findall(rb"[\x20-\x7e]{2,}", before)]
            inside = field == AGX_FIELDS[0] and any(a <= m.start() and m.end() <= b for a, b in longer)
            out.append(f"      @{m.start()} matched {m.group().decode('latin-1')!r}{' (inside a longer field name)' if inside else ''}; before: {' | '.join(ahead[-2:]) or '-'}; after: {' | '.join(vals[:6]) or '-'}")
            out.append(f"        hex after: {tail[:32].hex(' ')}")
    return out


def hkx_lines(name, data):
    strings = []
    seen = set()
    for s in ascii_strings(data, 3):
        if s not in seen:
            seen.add(s)
            strings.append(s)
    shown = strings[:MAX_STRINGS]
    more = f" (+{len(strings) - MAX_STRINGS} more)" if len(strings) > MAX_STRINGS else ""
    return [f"  graph {name}: {len(data)} bytes, {len(strings)} distinct strings{more}", "    " + " | ".join(shown)]


# ----------------------------------------------------------------------------------------------- the report
def report_ref(plugin, records, cell_of, archives, fo4, fid):
    """The report of one reference: REFR, cell, position, base with every subrecord, its links, and each model read."""
    out = []
    rec, lines, _ = describe(plugin, records, fid)
    info = ref_line(rec)
    cell = cell_of.get(fid)
    cell_edid = plugin.record_at(records[cell][0]).edid if cell in records else "?"
    out += ["  " + lines[0], f"  cell {cell_edid} ({cell:08X})" if cell is not None else "  cell unknown",
            "  " + position(info.get("DATA"))]
    base = info.get("base")
    if base is None or base not in records:
        out.append(f"  base {base:08X} is not in this plugin (a master's record: read it with the records tool)"
                   if base is not None else "  no NAME subrecord: no base")
        return out
    brec, blines, paths = describe(plugin, records, base)
    out.append("  base " + blines[0])
    out.append("  base type " + records[base][1])
    out += ["  base subrecords:"] + sub_lines(brec)
    for sub, fid2 in links(brec, records, base):
        r2, l2, p2 = describe(plugin, records, fid2)
        out.append(f"  base link {sub} -> " + l2[0])
        out += sub_lines(r2)
        for sub2, path2 in p2:
            out += file_report(archives, path2, f"link {sub} path ({sub2})", None)
    if not paths:
        out.append("  model path: none found in the base's subrecords")
    for sub, path in paths:
        low = path.lower()
        if low.endswith(ANIM_EXT):
            out.append(f"  animation file ({sub}): {path}")
            out += file_report(archives, path, f"base {sub}", None)
        else:
            out.append(f"  model path ({sub}): {path}")
            out += file_report(archives, path, "port", fo4)
    for sub, text in folders(brec):
        out += folder_report(archives, text, f"base {sub}")
    return out


def folders(rec):
    """[(subrecord signature, text)] of printable path-like subrecords with a folder separator and no file extension."""
    out = []
    for sig, d in rec.subs:
        text = zstr(d)
        if sig != b"EDID" and len(text) >= 5 and len(text) == len(d) - 1 and text.isprintable() and ("\\" in text or "/" in text) \
                and not re.search(r"\.\w{1,4}$", text):
            out.append((sig.decode("latin-1"), text))
    return out


def refs_by_base_word(plugin, records, word):
    """([reference form ids whose base EditorID contains word], [base records of this plugin that do, placed or not])."""
    word = word.lower()
    base_edid = {}

    def edid_of(fid):
        if fid not in base_edid:
            base_edid[fid] = (plugin.record_at(records[fid][0]).edid or "") if fid in records else ""
        return base_edid[fid]
    refs = []
    for fid, (off, sig) in sorted(records.items()):
        if sig in ("REFR", "ACHR"):
            name = plugin.record_at(off).get(b"NAME")
            if name and len(name) >= 4 and word in edid_of(struct.unpack_from("<I", name)[0]).lower():
                refs.append(fid)
    bases = [f for f, (_, sig) in sorted(records.items()) if sig not in ("REFR", "ACHR", "CELL", "GRUP") and word in edid_of(f).lower()]
    return refs, bases


def probe(plugin, archives, refs, fo4=None, words=()):
    fo4 = [] if fo4 is None else fo4
    records, cell_of = index_records(plugin)
    out = [f"vault111_anim_probe: {plugin.path}; masters {', '.join(plugin.masters) or 'none'}; "
           f"{len(records)} records; archives: " + (", ".join(f"{os.path.basename(p)} ({a if isinstance(a, str) else len(a.names)} files)"
                                                             for p, a in archives) or "none")]
    out.append("Fallout 4 archives: " + (", ".join(f"{os.path.basename(p)} ({a if isinstance(a, str) else len(a.names)} files)"
                                                   for p, a in fo4) or "none given (--fo4-data)"))
    done = set()
    for local in refs:
        out += ["", f"===== ref {local.upper()}"]
        fid = find_ref(records, plugin, local)
        if fid is None:
            out.append(f"  not found: no REFR or ACHR with local id {local.upper()} in {os.path.basename(plugin.path)}")
            continue
        done.add(fid)
        out += report_ref(plugin, records, cell_of, archives, fo4, fid)
    for word in words:
        found, bases = refs_by_base_word(plugin, records, word)
        out += ["", f"===== references whose base EditorID contains '{word}': {len(found)}"
                    + (f" ({', '.join(f'{f & 0xFFFFFF:06X}' for f in found)})" if found else "")]
        if not found:
            out.append(f"  none: the port has no placed reference on such a base; base records with that word in the EditorID: "
                       + (", ".join(f"{records[f][1]} {f & 0xFFFFFF:06X} {plugin.record_at(records[f][0]).edid}" for f in bases[:12]) if bases else "none"))
        for fid in found:
            if fid in done:
                out.append(f"  ref {fid & 0xFFFFFF:06X}: already reported above")
                continue
            done.add(fid)
            out += ["", f"  --- ref {fid & 0xFFFFFF:06X}"] + report_ref(plugin, records, cell_of, archives, fo4, fid)
    return "\n".join(out) + "\n"


def file_report(archives, path, label, fo4):
    """Lines about one model or graph path: its archive entry, the NIF read, files beside it, graphs; then (fo4 not None) its original."""
    out = []
    low = path.lower()
    anim = low.endswith(ANIM_EXT)
    model = path if low.startswith("meshes") or low.startswith("animations") or anim else "Meshes\\" + path
    got = lookup(archives, model)
    if got is None and anim:
        for cand in ("Meshes\\" + path, "Animations\\" + path):
            got = lookup(archives, cand)
            if got:
                model = cand
                break
    if got is None:
        out.append(f"  {label}: model not in the archives read: {model}")
        for n in neighbours(archives, model):
            out.append("  beside it: " + n)
    else:
        where, data = got
        out.append(f"  {label}: read from {where}: {len(data)} bytes")
        if low.endswith(".hkx") or anim:
            out += hkx_lines(model + " in " + where, data)
            if low.endswith(".agx"):
                out += agx_field_lines(data)
        elif low.endswith(".kf"):
            out.append("  a .kf clip: strings " + " | ".join(ascii_strings(data, 3)[:60]))
        else:
            lines2, (parsed, graphs) = read_nif(data)
            out += lines2
            near = neighbours(archives, model)
            out.append("  files beside the model (.hkx .kf .nif .hkt): " + ("; ".join(near) if near else "none"))
            for g in graphs:
                for cand in (g, "Meshes\\" + g, "Animations\\" + g):
                    hit = lookup(archives, cand)
                    if hit:
                        out += hkx_lines(cand + " in " + hit[0], hit[1])
                        break
                else:
                    out.append(f"  graph {g}: not in the archives read")
            for n in near:
                if n.lower().endswith(".hkx") and not any(n.lower().endswith(g.lower().replace("/", "\\")) for g in graphs):
                    nm = n.split(": ", 1)[1]
                    hit = lookup(archives, nm)
                    if hit:
                        out += hkx_lines(nm + " in " + hit[0], hit[1])
    if fo4 is not None and not anim:
        out += original_report(fo4, path)
    return out


def folder_report(archives, folder, label):
    """A subrecord that is a folder (the DOOR's animations folder): every archive entry under it, each animation file read."""
    key = folder.replace("/", "\\").strip("\\").lower()
    found = []
    for path, a in archives:
        if isinstance(a, str):
            continue
        for n in a.names:
            low = n.replace("/", "\\").lower()
            if low.startswith(key + "\\") or low.startswith("meshes\\" + key + "\\") or low.startswith("animations\\" + key + "\\"):
                found.append(n)
    if not found:
        return [f"  {label}: folder {folder}: no archive entry under it (tried as named, under Meshes\\ and under Animations\\)"]
    out = [f"  {label}: folder {folder}: {len(found)} entries: " + "; ".join(sorted(found)[:40])]
    for n in sorted(found):
        if n.lower().endswith(ANIM_EXT + (".hkx", ".kf")):
            out += file_report(archives, n, f"{label} file", None)
    return out


def original_candidates(path):
    """The Fallout 4 path the port path was made from: the same path with the port's "fo4port\\" folder taken out and its
    "interiors" / "animobjects" folder put back to Fallout 4's names, plus the path as it is."""
    p = path.replace("/", "\\").strip("\\")
    if p.lower().startswith("meshes\\"):
        p = p[7:]
    parts = p.split("\\")
    out = ["Meshes\\" + p]
    if parts and parts[0].lower() == "fo4port":
        rest = parts[1:]
        if rest and rest[0].lower() in ("interiors", "animobjects"):
            out.append("Meshes\\" + "\\".join([{"interiors": "Interiors", "animobjects": "AnimObjects"}[rest[0].lower()]] + rest[1:]))
        out.append("Meshes\\" + "\\".join(rest))
    return out


def original_report(fo4, path):
    if not fo4:
        return ["  original (Fallout 4): not read: no --fo4-data given"]
    if all(isinstance(a, str) for _, a in fo4):
        return ["  original (Fallout 4): not read: " + "; ".join(f"{os.path.basename(p)} {a}" for p, a in fo4)]
    tried = original_candidates(path)
    for cand in tried:
        got = lookup(fo4, cand)
        if got is not None:
            return [f"  original (Fallout 4) at {cand}:"] + ["  " + l for l in file_report(fo4, cand, "original", None)]
    base = tried[0].rsplit("\\", 1)[-1].lower()
    same = sorted({f"{os.path.basename(p)}: {n}" for p, a in fo4 if not isinstance(a, str) for n in a.names
                  if n.replace("/", "\\").lower().rsplit("\\", 1)[-1] == base})
    if len(same) == 1:
        nm = same[0].split(": ", 1)[1]
        return [f"  original (Fallout 4) found by file name {nm}:"] + ["  " + l for l in file_report(fo4, nm, "original", None)]
    return ["  original (Fallout 4): not found by the paths " + ", ".join(tried) + ("; " + str(len(same)) + " files of that name: " + "; ".join(same[:6]) if same else "; no file of that name")]



def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--graphs" in argv:
        argv.remove("--graphs")
        import vault111_anim_graphs
        return vault111_anim_graphs.main(argv)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default=STARFIELD)
    ap.add_argument("--port")
    ap.add_argument("--archive", action="append", default=[])
    ap.add_argument("--game-archive", action="append", default=[],
                    help="a Starfield archive to read as well (the DOOR's .agx graph and .rig live in the game's own archives, e.g. Starfield - Animations.ba2)")
    ap.add_argument("--fo4-data")
    ap.add_argument("--ref", action="append")
    ap.add_argument("--base-edid", action="append", help="a word of a base EditorID; every reference on such a base is reported")
    a = ap.parse_args(argv)
    port = a.port or os.path.join(a.data, "FO4Port.esm")
    if not os.path.isfile(port):
        sys.exit(f"{port} missing")
    paths = list(a.archive) or sorted(glob.glob(os.path.join(a.data, "FO4Port*.ba2")))
    paths += [g if os.path.isabs(g) else os.path.join(a.data, g) for g in a.game_archive]
    fo4 = []
    if a.fo4_data:
        fo4 = open_archives([os.path.join(a.fo4_data, n) for n in FO4_NAMES if os.path.isfile(os.path.join(a.fo4_data, n))])
    with esm.Plugin(port) as plugin:
        text = probe(plugin, open_archives(paths), a.ref or list(DEFAULT_REFS), fo4,
                     a.base_edid if a.base_edid is not None else DEFAULT_BASE_WORDS)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"vault111_anim_probe ok: {len(paths)} archive(s), {len(fo4 or [])} Fallout 4 archive(s), report {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
