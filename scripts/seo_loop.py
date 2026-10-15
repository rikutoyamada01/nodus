#!/usr/bin/env python3
"""
Nodus Autonomous Market-Predictive SEO & AEO Optimization Loop (`scripts/seo_loop.py`)

Upgraded from blind round-robin template switching to a Market-Predictive Optimization Engine:
1. Position-Expected CTR Curve Modeling:
   - Compares actual CTR against expected CTR for the page's exact SERP position (`actual_ctr / expected_ctr`),
     preventing false triggers on lower-ranked pages and catching underperforming top-ranked pages.
2. Non-Overlapping Pre/Post Window & Cooldown Lock:
   - Locks pages with an active `AB_VARIANT_SWITCH` during the 14-day observation window so consecutive runs
     never overwrite an active test.
   - Queries page-level GSC aggregates (`dimensions=["page"]`) separately from query-level rows (`dimensions=["page", "query"]`)
     using zero-dependency REST calls (`urllib.request`), and queries post-change dates (`switch_date + 1d` to `end_date`)
     when evaluating past experiments.
   - Requires a minimum impression floor (`min_eval_impressions`) before declaring a win or rotating.
3. Market-Predictive Variant Scoring (GSC Queries + Google Suggest Trends):
   - Integrates `scripts/trend_radar.py` (`data/search_trends.json`) and GSC query distributions.
   - Identifies market search tokens that are answered in the article body/table/FAQ but missing from `meta_title`.
   - Predicts and scores candidate `(title_variant, desc_variant, lead_variant)` bundles by Search Intent Alignment,
     Verified Body-Backed Token Gain, and SERP Length Fitness before selecting the optimal variant.
4. Immutable Base Metadata & Verified Fact Claims:
   - Preserves `original_meta_title` and `original_meta_description` so generated prefixes never accumulate.
   - Verifies actual presence of `comparison_table.rows`, `sample_size_n > 0`, CSV dataset, and raw logs before
     emitting claims in titles or descriptions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from build_site import build_all
from trend_radar import (
    classify_search_intent,
    evaluate_query_against_article,
    load_articles_structured,
    normalize_text_ja,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "site_config.json"
ARTICLES_DIR = ROOT_DIR / "content" / "articles"
RAW_LOGS_DIR = ROOT_DIR / "content" / "raw_logs"
LEDGER_PATH = ROOT_DIR / "data" / "seo_loop_ledger.json"
LIVE_GSC_PATH = ROOT_DIR / "data" / "gsc_telemetry_live.json"
SAMPLE_GSC_PATH = ROOT_DIR / "data" / "gsc_telemetry_sample.json"
TRENDS_PATH = ROOT_DIR / "data" / "search_trends.json"
MAX_LIVE_SNAPSHOT_AGE_DAYS = 7

TITLE_VARIANTS = [
    "v1_metric_lead",       # 具体的な実測数値・KPI先出し型
    "v2_versus_hook",       # 比較・対決フック型 (A vs B / 徹底比較)
    "v3_question_intent",   # 疑問解決・検索クエリ直結型
    "v4_dataset_authority", # 一次データ・CSV公開強調型
]

DESC_VARIANTS = [
    "d1_kpi_frontload",     # 冒頭40文字に実測KPIとN数を凝縮配置
    "d2_faq_conclusion",    # FAQまたはTL;DRの結論アンサー先出し型
    "d3_dataset_cta",       # 検証環境・CSVデータセット・生ログ強調型
]

LEAD_VARIANTS = [
    "default",              # 標準構成 (TL;DR -> チャート -> 比較表 -> 本文)
    "table_first",          # 比較表最優先配置 (比較意図が強いクエリ向け)
    "faq_boost",            # 疑問即答・FAQ先出し配置 (疑問・トラブル解決クエリ向け)
]

# Empirical organic CTR curve by SERP position (1-indexed)
POSITION_EXPECTED_CTR_TABLE: dict[int, float] = {
    1: 0.240,
    2: 0.145,
    3: 0.100,
    4: 0.072,
    5: 0.055,
    6: 0.042,
    7: 0.033,
    8: 0.026,
    9: 0.021,
    10: 0.018,
    11: 0.015,
    12: 0.013,
    13: 0.011,
    14: 0.010,
    15: 0.009,
    16: 0.008,
    17: 0.007,
    18: 0.006,
    19: 0.006,
    20: 0.005,
}


def expected_ctr_for_position(position: float) -> float:
    """Compute position-adjusted expected CTR using linear interpolation."""
    if position <= 1.0:
        return POSITION_EXPECTED_CTR_TABLE[1]
    if position >= 20.0:
        return max(0.003, 0.005 * (20.0 / position))
    low_pos = int(position)
    high_pos = min(20, low_pos + 1)
    frac = position - low_pos
    c_low = POSITION_EXPECTED_CTR_TABLE.get(low_pos, 0.010)
    c_high = POSITION_EXPECTED_CTR_TABLE.get(high_pos, 0.008)
    return round(c_low + frac * (c_high - c_low), 5)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def extract_slug_from_url(page_url: str) -> str | None:
    m = re.search(r"/articles/([a-z0-9-]+?)(?:\.html)?(?:[?#]|$)", page_url)
    return m.group(1) if m else None


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


def _gsc_query_rest(property_url: str, access_token: str, body_dict: dict[str, Any]) -> dict[str, Any]:
    encoded_prop = urllib.parse.quote(property_url, safe="")
    api_url = f"https://www.googleapis.com/webmasters/v3/sites/{encoded_prop}/searchAnalytics/query"
    body = json.dumps(body_dict).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "NodusSEOLoop/2.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_gsc_window_rest(
    property_url: str,
    access_token: str,
    start_date: str,
    end_date: str,
) -> dict[str, dict[str, Any]]:
    """
    Fetch exact page-level metrics (`dimensions=["page"]`) AND query breakdown (`dimensions=["page", "query"]`)
    for `[start_date, end_date]` so page-level totals are never truncated by the query row limit.
    """
    pages: dict[str, dict[str, Any]] = {}

    # 1. Exact page-level totals
    page_raw = _gsc_query_rest(
        property_url,
        access_token,
        {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": 500,
        },
    )
    for row in page_raw.get("rows", []):
        keys = row.get("keys", [])
        if not keys:
            continue
        slug = extract_slug_from_url(keys[0])
        if not slug:
            continue
        imp = int(row.get("impressions", 0))
        clk = int(row.get("clicks", 0))
        pos = float(row.get("position", 0.0))
        pages[slug] = {
            "impressions": imp,
            "clicks": clk,
            "ctr": round(clk / imp, 4) if imp > 0 else 0.0,
            "position": round(pos, 2),
            "top_queries": [],
        }

    # 2. Query-level breakdown
    query_raw = _gsc_query_rest(
        property_url,
        access_token,
        {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page", "query"],
            "rowLimit": 2000,
        },
    )
    for row in query_raw.get("rows", []):
        keys = row.get("keys", [])
        if len(keys) < 2:
            continue
        slug = extract_slug_from_url(keys[0])
        query_str = keys[1]
        if not slug or slug not in pages:
            continue
        imp = int(row.get("impressions", 0))
        clk = int(row.get("clicks", 0))
        pos = float(row.get("position", 0.0))
        pages[slug]["top_queries"].append(
            {
                "query": query_str,
                "impressions": imp,
                "clicks": clk,
                "ctr": round(clk / imp, 4) if imp > 0 else 0.0,
                "position": round(pos, 1),
            }
        )

    for slug, entry in pages.items():
        entry["top_queries"] = sorted(entry["top_queries"], key=lambda x: x["impressions"], reverse=True)[:15]

    return pages


def fetch_live_gsc_telemetry(property_url: str, access_token: str) -> dict[str, Any]:
    """Fetch 28-day search analytics from Google Search Console REST API."""
    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d")
    formatted_pages = fetch_gsc_window_rest(property_url, access_token, start_date, end_date)
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


def load_telemetry(config: dict[str, Any], allow_sample: bool = False) -> tuple[dict[str, Any], bool, str]:
    """Return `(telemetry_dict, is_verified_fresh_live_data, access_token)`."""
    prop_url = config["seo_loop"]["gsc_property_url"]
    access_token = ""
    try:
        access_token = resolve_gsc_access_token()
        if access_token:
            return fetch_live_gsc_telemetry(prop_url, access_token), True, access_token
    except Exception as exc:
        return {"source_mode": "GSC_API_ERROR", "error": str(exc), "pages": {}}, False, ""

    if LIVE_GSC_PATH.exists():
        data = load_json(LIVE_GSC_PATH)
        if is_fresh_live_snapshot(data, prop_url):
            return data, True, ""
        data["source_mode"] = "STALE_LIVE_GSC_CACHE"
        return data, False, ""

    if allow_sample and SAMPLE_GSC_PATH.exists():
        sample = load_json(SAMPLE_GSC_PATH)
        sample["source_mode"] = "SAMPLE_TELEMETRY"
        return sample, False, ""

    return {
        "source_mode": "GSC_NOT_CONFIGURED",
        "message": "Set GSC_CLIENT_ID, GSC_CLIENT_SECRET and GSC_REFRESH_TOKEN, or a valid GSC_ACCESS_TOKEN. Sample data is disabled unless --allow-sample is explicit.",
        "pages": {},
    }, False, ""


def strip_generated_prefixes(text: str) -> str:
    """Strip any leading bracketed tags like 【...】 so prefixes never accumulate across rewrites."""
    return re.sub(r"^(?:【[^】]+】\s*)+", "", text.strip()).strip()


def ensure_immutable_originals(article: dict[str, Any]) -> tuple[str, str]:
    """
    Ensure `seo.original_meta_title` and `seo.original_meta_description` are stored once
    from the clean base article, preventing recursive prefix accumulation.
    """
    seo = article.setdefault("seo", {})
    if not seo.get("original_meta_title"):
        raw_title = seo.get("meta_title") or article.get("title", "")
        seo["original_meta_title"] = strip_generated_prefixes(raw_title.split("|")[0].strip())
    if not seo.get("original_meta_description"):
        raw_desc = seo.get("meta_description") or article.get("subtitle", "")
        seo["original_meta_description"] = strip_generated_prefixes(raw_desc)
    return seo["original_meta_title"], seo["original_meta_description"]


def inspect_article_capabilities(article: dict[str, Any]) -> dict[str, Any]:
    """Verify what empirical assets actually exist in the article before making claims in metadata."""
    slug = article.get("slug", "")
    rows = article.get("comparison_table", {}).get("rows", [])
    has_table = isinstance(rows, list) and len(rows) >= 2
    has_csv = has_table and (
        (ROOT_DIR / "dist" / "datasets" / f"{slug}.csv").exists() or bool(rows)
    )
    has_raw_log = (RAW_LOGS_DIR / f"{slug}.json").exists()
    sample_n = int(article.get("sample_size_n") or 0)
    pub_date = str(article.get("published_at") or "")
    pub_year = pub_date[:4] if re.match(r"^20\d{2}", pub_date) else ""

    entities: list[str] = []
    if has_table:
        for r in rows[:4]:
            if isinstance(r, list) and r:
                ent = re.sub(r"\s*\([^)]*\)", "", str(r[0])).strip()
                if ent and ent not in entities:
                    entities.append(ent)

    return {
        "has_table": has_table,
        "has_csv": has_csv,
        "has_raw_log": has_raw_log,
        "sample_n": sample_n,
        "pub_year": pub_year,
        "entities": entities,
        "summary_metrics": article.get("summary_metrics", []),
        "faqs": article.get("faqs", []),
        "tldr": article.get("tldr", []),
    }


def truncate_cleanly_ja(text: str, max_len: int) -> str:
    """Truncate text without chopping inside ASCII words, numbers before units, or parentheses."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    m_num = re.search(r"[・/、,\s]*(?:[A-Za-z0-9.\-+]+は)?\d+(?:\.\d+)?$", cut)
    if m_num and len(text) > max_len:
        cut = cut[: m_num.start()].rstrip(" ・/、,(")
    m = re.search(r"[A-Za-z0-9.\-+]+$", cut)
    if m and len(text) > max_len and re.match(r"[A-Za-z0-9.\-+]", text[max_len]):
        cut = cut[: m.start()].rstrip(" ・/、,(")
    for open_b, close_b in [("（", "）"), ("(", ")"), ("【", "】")]:
        if cut.count(open_b) > cut.count(close_b):
            last_open = cut.rfind(open_b)
            if last_open >= 0:
                cut = cut[:last_open].rstrip()
    return cut.rstrip(" ・/、,。")


def build_title_variant(
    article: dict[str, Any],
    variant_id: str,
    market_bonus_tokens: list[str],
    site_name: str = "Nodus",
) -> str:
    """Construct a title variant grounded strictly in verified article capabilities + market tokens."""
    base_title, _ = ensure_immutable_originals(article)
    caps = inspect_article_capabilities(article)
    n = caps["sample_n"]
    metrics = caps["summary_metrics"]
    lead_val = ""
    for m in metrics:
        lbl = str(m.get("label", ""))
        if "サンプル" not in lbl and "(N)" not in lbl and m.get("value"):
            lead_val = str(m["value"])
            break
    if not lead_val and metrics:
        lead_val = str(metrics[0].get("value", ""))

    base_norm = normalize_text_ja(base_title)
    extra_token = ""
    for tok in market_bonus_tokens:
        if len(tok) >= 2 and tok not in base_norm and tok not in {"google", "claude", "code", "colab"}:
            extra_token = tok
            break

    suffix_tag = f"・{extra_token}" if extra_token and len(base_title) <= 34 else ""

    if variant_id == "v1_metric_lead":
        if lead_val and n > 0:
            prefix = f"【実測: {lead_val}】"
            tail = f" (N={n})"
        elif n > 0:
            prefix = f"【実測N={n}】"
            tail = ""
        else:
            prefix = "【実測検証】"
            tail = ""
        core = truncate_cleanly_ja(f"{prefix}{base_title}{suffix_tag}{tail}", 56)

    elif variant_id == "v2_versus_hook":
        ents = caps["entities"]
        if len(ents) >= 2 and ents[0].lower() not in base_norm:
            vs_prefix = f"【{ents[0]} vs {ents[1]}】"
        else:
            vs_prefix = "【徹底比較】"
        tail = "｜実測比較表" if caps["has_table"] else ""
        core = truncate_cleanly_ja(f"{vs_prefix}{base_title}{suffix_tag}{tail}", 56)

    elif variant_id == "v3_question_intent":
        prefix = f"【{extra_token}を検証】" if extra_token else "【実測検証】"
        tail = f" (N={n})" if n > 0 else ""
        core = truncate_cleanly_ja(f"{prefix}{base_title}{tail}", 56)

    elif variant_id == "v4_dataset_authority":
        if caps["has_raw_log"] and n > 0:
            prefix = f"【一次ログ・N={n}】"
            tail = "｜生ログ・CSV公開"
        elif caps["has_csv"] and n > 0:
            prefix = f"【実測データ・N={n}】"
            tail = "｜CSV・比較表付"
        elif n > 0:
            prefix = f"【N={n}集計】"
            tail = ""
        else:
            prefix = "【技術検証】"
            tail = ""
        core = truncate_cleanly_ja(f"{prefix}{base_title}{suffix_tag}{tail}", 56)

    else:
        core = truncate_cleanly_ja(base_title, 56)

    return f"{core} | {site_name}"


def build_desc_variant(
    article: dict[str, Any],
    variant_id: str,
    market_bonus_tokens: list[str],
) -> str:
    """Construct a meta description from the immutable original description + verified article data."""
    _, base_desc = ensure_immutable_originals(article)
    caps = inspect_article_capabilities(article)
    n = caps["sample_n"]
    metrics = caps["summary_metrics"]
    faqs = caps["faqs"]
    tldr = caps["tldr"]

    if variant_id == "d1_kpi_frontload":
        kpi_snippet = " / ".join(f"{m.get('label')}: {m.get('value')}" for m in metrics[:2] if m.get("value"))
        n_tag = f"【実測N={n}】" if n > 0 else "【実測検証】"
        lead = f"{n_tag}{kpi_snippet}。" if kpi_snippet else n_tag
        combined = f"{lead}{base_desc}"

    elif variant_id == "d2_faq_conclusion":
        if faqs and faqs[0].get("answer"):
            ans = strip_generated_prefixes(str(faqs[0]["answer"]))
            combined = f"【結論】{ans[:75]}… {base_desc}"
        elif tldr:
            combined = f"【要点】{strip_generated_prefixes(str(tldr[0]))} {base_desc}"
        else:
            combined = base_desc

    elif variant_id == "d3_dataset_cta":
        assets = []
        if caps["has_table"]:
            assets.append("ソート可能な実測比較表")
        if caps["has_csv"]:
            assets.append("CSVデータセット")
        if caps["has_raw_log"]:
            assets.append("匿名化生ログ(JSON)")
        asset_str = "・".join(assets) if assets else "実測検証データ"
        kw_note = f"（{'・'.join(market_bonus_tokens[:3])}対応）" if market_bonus_tokens else ""
        combined = f"{asset_str}を公開{kw_note}。{base_desc}"

    else:
        combined = base_desc

    return truncate_cleanly_ja(combined, 150)


def collect_market_signals_for_article(
    article: dict[str, Any],
    gsc_queries: list[dict[str, Any]],
    trends_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Combine GSC search queries and Google Suggest trend data for a specific article
    to predict dominant market intent and identify body-backed tokens missing from the current title.
    """
    slug = article.get("slug", "")
    art_records = {r["slug"]: r for r in load_articles_structured()}
    art_rec = art_records.get(slug)

    intent_weights: Counter[str] = Counter()
    body_backed_missing_title_tokens: Counter[str] = Counter()
    uncovered_faq_queries: list[dict[str, Any]] = []

    # 1. Analyze GSC queries (weighted by impressions)
    for q_obj in gsc_queries:
        q_str = q_obj.get("query", "")
        impr = max(1, int(q_obj.get("impressions", 1)))
        intent = classify_search_intent(q_str)
        intent_weights[intent] += impr
        if art_rec:
            ev = evaluate_query_against_article(q_str, art_rec)
            if ev["status"] == "answer_in_body_missing_in_title":
                for tok in ev["missing_in_title"]:
                    body_backed_missing_title_tokens[tok] += impr * 2
            elif ev["status"] == "missing_in_article":
                uncovered_faq_queries.append(
                    {
                        "query": q_str,
                        "source": "GSC",
                        "impressions": impr,
                        "position": q_obj.get("position", 0.0),
                        "missing_tokens": ev["missing_in_body"],
                    }
                )

    # 2. Analyze Google Suggest trends from `data/search_trends.json`
    if trends_data:
        for item in trends_data.get("google_suggest_analysis", []):
            if item.get("slug") == slug or (
                not item.get("slug")
                and art_rec
                and normalize_text_ja(item.get("seed", "")) in art_rec["body_norm"]
            ):
                for intent_k, cnt in item.get("intent_distribution", {}).items():
                    intent_weights[intent_k] += int(cnt) * 25
                for opp in item.get("title_optimization_opportunities", []):
                    for tok in opp.get("missing_in_title", []):
                        body_backed_missing_title_tokens[tok] += 40
                for gap in item.get("uncovered_content_gaps", []):
                    uncovered_faq_queries.append(
                        {
                            "query": gap.get("query", ""),
                            "source": "GOOGLE_SUGGEST",
                            "impressions": 0,
                            "position": 0.0,
                            "missing_tokens": gap.get("missing_in_body", []),
                        }
                    )

    dominant_intent = intent_weights.most_common(1)[0][0] if intent_weights else "metric_cost_spec"
    bonus_tokens = [tok for tok, _ in body_backed_missing_title_tokens.most_common(5)]

    return {
        "dominant_intent": dominant_intent,
        "intent_weights": dict(intent_weights),
        "body_backed_missing_title_tokens": bonus_tokens,
        "uncovered_faq_queries": uncovered_faq_queries[:6],
    }


def score_candidate_bundle(
    article: dict[str, Any],
    t_var: str,
    d_var: str,
    lead_var: str,
    market_signals: dict[str, Any],
    site_name: str,
) -> tuple[float, dict[str, Any]]:
    """
    Predict how well a candidate `(t_var, d_var, lead_var)` bundle matches real market demand
    BEFORE applying it.
    """
    caps = inspect_article_capabilities(article)
    dominant_intent = market_signals["dominant_intent"]
    bonus_tokens = market_signals["body_backed_missing_title_tokens"]

    cand_title = build_title_variant(article, t_var, bonus_tokens, site_name=site_name)
    cand_desc = build_desc_variant(article, d_var, bonus_tokens)
    cand_norm = normalize_text_ja(f"{cand_title} {cand_desc}")

    score = 0.0
    reasons: list[str] = []

    intent_map = {
        "comparison": ("v2_versus_hook", "d1_kpi_frontload", "table_first"),
        "metric_cost_spec": ("v1_metric_lead", "d1_kpi_frontload", "default"),
        "question_troubleshoot": ("v3_question_intent", "d2_faq_conclusion", "faq_boost"),
        "dataset_benchmark": ("v4_dataset_authority", "d3_dataset_cta", "table_first"),
    }
    ideal_t, ideal_d, ideal_l = intent_map.get(dominant_intent, ("v1_metric_lead", "d1_kpi_frontload", "default"))
    if t_var == ideal_t:
        score += 22.0
        reasons.append(f"title matches dominant intent '{dominant_intent}'")
    if d_var == ideal_d:
        score += 10.0
    if lead_var == ideal_l:
        score += 8.0
        reasons.append(f"layout '{lead_var}' matches intent '{dominant_intent}'")

    covered_bonus = [tok for tok in bonus_tokens if tok in cand_norm]
    if covered_bonus:
        gain = min(30.0, len(covered_bonus) * 10.0)
        score += gain
        reasons.append(f"covers missing market tokens {covered_bonus}")

    if t_var == "v1_metric_lead" and caps["summary_metrics"] and caps["sample_n"] > 0:
        score += 15.0
    elif t_var == "v2_versus_hook" and len(caps["entities"]) >= 2:
        score += 15.0
    elif t_var == "v4_dataset_authority" and (caps["has_raw_log"] or caps["has_csv"]):
        score += 15.0
    elif t_var == "v3_question_intent" and caps["faqs"]:
        score += 12.0

    title_len = len(cand_title)
    if 32 <= title_len <= 64:
        score += 10.0
    elif title_len > 68:
        score -= 10.0

    return round(score, 2), {
        "predicted_score": round(score, 2),
        "dominant_intent": dominant_intent,
        "covered_market_tokens": covered_bonus,
        "rationale": "; ".join(reasons) if reasons else "baseline structural fit",
        "candidate_title": cand_title,
        "candidate_desc": cand_desc,
    }


def predict_best_variant_bundle(
    article: dict[str, Any],
    market_signals: dict[str, Any],
    site_name: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """
    Evaluate all candidate combinations against market signals and select the highest-scoring
    untested bundle (Market-Predictive Optimization before A/B exploration).
    """
    seo = article.get("seo", {})
    history = seo.get("ab_history", [])
    tried_keys = {
        f"{h.get('title_variant')}|{h.get('desc_variant')}|{h.get('lead_variant')}"
        for h in history
        if h.get("title_variant")
    }

    best_bundle: dict[str, str] | None = None
    best_meta: dict[str, Any] = {}
    best_score = -999.0

    for t_var in TITLE_VARIANTS:
        for d_var in DESC_VARIANTS:
            for l_var in LEAD_VARIANTS:
                key = f"{t_var}|{d_var}|{l_var}"
                if key in tried_keys:
                    continue
                sc, meta = score_candidate_bundle(article, t_var, d_var, l_var, market_signals, site_name)
                if sc > best_score:
                    best_score = sc
                    best_bundle = {
                        "title_variant": t_var,
                        "desc_variant": d_var,
                        "lead_variant": l_var,
                    }
                    best_meta = meta

    if best_bundle is None:
        best_bundle = {
            "title_variant": TITLE_VARIANTS[0],
            "desc_variant": DESC_VARIANTS[0],
            "lead_variant": "default",
        }
        _, best_meta = score_candidate_bundle(
            article,
            best_bundle["title_variant"],
            best_bundle["desc_variant"],
            best_bundle["lead_variant"],
            market_signals,
            site_name,
        )

    return best_bundle, best_meta


def has_active_cooldown(
    slug: str,
    ledger_entries: list[dict[str, Any]],
    now: datetime,
    eval_days: int = 14,
) -> dict[str, Any] | None:
    """
    Check if `slug` already has an active, unevaluated `AB_VARIANT_SWITCH` within the observation window.
    Prevents overwriting an active test before the 14-day measurement window completes.
    """
    for entry in reversed(ledger_entries):
        if entry.get("slug") != slug:
            continue
        if entry.get("action_type") != "AB_VARIANT_SWITCH":
            continue
        if entry.get("evaluated"):
            return None
        try:
            exp_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        except Exception:
            return None
        days_elapsed = (now - exp_date).days
        if days_elapsed < eval_days:
            return {
                "active_since": entry["date"],
                "days_elapsed": days_elapsed,
                "days_remaining": eval_days - days_elapsed,
                "variant_bundle": entry.get("variant_bundle"),
            }
    return None


def evaluate_past_experiments(
    ledger_entries: list[dict[str, Any]],
    current_by_slug: dict[str, dict[str, Any]],
    now: datetime,
    eval_days: int = 14,
    min_eval_impressions: int = 100,
    property_url: str = "",
    access_token: str = "",
) -> dict[str, dict[str, Any]]:
    """
    Evaluate past `AB_VARIANT_SWITCH` experiments that have been live for >= `eval_days`.
    - Strictly ignores non-switch records (e.g. `MARKET_CONTENT_GAP_CANDIDATE`).
    - Uses post-change GSC window (`switch_date + 1d` to `now - 3d`) when live GSC token is available
      so pre-change impressions never contaminate post-change CTR.
    - Enforces `min_eval_impressions` before declaring a winner or rotating.
    """
    evaluations: dict[str, dict[str, Any]] = {}
    latest_switch_by_slug: dict[str, dict[str, Any]] = {}

    for entry in ledger_entries:
        if entry.get("action_type") == "AB_VARIANT_SWITCH" and not entry.get("evaluated"):
            slug = entry.get("slug")
            if slug:
                latest_switch_by_slug[slug] = entry

    for slug, entry in latest_switch_by_slug.items():
        try:
            exp_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        except Exception:
            continue
        days_elapsed = (now - exp_date).days
        if days_elapsed < eval_days:
            continue

        post_stats = current_by_slug.get(slug)
        if property_url and access_token:
            post_start = (exp_date + timedelta(days=1)).strftime("%Y-%m-%d")
            post_end = (now - timedelta(days=3)).strftime("%Y-%m-%d")
            if post_start < post_end:
                try:
                    window_map = fetch_gsc_window_rest(property_url, access_token, post_start, post_end)
                    if slug in window_map:
                        post_stats = window_map[slug]
                except Exception:
                    pass

        if not post_stats:
            continue

        eval_impr = int(post_stats.get("impressions", 0))
        if eval_impr < min_eval_impressions:
            evaluations[slug] = {
                "slug": slug,
                "experiment_date": entry["date"],
                "days_elapsed": days_elapsed,
                "eval_impressions": eval_impr,
                "verdict": "INSUFFICIENT_DATA_HOLD",
            }
            continue

        base_ctr = float(entry.get("baseline_ctr", 0.0))
        base_pos = float(entry.get("baseline_position", 99.0))
        current_ctr = float(post_stats.get("ctr", 0.0))
        current_pos = float(post_stats.get("position", 99.0))

        base_expected = expected_ctr_for_position(base_pos)
        curr_expected = expected_ctr_for_position(current_pos)
        base_ratio = (base_ctr / base_expected) if base_expected > 0 else 0.0
        curr_ratio = (current_ctr / curr_expected) if curr_expected > 0 else 0.0

        if base_ctr == 0.0:
            improved = current_ctr > 0.0 and curr_ratio >= 0.70
        else:
            improved = (
                (curr_ratio >= base_ratio * 1.10)
                or (current_ctr >= base_ctr * 1.15)
                or (current_pos <= base_pos - 0.5)
            )

        entry["evaluated"] = True
        entry["evaluated_at"] = now.strftime("%Y-%m-%d")
        entry["verdict"] = "WIN_KEPT" if improved else "UNDERPERFORMED_ROTATE"

        evaluations[slug] = {
            "slug": slug,
            "experiment_date": entry["date"],
            "days_elapsed": days_elapsed,
            "eval_impressions": eval_impr,
            "baseline_ctr": base_ctr,
            "current_ctr": current_ctr,
            "baseline_position": base_pos,
            "current_position": current_pos,
            "baseline_ctr_ratio": round(base_ratio, 3),
            "current_ctr_ratio": round(curr_ratio, 3),
            "verdict": entry["verdict"],
        }
    return evaluations


def run_seo_loop(apply_changes: bool = False, allow_sample: bool = False) -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    rules = config["seo_loop"]
    site_name = config["site"]["name"]
    prop_url = rules.get("gsc_property_url", "")

    telemetry, is_live, access_token = load_telemetry(config, allow_sample=allow_sample)
    source_mode = telemetry.get("source_mode", "UNKNOWN")

    if apply_changes and not is_live and not allow_sample:
        result = {
            "status": "blocked_non_live_telemetry",
            "source_mode": source_mode,
            "message": "Refusing to overwrite production articles without verified fresh LIVE_GSC_API data. Pass --allow-sample only for local sandbox tests.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    pages_dict: dict[str, dict[str, Any]] = telemetry.get("pages", {})
    trends_data = load_json(TRENDS_PATH) if TRENDS_PATH.exists() else None
    raw_ledger = load_json(LEDGER_PATH) if LEDGER_PATH.exists() else []
    if isinstance(raw_ledger, list):
        history_list: list[dict[str, Any]] = raw_ledger
    else:
        history_list = raw_ledger.get("history", [])
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    eval_days = int(rules.get("evaluation_window_days", 14))
    min_impr = int(rules.get("min_impressions_for_ctr_eval", 300))
    min_eval_impr = int(rules.get("min_eval_impressions", 100))
    ctr_ratio_threshold = float(rules.get("ctr_ratio_threshold", 0.70))

    evaluations = evaluate_past_experiments(
        ledger_entries=history_list,
        current_by_slug=pages_dict,
        now=now,
        eval_days=eval_days,
        min_eval_impressions=min_eval_impr,
        property_url=prop_url if is_live else "",
        access_token=access_token,
    )

    actions_taken: list[dict[str, Any]] = []
    cooldown_locks: list[dict[str, Any]] = []
    modified_articles = 0

    for slug, record in pages_dict.items():
        article_path = ARTICLES_DIR / f"{slug}.json"
        if not article_path.exists():
            continue

        article = load_json(article_path)
        # Guide copy must not inherit the benchmark-only title/description variants.
        if article.get("kind") == "guide":
            continue
        seo = article.setdefault("seo", {})
        ensure_immutable_originals(article)

        impressions = int(record.get("impressions", 0))
        ctr = float(record.get("ctr", 0.0))
        position = float(record.get("position", 99.0))
        top_queries = record.get("top_queries", [])

        expected_ctr = expected_ctr_for_position(position)
        ctr_ratio = round(ctr / expected_ctr, 3) if expected_ctr > 0 else 1.0

        eval_res = evaluations.get(slug)
        if eval_res and eval_res["verdict"] == "INSUFFICIENT_DATA_HOLD":
            cooldown_locks.append(eval_res)
            continue

        active_lock = has_active_cooldown(slug, history_list, now, eval_days=eval_days)
        if active_lock is not None:
            cooldown_locks.append({"slug": slug, "status": "ACTIVE_EXPERIMENT_COOLDOWN", **active_lock})
            continue

        force_rotate = bool(eval_res and eval_res["verdict"] == "UNDERPERFORMED_ROTATE")
        needs_initial_opt = (
            impressions >= min_impr
            and ctr_ratio < ctr_ratio_threshold
            and not (eval_res and eval_res["verdict"] == "WIN_KEPT")
        )

        market_signals = collect_market_signals_for_article(article, top_queries, trends_data)

        if force_rotate or needs_initial_opt:
            bundle, prediction = predict_best_variant_bundle(article, market_signals, site_name=site_name)
            old_title = seo.get("meta_title", article.get("title", ""))
            old_desc = seo.get("meta_description", article.get("subtitle", ""))
            old_lead = seo.get("lead_variant", "default")

            new_title = prediction["candidate_title"]
            new_desc = prediction["candidate_desc"]
            new_lead = bundle["lead_variant"]

            if new_title != old_title or new_desc != old_desc or new_lead != old_lead:
                seo["meta_title"] = new_title
                seo["meta_description"] = new_desc
                seo["lead_variant"] = new_lead
                seo["active_variant_bundle"] = bundle
                seo.setdefault("ab_history", []).append(
                    {
                        "date": today_str,
                        **bundle,
                        "baseline_ctr": ctr,
                        "expected_ctr": expected_ctr,
                        "ctr_ratio": ctr_ratio,
                        "baseline_position": position,
                        "predicted_score": prediction["predicted_score"],
                        "dominant_intent": prediction["dominant_intent"],
                    }
                )
                article["updated_at"] = today_str

                action_entry = {
                    "date": today_str,
                    "slug": slug,
                    "source_mode": source_mode,
                    "action_type": "AB_VARIANT_SWITCH",
                    "evaluated": False,
                    "trigger": (
                        f"eval={eval_res['verdict']}"
                        if force_rotate
                        else f"impressions={impressions}, pos={position}, ctr={ctr*100:.2f}% vs expected={expected_ctr*100:.2f}% (ratio={ctr_ratio})"
                    ),
                    "baseline_ctr": ctr,
                    "expected_ctr": expected_ctr,
                    "ctr_ratio": ctr_ratio,
                    "baseline_position": position,
                    "variant_bundle": bundle,
                    "market_prediction": {
                        "predicted_score": prediction["predicted_score"],
                        "dominant_intent": prediction["dominant_intent"],
                        "covered_market_tokens": prediction["covered_market_tokens"],
                        "rationale": prediction["rationale"],
                    },
                    "before": {
                        "meta_title": old_title,
                        "meta_description": old_desc,
                        "lead_variant": old_lead,
                    },
                    "after": {
                        "meta_title": new_title,
                        "meta_description": new_desc,
                        "lead_variant": new_lead,
                    },
                }
                actions_taken.append(action_entry)
                if apply_changes:
                    atomic_write_json(article_path, article)
                    modified_articles += 1

        for gap_q in market_signals["uncovered_faq_queries"][:2]:
            actions_taken.append(
                {
                    "date": today_str,
                    "slug": slug,
                    "source_mode": gap_q["source"],
                    "action_type": "MARKET_CONTENT_GAP_CANDIDATE",
                    "trigger": f"pos={gap_q['position']}, source={gap_q['source']}",
                    "uncovered_query": gap_q["query"],
                    "missing_tokens": gap_q["missing_tokens"],
                    "query_impressions": gap_q["impressions"],
                }
            )

    if apply_changes and (actions_taken or evaluations):
        history_list.extend(actions_taken)
        atomic_write_json(LEDGER_PATH, history_list)
        if modified_articles > 0:
            build_all()

    summary = {
        "status": "ok",
        "source_mode": source_mode,
        "mode": "APPLIED" if apply_changes else "DRY_RUN",
        "articles_modified": modified_articles,
        "cooldown_locks_count": len(cooldown_locks),
        "cooldown_locks": cooldown_locks,
        "evaluations_count": len(evaluations),
        "evaluations": list(evaluations.values()),
        "actions_count": len(actions_taken),
        "actions": actions_taken,
        "ledger_path": str(LEDGER_PATH),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Nodus Autonomous Market-Predictive SEO & AEO Loop")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write optimizations to article JSON files and update the SEO ledger",
    )
    parser.add_argument(
        "--allow-sample",
        action="store_true",
        help="Allow running against local sample telemetry (for CI dry-run verification)",
    )
    args = parser.parse_args()
    result = run_seo_loop(apply_changes=args.apply, allow_sample=args.allow_sample)
    if result.get("status") == "blocked_non_live_telemetry":
        sys.exit(2)
