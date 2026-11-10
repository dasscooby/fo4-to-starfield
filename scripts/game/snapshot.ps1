# snapshot.ps1 (Claude, 2026-10-16): what the owner is looking at, for Claude to read. Sends NOTHING to the game: one
# screenshot of the whole screen (shot.ps1), the bridge's newest line (bridge_log.py latest: position, cell, worldspace,
# loaded; the owner's session must have FO4SFBridge.esm active, as every pinned build does), the game's newest Papyrus
# log tail, the mission's own log, and the installed experiment record. Everything goes to -Out (default
# C:\Modding\snapshots\<timestamp>): screen.png, state.json, papyrus_tail.txt, fo4sf_mission.0.log, and one summary line
# on stdout. The owner says "look" and what they see;
# Claude runs this and reads screen.png. docs/owner/in-game-test-sheet.md section 7.
# -Ask (2026-10-18): after the screenshot (so the box is never in the picture) a small box asks "what is wrong?"; the text
# goes to description.txt and state.json's description. "Screenshot only" or an empty box keeps the plain snapshot.
# -Submit (2026-10-18, players): after saving, opens the repository's "Player report" form in the browser already filled
# in (description, position, cell, the port's plugin names; never a folder path) and puts screen.png on the clipboard, so
# the player pastes it (Ctrl+V) and presses Submit. Nothing is sent without that click and the player's GitHub sign-in;
# the form labels it community + needs-triage, so it waits for the owner's review. The link is kept in issue_url.txt.
# $env:FO4SF_SUBMIT_DRYRUN: write issue_url.txt only (tests: no browser, no clipboard).
# usage: snapshot.ps1 [-Out <folder>] [-Note "<what the owner said>"] [-MaxAge 900] [-Ask [-AskTimeout 600]] [-Submit]
param([string]$Out = '', [string]$Note = '', [double]$MaxAge = 900, [switch]$Ask, [switch]$Submit, [int]$AskTimeout = 600)
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'C:\Modding\venv-render\Scripts\python.exe' }
$root = $(if ($env:FO4SF_SNAPSHOT_ROOT) { $env:FO4SF_SNAPSHOT_ROOT } else { 'C:\Modding\snapshots' })   # tests: a temp root
if (-not $Out) { $Out = Join-Path $root (Get-Date -Format 'yyyyMMdd-HHmmss') }
New-Item -ItemType Directory -Force $Out | Out-Null
$state = [ordered]@{ taken = (Get-Date -Format s); note = $Note; game_running = $false; game_foreground = $null }
$g = Get-Process Starfield -ErrorAction SilentlyContinue
if ($g) {
  $state.game_running = $true
  Add-Type -Namespace W -Name U -MemberDefinition '[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow(); [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(System.IntPtr h, out int pid);'
  $fpid = 0; [W.U]::GetWindowThreadProcessId([W.U]::GetForegroundWindow(), [ref]$fpid) | Out-Null
  $state.game_foreground = ($fpid -eq $g.Id)
}
$shot = Join-Path $Out 'screen.png'
# never a stale picture: a reused folder's screen.png goes first, and the capture must exit 0 and leave a new file
# (Codex's review of #175); without one, screen is null and the tool exits 3
Remove-Item -LiteralPath $shot -Force -ErrorAction SilentlyContinue
# nor a stale description: a reused folder's description.txt / describe_later.txt belong to the previous capture (Codex on #463)
foreach ($n in 'description.txt', 'describe_later.txt') { Remove-Item -LiteralPath (Join-Path $Out $n) -Force -ErrorAction SilentlyContinue }
$shotScript = $(if ($env:FO4SF_SHOT_SCRIPT) { $env:FO4SF_SHOT_SCRIPT } else { Join-Path $here 'shot.ps1' })   # the test's stub
powershell -NoProfile -ExecutionPolicy Bypass -File $shotScript -Out $shot | Out-Null
$shotCode = $LASTEXITCODE
$shotOk = ($shotCode -eq 0) -and (Test-Path -LiteralPath $shot) -and ((Get-Item -LiteralPath $shot).Length -gt 0)
$state.screen = $(if ($shotOk) { 'screen.png' } else { $null })
if (-not $shotOk) { $state.screen_error = "shot.ps1 exit $shotCode"; Remove-Item -LiteralPath $shot -Force -ErrorAction SilentlyContinue }
# the bridge's newest line (any age up to MaxAge: the owner may have paused; the age is reported, never hidden)
$b = $null
try { $b = (& $py (Join-Path $here 'bridge_log.py') latest --max-age $MaxAge) | ConvertFrom-Json } catch { $b = $null }
if ($b -and $b.ok) {
  $state.bridge = [ordered]@{ pos = @($b.pos); ang = $b.ang; cell = $b.cell; world = $b.world; loaded = $b.loaded; rt = $b.rt; line = $b.n; age_s = $b.age_s }
} else { $state.bridge = [ordered]@{ why = $(if ($b) { "$($b.why)" } else { 'bridge_log.py gave nothing (no log, or no FO4SFBridge.esm in this session)' }) } }
# the newest Papyrus log's tail (script errors the owner cannot see)
$pap = Join-Path $env:USERPROFILE 'OneDrive\Documents\My Games\Starfield\Logs\Script\Papyrus.0.log'
if (-not (Test-Path $pap)) { $pap = Join-Path $env:USERPROFILE 'Documents\My Games\Starfield\Logs\Script\Papyrus.0.log' }
if (Test-Path $pap) { Get-Content $pap -Tail 40 | Set-Content (Join-Path $Out 'papyrus_tail.txt'); $state.papyrus_tail = 'papyrus_tail.txt' }
# the mission's own log, whole (FO4SF_Min00Quest's Debug.TraceUser: every stage, each keeper move of Preston and Codsworth,
# a status line every 5 s), for the Preston diagnosis (FAL-144). Found as Papyrus.0.log is, OneDrive first, and only that
# one file: fo4sf_mission.1.log and older are earlier sessions, and nothing else in the folder is read. state.json's
# mission_log says where it came from relative to the profile (no user name) and how old it is. A reused folder's copy
# goes first; a missing or unreadable log is recorded in mission_log.why and never fails the snapshot.
$misName = 'fo4sf_mission.0.log'
$mis = Join-Path (Get-Item -LiteralPath $Out).FullName $misName   # a full path: .NET resolves a relative one elsewhere
Remove-Item -LiteralPath $mis -Force -ErrorAction SilentlyContinue
$misFrom = "OneDrive\Documents\My Games\Starfield\Logs\Script\User\$misName"
if (-not (Test-Path -LiteralPath (Join-Path $env:USERPROFILE $misFrom))) { $misFrom = "Documents\My Games\Starfield\Logs\Script\User\$misName" }
$misSrc = Join-Path $env:USERPROFILE $misFrom
if (Test-Path -LiteralPath $misSrc) {
  try {
    # shared read and write, as Get-Content opens it: Copy-Item's open does not share writing, so the running game, which
    # holds the log open, could make it refuse
    $src = [System.IO.File]::Open($misSrc, 'Open', 'Read', 'ReadWrite')
    try { $dst = [System.IO.File]::Create($mis); try { $src.CopyTo($dst) } finally { $dst.Dispose() } } finally { $src.Dispose() }
    $misT = (Get-Item -LiteralPath $misSrc).LastWriteTime
    $state.mission_log = [ordered]@{ file = $misName; from = $misFrom; bytes = (Get-Item -LiteralPath $mis).Length
                                     modified = $misT.ToString('s'); age_s = [int]((Get-Date) - $misT).TotalSeconds }
  } catch {
    Remove-Item -LiteralPath $mis -Force -ErrorAction SilentlyContinue
    $state.mission_log = [ordered]@{ file = $null; why = "copy failed: $($_.Exception.Message)" }
  }
} else { $state.mission_log = [ordered]@{ file = $null; why = "no $misName under OneDrive\Documents or Documents\My Games\Starfield\Logs\Script\User" } }
# what is installed (exp_install's record) and active
$rec = 'D:\SteamLibrary\steamapps\common\Starfield\Data\FO4SFExp.install.json'
if (Test-Path $rec) { try { $r = Get-Content $rec -Raw | ConvertFrom-Json; $state.installed = [ordered]@{ exp_dir = $r.exp_dir; plugins = @($r.files.PSObject.Properties.Name | Where-Object { $_ -like '*.esm' }) } } catch { } }
$pl = Join-Path $env:LOCALAPPDATA 'Starfield\Plugins.txt'
# plain strings: Get-Content's lines carry PSPath, PSDrive and Provider, which ConvertTo-Json writes out (a 3 MB state.json)
if (Test-Path $pl) { $state.plugins_txt = @(Get-Content $pl | Where-Object { $_ -and -not $_.StartsWith('#') } | ForEach-Object { "$_" }) }
if ($Ask) { $state.description_pending = $true }   # the box opens after this write; read the folder again later
$state | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Out 'state.json') -Encoding utf8
# the description box (-Ask): after the capture and after state.json is written, so the snapshot is readable while the box
# waits; $env:FO4SF_ASK_ANSWER stands in for the typed text in tests (no window). The owner's play test (2026-10-22): three
# boxes sat waiting unseen (visible=False: look_hotkey started this script hidden, and a hidden start hides the first
# window; a visible start instead put an empty console over the game). The start stays hidden and the box shows itself
# (SW_SHOW, which a hidden start does not override, re-applied every half second while the window is invisible), then
# takes the foreground (the hotkey hands it the right, AllowSetForegroundWindow; AttachThreadInput when
# Windows still refuses; no synthetic key ever), blinking on the taskbar if even that fails.
# Unanswered after -AskTimeout seconds (default 600) it closes and leaves describe_later.txt in the folder and the folder in
# <snapshots>\describe_later.txt: type the description into the folder's description.txt afterwards.
if ($Ask) {
  $text = $null; $timedOut = $false
  if ($null -ne $env:FO4SF_ASK_ANSWER) { $text = $env:FO4SF_ASK_ANSWER; $timedOut = ($env:FO4SF_ASK_ANSWER -eq '<timeout>') }
  else {
    try {
      Add-Type -AssemblyName System.Windows.Forms, System.Drawing
      Add-Type -Namespace W -Name F -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr h, System.IntPtr pid);
[DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
[DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll")] public static extern bool BringWindowToTop(System.IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int cmd);
[DllImport("user32.dll")] public static extern bool FlashWindow(System.IntPtr h, bool invert);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr h);
public static bool Front(System.IntPtr h) {
  ShowWindow(h, 5); ShowWindow(h, 9);                                        // SW_SHOW, SW_RESTORE
  if (SetForegroundWindow(h)) return true;
  // never a synthetic key (the Alt-key nudge): it would reach the game, and this tool sends nothing to it (Codex on #463)
  uint fg = GetWindowThreadProcessId(GetForegroundWindow(), System.IntPtr.Zero), me = GetCurrentThreadId();
  bool att = fg != 0 && fg != me && AttachThreadInput(me, fg, true);
  bool ok = SetForegroundWindow(h); BringWindowToTop(h);
  if (att) AttachThreadInput(me, fg, false);
  if (!ok) FlashWindow(h, true);
  return ok || GetForegroundWindow() == h;
}
'@
      $f = New-Object System.Windows.Forms.Form
      $f.Text = 'FO4SF report: what is wrong?'; $f.TopMost = $true; $f.StartPosition = 'CenterScreen'; $f.ShowInTaskbar = $true
      $f.Size = New-Object System.Drawing.Size 520, 300; $f.FormBorderStyle = 'FixedDialog'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
      $lbl = New-Object System.Windows.Forms.Label
      $lbl.Text = 'The screenshot is saved. Describe what is wrong (what you did, what you expected, what happened):'
      $lbl.SetBounds(10, 8, 490, 34)
      $tb = New-Object System.Windows.Forms.TextBox
      $tb.Multiline = $true; $tb.ScrollBars = 'Vertical'; $tb.AcceptsReturn = $true; $tb.SetBounds(10, 44, 485, 160)
      $ok = New-Object System.Windows.Forms.Button; $ok.Text = 'Save'; $ok.SetBounds(300, 215, 90, 30); $ok.DialogResult = 'OK'
      $skip = New-Object System.Windows.Forms.Button; $skip.Text = 'Screenshot only'; $skip.SetBounds(395, 215, 100, 30); $skip.DialogResult = 'Cancel'
      $f.Controls.AddRange(@($lbl, $tb, $ok, $skip)); $f.AcceptButton = $null; $f.CancelButton = $skip
      $script:fronted = $false; $script:tries = 0; $script:timedOut = $false; $deadline = (Get-Date).AddSeconds($AskTimeout)
      $tick = New-Object System.Windows.Forms.Timer; $tick.Interval = 500
      $tick.Add_Tick({
        if ((Get-Date) -ge $deadline) { $script:timedOut = $true; $tick.Stop(); $f.DialogResult = 'Cancel'; $f.Close(); return }
        if (-not [W.F]::IsWindowVisible($f.Handle)) { [W.F]::ShowWindow($f.Handle, 5) | Out-Null; $script:shown++ }   # SW_SHOW
        # keep trying for the first 10 s: the game may take the foreground back while it minimizes
        if ($script:tries -lt 20 -and [W.F]::GetForegroundWindow() -ne $f.Handle) { $script:tries++; $script:fronted = [W.F]::Front($f.Handle) -or $script:fronted; $tb.Focus() | Out-Null }
      })
      $script:shown = 0
      $f.Add_Load({ $tick.Start() })                                         # runs even when the start hid the window
      $f.Add_Shown({ $script:fronted = [W.F]::Front($f.Handle); $f.Activate(); $tb.Focus() | Out-Null })
      if ($f.ShowDialog() -eq 'OK') { $text = $tb.Text }
      $tick.Stop(); $tick.Dispose(); $f.Dispose()
      $timedOut = $script:timedOut
      $state.description_box_foreground = $script:fronted
      $state.description_box_reshown = $script:shown
    } catch { $state.description_error = "$_" }
  }
  if ($timedOut) {
    $text = $null
    $state.description_timed_out = $AskTimeout
    Set-Content -LiteralPath (Join-Path $Out 'describe_later.txt') -Encoding utf8 -Value ("The description box got no answer within $AskTimeout s " +
      "(it may have opened behind the game). Type what was wrong into description.txt in this folder.")
    Add-Content -LiteralPath (Join-Path (Split-Path -Parent $Out) 'describe_later.txt') -Value $Out -Encoding utf8
  }
  if ($text -and $text.Trim() -and -not $timedOut) {
    $state.description = $text.Trim()
    Set-Content -LiteralPath (Join-Path $Out 'description.txt') -Value $state.description -Encoding utf8
    $state.description_file = 'description.txt'
  } else { $state.description = $null }
  $state.Remove('description_pending')
  $state | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Out 'state.json') -Encoding utf8
}
# no screenshot, no form: the link promises one on the clipboard (Codex's review of #350); the local failure stays recorded
if ($Submit -and -not $shotOk) { $state.submit_skipped = 'no screenshot' }
if ($Submit -and $shotOk) {
  $repo = $(if ($env:FO4SF_REPORT_REPO) { $env:FO4SF_REPORT_REPO } else { 'fo4sf/fo4-to-starfield' })
  $desc = $(if ($state.description) { $state.description } else { '' })
  $first = ($desc -split "`r?`n")[0]
  $title = '[Player report]: ' + $(if ($first) { $first.Substring(0, [Math]::Min(80, $first.Length)) } else { 'screenshot' })
  $where = $(if ($state.bridge.pos) { "pos $($state.bridge.pos -join ' ') cell $($state.bridge.cell) world $($state.bridge.world)" } else { '' })
  $ports = @($state.plugins_txt | Where-Object { "$_".StartsWith('*') } | ForEach-Object { "$_".Substring(1) } | Where-Object { $_ -like 'FO4*' })   # '*' = enabled
  $cap = "Captured $($state.taken); game running: $($state.game_running). Port plugins active: $(if ($ports) { $ports -join ', ' } else { 'none found' }).`n`nPaste the screenshot here (it is on your clipboard: Ctrl+V)."
  $fields = [ordered]@{ template = 'community_report.yml'; title = $title; what = $desc; where = $where; capture = $cap }
  $q = ($fields.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString(($_.Value + '').Substring(0, [Math]::Min(1500, ($_.Value + '').Length))))" }) -join '&'
  $url = "https://github.com/$repo/issues/new?$q"
  Set-Content -LiteralPath (Join-Path $Out 'issue_url.txt') -Value $url -Encoding utf8
  $state.issue_url = 'issue_url.txt'
  if (-not $env:FO4SF_SUBMIT_DRYRUN) {
    try { Add-Type -AssemblyName System.Windows.Forms, System.Drawing
          $img = [System.Drawing.Image]::FromFile($shot); [System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose() }
    catch { $state.clipboard_error = "$_" }
    try { Start-Process $url } catch { $state.submit_error = "$_" }
  }
}
if ($Submit) { $state | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Out 'state.json') -Encoding utf8 }
$posTxt = $(if ($state.bridge.pos) { "pos $($state.bridge.pos -join ' ') cell $($state.bridge.cell) world $($state.bridge.world) loaded $($state.bridge.loaded) age $($state.bridge.age_s)s" } else { "bridge: $($state.bridge.why)" })
"snapshot ${Out}: game=$($state.game_running) foreground=$($state.game_foreground) screen=$($state.screen)$(if ($state.description) { ' described=yes' }) | $posTxt"
if (-not $shotOk) { exit 3 }
