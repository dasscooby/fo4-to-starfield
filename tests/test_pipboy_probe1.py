"""FO4SFPipboyMenu's probe 1 (FAL-739): source-level checks that Probe stays off by default and that, off, no probe
code runs and no probe line is logged; that its keys are checked and refused; that every engine call goes by an id
checked like the others; that every object is checked before use; and that the source carries ids and call shapes
only (the native build and the game run are the PC's)."""
import pathlib
import re
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1] / "sfse" / "FO4SFPipboyMenu"

PROBE_IDS = {"43207", "43209", "43211", "44195", "140022", "130595", "909463", "47401"}


def function(src, head):
    """The body of the function whose definition starts with head, up to its closing brace at one tab."""
    start = src.index("\t" + head)
    end = re.search(r"\n\t\}\n", src[start:]).end()
    return src[start:start + end]


class PipboyProbe1Test(unittest.TestCase):
    def setUp(self):
        self.src = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
        self.ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="ascii")
        self.readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
        self.section = self.src[re.search(r"// -+ FAL-739: probe 1", self.src).start():
                                re.search(r"// -+ stage e: the kit", self.src).start()]

    def test_ini_ships_the_probe_off(self):
        for line in ("Probe=0", "ProbeMovie=", "ProbeModelForm=", "ProbeWidth=1280", "ProbeHeight=720", "Stage=0"):
            self.assertIn("\n" + line + "\n", self.ini, line)
        self.assertIn("bool                                     g_probe = false;", self.src)
        self.assertIn('ReadNumber(a_ini, L"ProbeWidth", 1280)', self.src)
        self.assertIn('ReadNumber(a_ini, L"ProbeHeight", 720)', self.src)

    def test_probe_off_reads_runs_and_logs_nothing_new(self):
        read = function(self.src, "bool ReadProbe(")
        # the first thing read: Probe=0 returns before any other key is read or any line is logged
        first = read.index('if (ReadNumber(a_ini, L"Probe", 0) == 0) {\n\t\t\treturn true;\n\t\t}')
        self.assertLess(first, read.index("Refuse("))
        self.assertLess(first, read.index("ReadText("))
        self.assertLess(read.index("g_probe = true;"), read.index("REX::INFO("))
        self.assertEqual(self.src.count("g_probe = true;"), 1)
        # every probe function is called only behind g_probe
        calls = {
            "ProbeOpen(a_self);": "RE::UI_MESSAGE_RESULT MenuProcessMessage(",
            "ProbePoll(a_self);": "RE::UI_MESSAGE_RESULT MenuProcessMessage(",
            "ProbeHide();": "RE::UI_MESSAGE_RESULT MenuProcessMessage(",
            "ProbeDestroy(a_self);": "void* MenuDestroy(",
        }
        for call, where in calls.items():
            body = function(self.src, where)
            self.assertEqual(self.src.count(call), 1, call)
            self.assertIn(call, body)
            self.assertLess(body.index("if (g_probe) {"), body.index(call), call)
        message = function(self.src, "RE::UI_MESSAGE_RESULT MenuProcessMessage(")
        gate = message[message.index("if (g_probe) {"):message.index("if (g_stage >= 3) {   // stages c, d and e")]
        for call in ("ProbeOpen(", "ProbePoll(", "ProbeHide("):
            self.assertIn(call, gate)
        load = self.src[self.src.index("SFSE_PLUGIN_LOAD"):]
        self.assertIn('if (g_probe && !CheckProbeIds(dir / "versionlib-1-16-244-0.bin")) {', load)
        self.assertLess(load.index("ReadProbe(ini)"), load.index("CheckEverything(dir)"))
        self.assertLess(load.index("CheckEverything(dir)"), load.index("CheckProbeIds("))
        # the movie's name and the extra updates, likewise
        self.assertIn("if (g_probe && g_probeLoading.load()) {\n\t\t\treturn g_probeMovie.c_str();\n\t\t}\n\t\treturn kMenuName;",
                      function(self.src, "const char* MenuGetName("))
        movie = function(self.src, "bool MenuLoadMovie(")
        self.assertIn("if (g_probe) {   // FAL-739: the staged movie instead of ours, for this call only\n"
                      "\t\t\tREX::INFO(\"step=probe_movie", movie)
        self.assertEqual(movie.count("g_probeLoading = true;"), 1)
        self.assertLess(movie.index("if (g_probe) {"), movie.index("g_probeLoading = true;"))
        thread = function(self.src, "std::uint32_t KeyThread(")
        self.assertIn("if (g_probe && g_open && ++ticks % 17 == 0) {", thread)   # g_probe first: ticks untouched when off
        # no probe line is logged outside the probe's own functions and those gates
        outside = self.src.replace(self.section, "")
        for name in ("bool ReadProbe(", "bool CheckProbeIds("):
            outside = outside.replace(function(self.src, name), "")
        self.assertEqual(re.findall(r'step=(?:load_)?probe\w*', outside), ["step=probe_movie"])
        self.assertEqual(re.findall(r'Refuse\("probe\w*"', outside), [])
        # the shared id list is as it was: the probe's ids are checked on their own
        self.assertIn("kDataHandlerSingleton = kIdCountC,\n\t\tkLookupById,\n\t\tkIdCount", self.src)
        self.assertIn("std::size_t IdCount() { return g_stage >= 4 ? kIdCount : g_stage == 3 ? kIdCountC : kIdCountB; }",
                      self.src)

    def test_probe_keys_are_checked_and_refused(self):
        read = function(self.src, "bool ReadProbe(")
        for reason in ("probe_stage", "probe_movie", "probe_model_form", "probe_size"):
            self.assertIn(f'Refuse("ini", std::format("reason={reason}', read, reason)
            self.assertIn(reason, self.readme, reason)
        self.assertIn('if (!g_keepAlive) {', read)                                 # the menu object needs its extra reference
        self.assertIn('Refuse("ini", "reason=probe_keep_alive (Probe=1 needs KeepAlive=1)")', read)
        self.assertNotIn("needs KeepAlive=0", self.src)
        self.assertIn("probe_keep_alive", self.readme)

    def test_keep_alive_zero_is_refused_at_every_stage(self):
        load = self.src[self.src.index("SFSE_PLUGIN_LOAD"):]
        refusal = ('if (!g_keepAlive) {\n\t\tRefuse("ini", "reason=keep_alive (KeepAlive=0 frees the menu at its create; '
                   'set KeepAlive=1)");\n\t\treturn true;\n\t}')
        self.assertIn(refusal, load)
        # not behind a stage or the probe, and before any check of the game or any registration
        at = load.index(refusal)
        self.assertEqual(load[:at].rstrip().splitlines()[-1].startswith("\t//"), True)
        for later in ("CheckEverything(dir)", "RegisterListener(", "World::Configure("):
            self.assertLess(at, load.index(later), later)
        # the shipped default keeps the extra reference, and Create adds it as before
        self.assertIn("\nKeepAlive=1\n", self.ini)
        self.assertIn('g_keepAlive = ReadNumber(ini, L"KeepAlive", 1) != 0;', load)
        self.assertIn("if (g_keepAlive && ctorRefs == 1) {\n\t\t\tREX::W32::InterlockedIncrement(refs);", self.src)
        self.assertIn("refuse step=ini reason=keep_alive", self.readme)
        self.assertIn("refuse step=ini reason=keep_alive", self.ini)
        self.assertNotIn("try `KeepAlive=1` if it was 0", self.readme)

    def test_no_teardown_at_close_and_the_three_outcomes_are_logged(self):
        hide = function(self.src, "void ProbeHide(")
        self.assertNotIn("ProbeAddress(", hide)                                    # a close calls nothing in the game
        self.assertNotIn("_aligned_free", hide)
        self.assertEqual(self.src.count("ProbeAddress(kProbeRendererDtor)"), 1)   # only from ProbeDestroy
        self.assertIn("ProbeAddress(kProbeRendererDtor)", function(self.src, "void ProbeDestroy("))
        open_ = function(self.src, "void ProbeOpen(")
        self.assertIn('"step=probe_open n={} result=kept renderer={} scene={} bound={} menu_flags={}"', open_)   # (b)
        self.assertIn('"what=open n={} reason=other_menu menu={}"', open_)                                        # (c)
        self.assertIn('REX::INFO("step=probe_destroy result=1");', function(self.src, "void ProbeDestroy("))     # (a)
        self.assertIn('"step=create n={} menu={}', self.src)
        self.assertIn('"step=destroy menu={} flags={}"', self.src)
        for text in ("**(a)**", "**(b)**", "**(c)**", "result=kept", "reason=other_menu", "step=probe_destroy result=1"):
            self.assertIn(text, self.readme, text)

    def test_probe_movie_form_and_size_are_checked(self):
        read = function(self.src, "bool ReadProbe(")
        self.assertIn("if (g_stage != 2) {", read)
        self.assertIn('g_probeMovie.starts_with("FO4SF_")', read)                 # never a game menu's movie
        self.assertIn("SameText(g_probeMovie, kMenuName)", read)
        self.assertIn("std::strtoul(formText.c_str(), &end, 16)", read)
        self.assertIn("form == 0 || form > 0x00FFFFFF", read)
        self.assertIn("g_probeWidth < 16 || g_probeWidth > kProbeMaxSide || g_probeHeight < 16 || g_probeHeight > kProbeMaxSide",
                      read)

    def test_every_call_is_by_a_checked_id(self):
        table = self.section[self.section.index("kProbeIds{ {"):self.section.index("} };")]
        self.assertEqual(set(re.findall(r'\{ (\d+), "', table)), PROBE_IDS)
        check = function(self.src, "bool CheckProbeIds(")
        for reason in ("beyond_count", "short_file", "missing", "outside_image", "library_mismatch"):
            self.assertIn(f"reason={reason}", check, reason)
        self.assertIn("const auto viaLibrary = REL::ID(id.id).offset();", check)
        self.assertIn("for (std::size_t i = 0; i < kProbeIdCount; ++i) {", check)
        # every function pointer the probe calls comes from ProbeAddress(<an id of the table>)
        casts = re.findall(r"reinterpret_cast<(Probe\w+_t)>\((\w+)\((\w+)\)\)", self.section)
        self.assertEqual(sorted(c[0] for c in casts),
                         ["ProbeBind_t", "ProbeLookupById_t", "ProbeModelRequest_t", "ProbeRendererCtor_t",
                          "ProbeRendererDtor_t", "ProbeScenePush_t", "ProbeSceneTexture_t"])
        for _, getter, name in casts:
            self.assertEqual(getter, "ProbeAddress")
            self.assertIn(name + ",", self.section[self.section.index("enum : std::size_t"):self.section.index("kProbeIdCount")])
        for id_ in PROBE_IDS:
            self.assertIn(id_, self.readme, id_)

    def test_source_carries_ids_and_shapes_only(self):
        # no address of the game in the probe's code, the ini or the README: the ids alone
        added = self.section + function(self.src, "bool ReadProbe(") + function(self.src, "bool CheckProbeIds(")
        for text in (added, self.ini, self.readme[self.readme.index("## Probe 1"):self.readme.index("## Build (PC)")]):
            self.assertEqual(re.findall(r"0x14[0-9a-fA-F]{7}\b", text), [])
        self.assertNotIn("Rva = 0x", self.section)

    def test_objects_are_checked_before_use(self):
        open_ = function(self.src, "void ProbeOpen(")
        order = ['IsType(cell, "TESObjectCELL@@", cellType)', 'IsType(form, "TESObjectBOOK@@", formType)',
                 "ProbeAddress(kProbeRendererCtor)", 'IsType(renderer, "UICellRenderer_InventoryItem@@", rendererType)',
                 "SameText(sceneText, kMenuName)", "ProbeAddress(kProbeScenePush)", "ProbeAddress(kProbeSceneTexture)",
                 "ProbeAddress(kProbeModelRequest)"]
        at = [open_.index(step) for step in order]
        self.assertEqual(at, sorted(at))
        self.assertIn("if (!movie) {\n\t\t\tProbeRefuse(\"what=movie reason=not_loaded\");", open_)
        self.assertLess(open_.index("if (!movie) {"), at[0])
        # once per menu object; a second menu object while the first renderer lives is refused
        self.assertIn("if (s.renderer && s.menu == a_menu) {", open_)
        self.assertIn("reason=other_menu", open_)
        refuse = function(self.src, "bool ProbeRefuse(")
        self.assertIn("g_probeState.off = true;", refuse)
        for name in ("void ProbeOpen(", "void ProbePoll("):
            self.assertIn("s.off", function(self.src, name)[:900], name)

    def test_walk_is_read_only_and_bind_takes_display_geometry_only(self):
        walk = function(self.src, "std::vector<ProbeNode> ProbeWalk(")
        self.assertIn('!TypeOf(node, type) || type.offset != 0 || !ProbeIsA(type, "NiAVObject@@")', walk)
        self.assertIn('ProbeIsA(type, "BSGeometry@@")', walk)
        self.assertIn('!ProbeIsA(type, "NiNode@@")', walk)
        self.assertIn("found.size() < kProbeMaxNodes", walk)
        self.assertNotIn("reinterpret_cast<Probe", walk)                          # no call into the game
        poll = function(self.src, "void ProbePoll(")
        self.assertEqual(poll.count("ProbeAddress("), 1)
        self.assertIn("if (s.bound || !usable || !displays) {\n\t\t\treturn;\n\t\t}\n\t\ts.bound = true;", poll)
        self.assertIn("if (!node.geometry || !node.name.starts_with(kProbeShapePrefix)) {\n\t\t\t\tcontinue;", poll)
        self.assertLess(poll.index("s.bound = true;"), poll.index("ProbeAddress(kProbeBind)"))
        self.assertIn('constexpr std::string_view kProbeShapePrefix = "Display";', self.src)
        self.assertIn("const bool  usable = texture && (phase == 1 || phase == 2);", poll)

    def test_renderer_is_destroyed_before_the_menu(self):
        destroy = function(self.src, "void* MenuDestroy(")
        self.assertLess(destroy.index("ProbeDestroy(a_self);"), destroy.index("g_engineDtor(a_self, a_flags & ~1u);"))
        probe = function(self.src, "void ProbeDestroy(")
        self.assertLess(probe.index("ProbeAddress(kProbeRendererDtor)"), probe.index("_aligned_free("))
        self.assertIn("if (!s.renderer || s.menu != a_menu) {\n\t\t\treturn;", probe)

    def test_no_shape_outside_the_scene_is_touched(self):
        # stage B is not in this probe: no restore exists, so nothing outside the menu scene is bound
        for word in ("PlayerCharacter", "kPlayerSingleton", "1stPerson", "Get3D", "140179", "147317"):
            self.assertNotIn(word, self.section, word)
        self.assertEqual(self.section.count("ProbeAddress(kProbeBind)"), 1)
        self.assertIn("**Left out of this probe:**", self.readme)
        self.assertIn("Shapes outside the menu scene", self.readme)

    def test_one_line_per_step_and_readme_names_them(self):
        steps = set(re.findall(r"step=(probe_\w+)", self.section))
        self.assertEqual(steps, {"probe_open", "probe_inputs", "probe_renderer", "probe_scene", "probe_scene_push",
                                 "probe_texture", "probe_model", "probe_state", "probe_bind", "probe_hide",
                                 "probe_destroy"})
        self.assertIn("## Probe 1: a menu movie on a model (FAL-739)", self.readme)
        for step in sorted(steps | {"probe_movie", "probe_id"}):
            self.assertIn("step=" + step, self.readme, step)
        self.assertIn("refuse step=probe what=", self.readme)


if __name__ == "__main__":
    unittest.main()
