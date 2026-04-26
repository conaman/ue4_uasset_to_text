# ue4-uasset-tools

Current release: `2026-04-26`

`ue4-uasset-tools` is a small standalone Python toolkit for reviewing Unreal
Engine 4.27 `.uasset` metadata and UMG widget changes as readable JSON.

It can:

- Convert a `.uasset` file to readable metadata JSON.
- Extract UMG review properties such as slot padding, layout data, alignment,
  visibility, colors, widget styling, button/slider state, and custom primitive
  variables.
- Print a compact UMG WidgetTree export summary with widget names and types.
- Print 2-way and 3-way metadata JSON diffs for `.uasset` files.
- Open Perforce P4Merge on generated metadata JSON files for visual comparison.

The parser reads UE4.27 package metadata plus supported UMG tagged property
values. It does not link against Unreal Engine.

## Requirements

- Python 3.9 or newer.
- A UE4 `.uasset` file.
- Perforce P4Merge is optional and only needed for `uasset_p4merge.py`.

No third-party Python packages are required.

## Use Cases

- Review UMG hierarchy changes in Perforce before accepting a changelist.
- Review UMG layout changes such as padding, anchors, position, alignment, and
  parent/content slot relationships.
- Review widget property changes on Button, CheckBox, Image, Border, Slider,
  ProgressBar, SizeBox, ScaleBox, ScrollBox, ComboBoxString, and common panel
  slot types.
- Review TextBlock/RichTextBlock changes such as text source, localization key,
  font, color, shadow, wrapping, and justification.
- See custom primitive fields serialized on widgets without maintaining a
  property-name filter.
- Compare binary `.uasset` metadata without launching Unreal Editor.
- Inspect imports, exports, dependencies, and soft package references.
- Use P4Merge as a visual JSON diff viewer for UE4 assets.

## Tools

| Tool | Purpose |
| --- | --- |
| `uasset_to_text.py` | Convert `.uasset` to metadata JSON. |
| `uasset_umg_summary.py` | Print a UMG WidgetTree summary from a `.uasset` or metadata JSON file. |
| `uasset_diff.py` | Print a unified 2-way diff between two `.uasset` files. |
| `uasset_diff3.py` | Print a structured 3-way diff report. |
| `uasset_p4merge.py` | Convert `.uasset` files to metadata JSON, then open P4Merge. |

## Quick Start

Clone or download this repository, then run the scripts with Python 3.9 or
newer. The scripts do not need Unreal Engine or third-party Python packages.

Convert a `.uasset` to metadata JSON:

```bash
./uasset_to_text.py /path/to/Asset.uasset
```

Print a compact UMG WidgetTree summary:

```bash
./uasset_umg_summary.py /path/to/Widget.uasset
```

Compare two `.uasset` files as metadata JSON:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset
```

Open P4Merge on generated metadata JSON:

```bash
./uasset_p4merge.py /path/to/Old.uasset /path/to/New.uasset
```

## Examples

Sample outputs generated from a UE4.27 UMG widget asset are available in
`examples/`:

- `WidgetMenu.summary.txt`: UMG WidgetTree summary output.
- `WidgetMenu.exports.json`: compact export list with path and class fields.
- `WidgetMenu.metadata.json`: full metadata JSON produced by
  `uasset_to_text.py`, with the file path shortened for readability.
- `WidgetMenu.review_properties.json`: UMG `review_properties` excerpt showing
  every parsed export property and `_raw_hex` for unparsed values.
- `Snapshot_UI_VR.review_properties.json`: focused UMG `review_properties`
  excerpt showing CanvasPanelSlot `LayoutData` position, anchors, alignment,
  and slot padding/alignment fields.
- `WidgetMenu.diff.txt`: unified metadata diff between two widget revisions.

## Usage

### uasset_to_text.py

`uasset_to_text.py` writes parsed metadata as readable JSON. The output is for
inspection, summaries, and diff workflows. It is not a `.uasset` editing format
and cannot be converted back into a modified `.uasset` file.

Default output path is `./Asset.json` in the current directory:

```bash
./uasset_to_text.py /path/to/Asset.uasset
```

Common options:

```bash
./uasset_to_text.py /path/to/Asset.uasset --stdout
./uasset_to_text.py /path/to/Asset.uasset -o /tmp/Asset.json
./uasset_to_text.py /path/to/Asset.uasset --indent 4
./uasset_to_text.py /path/to/Asset.uasset --compact
./uasset_to_text.py /path/to/Asset.uasset --no-review-properties
```

Print a compact export list:

```bash
./uasset_to_text.py /path/to/Asset.uasset --exports-only
```

Example export entry:

```json
{
  "path": "WidgetMenu.WidgetTree.ExitButton",
  "class": "/Script/UMG.Button",
  "super": null,
  "is_asset": false
}
```

### uasset_umg_summary.py

`uasset_umg_summary.py` accepts a `.uasset` file directly. It uses the same
parser as `uasset_to_text.py` internally, then prints a focused list of
WidgetTree exports without creating an intermediate JSON file.

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
  Border_0 (Border)
  ExitButton (Button)
  RestartButton (Button)
  Text_ExitButton (TextBlock)
  Text_RestartButton (TextBlock)
  VerticalBox_48 (VerticalBox)
```

The default output shows `Name (Type)` entries. UMG slot exports are hidden by
default. Parent/content relationships are available in `review_properties`
fields such as `Parent`, `Content`, `Slot`, and `Slots`.

Common options:

```bash
./uasset_umg_summary.py /path/to/Widget.uasset --include-slots
./uasset_umg_summary.py /path/to/Widget.uasset --json
./uasset_umg_summary.py /path/to/Widget.uasset --show-paths
```

Metadata JSON from `uasset_to_text.py` can also be used as input:

```bash
./uasset_to_text.py /path/to/Widget.uasset
./uasset_umg_summary.py Widget.json
```

If the input does not look like a UMG asset, the command prints an error and
exits with a non-zero status.

### uasset_diff.py

Print a unified metadata diff between two `.uasset` files:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset
```

Common options:

```bash
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset --quiet
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset --keep-paths
./uasset_diff.py /path/to/Old.uasset /path/to/New.uasset --context-lines 8
```

Exit codes:

- `0`: no diff.
- `1`: differences found.
- `2`: error.

### uasset_diff3.py

Print a structured 3-way JSON diff report:

```bash
./uasset_diff3.py /path/to/Base.uasset /path/to/Ours.uasset /path/to/Theirs.uasset
```

The report separates non-conflicting `changes` from `conflicts`.

Common options:

```bash
./uasset_diff3.py Base.uasset Ours.uasset Theirs.uasset --quiet
./uasset_diff3.py Base.uasset Ours.uasset Theirs.uasset --keep-paths
./uasset_diff3.py Base.uasset Ours.uasset Theirs.uasset --indent 4
```

Exit codes:

- `0`: no changes.
- `1`: non-conflicting changes found.
- `2`: conflicts found.
- `3`: error.

### uasset_p4merge.py

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

Common options:

```bash
./uasset_p4merge.py A.uasset B.uasset --tool "open -a p4merge --args"
./uasset_p4merge.py A.uasset B.uasset --keep-paths
./uasset_p4merge.py A.uasset B.uasset --delete-temp
./uasset_p4merge.py Base.uasset Ours.uasset Theirs.uasset --result /tmp/Merged.json
./uasset_p4merge.py Base.uasset Ours.uasset Theirs.uasset --overwrite-result
```

### P4Merge Tool Path

The script looks for P4Merge in this order:

- `--tool`
- `P4MERGE`
- `MERGE`
- `p4merge` or `launchp4merge` on `PATH`
- common macOS P4Merge app paths

Tool path examples:

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
- `exports`: exported object table, with `review_properties` on supported UMG
  exports when tagged properties are found.
- `depends`: export dependency map.
- `soft_package_references`: soft package references.
- `preload_dependencies`: cooked preload dependency indexes.

## UMG Review Coverage

`review_properties` is emitted for UMG and WidgetTree exports when the parser
can read the tagged property stream. Property names are not filtered, so custom
primitive fields on widgets can show up too.

- hierarchy references: `Parent`, `Content`, `Slot`, `Slots`
- layout: Canvas `LayoutData`, `Padding`, alignment, size, row/column/layer,
  SizeBox/ScaleBox settings, and major panel slot settings
- appearance: `Brush`, `Background`, `WidgetStyle`, colors, visibility, render
  opacity, and render transform
- interaction/state: Button and CheckBox methods/focus/state, Slider values,
  ProgressBar percent/fill, ScrollBox and ComboBox behavior
- text: TextBlock, RichTextBlock, EditableText, and EditableTextBox content,
  font, color, shadow, wrapping, justification, and virtual keyboard options
- custom values: supported primitive properties such as bool, int, float,
  string, text, name, enum, object/class references, and arrays of those values

WidgetTree custom widgets are checked too. For example, a `CustomButton` can
show inherited Button fields, and a `CustomTextBlock` can show inherited
TextBlock fields. A `ModuleWidget` can also show custom primitive fields that
are serialized in the parent widget instance.

When a property is present but its value is not decoded yet, it is kept as
`_unparsed` with `_raw_hex`. That means the diff can still show that a value
changed, even when this tool cannot name every field inside that value.

## Limitations

This tool focuses on package metadata tables and supported UMG tagged property
values. It is not a full UObject property serializer.

Unsupported custom serializers are marked as `_unparsed` with `_raw_hex`
instead of guessed. Default-valued properties may not appear if Unreal did not
serialize them into the asset.

Struct arrays can be reported as `_unparsed` when the asset stream only says
the array contains `StructProperty` values and does not include the concrete
struct type name needed to decode each element safely.

`uasset_p4merge.py` is a JSON comparison launcher. Even if P4Merge saves a merged
JSON result, the original `.uasset` files are not modified.

The implementation targets Unreal Engine 4.27 package layout. Older UE4 assets
may work when their package metadata matches the layouts this parser handles,
but the parser is intentionally conservative when it sees unsupported or
implausible data.
