# ProxyPoolMaster 本地开发指南

本文档描述当前版本推荐的开发入口、启动方式、运行模式、联调策略和验证命令。面向部署后使用者的说明请看 `docs/guides/usage-guide.md`。

## 相关文档

- 项目总览：`README.md`
- 文档导航：`docs/README.md`
- 使用指引：`docs/guides/usage-guide.md`
- Collector V2 Web UI 教程：`docs/guides/collector-v2-webui-guide.md`
- AI 开发指引：`AGENTS.md`

## 环境准备

1. Python 3.9 及以上
2. Node.js 20 及以上
3. Docker 或本地 Redis
4. 根目录准备好 `.env`

建议从模板生成：

```bash
cp env.example .env
```

至少确认以下配置：

- `API_TOKEN`：本地联调必须有，前端和 WebSocket 都依赖它。
- `REDIS_HOST`：本地开发通常为 `localhost`。
- `COLLECTOR_RUNTIME_MODE`：默认 `v2`，通常保持默认即可；只有回退旧版收集器时才改为 `legacy`。
- `TIMEZONE`：默认 `Asia/Shanghai`，容器和本地日志建议保持一致。
- `ZDAYE_APP_ID` / `ZDAYE_AKEY`：仅在 `legacy` 模式或使用内置站大爷收集器时需要，Collector V2 默认不需要。

补充说明：

- 项目会在首次启动时自动创建运行时配置文件。
- 项目不会因为 `COLLECTORS` 为空而自动写入默认站大爷收集器；无论 `v2` 还是 `legacy`，都应显式维护你要启用的收集器定义。
- 仓库内受 Git 跟踪的只有 `config.default.json`，它用于提供镜像内默认模板。
- `config.json` 是运行时文件，默认不纳入 Git；本地默认路径为项目根目录 `config.json`，容器内默认路径为 `/app/data/config/config.json`。
- 不要把本地 `config.json` 手工复制回仓库，保留它给当前开发实例或容器自行维护。
- 环境变量优先级高于配置文件中的同名配置。

## 启动方式选择

| 场景 | 命令 | 说明 |
| --- | --- | --- |
| 推荐的全量联调 | `./start_dev.sh all` | 启动 Backend、API、Frontend，并自动避免重复调度 |
| 仅后端调度 | `./start_dev.sh backend` | 启动 `main.py`，跑 Collector / Tester |
| 仅 API | `./start_dev.sh api` | 启动 FastAPI 开发服务 |
| 仅前端 | `./start_dev.sh frontend` | 启动 Vite 开发服务 |
| Docker 开发容器 | `docker compose -f docker-compose.dev.yml up -d --build` | 启动 `proxypoolmaster:dev-local`、`app_dev` 和 `collector_worker_dev` |
| 手动启动调度 | `python main.py` | 独立后端调度进程 |
| 手动启动 API | `python src/api/main.py --reload` | FastAPI 开发模式 |
| 单独启动 V2 Worker | `python -m src.collectors_v2.worker_main` | 适合验证 Collector V2 worker 心跳与执行链路 |

### macOS / Linux

```bash
./start_dev.sh all
```

可选模式：

```bash
./start_dev.sh backend
./start_dev.sh api
./start_dev.sh frontend
```

### Windows PowerShell

首次检查环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\test_setup.ps1
```

启动全部服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_dev.ps1
```

可选模式：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_dev.ps1 -Backend
powershell -ExecutionPolicy Bypass -File .\start_dev.ps1 -API
powershell -ExecutionPolicy Bypass -File .\start_dev.ps1 -Frontend
```

## Docker 开发容器

如果你需要直接验证 Dockerfile、Compose、时区注入或独立 `collector-worker` 行为，推荐使用开发容器而不是手动拼装进程。

前置条件：

- 根目录已有 `.env`
- 宿主机 Redis 可访问，默认地址为 `host.docker.internal:6379`
- 如需改 Redis 地址，设置 `DEV_REDIS_HOST` / `DEV_REDIS_PORT`

常用命令：

```bash
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml up -d --build --force-recreate app collector-worker
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs -f app collector-worker
docker compose -f docker-compose.dev.yml down
```

默认访问地址：`http://localhost:18080`

## 推荐联调方式

### 只改前端

```bash
cd web-ui
npm install
npm run dev
```

默认前端开发地址：`http://localhost:5173`

### API + 前端

当你主要在改接口或页面交互时，可以只起 API 和前端：

```bash
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine
export REDIS_HOST=localhost
export API_TOKEN=test
python src/api/main.py --reload
cd web-ui && npm run dev
```

### 完整后端调度 + API + 前端

如果你同时需要 Collector / Tester 调度、API 和前端页面，优先用：

```bash
./start_dev.sh all
```

如果手动启动 `main.py` 和 `src/api/main.py`，建议为 API 进程关闭内置 tester，避免重复检测：

```bash
export DISABLE_API_TESTER=1
python src/api/main.py --reload
```

API 进程已经不再启动 collector；collector 由 `main.py` 或独立 worker 承担。

### Collector V2 联调

Collector V2 是当前默认模式，推荐优先按这条链路开发和验证。

1. 确认运行模式：

```bash
export COLLECTOR_RUNTIME_MODE=v2
```

2. 根据场景选择执行方式：

- Docker：直接运行 `docker compose -f docker-compose.dev.yml up -d`
- 跑独立后端：`python main.py`
- 需要单独验证 Worker：运行 `python -m src.collectors_v2.worker_main`

3. 关键约束：

- API 进程不会再启动 collector task
- Docker 部署里 collector 固定由独立 `collector-worker` 容器承担
- 系统状态页里统一显示为 `Collector`，不再区分 manager / worker

4. 验证 UI：

- 进入“收集器管理”页面，确认顶部 `Collector` 状态正常。
- 先做测试运行，再做发布 / 暂停 / 恢复验证。

## 手动启动步骤

### 1. 启动 Redis

```bash
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine
```

### 2. 启动独立调度进程

```bash
export REDIS_HOST=localhost
export API_TOKEN=test
python main.py
```

### 3. 启动 API

```bash
export REDIS_HOST=localhost
export API_TOKEN=test
python src/api/main.py --reload
```

### 4. 启动前端

```bash
cd web-ui
npm install
npm run dev
```

## 常用访问地址

| 服务 | 地址 |
| --- | --- |
| 前端开发服务 | `http://localhost:5173` |
| API 文档 | `http://localhost:8000/docs` |
| 健康检查 | `http://localhost:8000/health` |
| 仪表盘 WebSocket | `ws://localhost:8000/ws/dashboard?token=test` |
| 日志 WebSocket | `ws://localhost:8000/ws/logs?token=test` |

## Collector 运行模式说明

| 模式 | 行为 |
| --- | --- |
| `legacy` | 使用旧版 `CollectorManager` 跑内置收集器 |
| `v2` | 启用 Collector V2 能力；显式设置后会自动打开 `COLLECTOR_V2_ENABLED`、`COLLECTOR_V2_UI_ENABLED`、`COLLECTOR_V2_MIGRATION_AUTO` |
| `disabled` | 不启动 Collector 调度 |

补充说明：

- `COLLECTOR_WORKER_ENABLED=1` 时，V2 Worker 才会真正启动。
- `main.py` 是“独立调度进程”入口；`src/api/main.py` 是“API 服务”入口。
- API 与 Backend 同时运行时，建议由 Backend 托管调度，API 只提供接口和页面联调。

## 常用验证命令

### 后端回归

```bash
python -m unittest discover -s tests -v
```

### 后端定向验证

```bash
python -m unittest tests.test_api tests.test_tester_manager tests.test_migrate_test_schedule -v
python -m unittest tests.test_async_tester tests.test_tester_baseline tests.test_proxy_availability_filter -v
python -m unittest tests.test_collectors_v2_endpoints tests.test_collectors_v2_scheduler tests.test_collectors_v2_worker_heartbeat -v
```

### 前端验证

```bash
cd web-ui
npm run test:unit
npm run build
```

### 前端定向验证

```bash
cd web-ui
npm run test:unit -- src/views/CollectorManagerView.test.ts
npm run test:unit -- src/views/DashboardView.test.ts
npm run test:unit -- src/views/ProxyListView.test.ts
```

## 一次性维护脚本

补齐代理测试调度索引：

```bash
python scripts/migrate_test_schedule.py --dry-run
python scripts/migrate_test_schedule.py --force
```

检测代理池对真实目标页面的可用性：

```bash
python scripts/check_proxy_pool_availability.py \
  --target-url https://example.com \
  --api-base-url http://127.0.0.1:8000/api/v1 \
  --api-token test \
  --api-rps 1
```

这个脚本适合排查“接口返回可用，但真实目标站点访问成功率不稳”的问题。

## 常用配置

- `REDIS_HOST`：本地开发通常设为 `localhost`
- `API_TOKEN`：前后端联调统一使用同一个 token
- `LOG_LEVEL`：本地排障时可临时设为 `DEBUG`
- `COLLECTOR_RUNTIME_MODE`：决定是 `legacy`、`v2` 还是 `disabled`
- `DISABLE_API_TESTER`：当 `main.py` 与 API 同时运行时，避免 API 重复检测

## 故障排查

### PowerShell 执行策略限制

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Redis 未启动

```bash
docker ps | grep redis
```

### Collector Worker 一直显示离线

优先检查：

1. `COLLECTOR_RUNTIME_MODE` 是否为 `v2`
2. 是否真的启动了 `docker-compose.dev.yml` 里的 `collector-worker`、`main.py`，或独立 `src.collectors_v2.worker_main`
3. 是否能在系统状态页里看到统一的 `Collector` 状态

### 出现重复收集 / 重复测试

优先检查是否同时启动了多套调度链路，例如 `main.py` 和独立 `collector-worker`/`worker_main` 一起运行。

如果是 `main.py` 和 API 同时运行，确保为 API 进程设置了：

```bash
export DISABLE_API_TESTER=1
```

### 401 / Token 校验失败

- 确认前端右上角的 Token 已保存
- 确认请求头使用 `X-API-Token`
- 确认 WebSocket URL 使用 `?token=...`

### 端口占用

macOS / Linux：

```bash
lsof -i :8000
lsof -i :5173
```

Windows：

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

### 日志文件位置

- 主日志：`logs/app.log`
- 详细日志治理说明：`docs/guides/logging-operations.md`
