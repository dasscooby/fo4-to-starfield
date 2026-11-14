"""No kit script uses a Papyrus keyword as a variable, parameter, property or function name (FAL-777: `int state = ...` in
FO4SF_CogDoorQuest.psc did not compile on the PC; the fake compilers in the stager tests cannot catch it). Static scan of
declaration positions only, on synthetic text and on every tracked .psc."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

KEYWORDS = {
    "as", "auto", "autoreadonly", "bool", "conditional", "const", "else", "elseif", "endevent", "endfunction", "endgroup",
    "endif", "endproperty", "endstate", "endstruct", "endwhile", "event", "extends", "false", "float", "function", "global",
    "group", "hidden", "if", "import", "int", "is", "length", "mandatory", "native", "new", "none", "parent", "property",
    "return", "scriptname", "self", "state", "string", "struct", "true", "var", "while", "customevent", "debugonly",
    "betaonly", "collapsed", "collapsedonbase", "collapsedonref", "default", "scriptobject",
}
TYPE = r"(?:int|float|bool|string|var|[A-Za-z_][A-Za-z0-9_:]*)(?:\[\])?"


def strip(text):
    """Source without block comments, {doc} blocks, ; comments and string contents."""
    text = re.sub(r";/.*?/;", " ", text, flags=re.S)
    text = re.sub(r"\{[^}]*\}", " ", text, flags=re.S)
    out = []
    for line in text.splitlines():
        line = re.sub(r'"(?:\\.|[^"\\])*"', '""', line)
        out.append(line.split(";", 1)[0])
    return "\n".join(out)


def bad_names(text):
    """[(line, name, what)] for every declared name that is a Papyrus keyword."""
    bad = []
    for no, line in enumerate(strip(text).splitlines(), 1):
        s = line.strip()
        decls = []
        m = re.match(rf"^(?:{TYPE}\s+)?(?:function|event)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", s, re.I)
        if m:
            decls.append((m.group(1), "function/event"))
            for p in m.group(2).split(","):
                pm = re.match(rf"\s*{TYPE}\s+([A-Za-z_]\w*)", p)
                if pm:
                    decls.append((pm.group(1), "parameter"))
        elif re.match(rf"^{TYPE}\s+property\s+([A-Za-z_]\w*)", s, re.I):
            decls.append((re.match(rf"^{TYPE}\s+property\s+([A-Za-z_]\w*)", s, re.I).group(1), "property"))
        else:
            vm = re.match(rf"^({TYPE})\s+([A-Za-z_]\w*)\s*(?:=.*)?$", s)
            if vm and vm.group(1).lower() not in ("return", "endif", "else", "elseif", "if", "while", "endwhile"):
                decls.append((vm.group(2), "variable"))
        for name, what in decls:
            if name.lower() in KEYWORDS:
                bad.append((no, name, what))
    return bad


class PscKeywordTest(unittest.TestCase):
    def test_scanner_catches_the_cog_door_bug(self):
        self.assertEqual(bad_names("Function R()\n    int state = d.GetOpenState()\nEndFunction\n"), [(2, "state", "variable")])
        self.assertEqual(bad_names("Function F(int length, string ok)\nEndFunction\n"), [(1, "length", "parameter")])
        self.assertEqual(bad_names("int Property Self = 1 Auto\n"), [(1, "Self", "property")])
        self.assertEqual(bad_names("int[] parent\n"), [(1, "parent", "variable")])

    def test_scanner_ignores_comments_strings_and_calls(self):
        text = 'int openState = 1 ; int state = 2\n{int state = 3}\nTrace("int state = 4")\nreturn state\nGoToState("x")\n'
        self.assertEqual(bad_names(text), [])

    def test_no_tracked_script_uses_a_keyword_as_a_name(self):
        files = subprocess.run(["git", "ls-files", "*.psc"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        self.assertTrue(files)
        found = []
        for f in files:
            for no, name, what in bad_names((ROOT / f).read_text(encoding="utf-8", errors="replace")):
                found.append(f"{f}:{no} {what} '{name}'")
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
