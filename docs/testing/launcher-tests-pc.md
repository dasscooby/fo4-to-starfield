# Tests page: Windows helper card (FAL-274)

Operator: Claude on the owner Windows PC. Source worker: Lone on Ubuntu OptiPlex.
Use the exact 40-hex head in the task's current receipt; `git rev-parse HEAD` must match.
Independent CLEAR at that head comes before this card. Do not take an earlier slice's
CLEAR as review of the UI. Record Windows/Python/Tk versions, head, command and result.
No native/game result has been observed by this source task yet.

## First: synthetic installer and window check

Run with the PC's repository Python environment (numpy and Pillow installed):

```powershell
python -m unittest tests.test_launcher_kit_actions tests.test_pipboy_probe_install tests.test_planet_probe_install tests.test_questprobe_install
python scripts/guard.py
```

Expected: synthetic cases pass; guard ok. They use temporary fake game folders and
prebuilt synthetic archives, no game launch or Archive2. In particular, wrong archives
refuse without publication; valid prebuilt archives install through each kit's installer.

For a window check use a private temporary fixture, not the owner's normal game:
create an empty `game\Data` and a zero-byte `game\Starfield.exe` **in that fixture**,
plus `local\Starfield\Plugins.txt` containing a harmless comment. Keep its paths private.
In a separate PowerShell set that shell's LOCALAPPDATA to the fixture's `local`; do not
change system/user environment settings. Do not press Play on a synthetic fixture.
Generate the synthetic Pip-Boy stage with the existing tool:

```powershell
python -I scripts/ui/make_pipboy_probe.py stage "<fixture>\pipboy"
python scripts/launcher.py settings --settings "<fixture>\settings.json" --set "starfield=<fixture>\game" --set "update=off" --set "route=exe"
python scripts/launcher.py gui --settings "<fixture>\settings.json"
```

Expected window sequence:

1. Open Tests; empty inventory is explained. Choose Pip-Boy, Add staged kit, then the
   generated folder. Row reads **not installed**. With no prebuilt archive, Install
   reports a missing prepared archive and leaves the fake Data and Plugins.txt alone.
2. Have the helper prepare a matching General stored archive separately, named
   `FO4SFPipboyProbe - Main.ba2` beside that stage's plugin. This preparation is outside
   the launcher page. Use the packaging pipeline already qualified on the PC; if none
   is available, stop this success subcase as NOT_RUN rather than changing the page.
   Copy an owner-card.txt using the documented title/numbered-steps contract beside it.
3. Install: expect **installed and active**, the save-plugin notice, and no Archive2
   process from the Tests command. Compare the installer receipt and plugin-list bytes.
   Show card must open plain read-only text. Removing restores the original plugin-list
   bytes and retires only owned files; retain an unrelated sentinel through both actions.
4. Reinstall, untick one test plugin in the fixture's list, then Refresh: **installed**.
   Retick and Refresh: **installed and active**. Move only the helper-owned fixture stage
   aside, Refresh and Remove: the orphaned install stays visible and removes normally.
   Do not move an owner file or a real stage to test this case.
5. Missing or malformed owner cards must show a clear message without opening an OS
   application. A title plus nine numbered steps must refuse. Standalone owner card
   opens its eight plain steps; viewing it does not start the standalone diagnostic.
6. Change a location without confirming it: mutation buttons disable. Reload, then
   change the settings file externally: action refuses and asks to reload. An
   interrupted fake receipt blocks install/remove and Play; use the existing Recover
   install path only on this disposable fixture and preserve its journal on failure.

Record actual window labels and messages, screenshots without private paths, initial/
final fixture plugin bytes, and any remaining journals. Leave helper-created fixtures
and evidence for review; no cleanup or changes to the owner's normal files in this card.

## Then: actual staged-kit inventory, game-closed checks

After synthetic checks pass, use the already-approved saved game/instance locations
and staged kits; do not change the owner's installation/profile selection just to make
a row appear. Register planet, quest, Pip-Boy, radiation and power armor stages that
actually exist. Missing installers or unprepared archives must report/refuse, not build
or download. Radiation/power armor wrapper --prepacked support must have landed before
their success subcases. Confirm an instance reads its own plugin list.

With a game the PC helper already owns running, check that Install/Remove are disabled;
a direct CLI tests action must refuse too. The PC helper controls closing that game.
Repeat with an unavailable process query in the synthetic automated cases, not by
changing system permissions. Native game input/deploy remains the PC helper's scope.
For each staged kit whose installer and --prepacked support are present, record the
initial installed/active state. With the game closed, exercise Install and Remove using
that kit's existing reviewed preparation and preservation contract. Verify the state,
notice, fixed installer output and unchanged unrelated files; return to the recorded
initial state through its installer. Keep any pre-existing kit's recovery materials.
Starting the game to follow a kit's owner card remains that kit's own PC session; this
launcher check needs no save, load or new game.

Report `PC PASS <head>` only for the checks actually observed, naming partial/NOT_RUN
subcases. Full Tests-page acceptance requires the intended five staged-kit successes,
process refusal, recovery and preservation checks. STANDALONE-01 execution separately
retains FAL-224's helper preparation and owner release; showing its card does not grant it.
