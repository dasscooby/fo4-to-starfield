"""The Pip-Boy page kit (FAL-301; sfse/FO4SFPipboyMenu/README.md, "Stage (e): the page kit"): one movie for every page,
and the pages as data.

usage: python scripts/ui/make_pipboy_kit.py --out <file.swf> [--ini <FO4SFPipboyMenu.ini>] [--color RRGGBB]
                                            [--uncompressed]
       python scripts/ui/make_pipboy_kit.py --check [--ini <FO4SFPipboyMenu.ini>]   the pages, as JSON

A page is a section of the plugin's own ini, read by this script (to draw the main tabs) and by the plugin at load (to
fill them); adding or changing a page is an edit of that file and a re-stage, no new code and no new movie by hand:

  [Kit]                     Title=<text>, Header=<value> (the title bar's right side), Hints=<text> (the key hints)
  [Page <TAB>/<SUB>]        one page: the main tab it sits under and its sub-tab, in the order the sections come; then
                            exactly one of
    Row=<label>|<value>       a row of the list, its value from a value provider (any number, scrolled 16 at a time)
    List=<list>               the rows from a list provider
    Notice=<text>             a line of a placeholder page (up to 16)
                            and, on any page,
    Footer=<label>|<value>    a footer cell (up to three)
    Hint=<text>               the key hints on this page instead of [Kit]'s

Values (VALUE_PROVIDERS): health, level, xp, carry_max, rads, cell, world, time, days, position, and av:<hex>, any
actor value by its form id (Starfield.esm's are 00 + the id: av:2C2 is Strength). Lists (LIST_PROVIDERS): kit_test,
inventory (the player's items, FAL-426).
Every label is upper case in KIT_FONT's characters and fits its field; the plugin refuses the whole file otherwise
(`refuse step=pages line=<n> reason=<r>`), as --check does here.

The movie is make_probe_swf.py's kind (CWS, SWF 12, the ActionScript 3 flag, no code, its own 5 x 7 font): a dark screen
in one phosphor colour (--color; every other colour is derived from it), and named children the plugin finds with
getChildByName and changes through `text` and `visible` only:
  title bar     fo4sfTitle, fo4sfHeaderInfo
  main tabs     fo4sfTab<i> (the label), fo4sfTabMark<i> (the bracket around it), fo4sfTabHit<i>
  sub-tabs      fo4sfSub<i> (bright, the shown one), fo4sfSubDim<i> (the others), fo4sfSubHit<i>, 5 slots
  list          fo4sfRowName<i> and fo4sfRowValue<i>, fo4sfRowNameSel<i> and fo4sfRowValueSel<i> (dark, on the bar),
                fo4sfBar<i> (the selection bar), fo4sfRowHit<i>, 16 rows; fo4sfMoreUp and fo4sfMoreDown (scrolling)
  value rows    fo4sfInfoLabel<i> and fo4sfInfoValue<i>, 16 two-column rows beside the list
  footer        fo4sfFoot<i>, 3 cells; fo4sfHints, the key hints under the screen; fo4sfClose, the CLOSE button
  check         fo4sfKitId, the kit's signature in the screen's own colour (invisible), which the plugin compares
                with the one it builds from the ini it read
Clicks reach one listener on the root, which reads the click's target name; the hit sprites (filled in the screen's
colour, so invisible) sit under the text, so a click anywhere on a tab, a sub-tab or a row names it. Output is
deterministic; nothing is written into the repo.
"""
import argparse
import json
import os
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_probe_swf as swf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
INI = os.path.join(REPO, "sfse", "FO4SFPipboyMenu", "FO4SFPipboyMenu.ini")
TWIPS = swf.TWIPS
KIT_VERSION = 1

# the font: the STAT page's table plus what hints and lists need
KIT_GLYPHS = {
    "[": (0x0E, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0E), "]": (0x0E, 0x02, 0x02, 0x02, 0x02, 0x02, 0x0E),
    "<": (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02), ">": (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08),
    "*": (0x00, 0x04, 0x15, 0x0E, 0x15, 0x04, 0x00), ";": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x04, 0x08),
}
KIT_FONT = {**swf.PAGE_FONT, **KIT_GLYPHS}
KIT_CHARS = "".join(sorted(KIT_FONT))

# the layout, in stage pixels (1920 x 1080, the stage of every movie here)
STAGE = (1920, 1080)
SCREEN = (160, 56, 1600, 904)            # the Pip-Boy screen: x, y, width, height
PAD = 32                                 # the screen's inner margin, left and right
TITLE_PX, TAB_PX, TEXT_PX, HINT_PX, ID_PX = 24, 36, 28, 24, 10   # font sizes (one em)
TABS, SUBS, ROWS, FOOTER = 5, 5, 16, 3   # main tabs, sub-tab slots, list rows on screen, footer cells
ROW_PITCH = 36
LIST_WIDTH = 900                         # the list's column; the value rows fill the rest after INFO_GAP
INFO_GAP = 36
TITLE_Y, TAB_Y, UNDERLINE_Y, SUB_Y, ROW_Y = 68, 108, 160, 174, 226
FOOTER_Y, FOOTER_H, FOOTER_GAP = 904, 40, 12
HINT_Y = 972
HINT_BAND = (960, 62)                    # the dark band under the screen that holds the hints: y, height
CLOSE_BOX = (1528, 964, 200, 56)         # the CLOSE button, on that band at the screen's right edge
LINE = 3                                 # the width of every drawn line

# the columns of each field: what the plugin may write into it (KitText), the generator's fields fit them
TITLE_COLUMNS = 42
TAB_COLUMNS = 9
SUB_COLUMNS = 13
NAME_COLUMNS = 33
VALUE_COLUMNS = 8
INFO_LABEL_COLUMNS = 16
INFO_VALUE_COLUMNS = 12
FOOTER_COLUMNS = 23
HINT_COLUMNS = 72
FOOTER_LABEL_COLUMNS = 10
MAX_PAGE_ROWS = 64                       # Row= lines per page

# the names the plugin uses (main.cpp, "stage e: the kit", kKit...Name), <i> appended where there are several
NAMES = {
    "title": "fo4sfTitle", "header": "fo4sfHeaderInfo", "tab": "fo4sfTab", "mark": "fo4sfTabMark",
    "tab_hit": "fo4sfTabHit", "sub": "fo4sfSub", "sub_dim": "fo4sfSubDim", "sub_hit": "fo4sfSubHit",
    "row_name": "fo4sfRowName", "row_value": "fo4sfRowValue", "row_name_sel": "fo4sfRowNameSel",
    "row_value_sel": "fo4sfRowValueSel", "bar": "fo4sfBar", "row_hit": "fo4sfRowHit", "more_up": "fo4sfMoreUp",
    "more_down": "fo4sfMoreDown", "info_label": "fo4sfInfoLabel", "info_value": "fo4sfInfoValue", "foot": "fo4sfFoot",
    "hints": "fo4sfHints", "close": "fo4sfClose", "kit_id": "fo4sfKitId",
}

VALUE_PROVIDERS = ("health", "level", "xp", "carry_max", "rads", "cell", "world", "time", "days", "position")
LIST_PROVIDERS = ("kit_test", "inventory")
AV_PREFIX = "av:"
PIPBOY_GREEN = swf.PIPBOY_GREEN


class KitError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ the pages (data)
def _fits(text, columns, what, line):
    if not text:
        raise KitError(f"line {line}: {what} is empty")
    bad = sorted({c for c in text if c not in KIT_FONT})
    if bad:
        raise KitError(f"line {line}: {what} {text!r} has characters the kit's font lacks: {bad} (upper case only)")
    if len(text) > columns:
        raise KitError(f"line {line}: {what} {text!r} is longer than its {columns} columns")
    return text


def check_value(spec, line):
    """A value provider's name, or av:<1 to 8 hex digits, not zero>."""
    if spec in VALUE_PROVIDERS:
        return spec
    if spec.startswith(AV_PREFIX) and re.fullmatch(r"[0-9A-Fa-f]{1,8}", spec[len(AV_PREFIX):]) and \
            int(spec[len(AV_PREFIX):], 16):
        return spec
    raise KitError(f"line {line}: value {spec!r} is not a value provider ({', '.join(VALUE_PROVIDERS)}, av:<hex>)")


def _cell(value, line, columns, what):
    if value.count("|") != 1:
        raise KitError(f"line {line}: {what} needs <label>|<value>")
    label, spec = (part.strip() for part in value.split("|"))
    return _fits(label, columns, f"{what} label", line), check_value(spec, line)


def parse_kit(text):
    """The [Kit] section and the [Page <TAB>/<SUB>] sections of the ini, checked; other sections are skipped. The
    plugin's ReadKit (main.cpp) reads the same grammar with the same checks."""
    kit = {"title": "FO4SF PIP-BOY", "header": "", "hints": "", "pages": []}
    section = None
    page = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip(" \t\r")
        if not line or line[0] in ";#":
            continue
        if line[0] == "[":
            if line[-1] != "]":
                raise KitError(f"line {n}: a section name without its ]")
            name = line[1:-1].strip(" \t")
            page = None
            if name == "Kit":
                section = "kit"
            elif name.startswith("Page "):
                path = name[5:].strip(" \t")
                if path.count("/") != 1:
                    raise KitError(f"line {n}: a page is [Page <TAB>/<SUB>]")
                tab, sub = (part.strip(" \t") for part in path.split("/"))
                page = {"tab": _fits(tab, TAB_COLUMNS, "tab", n), "sub": _fits(sub, SUB_COLUMNS, "sub-tab", n),
                        "rows": [], "list": "", "notice": [], "footer": [], "hint": "", "line": n}
                if any(p["tab"] == tab and p["sub"] == sub for p in kit["pages"]):
                    raise KitError(f"line {n}: page {tab}/{sub} comes twice")
                kit["pages"].append(page)
                section = "page"
            else:
                section = None
            continue
        if section is None:
            continue
        if "=" not in line:
            raise KitError(f"line {n}: <key>=<value> expected")
        key, value = (part.strip(" \t") for part in line.split("=", 1))
        if section == "kit":
            if key == "Title":
                kit["title"] = _fits(value, TITLE_COLUMNS, "title", n)
            elif key == "Header":
                kit["header"] = check_value(value, n)
            elif key == "Hints":
                kit["hints"] = _fits(value, HINT_COLUMNS, "hints", n)
            else:
                raise KitError(f"line {n}: [Kit] has no key {key!r} (Title, Header, Hints)")
            continue
        if key == "Row":
            if len(page["rows"]) == MAX_PAGE_ROWS:
                raise KitError(f"line {n}: more than {MAX_PAGE_ROWS} rows")
            page["rows"].append(_cell(value, n, NAME_COLUMNS, "row"))
        elif key == "List":
            if page["list"]:
                raise KitError(f"line {n}: a second List")
            if value not in LIST_PROVIDERS:
                raise KitError(f"line {n}: list {value!r} is not a list provider ({', '.join(LIST_PROVIDERS)})")
            page["list"] = value
        elif key == "Notice":
            if len(page["notice"]) == ROWS:
                raise KitError(f"line {n}: more than {ROWS} notice lines")
            page["notice"].append(_fits(value, NAME_COLUMNS, "notice", n))
        elif key == "Footer":
            if len(page["footer"]) == FOOTER:
                raise KitError(f"line {n}: more than {FOOTER} footer cells")
            page["footer"].append(_cell(value, n, FOOTER_LABEL_COLUMNS, "footer"))
        elif key == "Hint":
            page["hint"] = _fits(value, HINT_COLUMNS, "hint", n)
        else:
            raise KitError(f"line {n}: a page has no key {key!r} (Row, List, Notice, Footer, Hint)")
    if not kit["pages"]:
        raise KitError("no [Page <TAB>/<SUB>] section")
    for p in kit["pages"]:
        kinds = bool(p["rows"]) + bool(p["list"]) + bool(p["notice"])
        if kinds != 1:
            raise KitError(f"line {p['line']}: page {p['tab']}/{p['sub']} needs exactly one of Row, List and Notice")
    tabs = tabs_of(kit)
    if len(tabs) > TABS:
        raise KitError(f"{len(tabs)} main tabs, the kit has {TABS}")
    for tab in tabs:
        subs = [p for p in kit["pages"] if p["tab"] == tab]
        if len(subs) > SUBS:
            raise KitError(f"main tab {tab} has {len(subs)} sub-tabs, the kit has {SUBS}")
    return kit


def read_kit(path=INI):
    with open(path, encoding="ascii") as f:
        return parse_kit(f.read())


def tabs_of(kit):
    """The main tabs, in the order their first page comes."""
    out = []
    for p in kit["pages"]:
        if p["tab"] not in out:
            out.append(p["tab"])
    return out


def signature(kit):
    """What fo4sfKitId says, and what the plugin builds from the ini it read (KitSignature): a mismatch means the
    movie was staged from another ini."""
    return f"FO4SF KIT {KIT_VERSION} {ROWS} {','.join(tabs_of(kit))}"


# ------------------------------------------------------------------------------------------------ the colours
def scale(rgb, k):
    return tuple(min(255, int(round(c * k))) for c in ((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF))


def packed(t):
    return (t[0] << 16) | (t[1] << 8) | t[2]


def palette(color):
    """Every colour of the kit from the one phosphor colour: the screen, the dim text, the footer's boxes."""
    if not 0 <= color <= 0xFFFFFF:
        raise KitError("the colour is RRGGBB")
    return {"ink": color, "screen": packed(scale(color, 0.07)), "dim": packed(scale(color, 0.45)),
            "box": packed(scale(color, 0.22))}


# ------------------------------------------------------------------------------------------------ the movie
def advance(px):
    """One character's width in pixels at that font size: six of the font's eight pixels to the em."""
    return px * 6 / 8


def text_box(x, y, columns, px, height=None):
    """A field that holds `columns` characters at px, in twips; text starts 2 px in (the field's gutter)."""
    w = int(columns * advance(px)) + 4
    return x * TWIPS, y * TWIPS, w * TWIPS, (height or px + px // 4 + 4) * TWIPS


def rx(x, y, w, h):
    return x * TWIPS, y * TWIPS, w * TWIPS, h * TWIPS


def layout(kit):
    """Every box of the kit in twips (x, y, w, h), keyed by name; the tests check that each fits the screen and that
    no two text fields overlap."""
    sx, sy, sw, sh = SCREEN
    left, right = sx + PAD, sx + sw - PAD
    inner = right - left
    tabs = tabs_of(kit)
    out = {"screen": rx(*SCREEN)}
    out["title"] = text_box(left, TITLE_Y, TITLE_COLUMNS, TITLE_PX)
    header_w = int(TITLE_COLUMNS * advance(TITLE_PX)) + 4
    out["header"] = text_box(right - header_w, TITLE_Y, TITLE_COLUMNS, TITLE_PX)
    slot = inner // TABS
    for i, tab in enumerate(tabs):
        width = int(len(tab) * advance(TAB_PX))
        x = left + i * slot + (slot - width) // 2
        out[f"tab{i}"] = text_box(x - 2, TAB_Y, len(tab) + 1, TAB_PX, TAB_PX + 12)
        out[f"tab_label{i}"] = (x, width)
        out[f"tab_hit{i}"] = rx(left + i * slot, TAB_Y - 4, slot, UNDERLINE_Y - TAB_Y + 4)
        m = 14
        out[f"mark{i}"] = [rx(x - m, TAB_Y - 4, width + 2 * m, LINE),
                           rx(x - m, TAB_Y - 4, LINE, UNDERLINE_Y - TAB_Y + 4 + LINE),
                           rx(x + width + m - LINE, TAB_Y - 4, LINE, UNDERLINE_Y - TAB_Y + 4 + LINE)]
    out["underline"] = rx(left, UNDERLINE_Y, inner, LINE)
    sub_slot = inner // SUBS
    for i in range(SUBS):
        out[f"sub{i}"] = text_box(left + i * sub_slot, SUB_Y, SUB_COLUMNS, TEXT_PX, ROW_PITCH)
        out[f"sub_hit{i}"] = rx(left + i * sub_slot, SUB_Y - 4, sub_slot, ROW_PITCH + 4)
    value_w = int(VALUE_COLUMNS * advance(TEXT_PX)) + 4
    info_x = left + LIST_WIDTH + INFO_GAP
    info_value_w = int(INFO_VALUE_COLUMNS * advance(TEXT_PX)) + 4
    for i in range(ROWS):
        y = ROW_Y + i * ROW_PITCH
        out[f"row_name{i}"] = text_box(left + 8, y, NAME_COLUMNS, TEXT_PX, ROW_PITCH)
        out[f"row_value{i}"] = text_box(left + LIST_WIDTH - 8 - value_w, y, VALUE_COLUMNS, TEXT_PX, ROW_PITCH)
        out[f"bar{i}"] = rx(left, y - 1, LIST_WIDTH, TEXT_PX + 3)
        out[f"row_hit{i}"] = rx(left, y - 3, LIST_WIDTH, ROW_PITCH)
        out[f"info_label{i}"] = text_box(info_x, y, INFO_LABEL_COLUMNS, TEXT_PX, ROW_PITCH)
        out[f"info_value{i}"] = text_box(right - info_value_w, y, INFO_VALUE_COLUMNS, TEXT_PX, ROW_PITCH)
    arrow_x = left + LIST_WIDTH + 8
    out["more_up"] = [rx(arrow_x + 8 - 2 * k, ROW_Y + 2 * k, 4 * k + 2, 2) for k in range(5)]
    bottom = ROW_Y + (ROWS - 1) * ROW_PITCH + TEXT_PX
    out["more_down"] = [rx(arrow_x + 8 - 2 * k, bottom - 2 * k - 2, 4 * k + 2, 2) for k in range(5)]
    cell_w = (inner - (FOOTER - 1) * FOOTER_GAP) // FOOTER
    for i in range(FOOTER):
        cx = left + i * (cell_w + FOOTER_GAP)
        out[f"foot_box{i}"] = rx(cx, FOOTER_Y, cell_w, FOOTER_H)
        out[f"foot{i}"] = text_box(cx + (cell_w - int(FOOTER_COLUMNS * advance(TEXT_PX)) - 4) // 2, FOOTER_Y + 4,
                                   FOOTER_COLUMNS, TEXT_PX, ROW_PITCH)
    out["hint_band"] = rx(sx, HINT_BAND[0], sw, HINT_BAND[1])
    out["hints"] = text_box(left, HINT_Y, HINT_COLUMNS, HINT_PX)
    out["close"] = rx(*CLOSE_BOX)
    out["kit_id"] = text_box(left, FOOTER_Y + FOOTER_H + 2, len(signature(kit)), ID_PX, ID_PX + 4)
    return out


class _Movie:
    """Definitions and placements, ids and depths given out in order."""

    def __init__(self):
        self.defs, self.places, self.next_id, self.depth = [], [], 1, 1

    def define(self, make):
        char_id = self.next_id
        self.next_id += 1
        self.defs.append(make(char_id))
        return char_id

    def place(self, char_id, name=None):
        self.places.append(swf.place_named(char_id, self.depth, name) if name else
                           swf.place_object2(char_id, self.depth))
        self.depth += 1

    def shape(self, boxes, rgb, name=None):
        """A shape of filled boxes, placed as it is, or with a name inside a sprite of its own (a shape is not an
        InteractiveObject: it has no name to click and no `visible` the plugin sets)."""
        shape_id = self.define(lambda i: swf.define_shape3(i, list(boxes), rgb))
        if name:
            sprite_id = self.define(lambda i: swf.define_sprite(i, [swf.place_object2(shape_id, 1)]))
            self.place(sprite_id, name)
        else:
            self.place(shape_id)

    def field(self, box, px, rgb, text, name, font_id):
        field_id = self.define(lambda i: swf.define_edit_text(i, box, font_id, px * TWIPS, rgb, text))
        self.place(field_id, name)


def kit_movie_bytes(kit, color=PIPBOY_GREEN, compressed=True):
    """The kit's movie for these pages (parse_kit) in this colour."""
    c = palette(color)
    lay = layout(kit)
    tabs = tabs_of(kit)
    m = _Movie()
    n = NAMES
    font_id = m.define(lambda i: swf.define_font3(i, KIT_FONT))
    m.shape([lay["screen"]], c["screen"])
    m.shape([lay["hint_band"]], c["screen"])
    m.shape([lay[f"foot_box{i}"] for i in range(FOOTER)], c["box"])
    m.shape([lay["underline"]], c["ink"])
    for i in range(len(tabs)):                                                      # under everything: the hit areas
        m.shape([lay[f"tab_hit{i}"]], c["screen"], f"{n['tab_hit']}{i}")
    for i in range(SUBS):
        m.shape([lay[f"sub_hit{i}"]], c["screen"], f"{n['sub_hit']}{i}")
    for i in range(ROWS):
        m.shape([lay[f"row_hit{i}"]], c["screen"], f"{n['row_hit']}{i}")
    for i in range(ROWS):
        m.shape([lay[f"bar{i}"]], c["ink"], f"{n['bar']}{i}")
    for i in range(len(tabs)):
        m.shape(lay[f"mark{i}"], c["ink"], f"{n['mark']}{i}")
    m.shape(lay["more_up"], c["ink"], n["more_up"])
    m.shape(lay["more_down"], c["ink"], n["more_down"])
    m.field(lay["title"], TITLE_PX, c["dim"], kit["title"], n["title"], font_id)
    m.field(lay["header"], TITLE_PX, c["dim"], "", n["header"], font_id)
    for i, tab in enumerate(tabs):
        m.field(lay[f"tab{i}"], TAB_PX, c["ink"], tab, f"{n['tab']}{i}", font_id)
    for i in range(SUBS):
        m.field(lay[f"sub{i}"], TEXT_PX, c["dim"], "", f"{n['sub_dim']}{i}", font_id)
        m.field(lay[f"sub{i}"], TEXT_PX, c["ink"], "", f"{n['sub']}{i}", font_id)
    for i in range(ROWS):
        m.field(lay[f"row_name{i}"], TEXT_PX, c["ink"], "", f"{n['row_name']}{i}", font_id)
        m.field(lay[f"row_value{i}"], TEXT_PX, c["ink"], "", f"{n['row_value']}{i}", font_id)
        m.field(lay[f"row_name{i}"], TEXT_PX, c["screen"], "", f"{n['row_name_sel']}{i}", font_id)
        m.field(lay[f"row_value{i}"], TEXT_PX, c["screen"], "", f"{n['row_value_sel']}{i}", font_id)
    for i in range(ROWS):
        m.field(lay[f"info_label{i}"], TEXT_PX, c["dim"], "", f"{n['info_label']}{i}", font_id)
        m.field(lay[f"info_value{i}"], TEXT_PX, c["ink"], "", f"{n['info_value']}{i}", font_id)
    for i in range(FOOTER):
        m.field(lay[f"foot{i}"], TEXT_PX, c["ink"], "", f"{n['foot']}{i}", font_id)
    m.field(lay["hints"], HINT_PX, c["ink"], "WAITING FOR THE PLUGIN", n["hints"], font_id)
    m.field(lay["kit_id"], ID_PX, c["screen"], signature(kit), n["kit_id"], font_id)
    close_rect = m.define(lambda i: swf.define_shape3(i, [lay["close"]], c["ink"]))
    close_label = m.define(lambda i: swf.define_shape3(i, swf.label_squares("CLOSE", lay["close"]), c["screen"]))
    close = m.define(lambda i: swf.define_sprite(i, [swf.place_object2(close_rect, 1), swf.place_object2(close_label, 2)]))
    m.place(close, n["close"])
    W, H = STAGE[0] * TWIPS, STAGE[1] * TWIPS
    body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
    body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
    body += b"".join(m.defs) + b"".join(m.places) + swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
    length = 8 + len(body)
    if compressed:
        return b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", length) + zlib.compress(body, 9)
    return b"FWS" + bytes([swf.VERSION]) + struct.pack("<I", length) + body


def kit_names(kit):
    """Every instance name the movie places, in depth order: what the plugin finds by name."""
    n, tabs = NAMES, tabs_of(kit)
    out = [f"{n['tab_hit']}{i}" for i in range(len(tabs))] + [f"{n['sub_hit']}{i}" for i in range(SUBS)]
    out += [f"{n['row_hit']}{i}" for i in range(ROWS)] + [f"{n['bar']}{i}" for i in range(ROWS)]
    out += [f"{n['mark']}{i}" for i in range(len(tabs))] + [n["more_up"], n["more_down"], n["title"], n["header"]]
    out += [f"{n['tab']}{i}" for i in range(len(tabs))]
    for i in range(SUBS):
        out += [f"{n['sub_dim']}{i}", f"{n['sub']}{i}"]
    for i in range(ROWS):
        out += [f"{n['row_name']}{i}", f"{n['row_value']}{i}", f"{n['row_name_sel']}{i}", f"{n['row_value_sel']}{i}"]
    for i in range(ROWS):
        out += [f"{n['info_label']}{i}", f"{n['info_value']}{i}"]
    out += [f"{n['foot']}{i}" for i in range(FOOTER)] + [n["hints"], n["kit_id"], n["close"]]
    return out


def write_movie(path, ini=INI, color=PIPBOY_GREEN, compressed=True):
    data = kit_movie_bytes(read_kit(ini), color=color, compressed=compressed)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="the movie to write (its folder is created)")
    ap.add_argument("--check", action="store_true", help="check the pages and print them as JSON instead")
    ap.add_argument("--ini", default=INI, help="the plugin's ini with the [Kit] and [Page ...] sections")
    ap.add_argument("--color", default=f"{PIPBOY_GREEN:06X}", help="the phosphor colour, RRGGBB (the one setting)")
    ap.add_argument("--uncompressed", action="store_true", help="FWS instead of CWS")
    a = ap.parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", a.color):
            raise KitError(f"--color {a.color!r} is not RRGGBB")
        if a.check:
            kit = read_kit(a.ini)
            print(json.dumps({"signature": signature(kit), "tabs": tabs_of(kit), "pages": kit["pages"]}, indent=1))
            return 0
        if not a.out:
            ap.error("--out or --check is needed")
        data = write_movie(a.out, a.ini, int(a.color, 16), not a.uncompressed)
    except (KitError, swf.SwfError, OSError, UnicodeDecodeError) as e:
        print(f"make_pipboy_kit: {e}", file=sys.stderr)
        return 1
    print(f"wrote {a.out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
