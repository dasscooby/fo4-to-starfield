"""Compile a sample of Fallout 4 Papyrus scripts against Starfield's sources and bucket the errors.

Runs Starfield's PapyrusCompiler once per sampled script, keeps each raw output,
and sorts every error into a bucket. Writes census.json and prints a table.

Import order given to the compiler is: shim folder, the clash overlay, Starfield sources, then the Fallout 4
sources. Starfield therefore wins an engine base type (Game, Actor, ...: a Fallout 4 copy never shadows it), and
other Fallout 4 scripts a sampled script depends on still resolve.

How a script is compiled (PC run of 94a7ae03, FAL-245): the compiler is started in a new EMPTY working folder
(<out>/work), never inside the Fallout 4 sources, because it finds the files of its current folder before its
import list and would compile every script against Fallout 4's own Game.psc, Actor.psc and so on. And a script is
named by its namespaced name (Fragments:Quests:QF__010020E0), not by its bare file name: a script in a sub-folder
is refused as "filename does not match script name" otherwise.

Name clashes: a script name that exists in both games' sources is a clash (317 of them on the PC). Where
Starfield's copy is `Native` it is an engine base type and Starfield's wins. Where it is not (REScript, a
Fallout 4 quest script that Starfield also happens to name) the script is Fallout 4's own, so Fallout 4's copy is
copied into <out>/overlay, which comes first in the import list; otherwise the 29 random-encounter fragments that
cast to REScript fail on Starfield's REScript, which has other functions. census.json lists the clashes
("clashes") and marks the sampled scripts that are one.

Two rates, never one. Scene and topic scripts (dialogue fragments: TIF__*, SF_* and anything that extends TopicInfo or
Scene) are short, call a small set of functions and compile far more often than logic scripts (quests, fragments of
quests and packages, effects, activators). One mixed rate would be read as "quests work". Every script is therefore
tagged "logic" or "scene" and census.json, the table and the verdict line report both groups separately (`groups`);
the top-level numbers are kept for the overall sample only. --scene-count adds that many scene/topic scripts to the
sample (the logic sample is the fragment and --count others, drawn from the logic scripts only).

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

SCHEMA = 3
KINDS = ("logic", "scene")
SCENE_PREFIXES = ("tif__", "sf_")
SCENE_EXTENDS = ("topicinfo", "scene")
FRAGMENT_PREFIXES = ("qf_", "pf_", "tif_", "sf_", "term_", "scene_", "pack_")
NATIVE = re.compile(r"^\s*scriptname\s+\S+(?:\s+\w+)*?\s+native\b", re.I | re.M)
EXTENDS = re.compile(r"^\s*scriptname\s+\S+\s+extends\s+(?P<base>[\w:]+)", re.I | re.M)
BUCKETS = ("unknown_function", "unknown_type", "unknown_property_or_variable",
           "wrong_argument_count", "signature_mismatch", "self_only_function", "type_mismatch", "follow_on",
           "syntax", "other")
# Buckets whose errors name a missing thing; the top-names list draws from these.
NAMED_BUCKETS = ("unknown_function", "unknown_type", "unknown_property_or_variable")
# Buckets whose errors name a thing that EXISTS (a changed signature, a self-only function): the name is kept on the
# error record and counted in `top_named`, never in the missing-name list.
EXISTING_BUCKETS = ("signature_mismatch", "self_only_function")
DEFAULT_FLAGS = "Starfield_Papyrus_Flags.flg"
MAX_MESSAGE = 200
TOP_NAMES = 20

# file(line,col): message
LOCATED = re.compile(r"^(?P<file>.*?)\((?P<line>\d+),(?P<col>\d+)\):\s*(?P<msg>.*\S)\s*$")
# The compiler's own trailer lines are not errors: they restate failures already counted.
SUMMARY = re.compile(r"(?:compilation (?:succeeded|failed)|batch compile\b|no output generated|failed on\b|"
                     r"starting \d+ compile threads)", re.I)
SUCCESS = "Compilation succeeded"
UNLOCATED = re.compile(r"\b(error|failed)\b", re.I)

# Checked in order; the first match wins. Name group is optional.
RULES = (
    # PC run of cb2c7539: the largest real group of the old "other" bucket. A changed event or function signature:
    # "the parameter types of function OnDeath in the empty state on script X do not match the original script Y".
    ("signature_mismatch", re.compile(r"the parameter types of function\s+'?(?P<name>\w+)'?.*?do not match the original", re.I)),
    ("self_only_function", re.compile(r"cannot access self-only function\s+'?(?P<name>\w+)'?", re.I)),
    ("type_mismatch", re.compile(r"type mismatch while assigning", re.I)),
    # a follow-on of an unknown function: the member call is rejected because its target never resolved
    ("follow_on", re.compile(r"cannot call the member function\s+'?(?P<name>\w+)'?\s+alone or on a type", re.I)),
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
            msg = re.sub(r"^error:\s+", "", msg, flags=re.I)   # only the compiler's own "error: " prefix; "Error is ..." names a function
            where = (int(located.group("line")), int(located.group("col")))
        elif UNLOCATED.search(line) and not re.search(r"\b0 error", line, re.I) \
                and not SUMMARY.match(line):
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


def classify_script(rel, head=""):
    """"scene" for a dialogue scene or topic script (by file name prefix, or by what it extends in the first lines
    of its source), "logic" for every other script."""
    stem = Path(rel).stem.lower()
    if stem.startswith(SCENE_PREFIXES):
        return "scene"
    m = EXTENDS.search(head)
    if m and m.group("base").lower().split(":")[-1] in SCENE_EXTENDS:
        return "scene"
    return "logic"


def kinds_of(folder, scripts):
    """{relative path: "logic" | "scene"} for the scripts of a source folder (reads the first 4 KB of each one that
    the file name alone does not settle)."""
    out = {}
    for rel in scripts:
        if Path(rel).stem.lower().startswith(SCENE_PREFIXES):
            out[rel] = "scene"
            continue
        try:
            with open(Path(folder) / rel, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(4096)
        except OSError:
            head = ""
        out[rel] = classify_script(rel, head)
    return out


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


def script_name(rel):
    """The namespaced script name of a relative source path: Fragments/Quests/QF__0100.psc -> Fragments:Quests:QF__0100."""
    return Path(rel).with_suffix("").as_posix().replace("/", ":")


def is_native(path):
    """True when the source file's Scriptname line declares the script Native (an engine base type)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return bool(NATIVE.search(f.read(2048)))
    except OSError:
        return False


def find_clashes(fo4, starfield, fo4_scripts):
    """({lower-case relative path: (fo4 relative path, starfield relative path)} of the scripts both games name,
    the same list split into engine base types (Starfield's copy is Native) and overlaid ones)."""
    sf = {s.lower(): s for s in list_scripts(starfield)}
    both = {}
    for rel in fo4_scripts:
        if rel.lower() in sf:
            both[rel.lower()] = (rel, sf[rel.lower()])
    native = {k for k, (_, srel) in both.items() if is_native(Path(starfield) / srel)}
    return both, native


def build_overlay(fo4, both, native, overlay):
    """Copy Fallout 4's version of every clash whose Starfield copy is not Native into overlay; returns their names."""
    names = []
    for key in sorted(set(both) - set(native)):
        rel = both[key][0]
        dst = Path(overlay) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((Path(fo4) / rel).read_bytes())
        names.append(script_name(rel))
    return names


def build_command(compiler, name, flags, imports, out_dir):
    """The script is named by its namespaced name and the compiler runs in an empty folder (see the module doc)."""
    script_name_ = name
    return [str(compiler), script_name_, f"-f={flags}", f"-i={';'.join(map(str, imports))}", f"-o={out_dir}"]


def default_runner(cmd, timeout, cwd=None):
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors="replace", cwd=cwd)
    return res.returncode, res.stdout, res.stderr


def _text(value):
    """Output a timeout carried: str, bytes or None."""
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def run_census(fo4, starfield, shim, compiler, fragment, count, seed, out, flags=DEFAULT_FLAGS,
               timeout=120, runner=default_runner, scene_count=0):
    fo4, starfield, shim, out = (Path(p).resolve() for p in (fo4, starfield, shim, out))
    for folder in (fo4, starfield, shim):
        if not folder.is_dir():
            raise ValueError(f"not a folder: {folder}")
    if not Path(compiler).is_file():
        raise ValueError(f"compiler not found: {compiler}")
    work, overlay = out / "work", out / "overlay"
    work.mkdir(parents=True, exist_ok=True)
    overlay.mkdir(parents=True, exist_ok=True)
    imports = [shim, overlay, starfield, fo4]
    if not any((d / flags).is_file() for d in imports):
        raise ValueError(f"flags file {flags} not found in the shim, Starfield or Fallout 4 folder")
    every = list_scripts(fo4)
    both, native = find_clashes(fo4, starfield, every)
    overlaid = build_overlay(fo4, both, native, overlay)
    kinds = kinds_of(fo4, every)
    if kinds.get(next((s for s in every if Path(s).stem.lower() == fragment.lower()), ""), "logic") == "scene":
        raise ValueError(f"the fragment {fragment} is a scene or topic script; name a quest fragment")
    sample = pick_sample([s for s in every if kinds[s] == "logic"], fragment, count, seed)
    if scene_count:
        scenes = [s for s in every if kinds[s] == "scene"]
        if scene_count > len(scenes):
            raise ValueError(f"asked for {scene_count} scene/topic scripts but only {len(scenes)} exist (is "
                             "--fo4-sources the root that holds Fragments\\ and the other namespace folders, not a "
                             "sub-folder of it?)")
        sample += random.Random(seed).sample(scenes, scene_count)
    raw_dir, pex_dir = out / "raw", out / "pex"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pex_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for rel in sample:
        cmd = build_command(compiler, script_name(rel), flags, imports, pex_dir)
        try:
            code, stdout, stderr = runner(cmd, timeout, str(work))
            note = None
        except subprocess.TimeoutExpired as err:
            code, stdout, stderr, note = None, _text(err.stdout), _text(err.stderr), f"timed out after {timeout}s"
        except OSError as err:
            code, stdout, stderr, note = None, "", "", f"could not run compiler: {err}"
        raw_name = rel.replace("/", "__") + ".txt"
        (raw_dir / raw_name).write_text(f"$ (cwd {work}) {' '.join(cmd)}\nexit={code}\n--stdout--\n{stdout}\n--stderr--\n{stderr}\n"
                                        f"{note or ''}\n", encoding="utf-8")
        errors = parse_output(stdout + "\n" + stderr)
        if note:
            errors.append({"bucket": "other", "name": None, "line": 0, "col": 0, "message": note})
        elif not errors and (code != 0 or SUCCESS not in stdout):
            # Nothing parseable but no clean success either: never count it as a pass.
            errors.append({"bucket": "other", "name": None, "line": 0, "col": 0,
                           "message": f"exit code {code} without '{SUCCESS}' and no parseable error"})
        results.append({"script": rel, "compiled": code == 0 and SUCCESS in stdout and not errors, "exit_code": code,
                        "kind": kinds[rel], "is_named_fragment": rel == sample[0],
                        "is_fragment": Path(rel).stem.lower().startswith(FRAGMENT_PREFIXES),
                        "clash": rel.lower() in both, "clash_overlaid": rel.lower() in both and rel.lower() not in native, "errors": errors, "raw": f"raw/{raw_name}"})

    census = summarize(results)
    census.update(clashes={"count": len(both), "engine_base_starfield_wins": len(native),
                           "overlaid_fo4_wins": len(overlaid), "overlaid_names": overlaid},
                  schema=SCHEMA, seed=seed, requested_count=count, requested_scene_count=scene_count,
                  fragment=fragment, scripts=results)
    (out / "census.json").write_text(json.dumps(census, indent=2) + "\n", encoding="utf-8")
    return census


def summarize(results):
    """The overall numbers plus `groups`: the same numbers for "logic" and for "scene" scripts, each its own rate."""
    out = _summarize(results)
    out["groups"] = {k: _summarize([r for r in results if r.get("kind", "logic") == k]) for k in KINDS}
    return out


def _summarize(results):
    total = len(results)
    compiled = sum(1 for r in results if r["compiled"])
    buckets = {b: {"errors": 0, "scripts": 0} for b in BUCKETS}
    names, shown = Counter(), {}
    existing, existing_shown = Counter(), {}
    for r in results:
        seen = set()
        for e in r["errors"]:
            buckets[e["bucket"]]["errors"] += 1
            seen.add(e["bucket"])
            if e["bucket"] in EXISTING_BUCKETS and e["name"]:
                existing[(e["bucket"], e["name"].casefold())] += 1
                existing_shown.setdefault((e["bucket"], e["name"].casefold()), e["name"])
            if e["bucket"] in NAMED_BUCKETS and e["name"]:
                key = (e["bucket"], e["name"].casefold())          # SetAvailableToBeCompanion == SetAvailabletoBeCompanion
                names[key] += 1
                shown.setdefault(key, e["name"])
        for b in seen:
            buckets[b]["scripts"] += 1
    top_existing = [{"bucket": b, "name": existing_shown[(b, n)], "count": c}
                    for (b, n), c in sorted(existing.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_NAMES]]
    top = [{"bucket": b, "name": shown[(b, n)], "count": c}
           for (b, n), c in sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_NAMES]]
    return {"total": total, "compiled": compiled,
            "compile_share": round(compiled / total, 4) if total else 0.0,
            "buckets": buckets, "top_missing_names": top, "top_existing_names": top_existing}


def format_table(census):
    lines = []
    for k in KINDS:
        g = census.get("groups", {}).get(k)
        if g is not None:
            lines.append(f"{k + ' scripts':<16} sampled {g['total']:>4}   compiled clean {g['compiled']:>4} "
                         f"({g['compile_share'] * 100:.1f}%)")
    c = census.get("clashes")
    if c:
        lines.append(f"Name clashes between the games: {c['count']} ({c['engine_base_starfield_wins']} engine base "
                     f"types where Starfield's copy wins, {c['overlaid_fo4_wins']} where Fallout 4's copy wins)")
    lines += ["Quote the two rates, not their mix.",
              f"Overall (mixed, do not quote): {census['total']} sampled, {census['compiled']} clean "
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
    if census.get("top_existing_names"):
        lines += ["", "Functions that exist but do not fit (changed signature, self-only): not missing names"]
        lines += [f"  {t['count']:>4}  {t['name']}  ({t['bucket']})" for t in census["top_existing_names"]]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fo4-sources", required=True, help="folder of Fallout 4 .psc sources")
    p.add_argument("--starfield-sources", required=True, help="folder of Starfield .psc sources")
    p.add_argument("--shim", required=True, help="shim .psc folder (may be empty)")
    p.add_argument("--compiler", required=True, help="path to Starfield's PapyrusCompiler.exe")
    p.add_argument("--fragment", required=True, help="script name of one quest fragment, e.g. QF_Something_01234567")
    p.add_argument("--count", type=int, default=100, help="how many more scripts to sample")
    p.add_argument("--scene-count", type=int, default=50, help="how many scene/topic scripts to sample as well")
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
                            a.seed, out, a.flags, a.timeout, scene_count=a.scene_count)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(format_table(census))
    print(f"\ncensus.json: {out / 'census.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
