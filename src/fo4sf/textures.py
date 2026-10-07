"""Texture conversion helpers: Fallout 4 DDS (spec/gloss) -> Starfield DDS (color / normal / rough).

Needs numpy. Final block compression is done by Microsoft's `texconv` (ships with xEdit in `Edit Scripts/`).

Formats (measured on vanilla files, see docs/spikes/S3-materials.md):
  Fallout 4  _d  DXT5 / BC1 colour, sRGB      _n  BC5 (fourCC "BC5U" / ATI2) RG tangent-space normal
             _s  BC5 (fourCC "BC5U"): R = specular strength, G = smoothness (gloss)
  Starfield  _color  BC1_SRGB (BC7_SRGB with alpha)   _normal  BC5_SNORM   _rough  BC4_UNORM (1.0 = fully rough)
"""
import struct
import subprocess

import numpy as np

DDS_MAGIC = b"DDS "
DXGI_R8_UNORM = 61
DXGI_R8G8_SNORM = 51
DXGI_R8G8B8A8_UNORM = 28


class DdsError(ValueError):
    pass


def read_dds_header(data: bytes):
    if data[:4] != DDS_MAGIC:
        raise DdsError("not a DDS file")
    height, width = struct.unpack_from("<II", data, 12)
    mips, = struct.unpack_from("<I", data, 28)
    four = data[84:88]
    dxgi, offset = None, 128
    if four == b"DX10":
        dxgi, = struct.unpack_from("<I", data, 128)
        offset = 148
    return {"width": width, "height": height, "mips": max(mips, 1), "fourcc": four, "dxgi": dxgi, "data_offset": offset}


# ---- block decoders (mip 0 only) ---------------------------------------------------------

def _bc4_block_values(blocks):
    """blocks: (N, 8) uint8 -> (N, 16) uint8 values (BC4 / BC5 single-channel unorm)."""
    a0 = blocks[:, 0].astype(np.float32)
    a1 = blocks[:, 1].astype(np.float32)
    pal = np.zeros((len(blocks), 8), dtype=np.float32)
    pal[:, 0], pal[:, 1] = a0, a1
    gt = a0 > a1
    for i in range(1, 7):
        pal[:, i + 1] = np.where(gt, ((7 - i) * a0 + i * a1) / 7.0, 0.0)
    for i in range(1, 5):
        pal[:, i + 1] = np.where(~gt, ((5 - i) * a0 + i * a1) / 5.0, pal[:, i + 1])
    pal[:, 6] = np.where(~gt, 0.0, pal[:, 6])
    pal[:, 7] = np.where(~gt, 255.0, pal[:, 7])
    bits = blocks[:, 2:8].astype(np.uint64)
    word = np.zeros(len(blocks), dtype=np.uint64)
    for i in range(6):
        word |= bits[:, i] << np.uint64(8 * i)
    out = np.zeros((len(blocks), 16), dtype=np.uint8)
    for px in range(16):
        idx = ((word >> np.uint64(3 * px)) & np.uint64(7)).astype(np.int64)
        out[:, px] = np.round(pal[np.arange(len(blocks)), idx]).astype(np.uint8)
    return out


def _blocks_to_plane(values, width, height):
    bw, bh = width // 4, height // 4
    v = values.reshape(bh, bw, 4, 4)                     # block row, block col, y in block, x in block
    return v.transpose(0, 2, 1, 3).reshape(height, width)


def decode_bc4(data: bytes, width: int, height: int):
    n = (width // 4) * (height // 4)
    blocks = np.frombuffer(data[:n * 8], dtype=np.uint8).reshape(n, 8)
    return _blocks_to_plane(_bc4_block_values(blocks), width, height)


def decode_bc5(data: bytes, width: int, height: int):
    """Returns (R, G) planes, uint8."""
    n = (width // 4) * (height // 4)
    blocks = np.frombuffer(data[:n * 16], dtype=np.uint8).reshape(n, 16)
    return (_blocks_to_plane(_bc4_block_values(blocks[:, :8]), width, height),
            _blocks_to_plane(_bc4_block_values(blocks[:, 8:]), width, height))


def load_fo4_bc5(path):
    d = open(path, "rb").read()
    h = read_dds_header(d)
    if h["fourcc"] not in (b"BC5U", b"ATI2") and h["dxgi"] not in (83, 84):
        raise DdsError(f"{path}: expected BC5, got {h['fourcc']!r}/{h['dxgi']}")
    return decode_bc5(d[h["data_offset"]:], h["width"], h["height"])


# ---- DDS writers (uncompressed intermediates that texconv then compresses) ----------------

def write_dds_dx10(path, width, height, dxgi, pixels: bytes, bytes_per_pixel: int):
    hdr = DDS_MAGIC + struct.pack("<7I", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8, height, width, width * bytes_per_pixel, 0, 1)
    hdr += b"\0" * 44
    hdr += struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    hdr += struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    hdr += struct.pack("<5I", dxgi, 3, 0, 1, 0)
    with open(path, "wb") as f:
        f.write(hdr + pixels)


def write_r8(path, plane):
    h, w = plane.shape
    write_dds_dx10(path, w, h, DXGI_R8_UNORM, np.ascontiguousarray(plane, dtype=np.uint8).tobytes(), 1)


def write_rg8_snorm(path, r_unorm, g_unorm):
    """Map unorm 0..255 (0.5 = zero) to signed bytes and write an R8G8_SNORM DDS."""
    h, w = r_unorm.shape
    conv = lambda a: np.clip(np.round((a.astype(np.float32) / 255.0 * 2.0 - 1.0) * 127.0), -127, 127).astype(np.int8)  # noqa: E731
    px = np.stack([conv(r_unorm), conv(g_unorm)], axis=-1)
    write_dds_dx10(path, w, h, DXGI_R8G8_SNORM, px.tobytes(), 2)


def texconv(texconv_exe, src, out_dir, fmt, extra=()):
    mips = () if "-m" in extra else ("-m", "0")          # full mip chain unless the caller sets -m
    r = subprocess.run([texconv_exe, "-nologo", "-y", *mips, "-dx10", "-f", fmt, *extra, "-o", out_dir, src],
                       capture_output=True, text=True)
    if r.returncode != 0 or "FAILED" in r.stdout:
        raise DdsError(f"texconv failed for {src}: {r.stdout.strip()[-300:]} {r.stderr.strip()[-200:]}")


# ---- Fallout 4 spec/gloss -> Starfield PBR -------------------------------------------------

def roughness_from_smoothness(g):
    """FO4 gloss (0..255, 255 = mirror) -> Starfield roughness (255 = fully rough)."""
    return (255 - g.astype(np.int32)).astype(np.uint8)


def flip_green(g):
    return (255 - g.astype(np.int32)).astype(np.uint8)
