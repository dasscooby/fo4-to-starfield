"""Synthetic test for the ba2_census CLI."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.ba2_fixture import general_archive


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "ba2_census.py"


class Ba2CensusCliTests(unittest.TestCase):
    def test_prints_summary_and_largest(self):
        entries = {
            "small.txt": b"a" * 10,
            "big.dat": b"b" * 500,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "census.ba2"
            path.write_bytes(data)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO / "src")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), "--top", "1"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["summary"]["entries"], 2)
            self.assertEqual(report["summary"]["general"], 2)
            self.assertEqual(len(report["largest"]), 1)
            self.assertEqual(report["largest"][0]["name"], "big.dat")
            self.assertEqual(report["largest"][0]["unpacked"], 500)
            self.assertNotIn("path", report["summary"])


if __name__ == "__main__":
    unittest.main()
