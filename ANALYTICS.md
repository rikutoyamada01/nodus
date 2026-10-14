# Analyticsの取得と設定

`python scripts/analytics_report.py` は実際のCloudflare Web AnalyticsとSearch Console APIを読み取る。サンプルへ切り替えない。結果は `data/analytics/latest.json` に保存し、Gitと公開サイトから除外する。

既存の日次GitHub Actionsにも取得ジョブを追加した。結果は実行画面のSummaryと `analytics-report` artifactから確認する。全取得先が利用できない場合は失敗、一部のみ取得できた場合も不足を警告する。

## 集計の意味

- Cloudflare：完了したUTC日で直近7日とその前の7日を比較する。PVとvisitsはブラウザbeaconに基づく推計。visitsをユニーク人数やGA4のセッション数とは呼ばない。
- Search Console：確定データを日単位で取得し、14日ずつを比較する。ホームを含むサイト全体のクリック数・表示回数。日付はSearch Consoleの集計タイムゾーン。
- 認証エラー、計測無効、観測なしをアクセスゼロと扱わない。空の結果にゼロの比較表を作らず、比較は `null`。前期間が0のときの増減率も `null`。
- 計測を始める前のアクセスを後から復元することはできない。

## Cloudflare

既存のSecrets `CLOUDFLARE_ACCOUNT_ID` と `CLOUDFLARE_API_TOKEN` を使用する。解析権限が足りない場合は、対象アカウントの **Account Analytics Read** を持つ専用トークンを `CLOUDFLARE_ANALYTICS_API_TOKEN` に登録する。専用トークンにPagesの編集権限は不要。

Dashboardで **Workers & Pages → nodus-lab → Metrics → Web Analytics → Enable**。次回デプロイでHTMLにbeaconが追加される。CSPでは計測スクリプトと送信先だけを追加で許可する。ローカルWranglerのログインはGitHub Secretsとは別であり、短命のOAuthトークンをSecretsへコピーしない。

## Search Console

現在、Googleの認証は未設定。取得を有効にするには、Google CloudでSearch Console APIを有効化してOAuthクライアントを作り、NodusにアクセスできるGoogleアカウントで認証し、以下をGitHub Secretsに登録する。認証値をチャットや公開ファイルへ貼らない。

- `GSC_CLIENT_ID`
- `GSC_CLIENT_SECRET`
- `GSC_REFRESH_TOKEN`

取得だけならスコープは `https://www.googleapis.com/auth/webmasters.readonly`。同じ認証でサイトマップ送信も行う場合は `webmasters` が必要。

対象プロパティは `config/site_config.json` の `seo_loop.gsc_property_url`。URLプレフィックス型なら `https://nodus-lab.pages.dev/`。ドメイン型を使う場合は、実際に登録されている識別子に合わせる。所有権確認ファイルとAPI認証は別の設定。

短命の `GSC_ACCESS_TOKEN` も使えるが、継続取得にはrefresh token方式を使う。GA4は別サービスであり、今回はCloudflareの復旧を優先する。架空のGA4 IDや動かないタグは追加しない。

## 検証

```text
python -m unittest discover -s scripts -p test_analytics_report.py
python scripts/analytics_report.py
```

SEO処理も、認証なしでサンプルを読む動作を止めた。サンプルを使うテストは `python scripts/seo_loop.py --allow-sample` と明示する。実データなしでの `--apply` は終了コード2とする。

参照：[Cloudflare Pagesの有効化](https://developers.cloudflare.com/pages/how-to/web-analytics/)、[計測の仕組み](https://developers.cloudflare.com/web-analytics/data-metrics/data-origin-and-collection/)、[Google API認証](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing)。
