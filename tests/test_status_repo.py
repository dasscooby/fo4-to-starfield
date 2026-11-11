"""Synthetic check that fo4sf status mentions the repo root when run from a checkout."""
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StatusRepoTest(unittest.TestCase):
    def test_status_prints_repo(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        # Use 3.11+ so tomllib is available
        proc = subprocess.run(
            ["/usr/bin/python3.11", "-m", "fo4sf", "--config", "/tmp/test-config.toml", "status"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("repo:", proc.stdout)
        self.assertIn("branch:", proc.stdout)


if __name__ == "__main__":
    unittest.main()
