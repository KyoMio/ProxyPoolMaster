# ProxyPoolMaster Web UI

这是 ProxyPoolMaster 的前端应用，基于 Vue 3、TypeScript、Element Plus 与 Vite。

## 主要页面

- `DashboardView.vue`：仪表盘
- `ProxyListView.vue`：代理列表
- `CollectorManagerView.vue`：Collector V2 管理
- `LogView.vue`：日志查看
- `ConfigView.vue`：配置管理
- `SystemStatusView.vue`：系统状态

## 开发命令

```bash
npm install
npm run dev
```

## 常用脚本

```bash
npm run build
npm run test:unit
npm run test:e2e
npm run lint
```

## 依赖环境

- Node.js 20+
- 推荐与根目录后端服务联调

详细联调方式请查看：

- `../docs/guides/development-guide.md`
- `../README.md`
