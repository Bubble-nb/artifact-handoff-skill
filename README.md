# Artifact Handoff Skill

**公开仓库 / Public repository · MIT License · Python 3.10+ · 零第三方运行依赖**

面向 Codex、Claude 等支持 `SKILL.md` 的智能体：追踪 AI 生成文件的版本关系，明确最终版本，整理可校验的交付目录。

不是根据“最终最终2.png”猜哪个版本最好。每次登记保存文件哈希、角色、状态和可选父版本；交付前再次验算哈希。

## 能做什么

- 扫描目录，按 SHA-256 发现完全重复文件，报告失效的版本记录。
- 显式记录源文件、导出件、素材，以及 draft / final 状态。
- 记录前后版本或源文件到导出件的关联与修改说明。
- 检查必需角色是否齐全，阻止已改动或缺失文件进入交付包。
- 保留源文件，为选定文件创建新目录，生成 `manifest.json` 和离线 `index.html` 预览。

## 安装

下载或克隆这个仓库，将 `skills/artifact-handoff` 文件夹放入智能体的技能目录。例如 Codex 的 `~/.codex/skills/` 或 Claude Code 的 `~/.claude/skills/`。不需要安装 Python 包；已有 Python 3.10+ 即可。

如果 C 盘空间紧张，可以把仓库存到 D 盘，再按你的智能体配置引用技能目录。不要为了安装覆盖已有同名技能。

## 对智能体说

> 使用 $artifact-handoff 检查这个目录里的重复文件和版本记录。我选海报第二版作为最终交付，连同源文件整理到一个新目录，并生成预览和清单。

## 独立命令行使用

以下是 Windows 示例。macOS / Linux 使用 `python3` 和对应路径。`<source-id>`、`<export-id>` 必须替换成 register 命令返回的 ID。

```powershell
python skills/artifact-handoff/scripts/artifacts.py scan --root "D:\Work\poster"
python skills/artifact-handoff/scripts/artifacts.py register --root "D:\Work\poster" --file "editable.svg" --role source
python skills/artifact-handoff/scripts/artifacts.py register --root "D:\Work\poster" --file "poster-v2.png" --role export --parent <source-id> --status final --note "用户确认交付版本"
python skills/artifact-handoff/scripts/artifacts.py package --root "D:\Work\poster" --ids <source-id> <export-id> --out "D:\Deliveries\poster-01" --require-role source --require-role export
```

## 交付结构

```text
poster-01/
  index.html
  manifest.json
  files/
    <source-id>/editable.svg
    <export-id>/poster-v2.png
```

文件按 ID 分目录，避免同名覆盖。HTML 对 PNG/JPEG/GIF/WebP 显示预览，其他格式给出链接。注册表留在源目录，不自动公开。发布这个技能仓库不会上传你的工作文件。

## 边界

- 只做字节级重复检测；不支持感知相似度，也不能凭外观推断版本关系。
- final 必须明确登记，文件名和修改时间不会自动获得最终状态。
- 必需角色由本次任务指定。不会自动解析 PPT 字体、文档内容或网页依赖。
- 单父节点版本关系；父版本会被验证，但不会自动加入交付包。
- 原地覆盖文件会使旧哈希失效。请把不同版本保存到不同路径。
- 不支持符号链接、junction/reparse point 或并发登记。扫描结果含相对文件名，公开分享前应核对内容。

## 验证

先运行一个不含个人数据的完整示例（输出目录必须尚不存在）：

```powershell
python examples/demo.py --out "D:\Codex_Output\artifact-handoff-demo"
```

示例创建源 SVG、导出 PNG 及完全重复副本，登记版本关系，生成交付目录。打开输出目录下 `delivery/index.html` 查看结果。示例数据仅用于展示流程。

```text
python -m unittest discover -s tests -v
```

测试覆盖重复文件、未知最终状态、文件改动、父版本失效、缺少源文件、中文文件名、HTML 转义、路径越界、输出覆盖保护和同名文件。GitHub Actions 在 Windows / Linux、Python 3.10 / 3.12 上运行同一套测试。

## English

A portable agent skill for explicit AI artifact provenance and verified handoff packages. Uses content hashes rather than filenames to track registered snapshots. Supports exact duplicate detection, user-selected finality, single-parent lineage, required delivery roles, and local HTML previews. Source files are never moved or deleted. Runtime is Python standard library only.
