"""FOCCPing (sfse/FOCCPing), the B0 bridge spike's SFSE plugin, as text: its one native matches the declaration in
scripts/combined_probes/FOCC.psc, it binds the native on SFSE's PostDataLoad message through the GameVM singleton (no
hook), its xmake project takes the libxse CommonLibSF checkout through the library's own plugin rule, its build script
drives xmake in the loaded MSVC environment, and the README and the runbook's B0-2 card name the format-5 Address
Library and the libxse commits. No compiler or library here (docs/combined-core-cpp-port.md section 4;
docs/spikes/combined-core-probes.md section B0)."""
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FOCCPing"
LIBXSE = "9d090c4"
SHARED = "9fbb74d"


class PingPluginTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    pch = (PLUGIN / "src" / "pch.h").read_text(encoding="utf-8")
    xmake = (PLUGIN / "xmake.lua").read_text(encoding="utf-8")
    build = (PLUGIN / "build.ps1").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    psc = (ROOT / "scripts" / "combined_probes" / "FOCC.psc").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "spikes" / "combined-core-probes.md").read_text(encoding="utf-8")
    port = (ROOT / "docs" / "combined-core-cpp-port.md").read_text(encoding="utf-8")

    def test_the_native_matches_the_papyrus_declaration(self):
        self.assertIn("\nint Function Ping(int v) global native\n", self.psc)             # the script side
        self.assertIn("Scriptname FOCC Hidden Native", self.psc)
        # a global native: std::monostate in the self slot, int in and out, answers v + 1
        self.assertIn("std::int32_t Ping(std::monostate, std::int32_t a_v)", self.main)
        self.assertIn("return a_v + 1;", self.main)
        # no tasklet flag: libxse would call one of an overloaded virtual pair whose MSVC slot order is unproven
        self.assertIn('vm->BindNativeMethod("FOCC"sv, "Ping"sv, &Ping, std::nullopt, false);', self.main)
        self.assertNotIn("SetCallableFromTasklets(", self.main.replace("// tasklet flag libxse would also call SetCallableFromTasklets,", ""))
        code = "\n".join(l for l in self.main.splitlines() if not l.lstrip().startswith("//"))
        self.assertEqual(code.count("BindNativeMethod("), 1)

    def test_the_native_is_bound_on_post_data_load_through_the_singleton_without_a_hook(self):
        self.assertIn("SFSE_PLUGIN_LOAD(const SFSE::LoadInterface* a_sfse)", self.main)
        load = self.main[self.main.index("SFSE_PLUGIN_LOAD("):]
        self.assertIn("SFSE::Init(a_sfse, { .trampoline = false, .hook = false });", load)
        self.assertLess(load.index("SFSE::Init("), load.index("RegisterListener(&OnMessage)"))
        self.assertIn("if (a_msg && a_msg->type == SFSE::MessagingInterface::kPostDataLoad) {", self.main)
        self.assertIn("const auto game = RE::GameVM::GetSingleton();", self.main)
        self.assertIn("const auto vm = game->GetVM();", self.main)
        self.assertIn("if (!vm) {", self.main)                                           # no VM, no bind, no crash
        self.assertEqual(load.count("return true;"), 4)                                   # loaded either way, the log tells
        code = "\n".join(l for l in self.main.splitlines() if not l.lstrip().startswith("//"))   # the comments cite the old hook
        for banned in ("static ", "new ", "malloc", "WriteProcessMemory", "REL::Relocation", "THook",
                       "SetPapyrusCallback", "SFSEPluginVersion", "SFSE_PLUGIN_VERSION", "write_call"):
            self.assertNotIn(banned, code, banned)                                       # no hook, no allocation, no version data of its own
        self.assertIn('#include "pch.h"', self.main)
        self.assertEqual(self.pch.count("#include"), 2)
        for inc in ('#include "RE/Starfield.h"', '#include "SFSE/SFSE.h"'):
            self.assertIn(inc, self.pch)
        # the log lines the runbook's card reads
        for line in ("FOCCPing loaded on runtime {}", "listening for PostDataLoad; FOCC.Ping binds then", "bound FOCC.Ping",
                     "no script VM at PostDataLoad: FOCC.Ping not bound", "ping {} -> {}"):
            self.assertIn(line, self.main, line)
        self.assertIn("FOCCPing.log", self.readme)
        self.assertIn("FOCCPing.log", self.runbook)

    def test_nothing_is_called_before_it_is_checked(self):
        """FAL-216: the version guard, the plugin's own Address Library read with the libxse cross-check, the game's
        NativeFunctionBase vtable and five slots, and the GameVM and VM types, all before the bind (PR #704's checks)."""
        load = self.main[self.main.index("SFSE_PLUGIN_LOAD("):]
        self.assertIn("constexpr REL::Version kRuntime{ 1, 16, 244, 0 };", self.main)
        guard = load.index('Refuse("version"')
        checks = load.index('!CheckImage() || !ReadAddressLibrary(dir / "versionlib-1-16-244-0.bin") || !CheckNativeFunctionBase()')
        self.assertLess(guard, checks)
        self.assertLess(checks, load.index("RegisterListener(&OnMessage)"))
        self.assertLess(checks, load.index("g_ready = true;"))
        bind = self.main[self.main.index("void BindPing()"):self.main.index("void OnMessage(")]
        self.assertTrue(bind.index("if (!g_ready) {") < bind.index('CheckObject("GameVM"') <
                        bind.index('CheckObject("VirtualMachine"') < bind.index("InImage(slot[kBindSlot], 1)") <
                        bind.index("vm->BindNativeMethod("))
        ids = {"GameVM.Singleton": 937585, "GameVM.RTTI": 865426, "BSScript.Internal.VirtualMachine.RTTI": 870795,
               "BSStringPool.GetEntry": 1186742, "BSStringPool.Entry.Release": 139340,
               "NativeFunctionBase.vtable": 480710, "NativeFunctionBase.RTTI": 853245,
               "NativeFunctionBase.GetParam": 138061, "NativeFunctionBase.Call": 138074,
               "NativeFunctionBase.GetSourceFilename": 138065, "NativeFunctionBase.GetParamInfo": 138067,
               "NativeFunctionBase.Unk_15": 138068, "BSScript.Stack.GetPageForFrame": 138020,
               "BSScript.StackFrame.GetVariable": 84986}
        for name, value in ids.items():
            self.assertIn(f'{{ "{name}", {value}, ', self.main, name)
            self.assertIn(str(value), self.readme, name)
        self.assertEqual(self.main.count('{ "'), len(ids))
        for slot, name in (("0x06", "kNativeGetParam"), ("0x0F", "kNativeCall"), ("0x10", "kNativeGetSourceFilename"),
                           ("0x14", "kNativeGetParamInfo"), ("0x15", "kNativeUnk15")):
            self.assertIn(f"{{ {slot}, {name} }}", self.main)
        self.assertIn("constexpr std::size_t  kBindSlot = 0x1E;", self.main)
        self.assertIn("const auto viaLibrary = REL::ID(kIds[i].id).offset();", self.main)
        for step in ('Refuse("version"', 'Refuse("image"', 'Refuse("address_library"', 'Refuse("id"', 'Refuse("rtti"',
                     'Refuse("slots"', 'Refuse("object"'):
            self.assertIn(step, self.main, step)
            self.assertIn("refuse step=" + step.split('"')[1], self.readme, step)
        self.assertIn('REX::ERROR("refuse step={} {}", a_step, a_what);', self.main)

    def test_the_xmake_project_follows_the_libxse_template_and_installs_nothing(self):
        self.assertIn('includes("lib/commonlibsf")', self.xmake)
        self.assertIn('set_project("FOCCPing")', self.xmake)
        self.assertIn('set_languages("c++23")', self.xmake)
        self.assertIn('add_rules("commonlibsf.plugin", {', self.xmake)                  # the rule writes the SFSE version data
        self.assertIn('name = "FOCCPing",', self.xmake)
        self.assertIn('set_values("commonlib.plugin.install", false)', self.xmake)
        self.assertIn('set_pcxxheader("src/pch.h")', self.xmake)
        for banned in ("XSE_SF_GAME_PATH\")", "add_requires(", "Data/SFSE", "SFSE/Plugins"):
            self.assertNotIn(banned, self.xmake.replace("-- the rule's after_build would copy the dll into a game or mods folder named by XSE_SF_GAME_PATH or", ""))
        # nothing of CommonLibSF, SFSE or the game is in the folder
        files = sorted(os.path.relpath(os.path.join(d, f), PLUGIN) for d, _, fs in os.walk(PLUGIN) for f in fs)
        self.assertEqual(files, ["README.md", "build.ps1", os.path.join("src", "main.cpp"), os.path.join("src", "pch.h"), "xmake.lua"])

    def test_the_build_drives_xmake_against_the_pinned_checkout_and_never_overwrites(self):
        self.assertIn("[Parameter(Mandatory)][string]$Out, [string]$Lib = 'D:\\Modding\\tools\\libxse-commonlibsf', [string]$Env = '', [string]$Sdk = ''", self.build)
        self.assertIn("if ($Env) {\n  if (-not (Test-Path $Env)) { \"-Env $Env not found\"; exit 1 }\n  . $Env\n}", self.build)
        self.assertIn("$PinnedLib = '9d090c4c521f4f2c1aa00bb05923c380d47ae596'", self.build)
        self.assertIn("$PinnedShared = '9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d'", self.build)
        self.assertIn("if ([int]$Matches[1] -lt 3)", self.build)                        # libxse's set_xmakever("3.0.0")
        self.assertIn("(& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''", self.build)      # x64 only, as FOCCSidecar
        self.assertIn("if ($banner -notmatch '\\bx64\\b')", self.build)
        self.assertIn("'lib\\commonlib-shared\\src\\REL\\IDDB.cpp'", self.build)         # the submodule is there (the format-5 reader)
        # xmake's MSVC root from the PC's environment: VC and Windows Kits junctions in the staging folder
        self.assertIn("$vcRoot = Split-Path (Split-Path (Split-Path $env:VCToolsInstallDir.TrimEnd('\\', '/')))", self.build)
        self.assertIn("$kits = Split-Path $env:WindowsSdkDir.TrimEnd('\\', '/')", self.build)
        self.assertIn("New-Junction (Join-Path $Sdk 'Windows Kits') $kits", self.build)
        self.assertIn("New-Junction (Join-Path $proj 'lib\\commonlibsf') (Resolve-Path $Lib).Path", self.build)
        # a re-run into the same -Out after exit 90/91 keeps a junction with the same target, refuses another
        self.assertIn("function New-Junction([string]$Path, [string]$Target) {", self.build)
        self.assertIn("if (-not $have -or $have.TrimEnd('\\', '/') -ieq $Target.TrimEnd('\\', '/')) { \"reusing $Path\"; return }", self.build)
        self.assertEqual(self.build.count("New-Item -ItemType Junction"), 1)              # only through the helper
        # git's stderr under the Stop preference is terminating on PowerShell 5.1: the two reads run under SilentlyContinue
        self.assertIn("$eap = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'\n"
                      "  $libCommit = (& git.exe -C $Lib rev-parse HEAD 2>$null) -join ''\n"
                      "  $sharedCommit = (& git.exe -C (Join-Path $Lib 'lib\\commonlib-shared') rev-parse HEAD 2>$null) -join ''\n"
                      "  $ErrorActionPreference = $eap\n", self.build)
        self.assertIn('if (-not $libCommit) { $libCommit = $null; "note: -Lib $Lib is not a git checkout', self.build)
        self.assertIn("Remove-Item Env:XSE_SF_MODS_PATH -ErrorAction SilentlyContinue", self.build)
        self.assertIn("Remove-Item Env:XSE_SF_GAME_PATH -ErrorAction SilentlyContinue", self.build)
        self.assertIn('"xmake.exe f -y -p windows -a x64 -m releasedbg --toolchain=msvc$sdkArg 2>&1 || exit /b 90",', self.build)
        self.assertIn('"xmake.exe build -y FOCCPing 2>&1 || exit /b 91",', self.build)   # stderr merged inside cmd.exe
        self.assertIn("'build\\windows\\x64\\releasedbg\\FOCCPing.dll'", self.build)
        self.assertIn("this script never overwrites", self.build)
        self.assertNotIn("Remove-Item $", self.build)
        self.assertNotIn("Data\\SFSE\\Plugins\\'", self.build)                            # it installs nothing
        for text in (self.readme, self.runbook):                                        # the PC's setup, Install 28 Oct
            self.assertIn("libxse", text)
            self.assertIn(LIBXSE, text)
            self.assertIn(SHARED, text)
            self.assertIn("D:\\Modding\\tools\\libxse-commonlibsf", text)
            self.assertIn("-Env D:\\Modding\\tools\\msvc_env.ps1", text)
            self.assertNotIn("CommonLibSF-install -Vcpkg", text)                         # the morning's cmake line is gone
            self.assertIn("Format-Hex <", text)                                        # the address library format check
            self.assertIn("| Select-Object -First 1", text)                            # runs on Windows PowerShell 5.1
            self.assertNotIn("-Count 4", text)                                         # Format-Hex -Count is PowerShell 6.2+
            self.assertIn("05 00 00 00", text)                                         # format 5, the file on the PC
        self.assertIn("RUNTIME_LATEST` (1.16.244 at `9d090c4`", self.readme)                 # include/SFSE/Version.h at the pin
        self.assertNotIn("1.16.236", self.readme)
        self.assertIn("`FOCCPing v0.3.0.0` (the library's own, from `SFSE::Init`)", self.readme)   # the log's first line
        self.assertIn('set_version("0.3.0")', self.xmake)
        self.assertIn("the same `-Out` runs again", self.readme)
        # a wrong offset is a crash with no message box, not "cannot crash"
        self.assertIn('"Failed to find offset for Address Library ID"', self.runbook)
        self.assertIn("faults at the bind", self.runbook)
        self.assertNotIn("cannot crash", self.runbook)
        self.assertIn("libxse/commonlibsf", self.port)
        self.assertIn("Unsupported address library format: 5", self.port)


if __name__ == "__main__":
    unittest.main()
