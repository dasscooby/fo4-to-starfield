"""Test environment summary in fo4sf status."""
import os
import sys
import unittest
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(tomllib, "tomllib requires Python 3.11+")
class TestStatusEnv(unittest.TestCase):
    def test_env_lines_present(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text(
                '[fo4]\ndata_dirs = []\n[starfield]\ndata_dir = "/tmp/sf"\n'
                '[paths]\nwork_dir = "/tmp/w"\nstaging_dir = "/tmp/s"\n'
            )
            import subprocess
            r = subprocess.run(
                [sys.executable, "-m", "fo4sf", "--config", str(cfg), "status"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out = r.stdout
            self.assertIn("python:", out)
            self.assertIn("platform:", out)


if __name__ == "__main__":
    unittest.main()
