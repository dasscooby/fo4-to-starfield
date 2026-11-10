# Probe session card: the Pip-Boy data channel, the bridge ping B0-2 and the sidecar P1 (FAL-216)

For: the owner PC (Claude, the chosen one), Windows PowerShell, a checkout of `fo4sf/fo4-to-starfield` at the head
this card is published with. One build round and one game session cover three tests:

| Test | Plugin | Settles |
| --- | --- | --- |
| **C**, Pip-Boy stage (c) | `sfse/FO4SFPipboyMenu`, `Stage=3` | native code writes a text field in our movie and hears a button click from it; pause state and who holds input per flag set |
| **B0-2**, the bridge ping | `sfse/FOCCPing` | a quest script calls our plugin and reads its answer, before and after a save and load |
| **P1**, the sidecar | `sfse/FOCCSidecar` | one value written beside a save at save time and read back at load time |

**Which steps need a save:** B0-2 makes one save (`focc_b0_a`) and loads it; P1 makes two saves (`focc_p1_a`,
`focc_p1_b`) and loads one. Test C makes no save; it needs only a loaded game. Use a throwaway character's save.

**Before the session.** FAL-187's stage (b) must have shown the movie (PASS at (b), `sfse/FO4SFPipboyMenu/README.md`);
stage (c) is that movie with two more children. The PR's independent review must be CLEAR at this head. All three dlls
come from this one head. The usual rules of `docs/spikes/combined-core-probes.md` hold: game closed for every copy,
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

Expect `ok:` from the check and three matching lines (the font and the two instance names). B0-2's script side is the
combined probe kit (`FOCC.psc`, `FOCC_B0.psc`, GMST `iFOCC_Pong` = 7 in `FO4SFCombinedProbe.esm`): if
`probe_install.py status --starfield $sf` does not show it installed, run the runbook's jobs `focc-stage` and
`focc-install` first and check `compile_b0.txt` says compiled.

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
Select-String -Path "$pl\FO4SFPipboyMenu.ini","$pl\FOCCSidecar.ini" -Pattern '^(Stage|bEnabled|FlagSets|SnapshotKey)='
Get-FileHash -Algorithm SHA256 "$pl\*.dll"
```

Expect `Stage=3`, `FlagSets=0x0,0x8,0x9`, `SnapshotKey=0x7A`, `bEnabled=1`, and the dll hashes equal to the builds'.
Then the movie's plugin and archive, as for stage (b) (inside the `plugin_toggle.py` hold, as the FO4SFPipboyMenu
README says):

```powershell
python scripts\ui\pipboy_probe_install.py install --dir $exp --starfield $sf; $LASTEXITCODE
```

## 4. The session: launch through `sfse_loader.exe`, load a throwaway save, wait until in control

Keys: **F10** opens and closes our menu; **F11** writes a snapshot line. Give each step about two seconds.

**Test C, the Pip-Boy data channel (no save).**

1. *Control for pause and input:* F11 in plain play. Then Esc (the game's own pause menu), F11, Esc again.
2. **Open 1** (flag set 0, `0x0`): F10. Wait 2 s. Hold W for 2 s (does the player move with our menu open?). Stop,
   wait 1 s. Screenshot. Click CLICK once. F11. F10 to close. Without moving, open the console:
   `player.getpos x`, `player.getpos y`, `player.getpos z`; close the console.
3. **Open 2** (flag set 1, `0x8`, libxse's ShowCursor): F10. Click CLICK twice; click once on the green beside it
   (*control for the click*). Hold W for 2 s, stop, wait 1 s. Screenshot. F11. F10 to close. `player.getpos x`, `y`,
   `z` again.
4. **Open 3** (flag set 2, `0x9`, ShowCursor and bit 0): F10. Click CLICK once. Hold W for 2 s. Screenshot. F11.
   F10 to close.
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

On `got=0`, add `Papyrus.0.log` now too. Then relaunch through the loader, delete `focc_p1_b` in the load menu, quit
(P1's orphan step).

## 5. Collect the rest, then uninstall (game closed)

```powershell
Copy-Item "$pl\FOCCSidecar\focc_sidecar.log" "$out\sfse\"; Copy-Item "$pl\FOCCSidecar\sidecars" "$out\sfse\sidecars" -Recurse
Get-ChildItem $saves -Filter *.sfs | Select Name,Length | ConvertTo-Json > "$out\saves.json"
$env:PYTHONPATH = "src"; python -m fo4sf.combined.probes b0 $out; python -m fo4sf.combined.probes p1 $out
```

Then uninstall:
`pipboy_probe_install.py uninstall --starfield $sf`; delete `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini`,
`FOCCPing.dll`, `FOCCSidecar.dll`, `FOCCSidecar.ini` and the `FOCCSidecar\` folder from `$pl`; delete
`versionlib-1-16-244-0.bin` only if `$had_bin` was false; `probe_install.py uninstall` if the B0 kit went in for this
session. Compare with the receipts.

## 6. What passes, and each test's control

**Load (all three logs).** `FO4SFPipboyMenu.log`: `step=load ... stage=3`, `step=load_c flag_sets=0x0,0x8,0x9
snapshot_key=0x7a`, 29 `step=id` lines, `step=channel_ids value_functions=sfse_equal rtti_names=ok`, `step=ready
stage=c`, `step=register result=ok`, `step=key_thread ... snapshot_key=0x7a`. `FOCCPing.log`: `FOCCPing v0.3.0.0`,
14 `step=id` lines, `step=rtti vtable=NativeFunctionBase offset=0x0 slots=0x06,0x0F,0x10,0x14,0x15 match`, `listening
for PostDataLoad; FOCC.Ping binds then`, `step=object name=GameVM`, `step=object name=VirtualMachine`, `step=bind
slot=0x1e`, `bound FOCC.Ping`. `FOCCSidecar.log`: `step=load runtime=1.16.244.0 ... enabled=1`, `step=listen`. Any
`refuse step=` line stops that plugin's test; its README says what each one means.

**C, text field in.** PASS: `step=movie_root ... root_type=.?AVMovieRoot@AS3@GFx@Scaleform@@`; at each open
`step=field n=0 ... field=1 set=1 read_back=1 match=yes text="X <x> Y <y> Z <z> CLICKS <k>"`, then `step=field n=<k>`
lines about twice a second; where the player moved with the menu open, the numbers change; the screenshots show the
line in the green box. *Control:* the console's `player.getpos x/y/z` after opens 1 and 2 equal the last `step=field`
numbers before that close, to 0.1.

**C, click out.** PASS: `step=listen root=1 button=1 ... added=1 event=click` at the first open, and one `step=click
n=<k>` per click on CLICK (1, then 2 more, then 1: n=1 to 4 if every open takes the mouse), and the next `step=field`
reads that `CLICKS` count. *Control:* the click on the green beside the button (open 2) adds no `step=click`. An open
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

Send back: the three dll sha256s, the three logs and `focc_sidecar.log`, the sidecars, `focc.0.log`, `saves.json`, the
two verdicts, the screenshots, and for test C the three opens side by side.
