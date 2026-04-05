import unittest
from argparse import Namespace
from unittest.mock import Mock, patch

from scripts.check_proxy_pool_availability import (
    AttemptResult,
    BaselineFingerprint,
    ResponseSnapshot,
    build_baseline_fingerprint,
    build_requests_proxies,
    evaluate_response_success,
    fetch_available_proxy_payloads,
    parse_args,
    run_rounds,
)


class TestCheckProxyPoolAvailability(unittest.TestCase):
    def test_build_baseline_fingerprint_should_use_explicit_keywords(self):
        samples = [
            ResponseSnapshot(
                status_code=200,
                final_url="https://example.com/welcome",
                content_type="text/html; charset=utf-8",
                body_length=1200,
                text_length=320,
                title="Example Domain",
                text="Example Domain is a sample page for testing proxies.",
            ),
            ResponseSnapshot(
                status_code=200,
                final_url="https://example.com/welcome",
                content_type="text/html; charset=utf-8",
                body_length=1230,
                text_length=330,
                title="Example Domain",
                text="Example Domain is still stable enough for keyword extraction.",
            ),
        ]

        fingerprint = build_baseline_fingerprint(
            samples,
            explicit_keywords=["Example Domain", "testing proxies"],
        )

        self.assertEqual(fingerprint.host, "example.com")
        self.assertEqual(fingerprint.title, "Example Domain")
        self.assertEqual(fingerprint.median_body_length, 1215)
        self.assertEqual(fingerprint.keywords, ["Example Domain", "testing proxies"])

    def test_evaluate_response_success_should_accept_matching_content(self):
        fingerprint = BaselineFingerprint(
            host="example.com",
            title="Example Domain",
            content_type_prefix="text/html",
            median_body_length=1200,
            median_text_length=320,
            keywords=["Example Domain", "testing proxies"],
        )
        response = ResponseSnapshot(
            status_code=200,
            final_url="https://example.com/welcome?from=proxy",
            content_type="text/html; charset=utf-8",
            body_length=1260,
            text_length=315,
            title="Example Domain",
            text="This proxy reached Example Domain successfully for testing proxies today.",
        )

        result = evaluate_response_success(response, fingerprint)

        self.assertTrue(result.is_success)
        self.assertEqual(result.reasons, [])
        self.assertEqual(result.keyword_hits, ["Example Domain", "testing proxies"])

    def test_evaluate_response_success_should_reject_obvious_error_page(self):
        fingerprint = BaselineFingerprint(
            host="example.com",
            title="Example Domain",
            content_type_prefix="text/html",
            median_body_length=1200,
            median_text_length=320,
            keywords=["Example Domain", "testing proxies"],
        )
        response = ResponseSnapshot(
            status_code=200,
            final_url="https://malicious-proxy.invalid/block",
            content_type="text/html; charset=utf-8",
            body_length=320,
            text_length=120,
            title="Access Denied",
            text="Access Denied by upstream firewall.",
        )

        result = evaluate_response_success(response, fingerprint)

        self.assertFalse(result.is_success)
        self.assertIn("host_mismatch", result.reasons)
        self.assertIn("keyword_miss", result.reasons)
        self.assertIn("body_length_out_of_range", result.reasons)

    def test_build_requests_proxies_should_map_both_http_and_https(self):
        proxies = build_requests_proxies({"ip": "1.2.3.4", "port": 8080})

        self.assertEqual(
            proxies,
            {
                "http": "http://1.2.3.4:8080",
                "https": "http://1.2.3.4:8080",
            },
        )

    def test_parse_args_should_use_longer_default_timeouts(self):
        args = parse_args(
            [
                "--target-url",
                "https://example.com",
                "--api-token",
                "test-token",
            ]
        )

        self.assertEqual(args.timeout, 20.0)
        self.assertEqual(args.api_timeout, 10.0)
        self.assertEqual(args.rounds, 3)
        self.assertEqual(args.round_interval, 10.0)

    def test_fetch_available_proxy_payloads_should_collect_all_pages(self):
        page_one = Mock()
        page_one.raise_for_status = Mock()
        page_one.json.return_value = {
            "data": [
                {"ip": "1.1.1.1", "port": 80, "protocol": "http", "grade": "A"},
                {"ip": "2.2.2.2", "port": 81, "protocol": "https", "grade": "B"},
            ],
            "total": 3,
            "page": 1,
            "size": 2,
        }
        page_two = Mock()
        page_two.raise_for_status = Mock()
        page_two.json.return_value = {
            "data": [
                {"ip": "3.3.3.3", "port": 82, "protocol": "http", "grade": "S"},
            ],
            "total": 3,
            "page": 2,
            "size": 2,
        }
        mock_session = Mock()
        mock_session.get.side_effect = [page_one, page_two]
        rate_limiter = Mock()

        with patch("scripts.check_proxy_pool_availability.get_session", return_value=mock_session):
            proxies = fetch_available_proxy_payloads(
                "http://127.0.0.1:8000/api/v1",
                "token",
                timeout=10.0,
                verify_tls=True,
                user_agent="ua",
                rate_limiter=rate_limiter,
                page_size=2,
            )

        self.assertEqual(len(proxies), 3)
        self.assertEqual([proxy["ip"] for proxy in proxies], ["1.1.1.1", "2.2.2.2", "3.3.3.3"])
        self.assertEqual(rate_limiter.wait.call_count, 2)
        first_call = mock_session.get.call_args_list[0]
        self.assertEqual(first_call.args[0], "http://127.0.0.1:8000/api/v1/get")
        self.assertEqual(first_call.kwargs["params"]["is_available"], "true")
        self.assertEqual(first_call.kwargs["params"]["page"], 1)
        self.assertEqual(first_call.kwargs["params"]["size"], 2)

    def test_run_rounds_should_retest_same_proxy_set_three_times_with_interval(self):
        args = Namespace(
            rounds=3,
            round_interval=10.0,
            workers=2,
            total=0,
        )
        baseline = BaselineFingerprint(
            host="example.com",
            title="Example Domain",
            content_type_prefix="text/html",
            median_body_length=1200,
            median_text_length=320,
            keywords=["Example Domain"],
        )
        proxy_payloads = [
            {"ip": "1.1.1.1", "port": 80, "protocol": "http", "grade": "A"},
            {"ip": "2.2.2.2", "port": 81, "protocol": "http", "grade": "B"},
        ]

        def fake_attempt(attempt_id, round_number, proxy_payload, passed_args, passed_baseline):
            return AttemptResult(
                attempt_id=attempt_id,
                round_number=round_number,
                proxy_label=f"{proxy_payload['ip']}:{proxy_payload['port']}",
                is_success=True,
                latency_ms=100.0,
                status_code=200,
                reasons=[],
                keyword_hits=["Example Domain"],
            )

        with patch("scripts.check_proxy_pool_availability.run_single_attempt_for_proxy", side_effect=fake_attempt) as mocked_attempt, patch(
            "scripts.check_proxy_pool_availability.time.sleep"
        ) as mocked_sleep:
            results = run_rounds(args, baseline, proxy_payloads)

        self.assertEqual(len(results), 6)
        self.assertEqual([result.round_number for result in results], [1, 1, 2, 2, 3, 3])
        self.assertEqual(mocked_attempt.call_count, 6)
        self.assertEqual(mocked_sleep.call_count, 2)
        mocked_sleep.assert_called_with(10.0)
        called_proxy_ips = [call.args[2]["ip"] for call in mocked_attempt.call_args_list]
        self.assertEqual(called_proxy_ips, ["1.1.1.1", "2.2.2.2", "1.1.1.1", "2.2.2.2", "1.1.1.1", "2.2.2.2"])


if __name__ == "__main__":
    unittest.main()
