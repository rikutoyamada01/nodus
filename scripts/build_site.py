#!/usr/bin/env python3
"""
Nodus Static Site & Quantitative Intelligence Builder
Generates enterprise-grade HTML5, Schema.org JSON-LD, CSV datasets, Atom feed,
sitemap.xml, robots.txt, llms.txt, 404.html, and Cloudflare Pages _headers
from structured quantitative datasets in content/articles/*.json.
"""

from __future__ import annotations

import csv
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


def build_css() -> str:
    return """
:root {
  --bg-page: #f8fafc;
  --bg-surface: #ffffff;
  --bg-subtle: #f1f5f9;
  --bg-dark: #0f172a;
  --text-primary: #0f172a;
  --text-secondary: #334155;
  --text-muted: #475569;
  --border-color: #e2e8f0;
  --border-strong: #cbd5e1;
  --brand-primary: #1e40af;
  --brand-accent: #2563eb;
  --brand-light: #eff6ff;
  --status-good: #047857;
  --status-good-bg: #ecfdf5;
  --status-warn: #b45309;
  --status-warn-bg: #fffbeb;
  --status-danger: #b91c1c;
  --status-danger-bg: #fef2f2;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
  --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, "Liberation Mono", Menlo, monospace;
  --shadow-sm: 0 1px 2px 0 rgba(15, 23, 42, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.05);
  --radius-md: 8px;
  --radius-lg: 12px;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  scroll-padding-top: 80px;
}

body {
  font-family: var(--font-sans);
  background-color: var(--bg-page);
  color: var(--text-primary);
  line-height: 1.7;
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
  border-radius: var(--radius-md);
  font-weight: 700;
  z-index: 1000;
  transition: top 0.15s ease;
}

.skip-link:focus {
  top: 12px;
  color: #ffffff;
  outline: 3px solid #93c5fd;
}

a {
  color: var(--brand-accent);
  text-decoration: none;
  transition: color 0.15s ease;
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
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 20px;
}

/* Header */
.site-header {
  background: var(--bg-dark);
  color: #ffffff;
  border-bottom: 1px solid #1e293b;
  position: sticky;
  top: 0;
  z-index: 50;
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 64px;
  padding-top: 8px;
  padding-bottom: 8px;
  flex-wrap: wrap;
  gap: 12px;
}

.brand-logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #ffffff;
  font-weight: 800;
  font-size: 1.2rem;
  letter-spacing: -0.02em;
  text-decoration: none;
}

.brand-logo:hover {
  color: #ffffff;
  text-decoration: none;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 0.95rem;
  font-weight: 700;
  color: #ffffff;
  flex-shrink: 0;
}

.brand-tagline {
  font-size: 0.78rem;
  color: #cbd5e1;
  font-weight: 400;
  border-left: 1px solid #334155;
  padding-left: 12px;
}

.site-nav {
  display: flex;
  align-items: center;
  gap: 18px;
  font-size: 0.85rem;
  flex-wrap: wrap;
}

.site-nav a {
  color: #e2e8f0;
  font-weight: 500;
  text-decoration: none;
}

.site-nav a:hover {
  color: #ffffff;
  text-decoration: underline;
}

/* Compliance Bar */
.pr-banner {
  background: #f1f5f9;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 0.78rem;
  padding: 8px 0;
  font-weight: 500;
}

/* Hero Section */
.hero {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color: #ffffff;
  padding: 52px 0 44px;
  border-bottom: 1px solid #334155;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(59, 130, 246, 0.18);
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: #bfdbfe;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  padding: 4px 12px;
  border-radius: 999px;
  margin-bottom: 16px;
}

.hero h1 {
  font-size: 2.15rem;
  line-height: 1.28;
  font-weight: 800;
  letter-spacing: -0.025em;
  margin-bottom: 14px;
}

.hero p {
  color: #e2e8f0;
  font-size: 1.02rem;
  max-width: 760px;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr));
  gap: 16px;
  margin-top: 32px;
  padding-top: 28px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.hero-stat-item {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 14px 18px;
  border-radius: var(--radius-md);
}

.hero-stat-num {
  font-family: var(--font-mono);
  font-size: 1.35rem;
  font-weight: 700;
  color: #93c5fd;
}

.hero-stat-label {
  font-size: 0.8rem;
  color: #cbd5e1;
  margin-top: 2px;
}

/* Index Controls & Cards */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 36px 0 20px;
  flex-wrap: wrap;
  gap: 14px;
}

.section-title {
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.controls-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  width: 100%;
  justify-content: space-between;
  margin-bottom: 24px;
}

.filter-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  background: var(--bg-surface);
  border: 1px solid var(--border-strong);
  color: var(--text-secondary);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.filter-btn[aria-pressed="true"],
.filter-btn:hover {
  background: var(--brand-accent);
  color: #ffffff;
  border-color: var(--brand-accent);
}

.search-input {
  background: var(--bg-surface);
  border: 1px solid var(--border-strong);
  color: var(--text-primary);
  padding: 7px 14px;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  min-width: 240px;
  max-width: 100%;
}

.article-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
  gap: 24px;
  margin-bottom: 56px;
}

.article-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 22px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}

.article-card[hidden] {
  display: none !important;
}

.article-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: #93c5fd;
}

.card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.75rem;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.category-pill {
  background: var(--brand-light);
  color: var(--brand-primary);
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  font-family: var(--font-mono);
}

.date-text {
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.article-card h2 {
  font-size: 1.12rem;
  line-height: 1.45;
  margin-bottom: 10px;
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
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: 18px;
}

.card-metrics-preview {
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
}

.mini-metric-label {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.mini-metric-val {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-primary);
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  font-size: 0.82rem;
  font-weight: 600;
  flex-wrap: wrap;
  gap: 8px;
}

.card-count-meta {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--text-muted);
  font-weight: 500;
}

/* Article Detail Layout */
.article-header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  padding: 36px 0 28px;
}

.breadcrumb {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 14px;
  font-family: var(--font-mono);
  word-break: break-word;
}

.article-title {
  font-size: 1.85rem;
  line-height: 1.32;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-bottom: 12px;
}

.article-subtitle {
  font-size: 1.02rem;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.article-timestamps {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
}

.methodology-box {
  background: var(--bg-subtle);
  border-left: 4px solid var(--brand-primary);
  padding: 12px 16px;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  font-size: 0.84rem;
  color: var(--text-secondary);
  margin-top: 12px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
  gap: 16px;
  margin-top: 24px;
}

.kpi-card {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-left: 4px solid var(--brand-accent);
  border-radius: var(--radius-md);
  padding: 16px;
}

.kpi-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.kpi-value {
  font-family: var(--font-mono);
  font-size: 1.3rem;
  font-weight: 800;
  color: var(--text-primary);
  margin: 4px 0;
}

.kpi-sub {
  font-size: 0.76rem;
  color: var(--text-secondary);
}

.article-body {
  padding: 32px 0 64px;
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 28px;
  box-shadow: var(--shadow-sm);
}

.panel-title {
  font-size: 1.18rem;
  font-weight: 700;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.panel-unit {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  color: var(--text-muted);
  background: var(--bg-subtle);
  padding: 4px 10px;
  border-radius: 6px;
}

.csv-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--brand-primary);
  background: var(--brand-light);
  border: 1px solid #bfdbfe;
  padding: 4px 10px;
  border-radius: 6px;
  text-decoration: none;
}

.csv-btn:hover {
  background: #dbeafe;
  text-decoration: none;
}

/* Spec Gap Chart (SVG bars for zero inline CSS) */
.gap-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 18px;
}

.gap-item {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  background: #fcfdff;
}

.gap-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  flex-wrap: wrap;
  gap: 8px;
}

.gap-item-name {
  font-weight: 700;
  font-size: 0.96rem;
}

.status-badge {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
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
  gap: 8px;
  margin: 10px 0;
}

.bar-row {
  display: grid;
  grid-template-columns: 260px 1fr;
  align-items: center;
  gap: 12px;
}

.bar-label {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.bar-svg {
  width: 100%;
  height: 12px;
  background: var(--bg-subtle);
  border-radius: 999px;
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

/* Comparison Table */
.table-wrap {
  overflow-x: auto;
  margin-top: 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

table.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
  text-align: left;
}

table.data-table caption {
  text-align: left;
  font-size: 0.78rem;
  color: var(--text-muted);
  padding: 8px 14px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border-color);
}

table.data-table thead th {
  background: var(--bg-dark);
  color: #ffffff;
  font-weight: 600;
  padding: 0;
  white-space: nowrap;
  font-size: 0.78rem;
}

.th-sort-btn {
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  font-weight: 600;
  padding: 12px 14px;
  width: 100%;
  text-align: left;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.th-sort-btn:hover {
  background: #1e293b;
}

table.data-table td,
table.data-table tbody th {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-color);
  font-family: var(--font-mono);
  font-size: 0.82rem;
}

table.data-table tbody th {
  font-family: var(--font-sans);
  font-weight: 700;
  background: #f8fafc;
  color: var(--text-primary);
}

table.data-table tr:last-child td,
table.data-table tr:last-child th {
  border-bottom: none;
}

table.data-table tbody tr:hover td,
table.data-table tbody tr:hover th {
  background: #f1f5f9;
}

/* Analytical Prose */
.prose-section {
  margin-bottom: 24px;
}

.prose-section:last-child {
  margin-bottom: 0;
}

.prose-section h2 {
  font-size: 1.16rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--bg-subtle);
}

.prose-section p {
  color: var(--text-secondary);
  font-size: 0.95rem;
}

/* Monetization / Affiliate CTA */
.cta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 16px;
  margin-top: 16px;
}

.cta-card {
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  padding: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12px;
}

.cta-badge {
  display: inline-block;
  background: var(--brand-light);
  color: var(--brand-primary);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  width: fit-content;
}

.cta-title {
  font-weight: 700;
  font-size: 0.96rem;
  color: var(--text-primary);
  margin-top: 8px;
}

.cta-provider {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 4px;
}

.cta-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-accent);
  color: #ffffff;
  font-weight: 600;
  font-size: 0.86rem;
  padding: 10px 16px;
  border-radius: 6px;
  text-align: center;
  text-decoration: none;
  transition: background 0.15s;
}

.cta-btn:hover {
  background: var(--brand-primary);
  color: #ffffff;
  text-decoration: none;
}

.cta-disclosure-note {
  font-size: 0.76rem;
  color: var(--text-muted);
  margin-top: 12px;
}

/* FAQ & Sources */
.faq-list {
  margin-top: 8px;
}

.faq-item {
  border-bottom: 1px solid var(--border-color);
  padding: 16px 0;
}

.faq-item:last-child {
  border-bottom: none;
}

.faq-q {
  font-weight: 700;
  font-size: 0.96rem;
  margin-bottom: 6px;
  color: var(--text-primary);
}

.faq-a {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.source-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-subtle);
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.82rem;
  flex-wrap: wrap;
  gap: 8px;
}

.source-meta {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 0.75rem;
}

/* Footer */
.site-footer {
  background: var(--bg-dark);
  color: #cbd5e1;
  padding: 48px 0 36px;
  font-size: 0.85rem;
  margin-top: 64px;
}

.footer-grid {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 32px;
  padding-bottom: 28px;
  border-bottom: 1px solid #1e293b;
}

.footer-desc {
  max-width: 480px;
  color: #cbd5e1;
  margin-top: 8px;
  font-size: 0.82rem;
}

.footer-amazon-notice {
  margin-top: 10px;
  font-size: 0.78rem;
  color: #94a3b8;
}

.footer-links {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.footer-links a {
  color: #e2e8f0;
  text-decoration: none;
}

.footer-links a:hover {
  color: #ffffff;
  text-decoration: underline;
}

.footer-bottom {
  padding-top: 24px;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.78rem;
  color: #94a3b8;
}

@media (max-width: 680px) {
  .brand-tagline {
    display: none;
  }
  .hero h1 {
    font-size: 1.55rem;
  }
  .article-title {
    font-size: 1.4rem;
  }
  .bar-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
  .panel {
    padding: 18px;
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

    var activeCategory = "all";

    function applyFilter() {
      var query = searchInput ? searchInput.value.trim().toLowerCase() : "";
      cards.forEach(function (card) {
        var catMatch = activeCategory === "all" || card.getAttribute("data-category") === activeCategory;
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
        activeCategory = btn.getAttribute("data-filter") || "all";
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

  function extractLeadingNumber(text) {
    var m = text.match(/[-+]?\d+(?:,\d{3})*(?:\.\d+)?/);
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
            var cellA = a.children[colIdx] ? a.children[colIdx].textContent.trim() : "";
            var cellB = b.children[colIdx] ? b.children[colIdx].textContent.trim() : "";
            var numA = extractLeadingNumber(cellA);
            var numB = extractLeadingNumber(cellB);
            if (!isNaN(numA) && !isNaN(numB) && numA !== numB) {
              return asc ? numA - numB : numB - numA;
            }
            return asc ? cellA.localeCompare(cellB, "ja") : cellB.localeCompare(cellA, "ja");
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
      <span class="brand-tagline">{esc(site["jp_subtitle"])}</span>
    </a>
    <nav class="site-nav" aria-label="グローバルナビゲーション">
      <a href="{root_prefix}index.html">実測データベース一覧</a>
      <a href="{root_prefix}about.html">調査手法・運営情報</a>
      <a href="{root_prefix}about.html#privacy">運営ポリシー・プライバシー</a>
      <a href="{root_prefix}feed.xml">RSS/Atom</a>
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
    contact_url = validate_url(site.get("contact_url", "https://github.com/rikutoyamada01/nodus/issues"))
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
          {esc(site["tagline"])} — カタログ公称値とグローバル技術コミュニティの一次検証ログ・実測統計データを突合する定量リサーチメディア。
        </p>
        <p class="footer-amazon-notice">{esc(footer_notice)}</p>
      </div>
      <div class="footer-links">
        <a href="{root_prefix}index.html">トップページ</a>
        <a href="{root_prefix}about.html">調査手法・免責事項</a>
        <a href="{root_prefix}about.html#privacy">プライバシーポリシー・外部送信規律</a>
        <a href="{esc(contact_url)}" target="_blank" rel="noopener noreferrer">お問い合わせ・訂正申請</a>
        <a href="{root_prefix}sitemap.xml">Sitemap</a>
        <a href="{root_prefix}llms.txt">LLMs.txt</a>
      </div>
    </div>
    <div class="footer-bottom">
      <span>&copy; {esc(site["copyright_year"])} {esc(site["organization"])}. All rights reserved.</span>
      <span>Quantitative Data Engine (Verified Schema &amp; CSP Enforced)</span>
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


def render_article_page(article: dict[str, Any], config: dict[str, Any]) -> str:
    site = config["site"]
    seo = article["seo"]
    slug = validate_slug(article["slug"])
    base_url = validate_url(site["base_url"]).rstrip("/")
    canonical_url = f"{base_url}/articles/{slug}.html"
    data_updated_at = article.get("data_updated_at", article["updated_at"])
    methodology_note = article.get("methodology_note", "")
    amazon_notice = config["compliance"].get(
        "amazon_disclosure_text",
        "Amazon のアソシエイトとして、Nodusは適格販売により収入を得ています。",
    )

    faq_entities = [
        {
            "@type": "Question",
            "name": f["question"],
            "acceptedAnswer": {"@type": "Answer", "text": f["answer"]},
        }
        for f in article.get("faqs", [])
    ]
    schema_ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "TechArticle",
                "headline": article["title"],
                "description": seo["meta_description"],
                "datePublished": article["published_at"],
                "dateModified": article["updated_at"],
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
                "mainEntityOfPage": canonical_url,
            },
            {
                "@type": "Dataset",
                "name": article["title"],
                "description": article["subtitle"],
                "url": canonical_url,
                "dateModified": data_updated_at,
                "distribution": {
                    "@type": "DataDownload",
                    "encodingFormat": "text/csv",
                    "contentUrl": f"{base_url}/datasets/{slug}.csv",
                },
            },
            {
                "@type": "FAQPage",
                "mainEntity": faq_entities,
            },
        ],
    }

    kpi_html = "".join(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">{esc(m["label"])}</div>
          <div class="kpi-value">{esc(m["value"])}</div>
          <div class="kpi-sub">{esc(m["subtext"])}</div>
        </div>
        """
        for m in article.get("summary_metrics", [])
    )

    chart = article["spec_gap_chart"]
    max_scale = float(chart.get("max_scale", 100.0)) or 100.0
    gap_items_html = []
    for item in chart.get("items", []):
        off_pct = min(100.0, max(4.0, (float(item["official_value"]) / max_scale) * 100.0))
        meas_pct = min(100.0, max(4.0, (float(item["measured_value"]) / max_scale) * 100.0))
        status_raw = item.get("status", "good")
        status_cls = f"status-{status_raw if status_raw in ALLOWED_STATUSES else 'good'}"
        status_text = {
            "good": "実測良好 / 高効率",
            "warning": "条件付き制限・乖離あり",
            "danger": "大幅乖離・高消費注意",
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
                    <rect class="bar-rect-official" x="0" y="0" width="{off_pct:.1f}" height="6" rx="3"></rect>
                  </svg>
                </div>
                <div class="bar-row">
                  <span class="bar-label"><strong>{esc(item["measured_label"])}</strong></span>
                  <svg class="bar-svg" viewBox="0 0 100 6" preserveAspectRatio="none" role="img" aria-label="{esc(item['measured_label'])}">
                    <rect class="bar-rect-measured" x="0" y="0" width="{meas_pct:.1f}" height="6" rx="3"></rect>
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
        rest_cells = "".join(f"<td>{esc(cell)}</td>" for cell in row[1:])
        tr_rows.append(f"<tr>{first_cell}{rest_cells}</tr>")
    tr_html = "".join(tr_rows)

    sections_html = "".join(
        f"""
        <div class="prose-section">
          <h2>{esc(sec["heading"])}</h2>
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
                    <div class="cta-provider">取扱・提供元: {esc(aff["provider"])} {provider_suffix}</div>
                  </div>
                  <a href="{esc(aff_url)}" target="_blank" rel="{rel_attr}" class="cta-btn">
                    公式仕様・最新価格を確認する &rarr;
                  </a>
                </div>
                """
            )
    cta_panel_html = ""
    if cta_cards:
        panel_badge = "【広告・PR】Sponsored Links" if monetized else "Reference Links (広告なし)"
        panel_note = (
            f"※上記リンクにはアフィリエイト広告が含まれます。{esc(amazon_notice)}"
            if monetized
            else "※上記は読者の利便性のための純粋な参考リンクであり、現在アフィリエイトタグや広告報酬は一切設定されていません。"
        )
        cta_panel_html = f"""
        <section class="panel" aria-label="検証対象モデル・関連サービス参考リンク">
          <div class="panel-title">
            <span>検証対象モデル・関連サービス取扱先リンク</span>
            <span class="panel-unit">{panel_badge}</span>
          </div>
          <div class="cta-grid">
            {''.join(cta_cards)}
          </div>
          <p class="cta-disclosure-note">
            {panel_note}
          </p>
        </section>
        """

    faq_html = "".join(
        f"""
        <div class="faq-item">
          <div class="faq-q">Q. {esc(f["question"])}</div>
          <div class="faq-a">{esc(f["answer"])}</div>
        </div>
        """
        for f in article.get("faqs", [])
    )

    sources_html = "".join(
        f"""
        <li class="source-item">
          <a href="{esc(validate_url(s["url"]))}" target="_blank" rel="noopener noreferrer">{esc(s["title"])}</a>
          <span class="source-meta">対象: {esc(s["sample_size"])} | 確認日: {esc(s["verified_date"])}</span>
        </li>
        """
        for s in article.get("sources", [])
    )

    methodology_html = ""
    if methodology_note:
        methodology_html = f'<div class="methodology-box"><strong>集計・測定条件メソドロジー:</strong> {esc(methodology_note)}</div>'

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
  <link rel="stylesheet" href="../assets/style.css">
  <script type="application/ld+json">{safe_json_ld(schema_ld)}</script>
</head>
<body>
  {render_header(config, root_prefix="../")}

  <section class="article-header">
    <div class="container">
      <nav class="breadcrumb" aria-label="パンくずリスト">
        <a href="../index.html">Nodus</a> &rsaquo; <span>{esc(article["category"])}</span> &rsaquo; <span>{esc(slug)}</span>
      </nav>
      <h1 class="article-title">{esc(article["title"])}</h1>
      <p class="article-subtitle">{esc(article["subtitle"])}</p>
      <div class="article-timestamps">
        <span>公開日: <time datetime="{esc(article["published_at"])}">{esc(article["published_at"])}</time></span>
        <span>実測データ更新日: <time datetime="{esc(data_updated_at)}">{esc(data_updated_at)}</time></span>
        <span>記事改訂日: <time datetime="{esc(article["updated_at"])}">{esc(article["updated_at"])}</time></span>
      </div>
      {methodology_html}
      <div class="kpi-grid">
        {kpi_html}
      </div>
    </div>
  </section>

  <main id="main-content" class="container article-body">
    <section class="panel">
      <div class="panel-title">
        <span>{esc(chart["title"])}</span>
        <span class="panel-unit">単位: {esc(chart["unit"])}</span>
      </div>
      <div class="gap-list">
        {''.join(gap_items_html)}
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <span>公称スペック vs コミュニティ実測値 マトリクス比較表</span>
        <div class="panel-actions">
          <a href="../datasets/{esc(slug)}.csv" download="{esc(slug)}.csv" class="csv-btn">CSVダウンロード</a>
          <span class="panel-unit">列ヘッダークリックでソート可能</span>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <caption>{esc(article["title"])} — 定量比較データテーブル（実測値中央値および公称仕様）</caption>
          <thead><tr>{th_html}</tr></thead>
          <tbody>{tr_html}</tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      {sections_html}
    </section>

    {cta_panel_html}

    <section class="panel">
      <div class="panel-title"><span>よくある質問（実測データFAQ）</span></div>
      <div class="faq-list">
        {faq_html}
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <span>一次情報・コミュニティ検証ログ出典・仕様基準 (Primary Sources)</span>
        <span class="panel-unit">Fact Provenance</span>
      </div>
      <ul class="source-list">
        {sources_html}
      </ul>
    </section>
  </main>

  {render_footer(config, root_prefix="../")}
</body>
</html>
"""


def render_index_page(articles: list[dict[str, Any]], config: dict[str, Any]) -> str:
    site = config["site"]
    base_url = validate_url(site["base_url"]).rstrip("/")
    categories = sorted({a["category"] for a in articles})

    total_samples = sum(int(a.get("sample_size_n", 0)) for a in articles)
    total_models = sum(len(a.get("comparison_table", {}).get("rows", [])) for a in articles)

    filter_btns = [
        '<button type="button" class="filter-btn" data-filter="all" aria-pressed="true">すべて表示</button>'
    ]
    for cat in categories:
        filter_btns.append(
            f'<button type="button" class="filter-btn" data-filter="{esc(cat)}" aria-pressed="false">{esc(cat)}</button>'
        )

    cards_html = []
    for a in articles:
        slug = validate_slug(a["slug"])
        m1 = a["summary_metrics"][0] if len(a["summary_metrics"]) > 0 else {"label": "データ", "value": "-"}
        m2 = a["summary_metrics"][1] if len(a["summary_metrics"]) > 1 else {"label": "指標", "value": "-"}
        data_date = a.get("data_updated_at", a["updated_at"])
        cards_html.append(
            f"""
            <article class="article-card" data-category="{esc(a["category"])}">
              <div>
                <div class="card-meta">
                  <span class="category-pill">{esc(a["category"])}</span>
                  <time class="date-text" datetime="{esc(data_date)}">実測更新: {esc(data_date)}</time>
                </div>
                <h2><a href="articles/{esc(slug)}.html" class="card-title-link">{esc(a["title"])}</a></h2>
                <p>{esc(a["subtitle"])}</p>
              </div>
              <div>
                <div class="card-metrics-preview">
                  <div>
                    <div class="mini-metric-label">{esc(m1["label"])}</div>
                    <div class="mini-metric-val">{esc(m1["value"])}</div>
                  </div>
                  <div>
                    <div class="mini-metric-label">{esc(m2["label"])}</div>
                    <div class="mini-metric-val">{esc(m2["value"])}</div>
                  </div>
                </div>
                <div class="card-footer">
                  <a href="articles/{esc(slug)}.html">実測比較データを見る &rarr;</a>
                  <span class="card-count-meta">
                    {len(a["comparison_table"]["rows"])} Models / N={int(a.get("sample_size_n", 0))}
                  </span>
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
  <meta name="description" content="カタログ公称スペックには記載されない実測出力・非公開レート制限・持続性能を、Reddit等の海外一次検証ログから定量集計・比較するデータベースメディア。">
  <link rel="canonical" href="{esc(base_url)}/">
  <meta property="og:title" content="{esc(site["name"])} | {esc(site["jp_subtitle"])}">
  <meta property="og:description" content="カタログ公称スペックとコミュニティ実測値のギャップを数値とCSVで公開する定量比較データベース。">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(base_url)}/">
  <link rel="alternate" type="application/atom+xml" title="{esc(site["name"])} Feed" href="feed.xml">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  {render_header(config, root_prefix="")}

  <section class="hero">
    <div class="container">
      <div class="hero-badge">QUANTITATIVE SPEC INTELLIGENCE // NODUS</div>
      <h1>カタログ値の裏にある「実測値」を、数字で比較する。</h1>
      <p>
        メーカー公式ページの「最大〇〇W」「高速アクセス」といった定性的な宣伝文句ではなく、グローバル開発者・ハードウェア検証コミュニティの一次計測ログを集計し、測定条件付きの中央値テーブルおよびCSVデータセットとして公開しています。
      </p>
      <div class="hero-stats">
        <div class="hero-stat-item">
          <div class="hero-stat-num">{len(articles)} Datasets</div>
          <div class="hero-stat-label">公開中の実測比較レポート（CSV付）</div>
        </div>
        <div class="hero-stat-item">
          <div class="hero-stat-num">N = {total_samples}</div>
          <div class="hero-stat-label">累計集計コミュニティ検証ログ・セッション</div>
        </div>
        <div class="hero-stat-item">
          <div class="hero-stat-num">{total_models} Models</div>
          <div class="hero-stat-label">横断比較済みハードウェア・SaaSプラン数</div>
        </div>
      </div>
    </div>
  </section>

  <main id="main-content" class="container">
    <div class="section-header">
      <h2 class="section-title">最新の実測比較・定量検証レポート</h2>
    </div>
    <div class="controls-wrap">
      <div class="filter-bar" role="group" aria-label="カテゴリ絞り込み">
        {''.join(filter_btns)}
      </div>
      <div>
        <label for="datasetSearch" class="mini-metric-label">キーワード検索: </label>
        <input type="search" id="datasetSearch" class="search-input" placeholder="例: 100W, A100, Claude, USB4...">
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
    contact_url = validate_url(site.get("contact_url", "https://github.com/rikutoyamada01/nodus/issues"))
    repo_url = validate_url(site.get("repository_url", "https://github.com/rikutoyamada01/nodus"))
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

  <section class="article-header">
    <div class="container">
      <h1 class="article-title">データ集計手法・運営情報・法的コンプライアンス</h1>
      <p class="article-subtitle">{esc(site["name"])} ({esc(site["organization"])}) における定量データの抽出基準、広告開示、プライバシー保護方針について</p>
    </div>
  </section>

  <main id="main-content" class="container article-body">
    <section class="panel">
      <div class="prose-section">
        <h2>1. 定量データの収集・正規化メソドロジーと統計的限界</h2>
        <p>
          当サイト（{esc(site["name"])}）は、ハードウェア製品やクラウド・SaaSサービスの「メーカー公称仕様（カタログ値）」と「実運用環境における実測パフォーマンス」の乖離を可視化することを目的とした定量データベースメディアです。英語圏の技術コミュニティ（Redditの各専門Subreddit、Hacker News、GitHub Discussions等）で公開されている計測報告から、測定条件（室温、負荷時間、バージョン等）が確認可能な数値データを抽出し、外れ値を除外した中央値（Median）およびレンジを算出して独自の比較表・CSVデータセットを構築しています。個体差やファームウェア更新、測定機器の誤差により実測値は変動するため、各記事にサンプル数（N）と測定条件メソドロジーを明記しています。
        </p>
      </div>
      <div class="prose-section">
        <h2>2. 知的財産権の尊重および一次情報源への参照方針</h2>
        <p>
          当サイトは、他者の創作的表現（投稿本文の文章や撮影画像・図表）の無断転載や翻案を行いません。著作権法上の保護対象とならない客観的な「計測事実・数値・条件データ」のみを抽出し、当サイト独自の比較体系および解説文として再構成しています。また、データの検証可能性（トレーサビリティ）を担保するため、すべての記事末尾に一次情報源および公式仕様書への参照リンクを明記しています。
        </p>
      </div>
      <div class="prose-section" id="privacy">
        <h2>3. 編集独立性・広告配信方針および景品表示法（ステマ規制）への対応</h2>
        <p>
          {f"<strong>【Amazonアソシエイト・プログラム等の開示】</strong><br>{esc(amazon_notice)} また、当サイトは各種ASPおよびSaaSパートナープログラムに参加しており、記事内の「広告・PR（Sponsored Links）」セクションのリンクを経由して適格な購入や契約が行われた場合、紹介料を受領することがあります。" if is_monetized(config) else "<strong>【現在の運営ステータス（非商用・広告なし）】</strong><br>現在、当サイトはアフィリエイト広告やプロモーションリンクを一切掲載していない独立リサーチメディアとして運営されています。記事内の外部製品・サービスへのリンクはすべて読者の検証・参照利便性のための純粋な参考リンクであり、金銭的報酬やトラッキングタグは含まれていません。将来、審査通過後にアフィリエイトプログラムを導入する際は、日本の景品表示法（ステルスマーケティング告示）および各プログラム規約に準拠し、全ページ上部およびリンク周辺に明瞭な「【PR】」開示および必須文言を表示します。"}<br><br>
          <strong>【編集の独立性と不当表示の防止】</strong><br>
          特定のメーカーや外部事業者からの対価によって実測データの数値を改変したり、根拠のない順位付けを行うことは一切ありません。
        </p>
      </div>
      <div class="prose-section">
        <h2>4. プライバシーポリシーおよび外部送信規律に関する公表事項</h2>
        <p>
          当サイトはCloudflare Pages上で静的HTMLとして配信されており、当サイト自身が訪問者の氏名・メールアドレス等の個人情報を自動的に収集・保存することはありません。ただし、インフラ提供元であるCloudflare社のセキュリティ・CDN機能により、アクセス時のIPアドレスやリクエストヘッダが不正アクセス防止および配信最適化の目的で処理されます。また、記事内の外部リンク（Amazon.co.jp、各SaaS公式サイト等）をクリックして遷移する際、遷移先サイトにてアフィリエイト成果計測のためのCookieやパラメータが利用される場合があります。
        </p>
      </div>
      <div class="prose-section">
        <h2>5. 免責事項・訂正ポリシー・運営者情報およびお問い合わせ窓口</h2>
        <p>
          掲載されている実測統計はコミュニティの特定環境下における観測値であり、すべての個体や最新アップデート後の環境で同一の結果を保証するものではありません。製品購入やサービス契約の最終判断は、各メーカーの最新公式仕様をご確認の上、ご自身の責任において行ってください。<br><br>
          <strong>運営主体:</strong> {esc(site["organization"])}<br>
          <strong>公開リポジトリ・データ監査履歴:</strong> <a href="{esc(repo_url)}" target="_blank" rel="noopener noreferrer">{esc(repo_url)}</a><br>
          <strong>お問い合わせ・データ訂正申請窓口:</strong> 記事内の数値データの誤り、最新ファームウェアでの再計測データ提供、または権利関係に関するご連絡は、<a href="{esc(contact_url)}" target="_blank" rel="noopener noreferrer">公式GitHub Issue窓口 ({esc(contact_url)})</a> よりお願いいたします。確認の上、速やかにデータセットの検証・改訂を行います。
        </p>
      </div>
    </section>
  </main>

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
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f"  <title>{esc(site['name'])} — {esc(site['jp_subtitle'])}</title>\n"
        f'  <link href="{esc(base_url)}/feed.xml" rel="self" />\n'
        f'  <link href="{esc(base_url)}/" />\n'
        f"  <updated>{esc(updated)}T00:00:00Z</updated>\n"
        f"  <id>{esc(base_url)}/</id>\n"
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
"""


def build_all() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    site_url = validate_url(config["site"]["base_url"]).rstrip("/")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    assets_dir = DIST_DIR / "assets"
    articles_out_dir = DIST_DIR / "articles"
    datasets_out_dir = DIST_DIR / "datasets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    articles_out_dir.mkdir(parents=True, exist_ok=True)
    datasets_out_dir.mkdir(parents=True, exist_ok=True)

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

    articles.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    # Remove stale generated articles and CSV datasets
    for old_html in articles_out_dir.glob("*.html"):
        if old_html.stem not in seen_slugs:
            old_html.unlink()
    for old_csv in datasets_out_dir.glob("*.csv"):
        if old_csv.stem not in seen_slugs:
            old_csv.unlink()

    # Render each article & CSV dataset
    for article in articles:
        slug = validate_slug(article["slug"])
        out_path = (articles_out_dir / f"{slug}.html").resolve()
        if out_path.parent != articles_out_dir.resolve():
            raise ValueError(f"Path traversal blocked for slug: {slug}")
        out_path.write_text(render_article_page(article, config), encoding="utf-8")

        csv_path = (datasets_out_dir / f"{slug}.csv").resolve()
        csv_path.write_text(build_article_csv(article), encoding="utf-8")

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

    # Generate robots.txt
    robots_txt = f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n"
    (DIST_DIR / "robots.txt").write_text(robots_txt, encoding="utf-8")

    # Generate llms.txt (for AI Search Engines / GEO citation)
    llms_lines = [
        f"# {config['site']['name']} - {config['site']['tagline']}",
        f"> {config['site']['jp_subtitle']}",
        "",
        "## Datasets & Quantitative Benchmark Reports",
    ]
    for a in articles:
        llms_lines.append(
            f"- [{a['title']}]({site_url}/articles/{a['slug']}.html) ([CSV Dataset]({site_url}/datasets/{a['slug']}.csv)): {a['subtitle']}"
        )
    (DIST_DIR / "llms.txt").write_text("\n".join(llms_lines) + "\n", encoding="utf-8")

    summary = {
        "status": "ok",
        "articles_built": len(articles),
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
        ]
        + [f"articles/{a['slug']}.html" for a in articles]
        + [f"datasets/{a['slug']}.csv" for a in articles],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build_all()
