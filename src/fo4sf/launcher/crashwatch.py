"""`launcher.py play`: apply the launcher settings, start Starfield, and (when the crash watcher is on) watch it from
start to exit (owner, 2026-10-21: "rebuild the crash watcher to be allowed to start and close with the game").

The old watcher (C:\\Modding\\tools\\crashwatch.cmd on the owner's PC) was a loop the player started by hand:
`procdump64.exe -accepteula -e 1 -f "80000003" -ma -n 1 -w Starfield.exe <folder>`, again and again, all day. It
caught the museum crashes (three full dumps, ACCESS_VIOLATION at Starfield.exe+0x2bf016b), but:
  - it ran whether or not anyone was playing, and only stopped when someone killed it;
  - `-w` attached the instant Starfield.exe appeared, the leading lead for Steam's "ERROR 84" launch failures;
  - full dumps only (about 18 GB each);
  - a silent exit (no exception, no Windows error report: 21 Oct 11:03:25) left nothing behind at all.

Here the watcher lives exactly as long as one game:
  1. the settings are applied with the game closed (bridge held off or put back, Papyrus logging);
  2. the game is started (Steam or Starfield.exe, `route`);
  3. once Starfield.exe has stayed up `settle_s` seconds, ProcDump attaches to that process id (no `-w`), with the
     old watcher's triggers (`-e 1 -f 80000003`: the assertion stop, and unhandled exceptions, which caught the three
     museum dumps) and, when asked, `-t` (a dump at any exit);
  4. this process holds its own handle on the game, so when the game ends, by a crash, a silent exit or a quit, it
     logs the exit code and its name to crashwatch.log, with the dumps written in that run;
  5. ProcDump detaches and exits by itself when the game ends. It is never killed here: a dump cut short is useless
     (docs/PLAY-AND-TEST.md); if it is still writing after `dump_wait_s`, play says so and leaves it running.
With the watcher off, play still starts the game and prints its exit code (a handle costs nothing).

Everything Windows-specific goes through a `System` object, so the flow is tested on synthetic stand-ins.
"""
import codecs
import datetime
import glob
import os
import re
import subprocess
import sys
import time

from . import detect, manifest as mf, runtimes as rt, settings as settings_mod
from ..core import loadset

STEAM_URL = "steam://rungameid/1716740"
ATTACH_CHECK_S = 5.0               # how long ProcDump must stay up after attaching before the watcher counts as armed
GAME_EXE = "Starfield.exe"
SFSE_LOADER = "sfse_loader.exe"                         # starts Starfield.exe with SFSE; the watcher follows the game
BRIDGE = "FO4SFBridge.esm"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PLUGIN_TOGGLE = os.path.join(REPO, "scripts", "game", "plugin_toggle.py")
LOAD_ORDER = os.path.join(REPO, "scripts", "game", "load_order.py")   # the target order (its module doc)

# Windows NTSTATUS / exception codes a game exit is likely to carry (winnt.h / ntstatus.h names)
EXIT_NAMES = {
    0: "normal exit (also what a silent ExitProcess gives)",
    1: "exit code 1",
    0xC0000005: "ACCESS_VIOLATION",
    0x80000003: "BREAKPOINT (the engine's assertion stop)",
    0xC0000409: "STACK_BUFFER_OVERRUN (a fast fail)",
    0xC00000FD: "STACK_OVERFLOW",
    0xC0000374: "HEAP_CORRUPTION",
    0xC000001D: "ILLEGAL_INSTRUCTION",
    0xC0000017: "NO_MEMORY",
    0xC000013A: "CONTROL_C_EXIT (closed from outside)",
    0x40010004: "DBG_TERMINATE_PROCESS (ended by a debugger)",
}


def exit_name(code):
    if code is None:
        return "unknown (no handle on the game, or the wait failed)"
    code &= 0xFFFFFFFF
    return f"0x{code:08X} {EXIT_NAMES.get(code, 'not a known crash code')}"


FULL_DUMP_GB = 20.0          # one -ma dump of the game: about 18 GB on the owner's PC


def needed_free_gb(values):
    """Free space the watcher needs: the floor, and with full dumps room for every dump ProcDump may write (-n)."""
    n = 2 if values["crash_watch.dump_on_exit"] else 1
    full = FULL_DUMP_GB * n if values["crash_watch.dump"] == "full" else 0.0
    return max(values["crash_watch.min_free_gb"], full)


def free_floor_text(values):
    need = needed_free_gb(values)
    if need > values["crash_watch.min_free_gb"]:
        return (f"{need:g} GB, room for {int(need // FULL_DUMP_GB)} full dumps of about {FULL_DUMP_GB:g} GB "
                "(crash_watch.dump=full)")
    return f"crash_watch.min_free_gb {values['crash_watch.min_free_gb']:g}"


def procdump_argv(values, pid):
    """ProcDump's command line for one game process."""
    cw = lambda k: values["crash_watch." + k]          # noqa: E731
    argv = [cw("procdump"), "-accepteula", "-ma" if cw("dump") == "full" else "-mm"]
    if cw("catch_assertion"):
        argv += ["-e", "1", "-f", "80000003"]
    else:
        argv += ["-e"]
    if cw("dump_on_exit"):
        argv += ["-t"]
    # one dump per game; -t needs room for the exit dump after an exception dump
    argv += ["-n", "2" if cw("dump_on_exit") else "1", str(pid), cw("folder")]
    return argv


INFINITE, WAIT_OBJECT_0 = 0xFFFFFFFF, 0


def declare_kernel32(k):
    """Give the kernel32 calls their real types. Without them ctypes reads OpenProcess's HANDLE as a C int, which
    can cut a 64-bit handle short (Grok's review, #465)."""
    from ctypes import POINTER, wintypes
    k.OpenProcess.restype, k.OpenProcess.argtypes = wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.GetExitCodeProcess.restype = wintypes.BOOL
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, POINTER(wintypes.DWORD)]
    k.CloseHandle.restype, k.CloseHandle.argtypes = wintypes.BOOL, [wintypes.HANDLE]
    return k


class System:
    """The real Windows calls. Tests pass a stand-in with the same methods. env: the environment our tools run in (the
    FO4SF game folder's own LOCALAPPDATA, instance.env_for); plugins_txt: the Plugins.txt plugin_order reads."""

    def __init__(self, env=None, plugins_txt=None):
        self.env, self.plugins_txt = env, plugins_txt

    def now(self):
        return time.time()

    def sleep(self, s):
        time.sleep(s)

    def pids(self, image=GAME_EXE):
        """Process ids running `image`; failed queries raise ValueError rather than mean an empty list."""
        if os.name != "nt":
            return []
        try:
            r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                               capture_output=True, text=True)
        except OSError as e:
            raise ValueError(f"Cannot check {image} processes: tasklist could not run ({e})") from None
        if r.returncode != 0:
            detail = " ".join((r.stderr or r.stdout or "no diagnostic").split())[:300]
            raise ValueError(f"Cannot check {image} processes: tasklist exited {r.returncode}: {detail}")
        out = []
        for line in r.stdout.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[0].casefold() == image.casefold() and parts[1].isdigit():
                out.append(int(parts[1]))
        return out

    def start_game(self, route, starfield):
        if route == "steam":
            os.startfile(STEAM_URL)                         # noqa: the Windows shell opens Steam's URL
        else:
            exe = SFSE_LOADER if route == "sfse" else GAME_EXE
            subprocess.Popen([os.path.join(starfield, exe)], cwd=starfield)

    def open_process(self, pid):
        """A handle that stays valid after the process ends, so its exit code can be read; None if refused."""
        import ctypes
        SYNCHRONIZE, QUERY_LIMITED = 0x00100000, 0x1000
        h = declare_kernel32(ctypes.windll.kernel32).OpenProcess(SYNCHRONIZE | QUERY_LIMITED, False, pid)
        return h or None

    def wait_exit(self, handle):
        """Blocks until the process ends; returns its exit code, or None when the wait or the read failed."""
        import ctypes
        from ctypes import wintypes
        k = declare_kernel32(ctypes.windll.kernel32)
        waited = k.WaitForSingleObject(handle, INFINITE)
        code = wintypes.DWORD()
        # only a wait that returned WAIT_OBJECT_0 means the game ended: after a failed wait GetExitCodeProcess
        # would give STILL_ACTIVE (259) for a game still running (Grok's review, #465)
        ok = waited == WAIT_OBJECT_0 and k.GetExitCodeProcess(handle, ctypes.byref(code))
        k.CloseHandle(handle)
        return code.value if ok else None

    def spawn(self, argv, out_path):
        with open(out_path, "wb") as log:                 # the child keeps its own copy of the handle
            return subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)

    def run(self, argv):
        r = subprocess.run(argv, capture_output=True, text=True, env=self.env)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def free_gb(self, path):
        return detect.free_gb(path)

    def runtime_problems(self, starfield):
        """[problems] with the game folder's Starfield.exe and SFSE against the known-runtimes table, as detect
        judges them: an unlisted Starfield.exe, or an SFSE loader or DLL that is not the build listed with it."""
        g = mf.game_pins(starfield)
        exe = (g["files"].get("Starfield.exe") or {}).get("sha256")
        if not exe:
            return [f"{GAME_EXE} not found in {starfield}"]
        known = rt.match_runtime(rt.load_runtimes(), exe)
        if known is None:
            return [f"this {GAME_EXE} (sha256 {exe[:12]}...) is not listed as a good runtime"]
        return rt.sfse_problems(known, g)

    def plugins_path(self):
        return self.plugins_txt or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")

    def plugin_order(self):
        """The plugins ticked in the player's Plugins.txt, in file order, or None when it cannot be read."""
        entries = self.plugin_entries()
        return None if entries is None else [n for n, ticked in entries if ticked]

    def plugin_entries(self):
        """(name, ticked) for every plugin line of the player's Plugins.txt, in file order, or None when it cannot be
        read."""
        try:
            with open(self.plugins_path(), encoding="utf-8-sig", errors="replace") as f:
                lines = [ln.strip() for ln in f]
        except OSError:
            return None
        return [(ln.lstrip("*").strip(), ln.startswith("*")) for ln in lines if ln and not ln.startswith("#")]

    def plugins_active(self):
        """Casefolded names ticked in the player's Plugins.txt, or None when it cannot be read."""
        order = self.plugin_order()
        return None if order is None else {n.casefold() for n in order}


TOGGLE_RECORD = "FO4SF.toggle.json"         # plugin_toggle.py's record in Data (scripts/game/exp_install.py TOGGLE)


def _held_off(starfield):
    """Casefolded plugins plugin_toggle.py holds off on purpose (its record's "off" list); empty when it cannot be read."""
    import json
    try:
        with open(os.path.join(starfield, "Data", TOGGLE_RECORD), encoding="utf-8") as f:
            return {str(x).casefold() for x in json.load(f).get("off", [])}
    except (OSError, ValueError, AttributeError, TypeError):     # no record, or not plugin_toggle's shape
        return set()


def unticked_ours(system, values=None, starfield=None):
    """Why play refuses a Plugins.txt that lists plugins of ours with none of them ticked, else None. Starfield writes
    it so when "Save" is picked at its "different Creations load order" prompt on loading a save made with other
    plugins (the PC, 14 Oct and 1 Nov 2026): the game would start without FO4SF, and the bridge step refused with a
    message that hid this cause (nine silent starts on 1 Nov). Plugins unticked on purpose do not count: those
    plugin_toggle.py holds off (its record) and the bridge when the setting `bridge` manages it (#662 review). Play never
    ticks them itself."""
    entries = getattr(system, "plugin_entries", lambda: None)()
    managed = _held_off(starfield) if starfield else set()
    if values is not None and values.get("bridge", "unchanged") != "unchanged":
        managed.add(BRIDGE.casefold())
    ours = [(n, ticked) for n, ticked in entries or () if loadset.ours(n)]
    names = [n for n, _ in ours if n.casefold() not in managed]   # a tick anywhere counts; the managed are not missed
    if not names or any(ticked for _, ticked in ours):
        return None
    path = getattr(system, "plugins_path", lambda: None)()
    good = None                                   # the newest copy kept beside it that has one of ours ticked
    found = glob.glob(glob.escape(path) + ".bak-*") if path else []
    def written(b):
        try:
            return os.path.getmtime(b)
        except OSError:                           # gone since the glob: last in line
            return 0.0
    for bak in sorted(found, key=lambda b: (written(b), b), reverse=True):
        try:
            with open(bak, encoding="utf-8-sig", errors="replace") as f:
                if any(ln.strip().startswith("*") and loadset.ours(ln.strip()[1:].strip()) for ln in f):
                    good = bak
                    break
        except OSError:
            continue
    folder = bool(values and values.get("instance"))
    fix = ("Tick them again in that file (the FO4SF game folder's own list: the game reads it only while play runs)"
           if folder else "Tick them again in the game's Creations menu")
    return (f"every FO4SF plugin in Plugins.txt is unticked ({len(names)} listed: {', '.join(names[:3])}"
            f"{', ...' if len(names) > 3 else ''}; {path or 'Plugins.txt'}). Starfield writes it so when \"Save\" is "
            f"picked at its \"different Creations load order\" prompt. {fix}"
            + (f", or put back {os.path.basename(good)}, the newest copy beside it with them ticked" if good else "")
            + "; play does not change Plugins.txt for this")


def decode_mixed(data):
    """ProcDump's redirected output starts with 8-bit text (its banner) and goes on in UTF-16LE, at any byte offset
    (seen on the PC, 2026-10-22): 8-bit up to the first two-byte unit with a zero high byte, UTF-16LE from there on,
    so a character outside Latin-1 in a path keeps both its bytes (Codex, #449)."""
    i = 2 if data.startswith(b"\xff\xfe") else 0
    start = i
    while i + 1 < len(data) and not (data[i] != 0 and data[i + 1] == 0):
        i += 1
    if i + 1 >= len(data):                          # no UTF-16 at all
        return data[start:].replace(b"\x00", b"").decode("cp1252", errors="replace")
    return data[start:i].decode("cp1252", errors="replace") + data[i:].decode("utf-16-le", errors="replace")


def fold_output(out_path, log_path):
    """Append a finished child's output file to crashwatch.log, decoded (ProcDump writes UTF-16 when its output is
    redirected), then remove the side file. Returns the text ("" when there is no file)."""
    try:
        with open(out_path, "rb") as f:
            data = f.read()
    except (OSError, TypeError):
        return ""
    text = decode_mixed(data)
    with open(log_path, "a", encoding="utf-8") as f:
        for line in text.splitlines():
            if line.strip():
                f.write(f"  procdump: {line.rstrip()}\n")
    try:
        os.remove(out_path)
    except OSError:
        pass
    return text


def dumps_confirmed(text, dumps):
    """True when ProcDump printed a "Dump N complete" line for every dump listed: a dump without one may be cut short
    (a full disk, a write error) and is not reported as usable (docs/PLAY-AND-TEST.md)."""
    return len(re.findall(r"Dump \d+ complete", text or "")) >= len(dumps)


def _log(path, line):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {line}\n")


def dump_names(folder):
    """The .dmp files in folder now."""
    if not folder or not os.path.isdir(folder):
        return set()
    return {n for n in os.listdir(folder) if n.lower().endswith(".dmp")}


def order_change(before, after):
    """"" when the ticked plugins kept their order, else which moved, came or went. A moved plugin gets another
    load-order index, so its form ids change between sessions (seen on the PC, 2026-10-22: the game rewrote
    Plugins.txt about 25 s after it started and FO4Port moved after FO4SFMission; Codsworth 06000811 became 05000811)."""
    if before is None or after is None:
        return ""
    fold_b, fold_a = [n.casefold() for n in before], [n.casefold() for n in after]
    if fold_b == fold_a:                            # the game may rewrite a name's case; that loads the same
        return ""
    parts = []
    for i, n in enumerate(before):
        if fold_b[i] in fold_a and fold_a.index(fold_b[i]) != i:
            parts.append(f"{n} {i + 1} -> {fold_a.index(fold_b[i]) + 1}")
    parts += [f"{n} unticked" for i, n in enumerate(before) if fold_b[i] not in fold_a]
    parts += [f"{n} ticked" for i, n in enumerate(after) if fold_a[i] not in fold_b]
    return ", ".join(parts) or "same plugins, other order"


def dumps_since(folder, before):
    """The dumps that appeared after the snapshot `before` (dump_names taken just before ProcDump attached): a dump
    of an earlier game is never listed, whatever its file time says (seen on the PC, 2026-10-21)."""
    return sorted(dump_names(folder) - set(before))


def apply_bridge(values, starfield, system, say):
    """bridge=off holds FO4SFBridge.esm off through plugin_toggle.py; bridge=on puts back a hold. Raises on refusal."""
    want = values["bridge"]
    if want == "unchanged":
        return
    import json
    # -I: plugin_toggle reads plugin headers and rewrites Plugins.txt, so no inherited PYTHONPATH or user site (AGENTS.md)
    code, out = system.run([sys.executable, "-I", PLUGIN_TOGGLE, "status", "--starfield", starfield])
    if code:
        raise ValueError(f"bridge: plugin_toggle.py status failed: {out.strip()}")
    st = json.loads(out.strip().splitlines()[-1])
    held = {p.casefold() for p in st.get("off", [])}
    owned = {p.casefold() for p in st.get("owned", [])}
    if BRIDGE.casefold() not in owned:
        say(f"bridge: {BRIDGE} is not installed; nothing to turn {want}")
        return
    if want == "off":
        # run off even for a recorded hold: the game may have ticked the bridge again, and a repeated off unticks it
        # (plugin_toggle.py prints "already held off" when nothing needs doing) (Codex, #449)
        argv = [sys.executable, "-I", PLUGIN_TOGGLE, "off", "--plugins", BRIDGE, "--starfield", starfield,
                "--why", "launcher setting bridge=off"]
    elif want == "on" and BRIDGE.casefold() in held:
        argv = [sys.executable, "-I", PLUGIN_TOGGLE, "on", "--plugins", BRIDGE, "--starfield", starfield]
    else:
        # not held is not proof of on: a restore that could not load the bridge releases the hold and leaves it
        # unticked (Codex, #449)
        active = system.plugins_active()
        if active is None or BRIDGE.casefold() not in active:
            raise ValueError(f"bridge=on: {BRIDGE} is installed and not held off, but "
                             + ("Plugins.txt cannot be read" if active is None else "it is not active in Plugins.txt")
                             + ": reinstall the bridge or tick it in the game, then play again")
        say(f"bridge: already {want}")
        return
    code, out = system.run(argv)
    if code:
        raise ValueError(f"bridge: plugin_toggle.py {want} refused: {out.strip()}")
    if want == "on" and not bridge_came_back(out):
        # plugin_toggle releases a hold it cannot restore (the plugin or a master cannot load) and still exits 0:
        # the bridge is then unticked, so the game must not start as if it ran (Codex, #449)
        raise ValueError(f"bridge: {BRIDGE} did not come back on: {out.strip()}")
    say(f"bridge: turned {want}")


def bridge_came_back(out):
    """True when plugin_toggle.py on reports the bridge among those ticked back ("back on: A, B; ...")."""
    for line in out.splitlines():
        if line.startswith("back on:"):
            names = line[len("back on:"):].split(";", 1)[0]
            return BRIDGE.casefold() in {n.strip().casefold() for n in names.split(",")}
    return False


PAPYRUS = ("bEnableLogging", "bEnableTrace", "bLoadDebugInformation")


def set_papyrus(text, on):
    """StarfieldCustom.ini text with the three [Papyrus] keys set to 1 (on) or 0 (off); everything else kept as it
    was, line endings included (a CRLF file stays CRLF). Returns (new_text, changed)."""
    v = "1" if on else "0"
    nl = "\r\n" if "\r\n" in text else "\r" if "\r" in text else "\n"
    # each line with its own ending: CRLF, LF or a lone CR (Codex, #487); never the other characters splitlines takes
    lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", text)
    out, in_sec, seen, found, changed = [], False, set(), False, False

    def add(line):
        if out and not out[-1].endswith(("\n", "\r")):
            out[-1] += nl                                          # the old last line had no ending
        out.append(line + nl)

    def close():
        nonlocal changed
        for k in PAPYRUS:
            if k.lower() not in seen:
                add(f"{k}={v}")
                changed = True
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if in_sec:
                close()
            in_sec = s.lower() == "[papyrus]"
            found = found or in_sec
            out.append(line)
            continue
        if in_sec and "=" in s:
            k, old = (x.strip() for x in s.split("=", 1))
            hit = next((p for p in PAPYRUS if p.lower() == k.lower()), None)
            if hit:
                seen.add(hit.lower())
                if old != v:
                    body = line.rstrip("\r\n")
                    out.append(f"{hit}={v}" + line[len(body):])
                    changed = True
                    continue
        out.append(line)
    if in_sec:
        close()
    if not found:
        for line in ["[Papyrus]"] + [f"{k}={v}" for k in PAPYRUS]:
            add(line)
        changed = True
    return "".join(out), changed


def keep_copy(path, raw):
    """Write raw to path.bak-<time>, never over an earlier copy (two changes in one second get -2, -3, ...); the
    copy's path. (Codex, #487)"""
    stem = path + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for n in range(1, 1000):
        bak = stem if n == 1 else f"{stem}-{n}"
        try:
            with open(bak, "xb") as f:
                f.write(raw)
            return bak
        except FileExistsError:
            continue
    raise OSError(f"no free backup name beside {path}")


def apply_papyrus(values, say, path=None):
    """path: the INI to change; default My Games' StarfieldCustom.ini (the FO4SF game folder passes its own
    Starfield.ini, so the player's game keeps its logging)."""
    want = values["papyrus_logging"]
    if want == "unchanged":
        return
    path = path or os.path.join(values["my_games"], "StarfieldCustom.ini")
    try:
        raw = b""
        if os.path.exists(path):
            with open(path, "rb") as f:
                raw = f.read()
        # bytes in and out: a BOM, CRLF endings and any non-UTF-8 byte all come back as they were (phase audit)
        if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) or b"\0" in raw:
            # UTF-16 (or anything with NUL bytes) is not edited: a UTF-8 section appended to it would break the file
            # (Codex, #487)
            raise ValueError(f"papyrus logging: {path} is UTF-16 or binary, not changed; save it as UTF-8 (or ANSI) "
                             "first, or set papyrus_logging=unchanged")
        bom = codecs.BOM_UTF8 if raw.startswith(codecs.BOM_UTF8) else b""
        new, changed = set_papyrus(raw[len(bom):].decode("utf-8", "surrogateescape"), want == "on")
        if not changed:
            say(f"papyrus logging: already {want} in {path}")
            return
        if os.path.exists(path):
            bak = keep_copy(path, raw)
            say(f"papyrus logging: kept {bak}")
        # written beside it and swapped in whole: a failed write never leaves the live INI cut short (Codex, #449)
        tmp = path + ".fo4sf-tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(bom + new.encode("utf-8", "surrogateescape"))
            os.replace(tmp, path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
    except OSError as e:
        raise ValueError(f"papyrus logging: cannot read or write {path} ({e.strerror or e}); Windows Controlled "
                         "Folder Access may block Python in Documents") from None
    say(f"papyrus logging: turned {want} in {path}")


def apply_load_order(values, starfield, system, say, dry_run=False):
    """load_order=fix puts our plugins in the target order before the game starts, check refuses a different order,
    off leaves Plugins.txt alone. A dry run only checks and says what fix would do. Raises on refusal."""
    want = values["load_order"]
    if want == "off":
        return
    cmd = "check" if dry_run or want == "check" else "fix"
    code, out = system.run([sys.executable, "-I", LOAD_ORDER, cmd, "--starfield", starfield])
    for line in out.strip().splitlines():
        say(line if line.startswith("load order") else f"load order: {line.strip()}")
    if code == 9 and dry_run and want == "fix":
        say("load order: play would put it right before the start")
        return
    if code:
        raise ValueError(f"load order: {out.strip().splitlines()[-1] if out.strip() else f'exit {code}'}"
                         + ("; set load_order=fix to put it right, or off" if code == 9
                            else "; put Plugins.txt right, or set load_order=off to start without this check"))


def _without_sfse(values, starfield, system):
    """The note on a start line whose route skips SFSE while an SFSE loader is in the game folder: the switch to
    route=sfse when the listed runtime checks out, else what keeps it from working (Codex, #497)."""
    if values["route"] == "sfse" or not os.path.isfile(os.path.join(starfield, SFSE_LOADER)):
        return ""
    try:
        problems = system.runtime_problems(starfield)
    except OSError as e:                            # an unreadable file is no reason to stop a dry run
        return f" (without SFSE; {SFSE_LOADER} is here but its runtime could not be read: {e.strerror or e})"
    if not problems:
        return f" (without SFSE, which is installed and required: --set route=sfse starts through {SFSE_LOADER})"
    return f" (without SFSE; {SFSE_LOADER} is here but route=sfse would be refused: {'; '.join(problems)})"


def play(values, starfield, system=None, say=print, start_timeout_s=180.0, dump_wait_s=3600.0, dry_run=False,
         folder=None):
    """Apply the settings, start the game and watch it to its end. Returns a result dict; raises ValueError on a
    refusal (nothing started). folder: the FO4SF game folder (setting `instance`, docs/ai/fo4sf-instance.md): the game
    starts from it, our tools run on its own Plugins.txt, its own Starfield.ini takes the saves path and the Papyrus
    keys, and its Plugins.txt stands in the player's place only while the game runs (instance.swap_in / swap_out)."""
    from . import instance as inst
    if folder:
        folder = os.path.abspath(folder)
        inst.check_ready(folder)
        player = inst.player_plugins_txt()
        starfield = folder
        system = system or System(env=inst.env_for(folder), plugins_txt=inst.plugins_txt(folder))
    system = system or System()
    bad = settings_mod.problems(values)
    if folder and values["route"] == "steam":
        bad.append("route=steam starts the Steam folder, not the FO4SF game folder: use route=sfse or exe")
    if folder:
        bad += inst.custom_ini_problems(values["my_games"], values)
    cw = values["crash_watch.enabled"]
    if cw:
        if values["crash_watch.procdump"] and not os.path.isfile(values["crash_watch.procdump"]):
            bad.append(f"crash_watch.procdump: {values['crash_watch.procdump']} not found")
        if values["crash_watch.folder"]:
            free = system.free_gb(values["crash_watch.folder"])
            if free < needed_free_gb(values):
                bad.append(f"crash watcher: {free:.1f} GB free for dumps, under {free_floor_text(values)}")
    for route, exe in (("exe", GAME_EXE), ("sfse", SFSE_LOADER)):
        if values["route"] == route and not os.path.isfile(os.path.join(starfield, exe)):
            bad.append(f"route={route}: {exe} not found in {starfield}")
            break
    else:
        if values["route"] == "sfse":
            # the loader alone is not enough: a missing or other SFSE DLL starts nothing, and play would wait for a
            # game that never comes (Codex, #487)
            bad += [f"route=sfse: {p} (launcher.py detect shows the whole check)" for p in system.runtime_problems(starfield)]
    if system.pids():
        bad.append("Starfield is already running: close it first (settings change only with the game closed, and "
                   "the watcher follows a game it started)")
    if bad:
        raise ValueError("; ".join(bad))
    if folder and not values["my_games"]:
        say("StarfieldCustom.ini not checked for lines that would undo the FO4SF folder's own Starfield.ini (its saves "
            "folder, Papyrus logging): set my_games to have play check it")
    log_path = os.path.join(values["crash_watch.folder"], "crashwatch.log") if cw else None
    plan = ([f"game folder: {folder} (FO4SF's own; its Plugins.txt stands in for yours only while it runs)"]
            if folder else [])
    plan += [f"bridge: {values['bridge']}", f"papyrus logging: {values['papyrus_logging']}",
            f"load order: {values['load_order']}",
            f"start: {values['route']}",
            "crash watcher: " + (f"on, {values['crash_watch.dump']} dumps to {values['crash_watch.folder']}, "
                                 + ("a dump on every exit" if values["crash_watch.dump_on_exit"]
                                    else "log only when the game exits without a crash")
                                 if cw else "off")]
    unticked = unticked_ours(system, values, starfield)
    if dry_run:
        if unticked:
            raise ValueError(unticked)
        # the note hashes the runtime, so only a dry run that shows it pays for it (Codex, #497)
        plan[3 + bool(folder)] += _without_sfse(values, starfield, system)
        for p in plan:
            say(p)
        apply_load_order(values, starfield, system, say, dry_run=True)
        return {"dry_run": True, "plan": plan}
    if cw:
        try:                                        # before the game starts: the log must be writable (Codex, #449)
            os.makedirs(values["crash_watch.folder"], exist_ok=True)
            _log(log_path, "play: starting the game")
        except OSError as e:
            raise ValueError(f"crash watcher: cannot write to {values['crash_watch.folder']} ({e.strerror or e})") \
                from None
    try:                                            # a refusal from here on is logged too: the window alone forgets it
        if unticked:
            raise ValueError(unticked)
        # never a blind bridge, even half way: logging goes on before the bridge comes back, and off only after the
        # bridge is held (Codex, #449)
        ini = os.path.join(folder, "Starfield.ini") if folder else None
        if values["bridge"] == "on":
            apply_papyrus(values, say, ini)
            apply_bridge(values, starfield, system, say)
        else:
            apply_bridge(values, starfield, system, say)
            apply_papyrus(values, say, ini)

        apply_load_order(values, starfield, system, say)   # after the bridge: a toggle rewrites Plugins.txt too
        if folder:
            inst.ensure_saves(folder, say)
        order = system.plugin_order()               # compared at the end: the game may rewrite Plugins.txt
        if folder:
            inst.swap_in(folder, player, say)
            system.plugins_txt = player             # while the game runs, the folder's list stands there
    except Exception as e:
        if cw:
            what = " | ".join(str(e).splitlines()) or type(e).__name__     # one timestamped line
            try:
                _log(log_path, f"play: refused: {what}" if isinstance(e, (ValueError, OSError))
                     else f"play: stopped by {type(e).__name__}: {what}")
            except Exception:                       # the refusal itself still reaches the window, unchanged
                pass
        raise
    try:
        t0 = system.now()
        try:
            system.start_game(values["route"], starfield)
        except OSError as e:                        # no steam:// handler, or the exe would not start (Codex, #465)
            why = f"could not start the game by {values['route']} ({e.strerror or e})"
            if cw:
                _log(log_path, f"play: {why}")
            raise ValueError(why) from None
        # the player's list comes back as soon as the game has ended, before any wait on ProcDump's dump
        on_exit = (lambda: system.pids() or inst.swap_out(player, say, after_game=True)) if folder else None
        result = _follow(values, system, say, t0, log_path, start_timeout_s, dump_wait_s, order_before=order,
                         on_exit=on_exit)
    except BaseException:
        if folder:
            try:
                closed = not system.pids()
            except ValueError:                      # unknown: leave the journal; recover() puts it back later
                closed = False
            if closed:
                inst.swap_out(player, say, after_game=True)
            elif inst.pending(player):              # stopped (Ctrl+C) under a running game: say where the list is
                say(STILL_SWAPPED)
        raise
    if folder:
        try:
            running = bool(system.pids())
        except ValueError:                          # unknown (review of 66c353dd): leave the journal and say so, as above
            running = True
        if inst.pending(player) and running:
            # a game that came up after the watch gave up still reads the list in place: the player's comes back at
            # the next `play` (with or without the setting) or `instance recover` once Starfield is closed
            say(STILL_SWAPPED)
        else:
            inst.swap_out(player, say, after_game=True)
        system.plugins_txt = inst.plugins_txt(folder)
    return result


STILL_SWAPPED = ("Plugins.txt: FO4SF's list is still in your place while Starfield runs; yours comes back at the next "
                 "launcher play (or `launcher.py instance recover`) after it closes")


def _follow(values, system, say, t0, log_path, start_timeout_s, dump_wait_s, only_pid=None, seen=(), order_before=None,
            on_exit=None):
    """Find a Starfield.exe that stays up settle_s, attach ProcDump when the watcher is on, wait for its end and log
    it. only_pid follows that one process; seen are process ids already watched (never picked again); order_before is
    the Plugins.txt order at the start, reported if the game changed it; on_exit runs once the game has ended, before
    the wait on ProcDump."""
    cw = values["crash_watch.enabled"]
    early = list(seen)             # processes that ended before they settled (a first launch can end within ~2 s)
    pid = handle = proc = None
    while pid is None and system.now() - t0 < start_timeout_s:
        found = [p for p in system.pids() if p not in early and (only_pid is None or p == only_pid)]
        if not found:
            system.sleep(1)
            continue
        cand = found[0]
        seen_at = system.now()                     # "after S s" counts from here, not from when the watch began
        h = system.open_process(cand)
        settle_end = system.now() + values["crash_watch.settle_s"]
        while system.now() < settle_end and cand in system.pids():
            system.sleep(1)
        if cand not in system.pids():
            early.append(cand)
            code = system.wait_exit(h) if h else None
            say(f"process {cand} ended within {values['crash_watch.settle_s']:g} s ({exit_name(code)}); "
                "looking for the next one")
            if log_path:
                _log(log_path, f"process {cand} ended before it settled: {exit_name(code)}")
            continue
        pid, handle, up_since = cand, h, seen_at
    if pid is None:
        say(f"Starfield did not stay up within {start_timeout_s:g} s; nothing to watch")
        if log_path:
            _log(log_path, "game did not stay up; watcher not armed")
        return {"started": False, "early": [p for p in early if p not in seen]}
    say(f"Starfield running (process {pid})")
    armed = False
    out_path = None
    pd_text = ""                    # ProcDump's report, folded at the attach check if it quit by then, else at the end
    if cw:
        argv = procdump_argv(values, pid)
        # ProcDump's own output goes to a side file first: it writes UTF-16 when redirected, which would leave
        # crashwatch.log spaced out; fold_output appends it decoded once ProcDump has ended
        # one name per run: a report a timed-out ProcDump left behind on a reused process id stays as it is (Codex, #449)
        out_path = os.path.join(values["crash_watch.folder"], f"procdump_{pid}_{int(system.now())}.out")
        before = dump_names(values["crash_watch.folder"])
        try:
            proc = system.spawn(argv, out_path)
        except OSError as e:
            proc = None
            why = f"ProcDump did not start ({e.strerror or e})"
        else:
            # ProcDump stays up while it is attached; one that exits while the game still runs refused the
            # arguments or could not attach (its own message is in crashwatch.log)
            system.sleep(ATTACH_CHECK_S)
            rc = proc.poll()
            why = ""
            if rc is not None:
                pd_text = fold_output(out_path, log_path)
                if pid in system.pids():
                    why = f"ProcDump exited at once (code {rc})"
                elif not re.search(r"Dump \d+ complete|Dump count (not )?reached", pd_text):
                    # the game ended inside the check too: only this run's own report shows its ProcDump had attached,
                    # by a finished dump or by its end-of-watch line (a normal quit prints "Dump count not reached");
                    # a new file in the folder may be an earlier ProcDump's (Codex, #449)
                    why = f"ProcDump ended with the game inside the attach check and reported no watch (code {rc})"
            armed = not why
        if armed:
            _log(log_path, f"armed: process {pid}: " + " ".join(argv[1:-2]))
            say(f"crash watcher armed on process {pid} ({values['crash_watch.dump']} dumps)")
        else:
            _log(log_path, f"NOT armed on process {pid}: {why}; only the exit code will be logged")
            say(f"crash watcher NOT armed: {why}; only the exit code will be logged (see crashwatch.log)")
    code = system.wait_exit(handle) if handle else None
    if code is None:                # no handle, or the wait failed: follow the process id; the exit code stays unknown
        say(f"{'the wait on process ' + str(pid) + ' failed' if handle else 'no handle on process ' + str(pid)}: "
            "following it by process id, the exit code will be unknown")
        while pid in system.pids():  # a failed wait says nothing about the game: never announce an exit it hasn't made
            system.sleep(2)
    result = {"started": True, "pid": pid, "early": [p for p in early if p not in seen], "exit_code": code, "exit": exit_name(code),
              "seconds": round(system.now() - up_since), "armed": armed}
    say(f"Starfield ended after {result['seconds']} s up: {result['exit']}")
    moved = order_change(order_before, system.plugin_order() if order_before is not None else None)
    if moved:
        result["load_order_changed"] = moved
        say(f"Plugins.txt load order changed while the game ran: {moved} (form ids of moved plugins change)")
        if log_path:
            _log(log_path, f"load order changed while the game ran: {moved}")
    if on_exit is not None:
        try:
            on_exit()
        except Exception as e:     # never at the cost of the crash record: the caller's own path or recover() retries
            say(f"after the game ended: {e}; the rest of the watch goes on")
            if log_path:
                _log(log_path, f"after the game ended: {e}")
    if proc is not None:
        try:
            result["procdump_exit"] = proc.wait(timeout=dump_wait_s)
            pd_text += fold_output(out_path, log_path)
        except subprocess.TimeoutExpired:
            say(f"ProcDump is still running {dump_wait_s:g} s after the game ended (a dump still being written?); "
                "left running: never kill it mid-dump")
            result["procdump_running"] = True
    if cw:
        new = dumps_since(values["crash_watch.folder"], before)
        if result.get("procdump_running"):     # no report yet: every new file is listed, and marked unconfirmed below
            result["dumps"] = new
        else:
            # only the dumps this run's ProcDump names in its report ("Dump 1 initiated: <path>"): a file another
            # ProcDump, left running after an earlier timeout, wrote meanwhile is not this game's (Codex, #449)
            result["dumps"] = [d for d in new if d in pd_text]
            if len(result["dumps"]) < len(new):
                result["dumps_other"] = [d for d in new if d not in result["dumps"]]
        note = " (a crash code and no dump)" if code not in (None, 0) and not result["dumps"] else ""
        if result["dumps"] and result.get("procdump_running"):
            result["dumps_unconfirmed"] = True
            note += " (still being written: not usable until ProcDump says it is complete)"
        elif result["dumps"] and not dumps_confirmed(pd_text, result["dumps"]):
            result["dumps_unconfirmed"] = True
            note += " (ProcDump did not report every dump complete: may be cut short, see the procdump lines)"
        _log(log_path, f"ended: process {pid}, {result['exit']}, after {result['seconds']} s up, dumps: "
                       f"{', '.join(result['dumps']) or 'none'}{note}"
                       + (f", ProcDump exit {result['procdump_exit']}" if "procdump_exit" in result else "")
                       + (f"; not this run's: {', '.join(result['dumps_other'])}" if result.get("dumps_other") else ""))
        if result["dumps"]:
            say("dumps: " + ", ".join(result["dumps"])
                + (" (NOT confirmed complete)" if result.get("dumps_unconfirmed") else "")
                + " (never upload a dump; docs/PLAY-AND-TEST.md)")
    return result


def watch(values, system=None, say=print, pid=None, repeat=False, start_timeout_s=600.0, dump_wait_s=3600.0,
          dry_run=False):
    """Watch a game something else starts (the test runner's own launch): wait for Starfield.exe (or process pid),
    let it settle, attach ProcDump as play does and log its end. Changes no setting and starts nothing. With repeat,
    goes on to the next game until none appears within start_timeout_s. Returns the list of results; raises
    ValueError on a refusal."""
    system = system or System()
    if not values["crash_watch.enabled"]:
        raise ValueError("crash watcher is off in the launcher settings (crash_watch.enabled): nothing to watch with")
    bad = [p for p in settings_mod.problems(values) if p.startswith("crash_watch.")]
    if values["crash_watch.procdump"] and not os.path.isfile(values["crash_watch.procdump"]):
        bad.append(f"crash_watch.procdump: {values['crash_watch.procdump']} not found")
    if values["crash_watch.folder"]:
        free = system.free_gb(values["crash_watch.folder"])
        if free < needed_free_gb(values):
            bad.append(f"crash watcher: {free:.1f} GB free for dumps, under {free_floor_text(values)}")
    if bad:
        raise ValueError("; ".join(bad))
    log_path = os.path.join(values["crash_watch.folder"], "crashwatch.log")
    what = f"process {pid}" if pid is not None else "the next Starfield.exe" + (" and each one after" if repeat else "")
    plan = [f"watch: {what}, attaching after {values['crash_watch.settle_s']:g} s",
            f"crash watcher: on, {values['crash_watch.dump']} dumps to {values['crash_watch.folder']}, "
            + ("a dump on every exit" if values["crash_watch.dump_on_exit"]
               else "log only when the game exits without a crash")]
    if dry_run:
        for p in plan:
            say(p)
        return [{"dry_run": True, "plan": plan}]
    try:
        os.makedirs(values["crash_watch.folder"], exist_ok=True)
        _log(log_path, f"watch: waiting for {what}")
    except OSError as e:
        raise ValueError(f"crash watcher: cannot write to {values['crash_watch.folder']} ({e.strerror or e})") from None
    results, seen = [], []
    while True:
        if results:                                 # each dump takes room: the floor holds for every game (Codex, #449)
            free = system.free_gb(values["crash_watch.folder"])
            if free < needed_free_gb(values):
                why = f"{free:.1f} GB free for dumps, under {free_floor_text(values)}; not watching the next game"
                _log(log_path, f"watch stopped: {why}")
                say(f"crash watcher stopped: {why}")
                results.append({"started": False, "stopped": why})
                return results
        t0 = system.now()
        r = _follow(values, system, say, t0, log_path, start_timeout_s, dump_wait_s, only_pid=pid, seen=seen)
        results.append(r)
        seen += r.get("early", []) + ([r["pid"]] if r.get("started") else [])
        if repeat and r.get("procdump_running"):    # never attach again while the last dump may still grow (Codex, #449)
            why = f"ProcDump on process {r['pid']} is still running; not watching the next game"
            _log(log_path, f"watch stopped: {why}")
            say(f"crash watcher stopped: {why}")
            results.append({"started": False, "stopped": why})
            return results
        if not (repeat and r.get("started") and pid is None):
            return results
