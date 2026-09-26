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
