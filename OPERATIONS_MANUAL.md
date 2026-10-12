# Nodus オーナー向け運用・初期設定手順書 (Operations Manual)

本ドキュメントは、自律型定量比較メディア **Nodus** に関して、オーナー（あなた）側で実施いただく外部アカウント連携・収益化設定の手順をまとめたものです。
サイト本体の構築、Codex（`gpt-6.1-sol`）による2段階のセキュリティ・法務・UX・アクセシビリティ監査、GitHub Actionsによる週次自律運用ワークフロー、および **Cloudflare Pages / GitHub への初回本番公開** はすべて完了しています。

---

## 1. 完了している自律運用の仕組み（自動稼働中）

1. **週次マイニング＆SEO改善ループ（`.github/workflows/autonomous-loop.yml`）**
   - 毎週月曜 06:00 (JST) にGitHub Actionsが自動起動します。
   - `scripts/miner.py --all-configured` により、Hacker News / GitHub（および設定時はReddit OAuth）から単位付き実測データを自動収集します（著作権遵守のため、本文テキストは保存せず数値・単位・出典URLのみを抽出）。
   - `scripts/seo_loop.py --apply` により、Google Search Consoleのライブデータが存在する場合は高表示・低CTR記事のタイトル改善やクエリ候補抽出を自動実行します（ライブデータ未連携時は安全装置が働き、サンプルデータでの誤上書きを自動スキップします）。
   - `scripts/build_site.py` と `scripts/validate_site.py` により、HTML・CSV・JSON-LD・CSPヘッダー・法的表記を全件検証し、合格した場合のみ `main` ブランチへ自動コミット＆デプロイします。
2. **PR・Push時の品質ゲート（`.github/workflows/ci-quality-gate.yml`）**
   - XSS/JSON-LD脱出防止、危険URLスキーム拒否、インラインJS/CSSゼロ（厳格CSP準拠）、Amazonアソシエイト必須文言、ステマ規制【PR】表記を自動検査します。

---

## 2. あなたが実施する作業（全3ステップ）

### ステップ1：Cloudflare Pages の Git 自動デプロイ連携（所要時間：約3分）

初回本番デプロイはすでに完了していますが、今後の週次コミットを自動反映させるため、以下のいずれか一方を設定してください。

#### 方法A：GitHub Secrets に Cloudflare トークンを登録する（推奨）
1. [Cloudflare ダッシュボード > API トークン](https://dash.cloudflare.com/profile/api-tokens) を開きます。
2. 「トークンを作成する」→「Cloudflare Pages を編集する」テンプレートを選択し、トークンを発行します。
3. GitHubリポジトリ（`https://github.com/rikutoyamada01/nodus/settings/secrets/actions`）の **New repository secret** から以下2つを登録します：
   - `CLOUDFLARE_ACCOUNT_ID` : `7fc57844538beb2ff0e46d38b15c25b3`
   - `CLOUDFLARE_API_TOKEN` : 発行したAPIトークン文字列

#### 方法B：Cloudflare ダッシュボードから GitHub リポジトリを直接接続する
- Cloudflare ダッシュボードの **Workers & Pages** からプロジェクトを選択し、GitHub (`rikutoyamada01/nodus`) を接続して「ビルド出力ディレクトリ: `dist`」「ビルドコマンド: `python3 scripts/build_site.py && python3 scripts/validate_site.py`」を設定する方法でも自動デプロイが可能です。

---

### ステップ2：Amazonアソシエイト・各種ASPのトラッキングID設定（所要時間：約5分）

現在、`config/site_config.json` にはプレースホルダーのトラッキングタグ（`nodus-stealth-22`）が設定されており、フッターおよび運営情報ページにはAmazon規約で定められた必須文言（`Amazon のアソシエイトとして、Nodusは適格販売により収入を得ています。`）がすでに掲載されています。

1. [Amazonアソシエイト・セントラル](https://affiliate.amazon.co.jp/) にログインし、「アカウントの管理」→「ウェブサイトとモバイルアプリの変更」に公開URL（`https://nodus-lab.pages.dev`）を追加します。
2. ご自身のトラッキングID（例：`yourtag-22`）を確認します。
3. リポジトリの `config/site_config.json` 内の `nodus-stealth-22` をご自身のIDに置換して `main` ブランチへコミット（または私にご指示）してください。

---

### ステップ3：Google Search Console (GSC) 登録と閉ループSEO有効化（所要時間：約10分）

検索インデックス登録と、自律型SEO改善ループ（`scripts/seo_loop.py`）のライブ稼働を有効化します。

1. **Google Search Console へのサイト登録とサイトマップ送信**
   - [Google Search Console](https://search.google.com/search-console) を開き、「URLプレフィックス」に `https://nodus-lab.pages.dev` を登録します。
   - 左メニュー「サイトマップ」から `https://nodus-lab.pages.dev/sitemap.xml` を送信します。
2. **（任意・インデックス蓄積後）GSC API 自動連携用の GitHub Secrets 登録**
   - 公開後2〜4週間ほど経過し検索データが蓄積されたら、Google Cloud Console で Search Console API を有効化し、OAuthクライアントの以下3つの値を GitHub Repository Secrets（`https://github.com/rikutoyamada01/nodus/settings/secrets/actions`）に登録してください：
     - `GSC_CLIENT_ID`
     - `GSC_CLIENT_SECRET`
     - `GSC_REFRESH_TOKEN`
   - これにより、毎週月曜のワークフローが自動的にライブ検索クエリ・CTRを取得し、14日後の効果測定を含めた閉ループ改善を完全無人で実行します。
3. **（任意）Reddit OAuth API の有効化**
   - Hacker News と GitHub からの数値マイニングは認証なしで既に稼働していますが、Reddit公式APIからも自動収集する場合は [Reddit App Preferences](https://www.reddit.com/prefs/apps) で `script` アプリを作成し、GitHub Secrets に `REDDIT_CLIENT_ID` と `REDDIT_CLIENT_SECRET` を登録してください。
