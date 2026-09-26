<a id="english"></a>
# FigNest user guide

[English](#english) · [简体中文](#中文)

## 1. Start a library

Click **＋ 导入 / Import**. Choose individual files or a directory, select an existing library or name a new one, then import. The result reports new, updated and skipped items. Reimport into the same library to retain its curation.

Choose **Keep directory hierarchy** to create virtual folders matching the selected directory structure. Assign an existing folder to keep a particular project under a stable parent. Add comma-separated tags and choose whether each import should also generate an offline HTML.

## 2. Organize and find

- Use the sidebar **＋** beside Folders to create a manual or smart folder. Choose a parent to make a subfolder.
- Click a thumbnail once to select and inspect, or double-click/press Space to preview. Clicking the title reveals its source or managed copy in Finder.
- Check boxes or use ⌘A for the current filtered result. Shift-select covers a continuous range. Selection remains when switching libraries.
- Use the batch bar for folders, tags, favorites and hiding. Right-click a card or folder for contextual actions.
- Search matches titles, paths, notes, tags and metadata. Use the filter panel for exact metadata values. Save suitable conditions as a smart folder.
- Smart folders match all their selected conditions; manual membership is managed separately. The duplicate-content view indicates identical bytes, not visually similar images.

## 3. Compare and annotate

Select 2–4 image items and click **Compare** or press ⌘Enter. Each panel keeps its title and source label. Switch between fit and original size. Single-image preview supports previous/next navigation.

Open **Notes and attachments** from the inspector or context menu. Save the note explicitly; dragged note files are saved as attachments. Right-click a source-group button within a library to favorite or annotate the whole group.

## 4. Settings

The toolbar button, sidebar button and native **FigNest → Settings… / ⌘,** reach the same settings panel.

| Tab | Options |
| --- | --- |
| Display | Light/dark appearance, grid/list, thumbnail size, sorting, inspector |
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

### 1. 建立图库

点击**＋ 导入**，选择文件或目录，指定已有图库或填写新名称。导入结果会显示新增、更新和跳过数量。更新已有集合时请选择同一个图库，以保留之前的整理。

“保留目录层级”会按所选目录生成虚拟文件夹。也可以指定一个稳定的父文件夹，添加逗号分隔的标签，并选择导入后是否自动生成 HTML。

### 2. 整理和查找

- 点击侧栏文件夹旁的 **＋**，建立手动或智能文件夹；选择上级目录即可创建子文件夹。
- 单击缩略图选择并查看详情，双击或空格预览。点击标题在 Finder 定位原文件或图库副本。
- 通过复选框或 ⌘A 批量选择；Shift 连续多选。切换图库仍保留选择，方便跨项目比较。
- 批量栏可操作文件夹、标签、收藏和隐藏。图片与目录都支持右键菜单。
- 搜索匹配标题、路径、备注、标签和参数；筛选面板提供参数精确匹配，可保存为智能文件夹。
- 智能文件夹要求同时满足选中的条件；手动分类单独管理。“重复内容”表示字节完全相同，不代表视觉相似。

### 3. 对比和备注

选择 2–4 张图片，点击**并排比较**或按 ⌘Enter。各面板保留名称和来源，可切换适应窗口或原始尺寸。单图预览支持前后切换。

在详情或右键菜单里打开**备注与附件**。文字备注需要明确保存，拖入备注区的文件会成为附件。在图库组别按钮上右键，可收藏或备注整个组。

### 4. 设置

右上角按钮、侧栏按钮和原生菜单 **FigNest → 设置… / ⌘,** 打开同一个设置面板。

| 分类 | 内容 |
| --- | --- |
| 显示 | 深浅外观、网格/列表、缩略图、排序、详情面板 |
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
