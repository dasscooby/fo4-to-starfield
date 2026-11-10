"""One shared writer for effects, spells, consumables, hazards, perks and actor values: no probe writes such a record
from scratch again.

Why: FAL-213's spell, effect and RadAway were written from nothing (no SPEL ETYP/EFIF/MUID, no MGEF DNAM; every one of
the 300 sampled vanilla records carries them) and the game died on `Cast` (0xC0000005 at +0x15c, cause unresolved). So
a record here is always a CLONE of a real Starfield record (the template): every subrecord the template has stays,
byte for byte, except those the caller replaces on purpose. Nothing is invented.

Three steps, each usable alone:

    dump       `dump_records(starfield_esm, ...)` -> JSON of real records (every subrecord's length and hex) with, per
               subrecord signature, which byte offsets are the same in every sampled record and which vary. This is the
               Starfield-side field oracle (stage additions item 2). It holds game bytes: keep it out of Git
               (scripts/dump_starfield_records.py writes under the output folder you name, nothing else).
    template   `Template.from_plugin(path, sig, edid=None, pick=None)` or `Template.from_dump(dump, sig, edid)`:
               one real record, found by editor id or by a predicate on the parsed record.
    write      `make(template, formid, edid, replace=..., full=..., desc=...)` -> a new Record. `set_field` changes
               bytes inside a subrecord at an offset the DUMP shows to vary (`Layout.check_offset`); an offset the
               dump shows constant in every sample is refused unless `force=True`, because a constant byte is a flag
               or a version, not a value.

What is checked at write time (all of it offline; none of it proves the game loads the record):
    * the template is the class asked for and carries every subrecord the class requires (plugin_verify.REQUIRED);
    * FULL and DESC: Starfield.esm is localized, so a template's FULL/DESC is a 4-byte string id; our plugins are not,
      where the same bytes read as a string. `make` therefore REPLACES both (`full`, `desc` default to "") and
      refuses a template whose text it could not replace;
    * form ids in a copied record keep their master index, so the plugin's master list must start with Starfield.esm
      (`PluginWriter` of fo4sf.planet.esm; `check_masters`);
    * `retarget_effect` replaces the effect id (EFID: the MGEF form id, 4 bytes) of one effect entry of a SPEL or ALCH
      and leaves its EFIT, EFIF and MUID (the entry's data, the template's ids) as they were.
"""
import json
import os
import struct

from .planet import esm
from . import plugin_verify

CLASSES = ("SPEL", "MGEF", "ALCH", "HAZD", "PERK", "AVIF")
TEXT = (b"FULL", b"DESC")
STARFIELD = "starfield.esm"


class WriterError(ValueError):
    pass


def _sig(s):
    return s if isinstance(s, bytes) else s.encode("ascii")


# ------------------------------------------------------------------------------------------------ dump
def _layout(samples):
    """{sub signature: {"records": n, "lengths": {len: n}, "constant": [offsets same in every sample of the most
    common length], "varying": [offsets that differ]}} for the (sig, data) lists of the sampled records."""
    by = {}
    for subs in samples:
        for s, d in subs:
            by.setdefault(s.decode("latin-1"), []).append(d)
    out = {}
    for s, datas in sorted(by.items()):
        lengths = {}
        for d in datas:
            lengths[len(d)] = lengths.get(len(d), 0) + 1
        common = max(lengths, key=lambda n: (lengths[n], n))
        same = [d for d in datas if len(d) == common]
        const, vary = [], []
        for i in range(common):
            (const if len({d[i] for d in same}) == 1 and len(same) > 1 else vary).append(i)
        out[s] = {"records": len(datas), "lengths": {str(k): v for k, v in sorted(lengths.items())},
                  "length": common, "constant": const if len(same) > 1 else [], "varying": vary if len(same) > 1 else []}
    return out


def _ranges(offsets):
    out = []
    for o in offsets:
        if out and o == out[-1][1] + 1:
            out[-1] = (out[-1][0], o)
        else:
            out.append((o, o))
    return out


def dump_records(path, classes=CLASSES, per_class=40, edids=(), keep=3):
    """Real records of a plugin as a dict. Per class: the first `per_class` records feed the layout; `keep` of them
    (plus every record whose editor id is in `edids`) are written out whole, subrecord by subrecord, in hex."""
    want = {e.casefold() for e in edids}
    out = {"plugin": path, "version": 1, "classes": {}}
    found_any = set()
    with esm.Plugin(path) as plugin:
        out["masters"] = list(plugin.masters)
        out["localized"] = plugin.localized
        for sig in classes:
            sample, kept, found = [], [], set()
            for rec in plugin.records(sig, [sig]):
                counted = len(sample) < per_class
                if counted:
                    sample.append(rec.subs)
                named = rec.edid.casefold() in want
                if named:
                    found.add(rec.edid.casefold())
                if named or (counted and len(kept) < keep):
                    kept.append(rec)
                if not counted and not want:
                    break
            found_any |= found
            out["classes"][sig] = {
                "sampled": len(sample),
                "layout": _layout(sample),
                "records": [{"formid": f"{r.formid:08X}", "edid": r.edid, "flags": r.flags, "version": r.version,
                             "subs": [[s.decode("latin-1"), len(d), d.hex()] for s, d in r.subs]} for r in kept],
                "found_edids": sorted(found)}
    # an editor id belongs to one class: it is missing only when no requested class holds it
    out["missing_edids"] = sorted(want - found_any)
    return out


def dump_text(dump):
    """The dump as a table a person can read: per class, each subrecord signature with its length, and which byte
    ranges differ between records (candidate value fields) and which never do (flags, versions, fixed ids)."""
    lines = [f"plugin {dump['plugin']}  localized={dump.get('localized')}  masters={dump.get('masters')}"]
    for sig, c in dump["classes"].items():
        lines.append(f"\n== {sig}: {c['sampled']} sampled records, {len(c['records'])} written out")
        for sub, lay in c["layout"].items():
            vary = ",".join(f"{a}" if a == b else f"{a}-{b}" for a, b in _ranges(lay["varying"]))
            lines.append(f"  {sub}  in {lay['records']}  lengths {lay['lengths']}  varying bytes [{vary}]")
        for r in c["records"]:
            lines.append(f"  -- {r['formid']} {r['edid']} flags={r['flags']:#x} form version {r['version']}")
            for s, n, h in r["subs"]:
                lines.append(f"     {s} {n:>4}  {h[:96]}{'...' if len(h) > 96 else ''}")
    if dump.get("missing_edids"):
        lines.append(f"\neditor ids not found in any class: {dump['missing_edids']}")
    return "\n".join(lines)


class Layout:
    """The per-signature layout of a dump: which offsets of a subrecord vary between real records."""

    def __init__(self, dump):
        self.classes = dump["classes"]

    def sub(self, sig, sub):
        c = self.classes.get(sig)
        if c is None or sub not in c["layout"]:
            raise WriterError(f"the dump has no {sig} {sub}")
        return c["layout"][sub]

    def check_offset(self, sig, sub, offset, size):
        lay = self.sub(sig, sub)
        if lay["records"] < 2 or not lay["varying"]:
            raise WriterError(f"{sig} {sub}: the dump has too few records to show which bytes carry values")
        varying = set(lay["varying"])
        if not any(o in varying for o in range(offset, offset + size)):
            raise WriterError(f"{sig} {sub} bytes {offset}..{offset + size - 1} are the same in all {lay['records']} "
                              "sampled vanilla records: a flag or a version, not a value (force=True overrides)")


# ------------------------------------------------------------------------------------------------ template
class Template:
    """One real record to clone."""

    def __init__(self, record, origin):
        self.record, self.origin = record, origin

    @property
    def sig(self):
        return self.record.sig.decode("ascii")

    @classmethod
    def from_plugin(cls, path, sig, edid=None, pick=None):
        """The record of class `sig` with editor id `edid`, or the first one `pick(record)` accepts."""
        if (edid is None) == (pick is None):
            raise WriterError("name the template by edid or by pick, not both and not neither")
        with esm.Plugin(path) as plugin:
            for rec in plugin.records(sig, [sig]):
                if (edid is not None and rec.edid.casefold() == edid.casefold()) or (pick is not None and pick(rec)):
                    return cls(rec, f"{path}:{rec.formid:08X}:{rec.edid}")
        raise WriterError(f"no {sig} {'named ' + edid if edid else 'matching the predicate'} in {path}")

    @classmethod
    def from_dump(cls, dump, sig, edid):
        """The written-out record `edid` of a dump (dump_records(..., edids=[edid]))."""
        for r in dump["classes"].get(sig, {}).get("records", []):
            if r["edid"].casefold() == edid.casefold():
                rec = esm.Record(sig, int(r["formid"], 16), [(s.encode("latin-1"), bytes.fromhex(h))
                                                            for s, _, h in r["subs"]], r["flags"] & ~esm.COMPRESSED,
                                 0, r["version"])
                return cls(rec, f"dump:{r['formid']}:{r['edid']}")
        raise WriterError(f"the dump has no {sig} named {edid}")


def save_dump(dump, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=1)


def load_dump(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------------------------------------ write
def check_masters(masters):
    if not masters or masters[0].casefold() != STARFIELD:
        raise WriterError("a cloned record keeps its form ids' master index: the plugin's first master must be "
                          f"Starfield.esm, got {masters[:1]}")


def _text(value):
    return esm.zbytes(value)


def make(template, formid, edid, replace=None, full="", desc="", drop=()):
    """A new Record cloned from `template`. replace: {sub signature: bytes} swaps whole subrecords (the first one
    of that signature); drop: signatures removed (every one); full/desc: the text, as a plain string (see the module
    docstring: the template's string ids cannot be kept in a plugin that is not localized)."""
    rec = template.record
    sig = template.sig
    req = plugin_verify.REQUIRED.get(sig, ())
    have = {s for s, _ in rec.subs}
    miss = [r for r in req if _sig(r) not in have]
    if miss:
        raise WriterError(f"template {template.origin} lacks {', '.join(miss)}: not a usable {sig} template")
    new = rec.copy(formid)
    new.flags &= ~esm.COMPRESSED
    subs = []
    for s, d in new.subs:
        if s == b"EDID":
            d = _text(edid)
        elif s in TEXT:
            if len(d) not in (4, 0) and not d.endswith(b"\0"):
                raise WriterError(f"template {template.origin}: {s.decode()} is neither a string id nor a string")
            d = _text(full if s == b"FULL" else desc)
        subs.append((s, d))
    names = {_sig(k): v for k, v in (replace or {}).items()}
    for k in names:
        if k not in {s for s, _ in subs}:
            raise WriterError(f"replace {k.decode()}: the template has no such subrecord (nothing is added blind)")
    done, out = set(), []
    for s, d in subs:
        if s in names and s not in done:
            d = names[s]
            done.add(s)
        if s not in {_sig(x) for x in drop}:
            out.append((s, d))
    new.subs = out
    return new


def set_field(rec, sub, offset, fmt, value, layout=None, force=False):
    """Pack `value` with struct `fmt` into the first `sub` subrecord of rec at `offset`. With a `layout` (from a
    dump), the bytes must be ones that vary between real records; without one, `force=True` is required: a field
    offset nobody checked is a guess."""
    sub = _sig(sub)
    i = rec.index(sub)
    if i < 0:
        raise WriterError(f"{rec.sig.decode()} {rec.edid}: no {sub.decode()} subrecord")
    data = bytearray(rec.subs[i][1])
    size = struct.calcsize("<" + fmt)
    if offset < 0 or offset + size > len(data):
        raise WriterError(f"{sub.decode()} is {len(data)} bytes: {fmt} at {offset} does not fit")
    if layout is not None:
        if not force:
            layout.check_offset(rec.sig.decode(), sub.decode(), offset, size)
    elif not force:
        raise WriterError("set_field needs the dump's layout (or force=True for an offset nobody checked)")
    struct.pack_into("<" + fmt, data, offset, value)
    rec.subs[i] = (sub, bytes(data))
    return rec


def retarget_effect(rec, mgef_formid, index=0):
    """Point effect entry `index` of a SPEL or ALCH at another effect (its EFID); EFIT, EFIF and MUID stay."""
    if rec.sig not in (b"SPEL", b"ALCH"):
        raise WriterError(f"{rec.sig.decode()} has no effect entries")
    ids = [i for i, (s, _) in enumerate(rec.subs) if s == b"EFID"]
    if index >= len(ids):
        raise WriterError(f"{rec.edid}: {len(ids)} effect entries, no entry {index}")
    i = ids[index]
    if len(rec.subs[i][1]) != 4:
        raise WriterError(f"{rec.edid}: EFID is {len(rec.subs[i][1])} bytes, not a form id")
    rec.subs[i] = (b"EFID", struct.pack("<I", mgef_formid))
    return rec


def write_plugin(path, masters, records, known=()):
    """Write the plugin and run the offline load check (fo4sf.plugin_verify) on the result; raises PluginVerifyError
    (the file is removed) when it finds problems."""
    check_masters(masters)
    w = esm.PluginWriter(masters, esm.ESM)
    for r in records:
        w.add(r)
    w.write(path)
    try:
        plugin_verify.assert_loadable(path, known=known)
    except plugin_verify.PluginVerifyError:
        os.remove(path)
        raise
    return w
