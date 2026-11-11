"""The Vault 111 exit kit (dotnet/Vault111Exit, scripts/vault111_exit; FAL-461): the scripts' ids and rules against the
tool's, and the writer on a synthetic Starfield.esm and FO4Port.esm (never a game; the Papyrus compile and the game run are the
PC's). The dotnet tests skip without the .NET SDK."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "vault111_exit"
TOOL_SRC = (ROOT / "dotnet" / "Vault111Exit" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFVault111Exit.esp"
NAMES = ("FO4SF_V111Exit", "FO4SF_V111PipBoyPickup", "FO4SF_V111DoorTerminal")
TYPES = {"race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug", "utility", "int", "float",
         "string", "bool", "math", "location", "activator", "message", "armor", "weapon", "door", "objectreference"}


def psc(name):
    return (SCRIPTS / f"{name}.psc").read_text(encoding="utf-8")


def code(name):
    return "\n".join(l for l in psc(name).splitlines() if not l.strip().startswith(";"))


def const_ids(text):
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_are_the_tools(self):
        ids = const_ids(TOOL_SRC)
        self.assertEqual((ids["QuestId"], ids["TokenId"]), (0x800, 0x801))
        for n in ("FO4SF_V111PipBoyPickup", "FO4SF_V111DoorTerminal"):
            text = code(n)
            self.assertIn(f'Game.GetFormFromFile(0x800, "{PLUGIN}")', text)
            self.assertIn(f'Game.GetFormFromFile(0x801, "{PLUGIN}")', text)
            self.assertEqual(set(re.findall(r'GetFormFromFile\((0x[0-9A-Fa-f]+),', text)) - {"0x800", "0x801"}, set())

    def test_the_script_names_are_the_tools_and_extend_the_right_bases(self):
        for n, base in zip(NAMES, ("Quest", "ObjectReference", "ObjectReference")):
            self.assertTrue(psc(n).startswith(f"Scriptname {n} extends {base}"), n)
            self.assertIn(f'= "{n}"', TOOL_SRC)
        self.assertIn(f'"{PLUGIN}"', TOOL_SRC.replace("FO4SFVault111Exit.esp", PLUGIN))     # the docs name the file; params carry it

    def test_quest_and_pickup_have_no_properties_and_the_terminal_has_the_two_the_tool_writes(self):
        self.assertNotIn(" Property ", code("FO4SF_V111Exit"))
        self.assertNotIn(" Property ", code("FO4SF_V111PipBoyPickup"))
        props = re.findall(r"^(\w+) Property (\w+) Auto", code("FO4SF_V111DoorTerminal"), re.M)
        self.assertEqual(sorted(props), [("int", "CogDoorId"), ("string", "DoorPlugin")])
        self.assertIn('Name = "CogDoorId"', TOOL_SRC)
        self.assertIn('Name = "DoorPlugin"', TOOL_SRC)

    def test_stages_in_the_tool_are_the_ones_the_scripts_set_and_each_step_needs_the_one_before(self):
        stages = [int(x) for x in re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC).group(1).split(",")]
        self.assertEqual(stages, [5, 10, 20, 30])
        t, p = code("FO4SF_V111DoorTerminal"), code("FO4SF_V111PipBoyPickup")
        self.assertEqual(sorted(set(map(int, re.findall(r"SetStage\((\d+)\)", t + p)))), stages)
        self.assertIn("SetStage(10)", p)
        # the door opens only after stage 20 (plugged in), plugging in only with the token, and a stage 5 without it
        self.assertLess(t.index("GetItemCount"), t.index("SetStage(20)"))
        self.assertLess(t.index("GetStageDone(20)"), t.index("SetOpen(True)"))
        self.assertLess(t.index("SetOpen(True)"), t.index("SetStage(30)"))
        self.assertLess(t.index("GetItemCount"), t.index("SetStage(5)"))
        self.assertLess(t.index("SetStage(5)"), t.index("SetStage(20)"))

    def test_the_pickup_gives_the_token_once_and_only_to_the_player(self):
        p = code("FO4SF_V111PipBoyPickup")
        self.assertIn("akActionRef != Game.GetPlayer()", p)
        self.assertIn("GetItemCount(tokenForm) == 0", p)
        self.assertLess(p.index("GetItemCount"), p.index("AddItem"))

    def test_no_variable_or_parameter_is_named_like_a_type_or_a_base_script(self):
        for n in NAMES:
            decl = re.findall(r"^\s*(?:[A-Za-z:]+(?:\[\])?)\s+(\w+)\s*(?:=|$)", code(n), re.M)
            params = re.findall(r"Event \w+\(\w+ (\w+)\)", code(n))
            self.assertEqual([x for x in decl + params if x.lower() in TYPES], [], n)

    def test_the_kit_adds_no_master_beyond_starfield_and_the_port(self):
        self.assertIn("masters are not exactly Starfield.esm, FO4Port.esm", TOOL_SRC)


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest("no .NET SDK")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "Vault111Exit"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout[-2000:] + proc.stderr[-2000:])
        cls.tool = ROOT / "dotnet/Vault111Exit/bin/Release/net9.0/Vault111Exit.dll"
        cls.tmp = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.fx = cls.tmp / "fx"
        assert cls.run_tool("fixture", cls.fx).returncode == 0
        cls.params = cls.fx / "params.json"

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def build(self, name="out", params=None):
        out = self.tmp / name
        r = self.run_tool("build", params or self.params, self.fx / "Starfield.esm", self.fx / "FO4Port.esm", out)
        return r, out / PLUGIN

    def check(self, plugin, params=None):
        return self.run_tool("check", plugin, params or self.params, self.fx / "Starfield.esm", self.fx / "FO4Port.esm")

    def test_build_then_check_passes(self):
        r, plugin = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        c = self.check(plugin)
        self.assertEqual(c.returncode, 0, c.stderr)

    def test_the_plugin_bytes_hold_exactly_the_two_masters_and_the_ids(self):
        _, plugin = self.build("bytes")
        data = plugin.read_bytes()
        self.assertEqual(data.count(b"MAST"), 2)
        self.assertLess(data.index(b"Starfield.esm"), data.index(b"FO4Port.esm"))
        for edid in (b"FO4SF_V111Exit", b"FO4SF_V111PipBoyToken", b"FO4SF_V111PipBoyPickup", b"FO4SF_V111DoorTerminal"):
            self.assertIn(edid + b"\x00", data)

    def test_check_rejects_a_changed_position_a_changed_door_id_and_another_cell(self):
        _, plugin = self.build("mut")
        spec = json.loads(self.params.read_text())
        for label, edit in (("position", lambda s: s["terminal"].update(pos=[30, 40, 2])),
                            ("door", lambda s: s["cog_door"].update(id="000C0E")),
                            ("model", lambda s: s["pickup"].update(model="Props\\Other.nif"))):
            s2 = json.loads(json.dumps(spec))
            edit(s2)
            p = self.tmp / f"{label}.json"
            p.write_text(json.dumps(s2))
            c = self.check(plugin, p)
            self.assertEqual(c.returncode, 1, label)
            self.assertIn("MISMATCH", c.stderr, label)

    def test_build_refuses_a_missing_cell_a_missing_model_and_a_bad_door_id(self):
        spec = json.loads(self.params.read_text())
        for label, edit, word in (("cell", lambda s: s.update(cell="FO4Port_Nowhere"), "no CELL"),
                                  ("model", lambda s: s["pickup"].pop("model"), "pickup.model"),
                                  ("door", lambda s: s["cog_door"].update(id="0"), "cog_door.id"),
                                  ("esm", lambda s: s.update(plugin="Kit.esm"), "must be an .esp")):
            s2 = json.loads(json.dumps(spec))
            edit(s2)
            p = self.tmp / f"bad_{label}.json"
            p.write_text(json.dumps(s2))
            r, _ = self.build("bad_" + label, p)
            self.assertEqual(r.returncode, 1, label)
            self.assertIn(word, r.stderr, label)


if __name__ == "__main__":
    unittest.main()
