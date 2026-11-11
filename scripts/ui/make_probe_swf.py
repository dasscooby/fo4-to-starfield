"""The Pip-Boy probe's stage (b) movie (FAL-187; sfse/FO4SFPipboyMenu/README.md): one filled rectangle and a text label
drawn as dot-matrix blocks, written as a SWF from pure Python (no Flash tool, no font, no ActionScript).

usage: python scripts/ui/make_probe_swf.py --out <file.swf> [--label TEXT | --no-label] [--color RRGGBB]
                                           [--ink RRGGBB] [--width 1920] [--height 1080] [--uncompressed]
                                           [--channel | --page]
       python scripts/ui/make_probe_swf.py --read <file.swf>         the header and every tag, as JSON

The movie, in the shape Starfield's own menu movies have (compressed "CWS", SWF version 12, the ActionScript 3 flag in
FileAttributes; the PC's look at them with JPEXS, 10 Nov 2026), with nothing that needs code or a font:
  FileAttributes (69)  ActionScript 3, nothing else; no code follows, so the root is a plain MovieClip
  DefineShape3 (32)    id 1: the rectangle, one solid RGBA fill, centred, 60 % x 50 % of the stage
  DefineShape3 (32)    id 2: the label, one square per lit pixel of a 5 x 7 font (squares never touch: no shared edges)
  PlaceObject2 (26)    id 1 at depth 1, id 2 at depth 2, identity matrices
  ShowFrame (1), End (0)
--channel (FAL-216, the plugin's Stage=3) adds, before the placements, DefineFont3 (id 3: the same 5 x 7 table as
glyphs), DefineEditText (id 4: one read-only line in that font) and DefineSprite (id 7: a dark button with the label
CLICK, shapes 5 and 6), placed by name as "fo4sfPosition" (depth 3) and "fo4sfButton" (depth 4); still no code.
Without --channel the bytes are exactly stage (b)'s. --page (FAL-272, the plugin's Stage=4) is the STAT page instead:
a panel of 70 % x 76 % of the stage, DefineFont3 (id 3: the table plus PAGE_GLYPHS), a title, the tab line
"fo4sfTab", seven lines "fo4sfLine0" to "fo4sfLine6", a hint, and two buttons "fo4sfTabButton" (NEXT TAB) and
"fo4sfCloseButton" (CLOSE), each a sprite of the CLICK button's size; no label shape, still no code. No
SetBackgroundColor: a menu movie draws over the game. Every shape's path is drawn clockwise on screen (y down) with its
fill on the right of each edge (FillStyle1), the side its inside is on; the glyphs are drawn anticlockwise with
FillStyle0. Output is deterministic: the same arguments give the same bytes (no time, no random). The file goes where
--out says; nothing is written into the repo.
"""
import argparse
import json
import os
import struct
import sys
import zlib

TWIPS = 20
VERSION = 12
FRAME_RATE = 30
FILE_ATTRIBUTES, DEFINE_SHAPE3, PLACE_OBJECT2, SHOW_FRAME, END = 69, 32, 26, 1, 0
TAG_NAMES = {FILE_ATTRIBUTES: "FileAttributes", DEFINE_SHAPE3: "DefineShape3", PLACE_OBJECT2: "PlaceObject2",
             SHOW_FRAME: "ShowFrame", END: "End"}
AS3 = 0x08                       # FileAttributes, first byte: the ActionScript3 bit
RECT_ID, LABEL_ID = 1, 2
PIPBOY_GREEN = 0x1AFF80          # the rectangle; Fallout 4's default Pip-Boy colour
INK = 0x06200F                   # the label, dark on the green
LABEL = "FO4SF PIP-BOY PROBE"
DOT = 0.8                        # a lit pixel's square, as a share of its cell (the rest is the gap between squares)

# 5 x 7 font: seven rows per glyph, five bits per row, the leftmost pixel in bit 4
FONT = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00), "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C), ":": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    "/": (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x00),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E), "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F), "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02), "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E), "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E), "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11), "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E), "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F), "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F), "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E), "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11), "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11), "N": (0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D), "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E), "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A), "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04), "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
}


class SwfError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ bits
class Bits:
    """MSB-first bit writer, as SWF packs RECT, MATRIX and shape records."""

    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def ub(self, value, nbits):
        if value < 0 or value >= 1 << nbits:
            raise SwfError(f"{value} does not fit UB[{nbits}]")
        for i in range(nbits - 1, -1, -1):
            self.acc = (self.acc << 1) | ((value >> i) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc)
                self.acc = self.n = 0

    def sb(self, value, nbits):
        if not -(1 << (nbits - 1)) <= value < 1 << (nbits - 1):
            raise SwfError(f"{value} does not fit SB[{nbits}]")
        self.ub(value & ((1 << nbits) - 1), nbits)

    def align(self):
        if self.n:
            self.out.append(self.acc << (8 - self.n))
            self.acc = self.n = 0
        return bytes(self.out)


def sb_bits(*values):
    """The fewest bits that hold every value as SB."""
    return max(1, *((v.bit_length() if v >= 0 else (~v).bit_length()) + 1 for v in values))


class BitReader:
    def __init__(self, data, pos=0):
        self.data, self.pos, self.bit = data, pos, 0

    def ub(self, nbits):
        v = 0
        for _ in range(nbits):
            if self.pos >= len(self.data):
                raise SwfError("bit read past the end")
            v = (v << 1) | ((self.data[self.pos] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit, self.pos = 0, self.pos + 1
        return v

    def sb(self, nbits):
        v = self.ub(nbits)
        return v - (1 << nbits) if nbits and v >> (nbits - 1) else v

    def align(self):
        if self.bit:
            self.bit, self.pos = 0, self.pos + 1
        return self.pos


def rect(xmin, xmax, ymin, ymax):
    n = sb_bits(xmin, xmax, ymin, ymax)
    b = Bits()
    b.ub(n, 5)
    for v in (xmin, xmax, ymin, ymax):
        b.sb(v, n)
    return b.align()


def read_rect(r):
    n = r.ub(5)
    return tuple(r.sb(n) for _ in range(4))


def tag(code, body=b""):
    if len(body) < 0x3F:
        return struct.pack("<H", code << 6 | len(body)) + body
    return struct.pack("<HI", code << 6 | 0x3F, len(body)) + body


# ------------------------------------------------------------------------------------------------ shapes
def define_shape3(shape_id, squares, rgb):
    """DefineShape3 of axis-aligned squares/rectangles (x, y, w, h in twips), one solid opaque fill, each a closed
    clockwise path (screen, y down) with the fill on its right (FillStyle1)."""
    if not squares:
        raise SwfError(f"shape {shape_id} has nothing to draw")
    xmin = min(x for x, _, _, _ in squares)
    xmax = max(x + w for x, _, w, _ in squares)
    ymin = min(y for _, y, _, _ in squares)
    ymax = max(y + h for _, y, _, h in squares)
    body = struct.pack("<H", shape_id) + rect(xmin, xmax, ymin, ymax)
    body += bytes([1, 0x00, (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, 0xFF])   # one solid fill, RGBA
    body += bytes([0])                                                                  # no line styles
    return tag(DEFINE_SHAPE3, body + square_records(squares, f"shape {shape_id}"))


def square_records(squares, what, glyph=False):
    """NumFillBits 1, NumLineBits 0 and one closed path per square. A shape's squares are clockwise on screen (y down)
    with the fill on their right (FillStyle1); a glyph's (glyph=True) are anticlockwise with the fill on their left
    (FillStyle0), the style the SWF specification requires of DefineFont3 glyphs. An empty list is a glyph with no
    outline (space)."""
    b = Bits()
    b.ub(1, 4)                                                                          # NumFillBits
    b.ub(0, 4)                                                                          # NumLineBits
    first = True
    for x, y, w, h in squares:
        if w <= 0 or h <= 0:
            raise SwfError(f"{what}: empty square {(x, y, w, h)}")
        # StyleChangeRecord: TypeFlag 0, NewStyles 0, LineStyle 0, FillStyle1, FillStyle0 (first path only), MoveTo 1
        b.ub(0, 1)
        b.ub(0, 1)
        b.ub(0, 1)
        b.ub(1 if first and not glyph else 0, 1)
        b.ub(1 if first and glyph else 0, 1)
        b.ub(1, 1)
        n = sb_bits(x, y)
        b.ub(n, 5)
        b.sb(x, n)                                                                      # MoveTo is absolute
        b.sb(y, n)
        if first:
            b.ub(1, 1)                                                                  # FillStyle1 or 0 = fill 1
            first = False
        # a shape: right, down, left, up; a glyph: down, right, up, left
        edges = ((True, h), (False, w), (True, -h), (False, -w)) if glyph else \
                ((False, w), (True, h), (False, -w), (True, -h))
        for vertical, delta in edges:
            nb = sb_bits(delta)
            nb = max(nb, 2)
            b.ub(1, 1)                                                                  # TypeFlag: edge
            b.ub(1, 1)                                                                  # StraightFlag
            b.ub(nb - 2, 4)
            b.ub(0, 1)                                                                  # GeneralLineFlag 0
            b.ub(1 if vertical else 0, 1)                                               # VertLineFlag
            b.sb(delta, nb)
    b.ub(0, 1)                                                                          # EndShapeRecord
    b.ub(0, 5)
    return b.align()


def place_object2(char_id, depth):
    # flags: HasMatrix (0x04) | HasCharacter (0x02); the MATRIX is identity: no scale, no rotate, 0-bit translate
    return tag(PLACE_OBJECT2, bytes([0x06]) + struct.pack("<HH", depth, char_id) + bytes([0x00]))


def label_squares(text, box):
    """One square per lit pixel of `text` in the 5 x 7 font, centred in box (x, y, w, h, twips): the text's cell is
    the largest whole twip size that fits 85 % of the box's width and 30 % of its height."""
    unknown = sorted({c for c in text if c not in FONT})
    if unknown:
        raise SwfError(f"label has characters the font lacks: {unknown} (A-Z, 0-9, space and - . : /)")
    bx, by, bw, bh = box
    cols = len(text) * 6 - 1                                                           # 5 columns + 1 gap per glyph
    cell = min(int(bw * 0.85) // cols, int(bh * 0.30) // 7)
    if cell < 5:
        raise SwfError("label too long for the rectangle")
    dot = max(1, int(round(cell * DOT)))
    x0 = bx + (bw - cols * cell) // 2
    y0 = by + (bh - 7 * cell) // 2
    out = []
    for i, ch in enumerate(text):
        for row, bits in enumerate(FONT[ch]):
            for col in range(5):
                if bits >> (4 - col) & 1:
                    out.append((x0 + (i * 6 + col) * cell, y0 + row * cell, dot, dot))
    return out


# ------------------------------------------------------------------------------------------------ the data channel
# --channel (FAL-216): the movie FO4SFPipboyMenu's Stage=3 talks to. Two named children of the root, which the plugin
# finds with getChildByName: a text field it writes (the player's position) and a sprite whose click it hears (the
# plugin adds the listener itself, so the movie still carries no code). The field's font is embedded, built from the
# same 5 x 7 table, so its text shows without any of the game's fonts.
FONT_ID, FIELD_ID, BUTTON_RECT_ID, BUTTON_LABEL_ID, BUTTON_ID = 3, 4, 5, 6, 7
FIELD_NAME, BUTTON_NAME = "fo4sfPosition", "fo4sfButton"
FIELD_TEXT = "POSITION: WAITING"
FONT_NAME = "FO4SFDot"
BUTTON_LABEL = "CLICK"
EM = 1024 * 20                   # DefineFont3 glyph units: the 1024 em square at 20 units each
PX = EM // 8                     # one font pixel: seven rows above the baseline, one below
FIELD_PX = 32                    # the field's font height (one em) in screen pixels
DEFINE_EDIT_TEXT, DEFINE_SPRITE, DEFINE_FONT3 = 37, 39, 75
TAG_NAMES.update({DEFINE_EDIT_TEXT: "DefineEditText", DEFINE_SPRITE: "DefineSprite", DEFINE_FONT3: "DefineFont3"})


def glyph_squares(ch, table=FONT):
    """The lit pixels of one character as squares in em units; the baseline is y 0 and the rows are above it."""
    dot = int(round(PX * DOT))
    return [(col * PX, (row - 7) * PX, dot, dot)
            for row, bits in enumerate(table[ch]) for col in range(5) if bits >> (4 - col) & 1]


def define_font3(font_id=FONT_ID, table=FONT):
    """DefineFont3 of every character in `table` (FONT unless the page's), with layout: advance six pixels, ascent
    seven, descent one, no kerning. Wide offsets, and wide codes (DefineFont3 always has them); the code table is in
    ascending order."""
    chars = sorted(table)
    shapes = [square_records(glyph_squares(c, table), f"glyph {c!r}", glyph=True) for c in chars]
    offsets, at = [], 4 * (len(chars) + 1)                                             # from the offset table's start
    for s in shapes:
        offsets.append(at)
        at += len(s)
    name = FONT_NAME.encode("ascii")
    body = struct.pack("<HBBB", font_id, 0x80 | 0x08 | 0x04, 0, len(name)) + name      # HasLayout WideOffsets WideCodes
    body += struct.pack("<H", len(chars)) + b"".join(struct.pack("<I", o) for o in offsets) + struct.pack("<I", at)
    body += b"".join(shapes) + b"".join(struct.pack("<H", ord(c)) for c in chars)
    body += struct.pack("<hhh", 7 * PX, PX, 0)                                          # ascent, descent, leading
    body += b"".join(struct.pack("<h", 6 * PX) for _ in chars)
    for c in chars:
        sq = glyph_squares(c, table)
        body += rect(min((x for x, _, _, _ in sq), default=0), max((x + w for x, _, w, _ in sq), default=0),
                     min((y for _, y, _, _ in sq), default=0), max((y + h for _, y, _, h in sq), default=0))
    return tag(DEFINE_FONT3, body + struct.pack("<H", 0))                               # KerningCount 0


def define_edit_text(field_id, box, font_id, height, rgb, text):
    """DefineEditText: one line, read-only, not selectable, the embedded font (UseOutlines), the given colour and
    initial text; no variable name (an ActionScript 2 feature)."""
    x, y, w, h = box
    body = struct.pack("<H", field_id) + rect(x, x + w, y, y + h)
    # HasText, ReadOnly, HasTextColor, HasFont; NoSelect, UseOutlines
    body += bytes([0x80 | 0x08 | 0x04 | 0x01, 0x10 | 0x01])
    body += struct.pack("<HH", font_id, height)
    body += bytes([(rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, 0xFF])
    body += b"\x00" + text.encode("ascii") + b"\x00"                                    # VariableName "", InitialText
    return tag(DEFINE_EDIT_TEXT, body)


def define_sprite(sprite_id, control_tags):
    return tag(DEFINE_SPRITE, struct.pack("<HH", sprite_id, 1) + b"".join(control_tags) + tag(SHOW_FRAME) + tag(END))


def place_named(char_id, depth, name):
    # flags: HasName (0x20) | HasMatrix (0x04) | HasCharacter (0x02); the MATRIX is identity; then the instance name
    return tag(PLACE_OBJECT2, bytes([0x26]) + struct.pack("<HH", depth, char_id) + bytes([0x00]) +
               name.encode("ascii") + b"\x00")


def channel_tags(box, color, ink):
    """The definitions and the two named placements of the data channel inside the rectangle `box` (twips): the
    field along its top edge, the button centred above its bottom edge (clear of a centred label)."""
    bx, by, bw, bh = box
    pad = 24 * TWIPS
    field = (bx + pad, by + pad, bw - 2 * pad, FIELD_PX * TWIPS * 3 // 2)
    button = (bx + (bw - 360 * TWIPS) // 2, by + bh - pad - 90 * TWIPS, 360 * TWIPS, 90 * TWIPS)
    defs = define_font3() + define_edit_text(FIELD_ID, field, FONT_ID, FIELD_PX * TWIPS, ink, FIELD_TEXT)
    defs += define_shape3(BUTTON_RECT_ID, [button], ink)
    defs += define_shape3(BUTTON_LABEL_ID, label_squares(BUTTON_LABEL, button), color)
    defs += define_sprite(BUTTON_ID, [place_object2(BUTTON_RECT_ID, 1), place_object2(BUTTON_LABEL_ID, 2)])
    return defs, [place_named(FIELD_ID, 3, FIELD_NAME), place_named(BUTTON_ID, 4, BUTTON_NAME)]


# ------------------------------------------------------------------------------------------------ the STAT page
# --page (FAL-272): the first page the owner uses by hand, the movie FO4SFPipboyMenu's Stage=4 fills. A larger panel
# with a title, a tab line and PAGE_LINES lines the plugin writes twice a second, a hint, and two buttons whose clicks
# the plugin hears: NEXT TAB shows the other set of lines, CLOSE closes the menu. Every field uses one embedded font,
# the 5 x 7 table plus PAGE_GLYPHS (so the names of places print); the plugin writes only these characters, upper
# case. Still no code: the plugin finds each child by its instance name, as on the channel movie.
PAGE_GLYPHS = {
    "'": (0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00), ",": (0x00, 0x00, 0x00, 0x00, 0x0C, 0x04, 0x08),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02), ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04), "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00), "%": (0x18, 0x19, 0x02, 0x04, 0x08, 0x13, 0x03),
    "&": (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D), "_": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F),
    "#": (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A), "=": (0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00),
}
PAGE_FONT = {**FONT, **PAGE_GLYPHS}
PAGE_LINES = 7
PAGE_TITLE = "FO4SF PIP-BOY  STAT"
PAGE_TAB_TEXT = "TAB: WAITING FOR THE PLUGIN"
PAGE_LINE_TEXT = "-"
PAGE_HINT = "F10 OPENS AND CLOSES THIS PAGE"
TAB_FIELD, LINE_FIELD = "fo4sfTab", "fo4sfLine"                # the lines are fo4sfLine0 ... fo4sfLine6
TAB_BUTTON, CLOSE_BUTTON = "fo4sfTabButton", "fo4sfCloseButton"
TAB_LABEL, CLOSE_LABEL = "NEXT TAB", "CLOSE"
PAGE_ROW = FIELD_PX * 3 // 2                                    # a line's height in pixels (the field's, 1.5 em)
PAGE_PAD = 24
PAGE_BUTTON = (360, 90)                                         # the CLICK button's size, hit at 0x9 on the PC
PAGE_TITLE_ID, PAGE_TAB_ID, PAGE_LINE0_ID = 4, 5, 6
PAGE_HINT_ID = PAGE_LINE0_ID + PAGE_LINES
TAB_RECT_ID, TAB_LABEL_ID, TAB_BUTTON_ID = PAGE_HINT_ID + 1, PAGE_HINT_ID + 2, PAGE_HINT_ID + 3
CLOSE_RECT_ID, CLOSE_LABEL_ID, CLOSE_BUTTON_ID = PAGE_HINT_ID + 4, PAGE_HINT_ID + 5, PAGE_HINT_ID + 6


def page_box(W, H):
    """The page's panel in twips: 70 % x 76 % of the stage, centred."""
    return (W - W * 7 // 10) // 2, (H - H * 19 // 25) // 2, W * 7 // 10, H * 19 // 25


def page_columns(width=1920):
    """How many characters one of the page's lines holds at that stage width (54 at 1920)."""
    return (page_box(width * TWIPS, 0)[2] - 2 * PAGE_PAD * TWIPS) // (6 * FIELD_PX * TWIPS // 8)


def page_tags(box, color, ink):
    """The page's definitions and named placements inside the panel `box` (twips), from the top: the title, the tab
    line, PAGE_LINES lines, then above the bottom edge the hint and the two buttons side by side."""
    bx, by, bw, bh = box
    pad, row = PAGE_PAD * TWIPS, PAGE_ROW * TWIPS
    bw_, bh_ = PAGE_BUTTON[0] * TWIPS, PAGE_BUTTON[1] * TWIPS

    def field(y):
        return bx + pad, y, bw - 2 * pad, row

    title_y = by + pad
    tab_y = title_y + row + 8 * TWIPS
    line_y = tab_y + row + 16 * TWIPS
    button_y = by + bh - pad - bh_
    hint_y = button_y - 16 * TWIPS - row
    if line_y + PAGE_LINES * row > hint_y:
        raise SwfError("the page's lines do not fit above its buttons")
    tab_button = (bx + bw // 2 - 40 * TWIPS - bw_, button_y, bw_, bh_)
    close_button = (bx + bw // 2 + 40 * TWIPS, button_y, bw_, bh_)
    height = FIELD_PX * TWIPS
    defs = define_font3(FONT_ID, PAGE_FONT)
    defs += define_edit_text(PAGE_TITLE_ID, field(title_y), FONT_ID, height, ink, PAGE_TITLE)
    defs += define_edit_text(PAGE_TAB_ID, field(tab_y), FONT_ID, height, ink, PAGE_TAB_TEXT)
    for i in range(PAGE_LINES):
        defs += define_edit_text(PAGE_LINE0_ID + i, field(line_y + i * row), FONT_ID, height, ink, PAGE_LINE_TEXT)
    defs += define_edit_text(PAGE_HINT_ID, field(hint_y), FONT_ID, height, ink, PAGE_HINT)
    buttons = (((TAB_RECT_ID, TAB_LABEL_ID, TAB_BUTTON_ID), TAB_LABEL, tab_button),
               ((CLOSE_RECT_ID, CLOSE_LABEL_ID, CLOSE_BUTTON_ID), CLOSE_LABEL, close_button))
    for (rect_id, label_id, sprite_id), label, box_ in buttons:
        defs += define_shape3(rect_id, [box_], ink)
        defs += define_shape3(label_id, label_squares(label, box_), color)
        defs += define_sprite(sprite_id, [place_object2(rect_id, 1), place_object2(label_id, 2)])
    places = [place_object2(PAGE_TITLE_ID, 2), place_named(PAGE_TAB_ID, 3, TAB_FIELD)]
    places += [place_named(PAGE_LINE0_ID + i, 4 + i, f"{LINE_FIELD}{i}") for i in range(PAGE_LINES)]
    places += [place_object2(PAGE_HINT_ID, 4 + PAGE_LINES), place_named(TAB_BUTTON_ID, 5 + PAGE_LINES, TAB_BUTTON),
               place_named(CLOSE_BUTTON_ID, 6 + PAGE_LINES, CLOSE_BUTTON)]
    return defs, places


def movie_bytes(width=1920, height=1080, color=PIPBOY_GREEN, ink=INK, label=LABEL, compressed=True, channel=False,
                page=False):
    """The whole movie. width/height in pixels; label None or "" for the rectangle alone; channel adds the data
    channel's field and button (FAL-216). Without channel the bytes are stage (b)'s. page is the STAT page (FAL-272)
    instead: its own panel, title and fields, no label shape."""
    if width <= 0 or height <= 0:
        raise SwfError("the stage needs a positive size")
    if channel and page:
        raise SwfError("--channel and --page are two different movies")
    W, H = width * TWIPS, height * TWIPS
    box = page_box(W, H) if page else ((W - W * 3 // 5) // 2, (H - H // 2) // 2, W * 3 // 5, H // 2)
    body = rect(0, W, 0, H) + struct.pack("<HH", FRAME_RATE << 8, 1)
    body += tag(FILE_ATTRIBUTES, bytes([AS3, 0, 0, 0]))
    body += define_shape3(RECT_ID, [box], color)
    tags = [place_object2(RECT_ID, 1)]
    if label and not page:
        body += define_shape3(LABEL_ID, label_squares(label, box), ink)
        tags.append(place_object2(LABEL_ID, 2))
    if channel or page:
        defs, places = page_tags(box, color, ink) if page else channel_tags(box, color, ink)
        body += defs
        tags += places
    body += b"".join(tags) + tag(SHOW_FRAME) + tag(END)
    length = 8 + len(body)
    if compressed:
        return b"CWS" + bytes([VERSION]) + struct.pack("<I", length) + zlib.compress(body, 9)
    return b"FWS" + bytes([VERSION]) + struct.pack("<I", length) + body


def write_movie(path, **kw):
    data = movie_bytes(**kw)
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return data


# ------------------------------------------------------------------------------------------------ reading
def read_shape(data):
    """A DefineShape3 body: id, bounds, fills (RGBA) and the paths as point lists, with each path's fill styles."""
    shape_id = struct.unpack_from("<H", data, 0)[0]
    r = BitReader(data, 2)
    bounds = read_rect(r)
    pos = r.align()
    nfill = data[pos]
    pos += 1
    fills = []
    for _ in range(nfill):
        if data[pos] != 0x00:
            raise SwfError(f"shape {shape_id}: fill type {data[pos]:#x}, only solid fills are written")
        fills.append(tuple(data[pos + 1:pos + 5]))
        pos += 5
    nline = data[pos]
    pos += 1
    if nline:
        raise SwfError(f"shape {shape_id}: {nline} line styles, none are written")
    return {"id": shape_id, "bounds": bounds, "fills": fills, "paths": read_records(data, pos, f"shape {shape_id}")[0]}


def read_records(data, pos, what):
    """The shape records at data[pos:] as paths (point lists with their fill styles) and the byte after the end."""
    r = BitReader(data, pos)
    fill_bits, line_bits = r.ub(4), r.ub(4)
    paths, cur, fill0, fill1, x, y = [], None, 0, 0, 0, 0
    while True:
        if r.ub(1) == 0:                                                               # style change or end
            flags = r.ub(5)
            if flags == 0:
                break
            if flags & 0x10:
                raise SwfError(f"{what}: new styles are never written")
            if flags & 0x01:                                                           # MoveTo
                n = r.ub(5)
                x, y = r.sb(n), r.sb(n)
            if flags & 0x02:
                fill0 = r.ub(fill_bits)
            if flags & 0x04:
                fill1 = r.ub(fill_bits)
            if flags & 0x08:
                r.ub(line_bits)
            cur = {"points": [(x, y)], "fill0": fill0, "fill1": fill1}
            paths.append(cur)
            continue
        if r.ub(1) == 0:
            raise SwfError(f"{what}: curved edges are never written")
        n = r.ub(4) + 2
        if r.ub(1):                                                                    # general line
            x, y = x + r.sb(n), y + r.sb(n)
        elif r.ub(1):
            y += r.sb(n)
        else:
            x += r.sb(n)
        if cur is None:
            raise SwfError(f"{what}: an edge before any MoveTo")
        cur["points"].append((x, y))
    return paths, r.align()


def read_movie(path_or_bytes):
    """The header and the tags of a movie this module writes (or any SWF; unknown tags are listed by code only)."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        raw = bytes(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as f:
            raw = f.read()
    if len(raw) < 8 or raw[:3] not in (b"CWS", b"FWS"):
        raise SwfError("not a SWF (signature is not CWS or FWS)")
    sig, version, length = raw[:3].decode(), raw[3], struct.unpack_from("<I", raw, 4)[0]
    body = zlib.decompress(raw[8:]) if sig == "CWS" else raw[8:]
    if 8 + len(body) != length:
        raise SwfError(f"FileLength {length} but the body is {len(body)} bytes + 8")
    r = BitReader(body)
    frame = read_rect(r)
    pos = r.align()
    rate, count = struct.unpack_from("<HH", body, pos)
    pos += 4
    tags, pos = read_tags(body, pos)
    if pos != len(body):
        raise SwfError(f"{len(body) - pos} bytes after the End tag")
    return {"signature": sig, "version": version, "file_length": length, "frame": frame,
            "frame_rate": rate / 256, "frame_count": count, "tags": tags}


def read_tags(body, pos):
    """The tags from body[pos:] up to and including End (a sprite's own list too) and the byte after End."""
    tags = []
    while pos < len(body):
        code_len = struct.unpack_from("<H", body, pos)[0]
        code, n = code_len >> 6, code_len & 0x3F
        pos += 2
        if n == 0x3F:
            n = struct.unpack_from("<I", body, pos)[0]
            pos += 4
        data = body[pos:pos + n]
        if len(data) != n:
            raise SwfError(f"tag {code} runs past the end")
        pos += n
        t = {"code": code, "name": TAG_NAMES.get(code, f"tag{code}"), "length": n}
        if code == FILE_ATTRIBUTES:
            t["actionscript3"] = bool(data[0] & AS3)
            t["flags"] = data.hex()
        elif code == DEFINE_SHAPE3:
            t.update(read_shape(data))
        elif code == PLACE_OBJECT2:
            t.update(read_place(data))
        elif code == DEFINE_SPRITE:
            t["id"], t["frame_count"] = struct.unpack_from("<HH", data, 0)
            t["tags"], end = read_tags(data, 4)
            if end != len(data):
                raise SwfError(f"sprite {t['id']}: {len(data) - end} bytes after its End tag")
        elif code == DEFINE_EDIT_TEXT:
            t.update(read_edit_text(data))
        elif code == DEFINE_FONT3:
            t.update(read_font3(data))
        tags.append(t)
        if code == END:
            break
    return tags, pos


def read_cstring(data, pos, what):
    end = data.find(b"\x00", pos)
    if end < 0:
        raise SwfError(f"{what}: string without its terminating zero")
    return data[pos:end].decode("latin-1"), end + 1


def read_place(data):
    """PlaceObject2: flags, depth, character and, when no colour transform or ratio comes before it, the instance
    name."""
    flags = data[0]
    t = {"flags": flags, "depth": struct.unpack_from("<H", data, 1)[0]}
    pos = 3
    if flags & 0x02:
        t["character"] = struct.unpack_from("<H", data, pos)[0]
        pos += 2
    if flags & 0x20 and not flags & 0x18:
        if flags & 0x04:                                                               # MATRIX
            r = BitReader(data, pos)
            for _ in range(2):                                                         # scale, rotate
                if r.ub(1):
                    n = r.ub(5)
                    r.sb(n)
                    r.sb(n)
            n = r.ub(5)
            r.sb(n)
            r.sb(n)
            pos = r.align()
        t["instance"] = read_cstring(data, pos, f"placement at depth {t['depth']}")[0]
    return t


def read_edit_text(data):
    """DefineEditText: id, bounds, the two flag bytes, font and height, colour, variable name and initial text."""
    field_id = struct.unpack_from("<H", data, 0)[0]
    r = BitReader(data, 2)
    t = {"id": field_id, "bounds": read_rect(r)}
    pos = r.align()
    f1, f2 = data[pos], data[pos + 1]
    t["flags"] = [f1, f2]
    pos += 2
    if f1 & 0x01:
        t["font"], t["height"] = struct.unpack_from("<HH", data, pos)
        pos += 4
    if f2 & 0x80 or f1 & 0x02 or f2 & 0x20:
        raise SwfError(f"field {field_id}: font class, max length and layout are never written")
    if f1 & 0x04:
        t["color"] = tuple(data[pos:pos + 4])
        pos += 4
    t["variable"], pos = read_cstring(data, pos, f"field {field_id}")
    if f1 & 0x80:
        t["text"], pos = read_cstring(data, pos, f"field {field_id}")
    if pos != len(data):
        raise SwfError(f"field {field_id}: {len(data) - pos} bytes after its text")
    return t


def read_font3(data):
    """DefineFont3 as written here: id, flags, name, the code table, each glyph's paths, advances, ascent, descent."""
    font_id, flags, _lang, name_len = struct.unpack_from("<HBBB", data, 0)
    pos = 5
    name = data[pos:pos + name_len].decode("latin-1")
    pos += name_len
    if flags & 0x0C != 0x0C:
        raise SwfError(f"font {font_id}: wide offsets and wide codes are always written")
    n = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    table = pos
    offsets = struct.unpack_from(f"<{n + 1}I", data, pos)
    glyphs = []
    for i in range(n):
        paths, end = read_records(data, table + offsets[i], f"font {font_id} glyph {i}")
        if end != table + (offsets[i + 1] if i + 1 < n else offsets[n]):
            raise SwfError(f"font {font_id} glyph {i}: its records end at {end}, not at the next offset")
        glyphs.append(paths)
    pos = table + offsets[n]
    codes = struct.unpack_from(f"<{n}H", data, pos)
    pos += 2 * n
    t = {"id": font_id, "font_flags": flags, "font_name": name, "codes": "".join(map(chr, codes)), "glyphs": glyphs}
    if flags & 0x80:
        t["ascent"], t["descent"], t["leading"] = struct.unpack_from("<hhh", data, pos)
        pos += 6
        t["advances"] = list(struct.unpack_from(f"<{n}h", data, pos))
        pos += 2 * n
        bounds = []
        for _ in range(n):
            r = BitReader(data, pos)
            bounds.append(read_rect(r))
            pos = r.align()
        t["glyph_bounds"] = bounds
        t["kerning"] = struct.unpack_from("<H", data, pos)[0]
        pos += 2
    if pos != len(data):
        raise SwfError(f"font {font_id}: {len(data) - pos} bytes after its tables")
    return t


def summary(movie):
    """read_movie() without the point lists, for --read."""
    out = dict(movie)
    out["tags"] = []
    for t in movie["tags"]:
        t = dict(t)
        if "paths" in t:
            t["paths"] = len(t["paths"])
        if "glyphs" in t:
            t["glyphs"] = len(t["glyphs"])
            t.pop("glyph_bounds", None)
            t.pop("advances", None)
        if "tags" in t:
            t["tags"] = summary({"tags": t["tags"]})["tags"]
        out["tags"].append(t)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="the movie to write (its folder is created)")
    ap.add_argument("--read", help="print a movie's header and tags as JSON instead")
    ap.add_argument("--label", default=LABEL, help=f"the text (A-Z, 0-9, space and - . : /; default {LABEL!r})")
    ap.add_argument("--no-label", action="store_true", help="the rectangle alone")
    ap.add_argument("--color", default=f"{PIPBOY_GREEN:06X}", help="the rectangle, RRGGBB")
    ap.add_argument("--ink", default=f"{INK:06X}", help="the label, RRGGBB")
    ap.add_argument("--width", type=int, default=1920, help="the stage in pixels")
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--uncompressed", action="store_true", help="FWS instead of CWS")
    ap.add_argument("--channel", action="store_true",
                    help=f"add the data channel (FAL-216): the field {FIELD_NAME!r} and the button {BUTTON_NAME!r}")
    ap.add_argument("--page", action="store_true",
                    help=f"the STAT page instead (FAL-272): {PAGE_LINES} lines, the buttons {TAB_BUTTON!r} and "
                         f"{CLOSE_BUTTON!r}")
    a = ap.parse_args(argv)
    try:
        if a.read:
            print(json.dumps(summary(read_movie(a.read)), indent=1))
            return 0
        if not a.out:
            ap.error("--out or --read is needed")
        data = write_movie(a.out, width=a.width, height=a.height, color=int(a.color, 16), ink=int(a.ink, 16),
                           label=None if a.no_label else a.label, compressed=not a.uncompressed,
                           channel=a.channel, page=a.page)
    except (SwfError, ValueError, OSError, zlib.error) as e:
        print(f"make_probe_swf: {e}", file=sys.stderr)
        return 1
    print(f"wrote {a.out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
