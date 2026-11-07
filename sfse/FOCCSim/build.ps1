# Compile the portable CLI into a new folder; never install it into the game.
# Usage: powershell -File build.ps1 -Out <new folder> [-Env <x64 MSVC environment script>]
param([Parameter(Mandatory)][string]$Out, [string]$Env = '')
$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot
if (-not [IO.Path]::IsPathRooted($Out)) { $Out = Join-Path (Get-Location).Path $Out }
$Out = [IO.Path]::GetFullPath($Out)
if (Test-Path -LiteralPath $Out) {
  throw "-Out already exists: choose a NEW folder; nothing is overwritten or deleted ($Out)"
}
# cmd expands percent variables even in quoted paths. Fail explicitly rather than build another path.
foreach ($p in @($src, $Out, $Env)) {
  if ($p -match '[%\r\n]') { throw 'Batch paths containing percent or a newline are unsupported' }
}
$cpp = @(Get-ChildItem -LiteralPath $src -Filter '*.cpp' -File | Sort-Object Name)
if (-not $cpp.Count) { throw "No C++ sources in $src" }
$shaCpp = Join-Path $src '..\FOCCSidecar\sha256.cpp'
$shaHeader = Join-Path $src '..\FOCCSidecar\sha256.h'
foreach ($p in @($shaCpp, $shaHeader)) {
  if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing $p" }
}
$headers = @(Get-ChildItem -LiteralPath $src -File |
  Where-Object { $_.Extension -in @('.h', '.hpp') } | Sort-Object Name)
$inputs = @($cpp | ForEach-Object { $_.FullName }) +
  @($headers | ForEach-Object { $_.FullName }) + @($shaCpp, $shaHeader)
$inputHashes = [ordered]@{}
foreach ($p in $inputs) {
  $key = if ($p -eq $shaCpp -or $p -eq $shaHeader) { '../FOCCSidecar/' + [IO.Path]::GetFileName($p) } else { [IO.Path]::GetFileName($p) }
  $inputHashes[$key] = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
}
$commit = (& git -C $src rev-parse HEAD) -join ''
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-f]{40}$') { throw 'Cannot record the source Git commit' }
if ($Env) {
  if (-not (Test-Path -LiteralPath $Env -PathType Leaf)) { throw "-Env not found: $Env" }
  . $Env
}
$clOnPath = Get-Command cl.exe -CommandType Application -ErrorAction SilentlyContinue
$vcvars = $null
$toolchain = 'environment'
if ($clOnPath -and $env:INCLUDE -and $env:LIB) {
  $banner = (& cmd.exe /d /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''
  if ($banner -notmatch '\bx64\b') { throw "MSVC environment is not x64: $banner" }
} else {
  $toolchain = 'visual-studio'
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
  if (-not (Test-Path -LiteralPath $vswhere)) { throw 'No loaded MSVC environment or vswhere; pass -Env' }
  $instance = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
  if (-not $instance) { throw 'No Visual Studio x64 C++ tools found' }
  $vcvars = Join-Path $instance 'VC\Auxiliary\Build\vcvars64.bat'
  if (-not (Test-Path -LiteralPath $vcvars)) { throw "Missing $vcvars" }
  if ($vcvars -match '[%\r\n]') { throw 'Unsupported vcvars path' }
}
New-Item -ItemType Directory -Path $Out | Out-Null
$obj = Join-Path $Out 'obj'
New-Item -ItemType Directory -Path $obj | Out-Null
$enter = if ($vcvars) { @("call `"$vcvars`" >nul || exit /b 90") } else { @() }
$verBat = Join-Path $Out 'compiler-version.cmd'
@('@echo off', 'setlocal DisableDelayedExpansion') + $enter + @('cl.exe 2>&1') |
  Set-Content -LiteralPath $verBat -Encoding ASCII
$banner = (& cmd.exe /d /c $verBat | Select-Object -First 1) -join ''
if ($banner -notmatch '\bx64\b') { throw "Cannot confirm an x64 compiler: $banner" }
$exe = Join-Path $Out 'foccsim.exe'
$quotedSources = ((@($cpp.FullName) + @($shaCpp)) | ForEach-Object { '"' + $_ + '"' }) -join ' '
# /utf-8 makes source string literals portable. /fp:precise is deliberate: no /fp:fast or /fp:contract.
# C4127: intentional constexpr FARM_SLOTS_PER_BEDS/ARRIVAL_SLOWDOWN_POP disable guards; keep /WX for other warnings.
$command = "cl.exe /nologo /std:c++17 /EHsc /O2 /W4 /WX /wd4127 /fp:precise /utf-8 /Fo`"$obj\\`" /Fe`"$exe`" $quotedSources"
$bat = Join-Path $Out 'build.cmd'
@('@echo off', 'setlocal DisableDelayedExpansion') + $enter +
  @("cd /d `"$src`" || exit /b 91", $command, 'exit /b %ERRORLEVEL%') |
  Set-Content -LiteralPath $bat -Encoding ASCII
$log = Join-Path $Out 'cl_output.txt'
& cmd.exe /d /c $bat 2>&1 | Tee-Object -FilePath $log
$code = $LASTEXITCODE
if ($code -ne 0 -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) {
  throw "MSVC build failed ($code); partial outputs preserved in $Out"
}
foreach ($p in $inputs) {
  $key = if ($p -eq $shaCpp -or $p -eq $shaHeader) { '../FOCCSidecar/' + [IO.Path]::GetFileName($p) } else { [IO.Path]::GetFileName($p) }
  if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputHashes[$key]) {
    throw "Source changed during compilation: $key; output retained without an attestation"
  }
}
$build = [ordered]@{
  tool = 'FOCCSim'; built_at = (Get-Date).ToUniversalTime().ToString('o'); commit = $commit
  compiler = $banner; toolchain = $toolchain; compiler_line = $command; sources = $inputHashes
  build_script_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
  output = [ordered]@{ path = $exe; sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant(); bytes = (Get-Item -LiteralPath $exe).Length }
}
$build | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Out 'build.json') -Encoding UTF8
"built $exe; sha256 $($build.output.sha256); no install performed"
