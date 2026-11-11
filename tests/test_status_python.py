"""Synthetic check that fo4sf status reports the Python version against the minimum."""
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StatusPythonTest(unittest.TestCase):
    def test_status_prints_python(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        proc = subprocess.run(
            ["/usr/bin/python3.11", "-m", "fo4sf", "--config", "/tmp/test-config.toml", "status"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Python:", proc.stdout)
        self.assertTrue("meets" in proc.stdout or "needs" in proc.stdout)


if __name__ == "__main__":
    unittest.main()
