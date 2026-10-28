"""Run: python -m unittest discover -s scripts -p test_analytics_report.py"""
import os
import unittest
from datetime import datetime, timezone
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

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test-only", "CLOUDFLARE_ACCOUNT_ID": "test-account"}, clear=True)
    @patch.object(analytics, "cloudflare_request")
    def test_enabled_but_empty_collection_stays_unknown(self, request):
        request.side_effect = [{"result": {"build_config": {"web_analytics_token": "test-beacon"}}}, {"data": {"viewer": {"accounts": [{"rumPageloadEventsAdaptiveGroups": []}]}}}]
        result = analytics.fetch_cloudflare({"site": {"base_url": "https://nodus-lab.pages.dev"}})
        self.assertEqual(result["status"], "no_observations")
        self.assertIsNone(result["comparison"])
        self.assertEqual(result["rows"], [])
        self.assertIn("start", result["window"])

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test-only", "CLOUDFLARE_ACCOUNT_ID": "test-account"}, clear=True)
    @patch.object(analytics, "cloudflare_request")
    def test_cloudflare_breakdowns_and_aliased_queries(self, request):
        account_data = {
            "daily": [{"dimensions": {"date": "2026-10-16"}, "count": 10, "sum": {"visits": 10}}],
            "pages": [{"dimensions": {"requestPath": "/articles/foo.html"}, "count": 6, "sum": {"visits": 6}}, {"dimensions": {"requestPath": "/"}, "count": 4, "sum": {"visits": 4}}],
            "referrers": [{"dimensions": {"refererHost": None}, "count": 8, "sum": {"visits": 8}}, {"dimensions": {"refererHost": "google.com"}, "count": 2, "sum": {"visits": 2}}],
            "countries": [{"dimensions": {"countryName": "Japan"}, "count": 10, "sum": {"visits": 10}}],
            "devices": [{"dimensions": {"deviceType": "desktop"}, "count": 10, "sum": {"visits": 10}}],
            "browsers": [{"dimensions": {"userAgentBrowser": "Chrome"}, "count": 10, "sum": {"visits": 10}}],
            "operating_systems": [{"dimensions": {"userAgentOS": "Windows"}, "count": 10, "sum": {"visits": 10}}],
        }
        request.side_effect = [
            {"result": {"build_config": {"web_analytics_token": "test-beacon"}}},
            {"data": {"viewer": {"accounts": [account_data]}}},
        ]
        result = analytics.fetch_cloudflare({"site": {"base_url": "https://nodus-lab.pages.dev"}})
        self.assertEqual(result["status"], "live")
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["pageviews"], 10)
        self.assertIn("breakdowns", result)
        self.assertEqual(result["breakdowns"]["page"][0], {"page": "/articles/foo.html", "pageviews": 6, "visits": 6})
        self.assertEqual(result["breakdowns"]["referer"][0], {"referer": "(direct / none)", "pageviews": 8, "visits": 8})
        self.assertEqual(result["breakdowns"]["referer"][1], {"referer": "google.com", "pageviews": 2, "visits": 2})
        self.assertEqual(result["breakdowns"]["country"][0], {"country": "Japan", "pageviews": 10, "visits": 10})
        self.assertEqual(result["breakdowns"]["device"][0], {"device": "desktop", "pageviews": 10, "visits": 10})
        self.assertEqual(result["breakdowns"]["browser"][0], {"browser": "Chrome", "pageviews": 10, "visits": 10})
        self.assertEqual(result["breakdowns"]["operating_system"][0], {"operating_system": "Windows", "pageviews": 10, "visits": 10})
        self.assertIn("audit", result)
        self.assertEqual(result["audit"]["clean_external_traffic"]["visits"], 10)

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test-only", "CLOUDFLARE_ACCOUNT_ID": "test-account"}, clear=True)
    @patch.object(analytics, "cloudflare_request")
    def test_cloudflare_audit_detects_pure_self_verification(self, request):
        account_data = {
            "daily": [{"dimensions": {"date": "2026-10-16"}, "count": 10, "sum": {"visits": 10}}],
            "pages": [{"dimensions": {"requestPath": "/"}, "count": 10, "sum": {"visits": 10}}],
            "referrers": [{"dimensions": {"refererHost": None}, "count": 10, "sum": {"visits": 10}}],
            "countries": [{"dimensions": {"countryName": "JP"}, "count": 10, "sum": {"visits": 10}}],
            "devices": [{"dimensions": {"deviceType": "desktop"}, "count": 10, "sum": {"visits": 10}}],
            "browsers": [{"dimensions": {"userAgentBrowser": "Chrome"}, "count": 10, "sum": {"visits": 10}}],
            "operating_systems": [{"dimensions": {"userAgentOS": "Windows"}, "count": 10, "sum": {"visits": 10}}],
        }
        request.side_effect = [
            {"result": {"build_config": {"web_analytics_token": "test-beacon"}}},
            {"data": {"viewer": {"accounts": [account_data]}}},
        ]
        result = analytics.fetch_cloudflare({"site": {"base_url": "https://nodus-lab.pages.dev"}})
        self.assertEqual(result["audit"]["verified_self_traffic"]["visits"], 10)
        self.assertEqual(result["audit"]["clean_external_traffic"]["visits"], 0)
        self.assertIsNotNone(result["audit"]["verified_self_traffic"]["detected_signature"])



    @patch.object(analytics, "datetime", wraps=datetime)
    @patch.object(analytics, "resolve_gsc_access_token", return_value="test-only")
    @patch.object(analytics, "_gsc_query_rest")
    def test_gsc_windows_breakdowns_and_independent_site_totals(self, query, token, clock):
        # UTC has crossed midnight; Search Console's reporting day has not.
        clock.now.return_value = datetime(2026, 10, 15, 1, tzinfo=timezone.utc)

        def respond(prop, access_token, request):
            dimensions = request["dimensions"]
            values = {"date": request["endDate"], "query": "mac llm ローカル", "page": "https://nodus-lab.pages.dev/", "country": "jpn", "device": "DESKTOP"}
            impressions = 9 if not dimensions else 1
            result = {"rows": [{"keys": [values[d] for d in dimensions], "clicks": 0, "impressions": impressions, "ctr": 0.0, "position": 99.0}], "responseAggregationType": "byPage" if "page" in dimensions else "byProperty"}
            if dimensions == ["date"] and request["dataState"] == "all":
                result["metadata"] = {"first_incomplete_date": "2026-10-13"}
            return result

        query.side_effect = respond
        result = analytics.fetch_gsc({"seo_loop": {"gsc_property_url": "https://nodus-lab.pages.dev/"}})
        final, recent = result["windows"]["final"], result["windows"]["recent"]
        self.assertEqual(final["window"], {"start": "2026-09-14", "end": "2026-10-11", "dataState": "final", "type": "web"})
        self.assertEqual(recent["window"], {"start": "2026-10-08", "end": "2026-10-14", "dataState": "all", "type": "web"})
        self.assertEqual(recent["daily"]["metadata"]["first_incomplete_date"], "2026-10-13")
        self.assertEqual(result["rows"], final["daily"]["rows"])
        self.assertEqual(result["comparison"]["totals"]["current"]["impressions"], 1)
        self.assertEqual(final["site_totals"]["rows"][0]["impressions"], 9)
        self.assertEqual(set(final["breakdowns"]), {"query", "page", "query_page", "country", "device"})
        pair = final["breakdowns"]["query_page"]["rows"][0]
        self.assertEqual(pair["query"], "mac llm ローカル")
        self.assertEqual(pair["page"], "https://nodus-lab.pages.dev/")
        self.assertEqual({m: pair[m] for m in ("clicks", "impressions", "ctr", "position")}, {"clicks": 0, "impressions": 1, "ctr": 0.0, "position": 99.0})
        self.assertEqual(query.call_count, 14)

    @patch.object(analytics, "GSC_ROW_LIMIT", 2)
    @patch.object(analytics, "_gsc_query_rest")
    def test_gsc_paginates_breakdowns(self, query):
        rows = [{"keys": [q], "clicks": 0, "impressions": 1, "ctr": 0.0, "position": 99.0} for q in ["first", "second", "third"]]
        query.side_effect = [{"rows": rows[:2], "responseAggregationType": "byProperty"}, {"rows": rows[2:]}]
        result = analytics.fetch_gsc_table("test-property", "test-only", {"dataState": "final"}, ["query"])
        self.assertEqual([row["query"] for row in result["rows"]], ["first", "second", "third"])
        self.assertEqual([call.args[2]["startRow"] for call in query.call_args_list], [0, 2])
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(result["response_aggregation_type"], "byProperty")

    @patch.object(analytics, "resolve_gsc_access_token", return_value="test-only")
    @patch.object(analytics, "_gsc_query_rest")
    def test_recent_observations_do_not_enter_final_comparison(self, query, token):
        query.side_effect = lambda prop, access_token, request: {"rows": [{"keys": [request["endDate"]], "clicks": 0, "impressions": 1, "ctr": 0.0, "position": 99.0}]} if request["dataState"] == "all" and request["dimensions"] == ["date"] else {}
        result = analytics.fetch_gsc({"seo_loop": {"gsc_property_url": "test-property"}})
        self.assertEqual(result["status"], "live")
        self.assertEqual(result["windows"]["final"]["status"], "no_observations")
        self.assertIsNone(result["comparison"])
        self.assertEqual(result["rows"], [])

    @patch.object(analytics, "_gsc_query_rest", return_value={"error": {"code": 403}})
    def test_gsc_error_body_does_not_become_empty_traffic(self, query):
        with self.assertRaises(RuntimeError):
            analytics.fetch_gsc_table("test-property", "test-only", {}, ["query"])

    @patch.object(analytics, "_gsc_query_rest", return_value={"rows": [{"keys": ["test-query"], "clicks": 0, "impressions": 1}]})
    def test_incomplete_metrics_are_not_filled_with_zero(self, query):
        with self.assertRaises(KeyError):
            analytics.fetch_gsc_table("test-property", "test-only", {}, ["query"])

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

    def test_gsc_sitemap_skips_redundant_put_when_already_registered(self):
        import json
        import urllib.error
        from unittest.mock import MagicMock
        import ping_index

        get_resp = MagicMock()
        get_resp.status = 200
        get_resp.read.return_value = json.dumps(
            {
                "path": "https://nodus-lab.pages.dev/sitemap.xml",
                "lastSubmitted": "2026-10-27T00:15:50Z",
                "lastDownloaded": None,
                "isPending": True,
                "errors": "0",
                "warnings": "0",
            }
        ).encode("utf-8")
        get_resp.__enter__.return_value = get_resp

        with patch.object(ping_index.urllib.request, "urlopen", return_value=get_resp) as mock_open:
            res = ping_index.submit_gsc_sitemap(
                "https://nodus-lab.pages.dev/",
                "https://nodus-lab.pages.dev/sitemap.xml",
                "test-token",
            )
            self.assertEqual(res["status"], "already_registered")
            self.assertTrue(res["is_pending"])
            self.assertEqual(mock_open.call_count, 1)
            self.assertEqual(mock_open.call_args.args[0].get_method(), "GET")

        put_resp = MagicMock()
        put_resp.status = 204
        put_resp.__enter__.return_value = put_resp
        not_found = urllib.error.HTTPError(
            url="https://www.googleapis.com/", code=404, msg="Not Found", hdrs=None, fp=None
        )
        with patch.object(ping_index.urllib.request, "urlopen", side_effect=[not_found, put_resp]) as mock_open2:
            res2 = ping_index.submit_gsc_sitemap(
                "https://nodus-lab.pages.dev/",
                "https://nodus-lab.pages.dev/sitemap.xml",
                "test-token",
            )
            self.assertEqual(res2["status"], "submitted")
            self.assertEqual(mock_open2.call_count, 2)
            self.assertEqual(mock_open2.call_args_list[0].args[0].get_method(), "GET")
            self.assertEqual(mock_open2.call_args_list[1].args[0].get_method(), "PUT")


if __name__ == "__main__":
    unittest.main()
