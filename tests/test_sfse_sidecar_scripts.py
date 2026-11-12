"""FOCCSidecar's PC scripts and plugin (sfse/FOCCSidecar) as text. check_toolchain.ps1, the runbook's read-only P1-0
check, takes a loaded MSVC environment (cl.exe on PATH with INCLUDE and LIB set, the PC's portable toolchain under
D:\\Modding\\tools since 28 Oct 2026) before it looks for Visual Studio with vswhere. Since FAL-216 the plugin is built
like FO4SFPipboyMenu (PR #704) and FOCCPing: libxse/commonlibsf 9d090c4 through xmake (build.ps1 is theirs with this
plugin's name and its codec files), with the same version guard and refusal lines. No compiler for the dll here."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FOCCSidecar"


class CompilerRouteTests(unittest.TestCase):
    check = (PLUGIN / "check_toolchain.ps1").read_text(encoding="utf-8")
    build = (PLUGIN / "build.ps1").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "spikes" / "combined-core-probes.md").read_text(encoding="utf-8")

    def test_the_check_takes_the_environment_script_and_dot_sources_it(self):
        self.assertIn("[string]$Env = ''", self.check)
        self.assertIn("if ($Env) {\n  if (-not (Test-Path $Env)) { \"-Env $Env not found\"; exit 1 }\n  . $Env\n}", self.check)

    def test_a_loaded_environment_comes_before_vswhere(self):
        env = self.check.index("Get-Command cl.exe -ErrorAction SilentlyContinue")
        self.assertIn("$clOnPath -and $env:INCLUDE -and $env:LIB", self.check)
        self.assertLess(env, self.check.index("vswhere.exe"))

    def test_the_check_reports_which_toolchain_it_found(self):
        self.assertIn("$r.toolchain = 'environment'", self.check)
        self.assertIn("$r.toolchain = 'visual-studio'", self.check)
        # the environment route needs no vcvars64 but must target x64; Visual Studio's route calls vcvars64
        self.assertIn("(($r.toolchain -eq 'environment' -and $r.cl_x64) -or $r.vcvars64)", self.check)
        # the portable SDK is registered nowhere: INCLUDE is read first, the registry second
        self.assertLess(self.check.index("Join-Path $_ 'windows.h'"), self.check.index("HKLM:\\SOFTWARE\\Microsoft\\Windows Kits"))

    def test_the_environment_route_must_target_x64(self):
        # an x86 developer prompt also has cl.exe, INCLUDE and LIB; its dll could not load into Starfield's 64-bit process
        # (Codex on #567). Both scripts read cl.exe's banner through cmd.exe (stderr merged) and want x64 in it.
        for text in (self.check, self.build):
            self.assertIn("(& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''", text)
        self.assertIn("$r.cl_x64 = [bool]($r.cl_banner -match '\\bx64\\b')", self.check)
        self.assertIn("if ($banner -notmatch '\\bx64\\b') {", self.build)
        self.assertIn("Nothing was built.\"; exit 1 }", self.build)

    def test_the_build_is_the_pipboy_menus_with_this_plugins_name_and_codec_files(self):
        pipboy = (ROOT / "sfse" / "FO4SFPipboyMenu" / "build.ps1").read_text(encoding="utf-8")
        body = lambda text: text[text.index("param("):]
        mine = body(self.build).replace("FOCCSidecar", "X").replace("bEnabled=0", "Stage=0")
        theirs = body(pipboy).replace("FO4SFPipboyMenu", "X")
        mine = mine.replace("$sources = @('xmake.lua', 'src\\main.cpp', 'src\\pch.h', 'codec.h', 'runtime_dir.h', 'sha256.h', 'sha256.cpp', 'X.ini')",
                            "$sources = @('xmake.lua', 'src\\main.cpp', 'src\\pch.h', 'src\\world.cpp', 'src\\world.h', 'X.ini')")  # FAL-250 adds world.*
        mine = mine.replace("plugin_version = '0.3.0'", "plugin_version = '0.1.0'")
        self.assertEqual(mine, theirs)
        self.assertIn("$PinnedLib = '9d090c4c521f4f2c1aa00bb05923c380d47ae596'", self.build)
        self.assertIn("$PinnedShared = '9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d'", self.build)
        self.assertIn('"xmake.exe build -y FOCCSidecar 2>&1 || exit /b 91",', self.build)
        self.assertIn("this script never overwrites", self.build)
        self.assertNotIn("Remove-Item $", self.build)
        self.assertNotIn("PluginAPI", self.build)

    def test_the_runbook_and_readme_pass_the_environment(self):
        # the sidecar's two lines (check_toolchain.ps1, build.ps1) and the B0-2 card's FOCCPing build line
        self.assertEqual(self.runbook.count("-Env D:\\Modding\\tools\\msvc_env.ps1"), 3)
        self.assertIn("-Env D:\\Modding\\tools\\msvc_env.ps1", self.readme)
        self.assertIn("sfse\\FOCCSidecar\\build.ps1 -Out D:\\Modding\\staging\\focc_sidecar_", self.readme)


class LibxsePluginTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    xmake = (PLUGIN / "xmake.lua").read_text(encoding="utf-8")
    ini = (PLUGIN / "FOCCSidecar.ini").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")

    def test_the_folder_holds_the_libxse_plugin_and_not_the_old_one(self):
        files = sorted(p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("*") if p.is_file())
        self.assertEqual(files, ["FOCCSidecar.ini", "README.md", "build.ps1", "check_toolchain.ps1", "codec.h",
                                 "fetch_pluginapi.ps1", "runtime_dir.h", "sha256.cpp", "sha256.h", "src/main.cpp", "src/pch.h",
                                 "xmake.lua"])
        self.assertIn('includes("lib/commonlibsf")', self.xmake)
        self.assertIn('add_rules("commonlibsf.plugin", {', self.xmake)
        self.assertIn('set_values("commonlib.plugin.install", false)', self.xmake)
        self.assertIn('add_files("src/**.cpp", "sha256.cpp")', self.xmake)
        self.assertIn('add_includedirs("src", ".")', self.xmake)
        self.assertIn("bEnabled=0", self.ini)

    def test_the_guard_comes_before_anything_is_created_or_registered(self):
        load = self.main[self.main.index("SFSE_PLUGIN_LOAD("):]
        self.assertIn("SFSE::Init(a_sfse, { .trampoline = false, .hook = false });", load)
        self.assertIn("constexpr REL::Version  kRuntime{ 1, 16, 244, 0 };", self.main)
        guard = load.index('Refuse("version"')
        off = load.index('REX::INFO("step=off')
        folder = load.index("if (!RuntimeFolder(dir)) {")
        listen = load.index("RegisterListener(&OnMessage)")
        self.assertTrue(guard < off < folder < listen)
        self.assertEqual(load.count("return true;"), 5)                                   # loaded either way, the log tells
        for step in ('Refuse("version"', 'Refuse("runtime_dir"', 'Refuse("listen"'):
            self.assertIn(step, self.main)
            self.assertIn("refuse step=" + step.split('"')[1], self.readme)
        self.assertIn('REX::ERROR("refuse step={} {}", a_step, a_what);', self.main)

    def test_no_game_address_no_windows_header_and_sfses_message_numbers(self):
        code = "\n".join(re.sub(r"//.*", "", l) for l in self.main.splitlines())   # comments cite the old build
        for banned in ("<windows.h>", "PluginAPI.h", "REL::ID", "REL::Relocation", "GetSingleton", "DeleteFile"):
            self.assertNotIn(banned, code, banned)
        for name, value in (("kPreSaveGame", 4), ("kPostSaveGame", 5), ("kPreLoadGame", 6), ("kPostLoadGame", 7)):
            self.assertIn(f"constexpr std::uint32_t {name} = {value};", self.main)
        self.assertIn("PreSaveGame 4, PostSaveGame 5, PreLoadGame 6, PostLoadGame 7", self.readme)

    def test_the_log_events_the_p1_judge_reads(self):
        for event in ('\\"event\\": \\"pre_save\\", ', '\\"event\\": \\"post_save\\", ', '\\"event\\": \\"pre_load\\", ',
                      '\\"event\\": \\"post_load\\", ', '\\"event\\": \\"load\\", ', '\\"event\\": \\"sfse_post_load\\"'):
            self.assertIn(event, self.main, event)
        for field in ('\\"written\\": ', '\\"found\\": ', '\\"valid\\": ', '\\"counter\\": ', '\\"file\\": '):
            self.assertIn(field, self.main, field)
        self.assertIn('"{{\\"seq\\": {}, \\"time\\": {}, {}}}"', self.main)
        self.assertIn('out << line << "\\r\\n";', self.main)
        self.assertIn("focc::encode_sidecar(a_save, k)", self.main)
        self.assertIn("focc::decode_sidecar(text, a_save)", self.main)


if __name__ == "__main__":
    unittest.main()
