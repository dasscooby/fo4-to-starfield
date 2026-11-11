"""Ensure the map markers staging script parses on the CI Python (and 3.10)."""
import ast
import os
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "mapmarkers", "make_map_markers.py")


class MapMarkersScriptSyntax(unittest.TestCase):
    def test_parses_with_ast(self):
        with open(SCRIPT, encoding="utf-8") as f:
            src = f.read()
        # Would raise SyntaxError on the old f-string with backslash in expression (Python < 3.12).
        ast.parse(src)


if __name__ == "__main__":
    unittest.main()
