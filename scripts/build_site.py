#!/usr/bin/env python3
"""
Nodus Static Site & Quantitative Intelligence Builder
Generates enterprise-grade HTML5, Schema.org JSON-LD, sitemap.xml, robots.txt, and llms.txt
from structured quantitative datasets in content/articles/*.json.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "site_config.json"
ARTICLES_DIR = ROOT_DIR / "content" / "articles"
DIST_DIR = ROOT_DIR / "dist"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def build_css() -> str:
    return """
:root {
  --bg-page: #f8fafc;
  --bg-surface: #ffffff;
  --bg-subtle: #f1f5f9;
  --bg-dark: #0f172a;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --border-color: #e2e8f0;
  --border-strong: #cbd5e1;
  --brand-primary: #1e40af;
  --brand-accent: #2563eb;
  --brand-light: #eff6ff;
  --status-good: #059669;
  --status-good-bg: #ecfdf5;
  --status-warn: #d97706;
  --status-warn-bg: #fffbeb;
  --status-danger: #dc2626;
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

body {
  font-family: var(--font-sans);
  background-color: var(--bg-page);
  color: var(--text-primary);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}

a {
  color: var(--brand-accent);
  text-decoration: none;
  transition: color 0.15s ease;
}

a:hover {
  color: var(--brand-primary);
}

.container {
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 24px;
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
  height: 64px;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #ffffff;
  font-weight: 800;
  font-size: 1.25rem;
  letter-spacing: -0.02em;
}

.brand-logo:hover {
  color: #ffffff;
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
}

.brand-tagline {
  font-size: 0.78rem;
  color: #94a3b8;
  font-weight: 400;
  border-left: 1px solid #334155;
  padding-left: 12px;
}

.site-nav {
  display: flex;
  align-items: center;
  gap: 24px;
  font-size: 0.875rem;
}

.site-nav a {
  color: #cbd5e1;
  font-weight: 500;
}

.site-nav a:hover {
  color: #ffffff;
}

/* Compliance Bar */
.pr-banner {
  background: #f1f5f9;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-muted);
  font-size: 0.75rem;
  padding: 8px 0;
}

/* Hero Section */
.hero {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color: #ffffff;
  padding: 56px 0 48px;
  border-bottom: 1px solid #334155;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(96, 165, 250, 0.3);
  color: #93c5fd;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  padding: 4px 12px;
  border-radius: 999px;
  margin-bottom: 16px;
}

.hero h1 {
  font-size: 2.25rem;
  line-height: 1.25;
  font-weight: 800;
  letter-spacing: -0.025em;
  margin-bottom: 14px;
}

.hero p {
  color: #cbd5e1;
  font-size: 1.05rem;
  max-width: 760px;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 32px;
  padding-top: 28px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.hero-stat-item {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 14px 18px;
  border-radius: var(--radius-md);
}

.hero-stat-num {
  font-family: var(--font-mono);
  font-size: 1.35rem;
  font-weight: 700;
  color: #60a5fa;
}

.hero-stat-label {
  font-size: 0.8rem;
  color: #94a3b8;
  margin-top: 2px;
}

/* Index Cards */
.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 40px 0 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.section-title {
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.filter-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.filter-btn.active, .filter-btn:hover {
  background: var(--brand-accent);
  color: #ffffff;
  border-color: var(--brand-accent);
}

.article-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 24px;
  margin-bottom: 56px;
}

.article-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
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
  font-size: 1.15rem;
  line-height: 1.45;
  margin-bottom: 10px;
  color: var(--text-primary);
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
  font-size: 0.7rem;
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
}

/* Article Detail Layout */
.article-header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  padding: 40px 0 32px;
}

.breadcrumb {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 16px;
  font-family: var(--font-mono);
}

.article-title {
  font-size: 1.95rem;
  line-height: 1.3;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-bottom: 12px;
}

.article-subtitle {
  font-size: 1.05rem;
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--text-primary);
  margin: 4px 0;
}

.kpi-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.article-body {
  padding: 36px 0 64px;
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 28px;
  margin-bottom: 28px;
  box-shadow: var(--shadow-sm);
}

.panel-title {
  font-size: 1.2rem;
  font-weight: 700;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.panel-unit {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-muted);
  background: var(--bg-subtle);
  padding: 3px 10px;
  border-radius: 6px;
}

/* Spec Gap Chart */
.gap-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 20px;
}

.gap-item {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px 18px;
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
  font-size: 0.98rem;
}

.status-badge {
  font-family: var(--font-mono);
  font-size: 0.75rem;
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
  grid-template-columns: 220px 1fr;
  align-items: center;
  gap: 12px;
}

.bar-label {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.bar-track {
  height: 12px;
  background: var(--bg-subtle);
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill-official {
  height: 100%;
  background: #94a3b8;
  border-radius: 999px;
}

.bar-fill-measured {
  height: 100%;
  background: var(--brand-accent);
  border-radius: 999px;
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
  margin-top: 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

table.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  text-align: left;
}

table.data-table th {
  background: var(--bg-dark);
  color: #ffffff;
  font-weight: 600;
  padding: 12px 16px;
  white-space: nowrap;
  font-size: 0.8rem;
}

table.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-family: var(--font-mono);
  font-size: 0.82rem;
}

table.data-table td:first-child {
  font-family: var(--font-sans);
  font-weight: 700;
  background: #f8fafc;
}

table.data-table tr:last-child td {
  border-bottom: none;
}

table.data-table tr:hover td {
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
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--bg-subtle);
}

.prose-section p {
  color: var(--text-secondary);
  font-size: 0.96rem;
}

/* Monetization / Affiliate CTA */
.cta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
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
  font-size: 0.98rem;
  color: var(--text-primary);
}

.cta-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-accent);
  color: #ffffff !important;
  font-weight: 600;
  font-size: 0.875rem;
  padding: 10px 16px;
  border-radius: 6px;
  text-align: center;
  transition: background 0.15s;
}

.cta-btn:hover {
  background: var(--brand-primary);
}

/* FAQ & Sources */
.faq-item {
  border-bottom: 1px solid var(--border-color);
  padding: 16px 0;
}

.faq-item:last-child {
  border-bottom: none;
}

.faq-q {
  font-weight: 700;
  font-size: 0.98rem;
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
  color: #94a3b8;
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
  padding-bottom: 32px;
  border-bottom: 1px solid #1e293b;
}

.footer-links {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.footer-links a {
  color: #cbd5e1;
}

.footer-bottom {
  padding-top: 24px;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.78rem;
}

@media (max-width: 640px) {
  .brand-tagline {
    display: none;
  }
  .hero h1 {
    font-size: 1.65rem;
  }
  .article-title {
    font-size: 1.45rem;
  }
  .bar-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
"""


def render_header(config: dict[str, Any], root_prefix: str = "") -> str:
    site = config["site"]
    disclosure = config["compliance"]["pr_disclosure_text"]
    return f"""
<header class="site-header">
  <div class="container header-inner">
    <a href="{root_prefix}index.html" class="brand-logo">
      <span class="brand-mark">N</span>
      <span>{esc(site["name"])}</span>
      <span class="brand-tagline">{esc(site["jp_subtitle"])}</span>
    </a>
    <nav class="site-nav">
      <a href="{root_prefix}index.html">データベース一覧</a>
      <a href="{root_prefix}about.html">調査手法・運営ポリシー</a>
      <a href="{root_prefix}llms.txt">LLMs.txt (AI Index)</a>
    </nav>
  </div>
</header>
<div class="pr-banner">
  <div class="container">{esc(disclosure)}</div>
</div>
"""


def render_footer(config: dict[str, Any], root_prefix: str = "") -> str:
    site = config["site"]
    return f"""
<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="brand-logo" style="margin-bottom: 8px;">
          <span class="brand-mark">N</span>
          <span>{esc(site["name"])}</span>
        </div>
        <p style="max-width: 460px; color: #94a3b8;">
          {esc(site["tagline"])} — カタログ公称値とグローバル技術コミュニティの一次検証ログ・実測統計データを突合する独立系リサーチメディア。
        </p>
      </div>
      <div class="footer-links">
        <a href="{root_prefix}index.html">トップページ</a>
        <a href="{root_prefix}about.html">データ集計手法・免責事項</a>
        <a href="{root_prefix}about.html#privacy">プライバシーポリシー・広告表記</a>
        <a href="{root_prefix}sitemap.xml">Sitemap</a>
      </div>
    </div>
    <div class="footer-bottom">
      <span>&copy; {esc(site["copyright_year"])} {esc(site["organization"])}. All rights reserved.</span>
      <span>Quantitative Data Engine v1.0 (GSC Closed-Loop Enabled)</span>
    </div>
  </div>
</footer>
"""


def render_article_page(article: dict[str, Any], config: dict[str, Any]) -> str:
    site = config["site"]
    seo = article["seo"]
    canonical_url = f"{site['base_url']}/articles/{article['slug']}.html"

    # Build JSON-LD Schema (TechArticle + FAQPage)
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
                },
                "publisher": {
                    "@type": "Organization",
                    "name": site["name"],
                },
                "mainEntityOfPage": canonical_url,
            },
            {
                "@type": "FAQPage",
                "mainEntity": faq_entities,
            },
        ],
    }

    # KPI cards
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

    # Spec Gap Chart
    chart = article["spec_gap_chart"]
    max_scale = float(chart.get("max_scale", 100.0)) or 100.0
    gap_items_html = []
    for item in chart.get("items", []):
        off_pct = min(100.0, max(4.0, (float(item["official_value"]) / max_scale) * 100.0))
        meas_pct = min(100.0, max(4.0, (float(item["measured_value"]) / max_scale) * 100.0))
        status_cls = f"status-{item.get('status', 'good')}"
        status_text = {
            "good": "実測良好 / 高効率",
            "warning": "条件付き制限・乖離あり",
            "danger": "大幅乖離・高消費注意",
        }.get(item.get("status", "good"), "検証済")

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
                  <div class="bar-track"><div class="bar-fill-official" style="width: {off_pct:.1f}%;"></div></div>
                </div>
                <div class="bar-row">
                  <span class="bar-label"><strong>{esc(item["measured_label"])}</strong></span>
                  <div class="bar-track"><div class="bar-fill-measured" style="width: {meas_pct:.1f}%;"></div></div>
                </div>
              </div>
              <div class="gap-note">{esc(item["note"])}</div>
            </div>
            """
        )

    # Comparison Table
    table = article["comparison_table"]
    th_html = "".join(f"<th>{esc(h)}</th>" for h in table["headers"])
    tr_html = "".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>"
        for row in table["rows"]
    )

    # Analytical Sections
    sections_html = "".join(
        f"""
        <div class="prose-section">
          <h2>{esc(sec["heading"])}</h2>
          <p>{esc(sec["body"])}</p>
        </div>
        """
        for sec in article.get("sections", [])
    )

    # Affiliate CTA Cards
    aff_map = config.get("affiliates", {}).get("links", {})
    cta_cards = []
    for key in article.get("affiliate_keys", []):
        if key in aff_map:
            aff = aff_map[key]
            cta_cards.append(
                f"""
                <div class="cta-card">
                  <div>
                    <span class="cta-badge">{esc(aff["badge"])}</span>
                    <div class="cta-title" style="margin-top: 8px;">{esc(aff["label"])}</div>
                    <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;">提供元: {esc(aff["provider"])}</div>
                  </div>
                  <a href="{esc(aff["url"])}" target="_blank" rel="nofollow sponsored noopener" class="cta-btn">
                    最新仕様・価格を確認する &rarr;
                  </a>
                </div>
                """
            )
    cta_panel_html = ""
    if cta_cards:
        cta_panel_html = f"""
        <section class="panel">
          <div class="panel-title">
            <span>検証データに基づく推奨モデル・公式リンク</span>
            <span class="panel-unit">PR / Sponsored Links</span>
          </div>
          <div class="cta-grid">
            {''.join(cta_cards)}
          </div>
        </section>
        """

    # FAQs
    faq_html = "".join(
        f"""
        <div class="faq-item">
          <div class="faq-q">Q. {esc(f["question"])}</div>
          <div class="faq-a">{esc(f["answer"])}</div>
        </div>
        """
        for f in article.get("faqs", [])
    )

    # Sources
    sources_html = "".join(
        f"""
        <li class="source-item">
          <a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["title"])}</a>
          <span class="source-meta">Sample: {esc(s["sample_size"])} | Verified: {esc(s["verified_date"])}</span>
        </li>
        """
        for s in article.get("sources", [])
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
  <link rel="stylesheet" href="../assets/style.css">
  <script type="application/ld+json">{json.dumps(schema_ld, ensure_ascii=False)}</script>
</head>
<body>
  {render_header(config, root_prefix="../")}

  <section class="article-header">
    <div class="container">
      <div class="breadcrumb">
        <a href="../index.html">Nodus</a> &rsaquo; <span>{esc(article["category"])}</span> &rsaquo; <span>{esc(article["slug"])}</span>
      </div>
      <h1 class="article-title">{esc(article["title"])}</h1>
      <p class="article-subtitle">{esc(article["subtitle"])}</p>
      <div style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted);">
        公開日: {esc(article["published_at"])} | 最終データ更新: {esc(article["updated_at"])}
      </div>
      <div class="kpi-grid">
        {kpi_html}
      </div>
    </div>
  </section>

  <main class="container article-body">
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
        <span class="panel-unit">Quantitative Matrix</span>
      </div>
      <div class="table-wrap">
        <table class="data-table">
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
      <div style="margin-top: 8px;">
        {faq_html}
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <span>一次情報・コミュニティ検証ログ出典 (Primary Sources)</span>
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
    categories = sorted({a["category"] for a in articles})

    filter_btns = ['<button class="filter-btn active" onclick="filterCategory(\'all\', this)">すべて表示</button>']
    for cat in categories:
        filter_btns.append(
            f'<button class="filter-btn" onclick="filterCategory(\'{esc(cat)}\', this)">{esc(cat)}</button>'
        )

    cards_html = []
    for a in articles:
        m1 = a["summary_metrics"][0] if len(a["summary_metrics"]) > 0 else {"label": "データ", "value": "-"}
        m2 = a["summary_metrics"][1] if len(a["summary_metrics"]) > 1 else {"label": "指標", "value": "-"}
        cards_html.append(
            f"""
            <article class="article-card" data-category="{esc(a["category"])}">
              <div>
                <div class="card-meta">
                  <span class="category-pill">{esc(a["category"])}</span>
                  <span class="date-text">{esc(a["updated_at"])}</span>
                </div>
                <h2><a href="articles/{esc(a["slug"])}.html" style="color: inherit;">{esc(a["title"])}</a></h2>
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
                  <a href="articles/{esc(a["slug"])}.html">実測比較データを見る &rarr;</a>
                  <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">
                    {len(a["comparison_table"]["rows"])} Models Compared
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
  <link rel="canonical" href="{esc(site["base_url"])}/">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  {render_header(config, root_prefix="")}

  <section class="hero">
    <div class="container">
      <div class="hero-badge">QUANTITATIVE SPEC INTELLIGENCE // NODUS</div>
      <h1>カタログ値の裏にある「実測値」を、数字で比較する。</h1>
      <p>
        メーカー公式ページの「最大〇〇W」「高速アクセス」といった定性的な宣伝文句ではなく、グローバル開発者・ハードウェア検証コミュニティ（Reddit等）の一次計測ログを集計し、再現性のある定量比較テーブルとして公開しています。
      </p>
      <div class="hero-stats">
        <div class="hero-stat-item">
          <div class="hero-stat-num">{len(articles)} Datasets</div>
          <div class="hero-stat-label">公開中の実測比較レポート</div>
        </div>
        <div class="hero-stat-item">
          <div class="hero-stat-num">N = 187+</div>
          <div class="hero-stat-label">累計集計コミュニティ検証ログ数</div>
        </div>
        <div class="hero-stat-item">
          <div class="hero-stat-num">100% Citation</div>
          <div class="hero-stat-label">全データに一次情報スレッド出典を明記</div>
        </div>
      </div>
    </div>
  </section>

  <main class="container">
    <div class="section-header">
      <h2 class="section-title">最新の実測比較・定量検証レポート</h2>
      <div class="filter-bar">
        {''.join(filter_btns)}
      </div>
    </div>

    <div class="article-grid" id="articleGrid">
      {''.join(cards_html)}
    </div>
  </main>

  <script>
    function filterCategory(cat, btn) {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.article-card').forEach(card => {{
        if (cat === 'all' || card.dataset.category === cat) {{
          card.style.display = 'flex';
        }} else {{
          card.style.display = 'none';
        }}
      }});
    }}
  </script>

  {render_footer(config, root_prefix="")}
</body>
</html>
"""


def render_about_page(config: dict[str, Any]) -> str:
    site = config["site"]
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>調査手法・編集ポリシー・免責事項 | {esc(site["name"])}</title>
  <meta name="description" content="{esc(site['name'])}のデータ集計メソドロジー、出典明記ポリシー、ステルスマーケティング規制対応、および免責事項。">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  {render_header(config, root_prefix="")}

  <section class="article-header">
    <div class="container">
      <h1 class="article-title">データ集計手法・運営ポリシー・免責事項</h1>
      <p class="article-subtitle">{esc(site["name"])} ({esc(site["organization"])}) における定量データの抽出基準と法的コンプライアンスについて</p>
    </div>
  </section>

  <main class="container article-body">
    <section class="panel">
      <div class="prose-section">
        <h2>1. 定量データの収集・正規化メソドロジー</h2>
        <p>
          当サイト（{esc(site["name"])}）は、製品やクラウドサービスの「メーカー公称値（カタログスペック）」と「実運用環境における実測パフォーマンス」の乖離を可視化することを目的としたデータインデックスです。英語圏の技術コミュニティ（Redditの各専門Subreddit、Hacker News、GitHub Discussions等）で公開されている有志の計測ログから、測定条件（室温、負荷時間、バージョン等）が明記された数値データのみを抽出し、中央値および分散を算出して独自の比較表・チャートを再構築しています。
        </p>
      </div>
      <div class="prose-section">
        <h2>2. 著作権および一次情報へのリスペクト</h2>
        <p>
          当サイトは日本の著作権法第30条の4（情報解析目的の利用）および国際的なフェアユース原則を遵守しています。第三者が撮影した画像や長文コメントの無断転載・直訳は一切行わず、客観的な「事実・計測数値」のみを統計処理した上で、すべての記事末尾に一次情報源（スレッドURL）への参照リンクを明記しています。
        </p>
      </div>
      <div class="prose-section" id="privacy">
        <h2>3. 広告配信（アフィリエイトプログラム）および景品表示法への対応</h2>
        <p>
          当サイトは、Amazon.co.jpを宣伝しリンクすることによってサイトが紹介料を獲得できる手段を提供することを目的に設定されたアフィリエイトプログラムである「Amazonアソシエイト・プログラム」をはじめ、各種ASPおよびSaaSパートナープログラムに参加しています。すべてのページ上部にプロモーションを含む旨を明記しており、広告報酬の有無によって実測データの数値を改変することはありません。
        </p>
      </div>
      <div class="prose-section">
        <h2>4. 免責事項</h2>
        <p>
          掲載されている実測値はコミュニティの特定環境下における計測統計であり、すべての個体やアップデート後の環境で同一の結果を保証するものではありません。製品購入やサービス契約の最終判断は、各メーカーの最新公式仕様をご確認の上、ご自身の責任において行っていただくようお願いいたします。
        </p>
      </div>
    </section>
  </main>

  {render_footer(config, root_prefix="")}
</body>
</html>
"""


def build_all() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    site_url = config["site"]["base_url"].rstrip("/")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    (DIST_DIR / "assets").mkdir(parents=True, exist_ok=True)
    (DIST_DIR / "articles").mkdir(parents=True, exist_ok=True)

    # Write CSS
    (DIST_DIR / "assets" / "style.css").write_text(build_css(), encoding="utf-8")

    # Load and sort articles
    articles: list[dict[str, Any]] = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        articles.append(load_json(path))
    articles.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    # Render each article
    for article in articles:
        out_path = DIST_DIR / "articles" / f"{article['slug']}.html"
        out_path.write_text(render_article_page(article, config), encoding="utf-8")

    # Render index & about
    (DIST_DIR / "index.html").write_text(render_index_page(articles, config), encoding="utf-8")
    (DIST_DIR / "about.html").write_text(render_about_page(config), encoding="utf-8")

    # Generate sitemap.xml
    today = datetime.now().strftime("%Y-%m-%d")
    urls = [
        f"  <url><loc>{site_url}/index.html</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>",
        f"  <url><loc>{site_url}/about.html</loc><lastmod>{today}</lastmod><priority>0.5</priority></url>",
    ]
    for a in articles:
        urls.append(
            f"  <url><loc>{site_url}/articles/{a['slug']}.html</loc><lastmod>{a['updated_at']}</lastmod><priority>0.9</priority></url>"
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
        llms_lines.append(f"- [{a['title']}]({site_url}/articles/{a['slug']}.html): {a['subtitle']}")
    (DIST_DIR / "llms.txt").write_text("\n".join(llms_lines) + "\n", encoding="utf-8")

    summary = {
        "status": "ok",
        "articles_built": len(articles),
        "output_dir": str(DIST_DIR),
        "files": ["index.html", "about.html", "sitemap.xml", "robots.txt", "llms.txt"]
        + [f"articles/{a['slug']}.html" for a in articles],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build_all()
