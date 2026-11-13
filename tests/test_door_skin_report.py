"""scripts/door_skin_report.py reads the clip alias the converter gives a model (FAL-489: the Vault 111 cog door plays Stage2 as Open; the report
planned without the alias, so it could not say, for that model, why its catwalk shapes are left out). Synthetic NIFs only."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import door_skin_report as dsr  # noqa: E402
from fo4sf import door_rig, nif, pipeline  # noqa: E402
from test_door_two_panels import door_nif, two_leaves  # noqa: E402


def cog_like():
    """The door fixture with its Open sequence named Stage2 and no Close: the cog door's shape."""
    f = door_nif(two_leaves())
    f.strings[f.strings.index(b"Open")] = b"Stage2"
    f.strings[f.strings.index(b"Close")] = b"Stage9"
    return nif.parse(nif.serialize(f))


class AliasTests(unittest.TestCase):
    def test_the_converters_own_table_is_read_by_file_name_whatever_the_slashes_and_case(self):
        want = pipeline.OWN_RIG_ALIASES["vltgeardoor01.nif"]
        self.assertEqual(dsr.aliases_for("Meshes\\Interiors\\Vault\\Doors\\VltGearDoor\\VltGearDoor01.nif"), want)
        self.assertEqual(dsr.aliases_for("meshes/interiors/vault/doors/vltgeardoor/vltgeardoor01.nif"), want)
        self.assertIsNone(dsr.aliases_for("Meshes\\Interiors\\RedRocket\\Doors\\RedRPedDoor.nif"))      # a plain door needs none

    def test_a_hand_alias_wins_and_a_bad_one_is_refused(self):
        self.assertEqual(dsr.aliases_for("x.nif", "Stage2=Open"), {"Stage2": "Open"})
        self.assertEqual(dsr.aliases_for("x.nif", "A=Open, B=Close"), {"A": "Open", "B": "Close"})
        for bad in ("Stage2", "Stage2=Shut", "=Open", "Stage2=Open,Other"):
            with self.assertRaises(SystemExit):
                dsr.aliases_for("x.nif", bad)

    def test_the_alias_is_what_gives_a_renamed_sequence_its_clip_in_the_plan_the_report_reads(self):
        # the report's plan must be the one the converter makes: Stage2 is the Open clip only through the alias
        src = cog_like()
        self.assertNotIn("Open", [c["name"] for c in door_rig.plan(src, placed=True)["clips"]])
        self.assertIn("Open", [c["name"] for c in door_rig.plan(src, placed=True, aliases={"Stage2": "Open"})["clips"]])
        out = dsr.report(src, {"Stage2": "Open"})
        self.assertIn("rig_bones", out)
        self.assertEqual(out["shapes"], [])                        # the fixture has no skinned shape: nothing to list

    def test_a_plain_door_is_reported_as_before(self):
        out = dsr.report(nif.parse(nif.serialize(door_nif(two_leaves()))))
        self.assertIn("rig_bones", out)


if __name__ == "__main__":
    unittest.main()
