# 最小发布修复验证说明

本文档记录当前“最小发布修复”收口时需要确认的边界与验证命令，避免把运行时配置、敏感信息和前端性能修复混在一起理解。

## 这次修复在收什么

1. **配置边界**
   - `config.default.json` 只提供镜像内安全模板。
   - 运行时 `config.json` 由启动脚本按需生成，继续保持 **不入库、不跟踪**。
   - 环境变量优先级高于运行时配置文件。
2. **鉴权边界**
   - `API_TOKEN` 必须来自环境变量或运行时配置。
   - 服务端缺少 token 时应保持 fail-closed，不应依赖硬编码默认密钥继续对外提供受保护接口。
3. **Collector 实时载荷稳定性**
   - 仪表盘 websocket 首帧和 Collector 实时摘要要保持字段稳定，便于前端和测试复用。
4. **前端发布质量**
   - 顶层页面路由按需懒加载，避免把较重页面一次性打进首屏入口包。
   - 任何 lint 例外都需要精确落点，不能靠大范围关闭规则掩盖 `CollectorManagerView` 现有改动。

## 配置文件边界速记

- 本地开发默认运行时配置路径：`./config.json`
- 容器默认运行时配置路径：`/app/data/config/config.json`
- 镜像内模板：`/app/config.default.json`
- 启动入口：`entrypoint.sh`

推荐理解方式：

- **要提交到仓库的**：`env.example`、`config.default.json`、文档、代码
- **只在运行时存在的**：`.env`、`config.json`、容器挂载下的配置内容
- **只通过环境变量传入更安全的**：`API_TOKEN`、`REDIS_PASSWORD`、第三方密钥

## 前端路由收口说明

顶层页面路由只在 `web-ui/src/router/index.ts` 做懒加载切换，不直接改 `CollectorManagerView.vue`，目的是把发布性能修复限定在路由层，避免覆盖正在进行中的视图实现 diff。

## 建议验证命令

### 后端重点回归

```bash
python -m unittest \
  tests.test_auth_query_token \
  tests.test_config_file_path \
  tests.test_collector_realtime_payload \
  tests.test_dashboard_websocket_initial_payload \
  tests.test_collector_route_mounting \
  -v
```

覆盖点：

- token 鉴权与日志脱敏
- `CONFIG_FILE` 路径覆盖
- Collector 实时 payload 字段稳定性
- 仪表盘 websocket 初始 payload
- Collector 路由挂载边界

### 前端重点回归

```bash
cd web-ui
npm run lint
npm run test:unit -- --run
npm run build
```

覆盖点：

- lint 规则没有被宽泛豁免
- 现有视图级测试仍通过
- 生产构建可完成，且页面按路由拆分 chunk

## 合并前最后检查

- `config.json` 仍然未被 Git 跟踪
- 文档明确区分模板配置与运行时配置
- `API_TOKEN` 没有重新引入默认密钥或明文日志
- 前端入口包没有因为同步引入所有页面而重新膨胀
