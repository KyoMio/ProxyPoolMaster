#!/usr/bin/env python3
"""测试代理池随机代理对指定页面的真实可用性。"""

from __future__ import annotations

import argparse
import os
import re
import statistics
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36 ProxyPoolMasterProbe/1.0"
)
DEFAULT_STOP_WORDS = {
    "about",
    "and",
    "are",
    "com",
    "domain",
    "example",
    "for",
    "from",
    "http",
    "https",
    "page",
    "that",
    "the",
    "this",
    "your",
    "with",
    "www",
}
THREAD_LOCAL = threading.local()


@dataclass(frozen=True)
class ResponseSnapshot:
    status_code: int
    final_url: str
    content_type: str
    body_length: int
    text_length: int
    title: str
    text: str


@dataclass(frozen=True)
class BaselineFingerprint:
    host: str
    title: str
    content_type_prefix: str
    median_body_length: int
    median_text_length: int
    keywords: List[str]


@dataclass(frozen=True)
class EvaluationResult:
    is_success: bool
    reasons: List[str]
    keyword_hits: List[str]


@dataclass(frozen=True)
class AttemptResult:
    attempt_id: int
    round_number: int
    proxy_label: str
    is_success: bool
    latency_ms: Optional[float]
    status_code: Optional[int]
    reasons: List[str]
    keyword_hits: List[str]


class RateLimiter:
    """限制代理列表接口请求频率，避免触发默认限流。"""

    def __init__(self, requests_per_second: float) -> None:
        self.interval = 0.0 if requests_per_second <= 0 else 1.0 / requests_per_second
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return

        while True:
            sleep_for = 0.0
            with self._lock:
                now = time.monotonic()
                if now >= self._next_allowed_at:
                    self._next_allowed_at = now + self.interval
                    return
                sleep_for = self._next_allowed_at - now
            time.sleep(sleep_for)


def normalize_content_type(content_type: str) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def tokenize_text(text: str) -> List[str]:
    candidates = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9_-]{2,20}", text or "")
    tokens: List[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        if normalized.isascii():
            lowered = normalized.lower()
            if lowered in DEFAULT_STOP_WORDS:
                continue
            tokens.append(lowered)
        else:
            tokens.append(normalized)
    return tokens


def dedupe_keep_order(values: Sequence[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(cleaned)
    return result


def derive_keywords(
    samples: Sequence[ResponseSnapshot],
    explicit_keywords: Optional[Sequence[str]] = None,
    limit: int = 5,
) -> List[str]:
    if explicit_keywords:
        return dedupe_keep_order(explicit_keywords)

    if not samples:
        return []

    keywords: List[str] = []
    titles = [sample.title for sample in samples if sample.title]
    if titles:
        title_counter = Counter(titles)
        keywords.append(title_counter.most_common(1)[0][0])

    token_counter: Counter[str] = Counter()
    for sample in samples:
        token_counter.update(tokenize_text(sample.text))

    for token, count in token_counter.most_common(limit * 3):
        if count <= 1 and len(samples) > 1:
            continue
        keywords.append(token)
        if len(dedupe_keep_order(keywords)) >= limit:
            break

    return dedupe_keep_order(keywords)[:limit]


def hosts_match(expected_host: str, actual_host: str) -> bool:
    expected = (expected_host or "").strip().lower()
    actual = (actual_host or "").strip().lower()
    if not expected or not actual:
        return False
    return actual == expected or actual.endswith(f".{expected}") or expected.endswith(f".{actual}")


def build_baseline_fingerprint(
    samples: Sequence[ResponseSnapshot],
    explicit_keywords: Optional[Sequence[str]] = None,
) -> BaselineFingerprint:
    if not samples:
        raise ValueError("至少需要一个基线样本。")

    first_sample = samples[0]
    host = urlparse(first_sample.final_url).netloc.lower()
    content_type_prefix = normalize_content_type(first_sample.content_type)
    titles = [sample.title for sample in samples if sample.title]
    title = Counter(titles).most_common(1)[0][0] if titles else ""

    median_body_length = int(round(statistics.median(sample.body_length for sample in samples)))
    median_text_length = int(round(statistics.median(sample.text_length for sample in samples)))
    keywords = derive_keywords(samples, explicit_keywords=explicit_keywords)

    return BaselineFingerprint(
        host=host,
        title=title,
        content_type_prefix=content_type_prefix,
        median_body_length=median_body_length,
        median_text_length=median_text_length,
        keywords=keywords,
    )


def build_requests_proxies(proxy_payload: Dict[str, Any]) -> Dict[str, str]:
    ip = str(proxy_payload["ip"]).strip()
    port = int(proxy_payload["port"])
    proxy_url = f"http://{ip}:{port}"
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def evaluate_response_success(
    response: ResponseSnapshot,
    baseline: BaselineFingerprint,
    *,
    length_tolerance: float = 0.35,
    min_keyword_hits: int = 1,
) -> EvaluationResult:
    reasons: List[str] = []
    keyword_hits: List[str] = []

    if not 200 <= response.status_code < 400:
        reasons.append("unexpected_status")

    actual_host = urlparse(response.final_url).netloc.lower()
    if not hosts_match(baseline.host, actual_host):
        reasons.append("host_mismatch")

    actual_content_type = normalize_content_type(response.content_type)
    if baseline.content_type_prefix and actual_content_type and baseline.content_type_prefix != actual_content_type:
        reasons.append("content_type_mismatch")

    response_text_casefold = (response.text or "").casefold()
    for keyword in baseline.keywords:
        if keyword.casefold() in response_text_casefold:
            keyword_hits.append(keyword)

    required_keyword_hits = min(len(baseline.keywords), max(0, min_keyword_hits))
    if baseline.keywords and len(keyword_hits) < required_keyword_hits:
        reasons.append("keyword_miss")

    if baseline.median_body_length > 0:
        lower_bound = baseline.median_body_length * max(0.0, 1.0 - length_tolerance)
        upper_bound = baseline.median_body_length * (1.0 + length_tolerance)
        if not lower_bound <= response.body_length <= upper_bound:
            title_matches = bool(
                baseline.title
                and response.title
                and baseline.title.casefold() == response.title.casefold()
            )
            enough_keywords = len(keyword_hits) >= max(required_keyword_hits, 1)
            if not (title_matches and enough_keywords):
                reasons.append("body_length_out_of_range")

    return EvaluationResult(
        is_success=not reasons,
        reasons=reasons,
        keyword_hits=keyword_hits,
    )


def get_session(pool_size: int = 20) -> requests.Session:
    session = getattr(THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        THREAD_LOCAL.session = session
    return session


def fetch_snapshot(
    url: str,
    *,
    timeout: float,
    verify_tls: bool,
    user_agent: str,
    proxies: Optional[Dict[str, str]] = None,
) -> ResponseSnapshot:
    session = get_session()
    response = session.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        verify=verify_tls,
        proxies=proxies,
        headers={"User-Agent": user_agent},
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    normalized_content_type = normalize_content_type(content_type)
    text = ""
    if (
        normalized_content_type.startswith("text/")
        or normalized_content_type.endswith("json")
        or normalized_content_type.endswith("xml")
        or "html" in normalized_content_type
    ):
        text = response.text

    return ResponseSnapshot(
        status_code=response.status_code,
        final_url=response.url,
        content_type=content_type,
        body_length=len(response.content or b""),
        text_length=len(text),
        title=extract_title(text),
        text=text,
    )


def validate_proxy_payload(proxy_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(proxy_payload, dict):
        raise ValueError("代理数据不是 JSON 对象。")
    if "ip" not in proxy_payload or "port" not in proxy_payload:
        raise ValueError("代理数据缺少 ip/port 字段。")
    return proxy_payload


def fetch_available_proxy_payloads(
    api_base_url: str,
    api_token: str,
    *,
    timeout: float,
    verify_tls: bool,
    user_agent: str,
    rate_limiter: RateLimiter,
    page_size: int,
) -> List[Dict[str, Any]]:
    session = get_session()
    all_proxies: List[Dict[str, Any]] = []
    current_page = 1
    total = None

    while True:
        rate_limiter.wait()
        response = session.get(
            f"{api_base_url.rstrip('/')}/get",
            timeout=timeout,
            verify=verify_tls,
            params={
                "is_available": "true",
                "page": current_page,
                "size": page_size,
            },
            headers={
                "X-API-Token": api_token,
                "User-Agent": user_agent,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("`/get` 接口返回的数据不是 JSON 对象。")

        page_items = payload.get("data")
        if not isinstance(page_items, list):
            raise ValueError("`/get` 接口返回的数据缺少 data 列表。")

        for item in page_items:
            all_proxies.append(validate_proxy_payload(item))

        if total is None:
            total = int(payload.get("total", len(all_proxies)))

        if len(all_proxies) >= total or not page_items:
            break

        current_page += 1

    return all_proxies


def build_proxy_label(proxy_payload: Dict[str, Any]) -> str:
    protocol = str(proxy_payload.get("protocol") or "http").lower()
    ip = str(proxy_payload.get("ip") or "").strip()
    port = proxy_payload.get("port")
    grade = str(proxy_payload.get("grade") or "").strip()
    if grade:
        return f"{protocol}://{ip}:{port} [{grade}]"
    return f"{protocol}://{ip}:{port}"


def run_single_attempt_for_proxy(
    attempt_id: int,
    round_number: int,
    proxy_payload: Dict[str, Any],
    args: argparse.Namespace,
    baseline: BaselineFingerprint,
) -> AttemptResult:
    proxy_payload = validate_proxy_payload(proxy_payload)
    proxy_label = build_proxy_label(proxy_payload)
    request_started_at = time.perf_counter()

    try:
        snapshot = fetch_snapshot(
            args.target_url,
            timeout=args.timeout,
            verify_tls=not args.insecure,
            user_agent=args.user_agent,
            proxies=build_requests_proxies(proxy_payload),
        )
        elapsed_ms = (time.perf_counter() - request_started_at) * 1000.0
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        elapsed_ms = (time.perf_counter() - request_started_at) * 1000.0
        return AttemptResult(
            attempt_id=attempt_id,
            round_number=round_number,
            proxy_label=proxy_label,
            is_success=False,
            latency_ms=elapsed_ms,
            status_code=status_code,
            reasons=[f"target_http_{status_code}" if status_code else "target_http_error"],
            keyword_hits=[],
        )
    except requests.RequestException as exc:
        elapsed_ms = (time.perf_counter() - request_started_at) * 1000.0
        return AttemptResult(
            attempt_id=attempt_id,
            round_number=round_number,
            proxy_label=proxy_label,
            is_success=False,
            latency_ms=elapsed_ms,
            status_code=None,
            reasons=[f"target_request_error:{exc.__class__.__name__}"],
            keyword_hits=[],
        )

    evaluation = evaluate_response_success(
        snapshot,
        baseline,
        length_tolerance=args.length_tolerance,
        min_keyword_hits=args.min_keyword_hits,
    )
    return AttemptResult(
        attempt_id=attempt_id,
        round_number=round_number,
        proxy_label=proxy_label,
        is_success=evaluation.is_success,
        latency_ms=elapsed_ms,
        status_code=snapshot.status_code,
        reasons=evaluation.reasons,
        keyword_hits=evaluation.keyword_hits,
    )


def run_rounds(
    args: argparse.Namespace,
    baseline: BaselineFingerprint,
    proxy_payloads: Sequence[Dict[str, Any]],
) -> List[AttemptResult]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: List[AttemptResult] = []
    attempt_id = 1

    for round_number in range(1, args.rounds + 1):
        print(
            f"\n[round {round_number}/{args.rounds}] 开始测试 {len(proxy_payloads)} 个可用代理",
            flush=True,
        )
        completed = 0
        progress_interval = max(1, len(proxy_payloads) // 10) if proxy_payloads else 1
        round_results: List[AttemptResult] = []

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = []
            for proxy_payload in proxy_payloads:
                futures.append(
                    executor.submit(
                        run_single_attempt_for_proxy,
                        attempt_id,
                        round_number,
                        proxy_payload,
                        args,
                        baseline,
                    )
                )
                attempt_id += 1

            for future in as_completed(futures):
                result = future.result()
                round_results.append(result)
                completed += 1
                if completed % progress_interval == 0 or completed == len(proxy_payloads):
                    current_success_count = sum(1 for item in round_results if item.is_success)
                    print(
                        f"第 {round_number} 轮进度: {completed}/{len(proxy_payloads)}，当前成功={current_success_count}",
                        flush=True,
                    )

        round_results.sort(key=lambda item: item.attempt_id)
        results.extend(round_results)

        if round_number < args.rounds:
            print(f"等待 {args.round_interval:.1f} 秒后开始下一轮...", flush=True)
            time.sleep(args.round_interval)

    return results


def build_baseline(args: argparse.Namespace) -> Tuple[BaselineFingerprint, List[ResponseSnapshot]]:
    samples: List[ResponseSnapshot] = []
    errors: List[str] = []

    for index in range(1, args.baseline_runs + 1):
        try:
            sample = fetch_snapshot(
                args.target_url,
                timeout=args.timeout,
                verify_tls=not args.insecure,
                user_agent=args.user_agent,
            )
            samples.append(sample)
            print(
                f"[baseline {index}/{args.baseline_runs}] "
                f"status={sample.status_code} host={urlparse(sample.final_url).netloc} "
                f"body={sample.body_length}",
                flush=True,
            )
        except Exception as exc:
            errors.append(f"第 {index} 次基线请求失败: {exc}")

    if not samples:
        raise RuntimeError("无法建立基线，请先确认目标页面在不使用代理时可访问。")

    baseline = build_baseline_fingerprint(samples, explicit_keywords=args.keyword)
    if errors:
        print("基线阶段存在部分失败：", flush=True)
        for item in errors:
            print(f"  - {item}", flush=True)
    return baseline, samples


def print_summary(
    args: argparse.Namespace,
    baseline: BaselineFingerprint,
    results: Sequence[AttemptResult],
) -> None:
    total = len(results)
    success_results = [result for result in results if result.is_success]
    success_count = len(success_results)
    success_rate = (success_count / total * 100.0) if total else 0.0

    proxy_counter = Counter(result.proxy_label for result in results if result.proxy_label != "-")
    reason_counter = Counter()
    for result in results:
        if result.is_success:
            continue
        if not result.reasons:
            reason_counter["unknown_failure"] += 1
            continue
        for reason in result.reasons:
            reason_counter[reason] += 1

    latency_values = [result.latency_ms for result in success_results if result.latency_ms is not None]
    average_latency = statistics.mean(latency_values) if latency_values else None

    print("\n===== 基线信息 =====")
    print(f"目标地址: {args.target_url}")
    print(f"目标主机: {baseline.host}")
    print(f"内容类型: {baseline.content_type_prefix or 'unknown'}")
    print(f"基线标题: {baseline.title or '(无)'}")
    print(f"基线长度(中位数): body={baseline.median_body_length}, text={baseline.median_text_length}")
    print(f"判定关键字: {', '.join(baseline.keywords) if baseline.keywords else '(未提取到，主要依赖状态/主机/长度)'}")

    print("\n===== 测试结果 =====")
    print(f"复测轮数: {args.rounds}")
    print(f"总请求数: {total}")
    print(f"成功次数: {success_count}")
    print(f"访问成功率: {success_rate:.2f}%")
    print(f"唯一代理数: {len(proxy_counter)}")
    print(f"重复代理次数: {sum(proxy_counter.values()) - len(proxy_counter)}")
    if average_latency is not None:
        print(f"成功请求平均耗时: {average_latency:.2f} ms")

    print("\n===== 每轮成功率 =====")
    for round_number in range(1, args.rounds + 1):
        round_results = [result for result in results if result.round_number == round_number]
        round_total = len(round_results)
        round_success = sum(1 for result in round_results if result.is_success)
        round_rate = (round_success / round_total * 100.0) if round_total else 0.0
        print(f"第 {round_number} 轮: {round_success}/{round_total} ({round_rate:.2f}%)")

    print("\n===== 代理复测表现 =====")
    proxy_success_counter = Counter(
        result.proxy_label for result in results if result.is_success and result.proxy_label != "-"
    )
    if proxy_counter:
        for proxy_label, count in proxy_counter.most_common():
            success_times = proxy_success_counter.get(proxy_label, 0)
            print(f"{proxy_label}: {success_times}/{count}")
    else:
        print("无")

    print("\n===== 失败原因统计 =====")
    if reason_counter:
        for reason, count in reason_counter.most_common():
            print(f"{reason}: {count}")
    else:
        print("无")

    print("\n===== 失败样本（最多 10 条） =====")
    failure_results = [result for result in results if not result.is_success][:10]
    if failure_results:
        for result in failure_results:
            print(
                f"#{result.attempt_id:03d} round={result.round_number} proxy={result.proxy_label} "
                f"status={result.status_code} reasons={','.join(result.reasons) or 'unknown'}"
            )
    else:
        print("无")

    print("\n===== 高频代理（最多 10 条） =====")
    if proxy_counter:
        for proxy_label, count in proxy_counter.most_common(10):
            print(f"{proxy_label}: {count}")
    else:
        print("无")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试代理池随机代理对指定页面的真实可用性")
    parser.add_argument("--target-url", required=True, help="用于验证代理的目标页面 URL")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("PPM_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
        help="API 基础地址，默认读取 PPM_API_BASE_URL 或 http://127.0.0.1:8000/api/v1",
    )
    parser.add_argument(
        "--api-token",
        default=os.getenv("API_TOKEN"),
        help="API Token，默认读取环境变量 API_TOKEN",
    )
    parser.add_argument("--workers", type=int, default=20, help="并发线程数，默认 20")
    parser.add_argument("--baseline-runs", type=int, default=3, help="基线请求次数，默认 3")
    parser.add_argument("--timeout", type=float, default=20.0, help="访问目标页面超时秒数，默认 20 秒")
    parser.add_argument(
        "--api-timeout",
        "--random-timeout",
        dest="api_timeout",
        type=float,
        default=10.0,
        help="调用代理列表接口超时秒数，默认 10 秒",
    )
    parser.add_argument("--rounds", type=int, default=3, help="复测轮数，默认 3")
    parser.add_argument("--round-interval", type=float, default=10.0, help="轮次间隔秒数，默认 10 秒")
    parser.add_argument("--page-size", type=int, default=100, help="拉取可用代理时的分页大小，默认 100")
    parser.add_argument(
        "--api-rps",
        "--random-rps",
        dest="api_rps",
        type=float,
        default=1.0,
        help="代理列表接口的最大请求速率，默认 1 次/秒，用于规避默认 60/minute 限流",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        default=None,
        help="可重复传入，用于强制指定页面关键字；未提供时自动从基线页面提取",
    )
    parser.add_argument(
        "--min-keyword-hits",
        type=int,
        default=1,
        help="判定成功所需命中的最少关键字数量，默认 1",
    )
    parser.add_argument(
        "--length-tolerance",
        type=float,
        default=0.35,
        help="页面长度允许偏差比例，默认 0.35 表示 +-35%%",
    )
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="请求使用的 User-Agent")
    parser.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验")

    args = parser.parse_args(argv)
    if not args.api_token:
        parser.error("缺少 --api-token，且环境变量 API_TOKEN 也未设置。")
    if args.workers <= 0:
        parser.error("--workers 必须大于 0。")
    if args.baseline_runs <= 0:
        parser.error("--baseline-runs 必须大于 0。")
    if args.rounds <= 0:
        parser.error("--rounds 必须大于 0。")
    if args.round_interval < 0:
        parser.error("--round-interval 不能小于 0。")
    if args.page_size <= 0 or args.page_size > 100:
        parser.error("--page-size 必须在 1 到 100 之间。")
    if args.timeout <= 0 or args.api_timeout <= 0:
        parser.error("--timeout 和 --api-timeout 必须大于 0。")
    if args.api_rps < 0:
        parser.error("--api-rps 不能小于 0。")
    if not 0 <= args.length_tolerance <= 1:
        parser.error("--length-tolerance 必须在 0 到 1 之间。")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    rate_limiter = RateLimiter(args.api_rps)

    baseline, _samples = build_baseline(args)

    proxy_payloads = fetch_available_proxy_payloads(
        args.api_base_url,
        args.api_token,
        timeout=args.api_timeout,
        verify_tls=not args.insecure,
        user_agent=args.user_agent,
        rate_limiter=rate_limiter,
        page_size=args.page_size,
    )
    if not proxy_payloads:
        raise RuntimeError("当前没有可用代理，无法执行三轮复测。")

    print("\n开始并发复测可用代理...", flush=True)
    print(
        f"代理数={len(proxy_payloads)}, 轮数={args.rounds}, 线程数={args.workers}, "
        f"接口速率上限={args.api_rps}/s",
        flush=True,
    )

    results = run_rounds(args, baseline, proxy_payloads)
    print_summary(args, baseline, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
