"""BA2 archive reader for Fallout 4 (v1, and v7/v8 from the 2024 next-gen update, same layout as v1) and Starfield
(v2, v3): general files and DX10 textures.

    a = Ba2("Fallout4 - Textures1.ba2")
    a.names                    # file names as stored (backslashes)
    data = a.read(name)        # general file bytes, or a complete DDS (DX10 header) for a texture
Lookup is case-insensitive and slash-agnostic: a.find("textures/setdressing/x_d.dds").
Starfield v3 (LZ4) textures are not supported (raises); v1/v2 zlib and uncompressed are.
"""
import os
import struct
import zlib
from dataclasses import dataclass
from typing import List, Optional


class Ba2Error(ValueError):
    pass


@dataclass
class Entry:
    name: str
    kind: str                  # "GNRL" | "DX10"
    # GNRL
    offset: int = 0
    packed: int = 0
    unpacked: int = 0
    # DX10
    width: int = 0
    height: int = 0
    mips: int = 0
    dxgi: int = 0
    cubemap: bool = False
    chunks: Optional[list] = None      # (offset, packed, unpacked, start_mip, end_mip)


def _dds_header_dx10(width, height, mips, dxgi, cubemap):
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mips > 1 else 0)
    caps = 0x1000 | (0x8 | 0x400000 if mips > 1 else 0)
    caps2 = 0xFE00 | 0x200 if cubemap else 0
    h = b"DDS " + struct.pack("<7I", 124, flags, height, width, 0, 0, mips) + b"\0" * 44
    h += struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    h += struct.pack("<5I", caps, caps2, 0, 0, 0)
    h += struct.pack("<5I", dxgi, 3, 4 if cubemap else 0, 6 if cubemap else 1, 0)
    return h


class Ba2:
    def __init__(self, path: str):
        self.path = path
        self._size = os.path.getsize(path)
        with open(path, "rb") as f:
            magic, version, kind, count, name_off = struct.unpack("<4sI4sIQ", f.read(24))
            if magic != b"BTDX":
                raise Ba2Error(f"{path}: not a BA2")
            self.version, self.kind = version, kind.decode()
            if self.kind not in ("GNRL", "DX10"):
                raise Ba2Error(f"{path}: unsupported archive type {self.kind}")
            # Fallout 4 next-gen and Anniversary archives say 7 or 8 but keep the v1 layout (xEdit and OpenMW read
            # them the same way; research/framework/findings/versions-performance.md)
            extra = {1: 0, 7: 0, 8: 0, 2: 8, 3: 12}.get(version)
            if extra is None:
                raise Ba2Error(f"{path}: unsupported version {version}")
            self.compression = struct.unpack("<I", f.read(12)[8:12])[0] if version == 3 else 0
            if version == 2:
                f.read(8)
            f.seek(24 + extra)
            raw = []
            for _ in range(count):
                if self.kind == "GNRL":
                    _h, _e, _d, _fl, off, pk, up, _al = struct.unpack("<I4sIIQIII", f.read(36))
                    raw.append(("GNRL", off, pk, up))
                else:
                    _h, _e, _d, _u, nch, _chsz, hgt, wid, mips, fmt, fl, _tile = struct.unpack("<I4sIBBHHHBBBB", f.read(24))
                    chunks = [struct.unpack("<QIIHHI", f.read(24))[:5] for _ in range(nch)]
                    raw.append(("DX10", wid, hgt, mips, fmt, bool(fl & 1), chunks))
            f.seek(name_off)
            names = []
            for _ in range(count):
                n, = struct.unpack("<H", f.read(2))
                names.append(f.read(n).decode("utf-8", "replace"))
        self.entries: List[Entry] = []
        for name, r in zip(names, raw):
            if r[0] == "GNRL":
                self.entries.append(Entry(name, "GNRL", offset=r[1], packed=r[2], unpacked=r[3]))
            else:
                self.entries.append(Entry(name, "DX10", width=r[1], height=r[2], mips=r[3], dxgi=r[4], cubemap=r[5], chunks=r[6]))
        self.names = names
        self._index = {self._norm(n): i for i, n in enumerate(names)}
        self._validate_entries()

    def _validate_entries(self) -> None:
        """Basic structural validation of entries to catch truncated or corrupt archives early."""
        if not self.entries:
            raise Ba2Error(f"{self.path}: archive contains no entries")
        for i, e in enumerate(self.entries):
            if not e.name:
                raise Ba2Error(f"{self.path}: entry {i} has empty name")
            if e.kind == "GNRL":
                if e.offset < 0 or e.unpacked < 0 or e.packed < 0:
                    raise Ba2Error(f"{self.path}: invalid offsets/sizes in GNRL entry {e.name}")
                payload = e.packed or e.unpacked
                if e.offset > self._size or e.offset + payload > self._size:
                    raise Ba2Error(f"{self.path}: GNRL entry {e.name} payload is outside the file")
            elif e.kind == "DX10":
                if e.width <= 0 or e.height <= 0 or e.mips <= 0:
                    raise Ba2Error(f"{self.path}: invalid dimensions in DX10 entry {e.name}")
                if not e.chunks:
                    raise Ba2Error(f"{self.path}: DX10 entry {e.name} has no chunks")
                for off, pk, up, _s, _e in e.chunks:
                    chunk = pk or up
                    if off > self._size or off + chunk > self._size:
                        raise Ba2Error(f"{self.path}: DX10 entry {e.name} chunk is outside the file")

    def summary(self) -> dict:
        """Return a short summary of the archive contents, including total packed and unpacked sizes.

        Totals help conversion planning: how much data will be read or written. Packed is the on-disk size
        (zlib or raw); unpacked is the expanded size. DX10 unpacked excludes the reconstructed DDS header.
        """
        gnrl = [e for e in self.entries if e.kind == "GNRL"]
        dx10 = [e for e in self.entries if e.kind == "DX10"]
        def packed_of(e):
            if e.kind == "GNRL":
                return e.packed or e.unpacked
            return sum((c[1] or c[2]) for c in (e.chunks or []))
        def unpacked_of(e):
            if e.kind == "GNRL":
                return e.unpacked
            return sum(c[2] for c in (e.chunks or []))
        total_packed = sum(packed_of(e) for e in self.entries)
        total_unpacked = sum(unpacked_of(e) for e in self.entries)
        return {
            "path": self.path,
            "version": self.version,
            "kind": self.kind,
            "entries": len(self.entries),
            "general": len(gnrl),
            "textures": len(dx10),
            "total_packed": total_packed,
            "total_unpacked": total_unpacked,
        }

    def size_estimates(self) -> dict:
        """Rough estimates of packed (on-disk) and unpacked (decompressed) total sizes.

        Useful for conversion planning: packed is what you download/store, unpacked is peak RAM/temp during extract.
        Counts only the payload sizes recorded in the index; does not read file data.
        """
        packed = 0
        unpacked = 0
        for e in self.entries:
            if e.kind == "GNRL":
                packed += e.packed or e.unpacked
                unpacked += e.unpacked
            elif e.kind == "DX10" and e.chunks:
                for _off, pk, up, _s, _e in e.chunks:
                    packed += pk or up
                    unpacked += up
        return {"packed_bytes": packed, "unpacked_bytes": unpacked, "entries": len(self.entries)}

    def largest_entries(self, n: int = 10) -> list:
        """Return the n largest entries by unpacked size, useful for conversion planning.

        Each item is a dict with name, kind, unpacked bytes, and packed bytes (0 if uncompressed).
        For DX10 textures the unpacked size is the sum of chunk unpacked sizes (excluding the DDS header).
        """
        def unpacked_of(e: Entry) -> int:
            if e.kind == "GNRL":
                return e.unpacked
            return sum(c[2] for c in (e.chunks or []))   # c[2] is unpacked

        def packed_of(e: Entry) -> int:
            if e.kind == "GNRL":
                return e.packed or e.unpacked
            return sum((c[1] or c[2]) for c in (e.chunks or []))

        ranked = sorted(self.entries, key=unpacked_of, reverse=True)[:n]
        return [
            {
                "name": e.name,
                "kind": e.kind,
                "unpacked": unpacked_of(e),
                "packed": packed_of(e),
            }
            for e in ranked
        ]

    @staticmethod
    def _norm(n: str) -> str:
        return n.replace("/", "\\").lower().lstrip("\\")

    def find(self, name: str) -> Optional[int]:
        return self._index.get(self._norm(name))

    def read(self, name_or_index) -> bytes:
        i = name_or_index if isinstance(name_or_index, int) else self.find(name_or_index)
        if i is None:
            raise KeyError(name_or_index)
        e = self.entries[i]
        with open(self.path, "rb") as f:
            if e.kind == "GNRL":
                f.seek(e.offset)
                raw = f.read(e.packed or e.unpacked)
                return zlib.decompress(raw) if e.packed else raw
            if self.version == 3 and self.compression == 3:
                raise Ba2Error("LZ4-compressed (v3) textures are not supported")
            out = [_dds_header_dx10(e.width, e.height, e.mips, e.dxgi, e.cubemap)]
            for off, pk, up, _s, _e in e.chunks:
                f.seek(off)
                raw = f.read(pk or up)
                out.append(zlib.decompress(raw) if pk else raw)
            return b"".join(out)
