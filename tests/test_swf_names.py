"""FAL-614 S1-R1: scripts/ui/swf_names.py prints names only from a movie's ActionScript 3. The movie here is built in
the test (an invented ABC block, no game file): classes, traits, placed instances, and the names each body uses."""
import struct
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ui"))
import make_probe_swf  # noqa: E402
import swf_names  # noqa: E402


def u30(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def tag(code, body):
    return struct.pack("<HI", code << 6 | 0x3F, len(body)) + body


class AbcBuilder:
    """Just enough of an ABC encoder for the test: strings, namespaces, QNames, methods, classes, bodies."""

    def __init__(self):
        self.strings, self.namespaces, self.multinames = [], [], []
        self.methods, self.classes, self.scripts, self.bodies = 0, [], [], []

    def s(self, text):
        if text not in self.strings:
            self.strings.append(text)
        return self.strings.index(text) + 1

    def ns(self, kind, name):
        self.namespaces.append((kind, self.s(name)))
        return len(self.namespaces)

    def qname(self, name, ns):
        self.multinames.append((ns, self.s(name)))
        return len(self.multinames)

    def method(self):
        self.methods += 1
        return self.methods - 1

    def bytes(self):
        out = bytearray(struct.pack("<HH", 16, 46))
        out += u30(0) + u30(0) + u30(0)                                         # ints, uints, doubles
        out += u30(len(self.strings) + 1)
        for text in self.strings:
            raw = text.encode()
            out += u30(len(raw)) + raw
        out += u30(len(self.namespaces) + 1)
        for kind, name in self.namespaces:
            out += bytes([kind]) + u30(name)
        out += u30(0)                                                           # namespace sets
        out += u30(len(self.multinames) + 1)
        for ns, name in self.multinames:
            out += b"\x07" + u30(ns) + u30(name)
        out += u30(self.methods)
        for _ in range(self.methods):
            out += u30(0) + u30(0) + u30(0) + b"\x00"                           # no params, any type, no name
        out += u30(0)                                                           # metadata
        out += u30(len(self.classes))
        for c in self.classes:
            out += u30(c["name"]) + u30(c["super"]) + bytes([c["flags"]]) + u30(0) + u30(c["iinit"])
            out += self._traits(c["traits"])
        for c in self.classes:
            out += u30(c["cinit"]) + self._traits(c["static"])
        out += u30(len(self.scripts))
        for init, traits in self.scripts:
            out += u30(init) + self._traits(traits)
        out += u30(len(self.bodies))
        for method, code in self.bodies:
            out += u30(method) + u30(4) + u30(2) + u30(0) + u30(2) + u30(len(code)) + code + u30(0) + u30(0)
        return bytes(out)

    @staticmethod
    def _traits(traits):
        out = bytearray(u30(len(traits)))
        for name, kind, a, b in traits:
            out += u30(name) + bytes([kind])
            if kind in (0, 6):
                out += u30(0) + u30(a) + u30(0)                                 # slot id, type, no value
            else:
                out += u30(0) + u30(a)
        return bytes(out)


def build_movie(unknown_op=False):
    abc = AbcBuilder()
    public = abc.ns(0x16, "")
    shared = abc.ns(0x16, "Shared")
    private = abc.ns(0x05, "")
    menu = abc.qname("TestShell", public)
    base = abc.qname("IMenu", shared)
    obj = abc.qname("Object", public)
    code_obj = abc.qname("BGSCodeObj", public)
    on_create = abc.qname("onCodeObjCreate", public)
    secret = abc.qname("secretState", private)
    get_tab = abc.qname("currentTab", public)
    ext = abc.qname("ExternalBridge", shared)
    call = abc.qname("call", public)
    listen = abc.qname("addEventListener", public)
    loader = abc.qname("PageLoader_mc", public)
    iinit, cinit, create, getter, closure, script_init = (abc.method() for _ in range(6))
    abc.classes.append({"name": menu, "super": base, "flags": 0x01, "iinit": iinit, "cinit": cinit,
                        "traits": [(code_obj, 0, obj, 0), (secret, 0, obj, 0), (on_create, 1, create, 0),
                                   (get_tab, 2, getter, 0)],
                        "static": []})
    abc.scripts.append((script_init, [(menu, 4, 0, 0)]))
    s_tab = abc.s("RequestTab")
    s_event = abc.s("TestChangeEvent")
    s_sentence = abc.s("not a name, a sentence")
    s_file = abc.s("Test_Page.swf")
    create_code = (
        b"\xd0\x30"                                                             # getlocal0, pushscope
        + b"\x60" + u30(ext)                                                    # getlex ExternalBridge
        + b"\xd0\x66" + u30(code_obj)                                           # getlocal0, getproperty BGSCodeObj
        + b"\x2c" + u30(s_tab)                                                  # pushstring RequestTab
        + b"\x24\x02"                                                           # pushbyte 2
        + b"\x4f" + u30(call) + u30(3)                                          # callpropvoid call, 3
        + b"\x12\x00\x00\x00"                                                   # iffalse +0 (s24)
        + b"\x1b\x00\x00\x00" + u30(1) + b"\x00\x00\x00\x00\x00\x00"            # lookupswitch, 2 cases
        + b"\xef\x01" + u30(s_sentence) + b"\x00" + u30(0)                      # debug
        + b"\xf1" + u30(s_sentence)                                             # debugfile
        + b"\x2c" + u30(s_sentence)                                             # pushstring (a sentence)
        + b"\x2c" + u30(s_file)                                                 # pushstring Test_Page.swf
        + b"\xd0\x2c" + u30(s_event) + b"\x40" + u30(closure)                   # newfunction closure
        + b"\x4f" + u30(listen) + u30(2)                                        # callpropvoid addEventListener, 2
        + (b"\x22\x01" if unknown_op else b"")                                  # pushconstant: not known here
        + b"\x47"                                                               # returnvoid
    )
    closure_code = b"\xd0\x30\x60" + u30(loader) + b"\x66" + u30(secret) + b"\x29\x47"
    abc.bodies += [(iinit, b"\xd0\x30\xd0\x49\x00\x47"), (cinit, b"\x47"), (create, create_code),
                   (getter, b"\xd0\x66" + u30(get_tab) + b"\x48"), (closure, closure_code),
                   (script_init, b"\x47")]

    sprite_inner = struct.pack("<BH", 0x20 | 0x02 | 0x04, 1) + struct.pack("<H", 9) + b"\x00" + b"inner_mc\x00"
    sprite = struct.pack("<HH", 5, 1) + struct.pack("<HI", 26 << 6 | 0x3F, len(sprite_inner)) + sprite_inner + \
        b"\x40\x00\x00\x00"                                                     # ShowFrame, End
    # PlaceObject3 on the root: character 5, a matrix with scale (1 bit set, 2 bits per value), a colour transform
    # with add terms (4 bits each), a ratio and the name
    matrix = bytes([0b10001001, 0b00000000])                                    # scale: n=2 (01,01); translate n=0
    cxform = bytes([0b10010000, 0, 0])                                          # add=1, mult=0, n=4, 4 x 4 bits
    po3 = struct.pack("<BBH", 0x02 | 0x04 | 0x08 | 0x10 | 0x20, 0, 2) + struct.pack("<H", 5) + matrix + cxform + \
        struct.pack("<H", 0) + b"Menu_mc\x00"
    symbols = struct.pack("<H", 2) + struct.pack("<H", 0) + b"TestShell\x00" + struct.pack("<H", 5) + b"Shared.Loader\x00"
    body = (make_probe_swf.rect(0, 876 * 20, 0, 700 * 20) + struct.pack("<HH", 30 << 8, 1)
            + tag(69, b"\x08\x00\x00\x00") + tag(39, sprite) + tag(70, po3)
            + tag(82, struct.pack("<I", 1) + b"frame1\x00" + abc.bytes())
            + tag(76, symbols) + b"\x40\x00" + b"\x00\x00")
    return b"CWS" + bytes([15]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body)


class SwfNamesTests(unittest.TestCase):
    def setUp(self):
        self.lines = swf_names.describe("TestShell.swf", build_movie())

    def test_header_symbols_and_places(self):
        self.assertTrue(self.lines[0].startswith("file=TestShell.swf signature=CWS version=15 stage=876x700 "),
                        self.lines[0])
        self.assertTrue(self.lines[0].endswith(" abc=1"), self.lines[0])
        self.assertIn("symbol id=0 class=TestShell", self.lines)
        self.assertIn("symbol id=5 class=Shared.Loader", self.lines)
        self.assertIn("place in=5 depth=1 id=9 class=- name=inner_mc", self.lines)
        self.assertIn("place in=0 depth=2 id=5 class=Shared.Loader name=Menu_mc", self.lines)

    def test_classes_and_traits(self):
        self.assertIn("class name=TestShell super=Shared.IMenu sealed=1 final=0 interface=0", self.lines)
        for line in ("trait of=instance kind=slot access=public name=BGSCodeObj type=Object",
                     "trait of=instance kind=slot access=private name=secretState type=Object",
                     "trait of=instance kind=method access=public name=onCodeObjCreate",
                     "trait of=instance kind=getter access=public name=currentTab",
                     "trait of=script kind=class access=public name=TestShell"):
            self.assertIn(line, self.lines, line)

    def test_uses(self):
        self.assertIn("uses method=TestShell.onCodeObjCreate calls=call,addEventListener "
                      "names=ExternalBridge,BGSCodeObj strings=RequestTab,Test_Page.swf,TestChangeEvent "
                      "other_strings=1", self.lines)
        self.assertIn("uses method=TestShell.onCodeObjCreate/fn calls=- names=PageLoader_mc,secretState strings=- "
                      "other_strings=0", self.lines)
        self.assertIn("uses method=TestShell.get:currentTab calls=- names=currentTab strings=- other_strings=0",
                      self.lines)
        self.assertIn("uses method=TestShell.<init> calls=- names=- strings=- other_strings=0", self.lines)
        self.assertIn("uses method=script0.<init> calls=- names=- strings=- other_strings=0", self.lines)
        self.assertFalse(any(line.startswith("partial ") for line in self.lines), self.lines)

    def test_names_only(self):
        text = "\n".join(self.lines)
        self.assertNotIn("sentence", text)          # a string that is not an identifier is counted, never printed
        for line in self.lines:
            self.assertRegex(line, r"^(file=|symbol |place |class |trait |uses |partial )")

    def test_unknown_opcode_is_partial(self):
        lines = swf_names.describe("TestShell.swf", build_movie(unknown_op=True))
        self.assertIn("partial method=TestShell.onCodeObjCreate at=0x22", lines)
        uses = next(line for line in lines if line.startswith("uses method=TestShell.onCodeObjCreate "))
        self.assertIn("strings=RequestTab,Test_Page.swf,TestChangeEvent", uses)

    def test_not_a_swf(self):
        self.assertEqual(swf_names.describe("x.swf", b"PK\x03\x04rest"), ["file=x.swf not_swf=1"])

    def test_main_reads_a_file(self):
        import io
        import tempfile
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TestShell.swf"
            path.write_bytes(build_movie())
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(swf_names.main([str(path)]), 0)
        self.assertIn("symbol id=0 class=TestShell", out.getvalue())

    def test_main_reads_an_archive(self):
        import io
        import tempfile
        from contextlib import redirect_stdout
        sys.path.insert(0, str(ROOT / "tests"))
        from ba2_fixture import general_archive
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Test - Interface.ba2"
            path.write_bytes(general_archive({"Interface\\TestShell.swf": build_movie()}, compressed=True))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(swf_names.main(["--ba2", str(path), "testshell.swf", "Missing.swf"]), 0)
        self.assertIn("file=testshell.swf signature=CWS", out.getvalue())
        self.assertIn("uses method=TestShell.onCodeObjCreate ", out.getvalue())
        self.assertIn("file=Missing.swf found=0", out.getvalue())


if __name__ == "__main__":
    unittest.main()
