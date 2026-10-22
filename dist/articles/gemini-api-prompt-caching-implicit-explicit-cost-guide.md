# Gemini APIのプロンプトキャッシュ仕様：ImplicitとExplicitの違い・料金と最小トークン条件

> 同じ指示文や参考資料を繰り返し送るとき、自動（Implicit）キャッシュと明示的（Explicit）キャッシュのどちらが使えるのか。モデル別の最小トークン数と設計の注意点を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/gemini-api-prompt-caching-implicit-explicit-cost-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/gemini-api-prompt-caching-implicit-explicit-cost-guide.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- Gemini 2.5以降のモデルでは設定不要の暗黙的キャッシュ（Implicit caching）が既定で有効になっており、キャッシュヒット時は自動でコスト削減が適用される。
- Gemini 4 ArgonおよびGemini 3系モデルのImplicit caching最小入力長は4,096トークン（Gemini 2.5系は2,048トークン）であり、それ未満の短いプロンプトでは対象にならない。
- Gemini 4 Argon以降およびInteractions APIでは明示的キャッシュ（Explicit caching）がサポートされないため、共通テキストを先頭に固定するプロンプト設計が重要になる。


## 選択肢の比較表
| キャッシュ方式 / モデル群 | 最小入力トークン数 | 事前のオブジェクト作成 | 主な制約・確認事項 |
| --- | --- | --- | --- |
| Implicit caching（Gemini 4 Argon / 3.x） | 4,096 トークン | 不要（既定で自動有効） | 共通プレフィックスを先頭に置き短時間内に連続送信する |
| Implicit caching（Gemini 2.5 Pro / Flash） | 2,048 トークン | 不要（既定で自動有効） | レスポンスの usage.total_cached_tokens でヒット数を確認 |
| Explicit caching（Gemini 3 / 2.5の対象モデル） | モデル・API仕様に準拠 | 必要（generateContent APIで作成） | 保持時間に応じたストレージ費用が発生。Argon以降は非対応 |

## 詳細解説・原因分析
### Gemini 4 Argon以降は明示的キャッシュではなく暗黙的キャッシュを使う
Gemini APIのコンテキストキャッシュには、開発者がキャッシュオブジェクトを作成・管理する「明示的キャッシュ（Explicit caching）」と、API側が自動で共通部分を検出する「暗黙的キャッシュ（Implicit caching）」の2種類があります。2026年10月16日確認の公式ドキュメントでは、Interactions APIおよびGemini 4 Argon以降のモデルではExplicit cachingはサポートされず、Implicit cachingのみに対応すると明記されています。そのため、新しいモデルを前提にシステムを組む場合は、Explicit caching用の管理コードを書くのではなく、Implicit cachingが効きやすいプロンプト構造にそろえるのが基本となります。
参照: [Google AI for Developers：Context caching（キャッシュ仕様と最小トークン数）](https://ai.google.dev/gemini-api/docs/caching)

### 最小トークン数（4,096トークン）に満たないプロンプトはキャッシュされない
Implicit cachingはすべてのリクエストで無条件に働くわけではなく、モデルごとに最小入力トークン数が定められています。公式表では、Gemini 4 Argon、Gemini 3.8 Flash、Gemini 3.6 Flash、Gemini 3.1 Pro Previewがいずれも最小4,096トークン、Gemini 2.5 Flashおよび2.5 Proが最小2,048トークンです。システムプロンプトが数百トークンしかない短い呼び出しではキャッシュの対象外となるため、固定の規約集やスキーマ定義など4,096トークンを超えるまとまった文脈を扱う場面で効果を発揮します。
参照: [Google AI for Developers：Context caching（キャッシュ仕様と最小トークン数）](https://ai.google.dev/gemini-api/docs/caching)

### ヒット率を高めるには固定の共通文脈をプロンプトの最前部に置く
Implicit cachingはプロンプトの先頭部分（プレフィックス）の一致をもとに判定されます。公式ドキュメントでも、ヒット率を高める方法として「大きく共通する内容をプロンプトの先頭に配置すること」と「類似したプレフィックスを持つリクエストを短時間のうちに送信すること」の2点が推奨されています。もしプロンプトの1行目に毎回変わる現在時刻やランダムなリクエストIDを入れてしまうと、先頭からの一致が崩れてキャッシュが効かなくなるため、動的な変数やユーザーの質問文は必ず末尾側に配置します。
参照: [Google AI for Developers：Context caching（キャッシュ仕様と最小トークン数）](https://ai.google.dev/gemini-api/docs/caching)

### 実際にキャッシュが効いたかはレスポンスのメタデータで毎回確認する
Implicit cachingは設定不要で有効化されていますが、ヒットが保証されているわけではありません。実際にキャッシュが適用されたトークン数は、APIレスポンスに含まれる `usage.total_cached_tokens` フィールド（PythonおよびJavaScript SDK等）から確認できます。仮定のヒット率だけで月額コストを見積もるのではなく、実際のトラフィック間隔でテストリクエストを送り、`total_cached_tokens` が期待通り計上されているかをログで確かめてから本番の予算を組むことが重要です。
参照: [Google AI for Developers：Context caching（キャッシュ仕様と最小トークン数）](https://ai.google.dev/gemini-api/docs/caching)
参照: [Google AI for Developers：Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)

## よくある疑問と回答 (FAQ)
### Q. Gemini APIの暗黙的キャッシュ（Implicit caching）は何トークンから自動で効きますか？
A. 公式ドキュメントでは、Gemini 4 ArgonおよびGemini 3系モデルは最小4,096入力トークン、Gemini 2.5系モデルは最小2,048入力トークンから設定不要で自動適用されます。

### Q. キャッシュがヒットしたかどうかはどうやって確認できますか？
A. APIレスポンスの `usage_metadata` に含まれるキャッシュヒットトークン数を確認します。ヒット率を高めるには、毎回変わらないシステム指示や長文資料をプロンプトの最前部（先頭）に固定して送信します。

## 記事の範囲
2026年10月16日にGoogle AI for DevelopersのContext caching公式ドキュメントおよびPricingページを確認して整理した記事です。実際の運用環境におけるキャッシュヒット率やレイテンシ短縮幅の実測は行っていません。


## 参考資料
- [Google AI for Developers：Context caching（キャッシュ仕様と最小トークン数）](https://ai.google.dev/gemini-api/docs/caching)
- [Google AI for Developers：Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)

## 次に考えたいこと
- [Google AI Pro契約中でもAI Studio・Gemini APIは別課金？ 無料枠と請求の境界](https://nodus-lab.pages.dev/articles/google-ai-pro-ai-studio-api-billing-boundary)
- [AIエージェントのトークン節約：AST解析と部分読みの使い分け](https://nodus-lab.pages.dev/articles/ai-coding-agent-ast-peek-token-reduction-benchmarks)
