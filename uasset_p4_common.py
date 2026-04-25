#!/usr/bin/env python3
"""
Shared helpers for Perforce P4Merge wrappers.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile

import uasset_diff
import uasset_to_text


class P4ToolError(Exception):
    pass


def split_tool_command(command: str) -> list[str]:
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise P4ToolError(f"invalid tool command {command!r}: {exc}") from exc

    if not parts:
        raise P4ToolError("tool command is empty")
    return parts


def resolve_tool(
    *,
    explicit_tool: str | None,
    env_names: tuple[str, ...],
    executable_names: tuple[str, ...],
    executable_paths: tuple[str, ...] = (),
    tool_label: str,
) -> list[str]:
    for setting in [explicit_tool, *[os.environ.get(name) for name in env_names]]:
        if not setting:
            continue
        command = split_tool_command(setting)
        executable = shutil.which(command[0])
        if executable:
            command[0] = executable
        elif not os.path.exists(command[0]):
            raise P4ToolError(
                f"cannot find {tool_label} executable {command[0]!r}; "
                f"use --tool or set {env_names[0]}"
            )
        return command

    for name in executable_names:
        executable = shutil.which(name)
        if executable:
            return [executable]

    for path in executable_paths:
        if os.path.exists(path):
            return [path]

    env_hint = " or ".join(env_names)
    raise P4ToolError(
        f"cannot find {tool_label}; use --tool or set {env_hint}"
    )


def safe_json_name(label: str, source_path: str) -> str:
    source_name = os.path.basename(source_path) or "asset"
    safe_name = "".join(
        char if char.isalnum() or char in "._-" else "_"
        for char in source_name
    )
    return f"{label}_{safe_name}.json"


def write_uasset_json(
    source_path: str,
    output_path: str,
    *,
    full_text: bool,
    keep_paths: bool,
    include_export_data: bool,
    preview_bytes: int,
    indent: int,
) -> None:
    document = uasset_diff.normalize_paths(
        uasset_diff.document_for_diff(
            source_path,
            full_text=full_text,
            include_export_data=include_export_data,
            preview_bytes=preview_bytes,
        ),
        keep_paths=keep_paths,
    )
    text = uasset_to_text.format_json(document, compact=False, indent=indent)
    with open(output_path, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
        file.write("\n")


def make_temp_dir(prefix: str, temp_root: str | None) -> str:
    if temp_root is not None:
        os.makedirs(temp_root, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=temp_root)


def run_tool(command: list[str]) -> int:
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        raise P4ToolError(str(exc)) from exc


def remove_temp_dir(path: str, *, keep_temp: bool) -> None:
    if keep_temp:
        return
    shutil.rmtree(path, ignore_errors=True)
