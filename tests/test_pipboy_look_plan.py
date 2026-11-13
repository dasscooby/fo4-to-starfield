"""FAL-571: the plan for the Pip-Boy's real-device look (docs/spikes/pipboy-real-device-look-plan.md). The card's
survey is run as written on made-up archives in a temporary Data folder: it lists names only and writes nothing there."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from ba2_fixture import general_archive  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "docs" / "spikes" / "pipboy-real-device-look-plan.md"


def survey(card):
    return card[card.index("@'\n") + 3:card.index("\n'@")]


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.card = CARD.read_text(encoding="utf-8")

    def test_the_card_keeps_the_rules(self):
        for text in ("player's **own** Fallout 4 install", "never in Git", "**hypothesis**", "names and counts only",
                     "No game launch, no install, nothing written under the Fallout 4 or Starfield folders",
                     "it extracts no file", "`Pause=0`", "legal-policy.md"):
            self.assertIn(text, self.card, text)
        for group in range(1, 10):
            self.assertIn(f"\n| {group} |", self.card)
        self.assertNotIn(".read(", survey(self.card))                           # names only, no file read out
        self.assertNotIn("open(", survey(self.card))

    def test_the_survey_lists_names_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "Data"
            (data / "Interface").mkdir(parents=True)
            archives = {
                "Fallout4 - Interface.ba2": {"Interface/PipboyMenu.swf": b"a", "Interface/fonts_en.swf": b"b",
                                             "Interface/FontConfig.txt": b"c", "Interface/Pipboy/scan.dds": b"d",
                                             "Interface/Components/x.swf": b"e", "Strings/Fallout4_en.STRINGS": b"f"},
                "Fallout4 - Sounds.ba2": {"Sound/FX/UI/Pipboy/UI_Pipboy_Tab.xwm": b"g", "Sound/FX/Other.xwm": b"h"},
                "ccBGSFO4001-PipBoy(Black) - Main.ba2": {"Materials/Skin.bgsm": b"i"},
            }
            for name, entries in archives.items():
                (data / name).write_bytes(general_archive(entries, version=1))
            (data / "Interface" / "PipboyMenu.swf").write_bytes(b"loose")
            (data / "Broken.ba2").write_bytes(b"not an archive")
            before = sorted((p.relative_to(data).as_posix(), p.stat().st_mtime_ns) for p in data.rglob("*"))
            run = subprocess.run([sys.executable, "-", str(data)], input=survey(self.card), capture_output=True,
                                 text=True, cwd=ROOT, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            after = sorted((p.relative_to(data).as_posix(), p.stat().st_mtime_ns) for p in data.rglob("*"))
            self.assertEqual(before, after)                                     # nothing written in Data
        lines = run.stdout.splitlines()
        self.assertTrue(any(line.startswith("archive=Broken.ba2 error=") for line in lines))
        self.assertIn("archive=Fallout4 - Interface.ba2 files=6 named=4", lines)
        for name in ("Interface/PipboyMenu.swf", "Interface/fonts_en.swf", "Interface/FontConfig.txt",
                     "Interface/Pipboy/scan.dds", "Sound/FX/UI/Pipboy/UI_Pipboy_Tab.xwm", "Materials/Skin.bgsm"):
            self.assertIn(f"  {name}", lines, name)
        for name in ("Interface/Components/x.swf", "Strings/Fallout4_en.STRINGS", "Sound/FX/Other.xwm"):
            self.assertNotIn(f"  {name}", lines, name)
        self.assertIn("  folder=Interface\\Components files=1", lines)
        self.assertIn("  folder=Interface\\Pipboy files=1", lines)
        self.assertIn("archive=Fallout4 - Sounds.ba2 files=2 named=1", lines)
        self.assertIn("archive=ccBGSFO4001-PipBoy(Black) - Main.ba2 files=1 named=1", lines)
        self.assertIn(f"loose={os.path.join('Interface', 'PipboyMenu.swf')}", lines)
        self.assertFalse(any(line.startswith("loose=") and line.endswith(".ba2") for line in lines))


if __name__ == "__main__":
    unittest.main()
