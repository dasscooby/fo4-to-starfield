"""Compile census: bucketing and sampling, with made-up compiler lines (no game content, no compiler)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compile_census", ROOT / "scripts" / "papyrus" / "compile_census.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

# Short invented lines in the compiler's "file(line,col): message" format.
SAMPLE_OUTPUT = r"""Starting 1 compile threads for 1 files...
C:\Fake\Demo.psc(10,5): Foo is not a function or does not exist
C:\Fake\Demo.psc(11,5): Foo is not a function or does not exist
C:\Fake\Demo.psc(12,9): unknown type fakething
C:\Fake\Demo.psc(14,1): variable Bar is undefined
C:\Fake\Demo.psc(15,3): Baz is not a property of Demo
C:\Fake\Demo.psc(16,3): Too many arguments to function Qux
C:\Fake\Demo.psc(17,0): no viable alternative at input 'x'
C:\Fake\Demo.psc(18,0): something nobody planned for
C:\Fake\Demo.psc(19,0): warning: unused variable
No output generated for Demo.psc, compilation failed.
Batch compile of 1 files finished. 0 succeeded, 1 failed.
"""


class Classify(unittest.TestCase):
    def test_each_bucket(self):
        cases = {
            "Foo is not a function or does not exist": ("unknown_function", "Foo"),
            "unknown type fakething": ("unknown_type", "fakething"),
            "Fake:Thing is not a known user-defined type": ("unknown_type", "Fake:Thing"),
            "variable Bar is undefined": ("unknown_property_or_variable", "Bar"),
            "Baz is not a property of Demo": ("unknown_property_or_variable", "Baz"),
            "Too many arguments to function Qux": ("wrong_argument_count", "Qux"),
            "Doit requires at least 2 arguments": ("wrong_argument_count", "Doit"),
            "no viable alternative at input 'x'": ("syntax", None),
            "mismatched input 'y' expecting NEWLINE": ("syntax", None),
            "something nobody planned for": ("other", None),
            "the parameter types of function OnDeath in the empty state on script Foo do not match the original "
            "script actor": ("signature_mismatch", "OnDeath"),
            "Cannot access self-only function GotoState declared in scriptobject": ("self_only_function", "GotoState"),
            "type mismatch while assigning to a objectreference[] (cast missing or types unrelated)":
                ("type_mismatch", None),
            "cannot call the member function GetFoo alone or on a type, must call it on a variable":
                ("follow_on", "GetFoo"),
        }
        for msg, want in cases.items():
            self.assertEqual(cc.classify(msg), want, msg)

    def test_type_wins_over_variable(self):
        self.assertEqual(cc.classify("unknown type Foo")[0], "unknown_type")


class Parse(unittest.TestCase):
    def test_parse_counts_and_skips_noise(self):
        errors = cc.parse_output(SAMPLE_OUTPUT)
        self.assertEqual([e["bucket"] for e in errors],
                         ["unknown_function", "unknown_function", "unknown_type",
                          "unknown_property_or_variable", "unknown_property_or_variable",
                          "wrong_argument_count", "syntax", "other"])
        self.assertEqual(errors[0]["line"], 10)
        self.assertNotIn("warning", " ".join(e["message"] for e in errors).lower().replace("compilation failed", ""))

    def test_trailer_lines_are_not_errors(self):
        text = ("Demo.psc(1,1): Foo is not a function or does not exist\n"
                "No output generated for Demo.psc, compilation failed.\n"
                "Batch compile of 1 files finished. 0 succeeded, 1 failed.\n")
        self.assertEqual([e["bucket"] for e in cc.parse_output(text)], ["unknown_function"])

    def test_clean_output_has_no_errors(self):
        self.assertEqual(cc.parse_output("Starting 1 compile threads\nBatch compile of 1 files finished. 1 succeeded, 0 failed.\n"), [])


class PcRunPatterns(unittest.TestCase):
    def test_failed_on_is_a_trailer_not_an_error(self):
        text = ("Fragments\\Quests\\QF_X.psc(3,1): Foo is not a function or does not exist\n"
                "Failed on Fragments:Quests:QF_X\n")
        self.assertEqual([e["bucket"] for e in cc.parse_output(text)], ["unknown_function"])

    def test_names_are_counted_with_case_folded(self):
        def res(name):
            return {"script": name + ".psc", "compiled": False, "kind": "logic", "errors": [
                {"bucket": "unknown_function", "name": name, "line": 1, "col": 1, "message": "m"}]}
        census = cc.summarize([res("SetAvailableToBeCompanion"), res("SetAvailabletoBeCompanion"), res("Other")])
        top = census["top_missing_names"]
        self.assertEqual(top[0], {"bucket": "unknown_function", "name": "SetAvailableToBeCompanion", "count": 2})
        self.assertEqual(len(top), 2)
        self.assertEqual(census["buckets"]["unknown_function"], {"errors": 3, "scripts": 3})


class ReviewFixes(unittest.TestCase):
    def test_error_prefix_needs_a_separator(self):
        text = ("Demo.psc(1,1): ErrorCount is not a function or does not exist\n"
                "Demo.psc(2,1): Error is not a function or does not exist\n"
                "Demo.psc(3,1): error: ErrorCount is not a function or does not exist\n"
                "Demo.psc(4,1): Error Foo is not a function or does not exist\n")
        self.assertEqual([e["name"] for e in cc.parse_output(text)], ["ErrorCount", "Error", "ErrorCount", "Foo"])

    def test_timeout_keeps_what_was_printed(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            fo4, sf, shim = t / "fo4", t / "sf", t / "shim"
            for d in (fo4, sf, shim):
                d.mkdir()
            (sf / cc.DEFAULT_FLAGS).write_text("")
            (fo4 / "QF_A.psc").write_text("Scriptname QF_A Extends Quest\n")
            (t / "c.exe").write_text("")
            for out, so, se in (("o1", "X.psc(1,1): Foo is not a function or does not exist", "err-side"),
                                ("o2", b"X.psc(1,1): Foo is not a function or does not exist", b"err-side")):
                def slow(cmd, timeout, cwd=None, so=so, se=se):
                    raise subprocess.TimeoutExpired(cmd, timeout, output=so, stderr=se)
                c = cc.run_census(fo4, sf, shim, t / "c.exe", "QF_A", 0, 1, t / out, runner=slow)
                raw = (t / out / "raw" / "QF_A.psc.txt").read_text(encoding="utf-8")
                self.assertIn("Foo is not a function", raw)
                self.assertIn("err-side", raw)
                self.assertEqual(c["buckets"]["unknown_function"]["errors"], 1)
                self.assertEqual(c["buckets"]["other"]["errors"], 1)          # the timeout marker is kept

    def test_existing_functions_are_not_missing_names(self):
        def res(bucket, name):
            return {"script": name + ".psc", "compiled": False, "kind": "logic", "errors": [
                {"bucket": bucket, "name": name, "line": 1, "col": 1, "message": "m"}]}
        census = cc.summarize([res("signature_mismatch", "OnDeath"), res("signature_mismatch", "ondeath"),
                               res("unknown_function", "OnDeath"), res("self_only_function", "GotoState")])
        self.assertEqual(census["top_missing_names"], [{"bucket": "unknown_function", "name": "OnDeath", "count": 1}])
        self.assertEqual(census["top_existing_names"][0], {"bucket": "signature_mismatch", "name": "OnDeath", "count": 2})
        table = cc.format_table(census)
        self.assertIn("not missing names", table)
        self.assertEqual(census["buckets"]["signature_mismatch"]["errors"], 2)


class Sampling(unittest.TestCase):
    NAMES = [f"S{i:02d}.psc" for i in range(30)] + ["Quests/QF_Fake_0001.psc"]

    def test_fragment_first_and_seed_stable(self):
        a = cc.pick_sample(sorted(self.NAMES), "qf_fake_0001", 5, 7)
        b = cc.pick_sample(sorted(self.NAMES), "QF_Fake_0001", 5, 7)
        self.assertEqual(a, b)
        self.assertEqual(a[0], "Quests/QF_Fake_0001.psc")
        self.assertEqual(len(set(a)), 6)
        self.assertNotEqual(a, cc.pick_sample(sorted(self.NAMES), "QF_Fake_0001", 5, 8))

    def test_errors(self):
        with self.assertRaises(ValueError):
            cc.pick_sample(self.NAMES, "Nope", 1, 1)
        with self.assertRaises(ValueError):
            cc.pick_sample(self.NAMES, "QF_Fake_0001", 999, 1)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.fo4, self.sf, self.shim = t / "fo4", t / "sf", t / "shim"
        for d in (self.fo4, self.sf, self.shim):
            d.mkdir()
        (self.sf / cc.DEFAULT_FLAGS).write_text("", encoding="utf-8")
        for n in ("QF_Fake_0001", "Alpha", "Beta", "Gamma"):
            (self.fo4 / f"{n}.psc").write_text("; made up\n", encoding="utf-8")
        self.compiler = t / "fake.exe"
        self.compiler.write_text("", encoding="utf-8")
        self.out = t / "out"
        self.cmds = []
        self.cwds = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, cmd, timeout, cwd=None):
        self.cwds.append(cwd)
        self.cmds.append(cmd)
        name = cmd[1].split(":")[-1]
        if name == "Alpha":
            return 1, "X.psc(1,1): Foo is not a function or does not exist\nX.psc(2,1): Foo is not a function or does not exist\n", ""
        if name == "Beta":
            return 1, "", "X.psc(3,1): unknown type Thing\n"
        if name == "Gamma":
            return 3, "", ""  # silent failure must not count as a pass
        return 0, "Compilation succeeded.\nBatch compile of 1 files finished. 1 succeeded, 0 failed.\n", ""

    def test_census(self):
        c = cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF_Fake_0001", 3, 1, self.out,
                          runner=self.runner)
        self.assertEqual((c["total"], c["compiled"]), (4, 1))
        self.assertEqual(c["compile_share"], 0.25)
        self.assertEqual(c["buckets"]["unknown_function"], {"errors": 2, "scripts": 1})
        self.assertEqual(c["buckets"]["unknown_type"], {"errors": 1, "scripts": 1})
        self.assertEqual(c["buckets"]["other"], {"errors": 1, "scripts": 1})
        self.assertEqual(c["top_missing_names"][0], {"bucket": "unknown_function", "name": "Foo", "count": 2})
        self.assertTrue(c["scripts"][0]["is_fragment"])
        on_disk = json.loads((self.out / "census.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["total"], 4)
        self.assertEqual(len(list((self.out / "raw").iterdir())), 4)
        # Import order: shim, Starfield, then Fallout 4.
        imports = self.cmds[0][3].removeprefix("-i=").split(";")
        self.assertEqual([Path(i).name for i in imports], ["shim", "overlay", "sf", "fo4"])
        self.assertIn("Foo", cc.format_table(c))
        # Named by script name, run from an empty folder that is not the Fallout 4 sources.
        for cmd, cwd in zip(self.cmds, self.cwds):
            self.assertFalse(cmd[1].endswith(".psc"))
            self.assertEqual(Path(cwd), self.out.resolve() / "work")
            self.assertEqual(list(Path(cwd).iterdir()), [])

    def test_exit_zero_without_success_line_is_not_a_pass(self):
        c = cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF_Fake_0001", 0, 1, self.out,
                          runner=lambda cmd, t, cwd=None: (0, "", ""))
        self.assertEqual(c["compiled"], 0)
        self.assertEqual(c["buckets"]["other"]["errors"], 1)

    def test_missing_flags_fails_early(self):
        (self.sf / cc.DEFAULT_FLAGS).unlink()
        with self.assertRaises(ValueError):
            cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF_Fake_0001", 1, 1, self.out,
                          runner=self.runner)
        self.assertEqual(self.cmds, [])

    def test_timeout_is_other(self):
        import subprocess

        def slow(cmd, timeout, cwd=None):
            raise subprocess.TimeoutExpired(cmd, timeout)
        c = cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF_Fake_0001", 1, 1, self.out, runner=slow)
        self.assertEqual(c["compiled"], 0)
        self.assertEqual(c["buckets"]["other"]["scripts"], 2)


class TwoRates(unittest.TestCase):
    def test_classify_script(self):
        self.assertEqual(cc.classify_script("TIF__00012345.psc"), "scene")
        self.assertEqual(cc.classify_script("Scenes/SF_Fake_00012345.psc"), "scene")
        self.assertEqual(cc.classify_script("Other.psc", "Scriptname Other Extends TopicInfo Hidden\n"), "scene")
        self.assertEqual(cc.classify_script("Other.psc", ";x\nScriptName Other extends Scene\n"), "scene")
        self.assertEqual(cc.classify_script("QF_Fake_0001.psc", "Scriptname QF_Fake_0001 Extends Quest Hidden"), "logic")
        self.assertEqual(cc.classify_script("Plain.psc"), "logic")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.fo4, self.sf, self.shim = t / "fo4", t / "sf", t / "shim"
        for d in (self.fo4, self.sf, self.shim):
            d.mkdir()
        (self.sf / cc.DEFAULT_FLAGS).write_text("", encoding="utf-8")
        for n in ("QF_Fake_0001", "Alpha", "Beta"):
            (self.fo4 / f"{n}.psc").write_text("Scriptname X Extends Quest\n", encoding="utf-8")
        for n in ("TIF__0001", "SF_Fake_0002"):
            (self.fo4 / f"{n}.psc").write_text("; made up\n", encoding="utf-8")
        (self.fo4 / "Odd.psc").write_text("Scriptname Odd Extends TopicInfo\n", encoding="utf-8")
        self.compiler = t / "fake.exe"
        self.compiler.write_text("", encoding="utf-8")
        self.out = t / "out"

    @staticmethod
    def runner(cmd, timeout, cwd=None):
        name = cmd[1].split(":")[-1]
        if name in ("Alpha", "Beta", "QF_Fake_0001"):                  # every logic script fails
            return 1, "X.psc(1,1): Foo is not a function or does not exist\n", ""
        return 0, "Compilation succeeded.\n", ""                       # every scene script compiles

    def test_two_rates_and_the_mix_is_not_the_headline(self):
        c = cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF_Fake_0001", 2, 1, self.out,
                          runner=self.runner, scene_count=3)
        g = c["groups"]
        self.assertEqual((g["logic"]["total"], g["logic"]["compiled"], g["logic"]["compile_share"]), (3, 0, 0.0))
        self.assertEqual((g["scene"]["total"], g["scene"]["compiled"], g["scene"]["compile_share"]), (3, 3, 1.0))
        self.assertEqual((c["total"], c["compiled"]), (6, 3))
        self.assertEqual(g["logic"]["buckets"]["unknown_function"]["scripts"], 3)
        self.assertEqual(g["scene"]["buckets"]["unknown_function"]["scripts"], 0)
        self.assertEqual({r["kind"] for r in c["scripts"] if "TIF" in r["script"] or "Odd" in r["script"]}, {"scene"})
        table = cc.format_table(c)
        self.assertIn("logic scripts", table)
        self.assertIn("scene scripts", table)
        self.assertIn("do not quote", table)
        self.assertNotIn("compile more often", table)
        self.assertEqual(c["schema"], 3)

    def test_logic_sample_never_takes_a_scene_script(self):
        c = cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF_Fake_0001", 2, 1, self.out,
                          runner=self.runner)
        self.assertEqual(c["groups"]["scene"]["total"], 0)
        self.assertEqual(c["groups"]["logic"]["total"], 3)

    def test_too_many_scene_scripts_and_a_scene_fragment(self):
        with self.assertRaises(ValueError):
            cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF_Fake_0001", 1, 1, self.out,
                          runner=self.runner, scene_count=9)
        with self.assertRaises(ValueError):
            cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "TIF__0001", 1, 1, self.out, runner=self.runner)


class NamespaceAndClashes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.fo4, self.sf, self.shim, self.out = t / "fo4", t / "sf", t / "shim", t / "out"
        for d in (self.fo4, self.sf, self.shim):
            d.mkdir()
        (self.sf / cc.DEFAULT_FLAGS).write_text("", encoding="utf-8")
        (self.fo4 / "Fragments" / "Quests").mkdir(parents=True)
        (self.fo4 / "Fragments" / "Quests" / "QF__0100.psc").write_text("Scriptname Fragments:Quests:QF__0100 Extends Quest\n")
        (self.fo4 / "Other.psc").write_text("Scriptname Other Extends Quest\n")
        (self.fo4 / "REScript.psc").write_text("Scriptname REScript extends Quest ; fo4's own\n")
        (self.fo4 / "Game.psc").write_text("Scriptname Game Native Hidden\n")
        (self.sf / "REScript.psc").write_text("ScriptName REScript extends Quest\n")
        (self.sf / "Game.psc").write_text("ScriptName Game Native Hidden\n")
        self.compiler = t / "fake.exe"
        self.compiler.write_text("")
        self.cmds = []

    def runner(self, cmd, timeout, cwd=None):
        self.cmds.append(cmd)
        return 0, "Compilation succeeded.\n", ""

    def test_script_name_and_native(self):
        self.assertEqual(cc.script_name("Fragments/Quests/QF__0100.psc"), "Fragments:Quests:QF__0100")
        self.assertEqual(cc.script_name("Other.psc"), "Other")
        self.assertTrue(cc.is_native(self.sf / "Game.psc"))
        self.assertFalse(cc.is_native(self.sf / "REScript.psc"))

    def test_namespaced_name_and_the_clash_rule(self):
        c = cc.run_census(self.fo4, self.sf, self.shim, self.compiler, "QF__0100", 3, 1, self.out, runner=self.runner)
        self.assertEqual(self.cmds[0][1], "Fragments:Quests:QF__0100")
        self.assertEqual(c["clashes"]["count"], 2)                       # Game and REScript
        self.assertEqual(c["clashes"]["engine_base_starfield_wins"], 1)  # Game is Native in Starfield
        self.assertEqual(c["clashes"]["overlaid_fo4_wins"], 1)
        self.assertEqual(c["clashes"]["overlaid_names"], ["REScript"])
        overlay = self.out.resolve() / "overlay"
        self.assertEqual(sorted(p.name for p in overlay.rglob("*.psc")), ["REScript.psc"])
        self.assertIn("fo4's own", (overlay / "REScript.psc").read_text())
        self.assertIn(f"Name clashes between the games: 2", cc.format_table(c))
        flags = {r["script"]: r for r in c["scripts"]}
        self.assertTrue(flags["Fragments/Quests/QF__0100.psc"]["is_named_fragment"])
        self.assertTrue(flags["Fragments/Quests/QF__0100.psc"]["is_fragment"])
        self.assertFalse(flags["Other.psc"]["is_fragment"])
        self.assertTrue(flags["REScript.psc"]["clash_overlaid"])
        self.assertTrue(flags["Game.psc"]["clash"] and not flags["Game.psc"]["clash_overlaid"])


if __name__ == "__main__":
    unittest.main()
