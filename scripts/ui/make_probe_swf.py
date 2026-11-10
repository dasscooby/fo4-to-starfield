"""The Pip-Boy probe's stage (b) movie (FAL-187; sfse/FO4SFPipboyMenu/README.md): one filled rectangle and a text label
drawn as dot-matrix blocks, written as a SWF from pure Python (no Flash tool, no font, no ActionScript).

usage: python scripts/ui/make_probe_swf.py --out <file.swf> [--label TEXT | --no-label] [--color RRGGBB]
                                           [--ink RRGGBB] [--width 1920] [--height 1080] [--uncompressed]
       python scripts/ui/make_probe_swf.py --read <file.swf>         the header and every tag, as JSON

The movie, in the shape Starfield's own menu movies have (compressed "CWS", SWF version 12, the ActionScript 3 flag in
FileAttributes; the PC's look at them with JPEXS, 10 Nov 2026), with nothing that needs code or a font:
  FileAttributes (69)  ActionScript 3, nothing else; no code follows, so the root is a plain MovieClip
  DefineShape3 (32)    id 1: the rectangle, one solid RGBA fill, centred, 60 % x 50 % of the stage
  DefineShape3 (32)    id 2: the label, one square per lit pixel of a 5 x 7 font (squares never touch: no shared edges)
  PlaceObject2 (26)    id 1 at depth 1, id 2 at depth 2, identity matrices
  ShowFrame (1), End (0)
No SetBackgroundColor: a menu movie draws over the game. Every path is drawn clockwise on screen (y down) with its
fill on the right of each edge (FillStyle1), the side its inside is on. Output is deterministic: the same arguments
give the same bytes (no time, no random). The file goes where --out says; nothing is written into the repo.
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
    b = Bits()
    b.ub(1, 4)                                                                          # NumFillBits
    b.ub(0, 4)                                                                          # NumLineBits
    first = True
    for x, y, w, h in squares:
        if w <= 0 or h <= 0:
            raise SwfError(f"shape {shape_id}: empty square {(x, y, w, h)}")
        # StyleChangeRecord: TypeFlag 0, NewStyles 0, LineStyle 0, FillStyle1 (first path only), FillStyle0 0, MoveTo 1
        b.ub(0, 1)
        b.ub(0, 1)
        b.ub(0, 1)
        b.ub(1 if first else 0, 1)
        b.ub(0, 1)
        b.ub(1, 1)
        n = sb_bits(x, y)
        b.ub(n, 5)
        b.sb(x, n)                                                                      # MoveTo is absolute
        b.sb(y, n)
        if first:
            b.ub(1, 1)                                                                  # FillStyle1 = fill 1
            first = False
        for vertical, delta in ((False, w), (True, h), (False, -w), (True, -h)):        # right, down, left, up
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
    return tag(DEFINE_SHAPE3, body + b.align())


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


def movie_bytes(width=1920, height=1080, color=PIPBOY_GREEN, ink=INK, label=LABEL, compressed=True):
    """The whole movie. width/height in pixels; label None or "" for the rectangle alone."""
    if width <= 0 or height <= 0:
        raise SwfError("the stage needs a positive size")
    W, H = width * TWIPS, height * TWIPS
    box = ((W - W * 3 // 5) // 2, (H - H // 2) // 2, W * 3 // 5, H // 2)
    body = rect(0, W, 0, H) + struct.pack("<HH", FRAME_RATE << 8, 1)
    body += tag(FILE_ATTRIBUTES, bytes([AS3, 0, 0, 0]))
    body += define_shape3(RECT_ID, [box], color)
    tags = [place_object2(RECT_ID, 1)]
    if label:
        body += define_shape3(LABEL_ID, label_squares(label, box), ink)
        tags.append(place_object2(LABEL_ID, 2))
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
    r = BitReader(data, pos)
    fill_bits, line_bits = r.ub(4), r.ub(4)
    paths, cur, fill0, fill1, x, y = [], None, 0, 0, 0, 0
    while True:
        if r.ub(1) == 0:                                                               # style change or end
            flags = r.ub(5)
            if flags == 0:
                break
            if flags & 0x10:
                raise SwfError(f"shape {shape_id}: new styles are never written")
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
            raise SwfError(f"shape {shape_id}: curved edges are never written")
        n = r.ub(4) + 2
        if r.ub(1):                                                                    # general line
            x, y = x + r.sb(n), y + r.sb(n)
        elif r.ub(1):
            y += r.sb(n)
        else:
            x += r.sb(n)
        if cur is None:
            raise SwfError(f"shape {shape_id}: an edge before any MoveTo")
        cur["points"].append((x, y))
    return {"id": shape_id, "bounds": bounds, "fills": fills, "paths": paths}


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
            flags = data[0]
            t["flags"] = flags
            t["depth"] = struct.unpack_from("<H", data, 1)[0]
            if flags & 0x02:
                t["character"] = struct.unpack_from("<H", data, 3)[0]
        tags.append(t)
        if code == END:
            break
    if pos != len(body):
        raise SwfError(f"{len(body) - pos} bytes after the End tag")
    return {"signature": sig, "version": version, "file_length": length, "frame": frame,
            "frame_rate": rate / 256, "frame_count": count, "tags": tags}


def summary(movie):
    """read_movie() without the point lists, for --read."""
    out = dict(movie)
    out["tags"] = []
    for t in movie["tags"]:
        t = dict(t)
        if "paths" in t:
            t["paths"] = len(t["paths"])
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
    a = ap.parse_args(argv)
    try:
        if a.read:
            print(json.dumps(summary(read_movie(a.read)), indent=1))
            return 0
        if not a.out:
            ap.error("--out or --read is needed")
        data = write_movie(a.out, width=a.width, height=a.height, color=int(a.color, 16), ink=int(a.ink, 16),
                           label=None if a.no_label else a.label, compressed=not a.uncompressed)
    except (SwfError, ValueError, OSError, zlib.error) as e:
        print(f"make_probe_swf: {e}", file=sys.stderr)
        return 1
    print(f"wrote {a.out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
