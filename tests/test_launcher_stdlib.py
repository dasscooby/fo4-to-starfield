"""#458 task 7: every src/fo4sf/launcher/ module imports with python -I -S, stdlib only, no Data/ read."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = "--probe-launcher-imports"


def _is_allowed(name, stdlib):
    top = name.split(".")[0]
    if top in {"fo4sf", "__main__", "__mp_main__"}:
        return True
    if top in stdlib:
        return True
    if name.startswith("_frozen_importlib"):
        return True
    return False


def non_stdlib_tops(names, stdlib):
    return sorted({n.split(".")[0] for n in names if not _is_allowed(n, stdlib)})


def path_has_data(text):
    parts = os.path.normpath(text).replace("\\", "/").split("/")
    return "data" in (p.casefold() for p in parts)


def probe(root):
    """Run inside `python -I -S`. Print non-stdlib modules or Data/ opens, then exit 1 if any."""
    src = os.path.join(root, "src")
    sys.path.insert(0, src)
    data_opens = []

    def hook(event, args):
        if event != "open":
            return
        path = args[0]
        if isinstance(path, int):
            return
        try:
            text = os.fsdecode(path)
        except (TypeError, ValueError):
            return
        if path_has_data(text):
            data_opens.append(text)

    sys.addaudithook(hook)

    import pkgutil
    import fo4sf.launcher as pkg
    loaded = []
    for info in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        __import__(info.name)
        loaded.append(info.name)

    stdlib = set(sys.stdlib_module_names)
    bad = non_stdlib_tops(sys.modules, stdlib)
    print("loaded:" + ",".join(loaded))
    if bad:
        print("non-stdlib:" + ",".join(bad))
    if data_opens:
        print("data-open:" + "\n".join(data_opens))
    if bad or data_opens:
        raise SystemExit(1)


class LauncherStdlibTests(unittest.TestCase):
    def test_sitecustomize_counts_as_non_stdlib_if_loaded(self):
        stdlib = set(sys.stdlib_module_names)
        self.assertEqual(
            non_stdlib_tops({"sitecustomize", "_distutils_hack", "os", "sys"}, stdlib),
            ["_distutils_hack", "sitecustomize"],
        )

    def test_numpy_is_reported(self):
        stdlib = set(sys.stdlib_module_names)
        self.assertEqual(non_stdlib_tops({"os", "sys", "numpy", "fo4sf.launcher"}, stdlib), ["numpy"])

    def test_data_path_match_is_case_insensitive(self):
        self.assertTrue(path_has_data(r"C:\Starfield\Data\Meshes\x.nif"))
        self.assertTrue(path_has_data("/game/DATA/foo"))
        self.assertFalse(path_has_data("/game/src/foo"))

    def test_every_launcher_module_imports_stdlib_only_in_isolated_python(self):
        r = subprocess.run(
            [sys.executable, "-I", "-S", os.path.abspath(__file__), PROBE, ROOT],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(r.returncode, 0, r.stdout + "\n" + r.stderr)
        self.assertIn("loaded:", r.stdout)
        self.assertNotIn("non-stdlib:", r.stdout)
        self.assertNotIn("data-open:", r.stdout)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == PROBE:
        probe(sys.argv[2])
    else:
        unittest.main()
