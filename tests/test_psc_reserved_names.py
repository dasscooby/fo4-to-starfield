"""No Papyrus script uses a language keyword as a variable, property or parameter name.

FAL-489 / FAL-772 (the cog door kit): the real compiler refused `int state = d.GetOpenState()` ("no viable alternative at input 'state'"), because
`state` is a Papyrus keyword; the offline tests use a fake compiler, so nothing caught it before the PC's stage. This scan reads every .psc in the repo
for a declaration (a local, a property, a function parameter) whose name is a keyword. It is a text scan, not the compiler: it catches the class, and the
PC's compile stays the proof.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = {"state", "auto", "autoreadonly", "event", "function", "property", "import", "native", "global", "new", "self", "parent", "extends",
            "scriptname", "as", "is", "none", "true", "false", "return", "while", "if", "else", "elseif", "endif", "endwhile", "endfunction",
            "endevent", "endstate", "endproperty", "length", "const", "conditional", "hidden", "mandatory", "collapsed", "debugonly", "betaonly"}
KEYWORDS.discard("length")                                              # an ordinary identifier in Papyrus (Array.Length is a member, not reserved)
TYPE = r"(?:int|float|bool|string|var|[A-Za-z_][A-Za-z0-9_:]*)(?:\[\])?"
LOCAL = re.compile(r"^\s*(%s)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|$)" % TYPE, re.I)          # `int state = ...` and `int state`
PROPERTY = re.compile(r"^\s*(%s)\s+Property\s+([A-Za-z_][A-Za-z0-9_]*)" % TYPE, re.I)
SIGNATURE = re.compile(r"^\s*(?:%s\s+)?(?:Function|Event)\s+[A-Za-z_][A-Za-z0-9_]*\s*\((.*)\)" % TYPE, re.I)
PARAM = re.compile(r"(%s)\s+([A-Za-z_][A-Za-z0-9_]*)" % TYPE, re.I)
NOT_TYPES = {"return", "if", "elseif", "else", "while", "endif", "endwhile", "endfunction", "endevent", "scriptname", "import", "function", "event"}


def names(line):
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line.split(";", 1)[0])    # no strings, no comments
    m = PROPERTY.match(code)
    if m:
        yield m.group(2)
    elif (m := SIGNATURE.match(code)):
        for p in m.group(1).split(","):
            q = PARAM.match(p.strip())
            if q:
                yield q.group(2)
    elif (m := LOCAL.match(code)) and m.group(1).lower() not in NOT_TYPES:
        yield m.group(2)


def code_lines(text):
    """(number, line) without the {doc comment} blocks (they run over several lines and hold prose)."""
    doc = False
    for i, line in enumerate(text.splitlines(), 1):
        code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        if doc:
            doc = "}" not in code
            continue
        if "{" in code and "}" not in code.split("{", 1)[1]:
            doc = True
            line = line.split("{", 1)[0]
        yield i, line


def offenders(text):
    return [(i, n) for i, line in code_lines(text) for n in names(line) if n.lower() in KEYWORDS]


class ReservedNameTests(unittest.TestCase):
    def test_the_scan_finds_the_bug_the_compiler_found_and_leaves_strings_alone(self):
        self.assertEqual(offenders("    int state = d.GetOpenState()\n"), [(1, "state")])
        self.assertEqual(offenders("Function F(int count, bool event)\n"), [(1, "event")])
        self.assertEqual(offenders("int Property auto = 3 Auto Const\n"), [(1, "auto")])
        self.assertEqual(offenders('    Say("S" + x + " state=" + openState)   ; int state = 1\n'), [])
        self.assertEqual(offenders("    int openState = d.GetOpenState()\n    if state != LastState\n"), [])
        self.assertEqual(offenders("Function F()\n{prose, logged\n as is; more prose}\n    int state = 1\n"), [(4, "state")])        # a doc block is skipped, the code after it is not

    def test_no_script_in_the_repo_names_a_variable_after_a_keyword(self):
        files = sorted(ROOT.glob("scripts/**/*.psc"))
        self.assertGreater(len(files), 10)
        bad = {str(f.relative_to(ROOT)): offenders(f.read_text(encoding="utf-8", errors="replace")) for f in files}
        bad = {k: v for k, v in bad.items() if v}
        self.assertEqual(bad, {}, "a Papyrus keyword used as a name: the compiler refuses it")


if __name__ == "__main__":
    unittest.main()
