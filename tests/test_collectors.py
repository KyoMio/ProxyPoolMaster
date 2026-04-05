import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.collectors.zdaye_collector import ZdayeCollector
from src.collectors.zdaye_overseas_collector import ZdayeOverseasCollector


class TestZdayeCollectors(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            ZDAYE_APP_ID="app-id",
            ZDAYE_AKEY="akey",
            REQUEST_TIMEOUT=3,
        )
        self.logger = Mock()

    @patch("src.collectors.zdaye_collector.requests.get")
    def test_zdaye_collector_fetch_proxies_success(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "code": "10001",
            "data": {
                "proxy_list": [
                    {"ip": "1.1.1.1", "port": "8080", "protocol": "http", "level": "elite"},
                    {"ip": "2.2.2.2", "port": "3128", "protocol": "https", "level": "anonymous"},
                ]
            },
        }
        mock_get.return_value = mock_response

        collector = ZdayeCollector(self.config, self.logger)
        proxies = collector.fetch_proxies()

        self.assertEqual(len(proxies), 2)
        self.assertEqual(proxies[0].ip, "1.1.1.1")
        self.assertEqual(proxies[0].country_code, "CN")
        self.assertEqual(proxies[1].protocol, "https")

        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["dalu"], 1)

    def test_zdaye_collector_should_return_empty_when_credential_missing(self):
        bad_cfg = SimpleNamespace(ZDAYE_APP_ID="", ZDAYE_AKEY="", REQUEST_TIMEOUT=3)
        collector = ZdayeCollector(bad_cfg, self.logger)
        self.assertEqual(collector.fetch_proxies(), [])

    @patch("src.collectors.zdaye_overseas_collector.requests.get")
    def test_zdaye_overseas_collector_fetch_proxies_should_map_country_code(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "code": "10001",
            "data": {
                "proxy_list": [
                    {
                        "ip": "8.8.8.8",
                        "port": "443",
                        "protocol": "https",
                        "level": "elite",
                        "adr": "美国 洛杉矶",
                    }
                ]
            },
        }
        mock_get.return_value = mock_response

        collector = ZdayeOverseasCollector(self.config, self.logger)
        proxies = collector.fetch_proxies()

        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies[0].country_code, "US")
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["dalu"], 0)

    def test_zdaye_overseas_country_extraction(self):
        collector = ZdayeOverseasCollector(self.config, self.logger)
        self.assertEqual(collector._extract_country_from_adr("韩国 KT电信"), "韩国")
        self.assertEqual(collector._country_name_to_code("美国"), "US")


if __name__ == "__main__":
    unittest.main()
