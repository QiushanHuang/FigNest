# Develop FigNest

The runtime backend uses Python 3.10+ and the standard library. The live interface is plain HTML/CSS/JavaScript; the Mac wrapper uses AppKit and WKWebView.

| Path | Responsibility |
| --- | --- |
| `scripts/library.py` | SQLite store, loopback API, CLI, import/export |
| `assets/workspace-core.js` | Pure selection/filtering behavior |
| `assets/workspace.js`, `settings.js` | Browser interaction and settings |
| `assets/library.html`, `workspace.css` | Application shell and styling |
| `assets/viewer.html` | Standalone offline viewer |
| `native/` | Mac menu, window, About panel and app builder |
| `tests/` | Synthetic regression suites; use temporary stores |

## Validate

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_workspace.js
node tests/test_settings.js
node tests/test_drop.js
```

Native menu checks run on macOS. Before a release, verify the actual packaged App, settings with text-field focus, persistence after reopening, Finder reveal, mixed-file import, comparison, and offline export. Keep tests separate from a personal library.

Version/build/ownership data live in `assets/app-info.json`. Build with a Python environment containing PyInstaller and Xcode Command Line Tools. The builder uses system `sips`, `iconutil` and `codesign`; no third-party image converter is required.

Keep source files read-only during organization. Preserve database migrations, backup paths and exact import identities. General files must never be injected into the page as active HTML. Network access is loopback-only; retain the Host, Origin and token checks.

## Documentation

Keep English and Chinese in one README with `#english` and `#中文` anchors and a logo in both sections. Write about user scenarios, actions and outcomes. Use synthetic data for public screenshots; never commit library databases, user images, private paths, credentials or local verification receipts.
