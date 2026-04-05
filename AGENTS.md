# ProxyPoolMaster - AGENTS.md

> 本文档面向 AI 编码助手，帮助快速理解和开发本项目。

## 文档入口

- 项目总览：`README.md`
- 文档导航：`docs/README.md`
- 当前使用指南：`docs/guides/usage-guide.md`
- 当前开发指南：`docs/guides/development-guide.md`
- Collector V2 使用说明：`docs/guides/collector-v2-webui-guide.md`
- 历史资料归档：`docs/archive/`

## 项目概述

ProxyPoolMaster 是一个自动化、免维护的免费代理池系统。它自动收集、检测和维护免费 HTTP/HTTPS 代理，通过 RESTful API、WebSocket 和 Web UI 对外提供能力。

### 核心功能

- **代理收集**：当前内置站大爷大陆与海外收集器，同时支持自定义收集器与 Collector V2。
- **代理检测**：定期检测代理可用性、响应时间、失败次数和评分。
- **代理存储**：使用 Redis 存储代理详情、索引和调度信息。
- **RESTful API**：提供随机获取代理、筛选代理、系统状态和配置相关接口。
- **Web UI**：支持仪表盘、代理列表、日志查看、配置管理、系统状态和 Collector V2 管理。

## 技术栈

### 后端

- Python 3.9+
- FastAPI
- Redis
- Pydantic
- asyncio

### 前端

- Vue.js 3
- TypeScript
- Element Plus
- ECharts
- Pinia
- Vite

### 部署

- Docker + Docker Compose
- Nginx

## 项目结构

```text
.
├── main.py                     # 独立调度进程入口（收集器 / 测试器）
├── src/
│   ├── api/                    # FastAPI 接口定义
│   │   ├── main.py
│   │   ├── endpoints.py
│   │   ├── auth.py
│   │   ├── dashboard_endpoints.py
│   │   ├── system_endpoints.py
│   │   ├── log_endpoints.py
│   │   ├── config_endpoints.py
│   │   ├── collector_v2_endpoints.py
│   │   └── websocket_manager.py
│   ├── collectors/             # 旧版收集器体系
│   │   ├── base_collector.py
│   │   ├── zdaye_collector.py
│   │   ├── zdaye_overseas_collector.py
│   │   ├── dynamic_loader.py
│   │   ├── safe_executor.py
│   │   ├── proxy_validator.py
│   │   └── manager.py
│   ├── collectors_v2/          # Collector V2 运行时、仓储和执行引擎
│   ├── testers/                # 代理测试器体系
│   │   ├── base_tester.py
│   │   ├── async_tester.py
│   │   ├── scoring.py
│   │   └── manager.py
│   ├── database/               # Redis 数据访问
│   ├── middleware/             # API 中间件
│   ├── utils/                  # 工具模块
│   ├── config.py
│   ├── logger.py
│   └── app_globals.py
├── web-ui/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   │   ├── charts/
│   │   │   ├── collectors/
│   │   │   ├── common/
│   │   │   ├── layout/
│   │   │   └── metrics/
│   │   ├── composables/
│   │   ├── router/
│   │   ├── stores/
│   │   ├── styles/
│   │   └── views/
│   └── package.json
├── tests/                      # Python 测试
├── scripts/                    # 一次性维护脚本
├── docs/
│   ├── guides/                 # 当前有效文档
│   └── archive/                # 历史归档
├── docker-compose.yml
├── env.example
└── AGENTS.md
```

## 架构设计

### 前后端分离架构

```text
Browser ──> Nginx(:8080) ──> FastAPI(:8000) ──> Redis(:6379)
                     └────> 静态前端资源
```

### 核心模块关系

- **CollectorManager**：旧版收集器管理器，按周期运行内置或动态收集器。
- **Collector V2 Runtime**：提供配置化收集器、执行引擎、调度器与 Worker。
- **TesterManager**：异步测试代理并维护测试调度。
- **RedisManager**：封装 Redis 操作，维护 Hash / Set / Sorted Set 结构。
- **FastAPI**：提供 REST API、WebSocket 推送和系统状态接口。

### 前端架构

```text
src/
├── api/                 # API 客户端封装
├── components/          # UI 组件
├── composables/         # 组合式函数
├── router/              # 路由配置
├── stores/              # Pinia 状态
├── styles/              # CSS 变量与全局样式
└── views/               # 页面视图
```

当前主要页面：

- `DashboardView.vue`
- `ProxyListView.vue`
- `CollectorManagerView.vue`
- `LogView.vue`
- `ConfigView.vue`
- `SystemStatusView.vue`

## 环境变量配置

项目通过 `.env` 或环境变量配置，模板见 `env.example`。

### 常用配置

```bash
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
API_TOKEN=your_strong_secret_api_token_here

LOG_LEVEL=INFO
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
TIMEZONE=Asia/Shanghai
TESTER_LOG_EACH_PROXY=false

REQUEST_TIMEOUT=10
COLLECT_INTERVAL_SECONDS=300
ZDAYE_COLLECT_INTERVAL=300
ZDAYE_OVERSEAS_COLLECT_INTERVAL=300

TEST_INTERVAL_SECONDS=300
MAX_FAIL_COUNT=5
TEST_MAX_CONCURRENT=100
TEST_TIMEOUT_PER_TARGET=5
TEST_SCHEDULE_ZSET_KEY=proxies:test_schedule
TEST_MIGRATION_BATCH_SIZE=500

API_HOST=0.0.0.0
API_PORT=8000
DASHBOARD_WS_BROADCAST_INTERVAL_SECONDS=10
SYSTEM_WS_BROADCAST_INTERVAL_SECONDS=10
DISABLE_API_TESTER=0
DISABLE_API_COLLECTOR=0

COLLECTOR_RUNTIME_MODE=legacy
COLLECTOR_WORKER_ENABLED=1
COLLECTOR_WORKER_ID=collector-worker-1
```

### Collector 运行模式

- `legacy`：仅启动旧版 `CollectorManager`
- `v2`：启用 Collector V2 Runtime / Worker
- `disabled`：不启动 Collector 调度

## 构建和运行

### Docker Compose 部署

```bash
docker compose up --build -d
```

如需单独启用 Collector V2 Worker：

```bash
docker compose --profile collector-worker up -d
```

访问地址：

- Web UI：`http://localhost:8080`
- Swagger：`http://localhost:8080/docs`
- ReDoc：`http://localhost:8080/redoc`

### 本地开发

```bash
cp env.example .env
pip install -r requirements.txt
docker compose up redis -d
python main.py
python src/api/main.py --reload
```

前端：

```bash
cd web-ui
npm install
npm run dev
```

更完整说明见 `docs/guides/development-guide.md`。

## 运行测试

```bash
python -m unittest discover -s tests -v
python -m unittest tests.test_api -v
python -m unittest tests.test_tester_manager -v
python -m unittest tests.test_migrate_test_schedule -v
```

前端测试：

```bash
cd web-ui
npm run test:unit
npm run test:e2e
```

## API 认证

所有受保护的 API 端点需要在请求头中携带：

```text
X-API-Token: your_strong_secret_api_token_here
```

WebSocket 连接通过 query parameter 传递 token：

```text
ws://localhost:8080/ws/dashboard?token=your_api_token
```

## 代码风格指南

### Python

- 使用 4 空格缩进
- 遵循 PEP 8
- 类名使用 PascalCase
- 函数和变量使用 snake_case
- 注释使用中文

### TypeScript / Vue

- 使用 2 空格缩进
- 保持 TypeScript 类型注解
- 组件名使用 PascalCase
- 组合式函数使用 camelCase

### 日志

- 使用统一的 `setup_logging()`
- 日志主文件固定为 `logs/app.log`
- `TESTER_LOG_EACH_PROXY` 默认关闭，仅在排障时临时开启

## 注意事项

### 循环导入

项目使用 `src/app_globals.py` 管理全局实例，API 模块优先从此处导入全局对象。

### 异步处理

- `CollectorManager` 使用线程处理旧版同步收集任务
- `TesterManager` 使用 asyncio 处理异步检测
- API 端点通过 `asyncio.to_thread()` 包装同步 Redis 操作

### Redis 数据存储

- 代理详情：`proxy:{protocol}:{ip}:{port}`
- 代理索引：`proxies:all`
- 代理评分：`proxies:score`
- 测试调度：`proxies:test_schedule`

### 安全性

- `API_TOKEN` 必须使用强密码
- 非开发环境建议启用 Redis 密码
- 妥善保管 `ZDAYE_APP_ID` 与 `ZDAYE_AKEY`
