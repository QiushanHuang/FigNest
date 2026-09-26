---
name: image-collection-viewer
description: Use when the user wants to manage FigNest / 图匣 libraries, images or files, organize nested or smart folders, import with reusable rules, compare pictures, annotate, recover or remove items, or export offline HTML. Not for creating plots or scientific conclusions.
---

# 图匣 · FigNest

**Default: 图匣 persistent library (`scripts/library.py`).** The lightweight local HTML entry and the macOS App use the same data store. The older standalone `gallery.py` remains compatible for one-off catalogues.

## Persistent libraries (preferred)

Default data directory: `~/Pictures/ImageCollectionViewer`. The native App is `~/Applications/图匣.app`; `~/Desktop/图匣.command` opens the lightweight HTML entrance. Both read the same library. Program/templates stay in this skill; user images and annotations never belong inside the skill or ResearchVault. Python 3.10+ standard library for the command-line program. Resolve `SKILL_DIR` from this installed file. When a user provides an image path:

1. Read `library.py state` and identify whether the user means a new experiment/library or updating an existing one. Match by explicit library ID, source and title; do not merge merely similar names. Ask only if the target is genuinely ambiguous.
2. Import only authorized local directories/configs; existing metadata schema is in `references/configuration.md`. Use recorded metadata, not guessed scientific parameters. Default CLI import is images-only; use `--all-files` when ordinary documents/files were requested. Import rules may add tags, preserve directory hierarchy, assign a virtual folder and optionally export HTML. Read `references/workspace-api.md` for these v4 interfaces.
3. For updates, retain `--library-id`. Repeated imports preserve favorites, hidden state, notes and category membership. Renamed source paths are new images; missing old paths retain managed copies and annotations. Changed content retains previous blob versions.
4. Open through `launch`, which starts or reuses a loopback server. For tool-controlled browser opening use `--no-open`, then open the returned URL. A fixed `.command` launcher can be installed at a user-approved location. Never install startup/login services by default.
5. Check asset counts, skips, changed/missing totals and export outcome. `export_error` means import committed but export needs recovery; do not duplicate the library. An absent `export` is normal when its import preset disables auto-export. Refresh an already-open page after CLI imports.

```sh
python3 "$SKILL_DIR/scripts/library.py" state
python3 "$SKILL_DIR/scripts/library.py" import --input "/path/to/images" --name "实验 B"
# Metadata-driven input: replace --input with --config /path/to/config.json
python3 "$SKILL_DIR/scripts/library.py" refresh --library-id EXACT_ID
python3 "$SKILL_DIR/scripts/library.py" export --library-id EXACT_ID
python3 "$SKILL_DIR/scripts/library.py" launch --no-open
```

The App and live HTML share a SQLite workspace: nested virtual folders, smart folders, tags, unlimited batch selection, 2–4-image comparison, generic-file cards, inspector, grid/list views, import presets, exact-content duplicate indication, notes/attachments, Finder, rename and recovery. Display preferences also live in SQLite, not browser cache. Notes save explicitly. Files may belong to several folders; moving/removing a folder never moves or deletes member source files. Smart folders are queries, not editable membership lists. Generic files are stored/downloaded, not executed or automatically converted. Offline HTML is a read-only snapshot; image/general-file bytes are embedded, while note attachments remain names only. Do not purge real user content to test deletion.

Read **`references/library-manager.md`** for operating modes, recovery, Finder, attachments and version semantics; **`references/workspace-api.md`** for nested folders, import presets, saved queries and automation. Automatic export runs when the library's preset enables it. No background watcher or login service is installed.

Settings are available from the visible toolbar button or native **FigNest → Settings… / ⌘,**. Display, per-library import/export rules, storage and About share one panel. Native **About FigNest** uses `assets/app-info.json` version/copyright via bundle metadata. The public source/distribution repository is `https://github.com/QiushanHuang/FigNest`; publication remains a separately authorized action.

## Legacy standalone gallery (only when requested)

Turn user-selected directories into a separate self-contained catalogue using `gallery.py`. This mode has no persistent personal annotations. Original images stay read-only; refreshed HTML retains prior revisions. Do not confuse it with the main library database.

## Workflow

1. Resolve the directory or directories the user explicitly placed in scope. If no path is supplied, ask only for the image location. Do not crawl home directories, historical projects, HPC, or remote hosts to guess inputs.
2. Use Python 3.10+ (`python3`, or an available bundled Python). There are no pip/npm/plugin dependencies. Resolve this skill's installed directory from its `SKILL.md`; do not assume the working directory is the skill folder.
3. Inspect before building. The program reports supported images, skipped files, groups, and byte totals without modifying sources:

   ```sh
   python3 "$SKILL_DIR/scripts/gallery.py" inspect --input "/path/to/images"
   ```

   For large inventories, keep output in a task-specific JSON file through the tool/environment's normal artifact mechanism, or inspect the returned structured summary; don't flood the conversation with thousands of paths. `inspect` reads/validates image bytes but writes nothing.
4. Default grouping is the first relative subfolder; root-level files are `未分组`. If the user requests dimensions such as model, metric, version or force range, read the closest existing manifest/index, then create a small JSON configuration using `references/configuration.md` and `assets/config.example.json`. Treat filenames as labels, not proof of units, scientific identity, simulation completion or physical equivalence. Unknown metadata stays unlabelled. Do not parse plot curves or invent conclusions.
5. Choose a separate output directory. Reuse an identified existing gallery only when the user asks to refresh it. Otherwise use a named sibling folder outside raw/immutable input data, or the current permitted artifact directory. Do not write image payloads into ResearchVault or install user images inside the skill.

   ```sh
   python3 "$SKILL_DIR/scripts/gallery.py" build \
     --input "/path/to/images" --output "/path/to/my-viewer" --title "实验图片对照"
   # For metadata-driven classification, use --config instead of --input:
   python3 "$SKILL_DIR/scripts/gallery.py" build \
     --config "/path/to/gallery-config.json" --output "/path/to/my-viewer"
   ```

6. Verify count/group totals against the import manifest, check skipped/unknown entries, then open `index.html`. For an in-app HTTP preview, use the included loopback server. Keep its process alive using the execution environment's supported session/background mechanism and use the printed URL. Do not claim an ephemeral server survives session shutdown.

   ```sh
   python3 "$SKILL_DIR/scripts/gallery.py" serve --output "/path/to/my-viewer" --port 0
   ```

   Use the available browser tool for a focused check: visible images decode; group/search/filter changes work; two selected images open side-by-side; labels do not overflow; clear/reset works. On a materially changed template, also check narrow width. Do not modify the template merely to change group names.
7. Deliver the local HTML link and, when running, the preview URL. State number of imported images, notable skips and classification assumptions. Explain that this is an image catalogue, not newly analysed data. No research record, scheduler, automation, or publication changes are implied.

## Reusing and updating

Each output contains `index.html`, `manifest.json`, reusable `config.json`, and timestamped `revisions/`. The HTML embeds the original image bytes and can be opened offline; source paths in the page are relative. The adjacent manifest/config include absolute input locations, so don't share them publicly without review.

```sh
python3 "$SKILL_DIR/scripts/gallery.py" build \
  --config "/path/to/my-viewer/config.json" \
  --output "/path/to/my-viewer" --update
```

The refresh changes only the gallery's current entry files and adds a revision. It does not modify source images. Never automatically delete revisions to save space. If a different collection should be compared, add a uniquely named non-overlapping root to a copied configuration, or use a new output folder. Keep root IDs stable to retain image identities. Updating an unrelated folder is rejected.

## Viewer contract

- SVG, PNG, JPEG, WebP, GIF and BMP; nested folders; Unicode/spaces; duplicate basenames.
- Group sidebar, optional metadata filters, text search, 12-image pagination, empty state and reset.
- Two-image comparison including cross-group selection; modal enlargement, original-size/fit toggle, keyboard Escape and original-byte downloads.
- Responsive layout, light/dark theme, explicit source/caption per image.
- No CDN, analytics, network upload, image recompression, scientific refit or automatic image editing.
- The template uses images in `<img>` contexts, never injects source SVG into live DOM. Labels use text nodes. Original SVG downloads are not sanitized and may retain scripts/external references; do not execute untrusted originals. Raster checks validate signatures, not full decoding; inspect browser decode failures.

## Boundaries and recovery

- Do not follow symlinks; hidden files/folders and unsupported formats are recorded as skipped. PDF/TIFF/HEIC are not converted implicitly. Offer an explicitly scoped conversion or source export if needed.
- Default cap: 5,000 images and 256 MiB total source bytes. Exceeding either stops before publication, never silently truncates. Split into smaller galleries or raise `--max-images`/`--max-mib` only after explaining offline HTML/memory cost (~4/3 source bytes plus browser overhead). Several revisions duplicate embedded payloads.
- `--update` is required for an owned nonempty output. An unknown nonempty output is refused. A build lock signals concurrent/interrupted work: first verify the process, preserve the partial revision, then resolve that exact lock; don't overwrite blindly.
- Source reading errors abort; corrupt supported files are recorded as skipped. Report these, not "all images imported".
- No server needed for offline HTML. A server binds only `127.0.0.1`, chooses a free port, and exposes only gallery `index.html` pages, not source roots/configs. Do not change to public/LAN binding without explicit authorization.

## Template maintenance only

The persistent program is `scripts/library.py`; interface shell `assets/library.html`, styling `assets/workspace.css`, interaction `assets/workspace.js`, pure behavior `assets/workspace-core.js`. Legacy `gallery.py` and the standalone `viewer.html` remain supported. For ordinary collections change data/config only. After program/template changes, run:

```sh
python3 "$SKILL_DIR/tests/test_gallery.py"
python3 "$SKILL_DIR/tests/test_library.py"
python3 "$SKILL_DIR/tests/test_workspace.py"
node "$SKILL_DIR/tests/test_workspace.js"
node "$SKILL_DIR/tests/test_settings.js"
node "$SKILL_DIR/tests/test_drop.js"
```

Validate the actual browser interaction as above. Keep tests synthetic and separate from real research data. See `references/validation.md` for the installed version's evidence and limitations.
