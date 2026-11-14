"""FO4SFPipboyMenu's stage (d), the STAT page (FAL-272): the movie make_probe_swf.py --page writes (read back by the
module's own reader and checked for layout), the stager and the installer's stage check, and the plugin's page code as
text: the names, line count, width and characters agree with the movie; the two new ids are checked against SFSE's
addresses and only at stage (d); every form is typed by RTTI before a field of it is read; the only calls into the
game are the checked GetActorValue slot and the engine's lookup by form id; the reads run on the main thread and the
writes on the menu's; the menu-stack read is gone; the time is shown only at a value offset found and range-checked.
Also the owner's card: at most eight steps, no console and no log in them, and its plain-text copy beside the staged
plugin in the launcher's format (a title, then 1. to 8., one line each). No
compiler here: the PC build is the compile check."""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_pipboy_probe as mpp  # noqa: E402
import make_probe_swf as swf  # noqa: E402
import pipboy_probe_install as ppi  # noqa: E402

TWIPS = swf.TWIPS
# the uncompressed bodies of the movies of #711's head, which test C passed with (FAL-216, e7925e00): --page must not
# change them. The body, not the CWS file: zlib builds differ in their compressed bytes (the PC's Python 3.14 with
# zlib-ng gives other ones), the body is what the game reads
CHANNEL_BODY_SHA256 = "e67efdc416028b4e8a4a3c7b9a8d39cdbb4a3b99a536d55322a90ca92527c188"
STAGE_B_BODY_SHA256 = "62906d68d012e37ca2f336a715a9ae8d116d3e99a29b8f08eb597ea7541d715f"
SCRIPT = os.path.join(ROOT, "scripts", "ui", "make_probe_swf.py")


def function(text, signature):
    """The body of the function whose definition starts with `signature` (to its closing brace at one tab)."""
    start = text.index(signature)
    end = text.index("\n\t}\n", start)
    return text[start:end]


def inside(inner, outer):
    x, y, w, h = inner
    ox, oy, ow, oh = outer
    return ox <= x and oy <= y and x + w <= ox + ow and y + h <= oy + oh


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def box_of(bounds):
    xmin, xmax, ymin, ymax = bounds
    return xmin, ymin, xmax - xmin, ymax - ymin


class PageMovieTests(unittest.TestCase):
    movie = swf.read_movie(swf.movie_bytes(page=True))
    tags = movie["tags"]
    by_id = {t["id"]: t for t in tags if "id" in t}
    places = [t for t in tags if t["name"] == "PlaceObject2"]

    def test_channel_and_stage_b_movies_are_unchanged(self):
        for kw, digest in (({"channel": True}, CHANNEL_BODY_SHA256), ({}, STAGE_B_BODY_SHA256)):
            data = swf.movie_bytes(**kw)
            self.assertEqual(hashlib.sha256(zlib.decompress(data[8:])).hexdigest(), digest, kw)
            self.assertEqual(swf.movie_bytes(compressed=False, **kw)[8:], zlib.decompress(data[8:]), kw)

    def test_deterministic_and_not_with_channel(self):
        self.assertEqual(swf.movie_bytes(page=True), swf.movie_bytes(page=True))
        with self.assertRaises(swf.SwfError):
            swf.movie_bytes(page=True, channel=True)

    def test_header_and_no_code(self):
        self.assertEqual(self.movie["signature"], "CWS")
        self.assertEqual(self.movie["version"], 12)
        self.assertTrue(self.tags[0]["actionscript3"])
        codes = {t["code"] for t in self.tags}
        for code in (82, 72, 76, 59, 12, 9):                                   # DoABC2, DoABC, SymbolClass, DoAction...
            self.assertNotIn(code, codes)

    def test_named_children_in_depth_order(self):
        names = [(p["depth"], p.get("instance")) for p in self.places]
        lines = [(4 + i, f"{swf.LINE_FIELD}{i}") for i in range(swf.PAGE_LINES)]
        self.assertEqual(names, [(1, None), (2, None), (3, swf.TAB_FIELD)] + lines +
                         [(4 + swf.PAGE_LINES, None), (5 + swf.PAGE_LINES, swf.TAB_BUTTON),
                          (6 + swf.PAGE_LINES, swf.CLOSE_BUTTON)])
        self.assertEqual(len({p["character"] for p in self.places}), len(self.places))

    def test_font_is_the_page_table(self):
        font = self.by_id[swf.FONT_ID]
        self.assertEqual(font["codes"], "".join(sorted(swf.PAGE_FONT)))
        self.assertTrue(set(swf.FONT) < set(swf.PAGE_FONT))
        for ch, glyph in zip(font["codes"], font["glyphs"]):
            self.assertEqual(len(glyph), sum(bin(r).count("1") for r in swf.PAGE_FONT[ch]), ch)
            for path in glyph:
                self.assertEqual((path["fill0"], path["fill1"]), (1, 0), ch)
        for ch, rows in swf.PAGE_GLYPHS.items():
            self.assertEqual(len(rows), 7, ch)
            self.assertTrue(all(0 <= r < 32 for r in rows), ch)
            self.assertNotIn(ch, swf.FONT, ch)

    def test_fields(self):
        panel = box_of(self.by_id[swf.RECT_ID]["bounds"])
        fields = [self.by_id[i] for i in range(swf.PAGE_TITLE_ID, swf.PAGE_HINT_ID + 1)]
        self.assertEqual([f["name"] for f in fields], ["DefineEditText"] * (swf.PAGE_LINES + 3))
        texts = [f["text"] for f in fields]
        self.assertEqual(texts, [swf.PAGE_TITLE, swf.PAGE_TAB_TEXT] + [swf.PAGE_LINE_TEXT] * swf.PAGE_LINES +
                         [swf.PAGE_HINT])
        for f in fields:
            self.assertEqual(f["font"], swf.FONT_ID)
            self.assertEqual(f["height"], swf.FIELD_PX * TWIPS)
            self.assertEqual(f["flags"], [0x80 | 0x08 | 0x04 | 0x01, 0x10 | 0x01])  # read-only, no select, outlines
            self.assertTrue(set(f["text"]) <= set(swf.PAGE_FONT), f["text"])
            self.assertTrue(inside(box_of(f["bounds"]), panel))
        boxes = [box_of(f["bounds"]) for f in fields]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                self.assertFalse(overlap(a, b), (a, b))

    def test_buttons(self):
        panel = box_of(self.by_id[swf.RECT_ID]["bounds"])
        hint = box_of(self.by_id[swf.PAGE_HINT_ID]["bounds"])
        boxes = []
        for rect_id, label_id, sprite_id, label in ((swf.TAB_RECT_ID, swf.TAB_LABEL_ID, swf.TAB_BUTTON_ID, swf.TAB_LABEL),
                                                    (swf.CLOSE_RECT_ID, swf.CLOSE_LABEL_ID, swf.CLOSE_BUTTON_ID,
                                                     swf.CLOSE_LABEL)):
            sprite = self.by_id[sprite_id]
            self.assertEqual(sprite["name"], "DefineSprite")
            self.assertEqual([(t.get("depth"), t.get("character")) for t in sprite["tags"] if t["name"] == "PlaceObject2"],
                             [(1, rect_id), (2, label_id)])
            box = box_of(self.by_id[rect_id]["bounds"])
            self.assertEqual(box[2:], (swf.PAGE_BUTTON[0] * TWIPS, swf.PAGE_BUTTON[1] * TWIPS))
            self.assertEqual(swf.PAGE_BUTTON, (360, 90))                            # test C's CLICK button
            self.assertTrue(inside(box, panel))
            self.assertFalse(overlap(box, hint))
            self.assertTrue(inside(box_of(self.by_id[label_id]["bounds"]), box))
            self.assertEqual(len(self.by_id[label_id]["paths"]),
                             sum(bin(r).count("1") for ch in label for r in swf.FONT[ch]))
            boxes.append(box)
        self.assertFalse(overlap(*boxes))
        self.assertLess(boxes[0][0], boxes[1][0])                                     # NEXT TAB left of CLOSE

    def test_columns(self):
        self.assertEqual(swf.page_columns(), 54)
        line = box_of(self.by_id[swf.PAGE_LINE0_ID]["bounds"])
        self.assertEqual(line[2] // (6 * swf.FIELD_PX * TWIPS // 8), swf.page_columns())

    def test_cli_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "page.swf")
            r = subprocess.run([sys.executable, SCRIPT, "--out", out, "--page"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), swf.movie_bytes(page=True))
            r = subprocess.run([sys.executable, SCRIPT, "--out", out, "--page", "--channel"], capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("two different movies", r.stderr)


class PageStageTests(unittest.TestCase):
    def test_stage_with_page_and_the_installers_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            esm, movie = mpp.stage(tmp, page=True)
            self.assertTrue(movie.endswith(os.path.join("Interface", "FO4SF_PipboyMenu.swf")))
            with open(movie, "rb") as f:
                self.assertEqual(f.read(), swf.movie_bytes(page=True))
            mpp.check(esm)
            self.assertEqual(ppi.stage_problems(tmp), [])
            self.assertEqual(sorted(os.listdir(tmp)), ["Data", "FO4SFPipboyProbe.esm", "owner-card.txt"])
            with open(os.path.join(tmp, "owner-card.txt"), "rb") as f:
                self.assertEqual(f.read().decode("utf-8"), mpp.PAGE_CARD)
            mpp.stage(tmp, channel=True)                         # no page, no card: a stale one would mislead
            self.assertNotIn("owner-card.txt", os.listdir(tmp))

    def test_owner_card_txt_is_the_launchers_format(self):
        # docs/ai/launcher-tests.md (FAL-274): UTF-8, at most 16 KiB, a title, then one to eight steps "1. " to "8. "
        raw = mpp.PAGE_CARD.encode("utf-8")
        self.assertLessEqual(len(raw), 16384)
        self.assertFalse(any(ord(c) < 32 and c not in "\r\n\t" for c in mpp.PAGE_CARD))
        lines = [line.strip() for line in mpp.PAGE_CARD.splitlines() if line.strip()]
        self.assertEqual(len(lines), 9)
        self.assertNotRegex(lines[0], r"^\d+\.")
        for i, line in enumerate(lines[1:], 1):
            self.assertRegex(line, rf"^{i}\. \S")
        steps = "\n".join(lines[1:]).lower()
        for word in ("console", "log", "save", "install", "`", "*", "#"):
            self.assertNotIn(word, steps, word)
        for seen in ("F10", "NEXT TAB", "CLOSE", "TIME"):
            self.assertIn(seen, mpp.PAGE_CARD, seen)

    def test_stage_cli_page_and_channel_exclude_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(mpp.main(["stage", tmp, "--page"]), 0)
            with self.assertRaises(SystemExit):
                mpp.main(["stage", tmp, "--page", "--channel"])


class PagePluginTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    card = (ROOT / "docs" / "spikes" / "pipboy-stat-page-owner-card.md").read_text(encoding="utf-8")
    page = main[re.search(r"// -+ stage d: the page", main).start():re.search(r"// -+ the menu's slots", main).start()]

    def test_the_movie_and_the_plugin_agree(self):
        self.assertIn(f"constexpr std::size_t   kPageLines = {swf.PAGE_LINES};", self.main)
        self.assertIn(f"constexpr std::size_t   kPageColumns = {swf.page_columns()};", self.main)
        chars = re.search(r'constexpr std::string_view kPageChars = "((?:[^"\\]|\\.)*)";', self.main).group(1)
        self.assertEqual(chars, "".join(sorted(swf.PAGE_FONT)))
        for constant, name in (("kTabFieldName", swf.TAB_FIELD), ("kLineFieldName", swf.LINE_FIELD),
                               ("kTabButtonName", swf.TAB_BUTTON), ("kCloseButtonName", swf.CLOSE_BUTTON)):
            self.assertRegex(self.main, rf'constexpr auto\s+{constant} = "{name}";')
        self.assertIn('std::format("{}{}", kLineFieldName, i - 1)', self.page)

    def test_every_literal_on_the_page_is_in_its_font(self):
        collect = function(self.main, "void PageCollect()")
        bodies = collect + "".join(function(self.main, f) for f in ("std::string NameText(", "std::string TimeText()",
                                                                       "std::pair<std::string, std::string> PlaceText()"))
        # the page's own text is upper case; lower-case literals are log keys and reasons
        texts = [t for t in re.findall(r'"([^"]*)"', bodies) if t and t == t.upper()]
        self.assertGreaterEqual(len(texts), 20)
        for text in texts:
            sample = re.sub(r"\{[^}]*\}", "12", text)
            self.assertTrue(set(sample) <= set(swf.PAGE_FONT), text)
        self.assertIn("line = PageText(line);", collect)
        page_text = function(self.main, "std::string PageText(")
        self.assertIn("a_text.substr(0, kPageColumns)", page_text)
        self.assertIn("kPageChars.find(up) != std::string_view::npos ? up : '?'", page_text)

    def test_two_new_ids_checked_against_sfse_and_only_at_stage_d(self):
        self.assertIn('{ "TESDataHandler.Singleton", 937572, "libxse, equal to SFSE\'s" },', self.main)
        self.assertIn('{ "TESForm.LookupByID", 47401, "libxse, equal to SFSE\'s" },', self.main)
        self.assertIn("kDataHandlerSingleton = kIdCountC,\n\t\tkLookupById,\n\t\tkIdCount", self.main)
        self.assertIn("constexpr std::uint32_t kLookupByIdRva = 0x5DE3B0;", self.main)
        self.assertIn("kIdCountC,", self.main)
        self.assertIn("kDataHandlerSingleton = kIdCountC,", self.main)
        self.assertIn("std::size_t IdCount() { return g_stage >= 4 ? kIdCount : ChannelIdsNeeded() ? kIdCountC : kIdCountB; }",
                      self.main)
        self.assertIn("constexpr std::uint32_t kDataHandlerRva = 0x5FD9B28;", self.main)
        check = function(self.main, "bool CheckPageIds()")
        self.assertIn("std::pair{ kDataHandlerSingleton, kDataHandlerRva }, std::pair{ kLookupById, kLookupByIdRva }", check)
        self.assertIn("if (g_rva[id] != rva) {", check)
        self.assertIn('return Refuse("page_ids"', check)
        self.assertIn("(ChannelIdsNeeded() && !CheckChannelIds()) || (g_stage >= 4 && !CheckPageIds())", self.main)
        # libxse and SFSE 0.2.21 agree on the list layout and the two types
        for line in ("constexpr std::size_t   kFormArraysAt = 0x70;", "constexpr std::size_t   kFormArrayBytes = 0x18;",
                     "constexpr std::size_t   kGlobType = 0x0A;", "constexpr std::size_t   kAvifType = 0x6D;"):
            self.assertIn(line, self.main)

    def test_every_form_is_typed_before_it_is_read(self):
        edid = function(self.main, "std::string EditorIdOf(")
        self.assertLess(edid.index("!IsType(a_form, a_type, type)"), edid.index("Peek(a_form + a_editorIdAt, entry)"))
        find = function(self.main, "void FindForms()")
        for line in ('AcceptById(kGameHourId, "GameHour", "TESGlobal@@", kGlobalEditorIdAt, g_forms.gameHour)',
                     'AcceptById(kGameDaysPassedId, "GameDaysPassed", "TESGlobal@@", kGlobalEditorIdAt',
                     'AcceptById(kHealthId, "Health", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.health)',
                     'AcceptById(kCarryWeightId, "CarryWeight", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.carryWeight)',
                     'AcceptById(kExperienceId, "Experience", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.experience)',
                     'if (!form || !IsType(form, "ActorValueInfo@@", type)) {',
                     'EditorIdOf(form, "ActorValueInfo@@", kAvifEditorIdAt)',
                     "for (std::uint32_t id = 1; id < kCoreFormIds; ++id) {", "((i + 1) << 24) | kRadsLocalId",
                     "0xFE000000u | ((i - 0xFD) << 12) | kRadsLocalId"):
            self.assertIn(line, find, line)
        accept = function(self.main, "std::string AcceptById(")
        self.assertLess(accept.index("if (IsType(form, a_type, type)) {"), accept.index("a_out = form;"))
        self.assertLess(accept.index("a_out = form;"), accept.index("Peek(form + a_editorIdAt, entry)"))
        for constant, value in (("kHealthId", "0x2D4"), ("kCarryWeightId", "0x2DC"), ("kExperienceId", "0x2C9"),
                                ("kGameHourId", "0x38"), ("kGameDaysPassedId", "0x39")):
            self.assertRegex(self.main, rf"constexpr std::uint32_t {constant} = {value};")
        self.assertNotIn("inventoryWeight", self.main)
        self.assertNotIn("ScanForms", self.main)
        page_scan = function(self.main, "void PageScan()")
        self.assertLess(page_scan.index("g_forms.strings = CheckStrings();"), page_scan.index("FindForms();"))
        self.assertIn("if (g_forms.strings) {", page_scan)
        self.assertIn("LogFormArrays(handler);", page_scan)
        layout = function(self.main, "void LogFormArrays(")
        self.assertIn("Peek(a_handler + kFormArraysAt + i * kFormArrayBytes, q)", layout)
        for name, tail in (("std::uintptr_t DataHandler()", "TESDataHandler@@"), ("std::string LevelText()", "TESNPC@@"),
                           ("std::pair<std::string, std::string> PlaceText()", "TESObjectCELL@@")):
            body = function(self.main, name)
            self.assertIn(f'IsType(', body, name)
            self.assertIn(f'"{tail}"', body, name)
        level = function(self.main, "std::string LevelText()")
        self.assertLess(level.index('IsType(base, "TESNPC@@", type)'), level.index("BaseOffset(type"))
        self.assertLess(level.index("CheckSubobject(base, type, *at)"), level.index("Peek(base + *at + kLevelAt, level)"))
        place = function(self.main, "std::pair<std::string, std::string> PlaceText()")
        self.assertLess(place.index('IsType(cell, "TESObjectCELL@@", cellType)'), place.index("NameText("))
        self.assertLess(place.index('IsType(world, "TESWorldSpace@@", worldType)'), place.rindex("NameText("))
        name = function(self.main, "std::string NameText(")
        self.assertLess(name.index("CheckSubobject(a_form, a_type, *at)"), name.index("Peek(a_form + *at + kFullNameAt"))
        strings = function(self.main, "bool CheckStrings()")
        self.assertIn("SameText(read, kMenuName)", strings)

    def test_the_only_calls_into_the_game_are_the_checked_ones(self):
        self.assertEqual(self.page.count("reinterpret_cast<GetActorValue_t>"), 1)
        self.assertEqual(self.page.count("reinterpret_cast<LookupById_t>(Address(kLookupById))"), 1)
        self.assertEqual(self.main.count("FormById("), 6)                    # the definition, AcceptById, FindForms' two
        # and the kit's quest list's two (FAL-431, test_pipboy_kit's test_nothing_new_is_called_in_the_game)
        self.assertNotIn("REL::Relocation", self.page)
        self.assertNotIn("REL::ID", self.page)
        value = function(self.main, "std::string ActorValueText(")
        self.assertLess(value.index("vtable != g_forms.ownerVtable"), value.index("reinterpret_cast<GetActorValue_t>"))
        check = function(self.main, "bool CheckActorValues()")
        self.assertIn('BaseOffset(type, "ActorValueOwner@@")', check)
        self.assertIn("CheckSubobject(player, type, *at)", check)
        self.assertLess(check.index("if (target0 != destructor || !InImage(slots[1], 1)) {"),
                        check.index("g_forms.getActorValue = slots[1];"))
        hierarchy = function(self.main, "std::optional<std::uint32_t> BaseOffset(")
        self.assertIn("if (pdisp != -1 || mdisp < 0) {", hierarchy)
        self.assertIn("return matches == 1 ? found : std::nullopt;", hierarchy)
        subobject = function(self.main, "bool CheckSubobject(")
        self.assertIn("sub.descriptor == a_type.descriptor && sub.offset == a_offset", subobject)
        thunk = function(self.main, "std::uintptr_t ThunkTarget(")
        self.assertIn("if (code[at] != 0xE9) {", thunk)

    def test_reads_on_the_main_thread_writes_on_the_menus(self):
        callers = {m.start() for m in re.finditer(r"PageCollect\(\);", self.main)}
        self.assertEqual(len(callers), 2)
        self.assertIn("if (g_stage == 4 && !open) {\n\t\t\tPageCollect();", function(self.main, "void Toggle("))
        self.assertIn("if (g_stage == 4) {\n\t\t\tPageCollect();", function(self.main, "void SendUpdate()"))
        process = function(self.main, "RE::UI_MESSAGE_RESULT MenuProcessMessage(")
        self.assertIn("PageWrite(a_self, 0);", process)
        self.assertIn("PageWrite(a_self, n);", process)
        self.assertNotIn("PageCollect", process)
        for handler in ("class TabHandler", "class CloseHandler"):
            body = self.main[self.main.index(handler):self.main.index("};", self.main.index(handler))]
            self.assertNotIn("AddMessage", body)
            self.assertNotIn("g_task", body)
        write = function(self.main, "void PageWrite(")
        self.assertLess(write.index("RootOf(a_menu)"), write.index("GetVariable("))
        self.assertIn("std::scoped_lock lock(g_pageLock);", write)
        listen = function(self.main, "void PageListen(")
        self.assertLess(listen.index("RootOf(a_menu)"), listen.index("GetVariable("))
        self.assertIn('args[0] = "click";', listen)
        close = function(self.main, "void Close(std::uint32_t a_n, const char* a_by = ")
        self.assertIn("if (open) {\n\t\t\tqueue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kHide);", close)
        key = function(self.main, "std::uint32_t KeyThread(")
        self.assertIn("if (g_closeNow.exchange(false)) {", key)
        self.assertIn("g_task->AddTask([n]() { Close(n); });", key)

    def test_the_menu_stack_read_is_gone(self):
        self.assertNotIn("kMenuStackAt", self.main)
        self.assertNotIn("ReadMenuStack", self.main)
        self.assertIn('const auto menus = a_main ? ReadMenus() : "-";', self.main)
        self.assertIn('Snapshot("key", true);', self.main)
        self.assertIn('Snapshot(open ? "main_after_open" : "main_after_close", true);', self.main)
        for tag in ('Snapshot("show");', 'Snapshot("open");', 'Snapshot("hide");'):
            self.assertIn(tag, self.main)
        menus = function(self.main, "std::string ReadMenus()")
        self.assertIn("ui->IsMenuRegistered(name)", menus)
        self.assertIn("ui->IsMenuOpen(name)", menus)
        self.assertIn('"step=menu_names registered={} not_registered={}"', menus)

    def test_ini_readme_and_flags(self):
        self.assertIn("\nPageFlagSets=0x19\n", self.ini)
        self.assertIn("; 4 = stage (d): the STAT page", self.ini)
        self.assertIn('ReadFlagSets(ini, L"PageFlagSets", L"0x19");', self.main)
        self.assertIn("if (g_stage < 1 || g_stage > 5) {", self.main)                 # (e), FAL-301
        self.assertIn("### PASS at (d), `Stage=4`", self.readme)
        self.assertIn("## Stage (d): the STAT page (FAL-272)", self.readme)
        for line in ("refuse step=page_ids", "refuse step=page what=strings", "what=get_actor_value",
                     "step=page_unknown what=", "step=page ... fields=0/8"):
            self.assertIn(line, self.readme, line)
        self.assertIn(f"{16 + 16 + 2} `step=id` lines", self.readme)

    def test_the_time_only_at_a_checked_value_offset(self):
        # libxse's TESGlobal::value at +0x40 read GameDaysPassed -3.5924 at a156037c (PC run, 11 Nov): no unchecked offset;
        # FAL-384: kGlobalValueAt (+0x48, the game's own GetValue) is only the first slot ChooseGlobalSlot tries, checked
        read = function(self.main, "bool ReadTime(")
        for check in ("!a_at", "a_hour < 0.0f || a_hour >= 24.0f || a_days <= 0.0f || a_days >= kMaxDays",
                      "std::fmod(a_days, 1.0f) * 24.0f - a_hour", "std::min(apart, 24.0f - apart) * 60.0f <= kGlobalMinutes"):
            self.assertIn(check, read, check)
        find = function(self.main, "void FindGlobalValue()")
        self.assertLess(find.index("GlobalBytes(g_forms.gameHour), GlobalBytes(g_forms.gameDaysPassed)"),
                        find.index("ChooseGlobalSlot("))
        self.assertIn("return ReadTime(a_at, hour, days);", find)
        self.assertIn("if (!ReadTime(g_forms.globalValueAt, hour, days)) {", function(self.main, "std::string TimeText()"))
        collect = function(self.main, "void PageCollect()")
        self.assertIn("const bool           haveDays = ReadTime(g_forms.globalValueAt, hour, days);", collect)
        self.assertLess(collect.index("PageScan();"), collect.index("FindGlobalValue();"))
        self.assertIn("constexpr std::size_t   kGlobalBytesAt = 0x28;", self.main)
        self.assertIn("constexpr std::size_t   kGlobalBytes = kGlobalObjectBytes - kGlobalBytesAt;", self.main)
        self.assertIn("`step=page_globals from=0x28", self.readme)

    def test_owner_card(self):
        owner = self.card[:self.card.index("## For the PC helper")]
        steps = owner[owner.index("## The eight steps"):owner.index("**Report:**")]
        rows = [r for r in steps.splitlines() if re.match(r"\| \d \|", r)]
        self.assertEqual([int(r.split("|")[1]) for r in rows], list(range(1, 9)))
        for word in ("console", "log", "save"):
            self.assertNotIn(word, steps.lower(), word)
        for seen in ("NEXT TAB", "CLOSE", "F10", "TAB 2 OF 2: DATA", "TAB 1 OF 2: STATUS", "NOT INSTALLED"):
            self.assertIn(seen, steps, seen)
        helper = self.card[self.card.index("## For the PC helper"):]
        self.assertIn("--page", helper)
        self.assertIn("-replace '^Stage=0','Stage=4'", helper)
        self.assertIn("tests.test_pipboy_stat_page", helper)


if __name__ == "__main__":
    unittest.main()
