# Nodus — Quantitative Spec & Real-World Benchmark Intelligence

**Nodus** は、メーカーの「カタログ公称値」とグローバル技術コミュニティ（Reddit / Hacker News / 一次検証ログ）の「実測データ（中央値・制限閾値・持続性能）」を定量比較するステルス・データメディア基盤です。

## アーキテクチャとディレクトリ構成

- `config/site_config.json` : サイト基本設定、SEO改善ループ閾値、ステマ規制表記、およびアフィリエイトID一元管理
- `content/articles/*.json` : 構造化データセット記事（KPI指標、公称vs実測チャート、比較マトリクス表、FAQ、一次出典リスト）
- `scripts/build_site.py` : ゼロ依存・超高速静的サイトビルダー（HTML5, Schema.org JSON-LD, `sitemap.xml`, `robots.txt`, `llms.txt` を `dist/` に一括生成）
- `scripts/miner.py` : Reddit / Hacker News 公式APIから「単位付き実測数値」を含む投稿・検証スクショURLを自動発掘するマイナー
- `scripts/seo_loop.py` : Google Search Console (GSC) データに基づく自律型SEO改善ループ（CTR改善・順位8〜20位記事へのデータ追記・台帳記録）
- `colab/nodus_gpu_worker.ipynb` : Google AI Pro (200 CU) のL4/A100上でベンチマーク画像OCR（VLM）や動画文字起こしを一括処理し、自動でランタイムを解放するColabノートブック

## コマンド一覧

```bash
# 1. サイトのビルド（dist/ に本番用HTML一式を生成）
python scripts/build_site.py

# 2. コミュニティ実測データの発掘（Reddit / Hacker News / GitHub）
python scripts/miner.py --query "100W GaN thermal" --subreddit "UsbCHardware"

# 3. AI × SEO改善ループの実行（Dry Run / 本番適用）
python scripts/seo_loop.py
python scripts/seo_loop.py --apply
```
