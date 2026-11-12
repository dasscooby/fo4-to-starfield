"""Verify a stored General BA2 against the pinned experiment Data input hashes."""
import hashlib
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fo4sf.ba2 import Ba2  # noqa: E402


def normalized_name(name: str) -> str:
    name = name.replace("\\", "/")
    if name.startswith("/") or ":" in name or any(part in ("", ".", "..") for part in name.split("/")):
        raise ValueError(f"invalid archive resource path: {name!r}")
    return name.lower()  # Match Ba2._norm; Unicode casefold aliases reader-distinct names.


def verify_archive(path: str, inputs: dict[str, str]) -> None:
    expected = {}
    for key, identity in inputs.items():
        if not key.startswith("Data/"):
            continue
        name = normalized_name(key[5:])
        if name in expected:
            raise ValueError(f"duplicate archive input identity: {name}")
        expected[name] = identity
    size = os.path.getsize(path)
    try:
        with open(path, "rb") as stream:
            magic, version, kind, count, name_offset = struct.unpack("<4sI4sIQ", stream.read(24))
        extra = {1: 0, 2: 8, 3: 12}.get(version)
        if magic != b"BTDX" or kind != b"GNRL" or extra is None:
            raise ValueError("archive must use a supported General BA2 layout")
        if count != len(expected):
            raise ValueError(f"archive coverage differs: {count} entries for {len(expected)} pinned resources")
        records_end = 24 + extra + 36 * count
        if records_end > size or name_offset < records_end or name_offset + 2 * count > size:
            raise ValueError("archive record/name table is truncated or out of bounds")
        with open(path, "rb") as stream:
            stream.seek(name_offset)
            for _ in range(count):
                length, = struct.unpack("<H", stream.read(2))
                if length > size - stream.tell() or len(stream.read(length)) != length:
                    raise ValueError("archive declared name length exceeds the available bytes")
        archive = Ba2(path)
        names = [normalized_name(entry.name) for entry in archive.entries]
        if len(set(names)) != len(names) or set(names) != set(expected):
            raise ValueError("archive names do not exactly cover the pinned resource inventory")
        with open(path, "rb") as stream:
            for name, entry in zip(names, archive.entries):
                if entry.packed:
                    raise ValueError(f"archive resource must be stored uncompressed: {name}")
                if entry.offset + entry.unpacked > size or (entry.unpacked and entry.offset < records_end):
                    raise ValueError(f"archive resource is truncated or out of bounds: {name}")
                stream.seek(entry.offset)
                remaining, digest = entry.unpacked, hashlib.sha256()
                while remaining:
                    chunk = stream.read(min(remaining, 1 << 20))
                    if not chunk:
                        raise ValueError(f"archive resource is truncated: {name}")
                    digest.update(chunk)
                    remaining -= len(chunk)
                if digest.hexdigest() != expected[name]:
                    raise ValueError(f"archive resource differs from pinned input: {name}")
    except (struct.error, UnicodeError) as error:
        raise ValueError("archive layout is truncated or unreadable") from error


def verify_texture_archive(path: str, inputs: dict[str, str]) -> None:
    """A DX10 BA2 of textures against the pinned .dds files (key Data/Textures/..., SHA-256 of the whole file): the archive's names are
    exactly those, and each entry read back (fo4sf.ba2 regenerates the DX10 header) is the pinned file."""
    expected = {normalized_name(k[5:]): h for k, h in inputs.items() if k.startswith("Data/")}
    if not expected:
        raise ValueError("no pinned texture inputs for the texture archive")
    try:
        with open(path, "rb") as stream:
            magic, version, kind, count, _name_offset = struct.unpack("<4sI4sIQ", stream.read(24))
        if magic != b"BTDX" or kind != b"DX10" or version not in (1, 2, 7, 8):
            raise ValueError("texture archive must be an uncompressed-layout DX10 BA2 (v1/v2)")
        archive = Ba2(path)
    except (struct.error, UnicodeError) as error:
        raise ValueError("texture archive layout is truncated or unreadable") from error
    names = [normalized_name(entry.name) for entry in archive.entries]
    if len(set(names)) != len(names) or set(names) != set(expected) or count != len(expected):
        raise ValueError("texture archive names do not exactly cover the pinned texture inventory")
    for name, entry in zip(names, archive.entries):
        if entry.kind != "DX10":
            raise ValueError(f"texture archive entry is not a texture: {name}")
        if hashlib.sha256(archive.read(entry.name)).hexdigest() != expected[name]:
            raise ValueError(f"texture archive resource differs from pinned input: {name}")
