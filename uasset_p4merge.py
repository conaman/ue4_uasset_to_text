#!/usr/bin/env python3
"""
Open Perforce P4Merge on JSON converted from .uasset files.
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import sys
from dataclasses import dataclass

import uasset_p4_common
import uasset_to_text


TOOL_VERSION = "2026-04-26"

P4MERGE_EXECUTABLE_PATHS = (
    "/Applications/p4merge.app/Contents/Resources/launchp4merge",
    "/Applications/P4Merge.app/Contents/Resources/launchp4merge",
    "/Applications/P4V.app/Contents/Resources/launchp4merge",
)


@dataclass
class P4MergeRun:
    returncode: int
    temp_dir: str
    command: list[str]
    result_path: str | None


def resolve_p4merge_tool(explicit_tool: str | None = None) -> list[str]:
    return uasset_p4_common.resolve_tool(
        explicit_tool=explicit_tool,
        env_names=("P4MERGE", "MERGE"),
        executable_names=("p4merge", "launchp4merge"),
        executable_paths=P4MERGE_EXECUTABLE_PATHS,
        tool_label="P4Merge",
    )


def write_json_files(
    input_paths: list[str],
    labels: tuple[str, ...],
    temp_dir: str,
    *,
    full_text: bool,
    keep_paths: bool,
    include_export_data: bool,
    preview_bytes: int,
    indent: int,
) -> list[str]:
    json_paths: list[str] = []
    for label, input_path in zip(labels, input_paths):
        json_path = os.path.join(
            temp_dir,
            uasset_p4_common.safe_json_name(label, input_path),
        )
        uasset_p4_common.write_uasset_json(
            input_path,
            json_path,
            full_text=full_text,
            keep_paths=keep_paths,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
            indent=indent,
        )
        json_paths.append(json_path)
    return json_paths


def build_p4merge_command(
    tool_command: list[str],
    json_paths: list[str],
    result_path: str | None,
) -> list[str]:
    if len(json_paths) == 2:
        return [*tool_command, json_paths[0], json_paths[1]]

    if len(json_paths) == 3:
        if result_path is None:
            raise uasset_p4_common.P4ToolError("3-way merge needs a result JSON path")
        base_path, ours_path, theirs_path = json_paths
        return [*tool_command, base_path, theirs_path, ours_path, result_path]

    raise uasset_p4_common.P4ToolError("expected two or three .uasset files")


def default_result_path(temp_dir: str, ours_path: str) -> str:
    return os.path.join(temp_dir, uasset_p4_common.safe_json_name("result", ours_path))


def validate_result_path(
    result_path: str,
    input_paths: list[str],
    *,
    overwrite_result: bool,
) -> str:
    resolved = os.path.abspath(result_path)
    if os.path.splitext(resolved)[1].lower() != ".json":
        raise uasset_p4_common.P4ToolError(
            "--result must be a .json path; original .uasset files are never merge targets"
        )

    input_path_set = {os.path.abspath(path) for path in input_paths}
    if resolved in input_path_set:
        raise uasset_p4_common.P4ToolError("--result must not be one of the input files")

    if os.path.exists(resolved) and not overwrite_result:
        raise uasset_p4_common.P4ToolError(
            f"result file already exists: {resolved}; use --overwrite-result to replace it"
        )
    return resolved


def path_is_inside(path: str, directory: str) -> bool:
    path = os.path.abspath(path)
    directory = os.path.abspath(directory)
    return os.path.commonpath([path, directory]) == directory


def result_path_is_kept(run: P4MergeRun, *, delete_temp: bool) -> bool:
    if run.result_path is None:
        return False
    return not delete_temp or not path_is_inside(run.result_path, run.temp_dir)


def run_uasset_p4merge(
    input_paths: list[str],
    *,
    tool: str | None = None,
    result_path: str | None = None,
    overwrite_result: bool = False,
    temp_root: str | None = None,
    delete_temp: bool = False,
    full_text: bool = False,
    keep_paths: bool = False,
    include_export_data: bool = False,
    preview_bytes: int = 64,
    indent: int = 2,
) -> P4MergeRun:
    if len(input_paths) not in (2, 3):
        raise uasset_p4_common.P4ToolError(
            "expected two files for 2-way compare, or three files for 3-way merge"
        )
    if len(input_paths) == 2 and result_path is not None:
        raise uasset_p4_common.P4ToolError("--result is only valid for 3-way merge")

    tool_command = resolve_p4merge_tool(tool)
    temp_dir = uasset_p4_common.make_temp_dir("uasset_p4merge_", temp_root)
    command: list[str] = []
    final_result_path: str | None = None

    try:
        labels = ("left", "right") if len(input_paths) == 2 else ("base", "ours", "theirs")
        json_paths = write_json_files(
            input_paths,
            labels,
            temp_dir,
            full_text=full_text,
            keep_paths=keep_paths,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
            indent=indent,
        )

        if len(json_paths) == 3:
            final_result_path = (
                validate_result_path(
                    result_path,
                    input_paths,
                    overwrite_result=overwrite_result,
                )
                if result_path is not None
                else default_result_path(temp_dir, input_paths[1])
            )
            result_dir = os.path.dirname(final_result_path)
            if result_dir:
                os.makedirs(result_dir, exist_ok=True)
            shutil.copyfile(json_paths[1], final_result_path)

        command = build_p4merge_command(tool_command, json_paths, final_result_path)
        returncode = uasset_p4_common.run_tool(command)
        return P4MergeRun(returncode, temp_dir, command, final_result_path)
    finally:
        uasset_p4_common.remove_temp_dir(temp_dir, keep_temp=not delete_temp)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert .uasset files to JSON, then open P4Merge. "
            "Use two files for 2-way compare or three files for 3-way merge."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {TOOL_VERSION}",
    )
    parser.add_argument(
        "uassets",
        nargs="+",
        help=(
            "Two .uasset files for compare, or three files as: base ours theirs. "
            "For 3-way P4Merge is invoked as base, theirs, yours, result."
        ),
    )
    parser.add_argument(
        "-o",
        "--result",
        help="Result JSON path for 3-way merge. Defaults to a generated temp JSON file.",
    )
    parser.add_argument(
        "--overwrite-result",
        action="store_true",
        help="Allow --result to replace an existing .json file.",
    )
    parser.add_argument(
        "--tool",
        help="P4Merge command or path. Defaults to P4MERGE, MERGE, p4merge, then common macOS launch paths.",
    )
    parser.add_argument(
        "--temp-dir",
        help="Directory where converted JSON files are created. Defaults to the system temp directory.",
    )
    parser.add_argument(
        "--delete-temp",
        action="store_true",
        help=(
            "Delete generated JSON files after P4Merge exits. By default they are kept, "
            "because GUI launchers may return before the window closes."
        ),
    )
    parser.add_argument(
        "--full-text",
        action="store_true",
        help="Compare the full reversible JSON wrapper, including embedded base64 bytes.",
    )
    parser.add_argument(
        "--keep-paths",
        action="store_true",
        help="Keep source file paths in the JSON before opening P4Merge.",
    )
    parser.add_argument(
        "--include-export-data",
        action="store_true",
        help="Include serial data availability and byte previews in metadata.",
    )
    parser.add_argument(
        "--bytes",
        type=int,
        default=64,
        help="Number of export payload bytes to preview with --include-export-data.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces to use for JSON indentation. Defaults to 2.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print generated temp or result paths.",
    )
    args = parser.parse_args(argv)
    if len(args.uassets) not in (2, 3):
        parser.error("provide exactly two .uasset files for 2-way, or three for 3-way")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        run = run_uasset_p4merge(
            args.uassets,
            tool=args.tool,
            result_path=args.result,
            overwrite_result=args.overwrite_result,
            temp_root=args.temp_dir,
            delete_temp=args.delete_temp,
            full_text=args.full_text,
            keep_paths=args.keep_paths,
            include_export_data=args.include_export_data,
            preview_bytes=max(0, args.bytes),
            indent=args.indent,
        )
    except (
        OSError,
        uasset_p4_common.P4ToolError,
        uasset_to_text.UAssetError,
        struct.error,
    ) as exc:
        print(f"uasset_p4merge: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        if not args.delete_temp:
            print(f"generated JSON directory: {run.temp_dir}", file=sys.stderr)
        result_kept = result_path_is_kept(run, delete_temp=args.delete_temp)
        if run.result_path is not None and result_kept:
            print(f"merge result JSON: {run.result_path}", file=sys.stderr)
            print(run.result_path)
        elif run.result_path is not None:
            print(f"merge result JSON deleted with temp files: {run.result_path}", file=sys.stderr)
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
