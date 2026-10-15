# Nodus — Quantitative Spec & Real-World Benchmark Intelligence

サイトの編集方針は「買う、作る、その前に。」。企画の優先順位・需要の仮説・取材項目は [EDITORIAL_PLAN.md](EDITORIAL_PLAN.md) を参照。

既存12記事の数値・出典を見直した記録は [EDITORIAL_REVIEW.md](EDITORIAL_REVIEW.md) を参照。再現確認できない集計値を撤回し、選び方へ改訂済み。旧ログURLは取り下げ案内を配信し、元資料は編集用に保存する。

デザインのソースは `scripts/editorial.css`、ページの生成は `scripts/build_site.py`。`dist/` を直接編集する代わりにソースを変更して再ビルドする。`kind: "guide"` の記事は公式資料に基づく選び方として表示し、実測グラフや実測サンプル数を付けない。既存記事の一覧用見出しは `display_title` で指定できる。

**Nodus** は、メーカーの「カタログ公称値」とグローバル技術コミュニティ（Reddit / Hacker News / GitHub Discussions / 一次検証ログ）の「実測データ（中央値・制限閾値・持続性能）」を定量比較するデータメディア基盤です。

## アーキテクチャとディレクトリ構成

- `config/site_config.json` : サイト基本設定、SEO改善ループ閾値、景品表示法（ステマ規制）・Amazonアソシエイト必須開示文、定期マイニング対象トピック、およびアフィリエイトID一元管理
- `content/articles/*.json` : 構造化データセット記事（測定条件メソドロジー、サンプル数 `sample_size_n`、KPI指標、SVG公称vs実測チャート、比較マトリクス表、FAQ、一次出典リスト）
- `scripts/build_site.py` : ゼロ依存・静的サイト＆データセットビルダー（HTML5, Schema.org `TechArticle`/`Dataset`/`FAQPage` JSON-LD, CSVデータセット `dist/datasets/*.csv`, `feed.xml`, `sitemap.xml`, `robots.txt`, `llms.txt`, `404.html`, Cloudflare Pages用 `_headers` を一括生成）
- `scripts/validate_site.py` : エンタープライズ品質・セキュリティ・法務・アクセシビリティ検証ゲート（XSS/JSON-LD脱出防止、URLスキーム検証、インラインJS/CSSゼロによる厳格CSP準拠、Amazonアソシエイト・PR表記、著作権保護のための本文スニペット排除を自動検査）
- `scripts/miner.py` : Reddit OAuth / Hacker News Algolia / GitHub APIから「単位付き実測数値」のみを抽出するマイナー（本文の無断転載を行わず、数値・単位・出典URLのみを構造化保存）
- `scripts/seo_loop.py` : Google Search Console (GSC) REST API（OAuth2リフレッシュトークン対応）に基づく自律型SEO改善ループ（サンプルデータ時の本番記事誤書き換え防止ガードレール搭載）
- `.github/workflows/ci-quality-gate.yml` : Push / PR時の自動ビルド・品質検証ゲートおよびCloudflare Pages自動デプロイ
- `.github/workflows/autonomous-loop.yml` : 週次（毎週月曜06:00 JST）の自動マイニング・GSC閉ループ最適化・検証・自動コミット＆デプロイ
- `OPERATIONS_MANUAL.md` : オーナー向け初期設定・運用手順書

## コマンド一覧

```bash
# 1. サイトおよびCSVデータセットのビルド（dist/ に本番用ファイル一式を生成）
python scripts/build_site.py

# 2. セキュリティ・法務・CSP・A11y 品質検証ゲートの実行
python scripts/validate_site.py

# 3. コミュニティ実測データの発掘（設定済み全トピック / 個別クエリ）
python scripts/miner.py --all-configured
python scripts/miner.py --query "100W GaN thermal throttling" --subreddit "UsbCHardware"

# 4. AI × SEO改善ループの実行（Dry Run / 本番GSC適用）
python scripts/seo_loop.py
python scripts/seo_loop.py --apply
```
