#!/usr/bin/env python3
"""Run the unittest modules under tests/ in parallel, one process per module.

Replaces the single `python -m unittest discover -s tests -v` process in CI.
Each module runs as `python -m unittest discover -s tests -p <module>.py -v`, the
same loader and sys.path as the full discover, so test ids and counts are identical
(a module-level skip counts as one skipped test, imports like `import ba2_fixture`
resolve). Standard library only.

  python scripts/ci/run_tests.py --jobs 4        run everything, 4 at a time
  python scripts/ci/run_tests.py --serial        one module at a time (comparison)
  python scripts/ci/run_tests.py --list          print test ids, run nothing
  python scripts/ci/run_tests.py --tests-dir D   use another folder of test_*.py

Exit 1 on any failure, error, crash, module over --timeout, or module that
reports zero tests. Exit 0 only when every module ran at least one test and
all of them passed.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# Modules that cannot run beside others, with the reason. Empty on purpose:
# fix a test's isolation instead of adding it here.
SERIAL_MODULES: dict[str, str] = {}

# Seconds per module from a serial run; only used to start the slowest first.
DURATIONS_FILE = HERE / "test_durations.json"

RAN_RE = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.MULTILINE)
RESULT_RE = re.compile(r"^(OK|FAILED)(?: \((.*)\))?\s*$", re.MULTILINE)

LIST_SCRIPT = r"""
import sys, unittest

def flat(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flat(item)
        else:
            yield item.id()

for test_id in flat(unittest.defaultTestLoader.discover(sys.argv[1])):
    print(test_id)
"""


@dataclass
class Result:
    name: str
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    seconds: float = 0.0
    problem: str = ""  # non-empty: why this module counts as failed
    output: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return bool(self.problem) or self.failures > 0 or self.errors > 0


def module_stems(tests_dir: Path) -> list[str]:
    return sorted(p.stem for p in tests_dir.glob("test_*.py"))


def load_durations() -> dict[str, float]:
    try:
        data = json.loads(DURATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: float(v) for k, v in data.items()} if isinstance(data, dict) else {}


def order_slowest_first(stems: list[str], tests_dir: Path) -> list[str]:
    known = load_durations()

    def weight(stem: str) -> float:
        if stem in known:
            return known[stem]
        try:  # unknown module: file size is a rough proxy, below any timed one
            return (tests_dir / f"{stem}.py").stat().st_size / 1e6
        except OSError:
            return 0.0

    return sorted(stems, key=lambda s: (-weight(s), s))


def parse_counts(text: str) -> tuple[int, int, int, int, float] | None:
    ran = RAN_RE.search(text)
    if not ran:
        return None
    tests, secs = int(ran.group(1)), float(ran.group(2))
    failures = errors = skipped = 0
    res = RESULT_RE.search(text[ran.end():])
    if res and res.group(2):
        for part in res.group(2).split(","):
            key, _, val = part.strip().rpartition("=")
            if not val.isdigit():
                continue
            if key == "failures":
                failures = int(val)
            elif key == "errors":
                errors = int(val)
            elif key == "skipped":
                skipped = int(val)
            elif key == "unexpected successes":
                failures += int(val)
    return tests, failures, errors, skipped, secs


def kill_group(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def run_module(stem: str, tests_dir: Path, timeout: float) -> Result:
    res = Result(name=stem)
    cwd = tests_dir.parent
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir),
           "-p", f"{stem}.py", "-v"]
    started = time.monotonic()
    kwargs: dict[str, object] = {} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", **kwargs,  # type: ignore[arg-type]
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_group(proc)
        try:
            out, _ = proc.communicate(timeout=10)
        except Exception:
            out = ""
        res.output = out or ""
        res.seconds = time.monotonic() - started
        res.problem = f"timed out after {timeout:g} s"
        return res
    res.seconds = time.monotonic() - started
    res.output = out or ""
    counts = parse_counts(res.output)
    if counts is None:
        res.problem = f"crashed (exit {proc.returncode}, no unittest summary)"
        return res
    res.tests, res.failures, res.errors, res.skipped, secs = counts
    res.seconds = max(res.seconds, secs)
    if res.tests == 0 and res.skipped == 0:
        # A module whose every test is skipped in setUpClass/module level reports
        # "Ran 0 tests, skipped=N" (discover does the same); that is not a loss.
        res.problem = "reported zero tests"
    elif proc.returncode != 0 and not res.failures and not res.errors:
        res.problem = f"exit {proc.returncode} without a failure count"
    return res


def list_ids(tests_dir: Path, timeout: float) -> list[str]:
    """Every test id the full `unittest discover -s <tests_dir>` would load."""
    proc = subprocess.run(
        [sys.executable, "-c", LIST_SCRIPT, str(tests_dir)], cwd=tests_dir.parent,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise SystemExit(f"listing failed (exit {proc.returncode}):\n{proc.stderr}")
    # Test modules may print on import; ids are the lines that look like ids.
    return [ln for ln in proc.stdout.splitlines() if ln and " " not in ln]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                    help="modules run at once (default: CPU count)")
    ap.add_argument("--timeout", type=float, default=900.0,
                    help="seconds allowed per module (default 900)")
    ap.add_argument("--serial", action="store_true", help="one module at a time")
    ap.add_argument("--list", action="store_true", help="print test ids, run nothing")
    ap.add_argument("--tests-dir", type=Path, default=REPO_ROOT / "tests")
    ap.add_argument("--save-durations", type=Path, metavar="FILE",
                    help="write per-module seconds (>= 1 s) as JSON, for ordering")
    args = ap.parse_args(argv)

    tests_dir = args.tests_dir.resolve()
    stems = module_stems(tests_dir)
    if not stems:
        print(f"no test_*.py modules in {tests_dir}", file=sys.stderr)
        return 1

    if args.list:
        print("\n".join(list_ids(tests_dir, args.timeout)))
        return 0

    jobs = 1 if args.serial else max(1, args.jobs)
    ordered = order_slowest_first(stems, tests_dir)
    serial_only = [n for n in ordered if n in SERIAL_MODULES]
    parallel = [n for n in ordered if n not in serial_only]

    wall = time.monotonic()
    results: list[Result] = []

    def report(r: Result) -> None:
        status = "FAIL" if r.failed else "ok"
        print(f"{status:4} {r.name:50} tests={r.tests:<5} failures={r.failures:<3} "
              f"errors={r.errors:<3} skipped={r.skipped:<3} {r.seconds:7.1f}s"
              + (f"  [{r.problem}]" if r.problem else ""), flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_module, n, tests_dir, args.timeout) for n in parallel]
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            report(r)
    for n in serial_only:  # after the pool is idle, one at a time
        r = run_module(n, tests_dir, args.timeout)
        results.append(r)
        report(r)

    results.sort(key=lambda r: r.name)
    failed = [r for r in results if r.failed]
    for r in failed:
        print(f"\n{'=' * 70}\nFAILED MODULE {r.name}"
              + (f": {r.problem}" if r.problem else "") + f"\n{'=' * 70}")
        print(r.output.rstrip())

    total = lambda attr: sum(getattr(r, attr) for r in results)  # noqa: E731
    elapsed = time.monotonic() - wall
    print(f"\nTOTAL modules={len(results)} tests={total('tests')} "
          f"failures={total('failures')} errors={total('errors')} "
          f"skipped={total('skipped')} modules_failed={len(failed)} "
          f"wall={elapsed:.1f}s jobs={jobs}")
    if failed:
        print("FAILED modules: " + ", ".join(r.name for r in failed))
    else:
        print("OK")

    if args.save_durations:
        slow = {r.name: round(r.seconds, 1)
                for r in results if r.seconds >= 1.0}
        args.save_durations.write_text(
            json.dumps(dict(sorted(slow.items())), indent=1) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
