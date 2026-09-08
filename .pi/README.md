# Pivot 本地 Pi 目录

生成文件默认写在这里，不要写到 C 盘或 `%TEMP%`。

| 路径 | 是否入库 | 用途 |
|---|---|---|
| `settings.json` | 是 | 项目覆盖全局设置（含 `sessionDir`） |
| `handoffs/` | 是 | 会话交接文档 |
| `sessions/` | 否 | Pi 会话 JSONL |
| `artifacts/` | 否 | 其它本地产物 |

无仓库时的全局回退目录：`D:/桌面/AI工程/Pi/`。
