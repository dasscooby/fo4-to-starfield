# Probe session card: the Pip-Boy data channel, the bridge ping B0-2 and the sidecar P1 (FAL-216), and a click that reaches a quest, B0-3 (FAL-246)

For: the owner PC (Claude, the chosen one), Windows PowerShell, a checkout of `fo4sf/fo4-to-starfield` at the head
this card is published with. One build round and one game session (with the relaunch P1 already needs) cover four
tests:

| Test | Plugin | Settles |
| --- | --- | --- |
| **C**, Pip-Boy stage (c) | `sfse/FO4SFPipboyMenu`, `Stage=3` | native code writes a text field in our movie and hears a button click from it; pause state, who holds input and whether time runs, per flag set (the three menu answers, section 6) |
| **B0-2**, the bridge ping | `sfse/FOCCPing` | a quest script calls our plugin and reads its answer, before and after a save and load |
| **P1**, the sidecar | `sfse/FOCCSidecar` | one value written beside a save at save time and read back at load time |
| **B0-3**, click to quest | `sfse/FO4SFPipboyMenu`, `Stage=3`, `ClickCall=FOCC_B0.Click` | a click in our menu reaches the probe quest's script (native to script); run last, in the relaunch |

**Which steps need a save:** B0-2 makes one save (`focc_b0_a`) and loads it; P1 makes two saves (`focc_p1_a`,
`focc_p1_b`) and loads one. Test C makes no save, and neither does B0-3; both need only a loaded game. Use a throwaway
character's save.

**Before the session.** FAL-187's stages (a) and (b) passed at `782f944a` (owner PC, 10 Nov, 20:02 and 20:06 UTC), and
this head contains #704's head `256b3854`: `eb242b32`, which has that tree, with `main` merged in. Stage (c) is that
movie with two more children. B0-3 is FAL-246's pull request, stacked on #711 (FAL-216, head `e7925e00`): both
independent reviews must be CLEAR, #711's at `e7925e00` and FAL-246's at this head, and all three dlls come from this
one head. The usual rules of `docs/spikes/combined-core-probes.md` hold: game closed for every copy,
never during a runner run, D: keeps 40 GB free, nothing from the PC goes into Git, a launch that does not reach the
main menu is a result (remove the dlls first, then report).

## 1. Build (nothing is installed; the game may be running)

```powershell
cd <checkout at this head>; git log -1 --format=%H
$env_ = 'D:\Modding\tools\msvc_env.ps1'; $date = Get-Date -Format yyyyMMdd
powershell -File sfse\FO4SFPipboyMenu\build.ps1 -Out "D:\Modding\staging\pipboy_menu_c_$date" -Env $env_; $LASTEXITCODE
powershell -File sfse\FOCCPing\build.ps1 -Out "D:\Modding\staging\focc_ping_$date" -Env $env_; $LASTEXITCODE
powershell -File sfse\FOCCSidecar\build.ps1 -Out "D:\Modding\staging\focc_sidecar_$date" -Env $env_; $LASTEXITCODE
python -m unittest tests.test_make_probe_swf tests.test_make_pipboy_probe tests.test_pipboy_probe_install `
  tests.test_pipboy_menu_channel tests.test_sfse_ping_plugin tests.test_sfse_sidecar_scripts tests.test_sfse_sidecar_codec
python scripts\guard.py
```

Expect three `0`s, and in each folder the dll, its `.pdb` and `build.json` naming libxse `9d090c4c...` and
`9fbb74d6...`. Post the three dll sha256s. On exit 1, post that folder's `xmake_output.txt` whole: none of the three
sources has met a compiler before this round (FOCCPing's and FO4SFPipboyMenu's earlier versions have).

## 2. Stage the probe movie and the B0 kit

```powershell
$exp = "D:\Modding\staging\pipboy_probe_c_$date"
python scripts\ui\make_pipboy_probe.py stage $exp --channel
python scripts\ui\make_pipboy_probe.py check "$exp\FO4SFPipboyProbe.esm"
python scripts\ui\make_probe_swf.py --read "$exp\Data\Interface\FO4SF_PipboyMenu.swf" | Select-String 'DefineFont3|fo4sfPosition|fo4sfButton'
```

Expect `ok:` from the check and three matching lines (the font and the two instance names). The script side of B0-2
and B0-3 is the combined probe kit (`FOCC.psc`, `FOCC_B0.psc`, GMST `iFOCC_Pong` = 7 in `FO4SFCombinedProbe.esm`).
`FOCC_B0.psc` gained `Click` at this head, so stage the kit from this head in any case: if `probe_install.py status
--starfield $sf` shows an older kit installed, `probe_install.py uninstall` it first; then the runbook's jobs
`focc-stage` and `focc-install`, and check `compile_b0.txt` says compiled.

## 3. Install (game closed). Take the receipts first

Receipts before: `Plugins.txt`, `Get-ChildItem "$sf\Data\SFSE\Plugins"` with sha256s, and the saves list. Then:

```powershell
$pl = "$sf\Data\SFSE\Plugins"; New-Item -ItemType Directory -Force $pl | Out-Null
$had_bin = Test-Path "$pl\versionlib-1-16-244-0.bin"
if (-not $had_bin) { Copy-Item D:\Modding\staging\addresslib_v22\versionlib-1-16-244-0.bin $pl }
Format-Hex "$pl\versionlib-1-16-244-0.bin" | Select-Object -First 1          # opens with 05 00 00 00
Copy-Item "D:\Modding\staging\pipboy_menu_c_$date\FO4SFPipboyMenu.dll","D:\Modding\staging\pipboy_menu_c_$date\FO4SFPipboyMenu.ini" $pl
(Get-Content "$pl\FO4SFPipboyMenu.ini") -replace '^Stage=0','Stage=3' | Set-Content -Encoding ASCII "$pl\FO4SFPipboyMenu.ini"
Copy-Item "D:\Modding\staging\focc_ping_$date\FOCCPing.dll" $pl
Copy-Item "D:\Modding\staging\focc_sidecar_$date\FOCCSidecar.dll","D:\Modding\staging\focc_sidecar_$date\FOCCSidecar.ini" $pl
(Get-Content "$pl\FOCCSidecar.ini") -replace '^bEnabled=0','bEnabled=1' | Set-Content -Encoding ASCII "$pl\FOCCSidecar.ini"
$rt = "$saves\FO4SF-Runtime"; $had_rt = Test-Path "$pl\FO4SF-Runtime.ini"   # FAL-246: the sidecar's files go here, not under Data
if (-not $had_rt) { Set-Content -Encoding UTF8 "$pl\FO4SF-Runtime.ini" "[Runtime]`r`nDir=$rt" }
Get-Content "$pl\FO4SF-Runtime.ini"
Select-String -Path "$pl\FO4SFPipboyMenu.ini","$pl\FOCCSidecar.ini" -Pattern '^(Stage|bEnabled|FlagSets|SnapshotKey|ClickCall)='
Get-FileHash -Algorithm SHA256 "$pl\*.dll"
```

Expect `Stage=3`, `FlagSets=0x0,0x8,0x9`, `SnapshotKey=0x7A`, `ClickCall=` (empty: no click reaches a script in the
first launch), `bEnabled=1`, `FO4SF-Runtime.ini` naming `Dir=<saves folder>\FO4SF-Runtime` (if one was there already,
it stays as it was and its `Dir` is where the sidecars go; use that as `$rt`), and the dll hashes equal to the builds'.
Then the movie's plugin and archive, as for stage (b) (inside the `plugin_toggle.py` hold, as the FO4SFPipboyMenu
README says):

```powershell
python scripts\ui\pipboy_probe_install.py install --dir $exp --starfield $sf; $LASTEXITCODE
```

## 4. The session: launch through `sfse_loader.exe`, load a throwaway save, wait until in control

Keys: **F10** opens and closes our menu; **F11** writes a snapshot line. Give each step about two seconds.

**Clicking our button.** The game draws its own pointer while our menu shows it (flag sets `0x8` and `0x9`). It starts
at the screen centre at every open and does not follow the desktop pointer: it moves with relative mouse motion, about
0.40 pixels of a 1280-wide screenshot per unit (owner PC, 10 Nov). Move it onto CLICK from the centre; a click aimed at
the desktop pointer's place misses. Only at `0x9` do clicks reach our menu (section 7).

**Time reads (item 12, "does time slow").** A *time read* is the console's `GetGlobalValue GameDaysPassed`; write
down the number it prints. A *60-second window* runs from closing the console after one time read to opening it for
the next. If the console refuses the command, write `time: unknown` and go on; substitute nothing.

**Test C, the Pip-Boy data channel (no save).**

1. *Control for pause and input:* F11 in plain play. Then Esc (the game's own pause menu), F11, Esc again.
   *Control for time:* a time read, a 60-second window in plain play without moving, a time read.
2. **Open 1** (flag set 0, `0x0`): a time read. F10. Wait 2 s. Hold W for 2 s (does the player move with our menu
   open?). Stop, wait 1 s. Screenshot. Click CLICK once. F11. Keep the menu open to the end of the 60-second window,
   F10 to close, and without moving a time read; then `player.getpos x`, `player.getpos y`, `player.getpos z`; close
   the console.
3. **Open 2** (flag set 1, `0x8`, libxse's ShowCursor): a time read. F10. Click CLICK twice; click once on the green
   beside it (*control for the click*). Hold W for 2 s, stop, wait 1 s. Screenshot. F11. At the end of the 60-second
   window F10 to close, a time read, `player.getpos x`, `y`, `z` again.
4. **Open 3** (flag set 2, `0x9`, ShowCursor and bit 0): a time read. F10. Click CLICK once. Hold W for 2 s.
   Screenshot. F11. At the end of the 60-second window F10 to close, a time read.
5. If F10 does not close the menu within 5 s at any open, press Esc once; if it is still open, close the game the
   normal way and report it: that is a finding about that flag set, not a failure of the session.

**B0-2, the bridge ping (one save, one load).** In the console:

```
cgf "FOCC_B0.Gmst"
cgf "FOCC_B0.Ping" 41
save focc_b0_a
```

Load `focc_b0_a` from the menu, then:

```
cgf "FOCC_B0.Ping" 43
cgf "FOCC_B0.Gmst"
```

**B0-2 without a save**, when saving is not released: install `FOCCPing.dll` and the combined probe kit only, start
from the main menu with `coc FO4Core_RedRocketSpawn` (no save made without the kit is loaded), then
`cgf "FOCC_B0.Gmst"`, `cgf "FOCC_B0.Ping" 41`, `cgf "FOCC_B0.Ping" 43`, `cgf "FOCC_B0.Gmst"`. The judge passes on the
first read of 7 and an answered ping (`probes b0`); only "still bound after a load" stays NOT_RUN.

**P1, the sidecar (two saves, one load).** In the console `save focc_p1_a`. Load the save the session started from
(menu). In the console `save focc_p1_b`. Load `focc_p1_a` (menu). Quit to desktop.

**Collect the launch's logs now, before the relaunch:** the next launch rewrites `focc.0.log` and the three SFSE logs
(`focc_sidecar.log` is only ever appended). `$saves` and `$logs` as the runbook defines them:

```powershell
$out = "D:\Modding\testqueue\fal216_$date"; New-Item -ItemType Directory -Force "$out\sfse" | Out-Null
$sfseLogs = "$(Split-Path $saves)\SFSE\Logs"
Copy-Item "$sfseLogs\FO4SFPipboyMenu.log","$sfseLogs\FOCCPing.log","$sfseLogs\FOCCSidecar.log" "$out\sfse\"
Copy-Item "$logs\focc.0.log" $out
```

On `got=0`, add `Papyrus.0.log` now too.

**The relaunch: P1's orphan step, then B0-3, the click that reaches a quest (no save).** Game closed, turn the click on:

```powershell
(Get-Content "$pl\FO4SFPipboyMenu.ini") -replace '^ClickCall=.*','ClickCall=FOCC_B0.Click' | Set-Content -Encoding ASCII "$pl\FO4SFPipboyMenu.ini"
Select-String -Path "$pl\FO4SFPipboyMenu.ini" -Pattern '^(Stage|ClickCall)='
```

Expect `Stage=3` and `ClickCall=FOCC_B0.Click`. Relaunch through the loader. In the load menu delete `focc_p1_b`
(P1's orphan step). Then load the save the session started from (not a `focc_` save, so P1's read-backs stay as they
are) and wait until in control:

1. F10. If open 1 of Test C logged no `step=click`, F10 to close and F10 again until the open whose flag set did (open
   2, `0x8`).
2. Click CLICK twice, then once on the green beside it (*control*). Keep the menu open 10 s without clicking (*the
   clock mark*: whether the script runs while our menu is open). F10 to close. Wait 10 s. Quit to desktop.

This step runs last because it is the first call into the script VM from our menu: if the game stops at the first
click, the earlier tests are already collected. Then collect it:

```powershell
New-Item -ItemType Directory -Force "$out\b03" | Out-Null
Copy-Item "$sfseLogs\FO4SFPipboyMenu.log" "$out\b03\"; Copy-Item "$logs\focc.0.log" "$out\b03\"
Copy-Item "$(Split-Path $logs)\Papyrus.0.log" "$out\b03\"
```

(`Papyrus.0.log` is in `Logs\Script`, the folder above `$logs`.)

## 5. Collect the rest, then uninstall (game closed)

```powershell
Copy-Item "$rt\logs\focc_sidecar.log" "$out\sfse\"; Copy-Item "$rt\sidecars" "$out\sfse\sidecars" -Recurse
Get-ChildItem $saves -Filter *.sfs | Select Name,Length | ConvertTo-Json > "$out\saves.json"
$env:PYTHONPATH = "src"; python -m fo4sf.combined.probes b0 $out; python -m fo4sf.combined.probes p1 $out
```

Then uninstall:
`pipboy_probe_install.py uninstall --starfield $sf`; delete `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini`,
`FOCCPing.dll`, `FOCCSidecar.dll` and `FOCCSidecar.ini` from `$pl`, and `FO4SF-Runtime.ini` if `$had_rt` was false; leave
`$rt` (the run-time folder beside the saves is player data); delete
`versionlib-1-16-244-0.bin` only if `$had_bin` was false; `probe_install.py uninstall` if the B0 kit went in for this
session. Compare with the receipts.

## 6. What passes, and each test's control

**Load (all three logs).** `FO4SFPipboyMenu.log`: `step=load ... stage=3`, `step=load_c flag_sets=0x0,0x8,0x9
snapshot_key=0x7a click_call=none`, 32 `step=id` lines, `step=channel_ids value_functions=sfse_equal rtti_names=ok`,
`step=ready stage=c ... locator=<rva>`, `step=register result=ok`, `step=key_thread ... snapshot_key=0x7a`, and at each
open `step=create ... vtables=engine rtti=engine ... set=<i>`. `FOCCPing.log`: `FOCCPing v0.3.0.0`, 14 `step=id` lines,
`step=rtti vtable=NativeFunctionBase offset=0x0 slots=0x06,0x0F,0x10,0x14,0x15 match`, `listening for PostDataLoad;
FOCC.Ping binds then`, `step=object name=GameVM`, `step=object name=VirtualMachine`, `step=bind slot=0x1e`, `bound
FOCC.Ping`. `FOCCSidecar.log`: `step=load runtime=1.16.244.0 ... enabled=1`, `step=runtime_dir dir=<$rt>`, `step=listen`. Any `refuse step=` line
stops that plugin's test; its README says what each one means.

**C, text field in.** PASS: `step=movie_root ... root_type=.?AVMovieRoot@AS3@GFx@Scaleform@@`; at each open
`step=field n=0 ... field=1 set=1 read_back=1 match=yes text="X <x> Y <y> Z <z> CLICKS <k>"`, then `step=field n=<k>`
lines about twice a second; where the player moved with the menu open, the numbers change; the screenshots show the
line in the green box. *Control:* the console's `player.getpos x/y/z` after opens 1 and 2 equal the last `step=field`
numbers before that close, to 0.1.

**C, click out.** PASS: `step=listen root=1 button=1 ... added=1 event=click` at the first open, and one `step=click
n=<k>` per click on CLICK (1, then 2 more, then 1: n=1 to 4 if every open takes the mouse), and the next logged
`step=field` reads that `CLICKS` count. Field lines are logged for n = 0 to 20 and then every 20th (and on a mismatch),
so after the first ten seconds of an open the count shows at n = 40, 60, ... *Control:* a click beside the button at
the same flag set adds no `step=click`. An open
whose clicks log nothing is that flag set's finding (no cursor or no mouse for our menu), not a fail, as long as one
open logs its clicks.

**C, pause and who holds input.** Recorded, not judged: `step=flags show=<k> set=<i>` per open and `step=snapshot`
lines with `tag=show`, `open`, `hide`, `main_after_open`, `main_after_close`, `key`. Each gives `paused=`, the menu
stack (`menus=<n>[type/flags,...]`, our menu as `ours`) and the input contexts (`contexts=<n>[ids]`). *Control:* step
1's two F11 lines: plain play against the game's own pause menu. They show which value of `paused=` and which change
in `menus=` and `contexts=` mean "paused" and "a menu holds input"; each open's lines are read against them. Report the
three opens side by side, with whether W moved the player.

**B0-2.** PASS (the judge `probes b0` says PASS): `focc.0.log` has `b0 gmst name=iFOCC_Pong value=7` first, then
`b0 pong sent=41 got=42`, and after the load `b0 pong sent=43 got=44`. *Control:* the plugin's own record agrees,
`FOCCPing.log` holds `ping 41 -> 42` and `ping 43 -> 44` at those times; two different values (41, 43), both answered
`N + 1`, rule out a stale or fixed answer; the opening `value=7` shows the script side reads the kit as staged.
`got=0` with no `ping` line in `FOCCPing.log` is an unbound native: see FOCCPing's README.

**P1.** PASS (the judge `probes p1` says PASS): in `focc_sidecar.log`, a `pre_save` with `"written": true` and its
`post_save` for each of `focc_b0_a`, `focc_p1_a`, `focc_p1_b`, a sidecar file for each, and the load of `focc_p1_a`
logs `post_load ... "found": true, "valid": true, "counter": <the counter its pre_save wrote>`. *Control:* the load of
the save the session started from (made before the plugin was installed) logs `post_load ... "found": false` with
`"error": "not found"`: the plugin reads back only what it wrote, and never invents a value. The judge also lists
`focc_p1_b`'s sidecar as the one orphan after its save was deleted.

**B0-3, the click reaches a quest.** PASS: in `b03\FO4SFPipboyMenu.log`, `step=load_c ... click_call=FOCC_B0.Click`,
then at the first click `step=object name=GameVM`, `step=object name=VirtualMachine ...
type=.?AVVirtualMachine@Internal@BSScript@@ dispatch_static_call=<rva>`, and per click on CLICK one `step=click n=<k>`
followed by one `step=dispatch n=<k> call=FOCC_B0.Click queued=1`; in `b03\focc.0.log` one `b0 click` line per
`queued=1`, the same count. *Control:* the click beside the button adds neither line, and `b03\focc.0.log` has no `b0
click` before the first click (the console never types `FOCC_B0.Click`). `queued=0`, or `queued=1` with no `b0 click`:
`Papyrus.0.log` says why (README, the failure table). B0-3 has no judge of its own, and the judge `probes b0` ignores
the `b0 click` lines.

### The three menu answers (item 12 of the stage additions, FAL-246)

The systems waiting on our menus (the Pip-Boy, lockpicking, the HUD, later V.A.T.S.) need three answers per flag set.
Fill this table from Test C and B0-3; each answer is read against its control, never on its own:

| | Does the game pause? | Who has the keys? | Does time slow? |
| --- | --- | --- | --- |
| How it is read | `paused=` in the `show`, `open` and `main_after_open` snapshots | `contexts=` and `menus=` in the same snapshots; whether W moved the player; whether CLICK logged `step=click` | the two time reads around the open: their difference against the plain-play control's |
| Control | step 1: plain play's `paused=` against the Esc pause menu's | step 1: plain play's `contexts=` against the Esc pause menu's | step 1's 60-second window in plain play |
| Open 1, `0x0` | | | |
| Open 2, `0x8` | | | |
| Open 3, `0x9` | | | |

The answer words: **pauses** when `paused=` equals the Esc control's and differs from plain play's, else **runs**.
Keys: **the game** when W moved the player and `contexts=` equals plain play's; **our menu** when W did not move it
and CLICK logged; **both** or **neither** otherwise, as observed. Time: the open's difference divided by the
control's: about 1 **runs**, about 0 **stopped**, in between **slowed** (give the ratio); `unknown` when the console
refused the read. One more line from B0-3, for scripts: the `b0 click` lines' clock (`focc.0.log`, to the second)
against `step=message ... type=hide` (`FO4SFPipboyMenu.log`, local time): clicks logged before the hide mean the
script VM runs while that flag set's menu is open; clicks logged only at or after it mean scripts wait for the close.

Send back: the three dll sha256s, the three logs and `focc_sidecar.log`, the sidecars, `focc.0.log`, `saves.json`, the
two verdicts, the screenshots, for test C the three opens side by side, the `b03` folder, and the table of the three
menu answers filled in.

## 7. Results at `e7925e00` (owner PC, 10 Nov 2026, 22:52 to 23:06 UTC; landed as #711)

Build round: all three dlls built (exit 0, libxse `9d090c4` / `9fbb74d`). **Test C: PC PASS.** Three sessions on the
test save, no save made, the owner's set put back each time. `FO4SFPipboyMenu.log` had every load line above and no
`refuse` line (FOCCPing and FOCCSidecar were not installed).

- **Text field in: PASS.** `step=field n=0 ... match=yes`; with W held at open 1 the field went X 1.5 to -6.7 about
  twice a second; the console's position after the close equals the last field line.
- **Click out: PASS at `0x9`.** Two clicks on CLICK logged `step=click n=1` and `n=2`, and the next logged field line
  read `CLICKS 2`. Five clicks off the button at `0x9` logged nothing. At `0x8` clicks on the button logged nothing
  (they reach the game: the player attacks). At `0x0` there is no pointer.
- **Pause and input:** `paused=0` with our menu open at every flag set; no set pauses the game.

| | flags | pointer | W moves the player | a click goes to | contexts |
|---|---|---|---|---|---|
| plain play | | | | | `2[0,1]` |
| the game's pause menu | | | | | `paused=1`, `7[0,1,78,2,11,3,13]` |
| open 1 | 0x0 | none | yes | the game | `2[0,1]` |
| open 2 | 0x8 | shown | yes | the game | adds 13 |
| open 3 | 0x9 | shown | no | our menu | adds 13 |

Open findings: the menu-stack read logged `menus=0[]` everywhere, also in the game's pause menu. That is a read that
succeeded with size 0 (a failed one logs `fault`), so it does not show the offset is wrong: `0x3F0` is libxse's own,
held by its `static_assert`. The cause is unresolved; since #722, `menus=` asks the engine's `IsMenuOpen` instead. What
pauses the game is still to find (the pause menu adds contexts 78, 2, 11 and 3). F10 closed the menu at
every open (18 of 18 `match=yes`).

**B0-2 and P1: NOT_RUN.** They need saves (and P1 a deletion in the load menu), which the owner had not released; the
two dlls were built and not installed.
