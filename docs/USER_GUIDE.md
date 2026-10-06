<a id="english"></a>
# FigNest user guide

[English](#english) · [简体中文](#中文)

The 4.3.0 Mac download requires Apple Silicon and macOS 27+ and includes its runtime.
The source browser edition needs Python 3.10+.

## 1. Start a library

Click **＋ 导入 / Import**. Choose individual files or a directory, select an existing library or name a new one, then import. The result reports new, updated and skipped items. Reimport into the same library to retain its curation.

Choose **Keep directory hierarchy** to create virtual folders matching the selected directory structure. Assign an existing folder to keep a particular project under a stable parent. Add comma-separated tags and choose whether each import should also generate an offline HTML.

## 2. Organize and find

- Use the sidebar **＋** beside Folders to create a manual or smart folder. Choose a parent to make a subfolder.
- Click a thumbnail once to select and inspect, or double-click/press Space to preview. Clicking the title opens the preview. Use More or the right-click menu for Finder access.
- Check boxes or use ⌘A for the current filtered result. Shift-select covers a continuous range. Selection remains when switching libraries.
- The bottom selection bar stays available while scrolling. View all selected items, including ones outside the current filters, then return to your original view. Use folders, tags, favorites or More for batch actions. The folder picker supports search and partial-membership feedback.
- Right-click a card or folder for contextual actions. Compare appears when 2–4 selected items are images. Permanent removal is kept in recovery.
- Search matches titles, paths, notes, tags and metadata within the displayed scope. Remove filter chips or clear filters; an empty result can search all assets with the same keywords. Use **保存筛选 / Save filters** to create a smart folder.
- Arrow keys and Home/End move between visible items; Enter/Space previews the focused item.
- Smart folders match all their selected conditions; manual membership is managed separately. The duplicate-content view indicates identical bytes, not visually similar images.

## 3. Compare and annotate

Select 2–4 image items, then **right-click → 并排比较 / Compare**, click Compare in the persistent selection bar, or press ⌘Enter. Click a pane to make it the current image; a blue outline identifies it. The shared toolbar controls that image. Choose automatic/one-row/two-column layout (two columns for 3–4 images), optional relative zoom/pan linking, and fill-window view. **View alone → Return to comparison** keeps the same group and layout; previous/next stays within that comparison.

Pan (**V**), box zoom (**Z**), pixel distance (**R**), fit, 100%, pixel rulers and annotation visibility remain available with the annotation panel closed. Hold Space for temporary pan. Expand **标注工具 / Annotation tools** for arrows (**A**), lines (**L**), rectangles (**M**), ellipses (**O**), freehand (**B**), text (**T**), horizontal (**H**) and vertical (**G**) reference lines. These keys act on the current image and do not interrupt typing in text fields.

For text, enter the content and click the image to place it; Escape cancels an unplaced draft. Draw inside the image. Use Select to move a mark, Delete to remove the selected mark, and Undo/Redo to recover edits. **Clear annotations** clears the current image and can be undone. Choose **Expand annotations by default** in the panel or Display settings; observation tools stay available either way.

Save explicitly with **保存标注 / Save annotations** or ⌘S / Ctrl+S, including when the text field has focus. Comparison offers **保存全部 / Save all**. Save state is separate from coordinates and mode. A close/navigation/quit/reload guard protects unsaved edits. On an error or version conflict, keep the editor open; failed saves preserve edits. An unplaced text draft must be placed or canceled before saving.

Export a marked PNG or annotation JSON for an independent copy of the marks. Saved annotations use original decoded pixel coordinates and remain separate from source bytes. Pixel distances are not calibrated physical measurements. New offline HTML exports show saved marks read-only; editing or creating marks requires the live library.

Open **Notes and attachments** from the inspector or context menu. Save the note explicitly; dragged note files are saved as attachments. Right-click a source-group button within a library to favorite or annotate the whole group.

## 4. Settings

The toolbar button, sidebar button and native **FigNest → Settings… / ⌘,** reach the same settings panel.

| Tab | Options |
| --- | --- |
| Display | Light/dark appearance, grid/list, thumbnail size, sorting, inspector, default annotation expansion |
| Import & export | Per-library target folder, tags, directory hierarchy, automatic HTML |
| Storage | Data location, managed-file/database sizes, open folder, database backup |
| About | Version, build, copyright and maintainer |

Display preferences and import rules save when changed. The native app menu also includes **About FigNest** in a standard Mac About panel.

## 5. Export and share

Choose a library, nested folder or smart folder in **Export**. Hidden items are excluded unless enabled. A new export leaves earlier exports intact. Download or locate its HTML file and open it in a browser without starting FigNest.

The HTML contains the chosen image/general-file bytes and saved annotations. Ordinary files are downloadable cards. Note attachments are listed by name; use the live library for those attachment bytes. Offline comparison/filtering does not edit your database.

## 6. Recovery, backup and update

**Move to recovery** removes an item from ordinary views and allows restoration. A folder operation affects its virtual subtree; the member assets stay in the library. Removing a folder also clears import destinations pointing into that subtree, so future imports can continue.

**Permanently remove** and **Empty recovery** show a current item count and require a typed phrase. They remove FigNest records and unreferenced managed data, not the source files or previously exported HTML.

For a complete backup, finish imports/exports, close the live viewers, run `python3 scripts/library.py stop`, and preserve the entire `~/Pictures/ImageCollectionViewer` directory. The Settings database-backup command stores metadata only. Update the app separately from this data directory. `stop` verifies the live store identity, process owner and exact data-directory command before sending a signal; it never deletes library files.

## 7. Command-line automation

Run `python3 scripts/library.py --help`. Use `state` for exact IDs, `import` or `refresh` for repeatable ingestion, and `export` for snapshots. See [automation](automation.md) and [metadata configuration](../references/configuration.md). The local service uses a loopback address; do not expose it on a shared network.

---
<a id="中文"></a>
## 中文

[English](#english) · [简体中文](#中文)

4.3.0 Mac 下载包要求 Apple Silicon 与 macOS 27+，自带运行环境。
源码网页版需要 Python 3.10+。

### 1. 建立图库

点击**＋ 导入**，选择文件或目录，指定已有图库或填写新名称。导入结果会显示新增、更新和跳过数量。更新已有集合时请选择同一个图库，以保留之前的整理。

“保留目录层级”会按所选目录生成虚拟文件夹。也可以指定一个稳定的父文件夹，添加逗号分隔的标签，并选择导入后是否自动生成 HTML。

### 2. 整理和查找

- 点击侧栏文件夹旁的 **＋**，建立手动或智能文件夹；选择上级目录即可创建子文件夹。
- 单击缩略图选择并查看详情，点击标题、双击或空格预览。通过更多或右键菜单在 Finder 定位原文件或图库副本。
- 通过复选框或 ⌘A 批量选择；Shift 连续多选。切换图库仍保留选择，方便跨项目比较。
- 底部选择栏随滚动常驻，可查看筛选范围外的已选项，再返回原页面。支持文件夹、标签、收藏和更多批量操作；文件夹选择支持搜索与部分成员提示。
- 图片与目录支持右键菜单。选中 2–4 张图片时可直接右键比较；永久删除入口留在回收区。
- 搜索在所显示的范围内匹配标题、路径、备注、标签和参数。可移除筛选条目或清空条件；无结果时保留关键词搜索全部素材。**保存筛选**建立智能文件夹。
- 方向键与 Home/End 在可见素材中移动，Enter / 空格预览当前焦点项。
- 智能文件夹要求同时满足选中的条件；手动分类单独管理。“重复内容”表示字节完全相同，不代表视觉相似。

### 3. 对比、标注和备注

选择 2–4 张图片，通过**右键 → 并排比较**、底部选择栏或 ⌘Enter 进入。点击面板使其成为当前图，蓝色边框明确操作目标，共享工具栏控制该图。支持自动/一行/两列布局（两列适用于 3–4 张图）、相对缩放和平移联动、铺满窗口。**单独查看 → 返回比较**保留图片组与布局，前后切换只在当前比较组内进行。

平移（**V**）、框选放大（**Z**）、像素测距（**R**）、适应窗口、100%、像素标尺和标注显隐常驻；按住空格可临时平移。展开**标注工具**后，可用箭头（**A**）、直线（**L**）、矩形（**M**）、椭圆（**O**）、画笔（**B**）、文字（**T**）、水平（**H**）和垂直（**G**）参考线。快捷键作用于当前图片，输入文字时不会抢占单键。

文字输入后点击图片放置，Escape 取消未放置草稿。绘制需从图片内开始。选择工具可移动标注，Delete 删除选中的标注，撤销/重做恢复修改。**清除标注**一键清空当前图片，可撤销。在面板或显示设置里选择**默认展开标注工具**，收起后观察工具仍可用。

点击**保存标注**或 ⌘S / Ctrl+S 明确保存，文字框内同样有效；比较支持**保存全部**。保存状态与坐标、操作模式分开显示。关闭、切换、退出和重新载入前保护未保存修改；保存错误或版本冲突会保留编辑内容。未放置的文字须先放置或取消再保存。

可导出标注 PNG 或 JSON，独立保留标注数据。标注使用解码图片的原始像素坐标，单独保存，不改写源文件；像素距离不等于标定后的物理尺寸。新导出的离线 HTML 只读显示已保存标注，编辑标注需要实时图库。

在详情或右键菜单里打开**备注与附件**。文字备注需要明确保存，拖入备注区的文件会成为附件。在图库组别按钮上右键，可收藏或备注整个组。

### 4. 设置

右上角按钮、侧栏按钮和原生菜单 **FigNest → 设置… / ⌘,** 打开同一个设置面板。

| 分类 | 内容 |
| --- | --- |
| 显示 | 深浅外观、网格/列表、缩略图、排序、详情面板、标注默认展开 |
| 导入与导出 | 各图库的默认目录、标签、目录层级和自动 HTML |
| 存储 | 数据位置、托管文件和数据库大小、打开目录、数据库备份 |
| 关于 | 版本、构建号、版权与维护者 |

显示与导入规则修改后保存到数据库。Mac 左上角应用菜单也提供标准的**关于 FigNest**窗口。

### 5. 导出与分享

点击**导出**，选择图库、目录及其子目录，或智能目录的结果。默认不包含隐藏项；每次产生一个新快照，之前的版本继续保留。拿到 HTML 后可直接用浏览器离线打开。

HTML 内嵌所选图片、普通文件内容及保存的说明。普通文件以可下载卡片呈现；备注附件只列名称，访问附件文件请回实时图库。离线页的筛选与比较不会修改本机数据库。

### 6. 回收、备份和更新

**移入回收区**可恢复。文件夹操作只影响虚拟目录树，成员素材仍在图库内。删除目录时会清除指向其子树的导入目标，以便后续导入继续执行。

**永久删除**与**清空回收区**会显示当前数量并要求输入确认词，移除图库记录及不再使用的托管内容；不会删除原始来源文件或已经导出的独立 HTML。

完整备份时，完成导入导出、关闭实时窗口，运行 `python3 scripts/library.py stop`，再复制整个 `~/Pictures/ImageCollectionViewer`。设置中的数据库备份只保存整理记录。`stop` 会核对服务身份、进程所属账号和准确的数据目录后才停止，不删除图库文件。更新应用与图库数据分开进行。

### 7. 命令行自动化

运行 `python3 scripts/library.py --help`。用 `state` 查看准确 ID，通过 `import` 或 `refresh` 重复导入，用 `export` 生成快照。详见[自动化接口](automation.md)和[元数据配置](../references/configuration.md)。服务仅监听本机，不要暴露到共享网络。
