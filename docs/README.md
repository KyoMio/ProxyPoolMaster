# ProxyPoolMaster 文档导航

当前版本的有效文档统一收敛在这里。建议按角色和场景选择入口，而不是在仓库里逐个翻文件。

## 推荐入口

| 角色 / 场景 | 建议先读 |
| --- | --- |
| 首次接手项目 | `README.md` |
| 部署后通过 Web UI / API 使用系统 | `docs/guides/usage-guide.md` |
| 本地开发、联调、验证 | `README_DEV.md` 或 `docs/guides/development-guide.md` |
| 配置或排障 Collector V2 | `docs/guides/collector-v2-webui-guide.md` |
| 日志轮转、日志排障 | `docs/guides/logging-operations.md` |
| 查看本地归档的历史方案、旧文档和审计材料 | `docs/archive/` |

## 当前有效文档

| 文档 | 用途 |
| --- | --- |
| `README.md` | 项目总览、部署方式、运行模式与常用入口 |
| `README_DEV.md` | 开发者快捷入口 |
| `docs/guides/usage-guide.md` | 面向使用者的 UI / API 使用指引 |
| `docs/guides/development-guide.md` | 本地开发、手动启动、联调和测试命令 |
| `docs/guides/collector-v2-webui-guide.md` | Collector V2 的 Web UI 配置教程 |
| `docs/guides/logging-operations.md` | 日志治理、轮转和排障说明 |
| `AGENTS.md` | 面向 AI 编码助手的项目开发指引 |

## 文档组织方式

- `docs/guides/`
  当前仍适用、可以直接照着操作的文档。
- `docs/archive/`
  本地归档区，用于存放历史设计稿、阶段计划、开发会话、旧草案和审计材料；该目录默认不再纳入 Git 跟踪。

## 阅读建议

1. 先通过 `README.md` 了解系统能力、部署方式和运行模式。
2. 如果你的目标是“把系统用起来”，继续看 `docs/guides/usage-guide.md`。
3. 如果你的目标是“修改代码或本地联调”，继续看 `docs/guides/development-guide.md`。
4. 如果你正在配置 V2 收集器，优先看 `docs/guides/collector-v2-webui-guide.md`。
5. 如果你只是在本地查阅旧设计、审计或归档材料，再进入 `docs/archive/`；这里的内容默认不再进入 Git。
