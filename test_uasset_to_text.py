#!/usr/bin/env python3

import struct
import unittest

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


class UAssetParserValidationTests(unittest.TestCase):
    def test_pretty_json_is_indented(self):
        text = uasset.format_json({"outer": {"inner": 1}}, compact=False, indent=4)

        self.assertIn('\n    "outer"', text)
        self.assertIn('\n        "inner"', text)

    def test_compact_json_omits_extra_whitespace(self):
        text = uasset.format_json({"outer": {"inner": 1}}, compact=True, indent=4)

        self.assertEqual(text, '{"outer":{"inner":1}}')

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
