# ProxyPoolMaster 开发者快捷入口

这是一个开发入口索引；完整文档请优先以 `docs/README.md` 和 `docs/guides/development-guide.md` 为准。

## 开发文档

| 文档 | 用途 |
| --- | --- |
| `docs/guides/development-guide.md` | 本地开发、运行模式、联调与验证命令 |
| `docs/guides/usage-guide.md` | 部署后系统怎么使用、怎么看页面和 API |
| `docs/guides/collector-v2-webui-guide.md` | Collector V2 Web UI 配置教程 |
| `docs/guides/logging-operations.md` | 日志轮转、排障和日志治理 |
| `AGENTS.md` | AI 编码助手开发约束 |

## Docker 开发容器

适合需要复现正式镜像行为、验证 Dockerfile / compose 变更、或直接使用独立 `collector-worker` 开发链路的场景。

前置准备：

- 根目录准备好 `.env`
- 宿主机准备好 Redis，默认使用 `host.docker.internal:6379`
- 如需改 Redis 地址，使用 `.env` 中的 `DEV_REDIS_HOST` / `DEV_REDIS_PORT`

构建开发镜像：

```bash
docker compose -f docker-compose.dev.yml build
```

启动开发容器：

```bash
docker compose -f docker-compose.dev.yml up -d
```

强制重建当前运行中的 dev 容器：

```bash
docker compose -f docker-compose.dev.yml up -d --build --force-recreate app collector-worker
```

常用命令：

```bash
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs -f app collector-worker
docker compose -f docker-compose.dev.yml down
```

默认信息：

- 镜像：`proxypoolmaster:dev-local`
- 容器：`proxypool_app_dev`、`proxypool_collector_worker_dev`
- 访问地址：`http://localhost:18080`

当前开发容器口径：

- `collector` 固定由独立的 `collector-worker` 容器承担
- `app` 容器不再内嵌启动 collector
- 时区由 `.env` 里的 `TIMEZONE` 控制

## 脚本开发模式

macOS / Linux：

```bash
./start_dev.sh all
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_dev.ps1
```

后端测试：

```bash
python -m unittest discover -s tests -v
```

前端测试：

```bash
cd web-ui
npm run test:unit
```
