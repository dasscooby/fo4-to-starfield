"""FAL-246 item 2: our dlls' run-time files leave the game's Data folder for the profile's run-time folder that
FO4SF-Runtime.ini names (FAL-247 document native-launcher-contract). sfse/FOCCSidecar/runtime_dir.h reads the file;
tests/data/runtime_dir_vectors.json holds the cases it, and the launcher's writer, must meet.

Three layers: a Python port of the reader, line for line, run on every case here (no compiler needed); the header
itself, compiled with tests/sfse_runtime_dir_test.cpp and run on the same cases wherever a C++20 compiler exists
(required in CI, as for the sidecar codec); and the two dlls' sources as text: neither writes under Data any more."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "sfse" / "FOCCSidecar" / "runtime_dir.h"
VECTORS = json.loads((ROOT / "tests" / "data" / "runtime_dir_vectors.json").read_text(encoding="utf-8"))["cases"]
MAX_FILE = 64 * 1024
FORBIDDEN = set('<>:"|?*')


def absolute_windows_path(p):
    """runtime_dir.h absolute_windows_path: (ok, error)."""
    seps = "\\/"
    if len(p) >= 3 and p[0].isascii() and p[0].isalpha() and p[1] == ":" and p[2] in seps:
        p = p[3:]
    elif len(p) >= 5 and p[0] in seps and p[1] in seps and p[2] not in seps:
        p = p[2:]
        server = min((i for i, c in enumerate(p) if c in seps), default=-1)
        if server < 0 or server + 1 >= len(p) or p[server + 1] in seps:
            return False, "not absolute (a UNC path needs \\\\server\\share)"
    else:
        return False, "not absolute (a drive or a \\\\server\\share path is needed)"
    for c in p:
        if ord(c) < 0x20 or ord(c) == 0x7F or c in FORBIDDEN:
            return False, "a character Windows refuses in a path"
    for part in p.replace("/", "\\").split("\\"):
        if part in (".", ".."):
            return False, "a . or .. component (the path must be resolved)"
    return True, ""


def parse_runtime_ini(data):
    """runtime_dir.h parse_runtime_ini on the file's bytes: (ok, dir, error)."""
    if len(data) > MAX_FILE:
        return False, "", "file too large"
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    if b"\0" in data:
        return False, "", "a NUL byte (the file must be UTF-8, not UTF-16)"
    text = data.decode("utf-8", "surrogateescape")
    in_runtime = seen = False
    found, value = 0, ""
    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        line = line.strip(" \t")
        if not line or line[0] in ";#":
            continue
        if line[0] == "[":
            if line[-1] != "]":
                return False, "", "a malformed section line"
            in_runtime = line[1:-1].strip(" \t").lower() == "runtime"
            seen = seen or in_runtime
            continue
        if not in_runtime:
            continue
        if "=" not in line:
            return False, "", "a [Runtime] line without '='"
        key, rest = line.split("=", 1)
        if key.strip(" \t").lower() == "dir":
            found += 1
            value = rest.strip(" \t")
    if not seen:
        return False, "", "no [Runtime] section"
    if found == 0:
        return False, "", "no Dir= under [Runtime]"
    if found > 1:
        return False, "", "more than one Dir= under [Runtime]"
    if not value:
        return False, "", "Dir= is empty"
    ok, error = absolute_windows_path(value)
    return ok, (value if ok else ""), error


class VectorTests(unittest.TestCase):
    def check(self, case, ok, value, error):
        self.assertEqual(ok, case["ok"], (case["name"], error))
        if ok:
            self.assertEqual(value, case["dir"], case["name"])
        else:
            self.assertIn(case["error"], error, case["name"])

    def test_the_cases_cover_what_the_contract_names(self):
        names = {c["name"] for c in VECTORS}
        self.assertEqual(len(names), len(VECTORS))
        for wanted in ("non-ascii profile", "literal percent, no expansion", "backslashes kept, no unescaping", "relative",
                       "empty value", "two keys", "dot dot", "utf-16", "unc share", "crlf, bom, spaces and comments"):
            self.assertIn(wanted, names)
        self.assertTrue(any(not c["text"].isascii() and c["ok"] for c in VECTORS))

    def test_the_python_port_meets_every_case(self):
        for case in VECTORS:
            with self.subTest(case["name"]):
                self.check(case, *parse_runtime_ini(case["text"].encode("utf-8")))

    def test_a_file_over_the_limit_is_refused(self):
        # too big for the vectors file: built here, at the limit and one byte over
        line = b"[Runtime]\nDir=C:\\R\n"
        self.assertTrue(parse_runtime_ini(line + b";" * (MAX_FILE - len(line)))[0])
        self.assertEqual(parse_runtime_ini(line + b";" * (MAX_FILE - len(line) + 1))[2], "file too large")

    def test_the_port_follows_the_header(self):
        # the port mirrors these rules; a change to one of them in the header must reach the port
        header = HEADER.read_text(encoding="utf-8")
        for rule in ('constexpr const char* kIniName = "FO4SF-Runtime.ini";', 'constexpr const char* kSidecars = "sidecars";',
                     'constexpr const char* kLogs = "logs";', "constexpr std::size_t kMaxFile = 64 * 1024;",
                     "c == '<' || c == '>' || c == ':' || c == '\"' || c == '|' || c == '?' || c == '*'",
                     'equal_ci(trim(line.substr(1, line.size() - 2)), "Runtime")', 'equal_ci(trim(line.substr(0, eq)), "Dir")',
                     'if (part == "." || part == "..")', "line.front() == ';' || line.front() == '#'"):
            self.assertIn(rule, header)
        for word in ("getenv", "ExpandEnvironmentStrings", "%"):     # literal: nothing expands
            self.assertNotIn(word, header.split("#pragma once", 1)[1])


class CompiledHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = next((p for name in ("c++", "g++", "clang++", "cl") if (p := shutil.which(name))), None)
        if compiler is None:
            if os.environ.get("CI"):
                raise RuntimeError("runtime_dir.h tests need a C++20 compiler in CI")
            raise unittest.SkipTest("C++20 compiler unavailable; the Python port above covers the cases here")
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        directory = Path(temp.name)
        cls.binary = directory / ("runtime_dir_test.exe" if os.name == "nt" else "runtime_dir_test")
        source = ROOT / "tests" / "sfse_runtime_dir_test.cpp"
        includes = HEADER.parent
        if Path(compiler).stem.lower() in ("cl", "clang-cl"):
            argv = [compiler, "/nologo", "/std:c++20", "/EHsc", "/O2", "/W4", "/WX", f"/I{includes}", str(source),
                    f"/Fe:{cls.binary}"]
        else:
            argv = [compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{includes}", str(source), "-o",
                    str(cls.binary)]
        result = subprocess.run(argv, cwd=directory, capture_output=True, timeout=90)
        if result.returncode:
            raise AssertionError((result.stdout + result.stderr).decode("utf-8", "replace"))

    def test_the_header_meets_every_case(self):
        payload = "".join(c["text"].encode("utf-8").hex() + "\n" for c in VECTORS).encode("ascii")
        result = subprocess.run([str(self.binary)], input=payload, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        lines = result.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), len(VECTORS))
        for case, line in zip(VECTORS, lines):
            with self.subTest(case["name"]):
                kind, _, rest = line.partition("\t")
                ok = kind == "ok"
                VectorTests.check(self, case, ok, bytes.fromhex(rest).decode("utf-8") if ok else "", "" if ok else rest)

    def test_the_header_refuses_a_file_over_the_limit(self):
        line = b"[Runtime]\nDir=C:\\R\n"
        texts = [line + b";" * (MAX_FILE - len(line)), line + b";" * (MAX_FILE - len(line) + 1)]
        result = subprocess.run([str(self.binary)], input="".join(t.hex() + "\n" for t in texts).encode("ascii"),
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(result.stdout.decode("utf-8").splitlines(), ["ok\t" + b"C:\\R".hex(), "err\tfile too large"])


class PluginTests(unittest.TestCase):
    sidecar = (ROOT / "sfse" / "FOCCSidecar" / "src" / "main.cpp").read_text(encoding="utf-8")
    border = (ROOT / "sfse" / "FO4SFBorder" / "FO4SFBorder.cpp").read_text(encoding="utf-8")
    card = (ROOT / "docs" / "spikes" / "pipboy-channel-bridge-session.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "spikes" / "combined-core-probes.md").read_text(encoding="utf-8")

    def test_the_sidecar_writes_only_in_the_runtime_folder(self):
        self.assertIn('#include "runtime_dir.h"', self.sidecar)
        self.assertNotIn('dir / "FOCCSidecar"', self.sidecar)                 # the old folder under Data
        self.assertIn('std::ofstream out(g_logs / "focc_sidecar.log"', self.sidecar)
        folder = self.sidecar[self.sidecar.index("bool RuntimeFolder("):]
        folder = folder[:folder.index("\n\t}\n")]
        steps = [folder.index(s) for s in ("a_pluginDir / fo4sf_runtime::kIniName", "parse_runtime_ini(text)",
                                           "is_directory(root.parent_path(), ec)", "create_directories(folder, ec)")]
        self.assertEqual(steps, sorted(steps))                                # parsed, parent checked, then made
        self.assertEqual(folder.count('Refuse("runtime_dir"'), 4)
        load = self.sidecar[self.sidecar.index("SFSE_PLUGIN_LOAD("):]
        self.assertLess(load.index('REX::INFO("step=off'), load.index("if (!RuntimeFolder(dir)) {"))
        self.assertLess(load.index("if (!RuntimeFolder(dir)) {"), load.index("RegisterListener(&OnMessage)"))
        self.assertLess(load.index("if (!RuntimeFolder(dir)) {"), load.index("LogLine("))   # no log line before it

    def test_the_border_writes_only_in_the_runtime_folder(self):
        self.assertIn('#include "../FOCCSidecar/runtime_dir.h"', self.border)
        self.assertNotIn('L"\\\\FO4SFBorder"', self.border)                   # the old folder under Data
        load = self.border[self.border.index("__declspec(dllexport) bool SFSEPlugin_Load("):]
        refuse = load.index("if (!runtime_logs(base, g_dir, why)) {")
        self.assertLess(load.index("if (g_mode != 1 && g_mode != 2) return true;"), refuse)   # Mode=0 needs no file
        for later in ("CreateThread(", "RegisterListener(", "log_line("):
            self.assertLess(refuse, load.index(later), later)
        self.assertIn('OutputDebugStringA(("FO4SFBorder: refuse step=runtime_dir " + why', load)
        logs = self.border[self.border.index("bool runtime_logs("):]
        logs = logs[:logs.index("\n}\n")]
        self.assertLess(logs.index("parse_runtime_ini(text)"), logs.index("GetFileAttributesW(parent.c_str())"))
        self.assertLess(logs.index("GetFileAttributesW(parent.c_str())"), logs.index("CreateDirectoryW("))
        self.assertIn("MB_ERR_INVALID_CHARS", self.border)                   # UTF-8 in, refused when it is not

    def test_the_cards_write_the_file_and_collect_from_the_folder(self):
        for text in (self.card, self.runbook):
            self.assertIn('Set-Content -Encoding UTF8', text)
            self.assertIn('"[Runtime]`r`nDir=$rt"', text)
            self.assertIn('$rt = "$saves\\FO4SF-Runtime"', text)
            self.assertIn('Copy-Item "$rt\\logs\\focc_sidecar.log" "$out\\sfse\\"', text)
            self.assertIn('Copy-Item "$rt\\sidecars" "$out\\sfse\\sidecars" -Recurse', text)
            self.assertNotIn("FOCCSidecar\\focc_sidecar.log", text)
            self.assertNotIn("FOCCSidecar\\sidecars", text)
        self.assertIn("player data", self.card)
        self.assertIn("player data", self.runbook)


if __name__ == "__main__":
    unittest.main()
