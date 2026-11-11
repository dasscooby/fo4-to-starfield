# FOCCPing, PC build: xmake against the libxse CommonLibSF checkout, into a NEW staging folder; build.json records every
# sha256 and both library commits. Nothing is installed: the dll is copied by hand to <Starfield>\Data\SFSE\Plugins\
# (runbook section B0, job B0-2, the owner's line).
# usage: powershell -File build.ps1 -Out D:\Modding\staging\focc_ping_<date> [-Lib D:\Modding\tools\libxse-commonlibsf]
#        [-Env D:\Modding\tools\msvc_env.ps1] [-Sdk <a Visual Studio-shaped root>]
# -Lib is `git clone --recurse-submodules https://github.com/libxse/commonlibsf` at 9d090c4 (lib/commonlib-shared at
# 9fbb74d); another commit builds and is recorded as such. xmake 3.0 or newer must be on PATH (libxse's set_xmakever).
# -Env is dot-sourced first: the PC's msvc_env.ps1 puts cl.exe and xmake on PATH and sets VCToolsInstallDir and
# WindowsSdkDir. xmake finds MSVC through Visual Studio installs or through `xmake f --sdk=<root>`, a folder shaped like
# a VS root (<root>\VC\Tools\MSVC\<ver> and <root>\Windows Kits\10; xmake's find_build_tools). The PC has no VS install
# and keeps the SDK under msvc\sdk\, so with no -Sdk this script makes that root in the staging folder from the two
# environment variables: two directory junctions, VC and Windows Kits. Refuses an -Out that already holds a
# FOCCPing.dll (never overwrites, never deletes); after a failed configure or build the same -Out runs again, keeping
# the first run's junctions, project copy and xmake state. xmake runs from a batch file with stderr merged, as the
# other sfse build scripts do, into xmake_output.txt (90 = configure, 91 = build).
param([Parameter(Mandatory)][string]$Out, [string]$Lib = 'D:\Modding\tools\libxse-commonlibsf', [string]$Env = '', [string]$Sdk = '')
$ErrorActionPreference = 'Stop'
$PinnedLib = '9d090c4c521f4f2c1aa00bb05923c380d47ae596'
$PinnedShared = '9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d'
function New-Junction([string]$Path, [string]$Target) {
  # a re-run into the same -Out after exit 90/91 finds the first run's junction: kept when it points at the same
  # target (Get-Item's Target on a junction, PowerShell 5.1), refused when it points elsewhere (a different -Lib)
  if (Test-Path $Path) {
    $have = @((Get-Item $Path -Force).Target) -join ''
    if (-not $have -or $have.TrimEnd('\', '/') -ieq $Target.TrimEnd('\', '/')) { "reusing $Path"; return }
    "$Path exists and points at '$have', not ${Target}: pick a new -Out folder (this script never overwrites)"; exit 1
  }
  New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
}
if ($Env) {
  if (-not (Test-Path $Env)) { "-Env $Env not found"; exit 1 }
  . $Env
}
if (-not (Get-Command xmake.exe -ErrorAction SilentlyContinue)) { 'xmake.exe is not on PATH: install xmake 3.0 or newer (xmake.io) or load the environment that has it (-Env)'; exit 1 }
$xmakeVersion = ((& xmake.exe --version) | Select-Object -First 1) -join ''
if ($xmakeVersion -notmatch 'v(\d+)\.') { "xmake --version gave '$xmakeVersion'"; exit 1 }
if ([int]$Matches[1] -lt 3) { "xmake 3.0 or newer is needed (libxse's set_xmakever); found: $xmakeVersion"; exit 1 }
if (Get-Command cl.exe -ErrorAction SilentlyContinue) {
  $banner = (& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''
  if ($banner -notmatch '\bx64\b') { "cl.exe on PATH does not target x64 (banner: $banner); load the x64 environment. Nothing was built."; exit 1 }
} else { $banner = $null }
foreach ($need in 'xmake.lua', 'include\SFSE\SFSE.h', 'lib\commonlib-shared\xmake.lua', 'lib\commonlib-shared\src\REL\IDDB.cpp') {
  if (-not (Test-Path (Join-Path $Lib $need))) { "-Lib $Lib is not a libxse/commonlibsf checkout with its submodule: $need missing (git clone --recurse-submodules https://github.com/libxse/commonlibsf)"; exit 1 }
}
$libCommit = $null; $sharedCommit = $null
if (Get-Command git.exe -ErrorAction SilentlyContinue) {
  # under the Stop preference above, anything git writes to stderr (a -Lib that is a zip extract, not a clone) is a
  # terminating NativeCommandError in Windows PowerShell 5.1 even with 2>$null; the preference is lowered for the
  # two reads so the notes below are reached instead
  $eap = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
  $libCommit = (& git.exe -C $Lib rev-parse HEAD 2>$null) -join ''
  $sharedCommit = (& git.exe -C (Join-Path $Lib 'lib\commonlib-shared') rev-parse HEAD 2>$null) -join ''
  $ErrorActionPreference = $eap
  if (-not $libCommit) { $libCommit = $null; "note: -Lib $Lib is not a git checkout; no library commit goes into build.json" }
  elseif ($libCommit -ne $PinnedLib) { "note: -Lib is at $libCommit, not the pinned $PinnedLib (recorded in build.json)" }
  if (-not $sharedCommit) { $sharedCommit = $null }
  elseif ($sharedCommit -ne $PinnedShared) { "note: lib\commonlib-shared is at $sharedCommit, not the pinned $PinnedShared (recorded in build.json)" }
}
$src = $PSScriptRoot
$sources = @('xmake.lua', 'src\main.cpp', 'src\pch.h')
foreach ($s in $sources) { if (-not (Test-Path (Join-Path $src $s))) { "missing $s in $src"; exit 1 } }
if ($Sdk -and -not (Test-Path (Join-Path $Sdk 'VC\Tools\MSVC'))) { "-Sdk $Sdk has no VC\Tools\MSVC folder: xmake's --sdk takes a Visual Studio-shaped root"; exit 1 }

$dll = Join-Path $Out 'FOCCPing.dll'
if (Test-Path $dll) { "$dll already exists: pick a new -Out folder (this script never overwrites)"; exit 1 }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
if (-not $Sdk -and $env:VCToolsInstallDir -and $env:WindowsSdkDir) {
  # ...\VC\Tools\MSVC\<ver>\ -> ...\VC ; ...\Windows Kits\10\ -> ...\Windows Kits
  $vcRoot = Split-Path (Split-Path (Split-Path $env:VCToolsInstallDir.TrimEnd('\', '/')))
  $kits = Split-Path $env:WindowsSdkDir.TrimEnd('\', '/')
  if ((Split-Path $vcRoot -Leaf) -eq 'VC' -and (Split-Path $kits -Leaf) -eq 'Windows Kits' -and (Test-Path $vcRoot) -and (Test-Path $kits)) {
    $Sdk = Join-Path $Out 'vsroot'
    New-Item -ItemType Directory -Path $Sdk -Force | Out-Null
    New-Junction (Join-Path $Sdk 'VC') $vcRoot
    New-Junction (Join-Path $Sdk 'Windows Kits') $kits
    "MSVC root for xmake: $Sdk (VC -> $vcRoot; Windows Kits -> $kits)"
  } else {
    "note: VCToolsInstallDir ($env:VCToolsInstallDir) and WindowsSdkDir ($env:WindowsSdkDir) do not give a VC and a Windows Kits folder; xmake looks for Visual Studio on its own"
  }
}
# the project is built from a copy: xmake writes build\ and .xmake\ beside xmake.lua, and lib\commonlibsf is a
# directory junction to -Lib (no copy of the library, nothing written into it)
$proj = Join-Path $Out 'proj'
New-Item -ItemType Directory -Path (Join-Path $proj 'src') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $proj 'lib') -Force | Out-Null
foreach ($s in $sources) { Copy-Item (Join-Path $src $s) (Join-Path $proj $s) }
New-Junction (Join-Path $proj 'lib\commonlibsf') (Resolve-Path $Lib).Path
# the commonlibsf.plugin rule would copy the dll into a folder named by these; none here, nothing is installed
Remove-Item Env:XSE_SF_MODS_PATH -ErrorAction SilentlyContinue
Remove-Item Env:XSE_SF_GAME_PATH -ErrorAction SilentlyContinue

$log = Join-Path $Out 'xmake_output.txt'
$bat = Join-Path $Out 'build.cmd'
$sdkArg = $(if ($Sdk) { " --sdk=`"$($Sdk.TrimEnd('\', '/'))`"" } else { '' })
# xmake writes progress to stderr; merged inside cmd.exe so the Stop preference above does not read it as errors.
# -y answers the package prompts (spdlog is fetched and built by xmake's package manager on the first configure)
@("@echo off",
  "cd /d `"$proj`" || exit /b 89",
  "xmake.exe f -y -p windows -a x64 -m releasedbg --toolchain=msvc$sdkArg 2>&1 || exit /b 90",
  "xmake.exe build -y FOCCPing 2>&1 || exit /b 91",
  "exit /b 0") | Set-Content -Encoding ASCII $bat
& cmd.exe /c $bat | Tee-Object -FilePath $log
$code = $LASTEXITCODE
$built = Join-Path $proj 'build\windows\x64\releasedbg\FOCCPing.dll'
if (-not (Test-Path $built)) {
  $found = Get-ChildItem -Path (Join-Path $proj 'build') -Recurse -Filter 'FOCCPing.dll' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($found) { $built = $found.FullName }
}
if ($code -ne 0 -or -not (Test-Path $built)) { "build.cmd exit $code (89 = project folder, 90 = configure, 91 = build); no dll produced. Output: $log"; exit 1 }
Copy-Item $built $dll
$pdb = [System.IO.Path]::ChangeExtension($built, '.pdb')
if (Test-Path $pdb) { Copy-Item $pdb (Join-Path $Out 'FOCCPing.pdb') }

$hash = { param($p) (Get-FileHash -Algorithm SHA256 $p).Hash.ToLower() }
$record = [ordered]@{
  plugin = 'FOCCPing'; plugin_version = '0.3.0'; built_at = (Get-Date).ToUniversalTime().ToString('o')
  xmake = $xmakeVersion; compiler = $banner; sdk_root = $(if ($Sdk) { (Resolve-Path $Sdk).Path } else { $null })
  env_script = $(if ($Env) { (Resolve-Path $Env).Path } else { $null })
  library = [ordered]@{ path = (Resolve-Path $Lib).Path; commit = $libCommit; pinned = $PinnedLib; shared_commit = $sharedCommit; shared_pinned = $PinnedShared }
  sources = [ordered]@{}
  output = [ordered]@{ path = $dll; sha256 = (& $hash $dll); bytes = (Get-Item $dll).Length }
  install = 'copy FOCCPing.dll and versionlib-1-16-244-0.bin (format 5) to <Starfield>\Data\SFSE\Plugins\ by hand (game closed)'
}
foreach ($s in $sources) { $record.sources[$s] = (& $hash (Join-Path $src $s)) }
$json = $record | ConvertTo-Json -Depth 4
$json | Set-Content -Encoding UTF8 (Join-Path $Out 'build.json')
$json
"FOCCPing: built $dll"
exit 0
