import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src import app_globals
from src.api.endpoints import get_redis_manager
from src.api.main import app
from src.database.models import Proxy
from src.database.redis_client import RedisManager


class TestAPIRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env_patcher = patch.dict(
            os.environ,
            {
                "DISABLE_API_TESTER": "1",
            },
            clear=False,
        )
        cls.env_patcher.start()

        cls.token_patcher = patch.object(app_globals.global_config, "API_TOKEN", "test_api_token")
        cls.token_patcher.start()

        cls.mock_redis_manager = Mock(spec=RedisManager)
        cls.mock_redis_manager.get_all_proxies.return_value = []
        cls.mock_redis_manager.get_all_non_cooldown_proxies.return_value = []
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        cls.mock_redis_manager.get_redis_client.return_value = mock_redis_client

        cls.global_redis_patcher = patch.object(app_globals, "global_redis_manager", cls.mock_redis_manager)
        cls.global_redis_patcher.start()

        app.dependency_overrides[get_redis_manager] = lambda: cls.mock_redis_manager
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides = {}
        cls.global_redis_patcher.stop()
        cls.token_patcher.stop()
        cls.env_patcher.stop()

    def setUp(self):
        self.mock_redis_manager.reset_mock()
        self.mock_redis_manager.get_all_proxies.return_value = []
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = []
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        self.mock_redis_manager.get_redis_client.return_value = mock_redis_client

    def test_health_check_success(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "redis_status": "connected"})

    def test_health_check_redis_down(self):
        mock_redis_client = Mock()
        mock_redis_client.ping.side_effect = Exception("Redis connection failed")
        self.mock_redis_manager.get_redis_client.return_value = mock_redis_client

        response = self.client.get("/health")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Health check failed", response.json()["detail"])

    def test_verify_api_token_success(self):
        response = self.client.get("/api/v1/random", headers={"X-API-Token": "test_api_token"})
        self.assertEqual(response.status_code, 404)

    def test_verify_api_token_missing(self):
        response = self.client.get("/api/v1/random")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or missing API token.")

    def test_verify_api_token_invalid(self):
        response = self.client.get("/api/v1/random", headers={"X-API-Token": "wrong_token"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or missing API token.")

    def test_update_global_config_route_exists(self):
        response = self.client.post(
            "/api/v1/config/global",
            headers={"X-API-Token": "test_api_token"},
            json={"config": {}, "save_to_file": False},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_global_config_should_ignore_env_only_runtime_fields(self):
        response = self.client.post(
            "/api/v1/config/global",
            headers={"X-API-Token": "test_api_token"},
            json={"config": {"API_PORT": 9000, "DASHBOARD_WS_BROADCAST_INTERVAL_SECONDS": 30}, "save_to_file": False},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["updated_keys"], [])
        self.assertEqual(payload["runtime_apply"]["applied_keys"], [])

    def test_runtime_info_should_expose_app_image_tag_without_auth(self):
        with patch.dict(
            os.environ,
            {
                "APP_IMAGE_TAG": "ghcr.io/example/proxypoolmaster:v1.2.3",
                "APP_RELEASE_VERSION": "1.2.3",
                "APP_GIT_SHA": "abc1234",
            },
            clear=False,
        ):
            response = self.client.get("/api/v1/runtime-info")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["image_tag"], "ghcr.io/example/proxypoolmaster:v1.2.3")
        self.assertEqual(payload["label"], "ghcr.io/example/proxypoolmaster:v1.2.3")

    def test_clear_logs_should_truncate_active_log_and_delete_rotated_backups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            active_log_path = os.path.join(temp_dir, "app.log")
            rotated_log_path = os.path.join(temp_dir, "app.log.1")

            with open(active_log_path, "w", encoding="utf-8") as file_handle:
                file_handle.write("hello log\n")
            with open(rotated_log_path, "w", encoding="utf-8") as file_handle:
                file_handle.write("old backup\n")

            with patch("src.api.log_endpoints.get_current_log_file_path", return_value=active_log_path):
                response = self.client.post(
                    "/api/v1/logs/clear",
                    headers={"X-API-Token": "test_api_token"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(os.path.exists(active_log_path))
            with open(active_log_path, "r", encoding="utf-8") as file_handle:
                self.assertEqual(file_handle.read(), "")
            self.assertFalse(os.path.exists(rotated_log_path))

    def test_health_check_should_use_latest_global_redis_manager_after_runtime_swap(self):
        swapped_redis_manager = Mock(spec=RedisManager)
        swapped_client = Mock()
        swapped_client.ping.return_value = True
        swapped_redis_manager.get_redis_client.return_value = swapped_client

        with patch.object(app_globals, "global_redis_manager", swapped_redis_manager):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        swapped_redis_manager.get_redis_client.assert_called_once()

    def test_get_random_proxy_success(self):
        mock_proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http", grade="A"),
            Proxy(ip="8.8.8.8", port=8080, protocol="http", grade="C"),
            Proxy(ip="9.9.9.9", port=8080, protocol="http", grade="D"),
            Proxy(ip="2.2.2.2", port=8080, protocol="https", grade="B"),
        ]
        self.mock_redis_manager.get_all_proxies.return_value = mock_proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = mock_proxies

        response = self.client.get("/api/v1/random", headers={"X-API-Token": "test_api_token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["ip"], {"1.1.1.1", "2.2.2.2"})
        self.assertNotEqual(response.json()["ip"], "8.8.8.8")

    def test_get_random_proxy_not_found(self):
        cooldown_only_proxies = [
            Proxy(ip="9.9.9.9", port=8080, protocol="http", grade="D")
        ]
        self.mock_redis_manager.get_all_proxies.return_value = cooldown_only_proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = []

        response = self.client.get("/api/v1/random", headers={"X-API-Token": "test_api_token"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No available proxies found.")

    def test_get_proxies_with_filters_success(self):
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http", country_code="US", anonymity_level="elite"),
            Proxy(ip="2.2.2.2", port=8080, protocol="https", country_code="CN", anonymity_level="anonymous"),
            Proxy(ip="3.3.3.3", port=8080, protocol="http", country_code="US", anonymity_level="transparent"),
        ]
        self.mock_redis_manager.get_all_proxies.return_value = proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = proxies

        response = self.client.get(
            "/api/v1/get?country_code=US&protocol=http&page=1&size=10",
            headers={"X-API-Token": "test_api_token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["size"], 10)

    def test_get_proxies_with_filters_no_match(self):
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http", country_code="US", anonymity_level="elite")
        ]
        self.mock_redis_manager.get_all_proxies.return_value = proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = proxies

        response = self.client.get(
            "/api/v1/get?country_code=CN&page=1&size=10",
            headers={"X-API-Token": "test_api_token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"], [])
        self.assertEqual(payload["total"], 0)

    def test_get_proxies_with_filters_limit(self):
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http", country_code="US", anonymity_level="elite"),
            Proxy(ip="2.2.2.2", port=8080, protocol="http", country_code="US", anonymity_level="elite"),
            Proxy(ip="3.3.3.3", port=8080, protocol="http", country_code="US", anonymity_level="elite"),
        ]
        self.mock_redis_manager.get_all_proxies.return_value = proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = proxies

        response = self.client.get(
            "/api/v1/get?page=1&size=2",
            headers={"X-API-Token": "test_api_token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        self.assertEqual(len(payload["data"]), 2)

    def test_get_proxies_with_filters_is_available_should_exclude_c_grade(self):
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http", grade="S"),
            Proxy(ip="2.2.2.2", port=8080, protocol="http", grade="B"),
            Proxy(ip="3.3.3.3", port=8080, protocol="http", grade="C"),
            Proxy(ip="4.4.4.4", port=8080, protocol="http", grade="D"),
        ]
        self.mock_redis_manager.get_all_proxies.return_value = proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = proxies

        response = self.client.get(
            "/api/v1/get?is_available=true&page=1&size=10",
            headers={"X-API-Token": "test_api_token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual({item["ip"] for item in payload["data"]}, {"1.1.1.1", "2.2.2.2"})

    def test_get_proxies_with_filters_is_unavailable_should_include_c_and_d(self):
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http", grade="S"),
            Proxy(ip="2.2.2.2", port=8080, protocol="http", grade="B"),
            Proxy(ip="3.3.3.3", port=8080, protocol="http", grade="C"),
            Proxy(ip="4.4.4.4", port=8080, protocol="http", grade="D"),
        ]
        self.mock_redis_manager.get_all_proxies.return_value = proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = proxies

        response = self.client.get(
            "/api/v1/get?is_available=false&page=1&size=10",
            headers={"X-API-Token": "test_api_token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual({item["ip"] for item in payload["data"]}, {"3.3.3.3", "4.4.4.4"})

    def test_get_proxies_with_filters_grade_should_delegate_to_backend_filter(self):
        proxies = [
            Proxy(ip="1.1.1.1", port=8080, protocol="http", grade="A"),
            Proxy(ip="2.2.2.2", port=8080, protocol="http", grade="C"),
            Proxy(ip="3.3.3.3", port=8080, protocol="http", grade="D"),
        ]
        self.mock_redis_manager.get_all_proxies.return_value = proxies
        self.mock_redis_manager.get_all_non_cooldown_proxies.return_value = proxies

        response = self.client.get(
            "/api/v1/get?grade=C&page=1&size=10",
            headers={"X-API-Token": "test_api_token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual({item["ip"] for item in payload["data"]}, {"2.2.2.2"})

    def test_get_proxies_with_filters_should_exclude_cooldown_pool_by_default(self):
        active_proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", country_code="US", anonymity_level="elite")
        cooldown_proxy = Proxy(ip="9.9.9.9", port=8080, protocol="http", country_code="US", anonymity_level="elite")
        self.mock_redis_manager.get_all_proxies.return_value = [active_proxy, cooldown_proxy]
        setattr(
            self.mock_redis_manager,
            "get_all_non_cooldown_proxies",
            Mock(return_value=[active_proxy]),
        )

        response = self.client.get(
            "/api/v1/get?page=1&size=10",
            headers={"X-API-Token": "test_api_token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertNotIn("9.9.9.9", {item["ip"] for item in payload["data"]})

    def test_legacy_collectors_routes_should_not_be_mounted_by_default(self):
        schema = app.openapi()
        self.assertNotIn("/api/v1/collectors", schema["paths"])
        self.assertIn("/api/v1/collectors-v2", schema["paths"])


if __name__ == "__main__":
    unittest.main()
