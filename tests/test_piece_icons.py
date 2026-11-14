"""src/fo4sf/workshop/piece_icons.py: the build pieces kit's pictures (128 x 128 BC3, DX10 header, drawn, nothing from either game),
and the texture archive check of scripts/verify_packed_experiment.py on a synthetic DX10 archive (no Archive2)."""
import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from ba2_fixture import general_archive, texture_archive  # noqa: E402
from fo4sf import ba2  # noqa: E402
from fo4sf.workshop import piece_icons as pi  # noqa: E402
import verify_packed_experiment as vpe  # noqa: E402


def decode(dds):
    """RGB of every pixel of a 128 x 128 BC3 body (alpha ignored)."""
    d = dds[148:]
    img = [[None] * 128 for _ in range(128)]
    for b in range(1024):
        c0, c1, idx = struct.unpack("<HHI", d[b * 16 + 8:b * 16 + 16])
        p0, p1 = pi._unpack(c0), pi._unpack(c1)
        pal = [p0, p1, tuple((2 * a + c) // 3 for a, c in zip(p0, p1)), tuple((a + 2 * c) // 3 for a, c in zip(p0, p1))]
        for k in range(16):
            img[(b // 32) * 4 + k // 4][(b % 32) * 4 + k % 4] = pal[(idx >> (2 * k)) & 3]
    return img


class PictureTests(unittest.TestCase):
    def test_the_file_is_a_128_square_bc3_with_a_dx10_header_one_mip(self):
        d = pi.dds(1, "FO4Core_junkwall01", "FO4 junk wall")
        self.assertEqual(d[:4], b"DDS ")
        self.assertEqual(len(d), 4 + 124 + 20 + 128 * 128)                              # one mip of BC3: 16 bytes per 4 x 4 block
        self.assertEqual((struct.unpack_from("<I", d, 12)[0], struct.unpack_from("<I", d, 16)[0], struct.unpack_from("<I", d, 28)[0]), (128, 128, 1))
        self.assertEqual(d[84:88], b"DX10")
        self.assertEqual(struct.unpack_from("<5I", d, 128), (77, 3, 0, 1, 0))             # DXGI 77 (BC3), texture 2D, one array slice
        self.assertEqual(pi.dds_header(), ba2._dds_header_dx10(128, 128, 1, 77, False))   # what fo4sf.ba2 regenerates from an archive entry

    def test_the_path_is_the_programs_format_plugin_masked_id_suffix(self):
        self.assertEqual(pi.icon_path("FO4SFBuildPieces.esm", 0x802), "Textures/Interface/WorkshopIcons/FO4SFBuildPieces.esm/00000802cl.dds")
        self.assertEqual(pi.icon_path("FO4SFBuildPieces.esm", 0x01000803), "Textures/Interface/WorkshopIcons/FO4SFBuildPieces.esm/00000803cl.dds")

    def test_the_picture_has_a_frame_a_shape_and_text_and_pieces_differ(self):
        img = decode(pi.dds(1, "FO4Core_junkwall01"))
        self.assertGreater(sum(img[0][x][0] for x in range(128)) / 128, 150)               # the light frame at the top row
        self.assertNotEqual(img[46][64], img[10][64])                                       # shape in the middle, tile behind
        light = [(x, y) for y in range(92, 120) for x in range(128) if min(img[y][x]) > 200]
        self.assertGreater(len(light), 100)                                                 # initials in the lower part
        again = pi.dds(1, "FO4Core_junkwall01")
        self.assertEqual(again, pi.dds(1, "FO4Core_junkwall01"))                            # stable
        self.assertNotEqual(again, pi.dds(2, "FO4Core_junkwall02"))

    def test_the_shapes_cycle_with_the_piece_number(self):
        mid = [decode(pi.dds(n, "x"))[46][36] for n in (1, 2, 3, 4)]                        # 28 px left of the centre on its middle row: square, circle and diamond cover it, the triangle does not
        tile = (34, 38, 46)
        self.assertTrue(all(abs(c - d) < 12 for c, d in zip(mid[2], tile)))
        for n in (0, 1, 3):
            self.assertGreater(sum(abs(c - d) for c, d in zip(mid[n], tile)), 60)

    def test_labels_are_initials_and_a_number(self):
        self.assertEqual(pi.label("FO4Core_junkwall01"), "JU1")
        self.assertEqual(pi.label("FO4Core_BedMetal01"), "BM1")
        self.assertEqual(pi.label("FO4Core_woodcrate"), "WO")
        self.assertEqual(pi.label(""), "?")
        self.assertTrue(all(c in pi._GLYPH for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?"))


class TextureArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.files = {f"Textures/Interface/WorkshopIcons/FO4SFBuildPieces.esm/0000080{n}cl.dds": pi.dds(n, f"FO4Core_x{n}") for n in (2, 3, 4)}
        self.inputs = {"Data/" + k: hashlib.sha256(v).hexdigest() for k, v in self.files.items()}
        self.path = Path(self.tmp.name) / "t.ba2"

    def test_the_synthetic_archive_reads_back_as_the_pinned_files(self):
        self.path.write_bytes(texture_archive(self.files))
        a = ba2.Ba2(str(self.path))
        self.assertEqual((a.kind, len(a.entries), a.entries[0].dxgi, a.entries[0].mips), ("DX10", 3, 77, 1))
        vpe.verify_texture_archive(str(self.path), self.inputs)

    def test_a_missing_extra_or_changed_texture_is_refused(self):
        names = list(self.files)
        for variant, text in ((dict(list(self.files.items())[:2]), "do not exactly cover"),
                              ({**self.files, "Textures/x/extra.dds": pi.dds(1, "e")}, "do not exactly cover"),
                              ({**self.files, names[0]: pi.dds(1, "changed")}, "differs from pinned")):
            self.path.write_bytes(texture_archive(variant))
            with self.assertRaises(ValueError) as e:
                vpe.verify_texture_archive(str(self.path), self.inputs)
            self.assertIn(text, str(e.exception))

    def test_a_general_archive_is_not_a_texture_archive(self):
        self.path.write_bytes(general_archive(dict(self.files)))
        with self.assertRaises(ValueError):
            vpe.verify_texture_archive(str(self.path), self.inputs)


if __name__ == "__main__":
    unittest.main()
