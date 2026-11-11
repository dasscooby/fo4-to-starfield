# Owner card: the STAT page, the first Pip-Boy page to use by hand (FAL-272)

About five minutes, keyboard and mouse only, in a loaded game. No console, no logs, no saving. The PC helper installs
the page first and takes it out afterwards (section "For the PC helper").

**Good to know.** F10 opens and closes the page. While it is open, the page has the mouse and the keys: W does not
move you, and the game draws its own small pointer, which starts in the middle of the screen at every open and moves
with the mouse. Moving the mouse slowly works best. The page does not pause the game: time goes on behind it.

## The eight steps

| # | Do | You should see | Write down |
| --- | --- | --- | --- |
| 1 | Stand somewhere safe, in control. Press **F10**. | A green panel: `FO4SF PIP-BOY  STAT` at the top, `TAB 1 OF 2: STATUS`, seven lines, and two dark buttons at the bottom, **NEXT TAB** and **CLOSE**. | Did the panel appear? |
| 2 | Read the seven lines. | `HEALTH`, `LEVEL ... XP`, `CARRIED ... MAX`, `RADS` (`NOT INSTALLED` unless the rads test is installed), `CELL` (a name or `NO NAME`, and a number in brackets), `WORLD`, `TIME ... DAY`. | The numbers for HEALTH, LEVEL, MAX and TIME, and every line that shows a `?`. |
| 3 | Touch nothing for ten seconds. | The minutes of `TIME` go up (about one game minute every three seconds). | Did TIME change? |
| 4 | Move the mouse down until the game's pointer is on **NEXT TAB**, then click once. | `TAB 2 OF 2: DATA`: `POSITION`, `UPDATES` counting up about twice a second, `NEXT TAB CLICKS 1`. | Did the tab change? Does UPDATES count up? |
| 5 | Click **NEXT TAB** again. | Back to `TAB 1 OF 2: STATUS`. | Did it come back? |
| 6 | Point at **CLOSE** and click. | The page goes away; you can walk again. | Did it close? |
| 7 | Walk through a door or about thirty steps; pick something up or drop something; if it is safe, take a little damage (a short fall). Then press **F10**. | The page again. `CELL` (its name or its number) and `TIME` have changed; `HEALTH` is lower after damage; `CARRIED` changes if it shows a number. | Which lines changed? |
| 8 | Press **F10**. | The page closes. | Did F10 close it? |

**Report:** the answers in the last column, plus a screenshot or a phone photo of each tab if you can. Say also if
anything was odd: the game stopped, no pointer, a click did nothing, a line stayed `?`, F10 did not close the page.
If the page does not close, press F10 once more, then Esc.

## For the PC helper (Windows, PowerShell, a checkout at the PR head)

Your own log card goes beside this one. This part only names what this head needs; the paths and receipts are those of
`docs/spikes/pipboy-channel-bridge-session.md`, sections 1 to 3, with these changes:

1. **Build** only `sfse\FO4SFPipboyMenu`, into a new staging folder. Tests:
   `python -m unittest tests.test_make_probe_swf tests.test_make_pipboy_probe tests.test_pipboy_probe_install
   tests.test_pipboy_menu_channel tests.test_pipboy_stat_page`, then `python scripts\guard.py`. Post the dll's sha256.
2. **Stage** with `--page`: `python scripts\ui\make_pipboy_probe.py stage $exp --page`, then `check`. `make_probe_swf.py
   --read` on the movie lists `fo4sfTab`, `fo4sfLine0` to `fo4sfLine6`, `fo4sfTabButton` and `fo4sfCloseButton`.
3. **Install** (game closed, receipts first): the dll, its ini with `Stage=4` (`-replace '^Stage=0','Stage=4'`), and
   the Address Library file, as in section 3 of that card; no FOCCPing or FOCCSidecar. Expect `Stage=4`,
   `PageFlagSets=0x9`, `SnapshotKey=0x7A`. Then `pipboy_probe_install.py install --dir $exp --starfield $sf`.
4. **Session:** launch through `sfse_loader.exe`, load a throwaway save, hand over to the owner. No save is made.
   After the owner's step 8, optionally press F11 once in play, then open the console for the controls:
   `player.getav health`, `player.getav carryweight`, `player.getlevel`, `getglobalvalue gamehour`; quit to desktop.
5. **Collect** `FO4SFPipboyMenu.log` (`My Games\Starfield\SFSE\Logs`) and the screenshots before any relaunch.
6. **Uninstall** as in that card: `pipboy_probe_install.py uninstall --starfield $sf`, delete the dll and ini (and the
   bin file if it was not there before), and compare the receipts.

**What the log must show** (`sfse/FO4SFPipboyMenu/README.md`, "PASS at (d)"): `step=ready stage=d` after
`step=page_ids data_handler=sfse_equal`; at the first open `step=page_strings self_test=ok`,
`step=page_actor_values ... get_actor_value_slot=0x01` and two `step=page_forms` lines with `found=`; two
`step=listen name=... added=1`; `step=page ... fields=8/8 set=8 match=8` lines whose `text=` changes; `step=click
button=tab` per NEXT TAB and `step=click button=close`, `step=close ... sent=hide`, `step=state ... match=yes` for
CLOSE. Any `refuse` or `step=page_unknown` line is a finding: post it whole. Also post `step=page_forms list=AVIF`
whole: its `weight_names=` names the carried-weight value if `CARRIED` shows `?`.

**PASS:** every STATUS line shows a value (RADS may say `NOT INSTALLED`), TIME and UPDATES change while the page is
open, CELL, HEALTH or CARRIED change between opens, both buttons work, and the console's controls match the page.
