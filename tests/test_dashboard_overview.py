import asyncio
import time
import unittest
from unittest.mock import Mock, patch

from src.api.dashboard_endpoints import get_dashboard_overview
from src.database.models import Proxy


class TestDashboardOverview(unittest.TestCase):
    def test_get_dashboard_overview_should_use_latest_proxy_check_time_as_last_updated(self):
        redis_manager = Mock()
        redis_manager.get_all_proxies.return_value = [
            Proxy(
                ip="1.1.1.1",
                port=80,
                protocol="http",
                country_code="CN",
                anonymity_level="high",
                last_check_time=1_700_000_000,
                response_time=0.2,
                grade="A",
            ),
            Proxy(
                ip="2.2.2.2",
                port=8080,
                protocol="https",
                country_code="US",
                anonymity_level="elite",
                last_check_time=1_700_000_300,
                response_time=0.1,
                grade="S",
            ),
        ]

        with patch("src.api.dashboard_endpoints.time.time", return_value=1_700_001_000):
            overview = asyncio.run(get_dashboard_overview(redis_manager))

        self.assertEqual(
            overview["last_updated"],
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(1_700_000_300)),
        )

    def test_get_dashboard_overview_should_exclude_cooldown_pool_from_totals(self):
        redis_manager = Mock()
        active_proxy = Proxy(
            ip="1.1.1.1",
            port=80,
            protocol="http",
            country_code="CN",
            anonymity_level="elite",
            last_check_time=1_700_000_000,
            response_time=0.2,
            grade="A",
        )
        cooldown_proxy = Proxy(
            ip="2.2.2.2",
            port=8080,
            protocol="https",
            country_code="US",
            anonymity_level="elite",
            last_check_time=1_700_000_300,
            response_time=0.1,
            grade="S",
        )
        redis_manager.get_all_proxies.return_value = [active_proxy, cooldown_proxy]
        redis_manager.get_all_non_cooldown_proxies = Mock(return_value=[active_proxy])

        with patch("src.api.dashboard_endpoints.time.time", return_value=1_700_001_000):
            overview = asyncio.run(get_dashboard_overview(redis_manager))

        self.assertEqual(overview["total_proxies"], 1)
        self.assertEqual(overview["available_proxies"], 1)
        self.assertEqual(overview.get("cooldown_pool_count"), 1)
        self.assertEqual(overview["available_grade_distribution"].get("A"), 1)
        self.assertEqual(overview["available_grade_distribution"].get("S"), 0)

    def test_get_dashboard_overview_should_only_count_b_and_above_as_available(self):
        redis_manager = Mock()
        redis_manager.get_all_non_cooldown_proxies.return_value = [
            Proxy(
                ip="1.1.1.1",
                port=80,
                protocol="http",
                country_code="CN",
                anonymity_level="elite",
                last_check_time=1_700_000_000,
                response_time=0.2,
                grade="S",
            ),
            Proxy(
                ip="2.2.2.2",
                port=8080,
                protocol="https",
                country_code="US",
                anonymity_level="elite",
                last_check_time=1_700_000_100,
                response_time=0.3,
                grade="B",
            ),
            Proxy(
                ip="3.3.3.3",
                port=9000,
                protocol="http",
                country_code="JP",
                anonymity_level="anonymous",
                last_check_time=1_700_000_200,
                response_time=0.4,
                grade="C",
            ),
        ]

        overview = asyncio.run(get_dashboard_overview(redis_manager))

        self.assertEqual(overview["total_proxies"], 3)
        self.assertEqual(overview["available_proxies"], 2)
        self.assertEqual(overview["available_grade_distribution"].get("S"), 1)
        self.assertEqual(overview["available_grade_distribution"].get("B"), 1)
        self.assertNotIn("C", overview["available_grade_distribution"])


if __name__ == "__main__":
    unittest.main()
