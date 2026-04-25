#!/usr/bin/env python3
"""
Print a 3-way diff report for .uasset files after converting them to JSON.
"""

from __future__ import annotations

import argparse
import struct
import sys
from typing import Any

import uasset_diff
import uasset_to_text


TOOL_VERSION = "2026-04-26"
MISSING = object()


def escape_path_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        if not value:
            return {prefix or "/": value}

        flattened: dict[str, Any] = {}
        for key in sorted(value):
            token = escape_path_token(str(key))
            child_prefix = f"{prefix}/{token}" if prefix else f"/{token}"
            flattened.update(flatten_json(value[key], child_prefix))
        return flattened

    if isinstance(value, list):
        if not value:
            return {prefix or "/": value}

        flattened: dict[str, Any] = {}
        for index, item in enumerate(value):
            child_prefix = f"{prefix}/{index}" if prefix else f"/{index}"
            flattened.update(flatten_json(item, child_prefix))
        return flattened

    return {prefix or "/": value}


def path_sort_key(path: str) -> list[tuple[int, int | str]]:
    key: list[tuple[int, int | str]] = []
    for token in path.strip("/").split("/"):
        if token.isdecimal():
            key.append((0, int(token)))
        else:
            key.append((1, token))
    return key


def report_value(value: Any) -> Any:
    if value is MISSING:
        return {"missing": True}
    return value


def side_status(side: str, base_value: Any, side_value: Any) -> str:
    if base_value is MISSING:
        return f"{side}_added"
    if side_value is MISSING:
        return f"{side}_deleted"
    return f"{side}_changed"


def both_status(base_value: Any, merged_value: Any) -> str:
    if base_value is MISSING:
        return "both_added"
    if merged_value is MISSING:
        return "both_deleted"
    return "both_changed"


def make_report_item(
    path: str,
    status: str,
    base_value: Any,
    ours_value: Any,
    theirs_value: Any,
) -> dict[str, Any]:
    return {
        "path": path,
        "status": status,
        "base": report_value(base_value),
        "ours": report_value(ours_value),
        "theirs": report_value(theirs_value),
    }


def classify_path(
    path: str,
    base_value: Any,
    ours_value: Any,
    theirs_value: Any,
) -> dict[str, Any] | None:
    if ours_value == theirs_value:
        if ours_value == base_value:
            return None
        return make_report_item(
            path,
            both_status(base_value, ours_value),
            base_value,
            ours_value,
            theirs_value,
        )

    if ours_value == base_value:
        return make_report_item(
            path,
            side_status("theirs", base_value, theirs_value),
            base_value,
            ours_value,
            theirs_value,
        )

    if theirs_value == base_value:
        return make_report_item(
            path,
            side_status("ours", base_value, ours_value),
            base_value,
            ours_value,
            theirs_value,
        )

    return make_report_item(path, "conflict", base_value, ours_value, theirs_value)


def diff3_uassets(
    base_path: str,
    ours_path: str,
    theirs_path: str,
    *,
    keep_paths: bool = False,
    include_export_data: bool = False,
    preview_bytes: int = 64,
) -> dict[str, Any]:
    base_document = uasset_diff.normalize_paths(
        uasset_diff.document_for_diff(
            base_path,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
        ),
        keep_paths=keep_paths,
    )
    ours_document = uasset_diff.normalize_paths(
        uasset_diff.document_for_diff(
            ours_path,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
        ),
        keep_paths=keep_paths,
    )
    theirs_document = uasset_diff.normalize_paths(
        uasset_diff.document_for_diff(
            theirs_path,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
        ),
        keep_paths=keep_paths,
    )

    base_values = flatten_json(base_document)
    ours_values = flatten_json(ours_document)
    theirs_values = flatten_json(theirs_document)

    changes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    all_paths = sorted(
        set(base_values) | set(ours_values) | set(theirs_values),
        key=path_sort_key,
    )

    for path in all_paths:
        item = classify_path(
            path,
            base_values.get(path, MISSING),
            ours_values.get(path, MISSING),
            theirs_values.get(path, MISSING),
        )
        if item is None:
            continue
        if item["status"] == "conflict":
            conflicts.append(item)
        else:
            changes.append(item)

    return {
        "format": "ue4-uasset-diff3-v1",
        "base": base_path,
        "ours": ours_path,
        "theirs": theirs_path,
        "summary": {
            "changes": len(changes),
            "conflicts": len(conflicts),
        },
        "changes": changes,
        "conflicts": conflicts,
    }


def format_diff3_report(report: dict[str, Any], *, indent: int) -> str:
    return uasset_to_text.format_json(report, compact=False, indent=indent) + "\n"


def exit_status(report: dict[str, Any]) -> int:
    if report["conflicts"]:
        return 2
    if report["changes"]:
        return 1
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diff three .uasset files by comparing their uasset_to_text JSON.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {TOOL_VERSION}",
    )
    parser.add_argument("base", help="Common base .uasset file")
    parser.add_argument("ours", help="Our changed .uasset file")
    parser.add_argument("theirs", help="Their changed .uasset file")
    parser.add_argument(
        "--keep-paths",
        action="store_true",
        help="Keep source file paths in the JSON before diffing.",
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
        help="Do not print the report; only return the exit status.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        report = diff3_uassets(
            args.base,
            args.ours,
            args.theirs,
            keep_paths=args.keep_paths,
            include_export_data=args.include_export_data,
            preview_bytes=max(0, args.bytes),
        )
    except (OSError, uasset_to_text.UAssetError, struct.error) as exc:
        print(f"uasset_diff3: {exc}", file=sys.stderr)
        return 3

    status = exit_status(report)
    if not args.quiet:
        try:
            print(format_diff3_report(report, indent=args.indent), end="")
        except BrokenPipeError:
            return status
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
