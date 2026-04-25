#!/usr/bin/env python3
"""
Dump Unreal Engine 4.27 .uasset package metadata as readable JSON.

This is a standalone parser for the binary package header tables. It does not
link against Unreal Engine and intentionally avoids trying to deserialize every
UObject property payload, which requires loaded classes and engine serializers.
"""

from __future__ import annotations

import argparse
import json
import os
import string
import struct
import sys
from dataclasses import dataclass
from typing import Any, Callable


PACKAGE_FILE_TAG = 0x9E2A83C1
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E
PKG_FILTER_EDITOR_ONLY = 0x80000000

TOOL_VERSION = "2026-04-26"
CURRENT_LEGACY_FILE_VERSION = -7
MAX_ARRAY_COUNT = 10_000_000
MAX_FSTRING_CODE_UNITS = 1024 * 1024
MAX_NAME_CODE_UNITS = 1024

VER_UE4_OLDEST_LOADABLE_PACKAGE = 214
VER_UE4_WORLD_LEVEL_INFO = 224
VER_UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS = 326
VER_UE4_ENGINE_VERSION_OBJECT = 336
VER_UE4_LOAD_FOR_EDITOR_GAME = 365
VER_UE4_ADD_STRING_ASSET_REFERENCES_MAP = 384
VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION = 444
VER_UE4_SERIALIZE_TEXT_IN_PACKAGES = 459
VER_UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT = 485
VER_UE4_NAME_HASHES_SERIALIZED = 504
VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 507
VER_UE4_TEMPLATE_INDEX_IN_COOKED_EXPORTS = 508
VER_UE4_ADDED_SEARCHABLE_NAMES = 510
VER_UE4_64BIT_EXPORTMAP_SERIALSIZES = 511
VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 516
VER_UE4_ADDED_PACKAGE_OWNER = 518
VER_UE4_NON_OUTER_PACKAGE_IMPORT = 520
VER_UE4_AUTOMATIC_VERSION = 522
VER_UE4_ADDED_CHUNKID_TO_ASSETDATA_AND_UPACKAGE = 278

PACKAGE_FLAG_NAMES = {
    0x00000001: "PKG_NewlyCreated",
    0x00000002: "PKG_ClientOptional",
    0x00000004: "PKG_ServerSideOnly",
    0x00000010: "PKG_CompiledIn",
    0x00000020: "PKG_ForDiffing",
    0x00000040: "PKG_EditorOnly",
    0x00000080: "PKG_Developer",
    0x00000100: "PKG_UncookedOnly",
    0x00000200: "PKG_Cooked",
    0x00000400: "PKG_ContainsNoAsset",
    0x00002000: "PKG_UnversionedProperties",
    0x00004000: "PKG_ContainsMapData",
    0x00010000: "PKG_Compiling",
    0x00020000: "PKG_ContainsMap",
    0x00040000: "PKG_RequiresLocalizationGather",
    0x00100000: "PKG_PlayInEditor",
    0x00200000: "PKG_ContainsScript",
    0x00400000: "PKG_DisallowExport",
    0x10000000: "PKG_DynamicImports",
    0x20000000: "PKG_RuntimeGenerated",
    0x40000000: "PKG_ReloadingForCooker",
    0x80000000: "PKG_FilterEditorOnly",
}

OBJECT_FLAG_NAMES = {
    0x00000001: "RF_Public",
    0x00000002: "RF_Standalone",
    0x00000004: "RF_MarkAsNative",
    0x00000008: "RF_Transactional",
    0x00000010: "RF_ClassDefaultObject",
    0x00000020: "RF_ArchetypeObject",
    0x00000040: "RF_Transient",
    0x00000080: "RF_MarkAsRootSet",
    0x00000100: "RF_TagGarbageTemp",
    0x00000200: "RF_NeedInitialization",
    0x00000400: "RF_NeedLoad",
    0x00000800: "RF_KeepForCooker",
    0x00001000: "RF_NeedPostLoad",
    0x00002000: "RF_NeedPostLoadSubobjects",
    0x00004000: "RF_NewerVersionExists",
    0x00008000: "RF_BeginDestroyed",
    0x00010000: "RF_FinishDestroyed",
    0x00020000: "RF_BeingRegenerated",
    0x00040000: "RF_DefaultSubObject",
    0x00080000: "RF_WasLoaded",
    0x00100000: "RF_TextExportTransient",
    0x00200000: "RF_LoadCompleted",
    0x00400000: "RF_InheritableComponentTemplate",
    0x00800000: "RF_DuplicateTransient",
    0x01000000: "RF_StrongRefOnFrame",
    0x02000000: "RF_NonPIEDuplicateTransient",
    0x04000000: "RF_Dynamic",
    0x08000000: "RF_WillBeLoaded",
    0x10000000: "RF_HasExternalPackage",
}


class UAssetError(Exception):
    pass


class Reader:
    def __init__(self, data: bytes, path: str):
        self.data = data
        self.path = path
        self.pos = 0
        self.endian = "<"

    def tell(self) -> int:
        return self.pos

    def seek(self, pos: int) -> None:
        if pos < 0 or pos > len(self.data):
            raise UAssetError(f"seek out of range: {pos}")
        self.pos = pos

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def read(self, size: int) -> bytes:
        if size < 0:
            raise UAssetError(f"negative read size: {size}")
        end = self.pos + size
        if end > len(self.data):
            raise UAssetError(
                f"unexpected end of file at 0x{self.pos:x}; need {size} bytes, "
                f"have {self.remaining()}"
            )
        chunk = self.data[self.pos:end]
        self.pos = end
        return chunk

    def unpack(self, fmt: str) -> Any:
        full_fmt = self.endian + fmt
        size = struct.calcsize(full_fmt)
        values = struct.unpack(full_fmt, self.read(size))
        return values[0] if len(values) == 1 else values

    def u16(self) -> int:
        return self.unpack("H")

    def i32(self) -> int:
        return self.unpack("i")

    def u32(self) -> int:
        return self.unpack("I")

    def i64(self) -> int:
        return self.unpack("q")

    def boolean(self) -> bool:
        value = self.u32()
        if value not in (0, 1):
            raise UAssetError(f"invalid UE bool value {value} at 0x{self.pos - 4:x}")
        return bool(value)

    def string(self, *, label: str, max_code_units: int) -> str:
        length = self.i32()
        if length == 0:
            return ""
        if abs(length) > max_code_units:
            raise UAssetError(f"implausible {label} length {length} at 0x{self.pos - 4:x}")
        if length > 0:
            raw = self.read(length)
            if raw.endswith(b"\x00"):
                raw = raw[:-1]
            return raw.decode("utf-8", errors="replace")

        char_count = -length
        raw = self.read(char_count * 2)
        if raw.endswith(b"\x00\x00"):
            raw = raw[:-2]
        encoding = "utf-16-le" if self.endian == "<" else "utf-16-be"
        return raw.decode(encoding, errors="replace")

    def fstring(self) -> str:
        return self.string(label="FString", max_code_units=MAX_FSTRING_CODE_UNITS)

    def guid(self) -> str:
        a = self.u32()
        b = self.u32()
        c = self.u32()
        d = self.u32()
        return (
            f"{a:08x}-{(b >> 16) & 0xffff:04x}-{b & 0xffff:04x}-"
            f"{(c >> 16) & 0xffff:04x}-{c & 0xffff:04x}{d:08x}"
        )


@dataclass
class NameRef:
    index: int
    number: int


def read_array(reader: Reader, item_reader: Callable[[], Any], *, label: str) -> list[Any]:
    count = reader.i32()
    validate_count(count, f"{label} array")
    return [item_reader() for _ in range(count)]


def validate_count(count: int, label: str, *, allow_minus_one: bool = False) -> None:
    if allow_minus_one and count == -1:
        return
    if count < 0:
        raise UAssetError(f"negative {label} count {count}")
    if count > MAX_ARRAY_COUNT:
        raise UAssetError(f"implausibly large {label} count {count}")


def validate_offset(offset: int, label: str, file_size: int, *, required: bool = False) -> None:
    if offset < 0:
        raise UAssetError(f"negative {label} offset {offset}")
    if required and offset == 0:
        raise UAssetError(f"missing {label} offset for non-empty table")
    if offset > file_size:
        raise UAssetError(f"{label} offset {offset} is past end of file ({file_size} bytes)")


def validate_supported_ue4_version(file_version_ue4: int, file_version_licensee_ue4: int) -> int:
    if file_version_ue4 == 0 and file_version_licensee_ue4 == 0:
        return VER_UE4_AUTOMATIC_VERSION
    if file_version_ue4 < VER_UE4_OLDEST_LOADABLE_PACKAGE:
        raise UAssetError(
            f"unsupported UE4 package version {file_version_ue4}; "
            f"oldest loadable version is {VER_UE4_OLDEST_LOADABLE_PACKAGE}"
        )
    if file_version_ue4 > VER_UE4_AUTOMATIC_VERSION:
        raise UAssetError(
            f"package UE4 version {file_version_ue4} is newer than this parser "
            f"understands ({VER_UE4_AUTOMATIC_VERSION})"
        )
    return file_version_ue4


def validate_summary(summary: dict[str, Any], file_size: int) -> None:
    validate_offset(summary["total_header_size"], "total header size", file_size)
    if summary["total_header_size"] and summary["total_header_size"] < summary["summary_size"]:
        raise UAssetError(
            f"total header size {summary['total_header_size']} is smaller than "
            f"parsed summary size {summary['summary_size']}"
        )

    for count_key in (
        "name_count",
        "gatherable_text_data_count",
        "export_count",
        "import_count",
        "soft_package_references_count",
    ):
        validate_count(summary[count_key], count_key)
    validate_count(summary["preload_dependency_count"], "preload_dependency_count", allow_minus_one=True)

    for count_key, offset_key, label in (
        ("name_count", "name_offset", "name table"),
        ("gatherable_text_data_count", "gatherable_text_data_offset", "gatherable text data"),
        ("export_count", "export_offset", "export map"),
        ("import_count", "import_offset", "import map"),
        ("soft_package_references_count", "soft_package_references_offset", "soft package references"),
        ("preload_dependency_count", "preload_dependency_offset", "preload dependencies"),
    ):
        count = summary[count_key]
        if count == -1:
            continue
        validate_offset(summary[offset_key], label, file_size, required=count > 0)

    validate_offset(summary["depends_offset"], "depends map", file_size)


def read_name_ref(reader: Reader) -> NameRef:
    return NameRef(reader.i32(), reader.i32())


def read_engine_version(reader: Reader) -> dict[str, Any]:
    major = reader.u16()
    minor = reader.u16()
    patch = reader.u16()
    changelist = reader.u32()
    branch = reader.fstring()
    text = f"{major}.{minor}.{patch}-{changelist}"
    if branch:
        text += f"+{branch}"
    return {
        "major": major,
        "minor": minor,
        "patch": patch,
        "changelist": changelist,
        "branch": branch,
        "text": text,
    }


def read_compressed_chunk(reader: Reader) -> dict[str, int]:
    return {
        "uncompressed_offset": reader.i32(),
        "uncompressed_size": reader.i32(),
        "compressed_offset": reader.i32(),
        "compressed_size": reader.i32(),
    }


def read_custom_versions(reader: Reader, legacy_file_version: int) -> tuple[str, list[dict[str, Any]]]:
    if legacy_file_version == -2:
        return (
            "Enums",
            read_array(
                reader,
                lambda: {
                    "tag": reader.u32(),
                    "version": reader.i32(),
                },
                label="custom version enum",
            ),
        )
    if legacy_file_version < -2 and legacy_file_version >= -5:
        return (
            "Guids",
            read_array(
                reader,
                lambda: {
                    "key": reader.guid(),
                    "version": reader.i32(),
                    "friendly_name": reader.fstring(),
                },
                label="custom version guid",
            ),
        )
    if legacy_file_version < -5:
        return (
            "Optimized",
            read_array(
                reader,
                lambda: {
                    "key": reader.guid(),
                    "version": reader.i32(),
                },
                label="custom version",
            ),
        )
    return "None", []


def read_package_summary(reader: Reader) -> dict[str, Any]:
    summary_start = reader.tell()
    tag = reader.u32()
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        reader.endian = ">" if reader.endian == "<" else "<"
        tag = PACKAGE_FILE_TAG
    if tag != PACKAGE_FILE_TAG:
        raise UAssetError(
            f"not a UE package: tag=0x{tag:08x}, expected 0x{PACKAGE_FILE_TAG:08x}"
        )

    legacy_file_version = reader.i32()
    if legacy_file_version < CURRENT_LEGACY_FILE_VERSION:
        raise UAssetError(
            f"package legacy version {legacy_file_version} is newer than this parser "
            f"understands ({CURRENT_LEGACY_FILE_VERSION})"
        )
    if legacy_file_version >= 0:
        raise UAssetError(f"unsupported old UE3-style package version {legacy_file_version}")

    legacy_ue3_version = None
    if legacy_file_version != -4:
        legacy_ue3_version = reader.i32()

    file_version_ue4 = reader.i32()
    file_version_licensee_ue4 = reader.i32()
    custom_version_format = "None"
    custom_versions: list[dict[str, Any]] = []
    if legacy_file_version <= -2:
        custom_version_format, custom_versions = read_custom_versions(reader, legacy_file_version)

    b_unversioned = file_version_ue4 == 0 and file_version_licensee_ue4 == 0
    effective_file_version_ue4 = validate_supported_ue4_version(
        file_version_ue4, file_version_licensee_ue4
    )

    total_header_size = reader.i32()
    folder_name = reader.fstring()
    package_flags = reader.u32()
    filter_editor_only = bool(package_flags & PKG_FILTER_EDITOR_ONLY)
    name_count = reader.i32()
    name_offset = reader.i32()

    localization_id = None
    if not filter_editor_only and effective_file_version_ue4 >= VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
        localization_id = reader.fstring()

    gatherable_text_data_count = 0
    gatherable_text_data_offset = 0
    if effective_file_version_ue4 >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES:
        gatherable_text_data_count = reader.i32()
        gatherable_text_data_offset = reader.i32()

    export_count = reader.i32()
    export_offset = reader.i32()
    import_count = reader.i32()
    import_offset = reader.i32()
    depends_offset = reader.i32()

    soft_package_references_count = 0
    soft_package_references_offset = 0
    if effective_file_version_ue4 >= VER_UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        soft_package_references_count = reader.i32()
        soft_package_references_offset = reader.i32()

    searchable_names_offset = 0
    if effective_file_version_ue4 >= VER_UE4_ADDED_SEARCHABLE_NAMES:
        searchable_names_offset = reader.i32()

    thumbnail_table_offset = reader.i32()
    guid = reader.guid()

    persistent_guid = None
    owner_persistent_guid = None
    if not filter_editor_only:
        if effective_file_version_ue4 >= VER_UE4_ADDED_PACKAGE_OWNER:
            persistent_guid = reader.guid()
            if effective_file_version_ue4 < VER_UE4_NON_OUTER_PACKAGE_IMPORT:
                owner_persistent_guid = reader.guid()
        else:
            persistent_guid = guid

    generations = read_array(
        reader,
        lambda: {
            "export_count": reader.i32(),
            "name_count": reader.i32(),
        },
        label="generation",
    )

    engine_changelist = None
    saved_by_engine_version = None
    if effective_file_version_ue4 >= VER_UE4_ENGINE_VERSION_OBJECT:
        saved_by_engine_version = read_engine_version(reader)
    else:
        engine_changelist = reader.i32()

    compatible_with_engine_version = None
    if effective_file_version_ue4 >= VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION:
        compatible_with_engine_version = read_engine_version(reader)
    else:
        compatible_with_engine_version = saved_by_engine_version

    compression_flags = reader.u32()
    compressed_chunks = read_array(reader, lambda: read_compressed_chunk(reader), label="compressed chunk")
    package_source = reader.u32()
    additional_packages_to_cook = read_array(reader, lambda: reader.fstring(), label="additional package")

    num_texture_allocations = None
    if legacy_file_version > -7:
        num_texture_allocations = reader.i32()

    asset_registry_data_offset = reader.i32()
    bulk_data_start_offset = reader.i64()

    world_tile_info_data_offset = 0
    if effective_file_version_ue4 >= VER_UE4_WORLD_LEVEL_INFO:
        world_tile_info_data_offset = reader.i32()

    chunk_ids: list[int] = []
    if effective_file_version_ue4 >= VER_UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS:
        chunk_ids = read_array(reader, lambda: reader.i32(), label="chunk id")
    elif effective_file_version_ue4 >= VER_UE4_ADDED_CHUNKID_TO_ASSETDATA_AND_UPACKAGE:
        chunk_id = reader.i32()
        if chunk_id >= 0:
            chunk_ids = [chunk_id]

    preload_dependency_count = -1
    preload_dependency_offset = 0
    if effective_file_version_ue4 >= VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
        preload_dependency_count = reader.i32()
        preload_dependency_offset = reader.i32()

    summary_end = reader.tell()
    return {
        "tag": f"0x{PACKAGE_FILE_TAG:08x}",
        "legacy_file_version": legacy_file_version,
        "legacy_ue3_version": legacy_ue3_version,
        "file_version_ue4": file_version_ue4,
        "file_version_licensee_ue4": file_version_licensee_ue4,
        "effective_file_version_ue4": effective_file_version_ue4,
        "unversioned": b_unversioned,
        "custom_version_format": custom_version_format,
        "custom_versions": custom_versions,
        "total_header_size": total_header_size,
        "folder_name": folder_name,
        "package_flags": package_flags,
        "package_flags_hex": f"0x{package_flags:08x}",
        "package_flag_names": flag_names(package_flags, PACKAGE_FLAG_NAMES),
        "filter_editor_only": filter_editor_only,
        "name_count": name_count,
        "name_offset": name_offset,
        "localization_id": localization_id,
        "gatherable_text_data_count": gatherable_text_data_count,
        "gatherable_text_data_offset": gatherable_text_data_offset,
        "export_count": export_count,
        "export_offset": export_offset,
        "import_count": import_count,
        "import_offset": import_offset,
        "depends_offset": depends_offset,
        "soft_package_references_count": soft_package_references_count,
        "soft_package_references_offset": soft_package_references_offset,
        "searchable_names_offset": searchable_names_offset,
        "thumbnail_table_offset": thumbnail_table_offset,
        "guid": guid,
        "persistent_guid": persistent_guid,
        "owner_persistent_guid": owner_persistent_guid,
        "generations": generations,
        "engine_changelist": engine_changelist,
        "saved_by_engine_version": saved_by_engine_version,
        "compatible_with_engine_version": compatible_with_engine_version,
        "compression_flags": compression_flags,
        "compressed_chunks": compressed_chunks,
        "package_source": package_source,
        "package_source_hex": f"0x{package_source:08x}",
        "additional_packages_to_cook": additional_packages_to_cook,
        "num_texture_allocations": num_texture_allocations,
        "asset_registry_data_offset": asset_registry_data_offset,
        "bulk_data_start_offset": bulk_data_start_offset,
        "world_tile_info_data_offset": world_tile_info_data_offset,
        "chunk_ids": chunk_ids,
        "preload_dependency_count": preload_dependency_count,
        "preload_dependency_offset": preload_dependency_offset,
        "summary_size": summary_end - summary_start,
    }


def read_name_map(reader: Reader, summary: dict[str, Any]) -> list[str]:
    reader.seek(summary["name_offset"])
    names = []
    has_hashes = summary["effective_file_version_ue4"] >= VER_UE4_NAME_HASHES_SERIALIZED
    for _ in range(summary["name_count"]):
        value = reader.string(label="name entry", max_code_units=MAX_NAME_CODE_UNITS)
        if has_hashes:
            reader.read(4)
        names.append(value)
    return names


def format_name_ref(ref: NameRef, names: list[str]) -> dict[str, Any]:
    if ref.index < 0 or ref.index >= len(names):
        value = f"<bad-name-index:{ref.index}>"
    else:
        value = names[ref.index]
        if ref.number != 0:
            value = f"{value}_{ref.number - 1}"
    return {
        "index": ref.index,
        "number": ref.number,
        "value": value,
    }


def package_index(raw: int) -> dict[str, Any]:
    if raw == 0:
        return {"raw": raw, "kind": "null", "index": None}
    if raw > 0:
        return {"raw": raw, "kind": "export", "index": raw - 1}
    return {"raw": raw, "kind": "import", "index": -raw - 1}


def flag_names(value: int, table: dict[int, str]) -> list[str]:
    return [name for bit, name in table.items() if value & bit]


def read_import_map(reader: Reader, summary: dict[str, Any], names: list[str]) -> list[dict[str, Any]]:
    if summary["import_count"] == 0:
        return []
    reader.seek(summary["import_offset"])
    imports = []
    has_package_name = (
        summary["effective_file_version_ue4"] >= VER_UE4_NON_OUTER_PACKAGE_IMPORT
        and not summary["filter_editor_only"]
    )
    for index in range(summary["import_count"]):
        item = {
            "index": index,
            "class_package": format_name_ref(read_name_ref(reader), names),
            "class_name": format_name_ref(read_name_ref(reader), names),
            "outer_index": package_index(reader.i32()),
            "object_name": format_name_ref(read_name_ref(reader), names),
        }
        if has_package_name:
            item["package_name"] = format_name_ref(read_name_ref(reader), names)
        imports.append(item)
    return imports


def read_export_map(reader: Reader, summary: dict[str, Any], names: list[str]) -> list[dict[str, Any]]:
    if summary["export_count"] == 0:
        return []
    reader.seek(summary["export_offset"])
    exports = []
    version = summary["effective_file_version_ue4"]
    for index in range(summary["export_count"]):
        item = {
            "index": index,
            "class_index": package_index(reader.i32()),
            "super_index": package_index(reader.i32()),
        }
        if version >= VER_UE4_TEMPLATE_INDEX_IN_COOKED_EXPORTS:
            item["template_index"] = package_index(reader.i32())
        item.update(
            {
                "outer_index": package_index(reader.i32()),
                "object_name": format_name_ref(read_name_ref(reader), names),
                "object_flags": reader.u32(),
            }
        )
        item["object_flags_hex"] = f"0x{item['object_flags']:08x}"
        item["object_flag_names"] = flag_names(item["object_flags"], OBJECT_FLAG_NAMES)
        if version < VER_UE4_64BIT_EXPORTMAP_SERIALSIZES:
            item["serial_size"] = reader.i32()
            item["serial_offset"] = reader.i32()
        else:
            item["serial_size"] = reader.i64()
            item["serial_offset"] = reader.i64()
        item.update(
            {
                "forced_export": reader.boolean(),
                "not_for_client": reader.boolean(),
                "not_for_server": reader.boolean(),
                "package_guid": reader.guid(),
                "package_flags": reader.u32(),
            }
        )
        item["package_flags_hex"] = f"0x{item['package_flags']:08x}"
        item["package_flag_names"] = flag_names(item["package_flags"], PACKAGE_FLAG_NAMES)
        if version >= VER_UE4_LOAD_FOR_EDITOR_GAME:
            item["not_always_loaded_for_editor_game"] = reader.boolean()
        if version >= VER_UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT:
            item["is_asset"] = reader.boolean()
        if version >= VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
            item.update(
                {
                    "first_export_dependency": reader.i32(),
                    "serialization_before_serialization_dependencies": reader.i32(),
                    "create_before_serialization_dependencies": reader.i32(),
                    "serialization_before_create_dependencies": reader.i32(),
                    "create_before_create_dependencies": reader.i32(),
                }
            )
        exports.append(item)
    return exports


def read_depends_map(reader: Reader, summary: dict[str, Any]) -> list[list[dict[str, Any]]]:
    if summary["depends_offset"] <= 0 or summary["export_count"] == 0:
        return []
    reader.seek(summary["depends_offset"])
    depends = []
    for _ in range(summary["export_count"]):
        refs = read_array(reader, lambda: package_index(reader.i32()), label="depends entry")
        depends.append(refs)
    return depends


def read_soft_package_references(
    reader: Reader, summary: dict[str, Any], names: list[str]
) -> list[dict[str, Any]]:
    if (
        summary["soft_package_references_count"] <= 0
        or summary["soft_package_references_offset"] <= 0
    ):
        return []
    reader.seek(summary["soft_package_references_offset"])
    return [
        format_name_ref(read_name_ref(reader), names)
        for _ in range(summary["soft_package_references_count"])
    ]


def read_preload_dependencies(reader: Reader, summary: dict[str, Any]) -> list[dict[str, Any]]:
    if summary["preload_dependency_count"] <= 0 or summary["preload_dependency_offset"] <= 0:
        return []
    reader.seek(summary["preload_dependency_offset"])
    return [package_index(reader.i32()) for _ in range(summary["preload_dependency_count"])]


def preview_export_data(
    data: bytes, exports: list[dict[str, Any]], preview_bytes: int
) -> list[dict[str, Any]]:
    previews = []
    printable = set(bytes(string.printable, "ascii"))
    for item in exports:
        offset = item["serial_offset"]
        size = item["serial_size"]
        entry: dict[str, Any] = {
            "export_index": item["index"],
            "offset": offset,
            "size": size,
            "available_in_uasset": size >= 0 and offset >= 0 and offset + size <= len(data),
        }
        if entry["available_in_uasset"] and preview_bytes > 0:
            raw = data[offset : offset + min(size, preview_bytes)]
            entry["hex_preview"] = raw.hex(" ")
            entry["ascii_preview"] = "".join(
                chr(byte) if byte in printable and byte not in (10, 13, 9) else "."
                for byte in raw
            )
        previews.append(entry)
    return previews


def resolve_references(imports: list[dict[str, Any]], exports: list[dict[str, Any]]) -> None:
    def resolve_index(index_info: dict[str, Any], seen: set[tuple[str, int]] | None = None) -> str | None:
        if seen is None:
            seen = set()
        kind = index_info["kind"]
        index = index_info["index"]
        if kind == "null" or index is None:
            return None
        key = (kind, index)
        if key in seen:
            return f"<cycle:{kind}[{index}]>"
        seen.add(key)
        table = exports if kind == "export" else imports
        if index < 0 or index >= len(table):
            return f"<bad-{kind}-index:{index}>"
        item = table[index]
        outer = resolve_index(item["outer_index"], seen)
        name = item["object_name"]["value"]
        return f"{outer}.{name}" if outer else name

    for item in imports:
        item["path"] = resolve_index({"kind": "import", "index": item["index"], "raw": -(item["index"] + 1)})
        item["class"] = (
            f"{item['class_package']['value']}.{item['class_name']['value']}"
            if item["class_package"]["value"] != "None"
            else item["class_name"]["value"]
        )
    for item in exports:
        item["path"] = resolve_index({"kind": "export", "index": item["index"], "raw": item["index"] + 1})
        item["class"] = resolve_index(item["class_index"])
        item["super"] = resolve_index(item["super_index"])
        if "template_index" in item:
            item["template"] = resolve_index(item["template_index"])


def parse_uasset(path: str, *, include_export_data: bool, preview_bytes: int) -> dict[str, Any]:
    with open(path, "rb") as file:
        data = file.read()
    reader = Reader(data, path)

    summary = read_package_summary(reader)
    validate_summary(summary, len(data))
    names = read_name_map(reader, summary)
    imports = read_import_map(reader, summary, names)
    exports = read_export_map(reader, summary, names)
    resolve_references(imports, exports)

    result: dict[str, Any] = {
        "file": {
            "path": os.path.abspath(path),
            "size": len(data),
        },
        "summary": summary,
        "names": [{"index": index, "value": value} for index, value in enumerate(names)],
        "imports": imports,
        "exports": exports,
        "depends": read_depends_map(reader, summary),
        "soft_package_references": read_soft_package_references(reader, summary, names),
        "preload_dependencies": read_preload_dependencies(reader, summary),
    }
    if include_export_data:
        result["export_data"] = preview_export_data(data, exports, preview_bytes)
    return result


def export_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": metadata.get("file"),
        "exports": [
            {
                "path": export.get("path"),
                "class": export.get("class"),
                "super": export.get("super"),
                "is_asset": bool(export.get("is_asset")),
            }
            for export in metadata.get("exports", [])
            if isinstance(export, dict)
        ],
    }


def default_json_path(path: str) -> str:
    root, _ = os.path.splitext(os.path.basename(path))
    return os.path.join(os.getcwd(), root + ".json")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a UE4.27 .uasset package to readable metadata JSON.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {TOOL_VERSION}",
    )
    parser.add_argument("uasset", help="Path to a .uasset file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON path. Defaults to the input filename with a .json extension in the current directory.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the JSON document to stdout instead of writing a .json file.",
    )
    parser.add_argument(
        "--include-export-data",
        action="store_true",
        help="Also include serial data availability and byte previews in metadata.",
    )
    parser.add_argument(
        "--exports-only",
        action="store_true",
        help="Only print a compact export list with path, class, super, and is_asset.",
    )
    parser.add_argument(
        "--bytes",
        type=int,
        default=64,
        help="Number of export payload bytes to preview when --include-export-data is used.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of indented JSON.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces to use for pretty JSON indentation. Defaults to 2.",
    )
    return parser.parse_args(argv)


def format_json(result: dict[str, Any], *, compact: bool, indent: int) -> str:
    if compact:
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(result, ensure_ascii=False, indent=max(0, indent))


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        result = parse_uasset(
            args.uasset,
            include_export_data=args.include_export_data,
            preview_bytes=max(0, args.bytes),
        )
        if args.exports_only:
            result = export_summary(result)
    except (OSError, UAssetError, struct.error) as exc:
        print(f"uasset_to_text: {exc}", file=sys.stderr)
        return 1

    text = format_json(result, compact=args.compact, indent=args.indent)
    if args.stdout:
        try:
            print(text)
        except BrokenPipeError:
            return 0
    else:
        output_path = args.output or default_json_path(args.uasset)
        try:
            with open(output_path, "w", encoding="utf-8") as file:
                file.write(text)
                file.write("\n")
        except OSError as exc:
            print(f"uasset_to_text: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
