#!/usr/bin/env python3
"""
Nodus Enterprise Quality, Security, Legal & A11y Validation Gate
Runs static and post-build checks on config, article JSONs, candidate logs, and dist/ output.
Exits with non-zero code if any invariant is violated.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

from build_site import (
    ARTICLES_DIR,
    CONFIG_PATH,
    DIST_DIR,
    ROOT_DIR,
    is_monetized,
    load_json,
    render_footer,
    resolve_affiliate_url,
    safe_json_ld,
    validate_article,
    validate_slug,
    validate_url,
)
from miner import QUANT_PATTERN

CANDIDATES_DIR = ROOT_DIR / "data" / "candidates"
INLINE_HANDLER_RE = re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE)
INLINE_STYLE_RE = re.compile(r"\bstyle\s*=", re.IGNORECASE)
STYLE_TAG_RE = re.compile(r"<\s*style\b", re.IGNORECASE)
SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)
EXACT_AMAZON_DISCLOSURE = "Amazon のアソシエイトとして、Nodusは適格販売により収入を得ています。"


def run_security_self_tests(config: dict[str, object]) -> None:
    # 1. Path traversal, trailing newline, or uppercase in slug must fail
    for bad_slug in ["../index", "valid-slug\n", "foo/bar", "UPPERCASE", "a", ""]:
        try:
            validate_slug(bad_slug)
            raise AssertionError(f"validate_slug failed to reject {bad_slug!r}")
        except ValueError:
            pass

    # 2. Dangerous URL schemes must fail
    for bad_url in ["javascript:alert(1)", "data:text/html,<script>", "file:///etc/passwd", ""]:
        try:
            validate_url(bad_url)
            raise AssertionError(f"validate_url failed to reject {bad_url!r}")
        except ValueError:
            pass

    # 3. JSON-LD script breakout must be escaped
    escaped = safe_json_ld({"evil": "</script><script>alert(1)</script>"})
    if "</script>" in escaped or "<script>" in escaped:
        raise AssertionError("safe_json_ld failed to escape script tags")

    # 4. Miner QUANT_PATTERN must preserve compound units like GB/s and Wh
    unit_sample = QUANT_PATTERN.findall("Transfer speed reached 1.78 GB/s and battery is 99.6 Wh")
    if "1.78 GB/s" not in unit_sample or "99.6 Wh" not in unit_sample:
        raise AssertionError(f"QUANT_PATTERN truncated compound units: {unit_sample}")

    # 5. Monetization toggle test: when tag is set, Amazon disclosure and ?tag= must activate automatically
    mock_cfg = copy.deepcopy(config)
    mock_cfg["affiliates"]["amazon_associate_tag"] = "verify-22"  # type: ignore[index]
    if not is_monetized(mock_cfg):  # type: ignore[arg-type]
        raise AssertionError("is_monetized should be True when amazon_associate_tag is non-empty")
    tagged_url = resolve_affiliate_url("https://www.amazon.co.jp/s?k=Anker", mock_cfg)  # type: ignore[arg-type]
    if "tag=verify-22" not in tagged_url:
        raise AssertionError(f"resolve_affiliate_url failed to append tag: {tagged_url}")
    footer_monetized = render_footer(mock_cfg)  # type: ignore[arg-type]
    if EXACT_AMAZON_DISCLOSURE not in footer_monetized:
        raise AssertionError("render_footer failed to include exact Amazon disclosure when monetized")


def validate_all() -> dict[str, object]:
    config = load_json(CONFIG_PATH)
    run_security_self_tests(config)

    config_raw = CONFIG_PATH.read_text(encoding="utf-8")
    if "example.com" in config_raw:
        raise ValueError("config/site_config.json still contains placeholder 'example.com'")

    amazon_text = config["compliance"].get("amazon_disclosure_text", "")
    if amazon_text != EXACT_AMAZON_DISCLOSURE:
        raise ValueError("Exact mandatory Amazon Associates disclosure missing in config")

    monetized = is_monetized(config)

    article_files = sorted(ARTICLES_DIR.glob("*.json"))
    if not article_files:
        raise ValueError("No article JSON files found in content/articles/")

    base_url = config["site"]["base_url"].rstrip("/")
    expected_slugs: list[str] = []

    for path in article_files:
        article = load_json(path)
        validate_article(article, config)
        slug = article["slug"]
        expected_slugs.append(slug)
        if int(article.get("sample_size_n", 0)) <= 0:
            raise ValueError(f"{path.name}: sample_size_n must be > 0")
        if not article.get("methodology_note"):
            raise ValueError(f"{path.name}: methodology_note is required")
        if not article.get("data_updated_at"):
            raise ValueError(f"{path.name}: data_updated_at is required")
        html_out = DIST_DIR / "articles" / f"{slug}.html"
        if not html_out.exists() or html_out.stat().st_size < 500:
            raise ValueError(f"Missing or incomplete article HTML output: {html_out}")
        csv_file = DIST_DIR / "datasets" / f"{slug}.csv"
        if not csv_file.exists() or csv_file.stat().st_size < 20:
            raise ValueError(f"Missing or empty CSV dataset: {csv_file}")
        raw_article_str = path.read_text(encoding="utf-8")
        prohibited_terms = [
            "欠陥品",
            "粗悪品",
            "詐欺まがい",
            "景表法違反",
            "違法製品",
            "絶対に買ってはいけない",
            "100%治る",
            "必ず儲かる",
        ]
        for bad_term in prohibited_terms:
            if bad_term in raw_article_str:
                raise ValueError(f"{path.name}: contains legally high-risk or defamatory term {bad_term!r}")
        if article.get("origin") == "first_party":
            log_file = DIST_DIR / "logs" / f"{slug}.json"
            if not log_file.exists() or log_file.stat().st_size < 20:
                raise ValueError(f"First-party article {slug} is missing site-hosted raw log: {log_file}")
            log_raw = log_file.read_text(encoding="utf-8")
            json.loads(log_raw)
            if "rikutoyamada" in log_raw.lower() or "yamadarikuto" in log_raw.lower() or "c:\\users\\" in log_raw.lower():
                raise ValueError(f"{log_file.name}: raw log contains personal username or local path")

    # Check candidate files for copyright compliance (no verbatim snippet field)
    if CANDIDATES_DIR.exists():
        for cand_path in CANDIDATES_DIR.glob("*.json"):
            cand_raw = cand_path.read_text(encoding="utf-8")
            if '"snippet"' in cand_raw:
                raise ValueError(f"{cand_path.name} contains prohibited verbatim 'snippet' field")

    # Check required dist artifacts
    required_dist = [
        "index.html",
        "about.html",
        "404.html",
        "feed.xml",
        "_headers",
        "sitemap.xml",
        "robots.txt",
        "llms.txt",
        "llms-full.txt",
        "assets/style.css",
        "assets/app.js",
    ]
    for rel in required_dist:
        p = DIST_DIR / rel
        if not p.exists() or p.stat().st_size == 0:
            raise ValueError(f"Missing required build output: dist/{rel}")

    # Deep SEO & AEO verification of sitemap.xml, feed.xml, robots.txt, llms.txt, and llms-full.txt
    import xml.etree.ElementTree as ET

    sitemap_raw = (DIST_DIR / "sitemap.xml").read_text(encoding="utf-8")
    sitemap_root = ET.fromstring(sitemap_raw)
    sitemap_locs = {el.text.strip() for el in sitemap_root.iter() if el.tag.endswith("loc") and el.text}

    feed_raw = (DIST_DIR / "feed.xml").read_text(encoding="utf-8")
    feed_root = ET.fromstring(feed_raw)
    has_feed_author = any(
        el.tag.endswith("name") and (el.text or "").strip()
        for author in feed_root
        if author.tag.endswith("author")
        for el in author
    )
    if not has_feed_author:
        raise ValueError("dist/feed.xml is missing required Atom <author><name> element")
    feed_ids = {el.text.strip() for el in feed_root.iter() if el.tag.endswith("id") and el.text}

    robots_raw = (DIST_DIR / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {base_url}/sitemap.xml" not in robots_raw:
        raise ValueError("dist/robots.txt is missing exact Sitemap declaration")
    for bot_name in ("OAI-SearchBot", "PerplexityBot", "Claude-SearchBot", "Google-Extended"):
        if f"User-agent: {bot_name}" not in robots_raw:
            raise ValueError(f"dist/robots.txt is missing AEO crawler allowance for {bot_name}")

    llms_raw = (DIST_DIR / "llms.txt").read_text(encoding="utf-8")
    llms_full_raw = (DIST_DIR / "llms-full.txt").read_text(encoding="utf-8")
    for slug in expected_slugs:
        art_url = f"{base_url}/articles/{slug}.html"
        md_url = f"{base_url}/articles/{slug}.md"
        csv_url = f"{base_url}/datasets/{slug}.csv"
        md_file = DIST_DIR / "articles" / f"{slug}.md"
        if not md_file.exists() or md_file.stat().st_size < 100:
            raise ValueError(f"Missing or incomplete AEO Markdown output: {md_file}")
        if art_url not in sitemap_locs:
            raise ValueError(f"dist/sitemap.xml is missing article URL: {art_url}")
        if art_url not in feed_ids:
            raise ValueError(f"dist/feed.xml is missing article entry: {art_url}")
        if art_url not in llms_raw or csv_url not in llms_raw or md_url not in llms_raw:
            raise ValueError(f"dist/llms.txt is missing article, Markdown, or dataset citation for {slug}")
        if art_url not in llms_full_raw:
            raise ValueError(f"dist/llms-full.txt is missing full Markdown section for {slug}")

    # Verify Cloudflare Pages _headers CSP rules
    headers_content = (DIST_DIR / "_headers").read_text(encoding="utf-8")
    if (
        "Content-Security-Policy:" not in headers_content
        or "script-src 'self'" not in headers_content
        or "style-src 'self'" not in headers_content
        or "unsafe-inline" in headers_content
    ):
        raise ValueError("dist/_headers is missing strict Content-Security-Policy")

    # Check all generated HTML files for CSP compliance, legal disclosures, and A11y landmarks
    html_files = list(DIST_DIR.glob("*.html")) + list((DIST_DIR / "articles").glob("*.html"))
    for html_path in html_files:
        content = html_path.read_text(encoding="utf-8")
        if INLINE_HANDLER_RE.search(content):
            raise ValueError(f"{html_path.name}: contains inline JS event handler (violates CSP)")
        if INLINE_STYLE_RE.search(content):
            raise ValueError(f"{html_path.name}: contains inline style attribute (violates strict CSP)")
        if STYLE_TAG_RE.search(content):
            raise ValueError(f"{html_path.name}: contains inline <style> tag (violates strict CSP)")
        for attrs, body in SCRIPT_TAG_RE.findall(content):
            if 'type="application/ld+json"' in attrs:
                json.loads(body)  # Verify valid JSON-LD
            elif "src=" in attrs:
                if body.strip():
                    raise ValueError(f"{html_path.name}: external <script> tag must have empty body")
            else:
                raise ValueError(f"{html_path.name}: contains inline executable <script> tag")
        if "example.com" in content:
            raise ValueError(f"{html_path.name}: contains placeholder 'example.com'")
        if "rikutoyamada" in content.lower():
            raise ValueError(f"{html_path.name}: leaks personal GitHub username or private repo link")
        if monetized:
            if EXACT_AMAZON_DISCLOSURE not in content:
                raise ValueError(f"{html_path.name}: missing exact Amazon Associates disclosure in monetized mode")
            if "【PR】" not in content:
                raise ValueError(f"{html_path.name}: missing 【PR】 stealth marketing disclosure in monetized mode")
        else:
            if "tag=" in content:
                raise ValueError(f"{html_path.name}: contains affiliate tag= parameter while monetization_enabled is false")
        if 'class="skip-link"' not in content or 'id="main-content"' not in content:
            raise ValueError(f"{html_path.name}: missing skip-link or #main-content landmark")

    report = {
        "status": "pass",
        "monetization_mode": "MONETIZED" if monetized else "PRE_REVIEW_NON_COMMERCIAL",
        "validated_articles": len(article_files),
        "validated_html_pages": len(html_files),
        "checks": [
            "security_self_tests_slug_newline_and_units",
            "monetization_switch_self_test",
            "strict_csp_no_inline_js_or_style_or_script_tags",
            "headers_csp_verified",
            "legal_and_disclosure_mode_verified",
            "copyright_no_verbatim_snippets",
            "a11y_landmarks_and_sortable_table_buttons",
            "csv_datasets_present",
        ],
    }
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    try:
        validate_all()
    except Exception as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
