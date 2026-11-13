# gwe second-read notes (Grok, session 01a14976)

Packet: issue 32 comment 6387271188 (MA/ME/DC) then keep-working continuation of the rest of batch `gwe`. Claim 6387328704.

MA done; ME done; DC done; MD done; PA done; VA done; NJ done; OH done; TN done; coast/None done; WV done.

Whole 170-entry `gwe` second-read is complete.

## Scope

- Input (read-only): `research/lore-inbox/store/data/entries/gwe.jsonl` (170 entries, all `unchecked` at start).
- Marker file (read-only): `D:\Modding\scratch\mapmarkers\cw_markers.json` (Fallout4.esm / Commonwealth, 310 named markers).
- Output: this folder. Fold-in replaces `gwe.jsonl`, so this file holds the **whole** 170-entry batch.
- No ids changed. No entries dropped. `label` stays `as-reported` (wiki pages as pointers to game/dev/guide quotes; primary in-game text not opened in CK). Existing lead rulings kept. Wiki is never `source_kind` `fan`.

## Second-read method

Opened fallout.wiki raw for: The_Commonwealth, Boston, Fallout_4 (Story / Pre-Production), Nuka-World_(location), Nuka-World_(add-on), Bradberton, The_Island, Far_Harbor_(add-on), Far_Harbor_(location), Capital_Wasteland, Point_Lookout_(DLC), Point_Lookout_(location), The_Pitt_(DLC), Atlantic_City, Burning_Springs_(Location), Skyline_Valley_(region), Appalachia.

Confirmed as written: `check=checked`, `check_note=null`.
Added in-game pos from a named Commonwealth map marker: `check=corrected`, `check_note` names the marker and FormID.
Unsupported: none dropped.

## Counts

- 19 corrected (Commonwealth `pos` from `cw_markers.json`).
- 151 checked (no named Commonwealth pin, or not a FO4 Commonwealth place).
- 0 still `unchecked`.
- 0 dropped.

## Corrected (pos added) — 19

- `GW-0009` Natick Banks FormID 0002C821 x=-86800 y=-47056
- `GW-0011` The Castle FormID 0002BCA5 x=48321.934 y=-46600.113
- `GW-0012` The Castle FormID 0002BCA5 x=48321.934 y=-46600.113
- `GW-0013` Massachusetts State House FormID 001A5B64 x=12895.229 y=-12818.047
- `GW-0014` Massachusetts State House FormID 001A5B64 x=12895.229 y=-12818.047
- `GW-0015` Old North Church FormID 0002C866 x=29036.896 y=1093.0277
- `GW-0016` Bunker Hill FormID 0002B880 x=18232.314 y=14378.211
- `GW-0017` USS Constitution FormID 00074BE0 x=27359.854 y=-3844.0212
- `GW-0019` Boston Public Library FormID 0002BB12 x=-3490.257 y=-22646.29
- `GW-0021` Boston Airport FormID 00084BEB x=48073.9 y=-3331.9624
- `GW-0022` C.I.T. Ruins FormID 0016349B x=-16793.678 y=-2777.44
- `GW-0024` Concord FormID 00082138 x=-60286.01 y=72977.79
- `GW-0025` Lexington FormID 00024F9C x=-33029.695 y=41006.22
- `GW-0026` Malden Center FormID 0002C561 x=14824.555 y=58814.344
- `GW-0027` Quincy Ruins FormID 0002C611 x=27461.742 y=-85579.984
- `GW-0028` Salem FormID 000BEB22 x=93443.66 y=80551.92
- `GW-0030` Revere Beach Station FormID 0002BA87 x=57612.566 y=29377.758
- `GW-0031` Lexington FormID 00024F9C x=-33029.695 y=41006.22
- `GW-0032` Malden Center FormID 0002C561 x=14824.555 y=58814.344

## Why the rest have no FO4 Commonwealth pos

- Regions / whole-map: GW-0001 Commonwealth, GW-0004 Boston, GW-0007 Glowing Sea.
- No named Commonwealth marker: GW-0010 Diamond City / Fenway, GW-0018 Paul Revere Monument, GW-0020 Freedom Trail, GW-0029 Nahant town, GW-0023 Lake Quannapowitt.
- Other worldspaces: Nuka-World, Far Harbor / The Island, Point Lookout, The Pitt, Appalachia / Skyline Valley / Burning Springs / Atlantic City.
- DC / FO3 Capital Wasteland.
- Zone / quote / design entries without one map pin.

## Rulings left as written

- GW-0002 Emil 2009 (tier 2 adopt).
- GW-0008 / GW-0031..0035 guide zones (tier 2 adopt).
- GW-0014 State House 1969 Thirteen Commonwealths (tier 2 hold).
- GW-0057 Burgess GDC 2011 (tier 2 adopt).
- GW-0058 cut downtown 26 to 12 (tier 3 hold).
- GW-0065 / GW-0071 Gardiner Point Lookout (tier 2 adopt).
- GW-0078 / GW-0079 Pitt radiation / Trogs (tier 2 adopt).
- GW-0081 guide dates the Scourge to 2042 (tier 2 **reject**; contradicts GW-0080 ~2247). Confirmed, not reopened.
- GW-0089 / GW-0090 Baudoin Appalachia nukes (tier 2 adopt).
- GW-0096 / GW-0098 / GW-0100 / GW-0120 / GW-0123 / GW-0124 / GW-0129..0132 / GW-0135 FO76 guide (tier 2 adopt).
- GW-0104 Massey Bramwell (tier 2 adopt).
- GW-0122 Massey / Purkeypile Whitespring (tier 2 adopt).
- GW-0148 Purkeypile Cranberry Bog (tier 2 adopt).
- GW-0156 McKevitt Chattanooga (tier 2 adopt).
- GW-0169 Massey next Expeditions city (tier 2 adopt).
- GW-0170 Making of Fallout 4 (tier 2 adopt).

## Dropped ids

None.

## Validate

`python tools/lore.py validate` on this `verified-1.jsonl`: 0 problems.

Did not touch `queue-todo.tsv` (599 pages). Did not write `store/data/`. Did not run plan.ps1. Did not write game Data.

## Delivery

Draft PR https://github.com/fo4sf/fo4-to-starfield/pull/544 (first commit 5f16e7ef MA/ME/DC; this folder is the fold-in copy). #32 recap 6387402578 for the first slice.
