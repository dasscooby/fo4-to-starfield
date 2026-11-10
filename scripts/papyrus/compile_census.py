"""Compile a sample of Fallout 4 Papyrus scripts against Starfield's sources and bucket the errors.

Runs Starfield's PapyrusCompiler once per sampled script, keeps each raw output,
and sorts every error into a bucket. Writes census.json and prints a table.

Import order given to the compiler is: shim folder, Starfield sources, then the
Fallout 4 sources. Starfield therefore wins any name clash (a Fallout 4 copy of
a base type never shadows Starfield's), and other Fallout 4 scripts a sampled
script depends on still resolve.

Nothing from either game belongs in Git. The inputs are the player's own files.
Raw outputs stay on the player's PC; census.json holds only counts, script
names and short compiler messages, never script source.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

SCHEMA = 1
BUCKETS = ("unknown_function", "unknown_type", "unknown_property_or_variable",
           "wrong_argument_count", "syntax", "other")
# Buckets whose errors name a missing thing; the top-names list draws from these.
NAMED_BUCKETS = ("unknown_function", "unknown_type", "unknown_property_or_variable")
DEFAULT_FLAGS = "Starfield_Papyrus_Flags.flg"
MAX_MESSAGE = 200
TOP_NAMES = 20

# file(line,col): message
LOCATED = re.compile(r"^(?P<file>.*?)\((?P<line>\d+),(?P<col>\d+)\):\s*(?P<msg>.*\S)\s*$")
UNLOCATED = re.compile(r"\b(error|failed)\b", re.I)

# Checked in order; the first match wins. Name group is optional.
RULES = (
    ("unknown_type", re.compile(r"unknown type\s+'?(?P<name>[\w:]+)'?", re.I)),
    ("unknown_type", re.compile(r"(?P<name>[\w:]+)\s+is not a known (?:user-defined )?(?:type|script)", re.I)),
    ("unknown_type", re.compile(r"(?:extends unknown script|unable to locate script|could not (?:find|locate) script|"
                                r"failed to (?:find|load) script|parent script)\s+'?(?P<name>[\w:]+)'?", re.I)),
    ("wrong_argument_count", re.compile(r"(?:too many|not enough|too few|wrong number of|incorrect number of)\s+arguments"
                                        r"(?:.*?\b(?:to|for)\s+(?:function\s+)?'?(?P<name>\w+)'?)?", re.I)),
    ("wrong_argument_count", re.compile(r"(?:function\s+)?'?(?P<name>\w+)'?\s+(?:requires|expects|takes)\s+"
                                        r"(?:at least |at most |exactly )?\d+\s+arguments?", re.I)),
    ("unknown_function", re.compile(r"(?P<name>[\w:.]+)\s+is not a function or does not exist", re.I)),
    ("unknown_function", re.compile(r"(?:unknown|undefined|undeclared) function\s+'?(?P<name>[\w:.]+)'?", re.I)),
    ("unknown_function", re.compile(r"function\s+'?(?P<name>[\w:.]+)'?\s+(?:is undefined|does not exist|not found|"
                                    r"is not defined)", re.I)),
    ("unknown_property_or_variable", re.compile(r"variable\s+'?(?P<name>[\w:.]+)'?\s+is undefined", re.I)),
    ("unknown_property_or_variable", re.compile(r"(?P<name>[\w:.]+)\s+is not a (?:known )?property of", re.I)),
    ("unknown_property_or_variable", re.compile(r"(?:unknown|undefined|undeclared)\s+(?:property|variable)\s+"
                                                r"'?(?P<name>[\w:.]+)'?", re.I)),
    ("unknown_property_or_variable", re.compile(r"(?:has no|does not have a?)\s+property\s+(?:named\s+)?'?(?P<name>\w+)'?", re.I)),
    ("syntax", re.compile(r"no viable alternative|mismatched input|extraneous input|missing\s+\S+\s+at|"
                          r"unexpected (?:token|character|end)|syntax error|token recognition error", re.I)),
)


def classify(message):
    """Return (bucket, name or None) for one compiler error message."""
    for bucket, rule in RULES:
        found = rule.search(message)
        if found:
            name = found.groupdict().get("name")
            return bucket, name
    return "other", None


def parse_output(text):
    """Pull error records out of raw compiler output.

    Warnings are ignored. A located line is an error unless it says "warning".
    An unlocated line counts only when it contains "error" or "failed" (and is
    not the compiler's own summary count line).
    """
    errors = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        located = LOCATED.match(line)
        if located:
            msg = located.group("msg")
            if re.match(r"warning\b", msg, re.I):
                continue
            msg = re.sub(r"^error:?\s*", "", msg, flags=re.I)
            where = (int(located.group("line")), int(located.group("col")))
        elif UNLOCATED.search(line) and not re.search(r"\b0 error", line, re.I) \
                and not re.match(r"(?:compilation|batch compile)\b", line, re.I):
            if re.match(r"warning\b", line, re.I):
                continue
            msg, where = line, (0, 0)
        else:
            continue
        bucket, name = classify(msg)
        errors.append({"bucket": bucket, "name": name, "line": where[0], "col": where[1],
                       "message": msg[:MAX_MESSAGE]})
    return errors


def list_scripts(folder):
    """Relative posix paths of every .psc under folder, sorted (stable for the seed)."""
    root = Path(folder)
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.suffix.lower() == ".psc" and p.is_file())


def pick_sample(scripts, fragment, count, seed):
    """The named fragment plus `count` others chosen with `seed`. Returns a list, fragment first."""
    matches = [s for s in scripts if Path(s).stem.lower() == fragment.lower()]
    if not matches:
        raise ValueError(f"fragment script not found in Fallout 4 sources: {fragment}")
    if len(matches) > 1:
        raise ValueError(f"fragment name is ambiguous: {matches}")
    rest = [s for s in scripts if s != matches[0]]
    if count > len(rest):
        raise ValueError(f"asked for {count} scripts but only {len(rest)} others exist")
    return [matches[0]] + random.Random(seed).sample(rest, count)


def build_command(compiler, script_path, flags, imports, out_dir):
    return [str(compiler), str(script_path), f"-f={flags}", f"-i={';'.join(map(str, imports))}", f"-o={out_dir}"]


def default_runner(cmd, timeout):
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors="replace")
    return res.returncode, res.stdout, res.stderr


def run_census(fo4, starfield, shim, compiler, fragment, count, seed, out, flags=DEFAULT_FLAGS,
               timeout=120, runner=default_runner):
    fo4, starfield, shim, out = (Path(p).resolve() for p in (fo4, starfield, shim, out))
    for folder in (fo4, starfield, shim):
        if not folder.is_dir():
            raise ValueError(f"not a folder: {folder}")
    if not Path(compiler).is_file():
        raise ValueError(f"compiler not found: {compiler}")
    imports = [shim, starfield, fo4]
    if not any((d / flags).is_file() for d in imports):
        raise ValueError(f"flags file {flags} not found in the shim, Starfield or Fallout 4 folder")
    sample = pick_sample(list_scripts(fo4), fragment, count, seed)
    raw_dir, pex_dir = out / "raw", out / "pex"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pex_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for rel in sample:
        cmd = build_command(compiler, fo4 / rel, flags, imports, pex_dir)
        try:
            code, stdout, stderr = runner(cmd, timeout)
            note = None
        except subprocess.TimeoutExpired:
            code, stdout, stderr, note = None, "", "", f"timed out after {timeout}s"
        except OSError as err:
            code, stdout, stderr, note = None, "", "", f"could not run compiler: {err}"
        raw_name = rel.replace("/", "__") + ".txt"
        (raw_dir / raw_name).write_text(f"$ {' '.join(cmd)}\nexit={code}\n--stdout--\n{stdout}\n--stderr--\n{stderr}\n"
                                        f"{note or ''}\n", encoding="utf-8")
        errors = parse_output(stdout + "\n" + stderr)
        if note:
            errors.append({"bucket": "other", "name": None, "line": 0, "col": 0, "message": note})
        elif code not in (0, None) and not errors:
            # Non-zero exit with nothing parseable: do not count it as a pass.
            errors.append({"bucket": "other", "name": None, "line": 0, "col": 0,
                           "message": f"compiler exit code {code} with no parseable error"})
        results.append({"script": rel, "compiled": code == 0 and not errors, "exit_code": code,
                        "is_fragment": rel == sample[0], "errors": errors, "raw": f"raw/{raw_name}"})

    census = summarize(results)
    census.update(schema=SCHEMA, seed=seed, requested_count=count, fragment=fragment, scripts=results)
    (out / "census.json").write_text(json.dumps(census, indent=2) + "\n", encoding="utf-8")
    return census


def summarize(results):
    total = len(results)
    compiled = sum(1 for r in results if r["compiled"])
    buckets = {b: {"errors": 0, "scripts": 0} for b in BUCKETS}
    names = Counter()
    for r in results:
        seen = set()
        for e in r["errors"]:
            buckets[e["bucket"]]["errors"] += 1
            seen.add(e["bucket"])
            if e["bucket"] in NAMED_BUCKETS and e["name"]:
                names[(e["bucket"], e["name"])] += 1
        for b in seen:
            buckets[b]["scripts"] += 1
    top = [{"bucket": b, "name": n, "count": c}
           for (b, n), c in sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_NAMES]]
    return {"total": total, "compiled": compiled,
            "compile_share": round(compiled / total, 4) if total else 0.0,
            "buckets": buckets, "top_missing_names": top}


def format_table(census):
    lines = [f"Scripts sampled: {census['total']}   compiled clean: {census['compiled']} "
             f"({census['compile_share'] * 100:.1f}%)", "",
             f"{'bucket':<30}{'errors':>8}{'scripts':>9}"]
    for b in BUCKETS:
        v = census["buckets"][b]
        lines.append(f"{b:<30}{v['errors']:>8}{v['scripts']:>9}")
    lines += ["", f"Top {TOP_NAMES} missing names:"]
    if census["top_missing_names"]:
        lines += [f"  {t['count']:>4}  {t['name']}  ({t['bucket']})" for t in census["top_missing_names"]]
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fo4-sources", required=True, help="folder of Fallout 4 .psc sources")
    p.add_argument("--starfield-sources", required=True, help="folder of Starfield .psc sources")
    p.add_argument("--shim", required=True, help="shim .psc folder (may be empty)")
    p.add_argument("--compiler", required=True, help="path to Starfield's PapyrusCompiler.exe")
    p.add_argument("--fragment", required=True, help="script name of one quest fragment, e.g. QF_Something_01234567")
    p.add_argument("--count", type=int, default=100, help="how many more scripts to sample")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", required=True, help="new or empty output folder")
    p.add_argument("--flags", default=DEFAULT_FLAGS)
    p.add_argument("--timeout", type=int, default=120, help="seconds per script")
    a = p.parse_args(argv)
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        p.error(f"--out must be new or empty: {out}")
    try:
        census = run_census(a.fo4_sources, a.starfield_sources, a.shim, a.compiler, a.fragment, a.count,
                            a.seed, out, a.flags, a.timeout)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(format_table(census))
    print(f"\ncensus.json: {out / 'census.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
