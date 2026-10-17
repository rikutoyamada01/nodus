# Cloudflare Pagesで独自ドメインを設定したとき、pages.devやプレビューURLも検索に出る？

> GitHub連携でブランチごとに自動生成されるプレビューURLや元の .pages.dev サブドメインが、検索エンジンに重複登録されるのを防ぐ公式仕様と確認手順を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/cloudflare-pages-custom-domain-preview-url-indexing
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/cloudflare-pages-custom-domain-preview-url-indexing.csv
- **Category**: Software & SaaS Economics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- Cloudflare Pagesでは開発ブランチやPRごとに `<hash>.<project>.pages.dev` のプレビューURLが自動生成され、初期設定ではURLを知っていれば誰でも閲覧できる公開状態になっている。
- プレビューデプロイメントには検索エンジン向けの `X-Robots-Tag: noindex` 仕様が用意されているが、書きかけの記事や非公開機能を外部から見せないためには Cloudflare Access の有効化が必要になる。
- 独自ドメイン（Apexドメインまたはサブドメイン）を追加する際は、HTML内の canonical URL とサイトマップのURLを正規ドメインへ統一し、評価の分散を防ぐ。


## 選択肢の比較表
| URLの種類 | 生成されるタイミング | 初期状態での閲覧権限 | 検索・公開管理でやること |
| --- | --- | --- | --- |
| カスタムドメイン（独自ドメイン） | Custom domainsで追加・DNS設定後 | 一般公開（本番URL） | canonicalタグとsitemap.xmlの基準URLに設定する |
| 本番 pages.dev（<project>.pages.dev） | プロジェクト作成時（mainブランチ等） | 一般公開 | 独自ドメイン運用時はcanonical統一やリダイレクトを確認 |
| プレビューURL（<hash>.<project>.pages.dev） | 開発ブランチ作成・PR更新時 | 既定で公開（URLを知っていれば閲覧可） | X-Robots-Tag: noindex の確認と、必要に応じCloudflare Accessで認証保護 |

## 詳細解説・原因分析
### ブランチを作ると自動でハッシュ付きプレビューURLが公開生成される
Cloudflare PagesをGitHubリポジトリと連携している場合、`main` などの本番ブランチ以外に新しい開発ブランチやプルリクエスト（リポジトリ内部からのPR）を作成すると、`<hash>.<project>.pages.dev` のように先頭へランダムなハッシュが付いたプレビューURLが自動的に生成されます。公式ドキュメント（Preview deployments）にある通り、このプレビュー環境は本番の `<project>.pages.dev` やカスタムドメインには影響しませんが、初期設定（By default）ではインターネット上に公開された状態になっており、認証なしで閲覧可能です。
参照: [Cloudflare Pages Docs：Preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/)

### 検索避け（noindex）と第三者からの閲覧防止（Cloudflare Access）を区別する
プレビューURLがGoogle検索にインデックスされて本番ページと重複する問題については、Cloudflare Pagesのプレビューデプロイメント機能で `X-Robots-Tag: noindex` ヘッダによる検索エンジン制御が扱われています。ただし、「検索結果に出ないこと」と「URLを推測・共有されたときに誰も開けないこと」は別です。公開前の記事やテスト中の画面を本人やチームメンバー以外に見せたくない場合は、プロジェクト設定からCloudflare Access（アクセスポリシー）を有効化し、プレビューデプロイメントの閲覧にログイン認証を必須にする手順が公式ドキュメントで案内されています。
参照: [Cloudflare Pages Docs：Preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/)

### 独自ドメイン（Apexドメイン）を使う場合はCloudflareゾーン設定とCanonicalをそろえる
独自ドメインを追加する場合、サブドメイン形式であれば外部DNSのままCNAMEレコードを向けるだけで利用できますが、ルート（Apex）ドメインを使う場合は、そのドメイン自体をCloudflareのゾーンとして追加しネームサーバーを向ける必要があります。また、独自ドメインを追加したあとも元の `<project>.pages.dev` が残っていると、検索エンジンがどちらを正規URLか迷う原因になるため、サイト側の `<link rel="canonical">` や `sitemap.xml` の出力先URLを必ず新しい独自ドメインへ統一し、必要に応じてリダイレクトを設定します。
参照: [Cloudflare Pages Docs：Preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/)
参照: [Cloudflare Pages Docs：Custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)

## 記事の範囲
2026年10月16日にCloudflare Pages公式ドキュメント（Preview deployments、Custom domains）を確認して整理した記事です。


## 参考資料
- [Cloudflare Pages Docs：Preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/)
- [Cloudflare Pages Docs：Custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)

## 次に考えたいこと
- [安いクラウドバックアップで100GBを戻すといくら？ 保存料金と下り転送費用の比較](https://nodus-lab.pages.dev/articles/cloud-backup-100gb-restore-egress-cost-comparison)
