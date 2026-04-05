"""
异步 HTTP 代理测试器
使用 aiohttp 实现纯异步、多目标并发测试
支持 HTTP/HTTPS/SOCKS4/SOCKS5 代理
"""

import asyncio
import aiohttp
import time
from typing import Dict, List, Optional, Set
import logging

try:
    from aiohttp_socks import ProxyConnector, ProxyType
    SOCKS_SUPPORT = True
except ImportError:
    SOCKS_SUPPORT = False

from src.testers.base_tester import BaseTester
from src.testers.scoring import ProxyScorer, TargetResult, MultiTargetTestResult
from src.testers.baseline import (
    BaselineFingerprint,
    ResponseSnapshot,
    build_baseline_fingerprint,
    evaluate_response_success,
    extract_title,
    normalize_content_type,
)
from src.config import Config

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36 ProxyPoolMasterTester/1.0"
)
DEFAULT_BASELINE_RUNS = 3
DEFAULT_BASELINE_LENGTH_TOLERANCE = 0.35
DEFAULT_BASELINE_MIN_KEYWORD_HITS = 1


class AsyncHttpTester(BaseTester):
    """
    异步 HTTP 代理测试器
    同时向多个目标发送请求，支持连接池复用
    支持 HTTP/HTTPS/SOCKS4/SOCKS5 代理
    """

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.scorer = ProxyScorer(logger)

        # 配置参数
        self.timeout = aiohttp.ClientTimeout(total=self._read_int_config("TEST_TIMEOUT_PER_TARGET", 5))
        self.targets = self._read_targets_config()
        self.verify_tls = True
        self.baseline_runs = self._read_int_config("TEST_BASELINE_RUNS", DEFAULT_BASELINE_RUNS)
        self.baseline_length_tolerance = self._read_float_config(
            "TEST_BASELINE_LENGTH_TOLERANCE",
            DEFAULT_BASELINE_LENGTH_TOLERANCE,
        )
        self.baseline_min_keyword_hits = max(
            1,
            self._read_int_config("TEST_BASELINE_MIN_KEYWORD_HITS", DEFAULT_BASELINE_MIN_KEYWORD_HITS),
        )
        self.default_headers = {"User-Agent": DEFAULT_USER_AGENT}
        self._target_baselines: Dict[str, BaselineFingerprint] = {}
        self._unhealthy_targets: Set[str] = set()
        self._baseline_lock = asyncio.Lock()

        # 创建连接池（用于 HTTP 代理）
        self.connector = aiohttp.TCPConnector(
            limit=100,  # 总连接数限制
            limit_per_host=30,  # 每个主机连接数限制
            enable_cleanup_closed=True,
            force_close=True  # 测试完成后关闭连接，避免代理混淆
        )

        if not SOCKS_SUPPORT:
            logger.warning("aiohttp-socks not installed, SOCKS proxies will not be tested properly")

        self.logger.debug(f"AsyncHttpTester initialized with {len(self.targets)} targets")
        self.logger.debug(f"Targets: {self.targets}")
        self.logger.debug(f"SOCKS support: {SOCKS_SUPPORT}")

    def _read_int_config(self, key: str, default: int) -> int:
        value = getattr(self.config, key, default)
        try:
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float, str)):
                return int(value)
        except (TypeError, ValueError):
            pass
        return default

    def _read_float_config(self, key: str, default: float) -> float:
        value = getattr(self.config, key, default)
        try:
            if isinstance(value, (int, float, str)):
                return float(value)
        except (TypeError, ValueError):
            pass
        return default

    def _read_targets_config(self) -> List[str]:
        raw_targets = getattr(self.config, "TEST_TARGETS", [])
        if isinstance(raw_targets, list):
            return [target for target in raw_targets if isinstance(target, str) and target]
        return []

    def _reset_baseline_cache(self) -> None:
        self._target_baselines = {}
        self._unhealthy_targets = set()

    def _build_request_kwargs(self, target: str, proxy_url: Optional[str]) -> Dict[str, object]:
        request_kwargs: Dict[str, object] = {
            "timeout": self.timeout,
            "allow_redirects": True,
        }
        if proxy_url:
            request_kwargs["proxy"] = proxy_url
        if target.lower().startswith("https://"):
            request_kwargs["ssl"] = self.verify_tls
        return request_kwargs

    def _should_extract_text(self, content_type: str) -> bool:
        normalized = normalize_content_type(content_type)
        return (
            normalized.startswith("text/")
            or normalized.endswith("json")
            or normalized.endswith("xml")
            or "html" in normalized
        )

    def _decode_text(self, body: bytes, charset: Optional[str]) -> str:
        encoding = charset or "utf-8"
        try:
            return body.decode(encoding, errors="ignore")
        except LookupError:
            return body.decode("utf-8", errors="ignore")

    async def _build_response_snapshot(self, response: aiohttp.ClientResponse) -> ResponseSnapshot:
        body = await response.read()
        content_type = response.headers.get("Content-Type", "")
        text = self._decode_text(body, getattr(response, "charset", None)) if self._should_extract_text(content_type) else ""
        return ResponseSnapshot(
            status_code=response.status,
            final_url=str(response.url),
            content_type=content_type,
            body_length=len(body),
            text_length=len(text),
            title=extract_title(text),
            text=text,
        )

    async def _fetch_response_snapshot(
        self,
        session: aiohttp.ClientSession,
        target: str,
        proxy_url: Optional[str] = None,
    ) -> ResponseSnapshot:
        async with session.get(target, **self._build_request_kwargs(target, proxy_url)) as response:
            return await self._build_response_snapshot(response)

    async def _build_target_baseline(
        self,
        session: aiohttp.ClientSession,
        target: str,
    ) -> Optional[BaselineFingerprint]:
        samples: List[ResponseSnapshot] = []

        for _ in range(max(1, self.baseline_runs)):
            try:
                samples.append(await self._fetch_response_snapshot(session, target))
            except asyncio.TimeoutError:
                self.logger.debug(f"Baseline timeout for target {target}")
            except aiohttp.ClientError as exc:
                self.logger.debug(f"Baseline client error for target {target}: {exc}")
            except Exception as exc:
                self.logger.debug(f"Baseline unexpected error for target {target}: {exc}")

        if not samples:
            return None

        try:
            return build_baseline_fingerprint(samples)
        except Exception as exc:
            self.logger.warning(f"Failed to build baseline for target {target}: {exc}")
            return None

    async def _ensure_target_baselines(self) -> None:
        if len(self._target_baselines) + len(self._unhealthy_targets) >= len(self.targets):
            return

        async with self._baseline_lock:
            if len(self._target_baselines) + len(self._unhealthy_targets) >= len(self.targets):
                return

            built_baselines: Dict[str, BaselineFingerprint] = {}
            unhealthy_targets: Set[str] = set()

            async with aiohttp.ClientSession(headers=self.default_headers) as session:
                for target in self.targets:
                    baseline = await self._build_target_baseline(session, target)
                    if baseline is None:
                        unhealthy_targets.add(target)
                        continue
                    built_baselines[target] = baseline

            self._target_baselines = built_baselines
            self._unhealthy_targets = unhealthy_targets

            if unhealthy_targets:
                self.logger.warning(
                    f"Skipped {len(unhealthy_targets)} unhealthy test targets during baseline build: "
                    f"{sorted(unhealthy_targets)}"
                )

    def apply_runtime_config(self, updated_keys: List[str]) -> List[str]:
        applied_keys: List[str] = []
        should_reset_baseline = False

        if "TEST_TIMEOUT_PER_TARGET" in updated_keys:
            self.timeout = aiohttp.ClientTimeout(total=self._read_int_config("TEST_TIMEOUT_PER_TARGET", 5))
            applied_keys.append("TEST_TIMEOUT_PER_TARGET")
            should_reset_baseline = True

        if "TEST_TARGETS" in updated_keys:
            self.targets = self._read_targets_config()
            applied_keys.append("TEST_TARGETS")
            should_reset_baseline = True

        if should_reset_baseline:
            self._reset_baseline_cache()

        return applied_keys

    def _get_proxy_connector(self, proxy_protocol: str, proxy_ip: str, proxy_port: int):
        """
        根据代理协议创建合适的 connector
        """
        protocol = proxy_protocol.lower()

        if protocol in ('http', 'https'):
            # HTTP/HTTPS 代理使用普通 connector，通过 proxy 参数指定
            return None, f"{protocol}://{proxy_ip}:{proxy_port}"

        elif protocol == 'socks4' and SOCKS_SUPPORT:
            # SOCKS4 代理
            connector = ProxyConnector(
                proxy_type=ProxyType.SOCKS4,
                host=proxy_ip,
                port=proxy_port,
                limit=10,
                enable_cleanup_closed=True,
                force_close=True
            )
            return connector, None

        elif protocol in ('socks5', 'socks5h') and SOCKS_SUPPORT:
            # SOCKS5 代理
            connector = ProxyConnector(
                proxy_type=ProxyType.SOCKS5,
                host=proxy_ip,
                port=proxy_port,
                limit=10,
                enable_cleanup_closed=True,
                force_close=True
            )
            return connector, None

        else:
            # 不支持的协议或缺少依赖
            if protocol in ('socks4', 'socks5', 'socks5h') and not SOCKS_SUPPORT:
                self.logger.warning(f"SOCKS proxy {proxy_ip}:{proxy_port} skipped - aiohttp-socks not installed")
            else:
                self.logger.warning(f"Unsupported proxy protocol: {protocol}")
            return None, None

    async def _test_single_target_with_session(
        self,
        session: aiohttp.ClientSession,
        target: str,
        proxy_url: Optional[str]
    ) -> TargetResult:
        """使用已有 session 测试单个目标"""
        baseline = self._target_baselines.get(target)
        if baseline is None:
            return TargetResult(
                target=target,
                success=False,
                response_time=0,
                error="Baseline unavailable"
            )

        start_time = time.time()

        try:
            snapshot = await self._fetch_response_snapshot(session, target, proxy_url)
            response_time = time.time() - start_time
            evaluation = evaluate_response_success(
                snapshot,
                baseline,
                length_tolerance=self.baseline_length_tolerance,
                min_keyword_hits=self.baseline_min_keyword_hits,
            )
            if evaluation.is_success:
                return TargetResult(
                    target=target,
                    success=True,
                    response_time=response_time,
                    status_code=snapshot.status_code,
                )
            return TargetResult(
                target=target,
                success=False,
                response_time=response_time,
                status_code=snapshot.status_code,
                error="Validation failed: " + ", ".join(evaluation.reasons),
            )

        except asyncio.TimeoutError:
            return TargetResult(
                target=target,
                success=False,
                response_time=time.time() - start_time,
                error="Timeout"
            )
        except aiohttp.ClientProxyConnectionError as e:
            return TargetResult(
                target=target,
                success=False,
                response_time=time.time() - start_time,
                error=f"Proxy connection error: {e}"
            )
        except aiohttp.ClientError as e:
            return TargetResult(
                target=target,
                success=False,
                response_time=time.time() - start_time,
                error=f"Client error: {e}"
            )
        except Exception as e:
            return TargetResult(
                target=target,
                success=False,
                response_time=time.time() - start_time,
                error=f"Unexpected error: {e}"
            )

    async def _test_single_target(
        self,
        session: aiohttp.ClientSession,
        target: str,
        proxy_ip: str,
        proxy_port: int,
        proxy_protocol: str
    ) -> TargetResult:
        """测试单个目标（兼容旧接口，实际使用 proxy_url 方式）"""
        proxy_url = f"{proxy_protocol}://{proxy_ip}:{proxy_port}"
        return await self._test_single_target_with_session(session, target, proxy_url)

    async def test_proxy_async(
        self,
        proxy_ip: str,
        proxy_port: int,
        proxy_protocol: Optional[str] = None
    ) -> MultiTargetTestResult:
        """
        异步测试代理（多目标并发）
        支持 HTTP/HTTPS/SOCKS4/SOCKS5
        """
        protocol = (proxy_protocol if proxy_protocol else 'http').lower()

        # 获取合适的 connector 和 proxy_url
        custom_connector, proxy_url = self._get_proxy_connector(protocol, proxy_ip, proxy_port)

        if custom_connector is None and proxy_url is None:
            # 不支持的协议
            self.logger.warning(f"Skipping unsupported proxy protocol: {protocol}")
            return MultiTargetTestResult(
                target_results=[
                    TargetResult(
                        target=t,
                        success=False,
                        response_time=0,
                        error=f"Unsupported protocol: {protocol}"
                    ) for t in self.targets
                ],
                total_time=0
            )

        await self._ensure_target_baselines()
        active_targets = [target for target in self.targets if target in self._target_baselines]
        if not active_targets:
            self.logger.warning("No healthy baseline targets available, skipping proxy validation")
            return MultiTargetTestResult(target_results=[], total_time=0)

        target_results = []

        if custom_connector:
            # SOCKS 代理：为每个目标创建独立的 session（因为 SOCKS connector 不能复用）
            for target in active_targets:
                # 为每个目标创建新的 connector（避免连接复用问题）
                connector = ProxyConnector(
                    proxy_type=ProxyType.SOCKS5 if 'socks5' in protocol else ProxyType.SOCKS4,
                    host=proxy_ip,
                    port=proxy_port,
                    limit=1,
                    enable_cleanup_closed=True,
                    force_close=True
                )

                async with aiohttp.ClientSession(
                        connector=connector,
                        headers=self.default_headers
                ) as session:
                    result = await self._test_single_target_with_session(session, target, None)
                    target_results.append(result)

        else:
            # HTTP/HTTPS 代理：使用共享 session
            async with aiohttp.ClientSession(
                    connector=self.connector,
                    connector_owner=False,
                    headers=self.default_headers
            ) as session:
                # 并发测试所有目标
                tasks = [
                    self._test_single_target_with_session(session, target, proxy_url)
                    for target in active_targets
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理异常结果（包括 CancelledError 等 BaseException）
                for i, result in enumerate(results):
                    if isinstance(result, BaseException):
                        target_results.append(TargetResult(
                            target=active_targets[i],
                            success=False,
                            response_time=0,
                            error=str(result)
                        ))
                    else:
                        target_results.append(result)

        return MultiTargetTestResult(
            target_results=target_results,
            total_time=sum(r.response_time for r in target_results)
        )

    def test_proxy(
        self,
        proxy_ip: str,
        proxy_port: int,
        proxy_protocol: Optional[str] = None
    ) -> dict:
        """
        同步接口（兼容 BaseTester）
        实际调用异步方法
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.test_proxy_async(proxy_ip, proxy_port, proxy_protocol),
                    loop
                )
                result = future.result(
                    timeout=self.config.TEST_TIMEOUT_PER_TARGET * len(self.targets) + 5)
            else:
                result = loop.run_until_complete(
                    self.test_proxy_async(proxy_ip, proxy_port, proxy_protocol)
                )
        except RuntimeError:
            result = asyncio.run(
                self.test_proxy_async(proxy_ip, proxy_port, proxy_protocol)
            )

        score_result = self.scorer.calculate_score(result)
        success = bool(score_result["is_available"])
        avg_time = result.avg_response_time if success else -1.0

        if result.total_targets == 0:
            error_message = "无健康基线目标可用于验证代理"
        elif success:
            error_message = None
        else:
            error_message = (
                f"未达到 B级及以上阈值，仅 {result.success_count}/{result.total_targets} "
                f"个健康目标通过"
            )

        return {
            "success": success,
            "response_time": avg_time,
            "status_code": 200 if success else None,
            "error_message": error_message,
            "multi_target_result": result
        }

    async def close(self):
        """关闭连接池"""
        await self.connector.close()
