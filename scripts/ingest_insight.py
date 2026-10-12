#!/usr/bin/env python3
"""
Nodus First-Party Insight & Chat Experiment Ingestor
Turns hands-on experiments, local benchmark logs, and AI chat session insights
into structured, searchable verification articles in content/articles/*.json.

Capabilities:
1. --scan-chats : Scans local AI chat transcripts for empirical numbers, commands,
                  and technical investigations not yet covered on Qiita/Zenn/Reddit.
2. --compile <path> : Compiles a field-note JSON (from data/field_notes/) into a
                      validated Nodus article JSON with `origin: "first_party"` or `"hybrid"`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from build_site import ARTICLES_DIR, CONFIG_PATH, ROOT_DIR, load_json, validate_article
from miner import QUANT_PATTERN, normalize_measurements

FIELD_NOTES_DIR = ROOT_DIR / "data" / "field_notes"
DEFAULT_BRAIN_DIR = Path.home() / ".gemini" / "antigravity" / "brain"


def scan_chat_transcripts(brain_dir: Path = DEFAULT_BRAIN_DIR, max_sessions: int = 20) -> dict[str, Any]:
    """Scan local Antigravity conversation transcripts for quantitative findings & experiments."""
    FIELD_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    sessions_found: list[dict[str, Any]] = []

    if brain_dir.exists():
        transcript_paths = sorted(
            brain_dir.glob("*/.system_generated/logs/transcript.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:max_sessions]

        for t_path in transcript_paths:
            conv_id = t_path.parent.parent.parent.name
            user_prompts: list[str] = []
            quant_hits: list[str] = []
            try:
                with t_path.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        content = str(obj.get("content") or "")
                        if obj.get("type") == "USER_INPUT" and content:
                            clean_q = re.sub(r"<[^>]+>", " ", content).strip()
                            if len(clean_q) >= 12:
                                user_prompts.append(clean_q[:160])
                        matches = QUANT_PATTERN.findall(content)
                        if matches:
                            quant_hits.extend(matches)
            except Exception:
                continue

            norm_nums = normalize_measurements(quant_hits)
            if user_prompts and len(norm_nums) >= 2:
                sessions_found.append(
                    {
                        "conversation_id": conv_id,
                        "updated_at": datetime.fromtimestamp(t_path.stat().st_mtime).strftime("%Y-%m-%d"),
                        "topic_seeds": user_prompts[:3],
                        "extracted_measurements": norm_nums,
                        "measurement_count": len(norm_nums),
                    }
                )

    digest = {
        "scanned_at": datetime.now().isoformat(),
        "sessions_with_empirical_data": len(sessions_found),
        "candidates": sessions_found,
    }
    out_path = FIELD_NOTES_DIR / "chat_empirical_digest.json"
    out_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "sessions_scanned": len(sessions_found),
                "saved_to": str(out_path),
            },
            ensure_ascii=False,
        )
    )
    return digest


def compile_field_note(note_path: Path) -> Path:
    """Compile a first-party field note JSON into a validated content/articles/<slug>.json."""
    config = load_json(CONFIG_PATH)
    note = load_json(note_path)

    slug = note["slug"]
    today = datetime.now().strftime("%Y-%m-%d")
    article: dict[str, Any] = {
        "slug": slug,
        "origin": note.get("origin", "first_party"),
        "origin_label": note.get("origin_label", "独自実機・チャット検証ログ"),
        "verification_env": note.get("verification_env", ""),
        "title": note["title"],
        "subtitle": note["subtitle"],
        "category": note["category"],
        "tags": note.get("tags", []),
        "published_at": note.get("published_at", today),
        "updated_at": note.get("updated_at", today),
        "data_updated_at": note.get("data_updated_at", today),
        "sample_size_n": int(note.get("sample_size_n", 1)),
        "tldr": note.get("tldr", []),
        "methodology_note": note["methodology_note"],
        "seo": note["seo"],
        "summary_metrics": note["summary_metrics"],
        "spec_gap_chart": note["spec_gap_chart"],
        "comparison_table": note["comparison_table"],
        "sections": note["sections"],
        "faqs": note.get("faqs", []),
        "sources": note["sources"],
        "affiliate_keys": note.get("affiliate_keys", []),
    }

    raw_bytes = json.dumps(note.get("comparison_table", {}), ensure_ascii=False, sort_keys=True).encode("utf-8")
    article["dataset_sha256"] = hashlib.sha256(raw_bytes).hexdigest()[:16]

    validate_article(article, config)

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    out_file = ARTICLES_DIR / f"{slug}.json"
    tmp_file = ARTICLES_DIR / f"{slug}.json.tmp"
    tmp_file.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_file.replace(out_file)

    print(
        json.dumps(
            {
                "status": "compiled",
                "slug": slug,
                "origin": article["origin"],
                "dataset_sha256": article["dataset_sha256"],
                "article_path": str(out_file),
            },
            ensure_ascii=False,
        )
    )
    return out_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nodus First-Party Insight & Chat Experiment Ingestor")
    parser.add_argument("--scan-chats", action="store_true", help="Scan local chat logs for empirical article seeds")
    parser.add_argument("--compile", type=str, default="", help="Path to field note JSON to compile into an article")
    args = parser.parse_args()

    if args.scan_chats:
        scan_chat_transcripts()
    elif args.compile:
        compile_field_note(Path(args.compile))
    else:
        parser.error("Provide --scan-chats or --compile <path>")
