"""Exterior lights through the actual terrain writer (dotnet/TerrainOverlays) on the synthetic master of
test_terrain_reference_identity (dotnet/TerrainIdentityFixture), never a game: every earlier FormID stays, the light
REFRs take new ids after every other record, one LIGH per base follows, and the raw records carry the mapped fields
(docs/terrain/exterior-lights.md)."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import dotnet_fast  # noqa: E402,F401  (FAL-558: stager `dotnet run` calls use the built dll)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
import test_terrain_reference_identity as tri  # noqa: E402  (module import: its TestCase is not collected twice)

spec = importlib.util.spec_from_file_location("make_core64c", ROOT / "scripts" / "terrain" / "make_core64c.py")
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)
import overlay_records  # noqa: E402

FIRE = {"edid": "FO4Core_ligh_000aaa_fallout4", "fo4_base": "000AAA:Fallout4.esm", "time": -1, "radius": 3.657143,
        "color": [237, 168, 122], "flags": 1, "type": 0, "falloff": 1.0, "fov": 90.0, "near_clip": 0.103106,
        "flicker": [0.363636, 0.8, 0.011429], "flicker_effect": 1, "lumens": 17655,
        "bounds": [[-0.128571, -0.142857, -0.257143], [0.128571, 0.142857, 0.171429]], "random_anim_start": True}
SPOT = dict(FIRE, edid="FO4Core_ligh_000bbb_fallout4", fo4_base="000BBB:Fallout4.esm", color=[255, 255, 255],
            flags=0x41, type=2, flicker_effect=0, lumens=4454, flicker=[1.0, 0.0, 0.0], random_anim_start=False)


def subrecords(payload):
    out, pos = [], 0
    while pos < len(payload):
        sig, size = payload[pos:pos + 4], struct.unpack_from("<H", payload, pos + 4)[0]
        out.append((sig, payload[pos + 6:pos + 6 + size]))
        pos += 6 + size
    return out


def field(payload, sig):
    return next((d for s, d in subrecords(payload) if s == sig), None)


class TerrainLightsWriterTests(unittest.TestCase):
    setUpClass = classmethod(tri.TerrainReferenceIdentityTests.setUpClass.__func__)
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    promote = tri.TerrainReferenceIdentityTests.promote

    def with_lights(self, objects):
        obj = copy.deepcopy(objects)
        obj["light_bases"] = [copy.deepcopy(FIRE), copy.deepcopy(SPOT)]
        obj["lights"] = [
            {"src": "00A001:Fallout4.esm", "edid": FIRE["edid"], "cell": [0, 0], "pos": [5, 5, 3], "rot": [0, 0, 1],
             "scale": 1.0, "disabled": False, "radius": -0.5, "lighting": {"fov": 0.0, "fade": 1.6, "near_clip": 0.0},
             "flags": 0x30100},                                    # FO4's DoesNotLightWater | NeverFades | DoesNotLightLandscape
            {"src": "00A002:Fallout4.esm", "edid": SPOT["edid"], "cell": [1, 1], "pos": [150, 150, 4], "rot": [0.5, 0, 0],
             "scale": 1.0, "disabled": True, "radius": None, "lighting": None, "flags": 0x100},
            {"src": "00A003:Fallout4.esm", "edid": FIRE["edid"], "cell": [0, 1], "pos": [5, 120, 4], "rot": [0, 0, 2],
             "scale": 1.5, "disabled": False, "radius": 2.0, "lighting": {"fov": -10.0, "fade": 0.25, "near_clip": 0.5},
             "flags": 0}]                                          # a FO4 light that lights water
        return obj

    def build_pair(self, name, items=()):
        base = self.promote([1], items)                            # one container: its CONT base must keep its id too
        before, old_stage = self.run_writer(base, f"{name}-before")
        after, new_stage = self.run_writer(self.with_lights(base), f"{name}-after")
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        return old_stage, new_stage

    def test_lights_are_appended_after_every_existing_record(self):
        old_stage, new_stage = self.build_pair("append")
        old = json.loads((old_stage / "formids.json").read_text())
        new = json.loads((new_stage / "formids.json").read_text())
        for k in ("bases", "refs", "containers"):
            self.assertEqual(new[k], old[k])
        self.assertNotIn("lights", old)
        old_records, new_records = tri.records(old_stage / "Synthetic.esm"), tri.records(new_stage / "Synthetic.esm")
        for key, rec in old_records.items():                       # every earlier record: same id, same bytes
            self.assertEqual(new_records[key], rec)
        first = max(old_records) + 1
        srcs = ["00A001:Fallout4.esm", "00A002:Fallout4.esm", "00A003:Fallout4.esm"]
        self.assertEqual([int(new["lights"][s]["ref"], 16) for s in srcs], [first, first + 1, first + 2])
        self.assertEqual([int(new["lights"][s]["base"], 16) for s in srcs], [first + 3, first + 4, first + 3])
        self.assertEqual(max(new_records), first + 4)
        cells = {k: struct.unpack_from("<ii", field(v[1], b"XCLC")) for k, v in new_records.items()
                 if v[0] == b"CELL" and field(v[1], b"XCLC") is not None}
        objects = self.with_lights(self.promote([1]))
        for e in objects["lights"]:
            sig, payload, owner, flags = new_records[int(new["lights"][e["src"]]["ref"], 16)]
            self.assertEqual(sig, b"REFR")
            self.assertEqual(tuple(e["cell"]), cells[owner])
            self.assertEqual(struct.unpack("<I", field(payload, b"NAME"))[0], 0x01000000 | int(new["lights"][e["src"]]["base"], 16))
            self.assertEqual(flags & 0x30100, e["flags"])           # the FO4 reference's own light bits (#246's review)
            self.assertEqual(bool(flags & 0x800), e["disabled"])
            data = struct.unpack("<6f", field(payload, b"DATA"))
            for u, v in zip(data, e["pos"] + e["rot"]):
                self.assertAlmostEqual(u, v, places=5)
            xrds = field(payload, b"XRDS")
            self.assertEqual(xrds is None, e["radius"] is None)
            if xrds is not None:
                self.assertAlmostEqual(struct.unpack("<f", xrds)[0], e["radius"], places=5)
            xlig = field(payload, b"XLIG")
            self.assertEqual(xlig is None, e["lighting"] is None)
            if xlig is not None:
                self.assertEqual(len(xlig), 32)                    # 6 floats + the two vanilla trailing words
                fov, fade, cap, bias, near, vol = struct.unpack_from("<6f", xlig)
                self.assertAlmostEqual(fov, e["lighting"]["fov"], places=5)
                self.assertAlmostEqual(fade, e["lighting"]["fade"], places=5)
                self.assertAlmostEqual(near, e["lighting"]["near_clip"], places=5)
                self.assertEqual((cap, bias, vol), (0.0, 0.0, 0.0))
                self.assertEqual(xlig[24:], bytes.fromhex("abababab00ababab"))
            scale = field(payload, b"XSCL")
            self.assertEqual(scale is None, e["scale"] == 1.0)
        for b in (FIRE, SPOT):
            key = next(int(new["lights"][e["src"]]["base"], 16) for e in objects["lights"] if e["edid"] == b["edid"])
            sig, payload, _owner, flags = new_records[key]
            self.assertEqual(sig, b"LIGH")
            self.assertEqual(field(payload, b"EDID").rstrip(b"\0").decode(), b["edid"])
            self.assertIsNone(field(payload, b"FLTR"))           # the template's CK object-window filter is dropped
            self.assertEqual(bool(flags & 0x10000), b["random_anim_start"])
            d = field(payload, b"DAT2")
            self.assertEqual(struct.unpack_from("<i", d, 0)[0], b["time"])
            self.assertAlmostEqual(struct.unpack_from("<f", d, 4)[0], b["radius"], places=5)
            self.assertEqual(list(d[8:12]), b["color"] + [0])
            self.assertEqual(struct.unpack_from("<I", d, 12)[0], b["flags"])
            falloff, fov, near, per, amp, mov = struct.unpack_from("<6f", d, 16)
            for u, v in zip((falloff, fov, near, per, amp, mov), [b["falloff"], b["fov"], b["near_clip"]] + b["flicker"]):
                self.assertAlmostEqual(u, v, places=5)
            self.assertEqual(struct.unpack_from("<I", d, 52)[0], b["lumens"])
            self.assertEqual((d[56], d[57]), (b["type"], b["flicker_effect"]))
            bounds = struct.unpack("<6f", field(payload, b"OBND"))
            for u, v in zip(bounds, b["bounds"][0] + b["bounds"][1]):
                self.assertAlmostEqual(u, v, places=5)

    def test_the_core64c_check_accepts_the_written_lights(self):
        _old_stage, new_stage = self.build_pair("check")
        objects = self.with_lights(self.promote([1]))
        ids = json.loads((new_stage / "formids.json").read_text())
        plugin = overlay_records.walk_plugin(str(new_stage / "Synthetic.esm"))
        mk.check_light_identities(objects, ids)
        self.assertEqual(mk.light_record_problems(plugin["records"], 1 << 24, objects, ids), [])
        first, last = mk.lights_after(plugin["records"], len(plugin["masters"]), ids)
        self.assertGreater(first, last)
        # and it notices a light REFR bound to the wrong base
        wrong = copy.deepcopy(objects)
        wrong["lights"][0]["edid"] = SPOT["edid"]
        self.assertTrue(any("base" in p for p in mk.light_record_problems(plugin["records"], 1 << 24, wrong, ids)))

    def test_lights_follow_the_containers_and_items_of_main(self):
        # merged with #235: a build with a CONT and a MISC promotion keeps every id and byte, the lights come after both
        old_stage, new_stage = self.build_pair("items", items=(2,))
        old = json.loads((old_stage / "formids.json").read_text())
        new = json.loads((new_stage / "formids.json").read_text())
        for k in ("bases", "refs", "containers", "items"):
            self.assertEqual(new[k], old[k])
        old_records, new_records = tri.records(old_stage / "Synthetic.esm"), tri.records(new_stage / "Synthetic.esm")
        for key, rec in old_records.items():
            self.assertEqual(new_records[key], rec)
        misc = [k for k, v in new_records.items() if v[0] == b"MISC"]
        self.assertEqual(len(misc), 1)
        first = max(old_records) + 1
        self.assertGreater(first, misc[0])
        self.assertEqual(sorted(int(v["ref"], 16) for v in new["lights"].values()), [first, first + 1, first + 2])
        objects = self.with_lights(self.promote([1], (2,)))
        mk.check_light_identities(objects, new)
        mk.check_reference_slots(objects, new)
        plugin = overlay_records.walk_plugin(str(new_stage / "Synthetic.esm"))
        self.assertEqual(mk.light_record_problems(plugin["records"], 1 << 24, objects, new), [])
        self.assertEqual(mk.promoted_record_check(plugin["records"], 1 << 24, objects, new), [])

    def test_an_empty_light_list_writes_the_build_without_lights(self):
        base = self.promote([1])
        a, sa = self.run_writer(base, "empty-a")
        empty = dict(copy.deepcopy(base), lights=[], light_bases=[])
        b, sb = self.run_writer(empty, "empty-b")
        self.assertEqual((a.returncode, b.returncode), (0, 0), a.stderr + b.stderr)
        self.assertEqual((sa / "Synthetic.esm").read_bytes(), (sb / "Synthetic.esm").read_bytes())
        self.assertEqual((sa / "formids.json").read_bytes(), (sb / "formids.json").read_bytes())

    def test_bad_light_inputs_do_not_replace_the_plugin_or_map(self):
        good = self.with_lights(self.promote([1]))
        proc, stage = self.run_writer(good, "light-refusals")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pinned = {n: (stage / n).read_bytes() for n in ("Synthetic.esm", "formids.json")}
        invalid = []
        claimed = copy.deepcopy(good)
        claimed["lights"][0]["reference_index"] = 0                # a light has no original slot
        invalid.append(claimed)
        alias = copy.deepcopy(good)
        alias["lights"][0]["src"] = good["refs"][0]["src"].lower()  # the same source as a reserved REFR
        invalid.append(alias)
        alias_cont = copy.deepcopy(good)
        alias_cont["lights"][1]["src"] = good["containers"][0]["src"]
        invalid.append(alias_cont)
        twice = copy.deepcopy(good)
        twice["lights"][2]["src"] = twice["lights"][0]["src"]
        invalid.append(twice)
        unknown = copy.deepcopy(good)
        unknown["lights"][1]["edid"] = "FO4Core_ligh_ffffff_fallout4"
        invalid.append(unknown)
        base_twice = copy.deepcopy(good)
        base_twice["light_bases"].append(copy.deepcopy(FIRE))
        invalid.append(base_twice)
        outside = copy.deepcopy(good)
        outside["lights"][0]["cell"] = [5, 5]
        invalid.append(outside)
        empty_src = copy.deepcopy(good)
        empty_src["lights"][0]["src"] = " "
        invalid.append(empty_src)
        for flags in (0x800, 0x200, -1, None):                     # only the three carried REFR bits
            bad_flags = copy.deepcopy(good)
            bad_flags["lights"][0]["flags"] = flags
            invalid.append(bad_flags)
        no_flags = copy.deepcopy(good)
        del no_flags["lights"][0]["flags"]
        invalid.append(no_flags)
        for objects in invalid:
            proc, _ = self.run_writer(objects, "light-refusals")
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)


class LightsAfterTerminalsWriterTests(unittest.TestCase):
    """Merged with #241: a build that promotes containers, items, activators and terminals (each TERM with its own TMLM
    menu) keeps every id and byte when lights are added, and the lights come after the menus."""
    setUpClass = classmethod(tri.ActivatorTerminalWriterTests.setUpClass.__func__)
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    promote_all = tri.ActivatorTerminalWriterTests.promote_all
    BODY = tri.ActivatorTerminalWriterTests.BODY

    def test_lights_follow_the_terminal_menus(self):
        base = self.promote_all()
        lit = copy.deepcopy(base)
        lit["light_bases"] = [copy.deepcopy(FIRE)]
        lit["lights"] = [{"src": "00A001:Fallout4.esm", "edid": FIRE["edid"], "cell": [0, 0], "pos": [5, 5, 3],
                          "rot": [0, 0, 1], "scale": 1.0, "disabled": False, "radius": None, "lighting": None,
                          "flags": 0x100}]
        before, old_stage = self.run_writer(base, "lit-term-before")
        after, new_stage = self.run_writer(lit, "lit-term-after")
        self.assertEqual((before.returncode, after.returncode), (0, 0), before.stderr + after.stderr)
        old = json.loads((old_stage / "formids.json").read_text())
        new = json.loads((new_stage / "formids.json").read_text())
        for k in ("bases", "refs", "containers", "items", "activators", "terminals"):
            self.assertEqual(new[k], old[k])
        old_records, new_records = tri.records(old_stage / "Synthetic.esm"), tri.records(new_stage / "Synthetic.esm")
        for key, rec in old_records.items():
            self.assertEqual(new_records[key], rec)
        menus = {int(v["menu"], 16) for v in new["terminals"].values()}
        self.assertEqual(int(new["lights"]["00A001:Fallout4.esm"]["ref"], 16), max(old_records) + 1)
        self.assertGreater(max(old_records), max(menus) - 1)
        mk.check_light_identities(lit, new)
        mk.check_reference_slots(lit, new)
        plugin = overlay_records.walk_plugin(str(new_stage / "Synthetic.esm"))
        self.assertEqual(mk.light_record_problems(plugin["records"], 1 << 24, lit, new), [])
        self.assertEqual(mk.promoted_record_check(plugin["records"], 1 << 24, lit, new), [])


if __name__ == "__main__":
    unittest.main()
