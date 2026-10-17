# 安いクラウドバックアップで100GBを戻すといくら？ 保存料金と復元時の下り転送費用

> 自宅NASや写真サーバーの外部バックアップ先を選ぶとき、毎月の保存料金だけでなく、障害時に100GB〜1TBを一括ダウンロード（Egress）したときの料金条件を公式価格表から比較します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/cloud-backup-100gb-restore-egress-cost-comparison
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/cloud-backup-100gb-restore-egress-cost-comparison.csv
- **Category**: Software & SaaS Economics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- オブジェクトストレージの費用は「毎月の保存料金（$/GB-月）」だけでなく、「データを戻すときの下り転送量（Egress）」「データ取得（Retrieval）料金」「API操作回数」の合計で決まる。
- Cloudflare R2（Standard）は保存が $0.015/GB-月 で下り転送（Egress）が無料だが、Infrequent Accessクラスを選ぶと取得時に $0.01/GB のRetrieval料金がかかる。
- Backblaze B2（Pay-as-you-go）は保存が $6/TB-月（$0.006/GB-月）と安く、月間平均保存量の3倍までの下り転送（Egress）が無料に含まれているため、月1〜3回の全体復元テストなら追加転送費なしで収まる。


## 選択肢の比較表
| サービス / クラス | 保存料金（公式単価） | 下り転送（Egress）料金 | データ取得・最低保持・API料金の条件 |
| --- | --- | --- | --- |
| Cloudflare R2（Standard） | $0.015 / GB-月（無料枠あり） | 無料（$0） | 取得費なし。Class A $4.50/100万回、Class B $0.36/100万回 |
| Cloudflare R2（Infrequent Access） | $0.010 / GB-月 | 無料（$0） | データ取得時に $0.01/GB の処理費＋最低保持期間の条件あり |
| Backblaze B2（Pay-as-you-go） | 最初の10GB無料、以降 $6/TB-月（$0.006/GB） | 月間平均保存量の3倍まで無料（超過分 $0.01/GB） | 最低ファイルサイズ・最低保持期間なし。Class A/B/C API無料 |

## 詳細解説・原因分析
### 毎月の保存単価だけで選ぶと障害復旧時の取り出し費用を見落としやすい
自宅NASや写真サーバー（Immich等）の外部バックアップ先としてS3互換のオブジェクトストレージを選ぶ際、「1GBあたり月いくらか」という保存料金だけに目が行きがちです。しかしバックアップの本来の目的は、HDDが壊れたときに100GBや500GBのデータを一気に手元へダウンロード（リストア）することにあります。もし下りデータ転送（Egress）やデータ取得（Data Retrieval）に高い従量課金がかかるプランを選んでいると、普段の月額は数百円でも、いざ全データを戻す月に思わぬ請求が発生することがあります。
参照: [Cloudflare R2 Docs：Pricing](https://developers.cloudflare.com/r2/pricing/)
参照: [Backblaze：B2 Cloud Storage Pricing](https://www.backblaze.com/cloud-storage/pricing)

### Cloudflare R2はEgress無料だがStandardとInfrequent Accessで取得費が異なる
2026年10月16日確認のCloudflare R2公式料金表では、インターネットへの下り転送（Egress）はいずれのストレージクラスでも無料（Free）と明記されています。ただし、通常の「Standard（$0.015/GB-月）」と、保存単価が安い「Infrequent Access（$0.01/GB-月）」では復元時の扱いが異なります。Standardクラスはデータ取得（Data Retrieval）料金が無料ですが、Infrequent Accessクラスではデータ取得時に `$0.01 / GB` の処理料金がかかり、さらにClass A/BのAPI操作単価もStandardの2倍以上に設定されています。バックアップの復元テストを定期的に行うなら、この取得料金の差を確認して選ぶ必要があります。
参照: [Cloudflare R2 Docs：Pricing](https://developers.cloudflare.com/r2/pricing/)

### Backblaze B2は月間保存量の3倍まで無料でダウンロードできる
一方、Backblaze B2の公式料金ページを確認すると、最初の10GBが常時無料で、従量課金の保存単価は1TBあたり月6ドル（1GBあたり0.006ドル）とR2 Standardより低く設定されています。気になる復元時の下り転送（Egress）についても、「月間平均保存データ量の3倍まで無料（Free 3x monthly egress）」という枠が標準で付帯しています（3倍を超えた超過分のみ $0.01/GB）。たとえば100GBのバックアップを保存している場合、同じ月の中に合計300GB（＝全データ100GBの丸ごと復元を月3回分）までダウンロードしても、下り転送の追加料金は0ドルとなります。また、最低保存期間や最低ファイルサイズ料金もありません。
参照: [Backblaze：B2 Cloud Storage Pricing](https://www.backblaze.com/cloud-storage/pricing)

### 100GBを保存して年1回丸ごと復元する場合の仮定計算例
公式単価をもとに、100GBのバックアップデータを保存し、ある月に100GBすべてを1回ダウンロードして復元したと仮定して単純計算してみます（無料枠やAPI端数切り上げを除いた単価比較の例）。
1. Cloudflare R2（Standard）：月間保存費は `100GB × $0.015 ＝ $1.50`、復元時のEgress費とRetrieval費は `$0` で、その月の合計は約 `$1.50`（＋APIリクエスト分）。
2. Cloudflare R2（Infrequent Access）：月間保存費は `100GB × $0.010 ＝ $1.00` だが、100GB復元する月にはデータ取得費 `100GB × $0.01 ＝ $1.00` が加わり、その月の合計は約 `$2.00`（＋APIリクエスト分）。
3. Backblaze B2：月間保存費は `100GB × $0.006 ＝ $0.60`（10GB無料枠を考慮すれば `$0.54`）、100GBの復元は「月3倍（300GB）無料枠」の範囲内に収まるためEgress費は `$0` となり、その月の合計は約 `$0.54〜$0.60`（＋Class D等の微小なAPI分）。
このように、小さなファイルが何十万個もあるのか、大きなアーカイブファイルにまとめて送るのか（APIリクエスト数）と、復元頻度をあわせて比較すると、自分のバックアップ運用に合った保存先を選べます。
参照: [Cloudflare R2 Docs：Pricing](https://developers.cloudflare.com/r2/pricing/)
参照: [Backblaze：B2 Cloud Storage Pricing](https://www.backblaze.com/cloud-storage/pricing)

## 記事の範囲
2026年10月16日にCloudflare R2およびBackblaze B2の公式Pricingページを確認して整理した記事です。記事内の金額試算は公式のドル建て単価に基づく計算例であり、APIリクエスト数や為替レート、税金によって実請求額は変動します。各ストレージからのダウンロード速度の実測は行っていません。


## 参考資料
- [Cloudflare R2 Docs：Pricing](https://developers.cloudflare.com/r2/pricing/)
- [Backblaze：B2 Cloud Storage Pricing](https://www.backblaze.com/cloud-storage/pricing)

## 次に考えたいこと
- [Immichは写真フォルダだけコピーすれば戻せる？ データベースダンプと復元範囲の確認](https://nodus-lab.pages.dev/articles/immich-backup-photos-database-restore-scope)
- [Cloudflare Pagesで独自ドメインを設定したとき、pages.devやプレビューURLも検索に出る？](https://nodus-lab.pages.dev/articles/cloudflare-pages-custom-domain-preview-url-indexing)
