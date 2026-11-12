# Build pieces: Fallout 4 statics in Starfield's outpost build menu

Task: FAL-381 piece 2 (stage plan tracks 7 and 8, settlements and C.A.M.P.s; follows the workshop kit, `workshop-probe.md`).
Status: **built offline, not run in game** (no Starfield.esm, no installed core, no ContentResources.zip, no Papyrus compiler, no
game on the build box). Every output below that says "fixture" is a synthetic file written by `BuildPieces fixture`; nothing
in it is a reading of the real game.

## The question

Building works at a scripted bench and at the core's placed benches (`workshop-probe.md`), but the build menu offers only
Starfield's six stations (CRAFTING tab; Industrial Workbench costs Aluminum 4 and Iron 3, PC 11 Nov). How does an outpost buildable
get into that menu, and can Fallout 4 pieces made from statics the installed core has be added to it?

## What is known, and how

* **Verified (PC, `workshop-probe.md`):** the menu is the outpost build mode opened by E on a workshop; it lists six stations in a
  CRAFTING tab with a build limit bar; a station is paid in Iron `0000556E` and Aluminum `0000557D` (the MISC the COBJ's IRES
  components `0057C7` and `0057D6` map to); a placed station was built with nothing from the console.
* **Verified (Mutagen 0.55.0-alpha.67, read by reflection on the Starfield `ConstructibleObject` type, this box):** a COBJ has
  `CreatedObject` (a `ConstructibleObjectTarget`), `WorkbenchKeyword`, `RecipeFilters` (a list of keywords), `InstantiationFilterKeyword`,
  `MaxBuildCountGlobal` (a GLOB link), `MenuSortOrder`, `Tier`, `ConstructableComponents` (item link + count), `Description`,
  `MenuArtObject`, `Flags`, sounds, conditions. So the task text's reading (workbench keyword, category and filter keywords, build
  limit) has a field for each of those: the **build limit is the recipe's own GLOB link**, the **category/filter is the
  `RecipeFilters` keyword list**, the **bench the recipe belongs to is `WorkbenchKeyword`**.
* **Supported hypothesis, not read:** the menu lists every COBJ whose `WorkbenchKeyword` is the workshop's (`OutpostCategoryCrafting`
  for the six stations, as the task text says) and sorts it into a tab by its `RecipeFilters`. This is what the kit tries.
* **Verified (PC offline run of #737 at 3a561478, owner PC, real Starfield.esm; written by Claude, not re-run here):** the real recipe 2E2F2C
  has workbench keyword and its only recipe filter both `2CFDE6 OutpostCategoryCrafting`, **no build limit global**, created object the
  Furniture `WorkbenchIndustrial`, components Aluminum x4 and Iron x3. 18 category keywords exist (Structures 2A7578, Furniture 2BE3B5,
  Decorations 293ADF, Miscellaneous 06D72D, ...): so a **category of its own may be a recipe filter that is one of those**, and the
  `FO4SF_BPCategory` copy of the first filter (which is the workbench keyword itself) is a weaker guess than a vanilla category keyword. The
  stage passed against the real files, and the quest script compiled with the real compiler. The core has 11,700 statics with a model: the default
  choice (first four by form id) took an airship hull section and a cliff, so **stage with `--pieces`**, e.g.
  `--pieces FO4Core_woodcrate,FO4Core_metalbarrel01,FO4Core_junkwall01,FO4Core_cafetable01` (all accepted).
* **Unresolved, still not read (earlier list, narrowed by the above):** the values in the real `co_Outpost_Crafting_WorkbenchIndustrialStation` (2E2F2C): its created
  object and that record's type, its real filter keywords, whether a filter keyword is a tab, what its build limit GLOB is and whether
  other recipes share it, its menu art, sound and flags, and whether a created object needs components or a snap template to be
  placeable. Nothing in this repository has the file. **`make_build_pieces.py menu` reads exactly these from the real file on the PC**
  and `stage` writes the output to `menu.txt`; the fixture output of the same command is in `tests/test_build_pieces.py`
  (`test_menu_reads_the_template_recipe_and_its_neighbours`), to show the format only.

## What is built

| Piece | Where |
|---|---|
| Plugin writer, `menu`, `core`, `pieces`, `build`, `check`, `fixture` | `dotnet/BuildPieces` |
| Quest script (reads, places nothing) | `scripts/planet/FO4SF_BPQuest.psc` |
| Stage (menu, core, precheck, stage, log) | `scripts/planet/make_build_pieces.py` |
| Ride-along installer, own record `Data\FO4SFBuildPieces.install.json` | `scripts/planet/build_pieces_install.py` |
| Log reader | `src/fo4sf/workshop/build_pieces_log.py` |
| Tests | `tests/test_build_pieces.py`, `_log.py`, `_install.py` |

`FO4SFBuildPieces.esm` (master `Starfield.esm` only; adds records, overrides none; **the installed core is not a master**):

* three or four **pieces**, each a **shell** (the buildable) and a **recipe** (COBJ);
* a **recipe** is a copy of the template COBJ (default 2E2F2C): workbench keyword, filters, build limit, sound, art and flags are inherited,
  the created object is the shell, the description is the piece's name, the sort order follows the template's, and the cost is one component:
  **Iron when the template has it, else its first component, x1, x1, x2, x2** (small; the owner kit's resource kit gives 40 Iron and 40 Aluminum);
* a **shell** takes the **model path of a core STAT**. The core is read by the stage tool (`BuildPieces core <FO4TerrainCore.esm>`: editor id,
  local id, model), a path string is copied, and nothing in the plugin points at a core record, so it loads wherever it is put.
  Only ids and names go in the repository; no converted mesh, no core byte. Deviation from the task text ("found by script with
  GetFormFromFile"): the **menu needs the model at build time**, which a script cannot give a COBJ, so the stage reads the core's statics
  and the **script finds the same statics at run time** (`Game.GetFormFromFile(<local id>, "FO4TerrainCore.esm")`, the `_Mars` core if
  that plugin is absent) and says in the log whether each is there, as the workshop kit finds the bench;
* default choice of the pieces (`core`): the first four statics by form id with a model of their own, skipping editor ids or paths that say
  collision, marker, lod, trigger, invisible, navcut, blocker, dummy, helper, portal, sound, light, and a model already used.
  `--pieces a,b,c,...` names 3 to 40 by editor id instead (or `--set fo4`). **Whether these look like furniture or like walls is the PC's reading of the
  `core` list**; the fixture's choice (crate, barrel, wall, locker) is made up;
* QUST `FO4SF_BPQuest` (start game enabled, one stage, no properties): 20 s after the game starts it writes, per piece, what it found
  (shell, recipe, core static) to `FO4SFBP.0.log` and says how many on screen.

### The variant ladder (the real menu is not readable offline, so the kit is staged in rungs)

| Option | Values | Meaning |
|---|---|---|
| `--shell` | `clone` (default), `plain` | `clone`: each shell is a copy of the template's created object with the script, model and name replaced (what the real file makes buildable stays); `plain`: a bare Activator with a model and a name. `clone` is refused by name when the created object is not a Furniture, Activator or Static |
| `--category` | `vanilla` (default), `add`, `replace` | `vanilla`: the template's filters (the pieces go to the CRAFTING tab); `add`: the template's filters plus a keyword of our own (`FO4SF_BPCategory`, a renamed copy of the template's first filter keyword, shown as "FO4 pieces"); `replace`: the first filter swapped for it |
| `--tab` | `structures`, `furniture`, `decorations`, `miscellaneous`, `storage`, `defenses`, or a KYWD editor id | (second pass, FAL-433) files the recipes under a vanilla `OutpostCategory*` keyword instead of our own; needs `--category add\|replace`, adds no KYWD record. `replace`: workbench keyword AND filter list become the tab keyword (what the template has twice as `OutpostCategoryCrafting`); `add`: the template's workbench keyword and filters stay and the tab keyword is appended to the filters. The PC reports per rung which tab lists them and whether a tab that was empty before appears at all |
| `--workbench` | a KYWD editor id, a tab short name or 6 hex digits of its form id | (third pass, FAL-438) the recipes' workbench keyword, chosen apart from the filter; the template's filters stay. Not together with `--tab` or `--category add\|replace` |
| `--filter` | as `--workbench`, or `own` | the recipes' only filter keyword, the template's workbench stays unless `--workbench` is given. `own`: a KYWD of our own (`FO4SF_BPCategory`, full name "FO4 pieces", copy of the template's first filter): does a sixth tab with that name appear? |
| `--variants` | **EXPERIMENTAL, off by default; crashes the game before the main menu (0xC0000005, PC at 47dc064b, with and without pictures).** Flag, with `--set fo4` | one recipe per group (junk walls 01..07 as "FO4 junk wall", the pier shack walls, the pier shack roofs) whose created object is a form list (`FO4SF_BPList1..`, ids 852..85F). **Fourth pass (FAL-445): the list holds one RECIPE per variant** (`FO4SF_BPInner<n>`, ids 860..887, each making its shell), as the vanilla `OutpostFurnitureBedList02_Beds` (15 items: nine `co_Outpost_Furniture_BedList02_Decor*` recipes, a pack-in, five Furniture objects). Third pass (shells in the list) showed seven separate entries all named "FO4 junk wall", no `1/7` counter. `menu --cobj co_Outpost_Furniture_BedList02_Decor1_01` and `co_Outpost_Furniture_BedList02_Beds` print what the vanilla recipes are. Single pieces keep their own recipe |
| `--lead` | `none` (default), `shells` | with `--variants`: the form list holds only the recipes, or the variants' shells first and then the recipes (the vanilla list's order: a pack-in and Furniture, then recipes). One rung per idea; offline cause not proven (see below) |
| `--inner` | `same` (default), `bare` | with `--variants`: the inner recipes' filing. `same`: the list recipe's workbench keyword and filters; `bare`: no workbench keyword, no filter (a recipe only the list offers). The vanilla `_Decor` recipes' real filing is unread: `menu` prints it (the FLST items show each recipe's workbench, filters, limit, sort, conditions, art) |
| `--pictures` | `N`, 0 to 40 (default: every piece with `--set fo4`, 0 otherwise; verified in the game at 47dc064b: the drawn pictures replace the round "!") | draws 128 x 128 pictures (shape + initials, BC3, DX10 header, nothing from either game) for the first N pieces' shells under `Data/Textures/Interface/WorkshopIcons/FO4SFBuildPieces.esm/<shell id, 8 hex>cl.dds`; the installer packs them into `FO4SFBuildPieces - Textures.ba2` (DX10) next to the Main archive |
| `--template-filing` | flag | `--set fo4` only: keep the template's workbench keyword and filters (the CRAFTING tab) instead of the default below |

**Default placement of `--set fo4` (fourth pass; rung A of the third, PC PASS at 211dae28):** workbench keyword `2CFDE6`, filter `06D72D`
(the MISCELLANEOUS tab, after its two vanilla entries). Any of `--workbench`, `--filter`, `--tab`, `--category add|replace` or
`--template-filing` replaces it. `plan.json` says what was applied (`variant.workbench`, `variant.filter`, `variant.default_filing`).
**The filter picks the tab; the workbench keyword decides whether the workshop offers the recipe.**

PC results of the second pass (#740 at 4df538ba, 11 Nov): this workshop shows CRAFTING, FURNITURE, DECORATIONS, DISPLAYS, MISCELLANEOUS; the workbench keyword decides whether it offers a recipe (`replace --tab structures`: workbench 2A7578 not listed; `replace --tab miscellaneous`: workbench 06D72D not listed; `add --tab structures`: workbench 2CFDE6, CRAFTING, all 34, no STRUCTURES tab). Vanilla MISCELLANEOUS entries use workbench `0E6A3E OutpostCategoryMiscInterior` with filter `06D72D`. Next rungs: workbench 2CFDE6 + filter 06D72D; workbench 0E6A3E + filter 06D72D; workbench 2BE3B5 / 293ADF + own filter; workbench 2CFDE6 + `--filter own`.
| `--set` | `fo4` | a named list of core statics (`FO4Core_junkwall01..07`, `junkwallcorner01`, `junkwalldoor01`, `junkwallgate01`, `piershackwall*`, `piershackroof*`, `sandbagsingle01`, `bedmetal01`, `cafetable01`, `woodcrate`, `cratelarge01`, `metalbarrel01`; each tried as `FO4Core_<name>`, then as written). A name the core lacks is printed on stderr and skipped. `--pieces` now takes 3 to 40 editor ids, `*` allowed; the default stays four. Layout: shells `0x802..0x829`, recipes `0x82A..0x851`; cost 1,1,2,2 repeating |

**The pictures (fourth pass, FAL-445; read from the game's archives and program, not from this repo):** the base game has
`textures/interface/workshopicons/<created object's form id, 8 hex>cl.dds` for each buildable: 128 x 128, one mip, DXGI 77 (BC3). The program
builds a mod item's name with `%s/%08x%s.dds` from the plugin's file name, the form id masked to the file's own part and a suffix:
`Textures/Interface/WorkshopIcons/FO4SFBuildPieces.esm/00000802cl.dds` for the shell at 0x802. Loose files of that name did not show in one run (no
loose-file setting on this install), so the stage holds them under `Data/Textures/...` and `build_pieces_install.py` builds `FO4SFBuildPieces - Textures.ba2`
(Archive2 `-format=DX10`, stored) beside the plugin, the scripts staying in `- Main.ba2`; `exp_install.py --textures-archive` is the switch (other kits
keep their textures in Main). The pictures are drawn by `src/fo4sf/workshop/piece_icons.py` (pure Python): a dark tile, a light frame, a plain shape
(square, circle, triangle, diamond by the piece's number) in a colour from its name, its initials in our own 5 x 7 letters; BC3, DX10 header as
`fo4sf.ba2` regenerates one. **Offline only:** the picture's look (decoded and viewed), the archive reader round trip on a synthetic DX10 archive, the
installer with a stub archiver. **Not run:** Archive2 on the PC, the game reading the archive, and whether the picture replaces the round "!". A
form list entry's picture would be keyed by the list's id (0x852..), not the shell's: `--pictures` draws shells only.

**The icon (rung 2 of FAL-433):** the template has `menu art none`, so the picture of a station is on the created object or elsewhere.
`menu` now prints every set field of the created object and of the COBJ (`fields of created object`, `fields of COBJ`, art-like names marked
`<- art-like`) and the fields of the records that art-like links point to. Run `make_build_pieces.py menu` on the real file and read it; nothing
offline says which field it is. `menu` also prints a `tabs` table: for each `OutpostCategory*` keyword how many recipes use it as workbench
keyword / as filter, with up to three samples (menu-art ones first), so a better template than 2E2F2C can be named with `--cobj`.

"A category of their own if the menu allows one": whether it does is rung 2 and 3 of the ladder. If the menu needs a tab keyword
that is not just a renamed filter, `menu` shows it (the `OutpostCategory*`/`Filter*` keyword list) and the next commit changes the
keyword, not the shape. Start with `clone` + `vanilla`: if nothing is listed there, the problem is the shell or the template, not the category.
Stage the next rung only after the screenshot of the last one.

`check` (Mutagen read-back, against the same Starfield.esm and core) asserts: the file name and master flag; masters exactly `[Starfield.esm]`
(the core is not one); every record is ours (no override); the record count; each shell's model, name and no script; each recipe makes
its shell, has the template's workbench keyword and build limit, one component of the stated cost, and the filters the variant says; the
quest's flags and script with no properties. Offline tests run it on the six variants of a fixture and refuse a wrong variant, a wrong choice and a
file of another shape.

## Install and read (the owner's word, game closed)

    python scripts\planet\make_build_pieces.py menu                       (read only; paste it on FAL-381)
    python scripts\planet\make_build_pieces.py core                       (read only; the pieces a build would use)
    python scripts\planet\make_build_pieces.py precheck
    python scripts\planet\make_build_pieces.py stage --out <dir> [--pieces a,b,c] [--shell clone|plain] [--category vanilla|add|replace]
    python scripts\planet\build_pieces_install.py install --dir <dir> --starfield <game dir>
    ... session ...
    python scripts\planet\make_build_pieces.py log
    python scripts\planet\build_pieces_install.py uninstall --starfield <game dir>

The kit rides along: **install the workshop owner kit too** (`workshop_probe_install.py`, its own record), it gives the bench and
the resources. The log is `My Games\Starfield\Logs\Script\User\FO4SFBP.0.log` (lines `FO4SFBP rt=... <event> key=value ... end=true`).
The kit pairs with the installed core. THROWAWAY STATE ONLY, NO SAVE.

## Console card (for the PC; one answer per line)

1. `make_build_pieces.py menu` and `core`: paste both on FAL-381 first. They answer, from the real files, what 2E2F2C is made of and which
   statics the default choice takes. If the choice is wrong (a wall segment, a trigger), name three or four with `--pieces`.
2. Stage rung 1 (`clone` + `vanilla`), install it **and** the workshop owner kit, start the game, load a throwaway save in open ground
   (north or west of where you stand if the ground drops, `workshop-probe.md`).
3. Wait 20 s: the screen says how many pieces were found. `make_build_pieces.py log` must say `ok: all N pieces`. If it says `PARTIAL` or
   `NONE FOUND`, no menu question can be answered yet: the plugin is not loaded or a record is missing.
4. Console: `player.placeatme <index>000802 1` (the load index of `FO4SFBuildPieces.esm`, two digits, then `000802`; the console does not know
   editor ids). Expected: the shell stands in front of you with the core static's model. Repeat for `000803`, `000804`, `000805`. This tests the
   model path and the shell alone, before the menu. If the model is missing (a hole, an error box), the path or the core's archive is the problem.
5. Drop the owner kit's bench (or use the Red Rocket bench), `player.additem 0000556E 20` and `player.additem 0000557D 20` if the resource kit
   was not dropped. Look at the bench: WORKSHOP / BUILD [E]. E: build mode. Screenshot every tab. **Are the pieces listed? In which tab? With which cost?**
6. Pick one and place it. Does it place, does the cost come off (Iron count), does the build limit bar move? Place it twice: does the second one respect a limit?
7. Not listed: stage rung 2 (`--shell plain`), then `--category add`, then `replace`, one at a time, with a new `--out` each (an earlier stage is
   never overwritten). Each rung is the same card from step 2.
8. Leave and re-enter the cell; `make_build_pieces.py log`; paste the log and the screenshots on the task. Uninstall.

## Owner card: build a piece by hand (eight steps, no console)

1. Install the workshop owner kit and the build pieces kit (the PC's stage folder), game closed.
2. Start Starfield, load a throwaway save in open ground. Do not save.
3. Wait 20 s: the screen says "FO4SF build pieces: N found".
4. Open the inventory and drop the resource kit (40 Iron and 40 Aluminum), then the workshop kit: a bench stands in front of you.
5. Look at the bench: the prompt reads WORKSHOP / BUILD [E]. Press E.
6. Look through the tabs of the build mode: do the Fallout 4 pieces appear (names starting "FO4 ")? Write down the tab and the price.
7. Pick one, turn the view to the side (straight ahead it can read "Needs support"), place it. Write down what happened. Esc **only while build mode is open**.
8. Quit without saving, then uninstall both kits. `make_build_pieces.py log` prints what the game found.

## Not run, honestly

* **Everything in the game:** whether any piece is listed, in which tab, whether a shell is placeable, whether a cost is taken, whether the limit
  counts, whether a Mutagen-written record of this shape is accepted by the engine (the workshop kit's records were; these are new types).
* **Starfield.esm:** the real 2E2F2C and every value listed under "Unresolved" above. `menu` reads it on the PC.
* **The installed core:** which statics exist, their editor ids and local ids, their model paths; the fixture's are made up. `core` reads them on the PC.
* **The Papyrus compile** of `FO4SF_BPQuest.psc` (the PC's compiler); only a fake compiler ran in the tests. The script's natives are the same
  ones the workshop and power armor kits already compile (`Game.GetFormFromFile`, `IsPluginInstalled`, `Debug.OpenUserLog`, `TraceUser`,
  `Notification`, `Utility.GetCurrentRealTime`, `StartTimer`, `GetFormID`): no optional native, no guessed name.
* **Fourth pass (FAL-445):** the vanilla `_Decor` recipes' filing (the inner recipes' `--inner` rung is a guess), whether a recipe inside a form list is
  shown as a VARIANTS entry (`1/7`), whether the pictures replace the "!", Archive2's DX10 output for these files, the BA2 name hashes (written by Archive2, not by us).
* **The category keyword:** a renamed copy of a filter keyword is a guess at what makes a tab.
* **A game update** changes Starfield.esm: `plan.json` pins its SHA-256 and the core's, and the installer refuses a changed one.

## --variants crash (FAL-464; offline, no game, nothing here is verified as the cause)

PC at 47dc064b: `--set fo4 --pictures 3` passes (pictures show); `--variants` (with or without pictures) crashes at data load, 0xC0000005.
The pictures-only plugin has the same shells and outer recipes, so the difference is the form list of recipes and the inner recipes.
Checked offline on the fixture: no inner recipe makes a list or a recipe (each makes its own Furniture shell), no list holds itself,
form ids 0x852..0x85F (lists) and 0x860..0x887 (inner recipes) do not overlap shells or outer recipes. Differences from the vanilla list that
remain as candidate ideas, one rung each: (1) our list holds ONLY recipes, the vanilla one starts with a pack-in and Furniture (`--lead shells`);
(2) our inner recipes carry the workbench keyword and filter (`--inner same`), vanilla `_Decor` recipes may not (`--inner bare`); (3) our inner
recipes are copies of the workbench template COBJ and keep its other fields (e.g. the build-limit global `MaxBuildCountGlobal`); whether a vanilla `_Decor` recipe has one is unread (no rung yet, the real record decides).
Needs from the real file: `menu --cobj co_Outpost_Furniture_BedList02_Beds` and `co_Outpost_Furniture_BedList02_Decor1_01`.
