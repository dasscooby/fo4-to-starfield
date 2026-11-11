"""scripts/ui/make_probe_swf.py, the Pip-Boy probe's stage (b) movie (FAL-187): the header and every tag it writes are
read back, both by its own reader and, for the header, the frame and the tag list, straight from the bytes. No movie
is kept: every file goes to a temporary folder."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_probe_swf as swf  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "ui", "make_probe_swf.py")


def raw_tags(body):
    """(code, length) of every tag, parsed here without the module's reader."""
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4                          # RECT, then frame rate and frame count
    out = []
    while pos < len(body):
        code_len = struct.unpack_from("<H", body, pos)[0]
        code, n = code_len >> 6, code_len & 0x3F
        pos += 2
        if n == 0x3F:
            n = struct.unpack_from("<I", body, pos)[0]
            pos += 4
        out.append((code, n))
        pos += n
    return out, pos


def signed_area2(points):
    """Twice the shoelace area; positive for a path drawn clockwise on screen (y down)."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:]))


class HeaderTest(unittest.TestCase):
    def test_compressed_header_version_12(self):
        data = swf.movie_bytes()
        self.assertEqual(data[:3], b"CWS")
        self.assertEqual(data[3], 12)
        body = zlib.decompress(data[8:])
        self.assertEqual(struct.unpack_from("<I", data, 4)[0], 8 + len(body))

    def test_uncompressed_is_the_same_body(self):
        c, u = swf.movie_bytes(), swf.movie_bytes(compressed=False)
        self.assertEqual(u[:3], b"FWS")
        self.assertEqual(u[3:8], c[3:8])
        self.assertEqual(u[8:], zlib.decompress(c[8:]))

    def test_frame_rect_rate_and_count_from_the_bytes(self):
        body = zlib.decompress(swf.movie_bytes(width=1920, height=1080)[8:])
        nbits = body[0] >> 3
        bits = int.from_bytes(body[:(5 + 4 * nbits + 7) // 8], "big")
        total = ((5 + 4 * nbits + 7) // 8) * 8
        fields = [(bits >> (total - 5 - (i + 1) * nbits)) & ((1 << nbits) - 1) for i in range(4)]
        self.assertEqual(fields, [0, 1920 * 20, 0, 1080 * 20])
        pos = (5 + 4 * nbits + 7) // 8
        self.assertEqual(struct.unpack_from("<HH", body, pos), (30 << 8, 1))

    def test_tag_list_from_the_bytes(self):
        body = zlib.decompress(swf.movie_bytes()[8:])
        tags, end = raw_tags(body)
        self.assertEqual([c for c, _ in tags], [69, 32, 32, 26, 26, 1, 0])
        self.assertEqual(end, len(body))
        self.assertEqual(tags[0][1], 4)                          # FileAttributes is four bytes
        self.assertEqual(tags[-1][1], 0)

    def test_no_background_colour_and_no_code(self):
        tags, _ = raw_tags(zlib.decompress(swf.movie_bytes()[8:]))
        codes = {c for c, _ in tags}
        self.assertNotIn(9, codes)                               # SetBackgroundColor
        self.assertFalse(codes & {72, 82, 76, 12, 59})           # DoABC, DoABC2, SymbolClass, DoAction, DoInitAction

    def test_deterministic(self):
        self.assertEqual(swf.movie_bytes(), swf.movie_bytes())
        self.assertNotEqual(swf.movie_bytes(), swf.movie_bytes(label="OTHER"))


class ReadBackTest(unittest.TestCase):
    def setUp(self):
        self.movie = swf.read_movie(swf.movie_bytes())
        self.tags = self.movie["tags"]

    def test_header_fields(self):
        m = self.movie
        self.assertEqual((m["signature"], m["version"]), ("CWS", 12))
        self.assertEqual(m["frame"], (0, 1920 * 20, 0, 1080 * 20))
        self.assertEqual((m["frame_rate"], m["frame_count"]), (30, 1))

    def test_tags_in_order(self):
        self.assertEqual([t["name"] for t in self.tags],
                         ["FileAttributes", "DefineShape3", "DefineShape3", "PlaceObject2", "PlaceObject2",
                          "ShowFrame", "End"])

    def test_actionscript3_flag(self):
        fa = self.tags[0]
        self.assertTrue(fa["actionscript3"])
        self.assertEqual(fa["flags"], "08000000")

    def test_rectangle(self):
        rect = self.tags[1]
        self.assertEqual(rect["id"], 1)
        self.assertEqual(rect["fills"], [(0x1A, 0xFF, 0x80, 0xFF)])
        W, H = 1920 * 20, 1080 * 20
        self.assertEqual(rect["bounds"], ((W - W * 3 // 5) // 2, (W - W * 3 // 5) // 2 + W * 3 // 5,
                                          (H - H // 2) // 2, (H - H // 2) // 2 + H // 2))
        self.assertEqual(len(rect["paths"]), 1)
        p = rect["paths"][0]
        xmin, xmax, ymin, ymax = rect["bounds"]
        self.assertEqual(p["points"], [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)])
        self.assertEqual((p["fill0"], p["fill1"]), (0, 1))
        self.assertGreater(signed_area2(p["points"]), 0)

    def test_label_squares(self):
        label, rect = self.tags[2], self.tags[1]
        self.assertEqual(label["id"], 2)
        self.assertEqual(label["fills"], [(0x06, 0x20, 0x0F, 0xFF)])
        lit = sum(bin(row).count("1") for ch in swf.LABEL for row in swf.FONT[ch])
        self.assertEqual(len(label["paths"]), lit)
        boxes = []
        for p in label["paths"]:
            pts = p["points"]
            self.assertEqual(len(pts), 5)
            self.assertEqual(pts[0], pts[-1])                    # closed
            self.assertGreater(signed_area2(pts), 0)             # clockwise on screen
            self.assertEqual((p["fill0"], p["fill1"]), (0, 1))
            xs, ys = [x for x, _ in pts], [y for _, y in pts]
            boxes.append((min(xs), max(xs), min(ys), max(ys)))
        rx0, rx1, ry0, ry1 = rect["bounds"]
        for x0, x1, y0, y1 in boxes:                             # inside the rectangle
            self.assertTrue(rx0 <= x0 < x1 <= rx1 and ry0 <= y0 < y1 <= ry1)
        boxes.sort()
        for i, a in enumerate(boxes):                            # no two squares touch or overlap
            for b in boxes[i + 1:]:
                if b[0] > a[1]:
                    break
                self.assertTrue(b[0] > a[1] or b[2] > a[3] or a[2] > b[3], (a, b))

    def test_placements(self):
        places = [(t["depth"], t["character"], t["flags"]) for t in self.tags if t["name"] == "PlaceObject2"]
        self.assertEqual(places, [(1, 1, 0x06), (2, 2, 0x06)])

    def test_no_label(self):
        tags = swf.read_movie(swf.movie_bytes(label=None))["tags"]
        self.assertEqual([t["name"] for t in tags], ["FileAttributes", "DefineShape3", "PlaceObject2", "ShowFrame",
                                                     "End"])

    def test_colours_and_size(self):
        m = swf.read_movie(swf.movie_bytes(width=800, height=600, color=0x123456, ink=0xABCDEF))
        self.assertEqual(m["frame"], (0, 800 * 20, 0, 600 * 20))
        self.assertEqual(m["tags"][1]["fills"], [(0x12, 0x34, 0x56, 0xFF)])
        self.assertEqual(m["tags"][2]["fills"], [(0xAB, 0xCD, 0xEF, 0xFF)])


class ChannelTest(unittest.TestCase):
    """--channel (FAL-216): the stage (b) movie plus an embedded font, the named field and the named button sprite."""

    @classmethod
    def setUpClass(cls):
        cls.movie = swf.read_movie(swf.movie_bytes(channel=True))
        cls.tags = cls.movie["tags"]
        cls.by_name = {}
        for t in cls.tags:
            cls.by_name.setdefault(t["name"], []).append(t)

    def test_without_channel_the_bytes_are_stage_b(self):
        self.assertEqual(swf.movie_bytes(channel=False), swf.movie_bytes())
        names = [t["name"] for t in swf.read_movie(swf.movie_bytes())["tags"]]
        self.assertNotIn("DefineFont3", names)

    def test_tag_order_and_no_code(self):
        self.assertEqual([t["name"] for t in self.tags],
                         ["FileAttributes", "DefineShape3", "DefineShape3", "DefineFont3", "DefineEditText",
                          "DefineShape3", "DefineShape3", "DefineSprite", "PlaceObject2", "PlaceObject2",
                          "PlaceObject2", "PlaceObject2", "ShowFrame", "End"])
        body = zlib.decompress(swf.movie_bytes(channel=True)[8:])
        codes = [c for c, _ in raw_tags(body)[0]]
        for code in (12, 59, 72, 76, 82, 9):                      # DoAction, DoInitAction, DoABC, SymbolClass, BG
            self.assertNotIn(code, codes)

    def test_named_placements(self):
        places = [(t["depth"], t["character"], t.get("instance")) for t in self.by_name["PlaceObject2"]]
        self.assertEqual(places, [(1, 1, None), (2, 2, None), (3, swf.FIELD_ID, "fo4sfPosition"),
                                  (4, swf.BUTTON_ID, "fo4sfButton")])

    def test_font_covers_the_table_with_layout(self):
        font = self.by_name["DefineFont3"][0]
        self.assertEqual(font["id"], swf.FONT_ID)
        self.assertEqual(font["font_name"], "FO4SFDot")
        self.assertEqual(font["codes"], "".join(sorted(swf.FONT)))
        self.assertEqual(font["font_flags"] & 0x8C, 0x8C)            # HasLayout, WideOffsets, WideCodes
        self.assertEqual((font["ascent"], font["descent"], font["kerning"]), (7 * swf.PX, swf.PX, 0))
        self.assertEqual(set(font["advances"]), {6 * swf.PX})

    def test_glyphs_are_the_table_drawn_anticlockwise_with_fill0(self):
        font = self.by_name["DefineFont3"][0]
        for ch, paths in zip(font["codes"], font["glyphs"]):
            lit = sum(bin(row).count("1") for row in swf.FONT[ch])
            self.assertEqual(len(paths), lit, ch)
            for i, p in enumerate(paths):
                self.assertEqual(len(p["points"]), 5)
                self.assertEqual(p["points"][0], p["points"][-1])
                self.assertLess(signed_area2(p["points"]), 0, ch)    # anticlockwise on screen
                self.assertEqual((p["fill0"], p["fill1"]), (1, 0))
                xs = [x for x, _ in p["points"]]
                ys = [y for _, y in p["points"]]
                self.assertTrue(0 <= min(xs) and max(xs) <= 5 * swf.PX, ch)
                self.assertTrue(-7 * swf.PX <= min(ys) and max(ys) <= 0, ch)
        space = font["glyphs"][font["codes"].index(" ")]
        self.assertEqual(space, [])

    def test_field(self):
        field = self.by_name["DefineEditText"][0]
        self.assertEqual(field["id"], swf.FIELD_ID)
        self.assertEqual((field["font"], field["height"]), (swf.FONT_ID, swf.FIELD_PX * 20))
        self.assertEqual(field["flags"], [0x8D, 0x11])               # HasText ReadOnly HasTextColor HasFont; NoSelect
                                                                     # UseOutlines
        self.assertEqual(field["variable"], "")
        self.assertEqual(field["text"], "POSITION: WAITING")
        self.assertTrue(set(field["text"]) <= set(swf.FONT))
        rect_ = self.by_name["DefineShape3"][0]["bounds"]
        b = field["bounds"]
        self.assertTrue(rect_[0] < b[0] < b[1] < rect_[1] and rect_[2] < b[2] < b[3] < rect_[3])

    def test_button_sprite_inside_the_rectangle_and_clear_of_the_label(self):
        sprite = self.by_name["DefineSprite"][0]
        self.assertEqual(sprite["id"], swf.BUTTON_ID)
        self.assertEqual([(t["depth"], t.get("character")) for t in sprite["tags"] if t["name"] == "PlaceObject2"],
                         [(1, swf.BUTTON_RECT_ID), (2, swf.BUTTON_LABEL_ID)])
        self.assertEqual([t["name"] for t in sprite["tags"]][-2:], ["ShowFrame", "End"])
        shapes = {t["id"]: t for t in self.by_name["DefineShape3"]}
        box, label = shapes[swf.RECT_ID]["bounds"], shapes[swf.LABEL_ID]["bounds"]
        button = shapes[swf.BUTTON_RECT_ID]["bounds"]
        field = self.by_name["DefineEditText"][0]["bounds"]
        self.assertTrue(box[0] < button[0] < button[1] < box[1] and box[2] < button[2] < button[3] < box[3])
        self.assertLess(field[3], label[2])                          # field above the label
        self.assertLess(label[3], button[2])                         # label above the button

    def test_cli_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "c.swf")
            r = subprocess.run([sys.executable, SCRIPT, "--out", out, "--channel"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), swf.movie_bytes(channel=True))
            r = subprocess.run([sys.executable, SCRIPT, "--read", out], capture_output=True, text=True)
            info = json.loads(r.stdout)
            font = [t for t in info["tags"] if t["name"] == "DefineFont3"][0]
            self.assertEqual(font["glyphs"], len(swf.FONT))


class RefusalTest(unittest.TestCase):
    def test_unknown_character(self):
        with self.assertRaises(swf.SwfError):
            swf.movie_bytes(label="lower")

    def test_label_too_long(self):
        with self.assertRaises(swf.SwfError):
            swf.movie_bytes(width=40, height=40)

    def test_empty_stage(self):
        with self.assertRaises(swf.SwfError):
            swf.movie_bytes(width=0)

    def test_not_a_swf(self):
        with self.assertRaises(swf.SwfError):
            swf.read_movie(b"GIF89a....")

    def test_length_mismatch(self):
        data = bytearray(swf.movie_bytes(compressed=False))
        data[4:8] = struct.pack("<I", len(data) + 1)
        with self.assertRaises(swf.SwfError):
            swf.read_movie(bytes(data))

    def test_bytes_after_end(self):
        data = swf.movie_bytes(compressed=False) + b"\0"
        data = data[:4] + struct.pack("<I", len(data)) + data[8:]
        with self.assertRaises(swf.SwfError):
            swf.read_movie(data)


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)

    def test_write_then_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "sub", "probe.swf")
            r = self.run_cli("--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), swf.movie_bytes())
            r = self.run_cli("--read", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            info = json.loads(r.stdout)
            self.assertEqual((info["signature"], info["version"]), ("CWS", 12))
            self.assertEqual([t["code"] for t in info["tags"]], [69, 32, 32, 26, 26, 1, 0])
            self.assertIsInstance(info["tags"][2]["paths"], int)

    def test_refusal_is_one_line_and_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_cli("--out", os.path.join(tmp, "x.swf"), "--label", "bad~")
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.startswith("make_probe_swf: "))
            self.assertFalse(os.path.exists(os.path.join(tmp, "x.swf")))


if __name__ == "__main__":
    unittest.main()
