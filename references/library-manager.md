# 图匣 persistent library manager

## Two entrances, one library

Open the installed FigNest app, or run `python3 scripts/library.py launch` for the lightweight HTML interface. Both connect to the same loopback service and `~/Pictures/ImageCollectionViewer` database; refresh the other view after an edit. The macOS App bundles its own Python backend and WebKit window. A separately exported offline HTML is a portable read-only snapshot, not a live database editor.

## Entrypoints

`python3 scripts/library.py [--data DIRECTORY] COMMAND` uses `~/Pictures/ImageCollectionViewer` by default. Run `--help` or command `--help` for flags. Do not use a new `--data` directory on each request: it is the entire multi-experiment store.

| Command | Meaning |
| --- | --- |
| `state` | JSON catalogue, IDs, saved annotations, import/export history and stale export flags. |
| `import --input DIR --name NAME` | Image library with managed copies. `--config JSON` can replace `--input`; `--all-files` opts in general files. |
| `import … --options JSON` | Import preset: tags, target folder, keep hierarchy, auto-export; persisted per library. |
| `import … --library-id ID` | Update the identified library; retain annotations and history. |
| `refresh --library-id ID` | Reread this library's already registered config/roots, never an arbitrary path from a webpage. |
| `export [--library-id ID] [--folder-id ID] [--include-hidden]` | Immutable offline snapshot; absent IDs mean all libraries/categories. |
| `launch [--no-open]` | Start/reuse local server, optionally open default browser. Prints URL. |
| `serve [--port 0]` | Foreground server; 0 chooses a free port. Only one server per store. |
| `install-launcher --destination /approved/path/图片看图器.command` | Fixed executable launcher; refuses unrelated existing content. |
| `backup` | Consistent SQLite snapshot under `backups/`; does not copy image blobs. |
| `rename`, `delete`, `restore` | App/UI operations for display names and recoverable catalogue deletion; see below. |

Fixed entry avoids remembering a port; it does not mean a global/public web address. Launch may select another port after restart. Server state is in `server.json`, startup diagnostics in `server.log`. Never kill a process solely from stale PID metadata; check its identity. If code changed while a server is running, an authorized restart is required to use new Python code; refresh the browser afterward. There is no login item, cron job or automatic OS startup installation.

## Storage and identity

- `library.sqlite3`: primary metadata and personal state. Versioned schema rejects unknown future versions.
- `blobs/`: immutable original image bytes, content-addressed to avoid storing equal bytes repeatedly. This local digest is a storage identity, not a scientific acceptance or remote provenance gate.
- `exports/<id>/index.html` and `manifest.json`: independent offline versions; never auto-pruned.
- `backups/`: metadata snapshots. For a complete portable backup, preserve the entire data directory, including blobs. The UI explicitly says database backup; do not call it a full image backup.

Each image ID is derived from library ID + stable source key. The same relative filename in different libraries is intentionally distinct. Renaming a library or image changes its display name, not the source filename or ID. Reimport changes managed metadata/content references, not favorite/hidden/note/category/name columns. Content changes append a version; old bytes remain. The UI reports version count, while old versions are retained internally, not yet an interactive rollback UI.

Directory refresh treats the supplied inventory as a full scan: missing paths are flagged, not erased. If a root is missing or no supported readable image is found, abort instead of treating it as an empty successful replacement. Renames cannot be guessed safely: old entries remain marked missing, new entries get new IDs. Do not automatically transfer annotations between renamed paths.

## Browser imports

The v4 UI accepts images and arbitrary ordinary files/directories explicitly selected or dragged by the user; uploads stay on the loopback service. Hidden entries are skipped. Images with invalid signatures/XML are rejected; general files are stored unchanged, without execution/conversion. Browser imports create or update a library with a separate `browser:` source namespace. Directory refresh retains browser additions; the full-inventory checkbox flags only unselected previous browser additions as missing. Selecting one outer directory removes that outer name; selecting several dragged directories retains each top-level name to avoid collisions. Drop assets onto a manual folder to add membership; drop a folder onto another to reparent safely.

Upload totals: 5,000 files / 256 MiB per import; UI single file cap 20 MiB (JSON chunk boundary). CLI directory import can handle a larger individual file within the 256 MiB total. Unsupported PDF/TIFF/HEIC are not converted implicitly. Uploaded data is validated before DB changes; temporary in-memory batches expire. Source inputs aren't deleted or moved.

## User state and exports

Image and source-group favorites are separate. Hide is reversible. Notes save explicitly. Arbitrary note attachments support 2 GiB each via chunked upload; offline HTML contains their names only. Custom folders are nested, many-to-many virtual relationships, with explicit parent IDs, sibling-name uniqueness, cycle prevention and breadcrumbs. Folder deletion hides its subtree; restore preserves children individually trashed earlier. Purging a folder removes its subtree and membership, never the member assets. Smart folders use saved conditions and update immediately as source state changes. A slash in an existing old folder name stays a literal label during migration; it does not imply a filesystem move.

The context menu on a picture, library or custom category offers common actions. "软件内删除" moves an image, category, library, or note attachment to 图匣's recovery area; restore it there. "永久删除" is available on an active item or a recovered-bin item. "清空回收区" permanently removes all items in that area, including images and attachments belonging to trashed libraries. Preview counts and a typed phrase gate each permanent action. A changed target invalidates the earlier preview. Permanent removal deletes catalogue records, versions and unreferenced app-managed bytes; it does not touch original source files, separately exported HTML snapshots, or existing database backups. Those independent copies must be reviewed separately if the user needs full erasure. No real user item is purged during feature testing.

Renaming retains stable source identity, notes and categories. Clicking an image title asks Finder to reveal the unchanged original when available; when it is unavailable or differs, Finder selects a named managed copy. Browser-dropped files use managed copies because browsers do not disclose original filesystem paths. Keep an older application copy until an update has been verified.

Imports create an immutable offline HTML when the per-library auto-export preset is enabled (default). Manual export can cover a nested subtree or smart query. General-file bytes are embedded for download, not active in-page execution. Editing metadata marks older library exports stale rather than rewriting distributed copies. History reports scope/count/time. Import can commit even if export fails: retry export, not import-as-new.

The live workspace separates unlimited management selection from 2–4-image comparison. Selection survives library navigation so cross-experiment comparison remains possible. Grid/list, thumbnail size, theme and inspector preferences persist in the database. An exact-content duplicate means identical bytes, not visual similarity or scientific equivalence; records are not silently merged. Import presets and metadata config rules provide repeatable automated organization without scanning unapproved roots or running background watchers. See `workspace-api.md`.

## Safety and verification

Loopback only; exact Host checks, same-Origin plus per-server token on mutation APIs, no CORS grant, no arbitrary web-supplied filesystem path API. Direct SVG responses have a sandbox CSP; UI never injects SVG into DOM. Original downloads are not sanitized. Labels/notes use DOM text nodes. Do not publish the data directory or open a public listener without explicit authorization.

After modifying code: run both test suites, then use a temporary store for browser checks. Verify new-library import, update/no duplicates, favorites/groups, hide/restore, notes after process restart, category membership, cross-library comparison, auto/manual export and offline preview. Synthetic tests must not add test notes to real scientific images. After migration verify count and original bytes against the identified old gallery. Existing raw results, scientific registries and remote jobs remain out of scope.
