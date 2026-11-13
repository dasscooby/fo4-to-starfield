# Pip-Boy: rebuilding Fallout 4's own Pip-Boy in Starfield (plan, FAL-614)

Claude (sole survivor), 13 Nov 2026. **A plan, no code.** Labels as in the other plans: **verified** = read from our
source or a PC log, **hypothesis** = to be proven by the read named beside it. The pause default (`Pause=0`) does not
change.

## The direction (owner, 13 Nov, FAL-614)

- Rebuild the Fallout 4 Pip-Boy in Starfield: its screen movies, map page, fonts and images, later the device on the
  arm. Do it by **converting the player's own installed copy on their PC at install time**, as the world's meshes and
  textures are converted. It is not a look-alike drawn by us.
- Converted game files never go into Git, a release, a task, a comment or a receipt. Only the converter goes into Git
  (`docs/research/framework/findings/legal-policy.md`, point 1).
- One Pip-Boy, one set of functions, one data feed. Fallout 3, New Vegas, 4 and 76, and later others, are
  selectable **looks** on top of it. Fallout 4 is the first look.
- Travel from the map (fast travel, moving between maps) is **not designed here**; it is the owner's later decision.
  Fallout 76's map style and extra Pip-Boy features are function, and also later.
- The kit's text rows stay as the debug view. The text map of our converted cells is **parked** for later uses (a
  warfare mode, settlement management views). It is a separate, later page, not the Pip-Boy's map page; its groundwork
  is held on `claude/fal614-pipboy-text-map` (`3133640d`).

## (a) What the files are, and what Starfield loads

**What we load today (verified, source).**
- The plugin registers its own menu and loads `Interface/FO4SF_PipboyMenu.swf` from our archive through the engine's
  `IMenu::LoadMovie` (`sfse/FO4SFPipboyMenu/src/main.cpp`, `kLoadMovieRva`).
- Starfield's player runs it as an ActionScript 3 movie: the plugin accepts the movie's root only when its RTTI is
  `MovieRoot@AS3@GFx@Scaleform` (`kMovieRootRtti`).
- Our movie is built by `scripts/ui/make_pipboy_kit.py`: CWS (zlib), SWF version 12, the AS3 bit set in
  `FileAttributes`, and **no ActionScript at all**. The plugin drives it from outside: `getChildByName`,
  `addEventListener` on a click, and `SetMember` of `text` and `visible`.
- Starfield's own `almanacmenu.swf` is also CWS version 12 (`ui-pipboy-vats.md`, item 1).

**What Fallout 4's files are (hypothesis, read D1 settles it).**

| File (in `Fallout4 - Interface.ba2`) | What it is expected to be |
| --- | --- |
| `PipboyMenu.swf` | the shell: the frame, the tab bar, the bottom bar, and the loader of each tab's movie |
| `Pipboy_StatsPage.swf`, `Pipboy_InvPage.swf`, `Pipboy_DataPage.swf`, `Pipboy_MapPage.swf`, `Pipboy_RadioPage.swf` | one movie per tab, loaded into the shell |
| `PipboyMessageBox.swf` | the in-Pip-Boy confirmation box |
| `pipboybootsequence.swf` | the boot animation shown when the Pip-Boy first opens |
| `fonts_en.swf` | the shared fonts the other movies import by name, with `FontConfig.txt` mapping font names |

- All are expected to be AS3 Scaleform movies, CWS, with a SWF version near ours.
- They are expected to carry ActionScript (`DoABC` tags) that expects things from Fallout 4's engine:
  - a code object the engine puts on the menu (sounds, tab changes, closing);
  - the Pip-Boy's data, pushed as a tree of named values (player info, inventory, quests, map, radio). This is the
    same tree the Fallout 4 companion app received.
- What each movie imports from `fonts_en.swf`, and which classes it defines, is what D1 prints.

**Read on the PC (D1, 13 Nov, at `c28a8d5d`, the script unchanged; PR #764 comment 6840521845): verified.**
- All nine files were found. Each is `CWS` **version 15**, ActionScript 3, with **one `DoABC`** each: the pages hold
  37 to 119 kB of it, the boot sequence only 2,203 bytes.
- Stage 876 x 700 (the boot sequence 826 x 700), 30 frames a second.
- Each imports only `fonts_en.swf`. No Scaleform tag of code 1000 and up, so no image file is named inside the movies.
- Starfield's two files: version 12, ActionScript 3, 1920 x 1080.
- So route A is open in principle: the same script generation on both sides, with the version (15 against 12) the
  first difference to watch. D2 is needed for the pages. The boot sequence, with the least code, stays proof 1.

## (b) The routes, and what proves or kills each

**Route A: load the converted original movies, feed them what they expect.**
- **How it works.**
  - The PC's install step reads the player's movies from their archive and writes them, with only the conversion the
    load needs (for example the SWF version byte, or import paths), into a private archive beside ours.
  - Our plugin loads the shell instead of our kit movie. It then plays Fallout 4's engine: it supplies the code
    object's functions and pushes the data tree in the shape the movies read.
- **Proves it.** The converted `pipboybootsequence.swf` (no data needed) plays in our menu, and the plugin's log shows
  the movie root accepted, with no ActionScript error.
- **Kills it.** Any of these:
  - the movie does not load;
  - Starfield's player refuses or faults on Fallout 4's ActionScript;
  - the movies need a native class from Fallout 4's executable that Starfield's player does not have.
- **Cost if it lives.** The data tree: every page reads its own names. The plugin must learn them from the movies'
  own class and member names (D1, D2), never by copying their code into Git.

**Route B: rebuild each page in our own movie from the original's parts, extracted on the PC.**
- **How it works.**
  - The install step reads the player's movies on the PC and copies the shapes, images, fonts and placements of a
    page into our kit movie. The kit generator already writes these tag kinds.
  - Our named fields go where the original's text sits. The plugin keeps feeding our fields exactly as it does today,
    so no Fallout 4 ActionScript runs.
- **Proves it.** Our menu shows the original STAT page's frame and font, with live HP from our plugin in it.
- **Kills it.** The page's look is built by its ActionScript at run time (lists filled, text created, layout computed)
  rather than placed on its timeline, so the copied parts come out empty or broken.
- **Cost.** Each page's layout is ours to keep in step with the original's pieces. Animations that the original's
  code drives are lost.

**Expected outcome (hypothesis).** A mix: the static frame, fonts and images come by route B; pages whose look is made
by their code need route A or a rebuild of that code's behaviour in our plugin. The first proof below decides route A
early, because it costs nothing to try.

## (c) The map page

**Where its parts live (hypothesis, read D3 settles it).**
- The map page's movie is `Pipboy_MapPage.swf`. The look survey found it in the player's `Fallout4 - Interface.ba2`
  (#759, PC run 12 Nov).
- The marker icons are expected to be symbols inside that movie (one per marker type).
- The world map image is expected to be a texture under `Textures\Interface\` (a `.dds`). It is named by the worldspace
  record, or found by a name holding `map`. The MAP plan's R5 lists those names.

**Read on the PC (D3, 13 Nov): verified.**
- The worldspace `Commonwealth`: `ICON` = `Interface\Pip-Boy\WorldMap_d.dds`, 2048 x 2048, BC1, 12 mips.
- `MNAM`: usable size 0 x 0; north-west cell (-33, 25), south-east cell (28, -36): 62 x 62 Fallout 4 cells.
  `ONAM`: scale 1, offsets 0. `NAM0` / `NAM9`: -393216 / 393216.
- So, as a **hypothesis** for the map card: the image spans those 62 cells of 4096 units. A Fallout 4 position (x, y)
  falls at pixel ((x / 4096 + 33) / 62 x 2048, (25 + 1 - y / 4096) / 62 x 2048), the south-east cell included. The
  first map card checks it against one marker the player can see on both maps.
- `Pipboy_MapPage.swf` holds 92 marker symbol classes. A separate `Interface\MapMarkers.swf` also exists; D2 below
  reads its names with the others.

**What our page must supply.** These come from the Fallout 4 data tree's map branch (hypothesis: the companion app's
`Map` → `World` values):

| Value | From us |
| --- | --- |
| The player's x, y | POSITION, back in Fallout 4's frame: (Starfield metres − the merge offset) × 70. The merge offset is `vmad_patch.MERGE_MEASURED`, and the core is built at Fallout 4 position / 70 (`core64c.md`) |
| The player's rotation | HEADING (FAL-595: `HeadingAt=88`, compass degrees, verified on the PC) |
| The map's extents (the world corners the image spans) | from the worldspace record of the player's own `Fallout4.esm`, read at install time |
| Markers: x, y, name, type, discovered | our converted markers (the marker conversion, MAP plan step 3), their discovered flag once read R3 and R4 find it |
| Which world the player is in | WORLD and GRID (FAL-595); indoors there is no world map, as in Fallout 4 |

The local map (Fallout 4 draws it from the scene at run time) and travel are not in this plan.

## (d) The reads the PC runs first (names and header fields only)

Environment: the owner's PC, PowerShell, the repository checkout at this branch's head, Python as for the look survey.
No game launch, nothing written under the Fallout 4 or Starfield folders.

The script reads each file **in memory** from the archive with `src/fo4sf/ba2.py` and prints only:
- the header: signature, version, length, stage size, frame rate, frame count;
- the `FileAttributes` flags;
- the count of each tag code;
- names: `SymbolClass` class names, `ExportAssets` names, `ImportAssets2` URLs and names, the `DoABC` name, and font
  names;
- the file names that Scaleform's own tags (code 1000 and up) refer to.

No shape, image, sound or code is written anywhere.

**D1 (movies).** For each of `PipboyMenu.swf`, `Pipboy_StatsPage.swf`, `Pipboy_InvPage.swf`, `Pipboy_DataPage.swf`,
`Pipboy_MapPage.swf`, `Pipboy_RadioPage.swf`, `PipboyMessageBox.swf`, `pipboybootsequence.swf`, `fonts_en.swf` (in
`Fallout4 - Interface.ba2`), print the lines below. If a name is not found, check the survey's spelling. Print the same
for two Starfield files for comparison: `interface/almanacmenu.swf` and `interface/fonts_en.swf` (in
`Starfield - Interface.ba2`).

```python
import re, struct, sys, zlib
sys.path.insert(0, "src")

NAMED = {76: "SymbolClass", 56: "ExportAssets", 71: "ImportAssets2", 82: "DoABC", 75: "DefineFont3",
         91: "DefineFont4", 88: "DefineFontName", 69: "FileAttributes"}


def cstr(b, at):
    end = b.index(b"\0", at)
    return b[at:end].decode("latin-1"), end + 1


def describe(name, data):
    """Header fields and names of one SWF or Scaleform GFX file; nothing else."""
    sig, version, length = data[:3], data[3], struct.unpack_from("<I", data, 4)[0]
    body = zlib.decompress(data[8:]) if sig in (b"CWS", b"CFX") else data[8:]
    if sig not in (b"FWS", b"CWS", b"GFX", b"CFX"):
        return [f"file={name} signature={sig!r} not_swf=1"]
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8
    bits = int.from_bytes(body[:pos], "big")
    shift = pos * 8 - 5
    rect = []
    for _ in range(4):
        shift -= nbits
        v = (bits >> shift) & ((1 << nbits) - 1)
        rect.append(v - (1 << nbits) if nbits and v >> (nbits - 1) else v)
    rate, frames = body[pos + 1] + body[pos] / 256, struct.unpack_from("<H", body, pos + 2)[0]
    out = [f"file={name} signature={sig.decode()} version={version} length={length} "
           f"stage={(rect[1] - rect[0]) / 20:g}x{(rect[3] - rect[2]) / 20:g} rate={rate:g} frames={frames}"]
    pos += 4
    counts = {}
    while pos + 2 <= len(body):
        head = struct.unpack_from("<H", body, pos)[0]
        code, size, pos = head >> 6, head & 0x3F, pos + 2
        if size == 0x3F:
            size, pos = struct.unpack_from("<I", body, pos)[0], pos + 4
        tag = body[pos:pos + size]
        pos += size
        counts[code] = counts.get(code, 0) + 1
        if code == 69:
            out.append(f"  FileAttributes flags=0x{tag[0]:02x} as3={(tag[0] >> 3) & 1}")
        elif code in (76, 56):
            n, at = struct.unpack_from("<H", tag)[0], 2
            for _ in range(n):
                at += 2
                s, at = cstr(tag, at)
                out.append(f"  {NAMED[code]} name={s}")
        elif code == 71:
            url, at = cstr(tag, 0)
            n, at = struct.unpack_from("<H", tag, at + 2)[0], at + 4
            names = []
            for _ in range(n):
                at += 2
                s, at = cstr(tag, at)
                names.append(s)
            out.append(f"  ImportAssets2 url={url} names={','.join(names)}")
        elif code == 82:
            out.append(f"  DoABC name={cstr(tag, 4)[0]!r} bytes={size}")
        elif code in (75, 91):
            at = 4 if code == 75 else 3
            if code == 75:
                s = tag[at + 1:at + 1 + tag[at]].decode("latin-1").rstrip("\0")
            else:
                s = cstr(tag, at)[0]
            out.append(f"  {NAMED[code]} name={s}")
        elif code == 0:
            break
        elif code >= 1000:
            for s in sorted(set(re.findall(rb"[\w\\/.-]{3,}\.(?:dds|tga|png|swf|gfx)", tag, re.I))):
                out.append(f"  GFxTag{code} file={s.decode('latin-1')}")
    out.append("  tags=" + ",".join(f"{c}x{counts[c]}" for c in sorted(counts)))
    return out


if __name__ == "__main__":
    from fo4sf.ba2 import Ba2
    archive = Ba2(sys.argv[1])
    for want in sys.argv[2:]:
        hit = [n for n in archive.names if n.lower().replace("/", "\\").endswith("\\" + want.lower())]
        if not hit:
            print(f"file={want} found=0")
            continue
        print("\n".join(describe(hit[0], archive.read(hit[0]))))
```

Run it once per archive, with the file names as arguments, and send the output back. The output stays in the PC's
private evidence folder; the comment carries the lines.

**D2 (data names; needed, D1 found `DoABC` in every movie).** The names the movies' ActionScript uses: classes,
members, and the names of the data the engine sends. It prints the ABC's version and its constant pool of strings,
filtered to identifiers (letters, digits, `_`, `$`, `.` and `:`, at most 64 characters). No code, no bytes, no
sentences. Run it on the same nine files as D1 plus `MapMarkers.swf`, in memory as D1:

```python
import re, struct, zlib

NAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$.:]{0,63}")


def u30(b, at):
    value = shift = 0
    while True:
        byte = b[at]
        at += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80 or shift >= 35:
            return value, at


def names(data):
    """The ABC version and the identifier strings of each DoABC tag's constant pool: names only, nothing else."""
    body = zlib.decompress(data[8:]) if data[:3] in (b"CWS", b"CFX") else data[8:]
    pos = ((5 + 4 * (body[0] >> 3) + 7) // 8) + 4
    out = []
    while pos + 2 <= len(body):
        head = struct.unpack_from("<H", body, pos)[0]
        code, size, pos = head >> 6, head & 0x3F, pos + 2
        if size == 0x3F:
            size, pos = struct.unpack_from("<I", body, pos)[0], pos + 4
        tag, pos = body[pos:pos + size], pos + size
        if code == 0:
            break
        if code not in (72, 82):
            continue
        at = 0 if code == 72 else tag.index(b"\0", 4) + 1
        minor, major = struct.unpack_from("<HH", tag, at)
        at += 4
        n, at = u30(tag, at)                       # ints: signed varints
        for _ in range(max(n - 1, 0)):
            at = u30(tag, at)[1]
        n, at = u30(tag, at)                       # uints
        for _ in range(max(n - 1, 0)):
            at = u30(tag, at)[1]
        n, at = u30(tag, at)                       # doubles
        at += 8 * max(n - 1, 0)
        n, at = u30(tag, at)                       # strings
        found = set()
        for _ in range(max(n - 1, 0)):
            length, at = u30(tag, at)
            text = tag[at:at + length].decode("utf-8", "replace")
            at += length
            if NAME.fullmatch(text):
                found.add(text)
        out.append(f"  abc={major}.{minor} strings={max(n - 1, 0)} names={len(found)}")
        out.extend(f"  name={t}" for t in sorted(found))
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")
    from fo4sf.ba2 import Ba2
    archive = Ba2(sys.argv[1])
    for want in sys.argv[2:]:
        hit = [n for n in archive.names if n.lower().replace("/", "\\").endswith("\\" + want.lower())]
        print(f"file={want} found={len(hit)}")
        if hit:
            print("\n".join(names(archive.read(hit[0]))))
```

The output stays in the PC's private evidence folder. Send back, per file, the `abc=` line and the count of names, and
for `PipboyMenu.swf`, `Pipboy_StatsPage.swf` and `pipboybootsequence.swf` the names themselves. The STAT page's names
are the data proof 2 must feed; the boot sequence's are what proof 1 may ask the engine for.

**D3 (the world map).**
- The look survey's names-only listing over `Fallout4 - Textures*.ba2` and `Fallout4 - Interface.ba2`, for names
  holding `map` (the MAP plan's R5).
- For each hit, the DDS header only: width, height, format, mip count.
- The worldspace record `Commonwealth` in the player's `Fallout4.esm`: the names of its subrecords and the map-related
  ones' sizes (`MNAM`, `NAM3`, `NAM4`, `ICON` if present). No values beyond what names the map image and its extents.

## (e) The smallest first proof a player can see

The owner PC suggested the boot sequence or the STAT page's frame with live HP. Weighed:

| Proof | Needs | Tells us |
| --- | --- | --- |
| **1. `pipboybootsequence.swf`, converted, playing inside our menu** | D1; a private converted copy; the plugin loading a second movie name from the ini (one setting) | Whether Starfield's player runs Fallout 4's ActionScript at all: route A alive or dead, with no data feed to build first |
| 2. The original STAT page's frame and font around our live HP | D1 (and D2 if route A); route B's extraction of one page, or route A's data tree for HP | The first page a player would call the real Pip-Boy |

**Recommendation: proof 1 first, then proof 2.** Proof 1 is the cheapest test that decides between the routes, and a
player sees the real boot screen. Proof 2 follows by whichever route proof 1 leaves standing.
- If the boot sequence plays: proof 2 is route A, the shell with the STAT page and the HP value pushed by name.
- If it does not: proof 2 is route B, the STAT frame's shapes and font copied into our kit movie on the PC.

**Proof 1, the card (owner PC; the plugin's `Movie=` setting, FAL-614).** Environment: the owner's PC, the plugin
built from this branch's head, the probe staged as for `Stage=2`. Nothing of the player's goes into Git.
1. Stage the probe as usual (`make_pipboy_probe.py stage`). Before packing, copy the player's own
   `Interface\pipboybootsequence.swf`, read from their `Fallout4 - Interface.ba2`, unchanged, into the staged
   `Data\Interface\` as `FO4SF_Fo4Boot.swf`. Pack as usual. This private archive stays on the PC.
2. In `FO4SFPipboyMenu.ini`: `Stage=2`, `Movie=FO4SF_Fo4Boot`.
3. Load a save outdoors, press F10, wait 5 seconds, take a screenshot, press F10 again.

PASS: `step=movie name=FO4SF_Fo4Boot`, `step=load_movie ... result=1 movie=<non-zero> movie_name=FO4SF_Fo4Boot
name_asks=<1 or more>`, and the screenshot shows Fallout 4's boot screen inside our menu, with no crash.
What each other outcome means:
- `name_asks=0`: the engine does not name the file after `GetName` in that call. Whatever loaded, the setting's
  hypothesis is wrong; send the log.
- `result=0` with `name_asks` of 1 or more: the engine refused the file. The next card converts it, the SWF version
  15 to 12 first.
- It loads but shows nothing, or freezes: its ActionScript waits for something of Fallout 4's engine. D2's boot names
  say what.
- A crash: send the crash log; the next card is the version conversion.

## Look and function: the seam

- **Function** (one, shared by every look): the pages, what each row or widget is fed, and input. It is the
  **union** of what every game's Pip-Boy needs (owner, 13 Nov), not Fallout 4's list alone; the next section lists it.
  - The values the plugin promises every look today: the value providers (`make_pipboy_kit.py` `VALUE_PROVIDERS`:
    health, level, xp, carry_max, rads, cell, world, time, days, position, heading, grid, `av:<id>`).
  - The lists: inventory and quests, and later markers.
  - The events: tab and sub-tab moves, selection, click, open and close.
  - Added by later function work: the map's world values (section c).
- **A look** is files plus settings. The files are the screen movies, fonts and images, later the device model,
  animations and sounds, each converted from that game's own files on the player's PC. The settings are:
  - the look's name;
  - which movie is the shell;
  - how each function value reaches it: by our field names (route B), or by the original's data names (route A).
  The converter writes a look into its own private folder and archive.
- **How a look is chosen:** one ini setting names the look. The plugin loads that look's shell and falls back to our
  kit movie, which is always present and is the debug view. Fallout 4 is the first look; Fallout 3, New Vegas and 76
  are not surveyed or converted now.
- **Per game, not one world (the seam for Fallout 76 and later).** Nothing in the plugin or the menu may assume one
  world map or one fixed set of pages:
  - The page set is data. It already is: the kit's `[Page]` sections.
  - A world map belongs to the world the player is in. It is chosen by WORLD, never fixed in code. The Commonwealth's
    map comes with the Fallout 4 conversion; another game's world brings its own.
  - Fallout 76's map style and extra features are function, decided by the owner later.

## The function union: a first inventory by game

Owner, 13 Nov: "the main functioning should just be a combination of everything that's needed from each of the
games." So the function side is one Pip-Boy holding every feature that Fallout 3, New Vegas, 4 and 76 need (more
games later). The looks stay per game.

**Source of this table.** Written from memory of the games, without reading their files. **None of it is verified.**
`known` means what players of that game see; `unread` means it is not certain whether, or where, that game has it.
No other game's files are surveyed now.

Games: **3** = Fallout 3, **NV** = New Vegas, **4** = Fallout 4, **76** = Fallout 76.

| Function id | What it shows or does | 3 | NV | 4 | 76 | Ours today |
| --- | --- | --- | --- | --- | --- | --- |
| `stat.status` | health, condition of limbs, rads, the player figure, use a stimpak or RadAway | known | known | known | known | rows: health, rads, level, xp |
| `stat.needs` | hunger, thirst, sleep | - | known (Hardcore) | unread (Survival mode, shown elsewhere?) | known | - |
| `stat.effects` | active effects: chems, perks, illness | unread | unread | known | known | - |
| `stat.special` | the seven S.P.E.C.I.A.L. values | known | known | known | known (with perk cards) | rows: `av:2C2` to `av:2C8` |
| `stat.skills` | skills (Small Guns, Lockpick ...) | known | known | - | - | - |
| `stat.perks` | the perks taken; Fallout 4's perk chart; Fallout 76's perk cards | known (list) | known (list) | known (chart) | known (cards, legendary perks) | - |
| `stat.general` | statistics, karma, level progress | known | known | unread (under DATA as Stats) | unread | - |
| `stat.reputation` | standing with each faction | - | known | - | unread (factions, reputation) | - |
| `stat.mutations` | mutations | - | - | - | known | - |
| `inv.items` | items by category (weapons, apparel, aid, misc, junk, mods, ammo, notes, holotapes), equip, drop, inspect, favourite | known | known | known | known | list: inventory (names, counts) |
| `inv.weight` | carry weight, current and maximum | known | known | known | known | row: carry_max |
| `inv.junk_components` | junk's components, tag for search | - | - | known | known | - |
| `data.quests` | quests and objectives, the active quest | known | known | known | known | list: quests (our mission) |
| `data.notes` | notes and holotapes, play a holotape | known | known | known (under INV) | known | - |
| `data.challenges` | challenges and their progress | - | known | - | known | - |
| `data.workshops` | settlements: people, food, water, power, defence, happiness | - | - | known | unread (camp, workshops) | - |
| `data.stats` | game statistics | unread (STATS / General) | unread | known | unread | - |
| `map.world` | the world map with the player's arrow and markers | known | known | known | known (its own style) | rows: world, position, heading, grid |
| `map.local` | the local map around the player | known | known | known | unread | - |
| `map.travel` | fast travel from the map | known | known | known | known (with a cost) | **not designed (owner's later decision)** |
| `radio.stations` | stations found, tune and turn off | known (under DATA) | known (under DATA) | known | known | notice only |
| `social` | team, friends, other players | - | - | - | known (outside the Pip-Boy?) | - |
| `device.light` | the Pip-Boy's light | known | known | known | known | - |

**The function contract every look is fed from.**
- Every function has a stable id (the table's first column). It has a home tab that is the same for every look:
  STAT, INV, DATA, MAP, RADIO. In Fallout 3 and New Vegas the map and radio sit under DATA, so a look also says
  where its own tabs put each id.
- For each id, the function side promises the same feed to every look: its values (value providers), its lists
  (list providers), and its events (move, select, click, open, close). These are today's kit pieces, extended by id.
- A look declares which ids it has a page of its own for. For example, a Fallout 4 look has no `stat.skills` page,
  and a Fallout 3 look has no `data.workshops` page.
- **A function the look's game lacks gets a generic page in that look's style:** the look's frame, font and list and
  value widgets, filled from the same feed. The kit's text rows are the ultimate fallback, so no feature is ever left
  without a place.
- A **stated gap** is used only when a function cannot be drawn in a look at all, for example a world map in a look
  that has no map component and no image to show. The gap is logged once with the look and the id, and the page says
  so in words.
- Which functions exist at all is the owner's choice per function, as with travel and Fallout 76's additions. This
  table is the shape, not a promise to build every row.

**The first build stays Fallout 4.** Fallout 4's look and Fallout 4's functions come first: the rows that are
`known` under 4. The union is the shape the code keeps room for (ids, the home tab, generic pages), not the first
delivery.

## What this plan does not do

- No code, no conversion, no movie of the player's in Git or anywhere public. Every converted byte stays on the PC.
- No travel from the map, no `coc` from the plugin, no fast travel.
- No survey or conversion of Fallout 3, New Vegas or 76 now.
- No change to the pause default or to the stages. The kit's text rows stay.

## Next gate

1. Done: D1 and D3 (13 Nov).
2. The owner PC runs D2 and proof 1 (the card above, with the `Movie=` setting on this branch).
3. Then proof 2, by the route proof 1 leaves standing. It has its own branch, tests, a CARRY line, the Scribe's
   review, and the PC's run.
