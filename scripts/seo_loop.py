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


TITLE_VARIANTS = [
    "v1_metric_lead",
    "v2_query_answer",
    "v3_spec_vs_real",
    "v4_year_conclusion",
]

DESC_VARIANTS = [
    "d1_kpi_frontload",
    "d2_tldr_summary",
    "d3_query_bolding",
]

LEAD_VARIANTS = [
    "default",
    "table_first",
    "faq_boost",
]


def _build_title_variant(article: dict[str, Any], variant_id: str, top_query: str) -> str:
    sample_n = int(article.get("sample_size_n", 0))
    title = article["title"]
    metrics = article.get("summary_metrics", [])
    m_val = metrics[1]["value"] if len(metrics) > 1 else (metrics[0]["value"] if metrics else f"N={sample_n}")
    year = article.get("updated_at", "2026")[:4]

    if variant_id == "v1_metric_lead":
        return f"【実測: {m_val}】{title} (N={sample_n}) | Nodus"
    if variant_id == "v2_query_answer" and top_query:
        return f"{top_query}の実測検証 — {title} (N={sample_n}) | Nodus"
    if variant_id == "v3_spec_vs_real":
        return f"【公称値vs実測N={sample_n}】{title}（比較表・CSV付）| Nodus"
    return f"[{year}年実測N={sample_n}] {title}｜検証データと結論まとめ | Nodus"


def _build_desc_variant(article: dict[str, Any], variant_id: str, top_queries: list[dict[str, Any]]) -> str:
    sample_n = int(article.get("sample_size_n", 0))
    metrics = article.get("summary_metrics", [])
    m0 = f"{metrics[0]['label']}: {metrics[0]['value']}" if len(metrics) > 0 else ""
    m1 = f"{metrics[1]['label']}: {metrics[1]['value']}" if len(metrics) > 1 else ""
    tldr = article.get("tldr", [])
    base_desc = article["seo"].get("meta_description", article.get("subtitle", ""))

    if variant_id == "d1_kpi_frontload" and (m0 or m1):
        kpi_lead = " / ".join(x for x in [m0, m1] if x)
        return f"【実測N={sample_n}】{kpi_lead}。{base_desc}"[:155]
    if variant_id == "d2_tldr_summary" and tldr:
        return f"【結論】{tldr[0]}（N={sample_n}・検証CSVデータ付）"[:155]
    if variant_id == "d3_query_bolding" and top_queries:
        q_terms = "・".join(q["query"] for q in top_queries[:2] if q.get("query"))
        return f"「{q_terms}」を一次ログ（N={sample_n}）から定量検証。{base_desc}"[:155]
    return base_desc


def _select_intent_lead_variant(top_queries: list[dict[str, Any]], tried_leads: list[str]) -> str:
    combined_q = " ".join(str(q.get("query", "")) for q in top_queries).lower()
    if any(k in combined_q for k in ["比較", "一覧", "違い", "vs", "コスパ", "単価", "スペック"]) and "table_first" not in tried_leads:
        return "table_first"
    if any(k in combined_q for k in ["なぜ", "制限", "上限", "原因", "対策", "どっち", "方法"]) and "faq_boost" not in tried_leads:
        return "faq_boost"
    for cand in LEAD_VARIANTS:
        if cand not in tried_leads:
            return cand
    return LEAD_VARIANTS[len(tried_leads) % len(LEAD_VARIANTS)]


def evaluate_past_actions(
    ledger: list[dict[str, Any]], pages: dict[str, Any], today_str: str
) -> tuple[list[dict[str, Any]], set[str]]:
    """Return (evaluation_entries, slugs_needing_variant_rotation)."""
    evaluations: list[dict[str, Any]] = []
    rotate_slugs: set[str] = set()
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
            current_ctr = float(pages[slug].get("ctr", 0.0))
            current_pos = float(pages[slug].get("position", 0.0))
            base_ctr = float(entry.get("baseline_ctr", 0.0))
            base_pos = float(entry.get("baseline_position", current_pos))

            ctr_improved = base_ctr > 0 and current_ctr >= base_ctr * 1.05
            pos_improved = base_pos > 0 and (base_pos - current_pos) >= 0.5 and current_ctr >= base_ctr * 0.95
            outcome = "WIN_KEPT" if (ctr_improved or pos_improved) else "UNDERPERFORMED_ROTATE"
            if outcome == "UNDERPERFORMED_ROTATE":
                rotate_slugs.add(slug)

            entry["evaluated_at"] = today_str
            entry["outcome"] = outcome
            entry["post_metrics"] = {"ctr": current_ctr, "position": current_pos}
            evaluations.append(
                {
                    "date": today_str,
                    "slug": slug,
                    "action_type": "EVALUATE_PREVIOUS_LOOP",
                    "reference_date": action_date_str,
                    "variant_tested": entry.get("variant_bundle", {}),
                    "baseline_ctr": base_ctr,
                    "observed_ctr": current_ctr,
                    "baseline_position": base_pos,
                    "observed_position": current_pos,
                    "outcome": outcome,
                }
            )
    return evaluations, rotate_slugs


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
    actions_taken, rotate_slugs = evaluate_past_actions(ledger, pages, today)
    modified_articles: list[tuple[Path, dict[str, Any]]] = []

    for slug, metrics in pages.items():
        article_path = ARTICLES_DIR / f"{slug}.json"
        if not article_path.exists():
            continue

        article = load_json(article_path)
        seo = article["seo"]
        impressions = int(metrics.get("impressions", 0))
        ctr = float(metrics.get("ctr", 0.0))
        position = float(metrics.get("position", 0.0))
        top_queries = metrics.get("top_queries", [])
        modified = False

        # Multi-Element A/B Test Trigger:
        # Either (High Impressions + Low CTR) OR previous 14-day A/B variant underperformed and needs rotation
        needs_ab_switch = (
            impressions >= thresholds["high_impression_min"] and ctr < thresholds["low_ctr_threshold"]
        ) or (slug in rotate_slugs)

        if needs_ab_switch:
            primary_q = top_queries[0]["query"] if top_queries else ""
            history: list[dict[str, str]] = list(seo.get("ab_history", []))
            tried_titles = [h.get("title_variant", "") for h in history]
            tried_descs = [h.get("desc_variant", "") for h in history]
            tried_leads = [h.get("lead_variant", "") for h in history]

            next_title_var = next(
                (v for v in TITLE_VARIANTS if v not in tried_titles),
                TITLE_VARIANTS[len(tried_titles) % len(TITLE_VARIANTS)],
            )
            next_desc_var = next(
                (v for v in DESC_VARIANTS if v not in tried_descs),
                DESC_VARIANTS[len(tried_descs) % len(DESC_VARIANTS)],
            )
            next_lead_var = _select_intent_lead_variant(top_queries, tried_leads)

            old_snapshot = {
                "meta_title": seo.get("meta_title", ""),
                "meta_description": seo.get("meta_description", ""),
                "lead_variant": seo.get("lead_variant", "default"),
            }
            new_title = _build_title_variant(article, next_title_var, primary_q)
            new_desc = _build_desc_variant(article, next_desc_var, top_queries)

            if (
                new_title != old_snapshot["meta_title"]
                or new_desc != old_snapshot["meta_description"]
                or next_lead_var != old_snapshot["lead_variant"]
            ):
                seo["meta_title"] = new_title
                seo["meta_description"] = new_desc
                seo["lead_variant"] = next_lead_var
                variant_bundle = {
                    "title_variant": next_title_var,
                    "desc_variant": next_desc_var,
                    "lead_variant": next_lead_var,
                }
                history.append({"date": today, **variant_bundle})
                seo["ab_history"] = history[-8:]
                article["updated_at"] = today
                modified = True
                actions_taken.append(
                    {
                        "date": today,
                        "slug": slug,
                        "source_mode": telemetry.get("source_mode"),
                        "action_type": "AB_VARIANT_SWITCH",
                        "trigger": (
                            f"rotate_after_14d_eval"
                            if slug in rotate_slugs
                            else f"impressions={impressions}, ctr={ctr:.2%} (< {thresholds['low_ctr_threshold']:.1%}), top_query='{primary_q}'"
                        ),
                        "baseline_ctr": ctr,
                        "baseline_position": position,
                        "variant_bundle": variant_bundle,
                        "before": old_snapshot,
                        "after": {
                            "meta_title": new_title,
                            "meta_description": new_desc,
                            "lead_variant": next_lead_var,
                        },
                    }
                )

        # Rule 2: Striking Distance Rank (8.0 <= position <= 20.0) -> Flag uncovered high-impression query & switch layout if needed
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
    parser = argparse.ArgumentParser(description="Nodus Closed-Loop Multi-Variant SEO Optimizer")
    parser.add_argument("--apply", action="store_true", help="Apply optimizations to article JSONs and rebuild site")
    parser.add_argument(
        "--allow-sample",
        action="store_true",
        help="Explicitly allow applying changes when running against sample telemetry",
    )
    args = parser.parse_args()
    analyze_and_optimize(apply_changes=args.apply, allow_sample=args.allow_sample)
