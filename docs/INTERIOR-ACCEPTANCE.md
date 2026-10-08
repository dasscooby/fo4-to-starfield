# Interior slice acceptance

The shipping milestone is eight interiors in one deployed build. This checklist does not
record a pass. A pass is an evidence JSON that
[`scripts/oracles/interior_acceptance.py`](../scripts/oracles/interior_acceptance.py)
accepts. Journal screenshots and offline round-trips are leads, not rows.

Actors, terrain, weapons, and Papyrus stay out until this slice exits 0.

## Cells

Vault 111, Vault 81, Red Rocket cave, Vault 114, Prydwen, Hotel Rexford, Boston Public
Library, Parsons.

## Per cell

| Check | Pass means |
|---|---|
| `walkable` | Floors and stairs hold the player. No fall-through. |
| `doorways` | A closed door blocks. An open hinged door can be walked through. A load door stays solid; falling through it fails the cell. |
| `door_swing` | Both sides of each hinged door open on OPEN, and the leaf rests in the frame. Walking through a leaf the other side already opened does not count. Load doors stay shut; teleport is not this check. |
| `selected_body` | Each attachment uses its own selected Havok body. A shared system does not put every body on every node. |
| `frame_collision` | The frame blocks. Only the opening changes when the leaf moves. |
| `lighting` | The room is neither washed out nor fully metallic. |
| `materials` | Surfaces read as the source materials, including decals that are part of the cell. |

## Build gates

These apply once to the deployed revision, not once per cell.

| Check | Pass means |
|---|---|
| `startup` | The game starts with this build installed and reaches a load. |
| `single_model` | One transplanted collision model is spawned before the whole slice is judged. |
| `rollback` | Uninstall removes this build and the game starts without it. |

## Evidence

`revision` is the 40-digit lowercase git sha that was built. `build_id` names that
staging build. `installed` lists relative paths and lowercase sha256 hashes of the files
that were actually installed. Every check is `{result, kind, evidence}`. `result` is
`pass`, `fail`, or `unverified`. `kind` is `game` or `offline`. `evidence` is a
non-empty note of what was seen.

A `pass` counts only when `kind` is `game` and the revision, build id, and install hashes
are present. An offline parse, a mesh round-trip, or a screenshot that is not tied to
those pins does not close a row. A missing row stays unverified. The oracle exits 1
while any row is unverified, failed, or malformed.

Do not commit the evidence file if it names a machine path or contains game data.
There is no accepted evidence file in the repo. Every row above is unverified.

```
python scripts/oracles/interior_acceptance.py --evidence <evidence.json>
```
