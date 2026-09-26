# Configuration and import contract

Use `--input` one or more times for a simple catalogue, or `--config file.json` for explicit metadata. They are alternatives, not cumulative. Each root must be an existing directory. Relative config paths are resolved relative to the config file, not the process cwd. Python `~` expansion is supported; shell variables inside JSON are not expanded.

| Key | Meaning |
| --- | --- |
| `title`, `description` | Plain text page labels. `--title` overrides the config title. |
| `roots` | List of `{id, path, label?}`. IDs must be unique ASCII letters/digits/underscore/hyphen. Roots cannot overlap. |
| `filters` | List of `{key, label}`. Values come from each image's `fields`. Missing values show `未标注`. File format is always available. |
| `groups` | Optional map of group name to a plain text description. Counts come from actual images. |
| `exclude` | Shell-style globs against relative paths. Directory matches prune the subtree; `drafts` excludes that directory at the root, `*.tmp` excludes matching files. |
| `rules` | Ordered `{glob, root?, set}` rules. Paths use `/`. `fnmatch` glob `*` can span path separators. An optional `root` restricts a rule to that root ID. All matching rules run; later values win, fields merge. |
| `overrides` | Exact `rootID:relative/path.svg` to metadata patch mapping. Overrides run after rules; unmatched keys are reported. |

Metadata patches can set `group`, `title`, `caption` (strings), `tags` (list of strings) and `fields` (object of scalar values, shown as strings). They cannot change source paths, embedded bytes, format, IDs or download targets. Unknown top-level and patch keys are rejected to catch silent configuration mistakes.

Example overrides:

```json
{
  "study:control/force_plot.svg": {
    "title": "控制组：力与长度",
    "group": "对照组",
    "caption": "与实验组比较前，确认面积定义、初始长度和采样窗口一致。这里仅标注阅读提示，不作物理结论。",
    "fields": {"metric": "F–L", "model": "control", "temperature": "见原图"},
    "tags": ["主对照", "原图"]
  }
}
```

Use a supplied manifest for scientific metadata when available. Never substitute substring guesses for actual composition, model parameters, units, volume fractions or simulation acceptance. Filename-based classification is acceptable if explicitly labelled and limited to navigation.

## Output

- `index.html`: current self-contained page; no source folder or server required when copied.
- `manifest.json`: source inventory, metadata, skips, warnings and source-byte total. Count = images, not scientific cases.
- `config.json`: resolved reusable configuration, including absolute root paths.
- `revisions/TIMESTAMP/`: HTML, manifest and configuration for each build, never automatically removed.
- `.image-collection-viewer.json`: ownership/version pointer; not a scientific provenance registry.

HTML is atomic per entry file; publication of the entire file set is not a filesystem transaction. If an interrupted build leaves a lock/partial revision, preserve it and inspect the current HTML/manifest before recovery. Original images are never changed. The catalogue is a snapshot, not a live filesystem watcher.

## CLI

```text
gallery.py inspect [--input DIR ... | --config JSON] [--output DIR]
gallery.py build   [--input DIR ... | --config JSON] --output DIR [--update]
gallery.py serve   --output DIR [--port 0]
```

Both inspect/build accept `--title`, `--max-images` (default 5000), `--max-mib` (default 256). When inspecting a collection with the output inside an input root, supply `--output` so the generated subtree is excluded. Prefer output outside source directories. `serve` has no upload, editing, deletion, or remote filesystem API.
