# ProxyPoolMaster

ProxyPoolMaster 是一个面向免费 HTTP/HTTPS 代理的自动化代理池系统，负责收集、检测、存储和对外提供代理能力，并附带 Web UI、REST API 与 WebSocket 实时接口。

**注意**：该项目为vibe-coding产物，由于个人水平有限，难免会有没有注意到的问题，但主要功能已完全可用，尚在不断地打磨优化。

当前版本的默认运行方式是：

- `app`：提供 Web UI、REST API、WebSocket
- `collector-worker`：独立执行 Collector V2 收集任务
- `redis`：保存代理数据、调度索引和运行状态

如果你想先把系统跑起来，看“快速开始”；如果你准备改代码，看“本地开发”；如果你想了解当前质量问题，看“审计与已知问题”。

## 项目特性

- 自动收集免费代理，内置站大爷大陆与海外收集器
- 支持 Collector V2，可通过 Web UI 配置、测试、发布与暂停收集器
- 异步检测代理质量，维护可用性、响应时间、失败次数和评分
- 使用 Redis 存储代理详情、索引、测试调度和部分运行状态
- 提供 REST API、Swagger / ReDoc 文档与 WebSocket 推送
- 提供 Vue 3 Web UI，覆盖仪表盘、代理列表、日志、配置和系统状态

## 架构概览

```text
Browser
  └─> Nginx :8080
       ├─> Web UI 静态资源
       ├─> FastAPI :8000
       │    ├─> REST API
       │    ├─> WebSocket
       │    └─> Tester
       └─> Redis :6379

Collector Worker
  └─> Collector V2 Runtime
       └─> Redis
```

核心模块说明：

- `main.py`：独立调度进程入口，主要用于本地开发或手动运行 Collector / Tester
- `src/api/`：FastAPI 接口、WebSocket、系统状态、日志与配置管理
- `src/collectors/`：旧版收集器体系
- `src/collectors_v2/`：Collector V2 运行时、仓储、调度与执行引擎
- `src/testers/`：异步代理测试器与评分逻辑
- `web-ui/`：Vue 3 + TypeScript 前端

## 适用场景与边界

适合：

- 需要搭建一个可自托管的免费代理池
- 需要通过页面或 API 查看代理状态、日志和系统运行情况
- 需要以“可配置收集器”的方式扩展代理来源

不适合：

- 对稳定性、合规性、匿名性有强保证要求的生产流量场景
- 把“免费代理”当作高可用基础设施直接依赖

**免费代理天然不稳定，项目目标是“自动化维护和可观测”，不是“保证任何代理一定可用”。**
**使用代理时推荐与本项目在同一网络环境下，避免代理可用性出现较大偏差。**

## 快速开始

### 1. 准备配置

```bash
cp env.example .env
```

说明：

- `.env` 用于环境变量配置
- 项目会在首次启动时自动创建运行时配置文件
- 仓库内提供受 Git 跟踪的 `config.default.json` 作为镜像内默认模板
- `config.json` 是运行时生成文件，默认被 Git 忽略；本地默认路径为仓库根目录 `config.json`
- 容器默认把运行时配置持久化到 `/app/data/config/config.json`，请保留该文件给运行中的实例自行维护

建议至少检查这些变量：

- `API_TOKEN`：必填；若未配置，服务会直接拒绝 API / WebSocket 访问（fail closed）
- `COLLECTOR_RUNTIME_MODE`：默认 `v2`
- `TIMEZONE`：默认 `Asia/Shanghai`
- `ZDAYE_APP_ID` / `ZDAYE_AKEY`：仅在 `legacy` 模式或启用内置站大爷收集器时需要，Collector V2 默认不需要
- `APP_IMAGE_TAG`：可选，侧边栏版本号优先显示它；CI/CD 自动构建时建议由工作流注入

### 2. 启动服务

```bash
docker compose up -d --build
```

常用命令：

```bash
docker compose ps
docker compose logs -f app collector-worker
docker compose down
```

### 3. 访问系统

- Web UI: [http://localhost:8080](http://localhost:8080)
- Swagger: [http://localhost:8080/docs](http://localhost:8080/docs)
- ReDoc: [http://localhost:8080/redoc](http://localhost:8080/redoc)
- Health: [http://localhost:8080/health](http://localhost:8080/health)

### 4. 首次使用建议

1. 打开 Web UI，先设置 `API_TOKEN`
2. 进入“系统状态”页，确认 Redis、API、Collector 状态正常
3. 进入“收集器管理”页，确认 Collector V2 Worker 在线
4. 如果这是首次部署，请先手动创建并测试至少一个收集器；系统不会自动内置默认站大爷收集器
5. 等待收集和检测完成后，再到“代理列表”或 API 验证数据

## 收集器配置指引

如果你准备通过 Web UI 新增或调整收集器，建议按下面顺序操作：

1. 先确认 `COLLECTOR_RUNTIME_MODE=v2`，并且“系统状态”页里 Collector Worker 在线
2. 进入“收集器管理”页，新建或编辑收集器；首次部署时需要手动完成这一步
3. 先保存配置，再执行一次“测试运行”
4. 查看测试结果、错误摘要和运行日志
5. 确认结果正常后再点击“发布”

README 里只保留快速入口，详细表单说明、JSONPath / CSS / XPath 示例、分页配置和站大爷实战示例请直接看：

- [Collector V2 Web UI 配置教程](docs/guides/collector-v2-webui-guide.md)
- [日常使用指引](docs/guides/usage-guide.md#配置-collector-v2)

## Collector 运行模式

| 模式 | 说明 |
| --- | --- |
| `legacy` | 启用旧版 `CollectorManager` |
| `v2` | 启用 Collector V2 运行时与独立 Worker |
| `disabled` | 不启动任何 Collector 调度 |

当前推荐模式是 `v2`。

## 本地开发

### 环境要求

- Python 3.9+
- Node.js 20+
- Docker 或本地 Redis

### 常用开发入口

macOS / Linux：

```bash
./start_dev.sh all
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_dev.ps1
```

### 手动启动

先启动 Redis：

```bash
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine
```

再启动后端调度和 API：

```bash
export REDIS_HOST=localhost
export API_TOKEN=test
python main.py
python src/api/main.py --reload
```

前端：

```bash
cd web-ui
npm install
npm run dev
```

如果 `main.py` 和 `src/api/main.py` 同时运行，建议为 API 进程关闭内置 tester，避免重复检测：

```bash
export DISABLE_API_TESTER=1
```

更多细节请看 [docs/guides/development-guide.md](docs/guides/development-guide.md)。

## API 与 WebSocket

### REST API

| 接口 | 说明 |
| --- | --- |
| `GET /api/v1/random` | 获取一个随机可用代理 |
| `GET /api/v1/get` | 按条件筛选代理 |
| `GET /api/v1/dashboard/overview` | 获取仪表盘概览 |
| `GET /api/v1/system/status` | 获取系统状态 |
| `GET /api/v1/logs` | 查询日志 |
| `GET /health` | 健康检查 |

### 认证方式

- HTTP Header：`X-API-Token: your_token`
- WebSocket：`ws://host/ws/dashboard?token=your_token`

### WebSocket 地址

| 地址 | 说明 |
| --- | --- |
| `ws://host/ws/dashboard?token=...` | 仪表盘与 Collector 实时更新 |
| `ws://host/ws/logs?token=...` | 日志实时流 |

## 测试与验证

后端：

```bash
python -m unittest discover -s tests -v
```

前端：

```bash
cd web-ui
npm run test:unit
npm run build
```

## 目录结构

```text
.
├── main.py
├── src/
│   ├── api/
│   ├── collectors/
│   ├── collectors_v2/
│   ├── database/
│   ├── middleware/
│   ├── testers/
│   └── utils/
├── web-ui/
├── tests/
├── scripts/
├── docs/
│   ├── guides/
│   └── archive/
├── docker-compose.yml
├── docker-compose.dev.yml
├── env.example
└── AGENTS.md
```

## 文档导航

| 文档 | 用途 |
| --- | --- |
| [docs/README.md](docs/README.md) | 文档总入口 |
| [docs/guides/usage-guide.md](docs/guides/usage-guide.md) | 部署后使用说明 |
| [docs/guides/development-guide.md](docs/guides/development-guide.md) | 本地开发与联调 |
| [docs/guides/collector-v2-webui-guide.md](docs/guides/collector-v2-webui-guide.md) | Collector V2 Web UI 教程 |
| [docs/guides/logging-operations.md](docs/guides/logging-operations.md) | 日志治理与排障 |
| [README_DEV.md](README_DEV.md) | 开发者快捷入口 |

## License

本项目使用 [MIT License](LICENSE)。
