"""Pictures for the build pieces kit's menu entries (docs/research/build-pieces.md): 128 x 128, drawn here, nothing taken from either game.

The base game's workshop menu shows `textures/interface/workshopicons/<created object's form id, 8 hex>cl.dds` for each buildable
(128 x 128, one mip, DXGI 77 = BC3, read from the game's archives). The program builds a mod item's name with `%s/%08x%s.dds` from
the plugin's file name, the form id masked to the file's own part and a suffix, so the shell at 0x802 of FO4SFBuildPieces.esm is
`Textures/Interface/WorkshopIcons/FO4SFBuildPieces.esm/00000802cl.dds`. (Loose files of that name did not show in one run: the
install has no loose-file setting, so the installer puts them in a texture archive beside the plugin.)

A picture is a plain shape (square, circle, triangle, diamond, by the piece's number) in a colour taken from its name, over a dark
tile with a light frame, and the piece's initials in a 5 x 7 pixel letters of our own below it. BC3 with a DX10 header, written
byte for byte as fo4sf.ba2 regenerates the header of a texture it reads out of an archive. Pure Python, no dependency.
"""
import hashlib
import re
import struct

SIZE = 128
DXGI_BC3 = 77
SUFFIX = "cl"

# 5 x 7 letters and digits, 7 rows of 5 cells each (# = on)
_ROWS = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"), "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"), "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"), "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#..##", "#...#", "#...#", ".###."), "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"), "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"), "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"), "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."), "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"), "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."), "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."), "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"), "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."), "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."), "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"), "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."), "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."), "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."), "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
}
_GLYPH = {c: "".join(rows) for c, rows in _ROWS.items()}
assert all(len(g) == 35 for g in _GLYPH.values())


def label(edid, name=""):
    """Up to three characters to write on a piece's picture: the first letters of the words of its core editor id, else of its name."""
    base = re.sub(r"^FO4Core_", "", edid or "", flags=re.I)
    words = re.findall(r"[A-Z][a-z]+|[a-z]+|[A-Z]+(?![a-z])|\d+", base) or re.findall(r"\w+", name or "") or ["?"]
    nums = [w for w in words if w.isdigit()]
    letters = [w for w in words if not w.isdigit()]
    out = "".join(w[0] for w in letters)[:2].upper()
    if len(letters) == 1 and len(letters[0]) > 1:
        out = letters[0][:2].upper()
    if nums:
        out += nums[-1].lstrip("0")[:1] or nums[-1][-1:]
    return (out or "?")[:3]


def colour(seed):
    """A mid-bright colour from a name (stable)."""
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    return tuple(90 + h[i] % 140 for i in range(3))


def draw(n, edid, name=""):
    """128 x 128 RGBA bytes of piece number n (1-based): a tile, a shape, the label."""
    px = bytearray(SIZE * SIZE * 4)

    def put(x, y, c):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            i = (y * SIZE + x) * 4
            px[i:i + 4] = bytes((c[0], c[1], c[2], 255))

    for y in range(SIZE):
        for x in range(SIZE):
            put(x, y, (34, 38, 46))
    for k in range(4):                                  # light frame
        for t in range(SIZE):
            for xy in ((t, k), (t, SIZE - 1 - k), (k, t), (SIZE - 1 - k, t)):
                put(xy[0], xy[1], (200, 206, 214))
    col = colour(edid or name or str(n))
    cx, cy, r = 64, 46, 30
    kind = (n - 1) % 4
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - cx, y - cy
            if kind == 0:
                on = abs(dx) <= r and abs(dy) <= r                          # square
            elif kind == 1:
                on = dx * dx + dy * dy <= r * r                             # circle
            elif kind == 2:
                on = -r <= dy <= r and abs(dx) <= (dy + r) * 0.5            # triangle
            else:
                on = abs(dx) + abs(dy) <= r + 6                             # diamond
            if on:
                put(x, y, col)
    text = label(edid, name)
    scale = 4
    gap = scale
    width = len(text) * 5 * scale + (len(text) - 1) * gap
    x0, y0 = (SIZE - width) // 2, 92
    for ci, ch in enumerate(text):
        g = _GLYPH.get(ch.upper())
        if g is None:
            continue
        ox = x0 + ci * (5 * scale + gap)
        for row in range(7):
            for colm in range(5):
                if g[row * 5 + colm] == "#":
                    for yy in range(scale):
                        for xx in range(scale):
                            put(ox + colm * scale + xx, y0 + row * scale + yy, (240, 240, 240))
    return bytes(px)


def _565(c):
    return ((c[0] >> 3) << 11) | ((c[1] >> 2) << 5) | (c[2] >> 3)


def _unpack(v):
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def _block(rgba, bx, by):
    """One BC3 block (16 bytes): 8 alpha bytes (opaque here), then the 4-colour block."""
    cols = []
    for y in range(4):
        for x in range(4):
            i = ((by * 4 + y) * SIZE + bx * 4 + x) * 4
            cols.append((rgba[i], rgba[i + 1], rgba[i + 2]))
    lo = min(cols, key=lambda c: c[0] + c[1] + c[2])
    hi = max(cols, key=lambda c: c[0] + c[1] + c[2])
    c0, c1 = _565(hi), _565(lo)
    if c0 < c1:
        c0, c1 = c1, c0
    if c0 == c1:
        idx = 0
    else:
        p0, p1 = _unpack(c0), _unpack(c1)
        pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)), tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
        idx = 0
        for k, c in enumerate(cols):
            best = min(range(4), key=lambda j: sum((c[t] - pal[j][t]) ** 2 for t in range(3)))
            idx |= best << (2 * k)
    if c0 == c1:
        idx = 0
    return bytes((255, 255, 0, 0, 0, 0, 0, 0)) + struct.pack("<HHI", c0, c1, idx)


def bc3(rgba):
    """BC3 data of a 128 x 128 RGBA image (opaque alpha): 1024 blocks of 16 bytes."""
    if len(rgba) != SIZE * SIZE * 4:
        raise ValueError("the picture is 128 x 128 RGBA")
    return b"".join(_block(rgba, bx, by) for by in range(SIZE // 4) for bx in range(SIZE // 4))


def dds_header():
    """DDS + DX10 header of a 128 x 128, one mip, DXGI 77 texture, as fo4sf.ba2 regenerates it."""
    flags = 0x1 | 0x2 | 0x4 | 0x1000
    h = b"DDS " + struct.pack("<7I", 124, flags, SIZE, SIZE, 0, 0, 1) + b"\0" * 44
    h += struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    h += struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    h += struct.pack("<5I", DXGI_BC3, 3, 0, 1, 0)
    return h


def dds(n, edid, name=""):
    """The whole .dds file of piece n."""
    return dds_header() + bc3(draw(n, edid, name))


def icon_path(plugin, form_id, suffix=SUFFIX):
    """Texture path (relative to Data) the program builds for a mod item: Textures/Interface/WorkshopIcons/<plugin>/<%08x><suffix>.dds."""
    return f"Textures/Interface/WorkshopIcons/{plugin}/{form_id & 0xFFFFFF:08x}{suffix}.dds"
