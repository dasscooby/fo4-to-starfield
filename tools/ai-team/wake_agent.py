"""Wake an idle remote agent (Codex or Grok) on this PC with a message from the Lead.

  python wake_agent.py codex|grok --message "..." [--idle-min 10] [--cooldown-min 30] [--dry-run]
  python wake_agent.py status

How it wakes: it FORKS the agent's most recent session (its full history, a new session id) and runs one headless
turn with the message: `codex exec fork <id> <msg>`, `grok --cwd <its cwd> -c --fork-session -p <msg>`. Forking means
it never writes into the session file an open Codex/Grok window may still hold. Nothing is typed into any window.

Guards (deterministic, not a prompt):
- idle: refuses if the agent's newest session log changed in the last --idle-min minutes (it's working; a second copy
  would be two writers in one repo). Tell it through GitHub #32 instead.
- cooldown: at most one wake per agent per --cooldown-min (their usage comes from the owner's plans).
- every attempt (woken / refused / failed) is appended to wakes.jsonl in the guardian state dir.
The woken turn runs in the background; its output goes to <state>/wake-<agent>-<time>.log.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "guardian"))
import store  # noqa: E402

HOME = os.path.expanduser("~")
CODEX = os.path.join(HOME, ".codex", "plugins", ".plugin-appserver", "codex.exe")
GROK = os.path.join(HOME, ".grok", "bin", "grok.exe")
LOG = os.path.join(store.STATE, "wakes.jsonl")
PREFIX = ("Lead (local) wake-up from the fo4-to-starfield local AI team, sent on the owner's instruction. "
          "Read GitHub issue #32 and docs/CODEX-HANDOFF.md, follow AGENTS.md (now on main), then continue your lane. "
          "Message: ")


def newest(pattern):
    files = glob.glob(pattern, recursive=True)
    return max(files, key=os.path.getmtime) if files else None


def latest_session(agent):
    """(session id or None, cwd or None, seconds since its log last changed)."""
    if agent == "codex":
        f = newest(os.path.join(HOME, ".codex", "sessions", "**", "*.jsonl"))
        if not f:
            return None, None, None
        sid = os.path.basename(f)[:-6].split("-", 6)[-1]             # rollout-YYYY-MM-DDThh-mm-ss-<uuid>.jsonl
        return sid, None, time.time() - os.path.getmtime(f)
    f = newest(os.path.join(HOME, ".grok", "sessions", "**", "updates.jsonl"))
    if not f:
        return None, None, None
    cwd = None
    s = os.path.join(os.path.dirname(f), "summary.json")
    if os.path.exists(s):
        info = json.load(open(s, encoding="utf-8")).get("info", {})
        cwd = info.get("cwd")
    return os.path.basename(os.path.dirname(f)), cwd, time.time() - os.path.getmtime(f)


def last_wake(agent):
    if not os.path.exists(LOG):
        return None
    t = None
    for line in open(LOG, encoding="utf-8"):
        e = json.loads(line)
        if e.get("agent") == agent and e.get("result") == "woken":
            t = e["t"]
    return t


def record(entry):
    os.makedirs(store.STATE, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry))


def wake(agent, message, idle_min, cooldown_min, dry):
    sid, cwd, idle_s = latest_session(agent)
    base = {"t": time.time(), "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": agent, "session": sid,
            "idle_min": None if idle_s is None else round(idle_s / 60, 1)}
    if sid is None:
        record(dict(base, result="refused", reason="no previous session found"))
        return 1
    if idle_s < idle_min * 60:
        record(dict(base, result="refused", reason=f"active {idle_s / 60:.1f} min ago (< {idle_min}); use GitHub #32"))
        return 2
    lw = last_wake(agent)
    if lw and time.time() - lw < cooldown_min * 60:
        record(dict(base, result="refused", reason=f"cooldown: woken {(time.time() - lw) / 60:.0f} min ago"))
        return 3
    msg = PREFIX + message
    if agent == "codex":
        cmd = [CODEX, "exec", "fork", sid, msg]
        run_cwd = os.path.dirname(os.path.dirname(HERE))              # the repository
    else:
        cmd = [GROK, "-c", "--fork-session", "-p", msg] + (["--cwd", cwd] if cwd else [])
        run_cwd = cwd or os.path.dirname(os.path.dirname(HERE))
    if dry:
        record(dict(base, result="dry-run", command=[os.path.basename(cmd[0])] + cmd[1:3]))
        return 0
    out = os.path.join(store.STATE, f"wake-{agent}-{time.strftime('%Y%m%d-%H%M%S')}.log")
    with open(out, "w", encoding="utf-8") as fh:
        p = subprocess.Popen(cmd, cwd=run_cwd, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    record(dict(base, result="woken", pid=p.pid, output=out))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", choices=["codex", "grok", "status"])
    ap.add_argument("--message", default="Please check #32 for the latest state and continue.")
    ap.add_argument("--idle-min", type=float, default=10)
    ap.add_argument("--cooldown-min", type=float, default=30)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.agent == "status":
        for ag in ("codex", "grok"):
            sid, cwd, idle_s = latest_session(ag)
            print(json.dumps({"agent": ag, "session": sid, "idle_min": None if idle_s is None else round(idle_s / 60, 1),
                              "last_wake": last_wake(ag)}))
        return 0
    return wake(a.agent, a.message, a.idle_min, a.cooldown_min, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
