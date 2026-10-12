# Nodus オーナー向け運用・初期設定手順書 (Operations Manual)

本ドキュメントは、自律型定量比較メディア **Nodus** に関して、オーナー（あなた）側で実施いただく外部アカウント連携および段階的マネタイズの手順をまとめたものです。
サイト本体の構築、Codex（`gpt-6.1-sol`）によるセキュリティ・法務・UX・アクセシビリティ監査、GitHub Actionsによる週次自律運用ワークフロー、および **Cloudflare Pages / GitHub への本番公開** はすべて完了しています。

---

## 1. 現在の運用モード：Phase 1（審査通過前・純粋リサーチモード）

ご指摘の通り、サイト立ち上げ初日（4記事・流入蓄積前）の段階では、Amazonアソシエイト本家の審査要件（原則10記事以上のオリジナルコンテンツ蓄積＋申請後180日以内に3件の適格販売）を満たすことができません。また、未承認の状態でダミーのトラッキングタグや「Amazonのアソシエイトとして〜」という文言を掲載すると、審査時に不承認の原因となります。

そのため現在、`config/site_config.json` は **`"monetization_enabled": false`（純粋リサーチメディアモード）** に設定し、本番環境へ反映済みです：
- Amazon等のリンクからダミーの `?tag=...` パラメータを完全撤廃し、クリーンな直リンク（参考リンク）として出力しています。
- ヘッダー・フッター・運営情報ページには「現在、広告およびアフィリエイトリンクを一切掲載していない独立リサーチメディアとして運営しています」と明記しています（この状態が最もASP審査・検索エンジンの初期評価に有利です）。

---

## 2. あなたが今すぐ実施する作業（2ステップ）

### ステップ1：Google Search Console (GSC) 登録とサイトマップ送信（所要時間：約5分）

まずは検索エンジンにインデックスさせ、オーガニック流入とクリック実績を蓄積します。

1. [Google Search Console](https://search.google.com/search-console) を開き、「URLプレフィックス」に `https://nodus-lab.pages.dev` を登録します。
2. 左メニュー「サイトマップ」から `https://nodus-lab.pages.dev/sitemap.xml` を送信します。

### ステップ2：Cloudflare Pages の Git 自動デプロイ連携（所要時間：約3分）

今後の週次コミットや記事追加を本番へ自動反映させるため、以下のいずれかを設定してください。

- **方法A（GitHub Secrets）**: [Cloudflare API トークン画面](https://dash.cloudflare.com/profile/api-tokens) で「Cloudflare Pages を編集する」トークンを作成し、GitHubリポジトリ（`https://github.com/rikutoyamada01/nodus/settings/secrets/actions`）に以下を登録します：
  - `CLOUDFLARE_ACCOUNT_ID` : `7fc57844538beb2ff0e46d38b15c25b3`
  - `CLOUDFLARE_API_TOKEN` : 発行したAPIトークン
- **方法B（Cloudflareダッシュボード直結）**: Cloudflare の **Workers & Pages** > `nodus-lab` の設定から GitHub (`rikutoyamada01/nodus`) を接続し、ビルドコマンド `python3 scripts/build_site.py && python3 scripts/validate_site.py`、出力先 `dist` を指定します。

---

## 3. 記事蓄積後（Phase 2）のマネタイズ解禁・ワンタッチ切り替え手順

データセット記事が **10本前後** に増えた段階（私に「〇〇の実測比較記事を追加して」と指示いただければいつでも自動生成・検証して追加します）で、以下の順でマネタイズを解禁します。

### ルートA：A8.net / もしもアフィリエイト経由（初期に最も審査が通りやすい推奨ルート）
本家Amazonアソシエイトの「180日以内3件販売」ノルマを回避したい場合、**もしもアフィリエイト** 経由でのAmazon提携、または **A8.net**（即時登録可能）から申請するのが定石です。

### ルートB：Amazonアソシエイト本家申請（10記事到達・GSC流入開始後）
1. 10記事到達後、[Amazonアソシエイト・セントラル](https://affiliate.amazon.co.jp/) から `https://nodus-lab.pages.dev` を申請します。
2. トラッキングID（例：`yourtag-22`）が発行されたら、`config/site_config.json` の以下の2箇所を書き換えてコミット（または私にご指示）してください：
   ```json
   "compliance": {
     "monetization_enabled": true,
     ...
   },
   "affiliates": {
     "amazon_associate_tag": "あなたのID-22",
   ```
3. **これだけでサイト全体が自動的に「収益化・法務完全準拠モード」に切り替わります**：
   - 全Amazonリンクへの `?tag=あなたのID-22` および `rel="nofollow sponsored"` の自動付与
   - 全ページ最上部の `【PR】本ページはプロモーションを含みます` バナーの自動有効化
   - フッター・CTA・運営情報への `Amazon のアソシエイトとして、Nodusは適格販売により収入を得ています。` の自動掲出
   - `scripts/validate_site.py` が収益化モードの必須開示文言を自動でCIチェック

---

## 4. （任意・公開2〜4週間後）GSC API 完全自律ループの有効化

Google Search Console に検索クエリデータが溜まり始めたら、Google Cloud Console で Search Console API の OAuth クライアントを作成し、GitHub Secrets に以下3つを登録してください：
- `GSC_CLIENT_ID`
- `GSC_CLIENT_SECRET`
- `GSC_REFRESH_TOKEN`

登録された瞬間から、毎週月曜 06:00 (JST) の GitHub Actions（`.github/workflows/autonomous-loop.yml`）が自動的にサンプル保護モードから **本番GSCライブ最適化モード** に切り替わり、検索順位8〜20位記事の強化や低CTR記事のタイトル改善を自動実行します。
