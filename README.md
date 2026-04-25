# ue4-uasset-tools

`ue4-uasset-tools` is a small standalone Python toolkit for inspecting
Unreal Engine 4.27 `.uasset` metadata as readable JSON.

It can:

- Convert a `.uasset` file to readable metadata JSON.
- Print a compact UMG widget tree summary with widget names and types.
- Print 2-way and 3-way metadata JSON diffs for `.uasset` files.
- Open Perforce P4Merge on generated metadata JSON files for visual comparison.

The parser reads UE4.27 package metadata tables, especially
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
| `uasset_to_text.py` | Convert `.uasset` to metadata JSON. |
| `uasset_umg_summary.py` | Print a UMG WidgetTree summary from a `.uasset` or metadata JSON file. |
| `uasset_diff.py` | Print a unified 2-way diff between two `.uasset` files. |
| `uasset_diff3.py` | Print a structured 3-way diff report. |
| `uasset_p4merge.py` | Convert `.uasset` files to metadata JSON, then open P4Merge. |
| `uasset_p4_common.py` | Internal helper code used by `uasset_p4merge.py`. |

## Quick Start

Convert `Asset.uasset` to metadata JSON at `./Asset.json` in the current
directory:

```bash
./uasset_to_text.py /path/to/Asset.uasset
```

Print JSON to the console instead of writing a file:

```bash
./uasset_to_text.py /path/to/Asset.uasset --stdout
```

Print a UMG widget summary directly from a `.uasset` file:

```bash
./uasset_umg_summary.py /path/to/Widget.uasset
```

Write to a specific path:

```bash
./uasset_to_text.py /path/to/Asset.uasset -o /tmp/Asset.json
```

## JSON Output

`uasset_to_text.py` writes parsed metadata as readable JSON. The output is for
inspection, summaries, and diff workflows. It is not a `.uasset` editing format
and cannot be converted back into a modified `.uasset` file.

Useful formatting options:

```bash
./uasset_to_text.py /path/to/Asset.uasset --indent 4
./uasset_to_text.py /path/to/Asset.uasset --compact
```

Include export payload locations and short byte previews:

```bash
./uasset_to_text.py /path/to/Asset.uasset --include-export-data --bytes 64
```

## UMG Widget Summary

`uasset_umg_summary.py` accepts a `.uasset` file directly. It uses the same
parser as `uasset_to_text.py` internally, then prints a focused WidgetTree
summary to stdout without creating an intermediate JSON file.

```bash
./uasset_umg_summary.py /path/to/Widget.uasset
```

Example output:

```text
Asset: WidgetMenu
UMG: WidgetBlueprint
ParentClass: UserWidget
Widgets: 6

WidgetTree
  CanvasPanel_0 (CanvasPanel)
    HorizontalBox_0 (HorizontalBox)
      StartButton (Button)
        StartText (TextBlock)
    SizeBox_0 (SizeBox)
      TitleText (TextBlock)
```

The default output shows `Name (Type)` entries. UMG slot exports are hidden by
default, but can be included when you need to inspect layout slot entries:

```bash
./uasset_umg_summary.py /path/to/Widget.uasset --include-slots
```

Print the summary as JSON:

```bash
./uasset_umg_summary.py /path/to/Widget.uasset --json
```

Metadata JSON from `uasset_to_text.py` can also be used as input:

```bash
./uasset_to_text.py /path/to/Widget.uasset
./uasset_umg_summary.py Widget.json
```

If the input does not look like a UMG asset, the command prints an error and
exits with a non-zero status.

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

`uasset_p4merge.py` converts `.uasset` files to temporary metadata JSON files,
then opens Perforce P4Merge.

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

On Windows, this README assumes `python` and `p4merge` are both on `PATH`:

```bat
python uasset_p4merge.py A.uasset B.uasset
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
  /path/to/ue4-uasset-tools/uasset_p4merge.py

Diff arguments:
  %1 %2

Merge application:
  /path/to/ue4-uasset-tools/uasset_p4merge.py

Merge arguments:
  %b %2 %1
```

Windows, assuming `python` is on `PATH`:

```text
Diff application:
  python

Diff arguments:
  "C:\path\to\ue4-uasset-tools\uasset_p4merge.py" %1 %2

Merge application:
  python

Merge arguments:
  "C:\path\to\ue4-uasset-tools\uasset_p4merge.py" %b %2 %1
```

Important: this merge registration opens a metadata JSON 3-way view. It does
not write a merged `.uasset` result back to P4V. Do not pass P4V's `%r`
placeholder to `--result`, because `%r` is normally the original `.uasset`
merge target and `uasset_p4merge.py` intentionally only allows `.json` review
result files.

### Result Files

For 3-way P4Merge runs, the merge result is a generated `.json` review file.
When the result file is kept and `--quiet` is not used, its path is printed to
stdout as a single line:

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
- `--result` must be a `.json` review path.
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

This tool focuses on package metadata tables and export payload locations.

`uasset_p4merge.py` is a JSON comparison launcher. Even if P4Merge saves a merged
JSON result, the original `.uasset` files are not modified.

The implementation targets Unreal Engine 4.27 package layout. Older UE4 assets
may work when their package metadata matches the layouts this parser handles,
but the parser is intentionally conservative when it sees unsupported or
implausible data.
