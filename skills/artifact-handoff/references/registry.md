# Registry format and examples

`.artifact-handoff.json` uses schema version 1 and an `artifacts` array. Each registration is a snapshot:

| Field | Meaning |
| --- | --- |
| id | Generated artifact identifier |
| path | Root-relative file path; absolute paths and traversal are rejected |
| sha256 | Content hash at registration time |
| bytes | File size |
| role | source / export / asset / other, explicitly supplied |
| status | draft / final, explicitly supplied; default draft |
| parent | Optional existing artifact ID; checked before registering |
| note | Human-supplied change or selection reason |
| recorded_at | UTC timestamp |

An export can have its editable source as its parent, or a revised artifact can have a prior version as its parent. Explain which relationship is intended in `note`. Version 1 supports one parent per record; do not claim a complete multi-input dependency graph.

The delivery manifest retains selected records and adds `packaged_path`. Files go in `files/<id>/<filename>` so equal basenames do not collide. Ancestors are validated but not automatically copied. Parent IDs may refer to history outside the package; the manifest is a delivery inventory, not the complete registry.

## Example requests

“找出所有完全重复文件，但不要删除”：run `scan`, report duplicate groups, do not register finality or create packages.

“我选 poster-v2.png 为最终版，连同 editable.svg 交付”：register the source and export with explicit roles; record the relationship if known; select both IDs and require source plus export.

“这是最终最终3.png，应该是最新版吧”：scan and inspect known provenance. A filename is insufficient evidence. If current context does not establish the approved version, ask for the actual selection.

“把已登记的最终版打包”，但文件后来被覆盖：report hash mismatch; recover the old file or register the current file after confirming its status. Do not silently update old hashes.
