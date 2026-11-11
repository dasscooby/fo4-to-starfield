# Per-save release binding: item 7, draft parts 1–6

FAL-247, Codex / The Lone Wanderer. This draft provides a read-only verifier,
CLI, Play enforcement and owned declaration publication. Automatic save-binding
publication and package/recipe integration remain unfinished. No existing save is automatically adopted.
No game-save header is read or modified; saves and native state are opaque files.

Each release declaration now has schema 2, a release_id, ordered masters (name,
size, sha256), implicit_loaders, and state_layouts keyed by component. Each layout declares format,
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


Part 5 pins the implicit CCC configuration in declaration schema 2:

```json
"implicit_loaders": {"game": null, "my_games": null}
```

Each key addresses `Starfield.ccc` in that named folder. `null` means the file
must be absent; a present file needs its measured `{"size": ..., "sha256": ...}`
identity. `release_load.implicit_inputs(game, my_games)` captures these bounded,
supported UTF-8 inputs without writes. A release producer supplies those pins;
Play never captures fresh pins to make a changed install pass. Locations cannot
be omitted or swapped. All exact bytes matter, including comments and line order.
Adding, removing or editing either file refuses until the matching configuration
is restored. The pins also enter compatibility and the original save declaration:
a new release cannot silently rebind an old save to different CCC inputs.
The read-only `check-save-release` command compares the declarations; actual CCC
inputs are checked by publication and profile Play with its confirmed My Games.
Publication rechecks before declaring complete; observed changes retain pending
ownership and require restoration then the same repeat command. The final check
after the load-order tool checks CCC pins as well as explicit Plugins.txt order.
There is no global cross-process lock or claim to defeat every filesystem race.

Earlier schema-1 draft declarations refuse; no automatic migration or adoption is
provided. Binding and instance-ownership schemas remain 1, and a binding embeds
the schema-2 declaration. No accepted item-7 release has been integrated yet.
This pins configuration identity, not native built-in indexes or CCC interpretation.
Native runtime/order acceptance, installer finalization, newly produced save
provenance and atomic binding publication remain required. Keep PR #716 draft;
Windows/native/Tk/game NOT_RUN. Saves and native state remain untouched.


Part 6 connects a component command to release publication:

```text
python scripts/launcher.py instance run --settings settings.json --declaration release.json -- python scripts/game/exp_install.py install --starfield <confirmed-instance> ...
```

The command must name the confirmed instance exactly once, under the existing
`instance run` target rules. Settings must name that same instance and an absolute,
existing My Games folder. After validating the command, closed game, instance and
explicit declaration ownership, the launcher writes pending ownership **before**
starting the installer. The installer receives the instance's own LOCALAPPDATA.
Its nonzero exit, exception or interrupted run leaves pending ownership, so Play
refuses even if the installer stopped before writing its own component journal.
Repeating the same command and declaration can resume; a different pending
release input refuses. After exit zero, the input and instance receipt must still
match, and existing `publish` validates installed master bytes, active/CCC inputs
and completed component journals before completing the declaration. A zero exit
alone cannot finalize wrong or incomplete installed files. Existing saves, bindings
and state are untouched. Restore a changed input/configuration before resuming.
The existing `install-release` command can finalize metadata after a component has
already been completed separately, subject to the same installed-state checks.

Once an instance owns a declaration, ordinary `instance run` without `--declaration`
refuses before command execution. A legacy instance with neither ownership nor
declaration retains its previous runner. This is an explicit managed command path;
packaging/recipe selection must still require the release input when installing a
managed package, rather than relying on the legacy path. No packaged release is
newly enabled here. Native runtime/implicit-order acceptance and provenance-safe
new-save publication remain mandatory. Keep #716 draft; Windows/native/Tk/game
NOT_RUN. No cross-process installation lock or arbitrary command authenticity is
claimed by this wrapper; it retains the existing command/target contract.


Part 7 adds an explicit `managed_release` recipe block with absolute `settings`
and `declaration` paths. See
`scripts/launcher_recipes/managed_instance_install.example.json`. Run it through
the existing launcher `build` command, supplying every `?` variable with `--set`.
The declaration describes the complete resulting release, including all component
masters. Each command must satisfy the existing confirmed instance target rules.
The driver validates all targets before writing pending ownership, then starts
one release transaction around the whole recipe. Every component receives the
instance LOCALAPPDATA; earlier components do not prematurely finalize a release
that later components have not installed yet.

Settings and declaration bytes enter every step fingerprint and are rechecked
before each step and final publication. Changed metadata or instance ownership
refuses further execution. A failed, interrupted or partial (`--until`) run stays
pending; restore the original inputs and repeat the same recipe to resume.
Successful cached steps remain reusable, but installed-state validation still runs
when every step is reused. Wrong masters, CCC configuration or incomplete component
journals prevent completion even after zero exits. The report names release
completion/refusal and only publishes a build manifest after release completion.
Dry-run validates the explicit inputs and targets without writing ownership or
starting installers. Malformed managed blocks refuse rather than selecting the
generic build path. Generic staging recipes keep their existing behavior.

This provides an explicit managed recipe template, not an authenticated package
channel or a migration of every existing staging recipe. No accepted release
package is newly enabled. Native runtime/implicit-order acceptance and proven
new-save binding publication remain required before completing item 7. Keep #716
draft; Windows/native/Tk/game NOT_RUN. No saves, state or bindings are written.
