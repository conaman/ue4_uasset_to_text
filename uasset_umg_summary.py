#!/usr/bin/env python3
"""
Print a compact UMG widget summary from a .uasset or uasset_to_text JSON file.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from typing import Any

import uasset_to_text


TOOL_VERSION = "2026-04-26"

UMG_CLASS_PREFIX = "/Script/UMG."
UMG_EDITOR_CLASS_PREFIX = "/Script/UMGEditor."
NON_WIDGET_UMG_TYPES = {
    "WidgetBlueprintGeneratedClass",
    "WidgetTree",
}


class UMGSummaryError(Exception):
    pass


def short_type_name(class_path: str) -> str:
    if "." in class_path:
        return class_path.rsplit(".", 1)[-1]
    return class_path.rsplit("/", 1)[-1]


def object_name(export: dict[str, Any]) -> str:
    name = export.get("object_name")
    if isinstance(name, dict):
        value = name.get("value")
        if isinstance(value, str):
            return value
    value = export.get("path")
    return value if isinstance(value, str) else "<unnamed>"


def widget_tree_path(export: dict[str, Any]) -> list[str]:
    path = export.get("path")
    if isinstance(path, str):
        parts = [part for part in path.split(".") if part]
        for index, part in enumerate(parts):
            if part == "WidgetTree":
                return parts[index + 1 :] or [object_name(export)]
    return [object_name(export)]


def is_widget_export(
    export: dict[str, Any],
    *,
    include_slots: bool,
    include_internal: bool,
) -> bool:
    class_path = export.get("class")
    if not isinstance(class_path, str) or not class_path.startswith(UMG_CLASS_PREFIX):
        return False

    widget_type = short_type_name(class_path)
    if not include_internal and widget_type in NON_WIDGET_UMG_TYPES:
        return False
    if not include_slots and widget_type.endswith("Slot"):
        return False
    return True


def unwrap_metadata(document: dict[str, Any]) -> dict[str, Any]:
    metadata = document.get("metadata", document)
    if not isinstance(metadata, dict):
        raise UMGSummaryError("JSON document does not contain a metadata object")
    if not isinstance(metadata.get("exports"), list):
        raise UMGSummaryError("metadata does not contain an exports array")
    return metadata


def load_metadata(
    path: str,
    *,
    include_export_data: bool,
    preview_bytes: int,
) -> dict[str, Any]:
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as file:
            document = json.load(file)
        if not isinstance(document, dict):
            raise UMGSummaryError("JSON input must be an object")
        return unwrap_metadata(document)

    return uasset_to_text.parse_uasset(
        path,
        include_export_data=include_export_data,
        preview_bytes=preview_bytes,
    )


def detect_umg_kind(metadata: dict[str, Any]) -> str:
    classes = {
        item.get("class")
        for item in metadata.get("exports", [])
        if isinstance(item, dict)
    }
    if "/Script/UMGEditor.WidgetBlueprint" in classes:
        return "WidgetBlueprint"
    if "/Script/UMG.WidgetBlueprintGeneratedClass" in classes:
        return "WidgetBlueprintGeneratedClass"
    if any(
        isinstance(class_path, str)
        and (
            class_path.startswith(UMG_CLASS_PREFIX)
            or class_path.startswith(UMG_EDITOR_CLASS_PREFIX)
        )
        for class_path in classes
    ):
        return "UMGReference"
    return "NotUMG"


def detect_asset_name(metadata: dict[str, Any]) -> str | None:
    for item in metadata.get("exports", []):
        if not isinstance(item, dict):
            continue
        if item.get("is_asset") and item.get("class") == "/Script/UMGEditor.WidgetBlueprint":
            return object_name(item)

    file_info = metadata.get("file")
    if isinstance(file_info, dict):
        path = file_info.get("path")
        if isinstance(path, str):
            return os.path.splitext(os.path.basename(path))[0]
    return None


def detect_parent_class(metadata: dict[str, Any]) -> str | None:
    for item in metadata.get("exports", []):
        if not isinstance(item, dict):
            continue
        if item.get("class") == "/Script/UMG.WidgetBlueprintGeneratedClass":
            parent_class = item.get("super")
            if isinstance(parent_class, str):
                return parent_class
    return None


def collect_widgets(
    metadata: dict[str, Any],
    *,
    include_slots: bool = False,
    include_internal: bool = False,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}
    for export in metadata.get("exports", []):
        if not isinstance(export, dict):
            continue
        if not is_widget_export(
            export,
            include_slots=include_slots,
            include_internal=include_internal,
        ):
            continue

        class_path = export["class"]
        name = object_name(export)
        widget_type = short_type_name(class_path)
        tree_path = widget_tree_path(export)
        key = (tuple(tree_path), widget_type)
        if key not in grouped:
            grouped[key] = {
                "name": name,
                "type": widget_type,
                "class": class_path,
                "tree_path": tree_path,
                "paths": [],
            }

        path = export.get("path")
        if isinstance(path, str):
            grouped[key]["paths"].append(path)

    return sorted(
        grouped.values(),
        key=lambda item: (
            [part.lower() for part in item["tree_path"]],
            item["type"].lower(),
        ),
    )


def summarize_umg(
    metadata: dict[str, Any],
    *,
    include_slots: bool = False,
    include_internal: bool = False,
) -> dict[str, Any]:
    umg_kind = detect_umg_kind(metadata)
    if umg_kind == "NotUMG":
        source = None
        file_info = metadata.get("file")
        if isinstance(file_info, dict):
            source = file_info.get("path")
        detail = f": {source}" if isinstance(source, str) else ""
        raise UMGSummaryError(f"input does not look like a UMG asset{detail}")

    return {
        "source": metadata.get("file", {}).get("path")
        if isinstance(metadata.get("file"), dict)
        else None,
        "asset_name": detect_asset_name(metadata),
        "umg_kind": umg_kind,
        "parent_class": detect_parent_class(metadata),
        "widgets": collect_widgets(
            metadata,
            include_slots=include_slots,
            include_internal=include_internal,
        ),
    }


def format_widget_tree(summary: dict[str, Any], *, show_paths: bool = False) -> str:
    rows = summary["widgets"]
    lines: list[str] = []

    asset_name = summary.get("asset_name")
    if asset_name:
        lines.append(f"Asset: {asset_name}")
    lines.append(f"UMG: {summary['umg_kind']}")
    parent_class = summary.get("parent_class")
    if isinstance(parent_class, str):
        lines.append(f"ParentClass: {short_type_name(parent_class)}")
    lines.append(f"Widgets: {len(rows)}")
    lines.append("")
    lines.append("WidgetTree")
    for row in rows:
        tree_path = row.get("tree_path")
        depth = len(tree_path) if isinstance(tree_path, list) else 1
        label = f"{row['name']} ({row['type']})"
        if show_paths and row["paths"]:
            label += f" [{'; '.join(row['paths'])}]"
        lines.append(f"{'  ' * depth}{label}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize UMG widget names and types from a .uasset or uasset_to_text JSON file.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {TOOL_VERSION}",
    )
    parser.add_argument("input", help="Path to a .uasset file or uasset_to_text .json")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the summary as JSON instead of a text tree.",
    )
    parser.add_argument(
        "--include-slots",
        action="store_true",
        help="Include UMG slot exports such as ButtonSlot and VerticalBoxSlot.",
    )
    parser.add_argument(
        "--include-internal",
        action="store_true",
        help="Include internal UMG exports such as WidgetTree.",
    )
    parser.add_argument(
        "--show-paths",
        action="store_true",
        help="Include resolved export paths in the text output.",
    )
    parser.add_argument(
        "--include-export-data",
        action="store_true",
        help="Include export data previews while parsing .uasset input.",
    )
    parser.add_argument(
        "--bytes",
        type=int,
        default=64,
        help="Number of export payload bytes to preview with --include-export-data.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        metadata = load_metadata(
            args.input,
            include_export_data=args.include_export_data,
            preview_bytes=max(0, args.bytes),
        )
        summary = summarize_umg(
            metadata,
            include_slots=args.include_slots,
            include_internal=args.include_internal,
        )
    except (
        OSError,
        json.JSONDecodeError,
        struct.error,
        UMGSummaryError,
        uasset_to_text.UAssetError,
    ) as exc:
        print(f"uasset_umg_summary: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(uasset_to_text.format_json(summary, compact=False, indent=2))
    else:
        print(format_widget_tree(summary, show_paths=args.show_paths), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
