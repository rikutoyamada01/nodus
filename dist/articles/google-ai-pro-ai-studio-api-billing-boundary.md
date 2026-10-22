# Google AI ProとGoogle AI Studio・Gemini APIの違い：無料枠・別課金の境界とデータ学習

> 個人向けのGoogle AI ProやUltraに加入していても、Google AI StudioやGemini APIで請求が発生する条件と無料枠・有料Tierの違いを公式資料から整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/google-ai-pro-ai-studio-api-billing-boundary
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/google-ai-pro-ai-studio-api-billing-boundary.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- 個人向けのGoogle AI Pro / Ultra（Google Oneサブスク）と、開発者向けのGemini API従量課金（Google Cloud請求先リンク）は別の契約体系である。
- Gemini APIとAI Studioは請求先未設定ならFree Tier（無料枠・レート制限あり）で始まるが、対象外モデルや高い制限枠を使うには有料Tierへの移行が必要。
- 公式Billing資料では、有料Tier（請求先アカウントをリンクした状態）に移行することで入出力がGoogle製品の改善（学習）に使われない扱いになる点も区別されている。


## 選択肢の比較表
| 利用経路・階層 | 料金体系 | 主な利用条件・上限 | 確認すべきポイント |
| --- | --- | --- | --- |
| Google AI Pro / Ultra | 定額サブスク（月2,900円 / 14,500円〜） | GeminiアプリやAntigravity等の個人向け特典枠 | APIキー経由の外部プログラム呼び出し枠ではない |
| Gemini API Free Tier | 無料（請求先リンクなし） | 対象モデルのみ・低いレート制限 | 入出力データの取り扱い条件（無料枠規約）を確認 |
| Gemini API Paid Tier 1 | 従量課金（有効な請求先をリンク） | 月間利用上限目安 250ドルまで | プロンプトと応答がGoogle製品改善に使われない |
| Gemini API Paid Tier 2 / 3 | 従量課金（累計支払額と経過日数で昇格） | Tier 2は累計100ドル＋3日、Tier 3は累計1,000ドル＋30日 | 大量バッチ処理や本番サービス運用時のレート上限 |

## 詳細解説・原因分析
### コンシューマー向けサブスクと開発者向けAPI課金は別口座で動く
Google AI ProやUltraは、Google Oneを通じて提供される個人向けの月額サブスクリプションであり、GeminiアプリやNotebookLM、Antigravityなどを利用するための契約です。一方、自作スクリプトや外部ツールにAPIキーを設定して呼び出すGemini APIは、Google AI for Developers（および紐づくGoogle Cloud請求アカウント）の従量課金体系で動きます。Proに加入しているからといって、Gemini APIの有料トークン消費が月額2,900円の中に自動的に含まれるわけではありません。
参照: [Google AI for Developers：Gemini API Billing（請求とTier仕様）](https://ai.google.dev/gemini-api/docs/billing)
参照: [Google AI for Developers：Gemini API Pricing（料金表）](https://ai.google.dev/gemini-api/docs/pricing)
参照: [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)

### AI Studioは請求先をリンクするかどうかで無料枠と有料枠が分かれる
公式Billing資料によると、新規アカウントはまずFree Tier（無料枠）から始まり、対象モデルを無料枠のレート制限内でGoogle AI StudioおよびGemini APIから試すことができます。また、AI StudioのBuildモードからフルスタックアプリを公開する用途では、Google Cloudプロジェクトや請求先を設定せずに最大2つまでアプリを公開できる「Google Cloud Starter Tier」も用意されています。請求が発生するのは、プロジェクトに有効なGoogle Cloud請求先アカウントをリンクしてPaid Tier（有料枠）へ移行した場合です。
参照: [Google AI for Developers：Gemini API Billing（請求とTier仕様）](https://ai.google.dev/gemini-api/docs/billing)

### 有料Tierへ移行する理由はレート制限とデータの取り扱いにある
無料枠のままでも試作は可能ですが、公式資料では有料Tierへ移行する目的として「より高いレート制限へのアクセス」「上位モデルの利用」「プロンプトと応答がGoogle製品の改善に使用されないようにすること」の3点が挙げられています。社内資料や顧客データ、非公開のソースコードをAPI経由で送信する場合は、料金だけでなく無料枠と有料枠におけるデータ利用ポリシーの違いを必ず確認する必要があります。
参照: [Google AI for Developers：Gemini API Billing（請求とTier仕様）](https://ai.google.dev/gemini-api/docs/billing)
参照: [Google AI for Developers：Gemini API Pricing（料金表）](https://ai.google.dev/gemini-api/docs/pricing)

### 上位のレート制限（Tier 2・Tier 3）は課金履歴と日数で段階的に開く
Gemini APIの有料枠は、請求先を登録した直後のTier 1（月間利用上限250ドル）から始まります。さらに高い同時リクエスト数が必要な場合でも、すぐ無制限になるわけではありません。公式基準では、Tier 2（上限2,000ドル）には「累計100ドルの支払い＋初回決済成功から3日経過」、Tier 3（上限20,000〜100,000ドル以上）には「累計1,000ドルの支払い＋30日経過」が必要です。大量のデータを一括処理する予定がある場合は、前もって少額の決済実績と経過日数を満たしておく必要があります。
参照: [Google AI for Developers：Gemini API Billing（請求とTier仕様）](https://ai.google.dev/gemini-api/docs/billing)

### 手元の用途がサブスク向きかAPI向きかを切り分ける
ブラウザ上のGeminiアプリやAI Studioの画面で対話的にプロンプトを試すだけなら、Google AI Proの定額枠やAI Studioの無料枠で十分に収まります。一方、既存の業務システムや自作ツールから毎日自動でモデルを呼び出す場合や、非公開データを学習させずにAPI処理したい場合は、Paid Tier 1を設定した上でトークン単価とキャッシュ機能から月額費用を見積もるのが適切です。
参照: [Google AI for Developers：Gemini API Billing（請求とTier仕様）](https://ai.google.dev/gemini-api/docs/billing)
参照: [Google AI for Developers：Gemini API Pricing（料金表）](https://ai.google.dev/gemini-api/docs/pricing)
参照: [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)

## よくある疑問と回答 (FAQ)
### Q. Google AI Pro（月額2,900円）を契約していればGemini APIやAI Studioの有料枠も無料になりますか？
A. いいえ。個人向けのGoogle Oneサブスク（Google AI Pro / Ultra）と、開発者向けのGoogle AI Studio / Gemini API（Google Cloud請求先による従量課金）は別口座・別契約として扱われます。

### Q. Google AI Studioを無料枠（Free Tier）で使う場合と有料枠（Paid Tier）にする場合の違いは？
A. 請求先をリンクしないFree Tierは無料で試せますがレート制限が低く、入出力データがGoogle製品の改善（学習）に利用されます。Cloud請求先をリンクしてPaid Tierにするとレート制限が緩和され、データが学習に使われない規約が適用されます。

## 記事の範囲
2026年10月16日にGoogle AI for Developersの公式Billing・PricingドキュメントおよびGoogle Oneプラン表を確認して整理した記事です。各Tierの昇格条件や料金単価は確認時点の公式記載に基づいており、今後の改定や為替変動を含みません。


## 参考資料
- [Google AI for Developers：Gemini API Billing（請求とTier仕様）](https://ai.google.dev/gemini-api/docs/billing)
- [Google AI for Developers：Gemini API Pricing（料金表）](https://ai.google.dev/gemini-api/docs/pricing)
- [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)

## 次に考えたいこと
- [Gemini 4 ArgonはProで使える？ 性能・評価とAntigravityのUltra条件](https://nodus-lab.pages.dev/articles/gemini-4-argon-google-ai-pro-ultra)
- [Google Antigravityの利用枠：上限の確認方法と5時間更新・週間制限の仕組み](https://nodus-lab.pages.dev/articles/antigravity-quota-5-hour-weekly-ai-credits-guide)
