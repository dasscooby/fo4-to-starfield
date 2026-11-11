# Owner card: the Pip-Boy page kit, several pages in one screen (FAL-301)

About five minutes, keyboard and mouse only, in a loaded game. No console, no logs, no saving. The PC helper installs
the kit first and takes it out afterwards (section "For the PC helper").

**Good to know.** F10 opens and closes the Pip-Boy. While it is open it has the mouse and the keys, and the game goes on
behind it. The keys:

- **W** and **S** (or the up and down arrows) move the bright bar up and down a list. Hold them to scroll.
- **A** and **D** (or the left and right arrows) change the small tab under the big ones.
- **Q** and **E** change the big tab at the top.
- **Tab** or **Esc** puts the Pip-Boy away, as F10 does.

The game draws its own small pointer for the mouse, starting in the middle of the screen. Clicking a tab or a row works
like the keys.

## The eight steps

| # | Do | You should see | Write down |
| --- | --- | --- | --- |
| 1 | Stand somewhere safe, in control. Press **F10**. | A dark screen in green. At the top: STAT INV DATA MAP RADIO, with a bracket around STAT. Under it, STATUS bright and SPECIAL dim. Eight rows from HEALTH to TIME, the first on a bright bar with dark letters, and VALUE and FROM for it on the right. Three boxes at the bottom (HP, LEVEL, XP), then the key hints and a CLOSE button. | Did it appear? Every row that shows a `?`. |
| 2 | Press **S** three times, then **W** once. | The bar goes down three rows, then up one. The right side follows the bar. | Did the bar move? Did the right side change with it? |
| 3 | Press **D**. | SPECIAL is bright: seven rows, STRENGTH to LUCK, each with a number. | The seven numbers. |
| 4 | Press **E** twice, then **D**. Then hold **S** for about three seconds. | The bracket is on DATA and KIT TEST is bright. Thirty TEST ROW lines scroll while S is held. A small arrow shows when more rows are below or above, and the right side says ROW n OF 30. | Did it scroll? Did it stop at TEST ROW 30? |
| 5 | With the mouse, click one TEST ROW line. Then click the word **MAP** at the top. | The clicked line gets the bar. Then the MAP page: THE MAP WAITS FOR THE MAP TRACK. | Did both clicks work? |
| 6 | Press **Q** until the bracket is back on STAT. Then click the word **SPECIAL**. | STAT, then the SPECIAL rows again. | Did Q and the click work? |
| 7 | Press **Tab** once and wait two seconds. Press **F10**, then **Esc** once and wait. Then, with the Pip-Boy away, press **Esc** once more. | Tab puts the Pip-Boy away and no game menu opens. F10 brings it back, and Esc puts it away the same way. The last Esc opens the game's own menu, as it always does: close that menu with Esc. | Did Tab and Esc each put the Pip-Boy away? Did a game menu open on either? Did the last Esc open the game's menu? |
| 8 | Click **CLOSE** (if the Pip-Boy is gone, press **F10** first). Then press **F10** twice, about two seconds apart. | The Pip-Boy closes. Then it opens again on SPECIAL, where you left it, and closes. | Did CLOSE work? Did it come back on SPECIAL? |

**Report:**

- the answers in the last column;
- a screenshot or a phone photo of STATUS, SPECIAL and KIT TEST if you can;
- whether your character moved, jumped, crouched or did anything else while you pressed keys on the Pip-Boy, and on
  which key;
- anything odd: the game stopped, no pointer, a click did nothing, a row stayed `?`, F10 did not close the Pip-Boy.

If the Pip-Boy does not close, press F10 once more, then Esc.

## For the PC helper (Windows, PowerShell, a checkout at the PR head)

Your own log card goes beside this one. This part names only what this head needs. The paths and receipts are those
of `docs/spikes/pipboy-channel-bridge-session.md`, sections 1 to 3, with these changes:

1. **Build** only `sfse\FO4SFPipboyMenu`, into a new staging folder. Run the tests
   `python -m unittest tests.test_make_probe_swf tests.test_make_pipboy_probe tests.test_pipboy_probe_install
   tests.test_pipboy_menu_channel tests.test_pipboy_stat_page tests.test_pipboy_kit tests.test_pipboy_close_keys`, then
   `python scripts\guard.py`.
   Post the dll's sha256.
2. **Stage** with `--kit`: `python scripts\ui\make_pipboy_probe.py stage $exp --kit`, then `check` on the plugin file: `python scripts\ui\make_pipboy_probe.py check $exp\FO4SFPipboyProbe.esm`.
   `python scripts\ui\make_pipboy_kit.py --check` prints the seven pages, and `make_probe_swf.py --read` on the movie
   lists `fo4sfKitId`, `fo4sfTab0` to `fo4sfTab4`, `fo4sfRowName0` to `fo4sfRowName15` and `fo4sfClose`. The stage
   also holds `owner-card.txt` beside the plugin: these eight steps in the launcher's plain-text form (outside Data, so
   neither packed nor installed).
3. **Install** (game closed, receipts first): the dll and the Address Library file, as in section 3 of that card; no
   FOCCPing or FOCCSidecar. The ini goes too, from this checkout, with `Stage=5` (`-replace '^Stage=0','Stage=5'`).
   Its pages are the ones the movie was staged from. Expect `Stage=5`, `PageFlagSets=0x9`, `SnapshotKey=0x7A`,
   `KitUp=0x26,0x57`, `CloseKeys=0x09,0x1B` and `HoldMenuKeys=1`. Then run `pipboy_probe_install.py install --dir $exp
   --starfield $sf`.
4. **Session:** launch through `sfse_loader.exe`, load a throwaway save, and hand over to the owner. No save is made.
   After the owner's step 8, press F11 once with the Pip-Boy open, then close it. Open the console for the controls
   below, then quit to desktop.
5. **Collect** `FO4SFPipboyMenu.log` (`My Games\Starfield\SFSE\Logs`) and the screenshots before any relaunch.
6. **Uninstall** as in that card: run `pipboy_probe_install.py uninstall --starfield $sf`, delete the dll and the ini
   (and the bin file if it was not there before), and compare the receipts.

**Console controls, one line per page that shows a value:**

| Page | Rows | Control |
| --- | --- | --- |
| STAT / STATUS | HEALTH, LEVEL, EXPERIENCE, CARRY WEIGHT MAX, RADS | `player.getav health`, `player.getlevel`, `player.getav experience`, `player.getav carryweight`, `player.getav FO4SF_Rads` (only with the rads probe) |
| STAT / STATUS | CELL, WORLD, TIME | where the player stands; TIME's minutes move while the Pip-Boy is open. Console: `getglobalvalue 00000039` (days passed; `00000038` is the hour); by name the console refuses both (PC run, 11 Nov, 0393cbe3) |
| STAT / SPECIAL | STRENGTH to LUCK | `player.getav strength`, `player.getav perception`, `player.getav endurance`, `player.getav charisma`, `player.getav intelligence`, `player.getav agility`, `player.getav luck` |
| DATA / KIT TEST | ROW n OF 30, KEY MOVES, CLICK MOVES | none: no game value |

**What the log must show:** see `sfse/FO4SFPipboyMenu/README.md`, "PASS at (e)".

- At load: `step=ready stage=e` after `step=pages pages=7 tabs=5 signature="FO4SF KIT 1 16 STAT,INV,DATA,MAP,RADIO"`.
- At the first open: `step=page_globals value_at=<offset>` (TIME's), `step=kit_movie ... match=yes`, `step=listen
  name=root ... added=1`, `step=listen name=fo4sfClose ... added=1`, and `step=kit n=1 ... show=1 ... missing=0` with
  `match` equal to `changed`.
- While the owner works through the steps:
  - `step=kit_key` lines with `moved=1`;
  - seven `step=kit_av av:2c2` to `av:2c8` lines, each `:used`;
  - `step=kit_click ... name=<a row's, a tab's or a sub-tab's name>` lines with `moved=1`;
  - `step=kit` lines whose `bar=` and `rows=` follow the keys.

Post whole:

- any `refuse` or `step=page_unknown` line;
- every `step=kit` line with `missing` above 0 or `match` below `changed`;
- the first `step=kit_click` line;
- the `step=close_keys`, `step=hold_id`, `step=hold_ids`, `step=hold_target`, `step=hold` and `step=close ...
  by=key` lines, and the `step=snapshot` lines around the owner's Tab and Esc (the F11 one included).

**PASS:**

- every STATUS and SPECIAL row shows a value (RADS may say `NOT INSTALLED`), and SPECIAL matches the console;
- the bar moves and scrolls on keys and on clicks, and tabs and sub-tabs change on keys and on clicks;
- CLOSE and F10 work, and the Pip-Boy reopens where it was left;
- Tab and Esc each put the Pip-Boy away with no game menu over it, and the last Esc opens the game's menu (README
  "PASS at (e)", step 7).

What the other keys did in the game is a finding for the next card, not a pass or a fail.
