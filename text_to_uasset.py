#!/usr/bin/env python3
"""
Restore a .uasset file from the reversible JSON text produced by uasset_to_text.py.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import sys
from typing import Any


TEXT_FORMAT = "ue4-uasset-text-v1"


class TextUAssetError(Exception):
    pass


def default_uasset_path(path: str) -> str:
    root, _ = os.path.splitext(path)
    return root + ".uasset"


def decode_uasset_data(document: dict[str, Any]) -> bytes:
    if document.get("format") != TEXT_FORMAT:
        raise TextUAssetError(
            f"unsupported text format {document.get('format')!r}; expected {TEXT_FORMAT!r}"
        )

    if "data_base64_lines" in document:
        lines = document["data_base64_lines"]
        if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
            raise TextUAssetError("data_base64_lines must be a list of strings")
        encoded = "".join(lines)
    elif "data_base64" in document:
        encoded = document["data_base64"]
        if not isinstance(encoded, str):
            raise TextUAssetError("data_base64 must be a string")
    else:
        raise TextUAssetError("text file does not contain embedded uasset bytes")

    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TextUAssetError(f"invalid base64 data: {exc}") from exc

    expected_sha256 = document.get("sha256")
    if expected_sha256:
        actual_sha256 = hashlib.sha256(data).hexdigest()
        if actual_sha256 != expected_sha256:
            raise TextUAssetError(
                f"sha256 mismatch: expected {expected_sha256}, got {actual_sha256}"
            )

    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        raise TextUAssetError("metadata must be an object when present")
    file_info = metadata.get("file", {})
    if not isinstance(file_info, dict):
        raise TextUAssetError("metadata.file must be an object when present")
    metadata_size = file_info.get("size")
    if metadata_size is not None and metadata_size != len(data):
        raise TextUAssetError(
            f"size mismatch: metadata says {metadata_size}, decoded {len(data)} bytes"
        )

    return data


def restore_uasset(text_path: str, output_path: str) -> None:
    with open(text_path, "r", encoding="utf-8") as file:
        document = json.load(file)
    if not isinstance(document, dict):
        raise TextUAssetError("text file must contain a JSON object")

    data = decode_uasset_data(document)
    with open(output_path, "wb") as file:
        file.write(data)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore a .uasset file from a reversible JSON text file.",
    )
    parser.add_argument("text", help="Path to a .txt file created by uasset_to_text.py")
    parser.add_argument(
        "-o",
        "--output",
        help="Output .uasset path. Defaults to the input filename with a .uasset extension.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    output_path = args.output or default_uasset_path(args.text)
    try:
        restore_uasset(args.text, output_path)
    except (OSError, json.JSONDecodeError, TextUAssetError) as exc:
        print(f"text_to_uasset: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
