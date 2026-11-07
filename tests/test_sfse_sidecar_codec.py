"""Compile the portable P1 codec; synthetic bytes only, no SFSE DLL or game APIs."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.combined import sidecar  # noqa: E402

HARNESS = r'''
#include <exception>
#include <iostream>
#include <string>
#include "codec.h"

std::string unhex(const std::string& hex) {
    std::string out;
    for (std::size_t i = 0; i < hex.size(); i += 2)
        out.push_back(static_cast<char>(std::stoul(hex.substr(i, 2), nullptr, 16)));
    return out;
}

int main() {
    try {
        std::string op, name, input;
        std::getline(std::cin, op);
        std::getline(std::cin, name);
        std::getline(std::cin, input);
        name = unhex(name);
        input = unhex(input);
        if (op == "name") std::cout << focc::sidecar_name(name);
        else if (op == "hash") std::cout << focc::sha256_hex(input);
        else if (op == "encode") std::cout << focc::encode_sidecar(name, std::stoll(input));
        else if (op == "decode") {
            const auto d = focc::decode_sidecar(input, name);
            if (d.valid) std::cout << "valid\t" << d.counter;
            else std::cout << "invalid\t" << d.error;
        } else return 2;
    } catch (const std::exception& e) {
        std::cerr << "codec exception: " << e.what();
        return 3;
    }
}
'''


def envelope(name="focc_p1_a", counter=1, *, state=None):
    state = json.dumps({"counter": counter, "probe": "P1"}, sort_keys=True) if state is None else state
    # Keep raw state text so malformed/type-invalid states can have a matching checksum.
    fields = {"format": "focc-sidecar", "save_name": name, "schema": 1,
              "sha256": hashlib.sha256(state.encode("utf-8")).hexdigest()}
    return json.dumps(fields, sort_keys=True)[:-1] + ', "world_state": ' + state + '}'


class PortableCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = next((p for name in ("c++", "g++", "clang++", "cl") if (p := shutil.which(name))), None)
        if compiler is None:
            if os.environ.get("CI"):
                raise RuntimeError("portable codec tests need a C++20 compiler in CI")
            raise unittest.SkipTest("C++20 compiler unavailable; load an MSVC environment or install g++/clang++")
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        directory = Path(temp.name)
        source = directory / "codec_test.cpp"
        source.write_text(HARNESS, encoding="ascii")
        cls.binary = directory / ("codec_test.exe" if os.name == "nt" else "codec_test")
        includes = ROOT / "sfse" / "FOCCSidecar"
        sha = includes / "sha256.cpp"
        if Path(compiler).stem.lower() in ("cl", "clang-cl"):
            argv = [compiler, "/nologo", "/std:c++20", "/EHsc", "/O2", "/W4", f"/I{includes}",
                    str(source), str(sha), f"/Fe:{cls.binary}"]
        else:
            argv = [compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{includes}",
                    str(source), str(sha), "-o", str(cls.binary)]
        result = subprocess.run(argv, cwd=directory, capture_output=True, timeout=90)
        if result.returncode:
            raise AssertionError((result.stdout + result.stderr).decode("utf-8", "replace"))

    def call(self, mode, name="focc_p1_a", value=""):
        # Hex transports names/body bytes unchanged across Windows and POSIX console encodings.
        payload = f"{mode}\n{name.encode('utf-8').hex()}\n{value.encode('utf-8').hex()}\n".encode("ascii")
        result = subprocess.run([str(self.binary)], input=payload, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout.decode("utf-8")

    def refused(self, body, name="focc_p1_a"):
        self.assertTrue(self.call("decode", name, body).startswith("invalid\t"))

    def test_sha256_matches_hashlib_at_block_boundaries(self):
        for text in ("", "abc", *("x" * n for n in (55, 56, 63, 64, 119, 120, 1000))):
            with self.subTest(length=len(text)):
                self.assertEqual(self.call("hash", value=text), hashlib.sha256(text.encode()).hexdigest())

    def test_ascii_filename_matches_python(self):
        for name in ("focc_p1_a", ".", "...", '../bad:"<>?|*save', "a" * 79 + "z", "a" * 80 + "z",
                     'save "quoted" \\path', "tab\tline\ncontrol\x01"):
            with self.subTest(name=name):
                self.assertEqual(self.call("name", name), sidecar.sidecar_name(name))

    def test_ascii_envelopes_match_python_canonical_json(self):
        for name in ("focc_p1_a", 'quote" and slash\\', "tab\tnewline\n\x01"):
            for counter in (0, 1, 42, -(2**63), 2**63 - 1):
                with self.subTest(name=name, counter=counter):
                    self.assertEqual(self.call("encode", name, str(counter)), envelope(name, counter))

    def test_signed_counter_limits_and_zero_roundtrip(self):
        for counter in (-(2**63), -1, 0, 1, 2**63 - 1):
            with self.subTest(counter=counter):
                self.assertEqual(self.call("decode", value=envelope(counter=counter)), f"valid\t{counter}")

    def test_utf8_names_keep_their_own_writer_roundtrip(self):
        # Filename parity for non-ASCII is deliberately outside the documented P1 contract.
        for name in ("caf\u00e9", "\u0394\U0001f680"):
            with self.subTest(name=name):
                body = self.call("encode", name, "42")
                self.assertEqual(json.loads(body)["save_name"], name)
                self.assertEqual(self.call("decode", name, body), "valid\t42")

    def test_wrong_checksum_save_format_and_schema_are_refused(self):
        body = envelope()
        wrong_sum = json.loads(body)
        wrong_sum["sha256"] = "0" * 64
        for malformed in (json.dumps(wrong_sum, sort_keys=True), body.replace('"focc-sidecar"', '"other"'),
                          body.replace('"schema": 1', '"schema": 2')):
            with self.subTest(body=malformed):
                self.refused(malformed)
        self.refused(body, "another_save")

    def test_out_of_range_counters_refuse_without_throwing(self):
        for counter in (2**63, -(2**63) - 1, 10**100):
            with self.subTest(counter=counter):
                self.refused(envelope(counter=counter))

    def test_non_integer_counters_with_matching_checksums_are_refused(self):
        for token in ("1.5", "1e3", '"1"', "true", "null", "{}", "--1"):
            with self.subTest(counter=token):
                self.refused(envelope(state='{"counter": ' + token + ', "probe": "P1"}'))

    def test_wrong_or_missing_probe_state_is_refused(self):
        for state in ('{"counter": 1, "probe": "OTHER"}', '{"counter": 1}',
                      '{"counter": 1, "counter": 2, "probe": "P1"}'):
            with self.subTest(state=state):
                self.refused(envelope(state=state))

    def test_malformed_or_duplicate_envelopes_are_refused(self):
        body = envelope()
        for malformed in (body[:-1], body + " trailing junk", body + body,
                          body[:-1] + ', "schema": 2}',
                          body.replace('"schema": 1', '"schema": 1junk')):
            with self.subTest(body=malformed):
                self.refused(malformed)


if __name__ == "__main__":
    unittest.main()
