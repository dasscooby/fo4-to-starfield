# Compile FO4SFBorder.dll with MSVC into a new folder; never install it into the game. build.sh is the mingw-w64
# cross-build of the same source; this is the PC's route (FAL-246: the PC has MSVC, not mingw).
# Usage: powershell -File build.ps1 -Out <new folder> [-Env <x64 MSVC environment script>]
# Needs PluginAPI.h next to this file: powershell -File ..\FOCCSidecar\fetch_pluginapi.ps1 -Dest <this folder>
# (pinned commit, sha256 checked, kept out of git). The static CRT (/MT) keeps the dll free of a runtime install, as
# build.sh's -static does. /W4 without /WX: the source was first written for g++ -Werror, and this is its first MSVC
# build, so warnings are recorded in cl_output.txt rather than stopping the build.
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
$cpp = Join-Path $src 'FO4SFBorder.cpp'
$api = Join-Path $src 'PluginAPI.h'
if (-not (Test-Path -LiteralPath $api -PathType Leaf)) {
  throw "PluginAPI.h missing in $src : run ..\FOCCSidecar\fetch_pluginapi.ps1 -Dest `"$src`" first"
}
$inputs = [ordered]@{
  'FO4SFBorder.cpp' = $cpp; 'scan.h' = (Join-Path $src 'scan.h'); 'FO4SFBorder.ini' = (Join-Path $src 'FO4SFBorder.ini')
  'PluginAPI.h' = $api; '../FOCCSidecar/runtime_dir.h' = (Join-Path $src '..\FOCCSidecar\runtime_dir.h')
}
$inputHashes = [ordered]@{}
foreach ($k in $inputs.Keys) {
  if (-not (Test-Path -LiteralPath $inputs[$k] -PathType Leaf)) { throw "Missing $($inputs[$k])" }
  $inputHashes[$k] = (Get-FileHash -LiteralPath $inputs[$k] -Algorithm SHA256).Hash.ToLowerInvariant()
}
$pin = Join-Path $src 'PluginAPI.pin.json'
$pluginapi = if (Test-Path -LiteralPath $pin) { Get-Content -LiteralPath $pin -Raw | ConvertFrom-Json } else { $null }
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
$dll = Join-Path $Out 'FO4SFBorder.dll'
$command = "cl.exe /nologo /std:c++20 /EHsc /O2 /W4 /MT /utf-8 /LD /Fo`"$obj\\`" /Fe`"$dll`" `"$cpp`" " +
  "/link /NOLOGO shell32.lib ole32.lib uuid.lib"
$bat = Join-Path $Out 'build.cmd'
@('@echo off', 'setlocal DisableDelayedExpansion') + $enter +
  @("cd /d `"$src`" || exit /b 91", $command, 'exit /b %ERRORLEVEL%') |
  Set-Content -LiteralPath $bat -Encoding ASCII
$log = Join-Path $Out 'cl_output.txt'
& cmd.exe /d /c $bat 2>&1 | Tee-Object -FilePath $log
$code = $LASTEXITCODE
if ($code -ne 0 -or -not (Test-Path -LiteralPath $dll -PathType Leaf)) {
  throw "MSVC build failed ($code); partial outputs preserved in $Out (paste cl_output.txt whole)"
}
foreach ($k in $inputs.Keys) {
  if ((Get-FileHash -LiteralPath $inputs[$k] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputHashes[$k]) {
    throw "Source changed during compilation: $k; output retained without an attestation"
  }
}
Copy-Item -LiteralPath $inputs['FO4SFBorder.ini'] -Destination (Join-Path $Out 'FO4SFBorder.ini')
$build = [ordered]@{
  plugin = 'FO4SFBorder'; built_at = (Get-Date).ToUniversalTime().ToString('o'); commit = $commit
  compiler = $banner; toolchain = $toolchain; compiler_line = $command; sources = $inputHashes
  pluginapi = $pluginapi
  build_script_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
  output = [ordered]@{ path = $dll; sha256 = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash.ToLowerInvariant(); bytes = (Get-Item -LiteralPath $dll).Length }
}
$build | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Out 'build.json') -Encoding UTF8
"built $dll; sha256 $($build.output.sha256); no install performed"
