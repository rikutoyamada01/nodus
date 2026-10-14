"""Run: python -m unittest discover -s scripts -p test_analytics_report.py"""
import os
import unittest
from unittest.mock import Mock, patch

import analytics_report as analytics
import seo_loop
from build_site import build_cloudflare_headers


class AnalyticsChecks(unittest.TestCase):
    def test_beacon_is_allowed_without_inline_scripts(self):
        headers = build_cloudflare_headers()
        self.assertIn("script-src 'self' https://static.cloudflareinsights.com", headers)
        self.assertIn("connect-src 'self' https://cloudflareinsights.com", headers)
        self.assertNotIn("unsafe-inline", headers)

    def test_period_boundaries_and_zero_baseline(self):
        rows = [{"date": "2026-10-06", "clicks": 2}, {"date": "2026-10-07", "clicks": 3}, {"date": "2026-10-14", "clicks": 99}]
        result = analytics.compare_days(rows, "2026-09-30", "2026-10-07", "2026-10-13", ["clicks"])
        self.assertEqual(result["totals"], {"previous": {"clicks": 2}, "current": {"clicks": 3}})
        self.assertEqual(result["change_pct"]["clicks"], 50)
        self.assertIsNone(analytics.compare_days([], "2026-09-30", "2026-10-07", "2026-10-13", ["clicks"])["change_pct"]["clicks"])

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test-only", "CLOUDFLARE_ACCOUNT_ID": "test-account"}, clear=True)
    @patch.object(analytics, "cloudflare_request")
    def test_disabled_collection_is_not_zero_traffic(self, request):
        request.side_effect = [{"result": {"build_config": {"web_analytics_token": None}}}, {"data": {"viewer": {"accounts": [{"rumPageloadEventsAdaptiveGroups": []}]}}}]
        result = analytics.fetch_cloudflare({"site": {"base_url": "https://nodus-lab.pages.dev"}})
        self.assertEqual(result["status"], "collection_disabled")
        self.assertIsNone(result["comparison"])
        self.assertEqual(request.call_args.args[2]["variables"]["host"], "nodus-lab.pages.dev")

    @patch.object(seo_loop, "resolve_gsc_access_token", return_value="")
    @patch.object(seo_loop, "LIVE_GSC_PATH")
    @patch.object(seo_loop, "SAMPLE_GSC_PATH")
    @patch.object(seo_loop, "load_json", return_value={"pages": {}})
    def test_sample_is_explicit_only(self, load, sample_path, live_path, token):
        live_path.exists.return_value = False
        sample_path.exists.return_value = True
        config = {"seo_loop": {"gsc_property_url": "https://nodus-lab.pages.dev/"}}
        result, is_live, _ = seo_loop.load_telemetry(config)
        self.assertEqual(result["source_mode"], "GSC_NOT_CONFIGURED")
        self.assertFalse(is_live)
        load.assert_not_called()
        self.assertEqual(seo_loop.load_telemetry(config, allow_sample=True)[0]["source_mode"], "SAMPLE_TELEMETRY")

    @patch.object(analytics, "OUTPUT", new_callable=Mock)
    @patch.object(analytics, "fetch_cloudflare", side_effect=RuntimeError("test"))
    @patch.object(analytics, "fetch_gsc", return_value={"status": "not_configured"})
    def test_failure_does_not_become_empty_success(self, gsc, cloudflare, output):
        result = analytics.collect()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sources"]["cloudflare"]["status"], "error")
        self.assertNotIn("comparison", result["sources"]["cloudflare"])


if __name__ == "__main__":
    unittest.main()
