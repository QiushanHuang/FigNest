# FigNest 4 workspace interfaces

Python 3.10+ standard library; SQLite schema 6. This extends the existing library, not a new datastore per experiment. The packaged macOS app and HTML entrance use the same backend. A v5 database receives a timestamped SQLite backup before migration. Full backup requires the entire data directory, not the database alone.

## Import adapters

For image-only scientific metadata, keep using `--config` and the existing `configuration.md` rules/overrides. General directory input is explicit:

```sh
python3 scripts/library.py import --input /approved/source --all-files --name "Experiment B" --options /approved/preset.json
python3 scripts/library.py refresh --library-id EXACT_ID
python3 scripts/library.py export --library-id EXACT_ID
```

`preset.json`:

```json
{"folder_id":null,"tags":["review"],"hierarchy":true,"auto_export":true}
```

Options persist per library; an update uses them unless explicitly replaced. `hierarchy` creates/reuses manual virtual folders for relative parent directories; without a target, a generated root is bound to the library ID, not its name. Same-named libraries get distinct numbered roots; renaming a library retains its root. Retiring a root allows a subsequent import to create a new one. Additional config `rules` assign metadata from explicit globs; filenames aren't scientific proof.

CLI limits: 5,000 assets and 256 MiB total. UI: same totals, 20 MiB per main asset; note attachments have a separate 2 GiB chunked path. No conversion, decompression, execution or OCR is implicit. Unsupported previews appear as file-type cards. CLI `--all-files` refresh remembers its mode; default image-only imports don't suddenly collect unrelated files. Symlinks/hidden files are skipped.

An import receipt distinguishes `added`, `changed`, `unchanged`, `missing`, `skipped`, `export` and `export_error`. Identical-byte assets share a blob but retain separate source identities. Changed content creates a version. Repeated source keys retain display rename, user tags, favorites, hide and notes. Failed auto-export does not roll back a successful import.

## Local API, contract version 1

The loopback server returns `api_version: 1` in state. Exact Host validation applies. Mutations require same Origin and the current `X-Viewer-Token` from the app shell; never expose the service on a public/LAN listener or store the token in shared configurations. Existing routes remain compatible. For agent automation, prefer CLI or the `Store` methods over browser scripting.

| Route | Body / result |
| --- | --- |
| GET `/api/state` | libraries, images/assets, folders, imports/exports, preferences, trash. Authenticated. |
| POST `/api/folder` | `name`, optional `id`, `parent_id`, `kind` (`manual`/`smart`), `query`. Returns `id`. Omit parent to keep it on rename; null moves to root. |
| POST `/api/batch` | `ids` list, `action`: favorite/hidden booleans, add_tags/remove_tags arrays, or folder_id + present. Atomic validation/transaction. |
| POST `/api/delete/batch` | `targets` list of kind/id. All targets are validated before an atomic recoverable deletion. |
| POST `/api/import-options` | `library_id`, `options` object. |
| POST `/api/preferences` | partial theme (`light`/`dark`), layout (`grid`/`list`), thumbnail (180–420), inspector boolean, sort. Stored in SQLite. |
| POST `/api/import/begin` | name, library_id, optional replace and options. Returns upload session. |
| POST `/api/import/add` | id, files list of relative `path` + base64 `data`. |
| POST `/api/import/commit` | id; validates then imports and applies rules. |
| POST `/api/import/cancel` | id; discard that temporary upload. |
| POST `/api/export` | library_id/folder_id/include_hidden. Folder scopes include descendants and matching smart children. |

`Store.folder`, `Store.batch`, `Store.set_import_options`, `Store.export` expose the same contracts to Python. Old `images` and `/media/ID` names are retained for compatibility, even for general assets. `asset_kind` is image/document/video/audio/file. General `/media/ID` downloads are octet-stream with attachment disposition and sandbox CSP. Original image preview stays in `<img>`, never inline SVG injection.

### Smart folder conditions

AND-combined keys: search (whitespace terms, case-insensitive), library_id, group, kind, favorite, tags (all present), fields (exact metadata values). Unknown keys/types are rejected. Example:

```json
{"search":"stress", "kind":"image", "tags":["report"], "favorite":true, "fields":{"composition":"E800"}}
```

Creating a smart folder does not tag or move anything. Query membership is computed from current state; manual membership APIs reject smart folders. Manual folders may contain smart-folder children, but smart folders cannot have children.

## Recovery boundaries

Software deletion uses deleted_at; permanent purge needs a fresh preview fingerprint plus typed confirmation in the UI. Folder purge includes descendants but not member assets. Deleting/retiring a folder clears import destinations that point into its subtree while keeping the remaining rules, so imports do not become blocked; restoring the folder doesn't automatically rebind these presets. Asset purge removes only unused app-owned bytes, not original sources, independent offline HTML or existing backups. Never test purge against real data. No watcher/login service, cloud sync or AI similarity model is installed.

## Validation scenarios

Run `tests/test_workspace.py`, original library/gallery suites, and Node `test_workspace.js` / `test_drop.js`. Focused UI checks: nested-folder create/reparent, import mixed files into a folder with tags/export, smart-query population, batch selection beyond 2, cross-library selection, 4-picture comparison, notes, list/grid and narrow window. Use an isolated datastore; verify real dataset counts and annotations after deployment, without adding test records to it.
