#!/usr/bin/env python3
"""Read actual Cloudflare Web Analytics and Search Console metrics; never use samples.

Reports stay outside dist/ and are uploaded as private Actions artifacts.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from seo_loop import CONFIG_PATH, _gsc_query_rest, load_json, resolve_gsc_access_token

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "analytics" / "latest.json"
GSC_ROW_LIMIT = 25000


def cloudflare_request(path: str, token: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Cloudflare HTTP {error.code}; check token validity and analytics read permissions") from None
    if result.get("errors") or result.get("success") is False:
        # Do not echo arbitrary API response bodies or credentials into Actions logs.
        raise RuntimeError("Cloudflare API rejected the query; check dataset access and token permissions")
    return result


def compare_days(rows: list[dict], start: str, split: str, end: str, metrics: list[str]) -> dict:
    periods = {"previous": {m: 0 for m in metrics}, "current": {m: 0 for m in metrics}}
    for row in rows:
        day = row["date"]
        if start <= day <= end:
            period = "previous" if day < split else "current"
            for metric in metrics:
                periods[period][metric] += row[metric]
    return {
        "periods": {"previous": {"start": start, "end": (datetime.fromisoformat(split) - timedelta(days=1)).date().isoformat()}, "current": {"start": split, "end": end}},
        "totals": periods,
        "change_pct": {m: round((periods["current"][m] / periods["previous"][m] - 1) * 100, 1) if periods["previous"][m] else None for m in metrics},
        "note": "A zero baseline has no percentage change. Empty rows mean no recorded observations, not proof of no visitors.",
    }


def fetch_cloudflare(config: dict) -> dict:
    token = os.environ.get("CLOUDFLARE_ANALYTICS_API_TOKEN", "").strip() or os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not token or not account:
        return {"status": "not_configured", "required": ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_ANALYTICS_API_TOKEN (Account Analytics Read)"]}
    host = urlparse(config["site"]["base_url"]).hostname
    project_name = config.get("analytics", {}).get("cloudflare_project", "nodus-lab")
    # A separate read-only analytics token need not have Pages Read permission.
    collection_enabled = None
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        try:
            project = cloudflare_request(f"accounts/{account}/pages/projects/{project_name}", os.environ["CLOUDFLARE_API_TOKEN"])["result"]
            collection_enabled = bool(project.get("build_config", {}).get("web_analytics_token"))
        except RuntimeError:
            pass
    end_dt = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = (end_dt - timedelta(days=13)).isoformat()
    split = (end_dt - timedelta(days=6)).isoformat()
    end = end_dt.isoformat()
    query = """query($account: String!, $host: String!, $start: Date!, $end: Date!) {
      viewer { accounts(filter: {accountTag: $account}) {
        rumPageloadEventsAdaptiveGroups(limit: 100, filter: {requestHost: $host, date_geq: $start, date_leq: $end}, orderBy: [date_ASC]) {
          dimensions { date } count sum { visits }
        }
      } }
    }"""
    result = cloudflare_request("graphql", token, {"query": query, "variables": {"account": account, "host": host, "start": start, "end": end}})
    accounts = result.get("data", {}).get("viewer", {}).get("accounts", [])
    if not accounts:
        raise RuntimeError("Cloudflare returned no accessible account; this is not zero traffic")
    groups = accounts[0]["rumPageloadEventsAdaptiveGroups"]
    rows = [{"date": g["dimensions"]["date"], "pageviews": g["count"], "visits": g["sum"]["visits"]} for g in groups]
    status = "live" if rows else "collection_disabled" if collection_enabled is False else "no_observations"
    return {"status": status, "source": "Cloudflare Web Analytics / RUM", "host": host, "timezone": "UTC", "window": {"start": start, "end": end}, "collection_enabled": collection_enabled, "rows": rows, "comparison": compare_days(rows, start, split, end, ["pageviews", "visits"]) if rows else None, "note": "Adaptive estimates of recorded browser beacons. Visits are not unique users. No historical backfill before collection was enabled."}


def fetch_gsc_table(prop: str, token: str, request: dict, dimensions: list[str]) -> dict:
    """Page through API rows without treating query breakdowns as site totals."""
    rows = []
    metadata = {}
    aggregation = None
    start_row = 0
    while True:
        raw = _gsc_query_rest(prop, token, {**request, "dimensions": dimensions, "rowLimit": GSC_ROW_LIMIT, "startRow": start_row, "aggregationType": "auto" if "page" in dimensions else "byProperty"})
        if raw.get("error"):
            raise RuntimeError("Search Console rejected the query")
        batch = raw.get("rows", [])
        for row in batch:
            keys = row.get("keys", [])
            if len(keys) != len(dimensions):
                raise ValueError("Search Console returned unexpected dimension keys")
            rows.append({**dict(zip(dimensions, keys)), **{m: row[m] for m in ("clicks", "impressions", "ctr", "position")}})
        metadata.update(raw.get("metadata", {}))
        aggregation = raw.get("responseAggregationType", aggregation)
        if len(batch) < GSC_ROW_LIMIT:
            break
        start_row += GSC_ROW_LIMIT
    return {"status": "live" if rows else "no_observations", "dimensions": dimensions, "rows": rows, "row_count": len(rows), "response_aggregation_type": aggregation, "metadata": metadata}


def fetch_gsc_window(prop: str, token: str, start: str, end: str, data_state: str) -> dict:
    request = {"startDate": start, "endDate": end, "dataState": data_state, "type": "web"}
    daily = fetch_gsc_table(prop, token, request, ["date"])
    totals = fetch_gsc_table(prop, token, request, [])
    breakdowns = {name: fetch_gsc_table(prop, token, request, dimensions) for name, dimensions in [("query", ["query"]), ("page", ["page"]), ("query_page", ["query", "page"]), ("country", ["country"]), ("device", ["device"])]}
    return {"status": "live" if daily["rows"] or totals["rows"] else "no_observations", "window": {"start": start, "end": end, "dataState": data_state, "type": "web"}, "daily": daily, "site_totals": totals, "breakdowns": breakdowns}


def fetch_gsc(config: dict) -> dict:
    token = resolve_gsc_access_token()
    if not token:
        return {"status": "not_configured", "required": ["GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN"]}
    today = datetime.now(timezone.utc).astimezone(ZoneInfo("America/Los_Angeles")).date()
    end_dt = today - timedelta(days=3)
    start = (end_dt - timedelta(days=27)).isoformat()
    split = (end_dt - timedelta(days=13)).isoformat()
    end = end_dt.isoformat()
    prop = config["seo_loop"]["gsc_property_url"]
    final = fetch_gsc_window(prop, token, start, end, "final")
    recent = fetch_gsc_window(prop, token, (today - timedelta(days=6)).isoformat(), today.isoformat(), "all")
    rows = final["daily"]["rows"]
    final["comparison"] = compare_days(rows, start, split, end, ["clicks", "impressions"]) if rows else None
    return {"status": "live" if final["status"] == "live" or recent["status"] == "live" else "no_observations", "source": "Google Search Console API", "property": prop, "timezone": "America/Los_Angeles (Search Console reporting)", "rows": rows, "comparison": final["comparison"], "windows": {"final": final, "recent": recent}, "note": "Legacy rows/comparison use the final 28-day window only. Recent all-data rows may change; daily.metadata.first_incomplete_date identifies incomplete dates when returned. Site totals come from a separate query without dimensions. Query data excludes anonymized queries; API internal limits can omit breakdown rows even after pagination. CTR is a fraction (0 to 1); position is the API average, never summed."}


def collect() -> dict:
    config = load_json(CONFIG_PATH)
    report = {"fetched_at": datetime.now(timezone.utc).isoformat(), "sources": {}}
    for name, fetch in [("cloudflare", fetch_cloudflare), ("search_console", fetch_gsc)]:
        try:
            report["sources"][name] = fetch(config)
        except (RuntimeError, OSError, ValueError, KeyError, TypeError):
            report["sources"][name] = {"status": "error", "message": f"{name} retrieval failed. Check authorization, property/dataset access and reporting window. No sample data was substituted."}
    usable = sum(s["status"] in {"live", "no_observations"} for s in report["sources"].values())
    report["status"] = "ok" if usable == 2 else "partial" if usable else "unavailable"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = collect()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for name, source in report["sources"].items():
            if source["status"] not in {"live", "no_observations"}:
                print(f"::warning::{name}: {source['status']}; actual metrics are not available for this source")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as stream:
                stream.write("## Analytics collection\n\n```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n")
    sys.exit(2 if report["status"] == "unavailable" else 0)
