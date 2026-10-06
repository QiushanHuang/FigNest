# Release acceptance — 4.3.0

Verified on macOS 27 / Apple Silicon on 2026-10-06 with isolated synthetic libraries, then the installed app was checked against an existing local store.

| Question | Evidence |
| --- | --- |
| Can people recover from a narrow or empty search? | Current scope, removable filters, clear-all and wider search retaining the query checked in the live browser. |
| Are selection actions reachable while scrolling? | Bottom dock, hidden-selection counts, view selected/return, retained keyboard focus and folder search/membership feedback checked. Same-viewport before/after screenshots inspected. |
| Can 2–4 images be compared without losing the group? | Adaptive/manual layout, nonzero pane dimensions, relative zoom/pan linking, active image and view alone/return checked. |
| Do observation tools remain available? | Shared toolbar with collapsed annotation panel; shortcuts/help; 390×844 layout checked and temporary viewport override reset. |
| Can marks be cleared and text drafts retained? | Clear/undo, drawing bounds, automatic panel expansion, default preference, unplaced-text close guard and Escape cancellation checked. |
| Is saving reliable and visible? | Focused-text ⌘S in the packaged Mac app, save-all, independent coordinates/save state, actual HTTP 409 conflict with retained edits, and inline leave-dialog error checked. |
| Do exports contain saved marks? | Native save dialog produced a valid marked PNG; offline HTML showed saved marks with snapshot state and no save controls. |
| Does the installed update retain data? | Consistent pre-update SQLite backup, all existing table records compared before/after, integrity and foreign-key checks passed; original image opened in the installed 4.3.0 app. |
| Is package compatibility stated accurately? | Bundled Mach-O requirements inspected; maximum is macOS 27.0. Info.plist and public docs corrected, app root re-signed, deep/strict verification passed. |

**69 Python tests** and **5 Node suites** passed locally, including native menu/download policy, deployment metadata, geometry, history, concurrency and UX rules. JavaScript syntax checks passed. CI runs the source suites on Linux and macOS; see the actual [workflow results](https://github.com/QiushanHuang/FigNest/actions/workflows/ci.yml).

The public binary is Apple Silicon / macOS 27+, ad-hoc signed and not Apple-notarized. Pixel measurements are not physical calibration; PNG export caps at 64 million pixels. Offline HTML remains read-only. Synthetic screenshots contain no personal library content. This is focused release acceptance, not a full accessibility certification or performance benchmark.

---

# Release acceptance — 4.1.0

Verified on macOS 27 / Apple Silicon on 2026-09-26. Acceptance follows user-visible outcomes, not just a test total.

| Question | Evidence |
| --- | --- |
| Can settings be found and reached consistently? | Visible toolbar and sidebar buttons, native FigNest menu, and Command-comma open the same four-tab settings UI. |
| Does the shortcut work while typing or reloading? | Actual packaged Mac app tested with search-field focus, repeated opening, and immediate Command-R then Command-comma. |
| Does reopening keep saved choices? | Isolated browser datastore checked after reload/reopening; SQLite stores display and import choices. |
| Can fast changes overwrite the final choice? | Deferred-request regression tests cover reverting an in-flight value and switching library ownership while a save is pending. |
| Is About information accurate? | Actual native About panel shows 4.1.0 (10), the new icon, Qiushan / @QiushanHuang and the configured copyright. |
| Does updating preserve an existing library? | Pre/post-update record comparison found no changes in image records, annotations, library records or existing export count; SQLite integrity and foreign-key checks passed. |
| Are public images safe to share? | Workspace/settings screenshots use generated demonstration figures. About screenshot contains public branding only. |

Local automated checks: **60 Python tests**, including compiled AppKit menu assertions and scoped service-stop checks; Node workspace-core, drop traversal and deferred settings suites; JavaScript syntax checks; native build and ad-hoc signature verification. Stop tests verify preserved data and rejection of a receipt pointing at another live store's PID. CI separately runs on Linux and macOS; see the actual [workflow results](https://github.com/QiushanHuang/FigNest/actions/workflows/ci.yml).

The release is not Apple-notarized. No Intel package, full document renderer, background filesystem watcher, cloud sync or semantic-image similarity system is claimed. Generic files are stored and downloadable; supported image formats preview directly. Offline HTML is a snapshot rather than a live editor.
