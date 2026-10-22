# Search Consoleとアクセス解析（GA4・Cloudflare）の数字が合わない理由：計測位置と確認手順

> 個人サイトを公開した直後、Google Search Consoleとブラウザ側のアクセス解析（Cloudflare Web AnalyticsやGA4）で数値が食い違うときに、タグの設定ミスと仕様上の差を切り分ける手順です。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/gsc-clicks-vs-ga4-zero-analytics-discrepancy-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/gsc-clicks-vs-ga4-zero-analytics-discrepancy-guide.csv
- **Category**: Software & SaaS Economics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- Google Search Consoleは「Google検索結果画面での表示とリンククリック」をGoogle側で記録するのに対し、Webアクセス解析は「着地後のページでJavaScriptビーコンが実行・送信されたか」を記録するため、測定している地点が根本的に異なる。
- Search Console側にもプライバシー保護のための「匿名化クエリ（まれな検索語句の除外）」や1日あたりの行数上限があり、クエリ別一覧の合計とサイト全体の合計は一致しない仕様になっている。
- 立ち上げ初期の少数の数値差でタグを何度もいじるのではなく、タイムゾーン、集計期間の確定遅れ、ブラウザのコンテンツブロッカーの影響を切り分けて確認する。


## 選択肢の比較表
| 計測ツール | 記録されるタイミング・場所 | カウントされない主なケース | 集計上の仕様・クセ |
| --- | --- | --- | --- |
| Google Search Console | Google検索結果画面で表示・クリックされた時点（Googleサーバー側） | 検索以外の直接流入・SNS流入、クエリ内訳における匿名化語句 | 米国太平洋時間（PT）基準。語句一覧の合計と全体合計は一致しない |
| ブラウザ側解析（Cloudflare Web Analytics等） | 訪問者のブラウザでページ読み込み完了後にJSビーコンが送信された時点 | 広告・トラッカー遮断拡張機能の利用者、JS実行前の即時離脱 | UTCや設定タイムゾーン基準。ビーコン通信が遮断されると記録ゼロになる |

## 詳細解説・原因分析
### 検索結果でのクリックと着地後のJavaScript実行は別の出来事として記録される
Search Consoleでクリックが数件記録されているのに、サイト側のアクセス解析（Cloudflare Web AnalyticsやGA4など）が0件のままだと、「計測タグの埋め込みに失敗しているのではないか」と不安になります。しかし両者は計測している場所が全く異なります。Search ConsoleはGoogleの検索結果ページ上でリンクが押された瞬間をGoogle側で記録します。一方、Cloudflare Web Analyticsなどのブラウザ側解析は、訪問者のブラウザがページを読み込み、Navigation Timing APIの計測値を含むJavaScriptビーコンを外部エンドポイントへ送信して初めて1件として記録されます。もし訪問者が広告ブロッカー（uBlock OriginやBraveのShields等）を使ってビーコン通信を遮断していたり、読み込み完了前に戻るボタンを押したりした場合は、Search Consoleにはクリックが残ってもブラウザ側解析には記録されません。
参照: [Google Search Central Blog：A deep dive into Search Console performance data filtering and limits](https://developers.google.com/search/blog/2022/10/performance-data-deep-dive)
参照: [Cloudflare Web Analytics Docs：Data origin and collection](https://developers.cloudflare.com/web-analytics/data-metrics/data-origin-and-collection/)

### Search Consoleの内部でも「サイト全体合計」と「検索語句の合計」は一致しない
Google Search Centralの公式解説（A deep dive into Search Console performance data filtering and limits）では、Search Console自身の数値を見る際の重要な仕様が説明されています。個人の特定を防ぐプライバシーフィルタリングにより、検索回数が少ないまれな検索語句は「匿名化されたクエリ（anonymized queries）」として語句別の表から除外されます。さらに、保存・処理リソースの制限から1日あたりの内訳行数にも上限があります。そのため、検索語句（query）の一覧表をすべて足し算しても、グラフ上部に表示されるサイト全体の合計クリック数・表示回数より少なくなるのが正常な仕様です。
参照: [Google Search Central Blog：A deep dive into Search Console performance data filtering and limits](https://developers.google.com/search/blog/2022/10/performance-data-deep-dive)

### タイムゾーンの違いとデータの確定ラグ（2〜3日）をそろえて比較する
もう一つ見落としやすいのが日付の区切り方です。Search Consoleの日次データは米国太平洋時間（America/Los_Angeles）を基準に集計されており、直近1〜2日分は速報値（未確定）として扱われます。一方、Cloudflare Web AnalyticsやサーバーログはUTCまたは日本時間（JST）で集計されるため、同じ「10月15日」という表示でも最大16〜17時間のズレがあります。立ち上げ直後でアクセスが数件しかない段階では、この時差と確定ラグだけで数字が食い違って見えます。
参照: [Google Search Central Blog：A deep dive into Search Console performance data filtering and limits](https://developers.google.com/search/blog/2022/10/performance-data-deep-dive)
参照: [Cloudflare Web Analytics Docs：Data origin and collection](https://developers.cloudflare.com/web-analytics/data-metrics/data-origin-and-collection/)

### タグの故障かどうかはブラウザの開発者ツール（Networkタブ）で1回確かめる
設定ミスかどうかを切り分けたい場合は、管理画面の数字を眺めるのではなく、実際の公開ページを自分のブラウザ（シークレットウィンドウ・拡張機能OFF）で開き、開発者ツールのConsoleおよびNetworkタブを確認します。CSP（Content Security Policy）エラーが出ておらず、ビーコンスクリプトが正常に読み込まれていれば実装自体は完了しています。あとは少数のノイズに振り回されず、1〜2週間単位のトレンドで検索流入の増減を追うのが適切です。
参照: [Google Search Central Blog：A deep dive into Search Console performance data filtering and limits](https://developers.google.com/search/blog/2022/10/performance-data-deep-dive)
参照: [Cloudflare Web Analytics Docs：Data origin and collection](https://developers.cloudflare.com/web-analytics/data-metrics/data-origin-and-collection/)

## よくある疑問と回答 (FAQ)
### Q. Search ConsoleではクリックがあるのにGA4やCloudflare Web Analyticsが0になるのはなぜですか？
A. Search ConsoleはGoogle検索結果上でリンクが押された回数を記録する一方、Webアクセス解析はページ読み込み後にブラウザ内でJavaScriptビーコンが送信された回数を記録するため、広告ブロッカー（AdBlock等）や読み込み前の離脱があると0になります。

### Q. Search Consoleの「検索クエリ一覧の合計」と「グラフのサイト全体合計」が一致しないのはバグですか？
A. バグではなくGoogleの仕様です。プライバシー保護のため検索回数が少ない「匿名化されたクエリ」が一覧表から除外されるため、一覧表の行を足し合わせてもサイト全体の合計クリック数・表示回数より少なくなります。

## 記事の範囲
2026年10月16日にGoogle Search Central公式ブログ（Search Consoleのパフォーマンスデータ制限の解説）およびCloudflare Web Analytics公式ドキュメント（Data origin and collection）を確認して整理した記事です。


## 参考資料
- [Google Search Central Blog：A deep dive into Search Console performance data filtering and limits](https://developers.google.com/search/blog/2022/10/performance-data-deep-dive)
- [Cloudflare Web Analytics Docs：Data origin and collection](https://developers.cloudflare.com/web-analytics/data-metrics/data-origin-and-collection/)

## 次に考えたいこと
- [Cloudflare Pagesの独自ドメイン設定：pages.devやプレビューURLも検索に出る？](https://nodus-lab.pages.dev/articles/cloudflare-pages-custom-domain-preview-url-indexing)
