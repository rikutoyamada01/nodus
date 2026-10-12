#!/usr/bin/env python3
"""
Nodus Search Trend & Keyword Gap Radar (`scripts/trend_radar.py`)
Zero-auth, standard-library tool to discover real-time search word trends and content gaps:

1. Google Autocomplete / Suggest API (`suggestqueries.google.com`):
   - Queries base seed keywords + high-intent technical modifiers (`比較`, `実測`, `制限`, `遅い`, `料金`, `vs`).
   - Cross-references discovered search queries against existing Nodus articles (title, h2, FAQ, tags)
     to highlight uncovered search demand ("Content Gaps").
2. Zenn Daily Tech Trends (`zenn.dev/api/articles?order=daily`):
   - Captures what Japanese developers are reading and discussing today.
3. Hacker News Frontpage (`hn.algolia.com/api/v1/search?tags=front_page`):
   - Captures surging global engineering topics.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT_DIR / "content" / "articles"
CONFIG_PATH = ROOT_DIR / "config" / "site_config.json"
OUTPUT_PATH = ROOT_DIR / "data" / "search_trends.json"

INTENT_MODIFIERS_JA = [
    "",
    " 比較",
    " 実測",
    " 制限",
    " 遅い",
    " 料金",
    " vs",
]

DEFAULT_SEEDS = [
    "Claude Code",
    "Cursor",
    "Google Colab",
    "ローカルLLM",
    "USB4 SSD",
    "GaN 充電器",
    "Wi-Fi 7 ルーター",
]


def fetch_google_suggest(query: str, hl: str = "ja", gl: str = "jp") -> list[str]:
    """Fetch real-time Google Search autocomplete suggestions (zero-auth)."""
    encoded = urllib.parse.quote(query)
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&gl={gl}&q={encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NodusTrendRadar/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                return [str(item).strip() for item in data[1] if str(item).strip()]
    except Exception:
        pass
    return []


def fetch_zenn_trending(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch today's top trending technical articles on Zenn."""
    url = f"https://zenn.dev/api/articles?order=daily&count={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NodusTrendRadar/1.0)"})
    items: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for art in data.get("articles", [])[:limit]:
                items.append(
                    {
                        "title": art.get("title", ""),
                        "liked_count": int(art.get("liked_count", 0)),
                        "comments_count": int(art.get("comments_count", 0)),
                        "url": f"https://zenn.dev{art.get('path', '')}",
                        "published_at": (art.get("published_at") or "")[:10],
                    }
                )
    except Exception:
        pass
    return items


def fetch_hn_frontpage(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch current Hacker News frontpage stories via Algolia API."""
    url = f"https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NodusTrendRadar/1.0)"})
    items: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for hit in data.get("hits", [])[:limit]:
                items.append(
                    {
                        "title": hit.get("title", ""),
                        "points": int(hit.get("points") or 0),
                        "num_comments": int(hit.get("num_comments") or 0),
                        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    }
                )
    except Exception:
        pass
    return items


def load_existing_corpus() -> tuple[str, list[dict[str, Any]]]:
    """Load all published article text and metadata to check keyword coverage."""
    articles: list[dict[str, Any]] = []
    blobs: list[str] = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            art = json.loads(path.read_text(encoding="utf-8"))
            articles.append(art)
            parts = [
                art.get("title", ""),
                art.get("meta_title", ""),
                art.get("subtitle", ""),
                " ".join(art.get("tags", [])),
                " ".join(s.get("heading", "") for s in art.get("sections", [])),
                " ".join(f.get("q", "") for f in art.get("faq", [])),
            ]
            blobs.append(" ".join(parts).lower())
        except Exception:
            continue
    return " ".join(blobs), articles


def is_query_covered(suggestion: str, corpus_lower: str) -> bool:
    """Check whether all meaningful tokens of a search suggestion appear in our article corpus."""
    tokens = [t.strip().lower() for t in suggestion.split() if len(t.strip()) >= 2]
    if not tokens:
        return True
    return all(tok in corpus_lower for tok in tokens)


def collect_seed_suggestions(seeds: list[str], expand_modifiers: bool = True) -> list[dict[str, Any]]:
    """Expand seed keywords with Google Suggest and identify uncovered content gaps."""
    corpus_lower, _ = load_existing_corpus()
    results: list[dict[str, Any]] = []

    modifiers = INTENT_MODIFIERS_JA if expand_modifiers else [""]
    for seed in seeds:
        seen_suggestions: list[str] = []
        uncovered_gaps: list[str] = []
        for mod in modifiers:
            q = f"{seed}{mod}"
            for s in fetch_google_suggest(q):
                if s not in seen_suggestions:
                    seen_suggestions.append(s)
                    if not is_query_covered(s, corpus_lower):
                        uncovered_gaps.append(s)
        results.append(
            {
                "seed": seed,
                "total_suggestions": len(seen_suggestions),
                "top_suggestions": seen_suggestions[:15],
                "uncovered_content_gaps": uncovered_gaps[:12],
            }
        )
    return results


def run_trend_radar(seeds: list[str], expand_modifiers: bool = True) -> dict[str, Any]:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    suggest_report = collect_seed_suggestions(seeds, expand_modifiers=expand_modifiers)
    zenn_trends = fetch_zenn_trending(limit=10)
    hn_trends = fetch_hn_frontpage(limit=10)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "google_suggest_analysis": suggest_report,
        "zenn_daily_trending": zenn_trends,
        "hackernews_frontpage": hn_trends,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Nodus Search Word Trend & Keyword Gap Radar")
    parser.add_argument(
        "--seeds",
        nargs="*",
        default=[],
        help="Custom seed keywords to query Google Suggest (e.g., --seeds 'Claude Code' 'Haiku 5.5')",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Query only base seed without intent modifiers for faster output",
    )
    args = parser.parse_args()
    target_seeds = args.seeds if args.seeds else DEFAULT_SEEDS
    report = run_trend_radar(seeds=target_seeds, expand_modifiers=not args.fast)
    print(json.dumps(report, ensure_ascii=False, indent=2))
