# Per-save release binding: item 7, part 1

FAL-247, Codex / The Lone Wanderer. This first part provides a read-only verifier and
CLI. It does **not yet enforce Play or automatically publish save bindings**. Those
are the next part of this same item-7 PR. No existing save is automatically adopted.
No game-save header is read or modified; saves and native state are opaque files.

Each release declaration has schema 1, a release_id, ordered masters (name, size,
sha256), and state_layouts keyed by component. Each layout declares format,
envelope_schema and payload_schema separately. This keeps a sidecar envelope version
from being mistaken for the schema of the state inside it.

A save binding has schema 1, the original release declaration, save_name,
save_identity (size/sha256) and state_files. State files are paths relative to the
resolved runtime directory, mapped to component/size/sha256. Every declared state
component must be covered. Relative paths cannot escape their root or traverse links.
Metadata is bounded and duplicate keys, unknown fields/schemas, ambiguous names and
malformed identities refuse. State-free releases may declare no state components.

```text
python -I scripts/launcher.py check-save-release \
  --release <release.json> --binding <save-binding.json> \
  --save <save-file> --starfield <game-folder> --state-dir <profile-runtime-folder>
```

Run on one line on Windows. Exit 0 means the declared compatibility inputs, actual
installed masters, bound save and required state bytes match. Exit 2 reports refusal.
The command writes nothing. It cannot establish that a declaration accurately describes
unmeasured native code, and is not an in-game save/load test.

Changing master membership/order/identity or state layout refuses. Changing only a
release label with identical compatibility inputs can pass while preserving the save's
original release ID. Missing/changed saves or state files, and missing/unreadable
bindings, refuse rather than creating or updating a receipt. Hashing installed masters
reads their full contents; no performance result is claimed here.

The snapshot_binding API creates an in-memory identity snapshot only. The upcoming
publisher must prove a save was newly produced by the running, checked release before
publishing it atomically. An old unbound save cannot be made compatible simply by
calling that helper. Publication/recovery, mandatory installer release declarations
and cross-native integration remain open.

Verification is synthetic: test_launcher_save_release.py constructs opaque fixture
bytes and covers changed declarations/files, missing/malformed bindings, component
coverage, path escape, concurrent changes, Unicode paths and read-only CLI behavior.
Windows/native/Tk/game acceptance remains **NOT_RUN** for this source part.

Part 2 consumes an installed `Data/FO4SF.release.json` declaration. Once present,
Play (including dry-run and the GUI's existing CLI worker) checks every `.sfs` save
in the launcher-resolved `my_games/Saves/FO4SF` folder. Each requires a sibling
`<save name>.fo4sf-release.json` binding using the schema above. The state root is
that profile's `FO4SF-Runtime` folder. This is configured storage, not an H3 result.
An unconfirmed instance/My Games folder or custom INI save-path override refuses.
Unreadable/unknown metadata, unbound or changed saves, changed required state,
changed master/layout declarations and changed installed master bytes refuse.
The player keeps the saves/bindings and restores the matching release; no file is
adopted, repaired, backed up or deleted by this check. An empty first-run profile
needs no binding, but its installed masters are still checked. Hashes run in the
launch worker, not the Tk process-status polling path. A second check runs after
settings, before load-order changes or game start. Symlink/redirected profile roots
and linked bindings refuse; inventories above 4096 saves refuse.

This remains an incomplete draft: installers do not yet publish the declaration,
and absence retains legacy behavior. Deleting a declaration is therefore not yet
detected as a broken managed install. The mandatory ownership/installation link,
active master-set/order validation, and provenance-safe publication for newly
produced saves are required before item 7 is complete or the PR can integrate.
Part 2 supplies the refusal consumer, not a supported workflow for manually
creating a declaration or retroactively binding old saves. No PC card is ready.
