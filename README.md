# ue4_uasset_to_text

`ue4_uasset_to_text` is a small standalone CLI that reads an Unreal Engine 4.27
`.uasset` file and prints its package metadata as JSON.

The parser is based on UE4.27 package serialization code, especially
`FPackageFileSummary`, `FNameEntrySerialized`, `FObjectImport`, and
`FObjectExport`. It does not link against Unreal Engine.

## Features

- Reads UE4 package summary fields.
- Dumps the name table.
- Dumps import and export maps with resolved object paths where possible.
- Dumps dependency, soft package reference, and preload dependency tables.
- Optionally shows export payload offsets and a short byte preview.
- Outputs UTF-8 JSON for easy inspection or downstream processing.

## Requirements

- Python 3.9 or newer.
- A UE4 `.uasset` file.

No third-party Python packages are required.

## Usage

Print pretty JSON to the console:

```bash
./uasset_to_text.py /path/to/Asset.uasset
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

You can redirect the output to a file:

```bash
./uasset_to_text.py /path/to/Asset.uasset > Asset.uasset.json
```

## Output

The JSON contains these top-level sections:

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

The implementation targets Unreal Engine 4.27 package layout. Older UE4 assets
may work when their serialized fields match the covered version branches, but
the parser is intentionally conservative when it sees unsupported or implausible
data.

## Development

Run a syntax check:

```bash
python3 -m py_compile uasset_to_text.py
```

Run the tests:

```bash
python3 -m unittest
```

Try it against an engine sample asset:

```bash
./uasset_to_text.py /path/to/UnrealEngine/Engine/Content/MaterialTemplates/Textures/T_Noise01.uasset
```
