# ue4_uasset_to_text

`ue4_uasset_to_text` is a small standalone Python toolkit for inspecting
Unreal Engine 4.27 `.uasset` files as readable JSON.

It can:

- Convert a `.uasset` file to a pretty JSON file.
- Restore a reversible JSON wrapper back to the exact original `.uasset` bytes.
- Print 2-way and 3-way JSON diffs for `.uasset` files.
- Open Perforce P4Merge on generated JSON files for visual comparison.

The parser is based on UE4.27 package serialization structures, especially
`FPackageFileSummary`, `FNameEntrySerialized`, `FObjectImport`, and
`FObjectExport`. It does not link against Unreal Engine.

## Requirements

- Python 3.9 or newer.
- A UE4 `.uasset` file.
- Perforce P4Merge is optional and only needed for `uasset_p4merge.py`.

No third-party Python packages are required.

## Tools

| Tool | Purpose |
| --- | --- |
| `uasset_to_text.py` | Convert `.uasset` to JSON. |
| `text_to_uasset.py` | Restore a reversible JSON wrapper to `.uasset`. |
| `uasset_diff.py` | Print a unified 2-way diff between two `.uasset` files. |
| `uasset_diff3.py` | Print a structured 3-way diff report. |
| `uasset_p4merge.py` | Convert `.uasset` files to JSON, then open P4Merge. |
| `uasset_p4_common.py` | Internal helper code used by `uasset_p4merge.py`. |

## Quick Start

Convert `Asset.uasset` to `./Asset.json` in the current directory:

```bash
./uasset_to_text.py /path/to/Asset.uasset
```

Restore `Asset.json` to `./Asset.uasset` in the current directory:

```bash
./text_to_uasset.py /path/to/Asset.json
```

Print JSON to the console instead of writing a file:

```bash
./uasset_to_text.py /path/to/Asset.uasset --stdout
```

Write to a specific path:

```bash
./uasset_to_text.py /path/to/Asset.uasset -o /tmp/Asset.json
./text_to_uasset.py /tmp/Asset.json -o /tmp/Asset.uasset
```

## JSON Output

By default, `uasset_to_text.py` writes a reversible JSON wrapper. It contains:

- `format`: text wrapper version.
- `source_path`: original input path.
- `source_filename`: original input filename.
- `sha256`: checksum of the embedded package bytes.
- `metadata`: parsed package metadata.
- `data_base64_lines`: original `.uasset` bytes encoded as text.

Use `--metadata-only` when you only want parsed metadata:

```bash
./uasset_to_text.py /path/to/Asset.uasset --metadata-only
```

Metadata-only JSON cannot be restored with `text_to_uasset.py` because it does
not contain the original binary bytes.

Useful formatting options:

```bash
./uasset_to_text.py /path/to/Asset.uasset --indent 4
./uasset_to_text.py /path/to/Asset.uasset --compact
```

Include export payload locations and short byte previews:

```bash
./uasset_to_text.py /path/to/Asset.uasset --include-export-data --bytes 64
```

## Diffing

Print a unified metadata diff between two `.uasset` files:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset
```

Return only the exit status:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset --quiet
```

Exit codes:

- `0`: no diff.
- `1`: differences found.
- `2`: error.

Diff the full reversible JSON wrapper, including embedded base64 bytes:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset --full-text
```

`--full-text` is useful when you need to verify the exact wrapper output, but it
can be very noisy because binary payloads are represented as base64.

## 3-Way Diff

Print a structured 3-way JSON diff report:

```bash
./uasset_diff3.py /path/to/Base.uasset /path/to/Ours.uasset /path/to/Theirs.uasset
```

The report separates non-conflicting `changes` from `conflicts`.

Exit codes:

- `0`: no changes.
- `1`: non-conflicting changes found.
- `2`: conflicts found.
- `3`: error.

## P4Merge Integration

`uasset_p4merge.py` converts `.uasset` files to temporary JSON files, then opens
Perforce P4Merge.

Use two files for a 2-way compare:

```bash
./uasset_p4merge.py /path/to/Old.uasset /path/to/New.uasset
```

Use three files for a 3-way view. The command accepts `base ours theirs`:

```bash
./uasset_p4merge.py /path/to/Base.uasset /path/to/Ours.uasset /path/to/Theirs.uasset
```

Internally, P4Merge is invoked in Perforce's expected order:

```text
base theirs yours result
```

### P4Merge Tool Path

The script looks for P4Merge in this order:

- `--tool`
- `P4MERGE`
- `MERGE`
- `p4merge` or `launchp4merge` on `PATH`
- common macOS P4Merge app paths

Examples:

```bash
./uasset_p4merge.py A.uasset B.uasset --tool "open -a p4merge --args"
./uasset_p4merge.py A.uasset B.uasset --tool "/Applications/p4merge.app/Contents/Resources/launchp4merge"
```

On Windows, this README assumes `python3` and `p4merge` are both on `PATH`:

```bat
python3 uasset_p4merge.py A.uasset B.uasset
```

### Registering in P4V

P4V can register external diff and merge applications by file type. In P4V,
open Preferences, then configure Diff and Merge applications for the `.uasset`
extension.

P4V diff placeholders:

- `%1`: first file.
- `%2`: second file.

P4V merge placeholders:

- `%b`: base file.
- `%1`: their/source file.
- `%2`: your/target file.
- `%r`: result file.

`uasset_p4merge.py` expects 3-way input as `base ours theirs`, so P4V merge
arguments must use `%b %2 %1`.

macOS or Linux, when the script is executable:

```text
Diff application:
  /path/to/ue4_uasset_to_text/uasset_p4merge.py

Diff arguments:
  %1 %2

Merge application:
  /path/to/ue4_uasset_to_text/uasset_p4merge.py

Merge arguments:
  %b %2 %1
```

Windows, assuming `python3` is on `PATH`:

```text
Diff application:
  python3

Diff arguments:
  "C:\path\to\ue4_uasset_to_text\uasset_p4merge.py" %1 %2

Merge application:
  python3

Merge arguments:
  "C:\path\to\ue4_uasset_to_text\uasset_p4merge.py" %b %2 %1
```

Important: this merge registration opens a JSON 3-way view. It does not write a
merged `.uasset` result back to P4V. Do not pass P4V's `%r` placeholder to
`--result`, because `%r` is normally the original `.uasset` merge target and
`uasset_p4merge.py` intentionally only allows `.json` result files.

### Result Files

For 3-way P4Merge runs, the merge result is a generated `.json` file. When the
result file is kept and `--quiet` is not used, its path is printed to stdout as
a single line:

```bash
result_json=$(./uasset_p4merge.py Base.uasset Ours.uasset Theirs.uasset)
echo "$result_json"
```

Status and temp directory messages are printed to stderr.

You can choose a result path:

```bash
./uasset_p4merge.py Base.uasset Ours.uasset Theirs.uasset --result /tmp/Merged.json
```

Safety rules:

- Original `.uasset` inputs are never used as merge result targets.
- `--result` must be a `.json` path.
- Existing result files are preserved unless `--overwrite-result` is used.
- Generated temp JSON files are kept by default because some GUI launchers
  return before P4Merge finishes reading the files.

Delete temp files after P4Merge exits:

```bash
./uasset_p4merge.py Base.uasset Ours.uasset Theirs.uasset --delete-temp
```

Use `--delete-temp` only with a P4Merge invocation that waits for the GUI to
close. Launchers such as `open -a p4merge --args` may return immediately.

## What This Tool Parses

The metadata object can include:

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

This tool parses package header tables and reports export payload locations. It
does not fully deserialize arbitrary UObject property data. Full UObject
deserialization needs the relevant UE classes and engine serializers loaded at
runtime.

The reversible JSON format is a lossless wrapper around the original binary
package. Editing metadata fields alone does not rewrite the embedded `.uasset`
bytes. Use it for readable inspection, exact round-trips, and diff workflows.

`uasset_p4merge.py` is a JSON comparison wrapper. Even if P4Merge saves a merged
JSON result, the original `.uasset` files are not modified. A merged JSON file
is only restorable with `text_to_uasset.py` if it is a valid reversible wrapper
containing embedded base64 data.

The implementation targets Unreal Engine 4.27 package layout. Older UE4 assets
may work when their serialized fields match the covered version branches, but
the parser is intentionally conservative when it sees unsupported or implausible
data.

## Development

Run a syntax check:

```bash
python3 -m py_compile uasset_to_text.py text_to_uasset.py uasset_diff.py uasset_diff3.py uasset_p4_common.py uasset_p4merge.py test_uasset_to_text.py
```

Run the tests:

```bash
python3 -m unittest
```

Try it against an engine sample asset:

```bash
./uasset_to_text.py /path/to/UnrealEngine/Engine/Content/MaterialTemplates/Textures/T_Noise01.uasset
```
