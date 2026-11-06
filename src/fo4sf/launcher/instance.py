"""The FO4SF game folder: a separate copy of Starfield that is always FO4SF, beside the player's own Starfield and its mod
packs (owner, 2026-11-01: "stay FO4SF all the time make a separate area then actual starfield so people can keep their
own mod packs for that"). Design and the steps after this one: docs/ai/fo4sf-instance.md.

This module plans and makes the folder; it never writes in the player's install.
* Data's game files and Tools (the Creation Kit's tools, gigabytes) are hard-linked into the new folder, so they cost no
  disk (a hard link is the same file under a second name). That needs the same drive: on another drive it refuses,
  since a copy would cost the whole game. A write into a linked file in place (not a new file put there) shows in both
  folders.
* Everything else is copied: the files at the top of the game folder (Starfield.exe, its DLLs, SFSE's loader: an SFSE
  update overwrites them in place, and the FO4SF folder may stay on an older game version), the other small folders,
  and every INI at any level, so the FO4SF folder's settings can change without changing the player's. A copy goes to a
  temporary name first and takes its own name only when complete.
* The player's own add-ons at the top of the game folder (injector DLLs such as dxgi.dll, ReShade and ENB files) and
  crash dumps are left out and listed, like the player's mods in Data.
* Data keeps only the game's own files: the plugins the game loads by itself (fo4sf.core.loadset.built_in) and the files
  named after them ("Starfield - Textures01.ba2", "SFBGS003 - Main.ba2", ...). Everything else in Data (the player's
  mods, our own installs, loose folders, SFSE plugins) is left out and listed, unless a Data folder is kept by name.
* The record FO4SF-instance.json in the new folder lists what was made; a run that stopped goes on from there, and a
  file that is already there and is not the one it would make is refused, never overwritten. Every file already there
  is checked before the record changes, so a refused rerun leaves a finished folder finished.
Read-only `plan` says all of it first: what is linked, copied and left out, and the disk it costs.
"""
import os
import shutil

from . import files
from fo4sf.core.loadset import built_in, is_plugin

RECORD = "FO4SF-instance.json"
SCHEMA = 1
GAME_EXE = "Starfield.exe"
COPY_EXT = (".ini",)                         # changed per folder: copied, never linked
PART = ".fo4sf-part"                         # a copy on its way: it takes its own name only when complete
# where a game folder should not be made (a Steam library, Program Files, a synced folder: the same advice the Starfield
# Launchpad Wabbajack instance gives, nexusmods.com/starfield/mods/18644)
BAD_PARTS = ("steamapps", "program files", "program files (x86)", "google drive", "my drive", "icloud drive",
             "iclouddrive", "box")
BAD_PREFIXES = ("onedrive", "dropbox")       # "OneDrive - Contoso", "Dropbox (Personal)", ...
LINK_DIRS = ("data", "tools")                # linked (Data: only the game's own files); the rest is copied
# the player's add-ons at the top of the game folder, never Starfield's own: proxy DLLs that injectors (ReShade, ENB,
# ASI loaders) put beside the exe, their files and folders, and crash dumps
ROOT_ADDONS = ("dxgi.dll", "d3d11.dll", "d3d12.dll", "dinput8.dll", "version.dll", "winmm.dll", "winhttp.dll",
               "opengl32.dll", "dsound.dll", "xinput1_3.dll", "xinput1_4.dll", "enblocal.ini", "enbseries.ini")
ROOT_ADDON_PREFIXES = ("reshade", "enbseries", "enbcache")
ROOT_ADDON_EXT = (".dmp", ".asi")


def _root_addon(name):
    n = name.casefold()
    return n in ROOT_ADDONS or n.startswith(ROOT_ADDON_PREFIXES) or n.endswith(ROOT_ADDON_EXT)


class InstanceRefused(ValueError):
    pass


def _parts(path):
    return [p.casefold() for p in os.path.normpath(os.path.abspath(path)).split(os.sep) if p]


def _is_link(path):
    """A symlink, or on Windows a directory junction (another reparse point that redirects a path)."""
    return os.path.islink(path) or bool(getattr(os.path, "isjunction", lambda _p: False)(path))


def _links_under(target):
    """Links and junctions anywhere in an existing target, without following any: each would carry a write elsewhere."""
    found, todo = [], [target]
    while todo:
        d = todo.pop()
        with os.scandir(d) as it:
            for e in it:
                if _is_link(e.path):
                    found.append(e.path)
                elif e.is_dir(follow_symlinks=False):
                    todo.append(e.path)
    return sorted(found)


def _real_dir(target, rel_dir):
    """target/rel_dir made of real directories only: a link or junction on the way is refused, never followed, and the
    result must resolve inside the resolved target. Missing directories are made one by one."""
    d = target
    for part in [p for p in rel_dir.split("/") if p]:
        d = os.path.join(d, part)
        if _is_link(d):
            raise InstanceRefused(f"{d} is a link or junction: a write through it would land outside the FO4SF folder")
        if not os.path.lexists(d):
            os.mkdir(d)
        elif not os.path.isdir(d):
            raise InstanceRefused(f"{d} is a file where a folder belongs; nothing overwritten")
    if not _inside(d, target):
        raise InstanceRefused(f"{d} resolves outside the FO4SF folder {target}")
    return d


def _inside(child, parent):
    c, p = os.path.normcase(os.path.realpath(child)), os.path.normcase(os.path.realpath(parent))
    try:
        return os.path.commonpath((c, p)) == p
    except ValueError:                        # another drive
        return False


def game_file(rel_in_data):
    """True for a file directly in Data that belongs to the game: a plugin it loads by itself, or a file named after one
    ("<stem> - anything", "<stem>.<ext>")."""
    name = rel_in_data.casefold()
    if is_plugin(name):
        return built_in(name)
    stem = name.split(" - ", 1)[0] if " - " in name else os.path.splitext(name)[0]
    return any(built_in(stem + ext) for ext in (".esm", ".esp", ".esl"))


def plan(source, target, keep_data_dirs=()):
    """{"link": [rel], "copy": [rel], "left_out": [rel], "link_bytes", "copy_bytes"} for making target from source
    (rel: "/" separators, relative to the game folder). Read only."""
    source = os.path.abspath(source)
    if not os.path.isfile(os.path.join(source, GAME_EXE)):
        raise InstanceRefused(f"{source} is not a Starfield game folder (no {GAME_EXE})")
    keep = {k.casefold().strip("/\\") for k in keep_data_dirs}
    out = {"link": [], "copy": [], "left_out": [], "link_bytes": 0, "copy_bytes": 0}
    for d, dirs, names in os.walk(source):
        dirs.sort()
        rel_d = os.path.relpath(d, source).replace(os.sep, "/")
        rel_d = "" if rel_d == "." else rel_d
        parts = rel_d.split("/") if rel_d else []
        top = parts[0].casefold() if parts else ""
        if len(parts) == 1 and top == "data":
            for sub in list(dirs):                           # Data's folders: left out unless kept by name
                if sub.casefold() not in keep:
                    out["left_out"].append(f"{rel_d}/{sub}/")
                    dirs.remove(sub)
        if not parts:
            for sub in list(dirs):                           # the player's injector folders (reshade-shaders, ...)
                if _root_addon(sub):
                    out["left_out"].append(f"{sub}/")
                    dirs.remove(sub)
        for n in sorted(names):
            rel = f"{rel_d}/{n}" if rel_d else n
            size = os.path.getsize(os.path.join(d, n))
            if (len(parts) == 1 and top == "data" and not game_file(n)) or (not parts and _root_addon(n)):
                out["left_out"].append(rel)
            elif n.casefold().endswith(COPY_EXT) or top not in LINK_DIRS:
                out["copy"].append(rel)
                out["copy_bytes"] += size
            else:
                out["link"].append(rel)
                out["link_bytes"] += size
    return out


def _device(path):
    return os.stat(path).st_dev


def check_target(source, target, min_free_gb, copy_bytes, disk_usage=shutil.disk_usage):
    """Problems with making target (refused before anything is written)."""
    target = os.path.abspath(target)
    if _inside(target, source) or _inside(source, target):
        raise InstanceRefused("the FO4SF folder must be outside the Starfield install (and not hold it)")
    # the spelling given and the path it resolves to (a junction or symlink may alias a Steam library)
    bad = [p for p in _parts(target) + _parts(os.path.realpath(target))
           if p in BAD_PARTS or p.startswith(BAD_PREFIXES)]
    if bad:
        raise InstanceRefused(f"{target} is inside {bad[0]!r}: put the FO4SF folder elsewhere, for example D:\\FO4SF\\"
                              "Starfield (Steam, Program Files and synced folders can move or lock its files)")
    if os.path.exists(target) and not os.path.isdir(target):
        raise InstanceRefused(f"{target} is a file")
    if os.path.isdir(target) and os.listdir(target) and not os.path.isfile(os.path.join(target, RECORD)):
        raise InstanceRefused(f"{target} is not empty and is no FO4SF game folder (no {RECORD}): pick an empty one")
    links = _links_under(target) if os.path.isdir(target) else []
    if links:
        raise InstanceRefused(f"{links[0]} is a link or junction inside the FO4SF folder: remove it first (a write "
                              "through it would land outside the folder)")
    parent = target
    while not os.path.isdir(parent):
        up = os.path.dirname(parent)
        if up == parent:                          # a drive or share that is not there (Z:\ is its own dirname)
            raise InstanceRefused(f"{target}: no such drive or share")
        parent = up
    if _device(parent) != _device(source):
        raise InstanceRefused(f"{target} is on another drive than {source}: hard links need the same drive (a copy "
                              "would cost the whole game)")
    free = disk_usage(parent).free - copy_bytes
    if free < min_free_gb * 1024 ** 3:
        raise InstanceRefused(f"{free / 1024 ** 3:.1f} GB would be left free, under {min_free_gb:g} GB")


def _same_link(src, dst):
    return not _is_link(dst) and os.path.samefile(src, dst)


def _own_copy(src, dst, recorded):
    """dst is the folder's own copy of src: a plain file with no second name (not the game's file, not linked elsewhere).
    A recorded copy may have changed since (the folder's INI is its own); one the record lacks must still be byte for
    byte the game's (a run that stopped between the copy and its record)."""
    if _is_link(dst) or not os.path.isfile(dst) or os.lstat(dst).st_nlink != 1:
        return False
    if recorded:
        return True
    import filecmp
    return filecmp.cmp(src, dst, shallow=False)


def create(source, target, keep_data_dirs=(), min_free_gb=40.0, say=print, disk_usage=shutil.disk_usage, link=os.link):
    """Make (or finish) the FO4SF game folder; returns the plan. Never writes in source, never overwrites a file."""
    source, target = os.path.abspath(source), os.path.abspath(target)
    p = plan(source, target, keep_data_dirs)
    rec_p = os.path.join(target, RECORD)
    rec = files.load_json(rec_p) if os.path.isfile(rec_p) else None
    if rec is not None and os.path.normcase(os.path.abspath(rec.get("source", ""))) != os.path.normcase(source):
        raise InstanceRefused(f"{target} was made from {rec.get('source')}, not {source}")
    check_target(source, target, min_free_gb, p["copy_bytes"], disk_usage)
    rec = rec or {"schema": SCHEMA, "source": source, "made": [], "complete": False}
    made = set(rec["made"])
    todo = [(r, "link") for r in p["link"]] + [(r, "copy") for r in p["copy"]]
    # every file already there is checked before the record changes: a refusal leaves a finished folder finished
    found = []
    for rel, how in todo:
        src = os.path.join(source, *rel.split("/"))
        dst = os.path.join(target, *rel.split("/"))
        if os.path.lexists(dst):
            if not (_same_link(src, dst) if how == "link" else _own_copy(src, dst, rel in made)):
                raise InstanceRefused(f"{dst} is already there and is not the game's file; nothing overwritten")
            if rel not in made:
                found.append(rel)                    # made by a run that stopped before its record was saved
    os.makedirs(target, exist_ok=True)
    rec["made"] += found
    rec.update({"left_out": p["left_out"], "keep_data_dirs": sorted(keep_data_dirs), "complete": False})
    files.save_json(rec_p, rec)
    for k, (rel, how) in enumerate(todo):
        src = os.path.join(source, *rel.split("/"))
        dst = os.path.join(target, *rel.split("/"))
        if os.path.lexists(dst):
            continue                                 # checked above
        _real_dir(target, os.path.dirname(rel))         # checked again per file: nothing written through a link
        if how == "link":
            link(src, dst)
        else:
            part = dst + PART
            if os.path.lexists(part):                # our own copy that stopped half way
                if _is_link(part) or not os.path.isfile(part):
                    raise InstanceRefused(f"{part} is not a file of ours; nothing overwritten")
                os.remove(part)
            shutil.copy2(src, part)
            os.replace(part, dst)
        rec["made"].append(rel)
        if how == "copy" or k % 200 == 199:
            files.save_json(rec_p, rec)              # a stop loses at most 200 links: the rerun finds them by samefile
    rec["complete"] = True
    files.save_json(rec_p, rec)
    say(f"FO4SF game folder ready: {target} ({len(p['link'])} files linked, {len(p['copy'])} copied, "
        f"{len(p['left_out'])} left out)")
    return p


def summary(p):
    """Lines that say what a plan would do."""
    gb = 1024 ** 3
    lines = [f"linked (no extra disk; Data's game files and Tools): {len(p['link'])} files, "
             f"{p['link_bytes'] / gb:.1f} GB",
             f"copied (the rest, and every INI): {len(p['copy'])} files, {p['copy_bytes'] / 1024 ** 2:.0f} MB",
             f"left out (the player's mods and add-ons, crash dumps; not the game's own): {len(p['left_out'])}"]
    lines += [f"    {r}" for r in p["left_out"][:40]]
    if len(p["left_out"]) > 40:
        lines.append(f"    ... and {len(p['left_out']) - 40} more")
    return lines


# --- playing from the folder (docs/ai/fo4sf-instance.md steps 2 to 4) ------------------------------------------------
LOCAL = "FO4SF-local"                 # the folder's own LOCALAPPDATA: <folder>\FO4SF-local\Starfield\Plugins.txt
SWAP = "FO4SF-swap.json"              # the journal of a Plugins.txt swap, while FO4SF's list stands in the player's place
SAVES = "Saves\\FO4SF\\"              # SLocalSavePath: the folder's saves, apart from the player's (H3)


def journal_path(player):
    """The swap journal, at a fixed place beside the launcher's settings (%LOCALAPPDATA%\\FO4SF), never in the FO4SF
    folder: every start finds it whatever the setting `instance` says now, and removing the folder cannot lose it."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(player))), "FO4SF", SWAP)


def pending(player):
    """The journal of a swap that was not put back (None when there is none): a dry run reports it, never acts."""
    j = journal_path(player)
    return files.load_json(j) if os.path.exists(j) else None


def local_dir(folder):
    return os.path.join(os.path.abspath(folder), LOCAL)


def plugins_txt(folder):
    """The folder's own Plugins.txt: every installer of ours writes it when LOCALAPPDATA is local_dir(folder)."""
    return os.path.join(local_dir(folder), "Starfield", "Plugins.txt")


def player_plugins_txt(environ=os.environ):
    """The Plugins.txt the game reads (the player's): %LOCALAPPDATA%\\Starfield\\Plugins.txt of this process."""
    local = environ.get("LOCALAPPDATA", "")
    if not local or not os.path.isabs(local):
        raise InstanceRefused("LOCALAPPDATA is not set: the player's Plugins.txt cannot be found")
    return os.path.join(local, "Starfield", "Plugins.txt")


def check_ready(folder):
    """Refuses a folder that is not a finished FO4SF game folder."""
    rec_p = os.path.join(folder, RECORD)
    if not os.path.isfile(rec_p) or not files.load_json(rec_p).get("complete"):
        raise InstanceRefused(f"{folder} is not a finished FO4SF game folder: `launcher.py instance create` it first")
    if not os.path.isfile(os.path.join(folder, GAME_EXE)):
        raise InstanceRefused(f"{folder} has no {GAME_EXE}")


def env_for(folder, environ=os.environ):
    """The environment our tools run in for this folder: its own Plugins.txt instead of the player's."""
    return dict(environ, LOCALAPPDATA=local_dir(folder))


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _sha(raw):
    import hashlib
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def _put(path, raw, expect):
    """Write (or remove, raw None) Plugins.txt, refused when it changed since read (expect: its sha256 then)."""
    import base64
    from . import restore
    os.makedirs(os.path.dirname(path), exist_ok=True)
    restore.write_plugins_txt(path, None if raw is None else base64.b64encode(raw).decode("ascii"), expect)


def swap_in(folder, player, say=print):
    """Put the folder's list where the game reads it, after journaling the player's own bytes (journal_path). Refuses
    while a journal is left from an earlier swap (recover() first)."""
    import base64
    journal = journal_path(player)
    if os.path.exists(journal):
        raise InstanceRefused(f"{journal} is left from an earlier start: the player's Plugins.txt is put back first")
    mine, ours = _read(player), _read(plugins_txt(folder))
    ours = b"" if ours is None else ours
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    if mine is not None:                               # a second copy outside the journal, kept: cheap insurance
        import datetime
        bak = os.path.join(os.path.dirname(journal),
                           "player-Plugins.txt.bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        if not os.path.exists(bak):
            with open(bak, "wb") as f:
                f.write(mine)
    files.save_json(journal, {"schema": 2, "player": player, "folder": os.path.abspath(folder),
                              "wrote_sha256": _sha(ours),
                              "player_b64": None if mine is None else base64.b64encode(mine).decode("ascii")})
    try:
        _put(player, ours, _sha(mine))
    except BaseException:
        if _read(player) == mine:                      # nothing was swapped: the journal goes with it
            os.remove(journal)
        raise                                          # else the write landed: the journal stays for recover()
    say(f"Plugins.txt: FO4SF's list in place for this start (yours is kept in {journal} and comes back at the end)")


def _keep_after(base, raw):
    """Keep raw at base (or base-2, base-3, ...), never overwriting. A kept list beside it with the same bytes, from
    any earlier second, is that same evidence from an attempt that stopped before the player's list was back, so it
    is reused instead of copied again."""
    folder, stem = os.path.dirname(base), os.path.basename(base).rsplit(".after-", 1)[0] + ".after-"
    os.makedirs(folder, exist_ok=True)
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if name.startswith(stem) and os.path.isfile(path) and not os.path.islink(path) and _read(path) == raw:
            return path
    for n in range(1, 1000):
        path = base if n == 1 else f"{base}-{n}"
        try:
            with open(path, "xb") as f:
                f.write(raw)
            return path
        except FileExistsError:
            if _read(path) == raw:
                return path
    raise InstanceRefused(f"{base}: too many kept lists; move some away")


def swap_out(player, say=print, after_game=True):
    """Put the player's list back from the journal. after_game: the game ran from the journal's folder and may have
    rewritten FO4SF's list (it does at every start), so that becomes the folder's list. A recovery (the launcher did not
    see the end), or a folder no longer there, keeps what stands there as Plugins.txt.after-<time> beside the journal
    instead, since it cannot tell whose rewrite it is."""
    import base64
    import datetime
    journal = journal_path(player)
    if not os.path.exists(journal):
        return False
    j = files.load_json(journal)
    player, now = j["player"], _read(j["player"])
    mine = None if j.get("player_b64") is None else base64.b64decode(j["player_b64"])
    if now == mine:                                    # already back (a put-back cut before the journal went)
        os.remove(journal)
        say("Plugins.txt: yours is back")
        return True
    if now is not None and _sha(now) != j["wrote_sha256"]:
        if after_game and os.path.isdir(j["folder"]):
            ours_p = plugins_txt(j["folder"])
            _put(ours_p, now, _sha(_read(ours_p)))
        else:
            keep = _keep_after(os.path.join(os.path.dirname(journal), "Plugins.txt.after-"
                                            + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")), now)
            say(f"Plugins.txt: what stood in its place is kept as {keep}")
    _put(player, mine, _sha(now))
    os.remove(journal)
    say("Plugins.txt: yours is back")
    return True


def recover(player, running, say=print):
    """A journal left by a launcher that did not see the game end (a crash, a power cut): put the player's list back
    once Starfield is closed. True when it did. Every `play` calls it first, with or without the setting `instance`."""
    if not os.path.exists(journal_path(player)):
        return False
    if running():
        raise InstanceRefused("Starfield is running with FO4SF's Plugins.txt in place: close it, then start again")
    return swap_out(player, say, after_game=False)


def set_ini_key(text, section, key, value):
    """INI text with key=value in [section] (the section added at the end if missing); other lines and their endings
    kept. (new text, changed)."""
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    out, in_sec, done, found = [], False, False, False
    for ln in lines:
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            if in_sec and not done:
                out.append(f"{key}={value}{nl}")
                done = True
            in_sec = s[1:-1].strip().casefold() == section.casefold()
            found = found or in_sec
        elif in_sec and "=" in s and s.split("=", 1)[0].strip().casefold() == key.casefold():
            if s.split("=", 1)[1].strip() == value:
                return text, False
            ln = f"{key}={value}" + ln[len(ln.rstrip("\r\n")):]
            done = True
        out.append(ln)
    if in_sec and not done:
        if out and not out[-1].endswith(("\n", "\r")):
            out[-1] += nl
        out.append(f"{key}={value}{nl}")
        done = True
    if not found:
        if out and not out[-1].endswith(("\n", "\r")):
            out[-1] += nl
        out += [f"[{section}]{nl}", f"{key}={value}{nl}"]
    return "".join(out), True


def ensure_saves(folder, say=print):
    """SLocalSavePath in the folder's own Starfield.ini, so its saves go to My Games\\Starfield\\Saves\\FO4SF (H3)."""
    ini = os.path.join(folder, "Starfield.ini")
    if _is_link(ini) or (os.path.lexists(ini) and os.lstat(ini).st_nlink > 1):
        raise InstanceRefused(f"{ini} is a link or has a second name (the Steam install's?): it must be the folder's "
                              "own copy")
    raw = _read(ini) or b""
    text = raw.decode("utf-8", "surrogateescape")
    new, changed = set_ini_key(text, "General", "SLocalSavePath", SAVES)
    if changed:
        part = ini + PART                              # a new file put in place: never a write into an old one
        with open(part, "wb") as f:
            f.write(new.encode("utf-8", "surrogateescape"))
        os.replace(part, ini)
        say(f"saves: the FO4SF folder saves to My Games\\Starfield\\{SAVES} (its Starfield.ini)")


def custom_ini_problems(my_games, values):
    """What My Games' StarfieldCustom.ini says that would undo the folder's own Starfield.ini (it wins over it, and both
    Starfields read it): its own saves path, or Papyrus logging off under bridge=on. [] when it says neither."""
    raw = _read(os.path.join(my_games, "StarfieldCustom.ini")) if my_games else None
    if raw is None:
        return []
    keys, sec = {}, ""
    for ln in raw.decode("utf-8-sig", "surrogateescape").splitlines():   # Notepad may save a BOM
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1].strip().casefold()
        elif "=" in s and not s.startswith((";", "#")):
            k, v = s.split("=", 1)
            keys[(sec, k.strip().casefold())] = v.strip()
    out = []
    if keys.get(("general", "slocalsavepath")):
        out.append(f"StarfieldCustom.ini sets SLocalSavePath={keys[('general', 'slocalsavepath')]}, which overrides the "
                   "FO4SF folder's own saves folder: remove that line to keep the two games' saves apart")
    if values.get("bridge") == "on" and keys.get(("papyrus", "benablelogging")) == "0":
        out.append("StarfieldCustom.ini sets bEnableLogging=0, which overrides the FO4SF folder's own Papyrus logging, "
                   "so the bridge would be blind: remove that line or use bridge=off")
    return out


def run(folder, cmd, *, running=lambda: False, cwd=None, call=None):
    """Run one of our tools (an installer, plugin_toggle.py, load_order.py) on the folder, with its own Plugins.txt.
    Refused while Starfield runs, and unless the command names this folder by exactly one --starfield (or a prefix of it
    that argparse would take, --starf), resolved from the command's own working folder: a tool's default --starfield is
    the player's install, so the target is never left to it. Returns the command's exit code."""
    import subprocess
    check_ready(folder)
    if not cmd:
        raise InstanceRefused("instance run needs a command after --")
    if running():
        raise InstanceRefused("Starfield is running: close it first")
    targets = []
    for i, arg in enumerate(cmd):
        name, eq, value = arg.partition("=")
        if len(name) >= 3 and name.startswith("--") and "--starfield".startswith(name):
            targets.append(value if eq else (cmd[i + 1] if i + 1 < len(cmd) else ""))
    if len(targets) != 1:
        raise InstanceRefused(f"the command must name the FO4SF game folder once, as --starfield {folder} "
                              f"({len(targets)} --starfield found)")
    target = os.path.join(cwd or os.getcwd(), targets[0])
    if os.path.normcase(os.path.abspath(target)) != os.path.normcase(os.path.abspath(folder)):
        raise InstanceRefused(f"the command's --starfield {targets[0]} is not the FO4SF game folder {folder}")
    return (call or subprocess.call)(cmd, cwd=cwd, env=env_for(folder))
