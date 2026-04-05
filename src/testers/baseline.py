"""
测试器基线指纹与响应比对模块。

该模块抽取自脚本 `scripts/check_proxy_pool_availability.py` 的基线构建和
结果判定逻辑，供后端 tester 复用。
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Sequence
from urllib.parse import urlparse


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


def normalize_content_type(content_type: str) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


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
