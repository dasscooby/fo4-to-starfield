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

Second mode, `--dump-graph NAME` (repeatable): the COMPLETE structure of the named graph(s) and nothing else (no Starfield.esm, no
models): every element of the XML in file order (tag, attributes, text), every property sheet with all its columns and all its rows
(no filter by column name, which the report above applies), and a census of element paths. It exists because the report prints only
the sheets whose columns look like sequences, events or states, so the transition rows of a state machine (from state, to state, the
event that fires it) were not printed. Where the XML keeps them (a sheet, node inputs and outputs, or elements this reader does not
know) is UNREAD by the author of this tool: the dump shows whatever is there, and marks sheets whose header names a transition word
(from, to, source, target, trans, trigger, condition, event, next) as candidates, by name only.
    python vault111_anim_probe.py --graphs --dump-graph genericstategraph01 --dump-graph activatorstategraph01 --out <dump.txt>
           --data <Starfield Data> --game-archive "Starfield - Animations.ba2"

Third mode, `--dump-form HEX` (repeatable) and `--refs-to HEX` (repeatable), for ONE base object whose 3D did not load (the lift
ShipQuickLift1, 00010C35: FAL-489, the lift half of the door and lift kit): no graph is read.
  --dump-form 00010C35   every subrecord of the record (signature, size, text or hex, any text strings found inside, and for a 4-byte
                         subrecord the form id it could be), the record flags, and the model path, rig (BNAM), clip folder (CNAM) and
                         the component names read from it; then the model checked against the archives given, exactly as in the report
                         above (is the file there, the NIF header, NiControllerManager / sequences / text keys, the rig's clips).
  --refs-to 00010C35     every REFR and ACHR of the CELL and WRLD top groups whose NAME is that form id: count, and the first --refs-limit
                         (default 12) with the cell (form id and editor id) and the position. A count of 0 says only that no such
                         placed reference was found in those groups, not why the game never places one.
Both write only --out.  Examples:
    python vault111_anim_probe.py --graphs --dump-form 00010C35 --out <lift.txt> --data <Starfield Data> --game-archive "Starfield - Meshes*.ba2"
    python vault111_anim_probe.py --graphs --refs-to 00010C35 --out <lift-refs.txt> --data <Starfield Data>

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
                  "furnituredefault", "1stperson_furniture",
                  "hybridstategraph01", "genericpowersimple", "outpostdeploy")      # the last three: the most used on ACTI/FURN (PC run, #744)
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
    by_header = False
    for h, v in pairs:
        key = norm(re.sub(r"\[\d+\]$", "", h))
        if key in FIELD_KEYS:
            by_header = True
            if v != "":
                got.setdefault(FIELD_KEYS[key], []).append(v)
    # the name/value layout (first cell is the field's name) only for a row with no column headed by a field: a state
    # whose value happens to read "Sequence Name" in a headed table must not pull its other cells in as values
    if not by_header and len(pairs) >= 2 and norm(pairs[0][1]) in FIELD_KEYS:
        got.setdefault(FIELD_KEYS[norm(pairs[0][1])], []).extend(v for _, v in pairs[1:] if v != "")
    return got


def row_state(row):
    for h, v in row["pairs"]:
        if re.fullmatch(r"state ?name|state|name", re.sub(r"[_\[\]\d]", " ", h).strip().lower()) and v:
            return v
    return ""


TRANSITION_HEADER = re.compile(r"from|\bto\b|source|target|dest|trans|trigger|condition|event|next|prev", re.I)
DUMP_MAX_ROWS = 500          # rows printed per property sheet
DUMP_PER_PATH = 300          # elements printed per element path (the census counts them all)


def _element_label(el):
    attrs = " ".join(f"{k}={v!r}" for k, v in el.attrib.items())
    text = (el.text or "").strip()
    return el.tag + (" " + attrs if attrs else "") + (f" = {text!r}" if text else "")


_ABSENT = object()


def _inline(el):
    """One element as one short string: its text, its attributes (@name=value) and its children (tag=...), nothing dropped."""
    out = (el.text or "").strip()
    if el.attrib:
        out += (" " if out else "") + " ".join(f"@{k}={v!r}" for k, v in el.attrib.items())
    if len(el):
        out += (" " if out else "") + "<" + ", ".join(f"{c.tag}={_inline(c)}" for c in el) + ">"
    return out


def _extras(el, skip):
    """{key: text} of everything on an element but the children named in skip: its attributes (@name), its own text (#text) and the other
    children (tag: their inline form)."""
    out = {"@" + k: v for k, v in el.attrib.items()}
    if (el.text or "").strip():
        out["#text"] = el.text.strip()
    for c in el:
        if c.tag not in skip:
            out[c.tag] = _inline(c)
    return out


def _common(items):
    """{key: the value most items have} (a key half or more of the items lack, or a tie, is left out): what is said once instead of on every cell."""
    keys = sorted(set().union(*items)) if items else []
    out = {}
    for k in keys:
        vals = [it.get(k, _ABSENT) for it in items]
        top = max(set(vals), key=lambda v: (vals.count(v), str(v)))
        if top is not _ABSENT and vals.count(top) * 2 > len(vals):         # strictly more than half, so "every" is never said of a tie
            out[k] = top
    return out


def _deviation(common, item):
    """{key: value or '<absent>'} where an item differs from the common values."""
    d = {}
    for k in sorted(set(common) | set(item)):
        v = item.get(k, _ABSENT)
        if v != common.get(k, _ABSENT):
            d[k] = "<absent>" if v is _ABSENT else v
    return d


def _fmt_extras(d):
    return "{" + ", ".join(f"{k}={v!r}" for k, v in d.items()) + "}"


def _census_below(el, path, census):
    for c in el:
        cp = path + "/" + c.tag
        census[cp] = census.get(cp, 0) + 1
        _census_below(c, cp, census)


def _key_of(node, name):
    """A node's id-like value: the text of a child of that name, else an attribute of that name, else None."""
    c = node.find(name)
    if c is not None and (c.text or "").strip():
        return c.text.strip()
    return node.attrib.get(name)


def _link_context(link, node, sibs):
    """One line about a link (`node/input/link`): the node it sits on, its attributes, and which sibling nodes of the same graph its `node` number
    could mean. What the number means is UNREAD by the author of this tool, so every plausible reading is printed, none is chosen."""
    where = f"on node {_key_of(node, 'name') or (node.findtext('name') or '?')!r}" if node is not None else "on no node"
    if node is not None:
        bits = [f"type {node.findtext('node_type')!r}"] + [f"{k} {_key_of(node, k)!r}" for k in ("user_id", "id") if _key_of(node, k) is not None]
        where += " (" + ", ".join(bits) + ")"
    attrs = " ".join(f"{k}={v!r}" for k, v in link.attrib.items())
    want = link.attrib.get("node")
    reads = []
    if want is not None and sibs:
        def name(n):
            return n.findtext("name") or "?"
        for label, pick in (("child/attribute id", lambda i, n: _key_of(n, "id")), ("user_id", lambda i, n: _key_of(n, "user_id")),
                            ("position from 0", lambda i, n: str(i)), ("position from 1", lambda i, n: str(i + 1))):
            hit = [f"{name(n)!r}" for i, n in enumerate(sibs) if pick(i, n) == want]
            reads.append(f"{label}: {', '.join(hit) if hit else 'none'}")
    return (f"link {where}; attributes {attrs or 'none'}"
            + (f"; node={want} could mean (readings, none chosen; {len(sibs)} node(s) in this graph): " + "; ".join(reads) if reads else ""))


def _is_link_sheet(rows):
    first = {(r.findall("prop")[0].findtext("value") or "").strip() for r in rows if r.findall("prop")}
    return {"Event", "Transition Type"} <= first


def dump_agx(data, max_rows=DUMP_MAX_ROWS, per_path=DUMP_PER_PATH):
    """(lines, census {element path: count}) of the whole XML of one graph in file order: every element's tag, attributes and text. A
    property_sheet is printed as a table (columns, then every row, empty cells left out) AND with everything inside it: the sheet's own
    attributes, text and other children, each column's attributes and other children, each row's attributes and other children, each cell's
    other children and attributes (type, flag, extra, ...). What every column, row or cell shares is said once on its line; a cell prints
    only what differs ({...} after its value). The census counts every element inside a sheet too. A sheet whose rows include Event and
    Transition Type is marked a transition link sheet, and a sheet under a `link` says which node it sits on and what the link's `node`
    number could mean. Raises ET.ParseError for a file that is not XML."""
    root = ET.fromstring(data)
    lines, census, printed, skipped = [], {}, {}, {}

    def sheet_lines(el, pad, p, ctx):
        cols = el.findall("column")
        headers = [_text(c, "header") for c in cols]
        rows = el.findall("row")
        out = []
        cand = any(TRANSITION_HEADER.search(h) for h in headers)
        mark = ("; a header names a transition word (by name only)" if cand else "") + ("; TRANSITION LINK SHEET (rows Event and Transition Type)" if _is_link_sheet(rows) else "")
        own = _extras(el, {"column", "row"})
        out.append(f"{pad}property_sheet {p}" + (" " + _fmt_extras(own) if own else "") + f": {len(headers)} column(s) {headers}; {len(rows)} row(s){mark}")
        parent = ctx.get("parent")
        if parent is not None and parent.tag == "link":
            out.append(f"{pad}  " + _link_context(parent, ctx.get("node"), ctx.get("sibs")))
        col_x = [_extras(c, {"header"}) for c in cols]
        col_common = _common(col_x)
        if col_common:
            out.append(f"{pad}  every column also has {_fmt_extras(col_common)}")
        for i, x in enumerate(col_x):
            d = _deviation(col_common, x)
            if d:
                out.append(f"{pad}  column {i} ({headers[i]!r}) differs: {_fmt_extras(d)}")
        row_x = [_extras(r, {"prop"}) for r in rows]
        row_common = _common(row_x)
        if row_common:
            out.append(f"{pad}  every row also has {_fmt_extras(row_common)}")
        cell_x = [[_extras(c, {"value", "listindex"}) for c in r.findall("prop")] for r in rows]
        cell_common = _common([x for r in cell_x for x in r])
        if cell_common:
            out.append(f"{pad}  every cell also has {_fmt_extras(cell_common)}")
        for ri, r in enumerate(rows[:max_rows]):
            shown = []
            for ci, c in enumerate(r.findall("prop")):
                li = _text(c, "listindex")
                h = headers[ci] if ci < len(headers) and headers[ci] else f"col{ci}"
                h += f"[{li}]" if li.lstrip("-").isdigit() else ""
                v = _text(c, "value")
                d = _deviation(cell_common, cell_x[ri][ci])
                if v != "" or d:
                    shown.append(f"{h}={v!r}" + (" " + _fmt_extras(d) if d else ""))
            rd = _deviation(row_common, row_x[ri])
            ncell = len(cell_x[ri])
            out.append(f"{pad}  row {ri}" + (" " + _fmt_extras(rd) if rd else "") + ": " + (" | ".join(shown) if shown else "(all cells empty)")
                       + (f"  [{ncell} cell(s), {ncell - len(shown)} empty]" if len(shown) != ncell else ""))
        if len(rows) > max_rows:
            out.append(f"{pad}  ... {len(rows) - max_rows} more row(s) not printed")
        return out

    def walk(el, depth, path, quiet, ctx):
        p = path + "/" + el.tag
        census[p] = census.get(p, 0) + 1
        pad = "  " * depth
        if el.tag == "property_sheet":
            _census_below(el, p, census)                               # the interior is counted whether or not the sheet is printed
        if quiet or printed.get(p, 0) >= per_path:                     # not printed: an ancestor or this path passed its cap
            skipped[p] = skipped.get(p, 0) + 1
            quiet = True
        else:
            printed[p] = printed.get(p, 0) + 1
            lines.extend(sheet_lines(el, pad, p, ctx) if el.tag == "property_sheet" else [pad + _element_label(el)])
        if el.tag == "property_sheet":
            return
        sub = dict(ctx)
        sub["parent"] = el
        if el.findall("node"):
            sub["sibs"] = el.findall("node")                           # the nodes of this graph: what a link's number may point at
        if el.tag == "node":
            sub["node"] = el
        for c in el:
            walk(c, depth + 1, p, quiet, sub)

    walk(root, 0, "", False, {})
    for p, n in sorted(skipped.items()):
        lines.append(f"(path {p}: {n} element(s) not printed: this path or an ancestor's passed {per_path} printed; the census counts them)")
    return lines, census


def dump_lines(name, where, data):
    """Report lines of one graph's complete dump (see the module doc)."""
    out = [f"=== graph {name}  [{where}, {len(data)} bytes]  COMPLETE DUMP"]
    try:
        lines, census = dump_agx(data)
    except ET.ParseError as e:
        return out + [f"  not XML: {e}; the first bytes: {data[:80]!r}"]
    out.append(f"  element paths, with counts ({len(census)} distinct):")
    out += [f"    {n:6d}  {p}" for p, n in sorted(census.items())]
    out.append("  the XML, in file order:")
    out += ["    " + ln for ln in lines]
    return out


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
         "sequences": None, "text_keys": [], "note": "", "raw": []}
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
        f["raw"] = sorted(f["types"])
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


def afx_lines(archives, files, limit=3):
    """Event-like strings of the first .afx files of a folder (the clip descriptors: where a clip's events would live)."""
    out = []
    for item in [x for x in files if x.lower().endswith(".afx")][:limit]:
        archive_name, name = item.split(": ", 1)
        got = find_entry(archives, name)
        if got is None or isinstance(got[1], Exception):
            out.append(f"    {name}: unreadable")
            continue
        words = []
        for m in re.finditer(rb"[\x20-\x7e]{3,}", got[1]):
            w = m.group().decode("latin-1")
            if w not in words:
                words.append(w)
        out.append(f"    {name} ({len(got[1])} bytes): " + (" | ".join(words[:25]) or "no printable strings"))
    return out


def rig_folders(bnam):
    """Folders to list for a record with a rig and no CNAM: the rig's own folder and its animations sibling."""
    folder = bnam.replace("/", "\\").rsplit("\\", 1)[0] if bnam else ""
    if not folder:
        return []
    parent = folder.rsplit("\\", 1)[0] if "\\" in folder else ""
    return [folder, folder + "\\animations"] + ([parent + "\\animations"] if parent else [])


def model_entry(archives, path):
    p = path.replace("/", "\\").lstrip("\\")
    for cand in ([p] if p.lower().startswith("meshes\\") else ["Meshes\\" + p, p]):
        got = find_entry(archives, cand)
        if got is not None:
            return cand, got
    return "Meshes\\" + p if not p.lower().startswith("meshes\\") else p, None


def clip_tied(archives, item, want):
    """True when a guessed-folder clip is tied to the graph: its file name, or a string in its .afx, is exactly (case-blind)
    one of the graph's Sequence Name values.  Nothing else ties a clip found only by folder guesswork to a record."""
    name = item.split(": ", 1)[1].replace("/", "\\").rsplit("\\", 1)[-1]
    if name.rsplit(".", 1)[0].lower() in want:
        return True
    if name.lower().endswith(".afx"):
        got = find_entry(archives, item.split(": ", 1)[1])
        if got is not None and not isinstance(got[1], Exception):
            return any(m.group().decode("latin-1").lower() in want for m in re.finditer(rb"[\x20-\x7e]{3,}", got[1]))
    return False


def model_report(archives, path, cnam="", bnam="", want=()):
    """(lines, facts dict for the outcome table) of one model.  want: the graph's Sequence Name values, lower-cased; a guessed
    rig folder's clips count (facts["af"]) only when they are tied to one of them, a CNAM folder's always do."""
    want = {w.lower() for w in want}
    lines = [f"--- model {path}"]
    facts = {"path": path, "read": False, "sequences": None, "managers": None, "af": None, "raw": []}
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
        facts["sequences"], facts["managers"], facts["raw"] = n["sequences"], n["managers"], n["raw"]
    if cnam:
        files = folder_files(archives, cnam)
        facts["af"] = len([x for x in files if x.lower().endswith((".af", ".afx"))])
        lines.append(f"  CNAM folder {cnam}: {len(files)} .af/.afx/.rig file(s)" + (": " + "; ".join(files[:8]) + (" ..." if len(files) > 8 else "") if files else ""))
        lines += afx_lines(archives, files)
    elif bnam:
        seen_files = []
        for folder in rig_folders(bnam):
            seen_files += [x for x in folder_files(archives, folder) if x not in seen_files]
        clips = [x for x in seen_files if x.lower().endswith((".af", ".afx"))]
        tied = [x for x in clips if clip_tied(archives, x, want)]
        facts["af"], facts["guessed"] = len(tied), [x for x in clips if x not in tied]
        lines.append(f"  no CNAM; rig {bnam}: clips under the rig's folders: {len(seen_files)} file(s)"
                     + (": " + "; ".join(seen_files[:8]) + (" ..." if len(seen_files) > 8 else "") if seen_files else " (none: the clips come from elsewhere)"))
        if clips:
            lines.append(f"  {len(tied)} of {len(clips)} .af/.afx tied to this graph's Sequence Name (by name or .afx string); counted for M1: {len(tied)}")
            if facts["guessed"]:
                lines.append("  found beside the rig, not tied to this graph (guessed folders, not counted): " + "; ".join(facts["guessed"][:8]) + (" ..." if len(facts["guessed"]) > 8 else ""))
        lines += afx_lines(archives, seen_files)
    return lines, facts


# ----------------------------------------------------------------------------------------------- the report
def outcome_table(values, counts, models, esm_read, graphs_read):
    """The rev 9 outcome rows, each 'YES ...', 'NO ...' or 'unread ...' from what was read.  A model whose container the
    parser refused is neither 'no sequences' nor 'has sequences': it is unread, and any raw-scan hit is said."""
    rows = []
    modelled = [m for m in models if m["read"]]
    parsed = [m for m in modelled if m["sequences"] is not None]
    refused = [m for m in modelled if m["sequences"] is None]
    refused_note = ""
    if refused:
        refused_note = (f"; {len(refused)} model(s) had a container the parser refused and are unread: "
                        + ", ".join(m["path"] + (" (raw scan saw " + ", ".join(m["raw"]) + ")" if m["raw"] else "") for m in refused[:4]))
    if not modelled:
        r1 = r2 = "unread (no model was found in the archives read)"
    else:
        match = []
        for m in parsed:
            seqs = {s.lower() for s in m["sequences"]}                 # exact names, case-blind only: Open_01 is not Open01
            want = {v.lower() for v in values.get(m.get("graph", ""), {}).get("Sequence Name", set())}
            if seqs & want:
                match.append(f"{m['path']} carries {sorted(seqs & want)} (graph {m.get('graph', '?')})")
        anyseq = [m["path"] for m in parsed if m["sequences"]]
        if match:
            r1 = "YES: " + "; ".join(match[:4]) + refused_note
        elif anyseq:
            r1 = ("NO among the parsed models: " + ", ".join(anyseq[:4]) + " carry sequences, but not under the graph's Sequence Name values"
                  + refused_note) if not refused else "unread in part: " + ", ".join(anyseq[:4]) + " carry sequences, not under the graph's names" + refused_note
        elif refused:
            r1 = f"unread: {len(parsed)} model(s) parsed with no sequence" + refused_note
        else:
            r1 = f"NO: {len(parsed)} model(s) read, none carries NiControllerSequence"
        rig = [m["path"] for m in parsed if m["af"] and not m["sequences"]]
        if rig:
            r2 = f"YES: {len(rig)} of {len(parsed)} parsed model(s) have .af/.afx in their clip folder and no sequences: " + ", ".join(rig[:4]) + refused_note
        elif refused:
            r2 = "unread: no parsed model has .af/.afx and no sequences" + refused_note
        else:
            r2 = (f"NO: none of {len(parsed)} model(s) read has .af/.afx in its clip folder with no sequences"
                  + ("" if any(m["af"] is not None for m in parsed) else " (no CNAM or rig folder was given for them)"))
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
        todo.append((m, "", "", ""))
        seen.add(m.lower())
    for g in wanted:
        taken = 0
        for h in [h for h in hits if h["graph"] == g and h["model"]]:
            if taken >= a.default_models:
                break
            if h["model"].lower() not in seen:
                seen.add(h["model"].lower())
                todo.append((h["model"], h["CNAM"], g, h["BNAM"]))
                taken += 1
    facts = []
    if not todo:
        out.append("no model to read (none given with --model, and no record named one)")
    for path, cnam, g, bnam in todo:
        lines, f = model_report(archives, path, cnam, bnam, values.get(g, {}).get("Sequence Name", ()))
        f["graph"] = g
        facts.append(f)
        out += (["  (graph " + g + ")"] if g else []) + lines

    # 4. the outcome table
    out += ["", "##### 4. outcome table (animation-needs rev 9), filled in from what was read", ""]
    for finding, got, nxt in outcome_table(values, counts, facts, esm_read, graphs_read):
        out += [f"- {finding}", f"    read: {got}", f"    if so: {nxt}"]
    out.append("")
    return "\n".join(out) + "\n"


def run_dump(a):
    """The --dump-graph report: only the archives are read, only --out is written."""
    out = []
    expanded = expand_archives(a.data, a.game_archive)
    archives = open_archives([p for _, ps in expanded for p in ps])
    wanted = [g.lower().rsplit(".", 1)[0] if g.lower().endswith(".agx") else g.lower() for g in a.dump_graph]
    out.append(f"vault111_anim_graphs --dump-graph (read-only; FAL-489): {', '.join(wanted)}")
    for given, ps in expanded:
        if not ps:
            out.append(f"archive argument {given!r}: nothing matched under {a.data}")
    out.append("archives: " + (", ".join(f"{os.path.basename(p)} ({ar if isinstance(ar, str) else str(len(ar.names)) + ' entries'})" for p, ar in archives) or "none given"))
    index = graph_index(archives)
    for g in wanted:
        hits = index.get(g)
        if not hits:
            out += ["", f"=== graph {g}.agx: unread (no entry of that name in the archives read)"]
            continue
        archive_name, entry, arch, i = hits[0]
        try:
            data = arch.read(i)
        except (ba2.Ba2Error, OSError, struct.error, ValueError) as e:
            out += ["", f"=== graph {g}.agx: entry {entry} in {archive_name} unreadable: {e}"]
            continue
        out += [""] + dump_lines(g + ".agx", f"{archive_name}: {entry}" + (f"; {len(hits) - 1} more entr(ies) of that name not read" if len(hits) > 1 else ""), data)
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------------------------- one form (--dump-form, --refs-to)
FORM_GROUPS = (b"ACTI", b"FURN", b"DOOR", b"MSTT", b"STAT", b"TERM", b"FLOR", b"CONT")
PLACED = (b"REFR", b"ACHR")
CHILD_GROUPS = (6, 8, 9, 10)          # cell children, persistent, temporary, visible distant: the label is the parent cell's form id


def parse_form_id(text):
    try:
        return int(str(text).strip().lower().replace("0x", ""), 16) & 0xFFFFFFFF
    except ValueError:
        raise SystemExit(f"not a hex form id: {text!r}")


def strings_in(data, minimum=4):
    return [m.group().decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minimum, data)]


def sub_line(sig, d, cap=64):
    """One subrecord, as stored: its text when it is all text, else hex (capped), the text strings inside it, and what 4 bytes could be."""
    s = sig.decode("latin1")
    if d and d[-1:] == b"\0" and len(d) > 1 and all(0x20 <= c < 0x7F for c in d[:-1]):
        return f"    {s} [{len(d)}] text {d[:-1].decode('ascii')!r}"
    line = f"    {s} [{len(d)}] hex {d[:cap].hex(' ')}" + (" ..." if len(d) > cap else "")
    if len(d) == 4:
        line += f"   (u32 {struct.unpack('<I', d)[0]:#010x}, float {struct.unpack('<f', d)[0]:.6g})"
    found = strings_in(d)
    if found:
        line += "   strings: " + " | ".join(found[:12]) + (" ..." if len(found) > 12 else "")
    return line


def find_form(plugin, fid):
    """The record with this form id in the flat groups of FORM_GROUPS, (record, None); (None, notes) when it is not there."""
    for label in FORM_GROUPS:
        if label.decode() not in plugin.groups:
            continue
        for start, end in plugin.groups[label.decode()]:
            for item in plugin.walk(start, end):
                if item[0] == "REC" and struct.unpack_from("<I", plugin.buf, item[1] + 12)[0] == fid:
                    return plugin.record_at(item[1]), None
    return None, "searched " + ", ".join(b.decode() for b in FORM_GROUPS if b.decode() in plugin.groups)


def form_lines(plugin, fid, archives):
    rec, note = find_form(plugin, fid)
    out = [f"=== form {fid:08X}"]
    if rec is None:
        return out + [f"  no record with that form id ({note}); unread"]
    out.append(f"  {rec.sig.decode()}  edid {rec.edid or '-'}  flags {rec.flags:#010x}  version {rec.version}  {len(rec.subs)} subrecord(s):")
    out += [sub_line(s, d) for s, d in rec.subs]
    comp, cname = graph_component(rec.subs)
    names = [esm.zstring(d) for s, d in rec.subs if s == b"BFCB"]
    model = model_path(rec.subs)
    out.append(f"  components (BFCB): " + (", ".join(names) or "none"))
    out.append(f"  animation graph component {cname or 'none'}: " + (", ".join(f"{k}={v}" for k, v in sorted(comp.items())) or "no ANAM/BNAM/CNAM"))
    out.append(f"  model: {model or 'no .nif text in the record'}")
    if not model:
        return out
    if not archives:
        return out + ["  model check unread: no --game-archive given"]
    lines, _ = model_report(archives, model, comp.get("CNAM", ""), comp.get("BNAM", ""), ())
    return out + lines


def find_refs(plugin, fid):
    """([(sig, ref form id, cell form id, (x, y, z) or None)], {cell form id: record offset}, records scanned): REFR / ACHR whose NAME is fid."""
    hits, cells, scanned, cur = [], {}, 0, 0
    for label in ("CELL", "WRLD"):
        for start, end in plugin.groups.get(label, []):
            for item in plugin.walk(start, end):
                if item[0] == "GRUP":
                    if item[2] in CHILD_GROUPS and len(item[1]) == 4:
                        cur = struct.unpack("<I", item[1])[0]
                    continue
                if item[2] == b"CELL":
                    cells[struct.unpack_from("<I", plugin.buf, item[1] + 12)[0]] = item[1]
                elif item[2] in PLACED:
                    scanned += 1
                    r = plugin.record_at(item[1])
                    name = r.get(b"NAME")
                    if name is not None and len(name) == 4 and struct.unpack("<I", name)[0] == fid:
                        pos = r.get(b"DATA")
                        hits.append((r.sig.decode(), r.formid, cur, struct.unpack_from("<3f", pos, 0) if pos is not None and len(pos) >= 12 else None))
    return hits, cells, scanned


def refs_lines(plugin, fid, limit):
    hits, cells, scanned = find_refs(plugin, fid)
    out = [f"=== references to {fid:08X} (REFR / ACHR with that NAME, in the CELL and WRLD top groups; {scanned} placed record(s) scanned)"]
    out.append(f"  {len(hits)} found" + (f"; first {min(len(hits), limit)}:" if hits else ""))
    for sig, rid, cell, pos in hits[:limit]:
        cedid = plugin.record_at(cells[cell]).edid if cell in cells else "-"
        out.append(f"    {sig} {rid:08X}  cell {cell:08X} {cedid or '-'}  position " + (", ".join(f"{v:.1f}" for v in pos) if pos else "unread"))
    if not hits:
        out.append("  none found: no placed reference of that base in the groups read (the game may place it another way: unread)")
    return out


def run_form(a):
    """The --dump-form / --refs-to report: Starfield.esm and, for the model check, the archives are read; only --out is written."""
    out = ["vault111_anim_graphs --dump-form / --refs-to (read-only; FAL-489)"]
    esm_path = a.esm or os.path.join(a.data, "Starfield.esm")
    expanded = expand_archives(a.data, a.game_archive)
    archives = open_archives([p for _, ps in expanded for p in ps])
    for given, ps in expanded:
        if not ps:
            out.append(f"archive argument {given!r}: nothing matched under {a.data}")
    out.append("archives: " + (", ".join(f"{os.path.basename(p)} ({ar if isinstance(ar, str) else str(len(ar.names)) + ' entries'})" for p, ar in archives) or "none given"))
    if not os.path.isfile(esm_path):
        return "\n".join(out + [f"unread: {esm_path} not found"]) + "\n"
    try:
        with esm.Plugin(esm_path) as plugin:
            for h in a.dump_form:
                out += [""] + form_lines(plugin, parse_form_id(h), archives)
            for h in a.refs_to:
                out += [""] + refs_lines(plugin, parse_form_id(h), a.refs_limit)
    except (esm.EsmError, OSError, struct.error) as e:
        out.append(f"unread: {esm_path}: {e}")
    return "\n".join(out) + "\n"


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default=STARFIELD)
    ap.add_argument("--esm")
    ap.add_argument("--game-archive", action="append", default=[], help='a Starfield archive (name in --data, * allowed), e.g. "Starfield - Animations.ba2"')
    ap.add_argument("--graph", action="append", help="a graph name (replaces the default list)")
    ap.add_argument("--dump-graph", action="append", default=[], help="a graph name: write only the complete dump of it (repeatable; no esm, no models)")
    ap.add_argument("--dump-form", action="append", default=[], help="a hex form id: write only every subrecord of that record and a check of its model against the archives (repeatable)")
    ap.add_argument("--refs-to", action="append", default=[], help="a hex form id: write only the REFR / ACHR placements of that base (repeatable; reads the whole CELL and WRLD groups)")
    ap.add_argument("--refs-limit", type=int, default=12)
    ap.add_argument("--model", action="append", default=[], help="a model path to read (repeatable)")
    ap.add_argument("--per-graph", type=int, default=12)
    ap.add_argument("--default-models", type=int, default=2)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    text = run_dump(a) if a.dump_graph else run_form(a) if (a.dump_form or a.refs_to) else run(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"vault111_anim_graphs ok: report {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
