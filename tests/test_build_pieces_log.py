"""The build pieces kit's log reader (src/fo4sf/workshop/build_pieces_log.py): one synthetic log per verdict."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.workshop import build_pieces_log as bl  # noqa: E402


def piece(when, n, shell, recipe, coreid, core):
    return f"FO4SFBP rt=12.5 piece when={when} n={n} shell={shell} recipe={recipe} coreid={coreid} core={core} end=true"


def found(when, pieces, named):
    return f"FO4SFBP rt=12.6 found when={when} pieces={pieces} named={named} end=true"


INIT = "[11/11/2026 - 04:00:01PM] FO4SFBP rt=1.0 init quest=2048 installed=true core=FO4TerrainCore.esm end=true"


class LogTests(unittest.TestCase):
    def test_ok_when_every_named_piece_has_a_shell_and_a_recipe(self):
        lines = [INIT] + [piece("ready", n, 167772162 + n, 167772166 + n, 10000 + n, 20000 + n) for n in (1, 2, 3, 4)] + [found("ready", 4, 4)]
        s = bl.summarize(lines)
        self.assertTrue(s["ok"])
        self.assertTrue(s["verdict"].startswith("ok: all 4 pieces"))
        text = "\n".join(bl.report(s))
        self.assertIn("plugin installed=True, core=FO4TerrainCore.esm", text)
        self.assertIn("ready piece 4:", text)
        self.assertIn("The menu is the card's screenshot", text)

    def test_partial_and_none_found_and_the_unread_core_static_is_said(self):
        lines = [piece("ready", 1, 5, 6, 7, "none"), piece("ready", 2, "none", "none", 8, "none"), found("ready", 1, 2)]
        s = bl.summarize(lines)
        self.assertFalse(s["ok"])
        self.assertTrue(s["verdict"].startswith("PARTIAL: 1 of 2"))
        self.assertIn("core static 7 -> none", "\n".join(bl.report(s)))
        none = bl.summarize([piece("ready", 1, "none", "none", 7, 9), found("ready", 0, 1)])
        self.assertTrue(none["verdict"].startswith("NONE FOUND"))

    def test_no_pieces_named_and_no_ready_reading_are_not_a_pass(self):
        self.assertTrue(bl.summarize([found("ready", 0, 0)])["verdict"].startswith("NO PIECES"))
        s = bl.summarize([INIT, found("init", 4, 4)])
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE"))
        self.assertFalse(s["ok"])
        self.assertTrue(bl.summarize([])["verdict"].startswith("INCONCLUSIVE"))

    def test_a_cut_line_is_left_out_and_counted_and_other_lines_are_ignored(self):
        lines = ["some other log line", "FO4SFBP rt=1.0 found when=ready pieces=4 named=4", found("ready", 0, 4), "FO4SFWS rt=1.0 init x=1 end=true"]
        s = bl.summarize(lines)
        self.assertEqual(s["cut"], 1)
        self.assertTrue(s["verdict"].startswith("NONE FOUND"))
        self.assertIn("1 line(s) cut", "\n".join(bl.report(s)))

    def test_a_missing_file_is_exit_2_and_a_pass_is_exit_0(self):
        import tempfile
        sys.path.insert(0, str(ROOT / "scripts" / "planet"))
        import make_build_pieces as mbp
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(mbp.main(["log", "--file", str(Path(d) / "none.log")]), 2)
            ok = Path(d) / "ok.log"
            ok.write_text("\n".join([INIT, piece("ready", 1, 1, 2, 3, 4), found("ready", 1, 1)]), encoding="utf-8")
            self.assertEqual(mbp.main(["log", "--file", str(ok)]), 0)
            bad = Path(d) / "bad.log"
            bad.write_text(found("ready", 0, 1), encoding="utf-8")
            self.assertEqual(mbp.main(["log", "--file", str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
