# PC card: script compile census (no game needed)

Question it answers: when Fallout 4's own Papyrus scripts are compiled against Starfield's script sources, how
many compile, and what breaks? That decides whether settlements, survival, power armor, companions and the radio
are recompiled or rewritten. Starfield does not need to be running. Nothing is installed or changed.

Tool: `scripts/papyrus/compile_census.py`. Tests: `tests/test_compile_census.py` (made-up compiler lines only).

## Where each input comes from

| Input | Where on your PC | Status |
|---|---|---|
| `--compiler` | `<Starfield>\Tools\Papyrus Compiler\PapyrusCompiler.exe` (Creation Kit install) | same path the bridge card uses |
| `--starfield-sources` | New empty folder. Extract `Scripts\Source\*` from `<Starfield>\Tools\ContentResources.zip` into it, so that `Starfield_Papyrus_Flags.flg` and `Actor.psc` sit directly in the folder | zip layout verified by `make_bridge.py`; flatten the `Scripts\Source` level |
| `--fo4-sources` | Fallout 4 Creation Kit script sources: under `<Fallout 4>\Data\Scripts\Source` (a `Base` folder or a `Base.zip`; unzip it into a new folder if it is a zip) | **unverified**: I have not seen the folder. If it differs, point at whatever holds the `.psc` files |
| `--shim` | New empty folder. Leave it empty for this run | empty first, by design |
| `--fragment` | The name (no `.psc`) of one Fallout 4 quest fragment script, one that starts `QF_`. Find one: `Get-ChildItem <fo4 sources> -Recurse -Filter QF_*.psc \| Select -First 5` | pick any; say which |
| `--count`, `--seed` | `--count 200 --seed 1` | same seed gives the same sample |

Everything lives outside the repo. Do not put game files in Git.

## Command

PowerShell, from the repo root, with the repo's Python (`$py`):

```powershell
& $py -I -B scripts\papyrus\compile_census.py `
  --compiler "<Starfield>\Tools\Papyrus Compiler\PapyrusCompiler.exe" `
  --starfield-sources "<new folder with Starfield .psc>" `
  --fo4-sources "<folder with Fallout 4 .psc>" `
  --shim "<new empty folder>" `
  --fragment "<QF_ script name>" --count 200 --seed 1 `
  --out "<new empty output folder>"
```

Run time: one compiler start per script, so a few minutes for 200. `--timeout` (default 120 s per script) marks a stuck
one as `other`. If the first run fails everything with one `other` line, send me that line: likely the compiler wants a
different script-path form or the flags file is elsewhere.

## Import order (so the result means what it says)

Shim, then Starfield sources, then Fallout 4 sources. Starfield wins any name clash. A sampled Fallout 4 script that
extends another Fallout 4 script still resolves it from the Fallout 4 folder.

## What to send back

1. The printed table (copy it from the console).
2. `<out>\census.json`.

Do **not** send the `.psc` files, the `.pex` files or the `raw` folder. `census.json` holds counts, script names,
line numbers and short compiler messages. Read it once; if a message quotes something you would rather not share,
trim it.

Buckets: unknown function, unknown type or script, unknown property or variable, wrong argument count, syntax,
other. A big `other` bucket means the tool's patterns missed a compiler phrasing; send two or three of its lines and
I will add them.
