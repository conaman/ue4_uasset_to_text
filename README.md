# ue4_uasset_to_text

`ue4_uasset_to_text` is a small standalone CLI that converts an Unreal Engine
4.27 `.uasset` file into a reversible JSON text file, then restores that text
file back to the original `.uasset`.

The parser is based on UE4.27 package serialization code, especially
`FPackageFileSummary`, `FNameEntrySerialized`, `FObjectImport`, and
`FObjectExport`. It does not link against Unreal Engine.

## Features

- Reads UE4 package summary fields.
- Dumps the name table.
- Dumps import and export maps with resolved object paths where possible.
- Dumps dependency, soft package reference, and preload dependency tables.
- Optionally shows export payload offsets and a short byte preview.
- Writes UTF-8 JSON text for easy inspection or downstream processing.
- Embeds the original package bytes so `text_to_uasset.py` can restore the
  exact `.uasset` file.

## Requirements

- Python 3.9 or newer.
- A UE4 `.uasset` file.

No third-party Python packages are required.

## Usage

Convert `Asset.uasset` to `./Asset.json` in the current directory:

```bash
./uasset_to_text.py /path/to/Asset.uasset
```

Restore `Asset.json` to `./Asset.uasset` in the current directory:

```bash
./text_to_uasset.py /path/to/Asset.json
```

Print a unified metadata diff between two `.uasset` files:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset
```

Print a 3-way metadata diff report between a common base, ours, and theirs:

```bash
./uasset_diff3.py /path/to/Base.uasset /path/to/Ours.uasset /path/to/Theirs.uasset
```

Open P4Merge with generated JSON files. Pass two `.uasset` files for 2-way
compare, or pass `base ours theirs` for 3-way merge:

```bash
./uasset_p4merge.py /path/to/Old.uasset /path/to/New.uasset
./uasset_p4merge.py /path/to/Base.uasset /path/to/Ours.uasset /path/to/Theirs.uasset
```

Include export payload location and byte previews:

```bash
./uasset_to_text.py /path/to/Asset.uasset --include-export-data --bytes 64
```

Use a wider indentation:

```bash
./uasset_to_text.py /path/to/Asset.uasset --indent 4
```

Print compact JSON:

```bash
./uasset_to_text.py /path/to/Asset.uasset --compact
```

Print to the console instead of writing a `.json` file:

```bash
./uasset_to_text.py /path/to/Asset.uasset --stdout
```

Write to a specific path:

```bash
./uasset_to_text.py /path/to/Asset.uasset -o /tmp/Asset.json
./text_to_uasset.py /tmp/Asset.json -o /tmp/Asset.uasset
```

Diff the full reversible JSON wrapper, including embedded base64 bytes:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset --full-text
./uasset_diff3.py /path/to/Base.uasset /path/to/Ours.uasset /path/to/Theirs.uasset --full-text
./uasset_p4merge.py /path/to/Old.uasset /path/to/New.uasset --full-text
```

## Output

The default text file contains these top-level sections:

- `format`: text wrapper version.
- `source_path`: original input path.
- `source_filename`: original input filename.
- `sha256`: checksum of the embedded package bytes.
- `metadata`: parsed package metadata.
- `data_base64_lines`: original `.uasset` bytes encoded as text.

The `metadata` object contains:

- `file`: input path and file size.
- `summary`: package file summary fields and version data.
- `names`: package name table.
- `imports`: imported object table.
- `exports`: exported object table.
- `depends`: export dependency map.
- `soft_package_references`: soft package references.
- `preload_dependencies`: cooked preload dependency indexes.
- `export_data`: optional byte previews when `--include-export-data` is used.

## Limitations

This tool parses the package header tables and reports export payload locations.
It does not fully deserialize arbitrary UObject property data. Full UObject
deserialization needs the relevant UE classes and engine serializers loaded at
runtime.

The text format is a lossless JSON wrapper around the original binary package,
not Unreal Engine's native editable text asset serialization. Editing metadata
fields alone will not rewrite the embedded `.uasset` bytes. Use it for readable
inspection and exact round-trips.

The implementation targets Unreal Engine 4.27 package layout. Older UE4 assets
may work when their serialized fields match the covered version branches, but
the parser is intentionally conservative when it sees unsupported or implausible
data.

## Development

Run a syntax check:

```bash
python3 -m py_compile uasset_to_text.py text_to_uasset.py uasset_diff.py uasset_diff3.py uasset_p4_common.py uasset_p4merge.py
```

Run the tests:

```bash
python3 -m unittest
```

Try it against an engine sample asset:

```bash
./uasset_to_text.py /path/to/UnrealEngine/Engine/Content/MaterialTemplates/Textures/T_Noise01.uasset
```
