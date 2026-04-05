import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
from threading import Thread
import time

from src.collectors_v2.execution.runner import run_execution_subprocess


class _StaticHandler(BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        status, headers, body = self.routes.get(
            self.path,
            (404, {"Content-Type": "text/plain; charset=utf-8"}, "not found"),
        )
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        return


@contextmanager
def _serve_routes(routes):
    _StaticHandler.routes = routes
    server = HTTPServer(("127.0.0.1", 0), _StaticHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        deadline = time.time() + 1.0
        while True:
            try:
                with socket.create_connection((host, port), timeout=0.1):
                    break
            except OSError:
                if time.time() >= deadline:
                    raise
                time.sleep(0.01)
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestCollectorsV2SubprocessRunner(unittest.TestCase):
    def _build_simple_jsonpath_payload(self, url):
        return {
            "run_id": "run-simple-jsonpath",
            "trigger": "test",
            "collector": {
                "id": "demo-jsonpath",
                "mode": "simple",
                "spec": {
                    "request": {"url": url, "method": "GET"},
                    "extract": {"type": "jsonpath", "expression": "$.data.items[*]"},
                    "field_mapping": {
                        "ip": "ip",
                        "port": "port",
                        "protocol": "protocol",
                    },
                },
            },
        }

    def test_subprocess_runner_should_return_success(self):
        payload = {
            "run_id": "run-subprocess-ok",
            "trigger": "test",
            "collector": {
                "id": "demo",
                "mode": "simple",
                "spec": {
                    "proxies": [
                        {"ip": "3.3.3.3", "port": 8080, "protocol": "http"},
                    ]
                },
            },
        }

        result = run_execution_subprocess(payload, timeout_seconds=3)
        self.assertTrue(result["success"])
        self.assertEqual(result["valid_count"], 1)

    def test_subprocess_runner_should_timeout(self):
        payload = {
            "run_id": "run-subprocess-timeout",
            "trigger": "test",
            "collector": {
                "id": "demo-timeout",
                "mode": "simple",
                "spec": {
                    "sleep_seconds": 2,
                    "proxies": [{"ip": "4.4.4.4", "port": 80, "protocol": "http"}],
                },
            },
        }

        result = run_execution_subprocess(payload, timeout_seconds=1)
        self.assertFalse(result["success"])
        self.assertTrue(any("timeout" in err.lower() for err in result["errors"]))

    def test_subprocess_runner_should_handle_empty_result(self):
        with _serve_routes(
            {
                "/empty": (
                    200,
                    {"Content-Type": "application/json; charset=utf-8"},
                    '{"data":{"items":[]}}',
                )
            }
        ) as base_url:
            payload = self._build_simple_jsonpath_payload(f"{base_url}/empty")
            result = run_execution_subprocess(payload, timeout_seconds=3)

        self.assertTrue(result["success"])
        self.assertEqual(result["raw_count"], 0)
        self.assertEqual(result["valid_count"], 0)
        self.assertEqual(result["stored_count"], 0)
        self.assertEqual(result["errors"], [])

    def test_subprocess_runner_should_handle_all_invalid_result(self):
        with _serve_routes(
            {
                "/invalid": (
                    200,
                    {"Content-Type": "application/json; charset=utf-8"},
                    '{"data":{"items":[{"ip":"21.21.21.21","port":"bad","protocol":"http"}]}}',
                )
            }
        ) as base_url:
            payload = self._build_simple_jsonpath_payload(f"{base_url}/invalid")
            result = run_execution_subprocess(payload, timeout_seconds=3)

        self.assertTrue(result["success"])
        self.assertEqual(result["raw_count"], 1)
        self.assertEqual(result["valid_count"], 0)
        self.assertGreaterEqual(len(result["errors"]), 1)

    def test_subprocess_runner_should_fail_on_json_parse_error(self):
        with _serve_routes(
            {
                "/bad-json": (
                    200,
                    {"Content-Type": "application/json; charset=utf-8"},
                    '{"data":',
                )
            }
        ) as base_url:
            payload = self._build_simple_jsonpath_payload(f"{base_url}/bad-json")
            result = run_execution_subprocess(payload, timeout_seconds=3)

        self.assertFalse(result["success"])
        self.assertEqual(result["raw_count"], 0)
        self.assertEqual(result["valid_count"], 0)
        self.assertTrue(any("json" in err.lower() for err in result["errors"]))


if __name__ == "__main__":
    unittest.main()
