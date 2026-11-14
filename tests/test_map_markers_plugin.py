"""dotnet/MapMarkers on a synthetic core (the actual terrain writer, dotnet/TerrainOverlays, on the synthetic master of
test_terrain_reference_identity with the map-marker template), never a game: the quest's Markers are the core's own
MapMarker REFRs in FormID order and LocalX / LocalY / LocalZ their written positions (docs/terrain/map-markers.md
"Markers in the merged world"); the plugin's overrides of those REFRs (the marker's own name shown, the arrival lifted,
docs/terrain/map-markers.md "Overrides"); plus the Papyrus script's contract (it cannot be compiled here)."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402

SCRIPT = ROOT / "scripts/mapmarkers/FO4SF_MapMarkers.psc"
PROGRAM = ROOT / "dotnet/MapMarkers/Program.cs"
Z_LIFT = 2.5                     # dotnet/MapMarkers DefaultZLift, metres above the core's sampled terrain height
Z_LIFT_STEP = 0.1                # dotnet/MapMarkers ZLiftStep: the build takes a lift on this grid only
USE_LOCATION_NAME, VISIBLE, STAR_MAP = 0x8, 0x1, 0x10   # map-marker FNAM bits (docs/terrain/map-markers.md)


def build(dotnet, project):
    proc = subprocess.run([dotnet, "build", str(ROOT / "dotnet" / project), "-c", "Release", "--nologo"],
                          capture_output=True, text=True)
    if proc.returncode:
        raise AssertionError(proc.stdout + proc.stderr)
    return ROOT / f"dotnet/{project}/bin/Release/net9.0/{project}.dll"


class MapMarkersPluginTests(unittest.TestCase):
    run_writer = tri.TerrainReferenceIdentityTests.run_writer

    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual writer test")
        fixture = build(cls.dotnet, "TerrainIdentityFixture")
        cls.writer = Path(os.environ.get("FO4SF_TERRAIN_WRITER", build(cls.dotnet, "TerrainOverlays")))
        cls.tool = build(cls.dotnet, "MapMarkers")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-mapmarkers-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.master = cls.root / "master/Starfield.esm"
        subprocess.run([cls.dotnet, str(fixture), str(cls.master), "map-marker"], capture_output=True, check=True)
        cls.params = {                                   # test_terrain_map_marker_writer's synthetic overlay
            "plugin": "Synthetic.esm", "hmin": 0, "hmax": 1, "alignment": "absolute", "hnam": 0,
            "objects": "objects.json", "overlays": [{"world": "SyntheticWorld", "block": "SyntheticBlock",
            "location": "SyntheticLocation", "tag": "Synthetic", "n": 2, "cell_min": 0, "cell_max": 1,
            "btd_path": "Terrain/Synthetic.btd", "fnam": [0] * 4, "bounds_min_m": 0, "bounds_max_m": 200,
            "spawn": [1, 1, 2], "spawn_cell": [1, 0], "coc": "SyntheticSpawn",
            "anchor": {"form_id": 0x800, "edid": "SyntheticAnchor", "local": [1, 1, 2]}}]}
        cls.objects = {"world": "SyntheticWorld", "bases": [{"edid": "SyntheticBase", "model": "synthetic.nif"}],
                       "refs": [{"src": "000001:Synthetic.esm", "base": 0, "cell": [0, 0], "pos": [1, 2, 3],
                                 "rot": [0, 0, 0], "scale": 1, "disabled": False}]}
        ov = cls.params["overlays"][0]
        cls.markers = [{"tag": "RedRocket", "name": "Red Rocket Truck Stop", "pos": ov["spawn"], "cell": [0, 0]},
                       {"tag": "Sanctuary", "name": "Sanctuary Hills", "pos": [150.0, 50.0, 1.0], "cell": [1, 0]},
                       {"tag": "Concord", "name": "Concord", "pos": [50.0, 150.0, 1.5], "cell": [0, 1]}]
        ov["map_markers"] = cls.markers
        proc, cls.stage = cls.run_writer(cls, cls.objects, "core")
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.core = cls.stage / "Synthetic.esm"
        cls.ids = json.loads((cls.stage / "formids.json").read_text())["map_marker_refs"]["SyntheticWorld"]

    def tool_run(self, *argv):
        return subprocess.run([self.dotnet, str(self.tool), *map(str, argv)], capture_output=True, text=True)

    def test_build_lists_every_core_marker_with_its_written_position(self):
        out = self.root / "plugin"
        proc = self.tool_run("build", "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("all checks pass", check.stdout)
        recs = tri.records(plugin)
        # the quest, plus an override of each core marker under the core's worldspace and persistent cell: nothing else
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"REFR"), sorted(int(v, 16) for v in self.ids.values()))
        self.assertEqual(sorted(r[0] for r in recs.values()), [b"CELL", b"QUST"] + [b"REFR"] * 3 + [b"WRLD"])
        for m in self.markers:
            sig, payload, _, flags = recs[int(self.ids[m["tag"]], 16)]
            self.assertEqual(flags & 0xC00, 0x400, m["tag"])                       # persistent, enabled
            fnam = struct.unpack("<I", tlw.field(payload, b"FNAM"))[0]
            self.assertEqual(fnam & (USE_LOCATION_NAME | VISIBLE), VISIBLE, m["tag"])  # its own name, visible
            self.assertEqual(tlw.field(payload, b"FULL"), m["name"].encode() + b"\0")
            x, y, z = struct.unpack_from("<fff", tlw.field(payload, b"DATA"))
            self.assertEqual([x, y], [float(v) for v in m["pos"][:2]])
            self.assertAlmostEqual(z, m["pos"][2] + Z_LIFT, places=4)
        self.assertEqual(check.stdout.count("  override "), 3)
        self.assertIn(f"overridden (own name shown, lifted {Z_LIFT} m)", proc.stdout)
        sig, payload, _, flags = recs[0x800]
        self.assertEqual(sig, b"QUST")
        vmad = tlw.field(payload, b"VMAD")
        self.assertIsNotNone(vmad)
        self.assertEqual(struct.unpack_from("<hH", vmad), (6, 2))
        self.assertIn(b"FO4SF_MapMarkers", vmad)
        # the three markers in FormID order, each a core reference (master index 1, after Starfield.esm)
        want = sorted(int(v, 16) for v in self.ids.values())
        self.assertEqual(len(want), 3)
        got = [f & 0xFFFFFF for f in self.object_list(vmad)]
        self.assertEqual(got, want)
        # masters: Starfield.esm (the overrides' base STAT) then the core; the quest's references are the core's
        self.assertTrue(all(f >> 24 == 1 for f in self.object_list(vmad)))
        # LocalX in FormID order equals the positions the writer was given; LocalZ the lifted height the override holds
        by_id = {int(self.ids[m["tag"]], 16): m["pos"] for m in self.markers}
        self.assertIn(f"LocalX: {', '.join(self.num(by_id[i][0]) for i in want)}", check.stdout)
        self.assertIn(f"LocalZ: {', '.join(self.num(by_id[i][2] + Z_LIFT) for i in want)}", check.stdout)

    def test_z_lift_is_an_option_and_the_check_follows_it(self):
        out = self.root / "plugin-flat"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--z-lift", "0")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        recs = tri.records(plugin)
        for m in self.markers:
            z = struct.unpack_from("<fff", tlw.field(recs[int(self.ids[m["tag"]], 16)][1], b"DATA"))[2]
            self.assertAlmostEqual(z, m["pos"][2], places=4)
        self.assertEqual(self.tool_run("check", plugin, self.core, "--z-lift", "0").returncode, 0)
        other = self.tool_run("check", plugin, self.core)               # the default lift is not what was built
        self.assertEqual(other.returncode, 1, other.stdout)
        self.assertIn(f"not the core's {self.num(self.markers[0]['pos'][2])} lifted {Z_LIFT} m", other.stdout)
        bad = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-bad-lift", "--z-lift", "-1")
        self.assertEqual(bad.returncode, 2)
        # lifts come in steps of Z_LIFT_STEP: a change between builds smaller than the script's ZTolerance would
        # never reach a saved game (Codex on #483), so the build refuses a lift off that grid
        fine = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-fine-lift", "--z-lift", "0.55")
        self.assertEqual(fine.returncode, 2, fine.stdout + fine.stderr)
        self.assertIn("multiple of 0.1 m", fine.stderr)
        self.assertIn("ZTolerance (0.05 m)", fine.stderr)
        stepped = self.root / "plugin-step-lift"
        step = self.tool_run("build", "--core", self.core, "--out", stepped, "--z-lift", "0.5")
        self.assertEqual(step.returncode, 0, step.stdout + step.stderr)
        self.assertEqual(self.tool_run("check", stepped / "FO4SFMapMarkers.esm", self.core, "--z-lift", "0.5").returncode, 0)

    def test_check_rejects_an_override_that_still_uses_the_location_name(self):
        out = self.root / "plugin-locname"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        at = data.index(b"FNAM\x04\x00") + 6                       # the first override's map-marker flags
        struct.pack_into("<I", data, at, struct.unpack_from("<I", data, at)[0] | USE_LOCATION_NAME)
        plugin.write_bytes(bytes(data))
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("override still uses the location's name", check.stdout)

    def test_check_rejects_a_world_copy_that_no_longer_matches_the_core(self):
        # the plugin carries the core's WRLD and persistent CELL as the overrides' containers; it loads after the
        # core, so a copy taken before a core rebuild (a changed world flag) would undo the rebuild: check compares
        # both records with the core's, so a stale stage fails before it is installed
        out = self.root / "plugin-stale-world"
        proc = self.tool_run("build", "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        fresh = self.tool_run("check", plugin, self.core)
        self.assertEqual(fresh.returncode, 0, fresh.stdout)
        # the writer gives the synthetic world the real one's SmallWorld flag and HNAM 0 (#495)
        self.assertIn("  worldspace 000803:Synthetic.esm SyntheticWorld: flags SmallWorld, HNAM [0], as the core's", fresh.stdout)
        data = bytearray(plugin.read_bytes())
        rec = data.index(b"WRLD", data.index(b"WRLD") + 4)            # the record, after the group label
        at = data.index(b"EDID", rec) + 6                             # a stale copy: its EditorID changes case
        data[at] ^= 0x20
        plugin.write_bytes(bytes(data))
        stale = self.tool_run("check", plugin, self.core)
        self.assertEqual(stale.returncode, 1, stale.stdout)
        self.assertIn("worldspace record differs from the core's (a core rebuilt since the stage: stage again)", stale.stdout)
        self.assertIn("NOT the core's", stale.stdout)

    def test_world_takes_the_border_probe_variant_and_the_check_expects_it(self):
        # --world nosmall / city: the WRLD copy as dotnet/BorderProbe's variant (SmallWorld cleared; city HNAM 5),
        # the marker overrides untouched; check wants the same --world, and fails the copy under any other
        control = self.root / "plugin-world-control"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", control).returncode, 0)
        for world, flags, hnam in [("nosmall", "0", "0"), ("city", "0", "5")]:     # the core's: SmallWorld, HNAM [0]
            out = self.root / f"plugin-world-{world}"
            proc = self.tool_run("build", "--core", self.core, "--out", out, "--world", world)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(f"world copy --world {world} (SmallWorld cleared, HNAM {'5' if world == 'city' else 'as the core'}", proc.stdout)
            plugin = out / "FO4SFMapMarkers.esm"
            check = self.tool_run("check", plugin, self.core, "--world", world)
            self.assertEqual(check.returncode, 0, check.stdout)
            self.assertIn(f"  worldspace 000803:Synthetic.esm SyntheticWorld: flags {flags}, HNAM [{hnam}], as the core's with --world {world}",
                          check.stdout)
            self.assertEqual(check.stdout.count("  override "), 3)       # the marker overrides, as under control
            # the bytes: the WRLD record's DATA flags (0: SmallWorld 0x1 gone) and HNAM
            data = plugin.read_bytes()
            rec = data.index(b"WRLD", data.index(b"WRLD") + 4)
            body = data[rec + 24: rec + 24 + int.from_bytes(data[rec + 4: rec + 8], "little")]
            at = body.index(b"DATA")
            flag_bytes = body[at + 6: at + 6 + int.from_bytes(body[at + 4: at + 6], "little")]
            self.assertTrue(flag_bytes and not any(flag_bytes), flag_bytes)
            at = body.index(b"HNAM")                                      # city sets 5; nosmall keeps the core's 0
            self.assertEqual(body[at + 6: at + 6 + int.from_bytes(body[at + 4: at + 6], "little")], b"\5" if world == "city" else b"\0")
            plain = self.tool_run("check", plugin, self.core)             # another --world: not this stage's
            self.assertEqual(plain.returncode, 1, plain.stdout)
            self.assertIn("NOT the core's", plain.stdout)
            self.assertIn("worldspace record differs from the core's (a core rebuilt since the stage: stage again)", plain.stdout)
            crossed = self.tool_run("check", control / "FO4SFMapMarkers.esm", self.core, "--world", world)
            self.assertEqual(crossed.returncode, 1, crossed.stdout)
            self.assertIn(f"NOT the core's with --world {world}", crossed.stdout)
            self.assertIn(f"worldspace record differs from the core's with --world {world} (a stage with another --world, or a core rebuilt since it: stage again)",
                          crossed.stdout)
        other = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-world-other", "--world", "hnam5")
        self.assertEqual(other.returncode, 2)
        self.assertIn("--world hnam5: want control", other.stderr)

    def test_many_markers_split_into_quests_of_20(self):
        # a quest places one marker at a time, about a frame for each read (a marker every 0.45 s at 100 a quest:
        # 45 s for the first placement, fo4sf_map.0.log 2026-10-31), and the quests run side by side
        params = copy.deepcopy(self.params)
        params["overlays"][0]["map_markers"] = [
            {"tag": f"M{k:03d}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
            for k in range(205)]
        saved, type(self).params = type(self).params, params
        try:
            proc, many = self.run_writer(self.objects, "core-many")
        finally:
            type(self).params = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = self.root / "plugin-many"
        built = self.tool_run("build", "--core", many / "Synthetic.esm", "--out", out)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("11 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", many / "Synthetic.esm")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        # eleven quests reach 0x80A of this plugin, which core markers' low bits can match: read by full FormID
        recs = self.records_by_form(out / "FO4SFMapMarkers.esm")
        quests = [0x02000000 | q for q in range(0x800, 0x80B)]
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"QUST"), quests)
        self.assertEqual(sum(1 for r in recs.values() if r[0] == b"REFR"), 205)    # one override per marker
        lists = [self.object_list(tlw.field(recs[q][1], b"VMAD")) for q in quests]
        self.assertEqual([len(x) for x in lists], [20] * 10 + [5])
        ids = [f & 0xFFFFFF for x in lists for f in x]
        self.assertEqual(ids, sorted(ids))                                     # FormID order across the quests
        self.assertEqual(len(set(ids)), 205)
        for q in quests:                                                       # 20 or fewer: the script's own 40
            self.assertNotIn(b"MaxMoves", tlw.field(recs[q][1], b"VMAD"))
        # a plugin missing its last quest no longer matches the core
        short = self.root / "plugin-many-short"
        three = self.tool_run("build", "--core", self.core, "--out", short)
        self.assertEqual(three.returncode, 0)
        bad = self.tool_run("check", short / "FO4SFMapMarkers.esm", many / "Synthetic.esm")
        self.assertEqual(bad.returncode, 1, bad.stdout)
        self.assertIn("1 quest(s) for 205 marker(s): 11 wanted (20 per quest)", bad.stdout)

    # sha256 of the synthetic core above and of the plugin main's dotnet/MapMarkers (5ffe8ff0, before --extra) built
    # from it with no options: a build without --extra must stay those bytes (Grok on #519)
    SYNTHETIC_CORE_SHA256 = "642628d4b3fad1397558f6a48728a7e3f3e90f09ffa58ce31a99d873b6f1dd40"
    PLAIN_PLUGIN_SHA256 = "750a80440b07bd8b042d51c1bd6d365f8d41cc440492183ed9ce4bb93811065d"

    def test_without_extra_the_plugin_is_byte_for_byte_the_one_before_extra(self):
        core = hashlib.sha256(self.core.read_bytes()).hexdigest()
        self.assertEqual(core, self.SYNTHETIC_CORE_SHA256, "the synthetic core changed (TerrainOverlays or its fixture): "
                         "rebuild the plain plugin with the last MapMarkers before the change and record both hashes")
        out = self.root / "plain"
        proc = self.tool_run("build", "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(hashlib.sha256((out / "FO4SFMapMarkers.esm").read_bytes()).hexdigest(), self.PLAIN_PLUGIN_SHA256)

    EXTRA = [{"tag": "M01F2A9", "name": "Abernathy Farm", "src": "01F2A9:Fallout4.esm", "pos": [120.0, 30.0, 4.0], "cell": [1, 0]},
             {"tag": "M01F2AA", "name": "Starlight Drive In", "src": "01F2AA:Fallout4.esm", "pos": [40.0, 160.0, 6.5], "cell": [0, 1]}]

    def extra_file(self, name, markers):
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({"markers": markers}))
        return path

    def test_extra_markers_are_the_plugins_own_with_lcsr_rows(self):
        # --extra (make_map_markers.py stage --fo4-map-markers): FO4's other markers as REFRs of this plugin, copies of
        # the core's first marker in the core world's persistent cell, one MapMarkerRefType LCSR row each in an
        # override of the core's Location, and listed after the core's markers in the quest
        extra = self.extra_file("extra", self.EXTRA)
        out = self.root / "plugin-extra"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("3 marker(s) overridden (own name shown, lifted 2.5 m), 2 of its own (--extra)", proc.stdout)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core, "--extra", extra)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("2 marker(s) of this plugin, 2 in --extra", check.stdout)
        recs = tri.records(plugin)
        core_ids = sorted(int(v, 16) for v in self.ids.values())
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"REFR"), core_ids + [0x900, 0x901])
        self.assertEqual(sorted(r[0] for r in recs.values()), [b"CELL", b"LCTN", b"QUST"] + [b"REFR"] * 5 + [b"WRLD"])
        core_recs = tri.records(self.core)
        cell = next(k for k, r in recs.items() if r[0] == b"CELL")
        template = core_recs[core_ids[0]][1]
        for k, m in zip((0x900, 0x901), self.EXTRA):
            sig, payload, owner, flags = recs[k]
            self.assertEqual(owner, cell, m["tag"])                                    # in the persistent cell copy
            self.assertEqual(flags & 0xC00, 0x400, m["tag"])                          # persistent, enabled
            self.assertEqual(tlw.field(payload, b"NAME"), struct.pack("<I", 0x10))    # Starfield.esm's MapMarker
            self.assertEqual(tlw.field(payload, b"EDID"), f"SyntheticWorldMapMarker{m['tag']}".encode() + b"\0")
            fnam = struct.unpack("<I", tlw.field(payload, b"FNAM"))[0]
            self.assertEqual(fnam & (USE_LOCATION_NAME | VISIBLE), VISIBLE, m["tag"])
            self.assertEqual(tlw.field(payload, b"TNAM"), tlw.field(template, b"TNAM"))  # the core's icon type
            self.assertEqual(tlw.field(payload, b"FULL"), m["name"].encode() + b"\0")
            x, y, z = struct.unpack_from("<fff", tlw.field(payload, b"DATA"))
            self.assertEqual([x, y], m["pos"][:2])
            self.assertAlmostEqual(z, m["pos"][2] + Z_LIFT, places=4)
        # the Location: the core's rows unchanged, then one row per own marker (own index 2, after Starfield.esm and
        # the core), the cell's grid packed as the core writes it (the core's Sanctuary row has cell [1, 0])
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf import map_markers
        loc = next(k for k, r in recs.items() if r[0] == b"LCTN")
        rows = map_markers.parse_lcsr(tlw.field(recs[loc][1], b"LCSR"))
        core_rows = map_markers.parse_lcsr(tlw.field(core_recs[loc][1], b"LCSR"))
        self.assertEqual(len(core_rows), 3)
        self.assertEqual([r["refr"] & 0xFFFFFF for r in rows[:3]], [r["refr"] & 0xFFFFFF for r in core_rows])
        self.assertEqual([r["refr"] for r in rows[3:]], [0x02000900, 0x02000901])
        self.assertEqual({r["lcrt"] for r in rows}, {map_markers.MAPMARKER_REF_TYPE})
        self.assertEqual({r["wrld"] for r in rows}, {rows[0]["wrld"]})
        self.assertEqual({r["tail"] for r in rows}, {map_markers.LCSR_TAIL})
        sanctuary = int(self.ids["Sanctuary"], 16)
        self.assertEqual(rows[3]["pad"], next(r["pad"] for r in core_rows if r["refr"] & 0xFFFFFF == sanctuary))
        self.assertNotEqual(rows[3]["pad"], rows[4]["pad"])
        # the quest: the core's markers in FormID order (index 1), then the plugin's own (index 2)
        got = self.object_list(tlw.field(recs[0x800][1], b"VMAD"))
        self.assertEqual(got, [0x01000000 | i for i in core_ids] + [0x02000900, 0x02000901])
        by_id = {int(self.ids[m["tag"]], 16): m["pos"] for m in self.markers}
        xs = [by_id[i][0] for i in core_ids] + [m["pos"][0] for m in self.EXTRA]
        zs = [by_id[i][2] + Z_LIFT for i in core_ids] + [m["pos"][2] + Z_LIFT for m in self.EXTRA]
        self.assertIn(f"LocalX: {', '.join(self.num(v) for v in xs)}", check.stdout)
        self.assertIn(f"LocalZ: {', '.join(self.num(v) for v in zs)}", check.stdout)

    def test_check_wants_the_same_extra_markers(self):
        extra = self.extra_file("extra-same", self.EXTRA)
        out = self.root / "plugin-extra-same"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        bare = self.tool_run("check", plugin, self.core)                    # without --extra: they are not expected
        self.assertEqual(bare.returncode, 1, bare.stdout)
        self.assertIn("is a REFR of this plugin that --extra and --landing do not list", bare.stdout)
        self.assertIn("1 Location record(s) without --extra or --landing", bare.stdout)
        moved = copy.deepcopy(self.EXTRA)
        moved[1]["pos"][0] += 1.0
        far = self.tool_run("check", plugin, self.core, "--extra", self.extra_file("extra-moved", moved))
        self.assertEqual(far.returncode, 1, far.stdout)
        self.assertIn("not --extra's (41, 160, 6.5) lifted 2.5 m", far.stdout)
        renamed = copy.deepcopy(self.EXTRA)
        renamed[0]["cell"] = [0, 0]                                          # another grid: the LCSR row differs
        grid = self.tool_run("check", plugin, self.core, "--extra", self.extra_file("extra-grid", renamed))
        self.assertEqual(grid.returncode, 1, grid.stdout)
        self.assertIn("LCSR rows are not the core's followed by one MapMarkerRefType row per own marker", grid.stdout)
        plain = self.root / "plugin-extra-none"                              # a plugin without them, checked with them
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", plain).returncode, 0)
        missing = self.tool_run("check", plain / "FO4SFMapMarkers.esm", self.core, "--extra", extra)
        self.assertEqual(missing.returncode, 1, missing.stdout)
        self.assertIn("(M01F2A9 \"Abernathy Farm\", --extra) is missing", missing.stdout)
        self.assertIn("Location records []: want one override of", missing.stdout)

    def test_check_rejects_a_location_copy_that_no_longer_matches_the_core(self):
        extra = self.extra_file("extra-loc", self.EXTRA)
        out = self.root / "plugin-extra-loc"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        rec = data.index(b"LCTN", data.index(b"LCTN") + 4)                   # the record, after the group label
        at = data.index(b"EDID", rec) + 6                                     # a stale copy: its EditorID changes case
        data[at] ^= 0x20
        plugin.write_bytes(bytes(data))
        stale = self.tool_run("check", plugin, self.core, "--extra", extra)
        self.assertEqual(stale.returncode, 1, stale.stdout)
        self.assertIn("Location override differs from the core's beyond its LCSR rows (a core rebuilt since the stage: stage again)",
                      stale.stdout)

    def test_build_refuses_a_bad_extra_file(self):
        for name, markers, want in [
                ("extra-repeat", [self.EXTRA[0], dict(self.EXTRA[1], tag="m01f2a9")], "tag M01F2A9 repeats"),
                ("extra-noname", [dict(self.EXTRA[0], name="")], "M01F2A9: no name"),
                ("extra-badtag", [dict(self.EXTRA[0], tag="M 1")], 'tag "M 1": want letters, digits or _'),
                ("extra-short", [dict(self.EXTRA[0], pos=[1.0, 2.0])], "M01F2A9: pos needs 3 finite numbers")]:
            proc = self.tool_run("build", "--core", self.core, "--out", self.root / f"plugin-{name}", "--extra",
                                 self.extra_file(name, markers))
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn(want, proc.stderr)
        # a marker the core already has (a core built with --fo4-map-markers) is not added twice
        dup = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-extra-dup", "--extra",
                            self.extra_file("extra-dup", [dict(self.EXTRA[0], tag="Sanctuary")]))
        self.assertEqual(dup.returncode, 1, dup.stdout + dup.stderr)
        self.assertIn("the core already has a record SyntheticWorldMapMarkerSanctuary", dup.stderr)

    def test_extra_markers_fill_the_quests_after_the_core_markers(self):
        # 3 core markers and 205 of the plugin's own: ten quests of 20 and one of 8, each with its own move budget
        many = [{"tag": f"M{k:06X}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
                for k in range(205)]
        extra = self.extra_file("extra-many", many)
        out = self.root / "plugin-extra-many"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("11 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", self.core, "--extra", extra)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        # the third quest is 0x802 of this plugin, the core's Location override 0x802 of the core: read by full FormID
        recs = self.records_by_form(out / "FO4SFMapMarkers.esm")
        lists = [self.object_list(tlw.field(recs[0x02000000 | q][1], b"VMAD")) for q in range(0x800, 0x80B)]
        self.assertEqual([len(x) for x in lists], [20] * 10 + [8])
        flat = [f for x in lists for f in x]
        self.assertEqual([f >> 24 for f in flat], [1] * 3 + [2] * 205)       # the core's first, then the plugin's
        self.assertEqual([f & 0xFFFFFF for f in flat[3:]], list(range(0x900, 0x900 + 205)))
        nxt = struct.unpack_from("<I", (out / "FO4SFMapMarkers.esm").read_bytes(), 24 + 4 + 2 + 8)[0]   # HEDR next id
        self.assertEqual(nxt, 0x900 + 205)

    @staticmethod
    def landing(**kw):
        """fo4sf.map_markers.landing_spot on the synthetic overlay (0..200 m): the pad at (100, 100), flat ground at 1 m."""
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf import map_markers
        return map_markers.landing_spot(100.0, 100.0, (0, 200), lambda x, y: 1.0, Z_LIFT, **kw)

    def landing_file(self, name, spot):
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({"landing": spot}))
        return path

    def test_landing_spot_is_landingoverlay01s_four_references_and_rows(self):
        # --landing (make_map_markers.py stage --landing): the pad, its landing-zone trigger, the "Landing Area" marker
        # and its heading, persistent in the world copy, linked as LandingOverlay01's, with its three LCSR rows after
        # --extra's, and listed after the plugin's markers in the quest
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf import map_markers
        spot = self.landing()
        landing, extra = self.landing_file("landing", spot), self.extra_file("extra-landing", self.EXTRA)
        out = self.root / "plugin-landing"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra, "--landing", landing)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("2 of its own (--extra), a landing spot (--landing RedRocketNorth)", proc.stdout)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core, "--extra", extra, "--landing", landing)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertEqual(check.stdout.count("  landing 0008F"), 4)
        recs = tri.records(plugin)
        core_ids = sorted(int(v, 16) for v in self.ids.values())
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"REFR"),
                         core_ids + [0x8F0, 0x8F1, 0x8F2, 0x8F3, 0x900, 0x901])
        cell = next(k for k, r in recs.items() if r[0] == b"CELL")
        bases = {0x8F0: 0x7145, 0x8F1: 0x267F4C, 0x8F2: 0x10, 0x8F3: 0x34}   # pad, trigger, MapMarker, XMarkerHeading
        parts = dict(zip((0x8F0, 0x8F1, 0x8F2, 0x8F3), ("pad", "trigger", "marker", "heading")))
        for k, part in parts.items():
            sig, payload, owner, flags = recs[k]
            self.assertEqual(owner, cell, part)                                     # all four persistent in the copy
            self.assertEqual(flags & 0xC00, 0x400, part)
            self.assertEqual(tlw.field(payload, b"NAME"), struct.pack("<I", bases[k]), part)   # Starfield.esm's bases
            got = struct.unpack_from("<6f", tlw.field(payload, b"DATA"))
            for g, w in zip(got, spot[part]["pos"] + spot[part]["rot"]):
                self.assertAlmostEqual(g, w, places=3, msg=part)
        links = lambda k: [struct.unpack("<II", d) for s, d in tlw.subrecords(recs[k][1]) if s == b"XLKR"]  # noqa: E731
        self.assertEqual(links(0x8F0), [(0x267F4D, 0x020008F1), (0x3A866F, 0x020008F2)])   # trigger, marker
        self.assertEqual(links(0x8F2), [(0, 0x020008F3)])                                   # the heading, no keyword
        self.assertEqual(links(0x8F1) + links(0x8F3), [])
        self.assertIsNotNone(tlw.field(recs[0x8F1][1], b"XPRM"))                            # the trigger's box
        marker = recs[0x8F2][1]
        self.assertEqual(struct.unpack("<I", tlw.field(marker, b"FNAM"))[0], 0x33)           # LandingOverlay01's
        self.assertEqual(tlw.field(marker, b"FULL"), b"Landing Area\0")
        # the Location: the core's rows, --extra's, then the marker's MapMarkerRefType row and the pad's two
        loc = next(k for k, r in recs.items() if r[0] == b"LCTN")
        rows = map_markers.parse_lcsr(tlw.field(recs[loc][1], b"LCSR"))
        self.assertEqual([r["refr"] for r in rows[3:]], [0x02000900, 0x02000901, 0x020008F2, 0x020008F0, 0x020008F0])
        self.assertEqual([r["lcrt"] for r in rows[5:]], [map_markers.MAPMARKER_REF_TYPE, map_markers.SHIP_LANDING_MARKER_REF_TYPE,
                                                         map_markers.SHIP_LANDING_MARKER_REF_TYPE_LARGE])
        self.assertNotEqual(rows[5]["pad"], rows[6]["pad"])          # the marker sits in the cell south of the pad's
        # the quest moves them with the markers, at their written spots (no lift: landing_spot lifted the heading)
        got = self.object_list(tlw.field(recs[0x800][1], b"VMAD"))
        self.assertEqual(got[3:], [0x02000900, 0x02000901, 0x020008F0, 0x020008F1, 0x020008F2, 0x020008F3])
        zs = [self.markers_z(i) for i in core_ids] + [m["pos"][2] + Z_LIFT for m in self.EXTRA] + \
             [spot[p]["pos"][2] for p in ("pad", "trigger", "marker", "heading")]
        self.assertIn(f"LocalZ: {', '.join(self.num(v) for v in zs)}", check.stdout)
        nxt = struct.unpack_from("<I", plugin.read_bytes(), 24 + 4 + 2 + 8)[0]          # HEDR next id: after --extra's
        self.assertEqual(nxt, 0x902)

    def markers_z(self, form):
        return next(m["pos"][2] for m in self.markers if int(self.ids[m["tag"]], 16) == form) + Z_LIFT

    def test_check_wants_the_same_landing_spot(self):
        landing = self.landing_file("landing-same", self.landing())
        out = self.root / "plugin-landing-same"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--landing", landing)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        self.assertEqual(struct.unpack_from("<I", plugin.read_bytes(), 24 + 4 + 2 + 8)[0], 0x8F4)   # no --extra
        self.assertEqual(self.tool_run("check", plugin, self.core, "--landing", landing).returncode, 0)
        bare = self.tool_run("check", plugin, self.core)
        self.assertEqual(bare.returncode, 1, bare.stdout)
        self.assertIn("is a REFR of this plugin that --extra and --landing do not list", bare.stdout)
        self.assertIn("1 Location record(s) without --extra or --landing", bare.stdout)
        renamed = self.tool_run("check", plugin, self.core, "--landing", self.landing_file("landing-renamed", self.landing(name="Pad")))
        self.assertEqual(renamed.returncode, 1, renamed.stdout)
        self.assertIn("SyntheticWorldLandingMapMarkerRedRocketNorth is not the record --landing builds", renamed.stdout)
        moved = self.landing()
        moved["pad"]["cell"] = [0, 0]                                           # the pad's rows name another grid
        grid = self.tool_run("check", plugin, self.core, "--landing", self.landing_file("landing-grid", moved))
        self.assertEqual(grid.returncode, 1, grid.stdout)
        self.assertIn("and the landing spot's three", grid.stdout)
        plain = self.root / "plugin-landing-none"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", plain).returncode, 0)
        missing = self.tool_run("check", plain / "FO4SFMapMarkers.esm", self.core, "--landing", landing)
        self.assertEqual(missing.returncode, 1, missing.stdout)
        self.assertIn("SyntheticWorldLandingPadRedRocketNorth (--landing) is missing", missing.stdout)

    def test_landing_undiscovered_writes_the_marker_without_discovered_and_tells_every_quest(self):
        # --landing-undiscovered (FAL-489, the Vault 111 exit): the landing marker's flags are 0x13, not 0x33, and every quest carries
        # ShowLandingMarker = false so FO4SF_MapMarkers.ShowLanding does not discover it; no script can clear Discovered later, so the
        # plugin has to start it undiscovered. A default build is unchanged and carries no such property (the pinned build above).
        landing = self.landing_file("landing-undisc", self.landing())
        many = [{"tag": f"M{k:06X}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]} for k in range(45)]
        extra = self.extra_file("extra-undisc", many)             # 3 core + 45 own + 4 landing = 52 markers: three quests of 20, 20 and 12
        out, plain = self.root / "plugin-undisc", self.root / "plugin-disc"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra, "--landing", landing, "--landing-undiscovered")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        default = self.tool_run("build", "--core", self.core, "--out", plain, "--extra", extra, "--landing", landing)
        self.assertEqual(default.returncode, 0, default.stdout + default.stderr)
        plugin, plugin_plain = out / "FO4SFMapMarkers.esm", plain / "FO4SFMapMarkers.esm"
        args = ("--extra", extra, "--landing", landing)
        self.assertEqual(self.tool_run("check", plugin, self.core, *args, "--landing-undiscovered").returncode, 0)
        self.assertEqual(self.tool_run("check", plugin_plain, self.core, *args).returncode, 0)
        recs, recs_plain = self.records_by_form(plugin), self.records_by_form(plugin_plain)    # by full FormID: three quests
        flags = lambda r: struct.unpack("<I", tlw.field(r[0x020008F2][1], b"FNAM"))[0]   # noqa: E731
        self.assertEqual((flags(recs), flags(recs_plain)), (0x13, 0x33))
        quests = [k for k, r in recs.items() if r[0] == b"QUST" and k >> 24 == 2]
        self.assertEqual(len(quests), 3)
        for k in quests:                                                   # every quest, not only the one that holds the pad
            self.assertIn(b"ShowLandingMarker", tlw.field(recs[k][1], b"VMAD"), hex(k))
            self.assertNotIn(b"ShowLandingMarker", tlw.field(recs_plain[k][1], b"VMAD"), hex(k))
        # check wants the same flag: an undiscovered build against a plain check, and a plain build against the flag, both fail
        wrong = self.tool_run("check", plugin, self.core, *args)
        self.assertEqual(wrong.returncode, 1, wrong.stdout)
        self.assertIn("ShowLandingMarker false: only --landing-undiscovered writes it", wrong.stdout)
        self.assertIn("is not the record --landing builds", wrong.stdout)                  # the marker's flags differ too
        wrong = self.tool_run("check", plugin_plain, self.core, *args, "--landing-undiscovered")
        self.assertEqual(wrong.returncode, 1, wrong.stdout)
        self.assertIn("ShowLandingMarker missing: --landing-undiscovered wants false on every quest", wrong.stdout)
        # the flag changes nothing without a landing spot
        bare = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-undisc-bare", "--landing-undiscovered")
        self.assertEqual(bare.returncode, 2, bare.stdout)
        self.assertIn("--landing-undiscovered needs --landing", bare.stderr)

    def star_file(self, name, names, strict=True):
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({"names": names, "strict": strict}))
        return path

    def test_star_map_keeps_only_the_named_markers_on_it(self):
        # --star-map (the owner's pick A, 2026-10-28): Mars's planet view stacks the markers at one spot into one icon
        # with a list, so only the named markers and the landing marker keep Visible on Star Map; every marker stays
        # Visible (the surface map), and check wants the same list
        extra, landing = self.extra_file("extra-star", self.EXTRA), self.landing_file("landing-star", self.landing())
        star = self.star_file("star", ["Sanctuary Hills", "Abernathy Farm"])
        out = self.root / "plugin-star"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra, "--landing", landing, "--star-map", star)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("star map: 2 of 5 marker(s) keep Visible on Star Map", proc.stdout)
        plugin = out / "FO4SFMapMarkers.esm"
        recs = tri.records(plugin)
        fnam = lambda k: struct.unpack("<I", tlw.field(recs[k][1], b"FNAM"))[0]      # noqa: E731
        on = {int(self.ids[m["tag"]], 16): m["name"] == "Sanctuary Hills" for m in self.markers}
        on.update({0x900: True, 0x901: False, 0x8F2: True})       # Abernathy Farm, Starlight Drive In, the landing marker
        for k, want in on.items():
            self.assertEqual(bool(fnam(k) & STAR_MAP), want, hex(k))
            self.assertEqual(fnam(k) & (USE_LOCATION_NAME | VISIBLE), VISIBLE, hex(k))   # all on the surface map
        self.assertEqual(fnam(0x8F2), 0x33)                                                 # LandingOverlay01's, as before
        same = self.tool_run("check", plugin, self.core, "--extra", extra, "--landing", landing, "--star-map", star)
        self.assertEqual(same.returncode, 0, same.stdout + same.stderr)
        other = self.tool_run("check", plugin, self.core, "--extra", extra, "--landing", landing,
                              "--star-map", self.star_file("star-other", ["Concord"]))
        self.assertEqual(other.returncode, 1, other.stdout)
        self.assertIn('"Concord" is not on the star map (--star-map wants)', other.stdout)
        self.assertIn('"Sanctuary Hills" is on the star map (--star-map wants it off)', other.stdout)
        bare = self.tool_run("check", plugin, self.core, "--extra", extra, "--landing", landing)
        self.assertEqual(bare.returncode, 1, bare.stdout)                 # without the list: the core's flags (off here)
        self.assertIn('"Sanctuary Hills" is on the star map (the core wants it off)', bare.stdout)
        # a name that matches no marker: strict fails the build, the stage's default list only says so
        typo = self.star_file("star-typo", ["Sanctuary Hils"])
        failed = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-star-typo", "--star-map", typo)
        self.assertEqual(failed.returncode, 1, failed.stdout)
        self.assertIn('--star-map: no marker is named "Sanctuary Hils"', failed.stderr)
        lenient = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-star-lenient",
                                "--star-map", self.star_file("star-lenient", ["Sanctuary Hils", "Concord"], strict=False))
        self.assertEqual(lenient.returncode, 0, lenient.stdout + lenient.stderr)
        self.assertIn('--star-map: no marker is named "Sanctuary Hils"', lenient.stdout)
        self.assertIn("star map: 1 of 3 marker(s) keep Visible on Star Map", lenient.stdout)
        bad = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-star-bad",
                            "--star-map", self.star_file("star-bad", ["Concord", "Concord"]))
        self.assertEqual(bad.returncode, 2, bad.stderr)
        self.assertIn('"Concord" repeats', bad.stderr)

    def test_star_map_clears_the_bit_a_real_core_sets(self):
        # the real core's markers carry LC172's FNAM 0x1B (on the star map); the synthetic core's are 0, so a copy with
        # 0x1B shows the bit kept without a list (0x13, as before the list) and cleared on every unnamed marker with one
        data = bytearray(self.core.read_bytes())
        pattern, n = b"XMRK\x00\x00FNAM\x04\x00", 0
        at = data.find(pattern)
        while at >= 0:
            struct.pack_into("<I", data, at + len(pattern), 0x1B)
            n, at = n + 1, data.find(pattern, at + len(pattern))
        self.assertEqual(n, len(self.markers))
        core = self.root / "core-1b" / "Synthetic.esm"
        core.parent.mkdir()
        core.write_bytes(bytes(data))
        extra, landing = self.extra_file("extra-star-1b", self.EXTRA), self.landing_file("landing-star-1b", self.landing())
        star = self.star_file("star-1b", ["Concord", "Starlight Drive In", "Landing Area"])
        for label, opts, named in (("all", [], None), ("list", ["--star-map", star], {"Concord", "Starlight Drive In"})):
            out = self.root / f"plugin-star-1b-{label}"
            proc = self.tool_run("build", "--core", core, "--out", out, "--extra", extra, "--landing", landing, *opts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertNotIn("no marker is named", proc.stdout + proc.stderr)       # the landing marker's name is no typo
            plugin = out / "FO4SFMapMarkers.esm"
            recs = tri.records(plugin)
            fnam = lambda k: struct.unpack("<I", tlw.field(recs[k][1], b"FNAM"))[0]      # noqa: E731
            names = {int(self.ids[m["tag"]], 16): m["name"] for m in self.markers} | {0x900: "Abernathy Farm",
                                                                                     0x901: "Starlight Drive In"}
            for k, name in names.items():
                self.assertEqual(fnam(k), 0x13 if named is None or name in named else 0x03, f"{label} {name}")
            self.assertEqual(fnam(0x8F2), 0x33)
            check = self.tool_run("check", plugin, core, "--extra", extra, "--landing", landing, *opts)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            crossed = self.tool_run("check", plugin, core, "--extra", extra, "--landing", landing,
                                    *([] if opts else ["--star-map", star]))
            self.assertEqual(crossed.returncode, 1, crossed.stdout)
            self.assertIn('"Sanctuary Hills" is not on the star map (the core wants)' if opts else
                          '"Sanctuary Hills" is on the star map (--star-map wants it off)', crossed.stdout)

    def test_the_landing_spot_stays_in_one_quest(self):
        # the script finds the landing marker two places after the pad (FO4SF_MapMarkers.psc ShowLanding): 3 core
        # markers, 195 of the plugin's own and the landing's 4 would leave 2 pieces alone in an eleventh quest, so that
        # quest takes the other two from the one before it (20 x 9, 18, 4), and the check wants the same split
        many = [{"tag": f"M{k:06X}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
                for k in range(195)]
        extra, landing = self.extra_file("extra-split", many), self.landing_file("landing-split", self.landing())
        out = self.root / "plugin-landing-split"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra, "--landing", landing)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("11 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", self.core, "--extra", extra, "--landing", landing)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        recs = self.records_by_form(out / "FO4SFMapMarkers.esm")
        vmads = [tlw.field(recs[0x02000000 | q][1], b"VMAD") for q in range(0x800, 0x80B)]
        lists = [self.object_list(v) for v in vmads]
        self.assertEqual([len(x) for x in lists], [20] * 9 + [18, 4])
        self.assertEqual(lists[-1], [0x020008F0, 0x020008F1, 0x020008F2, 0x020008F3])    # pad, trigger, marker, heading
        flat = [f for x in lists for f in x]
        self.assertEqual([f & 0xFFFFFF for f in flat[3:-4]], list(range(0x900, 0x900 + 195)))   # the order kept
        for v in vmads:                                                               # 20 or fewer: the script's 40
            self.assertNotIn(b"MaxMoves", v)

    def test_reload_adds_the_stop_and_the_first_quests_hopmarker(self):
        # the map lists only the markers in a world when the player enters it, and the quests move them in after
        # (owner, 2026-10-31): --reload adds a small interior of the plugin's own, lit as PluginSpike's door test cell,
        # whose persistent COC marker the first quest's HopMarker names; the script reloads the world through it once
        many = [{"tag": f"M{k:06X}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
                for k in range(40)]
        extra = self.extra_file("extra-reload", many)
        out = self.root / "plugin-reload"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra, "--reload")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("3 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)        # 43 markers: 20, 20, 3
        self.assertIn("the reload's stop FO4SF_MapMarkersHop (0008F4, its marker 0008F5 the first quest's HopMarker)", built.stdout)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core, "--extra", extra, "--reload")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("  reload stop ", check.stdout)
        self.assertIn("  HopMarker: ", check.stdout)
        recs = self.records_by_form(plugin)
        own = 0x02000000                                                            # after Starfield.esm and the core
        sig, cell, _ = recs[own | 0x8F4]
        self.assertEqual(sig, b"CELL")
        self.assertEqual(tlw.field(cell, b"EDID"), b"FO4SF_MapMarkersHop\0")
        self.assertEqual(tlw.field(cell, b"DATA")[0] & 0x1, 0x1)                    # interior
        self.assertEqual(struct.unpack("<I", tlw.field(cell, b"LTMP"))[0], 0x006658)  # ShipInteriorLT (Starfield.esm)
        self.assertEqual(struct.unpack("<I", tlw.field(cell, b"XCIM"))[0], 0x122393)
        data = plugin.read_bytes()
        marker, floor = recs[own | 0x8F5], recs[own | 0x8F6]
        self.assertEqual((marker[0], floor[0]), (b"REFR", b"REFR"))
        self.assertEqual(struct.unpack("<I", tlw.field(marker[1], b"NAME"))[0], 0x000032)   # COCMarkerHeading
        self.assertEqual(struct.unpack("<I", tlw.field(floor[1], b"NAME"))[0], 0x050776)    # the 8 x 8 m platform
        self.assertEqual(marker[2] & 0xC00, 0x400)                                  # persistent: the property resolves
        self.assertEqual(floor[2] & 0x400, 0)
        vmads = [tlw.field(recs[own | q][1], b"VMAD") for q in (0x800, 0x801, 0x802)]
        name = b"\x09\x00HopMarker"
        at = vmads[0].index(name) + len(name)
        self.assertEqual(struct.unpack_from("<BBHhI", vmads[0], at), (1, 1, 0, -1, own | 0x8F5))   # object, edited, direct
        self.assertNotIn(name, vmads[1])                                            # only the first quest reloads
        self.assertNotIn(name, vmads[2])
        nxt = struct.unpack_from("<I", data, 24 + 4 + 2 + 8)[0]                     # HEDR next id: past --extra's
        self.assertEqual(nxt, 0x900 + 40)
        # the check wants the same --reload: a stop it was not asked for, or none when it was, fails
        other = self.tool_run("check", plugin, self.core, "--extra", extra)
        self.assertEqual(other.returncode, 1, other.stdout)
        self.assertIn("1 cell(s) of this plugin's own without --reload", other.stdout)
        self.assertIn("FAIL  HopMarker set without --reload", other.stdout)
        self.assertIn("is a REFR of this plugin that --extra and --landing do not list", other.stdout)
        plain = self.root / "plugin-reload-none"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", plain, "--extra", extra).returncode, 0)
        none = self.tool_run("check", plain / "FO4SFMapMarkers.esm", self.core, "--extra", extra, "--reload")
        self.assertEqual(none.returncode, 1, none.stdout)
        self.assertIn("--reload: cells [], want only", none.stdout)
        self.assertIn("FAIL  HopMarker is not the stop's marker", none.stdout)
        # a plain build without --extra or --landing has its stop's ids too (next id past them)
        bare = self.root / "plugin-reload-bare"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", bare, "--reload").returncode, 0)
        self.assertEqual(self.tool_run("check", bare / "FO4SFMapMarkers.esm", self.core, "--reload").returncode, 0)
        self.assertEqual(struct.unpack_from("<I", (bare / "FO4SFMapMarkers.esm").read_bytes(), 24 + 4 + 2 + 8)[0], 0x8F7)

    def test_build_refuses_a_bad_landing_file(self):
        spot = self.landing()
        for name, bad, want in [
                ("landing-badtag", dict(spot, tag="Red Rocket"), 'tag "Red Rocket": want letters, digits or _'),
                ("landing-noname", dict(spot, name=""), "RedRocketNorth: no name"),
                ("landing-nopart", {k: v for k, v in spot.items() if k != "heading"}, "RedRocketNorth: no heading"),
                ("landing-short", dict(spot, pad=dict(spot["pad"], rot=[0.0, 0.0])), "pad: rot needs 3 finite numbers")]:
            proc = self.tool_run("build", "--core", self.core, "--out", self.root / f"plugin-{name}", "--landing",
                                 self.landing_file(name, bad))
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn(want, proc.stderr)

    def test_check_rejects_an_alias_encoded_marker(self):
        out = self.root / "plugin-alias"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        name = b"\x07\x00Markers"
        entry = data.index(name) + len(name) + 6                # type, status, u32 count
        self.assertEqual(struct.unpack_from("<Hh", data, entry), (0, -1))
        struct.pack_into("<h", data, entry + 2, 0)              # alias -1 -> 0, the form id untouched
        plugin.write_bytes(bytes(data))
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  Markers[0] is not a direct reference (alias 0, unused 0)", check.stdout)

    def test_check_rejects_a_plugin_built_from_another_core(self):
        params = copy.deepcopy(self.params)
        params["overlays"][0]["map_markers"] = self.markers[:2]
        saved, type(self).params = type(self).params, params
        try:
            proc, other = self.run_writer(self.objects, "core-two")
        finally:
            type(self).params = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = self.root / "plugin-two"
        self.assertEqual(self.tool_run("build", "--core", other / "Synthetic.esm", "--out", out).returncode, 0)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  Markers", check.stdout)

    def test_build_refuses_a_core_without_markers(self):
        # the plain synthetic master has no LC172 template, so the writer writes no MapMarker REFR
        fixture = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        plain = self.root / "master-plain/Starfield.esm"
        plain.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.dotnet, str(fixture), str(plain)], capture_output=True, check=True)
        saved, type(self).master = type(self).master, plain
        try:
            proc, stage = self.run_writer(self.objects, "core-plain")
        finally:
            type(self).master = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = self.tool_run("build", "--core", stage / "Synthetic.esm", "--out", self.root / "none")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("no MapMarker REFR", proc.stderr)

    @staticmethod
    def records_by_form(path):
        """{full FormID: (sig, payload, flags)} of a plugin (tri.records keys by the low 24 bits, so an override and a
        record of the plugin's own with the same low bits collide there)."""
        data, out = path.read_bytes(), {}

        def walk(pos, end):
            while pos < end:
                sig, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
                if sig == b"GRUP":
                    walk(pos + 24, pos + size)
                    pos += size
                    continue
                flags, form = struct.unpack_from("<II", data, pos + 8)
                payload = data[pos + 24:pos + 24 + size]
                out[form] = (sig, zlib.decompress(payload[4:]) if flags & 0x40000 else payload, flags)
                pos += 24 + size
        walk(0, len(data))
        return out

    @staticmethod
    def num(v):
        return f"{v:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def object_list(vmad):
        """Form ids of the Markers array property (type 11) in a quest VMAD."""
        name = b"\x07\x00Markers"                     # the property's u16-length-prefixed name
        pos = vmad.index(name) + len(name)
        kind, _status, count = struct.unpack_from("<BBI", vmad, pos)
        assert kind == 11, kind
        pos += 6
        out = []
        for _ in range(count):
            _zero, _alias, form = struct.unpack_from("<HhI", vmad, pos)
            out.append(form)
            pos += 8
        return out


class ScriptContractTests(unittest.TestCase):
    text = SCRIPT.read_text(encoding="utf-8")

    def test_properties_the_writer_fills(self):
        for decl in ("ObjectReference[] Property Markers", "float[] Property LocalX", "float[] Property LocalY",
                     "float[] Property LocalZ"):
            self.assertIn(decl, self.text)

    def test_offset_and_extent_match_the_repo(self):
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        import vmad_patch
        dx, dy, _ = vmad_patch.MERGE_MEASURED
        self.assertIn(f"MergeOffsetX = {dx}", self.text)
        self.assertIn(f"MergeOffsetY = {dy}", self.text)
        half = 64 // 2 * 100.0                             # core64: local -3200..3200 m
        for name, v in (("MinX", -half + dx), ("MaxX", half + dx), ("MinY", -half + dy), ("MaxY", half + dy)):
            self.assertIn(f"{name} = {v}", self.text)

    def test_a_marker_at_the_old_height_is_moved_again(self):
        # a save from before a lifted build holds the markers at the old z (Codex on #483): the reposition test
        # reads the height too, so the first pass moves them once more. The tolerance is half the lift step the
        # build enforces, so every supported change between builds (0.1 m up) is seen, while a landed move is not
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertIn("ez * ez > ZTolerance * ZTolerance", place)
        tol = float(re.search(r"float Property ZTolerance = ([0-9.]+) Auto Const", self.text).group(1))
        self.assertEqual(tol, Z_LIFT_STEP / 2)
        self.assertGreater(tol, 0.01)                                     # a landed move is within 0.01 m (22 Oct log)
        placed = lambda ez: not (ez * ez > tol * tol)                     # the script's test, in Python
        self.assertTrue(placed(0.01) and placed(-0.01))                   # landed: left alone
        self.assertFalse(placed(Z_LIFT_STEP) or placed(-Z_LIFT_STEP))     # the smallest change between builds: moved
        self.assertFalse(placed(Z_LIFT))                                  # a save from before the default lift: moved

    def test_the_move_budget_starts_over_for_a_new_build(self):
        # moves is saved state, so a save that spent its budget on the first placement and one lift would ignore
        # the next lift (Codex on #483): the budget is keyed to the build (marker count, LocalZ[0]) and starts over
        self.assertIn("int budgetN = -1", self.text)
        self.assertIn("float budgetZ = 0.0", self.text)
        reset = self.text[self.text.index("Function ResetBudget"):self.text.index("Function NewSession")]
        self.assertIn("budgetN != Markers.Length || budgetZ != LocalZ[0]", reset)
        for line in ("budgetN = Markers.Length", "budgetZ = LocalZ[0]", "moves = 0"):
            self.assertIn(line, reset)
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("ResetBudget()"), place.index("IsInInterior"))   # before any early return
        # the script's loop, modelled: n markers, the build's MaxMoves (2n above 40, as dotnet/MapMarkers sets it),
        # a pass per Interval; initial placement, then lift A, then lift B, on one save
        tol = float(re.search(r"float Property ZTolerance = ([0-9.]+) Auto Const", self.text).group(1))
        n = 100
        max_moves = max(2 * n, 40)
        saved_z = [None] * n                                              # None: not yet in the player's world
        state = {"moves": 0, "budget_n": -1, "budget_z": 0.0}

        def passes(local_z, count=3):
            moved = 0
            for _ in range(count):                                        # the script runs until nothing is off
                if state["budget_n"] != n or state["budget_z"] != local_z[0]:
                    state["budget_n"], state["budget_z"], state["moves"] = n, local_z[0], 0
                for i in range(n):
                    if state["moves"] >= max_moves:
                        break
                    off = saved_z[i] is None or (saved_z[i] - local_z[i]) ** 2 > tol * tol
                    if off:
                        saved_z[i] = local_z[i] + 0.004                   # a move lands within 0.01 m
                        state["moves"] += 1
                        moved += 1
            return moved

        base = [100.0 + i for i in range(n)]
        self.assertEqual(passes(base), n)                                 # placed once each
        self.assertEqual(passes([z + 0.5 for z in base]), n)              # lift A: every marker moved once more
        self.assertEqual(passes([z + 1.0 for z in base]), n)              # lift B: the budget started over
        self.assertEqual(passes([z + 1.0 for z in base]), 0)              # the same build again: nothing moves

    def test_moves_only_outdoors_capped_and_logged(self):
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("IsInInterior"), place.index("MoveTo"))
        # the budget is part of the loop condition, so it holds before every Enable / MoveTo (Codex 4311385104)
        loop = place.index("while i < Markers.Length && moves < MaxMoves")
        self.assertLess(loop, place.index("m.Enable"))
        self.assertEqual(place.count("moves += 1"), 1)
        self.assertEqual(place.count("MoveTo("), 1)
        # no match-rotation: a moved pad keeps its record's facing, not the player's
        self.assertRegex(place, r"m\.MoveTo\(player, x - px, y - py, z - pz, False, False\)")
        self.assertIn('Trace("moved "', place)
        self.assertNotIn("Math.", self.text)               # only the base scripts the bridge already imports

    def test_a_pass_reads_the_player_before_every_move(self):
        # a load door can take the player away while a pass runs: a pass that read them once put about 300 markers
        # into Vault 95 at the target plus the trip and spent every budget (PC, 2026-10-24 10:24, fo4sf_map.0.log).
        # Inside the move branch, just before MoveTo, the player is read again and the pass stops once they are
        # indoors or in another world; a marker already in place costs no player reads (fresh review on #570)
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        loop = place.index("while i < Markers.Length && moves < MaxMoves")
        self.assertLess(place.index("WorldSpace w = player.GetWorldSpace()"), loop)
        branch = place.index("if off\n", loop)
        stop = place.index("if player.IsInInterior() || player.GetWorldSpace() != w", loop)
        read = place.index("px = player.GetPositionX()", loop)
        self.assertLess(branch, stop)
        self.assertLess(stop, read)
        self.assertLess(read, place.index("m.Enable", loop))
        self.assertLess(place.index("m.Enable"), place.index("m.MoveTo("))
        self.assertIn('Trace("pass stopped at "', place)
        self.assertEqual(place.count("player.GetPositionX()"), 2)     # once for the extent, once before the move
        self.assertEqual(place[loop:branch].count("player.Get"), 1)   # only the distance before a move is needed

    def test_a_reference_the_game_will_not_move_is_left_alone_for_the_session(self):
        # the landing pad: "cannot be moved" on every pass, and its quest spent its whole budget retrying it
        # (Papyrus.0.log, 2026-10-24); a refused reference is skipped until the next game session
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertIn("if m != None && !refused[i]", place)
        self.assertLess(place.index("!refused[i]"), place.index("m.Enable"))
        self.assertLess(place.index("m.MoveTo("), place.index("refused[i] = True"))
        # still in its own world after the move, while the player stayed in theirs: refused. The pad's x/y read before
        # and after "cannot be moved" did not match on the PC (2026-10-28: 18 and 27 errors, no refused line), so the
        # position is not asked for; the line logs where it was
        after = place.index("float d = player.GetDistance(m)")
        # each line without its ; comment (a ; inside a string stays) and indentation, blank lines dropped
        code = "\n".join(re.sub(r'^((?:[^";]|"[^"]*")*);.*$', r"\1", line).strip()
                         for line in place[after:].splitlines())
        code = re.sub(r"\n+", "\n", code)
        self.assertRegex(code, r"\nif d > SameWorld\n"
                               r"if player\.IsInInterior\(\) \|\| player\.GetWorldSpace\(\) != w\n"
                               r'Trace\("pass stopped after moving " \+ i \+ "[^"\n]*"\)\n'
                               r"return\n"
                               r"endif\n"
                               r"refused\[i\] = True\n"
                               r'Trace\("refused " \+ i \+ ": still in its own world after the move, at " \+ m\.GetPositionX\(\) \+ " " '
                               r'\+ m\.GetPositionY\(\) \+ "[^"\n]*"\)\n'
                               r"else\n"
                               r"m\.SetPosition\(x, y, z\)\n")
        self.assertNotIn("sx * sx", place)
        self.assertLess(place.index("NewSession()"), place.index("IsInInterior"))
        session = self.text[self.text.index("Function NewSession"):self.text.index("Function ShowLanding")]
        size = int(re.search(r"refused = new bool\[(\d+)\]", session).group(1))
        per_quest = int(re.search(r"const int PerQuest = (\d+)", PROGRAM.read_text(encoding="utf-8")).group(1))
        self.assertGreaterEqual(size, per_quest)                          # every index a quest can hold
        self.assertLessEqual(size, 128)                                   # a script-made array's limit
        # every game session: the budget starts over, so markers a session left wrong are put right in the next
        for line in ("moves = 0", "landingShown = False"):
            self.assertIn(line, session)
        # a save from before these variables brings them in unset: 0.0 counts as a new session too, so the list is made
        self.assertIn("bool fresh = placeRealTime <= 0.0 || rt < placeRealTime", session)
        self.assertIn("return fresh", session)
        self.assertIn("float placeRealTime = -1.0", self.text)
        # a new build can list other references at the same places, so the list starts over with its budget
        reset = self.text[self.text.index("Function ResetBudget"):self.text.index("Function NewSession")]
        self.assertIn(f"refused = new bool[{size}]", reset)

    def test_every_save_load_is_a_new_session(self):
        # Codex on #570: the clock alone misses a launch whose first pass reads a later real time than the save's last
        # one (saved 20 s, first pass at 90 s), keeping that session's spent budget. The player's load event clears
        # both clocks. Replayed here from the script's own predicates and the values the event writes
        on_init = self.text[self.text.index("Event OnInit"):self.text.index("EndEvent")]
        self.assertIn('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")', on_init)
        load = self.text[self.text.index("Event Actor.OnPlayerLoadGame(Actor akSender)"):]
        load = load[:load.index("EndEvent")]
        written = dict(re.findall(r"^\s+(placeRealTime|lastRealTime) = ([0-9.]+)", load, re.M))
        self.assertEqual(set(written), {"placeRealTime", "lastRealTime"})
        session = self.text[self.text.index("bool Function NewSession"):self.text.index("Function SessionLine")]
        self.assertIn('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")', session)   # older saves
        # an old save's first load brings no event (it was not registered yet): a new session for Place is one for
        # Border too, with the value the event writes
        self.assertIn(f"lastRealTime = {written['lastRealTime']}", session)
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("NewSession()"), place.index("ResetBudget()"))          # the log open first
        place_new = re.search(r"bool fresh = (.+)$", session, re.M).group(1)
        border = self.text[self.text.index("Function Border"):self.text.index("Function Trace")]
        border_new = re.search(r"if (rt < lastRealTime)\s", border).group(1)

        def py(expr):
            return expr.replace("||", " or ").replace("&&", " and ")

        def replay(name, expr, initial, events):
            """The variable as saved, then each event: ("load",) or ("tick", rt); the ticks that start a session."""
            var, out = initial, []
            for e in events:
                if e[0] == "load":
                    var = float(written[name])
                else:
                    out.append(eval(py(expr), {}, {name: var, "rt": e[1]}))   # noqa: S307 - the script's own text
                    var = e[1]
            return out

        for name, expr, initial in (("placeRealTime", place_new, -1.0), ("lastRealTime", border_new, -1.0)):
            same = [("tick", 2.0), ("tick", 4.0), ("tick", 6.0)]
            self.assertEqual(replay(name, expr, initial, same)[1:], [False, False], name)             # one session
            later = [("tick", 18.0), ("tick", 20.0), ("load",), ("tick", 90.0), ("tick", 92.0)]
            self.assertEqual(replay(name, expr, initial, later)[2:], [True, False], name)            # a later clock
            earlier = [("tick", 600.0), ("load",), ("tick", 40.0), ("tick", 42.0)]
            self.assertEqual(replay(name, expr, initial, earlier)[1:], [True, False], name)          # an earlier one
            reload = [("tick", 300.0), ("load",), ("tick", 310.0)]
            self.assertEqual(replay(name, expr, initial, reload)[1:], [True], name)                  # same launch
            unset = [("tick", 90.0)]                                   # a save from before NewSession: 0.0
            if name == "placeRealTime":
                self.assertEqual(replay(name, expr, 0.0, unset), [True])

    def test_each_quest_says_once_per_session_what_the_border_guards_read(self):
        # a coc session from the main menu at Red Rocket wrote no border line in 240 s while "moved 9" lines kept
        # coming (Review, 2026-10-28): every line names its quest, and each quest's first pass of a session logs
        # what Border's guards read, so the log tells whether 0x800 ticked or its Markers[0] was None
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("if NewSession()"), place.index("SessionLine(player)"))
        self.assertLess(place.index("SessionLine(player)"), place.index("Border(player)"))
        line = self.text[self.text.index("Function SessionLine"):self.text.index("Function ShowLanding")]
        for field in ('"session id=" + GetFormID()', '" signal=" + SignalQuest()', '" enabled=" + BorderSignal',
                      '" markers=" + Markers.Length', '" first=" + first', '" interior=" + player.IsInInterior()'):
            self.assertIn(field, line)
        self.assertIn("if Markers.Length > 0", line)                     # no index into an empty list
        # FO4SFBorder takes the newest border= token in the log: only Border's own two lines may carry one
        traces = re.findall(r"Trace\((.*)\)\s*$", self.text, re.M)
        self.assertEqual([t for t in traces if "border=" in t],
                         ['"border=off cell=" + c + " world=" + w', '"border=on cell=" + c + " world=" + w'])
        self.assertGreaterEqual(len(traces), 10)
        # a load in a new launch runs no OnInit: the session opens the log before its first line
        session = self.text[self.text.index("bool Function NewSession"):self.text.index("Function SessionLine")]
        self.assertLess(session.index("Debug.OpenUserLog(LogName)"), session.index("Trace("))
        trace = self.text[self.text.index("Function Trace"):]
        self.assertIn('" q=" + QuestLow() + " " + msg', trace)

    def test_the_landing_marker_is_found_after_its_pad_and_shown_once_per_session(self):
        # Mars's map had no Commonwealth location (owner, 2026-10-28): the landing marker is marked discovered and
        # shown on the star map. dotnet/MapMarkers lists the landing spot pad, trigger, marker, heading, in one quest
        program = PROGRAM.read_text(encoding="utf-8")
        pad = int(re.search(r"LandingPad = 0x([0-9A-F]+)", program).group(1), 16)
        self.assertEqual(int(re.search(r"int Property LandingPadID = 0x([0-9A-Fa-f]+) Auto Const", self.text).group(1), 16), pad)
        self.assertIn("new List<PlacedObject> { pad, trigger, marker, heading }", program)
        self.assertIn("static List<T[]> QuestChunks<T>(", program)
        self.assertEqual(program.count("QuestChunks("), 2)                # build and check split the same way
        self.assertIn("var chunks = all.Chunk(PerQuest).ToList();", program)    # (test_the_landing_spot_stays_in_one_quest)
        show = self.text[self.text.index("Function ShowLanding"):self.text.index("Event OnTimer")]
        self.assertIn("int i = Markers.Length - 4", show)                      # the pad, fourth from the end
        self.assertIn("ObjectReference marker = Markers[i + 2]", show)
        self.assertIn("pad.GetBaseObject() == Game.GetForm(LandingPadID)", show)
        self.assertIn("marker.SetMarkerDiscovered()", show)
        self.assertIn("marker.SetMarkerVisibleOnStarMap(True)", show)
        self.assertNotIn("while", show)                                       # one read per quest
        self.assertLess(show.index("landingShown = True"), show.index("Game.GetForm"))   # once, found or not
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("Border(player)"), place.index("ShowLanding()"))   # the border signal first
        self.assertLess(place.index("ShowLanding()"), place.index("IsInInterior"))     # wherever the player is


    def fn(self, name, until):
        """The script's text from Function <name> to the next given marker."""
        start = self.text.index(name)
        return self.text[start:self.text.index(until, start + len(name))]

    def test_a_marker_in_another_world_is_moved_without_reading_where_it_stands(self):
        # each read is a call the game answers about once a frame (a marker every 0.45 s at 100 a quest, fo4sf_map.0.log
        # 2026-10-31): a marker in another world moves anyway, so only one in the player's world has its spot read
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        loop = place.index("while i < Markers.Length && moves < MaxMoves")
        branch = place.index("if off\n", loop)
        self.assertIn("bool off = before > SameWorld", place[loop:branch])
        reads = place.index("if !off", loop)
        self.assertEqual(place[loop:reads].count("m.GetPosition"), 0)
        self.assertEqual(place[reads:branch].count("m.GetPosition"), 3)

    def test_a_move_sets_the_spot_once_the_marker_is_in_the_players_world(self):
        # a move onto a walking player lands off by their steps in between (z 0.4 off, then moved again: 475 moves for
        # 313 markers, fo4sf_map.0.log 2026-10-31): SetPosition puts it on the spot, only once it is in that world
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        after = place[place.index("float d = player.GetDistance(m)"):]
        self.assertLess(after.index("refused[i] = True"), after.index("else"))
        self.assertLess(after.index("else"), after.index("m.SetPosition(x, y, z)"))
        self.assertLess(after.index("m.SetPosition(x, y, z)"), after.index('Trace("moved "'))
        self.assertEqual(place.count("SetPosition("), 1)
        # it came into the world after the player did only when it was in another one before the move
        self.assertRegex(after, r"if before > SameWorld\s+late = True")
        self.assertIn('" off=" + ex + " " + ey + " " + ez', after)          # why a marker in the world moved again

    def test_a_quest_with_every_marker_in_place_reads_one_a_pass(self):
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        loop = place.index("while i < Markers.Length && moves < MaxMoves")
        self.assertLess(place.index("if settledWorld == w && Probe(player)"), loop)
        self.assertLess(place.index("settledWorld = None"), loop)
        self.assertRegex(place[loop:], r"if i >= Markers\.Length && moved == 0\s+settledWorld = w")
        # a first quest out of moves before every marker stood still reloads too (Ready counts it)
        self.assertRegex(place[loop:], r"elseif moves >= MaxMoves\s+Reload\(player, w\)")
        self.assertEqual(place.count("moved += 1"), 1)
        probe = self.fn("bool Function Probe", "EndFunction")
        self.assertIn("int i = probeAt % n", probe)                       # a new build can list fewer markers
        self.assertIn("probeAt = (i + 1) % n", probe)
        self.assertIn("ex * ex + ey * ey > Tolerance * Tolerance || ez * ez > ZTolerance * ZTolerance", probe)
        self.assertIn("if player.GetDistance(m) > SameWorld", probe)
        # a new session or a new build reads them all again
        for f in ("bool Function NewSession", "Function ResetBudget"):
            self.assertIn("settledWorld = None", self.fn(f, "EndFunction"))
        # the model: a quest of n markers reads 4 a marker until all stand, then 4 a pass
        self.assertIn("return settledWorld == w || moves >= MaxMoves", self.fn("bool Function Ready", "EndFunction"))

    def test_the_player_entering_a_world_starts_its_late_count_over(self):
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        inside = place[place.index("if player.IsInInterior()"):place.index("WorldSpace w = player.GetWorldSpace()")]
        self.assertIn("seenWorld = None", inside)
        self.assertIn("late = False", inside)
        self.assertRegex(place, r"if w != seenWorld\s+seenWorld = w\s+.*\n\s+late = False\s+enteredAt = Utility\.GetCurrentRealTime\(\)")
        self.assertLess(place.index("if w != seenWorld"), place.index("if px < MinX"))   # outside the extent too

    def test_the_reload_comes_once_every_marker_is_in_and_some_came_late(self):
        # owner, 2026-10-31: no marker showed on the map or could be discovered until a trip to Cydonia and back
        reload = self.fn("Function Reload(Actor player, WorldSpace w)", "EndFunction")
        self.assertIn("if HopMarker == None || hops >= HopLimit || w != ourWorld", reload.splitlines()[1])
        self.assertIn("q = Game.GetForm(id + k) as FO4SF_MapMarkers", reload)
        self.assertRegex(reload, r"if !q\.Ready\(w\)\s+return")
        self.assertIn("if !anyLate || Utility.GetCurrentRealTime() - enteredAt < HopDelay", reload)
        self.assertIn("if player.IsInCombat() || player.IsInScene() || !Game.IsMovementControlsEnabled() || player.IsDead() "
                      "|| player.GetSitState() != 0", reload)
        # dark first, the count before the move (a reload that fails is not tried again), the stop, then back
        out = reload.index("player.MoveTo(HopMarker)")
        dark = reload.index("Game.FadeOutGame(True, True, 0.0, 0.5, True)")
        self.assertLess(reload.index("hops += 1"), dark)
        self.assertLess(dark, out)
        # the player as they are just before the move, with the screen black: w was read when the pass began, and a
        # load door can take them away in between (review of #624); the way back is read only then, and a reload
        # called off fades the screen back in
        recheck = reload.index("if player.IsInInterior() || player.GetWorldSpace() != w || hopX < MinX || hopX > MaxX "
                               "|| hopY < MinY || hopY > MaxY")
        for spot in ("hopX = player.GetPositionX()", "hopY", "hopZ = player.GetPositionZ()", "hopA = player.GetAngleZ()"):
            self.assertLess(dark, reload.index(spot))
            self.assertLess(reload.index(spot), recheck)
        self.assertLess(recheck, out)
        for way_back in ("hopAnchor = a", "hopWorld = w"):
            self.assertLess(recheck, reload.index(way_back))
            self.assertLess(reload.index(way_back), out)
        # the way back is a marker in the player's world: a quest out of moves may have some still in their own
        self.assertIn("while a < Markers.Length && (Markers[a] == None || refused[a] || player.GetDistance(Markers[a]) > SameWorld)",
                      reload)
        called_off = reload[recheck:reload.index("endif", recheck)]
        self.assertIn("Game.FadeOutGame(False, True, 0.0, 0.5, False)", called_off)
        self.assertIn("return", called_off)
        self.assertLess(out, reload.index("ComeBack(player)"))
        self.assertLess(reload.index("ComeBack(player)"), reload.index("q.Reentered(w)"))
        # later than the new game's landing check, 3 s after its arrival (FO4SF_NewGameQuest.psc CheckLanding)
        delay = float(re.search(r"float Property HopDelay = ([0-9.]+) Auto Const", self.text).group(1))
        self.assertGreater(delay, 3.0 + 2 * 1.0)                         # its 1 s ticks, ours every Interval
        self.assertEqual(int(re.search(r"int Property HopLimit = (\d+) Auto Const", self.text).group(1)), 1)
        self.assertIn("hops = 0", self.fn("bool Function NewSession", "EndFunction"))
        self.assertNotIn("IsInMenuMode", self.text)                     # not in Starfield's Utility.psc (PC, 19 Oct)

    def test_the_way_back_lands_on_the_spot_and_never_leaves_the_screen_black(self):
        back = self.fn("Function ComeBack(Actor player)", "\nEndFunction")
        self.assertIn("player.MoveTo(anchor, hopX - ax, hopY - ay, hopZ - az, False, False)", back)
        self.assertIn("float ax = LocalX[hopAnchor] + MergeOffsetX", back)
        # once outside with the 3D in, the spot (a SetPosition in the MoveTo's own tick is ignored) and the facing
        self.assertLess(back.index("while !player.Is3DLoaded()"), back.index("player.SetPosition(hopX, hopY, hopZ)"))
        # the spot is one in hopWorld: a world made again on the way, or a save made there loaded in a new launch, is not
        self.assertIn("bool snapped = back == hopWorld && dx * dx + dy * dy > 4.0", back)
        self.assertLess(back.index("WorldSpace back = player.GetWorldSpace()"), back.index("bool snapped"))
        self.assertIn("player.SetAngle(0.0, 0.0, hopA)", back)
        # every way out of ComeBack fades the screen back in
        parts = back.split("return")
        for part in parts[:-1]:
            self.assertIn("Game.FadeOutGame(False, True, 0.0, 0.5, False)", part.split("endif")[-1] if "endif" in part else part)
        self.assertIn("Game.FadeOutGame(False, True, 0.0, 0.5, False)", parts[-1])
        # a player still at the stop (a move back that did not take, or a save made there) is brought back next pass
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        # by the stop's cell alone (it has no door): a move out that lands after ComeBack gave up on it still comes back
        self.assertRegex(place, r"if HopMarker != None && player\.GetParentCell\(\) == HopMarker\.GetParentCell\(\)\s+ComeBack\(player\)")
        self.assertNotIn("hopOut", self.text)

    def test_the_dark_hold_starts_at_an_arrivals_first_late_marker(self):
        # option A put to the owner, 2026-10-31: the screen black from an arrival until the reload is back, so the first map opened
        # lists every marker (the retest: the reload was back about 14 s after the last marker went in)
        self.assertIn("bool Property HoldDark = True Auto Const", self.text)
        window = float(re.search(r"float Property HoldWindow = ([0-9.]+) Auto Const", self.text).group(1))
        most = float(re.search(r"float Property HoldMax = ([0-9.]+) Auto Const", self.text).group(1))
        self.assertGreater(window, 133.0 - 125.8)                       # the ride to the first quest's first move
        self.assertLessEqual(window, 20.0)
        self.assertGreater(most, 35.0)                                  # the retest's arrival to the reload's way back
        self.assertLessEqual(most, 90.0)
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        late = place.index("late = True                             ; it came into the world after the player did")
        start = place.index("Hold()", late)
        # only where a reload can follow: Reload wants our world (Border's), and none comes elsewhere
        self.assertIn("if !heldEntry && HoldDark && BorderSignal && HopMarker != None && hops < HopLimit && w == ourWorld && "
                      "Utility.GetCurrentRealTime() - enteredAt < HoldWindow", place[late:start])
        self.assertEqual(len(re.findall(r"(?<!Function )\bHold\(\)", self.text)), 1)        # only there
        hold = self.fn("Function Hold()", "EndFunction")
        self.assertIn("Game.FadeOutGame(True, True, 0.0, 0.5, True)", hold)   # stays black
        for line in ("heldEntry = True", "holding = True", "holdAt = Utility.GetCurrentRealTime()"):
            self.assertIn(line, hold)
        # held once per entry into a world, and a load starts with none
        self.assertRegex(place, r"if w != seenWorld\s+seenWorld = w\s+.*\n\s+late = False\s+enteredAt = .*\n\s+heldEntry = False")
        session = self.fn("bool Function NewSession", "EndFunction")
        self.assertRegex(session, r"if holding\s+Game\.FadeOutGame\(False, True, 0\.0, 0\.5, False\).*\n\s+holding = False")
        self.assertIn("heldEntry = False", session)

    def test_the_dark_hold_always_ends(self):
        release = self.fn("Function Release(string why)", "EndFunction")
        self.assertRegex(release, r"if holding\s+holding = False\s+Game\.FadeOutGame\(False, True, 0\.0, 0\.5, False\)")
        check = self.fn("Function HoldCheck(Actor player, bool ours)", "EndFunction")
        self.assertIn("if held > HoldMax", check)
        self.assertIn("elseif !ours", check)
        # whenever the reload would wait (Reload's own guard), the hold lets go
        self.assertIn("player.IsInCombat() || player.IsDead() || player.IsInScene() || player.GetSitState() != 0 || "
                      "!Game.IsMovementControlsEnabled()", check)
        self.assertEqual(check.count("Release("), 3)
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        # every outdoor pass checks it before any return, and indoors (a load door, the stop) ends it
        self.assertLess(place.index("HoldCheck(player, inside && w == ourWorld)"), place.index("if !inside\n        return"))
        self.assertLess(place.index("if holding\n        HoldCheck(player, inside && w == ourWorld)"), place.index("if settledWorld == w && Probe(player)"))
        inside = place[place.index("if player.IsInInterior()"):place.index("WorldSpace w = player.GetWorldSpace()")]
        self.assertIn('Release("the player went indoors")', inside)
        # a pass that moves markers for seconds checks between moves too
        loop = place[place.index("while i < Markers.Length && moves < MaxMoves"):]
        self.assertLess(loop.index("if holding\n                    HoldCheck(player, w == ourWorld)"), loop.index("m.MoveTo(player"))
        reload = self.fn("Function Reload(Actor player, WorldSpace w)", "EndFunction")
        waits = reload[reload.index("if player.IsInCombat() || player.IsInScene()"):reload.index("int a = 0")]
        self.assertIn('Release("the reload waits")', waits)
        skipped = reload[reload.index("skipped: no marker"):reload.index("Game.FadeOutGame(True, True, 0.0, 0.5, True)")]
        self.assertIn('Release("the reload was skipped")', skipped)
        recheck = reload.index("if player.IsInInterior() || player.GetWorldSpace() != w || hopX < MinX")
        self.assertRegex(reload[recheck:], r"\n\s+holding = False\s+Game\.FadeOutGame\(False, True, 0\.0, 0\.5, False\)")
        # the way back fades in on every way out (test above), so it ends the hold first
        back = self.fn("Function ComeBack(Actor player)", "\nEndFunction")
        self.assertLess(back.index("holding = False"), back.index("if hopAnchor < 0"))

    def test_the_fast_travel_line_reads_the_switches_and_a_marker(self):
        line = self.fn("Function FastTravelLine", "EndFunction")
        for call in ("Game.IsFastTravelEnabled()", "Game.IsFastTravelControlsEnabled()", "m.IsMapMarkerVisible()",
                     "m.CanFastTravelToMarker()"):
            self.assertIn(call, line)
        reload = self.fn("Function Reload(Actor player, WorldSpace w)", "EndFunction")
        self.assertIn("if !travelLogged", reload)                       # once a session before, then after each reload
        self.assertIn('FastTravelLine("after reload " + hops)', reload)

    def test_the_writer_and_the_script_agree_on_the_reload(self):
        program = PROGRAM.read_text(encoding="utf-8")
        self.assertIn('Name = "HopMarker"', program)
        self.assertIn("ObjectReference Property HopMarker Auto Const", self.text)
        self.assertIn(re.search(r'const string HopCell = "(\w+)"', program).group(1), self.text)
        per_quest = int(re.search(r"const int PerQuest = (\d+)", program).group(1))
        self.assertLessEqual(per_quest, 20)                             # the quests run side by side
        self.assertEqual(int(re.search(r"int Property MaxMoves = (\d+) Auto Const", self.text).group(1)), 2 * per_quest)


class StageTests(unittest.TestCase):
    def test_stage_builds_compiles_and_checks_against_the_core(self):
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        import make_map_markers as mm
        calls = []

        def fake_run(cmd, cwd=None):
            calls.append((cmd, cwd))
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w):
            out, core = os.path.join(d, "stage"), os.path.join(d, "FO4TerrainCore.esm")
            with open(core, "wb") as f:
                f.write(b"core bytes")
            mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe"])
            with open(os.path.join(out, "core.json"), encoding="utf-8") as f:   # the installer's pin on this core
                self.assertEqual(json.load(f), {"masters": {"FO4TerrainCore.esm": hashlib.sha256(b"core bytes").hexdigest()}})
            self.assertTrue(os.path.exists(os.path.join(out, "README.txt")))
            self.assertTrue(os.path.exists(os.path.join(out, "Data", "Scripts", "FO4SF_MapMarkers.pex")))
            with self.assertRaises(SystemExit):                # never into a used folder
                mm.main(["stage", "--core", core, "--out", out])
            with self.assertRaises(SystemExit):                # one plugin name, the one the installer knows
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s2"), "--plugin", "Custom.esm"])
            city = os.path.join(d, "city")                      # a world variant goes to build and check alike
            mm.main(["stage", "--core", core, "--out", city, "--compiler", "PapyrusCompiler.exe", "--world", "city"])
            with open(os.path.join(city, "README.txt"), encoding="utf-8") as f:
                self.assertIn("--world city (dotnet/BorderProbe's: SmallWorld cleared, HNAM 5)", f.read())
            with self.assertRaises(SystemExit):                # the probe's variants only
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s3"), "--world", "hnam5"])
            # the star map: the default list (not strict), names given (strict), or every marker as before
            with open(os.path.join(out, "star_map.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"names": list(mm.STAR_MAP), "strict": False})
            named = os.path.join(d, "named")
            mm.main(["stage", "--core", core, "--out", named, "--compiler", "PapyrusCompiler.exe", "--star-map", "Concord", "Vault 81"])
            with open(os.path.join(named, "star_map.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"names": ["Concord", "Vault 81"], "strict": True})
            with open(os.path.join(named, "README.txt"), encoding="utf-8") as f:
                self.assertIn("Visible on Star Map (star_map.json) only for those of Concord, Vault 81 the plugin has "
                              "(offline_check.txt: star map);", f.read())
            every = os.path.join(d, "every")
            mm.main(["stage", "--core", core, "--out", every, "--compiler", "PapyrusCompiler.exe", "--star-map-all"])
            self.assertFalse(os.path.exists(os.path.join(every, "star_map.json")))
            with self.assertRaises(SystemExit):                # a name twice, refused before the folder is made
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s4"), "--star-map", "Concord", "Concord"])
            self.assertFalse(os.path.exists(os.path.join(d, "s4")))
            with self.assertRaises(SystemExit):                # one or the other
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s5"), "--star-map", "Concord", "--star-map-all"])
            with self.assertRaises(SystemExit) as cm:          # FAL-489: it changes the landing marker, so it needs a landing spot
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s6"), "--landing-undiscovered"])
            self.assertIn("--landing-undiscovered needs --landing", str(cm.exception))
            self.assertFalse(os.path.exists(os.path.join(d, "s6")))
        build, comp, check, build2, comp2, check2, build3, _comp3, check3, build4, _comp4, check4 = calls
        star = os.path.join(out, "star_map.json")
        self.assertEqual(build[0][-10:], ["build", "--core", core, "--out", out, "--plugin", "FO4SFMapMarkers.esm", "--reload",
                                          "--star-map", star])
        self.assertEqual(comp[0][1], "FO4SF_MapMarkers.psc")
        self.assertEqual(check[0][-6:], ["check", os.path.join(out, "FO4SFMapMarkers.esm"), core, "--reload", "--star-map", star])
        star = os.path.join(city, "star_map.json")
        self.assertEqual(build2[0][-12:], ["build", "--core", core, "--out", city, "--plugin", "FO4SFMapMarkers.esm", "--world", "city",
                                           "--reload", "--star-map", star])
        self.assertEqual(check2[0][-8:], ["check", os.path.join(city, "FO4SFMapMarkers.esm"), core, "--world", "city", "--reload",
                                          "--star-map", star])
        self.assertEqual(build3[0][-2:], ["--star-map", os.path.join(named, "star_map.json")])
        self.assertEqual(check3[0][-2:], ["--star-map", os.path.join(named, "star_map.json")])
        self.assertEqual(build4[0][-8:], ["build", "--core", core, "--out", every, "--plugin", "FO4SFMapMarkers.esm", "--reload"])
        self.assertEqual(check4[0][-4:], ["check", os.path.join(every, "FO4SFMapMarkers.esm"), core, "--reload"])

    def test_stage_adds_the_reload_stop_unless_told_not_to(self):
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        import make_map_markers as mm
        calls = []

        def fake_run(cmd, cwd=None):
            calls.append(cmd)
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w):
            core = os.path.join(d, "FO4TerrainCore.esm")
            with open(core, "wb") as f:
                f.write(b"core bytes")
            readmes = {}
            for name, opts in (("with", []), ("without", ["--no-reload"])):
                out = os.path.join(d, name)
                mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe", "--star-map-all"] + opts)
                with open(os.path.join(out, "README.txt"), encoding="utf-8") as f:
                    readmes[name] = f.read()
        build, _comp, check, build2, _comp2, check2 = calls
        self.assertEqual((build[-1], check[-1]), ("--reload", "--reload"))       # build and check take the same stop
        self.assertNotIn("--reload", build2 + check2)
        self.assertIn("Plus the reload's stop FO4SF_MapMarkersHop", readmes["with"])
        self.assertNotIn("reload's stop", readmes["without"])

    def test_stage_adds_fo4_markers_from_the_core_stage(self):
        # --fo4-map-markers with --core-stage: the core's own stage folder gives the bounds, the fixed markers and the
        # BTD (its copy of the core must be --core), the export the markers; both dotnet runs get --extra
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        sys.path.insert(0, str(ROOT / "src"))
        import make_map_markers as mm
        import make_core64c
        calls, btds = [], []

        def fake_run(cmd, cwd=None):
            calls.append(cmd)
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        class FlatTerrain:
            def __init__(self, path):
                btds.append(path)

            def bilinear(self, xs, ys):
                return [3.0 for _ in xs]

        fixed = [{"tag": "RedRocket", "name": "Red Rocket Truck Stop", "src": "0211C0:Fallout4.esm",
                  "pos": [-989.2571, 1146.5143, 107.1429], "cell": [-10, 11]}]
        export = {"plugin": "Fallout4.esm", "world": "Commonwealth", "markers": [
            {"fid": "0001F2A9", "name": "Abernathy Farm", "pos": [-81000.0, 86000.0, 0]},
            {"fid": "0001F2AA", "name": None, "pos": [0, 0, 0]},
            {"fid": "0001F2AB", "name": "Far Away", "pos": [-300000.0, 0.0, 0]},
            {"fid": "00024FBE", "name": "Red Rocket Truck Stop", "pos": [-69230.0, 80240.0, 0]}]}   # on the fixed one

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w), \
                mock.patch.object(make_core64c, "Terrain", FlatTerrain):
            cs, core = os.path.join(d, "core_stage"), os.path.join(d, "FO4TerrainCore.esm")
            os.makedirs(cs)
            for path in (core, os.path.join(cs, "FO4TerrainCore.esm")):
                with open(path, "wb") as f:
                    f.write(b"core bytes")

            def params(markers):
                with open(os.path.join(cs, "overlays_params.json"), "w", encoding="utf-8-sig") as f:   # the PC's BOM
                    json.dump({"overlays": [{"btd_file": "Data/Terrain/W.btd", "bounds_min_m": -3200.0,
                                             "bounds_max_m": 3200.0, "map_markers": markers}]}, f)
            params(fixed)
            exp = os.path.join(d, "cw_markers.json")
            with open(exp, "w", encoding="utf-8") as f:
                json.dump(export, f)
            out = os.path.join(d, "stage")
            mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe",
                     "--fo4-map-markers", exp, "--core-stage", cs])
            self.assertEqual(btds, [os.path.join(cs, "Data", "Terrain", "W.btd")])
            with open(os.path.join(out, "extra_markers.json"), encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual([(m["tag"], m["name"], m["cell"]) for m in doc["markers"]],
                             [("M01F2A9", "Abernathy Farm", [-12, 12])])
            pos = doc["markers"][0]["pos"]
            self.assertAlmostEqual(pos[0], -81000.0 / 70, places=3)
            self.assertAlmostEqual(pos[1], 86000.0 / 70, places=3)
            self.assertEqual(pos[2], 3.0)                                     # the BTD ground, before the lift
            with open(os.path.join(out, "map_markers_left_out.json"), encoding="utf-8") as f:
                reasons = sorted(e["reason"] for e in json.load(f)["left_out"])
            self.assertEqual(len(reasons), 3)
            self.assertIn("no name", reasons)
            self.assertTrue(any(r.startswith("outside the overlay") for r in reasons), reasons)
            self.assertIn("Red Rocket Truck Stop: within 100 m of the fixed marker RedRocket", reasons)
            path = os.path.join(out, "extra_markers.json")
            build, _comp, check = calls
            star = os.path.join(out, "star_map.json")
            self.assertEqual(build[-5:], ["--extra", path, "--reload", "--star-map", star])
            self.assertEqual(check[-8:], ["check", os.path.join(out, "FO4SFMapMarkers.esm"), core, "--extra", path, "--reload",
                                          "--star-map", star])
            with open(os.path.join(out, "README.txt"), encoding="utf-8") as f:
                self.assertIn("Plus 1 markers of its own (extra_markers.json", f.read())
            # refusals: half the pair; a core stage holding another core build; a core already built with the markers
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s1"), "--fo4-map-markers", exp])
            self.assertIn("--core-stage goes with --fo4-map-markers or --landing", str(e.exception))
            with open(os.path.join(cs, "FO4TerrainCore.esm"), "wb") as f:
                f.write(b"another build")
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s2"), "--compiler", "PapyrusCompiler.exe",
                         "--fo4-map-markers", exp, "--core-stage", cs])
            self.assertIn("is not --core (another build)", str(e.exception))
            with open(os.path.join(cs, "FO4TerrainCore.esm"), "wb") as f:
                f.write(b"core bytes")
            params(fixed + [dict(doc["markers"][0])])
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s3"), "--compiler", "PapyrusCompiler.exe",
                         "--fo4-map-markers", exp, "--core-stage", cs])
            self.assertIn("it was built with --fo4-map-markers", str(e.exception))
        self.assertEqual(len(calls), 3)                                       # no dotnet run after a refusal

    def test_stage_adds_a_landing_spot_at_a_getpos_spot(self):
        # --landing x y (the merged frame, as getpos and the owner's snapshots give it) with --core-stage: the pad at
        # x, y less the merge offset, heights from the core stage's BTD; both dotnet runs get --landing
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        sys.path.insert(0, str(ROOT / "src"))
        import make_map_markers as mm
        import make_core64c
        calls = []

        def fake_run(cmd, cwd=None):
            calls.append(cmd)
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        class FlatTerrain:
            def __init__(self, path):
                pass

            def bilinear(self, xs, ys):
                return [3.0 for _ in xs]

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w), \
                mock.patch.object(make_core64c, "Terrain", FlatTerrain):
            cs, core = os.path.join(d, "core_stage"), os.path.join(d, "FO4TerrainCore.esm")
            os.makedirs(cs)
            for path in (core, os.path.join(cs, "FO4TerrainCore.esm")):
                with open(path, "wb") as f:
                    f.write(b"core bytes")
            with open(os.path.join(cs, "overlays_params.json"), "w", encoding="utf-8-sig") as f:
                json.dump({"overlays": [{"btd_file": "Data/Terrain/W.btd", "bounds_min_m": -3200.0,
                                         "bounds_max_m": 3200.0, "map_markers": []}]}, f)
            out = os.path.join(d, "stage")
            mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe",
                     "--landing", "-1959", "-493", "--core-stage", cs])
            path = os.path.join(out, "landing.json")
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual((doc["getpos"], doc["merge_offset"]), ([-1959.0, -493.0], [-1200.0, -2700.0]))
            spot = doc["landing"]
            self.assertEqual(spot["pad"]["pos"], [-759.0, 2207.0, 3.0])          # local = getpos less the offset
            self.assertEqual(spot["heading"]["pos"][2], 5.5)                     # its ground plus the tool's 2.5 m
            self.assertEqual(spot["name"], "Commonwealth Landing Area")
            build, _comp, check = calls
            star = os.path.join(out, "star_map.json")
            self.assertEqual(build[-5:], ["--landing", path, "--reload", "--star-map", star])
            self.assertEqual(check[-8:], ["check", os.path.join(out, "FO4SFMapMarkers.esm"), core, "--landing", path, "--reload",
                                          "--star-map", star])
            with open(os.path.join(out, "README.txt"), encoding="utf-8") as f:
                self.assertIn('Plus a ship landing spot "Commonwealth Landing Area" (landing.json): a pad at getpos -1959.0 -493.0', f.read())
            mm.main(["stage", "--core", core, "--out", os.path.join(d, "lift"), "--compiler", "PapyrusCompiler.exe",
                     "--landing", "-1959", "-493", "--core-stage", cs, "--z-lift", "1.0"])
            with open(os.path.join(d, "lift", "landing.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["landing"]["heading"]["pos"][2], 4.0)   # --z-lift lifts the heading too
            # refusals: no core stage; a pad less than a cell inside the overlay
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s1"), "--landing", "-1959", "-493"])
            self.assertIn("--core-stage goes with --fo4-map-markers or --landing", str(e.exception))
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s2"), "--compiler", "PapyrusCompiler.exe",
                         "--landing", "1950", "-493", "--core-stage", cs])
            self.assertIn("less than 100 m inside the overlay", str(e.exception))
        self.assertEqual(len(calls), 6)                                       # two stages, none after a refusal


if __name__ == "__main__":
    unittest.main()
