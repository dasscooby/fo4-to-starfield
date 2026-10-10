# Full test cycle: close Starfield, redeploy staging, launch, load the last save, clear dialogs, coc into a cell, screenshot.
# usage: cycle.ps1 -Staging <staging dir> -Starfield <game dir> -Cell FO4Port_Vault111Cryo -Shot <out.png> [-CellJson <cell.json>]
# -CellJson: enter the cell with coc.ps1, which verifies the arrival at the cell's COC marker (needs FO4SF_PYTHON = a Python
# with Pillow); exit 4 if the jump did not happen. Without it, coc is typed blind as before.
# Starfield's "Use of certain console commands will disable achievements." popup (first console command of a session)
# blocks the console until OK (E). It is detected by OCR and dismissed only when it is on screen: a blind E in game can
# start a conversation (2026-10-10: the popup swallowed the coc; a fixed-time E had missed it).
param([Parameter(Mandatory)][string]$Staging, [Parameter(Mandatory)][string]$Starfield, [string]$Cell = 'FO4Port_Vault111Cryo',
      [string]$Shot = (Join-Path $env:TEMP 'fo4sf_cycle.png'), [string]$CellJson = '')
$repo = Split-Path (Split-Path $PSScriptRoot); $sf = $Starfield
$i = (Join-Path $PSScriptRoot 'input.ps1'); $env:LEGACY = '1'
$p = Get-Process Starfield -ErrorAction SilentlyContinue
$pidFile = Join-Path $PSScriptRoot 'cycle_pid.txt'           # local only: the PID of the game this script launched
$own = if (Test-Path $pidFile) { [int](Get-Content $pidFile) } else { 0 }
if ($p -and $p.Id -ne $own) { "Starfield is running but was not started by cycle.ps1 (the user's own session): not closing it"; exit 3 }
if ($p) { $p.CloseMainWindow() | Out-Null; Start-Sleep 8; $p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -Confirm:$false }; Start-Sleep 4 }
python -I "$repo\scripts\deploy_starfield.py" uninstall --starfield $sf | Out-Null
python -I "$repo\scripts\deploy_starfield.py" install --staging $Staging --starfield $sf | Select-Object -Last 1
Start-Process 'steam://rungameid/1716740'
$deadline = (Get-Date).AddSeconds(150); while ((Get-Date) -lt $deadline) { $q = Get-Process Starfield -ErrorAction SilentlyContinue; if ($q) { $q.Id | Set-Content $pidFile; break }; Start-Sleep 3 }
Start-Sleep 30

function Send($seq) {
  powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq $seq | Out-Null
  if ($LASTEXITCODE -ne 0) { "input guard stopped the sequence (someone else has focus)"; exit 2 }
}
function Clear-AchievementsPopup {
  # true if the popup was on screen and E was sent to close it
  $tmp = Join-Path $env:TEMP 'fo4sf_popup.png'
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'shot.ps1') -Out $tmp | Out-Null
  $text = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'ocr.ps1') -Image $tmp -X 390 -Y 285 -W 500 -H 60
  if (($text | Out-String) -match 'achievement') { Send 'hold:e,300|wait:1500'; return $true }
  return $false
}

# main menu: Continue, clear load-time notices, wait for the save to load
Send 'click:768,432|wait:6000|key:up|wait:700|key:enter|wait:2500|hold:e,300|wait:2500|hold:e,300|wait:45000'
# first console command of the session (raises the popup on saves with achievements still on)
Send 'key:grave|wait:1500|type:fov 90|wait:300|key:enter|wait:2500|key:grave|wait:1500'
Clear-AchievementsPopup | Out-Null
if ($CellJson) {
  $name = $Cell -replace '^FO4Port_', ''
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'coc.ps1') -Cell $name -CellJson $CellJson
  if ($LASTEXITCODE -ne 0) { "coc.ps1 could not verify the arrival in $Cell (exit $LASTEXITCODE)"; exit 4 }
} else {
  Send "key:grave|wait:1500|key:back|key:back|key:back|type:coc $Cell|wait:400|key:enter|wait:3000"
  if (Clear-AchievementsPopup) {                              # the popup blocked the coc: send it once more
    Send "key:grave|wait:1500|key:back|key:back|key:back|type:coc $Cell|wait:400|key:enter|wait:3000"
  }
  Start-Sleep 37                                               # cell load
}
powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\shot.ps1 -Out $Shot | Out-Null
"cycle done -> $Shot"
