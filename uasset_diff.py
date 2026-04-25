#!/usr/bin/env python3
"""
Print a unified diff between two .uasset files after converting them to JSON.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import struct
import sys
from typing import Any

import uasset_to_text


def normalize_paths(document: dict[str, Any], *, keep_paths: bool) -> dict[str, Any]:
    if keep_paths:
        return document

    normalized = copy.deepcopy(document)
    if "file" in normalized and isinstance(normalized["file"], dict):
        normalized["file"].pop("path", None)

    metadata = normalized.get("metadata")
    if isinstance(metadata, dict):
        file_info = metadata.get("file")
        if isinstance(file_info, dict):
            file_info.pop("path", None)
        normalized.pop("source_path", None)

    return normalized


def document_for_diff(
    path: str,
    *,
    full_text: bool,
    include_export_data: bool,
    preview_bytes: int,
) -> dict[str, Any]:
    if full_text:
        return uasset_to_text.build_text_document(
            path,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
        )
    return uasset_to_text.parse_uasset(
        path,
        include_export_data=include_export_data,
        preview_bytes=preview_bytes,
    )


def diff_uassets(
    left_path: str,
    right_path: str,
    *,
    full_text: bool = False,
    keep_paths: bool = False,
    include_export_data: bool = False,
    preview_bytes: int = 64,
    indent: int = 2,
    context: int = 3,
) -> str:
    left_document = normalize_paths(
        document_for_diff(
            left_path,
            full_text=full_text,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
        ),
        keep_paths=keep_paths,
    )
    right_document = normalize_paths(
        document_for_diff(
            right_path,
            full_text=full_text,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
        ),
        keep_paths=keep_paths,
    )

    left_lines = uasset_to_text.format_json(
        left_document, compact=False, indent=indent
    ).splitlines()
    right_lines = uasset_to_text.format_json(
        right_document, compact=False, indent=indent
    ).splitlines()

    diff_lines = list(
        difflib.unified_diff(
            left_lines,
            right_lines,
            fromfile=left_path,
            tofile=right_path,
            lineterm="",
            n=max(0, context),
        )
    )
    if not diff_lines:
        return ""
    return "\n".join(diff_lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diff two .uasset files by comparing their uasset_to_text JSON.",
    )
    parser.add_argument("left", help="First .uasset file")
    parser.add_argument("right", help="Second .uasset file")
    parser.add_argument(
        "--full-text",
        action="store_true",
        help="Diff the full reversible JSON wrapper, including embedded base64 bytes.",
    )
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
        "-U",
        "--unified",
        type=int,
        default=3,
        help="Number of context lines to show in the unified diff. Defaults to 3.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print the diff; only return the exit status.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        diff_text = diff_uassets(
            args.left,
            args.right,
            full_text=args.full_text,
            keep_paths=args.keep_paths,
            include_export_data=args.include_export_data,
            preview_bytes=max(0, args.bytes),
            indent=args.indent,
            context=args.unified,
        )
    except (OSError, uasset_to_text.UAssetError, struct.error) as exc:
        print(f"uasset_diff: {exc}", file=sys.stderr)
        return 2

    if diff_text:
        if not args.quiet:
            try:
                print(diff_text, end="")
            except BrokenPipeError:
                return 1
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
