#!/usr/bin/env python3
"""
Nodus Quantitative Data Miner (Primary Empirical Log Extractor)
Fetches community discussions and benchmark logs via official public APIs:
1. Reddit OAuth API (when REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are configured)
2. Hacker News Algolia Search API (zero-auth, high-signal technical measurements)
3. GitHub Issues & Discussions Benchmark Search API (zero-auth empirical test logs)

Compliance & Quality Gates:
- Extracts only non-copyrightable factual measurements (numbers + units + source URL + date).
- Never stores verbatim comment prose snippets in repository files.
- Enforces query keyword relevance filtering and separates API errors from valid hits.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "site_config.json"
CANDIDATES_DIR = ROOT_DIR / "data" / "candidates"

# Strict quantitative unit regex: captures optional sign, comma-grouped or decimal numbers, and compound units first
QUANT_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9_])[-+]?(?:[1-9]\d*(?:,\d{3})+|[1-9]\d*|0)(?:\.\d+)?\s*(?:mVp-p|MB/s|GB/s|Gbps|tok/s|t/s|tokens|hours?|hrs?|mins?|degC|°C|mWh|CCU|USD|Wh|GB|TB|CU|ms|fps|dBA|dB|W|V|(?-i:A)|\$|円)(?![a-zA-Z0-9_/])",
    re.IGNORECASE,
)


def is_relevant(text: str, query: str) -> bool:
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", query) if len(t) >= 2]
    if not tokens:
        return True
    lower_text = text.lower()
    matched = sum(1 for t in tokens if t in lower_text)
    return matched >= max(1, (len(tokens) + 1) // 2)


def normalize_measurements(matches: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for m in matches:
        norm = re.sub(r"\s+", " ", m.strip())
        key = norm.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(norm)
    return cleaned[:12]


def fetch_hn_quantitative(query: str, limit: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Query Hacker News Algolia API for comments with relevant quantitative measurements."""
    encoded = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={encoded}&tags=comment&hitsPerPage={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "NodusQuantBot/1.1"})
    findings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for hit in data.get("hits", []):
                raw_html = hit.get("comment_text") or ""
                clean_text = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
                if not is_relevant(clean_text, query):
                    continue
                matches = normalize_measurements(QUANT_PATTERN.findall(clean_text))
                if len(matches) >= 2:
                    findings.append(
                        {
                            "source": "HackerNews",
                            "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                            "author": hit.get("author") or "anonymous",
                            "created_at": (hit.get("created_at") or "")[:10],
                            "measurement_count": len(matches),
                            "extracted_numbers": matches,
                        }
                    )
    except Exception as e:
        errors.append({"source": "HackerNews", "error": str(e)})
    return findings, errors


def fetch_github_benchmarks(query: str, limit: int = 10) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Query GitHub Issues/Discussions for real-world benchmark numbers and empirical logs."""
    encoded = urllib.parse.quote(f"{query} benchmark")
    url = f"https://api.github.com/search/issues?q={encoded}&per_page={limit}"
    headers = {
        "User-Agent": "NodusQuantBot/1.1",
        "Accept": "application/vnd.github+json",
    }
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    req = urllib.request.Request(url, headers=headers)
    findings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("items", []):
                title = (item.get("title") or "").strip()[:140]
                body = item.get("body") or ""
                combined = f"{title} {body}"
                if not is_relevant(combined, query):
                    continue
                matches = normalize_measurements(QUANT_PATTERN.findall(combined))
                if len(matches) >= 2:
                    findings.append(
                        {
                            "source": "GitHub",
                            "title": title,
                            "url": item.get("html_url", ""),
                            "created_at": (item.get("created_at") or "")[:10],
                            "measurement_count": len(matches),
                            "extracted_numbers": matches,
                        }
                    )
    except Exception as e:
        errors.append({"source": "GitHub", "error": str(e)})
    return findings, errors


def fetch_reddit_oauth_quantitative(
    query: str, subreddit: str = "", limit: int = 15
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Query official Reddit OAuth API when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set."""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return [], []

    findings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        auth_bytes = f"{client_id}:{client_secret}".encode("utf-8")
        b64_auth = base64.b64encode(auth_bytes).decode("ascii")
        token_req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {b64_auth}",
                "User-Agent": "python:nodus.quant.research:v1.1",
            },
        )
        with urllib.request.urlopen(token_req, timeout=10) as tresp:
            token = json.loads(tresp.read().decode("utf-8")).get("access_token")

        encoded = urllib.parse.quote(query)
        path = f"/r/{subreddit}/search" if subreddit else "/search"
        url = f"https://oauth.reddit.com{path}?q={encoded}&restrict_sr=1&sort=relevance&limit={limit}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "python:nodus.quant.research:v1.1",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                title = (post.get("title") or "").strip()[:140]
                combined = f"{title} {post.get('selftext', '')}"
                if not is_relevant(combined, query):
                    continue
                matches = normalize_measurements(QUANT_PATTERN.findall(combined))
                if len(matches) >= 2:
                    findings.append(
                        {
                            "source": f"r/{post.get('subreddit', 'all')}",
                            "title": title,
                            "url": f"https://www.reddit.com{post.get('permalink', '')}",
                            "score": int(post.get("score", 0)),
                            "measurement_count": len(matches),
                            "extracted_numbers": matches,
                        }
                    )
    except Exception as e:
        errors.append({"source": "RedditOAuth", "error": str(e)})
    return findings, errors


def run_mine(query: str, subreddit: str = "", limit: int = 15) -> dict[str, Any]:
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    reddit_hits, reddit_errs = fetch_reddit_oauth_quantitative(query=query, subreddit=subreddit, limit=limit)
    hn_hits, hn_errs = fetch_hn_quantitative(query=query, limit=limit)
    gh_hits, gh_errs = fetch_github_benchmarks(query=query, limit=min(limit, 10))

    all_errors = reddit_errs + hn_errs + gh_errs
    total_hits = len(reddit_hits) + len(hn_hits) + len(gh_hits)

    base_slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    sub_slug = re.sub(r"[^a-z0-9]+", "-", subreddit.lower()).strip("-") if subreddit else ""
    if not base_slug:
        import hashlib
        base_slug = "query-" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    slug = f"{base_slug}-{sub_slug}" if sub_slug and sub_slug not in base_slug else base_slug
    out_file = CANDIDATES_DIR / f"mined_{slug}.json"
    tmp_file = CANDIDATES_DIR / f"mined_{slug}.json.tmp"
    payload = {
        "query": query,
        "subreddit": subreddit or "all",
        "mined_at": datetime.now().isoformat(),
        "status": "ok" if not all_errors or total_hits > 0 else "degraded",
        "total_quantitative_hits": total_hits,
        "reddit_findings": reddit_hits,
        "hn_findings": hn_hits,
        "github_findings": gh_hits,
        "errors": all_errors,
    }
    tmp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_file.replace(out_file)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "query": query,
                "reddit_oauth_hits": len(reddit_hits),
                "hn_hits": len(hn_hits),
                "github_hits": len(gh_hits),
                "errors_count": len(all_errors),
                "saved_to": str(out_file),
            },
            ensure_ascii=False,
        )
    )
    return payload


def run_all_configured(limit: int = 15) -> list[dict[str, Any]]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = json.load(f)
    results = []
    for topic in config.get("mining_topics", []):
        results.append(
            run_mine(
                query=topic["query"],
                subreddit=topic.get("subreddit", ""),
                limit=limit,
            )
        )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nodus Quantitative Community Miner")
    parser.add_argument("--query", default="", help="Search query (e.g., '100W GaN thermal throttling')")
    parser.add_argument("--subreddit", default="", help="Optional subreddit name (e.g., 'UsbCHardware')")
    parser.add_argument("--limit", type=int, default=15, help="Max items per source")
    parser.add_argument(
        "--all-configured",
        action="store_true",
        help="Mine all topics configured in config/site_config.json",
    )
    args = parser.parse_args()
    if args.all_configured:
        run_all_configured(limit=args.limit)
    elif args.query:
        run_mine(query=args.query, subreddit=args.subreddit, limit=args.limit)
    else:
        parser.error("Provide --query or --all-configured")
