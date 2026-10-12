#!/usr/bin/env python3
"""
Nodus Closed-Loop SEO Improvement Engine (GSC API + Autonomous Article Optimizer)
Implements the Loop Engineering workflow:
1. Pull live URL & query metrics from Google Search Console API (via OAuth2 Refresh Token or Access Token).
2. Guardrail: Never overwrite production articles when running on sample or stale (>7 days) telemetry unless --allow-sample is passed.
3. Classify pages into actionable buckets:
   - CTR_OPTIMIZE: High impressions, low CTR -> Inject concrete measured numbers & top query keywords into meta_title.
   - RANK_BOOST_DATA_INJECT: Position 8.0 - 20.0 -> Identify uncovered sub-queries and record candidate.
   - EVALUATE_PREVIOUS_LOOP: Verify whether edits from 14+ days ago improved CTR/Clicks; record outcome in ledger.
4. Apply atomic updates to content/articles/*.json (updating editorial 'updated_at' while preserving 'data_updated_at').
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from build_site import build_all

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "site_config.json"
ARTICLES_DIR = ROOT_DIR / "content" / "articles"
LEDGER_PATH = ROOT_DIR / "data" / "seo_loop_ledger.json"
LIVE_GSC_PATH = ROOT_DIR / "data" / "gsc_telemetry_live.json"
SAMPLE_GSC_PATH = ROOT_DIR / "data" / "gsc_telemetry_sample.json"
MAX_LIVE_SNAPSHOT_AGE_DAYS = 7


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def resolve_gsc_access_token() -> str:
    """Resolve Google Search Console OAuth2 access token via refresh token flow or direct token."""
    client_id = os.environ.get("GSC_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GSC_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GSC_REFRESH_TOKEN", "").strip()
    if client_id and client_secret and refresh_token:
        payload = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
            return str(token_data.get("access_token", "")).strip()

    return os.environ.get("GSC_ACCESS_TOKEN", "").strip()


def fetch_live_gsc_telemetry(property_url: str, access_token: str) -> dict[str, Any]:
    """Fetch 28-day search analytics from Google Search Console REST API using OAuth2 Bearer token."""
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d")
    encoded_prop = urllib.parse.quote(property_url, safe="")
    api_url = f"https://www.googleapis.com/webmasters/v3/sites/{encoded_prop}/searchAnalytics/query"

    body = json.dumps(
        {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page", "query"],
            "rowLimit": 500,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "NodusSEOLoop/1.2",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    pages: dict[str, dict[str, Any]] = {}
    for row in raw.get("rows", []):
        keys = row.get("keys", [])
        if len(keys) < 2:
            continue
        page_url, query_str = keys[0], keys[1]
        if "/articles/" not in page_url:
            continue
        slug = page_url.split("/articles/")[-1].replace(".html", "").strip("/")
        entry = pages.setdefault(
            slug,
            {
                "impressions": 0,
                "clicks": 0,
                "weighted_pos_sum": 0.0,
                "top_queries": [],
            },
        )
        imp = int(row.get("impressions", 0))
        clk = int(row.get("clicks", 0))
        pos = float(row.get("position", 0.0))
        entry["impressions"] += imp
        entry["clicks"] += clk
        entry["weighted_pos_sum"] += pos * imp
        entry["top_queries"].append(
            {"query": query_str, "impressions": imp, "clicks": clk, "position": round(pos, 1)}
        )

    formatted_pages: dict[str, Any] = {}
    for slug, agg in pages.items():
        imp = agg["impressions"]
        clk = agg["clicks"]
        formatted_pages[slug] = {
            "impressions": imp,
            "clicks": clk,
            "ctr": round(clk / imp, 4) if imp > 0 else 0.0,
            "position": round(agg["weighted_pos_sum"] / imp, 1) if imp > 0 else 0.0,
            "top_queries": sorted(agg["top_queries"], key=lambda x: x["impressions"], reverse=True)[:10],
        }

    snapshot = {
        "source_mode": "LIVE_GSC_API",
        "fetched_at": datetime.now().strftime("%Y-%m-%d"),
        "window": {"start_date": start_date, "end_date": end_date},
        "property": property_url,
        "pages": formatted_pages,
    }
    atomic_write_json(LIVE_GSC_PATH, snapshot)
    return snapshot


def is_fresh_live_snapshot(data: dict[str, Any], expected_property: str) -> bool:
    if data.get("source_mode") != "LIVE_GSC_API":
        return False
    if data.get("property") != expected_property:
        return False
    fetched_str = str(data.get("fetched_at", ""))
    try:
        fetched_dt = datetime.strptime(fetched_str, "%Y-%m-%d")
    except ValueError:
        return False
    age_days = (datetime.now() - fetched_dt).days
    return 0 <= age_days <= MAX_LIVE_SNAPSHOT_AGE_DAYS


def load_telemetry(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return (telemetry_dict, is_verified_fresh_live_data)."""
    prop_url = config["seo_loop"]["gsc_property_url"]
    try:
        access_token = resolve_gsc_access_token()
        if access_token:
            return fetch_live_gsc_telemetry(prop_url, access_token), True
    except Exception as exc:
        return {"source_mode": "GSC_API_ERROR", "error": str(exc), "pages": {}}, False

    if LIVE_GSC_PATH.exists():
        data = load_json(LIVE_GSC_PATH)
        if is_fresh_live_snapshot(data, prop_url):
            return data, True
        data["source_mode"] = "STALE_LIVE_GSC_CACHE"
        return data, False

    if SAMPLE_GSC_PATH.exists():
        sample = load_json(SAMPLE_GSC_PATH)
        sample["source_mode"] = "SAMPLE_TELEMETRY"
        return sample, False

    return {"source_mode": "EMPTY", "pages": {}}, False


def evaluate_past_actions(
    ledger: list[dict[str, Any]], pages: dict[str, Any], today_str: str
) -> list[dict[str, Any]]:
    evaluations: list[dict[str, Any]] = []
    today_dt = datetime.strptime(today_str, "%Y-%m-%d")
    for entry in ledger:
        if entry.get("evaluated_at") or entry.get("action_type") == "EVALUATE_PREVIOUS_LOOP":
            continue
        action_date_str = entry.get("date", "")
        slug = entry.get("slug", "")
        if not action_date_str or slug not in pages:
            continue
        try:
            action_dt = datetime.strptime(action_date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if (today_dt - action_dt).days >= 14:
            current_ctr = pages[slug].get("ctr", 0.0)
            current_pos = pages[slug].get("position", 0.0)
            entry["evaluated_at"] = today_str
            entry["post_metrics"] = {"ctr": current_ctr, "position": current_pos}
            evaluations.append(
                {
                    "date": today_str,
                    "slug": slug,
                    "action_type": "EVALUATE_PREVIOUS_LOOP",
                    "reference_date": action_date_str,
                    "observed_ctr": current_ctr,
                    "observed_position": current_pos,
                }
            )
    return evaluations


def analyze_and_optimize(apply_changes: bool = False, allow_sample: bool = False) -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    thresholds = config["seo_loop"]["thresholds"]
    telemetry, is_live = load_telemetry(config)

    if apply_changes and not is_live and not allow_sample:
        result = {
            "status": "skipped",
            "reason": "Refusing to apply changes to production articles without fresh live GSC data. Configure GSC OAuth credentials or pass --allow-sample for testing.",
            "source_mode": telemetry.get("source_mode", "SAMPLE_TELEMETRY"),
            "error": telemetry.get("error"),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    ledger: list[dict[str, Any]] = []
    if LEDGER_PATH.exists():
        ledger = load_json(LEDGER_PATH)

    today = datetime.now().strftime("%Y-%m-%d")
    pages = telemetry.get("pages", {})
    actions_taken: list[dict[str, Any]] = evaluate_past_actions(ledger, pages, today)
    modified_articles: list[tuple[Path, dict[str, Any]]] = []

    for slug, metrics in pages.items():
        article_path = ARTICLES_DIR / f"{slug}.json"
        if not article_path.exists():
            continue

        article = load_json(article_path)
        impressions = int(metrics.get("impressions", 0))
        ctr = float(metrics.get("ctr", 0.0))
        position = float(metrics.get("position", 0.0))
        top_queries = metrics.get("top_queries", [])
        modified = False

        # Rule 1: High Impressions + Low CTR -> Ensure concrete sample size (N=...) is in meta_title
        if impressions >= thresholds["high_impression_min"] and ctr < thresholds["low_ctr_threshold"]:
            primary_q = top_queries[0]["query"] if top_queries else ""
            old_title = article["seo"]["meta_title"]
            sample_n = int(article.get("sample_size_n", 0))
            badge_tag = f"N={sample_n}"
            if sample_n > 0 and badge_tag not in old_title:
                new_title = f"【実測{badge_tag}】{article['title']} | Nodus"
                article["seo"]["meta_title"] = new_title
                article["updated_at"] = today
                modified = True
                actions_taken.append(
                    {
                        "date": today,
                        "slug": slug,
                        "source_mode": telemetry.get("source_mode"),
                        "action_type": "CTR_OPTIMIZE_META_TITLE",
                        "trigger": f"impressions={impressions}, ctr={ctr:.2%} (< {thresholds['low_ctr_threshold']:.1%}), top_query='{primary_q}'",
                        "before": old_title,
                        "after": new_title,
                    }
                )

        # Rule 2: Striking Distance Rank (8.0 <= position <= 20.0) -> Flag uncovered high-impression query
        if thresholds["striking_distance_rank_min"] <= position <= thresholds["striking_distance_rank_max"]:
            existing_text = (
                article.get("title", "")
                + " "
                + " ".join(f["question"] + f["answer"] for f in article.get("faqs", []))
            ).lower()
            for q_obj in top_queries:
                q_str = q_obj["query"]
                q_tokens = [t for t in q_str.lower().split() if len(t) >= 2]
                if q_tokens and not all(t in existing_text for t in q_tokens):
                    actions_taken.append(
                        {
                            "date": today,
                            "slug": slug,
                            "source_mode": telemetry.get("source_mode"),
                            "action_type": "STRIKING_DISTANCE_QUERY_CANDIDATE",
                            "trigger": f"position={position:.1f} (striking distance 8-20)",
                            "uncovered_query": q_str,
                            "query_impressions": q_obj.get("impressions", 0),
                        }
                    )
                    break

        if modified:
            modified_articles.append((article_path, article))

    if apply_changes and (modified_articles or actions_taken):
        for article_path, article_data in modified_articles:
            atomic_write_json(article_path, article_data)
        ledger.extend(actions_taken)
        atomic_write_json(LEDGER_PATH, ledger)
        build_all()

    result = {
        "status": "ok",
        "source_mode": telemetry.get("source_mode", "UNKNOWN"),
        "mode": "APPLIED" if apply_changes else "DRY_RUN",
        "articles_modified": len(modified_articles),
        "actions_count": len(actions_taken),
        "actions": actions_taken,
        "ledger_path": str(LEDGER_PATH),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nodus Closed-Loop SEO Optimizer")
    parser.add_argument("--apply", action="store_true", help="Apply optimizations to article JSONs and rebuild site")
    parser.add_argument(
        "--allow-sample",
        action="store_true",
        help="Explicitly allow applying changes when running against sample telemetry",
    )
    args = parser.parse_args()
    analyze_and_optimize(apply_changes=args.apply, allow_sample=args.allow_sample)
