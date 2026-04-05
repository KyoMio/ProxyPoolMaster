import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.testers.async_tester import AsyncHttpTester, SOCKS_SUPPORT


class TestAsyncTesterCompatibility(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = SimpleNamespace(
            TEST_TIMEOUT_PER_TARGET=1,
            TEST_TARGETS=["http://example.com", "http://example.org"],
        )
        self.logger = Mock()
        self.tester = AsyncHttpTester(self.config, self.logger)

    async def asyncTearDown(self):
        if getattr(self.tester, "connector", None) and not self.tester.connector.closed:
            await self.tester.connector.close()

    async def test_http_proxy_connector_should_return_proxy_url(self):
        connector, proxy_url = self.tester._get_proxy_connector("http", "1.1.1.1", 8080)
        self.assertIsNone(connector)
        self.assertEqual(proxy_url, "http://1.1.1.1:8080")

    async def test_unsupported_protocol_should_return_failed_results(self):
        result = await self.tester.test_proxy_async("1.1.1.1", 8080, "ftp")
        self.assertEqual(result.total_targets, 2)
        self.assertTrue(all(not item.success for item in result.target_results))
        self.assertTrue(all("Unsupported protocol" in (item.error or "") for item in result.target_results))

    async def test_socks_connector_behavior_should_match_dependency_state(self):
        connector, proxy_url = self.tester._get_proxy_connector("socks5", "1.1.1.1", 1080)
        if SOCKS_SUPPORT:
            self.assertIsNotNone(connector)
            self.assertIsNone(proxy_url)
            await connector.close()
        else:
            self.assertIsNone(connector)
            self.assertIsNone(proxy_url)


if __name__ == "__main__":
    unittest.main()
