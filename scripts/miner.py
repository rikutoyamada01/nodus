#!/usr/bin/env python3
"""
Nodus Quantitative Data Miner (Primary Empirical Log Extractor)
Fetches community discussions and benchmark logs via official public APIs:
1. Reddit OAuth API (when REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are configured)
2. Hacker News Algolia Search API (zero-auth, high-signal technical measurements)
3. GitHub Issues & Discussions Benchmark Search API (zero-auth empirical test logs)
Filters specifically for comments/posts containing empirical measurements (units, numbers, test conditions).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
CANDIDATES_DIR = ROOT_DIR / "data" / "candidates"

# Regex matching quantitative empirical measurements (Watts, Temps, Time, Tokens, Bandwidth, Price, Sample sizes)
QUANT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:W|Wh|mWh|V|A|mVp-p|°C|C|dB|ms|fps|GB|TB|MB/s|GB/s|CU|CCU|tokens|tok/s|t/s|hrs?|hours?|mins?|%|USD|\$|円)\b",
    re.IGNORECASE,
)


def fetch_hn_quantitative(query: str, limit: int = 15) -> list[dict[str, Any]]:
    """Query Hacker News Algolia API (zero-auth, fast, high-signal technical comments)."""
    encoded = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={encoded}&tags=comment&hitsPerPage={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "NodusQuantBot/1.0"})
    findings: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for hit in data.get("hits", []):
                text = hit.get("comment_text") or ""
                clean_text = re.sub(r"<[^>]+>", " ", text)
                matches = QUANT_PATTERN.findall(clean_text)
                if len(matches) >= 2:
                    findings.append(
                        {
                            "source": "HackerNews",
                            "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                            "author": hit.get("author"),
                            "created_at": hit.get("created_at", "")[:10],
                            "extracted_numbers": list(dict.fromkeys(matches))[:10],
                            "snippet": clean_text[:360].strip(),
                        }
                    )
    except Exception as e:
        findings.append({"source": "HackerNews", "error": str(e)})
    return findings


def fetch_github_benchmarks(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Query GitHub Issues/Discussions for real-world benchmark numbers and empirical logs."""
    encoded = urllib.parse.quote(f"{query} benchmark")
    url = f"https://api.github.com/search/issues?q={encoded}&per_page={limit}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NodusQuantBot/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    findings: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("items", []):
                body = item.get("body") or ""
                combined = f"{item.get('title', '')} {body}"
                matches = QUANT_PATTERN.findall(combined)
                if len(matches) >= 2:
                    findings.append(
                        {
                            "source": "GitHub",
                            "title": item.get("title", ""),
                            "url": item.get("html_url", ""),
                            "created_at": (item.get("created_at") or "")[:10],
                            "extracted_numbers": list(dict.fromkeys(matches))[:12],
                            "snippet": combined[:360].strip(),
                        }
                    )
    except Exception as e:
        findings.append({"source": "GitHub", "error": str(e)})
    return findings


def fetch_reddit_oauth_quantitative(query: str, subreddit: str = "", limit: int = 15) -> list[dict[str, Any]]:
    """Query official Reddit OAuth API when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set."""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return []

    findings: list[dict[str, Any]] = []
    try:
        auth_bytes = f"{client_id}:{client_secret}".encode("utf-8")
        b64_auth = base64.b64encode(auth_bytes).decode("ascii")
        token_req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {b64_auth}",
                "User-Agent": "python:nodus.quant.research:v1.0",
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
                "User-Agent": "python:nodus.quant.research:v1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                combined = f"{post.get('title', '')} {post.get('selftext', '')}"
                matches = QUANT_PATTERN.findall(combined)
                if matches:
                    findings.append(
                        {
                            "source": f"r/{post.get('subreddit', 'all')}",
                            "title": post.get("title", ""),
                            "url": f"https://www.reddit.com{post.get('permalink', '')}",
                            "score": post.get("score", 0),
                            "extracted_numbers": list(dict.fromkeys(matches))[:12],
                            "snippet": combined[:360].strip(),
                        }
                    )
    except Exception as e:
        findings.append({"source": "RedditOAuth", "error": str(e)})
    return findings


def run_mine(query: str, subreddit: str = "", limit: int = 15) -> dict[str, Any]:
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    reddit_hits = fetch_reddit_oauth_quantitative(query=query, subreddit=subreddit, limit=limit)
    hn_hits = fetch_hn_quantitative(query=query, limit=limit)
    gh_hits = fetch_github_benchmarks(query=query, limit=min(limit, 10))

    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    out_file = CANDIDATES_DIR / f"mined_{slug}.json"
    payload = {
        "query": query,
        "subreddit": subreddit or "all",
        "mined_at": datetime.now().isoformat(),
        "total_quantitative_hits": len(reddit_hits) + len(hn_hits) + len(gh_hits),
        "reddit_findings": reddit_hits,
        "hn_findings": hn_hits,
        "github_findings": gh_hits,
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "query": query,
                "reddit_oauth_hits": len(reddit_hits),
                "hn_hits": len(hn_hits),
                "github_hits": len(gh_hits),
                "saved_to": str(out_file),
            },
            ensure_ascii=False,
        )
    )
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nodus Quantitative Community Miner")
    parser.add_argument("--query", required=True, help="Search query (e.g., '100W GaN thermal throttling')")
    parser.add_argument("--subreddit", default="", help="Optional subreddit name (e.g., 'UsbCHardware')")
    parser.add_argument("--limit", type=int, default=15, help="Max items per source")
    args = parser.parse_args()
    run_mine(query=args.query, subreddit=args.subreddit, limit=args.limit)
