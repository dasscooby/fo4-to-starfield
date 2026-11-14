"""Names only from a movie's ActionScript 3 (FAL-614, the S1-R1 read; docs/spikes/pipboy-fo4-rebuild-plan.md): which
class each member sits in, which instances are placed by name, and which names each method uses. It reads the movie in
memory (from a SWF file, or from a BA2 archive with src/fo4sf/ba2.py) and prints names, never code, bytes or
sentences.

usage: python scripts/ui/swf_names.py <file.swf>...
       python scripts/ui/swf_names.py --ba2 <archive.ba2> <name.swf>...      a name is matched at the end of the path

Lines, one fact each:
  file=<name> signature= version= stage=<w>x<h> abc=<count>
                                                  (file=<name> not_swf=1: not a movie; found=0: not in the archive)
  symbol id=<n> class=<name>                      SymbolClass: id 0 is the root's class
  place in=<sprite id, 0 the root> depth=<n> id=<character> class=<class or -> name=<instance name>
  class name=<name> super=<name> sealed=<0|1> final=<0|1> interface=<0|1>
  trait of=<instance|class|script> kind=<slot|const|method|getter|setter|class|function> access=<public|private|...>
        name=<name> [type=<name>]
  uses method=<owner> calls=<names called> names=<names read or written> strings=<identifier strings pushed>
       other_strings=<count of strings that are not identifiers>
  partial method=<owner> at=<opcode>              a body with an opcode this reader does not know: its names stop there
A method's owner is <class>.<trait name> (get:<name> and set:<name> for accessors), <class>.<init> (constructor), <class>.<cinit>, script<n>.<init>, or the
owner of the body that creates it with /fn appended; #<index> when nothing names it. Identifiers are letters, digits,
_, $, . and :, at most 64 characters, as in read D2; anything else is counted, not printed. Output goes to stdout;
nothing is written. The output of a player's file stays private.
"""
import argparse
import os
import re
import struct
import sys
import zlib

NAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$.:]{0,63}")
DO_ABC1, DO_ABC, SYMBOL_CLASS, DEFINE_SPRITE, PLACE_OBJECT2, PLACE_OBJECT3, END = 72, 82, 76, 39, 26, 70, 0
ACCESS = {0x05: "private", 0x08: "namespace", 0x16: "public", 0x17: "internal", 0x18: "protected", 0x19: "explicit",
          0x1A: "static_protected"}
TRAIT_KINDS = ("slot", "method", "getter", "setter", "class", "function", "const")

# AVM2 opcodes by their operands: u30 (a u30), mn (a multiname index, u30), str (a string index, u30), s24, u8
_NONE = (0x01, 0x02, 0x03, 0x07, 0x09, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x21, 0x23, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B,
         0x30, 0x47, 0x48, 0x57, 0x64, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x81, 0x82, 0x83, 0x84, 0x85,
         0x87, 0x88, 0x89, 0x90, 0x91, 0x93, 0x95, 0x96, 0x97, 0xB3, 0xB4, 0xC0, 0xC1, 0xC4, 0xC5, 0xC6, 0xC7,
         *range(0x35, 0x3F), *range(0x50, 0x53), 0x70, *range(0xA0, 0xB2), 0xF3,
         *range(0xD0, 0xD8))
_U30 = (0x06, 0x08, 0x25, 0x2D, 0x2E, 0x2F, 0x31, 0x41, 0x42, 0x49, 0x53, 0x55, 0x56, 0x58, 0x5A, 0x62, 0x63, 0x6C,
        0x6D, 0x6E, 0x6F, 0x92, 0x94, 0xC2, 0xC3, 0xF0, 0xF1, 0xF2)
_MN = (0x04, 0x05, 0x59, 0x5D, 0x5E, 0x5F, 0x60, 0x61, 0x66, 0x68, 0x6A, 0x80, 0x86, 0xB2)
_MN_ARGS = (0x45, 0x46, 0x4A, 0x4C, 0x4E, 0x4F)                      # a multiname, then an argument count
_CALLS = (0x45, 0x46, 0x4A, 0x4C, 0x4E, 0x4F)
_S24 = tuple(range(0x0C, 0x1B))
OP_PUSHSTRING, OP_NEWFUNCTION, OP_PUSHBYTE, OP_GETSCOPEOBJECT, OP_LOOKUPSWITCH, OP_DEBUG = 0x2C, 0x40, 0x24, 0x65, 0x1B, 0xEF
OP_HASNEXT2, OP_CALLMETHOD, OP_CALLSTATIC = 0x32, 0x43, 0x44


class SwfNamesError(ValueError):
    pass


class Reader:
    def __init__(self, data, pos=0):
        self.b, self.at = data, pos

    def u8(self):
        if self.at >= len(self.b):
            raise SwfNamesError("read past the end")
        self.at += 1
        return self.b[self.at - 1]

    def u16(self):
        v = struct.unpack_from("<H", self.b, self.at)[0]
        self.at += 2
        return v

    def u30(self):
        value = shift = 0
        while True:
            byte = self.u8()
            value |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80 or shift >= 35:
                return value

    def skip(self, n):
        if self.at + n > len(self.b):
            raise SwfNamesError("read past the end")
        self.at += n


class Abc:
    """One ABC block: its constant pool, its classes and their traits, and the names each method body uses."""

    def __init__(self, data):
        r = Reader(data)
        r.skip(4)                                                               # minor, major
        for _pool in ("ints", "uints"):
            for _ in range(max(r.u30() - 1, 0)):
                r.u30()
        r.skip(8 * max(r.u30() - 1, 0))                                         # doubles
        self.strings = [""]
        for _ in range(max(r.u30() - 1, 0)):
            n = r.u30()
            self.strings.append(bytes(r.b[r.at:r.at + n]).decode("utf-8", "replace"))
            r.skip(n)
        self.namespaces = [(0, "")]
        for _ in range(max(r.u30() - 1, 0)):
            kind = r.u8()
            self.namespaces.append((kind, self.strings[r.u30()]))
        for _ in range(max(r.u30() - 1, 0)):                                    # namespace sets
            for _ in range(r.u30()):
                r.u30()
        self.multinames = [("*", 0)]
        for _ in range(max(r.u30() - 1, 0)):
            self.multinames.append(self._multiname(r))
        self.method_count = r.u30()
        for _ in range(self.method_count):
            params = r.u30()
            r.u30()                                                             # return type
            for _ in range(params):
                r.u30()
            r.u30()                                                             # name
            flags = r.u8()
            if flags & 0x08:                                                    # HAS_OPTIONAL
                for _ in range(r.u30()):
                    r.u30()
                    r.u8()
            if flags & 0x80:                                                    # HAS_PARAM_NAMES
                for _ in range(params):
                    r.u30()
        for _ in range(r.u30()):                                                # metadata
            r.u30()
            for _ in range(r.u30()):
                r.u30()
                r.u30()
        count = r.u30()
        self.classes = []
        for _ in range(count):
            name, sup, flags = self.name(r.u30()), self.name(r.u30()), r.u8()
            if flags & 0x08:
                r.u30()                                                         # protected namespace
            for _ in range(r.u30()):
                r.u30()                                                         # interfaces
            iinit = r.u30()
            self.classes.append({"name": name, "super": sup, "flags": flags, "iinit": iinit,
                                 "traits": self._traits(r)})
        for c in self.classes:
            c["cinit"] = r.u30()
            c["static"] = self._traits(r)
        self.scripts = []
        for _ in range(r.u30()):
            self.scripts.append({"init": r.u30(), "traits": self._traits(r)})
        self.bodies = []
        for _ in range(r.u30()):
            method = r.u30()
            for _ in range(4):                                                  # stack, locals, scope depths
                r.u30()
            n = r.u30()
            code = bytes(r.b[r.at:r.at + n])
            r.skip(n)
            for _ in range(r.u30()):                                            # exceptions
                for _ in range(5):
                    r.u30()
            self._traits(r)
            self.bodies.append((method, code))

    def _multiname(self, r):
        kind = r.u8()
        if kind in (0x07, 0x0D):                                                # QName
            ns = r.u30()
            return self.strings[r.u30()], ns
        if kind in (0x0F, 0x10):                                                # RTQName
            return self.strings[r.u30()], 0
        if kind in (0x11, 0x12):                                                # RTQNameL
            return "*", 0
        if kind in (0x09, 0x0E):                                                # Multiname
            name = self.strings[r.u30()]
            r.u30()
            return name, 0
        if kind in (0x1B, 0x1C):                                                # MultinameL
            r.u30()
            return "*", 0
        if kind == 0x1D:                                                        # TypeName (Vector.<T>)
            base = r.u30()
            params = [r.u30() for _ in range(r.u30())]
            return ("typename", base, params), 0
        raise SwfNamesError(f"multiname kind 0x{kind:02x}")

    def name(self, index, qualified=True):
        if not 0 <= index < len(self.multinames):
            return "?"
        name, ns = self.multinames[index]
        if isinstance(name, tuple):
            return f"{self.name(name[1])}.<{','.join(self.name(p) for p in name[2])}>"
        package = self.namespaces[ns][1] if 0 < ns < len(self.namespaces) else ""
        return f"{package}.{name}" if qualified and package and self.namespaces[ns][0] in (0x16, 0x17) else name

    def access(self, index):
        ns = self.multinames[index][1] if 0 <= index < len(self.multinames) else 0
        return ACCESS.get(self.namespaces[ns][0], "other") if 0 < ns < len(self.namespaces) else "other"

    def _traits(self, r):
        out = []
        for _ in range(r.u30()):
            name, kind_byte = r.u30(), r.u8()
            kind = kind_byte & 0x0F
            t = {"name": self.name(name, qualified=False), "access": self.access(name),
                 "kind": TRAIT_KINDS[kind] if kind < len(TRAIT_KINDS) else f"kind{kind}"}
            if kind in (0, 6):
                r.u30()
                t["type"] = self.name(r.u30())
                if r.u30():
                    r.u8()
            elif kind in (1, 2, 3):
                r.u30()
                t["method"] = r.u30()
            elif kind in (4, 5):
                r.u30()
                t["index"] = r.u30()
            else:
                raise SwfNamesError(f"trait kind {kind}")
            if kind_byte & 0x40:                                                # ATTR_Metadata
                for _ in range(r.u30()):
                    r.u30()
            out.append(t)
        return out

    def owners(self):
        """Each method index named by what holds it: <class>.<trait> (get:/set: for accessors), <class>.<init>, <class>.<cinit>,
        script<n>.<init>."""
        own = {}
        for c in self.classes:
            own.setdefault(c["iinit"], f"{c['name']}.<init>")
            own.setdefault(c["cinit"], f"{c['name']}.<cinit>")
            for t in c["traits"] + c["static"]:
                if "method" in t:
                    prefix = {"getter": "get:", "setter": "set:"}.get(t["kind"], "")
                    own.setdefault(t["method"], f"{c['name']}.{prefix}{t['name']}")
        for i, s in enumerate(self.scripts):
            own.setdefault(s["init"], f"script{i}.<init>")
        return own

    def uses(self, code):
        """The names one body uses: called, read or written, identifier strings pushed, the count of other strings,
        the functions it creates, and the opcode it stopped at (None when it read to the end)."""
        r = Reader(code)
        calls, names, strings, made = [], [], [], []
        other = 0
        while r.at < len(code):
            op = r.u8()
            if op in _NONE:
                continue
            if op in _U30:
                r.u30()
            elif op in _MN:
                names.append(self.name(r.u30(), qualified=False))
            elif op in _MN_ARGS:
                (calls if op in _CALLS else names).append(self.name(r.u30(), qualified=False))
                r.u30()
            elif op in _S24:
                r.skip(3)
            elif op == OP_PUSHSTRING:
                index = r.u30()
                text = self.strings[index] if index < len(self.strings) else ""
                if NAME.fullmatch(text):
                    strings.append(text)
                else:
                    other += 1
            elif op == OP_NEWFUNCTION:
                made.append(r.u30())
            elif op in (OP_PUSHBYTE, OP_GETSCOPEOBJECT):
                r.u8()
            elif op in (OP_HASNEXT2, OP_CALLMETHOD, OP_CALLSTATIC):
                r.u30()
                r.u30()
            elif op == OP_LOOKUPSWITCH:
                r.skip(3)
                r.skip(3 * (r.u30() + 1))
            elif op == OP_DEBUG:
                r.u8()
                r.u30()
                r.u8()
                r.u30()
            else:
                return calls, names, strings, other, made, op
        return calls, names, strings, other, made, None


def _matrix_and_cxform(r, matrix, cxform):
    from_bits = _Bits(r.b, r.at)
    if matrix:
        for _ in range(2):                                                      # scale, rotate
            if from_bits.ub(1):
                n = from_bits.ub(5)
                from_bits.ub(2 * n)
        n = from_bits.ub(5)
        from_bits.ub(2 * n)
        from_bits.align()
    if cxform:                                                                  # CXFORMWITHALPHA
        add, mult, n = from_bits.ub(1), from_bits.ub(1), from_bits.ub(4)
        from_bits.ub(4 * n * (add + mult))
        from_bits.align()
    r.at = from_bits.pos


class _Bits:
    def __init__(self, data, pos):
        self.b, self.pos, self.bit = data, pos, 0

    def ub(self, nbits):
        v = 0
        for _ in range(nbits):
            if self.pos >= len(self.b):
                raise SwfNamesError("bit read past the end")
            v = (v << 1) | ((self.b[self.pos] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit, self.pos = 0, self.pos + 1
        return v

    def align(self):
        if self.bit:
            self.bit, self.pos = 0, self.pos + 1


def _cstring(r):
    end = r.b.find(b"\0", r.at)
    if end < 0:
        raise SwfNamesError("string without its terminating zero")
    text = bytes(r.b[r.at:end]).decode("latin-1")
    r.at = end + 1
    return text


def _place(code, data):
    """PlaceObject2 or 3: depth, character (or None) and instance name (or None)."""
    r = Reader(data)
    flags = r.u8()
    flags2 = r.u8() if code == PLACE_OBJECT3 else 0
    depth = r.u16()
    if code == PLACE_OBJECT3 and (flags2 & 0x08 or (flags2 & 0x10 and flags & 0x02)):
        _cstring(r)                                                             # class name
    character = r.u16() if flags & 0x02 else None
    _matrix_and_cxform(r, flags & 0x04, flags & 0x08)
    if flags & 0x10:
        r.u16()                                                                 # ratio
    return depth, character, _cstring(r) if flags & 0x20 else None


def _tags(body, pos, sprite, found):
    while pos + 2 <= len(body):
        head = struct.unpack_from("<H", body, pos)[0]
        code, size, pos = head >> 6, head & 0x3F, pos + 2
        if size == 0x3F:
            size, pos = struct.unpack_from("<I", body, pos)[0], pos + 4
        data, pos = body[pos:pos + size], pos + size
        if len(data) != size:
            raise SwfNamesError(f"tag {code} runs past the end")
        if code == END:
            return
        if code == SYMBOL_CLASS:
            r = Reader(data)
            for _ in range(r.u16()):
                cid = r.u16()
                found["symbols"][cid] = _cstring(r)
        elif code == DEFINE_SPRITE:
            _tags(data, 4, struct.unpack_from("<H", data)[0], found)
        elif code in (PLACE_OBJECT2, PLACE_OBJECT3):
            depth, character, name = _place(code, data)
            if name is not None:
                found["places"].append((sprite, depth, character, name))
        elif code == DO_ABC:
            found["abc"].append(data[data.index(b"\0", 4) + 1:])
        elif code == DO_ABC1:
            found["abc"].append(data)


def describe(name, data):
    """The lines for one movie (see the module's docstring)."""
    sig, version = bytes(data[:3]), data[3]
    if sig not in (b"FWS", b"CWS", b"GFX", b"CFX"):
        return [f"file={name} not_swf=1"]
    body = zlib.decompress(data[8:]) if sig in (b"CWS", b"CFX") else data[8:]
    bits = _Bits(body, 0)
    n = bits.ub(5)
    box = []
    for _ in range(4):
        v = bits.ub(n)
        box.append(v - (1 << n) if n and v >> (n - 1) else v)
    bits.align()
    found = {"symbols": {}, "places": [], "abc": []}
    _tags(body, bits.pos + 4, 0, found)
    out = [f"file={name} signature={sig.decode()} version={version} "
           f"stage={(box[1] - box[0]) / 20:g}x{(box[3] - box[2]) / 20:g} abc={len(found['abc'])}"]
    out += [f"symbol id={cid} class={cls}" for cid, cls in sorted(found["symbols"].items())]
    for sprite, depth, character, inst in found["places"]:
        cls = found["symbols"].get(character, "-") if character is not None else "-"
        out.append(f"place in={sprite} depth={depth} id={character if character is not None else '-'} "
                   f"class={cls} name={inst}")
    for data_abc in found["abc"]:
        abc = Abc(data_abc)
        for c in abc.classes:
            out.append(f"class name={c['name']} super={c['super']} sealed={c['flags'] & 1} "
                       f"final={(c['flags'] >> 1) & 1} interface={(c['flags'] >> 2) & 1}")
            for of, traits in (("instance", c["traits"]), ("class", c["static"])):
                out += [_trait_line(of, t) for t in traits]
        for s in abc.scripts:
            out += [_trait_line("script", t) for t in s["traits"]]
        owners = abc.owners()
        results = {method: abc.uses(code) for method, code in abc.bodies}
        for _ in range(len(results)):                                           # closures, however deep
            named = len(owners)
            for method in [m for m in results if m in owners]:
                for child in results[method][4]:
                    owners.setdefault(child, f"{owners[method]}/fn")
            if len(owners) == named:
                break
        for method, code in abc.bodies:
            calls, names, strings, other, _made, stopped = results[method]
            owner = owners.get(method, f"#{method}")
            out.append(f"uses method={owner} calls={_list(calls)} names={_list(names)} strings={_list(strings)} "
                       f"other_strings={other}")
            if stopped is not None:
                out.append(f"partial method={owner} at=0x{stopped:02x}")
    return out


def _trait_line(of, t):
    line = f"trait of={of} kind={t['kind']} access={t['access']} name={t['name']}"
    return line + (f" type={t['type']}" if "type" in t else "")


def _list(items):
    seen = [i for n, i in enumerate(items) if i not in items[:n] and NAME.fullmatch(i)]
    return ",".join(seen) or "-"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ba2", help="read the movies from this archive (src/fo4sf/ba2.py)")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)
    archive = None
    if args.ba2:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                        "src"))
        from fo4sf.ba2 import Ba2
        archive = Ba2(args.ba2)
    for want in args.files:
        if archive is None:
            with open(want, "rb") as f:
                print("\n".join(describe(os.path.basename(want), f.read())))
            continue
        hit = [n for n in archive.names
               if n.lower().replace("/", "\\").endswith("\\" + want.lower().replace("/", "\\"))]
        if not hit:
            print(f"file={want} found=0")
            continue
        print("\n".join(describe(want, archive.read(hit[0]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
