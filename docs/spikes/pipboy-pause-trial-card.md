# Trial card: the Pip-Boy pauses the game, `Pause=1` (FAL-565)

The owner asked on 11 Nov for the Pip-Boy to pause the game ("paused"). The setting exists since `30d1d9f8` (FAL-446):
at stages (d) and (e), `Pause=1` in `FO4SFPipboyMenu.ini` adds bit 1 (`0x2`) to every `PageFlagSets` entry, the bit
that paused the game in the PC's flag sweep at `14176a5e`. It ships as `Pause=0`. This trial decides whether `Pause=1`
becomes the shipped default. Nothing changes in the code for it: the plugin source is the same as at `10409137`, the
head that passed the page kit in the game on 12 Nov (`git diff 10409137 <this head> -- sfse/FO4SFPipboyMenu/src` prints
nothing), so that build may be reused; post its sha256 either way.

What the sweep did not show, and this trial does: whether the page still updates, takes keys and clicks and closes on
Tab and Esc while the game is paused, and whether the game always runs again after it closes.

## For the owner (about five minutes, keyboard and mouse, a loaded game)

The same Pip-Boy as the page-kit card (`docs/spikes/pipboy-page-kit-owner-card.md`, its keys and its eight steps).
One difference: **the game should stop while the Pip-Boy is open**, and run again when it closes.

| # | Do | You should see | Write down |
| --- | --- | --- | --- |
| 1 | Stand somewhere with something moving in view (a person walking, a fire, water, a flag). Note the time on STAT / STATUS's TIME row after step 2. Press **F10**. | The Pip-Boy, as on the page-kit card. Behind it the world stands still: nothing moves. | Did the world stop? |
| 2 | Leave it open for about a minute, the mouse untouched. Read TIME at the start and at the end. | TIME does not change. | Both times. |
| 3 | Do the page-kit card's steps 2 to 6 (bar, SPECIAL, KIT TEST scrolling, clicks, back to SPECIAL). | All as on that card, while the world stays still. | Anything that did not work, and on which step. |
| 4 | Press **F10**. Wait about ten seconds. | The Pip-Boy closes, the world moves again, TIME goes on. | Did the world move again? |
| 5 | Open it with **F10** and close it with **Tab**. Open it again, close it with **Esc**. Open it again, close it with **CLOSE**. After each close, look for a few seconds. | Each time: the world stops while it is open and moves after it closes. The game's own menu does not appear on Tab or Esc. | Any close after which the world stayed still, or the game's menu appeared. |
| 6 | Walk a few steps, then open and close it with **F10** five times in a row, about two seconds apart. | The same each time; you can walk after the last close. | Could you walk after the last close? |

If the world stays still after a close: press F10 twice (open, close) and then Esc once, and write down what helped.

## For the PC helper (Windows, PowerShell, a checkout at this head)

The page-kit card's "For the PC helper", steps 1 to 6, with these changes:

1. **Build**, or reuse the `10409137` dll (above). Tests: the page-kit card's list, then `python scripts\guard.py`.
2. **Install** the ini with `Stage=5` and `Pause=1`: `-replace '^Stage=0','Stage=5' -replace '^Pause=0','Pause=1'`.
   Keep `MissionStageAt=328` in `[Kit]` if it was set for the 12 Nov run; it does not matter here.
3. **Session:** as on that card. During the owner's step 2, press **F11** once with the Pip-Boy open; after step 4,
   F11 once with it closed. Then the console controls below, then quit to desktop.
4. **Collect** and **uninstall** as on that card. The ini goes back to `Pause=0`.

**Console control** (Pip-Boy closed): `getglobalvalue 00000038` (the hour), twice about a minute apart, moves. While
the Pip-Boy is open the console cannot be used (the page has the keys), so TIME on the page is the control there.

**What the log must show:**

- At load: `step=load_e flag_sets=0x1b pause=1 snapshot_key=0x7a click_call=none` (`0x19` with bit 1 added), then
  `step=ready stage=e`.
- While open: the F11 line `step=snapshot ... tag=key paused=1 ...`, and the `tag=open` lines (one per ten updates)
  with `paused=1`.
- While open: `step=kit n=<k>` lines keep coming, about two a second, and the `step=kit_key` and `step=kit_click`
  lines of the owner's step 3 with `moved=1`, as at `10409137`.
- At each close: `step=toggle ... was_open=1 sent=hide` for F10, `step=close ... by=cancel was_open=1 sent=hide` for
  Tab and Esc, `step=close ... by=button was_open=1 sent=hide` for CLOSE; then `step=state ... open=0 expected=0
  match=yes` and `step=snapshot ... tag=main_after_close paused=0`.
- After step 4: the F11 line `step=snapshot ... tag=key paused=0`.

Post whole: the `step=load_e` line, every `step=snapshot` line, the first and last `step=kit` line of step 2, every
`step=toggle`, `step=close` and `step=state` line, and any `refuse` or `step=page_unknown` line.

**PASS** (then `Pause=1` becomes the shipped default, below):

- the world and TIME stand still while the Pip-Boy is open and move after every close, by F10, Tab, Esc and CLOSE;
- `paused=1` in every snapshot while open, `paused=0` in every `main_after_close` and in the F11 one after step 4;
- keys, clicks, scrolling and CLOSE work as on the page-kit card, and `step=kit` lines keep coming while paused;
- the game's own menu never appears on Tab or Esc, and the player can walk after step 6.

**FAIL**, and `Pause=0` stays: a close after which the game stays paused (`paused=1` in `main_after_close`, or the
world still), or a page that stops updating or taking keys or clicks while paused. Post which close and which lines.

## After a PASS: the default

One commit, by the writer, on a branch from the passing head: `Pause=1` in `sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini`
and its comment ("1 = it pauses, as shipped"), the default in `main.cpp`'s `ReadNumber(ini, L"Pause", ...)` to `1`
(so an older ini without the line pauses too), the README's Pause paragraph, the page-kit owner card's "the game goes
on behind it", and the test in `tests/test_pipboy_quest_bytes.py` that reads the shipped value. That commit changes the
dll, so it needs its own build and a short check in the game: `step=load_e ... pause=1` with the ini's line removed.
