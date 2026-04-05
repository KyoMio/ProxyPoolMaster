import unittest
from unittest.mock import patch

import requests

from src.collectors_v2.execution.engines.simple_engine import run_simple_engine


class _FakeResponse:
    def __init__(self, *, text="", json_data=None, status_code=200):
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class TestCollectorsV2SimpleEngine(unittest.TestCase):
    def test_simple_engine_should_extract_by_jsonpath_and_mapping(self):
        spec = {
            "request": {
                "url": "https://example.test/api/proxies",
                "method": "GET",
                "timeout_seconds": 5,
                "headers": {"X-Test": "1"},
            },
            "extract": {
                "type": "jsonpath",
                "expression": "$.data.items[*]",
            },
            "field_mapping": {
                "ip": "ip",
                "port": "port",
                "protocol": "protocol",
                "country_code": "country",
                "anonymity_level": "anon",
            },
        }

        with patch("src.collectors_v2.execution.engines.simple_engine.requests.request") as mock_request:
            mock_request.return_value = _FakeResponse(
                json_data={
                    "data": {
                        "items": [
                            {
                                "ip": "11.11.11.11",
                                "port": 8080,
                                "protocol": "http",
                                "country": "CN",
                                "anon": "high",
                            }
                        ]
                    }
                }
            )

            proxies = run_simple_engine(spec)

        self.assertEqual(
            proxies,
            [
                {
                    "ip": "11.11.11.11",
                    "port": 8080,
                    "protocol": "http",
                    "country_code": "CN",
                    "anonymity_level": "high",
                }
            ],
        )

    def test_simple_engine_should_extract_by_css_and_mapping(self):
        spec = {
            "request": {
                "url": "https://example.test/html",
                "method": "GET",
            },
            "extract": {
                "type": "css",
                "expression": ".proxy-row",
            },
            "field_mapping": {
                "ip": ".ip::text",
                "port": ".port::text",
                "protocol": ".proto::text",
            },
        }

        html = """
        <html><body>
          <div class=\"proxy-row\"><span class=\"ip\">12.12.12.12</span><span class=\"port\">8888</span><span class=\"proto\">https</span></div>
        </body></html>
        """

        with patch("src.collectors_v2.execution.engines.simple_engine.requests.request") as mock_request:
            mock_request.return_value = _FakeResponse(text=html)
            proxies = run_simple_engine(spec)

        self.assertEqual(
            proxies,
            [{"ip": "12.12.12.12", "port": "8888", "protocol": "https"}],
        )

    def test_simple_engine_should_extract_by_xpath_and_support_const_mapping(self):
        spec = {
            "request": {
                "url": "https://example.test/xpath",
                "method": "GET",
            },
            "extract": {
                "type": "xpath",
                "expression": "//table/tbody/tr",
            },
            "field_mapping": {
                "ip": "./td[1]/text()",
                "port": "./td[2]/text()",
                "protocol": "const:http",
            },
        }

        html = """
        <table><tbody>
          <tr><td>13.13.13.13</td><td>3128</td></tr>
        </tbody></table>
        """

        with patch("src.collectors_v2.execution.engines.simple_engine.requests.request") as mock_request:
            mock_request.return_value = _FakeResponse(text=html)
            proxies = run_simple_engine(spec)

        self.assertEqual(
            proxies,
            [{"ip": "13.13.13.13", "port": "3128", "protocol": "http"}],
        )

    def test_simple_engine_should_raise_api_error_message_when_jsonpath_empty(self):
        spec = {
            "request": {
                "url": "https://example.test/api/proxies",
                "method": "GET",
            },
            "extract": {
                "type": "jsonpath",
                "expression": "$.data.proxy_list[*]",
            },
            "field_mapping": {
                "ip": "ip",
                "port": "port",
            },
        }

        with patch("src.collectors_v2.execution.engines.simple_engine.requests.request") as mock_request:
            mock_request.return_value = _FakeResponse(
                json_data={
                    "code": "10002",
                    "msg": "akey invalid",
                    "data": {
                        "proxy_list": []
                    }
                }
            )

            with self.assertRaises(ValueError) as ctx:
                run_simple_engine(spec)

        self.assertIn("akey invalid", str(ctx.exception))

    def test_simple_engine_should_transform_country_text_to_iso_code(self):
        spec = {
            "request": {
                "url": "https://example.test/api/proxies",
                "method": "GET",
            },
            "extract": {
                "type": "jsonpath",
                "expression": "$.data.proxy_list[*]",
            },
            "field_mapping": {
                "ip": "ip",
                "port": "port",
                "protocol": "protocol",
                "country_code": {
                    "expression": "adr",
                    "transform": "country_text_to_code",
                    "default": "Unknown",
                },
            },
        }

        with patch("src.collectors_v2.execution.engines.simple_engine.requests.request") as mock_request:
            mock_request.return_value = _FakeResponse(
                json_data={
                    "data": {
                        "proxy_list": [
                            {
                                "ip": "8.8.8.8",
                                "port": 443,
                                "protocol": "https",
                                "adr": "美国 洛杉矶",
                            },
                            {
                                "ip": "9.9.9.9",
                                "port": 8080,
                                "protocol": "http",
                                "adr": "日本东京 Amazon数据中心",
                            },
                            {
                                "ip": "7.7.7.7",
                                "port": 3128,
                                "protocol": "http",
                                "adr": "usa",
                            },
                            {
                                "ip": "5.5.5.5",
                                "port": 8081,
                                "protocol": "http",
                                "adr": "United States Los Angeles",
                            },
                            {
                                "ip": "4.4.4.4",
                                "port": 8082,
                                "protocol": "http",
                                "adr": "Tokyo, Japan",
                            },
                            {
                                "ip": "3.3.3.3",
                                "port": 8083,
                                "protocol": "https",
                                "adr": "Hosted in Netherlands",
                            },
                            {
                                "ip": "2.2.2.2",
                                "port": 8084,
                                "protocol": "https",
                                "adr": "South Korea Seoul",
                            },
                            {
                                "ip": "6.6.6.6",
                                "port": 1080,
                                "protocol": "socks5",
                                "adr": "unknown region",
                            },
                        ]
                    }
                }
            )

            proxies = run_simple_engine(spec)

        self.assertEqual(proxies[0]["country_code"], "US")
        self.assertEqual(proxies[1]["country_code"], "JP")
        self.assertEqual(proxies[2]["country_code"], "US")
        self.assertEqual(proxies[3]["country_code"], "US")
        self.assertEqual(proxies[4]["country_code"], "JP")
        self.assertEqual(proxies[5]["country_code"], "NL")
        self.assertEqual(proxies[6]["country_code"], "KR")
        self.assertEqual(proxies[7]["country_code"], "Unknown")

    def test_simple_engine_should_paginate_until_empty_result(self):
        spec = {
            "request": {
                "url": "https://example.test/api/proxies",
                "method": "GET",
                "params": {
                    "page_size": 2,
                },
            },
            "pagination": {
                "page_param": "page",
                "start_page": 1,
                "max_pages": 5,
                "stop_when_empty": True,
            },
            "extract": {
                "type": "jsonpath",
                "expression": "$.data.items[*]",
            },
            "field_mapping": {
                "ip": "ip",
                "port": "port",
                "protocol": "protocol",
            },
        }

        with patch("src.collectors_v2.execution.engines.simple_engine.requests.request") as mock_request:
            mock_request.side_effect = [
                _FakeResponse(
                    json_data={
                        "data": {
                            "items": [
                                {"ip": "1.1.1.1", "port": 80, "protocol": "http"},
                                {"ip": "2.2.2.2", "port": 81, "protocol": "https"},
                            ]
                        }
                    }
                ),
                _FakeResponse(
                    json_data={
                        "data": {
                            "items": [
                                {"ip": "3.3.3.3", "port": 82, "protocol": "http"},
                            ]
                        }
                    }
                ),
                _FakeResponse(
                    json_data={
                        "data": {
                            "items": []
                        }
                    }
                ),
            ]

            proxies = run_simple_engine(spec)

        self.assertEqual(
            proxies,
            [
                {"ip": "1.1.1.1", "port": 80, "protocol": "http"},
                {"ip": "2.2.2.2", "port": 81, "protocol": "https"},
                {"ip": "3.3.3.3", "port": 82, "protocol": "http"},
            ],
        )
        self.assertEqual(mock_request.call_count, 3)
        self.assertEqual(mock_request.call_args_list[0].kwargs["params"]["page"], 1)
        self.assertEqual(mock_request.call_args_list[1].kwargs["params"]["page"], 2)
        self.assertEqual(mock_request.call_args_list[2].kwargs["params"]["page"], 3)


if __name__ == "__main__":
    unittest.main()
