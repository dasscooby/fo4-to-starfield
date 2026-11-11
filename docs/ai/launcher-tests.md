# Launcher Tests page (FAL-274)

Writer: Codex / The Lone Wanderer, Paperclip Ubuntu OptiPlex.

The launcher window has a **Tests** tab. Choose a kit type, press **Add staged kit…**
and choose its prepared stage folder. Each listed kit has **Install**, **Remove** and
**Show card**. **Refresh** rereads receipts and the selected profile. Inventory hashing
runs on a worker so the window can still respond. Cards open in a read-only dialog.
The separate **Standalone owner card** button displays the FAL-224 owner test.

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
private. Registering a folder changes this catalog only, not game files.

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

## Installer actions and PC gates

Install/remove use the kit's own fixed installer. They refuse a running/unknown game
state, changed/unsaved locations, incomplete/unreadable recovery state, unknown or
unregistered kit, missing installer, missing plugin/archive, double install, and removal
of a kit that is not installed. The CLI rechecks processes, saved settings, stage registry
and journal bytes immediately before invoking the installer. The installer retains its
own no-overwrite, stage-validation, dependency, held-plugin and journal checks.

The stage must contain `<primary plugin stem> - Main.ba2` next to the plugin. The page
always passes **`--prepacked <that file>`**. exp_install.py and bridge_install.py validate
this archive against the staged source inventory and use their normal exclusive-copy,
hash and rollback paths; they never call Archive2 in this mode. Planet/Pip-Boy wrappers
forward the flag; the quest wrapper already forwards its arguments to bridge_install.
Default command-line installers still pack when explicitly called without --prepacked.
The PC helper prepares archives separately through the existing packaging pipeline.
An older kit wrapper that does not accept --prepacked refuses; it cannot silently build.
Radiation/power armor wrappers belong to their writer's unmerged branches; forwarding
this flag is coordinated on FAL-273. Missing scripts remain visible and disabled.

For scripts/helpers, `launcher.py tests list|register|install|remove --settings <file>`
uses the same model. Register takes `--kit <key> --stage <folder>`. Install/remove take
`--kit <key> --starfield <expected saved game folder>`; a stale target refuses. These
mutations are Windows-only. A configured instance uses its own LOCALAPPDATA and must
pass instance.check_ready; the normal profile's plugin list is not used.

The recovery guard now recognizes all five kit receipt names, including Pip-Boy,
radiation and power armor. If an interrupted kit's installer is absent, recovery
refuses before making a plugin-list backup or running any installer; it preserves
all journals for the PC helper. This does not install a missing tool automatically.

Synthetic checks: `python3 -m unittest tests.test_launcher_test_kits tests.test_launcher_recovery tests.test_launcher_gui`.
Action/prepacked checks: `python -m unittest tests.test_launcher_kit_actions tests.test_pipboy_probe_install tests.test_planet_probe_install tests.test_questprobe_install`.
Use the repository Python environment with requirements-ci.txt.
Windows GUI and game checks: NOT_RUN on Ubuntu. See the [Windows helper card](../testing/launcher-tests-pc.md); execute only after independent exact-head review.
