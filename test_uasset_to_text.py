#!/usr/bin/env python3

import contextlib
import hashlib
import io
import json
import os
import struct
import tempfile
import unittest

import text_to_uasset
import uasset_diff
import uasset_diff3
import uasset_p4_common
import uasset_p4merge
import uasset_to_text as uasset


TOOL_VERSION = "2026-04-26"


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


def write_fake_p4merge(tool_path: str, log_path: str) -> None:
    script = "\n".join(
        [
            "#!/usr/bin/env python3",
            "import json",
            "import sys",
            f"with open({log_path!r}, 'w', encoding='utf-8') as file:",
            "    json.dump(sys.argv[1:], file)",
            "",
        ]
    )
    with open(tool_path, "w", encoding="utf-8") as file:
        file.write(script)
    os.chmod(tool_path, 0o755)


class UAssetParserValidationTests(unittest.TestCase):
    def test_script_versions_use_korean_release_date(self):
        modules = (
            text_to_uasset,
            uasset,
            uasset_diff,
            uasset_diff3,
            uasset_p4_common,
            uasset_p4merge,
        )
        for module in modules:
            self.assertEqual(module.TOOL_VERSION, TOOL_VERSION)

    def test_cli_scripts_print_version(self):
        modules = (
            text_to_uasset,
            uasset,
            uasset_diff,
            uasset_diff3,
            uasset_p4merge,
        )
        for module in modules:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as caught:
                    module.parse_args(["--version"])
            self.assertEqual(caught.exception.code, 0)
            self.assertIn(TOOL_VERSION, stdout.getvalue())

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

    def test_uasset_p4merge_runs_2_way_compare_with_json_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_path = os.path.join(temp_dir, "fake_p4merge.py")
            log_path = os.path.join(temp_dir, "argv.json")
            left_path = os.path.join(temp_dir, "Left.uasset")
            right_path = os.path.join(temp_dir, "Right.uasset")
            write_fake_p4merge(tool_path, log_path)
            with open(left_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=0))
            with open(right_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=1))

            run = uasset_p4merge.run_uasset_p4merge(
                [left_path, right_path],
                tool=tool_path,
                temp_root=temp_dir,
            )

            with open(log_path, "r", encoding="utf-8") as file:
                p4_args = json.load(file)
            with open(p4_args[0], "r", encoding="utf-8") as file:
                left_json = json.load(file)

        self.assertEqual(run.returncode, 0)
        self.assertEqual(len(p4_args), 2)
        self.assertTrue(os.path.basename(p4_args[0]).startswith("left_Left.uasset"))
        self.assertTrue(os.path.basename(p4_args[1]).startswith("right_Right.uasset"))
        self.assertEqual(left_json["summary"]["package_source"], 0)

    def test_uasset_p4merge_runs_3_way_in_perforce_argument_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_path = os.path.join(temp_dir, "fake_p4merge.py")
            log_path = os.path.join(temp_dir, "argv.json")
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            result_path = os.path.join(temp_dir, "Merged.json")
            write_fake_p4merge(tool_path, log_path)
            with open(base_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=0))
            with open(ours_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=1))
            with open(theirs_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=2))

            run = uasset_p4merge.run_uasset_p4merge(
                [base_path, ours_path, theirs_path],
                tool=tool_path,
                result_path=result_path,
                temp_root=temp_dir,
            )

            with open(log_path, "r", encoding="utf-8") as file:
                p4_args = json.load(file)
            with open(result_path, "r", encoding="utf-8") as file:
                result_json = json.load(file)

        self.assertEqual(run.returncode, 0)
        self.assertEqual(len(p4_args), 4)
        self.assertTrue(os.path.basename(p4_args[0]).startswith("base_Base.uasset"))
        self.assertTrue(os.path.basename(p4_args[1]).startswith("theirs_Theirs.uasset"))
        self.assertTrue(os.path.basename(p4_args[2]).startswith("ours_Ours.uasset"))
        self.assertEqual(p4_args[3], os.path.abspath(result_path))
        self.assertEqual(result_json["summary"]["package_source"], 1)

    def test_uasset_p4merge_prints_result_path_to_stdout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_path = os.path.join(temp_dir, "fake_p4merge.py")
            log_path = os.path.join(temp_dir, "argv.json")
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            result_path = os.path.join(temp_dir, "Merged.json")
            write_fake_p4merge(tool_path, log_path)
            for path in (base_path, ours_path, theirs_path):
                with open(path, "wb") as file:
                    file.write(make_minimal_uasset())

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = uasset_p4merge.main(
                    [
                        base_path,
                        ours_path,
                        theirs_path,
                        "--tool",
                        tool_path,
                        "--result",
                        result_path,
                        "--temp-dir",
                        temp_dir,
                    ]
                )

        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue(), os.path.abspath(result_path) + "\n")
        self.assertIn("merge result JSON:", stderr.getvalue())

    def test_uasset_p4merge_rejects_uasset_result_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_path = os.path.join(temp_dir, "fake_p4merge.py")
            log_path = os.path.join(temp_dir, "argv.json")
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            write_fake_p4merge(tool_path, log_path)
            for path in (base_path, ours_path, theirs_path):
                with open(path, "wb") as file:
                    file.write(make_minimal_uasset())

            with self.assertRaisesRegex(uasset_p4_common.P4ToolError, ".json"):
                uasset_p4merge.run_uasset_p4merge(
                    [base_path, ours_path, theirs_path],
                    tool=tool_path,
                    result_path=ours_path,
                    temp_root=temp_dir,
                )

    def test_uasset_p4merge_refuses_to_overwrite_existing_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_path = os.path.join(temp_dir, "fake_p4merge.py")
            log_path = os.path.join(temp_dir, "argv.json")
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            result_path = os.path.join(temp_dir, "Merged.json")
            write_fake_p4merge(tool_path, log_path)
            for path in (base_path, ours_path, theirs_path):
                with open(path, "wb") as file:
                    file.write(make_minimal_uasset())
            with open(result_path, "w", encoding="utf-8") as file:
                file.write("keep me")

            with self.assertRaisesRegex(uasset_p4_common.P4ToolError, "already exists"):
                uasset_p4merge.run_uasset_p4merge(
                    [base_path, ours_path, theirs_path],
                    tool=tool_path,
                    result_path=result_path,
                    temp_root=temp_dir,
                )

            with open(result_path, "r", encoding="utf-8") as file:
                result_text = file.read()

        self.assertEqual(result_text, "keep me")

    def test_uasset_p4merge_can_overwrite_existing_result_when_requested(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_path = os.path.join(temp_dir, "fake_p4merge.py")
            log_path = os.path.join(temp_dir, "argv.json")
            base_path = os.path.join(temp_dir, "Base.uasset")
            ours_path = os.path.join(temp_dir, "Ours.uasset")
            theirs_path = os.path.join(temp_dir, "Theirs.uasset")
            result_path = os.path.join(temp_dir, "Merged.json")
            write_fake_p4merge(tool_path, log_path)
            with open(base_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=0))
            with open(ours_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=1))
            with open(theirs_path, "wb") as file:
                file.write(make_minimal_uasset(package_source=2))
            with open(result_path, "w", encoding="utf-8") as file:
                file.write("replace me")

            run = uasset_p4merge.run_uasset_p4merge(
                [base_path, ours_path, theirs_path],
                tool=tool_path,
                result_path=result_path,
                overwrite_result=True,
                temp_root=temp_dir,
            )

            with open(result_path, "r", encoding="utf-8") as file:
                result_json = json.load(file)

        self.assertEqual(run.returncode, 0)
        self.assertEqual(result_json["summary"]["package_source"], 1)

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
