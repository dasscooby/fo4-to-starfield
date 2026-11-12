"""Read-only (Step 0 of the Vault 111 animation experiment, FAL-489): which of the game's own activators play named
sequences, and how.  Run it as `vault111_anim_probe.py --graphs ...` (same arguments) or directly.

It reads three things and ties them together:
 1. The generic object graphs (.agx, XML) of Starfield's Animations archive: per state-table row the state name, the
    `Sequence Name` values, the Enter / Exit events with their payloads and `Send Event On End`.  The layout read is the
    serializer of the open-source Starfield-Behavior-Editor: root > node (node_type, name, input, output, property_sheet,
    embedded graph) and property_sheet > column (header) + row > prop (type, value, listindex).  A cell is printed as
    header=value, so the table is read as the game stores it, and nothing is guessed from names.
 2. Starfield.esm: every ACTI and FURN whose animation graph component (ANAM graph, BNAM rig, CNAM animations folder)
    names one of those graphs: editor id, form id, model path, ANAM, BNAM, CNAM; the count per graph and at most a dozen
    per graph in the list.
 3. For named models (--model, repeatable; by default the first two per graph from 2): which mesh archive holds the file,
    the NIF header version, whether it carries NiControllerManager / NiControllerSequence with their names and text keys,
    and whether its CNAM folder holds .af / .afx files.
It ends with the outcome table of animation-needs rev 9, filled in from what was read ("unread" where a file was not found).

usage: python vault111_anim_probe.py --graphs --out <report.txt> --data <Starfield Data>
           --game-archive "Starfield - Animations.ba2" --game-archive "Starfield - Meshes*.ba2"
           [--esm <Starfield.esm>] [--graph <name> ...] [--model <meshes path> ...] [--per-graph 12] [--default-models 2]
Which archives to pass: the one with the .agx graphs (Starfield - Animations.ba2) and the ones with the models and the
.af/.afx clips (Starfield - Meshes*.ba2, which takes Meshes01, Meshes02 and MeshesPatch).  A name with * is expanded in
--data, so a wrong guess shows in the first report lines ("archives: ..." lists each file and its entry count, or says
nothing matched).  --esm defaults to <data>\\Starfield.esm.  --graph replaces the default graph list.
It opens everything read-only and writes only --out.  Nothing is installed and no game file changes.
"""
import argparse
import glob
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import ba2, nif  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield\Data"
DEFAULT_GRAPHS = ("stageswithloops", "stages", "twostages", "activatorstategraph01", "twostateactivator", "onestateactivator",
                  "genericstategraph01", "genericstategraph02", "genericopenclose01", "fxbeginmiddleend", "furnitureopenclose",
                  "furnituredefault", "1stperson_furniture")
RECORD_GROUPS = (b"ACTI", b"FURN")
FIELD_LABELS = ("Sequence Name", "Enter Events", "Exit Events", "Send Event On End")
INTEREST = re.compile(r"sequence|event|state|anim", re.I)


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


FIELD_KEYS = {norm(f): f for f in FIELD_LABELS}


# ----------------------------------------------------------------------------------------------- archives
def expand_archives(data_dir, names):
    """Absolute archive paths: each name as given, relative to --data, with * and ? expanded.  [(name given, [paths])]."""
    out = []
    for g in names:
        pat = g if os.path.isabs(g) else os.path.join(data_dir, g)
        out.append((g, sorted(glob.glob(pat))))
    return out


def open_archives(paths):
    out = []
    for p in paths:
        try:
            out.append((p, ba2.Ba2(p)))
        except (ba2.Ba2Error, OSError, struct.error) as e:
            out.append((p, f"unreadable: {e}"))
    return out


def ok_archives(archives):
    return [(p, a) for p, a in archives if not isinstance(a, str)]


def find_entry(archives, name):
    """(archive file name, entry bytes) of the first archive holding name (case and slash blind), else None."""
    for path, a in ok_archives(archives):
        i = a.find(name)
        if i is not None:
            try:
                return os.path.basename(path), a.read(i)
            except (ba2.Ba2Error, OSError, struct.error, ValueError) as e:
                return os.path.basename(path), e
    return None


def graph_index(archives):
    """{lower case graph base name (no extension): [(archive file name, entry name, archive, index)]} over every .agx."""
    out = {}
    for path, a in ok_archives(archives):
        for i, n in enumerate(a.names):
            if n.lower().endswith(".agx"):
                base = n.replace("/", "\\").rsplit("\\", 1)[-1][:-4].lower()
                out.setdefault(base, []).append((os.path.basename(path), n, a, i))
    return out


# ----------------------------------------------------------------------------------------------- the .agx
def _text(el, tag):
    c = el.find(tag)
    return (c.text or "").strip() if c is not None else ""


def _sheet(sheet):
    """(headers, rows): rows are lists of (value, listindex or None) per prop, in file order."""
    headers = [_text(c, "header") for c in sheet.findall("column")]
    rows = []
    for r in sheet.findall("row"):
        cells = []
        for p in r.findall("prop"):
            li = _text(p, "listindex")
            cells.append((_text(p, "value"), int(li) if li.lstrip("-").isdigit() else None))
        rows.append(cells)
    return headers, rows


def _pairs(headers, cells):
    """[(header, value)] for one row: by column when the prop count fits, else numbered; list items keep [listindex]."""
    out = []
    for i, (value, li) in enumerate(cells):
        h = headers[i] if i < len(headers) and headers[i] else f"col{i}"
        out.append((h + (f"[{li}]" if li is not None else ""), value))
    return out


def parse_agx(data):
    """{"error", "root": {Name, Category}, "nodes": [(depth, node_type, name, inputs, outputs)], "rows": [row dicts],
    "sheets_skipped": [...]}.  A row dict: owner, sheet, row, pairs [(header, value)], interesting."""
    out = {"error": None, "root": {}, "nodes": [], "rows": [], "sheets_skipped": []}
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        out["error"] = f"not XML: {e}"
        return out
    out["root"] = {"Name": _text(root, "Name") or root.get("Name", ""), "Category": _text(root, "Category") or root.get("Category", "")}

    def sheets(container, owner):
        for si, sh in enumerate(container.findall("property_sheet")):
            headers, rows = _sheet(sh)
            hot = any(INTEREST.search(h) for h in headers) or any(norm(v) in FIELD_KEYS for r in rows for v, _ in r)
            if not hot:
                out["sheets_skipped"].append(f"{owner}: sheet {si}: {len(rows)} row(s), columns {headers or 'none'}")
                continue
            for ri, cells in enumerate(rows):
                out["rows"].append({"owner": owner, "sheet": si, "row": ri, "pairs": _pairs(headers, cells)})

    def walk(container, owner, depth):
        sheets(container, owner)
        for n in container.findall("node"):
            ntype, name = _text(n, "node_type"), _text(n, "name")
            ins = [_text(i, "name") for i in n.findall("input")]
            outs = [_text(o, "name") for o in n.findall("output")]
            out["nodes"].append((depth, ntype, name, ins, outs))
            label = f"node '{name}' ({ntype})"
            sheets(n, label)
            g = n.find("graph")
            if g is not None:
                walk(g, label + " graph", depth + 1)

    walk(root, "root", 0)
    return out


def row_fields(row):
    """{field label: [values]} of one parsed row: header=value cells, and name/value rows whose first cell is the field."""
    got = {}
    pairs = row["pairs"]
    for h, v in pairs:
        key = norm(re.sub(r"\[\d+\]$", "", h))
        if key in FIELD_KEYS and v != "":
            got.setdefault(FIELD_KEYS[key], []).append(v)
    if len(pairs) >= 2 and norm(pairs[0][1]) in FIELD_KEYS:
        got.setdefault(FIELD_KEYS[norm(pairs[0][1])], []).extend(v for _, v in pairs[1:] if v != "")
    return got


def row_state(row):
    for h, v in row["pairs"]:
        if re.fullmatch(r"state ?name|state|name", re.sub(r"[_\[\]\d]", " ", h).strip().lower()) and v:
            return v
    return ""


def graph_lines(name, where, data):
    """(report lines, {field label: set of values}) of one graph."""
    g = parse_agx(data)
    out = [f"=== graph {name}  [{where}, {len(data)} bytes]"]
    if g["error"]:
        out.append(f"  {g['error']}; the first bytes: {data[:80]!r}")
        return out, {}
    out.append(f"  root Name={g['root']['Name']!r} Category={g['root']['Category']!r}; {len(g['nodes'])} node(s): "
               + "; ".join(f"{'  ' * d}{t} '{n}'" + (f" in={ins}" if any(ins) else "") + (f" out={outs}" if any(outs) else "")
                           for d, t, n, ins, outs in g["nodes"][:60]) + (" ..." if len(g["nodes"]) > 60 else ""))
    values = {f: set() for f in FIELD_LABELS}
    if not g["rows"]:
        out.append("  no state-table row with a sequence, event or state column was found in the XML")
    for r in g["rows"]:
        fields = row_fields(r)
        for f, vs in fields.items():
            values[f].update(vs)
        cells = " | ".join(f"{h}={v!r}" for h, v in r["pairs"] if v != "")
        state = row_state(r)
        out.append(f"  {r['owner']} sheet {r['sheet']} row {r['row']}" + (f" state {state!r}" if state else "") + ": " + (cells or "(empty row)"))
    for f in FIELD_LABELS:
        out.append(f"  {f} values: " + (", ".join(sorted(values[f])) if values[f] else "none"))
    if g["sheets_skipped"]:
        out.append(f"  {len(g['sheets_skipped'])} other sheet(s) not printed: " + "; ".join(g["sheets_skipped"][:6]))
    return out, values


# ----------------------------------------------------------------------------------------------- Starfield.esm
def graph_component(subs):
    """{ANAM, BNAM, CNAM} text of the animation graph component's block, and its BFCB name; ({}, None) without one."""
    name, got = None, {}
    for sig, d in subs:
        if sig == b"BFCB":
            name, got = esm.zstring(d), ({} if "animationgraph" not in norm(esm.zstring(d)) and "animgraph" not in norm(esm.zstring(d)) else {"_": 1})
        elif sig == b"BFCE":
            if got:
                return {k: v for k, v in got.items() if k != "_"}, name
            name, got = None, {}
        elif got and sig in (b"ANAM", b"BNAM", b"CNAM") and sig.decode() not in got:
            got[sig.decode()] = esm.zstring(d)
    return {}, None


def model_path(subs):
    for sig, d in subs:
        t = esm.zstring(d)
        if sig != b"EDID" and t.lower().endswith(".nif"):
            return t
    return ""


def graph_base(path):
    return path.replace("/", "\\").rsplit("\\", 1)[-1].rsplit(".", 1)[0].lower()


def read_records(plugin, wanted):
    """([record dicts naming a wanted graph], {graph base: count}, {other graph base: count}, {component name: count}, notes)."""
    hits, other, comps, notes = [], {}, {}, []
    counts = {}
    for label in RECORD_GROUPS:
        if label.decode() not in plugin.groups:
            notes.append(f"no {label.decode()} top group in {os.path.basename(plugin.path)}")
            continue
        for rec in plugin.records(label.decode()):
            comp, cname = graph_component(rec.subs)
            if cname:
                comps[cname] = comps.get(cname, 0) + 1
            anam = comp.get("ANAM", "")
            if not anam:
                continue
            base = graph_base(anam)
            if base in wanted:
                counts[base] = counts.get(base, 0) + 1
                hits.append({"sig": rec.sig.decode(), "formid": rec.formid, "edid": rec.edid, "model": model_path(rec.subs),
                             "ANAM": anam, "BNAM": comp.get("BNAM", ""), "CNAM": comp.get("CNAM", ""), "graph": base})
            else:
                other[base] = other.get(base, 0) + 1
    return hits, counts, other, comps, notes


# ----------------------------------------------------------------------------------------------- the models
def nif_facts(data):
    """Facts of one NIF: header (text line, version, user and BS versions), NiControllerManager count, sequence names, text keys
    per NiTextKeyExtraData block.  A file the container parser refuses still gets its header words and a raw presence scan."""
    f = {"line": "", "version": None, "bs_version": None, "user_version": None, "blocks": None, "types": {}, "managers": None,
         "sequences": None, "text_keys": [], "note": ""}
    nl = data.find(b"\n")
    f["line"] = data[:nl].decode("latin-1") if 0 < nl < 80 and data.startswith(b"Gamebryo") else ""
    if not f["line"]:
        f["note"] = "not a Gamebryo NIF (no header line)"
        return f
    try:
        f["version"], _endian, f["user_version"], f["blocks"], f["bs_version"] = struct.unpack_from("<IBIII", data, nl + 1)
    except struct.error:
        pass
    try:
        n = nif.parse(data)
    except Exception as e:  # noqa: BLE001 - a read tool: say what failed and fall back to a raw scan
        head = data[:min(len(data), 8192)]
        f["note"] = f"container not parsed ({type(e).__name__}: {e}); block names found by raw scan of the first 8 KB only"
        f["managers"] = None
        f["types"] = {t: 1 for t in ("NiControllerManager", "NiControllerSequence", "NiTextKeyExtraData") if t.encode() in head}
        return f
    f["bs_version"], f["blocks"] = n.bs_version, len(n.blocks)
    seqs, keys = [], []
    for i in range(len(n.blocks)):
        t = n.type_of(i)
        f["types"][t] = f["types"].get(t, 0) + 1
        try:
            if t == "NiControllerSequence":
                idx, = struct.unpack_from("<i", n.blocks[i])
                seqs.append(n.strings[idx].decode("latin-1") if 0 <= idx < len(n.strings) else f"<string {idx}>")
            elif t == "NiTextKeyExtraData":
                _name, count = struct.unpack_from("<iI", n.blocks[i])
                block = []
                if 8 + 8 * count <= len(n.blocks[i]):
                    for k in range(count):
                        time, sidx = struct.unpack_from("<fi", n.blocks[i], 8 + 8 * k)
                        block.append(f"{time:.3f}s {n.strings[sidx].decode('latin-1') if 0 <= sidx < len(n.strings) else f'<string {sidx}>'}")
                keys.append((i, block))
        except (struct.error, IndexError):
            f["note"] += f" block {i} {t} could not be read;"
    f["managers"], f["sequences"], f["text_keys"] = f["types"].get("NiControllerManager", 0), seqs, keys
    return f


def folder_files(archives, folder):
    """Archive entries under an animations folder (as named, under Meshes\\ and under Animations\\) with a clip extension."""
    key = folder.replace("/", "\\").strip("\\").lower()
    found = []
    for path, a in ok_archives(archives):
        for n in a.names:
            low = n.replace("/", "\\").lower()
            if low.rsplit(".", 1)[-1] in ("af", "afx", "rig", "gltf") and (
                    low.startswith(key + "\\") or low.startswith("meshes\\" + key + "\\") or low.startswith("animations\\" + key + "\\")):
                found.append(f"{os.path.basename(path)}: {n}")
    return sorted(found)


def model_entry(archives, path):
    p = path.replace("/", "\\").lstrip("\\")
    for cand in ([p] if p.lower().startswith("meshes\\") else ["Meshes\\" + p, p]):
        got = find_entry(archives, cand)
        if got is not None:
            return cand, got
    return "Meshes\\" + p if not p.lower().startswith("meshes\\") else p, None


def model_report(archives, path, cnam=""):
    """(lines, facts dict for the outcome table) of one model."""
    lines = [f"--- model {path}"]
    facts = {"path": path, "read": False, "sequences": None, "managers": None, "af": None}
    name, got = model_entry(archives, path)
    if got is None:
        lines.append(f"  not in the archives read (tried {name})")
    elif isinstance(got[1], Exception):
        lines.append(f"  {got[0]}: entry found but unreadable: {got[1]}")
    else:
        where, data = got
        facts["read"] = True
        n = nif_facts(data)
        lines.append(f"  read from {where} as {name}: {len(data)} bytes")
        lines.append(f"  header: {n['line'] or 'none'}; version {n['version']:#x}" if n["version"] is not None else f"  header: {n['line'] or 'none'}")
        lines.append(f"  user_version {n['user_version']}, bs_version {n['bs_version']}, blocks {n['blocks']}" + (f"; {n['note']}" if n["note"] else ""))
        if n["types"]:
            lines.append("  block types: " + ", ".join(f"{k} x{v}" for k, v in sorted(n["types"].items())))
        if n["managers"] is None:
            lines.append("  NiControllerManager / NiControllerSequence: unread (container not parsed); raw scan found: "
                         + (", ".join(n["types"]) or "neither"))
        else:
            lines.append(f"  NiControllerManager: {n['managers']}")
            lines.append(f"  NiControllerSequence: {len(n['sequences'])}: " + (", ".join(n["sequences"]) if n["sequences"] else "none"))
            lines.append("  text keys: " + ("; ".join(f"block {i}: " + (", ".join(k) if k else "none") for i, k in n["text_keys"]) if n["text_keys"] else "none"))
        facts["sequences"], facts["managers"] = n["sequences"], n["managers"]
    if cnam:
        files = folder_files(archives, cnam)
        facts["af"] = len([x for x in files if x.lower().endswith((".af", ".afx"))])
        lines.append(f"  CNAM folder {cnam}: {len(files)} .af/.afx/.rig file(s)" + (": " + "; ".join(files[:8]) + (" ..." if len(files) > 8 else "") if files else ""))
    return lines, facts


# ----------------------------------------------------------------------------------------------- the report
def outcome_table(values, counts, models, esm_read, graphs_read):
    """The rev 9 outcome rows, each 'YES ...', 'NO ...' or 'unread ...' from what was read."""
    rows = []
    modelled = [m for m in models if m["read"]]
    if not modelled:
        r1 = "unread (no model was found in the archives read)"
        r2 = r1
    else:
        match = []
        for m in modelled:
            seqs = {norm(s) for s in (m["sequences"] or [])}
            want = {norm(v) for v in values.get(m.get("graph", ""), {}).get("Sequence Name", set())}
            if seqs & want:
                match.append(f"{m['path']} carries {sorted(seqs & want)} (graph {m.get('graph', '?')})")
        anyseq = [m["path"] for m in modelled if m["sequences"]]
        unparsed = [m["path"] for m in modelled if m["sequences"] is None]
        if match:
            r1 = "YES: " + "; ".join(match[:4])
        elif anyseq:
            r1 = "NO: models carry sequences, but not under the graph's Sequence Name values: " + ", ".join(anyseq[:4])
        elif unparsed and len(unparsed) == len(modelled):
            r1 = "unread (every model's container was refused by the parser; see the raw scan lines)"
        else:
            r1 = f"NO: {len(modelled)} model(s) read, none carries NiControllerSequence"
        rig = [m["path"] for m in modelled if m["af"] and not m["sequences"]]
        r2 = (f"YES: {len(rig)} of {len(modelled)} model(s) have .af/.afx in their CNAM folder and no sequences: " + ", ".join(rig[:4])
              if rig else f"NO: none of {len(modelled)} model(s) read has .af/.afx in its CNAM folder with no sequences"
              + ("" if any(m["af"] is not None for m in modelled) else " (no CNAM folder was given for them)"))
    rows.append(("vanilla activator models carry NiControllerSequence named as the graph's Sequence Name values", r1, "M2 is the game's own way: Step 1 variants B and C"))
    rows.append(("vanilla activator ACTIs use rig + .af and their models carry no sequences", r2, "M1 is the way: Step 1 variant D"))
    both = r1.startswith("YES") and r2.startswith("YES")
    rows.append(("both exist", "YES" if both else ("unread" if r1.startswith("unread") or r2.startswith("unread") else "NO"), "either: run B and D"))
    if not esm_read:
        neither = "unread (Starfield.esm was not read)"
    elif not graphs_read:
        neither = "unread (no graph file was found in the archives read)"
    else:
        total = sum(counts.values())
        neither = ("YES: no ACTI or FURN names these graphs" if total == 0 else f"NO: {total} ACTI/FURN name them")
    rows.append(("neither: no vanilla ACTI names these graphs", neither, "graphs are for other record types: rethink, test on a furniture"))
    return rows


def run(a):
    out = []
    data_dir = a.data
    wanted = [g.lower().rsplit(".", 1)[0] if g.lower().endswith(".agx") else g.lower() for g in (a.graph or DEFAULT_GRAPHS)]
    expanded = expand_archives(data_dir, a.game_archive)
    paths = [p for _, ps in expanded for p in ps]
    archives = open_archives(paths)
    out.append(f"vault111_anim_graphs (read-only; FAL-489 Step 0): graphs {', '.join(wanted)}")
    for given, ps in expanded:
        if not ps:
            out.append(f"archive argument {given!r}: nothing matched under {data_dir}")
    out.append("archives: " + (", ".join(f"{os.path.basename(p)} ({ar if isinstance(ar, str) else str(len(ar.names)) + ' entries'})" for p, ar in archives) or "none given"))

    # 1. the graphs
    out += ["", "##### 1. the .agx graphs"]
    index = graph_index(archives)
    values, graphs_read = {}, 0
    for g in wanted:
        hits = index.get(g)
        if not hits:
            out += [f"=== graph {g}.agx: unread (no entry of that name in the archives read)", ""]
            continue
        archive_name, entry, arch, i = hits[0]
        try:
            data = arch.read(i)
        except (ba2.Ba2Error, OSError, struct.error, ValueError) as e:
            out += [f"=== graph {g}.agx: entry {entry} in {archive_name} unreadable: {e}", ""]
            continue
        graphs_read += 1
        lines, vals = graph_lines(g + ".agx", f"{archive_name}: {entry}" + (f"; {len(hits) - 1} more entr(ies) of that name not read" if len(hits) > 1 else ""), data)
        values[g] = vals
        out += lines + [""]

    # 2. the records
    out += ["##### 2. ACTI and FURN of Starfield.esm that name these graphs"]
    esm_path = a.esm or os.path.join(data_dir, "Starfield.esm")
    hits, counts, other, esm_read = [], {}, {}, False
    if not os.path.isfile(esm_path):
        out.append(f"unread: {esm_path} not found")
    else:
        try:
            with esm.Plugin(esm_path) as plugin:
                hits, counts, other, comps, notes = read_records(plugin, set(wanted))
            esm_read = True
            out += notes
            out.append(f"read {esm_path}: components with 'graph' in the name seen on ACTI/FURN: "
                       + (", ".join(f"{k} x{v}" for k, v in sorted(comps.items())) or "none"))
        except (esm.EsmError, OSError, struct.error) as e:
            out.append(f"unread: {esm_path}: {e}")
    if esm_read:
        for g in wanted:
            mine = [h for h in hits if h["graph"] == g]
            out.append(f"  {g}: {counts.get(g, 0)} record(s)" + (f" (ACTI {sum(h['sig'] == 'ACTI' for h in mine)}, FURN {sum(h['sig'] == 'FURN' for h in mine)}); first {min(len(mine), a.per_graph)}:" if mine else ""))
            for h in mine[:a.per_graph]:
                out.append(f"    {h['sig']} {h['formid']:08X} {h['edid'] or '-'}  model={h['model'] or '-'}  ANAM={h['ANAM'] or '-'}  BNAM={h['BNAM'] or '-'}  CNAM={h['CNAM'] or '-'}")
        out.append("  other graphs named by ACTI/FURN (not in the list; count): " + (", ".join(f"{k} x{v}" for k, v in sorted(other.items(), key=lambda kv: -kv[1])[:20]) or "none"))

    # 3. the models
    out += ["", "##### 3. models"]
    todo, seen = [], set()
    for m in a.model:
        todo.append((m, "", ""))
        seen.add(m.lower())
    for g in wanted:
        taken = 0
        for h in [h for h in hits if h["graph"] == g and h["model"]]:
            if taken >= a.default_models:
                break
            if h["model"].lower() not in seen:
                seen.add(h["model"].lower())
                todo.append((h["model"], h["CNAM"], g))
                taken += 1
    facts = []
    if not todo:
        out.append("no model to read (none given with --model, and no record named one)")
    for path, cnam, g in todo:
        lines, f = model_report(archives, path, cnam)
        f["graph"] = g
        facts.append(f)
        out += (["  (graph " + g + ")"] if g else []) + lines

    # 4. the outcome table
    out += ["", "##### 4. outcome table (animation-needs rev 9), filled in from what was read", ""]
    for finding, got, nxt in outcome_table(values, counts, facts, esm_read, graphs_read):
        out += [f"- {finding}", f"    read: {got}", f"    if so: {nxt}"]
    out.append("")
    return "\n".join(out) + "\n"


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default=STARFIELD)
    ap.add_argument("--esm")
    ap.add_argument("--game-archive", action="append", default=[], help='a Starfield archive (name in --data, * allowed), e.g. "Starfield - Animations.ba2"')
    ap.add_argument("--graph", action="append", help="a graph name (replaces the default list)")
    ap.add_argument("--model", action="append", default=[], help="a model path to read (repeatable)")
    ap.add_argument("--per-graph", type=int, default=12)
    ap.add_argument("--default-models", type=int, default=2)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    text = run(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"vault111_anim_graphs ok: report {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
