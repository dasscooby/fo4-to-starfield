"""Reference format for the per-save sidecar file an SFSE plugin would keep beside each game save.

Why a sidecar (combined-core-notes/engine-feasibility.md, "In short" and section 1; the SFSE facts are verified there,
the sidecar design is the note's supported hypothesis until probe P1 runs): SFSE has no
working co-save (serialization disabled since 0.2.12, still off in 0.2.21), but it sends PreSaveGame, PostSaveGame,
PreLoadGame and PostLoadGame messages to plugins with the save name, so a plugin can write its own file keyed to that
name on save and read it back on load. SFSE says nothing when a save is deleted, so sidecars can be orphaned;
orphans() lists them and never deletes. Steam Cloud skipping the sidecar is a listed risk, not handled here.

Schema 1 is the P1 / codec.h envelope, legacy for world-state sidecars. Its functions and file-name rule remain
unchanged. Schema 2 is the character envelope: the additive character_* functions require an opaque, caller-supplied
character id and key files by both that id and the save name. The codec never creates or derives the id; its native
source remains a separate P1b gate. Legacy files are preserved and explicitly refused by character_read, never adopted.

This module is the offline codec of that file (the note's prototype item (c): "sidecar format and versioning as a
pure C++/Python codec with round-trip tests"). It runs on this PC, in Python, and claims nothing about the game: a
plugin would mirror the format, not import this. The body is JSON, sorted keys, so the same state writes the same
bytes:

    {"format": FORMAT, "schema": SCHEMA, "save_name": <exact save name>,
     "world_state": <WorldState.to_json() parsed>, "sha256": <hex sha256 of WorldState.to_json()>}

The checksum covers the canonical world state (model.WorldState.to_json, sort_keys JSON), so an edited or truncated
body fails read() with ValueError instead of loading half-right. The world state carries its own schema
(model.SCHEMA_VERSION); SCHEMA here versions only the envelope. Writes go to a temp file in the same directory and
then os.replace, so a crash mid-write leaves the old sidecar intact. Every number here is a placeholder or a
labelled assumption; there is no clock and no randomness.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile

from .model import WorldState

FORMAT = "focc-sidecar"
SCHEMA = 1
CHARACTER_SCHEMA = 2
EXTENSION = ".focc"                  # engine-feasibility.md section 1 names "<save name>.focc"

# File-name rule: the save name with everything outside [A-Za-z0-9_.-] replaced by "_", cut to SAFE_NAME_MAX
# characters, then "-" and the first HASH_CHARS hex digits of sha256(save name), so two save names that differ only in
# replaced characters or beyond the cut still get distinct files. SAFE_NAME_MAX is an ASSUMPTION about path limits
# (kept well under common 255-byte file-name caps), not a measured engine fact.
SAFE_NAME_MAX = 80
HASH_CHARS = 8
CHARACTER_ID_MAX = 64
CHARACTER_HASH_CHARS = 16
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def canonical_state(ws: WorldState) -> str:
    """The text the checksum covers: the world state's own sorted-keys JSON."""
    return ws.to_json()


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sidecar_name(save_name: str) -> str:
    """Schema-1 P1 / codec.h file name for `save_name`. Raises ValueError for an empty name."""
    if not isinstance(save_name, str) or not save_name:
        raise ValueError("save name must be a non-empty string")
    safe = _UNSAFE.sub("_", save_name)[:SAFE_NAME_MAX].strip(".") or "save"
    return f"{safe}-{checksum(save_name)[:HASH_CHARS]}{EXTENSION}"


def sidecar_path(path_dir: str, save_name: str) -> str:
    return os.path.join(path_dir, sidecar_name(save_name))


def encode(save_name: str, ws: WorldState) -> str:
    """The schema-1 P1 / codec.h body, legacy for world states; deterministic for a given state."""
    state = canonical_state(ws)
    body = {"format": FORMAT, "schema": SCHEMA, "save_name": save_name,
            "world_state": json.loads(state), "sha256": checksum(state)}
    return json.dumps(body, sort_keys=True)


def decode(text: str, save_name: str | None = None) -> WorldState:
    """Parse and verify a schema-1 P1 body: format, schema, checksum and (when given) the save name must match, or
    ValueError. The world state is then loaded through WorldState.from_json, which checks its own schema."""
    try:
        body = json.loads(text)
    except ValueError as e:
        raise ValueError(f"sidecar is not JSON: {e}") from None
    if not isinstance(body, dict) or body.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} file (format {body.get('format') if isinstance(body, dict) else None!r})")
    if body.get("schema") != SCHEMA:
        raise ValueError(f"unknown sidecar schema {body.get('schema')!r}, want {SCHEMA}")
    if save_name is not None and body.get("save_name") != save_name:
        raise ValueError(f"sidecar belongs to save {body.get('save_name')!r}, not {save_name!r}")
    if "world_state" not in body or "sha256" not in body:
        raise ValueError("sidecar lacks world_state or sha256")
    state = json.dumps(body["world_state"], sort_keys=True)
    if checksum(state) != body["sha256"]:
        raise ValueError("sidecar checksum mismatch: body edited or truncated")
    return WorldState.from_json(state)


def write(path_dir: str, save_name: str, ws: WorldState) -> str:
    """Write the schema-1 sidecar for `save_name` atomically (temp file, fsync, os.replace). Returns the
    path. An existing sidecar for the same save is replaced whole or not at all."""
    path = sidecar_path(path_dir, save_name)
    fd, tmp = tempfile.mkstemp(prefix=".focc-", suffix=".tmp", dir=path_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(encode(save_name, ws))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def read(path_dir: str, save_name: str) -> WorldState:
    """Load and verify the schema-1 sidecar for `save_name`. FileNotFoundError when there is none (the cue to start
    from the Papyrus floor), ValueError on any mismatch or tamper."""
    with open(sidecar_path(path_dir, save_name), encoding="utf-8") as f:
        return decode(f.read(), save_name)


def orphans(sidecar_dir: str, existing_save_names) -> list[str]:
    """Files not named for a schema-1 save in `existing_save_names`, including schema-2 files, sorted. Never deletes:
    SFSE gives no delete message (module docstring), so the plugin decides what to do with the list."""
    wanted = {sidecar_name(s) for s in existing_save_names}
    out = []
    for name in sorted(os.listdir(sidecar_dir)):
        if name.endswith(EXTENSION) and name not in wanted:
            out.append(os.path.join(sidecar_dir, name))
    return out


class LegacySidecarError(ValueError):
    """A schema-1 world-state sidecar has no character identity and cannot be adopted."""


def validate_character_id(cid: str) -> None:
    """Require an opaque caller-supplied id of 1 to 64 ASCII letters, digits, underscores or hyphens."""
    if not isinstance(cid, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cid) is None:
        raise ValueError(f"character id must match [A-Za-z0-9_-]{{1,{CHARACTER_ID_MAX}}}")


def character_sidecar_name(save_name: str, character_id: str) -> str:
    """Schema-2 character file name; keep the schema-1 safe name and save hash, then add the id hash."""
    legacy_name = sidecar_name(save_name)  # validates the save name before the id
    validate_character_id(character_id)
    return f"{legacy_name[:-len(EXTENSION)]}-{checksum(character_id)[:CHARACTER_HASH_CHARS]}{EXTENSION}"


def character_sidecar_path(path_dir: str, save_name: str, character_id: str) -> str:
    """Path for the schema-2 character envelope."""
    return os.path.join(path_dir, character_sidecar_name(save_name, character_id))


def character_encode(save_name: str, ws: WorldState, character_id: str) -> str:
    """Encode a schema-2 character envelope; the checksum covers only the canonical world state."""
    sidecar_name(save_name)
    validate_character_id(character_id)
    state = canonical_state(ws)
    body = {"character_id": character_id, "format": FORMAT, "save_name": save_name,
            "schema": CHARACTER_SCHEMA, "sha256": checksum(state), "world_state": json.loads(state)}
    return json.dumps(body, sort_keys=True)


def character_decode(text: str, save_name: str, character_id: str) -> WorldState:
    """Verify a schema-2 character envelope, refusing schema 1 before inspecting its checksum."""
    try:
        body = json.loads(text)
    except ValueError as e:
        raise ValueError(f"sidecar is not JSON: {e}") from None
    if not isinstance(body, dict) or body.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} file (format {body.get('format') if isinstance(body, dict) else None!r})")
    if body.get("schema") == SCHEMA:
        raise LegacySidecarError("schema 1 has no character id; refused, not adopted")
    if body.get("schema") != CHARACTER_SCHEMA:
        raise ValueError(f"unknown sidecar schema {body.get('schema')!r}, want {CHARACTER_SCHEMA}")
    sidecar_name(save_name)
    validate_character_id(character_id)
    if body.get("save_name") != save_name:
        raise ValueError(f"sidecar belongs to save {body.get('save_name')!r}, not {save_name!r}")
    if body.get("character_id") != character_id:
        raise ValueError(f"sidecar belongs to character {body.get('character_id')!r}, not {character_id!r}")
    if "world_state" not in body or "sha256" not in body:
        raise ValueError("sidecar lacks world_state or sha256")
    state = json.dumps(body["world_state"], sort_keys=True)
    if checksum(state) != body["sha256"]:
        raise ValueError("sidecar checksum mismatch: body edited or truncated")
    return WorldState.from_json(state)


def character_write(path_dir: str, save_name: str, ws: WorldState, character_id: str) -> str:
    """Atomically replace this schema-2 character file; never read, rename or delete a legacy file."""
    path = character_sidecar_path(path_dir, save_name, character_id)
    fd, tmp = tempfile.mkstemp(prefix=".focc-", suffix=".tmp", dir=path_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(character_encode(save_name, ws, character_id))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def character_read(path_dir: str, save_name: str, character_id: str) -> WorldState:
    """Read schema 2 first; if absent, refuse an existing legacy path loudly, otherwise FileNotFoundError."""
    path = character_sidecar_path(path_dir, save_name, character_id)
    try:
        f = open(path, encoding="utf-8")
    except FileNotFoundError:
        legacy_path = sidecar_path(path_dir, save_name)
        if os.path.exists(legacy_path):
            raise LegacySidecarError(f"legacy sidecar {legacy_path!r} has no character id; refused, not adopted") from None
        raise
    with f:
        return character_decode(f.read(), save_name, character_id)


def character_orphans(sidecar_dir: str, existing: set[tuple[str, str]]) -> list[str]:
    """Sorted .focc paths not named for a schema-2 (save_name, character_id) pair, including every legacy file.
    Never deletes anything."""
    wanted = {character_sidecar_name(save_name, character_id) for save_name, character_id in existing}
    return [os.path.join(sidecar_dir, name) for name in sorted(os.listdir(sidecar_dir))
            if name.endswith(EXTENSION) and name not in wanted]
