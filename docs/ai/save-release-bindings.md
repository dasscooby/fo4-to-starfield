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

Part 3 adds the metadata installer:

```
python scripts/launcher.py install-release --declaration release.json --settings settings.json
python scripts/launcher.py install-release --declaration release.json --settings settings.json --apply
```

Preview is read-only. Apply requires a finished confirmed FO4SF instance, matching
installed master bytes, no interrupted component installer and a closed game. It
normalizes the explicit release declaration and pins its exact bytes under
`save_release` in the existing `FO4SF-instance.json` receipt, preserving other
instance fields. It records pending publication first, replaces the owned
declaration atomically, and marks complete last. A stop after either durable step
blocks Play; repeat the same `install-release` command to resume. A different
pending declaration, unknown existing bytes or observed concurrent edits refuse.
Missing/changed owned declarations and corrupt ownership metadata block Play;
unowned declarations are not adopted or overwritten. Writes refuse linked metadata
and use temporary files, fsync, replacement and byte checks. Identical completed
publication writes nothing. Saves and their bindings are never touched.

This remains an incomplete draft. Legacy instances with neither declaration nor
ownership retain their existing behavior; explicit release publication does not
make their unbound saves safe. The packaging/component-install workflow must still
invoke this finalization step for managed releases. Provenance-safe atomic
publication for newly produced saves remains required before item 7 is complete
or this PR integrates. No old-save adoption command or PC-ready card is offered.

Part 4 validates explicit active master membership/order against the declaration,
using the instance's own `FO4SF-local/Starfield/Plugins.txt`. Missing, oversized,
non-UTF-8, duplicate or unknown entries refuse. An inactive extra file in Data is
not treated as loaded. All installed built-in master names must match the declared
built-in set; active non-built-in names must match the declared order exactly.
Existing loader preflight rules refuse sTestFile overrides, CCC entries naming
non-built-in plugins and shadow copies in My Games/Data. Loader inputs must be
bounded supported UTF-8 text; replacement decoding cannot hide an override. This
check runs during release publication and full Play checks, then runs again after
the load-order tool and before the game starts. `load_order=off` cannot bypass it.
No files are repaired to make a release match.

This does not establish native indexes or relative built-in ordering. Built-in-only
CCC files follow the existing loader preflight rules; identity/order evidence for
that implicit loader configuration remains necessary before claiming complete
load compatibility. Windows/native acceptance is still NOT_RUN. Packaging
finalization wiring, that implicit-loader evidence/pinning, and new-save provenance
and binding publication remain in this same draft PR.
