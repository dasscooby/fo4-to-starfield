"""Offline plugin-load check: reject a test plugin on the build machine, before a kit is handed to the PC.

Two game sessions were lost to plugins that loaded and then crashed the game (FAL-208 at a cell override, FAL-213 at
`Cast`, a spell/effect written from nothing). This reads the raw bytes (no Mutagen, no game, no load order file) and
reports what it can prove is wrong. It cannot prove a plugin loads: a clean report is "nothing found", not a PASS in game.

PROBLEMS (exit 1; each rests on a rule with evidence):
    structure      TES4 first with a HEDR; every record and GRUP inside its parent; subrecords parse; compressed
                   records inflate to the size they state
    masters        none twice, none the plugin itself, no BlueprintShips master, Starfield.esm first, every master
                   known (a plugin of the kit, one of the game's, or listed in `known`), and in the kit's load order
                   each master comes before the plugin that lists it
    form ids       the top byte is at most the master count; the plugin's own records are 0x800 or above, not twice;
                   a reference to the plugin's own record that is not in the plugin is dangling
    required       a new SPEL, MGEF, ALCH, HAZD, PERK or placed reference carries every subrecord that all sampled
                   vanilla records of its class carry (REQUIRED, checked against docs/measurements/sf_esm.json by
                   tests/test_plugin_verify.py)
    persistence    a record in a persistent child group (GRUP type 8) has flag 0x400; one in a temporary group
                   (type 9) has not
    exterior       no persistent child group (type 8) under an OVERRIDE of a master's exterior cell (inside an
                   exterior block or sub-block, types 4 / 5; a plugin's own new cell only warns: the planet probe
                   has that layout and ran in game, but its cell never loaded): in Starfield.esm 0 of 18,300 exterior cells have one, all 431
                   persistent groups of its worlds sit under the world's own persistent cell, and FAL-208's plugin,
                   the one file with such a group, crashed the game at SF+0x41efd6 (FAL-273, PC scan 11 Nov; the
                   link from the group to the crash was the PC's inference and the 11 Nov ladder showed it is NOT the group:
                   see the WARNINGS below). Put a persistent reference in an override of the world's persistent cell instead.
WARNINGS (listed, do not fail): an override CELL record of a master's exterior cell (PC ladder 11 Nov, FAL-273: the override
alone, with no reference, killed the game 28 s after arrival and moved `coc` to the world's origin cell; one core world, so a
warning and not a refusal); rules without evidence that they matter (the same rule for QUST, WRLD, LCTN,
CELL, MISC, STAT: the planet probe loads in game without them; a world or cell child group whose WRLD or CELL
record is not in the plugin; HEDR counts that differ from the real counts).

Used by `scripts/verify_plugin.py`, and by writers through `assert_loadable` so a staging script stops before a bad kit
is installed. Meant for the small plugins our tools write; a whole Starfield.esm is slow here (every record is parsed).
"""
import os
import struct

from .planet import esm

BLUEPRINT = "blueprintships-starfield.esm"
STARFIELD = "starfield.esm"
OWN_MIN = 0x800

# Subrecords present in every record of the class in the vanilla sample of 1.16.244 (docs/measurements/sf_esm.json,
# "sampled" records per class: SPEL 300, MGEF 300, ALCH 300, HAZD 75, PERK 300, QUST 300, WRLD 300, LCTN 300, REFR
# 300, CELL 300, MISC 300, STAT 300). A sample, not the whole game.
#
# REQUIRED (a problem): the classes of the shared writer (effects, consumables, hazards, perks), where a hand-written
# record is what crashed the game at `Cast` (FAL-213: the sample has ETYP and SPIT on every SPEL, DNAM on every MGEF;
# which missing field the engine read as null is still unresolved) and every placed reference's NAME.
REQUIRED = {
    "SPEL": ("EDID", "OBND", "ODTY", "ETYP", "DESC", "SPIT"),
    "MGEF": ("EDID", "DATA", "DNAM"),
    "ALCH": ("EDID", "OBND", "ODTY", "FLLD", "DESC", "DATA", "ENIT", "DNAM"),
    "HAZD": ("EDID", "OBND", "ODTY", "MODL", "FLLD", "DNAM"),
    "PERK": ("EDID",),
    "REFR": ("NAME", "DATA"),
}
# SAMPLED_ONLY (a warning): classes where plugins that loaded in game (the planet probe's QUST, LCTN, WRLD and CELL
# records) lack fields the whole sample carries, so "every vanilla record has it" is not "the game needs it".
SAMPLED_ONLY = {
    "QUST": ("EDID", "DNAM", "NEXT", "ANAM"),
    "WRLD": ("EDID", "DNAM", "MNAM", "ONAM", "NAMA", "DATA", "FNAM", "NAM0", "GNAM", "XCLW", "WHGT", "HNAM"),
    "LCTN": ("EDID", "DATA", "RNAM", "ANAM", "TNAM"),
    "CELL": ("EDID", "DATA", "XCLL", "LTMP", "XCLW", "XILS"),
    "MISC": ("EDID", "OBND", "ODTY", "MODL", "FLLD", "DATA"),
    "STAT": ("EDID", "OBND", "ODTY", "FLLD", "DNAM"),
}

# form id fields checked for the master index and for dangling own ids: (record sigs or None for any, subrecord)
REF_FIELDS = (
    (("REFR", "ACHR"), "NAME"),
    (("CELL", "WRLD"), "XLCN"),
    (("CELL",), "LTMP"),
    (("LCTN",), "PNAM"),
)
GROUP_PERSISTENT, GROUP_TEMPORARY = 8, 9
GROUP_WORLD_CHILDREN, GROUP_CELL_CHILDREN = 1, 6
GROUP_EXTERIOR_BLOCK, GROUP_EXTERIOR_SUB_BLOCK = 4, 5


class PluginVerifyError(Exception):
    """assert_loadable: the report's problems, one per line."""


class Report:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.masters = []
        self.problems = []
        self.warnings = []
        self.records = 0

    @property
    def ok(self):
        return not self.problems

    def bad(self, text):
        self.problems.append(f"{self.name}: {text}")

    def warn(self, text):
        self.warnings.append(f"{self.name}: {text}")

    def as_dict(self):
        return {"plugin": self.name, "ok": self.ok, "masters": self.masters, "records": self.records,
                "problems": self.problems, "warnings": self.warnings}


def _masters(rep, plugin, load_order, known, game):
    ms = plugin.masters
    rep.masters = list(ms)
    folded = [m.casefold() for m in ms]
    me = rep.name.casefold()
    seen = set()
    for m, f in zip(ms, folded):
        if f in seen:
            rep.bad(f"master {m} listed twice")
        seen.add(f)
        if f == me:
            rep.bad("lists itself as a master")
        if f == BLUEPRINT:
            rep.bad(f"lists {m} as a master (blueprint plugins load last and cannot be depended on)")
    if ms and folded[0] != STARFIELD and STARFIELD in folded:
        rep.bad(f"Starfield.esm is master {folded.index(STARFIELD) + 1}, not the first")
    order = [n.casefold() for n in load_order] if load_order else None
    for m, f in zip(ms, folded):
        if f in game or f in known or (order and f in order):
            pass
        else:
            rep.bad(f"master {m} is not a game master, not in the kit and not given as known")
        if order and me in order and f in order and order.index(f) > order.index(me):
            rep.bad(f"master {m} loads after this plugin in the load order (masters must come first)")
    # the order of the master list itself: a master the kit loads later than another must not be listed before it
    if order:
        pos = [order.index(f) for f in folded if f in order]
        if pos != sorted(pos):
            rep.bad("masters are listed in a different order than they load")


def _check_ref(rep, rec, sub, data, n_masters, own_ids, seen_dangling):
    if len(data) < 4:
        rep.bad(f"{rec.sig.decode()} {rec.formid:08X}: {sub} is {len(data)} bytes, not a form id")
        return
    ref = struct.unpack_from("<I", data, 0)[0]
    if ref == 0:
        return
    idx, local = ref >> 24, ref & 0xFFFFFF
    if idx > n_masters:
        rep.bad(f"{rec.sig.decode()} {rec.formid:08X}: {sub} {ref:08X} has master index {idx}, "
                f"but the plugin has {n_masters} masters")
    elif idx == n_masters and ref not in own_ids and ref not in seen_dangling:
        seen_dangling.add(ref)
        rep.bad(f"{rec.sig.decode()} {rec.formid:08X}: {sub} {ref:08X} names a record of this plugin that is not in it")


def verify(path, load_order=None, known=(), game=(STARFIELD,), deep=True):
    """Report for one plugin. load_order: plugin names in load order (the kit's, with the game's masters first);
    known: further master names to accept; game: master names the game itself provides."""
    rep = Report(path)
    try:
        plugin = esm.Plugin(path)
    except (esm.EsmError, OSError) as e:
        rep.bad(str(e))
        return rep
    with plugin:
        game = {g.casefold() for g in game}
        known = {k.casefold() for k in known}
        _masters(rep, plugin, load_order, known, game)
        hedr = plugin.header.get(b"HEDR")
        if hedr is None or len(hedr) < 12:
            rep.bad("TES4 has no HEDR of 12 bytes")
        n_masters = len(plugin.masters)
        try:
            items = []
            for label, spans in plugin.groups.items():
                for start, end in spans:
                    items.extend(plugin.walk(start, end))
        except esm.EsmError as e:
            rep.bad(str(e))
            return rep
        n_groups = len(plugin.groups) + sum(1 for it in items if it[0] == "GRUP")
        recs = []
        if deep:
            try:
                recs = [(it, esm.Record.parse(plugin.buf, it[1])) for it in items if it[0] == "REC"]
            except esm.EsmError as e:
                rep.bad(str(e))
                return rep
        rep.records = len(recs) if deep else sum(1 for it in items if it[0] == "REC")
        if hedr is not None and len(hedr) >= 12 and deep:
            count = struct.unpack_from("<I", hedr, 4)[0]
            if count != rep.records + n_groups:
                rep.warn(f"HEDR counts {count} records and groups, the file has {rep.records + n_groups}")
        if not deep:
            return rep
        own_ids, dup = set(), set()
        for it, rec in recs:
            if rec.formid >> 24 == n_masters:
                (dup if rec.formid in own_ids else own_ids).add(rec.formid)
        for fid in sorted(dup):
            rep.bad(f"own form id {fid:08X} used by two records")
        dangling = set()
        for it, rec in recs:
            sig = rec.sig.decode("latin-1")
            idx, local = rec.formid >> 24, rec.formid & 0xFFFFFF
            if idx > n_masters:
                rep.bad(f"{sig} {rec.formid:08X}: master index {idx}, but the plugin has {n_masters} masters")
            elif idx == n_masters and local < OWN_MIN:
                rep.bad(f"{sig} {rec.formid:08X}: an own record below 0x800 collides with the engine's reserved ids")
            overrides = idx < n_masters
            req = () if overrides else REQUIRED.get(sig, ())     # an override carries its master's fields
            have = {s for s, _ in rec.subs}
            miss = [r for r in req if r.encode("ascii") not in have]
            if miss:
                rep.bad(f"{sig} {rec.formid:08X} {rec.edid or ''}: missing {', '.join(miss)} "
                        f"(present on every sampled vanilla {sig})")
            soft = () if overrides else SAMPLED_ONLY.get(sig, ())
            miss = [r for r in soft if r.encode("ascii") not in have]
            if miss:
                rep.warn(f"{sig} {rec.formid:08X} {rec.edid or ''}: lacks {', '.join(miss)} (on every sampled "
                         f"vanilla {sig}; not proven needed)")
            for sigs, sub in REF_FIELDS:
                if sig in sigs:
                    for d in rec.all(sub):
                        _check_ref(rep, rec, sub, d, n_masters, own_ids, dangling)
            for kw in rec.all(b"KWDA"):
                for i in range(0, len(kw) - len(kw) % 4, 4):
                    _check_ref(rep, rec, "KWDA", kw[i:i + 4], n_masters, own_ids, dangling)
        _groups(rep, plugin, n_masters, {it[1]: r for it, r in recs})
    return rep


def _groups(rep, plugin, n_masters, by_offset):
    """Persistence flags and the group/record pairing, walked in file order with the group types in force."""
    stack = []                              # (end offset, group type)
    last_rec = {}                           # depth -> last record seen at that depth
    all_ids = {r.formid: r for r in by_offset.values()}
    for label, spans in plugin.groups.items():
        for start, end in spans:
            stack.clear()
            last_rec.clear()
            for it in plugin.walk(start, end):
                if it[0] == "GRUP":
                    _, lab, gtype, s, e, depth = it
                    while stack and stack[-1][0] <= s - 24:
                        stack.pop()
                    stack.append((e, gtype, lab))
                    if gtype == GROUP_PERSISTENT and any(g in (GROUP_EXTERIOR_BLOCK, GROUP_EXTERIOR_SUB_BLOCK) for _, g, _l in stack[:-1]):
                        # the enclosing cell children group (type 6) names the cell
                        cell_id = next((struct.unpack("<I", l)[0] for _, g, l in reversed(stack) if g == GROUP_CELL_CHILDREN), 0)
                        if cell_id >> 24 < n_masters:
                            rep.bad(f"persistent child group under the exterior cell {cell_id:08X}, an override of a master's cell: "
                                    "no Starfield world has one (all persistent groups are under the world's persistent cell); "
                                    "FAL-208's plugin with this layout crashed the game (FAL-273)")
                        else:
                            rep.warn(f"persistent child group under the plugin's own exterior cell {cell_id:08X}: no Starfield world has "
                                     "one (unproven for a new cell; an override of a master's cell is refused)")
                    if gtype in (GROUP_WORLD_CHILDREN, GROUP_CELL_CHILDREN):
                        fid = struct.unpack("<I", lab)[0]
                        kind = "WRLD" if gtype == GROUP_WORLD_CHILDREN else "CELL"
                        owner = all_ids.get(fid)
                        if owner is None:
                            rep.warn(f"{kind} children group {fid:08X} has no {kind} record in this plugin "
                                     "(unproven whether the game needs it)")
                        elif owner.sig.decode() != kind:
                            rep.bad(f"{kind} children group {fid:08X} belongs to a {owner.sig.decode()} record")
                        elif gtype == GROUP_CELL_CHILDREN:
                            prev = last_rec.get(depth)
                            if prev is not None and prev.formid != fid:
                                rep.bad(f"CELL children group {fid:08X} follows record {prev.formid:08X}, "
                                        "not its own cell")
                    continue
                _, off, sig, depth = it
                rec = by_offset.get(off)
                while stack and stack[-1][0] <= off:
                    stack.pop()
                gtypes = [g for _, g, _l in stack]
                if rec is not None:
                    last_rec[depth] = rec
                    if rec.sig == b"CELL" and rec.formid >> 24 < n_masters and any(
                            g in (GROUP_EXTERIOR_BLOCK, GROUP_EXTERIOR_SUB_BLOCK) for g in gtypes):
                        rep.warn(f"CELL {rec.formid:08X} is an override of a master's exterior cell: in game, FAL-273's plugin with only "
                                 "this override (no reference) crashed 28 s after arrival and moved the arrival to the world's origin "
                                 "cell; the mission's layout overrides the world's persistent cell only (one world seen: not proven general)")
                    in_p, in_t = GROUP_PERSISTENT in gtypes, GROUP_TEMPORARY in gtypes
                    if in_p and not rec.flags & esm.PERSISTENT:
                        rep.bad(f"{rec.sig.decode()} {rec.formid:08X} sits in a persistent group without flag 0x400")
                    if in_t and rec.flags & esm.PERSISTENT:
                        rep.bad(f"{rec.sig.decode()} {rec.formid:08X} sits in a temporary group with flag 0x400")


def verify_kit(paths, game=(STARFIELD,), known=(), deep=True):
    """Reports for plugins that are installed together; `paths` in load order. The game's own masters come first
    in the load order, so a kit plugin that lists a later kit plugin as a master is refused."""
    order = list(game) + [os.path.basename(p) for p in paths]
    return [verify(p, load_order=order, known=known, game=game, deep=deep) for p in paths]


def assert_loadable(paths, **kw):
    """Raise PluginVerifyError listing every problem of a plugin or of a kit (a path or a list, in load order)."""
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    reports = verify_kit([os.fspath(p) for p in paths], **kw)
    bad = [p for r in reports for p in r.problems]
    if bad:
        raise PluginVerifyError("plugin would not load cleanly:\n" + "\n".join(bad))
    return reports
