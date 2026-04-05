import unittest

from src.testers.baseline import (
    BaselineFingerprint,
    ResponseSnapshot,
    build_baseline_fingerprint,
    dedupe_keep_order,
    evaluate_response_success,
    extract_title,
    hosts_match,
    normalize_content_type,
)


class TestTesterBaseline(unittest.TestCase):
    def test_normalize_content_type_should_strip_charset(self):
        self.assertEqual(normalize_content_type("text/html; charset=utf-8"), "text/html")

    def test_extract_title_should_support_whitespace(self):
        self.assertEqual(
            extract_title("<html><head><title>\n Example Domain \t</title></head></html>"),
            "Example Domain",
        )

    def test_dedupe_keep_order_should_preserve_first_seen_values(self):
        self.assertEqual(
            dedupe_keep_order(["Example", "example", "  Example  ", "Proxy"]),
            ["Example", "Proxy"],
        )

    def test_hosts_match_should_accept_subdomain(self):
        self.assertTrue(hosts_match("example.com", "www.example.com"))
        self.assertFalse(hosts_match("example.com", "example.org"))

    def test_build_baseline_fingerprint_should_prioritize_explicit_keywords(self):
        samples = [
            ResponseSnapshot(
                status_code=200,
                final_url="https://example.com/path",
                content_type="text/html; charset=utf-8",
                body_length=1200,
                text_length=300,
                title="Example Domain",
                text="Example Domain test content.",
            ),
            ResponseSnapshot(
                status_code=200,
                final_url="https://example.com/path",
                content_type="text/html; charset=utf-8",
                body_length=1300,
                text_length=320,
                title="Example Domain",
                text="Example Domain more test content.",
            ),
        ]

        fingerprint = build_baseline_fingerprint(
            samples,
            explicit_keywords=["Example Domain", " proxy ", "example domain"],
        )

        self.assertEqual(fingerprint.host, "example.com")
        self.assertEqual(fingerprint.title, "Example Domain")
        self.assertEqual(fingerprint.content_type_prefix, "text/html")
        self.assertEqual(fingerprint.median_body_length, 1250)
        self.assertEqual(fingerprint.median_text_length, 310)
        self.assertEqual(fingerprint.keywords, ["Example Domain", "proxy"])

    def test_evaluate_response_success_should_accept_matching_response(self):
        baseline = BaselineFingerprint(
            host="example.com",
            title="Example Domain",
            content_type_prefix="text/html",
            median_body_length=1200,
            median_text_length=300,
            keywords=["Example Domain", "testing proxies"],
        )
        response = ResponseSnapshot(
            status_code=200,
            final_url="https://www.example.com/welcome",
            content_type="text/html; charset=utf-8",
            body_length=1220,
            text_length=305,
            title="Example Domain",
            text="This page confirms testing proxies against Example Domain.",
        )

        result = evaluate_response_success(response, baseline)

        self.assertTrue(result.is_success)
        self.assertEqual(result.reasons, [])
        self.assertEqual(result.keyword_hits, ["Example Domain", "testing proxies"])

    def test_evaluate_response_success_should_reject_obvious_block_page(self):
        baseline = BaselineFingerprint(
            host="example.com",
            title="Example Domain",
            content_type_prefix="text/html",
            median_body_length=1200,
            median_text_length=300,
            keywords=["Example Domain", "testing proxies"],
        )
        response = ResponseSnapshot(
            status_code=200,
            final_url="https://blocked.invalid/intercept",
            content_type="text/html; charset=utf-8",
            body_length=280,
            text_length=110,
            title="Access Denied",
            text="Access Denied by policy.",
        )

        result = evaluate_response_success(response, baseline)

        self.assertFalse(result.is_success)
        self.assertIn("host_mismatch", result.reasons)
        self.assertIn("keyword_miss", result.reasons)
        self.assertIn("body_length_out_of_range", result.reasons)


if __name__ == "__main__":
    unittest.main()
