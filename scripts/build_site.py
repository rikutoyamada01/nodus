#!/usr/bin/env python3
"""
Nodus Static Site & Quantitative Intelligence Builder
Generates enterprise-grade HTML5, Schema.org JSON-LD, CSV datasets, Atom feed,
sitemap.xml, robots.txt, llms.txt, 404.html, and Cloudflare Pages _headers
from structured quantitative datasets in content/articles/*.json.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "site_config.json"
ARTICLES_DIR = ROOT_DIR / "content" / "articles"
RAW_LOGS_DIR = ROOT_DIR / "content" / "raw_logs"
DIST_DIR = ROOT_DIR / "dist"

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,120}$")
ALLOWED_STATUSES = {"good", "warning", "danger"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug):
        raise ValueError(f"Invalid article slug: {slug!r}")
    return slug


def validate_url(url: str, allow_Hash: bool = False) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Empty URL is not allowed")
    url = url.strip()
    if allow_Hash and url.startswith("#"):
        return url
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError(f"Disallowed or invalid URL scheme/host: {url!r}")
    return url


def safe_json_ld(payload: dict[str, Any]) -> str:
    """Serialize JSON-LD and escape <, >, & to prevent </script> breakout."""
    raw = json.dumps(payload, ensure_ascii=False)
    return (
        raw.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def validate_article(article: dict[str, Any], config: dict[str, Any]) -> None:
    slug = validate_slug(article.get("slug", ""))
    excluded = {c.lower() for c in config.get("compliance", {}).get("excluded_categories", [])}
    category = str(article.get("category", "")).strip()
    if not category or category.lower() in excluded:
        raise ValueError(f"Article {slug}: category {category!r} is missing or excluded")

    if config.get("compliance", {}).get("require_source_links", True):
        sources = article.get("sources", [])
        if not sources:
            raise ValueError(f"Article {slug}: at least one primary source is required")
        for src in sources:
            validate_url(src.get("url", ""))

    chart = article.get("spec_gap_chart", {})
    max_scale = float(chart.get("max_scale", 0))
    if not math.isfinite(max_scale) or max_scale <= 0:
        raise ValueError(f"Article {slug}: max_scale must be a positive finite number")

    for item in chart.get("items", []):
        off_val = float(item.get("official_value", 0))
        meas_val = float(item.get("measured_value", 0))
        if not (math.isfinite(off_val) and math.isfinite(meas_val)):
            raise ValueError(f"Article {slug}: non-finite chart values")
        if item.get("status", "good") not in ALLOWED_STATUSES:
            raise ValueError(f"Article {slug}: invalid status {item.get('status')!r}")


def _looks_numeric_cell(text: str) -> bool:
    s = str(text).strip()
    if not s:
        return False
    return bool(
        re.match(
            r"^(?:約\s*|実測\s*|最大\s*|平均\s*|<|>|≦|≧|~|〜)*[-+$¥]?[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?\s*(?:%|倍|x|X|W|V|A|Wh|mWh|kTokens|Tokens|tok/s|t/s|ms|秒|s|分|時間|MB/s|GB/s|Gbps|GB|TB|dBA|dB|°C|℃|円|USD|\$|件|回|アカウント|セッション|Models|CU)",
            s,
            re.IGNORECASE,
        )
    )


def _normalize_sort_value(text: str) -> str:
    """Extract a unit-normalized numeric sort key when possible so '900 ms' < '1.2 秒' and '1.5 GB/s' > '800 MB/s'."""
    s = str(text).strip()
    m = re.search(r"([-+]?(?:\d+(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)", s)
    if not m:
        return ""
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return ""
    rest = s[m.end() :].strip().lower()
    if rest.startswith("万"):
        val *= 10000.0
    elif rest.startswith("gb/s"):
        val *= 1000.0
    elif rest.startswith("tb"):
        val *= 1024.0
    elif rest.startswith("ktokens") or rest.startswith("k "):
        val *= 1000.0
    elif rest.startswith("m ") or rest.startswith("mtokens"):
        val *= 1000000.0
    elif (rest.startswith("秒") or rest.startswith("s")) and not rest.startswith("session"):
        if "ms" not in s.lower():
            val *= 1000.0
    return f"{val:.6f}"


def build_css() -> str:
    return """
:root {
  --bg-page: #f5f7f9;
  --bg-surface: #ffffff;
  --bg-subtle: #f0f3f6;
  --bg-callout: #f2f9f6;
  --text-primary: #181a1c;
  --text-secondary: #374151;
  --text-muted: #64748b;
  --border-color: #e2e8f0;
  --border-strong: #cbd5e1;
  --brand-primary: #0f5c4d;
  --brand-accent: #0d7462;
  --brand-light: #e6f4f1;
  --origin-self-bg: #e6f4f1;
  --origin-self-fg: #0b5345;
  --origin-comm-bg: #f1f5f9;
  --origin-comm-fg: #334155;
  --status-good: #065f46;
  --status-good-bg: #d1fae5;
  --status-warn: #92400e;
  --status-warn-bg: #fef3c7;
  --status-danger: #991b1b;
  --status-danger-bg: #fee2e2;
  --font-sans: "Hiragino Kaku Gothic ProN", "Hiragino Sans", "BIZ UDPGothic", "Noto Sans JP", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", Consolas, "BIZ UDGothic", "Liberation Mono", Menlo, monospace;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  scroll-padding-top: 72px;
}

body {
  font-family: var(--font-sans);
  background-color: var(--bg-page);
  color: var(--text-primary);
  line-height: 1.8;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}

.skip-link {
  position: absolute;
  top: -100px;
  left: 16px;
  background: var(--brand-primary);
  color: #ffffff;
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: 700;
  z-index: 1000;
}

.skip-link:focus {
  top: 12px;
  color: #ffffff;
  outline: 2px solid var(--brand-accent);
}

a {
  color: var(--brand-accent);
  text-decoration: none;
}

a:hover {
  color: var(--brand-primary);
  text-decoration: underline;
}

a:focus-visible,
button:focus-visible,
input:focus-visible {
  outline: 2px solid var(--brand-accent);
  outline-offset: 2px;
}

.container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 20px;
}

/* Clean Editorial Tech Header (Zenn / Note / Qiita vibe) */
.site-header {
  background: var(--bg-surface);
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 50;
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 58px;
  padding-top: 6px;
  padding-bottom: 6px;
  flex-wrap: wrap;
  gap: 12px;
}

.brand-logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text-primary);
  font-weight: 800;
  font-size: 1.18rem;
  letter-spacing: -0.02em;
  text-decoration: none;
}

.brand-logo:hover {
  color: var(--brand-primary);
  text-decoration: none;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--text-primary);
  color: #ffffff;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 700;
  flex-shrink: 0;
}

.brand-tagline {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-weight: 500;
  border-left: 1px solid var(--border-strong);
  padding-left: 10px;
}

.site-nav {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 0.84rem;
  flex-wrap: wrap;
}

.site-nav a {
  color: var(--text-secondary);
  font-weight: 600;
  text-decoration: none;
}

.site-nav a:hover {
  color: var(--brand-primary);
  text-decoration: underline;
}

/* Compliance Notice Bar */
.pr-banner {
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border-color);
  color: var(--text-muted);
  font-size: 0.75rem;
  padding: 6px 0;
}

/* Compact Reader Intro Banner (Replaces dark SaaS Hero) */
.editorial-intro {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  padding: 24px 0 20px;
}

.intro-inner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}

.intro-copy {
  max-width: 720px;
}

.intro-kicker {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--brand-primary);
  margin-bottom: 4px;
}

.intro-copy h1 {
  font-size: 1.38rem;
  line-height: 1.4;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.intro-copy p {
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.65;
}

.intro-stats-inline {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-muted);
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  padding: 10px 14px;
  border-radius: 6px;
  align-self: center;
}

.intro-stats-inline strong {
  color: var(--text-primary);
  font-weight: 700;
}

/* Index Controls & Feed List */
.controls-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  width: 100%;
  justify-content: space-between;
  margin: 22px 0 18px;
}

.filter-bar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-btn {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
}

.filter-btn[aria-pressed="true"],
.filter-btn:hover {
  background: var(--text-primary);
  color: #ffffff;
  border-color: var(--text-primary);
}

.search-input {
  background: var(--bg-surface);
  border: 1px solid var(--border-strong);
  color: var(--text-primary);
  padding: 7px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  min-width: 240px;
  max-width: 100%;
}

/* Scannable Article Feed (Zenn / Qiita / Reddit list feel) */
.article-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 56px;
}

.article-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.12s ease;
}

.article-card[data-origin="first_party"] {
  border-left: 4px solid var(--brand-accent);
}

.article-card[hidden] {
  display: none !important;
}

.article-card:hover {
  border-color: var(--border-strong);
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.76rem;
  flex-wrap: wrap;
}

.origin-badge {
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.74rem;
}

.origin-self {
  background: var(--origin-self-bg);
  color: var(--origin-self-fg);
}

.origin-community {
  background: var(--origin-comm-bg);
  color: var(--origin-comm-fg);
}

.category-pill {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.76rem;
}

.date-text {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  margin-left: auto;
}

.article-card h2 {
  font-size: 1.18rem;
  line-height: 1.45;
  font-weight: 800;
  color: var(--text-primary);
}

.card-title-link {
  color: inherit;
  text-decoration: none;
}

.card-title-link:hover {
  color: var(--brand-accent);
  text-decoration: underline;
}

.article-card p {
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.65;
}

.card-takeaway-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--bg-subtle);
}

.card-metrics-inline {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.inline-metric {
  font-size: 0.8rem;
  color: var(--text-secondary);
  background: var(--bg-page);
  padding: 3px 9px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}

.inline-metric strong {
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-weight: 700;
  margin-left: 4px;
}

.card-tags-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.tag-chip {
  color: var(--text-muted);
  background: var(--bg-subtle);
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.73rem;
}

/* Article Detail: Zenn / Qiita / Note 2-Column Readable Layout */
.article-layout {
  display: grid;
  grid-template-columns: minmax(0, 760px) 280px;
  gap: 28px;
  align-items: start;
  padding: 28px 0 64px;
}

.article-sheet {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 36px 40px 48px;
}

.article-sidebar {
  position: sticky;
  top: 78px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-box {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px 18px;
  font-size: 0.84rem;
}

.sidebar-title {
  font-size: 0.8rem;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-color);
}

.toc-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.toc-list a {
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.45;
  display: block;
}

.toc-list a:hover {
  color: var(--brand-primary);
}

.meta-kv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.meta-kv-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px dashed var(--border-color);
  padding-bottom: 4px;
}

.meta-kv-row strong {
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.breadcrumb {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 14px;
  word-break: break-word;
}

.article-meta-top {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.article-title {
  font-size: 1.72rem;
  line-height: 1.38;
  font-weight: 800;
  letter-spacing: -0.015em;
  margin-bottom: 10px;
  color: var(--text-primary);
}

.article-subtitle {
  font-size: 0.96rem;
  color: var(--text-secondary);
  line-height: 1.65;
  margin-bottom: 14px;
}

.article-tags-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.article-timestamps {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  color: var(--text-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 24px;
}

/* TL;DR / Key Takeaways Callout (結論ファースト) */
.tldr-box {
  background: var(--bg-callout);
  border: 1px solid #b7e4d8;
  border-left: 4px solid var(--brand-accent);
  border-radius: 6px;
  padding: 18px 20px;
  margin-bottom: 28px;
}

.tldr-title {
  font-weight: 800;
  font-size: 0.95rem;
  color: var(--origin-self-fg);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.tldr-list {
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.92rem;
  color: var(--text-primary);
  line-height: 1.7;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 155px), 1fr));
  gap: 10px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #ccebe2;
}

.kpi-item {
  background: #ffffff;
  border: 1px solid #d5ede6;
  border-radius: 6px;
  padding: 10px 12px;
}

.kpi-label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
}

.kpi-value {
  font-family: var(--font-mono);
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  margin: 2px 0;
}

.kpi-sub {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

/* Cohesive Markdown-Style Sections inside Article Sheet */
.article-section {
  margin-top: 38px;
}

.section-h2 {
  font-size: 1.28rem;
  font-weight: 800;
  color: var(--text-primary);
  padding-bottom: 8px;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.section-subnote {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-muted);
}

.prose-section {
  margin-bottom: 28px;
}

.prose-section h3 {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 24px 0 10px;
  padding-left: 10px;
  border-left: 3px solid var(--brand-accent);
}

.prose-section p {
  color: var(--text-primary);
  font-size: 0.98rem;
  line-height: 1.85;
}

.methodology-box {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  padding: 14px 16px;
  border-radius: 6px;
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-top: 12px;
}

.csv-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 700;
  color: var(--brand-primary);
  background: var(--brand-light);
  border: 1px solid #a7f3d0;
  padding: 5px 11px;
  border-radius: 4px;
  text-decoration: none;
}

.csv-btn:hover {
  background: #d1fae5;
  text-decoration: none;
}

/* Honest Zero-Baseline Quantitative Plot */
.gap-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 12px;
}

.gap-item {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 14px 16px;
  background: var(--bg-page);
}

.gap-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}

.gap-item-name {
  font-weight: 700;
  font-size: 0.94rem;
}

.status-badge {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-good {
  background: var(--status-good-bg);
  color: var(--status-good);
}

.status-warning {
  background: var(--status-warn-bg);
  color: var(--status-warn);
}

.status-danger {
  background: var(--status-danger-bg);
  color: var(--status-danger);
}

.bar-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 8px 0;
}

.bar-row {
  display: grid;
  grid-template-columns: 270px 1fr;
  align-items: center;
  gap: 12px;
}

.bar-label {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.bar-svg {
  width: 100%;
  height: 10px;
  background: #e2e8f0;
  border-radius: 2px;
  overflow: hidden;
  display: block;
}

.bar-rect-official {
  fill: #94a3b8;
}

.bar-rect-measured {
  fill: var(--brand-accent);
}

.gap-note {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-color);
}

/* Booktabs-style Comparison Table with Right-Aligned Numeric Columns */
.table-wrap {
  overflow-x: auto;
  margin-top: 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
}

table.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
  text-align: left;
  font-variant-numeric: tabular-nums;
}

table.data-table caption {
  text-align: left;
  font-size: 0.76rem;
  color: var(--text-muted);
  padding: 8px 12px;
  background: var(--bg-page);
  border-bottom: 1px solid var(--border-color);
}

table.data-table thead th {
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-weight: 700;
  padding: 0;
  white-space: nowrap;
  font-size: 0.78rem;
  border-bottom: 2px solid var(--border-strong);
}

.th-sort-btn {
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  font-weight: 700;
  padding: 10px 12px;
  width: 100%;
  text-align: left;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.th-sort-btn:hover {
  background: #e2e8f0;
}

table.data-table td,
table.data-table tbody th {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.82rem;
}

table.data-table td.num-cell {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

table.data-table tbody th {
  font-family: var(--font-sans);
  font-weight: 700;
  background: #fafbfc;
  color: var(--text-primary);
}

table.data-table tr:last-child td,
table.data-table tr:last-child th {
  border-bottom: none;
}

table.data-table tbody tr:hover td,
table.data-table tbody tr:hover th {
  background: var(--bg-page);
}

/* Reference / Affiliate Links */
.cta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 12px;
  margin-top: 12px;
}

.cta-card {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 14px 16px;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
}

.cta-badge {
  display: inline-block;
  background: var(--brand-light);
  color: var(--brand-primary);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  width: fit-content;
}

.cta-title {
  font-weight: 700;
  font-size: 0.92rem;
  color: var(--text-primary);
  margin-top: 6px;
}

.cta-provider {
  font-size: 0.76rem;
  color: var(--text-muted);
  margin-top: 2px;
}

.cta-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--text-primary);
  color: #ffffff;
  font-weight: 600;
  font-size: 0.82rem;
  padding: 8px 14px;
  border-radius: 4px;
  text-align: center;
  text-decoration: none;
}

.cta-btn:hover {
  background: var(--brand-primary);
  color: #ffffff;
  text-decoration: none;
}

.cta-disclosure-note {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 10px;
}

/* FAQ & Sources */
.faq-list {
  margin-top: 8px;
}

.faq-item {
  border-bottom: 1px solid var(--border-color);
  padding: 14px 0;
}

.faq-item:last-child {
  border-bottom: none;
}

.faq-q {
  font-weight: 700;
  font-size: 0.95rem;
  margin-bottom: 6px;
  color: var(--text-primary);
}

.faq-a {
  font-size: 0.92rem;
  color: var(--text-secondary);
  line-height: 1.75;
}

.source-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  padding: 9px 12px;
  border-radius: 4px;
  font-size: 0.82rem;
  flex-wrap: wrap;
  gap: 8px;
}

.source-meta {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 0.74rem;
}

/* Clean Minimal Footer */
.site-footer {
  background: var(--bg-surface);
  border-top: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 40px 0 32px;
  font-size: 0.84rem;
  margin-top: 48px;
}

.footer-grid {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 28px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
}

.footer-desc {
  max-width: 500px;
  color: var(--text-secondary);
  margin-top: 8px;
  font-size: 0.82rem;
}

.footer-amazon-notice {
  margin-top: 8px;
  font-size: 0.76rem;
  color: var(--text-muted);
}

.footer-links {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}

.footer-links a {
  color: var(--text-secondary);
  font-weight: 600;
}

.footer-bottom {
  padding-top: 20px;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.76rem;
  color: var(--text-muted);
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 28px 32px;
  margin-bottom: 24px;
}

@media (max-width: 960px) {
  .article-layout {
    grid-template-columns: 1fr;
  }
  .article-sidebar {
    position: static;
    order: -1;
  }
}

@media (max-width: 680px) {
  .brand-tagline {
    display: none;
  }
  .article-sheet {
    padding: 22px 18px 32px;
  }
  .article-title {
    font-size: 1.38rem;
  }
  .bar-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
"""


def build_js() -> str:
    return """/* Nodus Quantitative Interactive Controls (CSP-safe external script) */
(function () {
  "use strict";

  function initIndexFilters() {
    var filterBtns = document.querySelectorAll(".filter-btn[data-filter]");
    var searchInput = document.getElementById("datasetSearch");
    var cards = document.querySelectorAll(".article-card[data-category]");
    if (!filterBtns.length && !searchInput) return;

    var activeFilter = "all";

    function applyFilter() {
      var query = searchInput ? searchInput.value.trim().toLowerCase() : "";
      cards.forEach(function (card) {
        var cat = card.getAttribute("data-category") || "";
        var origin = card.getAttribute("data-origin") || "community";
        var catMatch =
          activeFilter === "all" ||
          (activeFilter === "first_party" && (origin === "first_party" || origin === "hybrid")) ||
          cat === activeFilter;
        var textMatch = !query || card.textContent.toLowerCase().indexOf(query) !== -1;
        if (catMatch && textMatch) {
          card.removeAttribute("hidden");
        } else {
          card.setAttribute("hidden", "hidden");
        }
      });
    }

    filterBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeFilter = btn.getAttribute("data-filter") || "all";
        filterBtns.forEach(function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        applyFilter();
      });
    });

    if (searchInput) {
      searchInput.addEventListener("input", applyFilter);
    }
  }

  function extractSortNumber(cell) {
    if (!cell) return NaN;
    var attrVal = cell.getAttribute("data-sort-value");
    if (attrVal !== null && attrVal !== "") {
      var parsed = parseFloat(attrVal);
      if (!isNaN(parsed)) return parsed;
    }
    var text = cell.textContent.trim();
    var m = text.match(/[-+]?(?:\d+(?:,\d{3})+|\d+)(?:\.\d+)?/);
    return m ? parseFloat(m[0].replace(/,/g, "")) : NaN;
  }

  function initTableSorting() {
    var tables = document.querySelectorAll("table.data-table");
    tables.forEach(function (table) {
      var headers = table.querySelectorAll("thead th");
      var tbody = table.querySelector("tbody");
      if (!tbody) return;

      headers.forEach(function (th, colIdx) {
        var btn = th.querySelector(".th-sort-btn") || th;
        btn.addEventListener("click", function () {
          var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
          var asc = th.getAttribute("aria-sort") !== "ascending";
          headers.forEach(function (h) {
            h.setAttribute("aria-sort", "none");
          });
          th.setAttribute("aria-sort", asc ? "ascending" : "descending");

          rows.sort(function (a, b) {
            var cellA = a.children[colIdx];
            var cellB = b.children[colIdx];
            var numA = extractSortNumber(cellA);
            var numB = extractSortNumber(cellB);
            if (!isNaN(numA) && !isNaN(numB) && numA !== numB) {
              return asc ? numA - numB : numB - numA;
            }
            var txtA = cellA ? cellA.textContent.trim() : "";
            var txtB = cellB ? cellB.textContent.trim() : "";
            return asc ? txtA.localeCompare(txtB, "ja") : txtB.localeCompare(txtA, "ja");
          });

          rows.forEach(function (r) { tbody.appendChild(r); });
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initIndexFilters();
      initTableSorting();
    });
  } else {
    initIndexFilters();
    initTableSorting();
  }
})();
"""


def is_monetized(config: dict[str, Any]) -> bool:
    comp = config.get("compliance", {})
    aff = config.get("affiliates", {})
    return bool(comp.get("monetization_enabled")) or bool(str(aff.get("amazon_associate_tag", "")).strip())


def resolve_affiliate_url(raw_url: str, config: dict[str, Any]) -> str:
    url = validate_url(raw_url)
    tag = str(config.get("affiliates", {}).get("amazon_associate_tag", "")).strip()
    if tag and "amazon.co.jp" in url and "tag=" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}tag={tag}"
    return url


def render_header(config: dict[str, Any], root_prefix: str = "") -> str:
    site = config["site"]
    comp = config["compliance"]
    banner_text = (
        comp["pr_disclosure_text"]
        if is_monetized(config)
        else comp.get(
            "non_commercial_notice",
            "現在、当サイトは広告およびアフィリエイトリンクを一切掲載していない独立リサーチメディアとして運営されています。",
        )
    )
    return f"""
<a href="#main-content" class="skip-link">メインコンテンツへスキップ</a>
<header class="site-header">
  <div class="container header-inner">
    <a href="{root_prefix}index.html" class="brand-logo">
      <span class="brand-mark" aria-hidden="true">N</span>
      <span>{esc(site["name"])}</span>
      <span class="brand-tagline">一次検証・定量技術ノート</span>
    </a>
    <nav class="site-nav" aria-label="グローバルナビゲーション">
      <a href="{root_prefix}index.html">検証記事一覧</a>
      <a href="{root_prefix}about.html">検証手法・運営情報</a>
      <a href="{root_prefix}about.html#privacy">ポリシー</a>
      <a href="{root_prefix}feed.xml">RSS</a>
    </nav>
  </div>
</header>
<div class="pr-banner" role="note" aria-label="運営ステータス表示">
  <div class="container">{esc(banner_text)}</div>
</div>
"""


def render_footer(config: dict[str, Any], root_prefix: str = "") -> str:
    site = config["site"]
    comp = config["compliance"]
    footer_notice = (
        comp.get(
            "amazon_disclosure_text",
            "Amazon のアソシエイトとして、Nodusは適格販売により収入を得ています。",
        )
        if is_monetized(config)
        else comp.get(
            "non_commercial_notice",
            "現在、当サイトは広告およびアフィリエイトリンクを一切掲載していない独立リサーチメディアとして運営されています。",
        )
    )
    return f"""
<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="brand-logo">
          <span class="brand-mark" aria-hidden="true">N</span>
          <span>{esc(site["name"])}</span>
        </div>
        <p class="footer-desc">
          公式ドキュメントや一般的な技術ブログだけでは辿り着けない「独自の実機・チャット検証データ」と「コミュニティ一次計測ログ」を、結論ファーストで公開する技術検証メディア。
        </p>
        <p class="footer-amazon-notice">{esc(footer_notice)}</p>
      </div>
      <div class="footer-links">
        <a href="{root_prefix}index.html">記事一覧</a>
        <a href="{root_prefix}about.html">検証手法・免責事項</a>
        <a href="{root_prefix}about.html#privacy">プライバシーポリシー</a>
        <a href="{root_prefix}about.html#contact">運営者情報・訂正ポリシー</a>
        <a href="{root_prefix}sitemap.xml">Sitemap</a>
        <a href="{root_prefix}llms.txt">LLMs.txt</a>
      </div>
    </div>
    <div class="footer-bottom">
      <span>&copy; {esc(site["copyright_year"])} {esc(site["organization"])}. All rights reserved.</span>
      <span>Verified Empirical Notes &amp; Open CSV Datasets</span>
    </div>
  </div>
</footer>
<script src="{root_prefix}assets/app.js" defer></script>
"""


def build_article_csv(article: dict[str, Any]) -> str:
    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM for Excel compatibility
    writer = csv.writer(buf, lineterminator="\n")
    table = article["comparison_table"]
    writer.writerow(table["headers"])
    for row in table["rows"]:
        writer.writerow(row)
    return buf.getvalue()


def _build_tldr_bullets(article: dict[str, Any]) -> list[str]:
    custom_tldr = article.get("tldr")
    if isinstance(custom_tldr, list) and custom_tldr:
        return [str(item) for item in custom_tldr]
    bullets: list[str] = []
    for m in article.get("summary_metrics", [])[:3]:
        bullets.append(f"{m['label']}は「{m['value']}」（{m['subtext']}）。")
    items = article.get("spec_gap_chart", {}).get("items", [])
    if items:
        top = items[0]
        bullets.append(f"{top['name']}：{top['note']}")
    return bullets


def _select_related_articles(
    current: dict[str, Any], all_articles: list[dict[str, Any]], limit: int = 3
) -> list[dict[str, Any]]:
    cur_slug = current.get("slug", "")
    cur_cat = current.get("category", "")
    cur_tags = {str(t).lower() for t in current.get("tags", [])}
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for cand in all_articles:
        c_slug = cand.get("slug", "")
        if not c_slug or c_slug == cur_slug:
            continue
        score = 0
        if cand.get("category") == cur_cat:
            score += 3
        c_tags = {str(t).lower() for t in cand.get("tags", [])}
        score += len(cur_tags & c_tags) * 2
        if cand.get("origin") in {"first_party", "hybrid"}:
            score += 1
        scored.append((score, cand.get("updated_at", ""), cand))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item[2] for item in scored[:limit]]


def render_article_page(
    article: dict[str, Any],
    config: dict[str, Any],
    all_articles: list[dict[str, Any]] | None = None,
) -> str:
    site = config["site"]
    seo = article["seo"]
    slug = validate_slug(article["slug"])
    base_url = validate_url(site["base_url"]).rstrip("/")
    canonical_url = f"{base_url}/articles/{slug}.html"
    data_updated_at = article.get("data_updated_at", article["updated_at"])
    methodology_note = article.get("methodology_note", "")
    origin = article.get("origin", "community")
    is_self = origin in {"first_party", "hybrid"}
    origin_badge_cls = "origin-self" if is_self else "origin-community"
    origin_text = article.get(
        "origin_label",
        "🔬 独自実機・AIチャット検証" if is_self else "📊 一次検証ログ定量調査",
    )
    if is_self and not origin_text.startswith(("🔬", "🧪")):
        origin_text = f"🔬 {origin_text}"
    lead_variant = seo.get("lead_variant", "default")

    amazon_notice = config["compliance"].get(
        "amazon_disclosure_text",
        "Amazon のアソシエイトとして、Nodusは適格販売により収入を得ています。",
    )

    raw_log_file = RAW_LOGS_DIR / f"{slug}.json"
    has_raw_log = raw_log_file.exists()
    raw_log_sha = ""
    if has_raw_log:
        raw_log_sha = hashlib.sha256(raw_log_file.read_bytes()).hexdigest()[:16]

    distributions: list[dict[str, str]] = [
        {
            "@type": "DataDownload",
            "encodingFormat": "text/csv",
            "contentUrl": f"{base_url}/datasets/{slug}.csv",
        },
        {
            "@type": "DataDownload",
            "encodingFormat": "text/markdown",
            "contentUrl": f"{base_url}/articles/{slug}.md",
        },
    ]
    if has_raw_log:
        distributions.append(
            {
                "@type": "DataDownload",
                "encodingFormat": "application/json",
                "contentUrl": f"{base_url}/logs/{slug}.json",
            }
        )

    faq_entities = [
        {
            "@type": "Question",
            "name": f["question"],
            "acceptedAnswer": {"@type": "Answer", "text": f["answer"]},
        }
        for f in article.get("faqs", [])
    ]
    measured_vars = [
        str(h) for h in article.get("comparison_table", {}).get("headers", [])[1:] if str(h).strip()
    ]
    citation_urls = [validate_url(s["url"]) for s in article.get("sources", []) if s.get("url")]

    schema_ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "TechArticle",
                "headline": article["title"],
                "description": seo["meta_description"],
                "datePublished": article["published_at"],
                "dateModified": article["updated_at"],
                "inLanguage": "ja",
                "keywords": ", ".join(article.get("tags", [])),
                "citation": citation_urls,
                "author": {
                    "@type": "Organization",
                    "name": site["organization"],
                    "url": f"{base_url}/about.html",
                },
                "publisher": {
                    "@type": "Organization",
                    "name": site["name"],
                    "url": f"{base_url}/",
                },
                "speakable": {
                    "@type": "SpeakableSpecification",
                    "cssSelector": ["#sec-tldr", "#sec-faq"],
                },
                "mainEntityOfPage": canonical_url,
            },
            {
                "@type": "Dataset",
                "name": f"{article['title']} 実測検証データセット (N={int(article.get('sample_size_n', 0))})",
                "description": article["subtitle"],
                "url": canonical_url,
                "inLanguage": "ja",
                "license": "https://creativecommons.org/licenses/by/4.0/",
                "isAccessibleForFree": True,
                "datePublished": article["published_at"],
                "dateModified": data_updated_at,
                "creator": {
                    "@type": "Organization",
                    "name": site["organization"],
                    "url": f"{base_url}/about.html",
                },
                "measurementTechnique": methodology_note or "実機・一次計測ログに基づく中央値および条件別定量比較",
                "variableMeasured": measured_vars,
                "distribution": distributions,
            },
            {
                "@type": "FAQPage",
                "mainEntity": faq_entities,
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": site["name"],
                        "item": f"{base_url}/",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": article["category"],
                        "item": f"{base_url}/index.html",
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": article["title"],
                        "item": canonical_url,
                    },
                ],
            },
        ],
    }

    tldr_bullets = _build_tldr_bullets(article)
    if lead_variant == "faq_boost" and article.get("faqs"):
        top_faq = article["faqs"][0]
        tldr_bullets = [f"【最多の疑問】Q. {top_faq['question']} → {top_faq['answer']}"] + tldr_bullets
    tldr_bullets_html = "".join(f"<li>{esc(b)}</li>" for b in tldr_bullets)

    kpi_html = "".join(
        f"""
        <div class="kpi-item">
          <div class="kpi-label">{esc(m["label"])}</div>
          <div class="kpi-value">{esc(m["value"])}</div>
          <div class="kpi-sub">{esc(m["subtext"])}</div>
        </div>
        """
        for m in article.get("summary_metrics", [])
    )

    tags_html = "".join(f'<span class="tag-chip">#{esc(t)}</span>' for t in article.get("tags", []))

    chart = article["spec_gap_chart"]
    configured_max = float(chart.get("max_scale", 100.0)) or 100.0
    observed_max = max(
        [configured_max]
        + [
            max(0.0, float(it.get("official_value", 0.0)), float(it.get("measured_value", 0.0)))
            for it in chart.get("items", [])
        ]
    )
    gap_items_html = []
    for item in chart.get("items", []):
        off_v = max(0.0, float(item["official_value"]))
        meas_v = max(0.0, float(item["measured_value"]))
        off_pct = (off_v / observed_max) * 100.0 if observed_max > 0 else 0.0
        meas_pct = (meas_v / observed_max) * 100.0 if observed_max > 0 else 0.0
        status_raw = item.get("status", "good")
        status_cls = f"status-{status_raw if status_raw in ALLOWED_STATUSES else 'good'}"
        status_text = {
            "good": "実測良好・高効率",
            "warning": "条件付き制限・乖離あり",
            "danger": "大幅乖離・要注意",
        }.get(status_raw, "検証済")

        gap_items_html.append(
            f"""
            <div class="gap-item">
              <div class="gap-item-header">
                <span class="gap-item-name">{esc(item["name"])}</span>
                <span class="status-badge {status_cls}">{esc(status_text)}</span>
              </div>
              <div class="bar-group">
                <div class="bar-row">
                  <span class="bar-label">{esc(item["official_label"])}</span>
                  <svg class="bar-svg" viewBox="0 0 100 6" preserveAspectRatio="none" role="img" aria-label="{esc(item['official_label'])}">
                    <rect class="bar-rect-official" x="0" y="0" width="{off_pct:.2f}" height="6"></rect>
                  </svg>
                </div>
                <div class="bar-row">
                  <span class="bar-label"><strong>{esc(item["measured_label"])}</strong></span>
                  <svg class="bar-svg" viewBox="0 0 100 6" preserveAspectRatio="none" role="img" aria-label="{esc(item['measured_label'])}">
                    <rect class="bar-rect-measured" x="0" y="0" width="{meas_pct:.2f}" height="6"></rect>
                  </svg>
                </div>
              </div>
              <div class="gap-note">{esc(item["note"])}</div>
            </div>
            """
        )

    table = article["comparison_table"]
    th_html = "".join(
        f'<th scope="col" aria-sort="none"><button type="button" class="th-sort-btn"><span>{esc(h)}</span><span aria-hidden="true">↕</span></button></th>'
        for h in table["headers"]
    )
    tr_rows = []
    for row in table["rows"]:
        if not row:
            continue
        first_cell = f'<th scope="row">{esc(row[0])}</th>'
        rest_cells = []
        for cell in row[1:]:
            cell_str = str(cell)
            cls_attr = ' class="num-cell"' if _looks_numeric_cell(cell_str) else ""
            sort_val = _normalize_sort_value(cell_str)
            sort_attr = f' data-sort-value="{esc(sort_val)}"' if sort_val else ""
            rest_cells.append(f"<td{cls_attr}{sort_attr}>{esc(cell_str)}</td>")
        tr_rows.append(f"<tr>{first_cell}{''.join(rest_cells)}</tr>")
    tr_html = "".join(tr_rows)

    sections_html = "".join(
        f"""
        <div class="prose-section">
          <h3>{esc(sec["heading"])}</h3>
          <p>{esc(sec["body"])}</p>
        </div>
        """
        for sec in article.get("sections", [])
    )

    aff_map = config.get("affiliates", {}).get("links", {})
    monetized = is_monetized(config)
    cta_cards = []
    for key in article.get("affiliate_keys", []):
        if key in aff_map:
            aff = aff_map[key]
            aff_url = resolve_affiliate_url(aff["url"], config)
            rel_attr = "nofollow sponsored noopener noreferrer" if monetized else "noopener noreferrer"
            provider_suffix = "（広告リンク）" if monetized else "（公式・参考リンク）"
            cta_cards.append(
                f"""
                <div class="cta-card">
                  <div>
                    <span class="cta-badge">{esc(aff["badge"])}</span>
                    <div class="cta-title">{esc(aff["label"])}</div>
                    <div class="cta-provider">提供元: {esc(aff["provider"])} {provider_suffix}</div>
                  </div>
                  <a href="{esc(aff_url)}" target="_blank" rel="{rel_attr}" class="cta-btn">
                    公式仕様・詳細を見る &rarr;
                  </a>
                </div>
                """
            )
    cta_section_html = ""
    if cta_cards:
        panel_badge = "【広告・PR】Sponsored" if monetized else "公式・参考リンク (広告なし)"
        panel_note = (
            f"※上記リンクにはアフィリエイト広告が含まれます。{esc(amazon_notice)}"
            if monetized
            else "※上記は読者の利便性のための参考リンクであり、現在アフィリエイト報酬等は設定されていません。"
        )
        cta_section_html = f"""
        <section class="article-section" aria-label="検証対象モデル・関連サービス参考リンク">
          <h2 class="section-h2">
            <span>検証対象モデル・関連サービス公式リンク</span>
            <span class="section-subnote">{panel_badge}</span>
          </h2>
          <div class="cta-grid">
            {''.join(cta_cards)}
          </div>
          <p class="cta-disclosure-note">{panel_note}</p>
        </section>
        """

    faq_html = "".join(
        f"""
        <div class="faq-item">
          <h3 class="faq-q">Q. {esc(f["question"])}</h3>
          <p class="faq-a">{esc(f["answer"])}</p>
        </div>
        """
        for f in article.get("faqs", [])
    )

    sources_html = "".join(
        f"""
        <li class="source-item">
          <a href="{esc(validate_url(s["url"]))}" target="_blank" rel="noopener noreferrer">{esc(s["title"])}</a>
          <span class="source-meta">サンプル: {esc(s["sample_size"])} | 確認日: {esc(s["verified_date"])}</span>
        </li>
        """
        for s in article.get("sources", [])
    )

    methodology_html = ""
    if methodology_note:
        methodology_html = f'<div class="methodology-box"><strong>検証環境・集計メソドロジー:</strong> {esc(methodology_note)}</div>'

    citation_box_html = (
        f'<div class="methodology-box"><strong>データ引用・出典フォーマット (CC BY 4.0):</strong> '
        f'{esc(site["organization"])}「{esc(article["title"])}」({esc(data_updated_at)}更新, N={int(article.get("sample_size_n", 0))}) — '
        f'<code>{esc(canonical_url)}</code></div>'
    )

    raw_log_btn_html = (
        f'<a href="../logs/{esc(slug)}.json" target="_blank" rel="noopener noreferrer" class="csv-btn">📄 一次検証の生ログ (JSON)</a>'
        if has_raw_log
        else ""
    )
    raw_log_meta_row = (
        f'<div class="meta-kv-row"><span>生ログ SHA-256</span><strong>{esc(raw_log_sha[:10])}...</strong></div>'
        if has_raw_log
        else ""
    )

    related_list = _select_related_articles(article, all_articles or [])
    related_section_html = ""
    if related_list:
        rel_items = []
        for r in related_list:
            r_slug = validate_slug(r["slug"])
            r_m1 = r["summary_metrics"][0] if r.get("summary_metrics") else {"label": "実測", "value": "-"}
            rel_items.append(
                f"""
                <li class="source-item">
                  <a href="{esc(r_slug)}.html"><strong>{esc(r["title"])}</strong></a>
                  <span class="source-meta">{esc(r_m1["label"])}: {esc(r_m1["value"])} (N={int(r.get("sample_size_n", 0))})</span>
                </li>
                """
            )
        related_section_html = f"""
        <section id="sec-related" class="article-section" aria-label="関連する検証レポート">
          <h2 class="section-h2"><span>6. あわせて読みたい関連検証データ</span></h2>
          <ul class="source-list">
            {''.join(rel_items)}
          </ul>
        </section>
        """

    chart_num = "2" if lead_variant == "table_first" else "1"
    table_num = "1" if lead_variant == "table_first" else "2"

    chart_section_block = f"""
      <section id="sec-chart" class="article-section">
        <h2 class="section-h2">
          <span>{chart_num}. {esc(chart["title"])}</span>
          <span class="section-subnote">単位: {esc(chart["unit"])}</span>
        </h2>
        <div class="gap-list">
          {''.join(gap_items_html)}
        </div>
      </section>
    """
    table_section_block = f"""
      <section id="sec-table" class="article-section">
        <h2 class="section-h2">
          <span>{table_num}. 条件別・実測比較データテーブル</span>
          <span class="section-subnote">列見出しクリックで数値ソート可能</span>
        </h2>
        <div class="table-wrap">
          <table class="data-table">
            <caption>{esc(article["title"])} — 実測検証データ比較表</caption>
            <thead><tr>{th_html}</tr></thead>
            <tbody>{tr_html}</tbody>
          </table>
        </div>
      </section>
    """
    primary_quant_blocks = (
        table_section_block + chart_section_block
        if lead_variant == "table_first"
        else chart_section_block + table_section_block
    )
    toc_quant_links = (
        """
          <li><a href="#sec-table">1. 条件別・比較データ表</a></li>
          <li><a href="#sec-chart">2. 実測ギャップ・比較グラフ</a></li>
        """
        if lead_variant == "table_first"
        else """
          <li><a href="#sec-chart">1. 実測ギャップ・比較グラフ</a></li>
          <li><a href="#sec-table">2. 条件別・比較データ表</a></li>
        """
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(seo["meta_title"])}</title>
  <meta name="description" content="{esc(seo["meta_description"])}">
  <link rel="canonical" href="{esc(canonical_url)}">
  <meta property="og:title" content="{esc(seo["meta_title"])}">
  <meta property="og:description" content="{esc(seo["meta_description"])}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:site_name" content="{esc(site["name"])}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="alternate" type="application/atom+xml" title="{esc(site["name"])} Feed" href="../feed.xml">
  <link rel="alternate" type="text/markdown" title="Markdown (AI/LLM Citation)" href="{esc(slug)}.md">
  <link rel="stylesheet" href="../assets/style.css">
  <script type="application/ld+json">{safe_json_ld(schema_ld)}</script>
</head>
<body>
  {render_header(config, root_prefix="../")}

  <div class="container article-layout">
    <main id="main-content" class="article-sheet">
      <nav class="breadcrumb" aria-label="パンくずリスト">
        <a href="../index.html">Nodus</a> &rsaquo; <span>{esc(article["category"])}</span>
      </nav>

      <div class="article-meta-top">
        <span class="origin-badge {origin_badge_cls}">{esc(origin_text)}</span>
        <span class="category-pill">{esc(article["category"])}</span>
      </div>

      <h1 class="article-title">{esc(article["title"])}</h1>
      <p class="article-subtitle">{esc(article["subtitle"])}</p>

      <div class="article-tags-row">
        {tags_html}
      </div>

      <div class="article-timestamps">
        <span>公開: <time datetime="{esc(article["published_at"])}">{esc(article["published_at"])}</time></span>
        <span>実測データ更新: <time datetime="{esc(data_updated_at)}">{esc(data_updated_at)}</time></span>
        <span>サンプル数: <strong>N = {int(article.get("sample_size_n", 0))}</strong></span>
      </div>

      <section id="sec-tldr" class="tldr-box" aria-label="この記事の結論と要点">
        <div class="tldr-title">
          <span>💡 この記事でわかること（結論・実測サマリー）</span>
          <div class="card-metrics-inline">
            {raw_log_btn_html}
            <a href="../datasets/{esc(slug)}.csv" download="{esc(slug)}.csv" class="csv-btn">CSVデータを取得</a>
          </div>
        </div>
        <ul class="tldr-list">
          {tldr_bullets_html}
        </ul>
        <div class="kpi-strip">
          {kpi_html}
        </div>
      </section>

      {primary_quant_blocks}

      <section id="sec-analysis" class="article-section">
        <h2 class="section-h2">
          <span>3. 検証結果の詳しい解説・なぜこの差が出るのか？</span>
        </h2>
        {sections_html}
      </section>

      {cta_section_html}

      <section id="sec-faq" class="article-section">
        <h2 class="section-h2"><span>4. よくある疑問と回答 (FAQ)</span></h2>
        <div class="faq-list">
          {faq_html}
        </div>
      </section>

      <section id="sec-sources" class="article-section">
        <h2 class="section-h2">
          <span>5. 検証条件・一次情報ソース (Provenance)</span>
        </h2>
        {methodology_html}
        {citation_box_html}
        <ul class="source-list">
          {sources_html}
        </ul>
      </section>

      {related_section_html}
    </main>

    <aside class="article-sidebar" aria-label="記事目次およびデータ概要">
      <div class="sidebar-box">
        <div class="sidebar-title">目次</div>
        <ul class="toc-list">
          <li><a href="#sec-tldr">💡 結論・実測サマリー</a></li>
          {toc_quant_links}
          <li><a href="#sec-analysis">3. 詳細解説・原因分析</a></li>
          <li><a href="#sec-faq">4. よくある疑問 (FAQ)</a></li>
          <li><a href="#sec-sources">5. 検証方法・一次情報出典</a></li>
        </ul>
      </div>
      <div class="sidebar-box">
        <div class="sidebar-title">検証データ概要</div>
        <div class="meta-kv-list">
          <div class="meta-kv-row"><span>データ種別</span><strong>{"独自一次検証" if is_self else "一次ログ集計"}</strong></div>
          <div class="meta-kv-row"><span>サンプル数</span><strong>N = {int(article.get("sample_size_n", 0))}</strong></div>
          <div class="meta-kv-row"><span>比較行数</span><strong>{len(table["rows"])} 件</strong></div>
          <div class="meta-kv-row"><span>最終検証日</span><strong>{esc(data_updated_at)}</strong></div>
          {raw_log_meta_row}
        </div>
        <div class="card-takeaway-bar">
          {raw_log_btn_html}
          <a href="../datasets/{esc(slug)}.csv" download="{esc(slug)}.csv" class="csv-btn">CSVをダウンロード</a>
          <a href="{esc(slug)}.md" target="_blank" rel="noopener noreferrer" class="csv-btn">Markdown版 (AI/LLM用)</a>
        </div>
      </div>
    </aside>
  </div>

  {render_footer(config, root_prefix="../")}
</body>
</html>
"""


def render_article_markdown(article: dict[str, Any], config: dict[str, Any]) -> str:
    """Render a clean, token-efficient Markdown version of the article for Answer Engines and LLM RAG pipelines."""
    site = config["site"]
    base_url = validate_url(site["base_url"]).rstrip("/")
    slug = validate_slug(article["slug"])
    canonical_url = f"{base_url}/articles/{slug}.html"
    csv_url = f"{base_url}/datasets/{slug}.csv"
    has_raw_log = (RAW_LOGS_DIR / f"{slug}.json").exists()
    data_updated = article.get("data_updated_at", article["updated_at"])

    lines = [
        f"# {article['title']}",
        "",
        f"> {article['subtitle']}",
        "",
        f"- **Canonical URL**: {canonical_url}",
        f"- **CSV Dataset**: {csv_url}",
    ]
    if has_raw_log:
        lines.append(f"- **Raw Verification Log (JSON)**: {base_url}/logs/{slug}.json")
    lines.extend(
        [
            f"- **Category**: {article['category']}",
            f"- **Sample Size (N)**: {int(article.get('sample_size_n', 0))}",
            f"- **Data Updated**: {data_updated}",
            "",
            "## 結論・実測サマリー (TL;DR)",
        ]
    )
    for b in _build_tldr_bullets(article):
        lines.append(f"- {b}")

    lines.append("")
    lines.append("## 主要実測指標 (Key Metrics)")
    for m in article.get("summary_metrics", []):
        lines.append(f"- **{m['label']}**: {m['value']} ({m['subtext']})")

    table = article.get("comparison_table", {})
    headers = [str(h) for h in table.get("headers", [])]
    rows = table.get("rows", [])
    if headers and rows:
        lines.extend(
            [
                "",
                "## 条件別・実測比較データテーブル",
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |",
            ]
        )
        for r in rows:
            cells = [str(c).replace("|", "\\|") for c in r]
            lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## 詳細解説・原因分析")
    for sec in article.get("sections", []):
        lines.append(f"### {sec['heading']}")
        lines.append(sec["body"])
        lines.append("")

    if article.get("faqs"):
        lines.append("## よくある疑問と回答 (FAQ)")
        for f in article["faqs"]:
            lines.append(f"### Q. {f['question']}")
            lines.append(f"A. {f['answer']}")
            lines.append("")

    if article.get("methodology_note"):
        lines.append("## 検証環境・集計メソドロジー")
        lines.append(article["methodology_note"])
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_index_page(articles: list[dict[str, Any]], config: dict[str, Any]) -> str:
    site = config["site"]
    base_url = validate_url(site["base_url"]).rstrip("/")
    categories = sorted({a["category"] for a in articles})

    total_samples = sum(int(a.get("sample_size_n", 0)) for a in articles)
    first_party_count = sum(1 for a in articles if a.get("origin") in {"first_party", "hybrid"})

    filter_btns = [
        '<button type="button" class="filter-btn" data-filter="all" aria-pressed="true">すべて表示</button>',
        '<button type="button" class="filter-btn" data-filter="first_party" aria-pressed="false">🔬 独自検証・チャット知見</button>',
    ]
    for cat in categories:
        filter_btns.append(
            f'<button type="button" class="filter-btn" data-filter="{esc(cat)}" aria-pressed="false">{esc(cat)}</button>'
        )

    cards_html = []
    for a in articles:
        slug = validate_slug(a["slug"])
        origin = a.get("origin", "community")
        is_self = origin in {"first_party", "hybrid"}
        origin_badge_cls = "origin-self" if is_self else "origin-community"
        origin_text = a.get(
            "origin_label",
            "🔬 独自実機・AIチャット検証" if is_self else "📊 一次検証ログ定量調査",
        )
        if is_self and not origin_text.startswith(("🔬", "🧪")):
            origin_text = f"🔬 {origin_text}"

        m1 = a["summary_metrics"][0] if len(a["summary_metrics"]) > 0 else {"label": "データ", "value": "-"}
        m2 = a["summary_metrics"][1] if len(a["summary_metrics"]) > 1 else {"label": "指標", "value": "-"}
        data_date = a.get("data_updated_at", a["updated_at"])
        tags_chips = "".join(f'<span class="tag-chip">#{esc(t)}</span>' for t in a.get("tags", [])[:4])
        cards_html.append(
            f"""
            <article class="article-card" data-category="{esc(a["category"])}" data-origin="{esc(origin)}">
              <div class="card-meta">
                <span class="origin-badge {origin_badge_cls}">{esc(origin_text)}</span>
                <span class="category-pill">{esc(a["category"])}</span>
                <time class="date-text" datetime="{esc(data_date)}">更新: {esc(data_date)}</time>
              </div>
              <h2><a href="articles/{esc(slug)}.html" class="card-title-link">{esc(a["title"])}</a></h2>
              <p>{esc(a["subtitle"])}</p>
              <div class="card-takeaway-bar">
                <div class="card-metrics-inline">
                  <span class="inline-metric">{esc(m1["label"])}: <strong>{esc(m1["value"])}</strong></span>
                  <span class="inline-metric">{esc(m2["label"])}: <strong>{esc(m2["value"])}</strong></span>
                </div>
                <div class="card-tags-meta">
                  {tags_chips}
                  <span>N={int(a.get("sample_size_n", 0))}</span>
                </div>
              </div>
            </article>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(site["name"])} | {esc(site["jp_subtitle"])}</title>
  <meta name="description" content="Note・Zenn・Qiitaや公式仕様書だけでは辿り着けない「独自の実機・AIチャット検証ログ」と「海外一次検証データ」を、結論ファーストでわかりやすくまとめた技術検証メディア。">
  <link rel="canonical" href="{esc(base_url)}/">
  <meta property="og:title" content="{esc(site["name"])} | {esc(site["jp_subtitle"])}">
  <meta property="og:description" content="独自の実験・AIチャット検証と一次計測ログから、公式スペックの裏にある実測値をわかりやすく解説する技術検証ノート。">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(base_url)}/">
  <link rel="alternate" type="application/atom+xml" title="{esc(site["name"])} Feed" href="feed.xml">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  {render_header(config, root_prefix="")}

  <section class="editorial-intro">
    <div class="container intro-inner">
      <div class="intro-copy">
        <div class="intro-kicker">EMPIRICAL TECH NOTES &amp; BENCHMARKS</div>
        <h1>検索しても出てこない「実測値」と「独自の検証結果」を、結論ファーストで。</h1>
        <p>
          公式ドキュメントの曖昧な表記や、Zenn・Qiita・Note・Redditにもまだまとまっていない「実際に手元やAIチャットで試してわかった数値・挙動」を分析・構造化して公開しています。すべての記事に30秒で読める要点まとめと生CSVデータが付属します。
        </p>
      </div>
      <div class="intro-stats-inline" aria-label="公開データ統計">
        <span>検証記事: <strong>{len(articles)}本</strong> (独自検証 {first_party_count}本)</span>
        <span>累計検証サンプル: <strong>N = {total_samples}</strong></span>
      </div>
    </div>
  </section>

  <main id="main-content" class="container">
    <div class="controls-wrap">
      <div class="filter-bar" role="group" aria-label="カテゴリ・検証種別絞り込み">
        {''.join(filter_btns)}
      </div>
      <div>
        <label for="datasetSearch" class="category-pill">検索: </label>
        <input type="search" id="datasetSearch" class="search-input" placeholder="例: AST, Claude, 100W, USB4...">
      </div>
    </div>

    <div class="article-grid" id="articleGrid">
      {''.join(cards_html)}
    </div>
  </main>

  {render_footer(config, root_prefix="")}
</body>
</html>
"""


def render_about_page(config: dict[str, Any]) -> str:
    site = config["site"]
    base_url = validate_url(site["base_url"]).rstrip("/")
    amazon_notice = config["compliance"].get(
        "amazon_disclosure_text",
        "Amazon のアソシエイトとして、Nodusは適格販売により収入を得ています。",
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>調査手法・運営情報・プライバシーポリシー・免責事項 | {esc(site["name"])}</title>
  <meta name="description" content="{esc(site['name'])}のデータ集計メソドロジー、出典明記ポリシー、ステルスマーケティング規制対応、プライバシーポリシー、および運営者情報。">
  <link rel="canonical" href="{esc(base_url)}/about.html">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  {render_header(config, root_prefix="")}

  <div class="container article-layout">
    <main id="main-content" class="article-sheet">
      <h1 class="article-title">データ集計手法・運営情報・法的コンプライアンス</h1>
      <p class="article-subtitle">{esc(site["name"])} ({esc(site["organization"])}) における定量データの抽出基準、広告開示、プライバシー保護方針について</p>

      <div class="prose-section">
        <h3>1. 定量データの収集・正規化メソドロジーと統計的限界</h3>
        <p>
          当サイト（{esc(site["name"])}）は、ハードウェア製品やクラウド・SaaSサービスの「メーカー公称仕様（カタログ値）」と「実運用環境における実測パフォーマンス」の乖離、および独自環境での実機・AI検証結果を可視化する技術検証メディアです。測定条件（室温、負荷時間、バージョン、トークン数等）が確認可能な数値データを抽出し、中央値（Median）およびレンジを算出して比較表・CSVデータセットとして公開しています。個体差やアップデートにより実測値は変動するため、各記事にサンプル数（N）と測定条件メソドロジーを明記しています。
        </p>
      </div>
      <div class="prose-section">
        <h3>2. 知的財産権の尊重および一次情報源への参照方針</h3>
        <p>
          当サイトは、他者の創作的表現（投稿本文の文章や撮影画像・図表）の無断転載や翻案を行いません。著作権法上の保護対象とならない客観的な「計測事実・数値・条件データ」および当サイト独自の実験ログのみを基に、独自の比較体系および解説文として構成しています。また、データの検証可能性（トレーサビリティ）を担保するため、すべての記事末尾に一次情報源および公式仕様書への参照リンクを明記しています。
        </p>
      </div>
      <div class="prose-section" id="privacy">
        <h3>3. 編集独立性・広告配信方針および景品表示法（ステマ規制）への対応</h3>
        <p>
          {f"<strong>【Amazonアソシエイト・プログラム等の開示】</strong><br>{esc(amazon_notice)} また、当サイトは各種ASPおよびSaaSパートナープログラムに参加しており、記事内の「広告・PR（Sponsored）」セクションのリンクを経由して適格な購入や契約が行われた場合、紹介料を受領することがあります。" if is_monetized(config) else "<strong>【現在の運営ステータス（非商用・広告なし）】</strong><br>現在、当サイトはアフィリエイト広告やプロモーションリンクを一切掲載していない独立リサーチメディアとして運営されています。記事内の外部製品・サービスへのリンクはすべて読者の検証・参照利便性のための純粋な参考リンクであり、金銭的報酬やトラッキングタグは含まれていません。将来、審査通過後にアフィリエイトプログラムを導入する際は、日本の景品表示法（ステルスマーケティング告示）および各プログラム規約に準拠し、全ページ上部およびリンク周辺に明瞭な「【PR】」開示および必須文言を表示します。"}<br><br>
          <strong>【編集の独立性と不当表示の防止】</strong><br>
          特定のメーカーや外部事業者からの対価によって実測データの数値を改変したり、根拠のない順位付けを行うことは一切ありません。
        </p>
      </div>
      <div class="prose-section">
        <h3>4. プライバシーポリシーおよび外部送信規律に関する公表事項</h3>
        <p>
          当サイトはCloudflare Pages上で静的HTMLとして配信されており、当サイト自身が訪問者の氏名・メールアドレス等の個人情報を自動的に収集・保存することはありません。ただし、インフラ提供元であるCloudflare社のセキュリティ・CDN機能により、アクセス時のIPアドレスやリクエストヘッダが不正アクセス防止および配信最適化の目的で処理されます。また、記事内の外部リンク（Amazon.co.jp、各SaaS公式サイト等）をクリックして遷移する際、遷移先サイトにて成果計測のためのCookieやパラメータが利用される場合があります。
        </p>
      </div>
      <div class="prose-section" id="contact">
        <h3>5. 免責事項・訂正ポリシーおよび運営主体情報</h3>
        <p>
          掲載されている実測統計は特定環境下における観測値であり、すべての個体や最新アップデート後の環境で同一の結果を保証するものではありません。製品購入やサービス契約の最終判断は、各メーカーの最新公式仕様をご確認の上、ご自身の責任において行ってください。<br><br>
          <strong>運営主体:</strong> {esc(site["organization"])}<br>
          <strong>データ更新・訂正ポリシー:</strong> 掲載データの定期監査および最新仕様との突合を継続的に実施し、仕様改定や新ファームウェアによる数値変動が確認された場合は速やかにデータセット（CSV・本文）を改訂いたします。
        </p>
      </div>
    </main>
  </div>

  {render_footer(config, root_prefix="")}
</body>
</html>
"""


def render_404_page(config: dict[str, Any]) -> str:
    site = config["site"]
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>404 Page Not Found | {esc(site["name"])}</title>
  <meta name="robots" content="noindex">
  <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
  {render_header(config, root_prefix="/")}
  <main id="main-content" class="container article-body">
    <section class="panel">
      <h1 class="article-title">404 — 指定されたデータセットが見つかりません</h1>
      <p class="article-subtitle">URLが変更されたか、アーカイブされた可能性があります。トップページより最新の実測比較データベースをご参照ください。</p>
      <p><a href="/index.html" class="cta-btn">実測データベース一覧へ戻る &rarr;</a></p>
    </section>
  </main>
  {render_footer(config, root_prefix="/")}
</body>
</html>
"""


def render_atom_feed(articles: list[dict[str, Any]], config: dict[str, Any]) -> str:
    site = config["site"]
    base_url = validate_url(site["base_url"]).rstrip("/")
    updated = articles[0]["updated_at"] if articles else datetime.now().strftime("%Y-%m-%d")
    entries = []
    for a in articles:
        slug = validate_slug(a["slug"])
        url = f"{base_url}/articles/{slug}.html"
        entries.append(
            f"""  <entry>
    <title>{esc(a["title"])}</title>
    <link href="{esc(url)}" />
    <id>{esc(url)}</id>
    <updated>{esc(a["updated_at"])}T00:00:00Z</updated>
    <summary>{esc(a["subtitle"])}</summary>
  </entry>"""
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f"  <title>{esc(site['name'])} — {esc(site['jp_subtitle'])}</title>\n"
        f'  <link href="{esc(base_url)}/feed.xml" rel="self" />\n'
        f'  <link href="{esc(base_url)}/" />\n'
        f"  <updated>{esc(updated)}T00:00:00Z</updated>\n"
        f"  <id>{esc(base_url)}/</id>\n"
        f"  <author>\n    <name>{esc(site['organization'])}</name>\n  </author>\n"
        + "\n".join(entries)
        + "\n</feed>\n"
    )


def build_cloudflare_headers() -> str:
    return """/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'

/datasets/*.csv
  Content-Type: text/csv; charset=utf-8

/logs/*.json
  Content-Type: application/json; charset=utf-8

/articles/*.md
  Content-Type: text/markdown; charset=utf-8

/llms.txt
  Content-Type: text/plain; charset=utf-8

/llms-full.txt
  Content-Type: text/markdown; charset=utf-8
"""


def build_all() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    site_url = validate_url(config["site"]["base_url"]).rstrip("/")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    assets_dir = DIST_DIR / "assets"
    articles_out_dir = DIST_DIR / "articles"
    datasets_out_dir = DIST_DIR / "datasets"
    logs_out_dir = DIST_DIR / "logs"
    assets_dir.mkdir(parents=True, exist_ok=True)
    articles_out_dir.mkdir(parents=True, exist_ok=True)
    datasets_out_dir.mkdir(parents=True, exist_ok=True)
    logs_out_dir.mkdir(parents=True, exist_ok=True)

    # Write CSS and external JS
    (assets_dir / "style.css").write_text(build_css(), encoding="utf-8")
    (assets_dir / "app.js").write_text(build_js(), encoding="utf-8")

    # Load, validate, and sort articles
    articles: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        article = load_json(path)
        validate_article(article, config)
        slug = article["slug"]
        if slug in seen_slugs:
            raise ValueError(f"Duplicate article slug: {slug}")
        seen_slugs.add(slug)
        articles.append(article)

    articles.sort(
        key=lambda x: (
            x.get("updated_at", ""),
            1 if x.get("origin") in {"first_party", "hybrid"} else 0,
        ),
        reverse=True,
    )

    # Remove stale generated articles, Markdown files, CSV datasets, and raw logs
    for old_html in articles_out_dir.glob("*.html"):
        if old_html.stem not in seen_slugs:
            old_html.unlink()
    for old_md in articles_out_dir.glob("*.md"):
        if old_md.stem not in seen_slugs:
            old_md.unlink()
    for old_csv in datasets_out_dir.glob("*.csv"):
        if old_csv.stem not in seen_slugs:
            old_csv.unlink()
    for old_log in logs_out_dir.glob("*.json"):
        if old_log.stem not in seen_slugs:
            old_log.unlink()

    published_logs: list[str] = []
    markdown_corpus_blocks: list[str] = []

    # Render each article (HTML + Markdown), CSV dataset, and optional site-hosted raw log
    for article in articles:
        slug = validate_slug(article["slug"])
        out_path = (articles_out_dir / f"{slug}.html").resolve()
        if out_path.parent != articles_out_dir.resolve():
            raise ValueError(f"Path traversal blocked for slug: {slug}")
        out_path.write_text(render_article_page(article, config, articles), encoding="utf-8")

        md_content = render_article_markdown(article, config)
        md_path = (articles_out_dir / f"{slug}.md").resolve()
        md_path.write_text(md_content, encoding="utf-8")
        markdown_corpus_blocks.append(md_content)

        csv_path = (datasets_out_dir / f"{slug}.csv").resolve()
        csv_path.write_text(build_article_csv(article), encoding="utf-8")

        raw_log_src = RAW_LOGS_DIR / f"{slug}.json"
        if raw_log_src.exists():
            raw_obj = load_json(raw_log_src)
            log_out_path = (logs_out_dir / f"{slug}.json").resolve()
            log_out_path.write_text(json.dumps(raw_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            published_logs.append(f"logs/{slug}.json")

    # Render index, about, 404, feed, and _headers
    (DIST_DIR / "index.html").write_text(render_index_page(articles, config), encoding="utf-8")
    (DIST_DIR / "about.html").write_text(render_about_page(config), encoding="utf-8")
    (DIST_DIR / "404.html").write_text(render_404_page(config), encoding="utf-8")
    (DIST_DIR / "feed.xml").write_text(render_atom_feed(articles, config), encoding="utf-8")
    (DIST_DIR / "_headers").write_text(build_cloudflare_headers(), encoding="utf-8")

    # Generate sitemap.xml
    latest_date = articles[0]["updated_at"] if articles else datetime.now().strftime("%Y-%m-%d")
    urls = [
        f"  <url><loc>{esc(site_url)}/</loc><lastmod>{esc(latest_date)}</lastmod><priority>1.0</priority></url>",
        f"  <url><loc>{esc(site_url)}/about.html</loc><lastmod>{esc(latest_date)}</lastmod><priority>0.5</priority></url>",
    ]
    for a in articles:
        urls.append(
            f"  <url><loc>{esc(site_url)}/articles/{esc(a['slug'])}.html</loc><lastmod>{esc(a['updated_at'])}</lastmod><priority>0.9</priority></url>"
        )
    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (DIST_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")

    # Generate robots.txt with explicit Answer Engine / AI Search Crawler permissions
    ai_bots = [
        "OAI-SearchBot",
        "ChatGPT-User",
        "PerplexityBot",
        "ClaudeBot",
        "Claude-SearchBot",
        "Google-Extended",
        "Applebot-Extended",
        "Amazonbot",
    ]
    bot_rules = "".join(f"User-agent: {bot}\nAllow: /\n\n" for bot in ai_bots)
    robots_txt = (
        f"User-agent: *\nAllow: /\n\n"
        f"{bot_rules}"
        f"Sitemap: {site_url}/sitemap.xml\n"
    )
    (DIST_DIR / "robots.txt").write_text(robots_txt, encoding="utf-8")

    # Generate llms.txt (structured index with empirical KPIs) and llms-full.txt (complete Markdown corpus)
    llms_lines = [
        f"# {config['site']['name']} - {config['site']['tagline']}",
        f"> {config['site']['jp_subtitle']}",
        "",
        f"- Full Markdown Corpus for AI/LLMs: [{site_url}/llms-full.txt]({site_url}/llms-full.txt)",
        "- License for Data Citation: CC BY 4.0 (Attribute Nodus with canonical article URL)",
        "",
        "## Datasets & Quantitative Benchmark Reports",
    ]
    for a in articles:
        slug = a["slug"]
        n_val = int(a.get("sample_size_n", 0))
        kpi_summary = " / ".join(
            f"{m['label']}: {m['value']}" for m in a.get("summary_metrics", [])[:3] if m.get("value")
        )
        raw_suffix = (
            f" | [Raw Log JSON]({site_url}/logs/{slug}.json)"
            if (RAW_LOGS_DIR / f"{slug}.json").exists()
            else ""
        )
        llms_lines.append(
            f"- [{a['title']}]({site_url}/articles/{slug}.html) "
            f"([Markdown]({site_url}/articles/{slug}.md) | [CSV Dataset]({site_url}/datasets/{slug}.csv){raw_suffix}): "
            f"N={n_val} | {kpi_summary} — {a['subtitle']}"
        )
    (DIST_DIR / "llms.txt").write_text("\n".join(llms_lines) + "\n", encoding="utf-8")

    llms_full_header = (
        f"# {config['site']['name']} — Complete Empirical Benchmark Corpus (llms-full.txt)\n\n"
        f"> {config['site']['jp_subtitle']}\n\n"
        "---\n\n"
    )
    (DIST_DIR / "llms-full.txt").write_text(
        llms_full_header + "\n\n---\n\n".join(markdown_corpus_blocks) + "\n",
        encoding="utf-8",
    )

    indexnow_key = str(config.get("seo_loop", {}).get("indexnow_key", "")).strip()
    extra_files: list[str] = []
    if indexnow_key and re.match(r"^[a-fA-F0-9]{16,64}$", indexnow_key):
        (DIST_DIR / f"{indexnow_key}.txt").write_text(indexnow_key + "\n", encoding="utf-8")
        extra_files.append(f"{indexnow_key}.txt")

    gsc_verify_file = str(config.get("seo_loop", {}).get("google_site_verification_file", "")).strip()
    if gsc_verify_file and re.match(r"^google[a-fA-F0-9]{10,32}\.html$", gsc_verify_file):
        (DIST_DIR / gsc_verify_file).write_text(
            f"google-site-verification: {gsc_verify_file}",
            encoding="utf-8",
        )
        extra_files.append(gsc_verify_file)

    summary = {
        "status": "ok",
        "articles_built": len(articles),
        "raw_logs_published": len(published_logs),
        "output_dir": str(DIST_DIR),
        "files": [
            "index.html",
            "about.html",
            "404.html",
            "feed.xml",
            "_headers",
            "sitemap.xml",
            "robots.txt",
            "llms.txt",
            "llms-full.txt",
        ]
        + extra_files
        + [f"articles/{a['slug']}.html" for a in articles]
        + [f"articles/{a['slug']}.md" for a in articles]
        + [f"datasets/{a['slug']}.csv" for a in articles]
        + published_logs,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build_all()
