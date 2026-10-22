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

    if article.get("kind") == "guide":
        if article.get("origin") != "editorial" or article.get("sample_size_n") != 0:
            raise ValueError(f"Article {slug}: guides must be editorial with zero measured samples")
        if not article.get("sections") or not article.get("comparison_table", {}).get("rows"):
            raise ValueError(f"Article {slug}: guides require prose and a comparison table")
        for section in article["sections"]:
            for index in section.get("source_indices", []):
                if type(index) is not int or not 0 <= index < len(article["sources"]):
                    raise ValueError(f"Article {slug}: invalid section source index")
        for related in article.get("related_articles", []):
            validate_slug(related["slug"])
            if not (ARTICLES_DIR / f"{related['slug']}.json").exists():
                raise ValueError(f"Article {slug}: missing related article {related['slug']}")
        return

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
    return (ROOT_DIR / "scripts" / "editorial.css").read_text(encoding="utf-8")


def build_js() -> str:
    return """/* Nodus Quantitative Interactive Controls (CSP-safe external script) */
(function () {
  "use strict";

  /* Self-traffic / Admin analytics exclusion */
  try {
    var search = window.location.search || "";
    if (search.indexOf("admin=1") !== -1 || search.indexOf("admin=true") !== -1 || search.indexOf("preview=1") !== -1) {
      localStorage.setItem("nodus_admin_mode", "1");
    } else if (search.indexOf("admin=0") !== -1) {
      localStorage.removeItem("nodus_admin_mode");
    }

    var isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    if (isLocal || localStorage.getItem("nodus_admin_mode") === "1") {
      if (typeof console !== "undefined" && console.info) {
        console.info("[Nodus] Admin mode: Analytics beacon suppressed.");
      }
      if (navigator && navigator.sendBeacon) {
        var rawSendBeacon = navigator.sendBeacon.bind(navigator);
        navigator.sendBeacon = function (url, data) {
          if (typeof url === "string" && url.indexOf("cloudflareinsights.com") !== -1) {
            return true;
          }
          return rawSendBeacon(url, data);
        };
      }
      if (window.fetch) {
        var rawFetch = window.fetch.bind(window);
        window.fetch = function (input, init) {
          var url = typeof input === "string" ? input : (input && input.url ? input.url : "");
          if (typeof url === "string" && url.indexOf("cloudflareinsights.com") !== -1) {
            return Promise.resolve(new Response("", { status: 204, statusText: "No Content" }));
          }
          return rawFetch(input, init);
        };
      }
      if (window.XMLHttpRequest) {
        var rawOpen = window.XMLHttpRequest.prototype.open;
        window.XMLHttpRequest.prototype.open = function (method, url) {
          if (typeof url === "string" && url.indexOf("cloudflareinsights.com") !== -1) {
            this.send = function () {};
            return;
          }
          return rawOpen.apply(this, arguments);
        };
      }
    }
  } catch (e) {
    /* Ignore storage/sandbox restrictions */
  }

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
        var searchAttr = card.getAttribute("data-search") || "";
        var textMatch = !query || (card.textContent + " " + searchAttr).toLowerCase().indexOf(query) !== -1;
        if (catMatch && textMatch) {
          card.removeAttribute("hidden");
        } else {
          card.setAttribute("hidden", "hidden");
        }
      });
      var empty = document.getElementById("searchEmpty");
      if (empty) empty.hidden = Array.prototype.some.call(cards, function (card) { return !card.hidden; });
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
        var btn = th.querySelector(".th-sort-btn");
        if (!btn) return;
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
    <a href="{root_prefix}" class="brand-logo">
      <span class="brand-mark" aria-hidden="true">N</span>
      <span>{esc(site["name"])}</span>
      <span class="brand-tagline">買う、作る、その前に。</span>
    </a>
    <nav class="site-nav" aria-label="グローバルナビゲーション">
      <a href="{root_prefix}">記事を読む</a>
      <a href="{root_prefix}about">Nodusについて</a>
      <a href="{root_prefix}about#privacy">ポリシー</a>
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
          電子工作、AI、サーバー。買うか、作るか、借りるか。費用と手間、使い道をそろえて考える技術ノート。
        </p>
        <p class="footer-amazon-notice">{esc(footer_notice)}</p>
      </div>
      <div class="footer-links">
        <a href="{root_prefix}">記事一覧</a>
        <a href="{root_prefix}about">検証手法・免責事項</a>
        <a href="{root_prefix}about#privacy">プライバシーポリシー</a>
        <a href="{root_prefix}about#contact">運営者情報・訂正ポリシー</a>
        <a href="{root_prefix}sitemap.xml">Sitemap</a>
        <a href="{root_prefix}llms.txt">LLMs.txt</a>
      </div>
    </div>
    <div class="footer-bottom">
      <span>&copy; {esc(site["copyright_year"])} {esc(site["organization"])}. All rights reserved.</span>
      <span>道具を選ぶ。仕組みを知る。</span>
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
    if article.get("kind") == "guide":
        return render_guide(article, config, all_articles)
    site = config["site"]
    seo = article["seo"]
    slug = validate_slug(article["slug"])
    base_url = validate_url(site["base_url"]).rstrip("/")
    canonical_url = f"{base_url}/articles/{slug}"
    data_updated_at = article.get("data_updated_at", article["updated_at"])
    methodology_note = article.get("methodology_note", "")
    origin = article.get("origin", "community")
    is_self = origin in {"first_party", "hybrid"}
    origin_badge_cls = "origin-self" if is_self else "origin-community"
    origin_text = article.get(
        "origin_label",
        "🔬 独自実機・AIチャット検証" if is_self else "📊 一次検証ログ定量調査",
    )
    origin_text = origin_text.lstrip("🔬🧪📊 ")
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
                    "url": f"{base_url}/about",
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
                    "url": f"{base_url}/about",
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
                        "item": f"{base_url}/",
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
                  <a href="{esc(r_slug)}"><strong>{esc(r["title"])}</strong></a>
                  <span class="source-meta">{esc(r_m1["label"])}: {esc(r_m1["value"])} (N={int(r.get("sample_size_n", 0))})</span>
                </li>
                """
            )
        related_section_html = f"""
        <section id="sec-related" class="article-section" aria-label="関連する検証レポート">
          <h2 class="section-h2"><span>あわせて読みたい</span></h2>
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
          <span>{table_num}. 条件別の比較表</span>
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
        <a href="../">Nodus</a> &rsaquo; <span>{esc(article["category"])}</span>
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
          <span>この記事の要点</span>
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
          <span>結果をどう読むか</span>
        </h2>
        {sections_html}
      </section>

      {cta_section_html}

      <section id="sec-faq" class="article-section">
        <h2 class="section-h2"><span>よくある疑問</span></h2>
        <div class="faq-list">
          {faq_html}
        </div>
      </section>

      <section id="sec-sources" class="article-section">
        <h2 class="section-h2">
          <span>検証条件と出典</span>
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
          <li><a href="#sec-tldr">この記事の要点</a></li>
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
    canonical_url = f"{base_url}/articles/{slug}"
    csv_url = f"{base_url}/datasets/{slug}.csv"
    has_raw_log = article.get("kind") != "guide" and (RAW_LOGS_DIR / f"{slug}.json").exists()
    data_updated = article.get("data_updated_at", article["updated_at"])

    lines = [
        f"# {article['title']}",
        "",
        f"> {article['subtitle']}",
        "",
        f"- **Canonical URL**: {canonical_url}",
        f"- **{'CSV Comparison Table' if article.get('kind') == 'guide' else 'CSV Dataset'}**: {csv_url}",
    ]
    if has_raw_log:
        lines.append(f"- **Raw Verification Log (JSON)**: {base_url}/logs/{slug}.json")
    if article.get("revision_note"):
        lines.extend(["", "## 訂正について", article["revision_note"], "", "---", ""])
    lines.extend(
        [
            f"- **Category**: {article['category']}",
            ("- **Article type**: 選び方・公式資料から整理（実測なし）" if article.get("kind") == "guide" else f"- **Sample Size (N)**: {int(article.get('sample_size_n', 0))}"),
            f"- **Data Updated**: {data_updated}",
            "",
            "## 結論・実測サマリー (TL;DR)",
        ]
    )
    for b in _build_tldr_bullets(article):
        lines.append(f"- {b}")

    lines.append("")
    if article.get("summary_metrics"):
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
                "## 条件別の比較表",
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
        for source_index in sec.get("source_indices", []):
            source = article["sources"][source_index]
            lines.append(f"参照: [{source['title']}]({validate_url(source['url'])})")
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

    if article.get("kind") == "guide":
        lines = [line.replace("結論・実測サマリー (TL;DR)", "選び方の要点").replace("主要実測指標 (Key Metrics)", "判断の軸").replace("条件別の比較表", "選択肢の比較表").replace("検証環境・集計メソドロジー", "記事の範囲") for line in lines]
    lines.extend(["", "## 参考資料"] + [f"- [{src['title']}]({validate_url(src['url'])})" for src in article.get("sources", [])])
    if article.get("related_articles"):
        lines.extend(["", "## 次に考えたいこと"] + [f"- [{r['title']}]({base_url}/articles/{validate_slug(r['slug'])})" for r in article["related_articles"]])
    return "\n".join(lines).strip() + "\n"


CATEGORY_LABELS = {
    "Hardware & Power Electronics": "道具と電子工作",
    "Cloud & AI Infrastructure": "AIとサーバー",
    "Software & SaaS Economics": "サービスと費用",
}


def category_label(category):
    return CATEGORY_LABELS.get(category, category)


def illustration(kind):
    # Code-native diagrams illustrate the subject without suggesting a product photograph.
    drawings = {
        "esp": '<rect x="95" y="18" width="110" height="120" rx="3"/><rect x="120" y="55" width="60" height="48"/><path d="M120 40h60m-60 8h60M110 67H75m35 15H75m35 15H75m115-30h35m-35 15h35m-35 15h35M130 110v17m20-17v17m20-17v17"/><circle cx="106" cy="28" r="3"/><circle cx="194" cy="128" r="3"/>',
        "ai": '<rect x="25" y="45" width="70" height="70"/><path d="M35 63h50m-50 15h50m-50 15h28M95 80h30m50 0h30"/><circle cx="150" cy="80" r="25"/><rect x="205" y="45" width="70" height="70"/><path d="M220 65h40m-40 15h40m-40 15h20"/>',
        "diy": '<path d="M40 32h65v96H40zM55 48h35m-35 14h35M160 52h92v65h-92zM175 67h62m-62 15h62M122 80h22m-11-11v22"/><circle cx="72" cy="105" r="9"/>',
    }
    return '<svg viewBox="0 0 300 160" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">' + drawings[kind] + '</svg>'


def render_index(articles, config):
    site = config["site"]
    featured = [a for a in articles if a.get("kind") == "guide" and "feature_order" in a]
    featured.sort(key=lambda a: a.get("feature_order", 99))
    features = []
    for i, a in enumerate(featured[:3], 1):
        features.append(f'''<article class="feature-story">
          <a href="articles/{esc(a['slug'])}" tabindex="-1" aria-hidden="true"><div class="feature-art {esc(a['illustration'])}">{illustration(a['illustration'])}</div></a>
          <div class="feature-number">0{i} / {esc(category_label(a['category']))}</div>
          <h3><a href="articles/{esc(a['slug'])}">{esc(a.get('display_title', a['title']))}</a></h3>
          <p>{esc(a['subtitle'])}</p>
          <a class="feature-link" href="articles/{esc(a['slug'])}">選び方を読む <span aria-hidden="true">↗</span></a>
        </article>''')

    spotlight_slugs = [
        "gemini-4-argon-google-ai-pro-ultra",
        "antigravity-quota-5-hour-weekly-ai-credits-guide",
        "ollama-context-length-vram-default-memory-guide",
        "deepseek-v4-1-flash-1017-kv-cache-encoding-guide",
    ]
    slug_map = {a["slug"]: a for a in articles}
    spotlight_items = []
    for s_slug in spotlight_slugs:
        sa = slug_map.get(s_slug)
        if not sa:
            continue
        spotlight_items.append(
            f'''<a class="spotlight-chip" href="articles/{esc(sa['slug'])}">
              <span class="spotlight-cat">{esc(category_label(sa['category']))}</span>
              <strong class="spotlight-title">{esc(sa.get('display_title', sa['title']))}</strong>
            </a>'''
        )
    spotlight_html = (
        f'<div class="spotlight-bar" aria-label="注目の最新トピック"><div class="spotlight-label">注目のトピック</div><div class="spotlight-grid">{"".join(spotlight_items)}</div></div>'
        if spotlight_items
        else ""
    )

    buttons = [f'<button type="button" class="filter-btn" data-filter="all" aria-pressed="true">すべて ({len(articles)})</button>']
    for c in sorted({a['category'] for a in articles}):
        cat_count = sum(1 for a in articles if a['category'] == c)
        buttons.append(f'<button type="button" class="filter-btn" data-filter="{esc(c)}" aria-pressed="false">{esc(category_label(c))} ({cat_count})</button>')
    cards = []
    for a in articles:
        label = '選び方・公式資料から整理' if a.get('kind') == 'guide' else ('独自検証' if a.get('origin') in {'first_party', 'hybrid'} else '公開ログの調査')
        search_terms = " ".join(
            [
                str(a.get("title", "")),
                str(a.get("display_title", "")),
                " ".join(str(t) for t in a.get("tags", [])),
                " ".join(str(k) for k in a.get("seo", {}).get("target_keywords", [])),
            ]
        )
        tag_pills = "".join(f'<span class="tag-chip">#{esc(t)}</span>' for t in a.get("tags", [])[:4])
        cards.append(f'''<article class="article-card" data-category="{esc(a['category'])}" data-origin="{esc(a.get('origin', 'community'))}" data-search="{esc(search_terms)}">
          <div class="card-meta"><span class="category-pill">{esc(category_label(a['category']))}</span><span class="origin-badge">{label}</span><time class="date-text" datetime="{esc(a['updated_at'])}">{esc(a['updated_at'])}</time></div>
          <div class="card-content">
            <h2><a class="card-title-link" href="articles/{esc(a['slug'])}">{esc(a.get('display_title', a['title']))}</a></h2>
            <p>{esc(a['subtitle'])}</p>
            <div class="card-footer-row"><div class="article-tags-row">{tag_pills}</div><span class="card-read-more" aria-hidden="true">ノートを読む &rarr;</span></div>
          </div></article>''')
    description = '電子工作、AI、サーバー。買うか、作るか、借りるかを、費用と使い道から考える技術ノート。'
    return f'''<!DOCTYPE html><html lang="ja"><head>
      <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{esc(site['name'])} — 電子工作・AI・サーバーの選び方</title><meta name="description" content="{description}">
      <link rel="canonical" href="{esc(site['base_url'])}/"><meta property="og:title" content="Nodus — 買う、作る、その前に。">
      <meta property="og:description" content="{description}"><meta property="og:type" content="website"><meta property="og:url" content="{esc(site['base_url'])}/">
      <link rel="alternate" type="application/atom+xml" title="Nodus Feed" href="feed.xml"><link rel="stylesheet" href="assets/style.css">
      </head><body>{render_header(config)}
      <main id="main-content">
        <section class="editorial-intro"><div class="container intro-inner"><div class="intro-copy">
          <div class="intro-kicker">NODUS / NOTES ON MAKING &amp; CHOOSING</div>
          <h1>買う、作る、<br>その前に。</h1>
          <p>安いボードを買って、結局高くついた。<br>便利なサブスク。でも、自分で動かしたらどうだろう。<br>そんな迷いを、費用と使い道からほどく技術ノートです。</p>
        </div><div class="intro-note"><strong>値札の先まで、考える。</strong>部品代だけでなく、電気代、作る時間、使い続ける手間まで。自分に合う選択のために、条件をそろえて比べます。<p>手持ちのMacから試したい人へ。<a href="articles/local-llm-hardware-mac-unified-memory-vs-rtx-gpu-tokens-per-watt">MacでローカルLLMを使うには</a>で、必要メモリと機器選びを整理しました。</p></div></div></section>
        <div class="container"><section class="featured" aria-labelledby="featured-title">
          <div class="featured-heading"><h2 id="featured-title">いま、考えたいこと</h2><span>まずは、この3つから</span></div>
          <div class="feature-grid">{''.join(features)}</div>{spotlight_html}</section>
          <section aria-labelledby="archive-title"><div class="archive-heading"><h2 id="archive-title">記事を読む</h2><span>{len(articles)} articles / 比較と検証のノート</span></div>
          <div class="controls-wrap"><div class="filter-bar" role="group" aria-label="記事のカテゴリ">{''.join(buttons)}</div>
          <div><label for="datasetSearch" class="category-pill">記事検索 </label><input type="search" id="datasetSearch" class="search-input" placeholder="ESP32、電気代、ローカルLLM…"></div></div>
          <div class="article-grid" id="articleGrid">{''.join(cards)}<p class="empty-state" id="searchEmpty" role="status" hidden>該当する記事がありません。別の言葉で検索してください。</p></div></section>
        </div></main>{render_footer(config)}</body></html>'''


def render_guide(article, config, all_articles=None):
    a = article
    site = config['site']
    base_url = validate_url(site['base_url']).rstrip('/')
    url = base_url + '/articles/' + a['slug']
    graph_nodes = [
        {
            "@type": "TechArticle",
            "headline": a['title'],
            "description": a['seo']['meta_description'],
            "datePublished": a['published_at'],
            "dateModified": a['updated_at'],
            "inLanguage": "ja",
            "keywords": ", ".join(a.get("tags", [])),
            "mainEntityOfPage": url,
            "citation": [validate_url(s['url']) for s in a['sources']],
            "author": {"@type": "Organization", "name": site['organization'], "url": f"{base_url}/about"},
            "publisher": {"@type": "Organization", "name": site['name'], "url": f"{base_url}/"},
            "speakable": {"@type": "SpeakableSpecification", "cssSelector": ["#sec-tldr", "#sec-faq"]},
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": site['name'], "item": f"{base_url}/"},
                {"@type": "ListItem", "position": 2, "name": category_label(a['category']), "item": f"{base_url}/"},
                {"@type": "ListItem", "position": 3, "name": a['title'], "item": url},
            ],
        },
    ]
    if a.get("faqs"):
        graph_nodes.append(
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": f["answer"]},
                    }
                    for f in a["faqs"]
                ],
            }
        )
    schema = {"@context": "https://schema.org", "@graph": graph_nodes}
    headers = ''.join(
        f'<th scope="col" aria-sort="none"><button type="button" class="th-sort-btn"><span>{esc(h)}</span><span aria-hidden="true">↕</span></button></th>'
        for h in a['comparison_table']['headers']
    )
    tr_rows = []
    for r in a['comparison_table']['rows']:
        if not r:
            continue
        first_cell = f'<th scope="row">{esc(r[0])}</th>'
        rest_cells = []
        for c in r[1:]:
            c_str = str(c)
            cls_attr = ' class="num-cell"' if _looks_numeric_cell(c_str) else ""
            sort_val = _normalize_sort_value(c_str)
            sort_attr = f' data-sort-value="{esc(sort_val)}"' if sort_val else ""
            rest_cells.append(f"<td{cls_attr}{sort_attr}>{esc(c_str)}</td>")
        tr_rows.append(f"<tr>{first_cell}{''.join(rest_cells)}</tr>")
    rows = ''.join(tr_rows)
    sections = ''
    for i, section in enumerate(a['sections']):
        refs = ''.join(f'<a href="{esc(validate_url(a["sources"][n]["url"]))}" target="_blank" rel="noopener noreferrer">{esc(a["sources"][n]["title"])}</a> ' for n in section.get('source_indices', []))
        sections += f'<section class="prose-section" id="part-{i}"><h2 class="section-h2">{esc(section["heading"])}</h2><p>{esc(section["body"])}</p>' + (f'<p class="source-meta">参照: {refs}</p>' if refs else '') + '</section>'
    toc = ''.join(f'<li><a href="#part-{i}">{esc(s["heading"])}</a></li>' for i, s in enumerate(a['sections']))
    sources = ''.join(f'<li class="source-item"><a href="{esc(validate_url(s["url"]))}" target="_blank" rel="noopener noreferrer">{esc(s["title"])}</a><span class="source-meta">確認日: {esc(s["verified_date"])} / {esc(s.get("scope", "公式資料の参照"))}</span></li>' for s in a['sources'])
    bullets = ''.join(f'<li>{esc(b)}</li>' for b in a['tldr'])
    tags_html = ''.join(f'<span class="tag-chip">#{esc(t)}</span>' for t in a.get('tags', []))
    correction = ''
    if a.get('revision_note'):
        correction = f'<aside class="methodology-box" aria-label="記事の訂正"><strong>2026-10-13 内容を見直しました</strong><p>{esc(a["revision_note"])}</p></aside>'
    faq_section = ''
    faq_toc = ''
    if a.get('faqs'):
        faq_items = ''.join(
            f'<div class="faq-item"><h3 class="faq-q">Q. {esc(f["question"])}</h3><p class="faq-a">{esc(f["answer"])}</p></div>'
            for f in a['faqs']
        )
        faq_section = f'<section id="sec-faq" class="article-section"><h2 class="section-h2"><span>よくある疑問</span></h2><div class="faq-list">{faq_items}</div></section>'
        faq_toc = '<li><a href="#sec-faq">よくある疑問</a></li>'
    related = ''
    related_toc = ''
    if a.get('related_articles'):
        art_by_slug = {item['slug']: item for item in (all_articles or [])}
        rel_items = []
        for r in a['related_articles']:
            r_slug = validate_slug(r['slug'])
            target_art = art_by_slug.get(r_slug)
            r_title = (target_art.get('display_title') or target_art['title']) if target_art else r['title']
            r_sub = target_art['subtitle'] if target_art else ''
            r_cat = category_label(target_art['category']) if target_art else ''
            meta_line = f'<span class="source-meta">{esc(r_cat)} — {esc(r_sub)}</span>' if r_sub else ''
            rel_items.append(f'<li class="source-item"><a href="{esc(r_slug)}"><strong>{esc(r_title)}</strong></a>{meta_line}</li>')
        related = f'<section id="sec-related" class="article-section"><h2 class="section-h2"><span>次に考えたいこと</span></h2><ul class="source-list">{"".join(rel_items)}</ul></section>'
        related_toc = '<li><a href="#sec-related">次に考えたいこと</a></li>'
    return f'''<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{esc(a['seo']['meta_title'])}</title><meta name="description" content="{esc(a['seo']['meta_description'])}"><link rel="canonical" href="{esc(url)}">
      <meta property="og:title" content="{esc(a['seo']['meta_title'])}"><meta property="og:description" content="{esc(a['seo']['meta_description'])}"><meta property="og:type" content="article"><meta property="og:url" content="{esc(url)}"><meta property="og:site_name" content="{esc(site['name'])}"><meta name="twitter:card" content="summary_large_image">
      <link rel="stylesheet" href="../assets/style.css"><link rel="alternate" type="text/markdown" href="{esc(a['slug'])}.md" title="Markdown版"><link rel="alternate" type="application/atom+xml" href="../feed.xml" title="Nodus Feed">
      <script type="application/ld+json">{safe_json_ld(schema)}</script></head><body>{render_header(config, '../')}
      <div class="container article-layout"><main id="main-content" class="article-sheet">
      <nav class="breadcrumb" aria-label="パンくずリスト"><a href="../">Nodus</a> / {esc(category_label(a['category']))}</nav>
      <div class="article-meta-top"><span class="origin-badge">選び方 / 公式資料から整理</span><span class="category-pill">{esc(category_label(a['category']))}</span></div>
      <h1 class="article-title">{esc(a['title'])}</h1><p class="article-subtitle">{esc(a['subtitle'])}</p>
      <div class="article-tags-row">{tags_html}</div>
      <div class="article-timestamps"><span>公開 <time datetime="{esc(a['published_at'])}">{esc(a['published_at'])}</time></span><span>更新 <time datetime="{esc(a['updated_at'])}">{esc(a['updated_at'])}</time></span><span>{esc(a.get('evidence_notice', '実機テスト・実売価格調査は未実施'))}</span></div>
      {correction}
      <section class="tldr-box" id="sec-tldr"><h2 class="tldr-title">先に、選び方の要点</h2><ul class="tldr-list">{bullets}</ul></section>
      <section id="sec-table"><h2 class="section-h2"><span>選択肢を並べる</span><span class="section-subnote">列見出しクリックで並び替え可能</span></h2><p class="source-meta">表が画面に収まらない場合は、横にスクロールして読めます。</p><div class="table-wrap"><table class="data-table"><caption>{esc(a['table_caption'])}</caption><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></div><a class="csv-btn" href="../datasets/{esc(a['slug'])}.csv" download>比較表をCSVで保存</a></section>
      {sections}{faq_section}<section id="sec-sources" class="article-section"><h2 class="section-h2">参考資料とこの記事の範囲</h2><p class="methodology-box">{esc(a['methodology_note'])}</p><ul class="source-list">{sources}</ul></section>{related}
      </main><aside class="article-sidebar" aria-label="記事の目次"><div class="sidebar-box"><div class="sidebar-title">このノートの目次</div><ul class="toc-list"><li><a href="#sec-tldr">選び方の要点</a></li><li><a href="#sec-table">比較表</a></li>{toc}{faq_toc}<li><a href="#sec-sources">参考資料</a></li>{related_toc}</ul></div></aside></div>{render_footer(config, '../')}</body></html>'''



def render_index_page(articles: list[dict[str, Any]], config: dict[str, Any]) -> str:
    return render_index(articles, config)


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
  <link rel="canonical" href="{esc(base_url)}/about">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  {render_header(config, root_prefix="")}

  <div class="container article-layout">
    <main id="main-content" class="article-sheet">
      <h1 class="article-title">Nodusについて</h1>
      <p class="article-subtitle">記事の根拠、訂正、広告とプライバシーについて</p>

      <div class="prose-section">
        <h3>買う、作る、その前に。</h3>
        <p>電子工作、AI、サーバーについて、費用と使い道から選択を考える技術ノートです。「選び方」は公式資料と編集上の判断を整理した記事であり、実機テストや実売価格調査を行っていない場合は明記します。仮定に基づく計算例と測定結果を区別し、検証記事では条件と出典を示します。</p>
      </div>

      <div class="prose-section">
        <h3>1. 公式仕様、編集上の判断、実測を分ける</h3>
        <p>
          公式資料は機能や公称仕様の確認に使い、個別製品の実測や順位の証拠とは区別します。比較表には選択肢と確認事項をまとめ、仮定の計算には前提を添えます。今後、独自の実測記事を掲載する場合は、個別の記録、測定条件、採用したデータと集計手順を示します。検索結果ページや抜粋だけを、集計全体の根拠にはしません。
        </p>
      </div>
      <div class="prose-section">
        <h3>2026-10-13 既存12記事の訂正</h3>
        <p>既存12記事の根拠を見直したところ、掲載した件数・中央値・効果率を、保存資料と出典から再現確認できませんでした。該当する数値とランキングを撤回し、公式資料と判断手順に基づく「選び方」へ改訂しました。各記事の冒頭に訂正理由を記載しています。旧集計ファイルの公開URLには取り下げ案内を置き、未確認の数値が引用され続けないようにしました。</p>
      </div>
      <div class="prose-section">
        <h3>2. 知的財産権の尊重および一次情報源への参照方針</h3>
        <p>
          参照した公式資料や個別の技術報告は、記事内と末尾から確認できるようにします。資料が裏付ける範囲も明記し、メーカーの機能説明を独自実測として扱いません。他者の文章、画像、図表を無断転載せず、比較の考え方や判断手順は当サイトの言葉で説明します。
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
        <h3>アクセス解析</h3><p>ページ閲覧と表示性能の統計にCloudflare Web Analyticsを利用します。<a href="https://developers.cloudflare.com/web-analytics/data-metrics/data-origin-and-collection/" target="_blank" rel="noopener noreferrer">計測の仕組み</a>はCloudflareの公式説明をご覧ください。</p>
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
      <h1 class="article-title">404 — ページが見つかりません</h1>
      <p class="article-subtitle">URLが変更されたか、アーカイブされた可能性があります。トップページの記事一覧からお探しください。</p>
      <p><a href="/" class="cta-btn">記事一覧へ戻る &rarr;</a></p>
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
        url = f"{base_url}/articles/{slug}"
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
  Content-Security-Policy: default-src 'self'; script-src 'self' https://static.cloudflareinsights.com; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://cloudflareinsights.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'

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
        article_html = render_article_page(article, config, articles)
        out_path.write_text(re.sub(r"^[ \t]+$", "", article_html, flags=re.MULTILINE), encoding="utf-8")

        md_content = render_article_markdown(article, config)
        md_path = (articles_out_dir / f"{slug}.md").resolve()
        md_path.write_text(md_content, encoding="utf-8")
        markdown_corpus_blocks.append(md_content)

        csv_path = (datasets_out_dir / f"{slug}.csv").resolve()
        csv_path.write_text(build_article_csv(article), encoding="utf-8")

        raw_log_src = RAW_LOGS_DIR / f"{slug}.json"
        if raw_log_src.exists():
            if article.get("kind") == "guide":
                raw_obj = {
                    "status": "withdrawn_unverified",
                    "article_url": f"{site_url}/articles/{slug}",
                    "reviewed_at": article["data_updated_at"],
                    "notice": "旧集計値は母集団と集計手順を再現確認できないため公開を取り下げました。元ファイルは編集用に保存しています。",
                }
            else:
                raw_obj = load_json(raw_log_src)
            log_out_path = (logs_out_dir / f"{slug}.json").resolve()
            log_out_path.write_text(json.dumps(raw_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if article.get("kind") != "guide":
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
        f"  <url><loc>{esc(site_url)}/about</loc><lastmod>{esc(latest_date)}</lastmod><priority>0.5</priority></url>",
    ]
    for a in articles:
        urls.append(
            f"  <url><loc>{esc(site_url)}/articles/{esc(a['slug'])}</loc><lastmod>{esc(a['updated_at'])}</lastmod><priority>0.9</priority></url>"
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
        "## Articles & Comparison Tables",
    ]
    for a in articles:
        slug = a["slug"]
        n_val = int(a.get("sample_size_n", 0))
        kpi_summary = " / ".join(
            f"{m['label']}: {m['value']}" for m in a.get("summary_metrics", [])[:3] if m.get("value")
        )
        raw_suffix = (
            f" | [Raw Log JSON]({site_url}/logs/{slug}.json)"
            if a.get("kind") != "guide" and (RAW_LOGS_DIR / f"{slug}.json").exists()
            else ""
        )
        llms_lines.append(
            f"- [{a['title']}]({site_url}/articles/{slug}) "
            f"([Markdown]({site_url}/articles/{slug}.md) | [{'CSV Comparison Table' if a.get('kind') == 'guide' else 'CSV Dataset'}]({site_url}/datasets/{slug}.csv){raw_suffix}): "
            f"{'公式資料に基づく選び方・実測なし' if a.get('kind') == 'guide' else f'N={n_val}'}{f' | {kpi_summary}' if kpi_summary else ''} — {a['subtitle']}"
        )
    (DIST_DIR / "llms.txt").write_text("\n".join(llms_lines) + "\n", encoding="utf-8")

    llms_full_header = (
        f"# {config['site']['name']} — Complete Article Corpus (llms-full.txt)\n\n"
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
