# ProxyPoolMaster 使用指引

> 面向已经完成部署、准备通过 Web UI / API 使用系统的用户。开发联调请看 `docs/guides/development-guide.md`。

## 适用对象

- 想通过 Web UI 查看代理池状态和日志的运维人员
- 需要通过 API 获取代理的调用方
- 需要在页面中配置或排查 Collector V2 的使用者

## 默认访问地址

Docker 默认对外地址：

- Web UI：`http://localhost:8080`
- Swagger：`http://localhost:8080/docs`
- ReDoc：`http://localhost:8080/redoc`
- 健康检查：`http://localhost:8080/health`

本地前端开发模式常见地址：

- Web UI：`http://localhost:5173`
- API：`http://localhost:8000`

## 首次使用

### 1. 准备 API Token

系统的 Web UI、REST API 和 WebSocket 都需要认证。

- REST API 请求头：`X-API-Token: your_token`
- WebSocket：`ws://host/ws/dashboard?token=your_token`

Web UI 中可以通过右上角锁形按钮打开 Token 设置弹窗。保存后页面会刷新，以便后续接口自动带上 Token。

### 2. 检查服务是否正常

浏览器访问：

- `http://localhost:8080/health`
- `http://localhost:8080/docs`

如果健康检查不通过，优先检查 Redis、API Token 和日志文件 `logs/app.log`。

### 3. 打开系统状态页确认模块

建议先进入“系统状态”页面确认：

- Redis 是否在线
- API 是否正常
- 当前 Collector 运行模式是否符合预期
- Collector Worker 在 V2 模式下是否在线

## 页面说明

| 页面 | 用途 |
| --- | --- |
| 仪表盘 | 查看总代理数、可用代理数、平均响应和实时概览 |
| 代理列表 | 按协议、国家、匿名度等条件筛选代理 |
| 收集器管理 | 管理 Collector V2，执行测试运行、发布、暂停、恢复 |
| 日志查看 | 过滤日志级别、组件、关键字、`collector_id` 和 `run_id` |
| 配置管理 | 查看和更新系统配置 |
| 系统状态 | 查看模块运行状态、运行模式和系统指标 |

## 常见使用流程

### 获取随机代理

```bash
curl -H "X-API-Token: your_token" \
  http://localhost:8080/api/v1/random
```

### 获取带筛选条件的代理

```bash
curl -H "X-API-Token: your_token" \
  "http://localhost:8080/api/v1/get?protocol=https&country_code=CN&size=20"
```

### 查看仪表盘与实时状态

- 打开“仪表盘”页面看概览卡片和图表
- 右上角连接状态指示灯显示 WebSocket 是否正常
- 如果连接断开，可以点击状态指示器重连

### 查看日志

日志页适合排查：

- 指定组件报错
- 某次 Collector 测试运行失败
- 某个 `run_id` 的完整执行过程

推荐筛选方式：

- 按 `component` 看模块日志
- 按 `collector_id` 看某个收集器
- 按 `run_id` 看某次运行
- 按 `keyword` 搜错误关键字

### 修改配置

配置页适合修改全局参数，例如：

- 日志级别
- Tester 并发与批处理参数
- Collector 运行模式相关配置

注意：

- 某些配置可以运行时生效
- 某些配置会提示需要重启
- 环境变量会覆盖同名文件配置

### 配置 Collector V2

如果你的目标是新增或调整 V2 收集器，请直接阅读：

`docs/guides/collector-v2-webui-guide.md`

建议流程始终保持为：

1. 新建 / 编辑
2. 保存
3. 测试运行
4. 查看结果
5. 发布
6. 后续按需暂停 / 恢复

## API 与 WebSocket

### 常用 REST API

| 接口 | 说明 |
| --- | --- |
| `GET /api/v1/random` | 获取随机代理 |
| `GET /api/v1/get` | 按条件筛选代理 |
| `GET /api/v1/dashboard/overview` | 获取仪表盘概览 |
| `GET /api/v1/system/status` | 获取系统整体状态 |
| `GET /api/v1/logs` | 查询日志 |
| `GET /health` | 健康检查 |

### WebSocket 地址

| 地址 | 用途 |
| --- | --- |
| `ws://host/ws/dashboard?token=...` | 仪表盘概览与 Collector 实时更新 |
| `ws://host/ws/logs?token=...` | 日志实时流 |

## 常见问题

### Web UI 提示 401

说明 Token 缺失或不正确。请重新打开右上角 Token 设置弹窗保存一次，或检查后端 `.env` 里的 `API_TOKEN`。

### 页面没有数据

优先检查：

1. Redis 是否正常
2. 是否已经有 Collector / Tester 在工作
3. 当前是否把 Collector 运行模式设成了 `disabled`
4. 日志中是否有接口或调度错误

### Collector Worker 显示离线

一般说明当前没有有效的 V2 Worker 在上报心跳。请检查：

- `COLLECTOR_RUNTIME_MODE` 是否为 `v2`
- `COLLECTOR_WORKER_ENABLED` 是否为 `1`
- 是否启动了 API 内置 worker、`main.py`，或独立 `python -m src.collectors_v2.worker_main`

### 我只想通过 UI 使用，不想看开发文档

优先阅读顺序：

1. `README.md`
2. `docs/guides/usage-guide.md`
3. `docs/guides/collector-v2-webui-guide.md`

## 继续阅读

- 部署与运行模式：`README.md`
- 本地开发与联调：`docs/guides/development-guide.md`
- Collector V2 详细配置：`docs/guides/collector-v2-webui-guide.md`
- 日志轮转与日志排障：`docs/guides/logging-operations.md`
