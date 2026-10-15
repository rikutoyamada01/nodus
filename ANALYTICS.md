# Analyticsの取得と設定

`python scripts/analytics_report.py` は実際のCloudflare Web AnalyticsとSearch Console APIを読み取る。サンプルへ切り替えない。結果は `data/analytics/latest.json` に保存し、Gitと公開サイトから除外する。

既存の日次GitHub Actionsにも取得ジョブを追加した。結果は実行画面のSummaryと `analytics-report` artifactから確認する。全取得先が利用できない場合は失敗、一部のみ取得できた場合も不足を警告する。

## 集計の意味

- Cloudflare：完了したUTC日で直近7日とその前の7日を比較する。PVとvisitsはブラウザbeaconに基づく推計。visitsをユニーク人数やGA4のセッション数とは呼ばない。
- Search Console：`windows.final` はSearch Consoleの集計日（America/Los_Angeles）の3日前までの28日間を `dataState: final` で取得し、14日ずつのクリック数・表示回数を比較する。`windows.recent` は同タイムゾーンの当日を含む7日間を `dataState: all` で取得する速報用の別枠。期間は一部重なるので、両枠の合計を足さない。
- 両枠に日別の `daily`、次元なしで別途取得したサイト全体の `site_totals`、語句・ページ・語句×ページ・国・デバイス別の `breakdowns` を保存する。各行はクリック数・表示回数・CTR（0〜1の比率）・平均掲載順位を持つ。CTRや順位を足し合わせない。従来のトップ階層の `rows` と `comparison` は確定枠のまま維持する。
- 各枠の `window` に開始日・終了日・`dataState`・検索タイプ `web` を保存する。APIの `metadata` と `response_aggregation_type` も各表に保持する。速報の日別表で `daily.metadata.first_incomplete_date` が返れば、その日以降は未確定。速報にメタデータがないことを、取得期間全体の確定保証とは扱わない。
- 内訳は1回25,000行ずつページ送りする。ただし匿名化された語句とAPI内部の取得制限があるため、全語句の取得を保証しない。内訳の合計からサイト全体の合計を再構成しない。日別データでも観測のない日はAPIから返らない。
- 認証エラー、計測無効、観測なしをアクセスゼロと扱わない。空の結果にゼロの比較表を作らず、比較は `null`。前期間が0のときの増減率も `null`。
- 計測を始める前のアクセスを後から復元することはできない。

## Cloudflare

既存のSecrets `CLOUDFLARE_ACCOUNT_ID` と `CLOUDFLARE_API_TOKEN` を使用する。解析権限が足りない場合は、対象アカウントの **Account Analytics Read** を持つ専用トークンを `CLOUDFLARE_ANALYTICS_API_TOKEN` に登録する。専用トークンにPagesの編集権限は不要。

Dashboardで **Workers & Pages → nodus-lab → Metrics → Web Analytics → Enable**。次回デプロイでHTMLにbeaconが追加される。CSPでは計測スクリプトと送信先だけを追加で許可する。ローカルWranglerのログインはGitHub Secretsとは別であり、短命のOAuthトークンをSecretsへコピーしない。

## Search Console

Search Console APIは既存のGoogle認証を使用する。認証を新規設定・更新する場合は、Google CloudでSearch Console APIを有効化してOAuthクライアントを作り、NodusにアクセスできるGoogleアカウントで認証し、以下をGitHub Secretsに登録する。認証値をチャットや公開ファイルへ貼らない。

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

参照：[Cloudflare Pagesの有効化](https://developers.cloudflare.com/pages/how-to/web-analytics/)、[計測の仕組み](https://developers.cloudflare.com/web-analytics/data-metrics/data-origin-and-collection/)、[Google API認証](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing)、[Search Analytics APIの期間・次元・速報・取得上限](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)。
