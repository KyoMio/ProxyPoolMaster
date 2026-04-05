import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from database.models import Proxy


class TestProxyModel(unittest.TestCase):
    def test_proxy_initialization(self):
        now_ts = 1_700_000_000.0
        proxy = Proxy(
            ip="192.168.1.1",
            port=8080,
            protocol="http",
            country_code="US",
            anonymity_level="elite",
            last_check_time=now_ts,
            response_time=0.5,
            success_count=10,
            fail_count=2,
        )

        self.assertEqual(proxy.ip, "192.168.1.1")
        self.assertEqual(proxy.port, 8080)
        self.assertEqual(proxy.protocol, "http")
        self.assertEqual(proxy.country_code, "US")
        self.assertEqual(proxy.anonymity_level, "elite")
        self.assertEqual(proxy.last_check_time, now_ts)
        self.assertEqual(proxy.response_time, 0.5)
        self.assertEqual(proxy.success_count, 10)
        self.assertEqual(proxy.fail_count, 2)

    def test_proxy_default_values(self):
        proxy = Proxy(ip="127.0.0.1", port=3128)

        self.assertEqual(proxy.protocol, "http")
        self.assertEqual(proxy.country_code, "Unknown")
        self.assertEqual(proxy.anonymity_level, "Unknown")
        self.assertIsNone(proxy.last_check_time)
        self.assertIsNone(proxy.response_time)
        self.assertEqual(proxy.success_count, 0)
        self.assertEqual(proxy.fail_count, 0)

    def test_proxy_to_dict(self):
        now_ts = 1_700_000_000.0
        proxy = Proxy(ip="192.168.1.1", port=8080, protocol="https", last_check_time=now_ts)
        proxy_dict = proxy.to_dict()

        self.assertIsInstance(proxy_dict, dict)
        self.assertEqual(proxy_dict["ip"], "192.168.1.1")
        self.assertEqual(proxy_dict["port"], 8080)
        self.assertEqual(proxy_dict["protocol"], "https")
        self.assertEqual(proxy_dict["country_code"], "Unknown")
        self.assertEqual(proxy_dict["anonymity_level"], "Unknown")
        self.assertEqual(proxy_dict["last_check_time"], str(now_ts))
        self.assertEqual(proxy_dict["success_count"], 0)
        self.assertEqual(proxy_dict["fail_count"], 0)
        self.assertEqual(proxy_dict["full_proxy_string"], "https://192.168.1.1:8080")
        self.assertNotIn("response_time", proxy_dict)

    def test_proxy_from_dict(self):
        proxy_dict = {
            "ip": "10.0.0.1",
            "port": 9000,
            "protocol": "socks5",
            "country_code": "CN",
            "anonymity_level": "transparent",
            "last_check_time": "1700000000.0",
            "response_time": "1.2",
            "success_count": "5",
            "fail_count": "1",
            "score": "88",
            "grade": "A",
        }
        proxy = Proxy.from_dict(proxy_dict)

        self.assertIsInstance(proxy, Proxy)
        self.assertEqual(proxy.ip, "10.0.0.1")
        self.assertEqual(proxy.port, 9000)
        self.assertEqual(proxy.protocol, "socks5")
        self.assertEqual(proxy.country_code, "CN")
        self.assertEqual(proxy.anonymity_level, "transparent")
        self.assertEqual(proxy.last_check_time, 1700000000.0)
        self.assertEqual(proxy.response_time, 1.2)
        self.assertEqual(proxy.success_count, 5)
        self.assertEqual(proxy.fail_count, 1)
        self.assertEqual(proxy.score, 88)
        self.assertEqual(proxy.grade, "A")

    def test_proxy_from_dict_with_missing_optional_fields(self):
        proxy_dict = {
            "ip": "11.22.33.44",
            "port": 8888,
        }
        proxy = Proxy.from_dict(proxy_dict)

        self.assertEqual(proxy.ip, "11.22.33.44")
        self.assertEqual(proxy.port, 8888)
        self.assertEqual(proxy.protocol, "http")
        self.assertEqual(proxy.country_code, "Unknown")
        self.assertIsNone(proxy.last_check_time)
        self.assertIsNone(proxy.response_time)
        self.assertEqual(proxy.success_count, 0)
        self.assertEqual(proxy.fail_count, 0)

    def test_proxy_equality_and_hash(self):
        proxy1 = Proxy(ip="1.1.1.1", port=80, protocol="http")
        proxy2 = Proxy(ip="1.1.1.1", port=80, protocol="http")
        proxy3 = Proxy(ip="2.2.2.2", port=80, protocol="http")
        proxy4 = Proxy(ip="1.1.1.1", port=443, protocol="https")

        self.assertEqual(proxy1, proxy2)
        self.assertNotEqual(proxy1, proxy3)
        self.assertNotEqual(proxy1, proxy4)

        self.assertEqual(hash(proxy1), hash(proxy2))
        self.assertNotEqual(hash(proxy1), hash(proxy3))
        self.assertNotEqual(hash(proxy1), hash(proxy4))

        proxy_set = {proxy1}
        self.assertIn(proxy2, proxy_set)
        self.assertNotIn(proxy3, proxy_set)


if __name__ == "__main__":
    unittest.main()
