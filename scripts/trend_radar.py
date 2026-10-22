#!/usr/bin/env python3
"""
Nodus Search Trend & Market Intent Radar (`scripts/trend_radar.py`)
Discovers real-time search word trends and maps them per-article against Nodus's empirical corpus:

1. Dynamic Seed Extraction from `content/articles/*.json` (no reliance on static hardcoded seeds alone).
2. Google Autocomplete / Suggest API (`suggestqueries.google.com`) with technical intent modifiers.
3. Japanese compound-aware tokenization (preserving 1-kanji technical terms like 熱, 音, 差, 値 and splitting
   unspaced suffixes like `充電器比較` -> `充電器` + `比較`).
4. Per-article coverage diagnosis:
   - `fully_covered_in_meta`: Query tokens are already in the article's `seo.meta_title` or `faqs`.
   - `answer_in_body_missing_in_title`: Article body/table has the answer, but `meta_title` misses the query token (Prime Title Optimization target!).
   - `content_gap_missing_in_article`: Neither meta nor body covers the intent token (FAQ / Content addition target!).
5. Zenn Daily Tech Trends & Hacker News Frontpage for emerging engineering topics.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT_DIR / "content" / "articles"
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

# Known Japanese intent/modifier words to split even when written without spaces (e.g., "充電器比較", "ローカルllmとは")
KNOWN_SUFFIX_SPLIT_WORDS = [
    "ベンチマーク",
    "おすすめ",
    "ランキング",
    "インストール",
    "使い方",
    "始め方",
    "比較",
    "実測",
    "制限",
    "時間",
    "料金",
    "価格",
    "無料",
    "遅い",
    "発熱",
    "温度",
    "騒音",
    "寿命",
    "対策",
    "原因",
    "違い",
    "とは",
    "スペック",
    "モデル",
    "サイト",
    "データ",
    "検証",
]

INTENT_PATTERNS: dict[str, list[str]] = {
    "comparison": ["比較", "vs", "違い", "どっち", "おすすめ", "対決", "選び方"],
    "metric_cost_spec": ["料金", "価格", "制限", "時間", "速度", "実測", "消費", "温度", "熱", "騒音", "音", "寿命", "スペック", "容量", "コスパ", "トークン"],
    "question_troubleshoot": ["とは", "使い方", "なぜ", "原因", "遅い", "エラー", "できない", "対策", "落ちる", "止まる"],
    "dataset_benchmark": ["ベンチマーク", "データ", "検証", "測定", "ログ", "csv", "一覧", "表"],
}


def normalize_text_ja(text: str) -> str:
    """Normalize case, full-width alphanumeric characters, and punctuation."""
    if not text:
        return ""
    s = text.lower()
    # Convert full-width ASCII to half-width
    s = s.translate(
        str.maketrans(
            "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９",
            "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz0123456789",
        )
    )
    return re.sub(r"\s+", " ", s).strip()


def tokenize_japanese_query(query: str) -> list[str]:
    """
    Tokenize a Japanese/English search query without dropping 1-character Kanji terms (e.g. 熱, 音, 差)
    and splitting compound Japanese words that lack spaces (e.g. '充電器比較' -> ['充電器', '比較']).
    """
    norm = normalize_text_ja(query)
    if not norm:
        return []

    # Insert boundaries around known Japanese intent words when attached without spaces
    spaced = norm
    for kw in sorted(KNOWN_SUFFIX_SPLIT_WORDS, key=len, reverse=True):
        spaced = spaced.replace(kw, f" {kw} ")

    # Remove common Japanese particles when flanked by spaces or between tokens
    spaced = re.sub(r"(?<=[一-龥ァ-ヶーa-z0-9])[のとはがをにでとやもへからまでより](?=[一-龥ァ-ヶーa-z0-9])", " ", spaced)

    raw_chunks = re.findall(r"[a-z0-9][a-z0-9.\-+]*|[一-龥]+|[ァ-ヶー]{2,}", spaced)
    tokens: list[str] = []
    stopwords = {"の", "と", "は", "が", "を", "に", "で", "や", "も", "へ", "から", "まで", "こと", "ため"}
    for chunk in raw_chunks:
        c = chunk.strip(".-+")
        if not c or c in stopwords:
            continue
        # Keep 1-char Kanji (e.g. 熱, 音, 表, 差, 値, 数) because they carry critical technical meaning
        if len(c) == 1 and not re.match(r"^[一-龥]$", c):
            continue
        if c not in tokens:
            tokens.append(c)
    return tokens


def classify_search_intent(query: str) -> str:
    """Classify the dominant search intent of a query."""
    norm = normalize_text_ja(query)
    scores: Counter[str] = Counter()
    for intent, keywords in INTENT_PATTERNS.items():
        for kw in keywords:
            if kw in norm:
                scores[intent] += 1
    if not scores:
        return "metric_cost_spec"
    return scores.most_common(1)[0][0]


def derive_seed_for_article(article: dict[str, Any]) -> str:
    """Derive a clean, market-searchable Japanese seed phrase from an article's seo.primary_seed or title."""
    explicit = article.get("seo", {}).get("primary_seed") or article.get("primary_seed")
    if explicit:
        return str(explicit).strip()

    title = str(article.get("title", "")).strip()
    if title:
        head = re.split(r"[「？｜|]", title)[0]
        head = re.sub(r"（[^）]*）|\([^)]*\)", " ", head)
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-+]*|[一-龥ァ-ヶー]{2,}", head)
        stop = {"実測", "比較", "検証", "データベース", "推論", "主要", "高性能", "1000Wh級", "4機種の", "5社の"}
        clean_tokens = [t for t in tokens if t not in stop]
        if len(clean_tokens) >= 2:
            return " ".join(clean_tokens[:2])
        if clean_tokens:
            return clean_tokens[0]

    tags = [str(t).strip() for t in article.get("tags", []) if str(t).strip() and str(t).lower() not in {"first-party", "benchmark"}]
    if tags:
        return tags[0]
    return title[:20].strip()


def load_articles_structured() -> list[dict[str, Any]]:
    """Load all articles from `content/articles/*.json` with normalized fields matching Nodus schema."""
    records: list[dict[str, Any]] = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            art = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        seo = art.get("seo", {})
        meta_title = seo.get("meta_title") or art.get("meta_title") or art.get("title", "")
        meta_desc = seo.get("meta_description") or art.get("meta_description") or art.get("subtitle", "")
        faqs = art.get("faqs") or art.get("faq") or []
        faq_text = " ".join(
            f"{f.get('question') or f.get('q', '')} {f.get('answer') or f.get('a', '')}" for f in faqs
        )
        headings_text = " ".join(s.get("heading", "") for s in art.get("sections", []))
        body_text = " ".join(
            [
                art.get("title", ""),
                art.get("subtitle", ""),
                " ".join(art.get("tldr", [])),
                headings_text,
                " ".join(s.get("body", "") for s in art.get("sections", [])),
                faq_text,
                json.dumps(art.get("comparison_table", {}), ensure_ascii=False),
            ]
        )
        records.append(
            {
                "slug": art.get("slug", path.stem),
                "title": art.get("title", ""),
                "seed": derive_seed_for_article(art),
                "tags": art.get("tags", []),
                "meta_norm": normalize_text_ja(f"{meta_title} {meta_desc}"),
                "title_norm": normalize_text_ja(f"{meta_title} {art.get('title', '')}"),
                "faq_heading_norm": normalize_text_ja(f"{headings_text} {faq_text}"),
                "body_norm": normalize_text_ja(body_text),
            }
        )
    return records


def evaluate_query_against_article(query: str, art_rec: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluate how well a single target article covers a search suggestion.
    Distinguishes between:
    - `covered_in_title`: All query tokens already appear in `meta_title` / `title`
    - `answer_in_body_missing_in_title`: Article body/table/FAQ has the tokens, but title misses them (Title optimization opportunity!)
    - `missing_in_article`: Article lacks specific intent/entity tokens (FAQ / Section expansion opportunity!)
    """
    tokens = tokenize_japanese_query(query)
    if not tokens:
        return {
            "status": "covered_in_title",
            "tokens": [],
            "missing_in_title": [],
            "missing_in_body": [],
            "intent": classify_search_intent(query),
        }

    missing_in_title = [t for t in tokens if t not in art_rec["title_norm"]]
    missing_in_body = [t for t in tokens if t not in art_rec["body_norm"]]

    if not missing_in_title:
        status = "covered_in_title"
    elif not missing_in_body:
        status = "answer_in_body_missing_in_title"
    else:
        status = "missing_in_article"

    return {
        "status": status,
        "tokens": tokens,
        "missing_in_title": missing_in_title,
        "missing_in_body": missing_in_body,
        "intent": classify_search_intent(query),
    }


def fetch_google_suggest(query: str, hl: str = "ja", gl: str = "jp") -> list[str]:
    """Fetch real-time Google Search autocomplete suggestions (zero-auth)."""
    encoded = urllib.parse.quote(query)
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&gl={gl}&q={encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NodusTrendRadar/2.0)"})
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
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NodusTrendRadar/2.0)"})
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
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NodusTrendRadar/2.0)"})
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


def analyze_articles_and_seeds(
    custom_seeds: list[str] | None = None,
    expand_modifiers: bool = True,
) -> list[dict[str, Any]]:
    """
    Analyze search suggestions per article (or per custom seed matched to the closest article).
    """
    articles = load_articles_structured()
    modifiers = INTENT_MODIFIERS_JA if expand_modifiers else [""]
    results: list[dict[str, Any]] = []

    if custom_seeds:
        targets = []
        for s in custom_seeds:
            s_norm = normalize_text_ja(s)
            best_art = None
            best_score = -1
            for art in articles:
                score = sum(1 for tok in tokenize_japanese_query(s_norm) if tok in art["body_norm"])
                if score > best_score:
                    best_score = score
                    best_art = art
            targets.append((s, best_art))
    else:
        targets = [(art["seed"], art) for art in articles]

    for seed, art in targets:
        seen_suggestions: list[str] = []
        title_opportunities: list[dict[str, Any]] = []
        content_gaps: list[dict[str, Any]] = []
        intent_counts: Counter[str] = Counter()

        candidate_seeds = [seed]
        parts = seed.split()
        if len(parts) > 2:
            candidate_seeds.append(" ".join(parts[:2]))
        if len(parts) > 1:
            candidate_seeds.append(parts[0])

        for cand_seed in candidate_seeds:
            for mod in modifiers:
                q = f"{cand_seed}{mod}"
                for s in fetch_google_suggest(q):
                    if s not in seen_suggestions:
                        seen_suggestions.append(s)
                        intent = classify_search_intent(s)
                        intent_counts[intent] += 1
                        if art:
                            eval_res = evaluate_query_against_article(s, art)
                            if eval_res["status"] == "answer_in_body_missing_in_title":
                                title_opportunities.append(
                                    {
                                        "query": s,
                                        "intent": eval_res["intent"],
                                        "missing_in_title": eval_res["missing_in_title"],
                                    }
                                )
                            elif eval_res["status"] == "missing_in_article":
                                content_gaps.append(
                                    {
                                        "query": s,
                                        "intent": eval_res["intent"],
                                        "missing_in_body": eval_res["missing_in_body"],
                                    }
                                )
            if seen_suggestions:
                break

        dominant_intent = intent_counts.most_common(1)[0][0] if intent_counts else "metric_cost_spec"
        results.append(
            {
                "slug": art["slug"] if art else None,
                "seed": seed,
                "dominant_market_intent": dominant_intent,
                "intent_distribution": dict(intent_counts),
                "total_suggestions": len(seen_suggestions),
                "top_suggestions": seen_suggestions[:12],
                "title_optimization_opportunities": title_opportunities[:8],
                "uncovered_content_gaps": content_gaps[:8],
            }
        )
    return results


def run_trend_radar(seeds: list[str] | None = None, expand_modifiers: bool = True) -> dict[str, Any]:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    suggest_report = analyze_articles_and_seeds(custom_seeds=seeds, expand_modifiers=expand_modifiers)
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
    parser = argparse.ArgumentParser(description="Nodus Search Word Trend & Market Intent Radar")
    parser.add_argument(
        "--seeds",
        nargs="*",
        default=[],
        help="Optional custom seed keywords (if omitted, automatically extracts seeds from all published articles)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Query only base seed without intent modifiers for faster output",
    )
    args = parser.parse_args()
    report = run_trend_radar(seeds=args.seeds if args.seeds else None, expand_modifiers=not args.fast)
    print(json.dumps(report, ensure_ascii=False, indent=2))
