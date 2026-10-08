# Walk every route from routes.py in the game and record positions + a screenshot per route.
# usage: route_run.ps1 -Routes routes.json -Out <dir> [-First 0] [-Count 999]
# Requires: Starfield in front, in the route's cell, console CLOSED. Every keystroke goes through input.ps1's foreground
# guard (stops if anything else is in front). Results: <Out>\results.jsonl (one line per route), <Out>\r<k>.png.
param([string]$Routes, [string]$Out, [int]$First = 0, [int]$Count = 999)
$env:LEGACY = '1'
if (-not $env:FO4SF_PYTHON) { $env:FO4SF_PYTHON = 'C:\Modding\venv-render\Scripts\python.exe' }   # OCR prep needs numpy
$here = $PSScriptRoot
$i = Join-Path $here 'input.ps1'; $shot = Join-Path $here 'shot.ps1'; $readpos = Join-Path $here 'readpos.ps1'
New-Item -ItemType Directory -Force $Out | Out-Null
$res = Join-Path $Out 'results.jsonl'
$list = (Get-Content $Routes -Raw | ConvertFrom-Json).routes
$inv = [Globalization.CultureInfo]::InvariantCulture

function Read-Pos {
  # readpos leaves the console closed; if a read fails the console was probably open: close it once and retry
  $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos
  if ($p -eq 'fail') {
    powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq 'key:grave|wait:900' | Out-Null
    $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos
  }
  # OCR sometimes drops or shifts a column (e.g. "91.43 0.52 91.43"): re-read up to twice when x equals z or a value is missing
  for ($n = 0; $n -lt 2; $n++) {
    $v = "$p".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    if ($v.Count -eq 3 -and $v[0] -ne $v[2]) { break }
    $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos
  }
  return $p
}

for ($k = $First; $k -lt [Math]::Min($list.Count, $First + $Count); $k++) {
  $r = $list[$k]
  $x, $y, $z = $r.start | ForEach-Object { $_.ToString($inv) }
  $h = $r.heading.ToString($inv)
  $seq = "key:grave|wait:1000|type:player.setpos x $x|key:enter|wait:350|type:player.setpos y $y|key:enter|wait:350|" +
         "type:player.setpos z $z|key:enter|wait:350|type:player.setangle z $h|key:enter|wait:350|" +
         "type:player.setangle x 10|key:enter|wait:400|key:grave|wait:1800"
  powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq $seq | Out-Null
  if ($LASTEXITCODE -ne 0) { "guard stopped at route $k"; break }
  $p0 = Read-Pos
  if ($r.use) { powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq 'key:e|wait:2200' | Out-Null }
  powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq "hold:w,$($r.walk_ms)|wait:700" | Out-Null
  if ($LASTEXITCODE -ne 0) { "guard stopped at route $k"; break }
  $p1 = Read-Pos
  powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out (Join-Path $Out "r$k.png") | Out-Null
  $line = @{ index = $k; ref = $r.ref; kind = $r.kind; start_read = $p0; end_read = $p1 } | ConvertTo-Json -Compress
  Add-Content $res $line
  "route $k $($r.kind) $($r.ref): $p0 -> $p1"
}
