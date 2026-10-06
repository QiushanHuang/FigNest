# Changelog

## 4.3.0 — 2026-10-06

Public update from 4.1.0, including the intervening local image-tool builds.

- Original-pixel annotations: text, arrows, lines, rectangles, ellipses, freehand, horizontal/vertical guides and distance measurements; select/move/delete, undo/redo and one-action clear.
- Resident pan, box zoom, pixel rulers, fit/100% and visibility controls; configurable annotation expansion and tool shortcuts.
- Right-click 2–4-image comparison, adaptive/manual layout, explicit active image, optional relative zoom/pan linking, and single-image view with return to the same group.
- Scoped search and filter chips, useful empty results, persistent selection actions, view selected/return, title preview, keyboard navigation, searchable folder membership and save feedback.
- Explicit per-image/save-all actions, focused-text save shortcuts, independent save state, revision conflict protection and native quit/reload guards.
- Marked PNG and annotation JSON export; saved marks in new read-only offline HTML snapshots.
- Additive `image_markup` table; SQLite user_version stays 6, original files remain unchanged.
- Runtime-aware macOS deployment metadata, current dependency notices, expanded CI and bilingual guides. The 4.3.0 binary requires macOS 27+ / Apple Silicon; source browser use remains Python 3.10+.

### 中文

相较公开 4.1.0，包含中间本地版本的图片工具和便利性改进。

- 原始像素标注：文字、箭头、直线、矩形、椭圆、画笔、水平/垂直参考线和测距；移动、删除、撤销/重做与一键清除。
- 平移、框选放大、像素标尺、适应/100% 和显隐常驻；可选标注默认展开与工具快捷键。
- 右键 2–4 图比较、自适应/手动布局、当前图提示、相对视图联动、单独查看后返回同组。
- 搜索范围与筛选条目、无结果恢复、常驻选择栏、查看已选/返回、标题预览、键盘导航和文件夹搜索/保存反馈。
- 单图/全部保存、输入框内保存快捷键、独立保存状态、版本冲突保护及原生退出/重新载入保护。
- 标注 PNG、标注 JSON 导出，新离线 HTML 只读显示已保存标注。
- 新增 image_markup 表，SQLite user_version 保持 6，不改写原始文件。
- 根据实际运行环境设置最低系统版本，补齐许可证、CI 与中英文指南。4.3.0 二进制包要求 macOS 27+ / Apple Silicon，源码网页版仍支持 Python 3.10+。

## 4.1.0 — 2026-09-26

First public release of FigNest, bringing the existing local library workspace together with native Mac settings and distribution packages.

- Prominent toolbar Settings button; standard macOS **Settings… / ⌘,** and **About FigNest** menu items.
- Unified settings for appearance, layout, thumbnail size, sorting, inspector visibility, per-library import rules, export behavior and storage.
- Shared version/copyright metadata, native About panel, and a new FigNest app icon.
- Nested virtual folders, live smart folders, tags, notes, attachments, recovery and permanent-removal confirmation.
- Unlimited management selection and 2–4-image comparisons, including across libraries.
- General-file import and download cards; reusable presets and immutable offline HTML snapshots.
- Independent generated folder roots for same-named libraries; descendant-aware export invalidation; transactional batch recovery deletion; retired import destinations no longer block import.
- Portable source build, bilingual same-page README, user guide and release packages.
- Scoped `stop` command for updates/backups: live store, account, process and data-path checks before stopping a service.

No database schema change from local 4.0.0 (schema 6). Existing libraries, annotations, content versions and offline exports are retained.

### 中文

FigNest 首个公开版本，将已有的本地素材工作台、Mac 原生设置入口与发行包统一起来。

- 右上角显著设置按钮，Mac 菜单“设置… / ⌘,”和“关于 FigNest”。
- 显示、布局、缩略图大小、排序、详情面板、图库导入规则、导出与存储设置集中管理。
- 统一版本与版权信息；更新应用图标。
- 多级虚拟文件夹、智能文件夹、标签、备注、附件、回收及永久删除确认。
- 批量整理不受两张图片限制；跨图库 2–4 图对比。
- 普通文件导入、可复用规则和独立离线 HTML 导出。
- 修复同名图库的自动目录隔离、子目录修改后的导出状态、批量回收事务和退役导入目标。
- 中英同页 README、完整指南与可下载软件包。
- 用于更新与备份的 `stop` 命令，先核对图库身份、账号、进程与数据路径。

相较本地 4.0.0 不改变数据库 schema 6；既有图库、备注、内容版本和离线导出保留。
