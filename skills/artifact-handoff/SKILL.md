---
name: artifact-handoff
description: Track versions and provenance of AI-generated files and assemble verified delivery folders with manifests and previews. Use for confusing draft/final versions, editable-source and export relationships, or incomplete deliverables. Do not use for generic disk cleanup or infer final versions from filenames.
---

# Artifact Handoff

把 AI 生成的图片、文档、演示、网页等文件整理为可追溯的交付包。Python 3.10+；脚本仅使用标准库。本技能不生成内容、不移动或删除源文件。

## 何时使用

- “这个目录版本太多，帮我确认哪些可以交付。”
- “记录这次修改与上一个版本的关系。”
- “把最终图片和可编辑源文件一起打包，生成预览和清单。”

## 工作方式

1. 确定源目录、交付目标目录和本次需要的角色：`source` 可编辑源文件、`export` 导出件、`asset` 附属素材、`other` 其他文件。读取已有登记；扫描结果包含文件 SHA-256、完全重复组和已登记版本的健康状态。
2. 文件名、修改时间、扩展名仅作为线索。完全相同的哈希证明内容重复，不能证明哪个被批准。无登记文件的角色、最终状态、版本关系都视为未知。利用当前对话明确选择；若确实无法确定最终文件，再询问用户。不要逐项询问已有明确依据的信息。
3. 对明确的文件登记角色和状态；对已知父版本登记 `--parent`。只有用户明确选定，或当前任务已明确授权交付该文件，才标记 `final`。记录简短修改说明，不编造生成工具或提示词。
4. 打包时显式列出 ID 和本次必需的角色。脚本校验所选文件及父版本哈希，缺失、改动或缺少必需角色时停止。先解释证据，再修复或重新登记。父版本属于历史，不会自动加入交付包；需要时显式选择。
5. 打开交付目录的 `index.html`，检查链接、图片预览和中文文件名；核对 `manifest.json`。报告重复组、最终选择依据、交付文件数及未确认事项。

## 调用脚本

将下面 `<skill-dir>` 替换为此 SKILL.md 所在目录；按宿主环境使用 `python` 或 `python3`。路径含空格时加引号。

```text
python "<skill-dir>/scripts/artifacts.py" scan --root "<source-dir>"
python "<skill-dir>/scripts/artifacts.py" register --root "<source-dir>" --file "poster-v1.png" --role export --note "首次生成"
python "<skill-dir>/scripts/artifacts.py" register --root "<source-dir>" --file "poster-v2.png" --role export --parent <v1-id> --status final --note "用户选定的交付版本"
python "<skill-dir>/scripts/artifacts.py" package --root "<source-dir>" --ids <source-id> <final-id> --out "<delivery-dir>" --require-role source --require-role export
```

`register` 返回新 ID。不要把示例占位符当作真实 ID。注册表保存在源目录 `.artifact-handoff.json`。`scan` 只读，`register` 更新注册表，`package` 创建全新目录且保留源文件。

## 约束和实际边界

- 首先遵循用户的保存位置约定。输出目录必须位于源目录外且尚不存在。
- 默认只交付显式选定的文件，不把整个目录、秘密、日志或注册表一起上传。用户要求 GitHub 发布技能，不等于授权上传用户业务文件。
- 本工具记录人工/智能体提供的版本关系；不会从外观自动推断亲缘关系，不支持感知相似度。
- 只检测指定角色是否齐全；不能自动发现 PPT 内部缺失字体、链接素材或网页依赖。需要时使用对应文档/网页工具检查并明确报告检查范围。
- 已登记文件被原地改动会使旧记录失效。推荐每个版本保存为不同路径；保留旧文件后登记新版本。
- 符号链接、Windows junction/reparse point 不支持。注册表写入使用原子替换；并发注册不支持，应顺序执行。
- HTML 预览对常见光栅图片显示缩略图，其他格式提供文件链接。预览含文件名和登记备注，保留在授权的本地交付范围。

详细字段与示例见 [references/registry.md](references/registry.md)。
