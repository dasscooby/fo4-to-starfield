"""Read-only helpers for Starfield .sfs saves. Everything stays in memory; the save is opened 'rb' only."""
import struct
import zlib


def decompress(path):
    raw = open(path, "rb").read()
    if raw[:4] != b"BCPS":
        return raw
    chunk_sizes_off, = struct.unpack_from("<Q", raw, 8)
    comp_data_off, = struct.unpack_from("<Q", raw, 24)
    uncomp_size, = struct.unpack_from("<Q", raw, 32)
    chunk_uncomp, = struct.unpack_from("<Q", raw, 48)
    padding, = struct.unpack_from("<Q", raw, 56)
    n = (uncomp_size + chunk_uncomp - 1) // chunk_uncomp
    sizes = struct.unpack_from("<%dI" % n, raw, chunk_sizes_off)
    out = bytearray()
    pos = comp_data_off
    for i, s in enumerate(sizes):
        chunk = raw[pos:pos + s]
        want = min(chunk_uncomp, uncomp_size - len(out))
        if s == want:                       # stored chunk (incompressible)
            out += chunk
        else:
            out += zlib.decompress(chunk)
        pos += s
        if padding:
            pos = (pos + padding - 1) // padding * padding
    if len(out) != uncomp_size:
        raise ValueError("decompressed %d, expected %d" % (len(out), uncomp_size))
    return bytes(out)


def hexdump(data, start, length, width=32):
    lines = []
    for off in range(start, start + length, width):
        chunk = data[off:off + width]
        hx = " ".join("%02x" % b for b in chunk)
        tx = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append("%09d  %-*s  %s" % (off, width * 3, hx, tx))
    return "\n".join(lines)
