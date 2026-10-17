# LLM APIの速さは、何を測って比べればいい？

> 最初の文字までの待ち時間、全文の完了時間、出力の品質。APIプロバイダーを替える前に、遅い理由を切り分けます。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/llm-api-providers-ttft-latency-throughput-variance-benchmarks
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/llm-api-providers-ttft-latency-throughput-variance-benchmarks.csv

## 訂正について
旧版の672リクエスト集計、プロバイダー別のp50・p95、夜間の悪化率、キャッシュの短縮率は、計測記録を確認できないため撤回しました。待ち時間と品質を分けて比較する手順へ改訂しています。

---

- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-13

## 選び方の要点
- 同じ仕事を、同じ品質で完了できる条件をそろえてから速さを比べる。
- ストリーミングで早く見せることと、モデルが早く生成を終えることは区別する。
- 特定の時間帯やプロバイダーが必ず遅いという順位は、測定なしに付けない。


## 選択肢の比較表
| 指標 | 答える疑問 | 記録する条件 | 読み違えやすい点 |
| --- | --- | --- | --- |
| 初回表示までの時間 | ユーザーが待つ時間は長いか | 計測の開始点、最初のイベントか表示文字か | 接続完了や空のイベントを回答開始と混同しない |
| 全文の完了時間 | 1つの仕事を何秒で終えるか | 入力、出力長、ツール呼び出し、再試行 | 出力が短いだけの回答を速いと評価しない |
| 生成速度 | 生成中にどれくらい出力するか | トークナイザー、出力数、時間範囲 | 異なるモデルのtok/sをそのまま文章量の比較に使わない |
| 遅い側の分布 | 普段より待つケースはどれくらいか | 件数、測定期間、エラーとタイムアウト | p95だけを足して直列処理全体のp95にしない |

## 詳細解説・原因分析
### どの待ち時間を短くしたいか
対話画面なら最初の意味のある表示、帳票生成なら最後まで正しく作れた時間、複数段の処理ならアプリ全体の完了時間を測ります。送信開始から測るのか、接続後から測るのかも決めてください。測定の開始点と終了点をそろえてから、所要時間を比較します。

### 同じプロンプトでも、比較条件はまだ足りない
モデルのバージョン、入力の長さ、最大出力、思考設定、実行元、同時実行数を記録します。モデルごとにトークンへの分割方法が違うため、tok/sだけでは同じ量の日本語を処理したか分かりません。JSONの形式や必要な情報がそろったかを判定し、失敗と再試行を含めて比べます。

### キャッシュとストリーミングは、分けて測る
OpenAIの公式資料は、ストリーミングによる早い表示や、入力・出力・呼び出し回数を見直す方法を説明しています。Prompt Cachingにはモデルや設定ごとの条件があり、毎回同じ短縮率になるものではありません。キャッシュがない最初の呼び出しと、ヒットした呼び出しを混ぜず、使用量の情報も保存します。
参照: [OpenAI：Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization)
参照: [OpenAI：Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)

### p95を足せば、全体のp95になるわけではない
複数のAPI呼び出しを直列に行うと待ち時間は積み上がりますが、各段のp95を足した数値は処理全体のp95とは一般に一致しません。ユーザー操作から完了までの時間を直接記録します。エラーやタイムアウトを除き、速く完了したリクエストだけを集計すると、運用上の待ち時間を過小評価してしまいます。失敗や再試行も含めた待ち時間を記録し、成功率も併せて示します。

### 別のAPIへ切り替える前に
まず長すぎる出力、不要な直列呼び出し、データ読み込み、アプリ側のバッファリングを確認します。別のモデルに切り替えると、品質や対応機能、料金、データの送信先も変わる場合があります。障害時の代替構成も、同じ結果を出せるかと二重実行を防げるかを検証してから導入します。切替先を増やすだけで速さや可用性が保証されるわけではありません。

## 記事の範囲
公式資料で確認できる機能・仕様と、編集上の比較手順を整理しています。購入価格や性能の順位を確定する実機比較は行っていません。計算例を示す場合は仮定を明記しています。


## 参考資料
- [OpenAI：Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization)
- [OpenAI：Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)

## 次に考えたいこと
- [パーソナルAIは、どこに置く？](https://nodus-lab.pages.dev/articles/personal-ai-vps-home-server-subscription)
- [AIコーディングのサブスクとAPI、費用をどう比べる？](https://nodus-lab.pages.dev/articles/ai-coding-subscriptions-real-rate-limits-token-economics)
