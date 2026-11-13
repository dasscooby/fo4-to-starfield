# Pip-Boy real-device look: what the PC survey must name (plan, FAL-571)

Plan only, no code in the plugin or the kit. Owner's option 3 (FAL-565): before the kit's page can look like the
Fallout 4 Pip-Boy the player knows, we need the names of the Fallout 4 files that hold that look, read from the
player's **own** Fallout 4 install. This card says which files the survey must name, how the PC lists them (names
only), and what the names then decide. Nothing here is verified yet: every path below is a **hypothesis** that the
survey confirms or refutes.

## Why names first

- The kit today draws its own screen (`make_pipboy_kit.py`: one phosphor colour, its own font, no Fallout 4 byte).
- The project never ships a Bethesda byte or anything derived from one
  (`docs/research/framework/findings/legal-policy.md`, point 1). A real-device look can therefore only be built on the
  player's PC, from the player's own files, at staging time, and stays there: never in Git, a release, a task, a
  comment or a receipt.
- Which files exist, under which names and in which archive, is the first fact that decision needs. The measurement
  `docs/measurements/fo4_ba2.json` counts them (`Fallout4 - Interface.ba2`: 904 files, 304 `.swf`, 4 `.gfx`, 546
  `.dds`, 12 `.txt`) but names none of the Pip-Boy's.

## What the survey must name

| # | Group | Where (hypothesis) | Why it matters |
| --- | --- | --- | --- |
| 1 | the Pip-Boy's screen movies | `Fallout4 - Interface.ba2`, `Interface\` movies with `pipboy` in the name (a shell movie and one per tab or page) | the layout, the tab bar, the list and value columns the kit would follow |
| 2 | every other top-level movie | `Interface\*.swf`, `*.gfx` | the page movies may not carry `pipboy` in their names; the full list (names only) shows them |
| 3 | fonts and font map | `Interface\fonts_*.swf`, `Interface\FontConfig*.txt` | the Pip-Boy's typeface; the kit's own font stands in until this is decided |
| 4 | screen images | `.dds` under `Interface\` with `pipboy` in the path, and the count per `Interface\` folder | scan lines, icons, the vault-boy pictures |
| 5 | the device on the arm | `Fallout4 - Meshes.ba2`, `- MeshesExtra.ba2`, `- Textures*.ba2`, `- Materials.ba2` names with `pipboy` | the 3D device; later and separate from the screen |
| 6 | its animations | `Fallout4 - Animations.ba2` names with `pipboy` | raising and lowering the arm; later |
| 7 | its sounds | `Fallout4 - Sounds.ba2` names with `pipboy` | tab clicks, the open and close sound |
| 8 | Creation Club skins | every name in an archive whose own name has `PipBoy` (the measurement lists `ccBGSFO4001-PipBoy(Black)` and others) | only to know they exist; the plan uses the base game |
| 9 | loose overrides | files under `Data\` (not in an archive) that match 1 to 7 | a mod on the player's install may replace the vanilla look |

A group that comes back empty is an answer too: it says the hypothesis for that group was wrong.

## The survey (PC, read-only, about five minutes)

Environment: the owner's PC, PowerShell, the repository checkout at this branch's head, Python as for the other cards.
No game launch, no install, nothing written under the Fallout 4 or Starfield folders. It reads the archives' name
tables with `src/fo4sf/ba2.py` and lists names; it extracts no file.

```powershell
$fo4 = '<the Fallout 4 folder>\Data'
$out = '<private evidence folder>\pipboy-look-survey.txt'
@'
import os, re, sys
sys.path.insert(0, "src")
from fo4sf.ba2 import Ba2

data = sys.argv[1]
pipboy = re.compile(r"pip-?boy", re.I)
movie = re.compile(r"^interface[\\/][^\\/]+\.(swf|gfx|txt)$", re.I)
for name in sorted(os.listdir(data), key=str.lower):
    if not name.lower().endswith(".ba2"):
        continue
    try:
        names = Ba2(os.path.join(data, name)).names
    except Exception as error:
        print(f"archive={name} error={error}")
        continue
    interface = name.lower() == "fallout4 - interface.ba2"
    hits = [n for n in names if pipboy.search(name) or pipboy.search(n) or (interface and movie.match(n))]
    print(f"archive={name} files={len(names)} named={len(hits)}")
    if interface:
        folders = {}
        for n in names:
            parts = n.replace("/", "\\").split("\\")
            if len(parts) > 2:
                folders[parts[1]] = folders.get(parts[1], 0) + 1
        for folder in sorted(folders, key=str.lower):
            print(f"  folder=Interface\\{folder} files={folders[folder]}")
    for n in sorted(hits, key=str.lower):
        print(f"  {n}")
for root, _, files in os.walk(data):
    for f in sorted(files):
        rel = os.path.relpath(os.path.join(root, f), data)
        if not rel.lower().endswith((".ba2", ".esm", ".esp", ".esl")) and (pipboy.search(rel) or movie.match(rel)):
            print(f"loose={rel}")
'@ | python - $fo4 | Tee-Object -FilePath $out
```

Report back **names and counts only**: each `archive=` line, the `folder=` lines, the names under groups 1 to 7, the
`loose=` lines, and any `error=`. The file itself stays in the PC's private evidence folder.

## What the names then decide (later pieces, each its own card and owner word)

1. **Screen first or device first.** The kit is a screen; the plan proposes the screen's look (groups 1 to 4, 7)
   before the arm (5, 6).
2. **How the look reaches the kit**, open until the names are in: (a) the kit keeps drawing its own movie and only
   follows the Fallout 4 layout, colours and sizes read off the player's files on the PC; (b) the PC's staging step
   builds a private movie from the player's own movie or font, never leaving that PC; (c) Starfield loads the player's
   own Fallout 4 movie directly (needs its Scaleform version and ActionScript to run in Starfield's player: unknown).
3. **Which font** the kit uses: its own, or glyphs taken on the PC from the player's `fonts_*.swf` (route (b)).
4. **The sounds** for tab moves and the open and close, if group 7 names them.

None of these is decided here. The survey changes nothing in the game, the plugin or the shipped kit; the shipped
default stays `Pause=0`.

## PASS for the survey

- `archive=Fallout4 - Interface.ba2 files=904` (or the install's own count) with its `folder=` lines and its named
  movies.
- Groups 1 to 7 each either list names or are reported empty.
- No file was written under the game folders; the output file stays private.
