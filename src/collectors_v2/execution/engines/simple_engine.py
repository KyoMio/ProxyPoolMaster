"""simple 模式执行引擎。"""

import copy
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from lxml import html
from lxml.etree import _Element


DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
_COUNTRY_NAME_TO_CODE_MAP: Dict[str, str] | None = None
_SORTED_COUNTRY_NAMES: List[str] | None = None
_COUNTRY_ENGLISH_NAME_TO_CODE_MAP: Dict[str, str] | None = None
_SORTED_ENGLISH_COUNTRY_NAMES: List[str] | None = None
_COUNTRY_TEXT_ALIASES = {
    "USA": "US",
    "UNITED STATES": "US",
    "UK": "GB",
    "UNITED KINGDOM": "GB",
    "GREAT BRITAIN": "GB",
    "BRITAIN": "GB",
    "UAE": "AE",
    "SOUTH KOREA": "KR",
    "NORTH KOREA": "KP",
    "RUSSIA": "RU",
    "TURKEY": "TR",
    "CZECH REPUBLIC": "CZ",
    "NETHERLANDS": "NL",
    "HOLLAND": "NL",
    "IRAN": "IR",
    "SYRIA": "SY",
    "LAOS": "LA",
    "VIETNAM": "VN",
    "BRUNEI": "BN",
    "MOLDOVA": "MD",
    "BOLIVIA": "BO",
    "VENEZUELA": "VE",
    "TANZANIA": "TZ",
    "MICRONESIA": "FM",
    "TAIWAN": "TW",
    "MACAU": "MO",
    "PALESTINE": "PS",
    "CAPE VERDE": "CV",
    "IVORY COAST": "CI",
    "REPUBLIC OF KOREA": "KR",
    "REPUBLIC OF MOLDOVA": "MD",
    "REPUBLIC OF THE CONGO": "CG",
    "DEMOCRATIC REPUBLIC OF THE CONGO": "CD",
    "DEMOCRATIC REPUBLIC OF CONGO": "CD",
}


def run_simple_engine(spec: Dict[str, Any]) -> List[dict]:
    """
    simple 模式执行器：
    1) 兼容旧 spec.proxies/items 直出（用于已存在测试链路）。
    2) 支持 request + extract + field_mapping 的真实抓取流程。
    """
    if spec is None:
        return []
    if not isinstance(spec, dict):
        raise ValueError("simple spec 必须是 dict")

    sleep_seconds = float(spec.get("sleep_seconds", 0) or 0)
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

    if _is_legacy_candidates_spec(spec):
        return _load_legacy_candidates(spec)

    request_spec = spec.get("request")
    if not isinstance(request_spec, dict):
        raise ValueError("simple spec.request 必须是 dict")

    extract_spec = spec.get("extract")
    if not isinstance(extract_spec, dict):
        raise ValueError("simple spec.extract 必须是 dict")

    field_mapping = spec.get("field_mapping")
    if field_mapping is not None and not isinstance(field_mapping, dict):
        raise ValueError("simple spec.field_mapping 必须是 dict")

    pagination_spec = spec.get("pagination")
    if pagination_spec is not None and not isinstance(pagination_spec, dict):
        raise ValueError("simple spec.pagination 必须是 dict")

    if pagination_spec is not None:
        return _run_paginated_requests(request_spec, extract_spec, field_mapping, pagination_spec)

    response = _do_request(request_spec)
    extract_type, extract_expression = _parse_extract_spec(extract_spec)
    raw_items = _extract_items(response, extract_type, extract_expression)
    return _map_items(raw_items, field_mapping, extract_type)


def _is_legacy_candidates_spec(spec: Dict[str, Any]) -> bool:
    return "request" not in spec and "extract" not in spec and "field_mapping" not in spec


def _load_legacy_candidates(spec: Dict[str, Any]) -> List[dict]:
    candidates = spec.get("proxies")
    if candidates is None:
        candidates = spec.get("items", [])
    if candidates is None:
        return []
    if not isinstance(candidates, list):
        raise ValueError("simple spec 的 proxies/items 必须是列表")
    return list(candidates)


def _run_paginated_requests(
    request_spec: Dict[str, Any],
    extract_spec: Dict[str, Any],
    field_mapping: Dict[str, Any] | None,
    pagination_spec: Dict[str, Any],
) -> List[dict]:
    extract_type, extract_expression = _parse_extract_spec(extract_spec)

    page_param = str(pagination_spec.get("page_param", "page") or "page").strip() or "page"
    start_page = int(pagination_spec.get("start_page", 1) or 1)
    max_pages = max(1, int(pagination_spec.get("max_pages", 1) or 1))
    stop_when_empty = bool(pagination_spec.get("stop_when_empty", False))

    results: List[dict] = []
    current_page = start_page
    for _ in range(max_pages):
        paged_request_spec = _build_paged_request_spec(request_spec, page_param, current_page)
        response = _do_request(paged_request_spec)
        raw_items = _extract_items(response, extract_type, extract_expression)
        results.extend(_map_items(raw_items, field_mapping, extract_type))

        if stop_when_empty and not raw_items:
            break
        current_page += 1

    return results


def _build_paged_request_spec(request_spec: Dict[str, Any], page_param: str, page: int) -> Dict[str, Any]:
    paged_request_spec = copy.deepcopy(request_spec)
    params = paged_request_spec.get("params")
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        params = dict(params)
    else:
        params = copy.deepcopy(params)

    params[page_param] = page
    paged_request_spec["params"] = params
    return paged_request_spec


def _do_request(request_spec: Dict[str, Any]) -> requests.Response:
    url = str(request_spec.get("url", "")).strip()
    if not url:
        raise ValueError("simple spec.request.url 不能为空")

    method = str(request_spec.get("method", "GET")).upper()
    headers = request_spec.get("headers") or None
    params = request_spec.get("params") or None
    data = request_spec.get("data") or None
    json_body = request_spec.get("json")
    timeout_seconds = float(request_spec.get("timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS) or DEFAULT_REQUEST_TIMEOUT_SECONDS)

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        data=data,
        json=json_body,
        timeout=max(0.1, timeout_seconds),
    )
    response.raise_for_status()
    return response


def _parse_extract_spec(extract_spec: Dict[str, Any]) -> Tuple[str, str]:
    extract_type = str(extract_spec.get("type", "jsonpath")).strip().lower()
    expression = (
        extract_spec.get("expression")
        or extract_spec.get("selector")
        or extract_spec.get("path")
        or ""
    )
    expression = str(expression).strip()
    if not expression:
        raise ValueError("simple spec.extract.expression 不能为空")
    if extract_type not in {"jsonpath", "css", "xpath"}:
        raise ValueError(f"不支持的提取类型: {extract_type}")
    return extract_type, expression


def _extract_items(response: requests.Response, extract_type: str, expression: str) -> List[Any]:
    if extract_type == "jsonpath":
        try:
            payload = response.json()
        except Exception as exc:
            raise ValueError(f"JSON 解析失败: {exc}") from exc
        items = _eval_jsonpath(payload, expression)
        if not items:
            api_error = _extract_api_error_message(payload)
            if api_error:
                raise ValueError(api_error)
        return items

    document = html.fromstring(response.text or "")
    if extract_type == "css":
        return _css_select(document, expression)
    return list(document.xpath(expression))


def _extract_api_error_message(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    candidates = []
    for key in ("msg", "message", "detail", "error"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            candidates.append(text)

    errors = payload.get("errors")
    if isinstance(errors, list):
        for item in errors:
            text = str(item).strip()
            if text:
                candidates.append(text)
    elif errors is not None:
        text = str(errors).strip()
        if text:
            candidates.append(text)

    if not candidates:
        return None

    code = payload.get("code")
    status = payload.get("status")
    prefix_parts = []
    if code not in (None, ""):
        prefix_parts.append(f"code={code}")
    if status not in (None, ""):
        prefix_parts.append(f"status={status}")
    prefix = ", ".join(prefix_parts)
    summary = candidates[0]
    return f"API 返回错误: {prefix} {summary}".strip()


def _map_items(raw_items: List[Any], field_mapping: Dict[str, Any] | None, extract_type: str) -> List[dict]:
    if not raw_items:
        return []

    if not field_mapping:
        return [dict(item) for item in raw_items if isinstance(item, dict)]

    result: List[dict] = []
    for item in raw_items:
        mapped = _map_single_item(item, field_mapping, extract_type)
        if mapped:
            result.append(mapped)
    return result


def _map_single_item(item: Any, field_mapping: Dict[str, Any], extract_type: str) -> Dict[str, Any]:
    mapped: Dict[str, Any] = {}
    for field, rule in field_mapping.items():
        value = _resolve_field_value(item, rule, extract_type)
        if value is None:
            continue
        mapped[field] = value

    if "country" in mapped and "country_code" not in mapped:
        mapped["country_code"] = mapped.pop("country")
    if "anonymity" in mapped and "anonymity_level" not in mapped:
        mapped["anonymity_level"] = mapped.pop("anonymity")
    return mapped


def _resolve_field_value(item: Any, rule: Any, extract_type: str) -> Any:
    if isinstance(rule, dict):
        expression = rule.get("expression") or rule.get("path") or rule.get("selector")
        default = rule.get("default")
        transform = rule.get("transform")
    else:
        expression = rule
        default = None
        transform = None

    expression_text = str(expression or "").strip()
    if not expression_text:
        return default

    if expression_text.startswith("const:"):
        return expression_text[len("const:") :]

    value = None
    if extract_type == "jsonpath":
        value = _resolve_json_item_value(item, expression_text)
    elif extract_type == "css":
        value = _resolve_css_item_value(item, expression_text)
    elif extract_type == "xpath":
        value = _resolve_xpath_item_value(item, expression_text)

    if value is None:
        return default
    if transform:
        return _apply_transform(value, transform, default)
    return value


def _apply_transform(value: Any, transform: Any, default: Any) -> Any:
    transform_name = str(transform or "").strip()
    if not transform_name:
        return value
    if transform_name == "country_text_to_code":
        return _country_text_to_code(value, default)
    raise ValueError(f"不支持的字段转换器: {transform_name}")


def _country_text_to_code(value: Any, default: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return default

    upper_text = text.upper()
    if re.fullmatch(r"[A-Z]{2}", upper_text):
        return upper_text

    if upper_text in _COUNTRY_TEXT_ALIASES:
        return _COUNTRY_TEXT_ALIASES[upper_text]

    country_name_to_code_map = _load_country_name_to_code_map()
    if text in country_name_to_code_map:
        return country_name_to_code_map[text]

    for country_name in _load_sorted_country_names():
        if country_name in text:
            return country_name_to_code_map.get(country_name, default)

    normalized_english_text = _normalize_english_country_text(text)
    if not normalized_english_text:
        return default

    english_name_to_code_map = _load_english_country_name_to_code_map()
    if normalized_english_text in english_name_to_code_map:
        return english_name_to_code_map[normalized_english_text]

    padded_text = f" {normalized_english_text} "
    for country_name in _load_sorted_english_country_names():
        if f" {country_name} " in padded_text:
            return english_name_to_code_map.get(country_name, default)

    return default


def _load_country_name_to_code_map() -> Dict[str, str]:
    global _COUNTRY_NAME_TO_CODE_MAP
    if _COUNTRY_NAME_TO_CODE_MAP is not None:
        return _COUNTRY_NAME_TO_CODE_MAP

    data_dir = _get_country_data_dir()
    mapping_file = data_dir / "country_code_to_zh.json"
    code_to_name = json.loads(mapping_file.read_text(encoding="utf-8"))
    _COUNTRY_NAME_TO_CODE_MAP = {str(name): str(code).upper() for code, name in code_to_name.items()}
    return _COUNTRY_NAME_TO_CODE_MAP


def _load_sorted_country_names() -> List[str]:
    global _SORTED_COUNTRY_NAMES
    if _SORTED_COUNTRY_NAMES is not None:
        return _SORTED_COUNTRY_NAMES

    data_dir = _get_country_data_dir()
    country_file = data_dir / "countries_zh.json"
    country_names = json.loads(country_file.read_text(encoding="utf-8"))
    _SORTED_COUNTRY_NAMES = sorted((str(name) for name in country_names), key=len, reverse=True)
    return _SORTED_COUNTRY_NAMES


def _load_english_country_name_to_code_map() -> Dict[str, str]:
    global _COUNTRY_ENGLISH_NAME_TO_CODE_MAP
    if _COUNTRY_ENGLISH_NAME_TO_CODE_MAP is not None:
        return _COUNTRY_ENGLISH_NAME_TO_CODE_MAP

    data_dir = _get_country_data_dir()
    mapping_file = data_dir / "country_code_to_en.json"
    code_to_name = json.loads(mapping_file.read_text(encoding="utf-8"))
    _COUNTRY_ENGLISH_NAME_TO_CODE_MAP = {
        _normalize_english_country_text(str(name)): str(code).upper()
        for code, name in code_to_name.items()
        if _normalize_english_country_text(str(name))
    }
    for alias, code in _COUNTRY_TEXT_ALIASES.items():
        normalized_alias = _normalize_english_country_text(alias)
        if normalized_alias:
            _COUNTRY_ENGLISH_NAME_TO_CODE_MAP[normalized_alias] = str(code).upper()
    return _COUNTRY_ENGLISH_NAME_TO_CODE_MAP


def _load_sorted_english_country_names() -> List[str]:
    global _SORTED_ENGLISH_COUNTRY_NAMES
    if _SORTED_ENGLISH_COUNTRY_NAMES is not None:
        return _SORTED_ENGLISH_COUNTRY_NAMES

    _SORTED_ENGLISH_COUNTRY_NAMES = sorted(
        _load_english_country_name_to_code_map().keys(),
        key=len,
        reverse=True,
    )
    return _SORTED_ENGLISH_COUNTRY_NAMES


def _normalize_english_country_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.upper()
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _get_country_data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "collectors" / "data"


def _resolve_json_item_value(item: Any, expression: str) -> Any:
    if expression.startswith("$"):
        values = _eval_jsonpath(item, expression)
        return values[0] if values else None
    return _resolve_object_path(item, expression)


def _resolve_css_item_value(item: Any, expression: str) -> Any:
    if not isinstance(item, _Element):
        return None

    selector, extractor = _split_css_expression(expression)
    nodes = [item] if not selector else _css_select(item, selector)
    if not nodes:
        return None
    node = nodes[0]

    if extractor == "text":
        return _extract_node_text(node)
    if extractor.startswith("attr(") and extractor.endswith(")"):
        attr_name = extractor[5:-1].strip()
        return node.get(attr_name) if attr_name else None
    if extractor.startswith("attr:"):
        attr_name = extractor.split(":", 1)[1].strip()
        return node.get(attr_name) if attr_name else None
    raise ValueError(f"不支持的 CSS 字段提取器: {extractor}")


def _resolve_xpath_item_value(item: Any, expression: str) -> Any:
    if not isinstance(item, _Element):
        return None
    values = item.xpath(expression)
    if not values:
        return None
    first = values[0]
    if isinstance(first, _Element):
        return _extract_node_text(first)
    if isinstance(first, str):
        return first.strip()
    return first


def _split_css_expression(expression: str) -> Tuple[str, str]:
    if "::" not in expression:
        return expression.strip(), "text"
    selector, extractor = expression.split("::", 1)
    return selector.strip(), extractor.strip() or "text"


def _extract_node_text(node: _Element) -> str:
    return "".join(node.itertext()).strip()


def _css_select(root: _Element, selector: str) -> List[_Element]:
    selector = selector.strip()
    if not selector:
        return [root]

    xpath = _css_to_xpath(selector)
    return list(root.xpath(xpath))


def _css_to_xpath(selector: str) -> str:
    parts = [part.strip() for part in selector.split(" ") if part.strip()]
    if not parts:
        raise ValueError("CSS 选择器不能为空")

    xpath_parts = []
    for part in parts:
        xpath_parts.append(_css_part_to_xpath(part))
    return ".//" + "//".join(xpath_parts)


def _css_part_to_xpath(part: str) -> str:
    if not part:
        raise ValueError("CSS 选择器片段不能为空")

    tag_match = re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*", part)
    tag = tag_match.group(0) if tag_match else "*"
    cursor = len(tag) if tag_match else 0

    predicates: List[str] = []
    while cursor < len(part):
        token = part[cursor]
        cursor += 1
        name_start = cursor
        while cursor < len(part) and part[cursor] not in ".#":
            cursor += 1
        name = part[name_start:cursor]
        if not name:
            raise ValueError(f"不支持的 CSS 选择器: {part}")
        if token == ".":
            predicates.append(f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')")
            continue
        if token == "#":
            predicates.append(f"@id='{name}'")
            continue
        raise ValueError(f"不支持的 CSS 选择器: {part}")

    if not predicates:
        return tag
    return f"{tag}[{' and '.join(predicates)}]"


def _eval_jsonpath(payload: Any, expression: str) -> List[Any]:
    tokens = _tokenize_jsonpath(expression)
    current_nodes = [payload]
    for token_type, token_value in tokens:
        next_nodes: List[Any] = []
        for node in current_nodes:
            if token_type == "key":
                if isinstance(node, dict) and token_value in node:
                    next_nodes.append(node[token_value])
            elif token_type == "index":
                if isinstance(node, list) and 0 <= token_value < len(node):
                    next_nodes.append(node[token_value])
            elif token_type == "wildcard":
                if isinstance(node, list):
                    next_nodes.extend(node)
                elif isinstance(node, dict):
                    next_nodes.extend(node.values())
        current_nodes = next_nodes

    if len(current_nodes) == 1 and isinstance(current_nodes[0], list):
        return list(current_nodes[0])
    return current_nodes


def _tokenize_jsonpath(expression: str) -> List[Tuple[str, Any]]:
    if not expression or expression[0] != "$":
        raise ValueError(f"JSONPath 必须以 $ 开头: {expression}")
    if expression == "$":
        return []

    tokens: List[Tuple[str, Any]] = []
    idx = 1
    while idx < len(expression):
        char = expression[idx]
        if char == ".":
            idx += 1
            start = idx
            while idx < len(expression) and expression[idx] not in ".[":
                idx += 1
            key = expression[start:idx].strip()
            if not key:
                raise ValueError(f"JSONPath 非法 key: {expression}")
            tokens.append(("key", key))
            continue

        if char == "[":
            end = expression.find("]", idx)
            if end == -1:
                raise ValueError(f"JSONPath 缺少 ]: {expression}")
            inner = expression[idx + 1 : end].strip()
            if inner == "*":
                tokens.append(("wildcard", None))
            elif inner.isdigit():
                tokens.append(("index", int(inner)))
            elif (
                (inner.startswith("'") and inner.endswith("'")) or
                (inner.startswith('"') and inner.endswith('"'))
            ):
                tokens.append(("key", inner[1:-1]))
            else:
                raise ValueError(f"JSONPath 不支持的片段: [{inner}]")
            idx = end + 1
            continue

        raise ValueError(f"JSONPath 非法字符 '{char}': {expression}")
    return tokens


def _resolve_object_path(data: Any, path: str) -> Any:
    current = data
    for part in [segment for segment in path.split(".") if segment]:
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue

        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    if isinstance(current, str):
        return current.strip()
    if isinstance(current, (dict, list)):
        return json.dumps(current, ensure_ascii=False)
    return current
