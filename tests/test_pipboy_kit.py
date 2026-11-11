"""FO4SFPipboyMenu's stage (e), the Pip-Boy page kit (FAL-301): the pages as data (the [Kit] and [Page ...] sections of
the plugin's ini, parsed and checked by make_pipboy_kit.py, and refused line by line), the kit's movie built from every
page and read back (every instance name, the font, the layout, the colours), the stager, and the plugin's kit code as
text: its sizes, names, providers, font and checks agree with the generator's; the screen is built on the main thread
and written on the menu's through `text` and `visible` only; nothing new is called in the game. Also the owner's card.
No compiler here: the PC build is the compile check."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_pipboy_kit as kit  # noqa: E402
import make_pipboy_probe as mpp  # noqa: E402
import make_probe_swf as swf  # noqa: E402
import pipboy_probe_install as ppi  # noqa: E402

TWIPS = swf.TWIPS
SCRIPT = os.path.join(ROOT, "scripts", "ui", "make_pipboy_kit.py")
PAGE = "[Page T/S]\nRow=A|health\n"


def function(text, signature):
    """The body of the function whose definition starts with `signature` (to its closing brace at one tab)."""
    start = text.index(signature)
    end = text.index("\n\t}\n", start)
    return text[start:end]


def box_of(bounds):
    xmin, xmax, ymin, ymax = bounds
    return xmin, ymin, xmax - xmin, ymax - ymin


def inside(inner, outer):
    x, y, w, h = inner
    ox, oy, ow, oh = outer
    return ox <= x and oy <= y and x + w <= ox + ow and y + h <= oy + oh


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def built(pages=None, **kw):
    """The kit's movie for these pages (the shipped ini's by default), read back, with its placements by name."""
    k = pages or kit.read_kit()
    movie = swf.read_movie(kit.kit_movie_bytes(k, **kw))
    by_id = {t["id"]: t for t in movie["tags"] if "id" in t}
    places = [t for t in movie["tags"] if t["name"] == "PlaceObject2"]
    named = {p["instance"]: by_id[p["character"]] for p in places if "instance" in p}
    return k, movie, by_id, places, named


class KitPagesTests(unittest.TestCase):
    """The pages as data: the shipped ones, and each way a page is refused."""
    k = kit.read_kit()

    def test_the_shipped_pages(self):
        self.assertEqual(kit.tabs_of(self.k), ["STAT", "INV", "DATA", "MAP", "RADIO"])
        pages = {(p["tab"], p["sub"]): p for p in self.k["pages"]}
        self.assertEqual(list(pages), [("STAT", "STATUS"), ("STAT", "SPECIAL"), ("INV", "ITEMS"), ("DATA", "QUESTS"),
                                       ("DATA", "KIT TEST"), ("MAP", "WORLD"), ("RADIO", "STATIONS")])
        status = [value for _, value in pages[("STAT", "STATUS")]["rows"]]
        self.assertEqual(status, ["health", "level", "xp", "carry_max", "rads", "cell", "world", "time"])
        special = pages[("STAT", "SPECIAL")]["rows"]                     # Starfield.esm's AVIF 2C2 to 2C8 (the task)
        self.assertEqual(special, [("STRENGTH", "av:2C2"), ("PERCEPTION", "av:2C3"), ("ENDURANCE", "av:2C4"),
                                   ("CHARISMA", "av:2C5"), ("INTELLIGENCE", "av:2C6"), ("AGILITY", "av:2C7"),
                                   ("LUCK", "av:2C8")])
        self.assertEqual(pages[("DATA", "KIT TEST")]["list"], "kit_test")
        for placeholder in (("INV", "ITEMS"), ("DATA", "QUESTS"), ("MAP", "WORLD"), ("RADIO", "STATIONS")):
            self.assertTrue(pages[placeholder]["notice"], placeholder)   # named, and saying what it waits for
        self.assertIn("MAP TRACK", " ".join(pages[("MAP", "WORLD")]["notice"]))
        self.assertEqual(self.k["header"], "time")
        self.assertEqual(kit.signature(self.k), "FO4SF KIT 1 16 STAT,INV,DATA,MAP,RADIO")

    def test_every_page_fits_its_fields(self):
        """Each page's own text (built as the plugin builds it) fits the columns of the field it goes into."""
        for p in self.k["pages"]:
            what = f"{p['tab']}/{p['sub']}"
            self.assertLessEqual(len(p["tab"]), kit.TAB_COLUMNS, what)
            self.assertLessEqual(len(p["sub"]), kit.SUB_COLUMNS, what)
            texts = [label for label, _ in p["rows"]] + p["notice"] + [label for label, _ in p["footer"]]
            texts += [p["hint"] or self.k["hints"], p["tab"], p["sub"]]
            for text in texts:
                self.assertTrue(set(text) <= set(kit.KIT_FONT), (what, text))
            for label, _ in p["rows"]:
                self.assertLessEqual(len(label), kit.NAME_COLUMNS, what)
            for line in p["notice"]:
                self.assertLessEqual(len(line), kit.NAME_COLUMNS, what)
            self.assertLessEqual(len(p["hint"] or self.k["hints"]), kit.HINT_COLUMNS, what)
            self.assertLessEqual(len(p["footer"]), kit.FOOTER, what)

    def test_other_sections_are_skipped(self):
        k = kit.parse_kit("[FO4SFPipboyMenu]\nStage=5\nRow=not a page\n" + PAGE)
        self.assertEqual([(p["tab"], p["sub"], p["rows"]) for p in k["pages"]], [("T", "S", [("A", "health")])])
        self.assertEqual(k["title"], "FO4SF PIP-BOY")

    def test_values(self):
        for good in kit.VALUE_PROVIDERS + ("av:2C2", "av:1", "av:FFFFFFFF", "av:00000ABC", "av:2c2"):
            self.assertEqual(kit.check_value(good, 1), good)
        for bad in ("av:0", "av:", "av:XYZ", "av:123456789", "AV:2C2", "Health", "inventory", "", "av: 2C2"):
            with self.assertRaises(kit.KitError, msg=bad):
                kit.check_value(bad, 1)

    def test_every_refusal(self):
        bad = {
            "no page": "[Kit]\nTitle=X\n",
            "a section without its ]": PAGE + "[Page X/Y\n",
            "two slashes": "[Page A/B/C]\nRow=A|health\n",
            "no slash": "[Page AB]\nRow=A|health\n",
            "lower case tab": "[Page Stat/S]\nRow=A|health\n",
            "tab too long": "[Page ABCDEFGHIJ/S]\nRow=A|health\n",
            "sub-tab too long": "[Page T/ABCDEFGHIJKLMN]\nRow=A|health\n",
            "page twice": PAGE + PAGE,
            "no equals": PAGE + "Row\n",
            "unknown page key": PAGE + "Rows=A|health\n",
            "unknown kit key": "[Kit]\nColor=1AFF80\n" + PAGE,
            "bad title": "[Kit]\nTitle=lower\n" + PAGE,
            "bad header": "[Kit]\nHeader=clock\n" + PAGE,
            "row without bar": "[Page T/S]\nRow=A health\n",
            "row with two bars": "[Page T/S]\nRow=A|health|level\n",
            "row label too long": "[Page T/S]\nRow=" + "A" * 34 + "|health\n",
            "row character": "[Page T/S]\nRow=A\"B|health\n",
            "unknown value": "[Page T/S]\nRow=A|inventory\n",
            "unknown list": "[Page T/S]\nList=inventory\n",
            "two lists": "[Page T/S]\nList=kit_test\nList=kit_test\n",
            "two kinds": PAGE + "Notice=X\n",
            "no kind": "[Page T/S]\nFooter=HP|health\n",
            "notice too long": "[Page T/S]\nNotice=" + "N" * 34 + "\n",
            "too many notices": "[Page T/S]\n" + "Notice=N\n" * 17,
            "too many rows": "[Page T/S]\n" + "Row=A|health\n" * 65,
            "too many footers": PAGE + "Footer=A|health\n" * 4,
            "footer label too long": PAGE + "Footer=ABCDEFGHIJK|health\n",
            "hint too long": PAGE + "Hint=" + "H" * 73 + "\n",
            "six tabs": "".join(f"[Page T{i}/S]\nRow=A|health\n" for i in range(6)),
            "six sub-tabs": "".join(f"[Page T/S{i}]\nRow=A|health\n" for i in range(6)),
        }
        for why, text in bad.items():
            with self.assertRaises(kit.KitError, msg=why):
                kit.parse_kit(text)

    def test_limits_are_inclusive(self):
        text = "[Kit]\nTitle=" + "T" * 42 + "\nHints=" + "H" * 72 + "\n"
        text += "".join(f"[Page TABLE{t}/" + "S" * 12 + f"{s}]\nRow=" + "A" * 33 + "|av:2C2\n"
                        for t in range(5) for s in range(5))                  # 9-letter tabs, 13-letter sub-tabs
        k = kit.parse_kit(text)
        self.assertEqual(len(kit.tabs_of(k)), 5)
        self.assertEqual(len(k["pages"]), 25)
        rows = kit.parse_kit("[Page T/S]\n" + "Row=A|health\n" * 64 + ("Footer=" + "F" * 10 + "|xp\n") * 3)
        self.assertEqual((len(rows["pages"][0]["rows"]), len(rows["pages"][0]["footer"])), (64, 3))
        notices = kit.parse_kit("[Page T/S]\nNotice=" + "N" * 33 + "\n" + "Notice=N\n" * 15)
        self.assertEqual(len(notices["pages"][0]["notice"]), 16)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "kit.swf")
            r = subprocess.run([sys.executable, SCRIPT, "--out", out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), kit.kit_movie_bytes(self.k))
            r = subprocess.run([sys.executable, SCRIPT, "--check"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('"signature": "FO4SF KIT 1 16 STAT,INV,DATA,MAP,RADIO"', r.stdout)
            bad = os.path.join(tmp, "bad.ini")
            with open(bad, "w", encoding="ascii") as f:
                f.write("[Page T/S]\nRow=A|inventory\n")
            r = subprocess.run([sys.executable, SCRIPT, "--out", out, "--ini", bad], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("line 2: value 'inventory' is not a value provider", r.stderr)
            r = subprocess.run([sys.executable, SCRIPT, "--out", out, "--color", "GREEN!"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("is not RRGGBB", r.stderr)


class KitMovieTests(unittest.TestCase):
    """The movie, built from every page of the shipped ini and read back."""
    k, movie, by_id, places, named = built()
    lay = kit.layout(k)

    def test_header_no_code_and_deterministic(self):
        self.assertEqual(self.movie["signature"], "CWS")
        self.assertEqual(self.movie["version"], 12)
        self.assertEqual(self.movie["frame"], (0, 1920 * TWIPS, 0, 1080 * TWIPS))
        self.assertTrue(self.movie["tags"][0]["actionscript3"])
        for code in (82, 72, 76, 59, 12, 9):                                   # DoABC2, DoABC, SymbolClass, DoAction...
            self.assertNotIn(code, {t["code"] for t in self.movie["tags"]})
        self.assertEqual(kit.kit_movie_bytes(self.k), kit.kit_movie_bytes(self.k))
        raw = kit.kit_movie_bytes(self.k, compressed=False)
        self.assertEqual(raw[8:], zlib.decompress(kit.kit_movie_bytes(self.k)[8:]))

    def test_every_instance_name_reads_back(self):
        """The test the task asks for: every name the plugin looks for is in the movie, once, in depth order."""
        names = [p["instance"] for p in self.places if "instance" in p]
        self.assertEqual(names, kit.kit_names(self.k))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual([p["depth"] for p in self.places], list(range(1, len(self.places) + 1)))
        self.assertEqual(len({p["character"] for p in self.places}), len(self.places))
        n = kit.NAMES
        expected = {n["title"], n["header"], n["more_up"], n["more_down"], n["hints"], n["close"], n["kit_id"]}
        for key, count in (("tab", 5), ("mark", 5), ("tab_hit", 5), ("sub", 5), ("sub_dim", 5), ("sub_hit", 5),
                           ("row_name", 16), ("row_value", 16), ("row_name_sel", 16), ("row_value_sel", 16),
                           ("bar", 16), ("row_hit", 16), ("info_label", 16), ("info_value", 16), ("foot", 3)):
            expected |= {f"{n[key]}{i}" for i in range(count)}
        self.assertEqual(set(names), expected)

    def test_named_objects_are_fields_or_sprites(self):
        """`text` goes to fields, `visible` and clicks to sprites: a named shape would have neither."""
        n = kit.NAMES
        fields = {"title", "header", "tab", "sub", "sub_dim", "row_name", "row_value", "row_name_sel", "row_value_sel",
                  "info_label", "info_value", "foot", "hints", "kit_id"}
        for name, t in self.named.items():
            key = next(k for k, v in sorted(n.items(), key=lambda kv: -len(kv[1])) if name.startswith(v) and
                       name[len(v):].isdigit() or name == v)
            self.assertEqual(t["name"], "DefineEditText" if key in fields else "DefineSprite", name)
            if t["name"] == "DefineSprite":
                inner = [c for c in t["tags"] if c["name"] == "PlaceObject2"]
                self.assertTrue(inner, name)
                for c in inner:
                    self.assertEqual(self.by_id[c["character"]]["name"], "DefineShape3", name)

    def test_font_and_text(self):
        font = next(t for t in self.movie["tags"] if t["name"] == "DefineFont3")
        self.assertEqual(font["codes"], kit.KIT_CHARS)
        self.assertTrue(set(swf.PAGE_FONT) < set(kit.KIT_FONT))
        for ch, glyph in zip(font["codes"], font["glyphs"]):
            self.assertEqual(len(glyph), sum(bin(r).count("1") for r in kit.KIT_FONT[ch]), ch)
        for ch, rows in kit.KIT_GLYPHS.items():
            self.assertEqual(len(rows), 7, ch)
            self.assertTrue(all(0 <= r < 32 for r in rows), ch)
            self.assertNotIn(ch, swf.PAGE_FONT, ch)
        fields = [t for t in self.movie["tags"] if t["name"] == "DefineEditText"]
        for f in fields:
            self.assertEqual(f["font"], font["id"])
            self.assertEqual(f["flags"], [0x80 | 0x08 | 0x04 | 0x01, 0x10 | 0x01])  # read-only, no select, outlines
            self.assertTrue(set(f["text"]) <= set(kit.KIT_FONT), f["text"])
        self.assertEqual(self.named[kit.NAMES["kit_id"]]["text"], kit.signature(self.k))
        for i, tab in enumerate(kit.tabs_of(self.k)):
            self.assertEqual(self.named[f"{kit.NAMES['tab']}{i}"]["text"], tab)
        self.assertEqual(self.named[kit.NAMES["title"]]["text"], self.k["title"])

    def test_each_field_holds_its_columns(self):
        n = kit.NAMES
        columns = {"title": (kit.TITLE_COLUMNS, kit.TITLE_PX), "header": (kit.TITLE_COLUMNS, kit.TITLE_PX),
                   "hints": (kit.HINT_COLUMNS, kit.HINT_PX)}
        for i in range(kit.SUBS):
            columns[f"sub{i}"] = columns[f"sub_dim{i}"] = (kit.SUB_COLUMNS, kit.TEXT_PX)
        for i in range(kit.ROWS):
            for key, c in (("row_name", kit.NAME_COLUMNS), ("row_name_sel", kit.NAME_COLUMNS),
                           ("row_value", kit.VALUE_COLUMNS), ("row_value_sel", kit.VALUE_COLUMNS),
                           ("info_label", kit.INFO_LABEL_COLUMNS), ("info_value", kit.INFO_VALUE_COLUMNS)):
                columns[f"{key}{i}"] = (c, kit.TEXT_PX)
        for i in range(kit.FOOTER):
            columns[f"foot{i}"] = (kit.FOOTER_COLUMNS, kit.TEXT_PX)
        for i, tab in enumerate(kit.tabs_of(self.k)):
            columns[f"tab{i}"] = (len(tab), kit.TAB_PX)
        for key, (cols, px) in columns.items():
            base = re.sub(r"\d+$", "", key)
            name = n[base] + key[len(base):]
            f = self.named[name]
            self.assertEqual(f["height"], px * TWIPS, name)
            width = (f["bounds"][1] - f["bounds"][0]) / TWIPS - 4             # the field's 2 px gutters
            self.assertGreaterEqual(width // kit.advance(px), cols, name)

    def test_layout(self):
        screen = self.lay["screen"]
        stage = (0, 0, 1920 * TWIPS, 1080 * TWIPS)
        band = self.lay["hint_band"]
        fields = {name: box_of(t["bounds"]) for name, t in self.named.items() if t["name"] == "DefineEditText"}
        for name, box in fields.items():
            self.assertTrue(inside(box, screen) or inside(box, band), name)
        # text fields overlap only their twin: the bright and dark copies of a row, the two of a sub-tab
        twins = {}
        for i in range(kit.ROWS):
            for a, b in (("row_name", "row_name_sel"), ("row_value", "row_value_sel")):
                twins[f"{kit.NAMES[a]}{i}"] = f"{kit.NAMES[b]}{i}"
        for i in range(kit.SUBS):
            twins[f"{kit.NAMES['sub_dim']}{i}"] = f"{kit.NAMES['sub']}{i}"
        names = sorted(fields)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if twins.get(a) == b or twins.get(b) == a:
                    self.assertEqual(fields[a], fields[b], (a, b))
                else:
                    self.assertFalse(overlap(fields[a], fields[b]), (a, b))
        for box in [self.lay[k] for k in self.lay if k.startswith(("bar", "row_hit", "tab_hit", "sub_hit"))]:
            self.assertTrue(inside(box, screen), box)
        self.assertTrue(inside(self.lay["close"], band))
        self.assertTrue(inside(screen, stage) and inside(band, stage))
        for i in range(kit.ROWS - 1):                                           # rows' hit areas tile the list
            a, b = self.lay[f"row_hit{i}"], self.lay[f"row_hit{i + 1}"]
            self.assertEqual(a[1] + a[3], b[1])
        for i in range(kit.ROWS):                                               # each bar sits behind its row's text
            self.assertTrue(overlap(self.lay[f"bar{i}"], fields[f"{kit.NAMES['row_name']}{i}"]))
            self.assertTrue(inside(self.lay[f"bar{i}"], self.lay[f"row_hit{i}"]))
        for i, tab in enumerate(kit.tabs_of(self.k)):                           # the bracket hugs its label
            x, width = self.lay[f"tab_label{i}"]
            top, left, right = self.lay[f"mark{i}"]
            self.assertLess(left[0], x * TWIPS)
            self.assertGreater(right[0], (x + width) * TWIPS)
            self.assertTrue(inside(top, self.lay[f"tab_hit{i}"]) or overlap(top, self.lay[f"tab_hit{i}"]))
        self.assertEqual(len(kit.tabs_of(self.k)), kit.TABS)

    def test_depth_order(self):
        """Hit areas under the bars, the bars under the text, the dark copies above the bright ones, CLOSE on top."""
        depth = {p["instance"]: p["depth"] for p in self.places if "instance" in p}
        n = kit.NAMES
        for i in range(kit.ROWS):
            self.assertLess(depth[f"{n['row_hit']}{i}"], depth[f"{n['bar']}{i}"])
            self.assertLess(depth[f"{n['bar']}{i}"], depth[f"{n['row_name']}{i}"])
            self.assertLess(depth[f"{n['row_name']}{i}"], depth[f"{n['row_name_sel']}{i}"])
        for i in range(len(kit.tabs_of(self.k))):
            self.assertLess(depth[f"{n['tab_hit']}{i}"], depth[f"{n['tab']}{i}"])
        self.assertEqual(max(depth.values()), depth[n["close"]])

    def test_colours_come_from_one_setting(self):
        c = kit.palette(kit.PIPBOY_GREEN)
        self.assertEqual(c["ink"], 0x1AFF80)
        self.assertEqual(c["screen"], kit.packed(kit.scale(0x1AFF80, 0.07)))

        def rgb(t):
            return (t["color"][0] << 16) | (t["color"][1] << 8) | t["color"][2] if "color" in t else \
                (t["fills"][0][0] << 16) | (t["fills"][0][1] << 8) | t["fills"][0][2]

        def sprite_fill(t):
            return rgb(self.by_id[next(x["character"] for x in t["tags"] if x["name"] == "PlaceObject2")])

        n = kit.NAMES
        for i in range(kit.ROWS):
            self.assertEqual(rgb(self.named[f"{n['row_name']}{i}"]), c["ink"])
            self.assertEqual(rgb(self.named[f"{n['row_name_sel']}{i}"]), c["screen"])   # dark text on the bar
            self.assertEqual(sprite_fill(self.named[f"{n['bar']}{i}"]), c["ink"])
            self.assertEqual(sprite_fill(self.named[f"{n['row_hit']}{i}"]), c["screen"])  # invisible on the screen
            self.assertEqual(rgb(self.named[f"{n['info_label']}{i}"]), c["dim"])
        for i in range(kit.SUBS):
            self.assertEqual(rgb(self.named[f"{n['sub']}{i}"]), c["ink"])
            self.assertEqual(rgb(self.named[f"{n['sub_dim']}{i}"]), c["dim"])
        self.assertEqual(rgb(self.named[n["kit_id"]]), c["screen"])
        amber = kit.palette(0xFFB642)
        _, other, _, other_places, other_named = built(self.k, color=0xFFB642)
        self.assertEqual([p.get("instance") for p in other_places], [p.get("instance") for p in self.places])
        self.assertEqual(rgb(other_named[f"{n['row_name']}0"]), amber["ink"])
        self.assertNotEqual(kit.kit_movie_bytes(self.k, color=0xFFB642), kit.kit_movie_bytes(self.k))
        with self.assertRaises(kit.KitError):
            kit.palette(0x1000000)

    def test_another_ini_draws_its_own_tabs(self):
        k = kit.parse_kit("[Page ONE/A]\nRow=X|health\n[Page TWO/B]\nNotice=WAIT\n[Page ONE/C]\nList=kit_test\n")
        _, _, _, places, named = built(k)
        self.assertEqual(kit.tabs_of(k), ["ONE", "TWO"])
        self.assertEqual([named[f"fo4sfTab{i}"]["text"] for i in range(2)], ["ONE", "TWO"])
        self.assertNotIn("fo4sfTab2", named)
        self.assertNotIn("fo4sfTabMark2", named)
        self.assertEqual(named["fo4sfKitId"]["text"], "FO4SF KIT 1 16 ONE,TWO")
        self.assertEqual([p["instance"] for p in places if "instance" in p], kit.kit_names(k))


class KitStageTests(unittest.TestCase):
    def test_stage_kit_and_the_installers_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            esm, movie = mpp.stage(tmp, kit=True)
            self.assertTrue(movie.endswith(os.path.join("Interface", "FO4SF_PipboyMenu.swf")))
            with open(movie, "rb") as f:
                self.assertEqual(f.read(), kit.kit_movie_bytes(kit.read_kit()))
            mpp.check(esm)
            self.assertEqual(ppi.stage_problems(tmp), [])
            self.assertEqual(sorted(os.listdir(tmp)), ["Data", "FO4SFPipboyProbe.esm", "owner-card.txt"])
            with open(os.path.join(tmp, "owner-card.txt"), "rb") as f:
                self.assertEqual(f.read().decode("utf-8"), mpp.KIT_CARD)
            mpp.stage(tmp, page=True)                            # each page movie its own card
            with open(os.path.join(tmp, "owner-card.txt"), "rb") as f:
                self.assertEqual(f.read().decode("utf-8"), mpp.PAGE_CARD)
            mpp.stage(tmp, kit=True)
            mpp.stage(tmp, channel=True)                         # no page, no card: a stale one would mislead
            self.assertNotIn("owner-card.txt", os.listdir(tmp))

    def test_owner_card_txt_is_the_launchers_format(self):
        # docs/ai/launcher-tests.md (FAL-274): UTF-8, at most 16 KiB, a title, then one to eight steps "1. " to "8. "
        self.assertLessEqual(len(mpp.KIT_CARD.encode("utf-8")), 16384)
        self.assertFalse(any(ord(c) < 32 and c not in "\r\n\t" for c in mpp.KIT_CARD))
        lines = [line.strip() for line in mpp.KIT_CARD.splitlines() if line.strip()]
        self.assertEqual(len(lines), 9)
        self.assertNotRegex(lines[0], r"^\d+\.")
        for i, line in enumerate(lines[1:], 1):
            self.assertRegex(line, rf"^{i}\. \S")
        steps = "\n".join(lines[1:]).lower()
        for word in ("console", "log", "save", "install", "`", "*", "#"):
            self.assertNotIn(word, steps, word)
        for seen in ("F10", "STAT", "SPECIAL", "KIT TEST", "TEST ROW 30", "MAP", "CLOSE", "Q", "E", "S", "D"):
            self.assertIn(seen, mpp.KIT_CARD, seen)
        self.assertNotEqual(mpp.KIT_CARD, mpp.PAGE_CARD)

    def test_stage_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(mpp.main(["stage", tmp, "--kit", "--color", "FFB642"]), 0)
            with open(os.path.join(tmp, "Data", "Interface", "FO4SF_PipboyMenu.swf"), "rb") as f:
                self.assertEqual(f.read(), kit.kit_movie_bytes(kit.read_kit(), color=0xFFB642))
            for other in ("--page", "--channel"):
                with self.assertRaises(SystemExit):
                    mpp.main(["stage", tmp, "--kit", other])
            self.assertEqual(mpp.main(["stage", tmp, "--kit", "--color", "nope"]), 1)

    def test_a_wrong_page_stages_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini = os.path.join(tmp, "bad.ini")
            with open(ini, "w", encoding="ascii") as f:
                f.write("[Page T/S]\nRow=A|nothing\n")
            out = os.path.join(tmp, "stage")
            self.assertEqual(mpp.main(["stage", out, "--kit", "--ini", ini]), 1)
            self.assertFalse(os.path.exists(out))


class KitPluginTests(unittest.TestCase):
    """The plugin's kit code (main.cpp, "stage e: the kit") against the generator, as text."""
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="ascii")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    section = main[re.search(r"// -+ stage e: the kit", main).start():re.search(r"// -+ the menu's slots", main).start()]

    def constant(self, name):
        return re.search(rf"constexpr \S+\s+{name} = ([^;]+);", self.main).group(1)

    def test_sizes_columns_and_font_agree(self):
        for name, value in (("kKitTabs", kit.TABS), ("kKitSubs", kit.SUBS), ("kKitRows", kit.ROWS),
                            ("kKitFooter", kit.FOOTER), ("kKitMaxPageRows", kit.MAX_PAGE_ROWS),
                            ("kKitTitleColumns", kit.TITLE_COLUMNS), ("kKitTabColumns", kit.TAB_COLUMNS),
                            ("kKitSubColumns", kit.SUB_COLUMNS), ("kKitNameColumns", kit.NAME_COLUMNS),
                            ("kKitValueColumns", kit.VALUE_COLUMNS), ("kKitInfoLabelColumns", kit.INFO_LABEL_COLUMNS),
                            ("kKitInfoValueColumns", kit.INFO_VALUE_COLUMNS), ("kKitFooterColumns", kit.FOOTER_COLUMNS),
                            ("kKitFooterLabelColumns", kit.FOOTER_LABEL_COLUMNS), ("kKitHintColumns", kit.HINT_COLUMNS),
                            ("kKitVersion", kit.KIT_VERSION)):
            self.assertEqual(int(self.constant(name)), value, name)
        chars = re.search(r'constexpr std::string_view kKitChars = "((?:[^"\\]|\\.)*)";', self.main).group(1)
        self.assertEqual(chars, kit.KIT_CHARS)
        self.assertIn('return std::format("FO4SF KIT {} {} {}", kKitVersion, kKitRows, tabs);',
                      function(self.main, "std::string KitSignature()"))

    def test_names_agree(self):
        found = dict(re.findall(r'constexpr auto\s+(kKit\w+) = "(fo4sf\w+)";', self.main))
        constants = {"title": "kKitTitle", "header": "kKitHeader", "tab": "kKitTab", "mark": "kKitTabMark",
                     "tab_hit": "kKitTabHit", "sub": "kKitSub", "sub_dim": "kKitSubDim", "sub_hit": "kKitSubHit",
                     "row_name": "kKitRowName", "row_value": "kKitRowValue", "row_name_sel": "kKitRowNameSel",
                     "row_value_sel": "kKitRowValueSel", "bar": "kKitBar", "row_hit": "kKitRowHit",
                     "more_up": "kKitMoreUp", "more_down": "kKitMoreDown", "info_label": "kKitInfoLabel",
                     "info_value": "kKitInfoValue", "foot": "kKitFoot", "hints": "kKitHints", "close": "kKitClose",
                     "kit_id": "kKitId"}
        self.assertEqual(sorted(constants), sorted(kit.NAMES))
        self.assertEqual(found, {constants[key]: value for key, value in kit.NAMES.items()})

    def test_providers_agree(self):
        values = re.search(r"kKitValues\{([^}]*)\}", self.main).group(1)
        self.assertEqual(tuple(re.findall(r'"(\w+)"', values)), kit.VALUE_PROVIDERS)
        lists = re.search(r"kKitLists\{([^}]*)\}", self.main).group(1)
        self.assertEqual(tuple(re.findall(r'"(\w+)"', lists)), kit.LIST_PROVIDERS)
        self.assertEqual(self.constant("kKitActorValue"), f'"{kit.AV_PREFIX}"')
        read = function(self.main, "std::string KitValueRead(")
        for name in kit.VALUE_PROVIDERS:
            self.assertIn(f'if (a_spec == "{name}") {{', read, name)
        self.assertIn("a_spec.starts_with(kKitActorValue)", read)
        self.assertIn('return Unknown(a_spec, "reason=no_such_value");', read)
        collect = function(self.main, "void KitCollect()")
        for name in kit.LIST_PROVIDERS:
            self.assertIn(f'page.list == "{name}"', collect)

    def test_read_kit_mirrors_parse_kit(self):
        read = function(self.main, "bool ReadKit(")
        for check in ('line[0] == \';\' || line[0] == \'#\'', "line.back() != ']'", 'name == "Kit"',
                      'name.starts_with("Page ")', "path.find('/', slash + 1) != std::string_view::npos",
                      "KitLabel(page.tab, kKitTabColumns) || !KitLabel(page.sub, kKitSubColumns)",
                      "other.tab == page.tab && other.sub == page.sub",
                      'key == "Title" && KitLabel(value, kKitTitleColumns)', 'key == "Header" && KitValueName(value)',
                      'key == "Hints" && KitLabel(value, kKitHintColumns)',
                      'key == "Row" && page.rows.size() < kKitMaxPageRows && KitCellOf(value, kKitNameColumns, cell)',
                      'key == "List" && page.list.empty() && std::ranges::find(kKitLists, value) != kKitLists.end()',
                      'key == "Notice" && page.notice.size() < kKitRows && KitLabel(value, kKitNameColumns)',
                      'key == "Footer" && page.footer.size() < kKitFooter && KitCellOf(value, kKitFooterLabelColumns, cell)',
                      'key == "Hint" && KitLabel(value, kKitHintColumns)', "if (kinds != 1) {",
                      "if (g_kit.tabs.size() == kKitTabs) {", "if (subs.size() == kKitSubs) {",
                      'return KitRefuse(n, "no_pages");'):
            self.assertIn(check, read, check)
        cell = function(self.main, "bool KitCellOf(")
        self.assertIn("a_text.find('|', bar + 1) != std::string_view::npos", cell)
        value = function(self.main, "bool KitValueName(")
        self.assertIn("hex.size() <= 8", value)
        self.assertIn("std::strtoul(std::string(hex).c_str(), nullptr, 16) != 0", value)
        self.assertIn('" \\t\\r"', function(self.main, "std::string_view KitTrim("))
        self.assertIn('Refuse("pages"', function(self.main, "bool KitRefuse("))

    def test_threads(self):
        """The screen is built on the main thread with stage d's reads, and written on the menu's with no reads."""
        self.assertEqual(self.main.count("KitCollect();"), 2)
        self.assertIn("if (g_stage == 5 && !open) {\n\t\t\tKitCollect();", function(self.main, "void Toggle("))
        self.assertIn("if (g_stage == 5) {\n\t\t\tKitCollect();", function(self.main, "void SendUpdate()"))
        process = function(self.main, "RE::UI_MESSAGE_RESULT MenuProcessMessage(")
        self.assertIn("KitListen(a_self);\n\t\t\t\t\tKitWrite(a_self, 0, true);", process)
        self.assertIn("KitWrite(a_self, n, false);", process)
        self.assertNotIn("KitCollect", process)
        collect = function(self.main, "void KitCollect()")
        self.assertLess(collect.index("PageScan();"), collect.index("FindGlobalValue();"))   # as stage d's PageCollect
        for name in ("void KitCollect()", "std::string KitValueRead(", "std::uintptr_t KitActorValue("):
            body = function(self.main, name)
            for scaleform in ("SetMember", "GetMember", "Invoke(", "GetVariable", "ChildOf("):
                self.assertNotIn(scaleform, body, (name, scaleform))
        for name in ("void KitWrite(", "void KitSetText(", "void KitSetShown(", "void KitListen(", "std::string KitAct(",
                     "std::string KitClick("):
            body = function(self.main, name)
            for game in ("Peek(", "AcceptById", "KitValue(", "PageScan", "ActorValueText", "Singleton("):
                self.assertNotIn(game, body, (name, game))
        write = function(self.main, "void KitWrite(")
        self.assertLess(write.index("RootOf(a_menu)"), write.index("GetVariable("))
        self.assertIn("std::scoped_lock lock(g_pageLock);", write)
        self.assertLess(write.index("screen = g_kitScreen;"), write.index("GetVariable("))   # copied, then unlocked
        self.assertIn("std::scoped_lock lock(g_pageLock);", function(self.main, "std::string KitAct("))

    def test_only_text_and_visible_are_set(self):
        members = re.findall(r'SetMember\("(\w+)"', self.section)
        self.assertEqual(sorted(set(members)), ["text", "visible"])
        self.assertIn('field.GetMember("text", &back) && back.IsString() && a_text == back.GetString()',
                      function(self.main, "void KitSetText("))
        self.assertIn('object.GetMember("visible", &back) && back.IsBoolean() && back.GetBoolean() == a_shown',
                      function(self.main, "void KitSetShown("))
        click = self.section[self.section.index("class KitClickHandler"):self.section.index("KitClickHandler g_kitClickHandler")]
        self.assertEqual(re.findall(r'GetMember\("(\w+)"', click), ["target", "name"])
        self.assertNotIn("AddMessage", click)
        self.assertNotIn("g_task", click)

    def test_nothing_new_is_called_in_the_game(self):
        self.assertNotIn("REL::Relocation", self.section)
        self.assertNotIn("REL::ID", self.section)
        self.assertNotIn("reinterpret_cast<", self.section)
        self.assertNotIn("FormById(", self.section)
        self.assertEqual(self.main.count("FormById("), 4)                     # stage d's: the definition and three
        self.assertEqual(self.main.count("reinterpret_cast<GetActorValue_t>"), 1)
        actor = function(self.main, "std::uintptr_t KitActorValue(")
        self.assertIn('AcceptById(a_id, "av", "ActorValueInfo@@", kAvifEditorIdAt, form)', actor)
        self.assertIn("g_kitActorValues.emplace(a_id, form);", actor)        # once per id
        self.assertIn("return ActorValueText(a_spec, KitActorValue(id));", function(self.main, "std::string KitValueRead("))

    def test_time_and_days_only_at_the_checked_value_offset(self):
        # stage d's ReadTime at the offset FindGlobalValue found (libxse's +0x40 read -3.5924 at a156037c)
        read = function(self.main, "std::string KitValueRead(")
        self.assertIn("return TimeText();", read)
        days = read[read.index('if (a_spec == "days")'):read.index('if (a_spec == "position")')]
        self.assertIn("if (!ReadTime(g_forms.globalValueAt, hour, days)) {", days)
        for reason in ('"globals_unread"', '"no_value_offset"', '"out_of_range"'):
            self.assertIn(reason, days, reason)
        self.assertNotIn("Peek(", days)
        self.assertNotIn("kGlobalValueAt", self.main)

    def test_clicks_reach_tabs_sub_tabs_and_rows(self):
        click = function(self.main, "std::string KitClick(")
        for group, move in (("{ kKitTab, kKitTabMark, kKitTabHit }", "KitMove::kTab"),
                            ("{ kKitSub, kKitSubDim, kKitSubHit }", "KitMove::kSub"),
                            ("{ kKitRowName, kKitRowValue, kKitRowNameSel, kKitRowValueSel, kKitBar, kKitRowHit }",
                             "KitMove::kRow")):
            self.assertIn(group, click)
            self.assertIn(f"KitAct({move}, *i, false)", click)
        self.assertIn("digits.size() > 2", click)                              # "fo4sfTab" + "Mark1" is no tab
        listen = function(self.main, "void KitListen(")
        self.assertIn("KitAddListener(root, top, &g_kitClickHandler, rootFunction)", listen)
        self.assertIn("KitAddListener(root, close, &g_closeHandler, closeFunction)", listen)
        self.assertIn('"step=kit_movie id=\\"{}\\" expected=\\"{}\\" match={}"', listen)
        add = function(self.main, "bool KitAddListener(")
        self.assertIn('args[0] = "click";', add)
        act = function(self.main, "std::string KitAct(")
        self.assertIn("g_refreshNow = true;", act)
        self.assertIn("s.top[page] = KitTop(s.top[page], s.selected[page], count);", act)

    def test_keys(self):
        defaults = dict(re.findall(r'\{ KitMove::k\w+, L"(Kit\w+)", L"([0-9x,]+)" \}', self.main))
        self.assertEqual(list(defaults), ["KitUp", "KitDown", "KitPrevSub", "KitNextSub", "KitPrevTab", "KitNextTab"])
        for key, value in defaults.items():
            self.assertIn(f"\n{key}={value}\n", self.ini)                       # the shipped ini says the defaults
        read = function(self.main, "bool ReadKitKeys(")
        self.assertIn("vk == 0 || vk > 0xFE || vk == g_key || vk == g_snapshotKey", read)
        thread = function(self.main, "std::uint32_t KeyThread(")
        self.assertIn("if (g_open && GameInFront()) {\n\t\t\t\t\tKitKeys(kitHeld);", thread)
        self.assertIn("if (g_stage >= 4) {", thread)
        keys = function(self.main, "void KitKeys(")
        self.assertIn("binding.move == KitMove::kUp || binding.move == KitMove::kDown", keys)
        for vk in ("0x26", "0x28", "0x25", "0x27", "0x57", "0x53", "0x41", "0x44", "0x51", "0x45"):
            self.assertIn(vk, " ".join(defaults.values()))
        self.assertNotIn("0x09", " ".join(defaults.values()))                  # Tab: only if the session says so

    def test_stage_wiring(self):
        self.assertIn("if (g_stage == 5 && (!ReadKitKeys(ini) || !ReadKit(ini))) {", self.main)
        load = self.main[self.main.index("SFSE_PLUGIN_LOAD"):]
        self.assertLess(load.index("ReadKit(ini)"), load.index("CheckEverything(dir)"))
        self.assertIn("if (g_stage < 1 || g_stage > 5) {", self.main)
        self.assertIn('g_stage == 5 ? "e" : g_stage == 4 ? "d" : "c"', self.main)
        self.assertIn('g_stage == 3 ? "c" : g_stage == 4 ? "d" : "e"', self.main)
        self.assertIn("if (g_stage >= 4) {   // (d) and (e)\n\t\t\tReadFlagSets(ini, L\"PageFlagSets\", L\"0x9\");",
                      self.main)
        self.assertIn("; 5 = stage (e): the page kit", self.ini)
        self.assertIn("\nPageFlagSets=0x9\n", self.ini)

    def test_every_literal_on_the_kit_is_in_its_font(self):
        bodies = "".join(function(self.main, f) for f in ("void KitCollect()", "std::string KitValueRead(",
                                                          "std::vector<KitRow> KitTestRows("))
        texts = [t for t in re.findall(r'"([^"]*)"', bodies) if t and t == t.upper()]
        self.assertGreaterEqual(len(texts), 8)
        for text in texts:
            sample = re.sub(r"\{[^}]*\}", "12", text)
            self.assertTrue(set(sample) <= set(kit.KIT_FONT), text)
        for name in ("std::string KitRight(", "std::string KitCentre("):
            self.assertIn("const auto text = KitText(a_text, a_columns);", function(self.main, name))
        text = function(self.main, "std::string KitText(")
        self.assertIn("a_text.substr(0, a_columns)", text)
        self.assertIn("kKitChars.find(up) != std::string_view::npos ? up : '?'", text)

    def test_readme(self):
        self.assertIn("## Stage (e): the page kit (FAL-301)", self.readme)
        self.assertIn("### PASS at (e), `Stage=5`", self.readme)
        for line in ("refuse step=pages line=", "step=kit_movie", "step=kit n=", "step=kit_key", "step=kit_click",
                     "step=kit_av", "step=page_def", "step=listen name=root", "refuse step=ini kit_key="):
            self.assertIn(line, self.readme, line)
        for name in kit.VALUE_PROVIDERS + kit.LIST_PROVIDERS:
            self.assertIn(f"`{name}`", self.readme, name)


class KitOwnerCardTests(unittest.TestCase):
    card = (ROOT / "docs" / "spikes" / "pipboy-page-kit-owner-card.md").read_text(encoding="utf-8")

    def test_owner_card(self):
        owner = self.card[:self.card.index("## For the PC helper")]
        steps = owner[owner.index("## The eight steps"):owner.index("**Report:**")]
        rows = [r for r in steps.splitlines() if re.match(r"\| \d \|", r)]
        self.assertEqual([int(r.split("|")[1]) for r in rows], list(range(1, 9)))
        for word in ("console", "log", "save"):
            self.assertNotIn(word, steps.lower(), word)
        for seen in ("F10", "STAT", "SPECIAL", "KIT TEST", "MAP", "CLOSE", "**Q**", "**E**", "**S**", "**D**"):
            self.assertIn(seen, steps, seen)
        helper = self.card[self.card.index("## For the PC helper"):]
        self.assertIn("make_pipboy_probe.py stage $exp --kit", helper)
        self.assertIn("-replace '^Stage=0','Stage=5'", helper)
        self.assertIn("tests.test_pipboy_kit", helper)
        for control in ("player.getav strength", "player.getav luck", "player.getav health", "player.getlevel"):
            self.assertIn(control, helper, control)


if __name__ == "__main__":
    unittest.main()
