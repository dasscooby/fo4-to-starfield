# Launcher Tests page (FAL-274)

Writer: Codex / The Lone Wanderer, Paperclip Ubuntu OptiPlex.

Implementation is being published in slices in one draft PR. The first slice provides
only the read-only catalog, owner-card parser and recovery coverage. The Tests tab,
registration UI and install/remove actions are not available in this slice.

## Local catalog

`src/fo4sf/launcher/test_kits.py` has five fixed adapters: planet, quest, Pip-Boy,
radiation and power armor. No command comes from a kit manifest or install receipt.
Radiation and power armor installers are not on this slice's base main; a row reports
whether its fixed installer exists, rather than promising an available operation.

The catalog file is `launcher_test_kits.json`, next to the selected launcher settings
file. It records explicit local stage folders only (absolute paths on that machine):

```json
{"schema": 1, "kits": {"pipboy_probe": "C:\\FO4SF-tests\\pipboy"}}
```

Other keys: `planet_probe`, `quest_probe`, `rads_probe`, `power_armor_probe`.
Kit folders are registered deliberately; the launcher does not scan personal folders,
build a kit, fetch dependencies, or download anything. Keep this machine-specific file
private. The GUI registration controls arrive in the following slice.

The list includes registered stages and owned installed kits even if their stage has
disappeared. It reports `not installed`, `installed`, or `installed and active`.
An active claim requires a readable, complete receipt, unchanged owned files and all
recorded plugins ticked in the selected profile's Plugins.txt. Problems remain visible;
a corrupt receipt is never silently treated as an absent install. An installed entry
always carries this line: **saves made now will list this test plugin**.

## Owner card: contract for kit writers

Ship **`owner-card.txt` beside the staged kit's plan/manifest**, outside its `Data`
subfolder, so it does not become a game resource or change a pinned Data inventory.
UTF-8 plain text (a BOM is allowed), at most 16 KiB. First nonempty line: short title.
Then one to eight nonempty steps, numbered `1. ` through `8. ` in order. Blank lines
are allowed; each step occupies one line. Use plain player language: what to press,
what should appear and what to report. Keep console commands, builds, installations
and file operations on the separate helper card. No Markdown or executable content.

```text
Menu check
1. Wait for the PC helper to say the test is ready.
2. Press the test's key and look for the menu.
3. Tell the helper what appeared.
```

The launcher reads and displays the text; it never executes it or opens the file with
an OS association. Missing/invalid/oversized cards are reported; linked cards are
refused. The parser validates structure, not the factual safety of a writer's steps;
independent review must check the card's actual instructions.

## Standalone owner test (FAL-224)

The owner-facing counterpart of STANDALONE-01 is
[the standalone owner card](../testing/standalone/owner-card.txt). It has no deletion,
move, save or load step. The PC helper must first prepare the separately reviewed
FAL-224 `standalone-look` revision 5 card: approved disposable Windows profile,
independent backups, inventory, trace capture and the prepared copy. Owner review and
release of that bounded diagnostic remain required. The short owner card does not
replace operator preparation or grant permission to create accounts or modify the
normal game. A successful menu-only run does not prove save isolation or a playable
Commonwealth.

## Remaining action and PC gates

Install/remove must use the kit's own installer, refuse a running/unknown game state
and pass the interrupted-install gate before any changes. Existing archive-packing
installer paths cannot be used unchanged by this page: an explicit validated prebuilt
archive path is required. No archive build/download belongs in a Tests action.

The recovery guard now recognizes all five kit receipt names, including Pip-Boy,
radiation and power armor. If an interrupted kit's installer is absent, recovery
refuses before making a plugin-list backup or running any installer; it preserves
all journals for the PC helper. This does not install a missing tool automatically.

Synthetic checks: `python3 -m unittest tests.test_launcher_test_kits tests.test_launcher_recovery tests.test_launcher_gui`.
Windows GUI and game checks: NOT_RUN on Ubuntu. The bounded, exact-head PC helper
recipe follows with the UI/action slice; this foundation is not a PC execution request.
