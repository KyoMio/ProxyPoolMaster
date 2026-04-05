# 日志治理与轮转运维手册

> 当前有效日志文档。日常系统使用说明见 `docs/guides/usage-guide.md`，开发联调说明见 `docs/guides/development-guide.md`。

## 1. 参数说明与推荐值

| 参数 | 默认值 | 推荐值 | 说明 |
| --- | --- | --- | --- |
| `LOG_LEVEL` | `INFO` | 生产 `INFO` / 故障期 `ERROR` | 控制全局日志输出级别 |
| `LOG_MAX_BYTES` | `10485760` | `10485760` (10MB) | 单个日志文件超过该值触发轮转 |
| `LOG_BACKUP_COUNT` | `5` | `5` | 最多保留的历史日志数量 |
| `TESTER_LOG_EACH_PROXY` | `false` | `false` | 是否将逐代理检测结果提升到 `INFO` |

## 2. 日志轮转规则

1. 活跃日志文件默认是 `logs/app.log`。
2. 文件超过 `LOG_MAX_BYTES` 时立即轮转。
3. 并发日志处理器启用时，历史文件为 `app.log.N.gz`。
4. 历史文件数超过 `LOG_BACKUP_COUNT` 后自动清理最旧文件。

## 3. 日常检查命令

```bash
cd /Volumes/Data/projects/ProxyPoolMaster
ls -lah logs
python - <<'PY'
import glob, gzip, os
for f in sorted(glob.glob("logs/app.log*.gz")):
    with gzip.open(f, "rb") as fh:
        raw = fh.read()
    print(f"{f}: compressed={os.path.getsize(f)}, uncompressed={len(raw)}")
PY
```

## 4. 临时排障（逐代理日志）

1. 在环境变量或配置中临时设置：
   - `TESTER_LOG_EACH_PROXY=true`
   - `LOG_LEVEL=INFO`
2. 重启服务并复现问题，观察 `TESTER` 逐代理日志。
3. 排障完成后立即恢复：
   - `TESTER_LOG_EACH_PROXY=false`
   - `LOG_LEVEL` 恢复原生产值（一般 `INFO` 或 `ERROR`）。

## 5. 常见问题

- 日志过多：检查 `TESTER_LOG_EACH_PROXY` 是否被误开。
- 没有轮转：确认 `LOG_MAX_BYTES` 是否过大、日志写入量是否达到阈值。
- 历史文件未压缩：确认 `concurrent-log-handler` 已安装并被启用。
