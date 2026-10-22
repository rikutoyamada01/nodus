# Google Antigravityの利用枠と上限確認：5時間更新・週間上限・AIクレジットの仕組み

> 作業の途中で利用上限に達したとき、5時間待てば戻るのか、週間上限なのか、追加クレジットを使うべきか。公式プラン仕様から確認手順を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/antigravity-quota-5-hour-weekly-ai-credits-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/antigravity-quota-5-hour-weekly-ai-credits-guide.csv
- **Category**: Software & SaaS Economics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- Google AI ProおよびUltraの基本利用枠は5時間ごとに更新されるが、別途設けられている週間上限に達すると5時間経過しても回復しない。
- 消費量はプロンプトの回数ではなくエージェントが実行した作業量に連動するため、複雑な調査や並列処理ほど枠を早く消費する。
- 基本枠を超過した後にAIクレジットを自動消費するかどうかは、設定のAI Credit Overages（Never / Always等）で制御できる。


## 選択肢の比較表
| 契約状態 | 基本枠の更新周期 | 週間上限の位置づけ | 基本枠超過後の選択肢 |
| --- | --- | --- | --- |
| Pro・Ultra未加入（個人） | 週単位で更新 | 週単位の利用上限が適用される | 次回更新まで待機、または上位プランへの加入を検討 |
| Google AI Pro（月2,900円） | 週間上限に達するまで5時間ごとに更新 | 無料枠より高い週間上限 | 更新まで待機、AIクレジット消費、またはUltraへの変更 |
| Google AI Ultra（月14,500円〜） | 最も大きい枠が5時間ごとに更新 | 個人向けで最も高い週間上限＋他社モデル利用権 | 更新まで待機、またはAIクレジットによる超過利用 |

## 詳細解説・原因分析
### 5時間待てば回復する停止と週間上限による停止を区別する
Google Antigravityの個人向けプランでは、契約段階によって利用枠の更新周期が異なります。公式ドキュメントによると、Google AI ProおよびUltra加入者には5時間ごとに更新される基本枠が割り当てられますが、同時に週間レート制限も設定されています。特にProプランでは「週間上限に達するまで5時間ごとに更新される」と明記されているため、5時間待っても利用枠が回復しない場合は週間上限に到達している可能性があります。一方、ProやUltraに加入していない個人アカウントの基本枠は週単位での更新となります。
参照: [Google Antigravity Docs：Plans（利用枠・週間上限・Overages）](https://antigravity.google/docs/plans/)
参照: [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)

### 消費量は質問の回数ではなくエージェントの作業量に比例する
利用枠を「1日に何回質問できるか」という固定の回数で見積もると、実際の消費とずれが生じます。公式資料では、レート制限はシステム容量とエージェントが実行した作業量に連動すると説明されています。短時間で完了する単純な修正であれば多くの指示を実行できますが、多数のファイルを横断する調査やテスト実行を伴う複雑な依頼では、1回の指示でも多くの枠を消費します。なお、コード補完（Tab completions）は全プランで無制限と記載されており、エージェントの基本枠とは分けて扱われます。
参照: [Google Antigravity Docs：Plans（利用枠・週間上限・Overages）](https://antigravity.google/docs/plans/)

### 超過時にAIクレジットを使うかは設定で事前に選ぶ
Google AI ProまたはUltraの加入者は、購入したAIクレジットやプロモーション付与分のクレジットを使い、基本枠を超えた超過利用（Overages）が可能です。超過時のクレジットは標準のGemini Enterprise従量料金で消費されます。意図しないクレジット消費を防ぎたい場合は、ユーザー設定の「AI Credit Overages」を「Never（自動消費せず基本枠の更新を待つ）」に設定します。逆に作業の中断を避けたい場合は「Always」などの設定を選択できます。
参照: [Google Antigravity Docs：Plans（利用枠・週間上限・Overages）](https://antigravity.google/docs/plans/)

### モデルごとの枠と代替モデルへの切り替えを確認する
公式資料では、特定のモデルの基本枠を使い切った後に超過設定が働く仕組みが説明されています。上位モデル（Gemini 4 Argonなど）の枠に達した場合でも、標準のコアモデル（Gemini 3.8 Flashなど）や別モデルで作業を継続できるかを確認することで、追加費用を抑えられる場合があります。また、サードパーティ製モデルの利用権は個人向けプランではGoogle AI Ultraの特典に含まれています。
参照: [Google Antigravity Docs：Plans（利用枠・週間上限・Overages）](https://antigravity.google/docs/plans/)
参照: [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)

### クレジット追加とUltraへの変更は月間の不足頻度で比較する
日本向けの月額表示では、Google AI Proが2,900円、Google AI Ultraが14,500円からとなっており、最小構成でも月11,600円の差があります。月に1〜2回だけ締め切り前に上限へ達する程度であれば、必要な時だけAIクレジットで超過分を補う方が総額を抑えやすくなります。一方、毎週のように週間上限へ到達し、かつAntigravity上でArgonやサードパーティ製モデルを日常的に使いたい場合は、Ultraへの変更が候補になります。
参照: [Google Antigravity Docs：Plans（利用枠・週間上限・Overages）](https://antigravity.google/docs/plans/)
参照: [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)
参照: [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)

## よくある疑問と回答 (FAQ)
### Q. Google Antigravityの利用枠やAIクレジット残量はどこで確認できますか？
A. Antigravity内の設定（Settings）画面にある利用状況および「AI Credit Overages」設定項目、ならびにGoogle Oneのプラン管理画面から現在の利用枠の状態と超過時のクレジット消費設定を確認できます。

### Q. 5時間待ったのにAntigravityの利用制限が解除されないのはなぜですか？
A. Google AI Pro・Ultraの利用枠には「5時間ごとに更新される枠」とは別に「週間レート制限（Weekly limit）」が設けられており、週間上限に到達している場合は5時間経過しても次の週間リセット日時またはAIクレジット利用まで回復しません。

### Q. 基本枠を超えたときに勝手にお金（クレジット）が減るのを防げますか？
A. はい。設定の「AI Credit Overages」で「Never（自動消費しない）」または都度確認を選んでおけば、基本利用枠を使い切った時点で停止し、意図しないAIクレジット消費を防げます。

## 記事の範囲
2026年10月16日にGoogle Antigravity公式ドキュメント（Plans）およびGoogle One日本向けプラン表を確認して整理した記事です。各プランにおける実際のプロンプト実行回数やクレジット消費速度の独自測定は行っていません。月額差額や時短換算の数値は表示料金に基づく計算例であり、実際の請求額や作業効率を保証するものではありません。


## 参考資料
- [Google Antigravity Docs：Plans（利用枠・週間上限・Overages）](https://antigravity.google/docs/plans/)
- [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)
- [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)

## 次に考えたいこと
- [Gemini 4 ArgonはProで使える？ 性能・評価とAntigravityのUltra条件](https://nodus-lab.pages.dev/articles/gemini-4-argon-google-ai-pro-ultra)
- [AIコーディングのサブスクとAPI比較：Claude Code・Cursorの費用](https://nodus-lab.pages.dev/articles/ai-coding-subscriptions-real-rate-limits-token-economics)
