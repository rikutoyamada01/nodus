#!/usr/bin/env python3
"""
Nodus Instant Search & Answer Engine Indexer (`scripts/ping_index.py`)
Automatically submits all canonical Nodus URLs and sitemaps to search & answer engines:
1. IndexNow Protocol (`api.indexnow.org` & `www.bing.com/indexnow`):
   - Immediately notifies Bing, Yandex, Naver, Seznam, and Bing-backed AI Search (ChatGPT Search / Copilot)
     using the site's static key file (`/<indexnow_key>.txt`).
2. Google Search Console Sitemap Submit API (`webmasters/v3/sites/.../sitemaps/...`):
   - Automatically submits `sitemap.xml` to Google Search Console when `GSC_ACCESS_TOKEN` or
     OAuth2 refresh credentials (`GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`, `GSC_REFRESH_TOKEN`) are configured.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from seo_loop import resolve_gsc_access_token

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "site_config.json"
ARTICLES_DIR = ROOT_DIR / "content" / "articles"


def collect_canonical_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    urls = [
        f"{base}/",
        f"{base}/index.html",
        f"{base}/about",
        f"{base}/sitemap.xml",
        f"{base}/llms.txt",
        f"{base}/llms-full.txt",
    ]
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            art = json.loads(path.read_text(encoding="utf-8"))
            slug = art.get("slug", path.stem)
            urls.append(f"{base}/articles/{slug}")
            urls.append(f"{base}/articles/{slug}.md")
        except Exception:
            continue
    return urls


def submit_indexnow(base_url: str, key: str, urls: list[str]) -> list[dict[str, Any]]:
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.netloc
    key_location = f"{base_url.rstrip('/')}/{key}.txt"
    payload = json.dumps(
        {
            "host": host,
            "key": key,
            "keyLocation": key_location,
            "urlList": urls,
        }
    ).encode("utf-8")

    endpoints = [
        "https://api.indexnow.org/indexnow",
        "https://www.bing.com/indexnow",
    ]
    results: list[dict[str, Any]] = []
    for ep in endpoints:
        req = urllib.request.Request(
            ep,
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Mozilla/5.0 (compatible; NodusIndexPinger/1.0)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                results.append(
                    {
                        "endpoint": ep,
                        "status_code": resp.status,
                        "urls_submitted": len(urls),
                        "status": "accepted",
                    }
                )
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            results.append(
                {
                    "endpoint": ep,
                    "status_code": e.code,
                    "status": "http_error",
                    "detail": body or str(e),
                }
            )
        except Exception as e:
            results.append({"endpoint": ep, "status": "error", "detail": str(e)})
    return results


def submit_gsc_sitemap(property_url: str, sitemap_url: str, access_token: str) -> dict[str, Any]:
    if not access_token:
        return {
            "engine": "GoogleSearchConsole",
            "status": "skipped_no_token",
            "note": "Set GSC_CLIENT_ID / GSC_CLIENT_SECRET / GSC_REFRESH_TOKEN or submit sitemap.xml once in Google Search Console UI.",
        }
    enc_prop = urllib.parse.quote(property_url, safe="")
    enc_sm = urllib.parse.quote(sitemap_url, safe="")
    api_url = f"https://www.googleapis.com/webmasters/v3/sites/{enc_prop}/sitemaps/{enc_sm}"
    req = urllib.request.Request(
        api_url,
        data=b"",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Length": "0",
            "User-Agent": "NodusIndexPinger/1.0",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return {
                "engine": "GoogleSearchConsole",
                "status": "submitted",
                "status_code": resp.status,
                "sitemap_url": sitemap_url,
            }
    except Exception as e:
        return {"engine": "GoogleSearchConsole", "status": "error", "detail": str(e)}


def run_ping() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    base_url = config["site"]["base_url"].rstrip("/")
    seo_cfg = config.get("seo_loop", {})
    key = str(seo_cfg.get("indexnow_key", "")).strip()
    prop_url = str(seo_cfg.get("gsc_property_url") or f"{base_url}/").strip()
    sitemap_url = f"{base_url}/sitemap.xml"

    urls = collect_canonical_urls(base_url)
    indexnow_res = submit_indexnow(base_url, key, urls) if key else []
    token = ""
    try:
        token = resolve_gsc_access_token()
    except Exception:
        pass
    gsc_res = submit_gsc_sitemap(prop_url, sitemap_url, token)

    report = {
        "base_url": base_url,
        "urls_count": len(urls),
        "indexnow": indexnow_res,
        "google_search_console": gsc_res,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_ping()
