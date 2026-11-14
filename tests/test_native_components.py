"""FAL-246 item 3: sfse/native_components.json says what each of our SFSE dlls declares to SFSE and checks for itself.
These tests read every field back from the dll's own source, so the file cannot drift from the code, and hold any
`native` entry in scripts/launcher_recipes/known_runtimes.json to it (FAL-247 document native-launcher-contract: one
table, the launcher's comparison in src/fo4sf/launcher/runtimes.py consumes it).

The two kinds of dll pin the game differently, and the file says which: FO4SFBorder is built on SFSE's PluginAPI.h and
lists 1.16.244 in its own version data, so SFSE refuses it on another game; the libxse dlls get their version data
from libxse's plugin rule (CompatibleVersions RUNTIME_LATEST), so SFSE loads them on any game and the pin is their own
first check (`refuse step=version`). Matching a version string proves neither."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = json.loads((ROOT / "sfse" / "native_components.json").read_text(encoding="utf-8"))
PLUGINS = TABLE["plugins"]
RUNTIME = TABLE["runtime"]
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def folder_sources(folder):
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / folder).rglob("*")) if p.suffix in (".cpp", ".h"))


def refuse_steps(source):
    return set(re.findall(r'Refuse\("([a-z_]+)"', source)) | set(re.findall(r"refuse step=([a-z_]+)", source))


def pluginapi_version(code):
    """The decoded {address, structure, compatible} of a PluginAPI.h SFSEPlugin_Version block."""
    block = code[code.index("SFSEPlugin_Version = {"):]
    block = block[:block.index("};")]
    address = {"kAddressIndependence_Signatures": "signatures",
               "kAddressIndependence_AddressLibrary": "address_library"}
    names = [v for k, v in address.items() if k in block]
    structure = "1.14.70_layout" if "kStructureIndependence_1_14_70_Layout" in block else None
    listed = re.search(r"\{\s*([A-Za-z_0-9,\s]+?)\s*,\s*0\s*\}", block).group(1)
    compatible = []
    for name in (n.strip() for n in listed.split(",")):
        m = re.search(r"constexpr std::uint32_t " + name + r" = \(1u << 24\) \| \((\d+)u << 16\) \| \((\d+)u << 4\);", code)
        compatible.append(f"1.{m.group(1)}.{m.group(2)}.0")
    return {"address": names, "structure": structure, "compatible": compatible}


def native_problems(entry, table=TABLE):
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from fo4sf.launcher.runtimes import native_declaration_problems
    return native_declaration_problems(entry, table)


class DeclarationTests(unittest.TestCase):
    def test_every_plugin_folder_is_declared_once(self):
        found = set()
        for folder in sorted(p for p in (ROOT / "sfse").iterdir() if p.is_dir()):
            xmake = folder / "xmake.lua"
            libxse = xmake.exists() and 'add_rules("commonlibsf.plugin"' in xmake.read_text(encoding="utf-8")
            if libxse or "SFSEPlugin_Version = {" in folder_sources(folder.relative_to(ROOT)):
                found.add(folder.relative_to(ROOT).as_posix())
        self.assertEqual(found, {p["folder"] for p in PLUGINS.values()})
        lowered = [name.lower() for name in PLUGINS]
        self.assertEqual(len(set(lowered)), len(lowered))
        for name, plugin in PLUGINS.items():
            self.assertRegex(name, r"^[A-Za-z0-9_]+\.dll$")
            self.assertTrue((ROOT / plugin["source"]).is_file(), name)
            self.assertTrue(plugin["source"].startswith(plugin["folder"] + "/"), name)
            self.assertTrue((ROOT / plugin["folder"] / "build.ps1").is_file(), name)   # the PC builds with MSVC

    def test_the_border_msvc_build_takes_the_declared_inputs(self):
        build = text("sfse/FO4SFBorder/build.ps1")
        for word in ("'FO4SFBorder.cpp' = $cpp", "'scan.h'", "'PluginAPI.h' = $api", "'../FOCCSidecar/runtime_dir.h'",
                     "/std:c++20", "/MT", "/LD", "shell32.lib ole32.lib uuid.lib", "fetch_pluginapi.ps1 -Dest",
                     "-Out already exists", "build_script_sha256"):
            self.assertIn(word, build)
        self.assertNotIn("Copy-Item -LiteralPath $dll", build)                # builds only; installs nothing

    def test_the_fields_agree_with_each_other(self):
        self.assertEqual(TABLE["schema"], 1)
        for name, plugin in PLUGINS.items():
            with self.subTest(name):
                self.assertIn(plugin["build"], ("pluginapi", "libxse"))
                self.assertIs(plugin["needs_address_library"], plugin["address"] == "address_library")
                if plugin["reads_address_library"]:
                    self.assertTrue(plugin["needs_address_library"])
                self.assertIsInstance(plugin["required"], bool)
                self.assertEqual(plugin["runtime_pin"], "sfse" if plugin["sfse_compatible"] == [RUNTIME] else "plugin")
                self.assertEqual(plugin["refuse_steps"], sorted(plugin["refuse_steps"]))
                for step in plugin["refuse_steps"]:
                    self.assertIn(step, TABLE["refuse_causes"])
        used = {s for p in PLUGINS.values() for s in p["refuse_steps"]}
        self.assertEqual(used, set(TABLE["refuse_causes"]))         # no cause for a step nothing logs

    def test_no_dll_is_required_yet(self):
        # every dll is still a probe: none ships in a release, so the gate must not refuse a game without them
        for name, plugin in PLUGINS.items():
            self.assertEqual((plugin["role"], plugin["required"]), ("probe", False), name)


class SourceTests(unittest.TestCase):
    def test_pluginapi_dlls_match_their_version_data(self):
        for name, plugin in PLUGINS.items():
            if plugin["build"] != "pluginapi":
                continue
            with self.subTest(name):
                code = text(plugin["source"])
                version = pluginapi_version(code)
                self.assertEqual(version["address"], [plugin["address"]])
                self.assertEqual(version["structure"], plugin["structure"])
                self.assertEqual(version["compatible"], plugin["sfse_compatible"])
                self.assertIn(f'"{name[:-4]}",', code[code.index("SFSEPlugin_Version = {"):])

    def test_libxse_dlls_take_the_rule_and_pin_the_game_themselves(self):
        for name, plugin in PLUGINS.items():
            if plugin["build"] != "libxse":
                continue
            with self.subTest(name):
                xmake = text(plugin["folder"] + "/xmake.lua")
                self.assertIn(f'add_rules("commonlibsf.plugin", {{\n        name = "{name[:-4]}",', xmake)
                self.assertIn("CompatibleVersions RUNTIME_LATEST", xmake)
                self.assertIn("1.14.70+ layout", xmake)
                self.assertEqual((plugin["address"], plugin["structure"], plugin["sfse_compatible"]),
                                 ("address_library", "1.14.70_layout", "latest"))
                self.assertNotIn("SFSEPlugin_Version = {", folder_sources(plugin["folder"]))   # nothing redeclares it
                code = text(plugin["source"])
                major, minor, patch, build = RUNTIME.split(".")
                self.assertRegex(code, rf"constexpr REL::Version\s+kRuntime\{{ {major}, {minor}, {patch}, {build} \}};")
                load = code[code.index("SFSE_PLUGIN_LOAD("):]
                guard = load.index('Refuse("version"')
                for later in ("RegisterListener(", "AddTask(", "ReadAddressLibrary("):
                    if later in load:
                        self.assertLess(guard, load.index(later), later)
                build = text(plugin["folder"] + "/build.ps1")
                self.assertIn(f"$PinnedLib = '{TABLE['libxse']['commit']}'", build)
                self.assertIn(f"$PinnedShared = '{TABLE['libxse']['shared_commit']}'", build)

    def test_address_library_reads_match_the_source(self):
        library = TABLE["address_library"]["file"]
        self.assertEqual(library, "versionlib-" + RUNTIME.replace(".", "-") + ".bin")
        for name, plugin in PLUGINS.items():
            with self.subTest(name):
                code = folder_sources(plugin["folder"])
                reads = "REL::ID(" in code
                self.assertIs(reads, plugin["reads_address_library"])
                if reads:
                    self.assertIn(f'"{library}"', code)
                    self.assertIn(f"format != {TABLE['address_library']['format']} || version != kRuntime", code)
                else:
                    self.assertNotIn("versionlib-", code)

    def test_refuse_steps_match_the_source(self):
        for name, plugin in PLUGINS.items():
            with self.subTest(name):
                self.assertEqual(refuse_steps(folder_sources(plugin["folder"])), set(plugin["refuse_steps"]))


class KnownRuntimeTests(unittest.TestCase):
    def test_known_runtimes_agree_with_the_declaration(self):
        known = json.loads(text("scripts/launcher_recipes/known_runtimes.json"))
        for entry in known["runtimes"]:
            self.assertEqual(native_problems(entry), [], entry.get("label"))

    def good(self):
        return {"exe_version": RUNTIME,
                "sfse": {"loader_sha256": "f" * 64, "dlls": {"sfse_1_16_244.dll": "e" * 64}}, "native": {
            "schema": 1,
            "address_library": {"file": TABLE["address_library"]["file"], "sha256": "a" * 64, "size": 5099968,
                                "provenance": "synthetic"},
            "plugins": {"FOCCPing.dll": {"runtime": RUNTIME, "sha256": "b" * 64, "size": 571904, "required": False,
                                         "needs_address_library": True, "source_commit": "c" * 40,
                                         "artifact_receipt": "synthetic"}}}}

    def test_the_check_takes_a_consistent_entry_and_no_entry(self):
        self.assertEqual(native_problems(self.good()), [])
        self.assertEqual(native_problems({"exe_version": "1.15.222.0"}), [])

    def test_the_check_names_each_inconsistency(self):
        cases = [
            (lambda n: n["plugins"]["FOCCPing.dll"].update(needs_address_library=False), "differs from the source"),
            (lambda n: n.pop("address_library"), "measures none"),
            (lambda n: n["address_library"].update(file="versionlib-1-15-222-0.bin"), "address_library file"),
            (lambda n: n["plugins"].update({"Other.dll": {}}), "not one of our dlls"),
            (lambda n: n["plugins"].update({"foccping.DLL": {}}), "collide"),
            (lambda n: n["plugins"]["FOCCPing.dll"].update(sha256="B" * 64), "sha256"),
            (lambda n: n["plugins"]["FOCCPing.dll"].update(size=True), "size"),
            (lambda n: n["plugins"]["FOCCPing.dll"].update(source_commit="9d090c4"), "source_commit"),
            (lambda n: n["plugins"]["FOCCPing.dll"].update(artifact_receipt=" "), "artifact_receipt"),
            (lambda n: n["plugins"]["FOCCPing.dll"].update(required="no"), "required"),
            (lambda n: n.update(schema=2), "schema"),
        ]
        for change, word in cases:
            entry = self.good()
            change(entry["native"])
            with self.subTest(word):
                self.assertTrue(any(word in p for p in native_problems(entry)), native_problems(entry))

    def test_a_signature_only_dll_needs_no_library(self):
        entry = self.good()
        entry["native"]["plugins"] = {"FO4SFBorder.dll": {"runtime": RUNTIME, "sha256": "d" * 64, "size": 1,
                                                          "required": False, "needs_address_library": False,
                                                          "source_commit": "e" * 40, "artifact_receipt": "synthetic"}}
        del entry["native"]["address_library"]
        self.assertEqual(native_problems(entry), [])


if __name__ == "__main__":
    unittest.main()
