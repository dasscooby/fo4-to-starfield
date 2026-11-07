"""Optional tkinter front end to launcher.py. Importing this module needs no display or tkinter.

SettingsModel is headless. Commands are argv lists for the existing CLI; no build, install, settings validation,
game-start or crash-watch implementation lives here. Tk and OS folder opening are used only after opening the UI.
"""
import os
import queue
import subprocess
import sys
import threading

from . import paths, settings


def controls():
    """The Settings tab's widgets come from the same specification as `settings --show`; the file locations are on
    the Locations tab instead (paths.LOCATIONS)."""
    return [{"key": key, "label": settings.LABELS[key], "default": default, "cost": cost,
             "kind": "bool" if kind is bool else "choice" if isinstance(kind, tuple) else "text",
             "choices": kind if isinstance(kind, tuple) else ()}
            for key, default, kind, cost in settings.SPEC if key not in paths.KEYS]


class SettingsModel:
    def __init__(self, launcher, path):
        self.launcher = os.path.abspath(launcher)
        self.path = os.path.abspath(path)
        self.reload()

    def reload(self):
        self.saved = settings.load(self.path)

    def values(self, raw):
        if set(raw) != set(settings.KEYS):
            raise ValueError("The settings fields do not match the launcher's settings specification")
        return {key: settings.coerce(key, raw[key]) for key in settings.KEYS}

    def command(self, action, raw=None, *, recipe="", overrides=(), fo4_data=(), starfield="", my_games="",
                pids=None, windows=None):
        argv = [sys.executable, "-I", "-u", self.launcher]
        if action == "save":
            values = self.values(raw)
            pairs = [f"{key}={str(value).lower() if isinstance(value, bool) else value}"
                     for key, value in values.items() if value != self.saved[key]]
            # Do not even open a file for writing on an unchanged Save (including a missing settings file).
            if not pairs:
                return None
            return argv + ["settings", "--settings", self.path] + [a for p in pairs for a in ("--set", p)]
        if action == "status":
            if not recipe:
                raise ValueError("Choose a build recipe first")
            return argv + ["status", recipe] + [a for p in overrides for a in ("--set", p)]
        if action == "detect":
            fo4_data = fo4_data or paths.split_dirs(self.saved["fo4_data"])
            starfield = starfield or self.saved["starfield"]
            if not fo4_data or not starfield:
                raise ValueError("Confirm the Fallout 4 Data and Starfield folders on the Locations tab first")
            # this window's settings file, never the default one: my_games falls back to it (Codex, #481)
            argv += ["detect", "--settings", self.path, "--starfield", starfield]
            argv += [a for path in fo4_data for a in ("--fo4-data", path)]
            my_games = my_games or self.saved["my_games"]       # the folder on screen first (Codex, #481)
            if my_games:
                argv += ["--my-games", my_games]
            return argv  # no --report or other output argument: the status panes are read-only
        if action == "update-check":
            return argv + ["update", "--check"]                 # fetches; changes nothing
        if action == "update":
            return argv + ["update"]                            # a fast-forward of a clean main only (selfupdate.py)
        if action == "play":
            starfield = starfield or (raw or self.saved).get("starfield", "")
            reason = self.play_reason(raw, starfield, pids, windows=windows)
            if reason:
                raise ValueError(reason)
            try:
                current = settings.load(self.path)
            except OSError as e:
                raise ValueError(f"Cannot read saved settings: {e}") from None
            if current != self.saved:
                raise ValueError("Settings changed outside this window; reload settings before playing")
            folder = current.get("instance")               # the FO4SF game folder: play starts that one
            return argv + ["play", "--settings", self.path, "--starfield", folder or starfield]
        raise ValueError(f"Unknown window action {action!r}")

    def play_reason(self, raw, starfield, pids, *, windows=None):
        if windows is None:
            windows = os.name == "nt"
        if not windows:
            return "Playing is available on Windows"
        if pids is None:
            return "Checking whether Starfield is running"
        if pids:
            return "Starfield is already running (PID " + ", ".join(map(str, pids)) + ")"
        try:
            values = self.values(raw)
        except ValueError as e:
            return str(e)
        problems = settings.problems(values)
        if problems:
            return "; ".join(problems)
        changed = {k for k in settings.KEYS if values[k] != self.saved[k]}
        if changed and changed <= set(paths.KEYS):
            return "Confirm the locations before playing (Locations tab)"
        if changed:
            return "Save the changed settings before playing"
        if not (starfield or values["starfield"]):
            return "Choose the Starfield folder first (Locations tab)"
        # a saved location can stop working (the game moved): Play waits until it is fixed (Codex, #481)
        for key in paths.needed(values):
            problem = paths.check(key, starfield or values[key] if key == "starfield" else values[key])
            if problem:
                return f"{settings.LABELS[key]}: {problem} (Locations tab)"
        return ""

    def part(self, raw, part="all"):
        """raw with the other half put back to the saved values: "settings" keeps the saved locations, so Save
        settings never saves a found path the player has not confirmed; "locations" keeps the saved settings (Codex,
        #481)."""
        if part == "all":
            return dict(raw)
        if part not in ("settings", "locations"):
            raise ValueError(f"Unknown part {part!r}")
        keep = [k for k in raw if (k in paths.KEYS) == (part == "settings")]
        return dict(raw, **{k: self.saved[k] for k in keep if k in self.saved})

    def locations(self, found, prefer=(), dirty=()):
        """Rows for the Locations tab: the saved value, or what was found and waits for the player's yes. dirty are
        locations the player typed or browsed and has not saved: a late detection never overwrites them (Codex,
        #481)."""
        return [r for r in paths.rows(self.saved, found, prefer) if r["key"] not in dirty]


REPORT_ACTIONS = ("status", "detect", "update-check", "update")    # their output shows on the Status tab


def run_command(argv, on_line, *, popen=subprocess.Popen):
    """Stream a single existing CLI command; the UI calls this on a worker, never on the Tk thread."""
    repo = os.path.dirname(os.path.dirname(argv[3]))
    with popen(argv, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
               text=True, errors="replace", bufsize=1) as proc:
        for line in proc.stdout:
            on_line(line)
        return proc.wait()


# A dark terminal look (owner, 2026-10-22: "more code terminal but less 90s"): one monospace face, flat panels,
# a single accent for the next thing to press, and green/amber/red only for state.
PALETTE = {"bg": "#0d1117", "panel": "#161b22", "field": "#010409", "border": "#30363d", "fg": "#e6edf3",
           "muted": "#8b949e", "accent": "#58a6ff", "ok": "#3fb950", "warn": "#d29922", "bad": "#f85149"}
MONO = ("Cascadia Mono", "Cascadia Code", "JetBrains Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono",
        "Liberation Mono")
MARKS = {"saved": ("✓ saved", "ok"), "found": ("? confirm", "warn"), "edited": ("• edited", "warn"),
         "problem": ("✗ problem", "bad"), "missing": ("✗ missing", "bad")}


def pick_font(families):
    for name in MONO:
        if name in families:
            return name
    return "TkFixedFont"


def apply_theme(root, ttk, tkfont):
    c = PALETTE
    face = pick_font(set(tkfont.families(root)))
    base, small, title = (face, 10), (face, 9), (face, 13, "bold")
    root.configure(background=c["bg"])
    root.option_add("*TCombobox*Listbox.background", c["field"])
    root.option_add("*TCombobox*Listbox.foreground", c["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
    root.option_add("*TCombobox*Listbox.font", base)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=c["bg"], foreground=c["fg"], font=base, bordercolor=c["border"],
                 lightcolor=c["border"], darkcolor=c["border"], troughcolor=c["panel"], focuscolor=c["accent"],
                 selectbackground=c["accent"], selectforeground=c["bg"], insertcolor=c["fg"])
    st.configure("TFrame", background=c["bg"])
    st.configure("Panel.TFrame", background=c["panel"])
    st.configure("TLabel", background=c["bg"], foreground=c["fg"])
    st.configure("Muted.TLabel", foreground=c["muted"], font=small)
    st.configure("Title.TLabel", foreground=c["accent"], font=title)
    for name in ("ok", "warn", "bad"):
        st.configure(f"{name}.TLabel", foreground=c[name])
    st.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
    st.configure("TNotebook.Tab", background=c["panel"], foreground=c["muted"], padding=(16, 6), borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", c["bg"])], foreground=[("selected", c["fg"])])
    st.configure("TButton", background=c["panel"], foreground=c["fg"], padding=(12, 5), borderwidth=1, relief="flat")
    st.map("TButton", background=[("disabled", c["bg"]), ("active", c["border"])],
           foreground=[("disabled", c["muted"])], bordercolor=[("focus", c["accent"]), ("active", c["accent"])])
    st.configure("Accent.TButton", background=c["accent"], foreground=c["bg"], font=(face, 10, "bold"))
    st.map("Accent.TButton", background=[("disabled", c["panel"]), ("active", "#79b8ff")],
           foreground=[("disabled", c["muted"])])
    st.configure("TEntry", fieldbackground=c["field"], foreground=c["fg"], padding=5, insertcolor=c["fg"])
    st.map("TEntry", bordercolor=[("focus", c["accent"])])
    st.configure("TCombobox", fieldbackground=c["field"], background=c["panel"], foreground=c["fg"],
                 arrowcolor=c["fg"], padding=4)
    st.map("TCombobox", fieldbackground=[("readonly", c["field"])], foreground=[("readonly", c["fg"])],
           bordercolor=[("focus", c["accent"])])
    st.configure("TCheckbutton", background=c["bg"], foreground=c["fg"], indicatorbackground=c["field"],
                 indicatorforeground=c["accent"])
    st.map("TCheckbutton", background=[("active", c["bg"])], indicatorbackground=[("selected", c["field"])])
    st.configure("Vertical.TScrollbar", background=c["panel"], arrowcolor=c["muted"], borderwidth=0)
    text = {"background": c["field"], "foreground": c["fg"], "insertbackground": c["fg"], "font": base,
            "relief": "flat", "highlightthickness": 1, "highlightbackground": c["border"],
            "highlightcolor": c["accent"], "selectbackground": c["accent"], "selectforeground": c["bg"],
            "padx": 8, "pady": 6}
    return text


def launch(launcher, path, *, recipe="", overrides=(), fo4_data=(), starfield=""):
    # The CLI's --help and every other subcommand work even when Python has no tkinter or display.
    try:
        import tkinter as tk
        from tkinter import filedialog, font as tkfont, messagebox, ttk
        from tkinter.scrolledtext import ScrolledText
    except ImportError:
        raise ValueError("The launcher window needs Python's tkinter; the command-line launcher still works") from None
    model = SettingsModel(launcher, path)
    try:
        root = tk.Tk()
    except tk.TclError as e:
        raise ValueError(f"Cannot open the launcher window: {e}") from None
    text_style = apply_theme(root, ttk, tkfont)
    # paths given on the command line are offered like found ones: the player still confirms them
    given = {}
    if starfield:
        given["starfield"] = (os.path.normpath(starfield), "command line")
    if fo4_data:
        given["fo4_data"] = (paths.join_dirs(fo4_data), "command line")

    class Window:
        def __init__(self):
            self.events = queue.Queue()
            self.busy, self.closed, self.action = False, False, ""
            self.pids, self.process_error = None, ""
            self.found = dict(given)
            self.dirty = set()                     # locations the player typed or browsed and has not saved yet
            self.widgets, self.vars, self.loc = [], {}, {}
            root.title("FO4SF Launcher")
            root.geometry("1020x760")
            root.minsize(800, 600)
            root.columnconfigure(0, weight=1)
            root.rowconfigure(1, weight=1)

            header = ttk.Frame(root, style="Panel.TFrame", padding=(16, 10))
            header.grid(row=0, column=0, sticky="ew")
            header.columnconfigure(1, weight=1)
            ttk.Label(header, text="fo4sf ▸ launcher", style="Title.TLabel", background=PALETTE["panel"]).grid(
                row=0, column=0, sticky="w")
            self.game = tk.StringVar(value="● game: checking…")
            self.game_label = ttk.Label(header, textvariable=self.game, style="Muted.TLabel",
                                        background=PALETTE["panel"])
            self.game_label.grid(row=0, column=1, sticky="e")

            self.notebook = ttk.Notebook(root)
            self.notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 0))
            places, status, config, logs = (ttk.Frame(self.notebook, padding=16) for _ in range(4))
            for frame, label in ((places, "Locations"), (status, "Status"), (config, "Settings"),
                                 (logs, "Log")):
                self.notebook.add(frame, text=label)
            self.places_tab = places
            self.build_locations(places)
            self.build_status(status)
            self.build_settings(config)
            self.build_log(logs)

            footer = ttk.Frame(root, padding=(16, 10))
            footer.grid(row=2, column=0, sticky="ew")
            footer.columnconfigure(0, weight=1)
            self.message = tk.StringVar(value="Looking for the game folders…")
            ttk.Label(footer, textvariable=self.message, wraplength=640).grid(row=0, column=0, sticky="w")
            self.reason = tk.StringVar()
            ttk.Label(footer, textvariable=self.reason, style="Muted.TLabel", wraplength=640).grid(
                row=1, column=0, sticky="w")
            reload_button = ttk.Button(footer, text="Reload", command=self.reload_settings)
            reload_button.grid(row=0, column=1, rowspan=2, padx=(8, 0))
            save = ttk.Button(footer, text="Save settings", command=lambda: self.start("save", part="settings"))
            save.grid(row=0, column=2, rowspan=2, padx=(8, 0))
            self.play = ttk.Button(footer, text="▶  Play", style="Accent.TButton", command=lambda: self.start("play"))
            self.play.grid(row=0, column=3, rowspan=2, padx=(8, 0))
            self.widgets += [(reload_button, "normal"), (save, "normal")]
            for var in self.vars.values():
                var.trace_add("write", lambda *_args: self.refresh_play())
            root.protocol("WM_DELETE_WINDOW", self.close)
            self.render_locations()
            self.refresh_play()
            self.detect_locations()
            root.after(75, self.drain)
            self.poll_processes()

        # --- Locations ---------------------------------------------------------------------------------------
        def build_locations(self, tab):
            tab.columnconfigure(2, weight=1)
            ttk.Label(tab, text="The launcher looked for everything it needs on this PC. Check each path; "
                                "Browse to change one, then press Confirm locations.",
                      style="Muted.TLabel", wraplength=860).grid(row=0, column=0, columnspan=4, sticky="w",
                                                                  pady=(0, 12))
            for i, (key, label, kind, what) in enumerate(paths.LOCATIONS):
                r = 1 + 2 * i
                ttk.Label(tab, text=label).grid(row=r, column=0, sticky="nw", padx=(0, 12), pady=(6, 0))
                mark = ttk.Label(tab, text="", width=11)
                mark.grid(row=r, column=1, sticky="nw", pady=(6, 0))
                if kind == "dirs":
                    entry = tk.Text(tab, height=3, wrap="none", **text_style)
                    entry.bind("<<Modified>>", lambda _e, k=key: self.location_edited(k))
                else:
                    var = tk.StringVar()
                    entry = ttk.Entry(tab, textvariable=var)
                    entry.var = var
                    var.trace_add("write", lambda *_a, k=key: self.location_edited(k))
                entry.grid(row=r, column=2, sticky="ew", pady=(4, 0))
                browse = ttk.Button(tab, text="Browse…", command=lambda k=key, kd=kind: self.browse(k, kd))
                browse.grid(row=r, column=3, sticky="ne", padx=(8, 0), pady=(4, 0))
                note = ttk.Label(tab, text=what, style="Muted.TLabel", wraplength=640)
                note.grid(row=r + 1, column=2, columnspan=2, sticky="w", pady=(2, 6))
                self.loc[key] = {"entry": entry, "mark": mark, "note": note, "what": what, "kind": kind,
                                 "status": "missing", "quiet": False}
                self.widgets += [(entry, "normal"), (browse, "normal")]
            buttons = ttk.Frame(tab)
            buttons.grid(row=2 + 2 * len(paths.LOCATIONS), column=0, columnspan=4, sticky="e", pady=(12, 0))
            again = ttk.Button(buttons, text="Detect again", command=self.detect_locations)
            again.pack(side="left", padx=(0, 8))
            confirm = ttk.Button(buttons, text="Confirm locations", style="Accent.TButton",
                                 command=self.confirm_locations)
            confirm.pack(side="left")
            self.widgets += [(again, "normal"), (confirm, "normal")]

        def location_value(self, key):
            e = self.loc[key]["entry"]
            if self.loc[key]["kind"] == "dirs":
                return paths.join_dirs(e.get("1.0", "end").splitlines())
            return e.var.get().strip()

        def set_location(self, key, value):
            e, item = self.loc[key]["entry"], self.loc[key]
            item["quiet"] = True
            if item["kind"] == "dirs":
                e.configure(state="normal")
                e.delete("1.0", "end")
                e.insert("1.0", "\n".join(paths.split_dirs(value)))
                e.edit_modified(False)
            else:
                e.var.set(value)
            item["quiet"] = False

        def show_mark(self, key, status, note):
            text, colour = MARKS[status]
            item = self.loc[key]
            item["status"] = status
            item["mark"].configure(text=text, style=f"{colour}.TLabel")
            item["note"].configure(text=f"{item['what']}  ·  {note}" if note else item["what"])

        def render_locations(self):
            for row in model.locations(self.found, prefer=given, dirty=self.dirty):
                self.set_location(row["key"], row["value"])
                self.show_mark(row["key"], row["status"], row["note"])
            self.refresh_play()

        def location_edited(self, key):
            item = self.loc[key]
            if item["kind"] == "dirs":
                if not item["entry"].edit_modified():
                    return
                item["entry"].edit_modified(False)
            if item["quiet"]:
                return
            given.pop(key, None)                       # the player's own choice now beats the command line (Codex, #481)
            self.dirty.add(key)
            value = self.location_value(key)
            problem = paths.check(key, value) if value else "not set"
            if value == model.saved[key] and not problem:
                self.show_mark(key, "saved", "saved")
            else:
                self.show_mark(key, "problem" if problem else "edited", problem or "press Confirm locations")
            self.refresh_play()

        def browse(self, key, kind):
            current = paths.split_dirs(self.location_value(key))
            start = current[-1] if current else ""
            if kind == "file":
                choice = filedialog.askopenfilename(initialdir=os.path.dirname(start) or None,
                                                    filetypes=[("procdump64.exe", "procdump*.exe"), ("All", "*.*")])
            else:
                choice = filedialog.askdirectory(initialdir=start or None, mustexist=key != "crash_watch.folder")
            if not choice:
                return
            choice = os.path.normpath(choice)
            self.set_location(key, paths.join_dirs(current + [choice]) if kind == "dirs" else choice)
            self.location_edited(key) if kind != "dirs" else self.loc[key]["entry"].event_generate("<<Modified>>")
            if kind == "dirs":
                self.loc[key]["entry"].edit_modified(True)
                self.location_edited(key)

        def detect_locations(self):
            self.message.set("Looking for the game folders…")
            def work():
                try:
                    self.events.put(("found", paths.detect()))
                except Exception as e:                          # detection is a convenience: never fatal
                    self.events.put(("found_error", str(e)))
            threading.Thread(target=work, daemon=True).start()

        def confirm_locations(self):
            bad = [(paths.LOCATIONS[i][1], paths.check(k, self.location_value(k)))
                   for i, k in enumerate(paths.KEYS) if self.location_value(k)
                   and paths.check(k, self.location_value(k))]
            if bad:
                self.message.set("Not saved: " + "; ".join(f"{label}: {why}" for label, why in bad))
                return
            self.start("save", part="locations")

        # --- Status, Settings, Log ---------------------------------------------------------------------------
        def build_status(self, tab):
            tab.columnconfigure(1, weight=1)
            tab.rowconfigure(2, weight=1)
            self.recipe = tk.StringVar(value=recipe)
            ttk.Label(tab, text="Build recipe").grid(row=0, column=0, sticky="w", padx=(0, 12))
            ttk.Entry(tab, textvariable=self.recipe).grid(row=0, column=1, sticky="ew")
            def pick():
                choice = filedialog.askopenfilename(filetypes=[("Recipe", "*.json"), ("All", "*.*")])
                if choice:
                    self.recipe.set(os.path.normpath(choice))
            ttk.Button(tab, text="Browse…", command=pick).grid(row=0, column=2, padx=(8, 0))
            actions = ttk.Frame(tab)
            actions.grid(row=1, column=0, columnspan=3, sticky="w", pady=12)
            for action, label in (("detect", "Check installation"), ("status", "Build status"),
                                  ("update-check", "Check for updates"), ("update", "Update launcher")):
                button = ttk.Button(actions, text=label, command=lambda a=action: self.start(a))
                button.pack(side="left", padx=(0, 8))
                self.widgets.append((button, "normal"))
            self.report = ScrolledText(tab, height=12, wrap="word", state="disabled", **text_style)
            self.report.grid(row=2, column=0, columnspan=3, sticky="nsew")

        def build_settings(self, tab):
            canvas = tk.Canvas(tab, highlightthickness=0, background=PALETTE["bg"])
            scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            form = ttk.Frame(canvas, padding=(0, 0, 12, 0))
            item = canvas.create_window((0, 0), window=form, anchor="nw")
            form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
            form.columnconfigure(1, weight=1)
            ttk.Label(form, text="saved in " + model.path, style="Muted.TLabel", wraplength=760).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
            for i, spec in enumerate(controls()):
                key, kind = spec["key"], spec["kind"]
                var = tk.BooleanVar(value=model.saved[key]) if kind == "bool" else tk.StringVar(value=model.saved[key])
                self.vars[key] = var
                ttk.Label(form, text=spec["label"]).grid(row=1 + 2*i, column=0, sticky="w", padx=(0, 16))
                if kind == "bool":
                    widget = ttk.Checkbutton(form, variable=var)
                elif kind == "choice":
                    widget = ttk.Combobox(form, textvariable=var, values=spec["choices"], state="readonly")
                else:
                    widget = ttk.Entry(form, textvariable=var)
                widget.grid(row=1 + 2*i, column=1, sticky="w" if kind == "bool" else "ew")
                self.widgets.append((widget, "readonly" if kind == "choice" else "normal"))
                ttk.Label(form, text=spec["cost"], style="Muted.TLabel", wraplength=760).grid(
                    row=2 + 2*i, column=0, columnspan=2, sticky="w", pady=(2, 14))

        def build_log(self, tab):
            tab.rowconfigure(0, weight=1)
            tab.columnconfigure(0, weight=1)
            self.log = ScrolledText(tab, wrap="word", state="disabled", **text_style)
            self.log.grid(row=0, column=0, sticky="nsew")
            row = ttk.Frame(tab)
            row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            ttk.Label(row, text="Recent command output. The crash watcher keeps its own crashwatch.log in the dump "
                                "folder.", style="Muted.TLabel").pack(side="left")
            ttk.Button(row, text="Open dump folder", command=self.open_logs).pack(side="right")

        # --- state -------------------------------------------------------------------------------------------
        def raw(self, part="all"):
            """The window's values. part="settings" keeps the saved locations (Save settings never saves a found path
            the player has not confirmed); part="locations" keeps the saved settings (Codex, #481)."""
            out = {key: var.get() for key, var in self.vars.items()}
            out.update({key: self.location_value(key) for key in paths.KEYS})
            return model.part(out, part)

        def reload_settings(self):
            self.dirty.clear()                         # Reload discards unsaved edits, locations included
            try:
                model.reload()
                for key, var in self.vars.items():
                    var.set(model.saved[key])
                self.render_locations()
                self.message.set("Reloaded saved settings")
            except (OSError, ValueError) as e:
                self.message.set(str(e))
            self.refresh_play()

        def refresh_play(self):
            if not hasattr(self, "play"):
                return
            reason = "A command is still running" if self.busy else self.process_error or model.play_reason(
                self.raw(), self.location_value("starfield"), self.pids)
            self.reason.set(reason)
            self.play.configure(state="disabled" if reason else "normal")

        def append(self, widget, text):
            widget.configure(state="normal")
            widget.insert("end", text)
            # Bound the window's memory; the underlying commands keep their own full recorded logs.
            lines = int(widget.index("end-1c").split(".")[0])
            if lines > 2000:
                widget.delete("1.0", f"{lines - 2000}.0")
            widget.see("end")
            widget.configure(state="disabled")

        def start(self, action, part="all"):
            if self.busy:
                return
            try:
                argv = model.command(action, self.raw(part), recipe=self.recipe.get(), overrides=overrides,
                                     starfield=self.location_value("starfield"),
                                     fo4_data=paths.split_dirs(self.location_value("fo4_data")),
                                     my_games=self.location_value("my_games"),
                                     pids=None if self.process_error else self.pids)
            except ValueError as e:
                self.message.set(str(e))
                return
            if argv is None:
                self.message.set("Nothing changed; nothing written")
                return
            self.busy, self.action, self.part = True, action, part
            for widget, _state in self.widgets:
                widget.configure(state="disabled")
            self.message.set(f"Running {action}…")
            self.refresh_play()
            self.append(self.log, "\n$ " + subprocess.list2cmdline(argv[3:]) + "\n")
            if action in REPORT_ACTIONS:
                self.report.configure(state="normal")
                self.report.delete("1.0", "end")
                self.report.configure(state="disabled")
            def work():
                try:
                    rc = run_command(argv, lambda line: self.events.put(("line", line)))
                    self.events.put(("done", rc))
                except Exception as e:
                    self.events.put(("error", str(e)))
            threading.Thread(target=work, daemon=True).start()

        def drain(self):
            if self.closed:
                return
            while True:
                try:
                    kind, value = self.events.get_nowait()
                except queue.Empty:
                    break
                if kind == "processes":
                    self.pids, self.process_error = value, ""
                    running = bool(value)
                    self.game.set("● game: running (PID " + ", ".join(map(str, value)) + ")" if running
                                  else "● game: not running")
                    self.game_label.configure(foreground=PALETTE["ok"] if running else PALETTE["muted"])
                elif kind == "process_error":
                    self.pids, self.process_error = None, "Cannot check game processes: " + value
                    self.game.set("● game: unknown")
                    self.game_label.configure(foreground=PALETTE["warn"])
                elif kind in ("found", "found_error"):
                    if kind == "found":
                        self.found = dict(value, **given)
                    self.render_locations()
                    waiting = [s for s in (self.loc[k]["status"] for k in paths.KEYS) if s != "saved"]
                    if any(self.loc[k]["status"] != "saved" for k in paths.needed(model.saved)):
                        self.notebook.select(self.places_tab)
                        self.message.set("Check the locations the launcher found, then press Confirm locations.")
                    elif waiting:
                        self.message.set("Ready. Some optional locations wait on the Locations tab.")
                    else:
                        self.message.set("Ready.")
                elif kind == "line":
                    self.append(self.log, value)
                    if self.action in REPORT_ACTIONS:
                        self.append(self.report, value)
                else:
                    self.busy = False
                    self.message.set(f"{self.action} finished (exit {value})" if kind == "done" else value)
                    for widget, state in self.widgets:
                        widget.configure(state=state)
                    if kind == "done" and value == 0 and self.action == "update":
                        self.message.set("Update finished: close and open the window again to use a new version.")
                    if kind == "done" and value == 0 and self.action == "save":
                        if self.part == "locations":   # confirmed: the command-line paths have had their say
                            given.clear()
                            self.dirty.clear()
                        try:
                            model.reload()
                            for key, var in self.vars.items():
                                var.set(model.saved[key])
                            self.render_locations()
                            self.message.set("Saved.")
                        except (OSError, ValueError) as e:
                            self.message.set(str(e))
                self.refresh_play()
            root.after(75, self.drain)

        def poll_processes(self):
            if self.closed:
                return
            def read():
                try:
                    from .crashwatch import System
                    self.events.put(("processes", System().pids()))
                except Exception as e:
                    self.events.put(("process_error", str(e)))
            threading.Thread(target=read, daemon=True).start()
            root.after(3000, self.poll_processes)

        def open_logs(self):
            folder = model.saved["crash_watch.folder"]
            if not folder or not os.path.isdir(folder):
                self.message.set("Confirm an existing dump folder on the Locations tab first")
                return
            try:
                if os.name == "nt":
                    os.startfile(folder)
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])
            except OSError as e:
                self.message.set(str(e))

        def close(self):
            if self.busy:
                messagebox.showinfo("A command is still running", "Keep this window open until the command "
                                    "finishes. Play follows the game and crash watcher until they finish.")
                return
            self.closed = True
            root.destroy()

    Window()
    root.mainloop()
    return 0
