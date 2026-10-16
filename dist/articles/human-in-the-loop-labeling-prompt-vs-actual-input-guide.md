# 実機データの継続学習で「出題ラベル＝正解ラベル」にしてはいけない理由：ユーザーの誤操作とモデル誤認識の分離設計

> 「使いながらデータを集めてモデルを賢くする」継続学習パイプラインで、アプリが出題したお題をそのまま正解ラベルとして自動学習させるとデータセットが崩壊する理由を解説。出題・実際の発声・モデル予測の3分離、Top-3救済ログの保持、安全なモデル配布設計をまとめます。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/human-in-the-loop-labeling-prompt-vs-actual-input-guide.html
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/human-in-the-loop-labeling-prompt-vs-actual-input-guide.csv
- **Category**: Architecture
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- 学習支援装置やエッジAIアプリで実利用データを収集する際、システムが出題した文字（例：『さ』）をそのまま録音データの正解ラベルにすると、利用者が読み間違えて『か』と発声したデータまで『さ』として学習しモデルが壊れる。
- 収集データには「出題ラベル」「人が確認した実際の発声ラベル」「モデルの予測（Top-1およびTop-3救済前の生スコア）」の3つを分離して記録し、判別不能なデータは学習へ投入せず保留にする。
- 発声した瞬間に端末内で重みを書き換えるのではなく、管理側の定期ジョブでVal選択・Test回帰確認を通過したモデルのみを配布し、端末側には『最新版・バージョン固定・ローカル限定』の切替を用意する。


## 選択肢の比較表
| 出題文字（お題） | 利用者の実際の発声 | モデルの第1候補予測 | 付与すべき学習ラベルとデータの意味 |
| --- | --- | --- | --- |
| 「さ」を出題 | 「さ」と正しく発声 | 「か」と誤予測 | 学習ラベルは『さ』。モデルの誤認識を改善するための貴重な教師データになる |
| 「さ」を出題 | 「か」と読み間違い | 「か」と予測 | 学習ラベルは『か』。利用者の読み間違いであり、モデルの音声分類自体は正しいため『さ』にしてはいけない |
| 「さ」を出題 | 雑音・小声で判別不能 | 「か」と予測 | 『保留（未投入）』。人が聞いても判別できないデータを無理にラベリングして学習へ混ぜない |
| 「さ」を出題 | 「さ」と発声 | 第1候補「か」・第2候補「さ」(スコア0.18) | 体験上はTop-3救済で正解扱いにするが、ログには『第1候補＝か』を上書きせず残し、Top-1改善の材料にする |

## 詳細解説・原因分析
### なぜ「出題した文字＝音声の正解ラベル」にするとモデルが壊れるのか
音声認識や手書き・点字認識を使った学習支援アプリでは、認識精度がまだ発展途上にある段階でもユーザー体験を損なわないよう、「モデルの第1候補（Top-1）が外れていても、上位3候補（Top-3）以内にお題の文字が一定のスコア（例：0.15以上）で入っていれば正解として救済する」といった工夫がよく使われます。

このシステムに「実際の利用で集まったデータを学習に戻して賢くする」仕組みを組み込む際、最もやってはいけないのが『アプリが出題した文字をそのまま録音データの正解ラベルとして自動付与する』ことです。なぜなら、利用者がお題の『さ』を『か』と読み間違えて発声した場合、モデルが正しく『か』と認識していても、出題ラベルの『さ』を正解として再学習させてしまうと、「『か』という音声波形は『さ』である」という誤った教師信号をモデルに教え込むことになるからです。

したがって、収集データには「1. 出題文字」「2. モデルの元の認識候補とスコア（Top-3救済で正解にした場合も元の第1候補を上書きせず保持）」「3. 人がレビューツールで実際に聞いて確認した発声ラベル」の3つを分けて記録し、確認済みのデータだけを学習パイプラインへ送る必要があります。また、認識が成功した回答ばかりを集めるとデータに偏りが出るため、低確信度やother（不明音）に分類された発声も漏れなく収集対象に含めます。

主なチェックポイントは以下の通りです：Top-3救済ログの保全：体験上の採点結果（正解/不正解）と、モデルが本来出した第1候補の予測ラベルを別カラムで保持し、モデルの誤認識と人間の読み間違いを切り分けられるようにする / 重複送信の防止（べき等性）：各録音に一意な録音ID・試行IDを付与し、ネットワーク再送等で同じバッチを再度アップロードしても学習データに重複登録されないようにする / 収集失敗時の非ブロッキング設計：録音保存やクラウドへのアップロードがエラーになっても、目の前のユーザーの学習体験やアプリの動作を絶対に止めない。
参照: [Hugging Face Hub Documentation: Upload files to the Hub](https://huggingface.co/docs/huggingface_hub/guides/upload)
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)

### 「その場で賢くなる」と誤解させないバッチ検証とモデル配布アーキテクチャ
展示会やフィールドテストで継続学習の仕組みを説明する際、「一度話すとその場で端末が賢くなる」「データが増えれば必ず精度が上がる」といった説明をするのは誠実ではありません。発声した瞬間に端末上で重みを更新（オンライン学習）すると、ノイズや偏った入力でモデルが即座に劣化するリスクがあり、またエッジ端末に重い学習用ライブラリ一式を持たせる必要も生じます。

堅牢なアーキテクチャでは、利用端末（エッジ側）は「推論と同意に基づく録音・メタデータ送信」だけに徹し、学習と評価は管理側の定期ジョブで行います。具体的には、Hugging Face Hub等のリポジトリを介して確認済みデータを回収し、既存の人物分離Splitを維持したまま再学習を行い、Valでモデル選択した後にTestで現行配布モデルと回帰比較します。そして採用基準（未知話者やスピーカーフォン条件での改善、雑音誤受理率の非劣化）を満たしたモデルだけを、ONNXファイル・ラベル一覧・前処理設定のセットとして公開します。

さらに利用端末側には「1. 最新版を自動取得（セッション開始前に確認）」「2. バージョン固定（指定したモデルを維持）」「3. ローカル限定（ネットワーク遮断・会場Wi-Fi混雑時でも手元のモデルで確実に動作）」の3モードを用意し、体験の最中にモデルが勝手に切り替わらないように固定するのが鉄則です。

主なチェックポイントは以下の通りです：同意と公開範囲の分離：「端末内での録音への同意」と「外部リポジトリへの送信・公開への同意」は区別して扱い、モデルだけを公開し音声データを非公開にしたい場合はリポジトリを分離する / コミットハッシュとモデルバージョンの分離：同一リポジトリに収集データを追加するだけでもGitコミットは進むため、推論端末側はリポジトリのコミットではなく『配布モデルのバージョン番号』を見て更新有無を判定する / 仕組みの完成と精度向上の分離：「収集から再学習・配布までのパイプラインが動いたこと」と「実際に未知話者での認識精度が上がったこと」は別の成果として分けて検証・報告する。
参照: [Hugging Face Hub Documentation: Upload files to the Hub](https://huggingface.co/docs/huggingface_hub/guides/upload)
参照: [Hugging Face Hub Documentation: Downloading files (hf_hub_download)](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download)
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)

## 記事の範囲
2026年10月16日にHugging Face Hub公式ドキュメント（upload、file_download）およびscikit-learnの評価ガイドを確認し、エッジAI端末における実利用データ収集・ラベリング・再学習・配布の安全な運用設計を整理した記事です。


## 参考資料
- [Hugging Face Hub Documentation: Upload files to the Hub](https://huggingface.co/docs/huggingface_hub/guides/upload)
- [Hugging Face Hub Documentation: Downloading files (hf_hub_download)](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download)
- [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)

## 次に考えたいこと
- [機械学習のベンチマークが正しく測れない原因：話者・撮影条件リークと学習パイプライン内の再分割バグ](https://nodus-lab.pages.dev/articles/ml-benchmark-data-leakage-group-split-pipeline-guide.html)
- [合成データ（TTS・画像生成）で機械学習の精度が上がったと錯覚する罠：ドメインギャップとメタデータ消失の防止策](https://nodus-lab.pages.dev/articles/tts-synthetic-data-augmentation-domain-gap-pitfalls.html)
- [展示会やコンテスト実機審査でAIが動かなくなる原因：会場Wi-Fi混雑・騒音による精度劣化とローカル完結設計](https://nodus-lab.pages.dev/articles/edge-ai-venue-wifi-congestion-offline-fallback-design.html)
