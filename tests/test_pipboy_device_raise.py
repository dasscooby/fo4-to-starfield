"""FO4SFPipboyMenu's device raise (FAL-714, step 3b): source-level checks that Device stays off by default, its keys are
checked and refused, the idles are found by editor id only, the lower is sent from the hide handling and Key (F10)
resets the root to the full screen (the native build and the game run are the PC's)."""
import pathlib
import re
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1] / "sfse" / "FO4SFPipboyMenu"


def function(src, head):
    """The body of the function whose definition starts with head, up to the next one at the same indent."""
    start = src.index("\t" + head)
    end = re.search(r"\n\t\}\n", src[start:]).end()
    return src[start:start + end]


class PipboyDeviceRaiseTest(unittest.TestCase):
    def setUp(self):
        self.src = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
        self.ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="ascii")
        self.readme = (PLUGIN / "README.md").read_text(encoding="utf-8")

    def test_ini_ships_the_card_defaults_and_device_off(self):
        for line in ("Device=0", "DeviceKey=0x76","DeviceRaiseIdle=Human_1stPersonRoot_DataSlateOpen",
                     "DeviceLowerIdle=Human_1stPersonRoot_DataSlateClose", "DeviceRaiseMs=900", "DeviceLowerMs=700",
                     "DeviceBox=0.078,0.271,0.309", "Stage=0"):
            self.assertIn("\n" + line + "\n", self.ini, line)
        for key, default in (("Device", "0"), ("DeviceKey", "0x76"),("DeviceRaiseMs", "900"), ("DeviceLowerMs", "700")):
            self.assertIn(f'ReadNumber(a_ini, L"{key}", {default})', self.src, key)
        self.assertIn("std::array<double, 3>                    g_deviceBox{ 0.078, 0.271, 0.309 };", self.src)
        self.assertIn("bool                                     g_device = false;", self.src)

    def test_device_zero_runs_and_logs_nothing_new(self):
        read = function(self.src, "bool ReadDevice(")
        # the first thing read: Device=0 returns before any other key is read or any line is logged
        first = read.index('if (ReadNumber(a_ini, L"Device", 0) == 0) {\n\t\t\treturn true;\n\t\t}')
        self.assertLess(first, read.index("Refuse("))
        self.assertLess(first, read.index("REX::INFO("))
        self.assertLess(read.index("g_device = true;"), read.index("REX::INFO("))
        self.assertEqual(self.src.count("g_device = true;"), 1)
        # every device path is behind g_device: load, the key thread, show and hide
        load = self.src[self.src.index("SFSE_PLUGIN_LOAD"):]
        self.assertIn("if (g_device && !CheckDeviceId(dir / \"versionlib-1-16-244-0.bin\")) {", load)
        thread = function(self.src, "std::uint32_t KeyThread(")
        self.assertIn("if (g_device) {   // FAL-714", thread)
        self.assertEqual(thread.count("DeviceRaise("), 2)   # the first try and the tick's retry (FAL-725)
        message = function(self.src, "RE::UI_MESSAGE_RESULT MenuProcessMessage(")
        self.assertEqual(message.count("if (g_device) {"), 2)
        for call in ("DevicePlace(", "DeviceLower(", "g_deviceShown = "):
            for at in [m.start() for m in re.finditer(re.escape(call), message)]:
                self.assertGreater(at, message.index("if (g_device) {"), call)
        # the shared id list and its count are unchanged: the device's id is checked on its own
        self.assertIn("kDataHandlerSingleton = kIdCountC,\n\t\tkLookupById,\n\t\tkIdCount", self.src)
        self.assertIn("std::size_t IdCount() { return g_stage >= 4 ? kIdCount : g_stage == 3 ? kIdCountC : kIdCountB; }",
                      self.src)
        self.assertNotIn("47403, \"", self.src[self.src.index("kIds{ {"):self.src.index("} };", self.src.index("kIds{ {"))])

    def test_device_key_collisions_are_refused(self):
        read = function(self.src, "bool ReadDevice(")
        self.assertIn("g_deviceKey == 0 || g_deviceKey > 0xFE || g_deviceKey == g_key || g_deviceKey == g_snapshotKey ||\n"
                      "\t\t\tg_deviceKey == worldKey || kitKey", read)
        self.assertIn('ReadNumber(a_ini, L"WorldKey", 0x77)', read)
        self.assertIn("for (const auto& binding : g_kitKeys) {", read)
        self.assertIn("kitKey = kitKey || binding.vk[k] == g_deviceKey;", read)
        for reason in ("device_stage", "device_key", "device_idle", "device_ms", "device_box"):
            self.assertIn(f'Refuse("ini", std::format("reason={reason}', read, reason)
            self.assertIn(reason, self.readme, reason)
        self.assertIn("if (g_stage != 5) {", read)
        # the shipped DeviceKey is none of the shipped keys
        shipped = dict(re.findall(r"^(\w+)=(\S*)$", self.ini.split("\n[Kit]\n")[0], re.M))
        device = int(shipped["DeviceKey"], 0)
        others = {int(shipped[k], 0) for k in ("Key", "SnapshotKey", "WorldKey")}
        for key, value in shipped.items():
            if key.startswith("Kit"):
                others |= {int(v, 0) for v in value.split(",")}
        self.assertNotIn(device, others)
        # the kit's keys are read before the device's, which compares against them
        load = self.src[self.src.index("SFSE_PLUGIN_LOAD"):]
        self.assertLess(load.index("ReadKitKeys(ini)"), load.index("ReadDevice(ini)"))
        self.assertLess(load.index("ReadDevice(ini)"), load.index("CheckEverything(dir)"))

    def test_device_box_parse_keeps_the_box_inside_the_stage(self):
        box = function(self.src, "bool ParseDeviceBox(")
        self.assertIn("box[0] + box[2] > 1.0 || box[1] + box[2] > 1.0", box)
        self.assertIn("box[2] <= 0.0", box)
        left, top, scale = (float(v) for v in re.search(r"^DeviceBox=(\S+)$", self.ini, re.M).group(1).split(","))
        self.assertTrue(0 <= left and 0 <= top and 0 < scale and left + scale <= 1 and top + scale <= 1)
        self.assertIn("constexpr double        kStageWidth = 1920.0;", self.src)
        self.assertIn("constexpr double        kStageHeight = 1080.0;", self.src)

    def test_idles_by_editor_id_only(self):
        # no form id for the idles anywhere in the source: step 3a found the raise plays only by editor id
        for form_id in ("26FCCA", "26fcca", "26FCC9", "26fcc9"):
            self.assertNotIn(form_id, self.src, form_id)
        self.assertNotIn("Human_1stPersonRoot", self.src)   # the editor ids come from the ini alone
        idle = function(self.src, "std::uintptr_t DeviceIdleForm(")
        self.assertIn("reinterpret_cast<LookupByEditorId_t>(g_base + g_deviceLookupRva)", idle)
        self.assertIn('IsType(form, "TESIdleForm@@", type)', idle)
        self.assertIn("formType != kIdleType", idle)
        for reason in ("not_found", "not_idle", "no_event"):
            self.assertIn(f"reason={reason}", idle, reason)
        self.assertIn("step=device_idle which={} editor_id={} form={:08X} type={:#x} graph={} event={}", idle)
        self.assertIn("constexpr std::uint32_t kLookupByEditorId = 47403;", self.src)
        self.assertIn("constexpr std::uint8_t  kIdleType = 0x5C;", self.src)
        check = function(self.src, "bool CheckDeviceId(")
        self.assertIn("const auto viaLibrary = REL::ID(kLookupByEditorId).offset();", check)

    def test_idle_offsets_are_the_3b_sessions(self):
        # 1.16.244: at 6040290d +0x68 held the graph's .agx path; graph and event move 8 bytes on
        note = "// 1.16.244, FAL-719, inferred from the 3b session; the Sep 2025 libxse header has 0x60/0x68"
        self.assertIn("constexpr std::size_t   kIdleGraphAt = 0x68;             " + note, self.src)
        self.assertIn("constexpr std::size_t   kIdleEventAt = 0x70;             " + note, self.src)
        idle = function(self.src, "std::uintptr_t DeviceIdleForm(")
        self.assertIn("Peek(form + kIdleGraphAt, graphEntry) && ReadPoolString(graphEntry, graph)", idle)
        self.assertIn("Peek(form + kIdleEventAt, eventEntry) && ReadPoolString(eventEntry, event)", idle)
        # DeviceNotify still sends the BSFixedString at kIdleEventAt
        notify = function(self.src, "std::string DeviceNotify(")
        self.assertIn("*reinterpret_cast<const RE::BSFixedString*>(a_idle + kIdleEventAt)", notify)
        self.assertNotIn("0x70", notify)

    def test_idle_slot_dump(self):
        self.assertIn("constexpr std::size_t   kIdleSlotFirst = 0x58;", self.src)
        self.assertIn("constexpr std::size_t   kIdleSlotLast = 0x80;", self.src)
        idle = function(self.src, "std::uintptr_t DeviceIdleForm(")
        self.assertIn("for (std::size_t at = kIdleSlotFirst; at <= kIdleSlotLast; at += 8) {", idle)
        self.assertIn("const bool     read = Peek(form + at, entry) && ReadPoolString(entry, text);", idle)
        self.assertIn('slots += std::format(" s{:x}={}", at, read && !text.empty() ? text : "-");', idle)
        self.assertIn('"step=device_idle_slots which={} form={:08X}{} t_ms={}"', idle)
        # after the type check, before the event is read; once per idle (DeviceResolve runs once)
        self.assertLess(idle.index("formType != kIdleType"), idle.index("step=device_idle_slots"))
        self.assertLess(idle.index("step=device_idle_slots"), idle.index("Peek(form + kIdleEventAt"))
        self.assertEqual(self.src.count("DeviceIdleForm("), 3)   # the definition and the two calls in DeviceResolve
        resolve = function(self.src, "bool DeviceResolve()")
        self.assertIn("if (g_deviceState >= 0) {", resolve)
        self.assertEqual(["s{:x}".format(a) for a in range(0x58, 0x81, 8)], ["s58", "s60", "s68", "s70", "s78", "s80"])

    def test_event_that_is_a_path_is_refused(self):
        guard = function(self.src, "bool EventIsPath(")
        self.assertIn('a_event.find_first_of("\\\\/")', guard)
        for ext in ('".agx"sv', '".hkx"sv', '".hkt"sv'):
            self.assertIn(ext, guard)
        idle = function(self.src, "std::uintptr_t DeviceIdleForm(")
        self.assertIn("if (EventIsPath(event)) {", idle)
        self.assertIn("reason=event_is_path slot={:#x} value={}", idle)
        self.assertLess(idle.index("if (EventIsPath(event)) {"), idle.index('REX::INFO("step=device_idle which='))
        self.assertIn("reason=event_is_path slot=0x70 value=", self.readme)
        # the 3b session's value is refused, an event-like name is not
        def is_path(event):
            return "\\" in event or "/" in event or event.lower().endswith((".agx", ".hkx", ".hkt"))
        self.assertTrue(is_path("AnimTextData\\Tables\\Graphs\\Human_1stPersonRoot.agx"))
        self.assertFalse(is_path("DataSlateOpen"))

    def test_device_key_refuses_game_bound_keys(self):
        self.assertIn("constexpr std::uint32_t kQuickSaveKey = 0x74;", self.src)
        self.assertIn("constexpr std::uint32_t kQuickLoadKey = 0x78;", self.src)
        read = function(self.src, "bool ReadDevice(")
        self.assertIn("if (g_deviceKey == kQuickSaveKey || g_deviceKey == kQuickLoadKey) {", read)
        self.assertIn('Refuse("ini", std::format("reason=device_key detail=game_bound', read)
        self.assertLess(read.index('L"DeviceKey", 0x76'), read.index("kQuickSaveKey"))
        self.assertIn("detail=game_bound", self.readme)
        self.assertIn("`0x76` (F7)", self.readme)
        self.assertNotIn("DeviceKey=0x78", self.ini)

    def test_raise_is_the_idle_event_on_the_players_holder(self):
        holder = function(self.src, "int DeviceHolder()")
        self.assertIn('BaseOffset(type, "IAnimationGraphManagerHolder@@")', holder)
        self.assertIn("*at != kAnimHolderAt", holder)
        self.assertIn("ThunkTarget(slots[0], *at)", holder)
        notify = function(self.src, "std::string DeviceNotify(")
        self.assertIn("*reinterpret_cast<const RE::BSFixedString*>(a_idle + kIdleEventAt)", notify)
        self.assertIn("reinterpret_cast<NotifyGraph_t>(g_deviceNotify)(reinterpret_cast<void*>(player + kAnimHolderAt), event)",
                      notify)
        self.assertIn("holder != g_deviceHolderVtable", notify)

    def test_sequence_raise_then_show_after_the_hold(self):
        thread = function(self.src, "std::uint32_t KeyThread(")
        # FAL-725: the show is due DeviceRaiseMs after the accepted (or given-up) raise, queued on the tick
        self.assertIn("DeviceRetryStart(g_raiseRetry, n);\n\t\t\t\t\t\t\tg_task->AddTask([n]() { DeviceRaise(n); });", thread)
        self.assertIn("g_task->AddTask([sn]() { DeviceShow(sn); });", thread)
        self.assertIn("g_deviceShowAt.compare_exchange_strong(showAt, 0)", thread)
        raise_ = function(self.src, "void DeviceRaise(")
        self.assertEqual(raise_.count("g_deviceShowAt = NowMs() + g_deviceRaiseMs;"), 2)   # retry 0, and the outcome
        self.assertIn('g_task->AddTask([n]() { Close(n, "device"); });', thread)
        self.assertIn("if (at < g_deviceLowerUntil.load()) {", thread)
        show = function(self.src, "void DeviceShow(")
        self.assertLess(show.index("g_deviceOpening = true;"), show.index("Toggle(a_n);"))
        # F10 (Key) still toggles as before, with no raise
        self.assertIn("g_task->AddTask([n]() { Toggle(n); });", thread)
        self.assertEqual(thread.count("Toggle(n)"), 1)

    def test_lower_is_sent_from_the_hide_handling(self):
        message = function(self.src, "RE::UI_MESSAGE_RESULT MenuProcessMessage(")
        hide = message[message.index("type == RE::UI_MESSAGE_TYPE::kHide) {\n\t\t\t\tSnapshot(\"hide\");"):]
        self.assertIn("if (g_asDevice.exchange(false)) {", hide)
        self.assertIn("g_task->AddTask([n]() { DeviceLower(n); });", hide)
        # not from CheckState's 750 ms check
        self.assertNotIn("DeviceLower", function(self.src, "void CheckState("))
        lower = function(self.src, "void DeviceLower(")
        self.assertIn("g_deviceLowerUntil = NowMs() + g_deviceLowerMs;", lower)
        self.assertIn("DeviceNotify(g_lowerIdle)", lower)
        # FAL-725: pending from kHide, before the first try is queued
        self.assertLess(hide.index("DeviceRetryStart(g_lowerRetry, n);"), hide.index("DeviceLower(n); });"))

    # ------------------------------------------------------------------ FAL-725 (rev 9): the retries
    def test_retry_ms_ini_default_and_range(self):
        self.assertIn("\nDeviceRetryMs=2000\n", self.ini)
        read = function(self.src, "bool ReadDevice(")
        self.assertIn('g_deviceRetryMs = ReadNumber(a_ini, L"DeviceRetryMs", 2000);', read)
        self.assertIn("g_deviceRetryMs > kMaxDeviceMs", read)
        self.assertIn("constexpr std::uint32_t kMaxDeviceMs = 5000;", self.src)
        self.assertIn("constexpr std::int64_t  kDeviceRetryEveryMs = 100;", self.src)
        self.assertIn("`DeviceRetryMs`", self.readme)

    def test_retry_only_on_zero_and_stops_on_one_deadline_or_stop_words(self):
        outcome = function(self.src, "std::string DeviceRetryOutcome(")
        self.assertIn('if (a_result == "0" && now + kDeviceRetryEveryMs <= a_retry.deadline.load()) {', outcome)
        self.assertIn("a_retry.nextAt = now + kDeviceRetryEveryMs;", outcome)
        self.assertIn("a_retry.state = kRetryWaiting;", outcome)
        self.assertIn('return a_result == "0" ? std::string("gave_up") : a_result;', outcome)
        # anything but "0" ends it: "1", holder_changed and no_player (DeviceNotify's words) and refused
        notify = function(self.src, "std::string DeviceNotify(")
        for word in ('"no_player"', '"holder_changed"', 'sent ? "1" : "0"'):
            self.assertIn(word, notify)
        start = function(self.src, "void DeviceRetryStart(")
        self.assertIn("a_retry.deadline = now + g_deviceRetryMs;", start)
        # the tick queues a waiting retry once (waiting -> in flight), from the key thread; no new thread
        thread = function(self.src, "std::uint32_t KeyThread(")
        self.assertIn("retry->state.compare_exchange_strong(waiting, kRetryInFlight)", thread)
        self.assertIn("tick >= retry->nextAt.load()", thread)
        self.assertIn("g_task->AddTask([rn]() { DeviceRaise(rn); });", thread)
        self.assertIn("g_task->AddTask([rn]() { DeviceLower(rn); });", thread)
        self.assertEqual(self.src.count("CreateThread("), 1)

    def test_one_done_line_per_send_and_none_per_retry(self):
        for name, step in (("void DeviceRaise(", "device_raise"), ("void DeviceLower(", "device_lower")):
            body = function(self.src, name)
            done = re.findall(r'"step=' + step + r'_done [^"]*"', body)
            self.assertEqual(len(done), 1, name)
            for field in ("tries=", "waited_ms=", "t_ms="):
                self.assertIn(field, done[0], (name, field))
            first = re.findall(r'"step=' + step + r' [^"]*"', body)
            self.assertEqual(len(first), 1, name)
            self.assertIn("try=1", first[0])
            self.assertIn("if (tries == 1) {\n\t\t\tREX::INFO(\"step=" + step + " ", body)
            self.assertIn("if (outcome.empty()) {\n\t\t\treturn;\n\t\t}", body)   # a try still due: no line
            self.assertIn(step + "_done", self.readme)

    def test_lock_only_on_the_accepted_lower(self):
        lower = function(self.src, "void DeviceLower(")
        self.assertEqual(lower.count("g_deviceLowerUntil = "), 2)
        retry0 = lower.index("if (g_deviceRetryMs == 0) {")
        accepted = lower.index('if (outcome == "1") {')
        for at in [m.start() for m in re.finditer("g_deviceLowerUntil = ", lower)]:
            self.assertTrue(retry0 < at < retry0 + 120 or accepted < at < accepted + 160, at)
        self.assertNotIn("g_deviceLowerUntil", function(self.src, "RE::UI_MESSAGE_RESULT MenuProcessMessage("))
        self.assertNotIn("g_deviceLowerUntil = ", function(self.src, "std::uint32_t KeyThread("))

    def test_device_key_ignored_while_a_lower_is_pending(self):
        thread = function(self.src, "std::uint32_t KeyThread(")
        pending = thread.index("if (g_lowerRetry.state.load() != kRetryIdle) {")
        self.assertIn('"step=device_key ignored=lowering pending=1 t_ms={}"', thread)
        self.assertLess(pending, thread.index("const auto n = ++presses;\n\t\t\t\t\t\tg_devicePressAt = at;"))
        self.assertIn('"step=device_key ignored=opening pending=1 t_ms={}"', thread)

    def test_no_device_sleep_left(self):
        thread = function(self.src, "std::uint32_t KeyThread(")
        device = thread[thread.index("if (g_device) {   // FAL-714"):thread.index("deviceDown = deviceNow;")]
        self.assertNotIn("Sleep(", device)
        self.assertNotIn("Sleep(g_deviceRaiseMs)", self.src)
        self.assertIn("deviceCheckAt = tick + 750;", device)
        self.assertIn("g_task->AddTask([cn]() { CheckState(cn); });", device)

    def test_retry_zero_keeps_one_send_and_the_lock_from_the_close(self):
        raise_ = function(self.src, "void DeviceRaise(")
        zero = raise_[raise_.index("if (g_deviceRetryMs == 0) {"):]
        self.assertLess(zero.index("g_raiseRetry.state = kRetryIdle;"), zero.index("return;"))
        self.assertLess(zero.index("return;"), zero.index("DeviceRetryOutcome("))
        lower = function(self.src, "void DeviceLower(")
        zero = lower[lower.index("if (g_deviceRetryMs == 0) {"):]
        self.assertTrue(zero.startswith("if (g_deviceRetryMs == 0) {\n\t\t\tg_deviceLowerUntil = NowMs() + g_deviceLowerMs;"))
        self.assertLess(lower.index("if (g_deviceRetryMs == 0) {\n\t\t\treturn;"), lower.index("DeviceRetryOutcome("))

    def test_key_opens_reset_the_root_to_the_full_screen(self):
        place = function(self.src, "void DevicePlace(")
        self.assertIn("const double              x = a_asDevice ? g_deviceBox[0] * kStageWidth : 0.0;", place)
        self.assertIn("const double              y = a_asDevice ? g_deviceBox[1] * kStageHeight : 0.0;", place)
        self.assertIn("const double              scale = a_asDevice ? g_deviceBox[2] : 1.0;", place)
        for name in ('"x"', '"y"', '"scaleX"', '"scaleY"'):
            self.assertIn(f"DeviceSetNumber(top, {name},", place)
        self.assertIn('a_asDevice ? "device" : "key"', place)
        setter = function(self.src, "void DeviceSetNumber(")
        self.assertIn("a_root.SetMember(a_name, RE::Scaleform::GFx::Value(a_value))", setter)
        self.assertIn("back.IsNumber() && std::fabs(back.GetNumber() - a_value) <= kBoxReadBack", setter)
        message = function(self.src, "RE::UI_MESSAGE_RESULT MenuProcessMessage(")
        show = message[message.index("if (g_stage == 5) {   // the kit opens"):message.index("} else if (g_stage == 4) {")]
        self.assertLess(show.index("KitWrite(a_self, 0, true);"), show.index("DevicePlace(a_self, asDevice);"))
        self.assertIn("const bool asDevice = g_deviceOpening.exchange(false);", show)

    def test_every_device_line_carries_t_ms(self):
        lines = re.findall(r'"((?:refuse )?step=device_\w+[^"]*)"', self.src)
        lines += re.findall(r'Refuse\("device_\w+", std::format\("([^"]*)"', self.src)
        self.assertGreaterEqual(len(lines), 12)
        for line in lines:
            if line.startswith("name=TESForm.LookupByEditorID") or line.startswith("step=device_id"):
                continue   # at load, before any press
            self.assertIn("t_ms=", line, line)

    def test_readme_documents_the_lines(self):
        self.assertIn("## The device raise (FAL-714, step 3b)", self.readme)
        for line in ("step=device_key", "step=device_holder", "step=device_idle", "step=device_raise", "step=device_show",
                     "step=device_box", "step=device_lower", "refuse step=device_id", "refuse step=device_holder"):
            self.assertIn(line, self.readme, line)
        self.assertIn("no camera or FOV write", self.readme)


if __name__ == "__main__":
    unittest.main()
