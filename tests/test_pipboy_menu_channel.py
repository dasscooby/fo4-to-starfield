"""FO4SFPipboyMenu's stage (c), the data channel (FAL-216), as text: the PR #704 plugin keeps every check and refusal
line of stages (a) and (b) and their 16 ids, stage (c) checks its 13 more ids (and only stages (c) and (d) do; stage
(d)'s one more id is tests/test_pipboy_stat_page.py's), the Scaleform Value functions against SFSE's own addresses,
the RTTI ids by name, and every object before it is used; the instance names the plugin looks for are the ones
make_probe_swf.py --channel writes; the ini, README and session card agree. No compiler here: the PC build is the
compile check."""
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_probe_swf as swf  # noqa: E402

IDS_B = [("UI.Singleton", 937580), ("UI.RegisterMenu", 130463), ("UI.IsMenuOpen", 130475),
         ("UIMessageQueue.Singleton", 937897), ("UIMessageQueue.AddMessage", 130659),
         ("BSStringPool.GetEntry", 1186742), ("BSStringPool.Entry.Release", 139340), ("IMenu.vtable.primary", 475515),
         ("IMenu.vtable.BSInputEventUser", 475517), ("IMenu.vtable.BSTEventSink", 475519), ("IMenu.RTTI", 844868),
         ("IMenu.ctor", 130615), ("IMenu.scalar_deleting_dtor", 130616), ("IMenu.LoadMovie", 130618),
         ("IMenu.ProcessMessage", 130624), ("IMenu.IsMovieLoaded", 130619)]
IDS_C = [("Main.Singleton", 883591), ("PlayerCharacter.Singleton", 922868), ("ControlMap.Singleton", 938003),
         ("Main.RTTI", 859948), ("PlayerCharacter.RTTI", 860819), ("ControlMap.RTTI", 867481),
         ("GFx.MovieImpl.RTTI", 841612), ("GFx.AS3.MovieRoot.RTTI", 842209), ("GFx.Value.ObjectAddRef", 169745),
         ("GFx.Value.ObjectRelease", 169746), ("GFx.Value.GetMember", 169748), ("GFx.Value.SetMember", 169749),
         ("GFx.Value.Invoke", 169750)]
IDS_D = [("TESDataHandler.Singleton", 937572)]
SFSE_RVAS = [("kValueAddRef", "0x3352400"), ("kValueRelease", "0x33524A0"), ("kValueGetMember", "0x33528A0"),
             ("kValueSetMember", "0x3352C90"), ("kValueInvoke", "0x33530B0")]


def function(text, signature):
    """The body of the function whose definition starts with `signature` (to its closing brace at one tab)."""
    start = text.index(signature)
    end = text.index("\n\t}\n", start)
    return text[start:end]


class ChannelPluginTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    card = (ROOT / "docs" / "spikes" / "pipboy-channel-bridge-session.md").read_text(encoding="utf-8")

    def test_the_ids_in_order_and_stages_a_and_b_read_only_theirs(self):
        found = re.findall(r'\{ "([A-Za-z0-9_.]+)", (\d+), "', self.main)
        self.assertEqual([(n, int(i)) for n, i in found], IDS_B + IDS_C + IDS_D)
        enum = self.main[self.main.index("kUISingleton,"):self.main.index("kIdCount\n")]
        self.assertIn("kIsMovieLoaded,\n\t\tkIdCountB,", enum)
        self.assertIn("kMainSingleton = kIdCountB,", enum)
        self.assertIn("kValueInvoke,\n\t\tkIdCountC,", enum)
        self.assertIn("std::size_t IdCount() { return g_stage == 4 ? kIdCount : g_stage == 3 ? kIdCountC : kIdCountB; }",
                      self.main)
        library = function(self.main, "bool ReadAddressLibrary(")
        self.assertEqual(library.count("for (std::size_t i = 0; i < IdCount(); ++i) {"), 2)
        self.assertNotIn("i < kIdCount;", library)
        self.assertIn("(g_stage >= 3 && !CheckChannelIds())", self.main)
        for name, _ in IDS_C:
            self.assertIn(name.split(".")[-1] if name.startswith("GFx.Value") else name.split(".")[0], self.readme)

    def test_value_functions_equal_sfses_addresses_and_rtti_ids_name_their_types(self):
        for constant, rva in SFSE_RVAS:
            self.assertIn(f"{{ {constant}, {rva} }}", self.main)
            self.assertIn(f"`{rva}`", self.readme)
        for constant, tail in (("kMainRtti", "Main@@"), ("kPlayerRtti", "PlayerCharacter@@"),
                               ("kControlMapRtti", "ControlMap@@"), ("kMovieImplRtti", "MovieImpl@GFx@Scaleform@@"),
                               ("kMovieRootRtti", "MovieRoot@AS3@GFx@Scaleform@@")):
            self.assertIn(f'{{ {constant}, "{tail}"sv }}', self.main)
        check = function(self.main, "bool CheckChannelIds()")
        self.assertIn("if (g_rva[id] != rva) {", check)
        self.assertIn("if (!NameIs(name, tail)) {", check)
        self.assertIn('a_name.starts_with(".?AV") || a_name.starts_with(".?AU")', self.main)

    def test_nothing_of_the_movie_is_called_before_its_root_is_checked(self):
        root = function(self.main, "RE::Scaleform::GFx::ASMovieRootBase* RootOf(")
        self.assertLess(root.index("rootType.descriptor != Address(kMovieRootRtti)"),
                        root.index("g_checkedMovie = MovieOf(a_menu);"))
        self.assertIn("!InImage(slot[kCreateFunctionSlot], 1) || !InImage(slot[kGetVariableSlot], 1)", root)
        self.assertIn("g_channelOff = true;", root)
        self.assertIn("constexpr std::size_t   kCreateFunctionSlot = 0x30;", self.main)
        self.assertIn("constexpr std::size_t   kGetVariableSlot = 0x32;", self.main)
        for name in ("void ChannelListen(", "void ChannelWrite("):
            body = function(self.main, name)
            first_call = min(body.index(c) for c in ("GetVariable(", "CreateFunction(", "Invoke(") if c in body)
            self.assertLess(body.index("RootOf(a_menu)"), first_call, name)
            self.assertIn("if (!root", body)
        # the singletons: type by RTTI at offset 0 before the first read; reads of libxse-only layouts are guarded
        singleton = function(self.main, "bool CheckSingleton(")
        self.assertIn("type.descriptor != Address(a_rtti) || type.offset != 0", singleton)
        for reader, singleton_id in (("std::string ReadPaused()", "kMainSingleton"),
                                     ("std::string ReadContexts()", "kControlMapSingleton"),
                                     ("bool ReadPosition(", "kPlayerSingleton")):
            body = function(self.main, reader)
            self.assertLess(body.index("CheckSingleton("), body.index(f"Singleton({singleton_id})"), reader)
        self.assertIn("} __except (1 /* EXCEPTION_EXECUTE_HANDLER */) {", self.main)

    def test_the_names_are_the_movies(self):
        self.assertIn(f'constexpr auto          kFieldName = "{swf.FIELD_NAME}";', self.main)
        self.assertIn(f'constexpr auto          kButtonName = "{swf.BUTTON_NAME}";', self.main)
        self.assertIn('a_root.Invoke("getChildByName", &a_out, &name, 1)', self.main)
        self.assertIn('added = button.Invoke("addEventListener", nullptr, args.data(), args.size());', self.main)
        self.assertIn('args[0] = "click";', self.main)
        self.assertIn('field.SetMember("text", RE::Scaleform::GFx::Value(text.c_str()))', self.main)
        self.assertIn('field.GetMember("text", &back)', self.main)
        # the text the plugin writes uses only characters the movie's embedded font has
        for text in ("X {:.1f} Y {:.1f} Z {:.1f} CLICKS {}", "NO POSITION CLICKS {}"):
            self.assertIn(text, self.main)
            sample = text.replace("{:.1f}", "-1234.5").replace("{}", "12")
            self.assertTrue(set(sample) <= set(swf.FONT), sample)

    def test_every_check_and_refusal_line_of_704_is_kept(self):
        for step in ("address_library", "ctor", "id", "image", "ini", "key_thread", "listen", "register", "rtti",
                     "slots", "version"):
            self.assertIn(f'Refuse("{step}"', self.main, step)
        for line in ('REX::ERROR("refuse step=create n={} reason=out_of_memory", n);',
                     'REX::ERROR("refuse step=toggle n={} reason=no_ui_or_queue", a_n);',
                     '!CheckVtable(kVtblPrimary, 0x00, "primary") || '
                     '!CheckVtable(kVtblInput, 0x10, "BSInputEventUser") ||',
                     '!CheckVtable(kVtblSink, 0x50, "BSTEventSink") || !CheckSlots() || !CheckCtor() ||',
                     "if (g_rva[kLoadMovie] != kLoadMovieRva) {", "if (slot[0x03] != slot[0x04]) {",
                     "const auto viaLibrary = REL::ID(kIds[i].id).offset();"):
            self.assertIn(line, self.main, line)
        self.assertIn('Refuse("channel_ids"', self.main)
        self.assertIn('Refuse("channel"', self.main)
        self.assertIn('Refuse("object"', self.main)
        self.assertIn("if (g_stage >= 3 && (g_snapshotKey > 0xFE || g_snapshotKey == g_key)) {", self.main)

    def test_ini_readme_and_card_agree(self):
        for line in ("Stage=0", "FlagSets=0x0,0x8,0x9", "SnapshotKey=0x7A", "Flags=0", "KeepAlive=1"):
            self.assertIn("\n" + line + "\n", self.ini)
        self.assertIn('L"FlagSets", L"0x0,0x8,0x9"', self.main)
        self.assertIn('ReadNumber(ini, L"SnapshotKey", 0x7A)', self.main)
        self.assertIn("### PASS at (c), `Stage=3`", self.readme)
        for line in ("refuse step=channel_ids", "refuse step=object", "refuse step=channel what=movie_root",
                     "refuse step=ini snapshot_key="):
            self.assertIn(line, self.readme, line)
        self.assertIn("**Which steps need a save:** B0-2 makes one save (`focc_b0_a`) and loads it; P1 makes two saves",
                      self.card)
        self.assertIn("Test C makes no save", self.card)
        self.assertIn("make_pipboy_probe.py stage $exp --channel", self.card)
        self.assertIn("-replace '^Stage=0','Stage=3'", self.card)
        self.assertIn("-replace '^bEnabled=0','bEnabled=1'", self.card)
        self.assertLess(self.card.index('Copy-Item "$logs\\focc.0.log" $out'),
                        self.card.index("Then relaunch through the loader"))
        self.assertIn(f"{len(IDS_B) + len(IDS_C)} `step=id` lines", self.card)


if __name__ == "__main__":
    unittest.main()
