"""scripts/game/campaign_arm.py: a chain of planned queues is armed only with the night-run caps, on the installed set,
away from held cells (synthetic queue folders; nothing launched)."""
import hashlib
import io
import json
import os
import sys
import tempfile
import re
import unittest
from unittest import mock
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import campaign_arm as ca  # noqa: E402
REAL_REV = ca.checkout_rev_why                                           # setUp mocks it for the other tests
REAL_KEPT = ca.game_kept_why
REAL_HERE = ca.checkout_here_why
REAL_ON_PY = ca.on_campaign_python
import testqueue as tq  # noqa: E402

CAPS = {"max_attempts": 1, "max_relaunch": 1, "crash_budget": 1, "min_free_gb": 43, "dump_drive": "D:\\"}
PY = "C:\\py\\python.exe"
PLUGINS = ["FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm", "FO4ActorRaider.esm", "FO4SFMission.esm"]


STARFIELD_T = ca.STARFIELD


def tes4(name, masters=("Starfield.esm",)):
    """A plugin header: its masters (MAST + DATA) and its name (SNAM), so each plugin's bytes differ."""
    import struct
    sub = lambda t, b: t + struct.pack("<H", len(b)) + b
    body = b"".join(sub(b"MAST", m.encode() + b"\0") + sub(b"DATA", b"\0" * 8) for m in masters)
    body += sub(b"SNAM", name.encode() + b"\0")
    return b"TES4" + struct.pack("<I", len(body)) + b"\0" * 16 + body


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        # Keep the real interpreter-existence check: positive campaigns need an
        # existing, synthetically named file. Runner calls themselves are faked.
        python = os.path.join(self.d, "runtime", "python.exe")
        os.makedirs(os.path.dirname(python))
        with open(python, "wb") as f:
            f.write(b"synthetic interpreter fixture; never executed")
        self.checkout = os.path.join(self.d, "checkout-without-runner-features")
        os.makedirs(self.checkout)
        default_game = os.path.join(self.d, "default-Starfield")
        for target, name, value in ((sys.modules[__name__], "PY", python),
                                    (sys.modules[__name__], "STARFIELD_T", default_game),
                                    (ca, "STARFIELD", default_game)):
            patch = mock.patch.object(target, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.staging = os.path.join(self.d, "integ_v6")
        os.makedirs(self.staging)
        with open(os.path.join(self.staging, "FO4Port.esm"), "wb") as f:
            f.write(b"port")
        self.exp = os.path.join(self.d, "v6e")
        self.sf = os.path.join(self.d, "SF")                              # the experiment already installed there
        os.makedirs(os.path.join(self.sf, "Data"))
        with open(os.path.join(self.sf, "Starfield.exe"), "wb") as f:   # an exe launch starts it (cycle.ps1)
            f.write(b"MZ")
        self.receipt(self.exp)
        self.local = os.path.join(self.d, "appdata")                     # Plugins.txt: the experiment ticked
        os.makedirs(os.path.join(self.local, "Starfield"))
        self.plugins_txt(["*" + p for p in PLUGINS])
        env = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local})
        env.start()
        self.addCleanup(env.stop)
        # the checkout's commit (checkout_rev_why) and a running game (game_running) have tests of their own
        for name in ("checkout_rev_why", "game_running", "game_kept_why", "checkout_here_why", "on_campaign_python"):
            m = mock.patch.object(ca, name, return_value=None)
            m.start()
            self.addCleanup(m.stop)
        self.stage = os.path.join(self.d, "stage")                       # the judges' rounds.json and presence.json
        os.makedirs(self.stage)
        for n in ("rounds.json", "presence.json"):
            with open(os.path.join(self.stage, n), "w") as f:
                json.dump({"tests": []}, f)

    def plugins_txt(self, lines):
        with open(os.path.join(self.local, "Starfield", "Plugins.txt"), "w") as f:
            f.write("".join(x + "\n" for x in lines))

    def receipt(self, exp, plugins=PLUGINS, **extra):
        """The install record exp_install.py writes for exp with plugins, its files copied into Data."""
        import exp_install as ei
        names = list(plugins if plugins is not None else PLUGINS)
        os.makedirs(exp, exist_ok=True)
        for n in names:
            for d in (exp, os.path.join(self.sf, "Data")):
                with open(os.path.join(d, n), "wb") as f:
                    f.write(tes4(n))
        rec = {"exp_dir": exp, "complete": True, "pack": True, "packing_policy": ei.PACKING_POLICY,
               "files": {n: ei.digest(os.path.join(self.sf, "Data", n)) for n in names},
               "source_inputs": ei.source_inventory(exp, names)}
        if plugins is not None:
            rec["plugins"] = list(plugins)
        with open(os.path.join(self.sf, "Data", "FO4SFExp.install.json"), "w") as f:
            json.dump(dict(rec, **extra), f)

    def queue(self, name, tests, pre=None, **extra):
        q = os.path.join(self.d, name)
        os.makedirs(q)
        digest = tq.sha256(os.path.join(self.staging, "FO4Port.esm"))
        body = dict({"staging": self.staging, "plugin_sha256": digest, "build_id": digest[:8], "experiment": self.stage,
                     "plugin_index": "02", "tests": [dict(t, id=f"{i:04d}_t") for i, t in enumerate(tests)]}, **extra)
        routes = {os.path.basename(t["routes_file"]): tq.sha256(t["routes_file"]) for t in body["tests"]
                  if t.get("routes_file") and os.path.isfile(t["routes_file"])}   # plan pins the routes it read
        if routes:
            body.setdefault("routes_sha256", routes)
        for n in ("rounds", "presence"):                                 # plan-terrain pins the stage's judge files
            if os.path.isfile(os.path.join(self.stage, n + ".json")):
                body.setdefault(n + "_sha256", tq.sha256(os.path.join(self.stage, n + ".json")))
        if pre is not None:
            body["pre_launch"] = pre
        with open(os.path.join(q, "queue.json"), "w") as f:
            json.dump(body, f)
        return q

    def camp(self, queues, **over):
        c = {"name": "v6e", "checkout": self.checkout, "python": PY,
             "staging": self.staging, "installed_exp": self.exp, "installed_plugins": PLUGINS, "caps": dict(CAPS),
             "starfield": self.sf,
             "holds": {"red_rocket": ["FO4Core_RedRocketSpawn"]},
             "queues": [{"name": n, "queue": q} for n, q in queues]}
        c.update(over)
        return c

    def check(self, camp, release=()):
        res, ok = ca.check(camp, set(release))
        return ok, [w for _, why, _ in res["queues"] for w in why] + res["caps"]


class CheckTests(Base):
    def test_an_interior_queue_on_the_installed_set_is_armed(self):
        q = self.queue("doors_out", [{"coc": "FO4Port_Vault95", "travel": "coc FO4Port_Vault95"}])
        self.assertEqual(self.check(self.camp([("doors_out", q)])), (True, []))
        stairs = self.queue("stairs", [{"kind": "stairs", "cell": "BostonPublicLibrary02"}, {"kind": "walk", "cell": ""}])
        # Codex on #391: the walk (no cell) launches into the queue's launch cell first, so that cell counts too
        self.assertEqual(ca.cells(tq.load(os.path.join(stairs, "queue.json"))), ["Vault111Cryo", "BostonPublicLibrary02"])
        held = self.queue("held", [{"kind": "terrain", "cell": "", "world_coc": "FO4Port_X"}],
                          launch_cell="FO4Core_RedRocketSpawn")
        ok, why = self.check(self.camp([("held", held)]))
        self.assertFalse(ok)
        self.assertIn("FO4Core_RedRocketSpawn: held (red_rocket)", " ".join(why))

    def test_a_red_rocket_start_is_held_until_released(self):
        q = self.queue("walk", [{"travel": "coc FO4Core_RedRocketSpawn"}])
        ok, why = self.check(self.camp([("walk", q)]))
        self.assertFalse(ok)
        self.assertIn("held (red_rocket)", why[0])
        self.assertEqual(self.check(self.camp([("walk", q)]), {"red_rocket"}), (True, []))
        ok, why = self.check(self.camp([("walk", q)]), {"sanctuary"})
        self.assertIn("does not have", why[-1])

    def test_only_the_installed_experiment_may_be_installed_before_launch(self):
        exp = [PY, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp, "--starfield", self.sf,
               "--plugins", ",".join(PLUGINS), "--pack"]
        q = self.queue("walk", [{"coc": "FO4Port_X"}], pre=exp)
        self.assertEqual(self.check(self.camp([("walk", q)], starfield=self.sf + os.sep)), (True, []))
        # Codex on #391: the experiment goes into the Starfield folder the chain launches (the default when unset)
        self.assertIn("pre_launch installs into %s, the campaign runs" % self.sf,
                      " ".join(self.check(self.camp([("walk", q)], starfield=None))[1]))
        # Codex on #391: with no record, or another experiment's, the "reinstall" would change the installed set
        for rec, want in ((None, "no readable install record"), ((os.path.join(self.d, "v6c"),), "would replace"),
                          ((self.exp, PLUGINS[:1]), "would replace"), ((self.exp, PLUGINS, {"complete": False}), "incomplete")):
            with self.subTest(rec=rec):
                os.remove(os.path.join(self.sf, "Data", "FO4SFExp.install.json"))
                if rec:
                    self.receipt(rec[0], *(rec[1:2]), **(rec[2] if len(rec) > 2 else {}))
                ok, why = self.check(self.camp([("walk", q)], starfield=self.sf))
                self.assertFalse(ok)
                self.assertIn(want, " ".join(why))
                self.receipt(self.exp)
        other = list(exp)
        other[4] = os.path.join(self.d, "v6c")
        q2 = self.queue("walk2", [{"coc": "FO4Port_X"}], pre=other)
        fewer = list(exp)
        fewer[8] = "FO4TerrainCore.esm"
        q3 = self.queue("walk3", [{"coc": "FO4Port_X"}], pre=fewer)
        q4 = self.queue("walk4", [{"coc": "FO4Port_X"}], pre=[PY, "scripts\\game\\bridge_install.py", "uninstall"])
        feat = self.queue("feat", [{"coc": "FO4Port_X"}], pre=[PY, "scripts/game/runner_features.py", "check", "bridge"])
        for q, want in ((q2, "would install"), (q3, "would activate"), (q4, "not a runner check")):
            with self.subTest(q=q):
                ok, why = self.check(self.camp([("q", q)]))
                self.assertFalse(ok)
                self.assertIn(want, why[0])
        self.assertTrue(self.check(self.camp([("feat", feat)], checkout=ROOT))[0])
        # Codex on #391: the features are the campaign checkout's, read from its runner_features.py
        old = os.path.join(self.d, "old_checkout")
        os.makedirs(os.path.join(old, "scripts", "game"))
        with open(os.path.join(old, "scripts", "game", "runner_features.py"), "w") as f:
            f.write('FEATURES = ("light", "console")\n')
        ok, why = self.check(self.camp([("feat", feat)], checkout=old))
        self.assertFalse(ok)
        self.assertIn("needs runner features ['bridge'] the checkout", " ".join(why))
        ok, why = self.check(self.camp([("feat", feat)], checkout=os.path.join(self.d, "none")))
        self.assertIn("has no readable", " ".join(why))
        bare = self.queue("bare", [{"coc": "FO4Port_X"}], pre=[PY, "scripts/game/runner_features.py", "check"])
        self.assertIn("want check <features>", " ".join(self.check(self.camp([("q", bare)], checkout=ROOT))[1]))

    def test_another_or_changed_build_is_refused(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        with open(os.path.join(self.staging, "FO4Port.esm"), "wb") as f:
            f.write(b"rebuilt")
        self.assertIn("changed since the plan", self.check(self.camp([("a", q)]))[1][0])
        q2 = self.queue("b", [{"coc": "FO4Port_X"}], staging=os.path.join(self.d, "other"))
        self.assertIn("pins the staging", self.check(self.camp([("b", q2)]))[1][0])

    def test_the_caps_must_be_the_night_run_caps(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        for change in ({"max_relaunch": 3}, {"crash_budget": 0}, {"min_free_gb": 25}, {"min_free_gb": float("nan")},
                       {"max_attempts": 5}, {"dump_drive": "D:\\dumps"}):
            with self.subTest(change=change):
                ok, why = self.check(self.camp([("a", q)], caps=dict(CAPS, **change)))
                self.assertFalse(ok)
                self.assertEqual(len(why), 1)

    def test_used_queues_bad_judges_and_missing_queues_are_refused(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"crashes": 0, "start_deaths": 1, "done": {}}, f)
        self.assertIn("dead start", self.check(self.camp([("a", q)]))[1][0])
        q2 = self.queue("b", [{"coc": "FO4Port_X"}])
        with open(os.path.join(q2, "state.json"), "w") as f:
            json.dump({"done": {"0000_t": {"verdict": "PASS"}}}, f)
        self.assertIn("already done", self.check(self.camp([("b", q2)]))[1][0])
        q3 = self.queue("c", [{"coc": "FO4Port_X"}])
        c = self.camp([("c", q3)])
        c["queues"][0]["judge"] = ["scripts/game/cycle.ps1"]
        self.assertIn("is not door_rounds.py judge", self.check(c)[1][0])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q3]
        self.assertTrue(self.check(c)[0])
        # Codex on #391: a judge of another queue folder (or of none, or of two) is refused
        q4 = self.queue("d", [{"coc": "FO4Port_X"}])
        for bad in (["--queue", q4], [], ["--queue", q3, "--queue", q4], ["--queue=" + q3], ["--queue"]):
            with self.subTest(bad=bad):
                c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge"] + bad
                self.assertIn("does not judge this queue", " ".join(self.check(c)[1]))
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q3.upper() + "\\"]
        self.assertTrue(self.check(c)[0])                                   # the same folder, written otherwise
        self.assertIn("no planned queue", self.check(self.camp([("x", os.path.join(self.d, "nope"))]))[1][0])
        self.assertIn("no queues", self.check(self.camp([]))[1][0])
        self.assertIn("repeated", " ".join(self.check(self.camp([("c", q3), ("c", q3)]))[1]))
        # Codex on #391: two names for one folder: the first would finish it, the second refuse it as done
        self.assertIn("named by an earlier entry too",
                      " ".join(self.check(self.camp([("c", q3), ("c2", q3.upper() + "\\")]))[1]))
        dotted = os.path.join(os.path.dirname(q3), "tmp", "..", os.path.basename(q3), ".")
        self.assertIn("named by an earlier entry too", " ".join(self.check(self.camp([("c", q3), ("c2", dotted)]))[1]))


    def test_a_judge_option_its_parser_would_refuse_is_refused(self):
        # Codex on #391: the judge's argparse exits 2 on an unknown, repeated or valueless option, after the run
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        c = self.camp([("a", q)])
        dr = ["scripts/bridge/door_rounds.py", "judge", "--queue", q]
        for good in (dr, dr + ["--world-instance", "FF00552F=02000803", "--world-instance", "FF000001=02000001"]):
            with self.subTest(good=good):
                c["queues"][0]["judge"] = good
                self.assertTrue(self.check(c)[0], self.check(c)[1])
        for bad, msg in ((dr + ["--typo"], "is not one"), (dr + ["--world-instance"], "needs a value"),
                         (dr + ["--world-instance", "FF00552F"], "needs a value"),
                         (dr + ["--rou", "x"], "is not one"),
                         (["scripts/game/testqueue.py", "report", "--queue", q, "--typo"], "is not one"),
                         (["scripts/bridge/presence.py", "judge", "--queue", q, "--rounds", "x"], "is not one"),
                         (dr + ["--world-instance", "-x=1"], "needs a value"),
                         (dr + ["--world-instance", "nope=also-nope"], "8 hex digits"),
                         (dr + ["--world-instance", "02000803=FF00552F"], "created (FF) world"),
                         (dr + ["--world-instance", "FF00552F=02000803", "--world-instance", "FF00552F=02000001"],
                          "pins FF00552F to both")):
            with self.subTest(bad=bad):
                c["queues"][0]["judge"] = bad
                ok, why = self.check(c)
                self.assertFalse(ok)
                self.assertIn(msg, " ".join(why))

    def test_a_fresh_test_only_starts_the_chains_first_queue(self):
        # Codex on #391: a later queue's runner reuses the game the queue before it left running, so its fresh first
        # test would run in a used session
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qf = self.queue("f", [{"coc": "FO4Port_Y", "fresh": True}])
        self.assertTrue(self.check(self.camp([("f", qf), ("a", qa)]))[0])
        ok, why = self.check(self.camp([("a", qa), ("f", qf)]))
        self.assertFalse(ok)
        self.assertIn("0000_t would launch the game again", " ".join(why))

    def test_a_queue_bridge_needs_the_campaign_bridge_and_holds_need_lists(self):
        # Codex on #391: a pinned bridge passed when the campaign named none; a hold written as a string held nothing
        q = self.queue("a", [{"coc": "FO4Core_RedRocketSpawn"}], bridge={"dir": "C:\\b\\bridge_t4"})
        ok, why = self.check(self.camp([("a", q)], holds={"red_rocket": "FO4Core_RedRocketSpawn"}))
        self.assertFalse(ok)
        self.assertTrue(any("campaign names no bridge" in w for w in why), why)
        self.assertTrue(any("is not a list of cell editor ids" in w for w in why), why)
        for bad in (["FO4Core_RedRocketSpawn", 3], ["coc X"], {"a": 1}):
            with self.subTest(bad=bad):
                self.assertIn("is not a list of cell editor ids", " ".join(self.check(self.camp([("a", q)],
                              bridge="C:\\b\\bridge_t4", holds={"red_rocket": bad}))[1]))


class PlanTerrainHoldTests(Base):
    def test_a_plan_terrain_door_in_leg_is_held(self):
        # review pass on #391: plan-terrain writes no "coc"; an IN leg starts at world_coc with an empty travel
        # (testqueue.py plan-terrain, door_rounds.py's IN leg), so the red_rocket hold never saw it
        q = self.queue("doors", [{"kind": "terrain", "cell": "", "ref": "FO4Core_RedRocketSpawn",
                                  "world_coc": "FO4Core_RedRocketSpawn", "travel": ""},
                                 {"kind": "terrain", "cell": "", "ref": "FO4Port_SuperDuperMart01",
                                  "world_coc": "FO4Port_SuperDuperMart01", "travel": "coc FO4Port_SuperDuperMart01"}])
        self.assertEqual(ca.cells(ca.tq.load(os.path.join(q, "queue.json"))),
                         ["Vault111Cryo", "FO4Core_RedRocketSpawn", "FO4Port_SuperDuperMart01"])
        ok, why = self.check(self.camp([("doors", q)]))
        self.assertFalse(ok)
        self.assertIn("FO4Core_RedRocketSpawn", " ".join(why))


    def test_a_door_trip_into_a_held_interior_is_held(self):
        # Codex on #391: the test starts outside, then enters its "inside" cell through the door
        q = self.queue("doors", [{"kind": "door_trip", "cell": "", "travel": "coc FO4Port_SuperDuperMart01",
                                  "outside": {"start": [0, 0, 0]}, "inside": {"cell": "FO4Port_RedRocket01"}}])
        self.assertIn("FO4Port_RedRocket01", ca.cells(ca.tq.load(os.path.join(q, "queue.json"))))
        c = self.camp([("doors", q)], holds={"red_rocket": ["FO4Port_RedRocket01"]})
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("FO4Port_RedRocket01: held (red_rocket)", " ".join(why))
        self.assertTrue(self.check(dict(c, checkout=ROOT), ["red_rocket"])[0])
        # Codex on #391: a door_trip queue needs the door_trip runner feature, which the checkout must have
        self.assertIn("needs runner features", " ".join(self.check(c, ["red_rocket"])[1]))


    def test_a_travel_into_a_held_cell_is_held(self):
        # Codex on #391: plan's travel test records the cell behind its load door in dest_cell
        q = self.queue("travel", [{"kind": "travel", "cell": "SanctuaryExt", "dest_cell": "FO4Port_RedRocket01"}])
        ok, why = self.check(self.camp([("travel", q)], holds={"red_rocket": ["FO4Port_RedRocket01"]}))
        self.assertFalse(ok)
        self.assertIn("FO4Port_RedRocket01: held (red_rocket)", " ".join(why))

    def test_a_planned_cell_is_held_under_its_ported_name(self):
        # Codex on #391: the runner enters FO4Port_<cell> for a planned cell, a dest_cell and the launch cell
        cases = (([{"kind": "travel", "cell": "RedRocket01"}], {}),
                 ([{"kind": "travel", "cell": "SanctuaryExt", "dest_cell": "RedRocket01"}], {}),
                 ([{"kind": "travel", "cell": "", "travel": "coc FO4Port_SanctuaryExt"}], {"launch_cell": "RedRocket01"}))
        for n, (tests, extra) in enumerate(cases):
            q = self.queue(f"p{n}", tests, **extra)
            ok, why = self.check(self.camp([("p", q)], holds={"red_rocket": ["FO4Port_RedRocket01"]}))
            self.assertFalse(ok, tests)
            self.assertIn("RedRocket01: held (red_rocket)", " ".join(why))
        # and a hold written without the prefix still holds the ported cell
        q = self.queue("bare", [{"coc": "FO4Port_RedRocket01"}])
        self.assertFalse(self.check(self.camp([("p", q)], holds={"red_rocket": ["RedRocket01"]}))[0])

    def test_pre_launch_must_run_the_campaigns_python(self):
        # Codex on #391: the runner runs pre_launch verbatim, its first element included
        for prog in ("C:\\evil.exe", "cmd.exe"):
            q = self.queue("pre_" + prog[:3].strip(":\\"), [{"coc": "FO4Port_X"}],
                           pre=[prog, "scripts/game/runner_features.py", "check", "bridge"])
            ok, why = self.check(self.camp([("p", q)]))
            self.assertFalse(ok)
            self.assertIn("not the campaign's python", " ".join(why))

    def test_fresh_tests_that_would_relaunch_are_refused(self):
        # Codex on #391: a fresh test after the first closes the game and launches again outside --max-relaunch
        q = self.queue("fresh2", [{"coc": "FO4Port_X", "fresh": True}, {"coc": "FO4Port_Y", "fresh": True}])
        ok, why = self.check(self.camp([("f", q)]))
        self.assertFalse(ok)
        self.assertIn("0001_t would launch the game again", " ".join(why))
        # one fresh first test with one attempt starts on the one launch
        q = self.queue("fresh1", [{"coc": "FO4Port_X", "fresh": True}, {"coc": "FO4Port_Y"}])
        self.assertTrue(self.check(self.camp([("f", q)]))[0])
        # a second attempt of a fresh test relaunches too
        self.assertFalse(self.check(self.camp([("f", q)], caps=dict(CAPS, max_attempts=2)))[0])

    def test_a_master_exp_install_order_would_refuse_is_refused(self):
        # Codex on #391: cycle.ps1 runs exp_install.py order after deploying FO4Port.esm; it exits 7 on an inactive master
        c = self.camp([("walk", self.queue("walk", [{"coc": "FO4Port_X"}]))], starfield=self.sf)
        with open(os.path.join(self.sf, "Data", PLUGINS[0]), "wb") as f:
            f.write(tes4(PLUGINS[0], ("Starfield.esm", "FO4Port.esm")))
        self.receipt(self.exp)
        for d in (self.exp, os.path.join(self.sf, "Data")):              # the record's digests follow the files
            with open(os.path.join(d, PLUGINS[0]), "wb") as f:
                f.write(tes4(PLUGINS[0], ("Starfield.esm", "FO4Port.esm")))
        import exp_install as ei
        rec_p = os.path.join(self.sf, "Data", "FO4SFExp.install.json")
        with open(rec_p) as f:
            rec = json.load(f)
        rec["files"][PLUGINS[0]] = ei.digest(os.path.join(self.sf, "Data", PLUGINS[0]))
        rec["source_inputs"] = ei.source_inventory(self.exp, PLUGINS)
        with open(rec_p, "w") as f:
            json.dump(rec, f)
        self.assertEqual(self.check(c), (True, []))                       # FO4Port.esm: the deploy activates it
        for d in (self.exp, os.path.join(self.sf, "Data")):
            with open(os.path.join(d, PLUGINS[0]), "wb") as f:
                f.write(tes4(PLUGINS[0], ("Starfield.esm", "Missing.esm")))
        rec["files"][PLUGINS[0]] = ei.digest(os.path.join(self.sf, "Data", PLUGINS[0]))
        rec["source_inputs"] = ei.source_inventory(self.exp, PLUGINS)
        with open(rec_p, "w") as f:
            json.dump(rec, f)
        self.assertIn(f"{PLUGINS[0]} needs active master Missing.esm", " ".join(self.check(c)[1]))

    def test_an_install_record_for_another_profile_is_refused(self):
        # Codex on #391: exp_install.py order exits 6 when the record's Plugins.txt is not this profile's
        c = self.camp([("walk", self.queue("walk", [{"coc": "FO4Port_X"}]))], starfield=self.sf)
        mine = os.path.join(self.local, "Starfield", "Plugins.txt")
        self.receipt(self.exp, plugins_txt=mine)
        self.assertEqual(self.check(c), (True, []))
        other = os.path.join(self.d, "other", "Starfield", "Plugins.txt")
        self.receipt(self.exp, plugins_txt=other)
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("was written for", " ".join(why))

    def test_the_checkout_must_be_the_campaigns_commit_and_clean(self):
        # Codex on #391: the pins covered data files, not the runner, judge and PowerShell code
        import subprocess
        co = os.path.join(self.d, "co")
        os.makedirs(co)
        git = lambda *a: subprocess.run(["git", "-C", co, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                        capture_output=True, text=True, check=True).stdout.strip()
        git("init", "-q")
        with open(os.path.join(co, "testqueue.py"), "w") as f:
            f.write("x = 1\n")
        git("add", "-A")
        git("commit", "-qm", "c")
        head = git("rev-parse", "HEAD")
        self.assertIsNone(REAL_REV({"checkout": co, "commit": head}))
        self.assertIn("name the checkout's full git sha", REAL_REV({"checkout": co}))
        self.assertIn("the campaign was armed on", REAL_REV({"checkout": co, "commit": "0" * 40}))
        with open(os.path.join(co, "testqueue.py"), "w") as f:
            f.write("x = 2\n")
        self.assertIn("uncommitted changes", REAL_REV({"checkout": co, "commit": head}))
        self.assertIn("not a git checkout", REAL_REV({"checkout": os.path.join(self.d, "none"), "commit": head}))

    def test_pin_writes_a_copy_armed_on_the_checkouts_head(self):
        # Codex on #397: the shipped manifest can not name the commit it is in; pin writes the armed copy
        import subprocess
        rev = mock.patch.object(ca, "checkout_rev_why", REAL_REV)
        rev.start()
        self.addCleanup(rev.stop)
        co = os.path.join(self.d, "co")
        os.makedirs(co)
        git = lambda *a: subprocess.run(["git", "-C", co, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                        capture_output=True, text=True, check=True).stdout.strip()
        git("init", "-q")
        with open(os.path.join(co, "testqueue.py"), "w") as f:
            f.write("x = 1\n")
        git("add", "-A")
        git("commit", "-qm", "c")
        src, out = os.path.join(self.d, "v6e.json"), os.path.join(self.d, "v6e.armed.json")
        with open(src, "w") as f:
            json.dump({"name": "v6e", "checkout": co, "queues": []}, f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["pin", "--campaign", src, "--out", out]), 0)
            self.assertEqual(ca.main(["pin", "--campaign", src, "--out", out]), 1)          # a new file only
        armed = ca.read_campaign(out)
        self.assertEqual(armed["commit"], git("rev-parse", "HEAD"))
        self.assertIsNone(REAL_REV(armed))
        with open(os.path.join(co, "testqueue.py"), "w") as f:
            f.write("x = 2\n")
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(ca.main(["pin", "--campaign", src, "--out", out + "2"]), 1)
        self.assertIn("uncommitted changes", buf.getvalue())
        self.assertFalse(os.path.exists(out + "2"))

    def test_an_install_record_selecting_more_plugins_is_refused(self):
        # Codex on #391: cycle.ps1 orders every plugin the record selected, not only the campaign's
        exp = [PY, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp, "--starfield", self.sf,
               "--plugins", ",".join(PLUGINS), "--pack"]
        q = self.queue("walk", [{"coc": "FO4Port_X"}], pre=exp)
        c = self.camp([("walk", q)], starfield=self.sf)
        self.receipt(self.exp, plugins=PLUGINS + ["FO4Extra.esm"])
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("selects", " ".join(why))
        # a legacy record without "plugins" is read from its added and replaced lines, as exp_install.py does
        self.receipt(self.exp, plugins=None,
                     plugins_added=["*" + p for p in PLUGINS[1:]], plugins_replaced=[{"active": "*" + PLUGINS[0]}])
        self.assertEqual(self.check(c), (True, []))
        self.receipt(self.exp, plugins=None, plugins_added=["*" + p for p in PLUGINS])
        self.assertTrue(self.check(c)[0])

    def test_a_queue_bridge_must_already_be_installed_and_active(self):
        # Codex on #391: Runner.ensure_game installs or reactivates a bridge that is not, before the launch
        import bridge_install as bi
        import exp_install as ei
        bdir = os.path.join(self.d, "bridge_t4")
        os.makedirs(os.path.join(bdir, "Data", "Scripts"))
        for rel, body in ((bi.PLUGIN, b"esm"), (bi.PEX, b"pex")):
            with open(os.path.join(bdir, rel), "wb") as f:
                f.write(body)
        pin = {"dir": bdir, "sha256": {rel: tq.sha256(os.path.join(bdir, rel)) for rel in (bi.PLUGIN, bi.PEX)}}
        q = self.queue("b", [{"coc": "FO4Port_X"}], bridge=pin)
        c = self.camp([("b", q)], starfield=self.sf, bridge=bdir)
        if True:
            ok, why = self.check(c)
            self.assertFalse(ok)
            self.assertIn("the bridge is not installed", " ".join(why))
            files = {}
            for rel, body in ((bi.PLUGIN, b"esm"), (bi.ARCHIVE, b"ba2")):
                with open(os.path.join(self.sf, "Data", rel), "wb") as f:
                    f.write(body)
                files[rel] = ei.digest(os.path.join(self.sf, "Data", rel))
            rec = {"dir": bdir, "plugin": bi.PLUGIN, "source_sha256": bi.source_inventory(bdir), "files": files,
                   "complete": True}
            with open(os.path.join(self.sf, "Data", bi.RECORD), "w") as f:
                json.dump(rec, f)
            ok, why = self.check(c)
            self.assertFalse(ok)
            self.assertIn("installed but not active", " ".join(why))
            self.plugins_txt(["*" + p for p in PLUGINS + [bi.PLUGIN]])
            self.assertEqual(self.check(c), (True, []))
            with open(os.path.join(self.sf, "Data", "FO4SF.toggle.json"), "w") as f:
                json.dump({"off": [bi.PLUGIN]}, f)                      # Codex on #391: bridge_install.py refuses
            self.assertIn("held off by plugin_toggle.py", " ".join(self.check(c)[1]))
            os.remove(os.path.join(self.sf, "Data", "FO4SF.toggle.json"))
            with open(os.path.join(self.sf, "Data", bi.RECORD), "w") as f:
                json.dump(dict(rec, source_sha256={bi.PLUGIN: "0" * 64}), f)
            self.assertIn("is not the queue's", " ".join(self.check(c)[1]))

    def test_an_installed_bridge_is_checked_for_queues_that_name_none(self):
        # Codex on #391: cycle.ps1 runs bridge_install.py order before every launch whenever its receipt exists
        import bridge_install as bi
        import exp_install as ei
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        c = self.camp([("a", q)])
        self.assertEqual(self.check(c), (True, []))                      # no receipt: nothing to order
        files = {}
        for rel, body in ((bi.PLUGIN, b"esm"), (bi.ARCHIVE, b"ba2")):
            with open(os.path.join(self.sf, "Data", rel), "wb") as f:
                f.write(body)
            files[rel] = ei.digest(os.path.join(self.sf, "Data", rel))
        rec = {"dir": "C:\\b", "plugin": bi.PLUGIN, "files": files, "complete": True}
        rec_p = os.path.join(self.sf, "Data", bi.RECORD)
        self.plugins_txt(["*" + p for p in PLUGINS + [bi.PLUGIN]])
        for bad, want in ((dict(rec, complete=False), "incomplete"), (dict(rec, files={bi.PLUGIN: files[bi.PLUGIN]}),
                                                                       "coverage"),
                          (dict(rec, files=dict(files, **{bi.ARCHIVE: "0" * 64})), "changed")):
            with self.subTest(want=want):
                with open(rec_p, "w") as f:
                    json.dump(bad, f)
                ok, why = self.check(c)
                self.assertFalse(ok)
                self.assertTrue(any("bridge_install.py order would stop" in w and want in w for w in why), why)
        with open(rec_p, "w") as f:
            json.dump(rec, f)
        self.assertEqual(self.check(c), (True, []))
        self.plugins_txt(["*" + p for p in PLUGINS])                    # installed, unticked: order would tick it
        self.assertIn("every launch would activate it", " ".join(self.check(c)[1]))
        entry = c["queues"][0]                                           # and again before each queue
        self.assertTrue(any("every launch would activate it" in w
                            for w in ca.recheck(entry, c, set(), ca.queue_sha256(entry))))

    def test_the_campaign_python_must_exist_where_the_check_runs(self):
        # Codex on #391: a typo in python passed the path checks and armed a chain that could start nothing
        self.assertIsNone(ca.python_why(sys.executable))
        self.assertIn("does not exist", ca.python_why(os.path.join(self.d, "python.exe")))
        self.assertIn("not found on PATH", ca.python_why("python-not-installed-here"))
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        with mock.patch.object(ca.os, "name", "nt"):
            missing = os.path.join(self.d, "missing", "python.exe")
            self.assertIn(f"python {missing!r} does not exist",
                          " ".join(self.check(self.camp([("a", q)], python=missing))[1]))

    def test_relative_checkout_staging_and_bridge_are_refused(self):
        # Codex on #391: the chain and the runner resolve a relative path where they are started, not where checked
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        for k, v in (("checkout", "wt_nightrun"), ("checkout", ".\\wt"), ("staging", "integ_v6"), ("bridge", "b\\t4")):
            ok, why = self.check(self.camp([("a", q)], **{k: v}))
            self.assertFalse(ok, k)
            self.assertIn(f"{k} {v!r} is not a full path", " ".join(why))
        rel = os.path.relpath(self.staging)
        q = self.queue("rel", [{"coc": "FO4Port_X"}], staging=rel)
        ok, why = self.check(self.camp([("a", q)], staging=rel))
        self.assertFalse(ok)
        self.assertIn("not a full path", " ".join(why))

    def test_an_inactive_or_held_and_active_experiment_plugin_is_refused(self):
        # Codex on #391: the no-op reinstall stops on either (exp_install.verify_relaunch)
        exp = [PY, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp, "--starfield", self.sf,
               "--plugins", ",".join(PLUGINS), "--pack"]
        q = self.queue("walk", [{"coc": "FO4Port_X"}], pre=exp)
        c = self.camp([("walk", q)], starfield=self.sf)
        self.assertTrue(self.check(c)[0])
        self.plugins_txt(["*" + p for p in PLUGINS[1:]] + [PLUGINS[0]])
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("experiment plugin is inactive", " ".join(why))
        with open(os.path.join(self.sf, "Data", "FO4SF.toggle.json"), "w") as f:
            json.dump({"off": [PLUGINS[0]]}, f)
        self.assertTrue(self.check(c)[0])                                      # held off and unticked: as planned
        self.plugins_txt(["*" + p for p in PLUGINS])
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("held off by plugin_toggle.py but active", " ".join(why))

    def test_the_reinstall_must_be_exp_installs_own_no_op(self):
        # Codex on #391: exp_install.py stops on another packing mode, a changed installed file or changed inputs
        exp = [PY, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp, "--starfield", self.sf,
               "--plugins", ",".join(PLUGINS), "--pack"]
        q = self.queue("walk", [{"coc": "FO4Port_X"}], pre=exp)
        c = self.camp([("walk", q)], starfield=self.sf)
        self.assertEqual(self.check(c), (True, []))
        self.receipt(self.exp, pack=False)
        self.assertIn("asks for a packed experiment", " ".join(self.check(c)[1]))
        self.receipt(self.exp)
        with open(os.path.join(self.sf, "Data", PLUGINS[1]), "ab") as f:
            f.write(b"!")
        self.assertIn("missing or changed", " ".join(self.check(c)[1]))
        self.receipt(self.exp)
        with open(os.path.join(self.exp, PLUGINS[2]), "ab") as f:
            f.write(b"!")
        self.assertIn("source inputs changed", " ".join(self.check(c)[1]))

    def test_a_route_file_is_part_of_the_pin_and_must_be_a_full_path(self):
        # Codex on #391: a stairs or door test reads routes_file when it runs and when it is judged
        r = os.path.join(self.d, "routes_A.json")
        with open(r, "w") as f:
            json.dump({"routes": [[0, 0, 0]]}, f)
        e = {"name": "a", "queue": self.queue("a", [{"coc": "FO4Port_X", "routes_file": r, "route_index": 0}])}
        pin = ca.queue_sha256(e)
        with open(r, "a") as f:
            f.write(" ")
        self.assertNotEqual(ca.queue_sha256(e), pin)
        q = self.queue("rel", [{"coc": "FO4Port_X", "routes_file": "routes_A.json", "route_index": 0}])
        self.assertIn("routes_file routes_A.json is not a full path", " ".join(self.check(self.camp([("a", q)]))[1]))
        os.remove(r)                                                     # Codex on #391: deleted after planning
        self.assertIn(f"routes_file {r} is missing", " ".join(self.check(self.camp([("a", e["queue"])]))[1]))

    def test_the_runners_staging_pin_and_the_planned_route_digests_are_checked(self):
        # Codex on #391: the runner stops before its first test on a changed staging file; a route changed between
        # planning and arming was pinned as it was
        pin = {k: tq.sha256(p) for k, p in tq.staging_paths(self.staging).items()}
        q = self.queue("a", [{"coc": "FO4Port_X"}], staging_files=pin)
        self.assertEqual(self.check(self.camp([("a", q)])), (True, []))
        with open(os.path.join(self.staging, "extra.nif"), "wb") as f:
            f.write(b"new")
        self.assertIn("the staging changed since the queue was planned", " ".join(self.check(self.camp([("a", q)]))[1]))
        os.remove(os.path.join(self.staging, "extra.nif"))
        r = os.path.join(self.d, "routes_A.json")
        with open(r, "w") as f:
            json.dump({"routes": [[0, 0, 0]]}, f)
        q2 = self.queue("b", [{"coc": "FO4Port_X", "routes_file": r, "route_index": 0}],
                        routes_sha256={"routes_A.json": tq.sha256(r)})
        self.assertEqual(self.check(self.camp([("b", q2)])), (True, []))
        with open(r, "a") as f:
            f.write(" ")
        self.assertIn("routes_A.json changed since the queue was planned", " ".join(self.check(self.camp([("b", q2)]))[1]))
        # Codex on #391: a queue without the planned digest (older, or the key removed) is planned again, not trusted
        for name, rs in (("c", None), ("d", {"routes_B.json": "0" * 64})):
            with self.subTest(routes_sha256=rs):
                q3 = self.queue(name, [{"coc": "FO4Port_X", "routes_file": r, "route_index": 0}], routes_sha256=rs)
                self.assertIn("routes_A.json has no planned digest", " ".join(self.check(self.camp([(name, q3)]))[1]))

    def test_an_exe_launch_needs_starfield_exe(self):
        # Codex on #391: cycle.ps1 refuses FO4SF_LAUNCH=exe with no Starfield.exe before any test
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        caps = lambda **over: " ".join(ca.check(self.camp([("a", q)], **over), set())[0]["caps"])
        self.assertNotIn("Starfield.exe", caps(launch="exe"))
        os.remove(os.path.join(self.sf, "Starfield.exe"))
        self.assertIn("Starfield.exe is missing", caps(launch="exe"))
        self.assertNotIn("Starfield.exe", caps(launch="steam"))

    def test_an_unknown_launch_or_a_relative_python_path_is_refused(self):
        # Codex on #391: chain() refused the launch only when writing; a relative python resolves in two folders
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        caps = lambda **over: " ".join(ca.check(self.camp([("a", q)], **over), set())[0]["caps"])
        self.assertIn("launch 'cmd'", caps(launch="cmd"))
        self.assertIn("is a relative path", caps(python=".\\venv\\Scripts\\python.exe"))
        self.assertNotIn("python", caps(python="python"))
        self.assertIn("is not named python.exe", caps(python="py"))           # Codex on #391: the py launcher
        self.assertIn("is not named python.exe", caps(python="C:\\py\\pythonw.exe"))
        self.assertNotIn("python", caps())

    def test_a_relative_starfield_is_refused(self):
        # Codex on #391: the check reads it where it runs, the runner in the checkout
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        self.assertIn("starfield 'SF' is not a full path", " ".join(self.check(self.camp([("a", q)], starfield="SF"))[1]))

    def test_the_declared_experiment_is_checked_without_a_pre_launch(self):
        # Codex on #391: cycle.ps1 launches whatever is installed, so every campaign checks it, not only a reinstall
        q = self.queue("plain", [{"coc": "FO4Port_X"}])
        c = self.camp([("p", q)])
        self.assertEqual(self.check(c), (True, []))
        self.plugins_txt(["*" + p for p in PLUGINS[1:]])
        self.assertIn("experiment plugin is inactive", " ".join(self.check(c)[1]))
        self.plugins_txt(["*" + p for p in PLUGINS])
        self.receipt(os.path.join(self.d, "v6c"))
        self.assertIn("another experiment is installed", " ".join(self.check(c)[1]))
        os.remove(os.path.join(self.sf, "Data", "FO4SFExp.install.json"))
        self.assertIn("no readable install record", " ".join(self.check(c)[1]))
        self.assertIn("names no installed_exp", " ".join(self.check(self.camp([("p", q)], installed_exp=None))[1]))

    def test_a_queue_with_no_launch_left_is_refused(self):
        # Codex on #391: a clean stop after the launch leaves relaunches 1, and --max-relaunch 1 refuses at once
        q = self.queue("a", [{"coc": "FO4Port_X"}, {"coc": "FO4Port_Y"}])
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"done": {"0000_t": "PASS"}, "relaunches": 1, "crashes": 0, "status": "stopped"}, f)
        ok, why = self.check(self.camp([("a", q)]))
        self.assertFalse(ok)
        self.assertIn("used 1 of 1 launch(es)", " ".join(why))
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"done": {"0000_t": "PASS"}, "relaunches": 0, "crashes": 0, "status": "stopped"}, f)
        self.assertTrue(self.check(self.camp([("a", q)]))[0])


    def test_travel_other_than_coc_and_relative_queues_are_refused(self):
        # Codex on #391: cow and player.moveto go where the holds can not see; a relative queue names another folder
        for travel in ("cow Commonwealth 0 0", "player.moveto 0001A2B3"):
            with self.subTest(travel=travel):
                q = self.queue(travel.split()[0].replace(".", "_"), [{"kind": "terrain", "cell": "", "world_coc": "FO4Port_X",
                                                                      "travel": travel}])
                ok, why = self.check(self.camp([("a", q)]))
                self.assertFalse(ok)
                self.assertIn("can not be checked against the holds", " ".join(why))
        q = self.queue("rel", [{"coc": "FO4Port_X"}])
        ok, why = self.check(self.camp([("a", os.path.relpath(q))]))
        self.assertFalse(ok)
        self.assertIn("is not a full path", " ".join(why))
        self.assertTrue(self.check(self.camp([("a", q)]))[0])


    def test_probe_moveto_booleans_and_a_relative_experiment_are_refused(self):
        # Codex on #391: MoveTo can load a held cell; JSON true passed as 1 and ran as "True"; a relative experiment
        # names two different rounds files from the check and from the judge in the checkout
        moveto = 'cgf "FO4SF_Probe.MoveTo" "FO4TerrainCore.esm" 2048 0.0 0.0 0.0'
        q = self.queue("mv", [{"coc": "FO4Port_X", "console_post": [moveto]}])
        ok, why = self.check(self.camp([("a", q)]))
        self.assertFalse(ok)
        self.assertIn("FO4SF_Probe.MoveTo in 0000_t", " ".join(why))
        q = self.queue("ok", [{"coc": "FO4Port_X"}])
        for k, v in (("max_relaunch", True), ("crash_budget", True), ("max_attempts", True), ("max_attempts", 1.0)):
            with self.subTest(k=k, v=v):
                ok, why = self.check(self.camp([("a", q)], caps=dict(CAPS, **{k: v})))
                self.assertFalse(ok)
                self.assertIn(k, " ".join(why))
        q = self.queue("relexp", [{"coc": "FO4Port_X"}], experiment="stage")
        c = self.camp([("a", q)])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q]
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("not a full path", " ".join(why))


class ScriptAndGateTests(Base):
    def test_the_chain_carries_the_caps_and_stops_on_the_gate(self):
        q = self.queue("doors_out", [{"coc": "FO4Port_Vault95"}])
        c = self.camp([("doors_out", q)])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q]
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(c, f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out, newline="") as f:
            text = f.read()
        self.assertIn("'--max-relaunch', '1', '--crash-budget', '1', '--min-free-gb', '43', '--dump-drive', 'D:\\'", text)
        self.assertIn("$jr = Py @('scripts\\bridge\\door_rounds.py', 'judge'", text)   # Codex on #391: the judge exit counts
        self.assertIn("'run', '--queue', '%s', '--starfield', '%s'" % (q, self.sf), text)
        self.assertIn("'--run-exit', \"$rc\", '--judge-exit', \"$jr\"", text)
        self.assertLess(text.index("$jr = Py"), text.index("'gate'"))
        # Codex on #391: the pin is checked again after the run, right before the judge reads its files
        self.assertLess(text.index("$rc = Py"), text.index("'--pin-only'"))
        self.assertLess(text.index("'--pin-only'"), text.index("$jr = Py"))
        self.assertLess(text.index("campaign_arm.py', 'check'"), text.index("testqueue.py"))
        self.assertLess(text.index("testqueue.py"), text.index("'gate'"))
        self.assertIn("\r\n", text)
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):      # a new file only
            ca.main(["script", "--campaign", cp, "--out", out])

    def test_the_chain_pins_the_manifest_bytes_it_was_written_from(self):
        # Codex on #391: a manifest edited while the chain is written must not be pinned in place of the parsed one
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)
        with open(cp, "rb") as f:
            parsed = hashlib.sha256(f.read()).hexdigest()
        load = ca.load_campaign

        def edited_after_load(path):
            got = load(path)
            with open(path, "w") as f:
                json.dump(self.camp([("a", q)], checkout="E:\\other"), f)
            return got
        with mock.patch.object(ca, "load_campaign", edited_after_load), redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out) as f:
            text = f.read()
        self.assertEqual(set(re.findall(r"'--sha256', '([0-9a-f]{64})'", text)), {parsed})
        self.assertIn(self.checkout, text)

    def test_a_refused_campaign_writes_no_chain(self):
        q = self.queue("walk", [{"coc": "FO4Core_RedRocketSpawn"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("walk", q)]), f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 1)
        self.assertFalse(os.path.exists(out))

    def test_the_chain_sets_the_launch_mode_and_runs_only_the_manifest_it_was_written_from(self):
        # Codex on #391: the script ignored "launch", and a manifest edited after the script still passed the check
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)], launch="exe"), f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out, newline="") as f:
            text = f.read()
        self.assertIn("$env:FO4SF_LAUNCH = 'exe'", text)
        digest = re.search(r"'--sha256', '([0-9a-f]{64})'", text).group(1)
        self.assertLess(text.index("FO4SF_LAUNCH"), text.index("testqueue.py"))
        self.assertIn("& $py -I @argv", text)                              # Codex on #391: isolated mode
        self.assertLess(text.index("if (Get-Process Starfield"), text.index("testqueue.py"))
        self.assertLess(text.index("$env:PATH = (Split-Path -Parent $py)"), text.index("testqueue.py"))
        self.assertIn("$env:FO4SF_PYTHON = $py", text)                     # Codex on #391: never the caller's
        self.assertLess(text.index("FO4SF_PYTHON"), text.index("testqueue.py"))

        def check(*extra):
            with redirect_stdout(io.StringIO()) as buf:
                return ca.main(["check", "--campaign", cp, *extra]), buf.getvalue()
        self.assertEqual(check("--sha256", digest)[0], 0)
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)                              # edited after the script was written
        rc, outp = check("--sha256", digest)
        self.assertEqual(rc, 1)
        self.assertIn("changed since the chain was written", outp)

    def test_each_queue_is_checked_again_against_its_pin_right_before_its_run(self):
        # Codex on #391: a later queue re-planned while an earlier one ran was loaded unchecked
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", qa), ("b", qb)]), f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out, newline="") as f:
            text = f.read()
        pins = re.findall(r"'--only', '(\w+)', '--queue-sha256', '([0-9a-f]{64})'", text)
        self.assertEqual([n for n, _ in pins], ["a", "a", "b", "b"])          # before and after each run
        self.assertLess(text.index("'--only', 'b'"), text.index("'--queue', '%s'" % qb))
        self.assertLess(text.index("'gate', '--game', '--queue', '%s'" % qa), text.index("'--only', 'b'"))
        digest = re.search(r"'--sha256', '([0-9a-f]{64})'", text).group(1)

        def recheck(name, pin):
            with redirect_stdout(io.StringIO()) as buf:
                return ca.main(["check", "--campaign", cp, "--sha256", digest, "--only", name,
                                "--queue-sha256", pin]), buf.getvalue()
        self.assertEqual(recheck("b", pins[2][1])[0], 0)
        with open(os.path.join(qb, "queue.json"), "w") as f:            # re-planned into the held arrival
            json.dump({"staging": self.staging, "plugin_sha256": tq.sha256(os.path.join(self.staging, "FO4Port.esm")),
                       "tests": [{"id": "0000_t", "coc": "FO4Core_RedRocketSpawn"}]}, f)
        rc, outp = recheck("b", pins[2][1])
        self.assertEqual(rc, 1)
        self.assertIn("changed since the chain was armed", outp)
        self.assertIn("held (red_rocket)", outp)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["check", "--campaign", cp, "--only", "c", "--queue-sha256", pins[0][1]]), 1)
            self.assertEqual(ca.main(["check", "--campaign", cp, "--only", "a"]), 1)

    def test_the_judges_definition_file_is_pinned_with_the_queue(self):
        # Codex on #391: door_rounds.py and presence.py read their rounds or presence file only at judge time
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        other = os.path.join(self.d, "other_rounds.json")
        with open(other, "w") as f:
            json.dump({"tests": []}, f)
        for judge, path in ((["--queue", q], os.path.join(self.stage, "rounds.json")), (["--queue", q, "--rounds", other], other)):
            with self.subTest(judge=judge):
                e = {"name": "a", "queue": q, "judge": ["scripts/bridge/door_rounds.py", "judge"] + judge}
                c = self.camp([])
                c["queues"] = [e]
                self.assertTrue(self.check(c)[0])
                pin = ca.queue_sha256(e)
                self.assertEqual(ca.recheck(e, c, set(), pin), [])
                with open(path, "w") as f:
                    json.dump({"tests": [{"test": 0}]}, f)                 # edited while an earlier queue ran
                self.assertIn("judge's definition file changed", " ".join(ca.recheck(e, c, set(), pin)))
        e = {"name": "a", "queue": q, "judge": ["scripts/bridge/presence.py", "judge", "--queue", q]}
        self.assertNotEqual(ca.queue_sha256(e), ca.queue_sha256({"name": "a", "queue": q}))
        for bad, want in ((["--rounds", "rel.json"], "relative"), (["--rounds=" + other], "once"),
                          (["--rounds", other, "--rounds", other], "once"), (["--rounds", other + ".gone"], "missing")):
            with self.subTest(bad=bad):
                c = self.camp([("a", q)])
                c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", q] + bad
                self.assertIn(want, " ".join(self.check(c)[1]))

    def test_a_door_judge_reads_the_rounds_its_queue_was_planned_from(self):
        # Codex on #391: queue.json rounds_sha256 pins the rounds.json plan-terrain read; an edit before arming would
        # have the judge score the run against other door definitions
        rounds = os.path.join(self.stage, "rounds.json")
        with open(rounds, "w") as f:
            json.dump({"tests": []}, f)
        q = self.queue("a", [{"coc": "FO4Port_X"}], rounds_sha256=tq.sha256(rounds))
        c = self.camp([])
        c["queues"] = [{"name": "a", "queue": q, "judge": ["scripts/bridge/door_rounds.py", "judge", "--queue", q]}]
        self.assertTrue(self.check(c)[0])
        with open(rounds, "w") as f:
            json.dump({"tests": [{"test": 0}]}, f)
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("not the rounds.json this queue was planned from", " ".join(why))

    def test_a_presence_judge_reads_the_presence_its_queue_was_planned_from(self):
        # Codex on #391: presence.py judge exits 0 on an emptied presence.json, so the file is pinned at planning
        presence = os.path.join(self.stage, "presence.json")
        with open(presence, "w") as f:
            json.dump({"tests": [{"ref": "0001"}]}, f)
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        c = self.camp([])
        c["queues"] = [{"name": "a", "queue": q, "judge": ["scripts/bridge/presence.py", "judge", "--queue", q]}]
        self.assertTrue(self.check(c)[0])
        with open(presence, "w") as f:
            json.dump({"tests": []}, f)
        ok, why = self.check(c)
        self.assertFalse(ok)
        self.assertIn("not the presence.json this queue was planned from", " ".join(why))
        q2 = self.queue("b", [{"coc": "FO4Port_X"}], presence_sha256=None)   # planned before the digest existed
        c["queues"] = [{"name": "b", "queue": q2, "judge": ["scripts/bridge/presence.py", "judge", "--queue", q2]}]
        self.assertIn("records no presence_sha256", " ".join(self.check(c)[1]))

    def test_powershell_strings_double_their_quotes(self):
        # Codex on #391: an apostrophe is a valid Windows path character; the check passed and the script exited
        self.assertEqual(ca.ps("D:\\Aaron's\\q"), "'D:\\Aaron''s\\q'")
        self.assertEqual(ca.ps("a\u2019b"), "'a\u2019\u2019b'")
        self.assertEqual(ca.psa(["x", "it's"]), "@('x', 'it''s')")
        with self.assertRaises(SystemExit):
            ca.ps("a\nb")

    def test_the_campaign_name_is_one_plain_line(self):
        # Codex on #391: chain() writes the name into its header comment; a line break would end the comment
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        for name in ("v6e\nStop-Process -Name Starfield", "", "a" * 81, "v6e; rm", None):
            with self.subTest(name=name):
                c = self.camp([("a", q)], name=name)
                self.assertIn("is not one plain line", " ".join(self.check(c)[1]))
                with self.assertRaises(SystemExit):
                    ca.chain(dict(c, caps=dict(CAPS)), os.path.join(self.d, "c.json"), set())
        self.assertTrue(self.check(self.camp([("a", q)], name="v6e night 2026-10-21"))[0])

    def test_the_chain_names_the_campaign_by_its_full_path(self):
        # Codex on #391: the chain runs Set-Location to the checkout before its check
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp = os.path.join(self.d, "c.json")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)
        old = os.getcwd()
        os.chdir(self.d)
        try:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ca.main(["script", "--campaign", "c.json", "--out", "chain.ps1"]), 0)
        finally:
            os.chdir(old)
        with open(os.path.join(self.d, "chain.ps1"), newline="") as f:
            text = f.read()
        self.assertIn("'check', '--campaign', '%s', '--sha256'" % os.path.abspath(cp), text)
        self.assertNotIn("--campaign 'c.json'", text)

    def test_the_chain_has_no_time_in_it(self):
        # Codex on #391: the same manifest and inputs write the same chain
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp = os.path.join(self.d, "c.json")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)
        texts = []
        for n in ("one.ps1", "two.ps1"):
            with redirect_stdout(io.StringIO()):
                ca.main(["script", "--campaign", cp, "--out", os.path.join(self.d, n)])
            with open(os.path.join(self.d, n), newline="") as f:
                texts.append(f.read())
        self.assertEqual(texts[0], texts[1])
        # Codex on #391: a missing checkout stops the chain before the first Python step
        self.assertIn(f"try {{ Set-Location -LiteralPath {ca.ps(self.checkout)} -ErrorAction Stop }} catch {{", texts[0])
        self.assertLess(texts[0].index("Set-Location"), texts[0].index("(Py @("))
        self.assertNotRegex(texts[0], r"\d{4}-\d\d-\d\dT")

    def test_repeated_pre_launch_options_are_refused(self):
        # Codex on #391: argparse runs the last --exp-dir, the check read the first
        for extra in (["--exp-dir", os.path.join(self.d, "v6c")], ["--starfield", "E:\\SF"],
                      ["--plugins", "Other.esm"]):
            with self.subTest(extra=extra):
                pre = [PY, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp,
                       "--starfield", STARFIELD_T, "--plugins", ",".join(PLUGINS), "--pack", *extra]
                q = self.queue("w" + str(len(extra[1])), [{"coc": "FO4Port_X"}], pre=pre)
                self.assertIn("2 times: at most 1", " ".join(self.check(self.camp([("w", q)]))[1]))
        pre = [PY, "scripts\\game\\exp_install.py", "install", "--exp-dir=" + self.exp,
               "--starfield", STARFIELD_T, "--plugins", ",".join(PLUGINS)]
        q = self.queue("eq", [{"coc": "FO4Port_X"}], pre=pre)
        self.assertIn("is not one it takes", " ".join(self.check(self.camp([("w", q)]))[1]))
        # Codex on #391: any option exp_install.py install does not take (or a repeated flag) exits 2 at launch
        base = [PY, "scripts\\game\\exp_install.py", "install", "--exp-dir", self.exp,
                "--starfield", STARFIELD_T, "--plugins", ",".join(PLUGINS), "--pack"]
        for extra, msg in ((["--typo"], "is not one it takes"), (["--pack"], "2 times"),
                           (["--needs", "a", "--needs", "b"], "2 times"), (["--needs"], "needs a value")):
            with self.subTest(extra=extra):
                q = self.queue("x" + str(len(extra)) + extra[-1][-1], [{"coc": "FO4Port_X"}], pre=base + extra)
                self.assertIn(msg, " ".join(self.check(self.camp([("w", q)]))[1]))

    def test_the_gate_passes_only_a_clean_finished_run(self):
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"status": "finished", "crashes": 0, "start_deaths": 0}, f)
        self.assertTrue(ca.gate(q, 0)[0])
        self.assertFalse(ca.gate(q, 4)[0])                                     # paused: tests left
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"status": "finished", "crashes": 1}, f)                 # a crash in the last test
        self.assertFalse(ca.gate(q, 0)[0])

    def test_the_gate_refuses_a_missing_unfinished_or_torn_state_and_a_failed_judge(self):
        # Codex on #391: a missing state.json or a running one passed as "clean: None" / "clean: running"
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        sp = os.path.join(q, "state.json")

        def cli(*extra):
            with redirect_stdout(io.StringIO()) as buf:
                rc = ca.main(["gate", "--queue", q, "--run-exit", "0", *extra])
            return rc, buf.getvalue()
        self.assertEqual(cli(), (1, f"STOP no readable state.json in {q}: nothing proves the queue ran\n"))
        for st, why in (({"status": "running", "crashes": 0}, "'running', not finished"),
                        ({"status": "new"}, "'new', not finished"), (["finished"], "no readable state.json")):
            with self.subTest(st=st):
                with open(sp, "w") as f:
                    json.dump(st, f)
                rc, out = cli()
                self.assertEqual(rc, 1)
                self.assertIn(why, out)
        with open(sp, "w") as f:
            f.write('{"status": "fini')
        self.assertIn("no readable state.json", ca.gate(q, 0)[1])
        with open(sp, "w") as f:
            json.dump({"status": "finished", "crashes": 0, "start_deaths": 0}, f)
        self.assertEqual(cli(), (0, "OK ran clean: finished (the verdicts are in the judge's report)\n"))
        self.assertEqual(cli("--judge-exit", "0")[0], 0)
        self.assertEqual(cli("--judge-exit", "2"), (1, "STOP the judge exited 2\n"))


if __name__ == "__main__":
    unittest.main()


class RunChainTests(Base):
    def setUp(self):
        super().setUp()
        self.calls, self.lines, self.envpy = [], [], []

    def fake(self, codes, state=None):
        def call(argv, env):
            self.assertEqual(argv[1], "-I")                                 # Codex on #391: isolated mode
            argv = argv[:1] + argv[2:]
            self.calls.append((argv[1:3], env.get("FO4SF_LAUNCH")))
            self.envpy.append(env.get("FO4SF_PYTHON"))
            self.assertTrue(env["PATH"].startswith(os.path.dirname(PY) + os.pathsep))  # cycle.ps1's python
            if state is not None and "testqueue.py" in argv[1]:
                q = argv[argv.index("--queue") + 1]
                with open(os.path.join(q, "state.json"), "w") as f:
                    json.dump(state, f)
            return codes.pop(0)
        return call

    def test_run_refuses_a_campaign_whose_checkout_is_not_this_one(self):
        # Codex on #391: the arm checks would be this checkout's and the runner another's
        here = mock.patch.object(ca, "checkout_here_why", REAL_HERE)
        here.start()
        self.addCleanup(here.stop)
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp_ = os.path.join(self.d, "c.json")
        with open(cp_, "w") as f:
            json.dump(self.camp([("a", q)]), f)
        with redirect_stdout(io.StringIO()) as buf, mock.patch.object(ca, "run_chain", return_value=0) as rc:
            self.assertEqual(ca.main(["run", "--campaign", cp_]), 1)
        rc.assert_not_called()
        self.assertIn("run campaign_arm.py from the campaign checkout", buf.getvalue())
        with open(cp_, "w") as f:
            json.dump(self.camp([("a", q)], checkout=ROOT, python=sys.executable), f)
        with redirect_stdout(io.StringIO()), mock.patch.object(ca, "run_chain", return_value=0) as rc:
            self.assertEqual(ca.main(["run", "--campaign", cp_]), 0)
        rc.assert_called_once()
        with open(cp_, "w") as f:                                         # and the chain it writes, too
            json.dump(self.camp([("a", q)]), f)
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(ca.main(["script", "--campaign", cp_, "--out", os.path.join(self.d, "c.ps1")]), 1)
        self.assertIn("run campaign_arm.py from the campaign checkout", buf.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.d, "c.ps1")))
        with redirect_stdout(io.StringIO()) as buf, mock.patch.object(ca, "check") as ck:  # and a standalone check
            self.assertEqual(ca.main(["check", "--campaign", cp_]), 1)
        ck.assert_not_called()
        self.assertIn("run campaign_arm.py from the campaign checkout", buf.getvalue())

    def test_a_queue_needs_a_full_plugins_load_index(self):
        # Codex on #391: the runner prepends it to every planned FormID
        for n, bad in enumerate((None, "", "2", "0x02", "FE", "ff", 2)):
            with self.subTest(plugin_index=bad):
                q = self.queue(f"pi{n}", [{"coc": "FO4Port_X"}], plugin_index=bad)
                if bad is None:
                    with open(os.path.join(q, "queue.json")) as f:
                        body = json.load(f)
                    del body["plugin_index"]
                    with open(os.path.join(q, "queue.json"), "w") as f:
                        json.dump(body, f)
                _, why, _ = ca.check_queue({"name": "a", "queue": q}, self.camp([("a", q)]), ca.releases(None))
                self.assertTrue(any("plugin_index" in w for w in why), why)
        q = self.queue("pi05", [{"coc": "FO4Port_X"}], plugin_index="05")
        _, why, _ = ca.check_queue({"name": "a", "queue": q}, self.camp([("a", q)]), ca.releases(None))
        self.assertFalse(any("plugin_index" in w for w in why), why)

    def test_the_gate_stops_on_a_form_missing_at_the_planned_index(self):
        # Codex on #391: a wrong index plans FormIDs of another plugin; the game finding no form is the proof
        q = self.queue("nb", [{"coc": "FO4Port_X"}])
        with open(os.path.join(q, "state.json"), "w") as f:
            json.dump({"status": "finished"}, f)
        self.assertTrue(ca.gate(q, 0)[0])
        with open(os.path.join(q, "results.jsonl"), "w") as f:
            f.write(json.dumps({"id": "0000_t", "verdict": "PASS", "class": ""}) + "\n{torn\n")
            f.write(json.dumps({"id": "0001_t", "verdict": "INCONCLUSIVE", "class": "NOBASE"}) + "\n")
        ok, why = ca.gate(q, 0)
        self.assertFalse(ok)
        self.assertIn("0001_t", why)
        self.assertIn("planned plugin index", why)

    def test_run_runs_again_on_the_campaigns_python(self):
        # Codex on #391: the arming checks import the judges; on another python they could refuse or pass otherwise
        real = mock.patch.object(ca, "on_campaign_python", REAL_ON_PY)
        real.start()
        self.addCleanup(real.stop)
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp_ = os.path.join(self.d, "c.json")
        with open(cp_, "w") as f:
            json.dump(self.camp([("a", q)], checkout=ROOT), f)
        done = mock.Mock(returncode=0)
        with redirect_stdout(io.StringIO()), mock.patch.object(ca, "run_chain") as rc, \
                mock.patch.object(ca.subprocess, "run", return_value=done) as sp:
            self.assertEqual(ca.main(["run", "--campaign", cp_]), 0)
        rc.assert_not_called()
        argv, kw = sp.call_args
        self.assertEqual(argv[0][:2], [PY, "-I"])
        self.assertEqual(argv[0][-3:], ["run", "--campaign", cp_])
        self.assertEqual(kw["env"]["FO4SF_ARM_REEXEC"], "1")
        with redirect_stdout(io.StringIO()) as buf, mock.patch.object(ca, "run_chain") as rc, \
                mock.patch.dict(os.environ, {"FO4SF_ARM_REEXEC": "1"}):  # still not it after the re-run: no loop
            self.assertEqual(ca.main(["run", "--campaign", cp_]), 1)
        rc.assert_not_called()
        self.assertIn("the campaign's python is", buf.getvalue())
        # and the chain it writes is checked there too
        with redirect_stdout(io.StringIO()), mock.patch.object(ca.subprocess, "run", return_value=done) as sp:
            self.assertEqual(ca.main(["script", "--campaign", cp_, "--out", os.path.join(self.d, "c.ps1")]), 0)
        self.assertEqual(sp.call_args[0][0][-5:], ["script", "--campaign", cp_, "--out", os.path.join(self.d, "c.ps1")])
        self.assertFalse(os.path.exists(os.path.join(self.d, "c.ps1")))       # written by the re-run, not here
        # and so is a standalone check
        with redirect_stdout(io.StringIO()), mock.patch.object(ca.subprocess, "run", return_value=done) as sp, \
                mock.patch.object(ca, "check") as ck:
            self.assertEqual(ca.main(["check", "--campaign", cp_]), 0)
        ck.assert_not_called()
        self.assertEqual(sp.call_args[0][0][-3:], ["check", "--campaign", cp_])

    def test_runs_each_queue_with_the_caps_and_stops_at_a_crash(self):
        os.environ["FO4SF_PYTHON"] = "C:\\other\\python.exe"
        self.addCleanup(os.environ.pop, "FO4SF_PYTHON", None)
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        c = self.camp([("a", qa), ("b", qb)], launch="exe")
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", qa]
        rc = ca.run_chain(c, self.lines.append, self.fake([0, 0], {"status": "finished", "crashes": 1}))
        self.assertEqual(rc, 1)
        self.assertEqual([a for a, _ in self.calls], [[os.path.join("scripts", "game", "testqueue.py"), "run"],
                                                      [os.path.join("scripts", "bridge", "door_rounds.py"), "judge"]])
        self.assertEqual({e for _, e in self.calls}, {"exe"})
        self.assertEqual(set(self.envpy), {PY})                          # Codex on #391: never the caller's python
        self.assertIn("a: STOP", self.lines[-1])

    def test_a_running_game_or_a_moved_checkout_stops_the_chain(self):
        # Codex on #391: the runner would reuse a game it started earlier, and run code the chain was not armed on
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        c = self.camp([("a", qa)])
        with mock.patch.object(ca, "game_running", return_value=4242):
            self.assertEqual(ca.run_chain(c, self.lines.append, self.fake([0])), 1)
        self.assertEqual(self.calls, [])
        self.assertIn("Starfield is running", self.lines[-1])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", qa]
        n = []
        with mock.patch.object(ca, "checkout_rev_why", side_effect=lambda camp: n.append(1) or
                               ("the checkout moved" if len(n) >= 3 else None)):
            self.assertEqual(ca.run_chain(c, self.lines.append, self.fake([0, 0], {"status": "finished"})), 1)
        self.assertEqual([a[1] for a, _ in self.calls], ["run"])                  # never judged
        self.assertEqual(self.lines[-1], "a: STOP after the run: the checkout moved")

    def test_a_queue_without_a_judge_is_checked_again_after_its_run(self):
        # Codex on #391: a route or checkout script changed during an unjudged run reached the gate unchecked
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        c = self.camp([("a", qa)])
        n = []
        with mock.patch.object(ca, "checkout_rev_why", side_effect=lambda camp: n.append(1) or
                               ("the checkout moved" if len(n) >= 3 else None)):
            self.assertEqual(ca.run_chain(c, self.lines.append, self.fake([0], {"status": "finished"})), 1)
        self.assertEqual(self.lines[-1], "a: STOP after the run: the checkout moved")
        cp = os.path.join(self.d, "c.json")
        with open(cp, "w") as f:
            json.dump(c, f)
        self.assertIn("'--pin-only'", ca.chain(c, cp, set()))

    def test_a_game_gone_after_a_run_stops_the_chain(self):
        # Codex on #391: a fresh runner does not know the game it should find and would launch another; after the
        # last queue the chain would end clean over a late crash
        qa, qb = self.queue("a", [{"coc": "FO4Port_X"}]), self.queue("b", [{"coc": "FO4Port_Y"}])
        c = self.camp([("a", qa), ("b", qb)])
        with mock.patch.object(ca, "game_kept_why", return_value="Starfield exited after its run"):
            self.assertEqual(ca.run_chain(c, self.lines.append, self.fake([0, 0], {"status": "finished"})), 1)
        self.assertEqual([a[1] for a, _ in self.calls], ["run"])                  # b never ran
        self.assertEqual(self.lines[-1], "a: STOP Starfield exited after its run")
        self.calls.clear()
        kept = iter([None, "Starfield exited after its run"])
        with mock.patch.object(ca, "game_kept_why", side_effect=lambda q: next(kept)):
            self.assertEqual(ca.run_chain(c, self.lines.append, self.fake([0, 0], {"status": "finished"})), 1)
        self.assertEqual([a[1] for a, _ in self.calls], ["run", "run"])           # the last queue's crash too
        self.assertEqual(self.lines[-1], "b: STOP Starfield exited after its run")
        cp = os.path.join(self.d, "c.json")
        with open(cp, "w") as f:
            json.dump(c, f)
        text = ca.chain(c, cp, set())
        self.assertIn("'before', '--queue', '%s')" % qa, text)                     # the first: no previous game
        self.assertIn("'before', '--queue', '%s', '--prev', '%s'" % (qb, qa), text)
        for q in (qa, qb):
            self.assertIn("'gate', '--game', '--queue', '%s'" % q, text)

    def test_a_game_is_owed_only_when_the_run_launched_or_inherited_one(self):
        # Codex on #391: a run of PRECONDITION or skipped tests finishes without ever launching the game
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        state = lambda **st: tq.save_atomic(os.path.join(q, "state.json"), dict({"status": "finished"}, **st))
        state(relaunches=0)
        with mock.patch.object(ca, "game_running", return_value=None):
            ca.game_before(q)
            self.assertIsNone(REAL_KEPT(q))                                    # nothing launched, nothing found
            state(relaunches=1)
            self.assertIn("exited after its run", REAL_KEPT(q))                # launched, then gone
        owned = mock.patch.object(tq.Controls, "owned_pid", return_value=4242)
        owned.start()
        self.addCleanup(owned.stop)
        with mock.patch.object(ca, "game_running", return_value=4242):
            self.assertIsNone(REAL_KEPT(q))
            ca.game_before(q)                                                  # inherited from the queue before
        with mock.patch.object(ca, "game_running", return_value=5151):    # Codex on #391: another Starfield
            self.assertIn("exited after its run", REAL_KEPT(q))
        state(relaunches=1)
        with mock.patch.object(ca, "game_running", return_value=None):
            self.assertIn("exited after its run", REAL_KEPT(q))
            # Codex on #391: gone between queues: the next queue does not start a new game over the crash
            q2 = self.queue("b", [{"coc": "FO4Port_Y"}])
            self.assertIn("exited after the previous queue", ca.game_before(q2, q))
            self.assertFalse(os.path.exists(os.path.join(q2, ca.GAME_SNAP)))
            with redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(ca.main(["before", "--queue", q2, "--prev", q]), 1)
            self.assertIn("STOP Starfield exited after the previous queue", buf.getvalue())
            self.assertIsNone(ca.game_before(q2))                              # the first queue: none owed
            os.remove(os.path.join(q, ca.GAME_SNAP))                           # no record: owed, fail closed
            self.assertIn("exited after its run", REAL_KEPT(q))
            with redirect_stdout(io.StringIO()) as buf, mock.patch.object(ca, "game_kept_why", REAL_KEPT):
                self.assertEqual(ca.main(["gate", "--game", "--queue", q, "--run-exit", "0"]), 1)
                self.assertEqual(ca.main(["gate", "--queue", q, "--run-exit", "0"]), 0)
            self.assertIn("STOP Starfield exited", buf.getvalue())

    def test_a_failed_judge_stops_the_chain(self):
        # Codex on #391: a judge exit 2 was only logged; the next queue ran and the chain ended 0
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        c = self.camp([("a", qa), ("b", qb)])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", qa]
        rc = ca.run_chain(c, self.lines.append, self.fake([0, 2], {"status": "finished", "crashes": 0}))
        self.assertEqual(rc, 1)
        self.assertEqual([a[1] for a, _ in self.calls], ["run", "judge"])          # b never started
        self.assertEqual(self.lines[-1], "a: STOP the judge exited 2")
        with open(os.path.join(qa, "state.json")) as f:                         # the run's evidence stays
            self.assertEqual(json.load(f)["status"], "finished")

    def test_a_run_that_wrote_no_state_stops_the_chain(self):
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        rc = ca.run_chain(self.camp([("a", qa), ("b", qb)]), self.lines.append, self.fake([0]))
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("a: STOP no readable state.json", self.lines[-1])

    def test_a_clean_chain_runs_every_queue(self):
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        rc = ca.run_chain(self.camp([("a", qa), ("b", qb)]), self.lines.append,
                          self.fake([0, 0], {"status": "finished", "crashes": 0}))
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual({e for _, e in self.calls}, {"steam"})

    def test_a_queue_changed_while_an_earlier_one_ran_stops_the_chain(self):
        # Codex on #391: the chain checked every queue once at the start
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        inner = self.fake([0, 0], {"status": "finished", "crashes": 0})

        def call(argv, env):
            with open(os.path.join(qb, "queue.json"), "a") as f:          # b re-planned while a runs
                f.write(" ")
            return inner(argv, env)
        rc = ca.run_chain(self.camp([("a", qa), ("b", qb)]), self.lines.append, call)
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.calls), 1)                                  # b never started
        self.assertIn("b: STOP before the run", self.lines[-1])
        self.assertIn("changed since the chain was armed", self.lines[-1])

    def test_a_judge_definition_changed_during_the_run_is_not_judged(self):
        # Codex on #391: the judge reads queue.json and rounds.json when it runs, hours after the pin was checked
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        c = self.camp([("a", qa)])
        c["queues"][0]["judge"] = ["scripts/bridge/door_rounds.py", "judge", "--queue", qa]
        inner = self.fake([0, 0], {"status": "finished", "crashes": 0})

        def call(argv, env):
            with open(os.path.join(self.stage, "rounds.json"), "a") as f:   # re-planned while a runs
                f.write(" ")
            return inner(argv, env)
        self.assertEqual(ca.run_chain(c, self.lines.append, call), 1)
        self.assertEqual(len(self.calls), 1)                                  # the judge never ran
        self.assertIn("a: STOP after the run", self.lines[-1])
        # the chain's --pin-only check: after the run state.json counts the launch, only the pin is compared
        cp = os.path.join(self.d, "c.json")
        with open(cp, "w") as f:
            json.dump(c, f)
        pin = ca.queue_sha256(c["queues"][0])
        with open(os.path.join(qa, "state.json"), "w") as f:
            json.dump({"done": {}, "relaunches": 1, "crashes": 1, "status": "stopped"}, f)
        argv = ["check", "--campaign", cp, "--only", "a", "--queue-sha256", pin]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(argv + ["--pin-only"]), 0)
            self.assertEqual(ca.main(argv), 1)                                 # the full check refuses the used queue
            with open(os.path.join(self.stage, "rounds.json"), "a") as f:
                f.write(" ")
            self.assertEqual(ca.main(argv + ["--pin-only"]), 1)

    def test_the_chain_fails_closed_when_python_can_not_be_run(self):
        # Codex on #391: a python that can not be run leaves $LASTEXITCODE as it was
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        cp, out = os.path.join(self.d, "c.json"), os.path.join(self.d, "chain.ps1")
        with open(cp, "w") as f:
            json.dump(self.camp([("a", q)]), f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["script", "--campaign", cp, "--out", out]), 0)
        with open(out) as f:
            text = f.read()
        self.assertIn("$global:LASTEXITCODE = $null", text)
        self.assertIn("if ($null -eq $c) { 1 } else { $c }", text)
        self.assertIn("Get-Command $py", text)
        self.assertNotIn("& $py scripts", text)                               # every step goes through Py
        self.assertEqual(text.count("LASTEXITCODE"), 2)                        # only inside Py

    def test_an_installed_map_markers_plugin_must_pass_its_order_check(self):
        # Codex on #391: cycle.ps1 runs map_markers_install.py order before every launch; it stops on a core that is
        # not the one the plugin was staged against, or on an inactive master
        import exp_install as ei
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        data = os.path.join(self.sf, "Data")
        with open(os.path.join(data, "FO4SFMapMarkers.esm"), "wb") as f:
            f.write(tes4("FO4SFMapMarkers.esm", ("Starfield.esm", "FO4TerrainCore.esm")))
        with open(os.path.join(data, "FO4SFMapMarkers - Main.ba2"), "wb") as f:
            f.write(b"BTDX")
        files = {n: ei.digest(os.path.join(data, n)) for n in ("FO4SFMapMarkers.esm", "FO4SFMapMarkers - Main.ba2")}
        core = ei.digest(os.path.join(data, "FO4TerrainCore.esm"))
        rec = os.path.join(data, "FO4SFMapMarkers.install.json")
        good = {"complete": True, "files": files, "masters_sha256": {"fo4terraincore.esm": core}}
        with open(rec, "w") as f:
            json.dump(good, f)
        self.assertEqual(self.check(self.camp([("a", q)])), (True, []))
        # Codex on #391: everything kit.order refuses too, not only the masters
        for bad, want in ((dict(good, complete=False), "incomplete"),
                          (dict(good, files={"FO4SFMapMarkers.esm": files["FO4SFMapMarkers.esm"]}), "coverage"),
                          (dict(good, files=dict(files, **{"FO4SFMapMarkers - Main.ba2": "0" * 64})), "changed")):
            with self.subTest(want=want):
                with open(rec, "w") as f:
                    json.dump(bad, f)
                ok, why = self.check(self.camp([("a", q)]))
                self.assertFalse(ok)
                self.assertTrue(any("map_markers_install.py order would stop" in w and want in w for w in why), why)
        with open(rec, "w") as f:
            json.dump(good, f)
        with open(os.path.join(data, "FO4SF.toggle.json"), "w") as f:
            json.dump({"off": ["FO4SFMapMarkers.esm"]}, f)              # held off and unticked: active exits 8
        self.assertIn("held off by plugin_toggle.py", " ".join(self.check(self.camp([("a", q)]))[1]))
        os.remove(os.path.join(data, "FO4SF.toggle.json"))
        with open(rec, "w") as f:
            json.dump(dict(good, masters_sha256={"fo4terraincore.esm": "0" * 64}), f)
        ok, why = self.check(self.camp([("a", q)]))
        self.assertFalse(ok)
        self.assertTrue(any("map_markers_install.py order would stop" in w and "not the core it was staged" in w
                            for w in why), why)
        entry = self.camp([("a", q)])["queues"][0]
        self.assertTrue(any("map_markers_install.py order" in w
                            for w in ca.recheck(entry, self.camp([("a", q)]), set(), ca.queue_sha256(entry))))

    def test_the_installed_experiment_is_checked_again_before_each_queue(self):
        # Codex on #391: an earlier queue's hours can change the installed experiment
        qa = self.queue("a", [{"coc": "FO4Port_X"}])
        qb = self.queue("b", [{"coc": "FO4Port_Y"}])
        inner = self.fake([0, 0], {"status": "finished", "crashes": 0})

        def call(argv, env):
            self.plugins_txt(["*" + p for p in PLUGINS[1:]])                # a plugin unticked while a runs
            return inner(argv, env)
        self.assertEqual(ca.run_chain(self.camp([("a", qa), ("b", qb)]), self.lines.append, call), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("b: STOP before the run", self.lines[-1])
        self.assertIn("experiment plugin is inactive", self.lines[-1])
        # and the chain's per-queue check (check --only) says the same
        cp = os.path.join(self.d, "c.json")
        c = self.camp([("a", qa), ("b", qb)])
        with open(cp, "w") as f:
            json.dump(c, f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ca.main(["check", "--campaign", cp, "--only", "b",
                                      "--queue-sha256", ca.queue_sha256(c["queues"][1])]), 1)

    def test_run_uses_the_campaign_checkout_and_python(self):
        # Codex on #391: run started the runner from this module's repo with this interpreter
        q = self.queue("a", [{"coc": "FO4Port_X"}])
        self.assertEqual(ca.run_chain(self.camp([("a", q)], checkout=os.path.join(self.d, "nope")), self.lines.append), 1)
        self.assertIn("checkout", self.lines[-1])
        seen = []
        import subprocess

        class Done:
            returncode = 0

        def fake_run(argv, cwd=None, env=None):
            seen.append((argv[0], cwd))
            if "testqueue.py" in argv[2]:
                with open(os.path.join(q, "state.json"), "w") as f:
                    json.dump({"status": "finished"}, f)
            return Done()
        old, subprocess.run = subprocess.run, fake_run
        try:
            rc = ca.run_chain(self.camp([("a", q)], checkout=self.d), self.lines.append)
        finally:
            subprocess.run = old
        self.assertEqual(rc, 0)
        self.assertEqual(seen, [(PY, self.d)])

    def test_holds_launch_and_released_come_from_the_campaign(self):
        q = self.queue("walk", [{"coc": "FO4Core_RedRocketSpawn"}])
        self.assertEqual(ca.run_chain(self.camp([("walk", q)]), self.lines.append, self.fake([])), 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(ca.run_chain(self.camp([("walk", q)], launch="cmd"), self.lines.append, self.fake([])), 1)
        self.assertEqual(ca.run_chain(self.camp([("walk", q)], released="red_rocket"), self.lines.append, self.fake([])), 1)
        rc = ca.run_chain(self.camp([("walk", q)], released=["red_rocket"]), self.lines.append,
                          self.fake([0], {"status": "finished"}))
        self.assertEqual(rc, 0)


class ShippedCampaignTests(unittest.TestCase):
    def test_the_v6e_campaign_has_the_caps_and_holds_the_red_rocket_walk(self):
        c = ca.read_campaign(os.path.join(ROOT, "scripts", "game", "campaigns", "v6e.json"))
        self.assertEqual(ca.check_caps(c["caps"]), [])
        self.assertEqual(c["released"], [])
        self.assertEqual(c["holds"], {"red_rocket": ["FO4Core_RedRocketSpawn"]})
        self.assertEqual([q["name"] for q in c["queues"]][-1], "walk")              # the held queue last
        self.assertIn(c["launch"], ca.LAUNCHES)
        self.assertNotIn("commit", c)                    # Codex on #397: `pin` writes the armed copy with it
        with open(os.path.join(ROOT, "docs", "testing", "v6e-queues.md"), encoding="utf-8") as f:
            doc = f.read()                               # Codex on #397: the documented steps must pass the check
        cmds = [l for l in doc.splitlines() if "testqueue.py plan" in l]
        self.assertTrue(cmds)
        self.assertFalse([l for l in cmds if "--fresh" in l])    # a fresh test outside the first queue is refused
        self.assertIn("campaign_arm.py run", doc)        # runs only through the campaign, which enforces the holds
        self.assertNotIn("one queue at a time", doc)
