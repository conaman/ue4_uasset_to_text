#!/usr/bin/env python3

import hashlib
import json
import os
import struct
import tempfile
import unittest

import text_to_uasset
import uasset_diff
import uasset_diff3
import uasset_to_text as uasset


def make_summary(**overrides):
    summary = {
        "total_header_size": 64,
        "summary_size": 64,
        "name_count": 0,
        "name_offset": 0,
        "gatherable_text_data_count": 0,
        "gatherable_text_data_offset": 0,
        "export_count": 0,
        "export_offset": 0,
        "import_count": 0,
        "import_offset": 0,
        "soft_package_references_count": 0,
        "soft_package_references_offset": 0,
        "preload_dependency_count": -1,
        "preload_dependency_offset": 0,
        "depends_offset": 0,
    }
    summary.update(overrides)
    return summary


def make_minimal_uasset(*, package_source: int = 0) -> bytes:
    binary = bytearray()

    def write(fmt, *values):
        binary.extend(struct.pack("<" + fmt, *values))

    def write_fstring(value=""):
        if value:
            raw = value.encode("utf-8") + b"\x00"
            write("i", len(raw))
            binary.extend(raw)
        else:
            write("i", 0)

    def write_guid():
        write("IIII", 0, 0, 0, 0)

    def write_engine_version():
        write("HHHI", 4, 27, 0, 17703452)
        write_fstring()

    write("I", uasset.PACKAGE_FILE_TAG)
    write("i", -7)
    write("i", 864)
    write("i", uasset.VER_UE4_AUTOMATIC_VERSION)
    write("i", 0)
    write("i", 0)  # custom version count
    write("i", 0)  # placeholder TotalHeaderSize
    write_fstring()
    write("I", 0)  # package flags
    write("ii", 0, 0)  # name count, name offset
    write_fstring()  # localization id
    write("ii", 0, 0)  # gatherable text data
    write("ii", 0, 0)  # exports
    write("ii", 0, 0)  # imports
    write("i", 0)  # depends offset
    write("ii", 0, 0)  # soft package references
    write("i", 0)  # searchable names offset
    write("i", 0)  # thumbnail table offset
    write_guid()
    write_guid()  # persistent guid
    write("i", 0)  # generations count
    write_engine_version()
    write_engine_version()
    write("I", 0)  # compression flags
    write("i", 0)  # compressed chunks count
    write("I", package_source)
    write("i", 0)  # additional packages count
    write("iq", 0, 0)  # asset registry offset, bulk data start offset
    write("i", 0)  # world tile info data offset
    write("i", 0)  # chunk ids count
    write("ii", -1, 0)  # preload dependencies
    struct.pack_into("<i", binary, 24, len(binary))
    return bytes(binary)


class UAssetParserValidationTests(unittest.TestCase):
    def test_pretty_json_is_indented(self):
        text = uasset.format_json({"outer": {"inner": 1}}, compact=False, indent=4)

        self.assertIn('\n    "outer"', text)
        self.assertIn('\n        "inner"', text)

    def test_compact_json_omits_extra_whitespace(self):
        text = uasset.format_json({"outer": {"inner": 1}}, compact=True, indent=4)

        self.assertEqual(text, '{"outer":{"inner":1}}')

    def test_default_json_path_uses_current_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                self.assertEqual(
                    uasset.default_json_path("/tmp/Somewhere/Asset.uasset"),
                    os.path.join(os.getcwd(), "Asset.json"),
                )
            finally:
                os.chdir(old_cwd)

    def test_default_uasset_path_uses_current_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                self.assertEqual(
                    text_to_uasset.default_uasset_path("/tmp/Somewhere/Asset.json"),
                    os.path.join(os.getcwd(), "Asset.uasset"),
                )
            finally:
                os.chdir(old_cwd)

    def test_text_document_round_trips_to_original_bytes(self):
        binary = make_minimal_uasset()

        with tempfile.TemporaryDirectory() as temp_dir:
            uasset_path = os.path.join(temp_dir, "RoundTrip.uasset")
            text_path = os.path.join(temp_dir, "RoundTrip.json")
            restored_path = os.path.join(temp_dir, "Restored.uasset")
            with open(uasset_path, "wb") as file:
                file.write(binary)

            document = uasset.build_text_document(
                uasset_path,
                include_export_data=False,
                preview_bytes=0,
            )
            with open(text_path, "w", encoding="utf-8") as file:
                json.dump(document, file)

            text_to_uasset.restore_uasset(text_path, restored_path)

            with open(restored_path, "rb") as file:
                restored = file.read()
            self.assertEqual(restored, binary)
            self.assertEqual(
                document["sha256"],
                hashlib.sha256(restored).hexdigest(),
            )

    def test_uasset_diff_reports_metadata_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            left_path = os.path.join(temp_dir, "Left.uasset")
            right_path = os.path.join(temp_dir, "Right.uasset")
            with open(left_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=0))
            with open(right_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=1))

            diff_text = uasset_diff.diff_uassets(left_path, right_path, context=1)

        self.assertIn("--- " + left_path, diff_text)
        self.assertIn("+++ " + right_path, diff_text)
        self.assertIn('"package_source": 0', diff_text)
        self.assertIn('"package_source": 1', diff_text)

    def test_uasset_diff_ignores_paths_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            left_path = os.path.join(temp_dir, "Left.uasset")
            right_path = os.path.join(temp_dir, "Right.uasset")
            binary = make_minimal_uasset()
            with open(left_path, "wb") as file:
                file.write(binary)
            with open(right_path, "wb") as file:
                file.write(binary)

            diff_text = uasset_diff.diff_uassets(left_path, right_path)

        self.assertEqual(diff_text, "")

    def test_uasset_diff3_reports_one_sided_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            with open(base_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=0))
            with open(ours_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=1))
            with open(theirs_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=0))

            report = uasset_diff3.diff3_uassets(base_path, ours_path, theirs_path)

        self.assertEqual(report["summary"], {"changes": 2, "conflicts": 0})
        self.assertEqual(report["changes"][0]["path"], "/summary/package_source")
        self.assertEqual(report["changes"][0]["status"], "ours_changed")
        self.assertEqual(report["changes"][0]["base"], 0)
        self.assertEqual(report["changes"][0]["ours"], 1)
        self.assertEqual(report["changes"][0]["theirs"], 0)

    def test_uasset_diff3_reports_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            with open(base_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=0))
            with open(ours_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=1))
            with open(theirs_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=2))

            report = uasset_diff3.diff3_uassets(base_path, ours_path, theirs_path)

        self.assertEqual(report["summary"], {"changes": 0, "conflicts": 2})
        self.assertEqual(report["conflicts"][0]["path"], "/summary/package_source")
        self.assertEqual(report["conflicts"][0]["status"], "conflict")
        self.assertEqual(report["conflicts"][0]["base"], 0)
        self.assertEqual(report["conflicts"][0]["ours"], 1)
        self.assertEqual(report["conflicts"][0]["theirs"], 2)

    def test_uasset_diff3_ignores_paths_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            binary = make_minimal_uasset()
            with open(base_path, "wb") as file:
                file.write(binary)
            with open(ours_path, "wb") as file:
                file.write(binary)
            with open(theirs_path, "wb") as file:
                file.write(binary)

            report = uasset_diff3.diff3_uassets(base_path, ours_path, theirs_path)

        self.assertEqual(report["summary"], {"changes": 0, "conflicts": 0})
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["conflicts"], [])

    def test_name_entry_length_is_bounded_like_ue4(self):
        data = struct.pack("<i", uasset.MAX_NAME_CODE_UNITS + 1)
        reader = uasset.Reader(data, "<memory>")
        summary = {
            "name_offset": 0,
            "name_count": 1,
            "effective_file_version_ue4": uasset.VER_UE4_NAME_HASHES_SERIALIZED - 1,
        }

        with self.assertRaisesRegex(uasset.UAssetError, "implausible name entry length"):
            uasset.read_name_map(reader, summary)

    def test_preview_rejects_negative_export_size(self):
        previews = uasset.preview_export_data(
            b"abcdef",
            [{"index": 0, "serial_offset": 2, "serial_size": -1}],
            4,
        )

        self.assertFalse(previews[0]["available_in_uasset"])
        self.assertNotIn("hex_preview", previews[0])
        self.assertNotIn("ascii_preview", previews[0])

    def test_summary_rejects_negative_table_count(self):
        with self.assertRaisesRegex(uasset.UAssetError, "negative name_count"):
            uasset.validate_summary(make_summary(name_count=-1), file_size=128)

    def test_summary_requires_offsets_for_non_empty_tables(self):
        with self.assertRaisesRegex(uasset.UAssetError, "missing export map offset"):
            uasset.validate_summary(make_summary(export_count=1), file_size=128)

    def test_version_rejects_newer_ue4_packages(self):
        with self.assertRaisesRegex(uasset.UAssetError, "newer than this parser"):
            uasset.validate_supported_ue4_version(uasset.VER_UE4_AUTOMATIC_VERSION + 1, 0)


if __name__ == "__main__":
    unittest.main()
