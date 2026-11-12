"""Small synthetic General BA2s using the record layout read by fo4sf.ba2."""
import struct
import zlib


def general_archive(entries, compressed=False, version=2):
    entries = list(entries.items()) if isinstance(entries, dict) else list(entries)
    extra = {1: b"", 7: b"", 8: b"", 2: bytes(8), 3: bytes(12)}[version]
    offset = 24 + len(extra) + 36 * len(entries)
    records, payloads, names = [], [], []
    for name, data in entries:
        payload = zlib.compress(data) if compressed else data
        extension = name.rsplit(".", 1)[-1].upper().encode("ascii")[:4].ljust(4, b"\0")
        records.append(struct.pack("<I4sIIQIII", 0, extension, 0, 0, offset,
                                   len(payload) if compressed else 0, len(data), 0))
        payloads.append(payload)
        encoded = name.encode("utf-8")
        names.append(struct.pack("<H", len(encoded)) + encoded)
        offset += len(payload)
    return (struct.pack("<4sI4sIQ", b"BTDX", version, b"GNRL", len(entries), offset) + extra
            + b"".join(records) + b"".join(payloads) + b"".join(names))


def archive_from_tree(root):
    return general_archive({p.relative_to(root).as_posix(): p.read_bytes()
                            for p in sorted(root.rglob("*")) if p.is_file()})


def texture_archive(entries, version=2):
    """A DX10 BA2 (one chunk per texture, stored) of {name: complete .dds bytes with a DX10 header}, the record layout fo4sf.ba2 reads."""
    entries = list(entries.items()) if isinstance(entries, dict) else list(entries)
    extra = {1: b"", 2: bytes(8)}[version]
    offset = 24 + len(extra) + (24 + 24) * len(entries)
    records, payloads, names = [], [], []
    for name, dds in entries:
        height, width, mips = struct.unpack_from("<I", dds, 12)[0], struct.unpack_from("<I", dds, 16)[0], struct.unpack_from("<I", dds, 28)[0]
        fmt = struct.unpack_from("<I", dds, 128)[0]
        body = dds[148:]
        records.append(struct.pack("<I4sIBBHHHBBBB", 0, b"dds\0", 0, 0, 1, 24, height, width, max(mips, 1), fmt, 0, 8)
                       + struct.pack("<QIIHHI", offset, 0, len(body), 0, max(mips, 1) - 1, 0xBAADF00D))
        payloads.append(body)
        encoded = name.encode("utf-8")
        names.append(struct.pack("<H", len(encoded)) + encoded)
        offset += len(body)
    return (struct.pack("<4sI4sIQ", b"BTDX", version, b"DX10", len(entries), offset) + extra
            + b"".join(records) + b"".join(payloads) + b"".join(names))
