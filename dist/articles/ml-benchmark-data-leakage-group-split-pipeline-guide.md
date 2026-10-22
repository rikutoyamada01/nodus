# 機械学習のデータリーク（Data Leakage）とは？ 話者リークと学習パイプライン内の再分割バグ

> 検証環境では高精度なのに本番・展示会場で全く動かない最大の原因である「データリーク（Data Leakage）」と「ベンチマーク設計の不備」を解説。話者・セッション独立分割の崩壊、学習スクリプト内部で勝手に再分割するバグ、テスト結果のサンプラー逆流を防ぐ手順をまとめました。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/ml-benchmark-data-leakage-group-split-pipeline-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/ml-benchmark-data-leakage-group-split-pipeline-guide.csv
- **Category**: Architecture
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- 未知条件を測るはずのVal/TestデータにTrainと同一の人物・同一の撮影セッション・派生データが混入する「グループリーク」があると、暗記だけで高スコアが出て実機で崩壊する。
- 固定Split CSVを作ったにもかかわらず、学習ラッパースクリプトがTrainとValを結合して前処理し、学習コード内部の自動 `train_test_split` で8:2に再分割してしまい、未知話者の8割がTrainに漏洩する実装バグが頻発する。
- Testセットの評価結果JSON（混同ペア）を学習時の重点サンプラーが読み込む逆流経路や、分割前のデータ拡張をコードレベルで遮断し、SHA-256ハッシュと人物台帳で交差ゼロを自動検証する必要がある。


## 選択肢の比較表
| リーク・計測不全のパターン | 発生しやすい実装箇所 | ベンチマークへの悪影響 | 確実な防止・監査方法 |
| --- | --- | --- | --- |
| 学習パイプライン内の勝手な再分割 | Colab用ラッパー等でTrain/Val CSVを結合して前処理し、train.py内部のstratified_splitで8:2に再分割する | 固定Valとして保留したはずの未知人物データの8割がTrainに混入し、Val精度が虚飾される | 前処理後も元CSVのsplit列またはファイルパス対応を引き継ぎ、学習時のランダム再分割を禁止する |
| Test評価結果のサンプラー逆流 | 過去のTest評価JSON（混同ペア一覧）を既定パスから読み込み、学習時のWeightedRandomSamplerの重みに使う | Test話者固有の誤り傾向を直接オーバーサンプリングしてしまい、独立テストとしての意味が失われる | 重点サンプラーの参照元はTrain内部の交差検証または固定Valのみに限定し、基準実験ではオフにする |
| 分割前のデータ拡張・切り出し | 元音声・元動画から音量変換やフレーム切り出しを作った後にファイル単位でランダム分割する | ほぼ同一の波形・画像がTrainとTestの両方に入り、暗記だけで90%以上の精度が出る | 必ず「元録音ID・人物ID・撮影セッションID」単位でTrain/Val/Testを確定させた後、Trainにのみ拡張を適用する |
| Testセットの反復参照による過適合 | Testのスコアを毎回見ながらTTS追加量、学習率、エポック数、前処理パラメータを選び直す | 人間を介した情報リークが起き、Testが実質的な第2のVal（開発評価）に変質する | モデル・閾値・停止エポックはValだけで確定させ、反復参照した既存Testは『回帰ベンチマーク』と明記する |

## 詳細解説・原因分析
### 固定Split CSVを作ったのに学習コード内部でリークする「再分割バグ」
音声認識やカメラ画像認識で「未知の人物・未知の紙面や照明条件でも動くか」を測るには、訓練データ（Train）と検証・評価データ（Val/Test）の間で人物IDや撮影セッションIDが絶対に重複しないGroup Split（scikit-learnの `GroupKFold` や `StratifiedGroupKFold` に相当する設計）が必要です。

しかし実務やチーム開発で非常に多いのが、「データセット作成時には人物を分けた固定CSV（`train.csv` / `val.csv` / `test.csv`）を作ったのに、クラウドGPU（Google Colab等）へ渡す前処理スクリプトが `train.csv` と `val.csv` を1つのディレクトリに合流させ、学習スクリプト（`train.py`）が受け取った全ファイルを内部の `train_test_split`（例：80%対20%の層化分割）で再分割していた」というパイプラインバグです。

例えばVal専用として1,058件保留していた未知話者のデータが、合流後の8:2再分割によって853件（約80.6%）もTrain側に混入してしまうと、モデルは「未知話者の声質やマイク特性」を訓練中に直接学習してしまいます。結果としてValスコアは跳ね上がりますが、本当に一度も見たことがないTest話者や本番環境に出した瞬間に精度が崩壊します。学習開始前には必ず「実際にDataLoaderへ渡されたTrainとValのファイルパス・SHA-256ハッシュ・人物IDの集合に交差（Intersection）が1件もないこと」を単体テストやアサーションで検査してください。

主なチェックポイントは以下の通りです：ファイルパスとSHA-256の両面検査：ファイル名が別でも中身（バイト列やPCM波形）が同一のコピーファイルがTrainとValに跨がっていないかハッシュ値で検証する / 派生データの同一グループ束ね：元録音からの切り出し、増幅、ピッチ変更、別名保存などの派生データはすべて元の人物ID・セッションIDに紐づけ、分割後にTrainへだけ拡張を掛ける / 学習に使った動画・音声でのベンチマーク禁止：物体検出（YOLO等）の学習に使用した録画をそのまま連続認識ベンチマークに使うと、未知の紙面や照明条件での低下を測れないため、評価専用録画を分離する。
参照: [scikit-learn User Guide: Common pitfalls and recommended practices (Data leakage)](https://scikit-learn.org/stable/common_pitfalls.html)
参照: [scikit-learn User Guide: Cross-validation: evaluating estimator performance (GroupKFold)](https://scikit-learn.org/stable/modules/cross_validation.html)

### テスト結果が学習へ逆流する「重点サンプラー」と「前処理統計」の罠
もう一つの巧妙なデータリークが、評価結果ファイルを通じた「情報の逆流」です。例えば、苦手ペア（混同しやすいクラス対）を重点的に学習させる『混同ペアサンプラー（Confusion Pair Sampler）』を実装したとします。このとき、サンプラーが読み込む評価結果JSONのデフォルトパスが「Testセットを含む評価結果」を指していると、Test話者で間違えたクラスの情報が学習時のサンプリング重みとして直接注入されてしまいます。

同様に、特徴量の正規化統計（平均・分散）、クラス重み、データ拡張のパラメータ、早期停止（Early Stopping）のエポック選択、および分類閾値（Threshold）をTestセットの情報から決めるのも典型的なリークです。これらはすべてTrainまたはVal（開発検証セット）だけから算出しなければなりません。

さらに注意すべき点として、「Valには男性話者しかおらず、女性話者がTestにしかいない」といった構成のまま開発を進めると、女性話者の精度を上げるためにTestセットのスコアを何度も確認しながらTTS（合成音声）の量やハイパーパラメータを調整することになります。一度でもモデル選択や設定変更の判断材料に使ったTestセットは、もはや『未知の盲検最終テスト』ではなく『第2の開発検証セット（回帰ベンチマーク）』になっていることを認識し、Val側にも評価したい属性（女性話者や対象デバイス条件）の独立人物を確保する必要があります。

主なチェックポイントは以下の通りです：サンプラーの分離：重点サンプリングを使う場合でも、まずサンプラー無しの全件1回通過（シャッフルのみ・重複なし）で基準実験を行い、導入時はValの評価結果だけを入力にする / 全件通過の検証：「全データを毎エポック学習した」と主張する場合は、WeightedRandomSamplerの重複抽選で未抽選データが大量に発生していないか、エポックごとの実使用ID数を記録する / 比較条件の完全固定：2つのモデルや手法を比較する際は、同一のSplit CSV・ラベル定義・前処理・推論バックエンド・乱数シード（DataLoader workerやAugmentorのシード含む）で揃える。
参照: [scikit-learn User Guide: Common pitfalls and recommended practices (Data leakage)](https://scikit-learn.org/stable/common_pitfalls.html)
参照: [scikit-learn User Guide: Cross-validation: evaluating estimator performance (GroupKFold)](https://scikit-learn.org/stable/modules/cross_validation.html)
参照: [scikit-learn User Guide: Metrics and scoring: quantifying the quality of predictions](https://scikit-learn.org/stable/modules/model_evaluation.html)

## よくある疑問と回答 (FAQ)
### Q. 機械学習のデータリーク（Data Leakage）が起きるとどんな症状が出ますか？
A. 学習・検証（Val/Test）での正答率は90%以上と非常に高いのに、学習データに含まれない新しい人物（未知話者）や別の日・別の場所で実機テストした瞬間に精度が急落します。

### Q. 事前にTrainとValのCSVを分けていたのにデータリークが起きるのはなぜですか？
A. 前処理スクリプトや学習ラッパーが一度TrainとValを結合して特徴量を作り、学習コード内部の `train_test_split` でランダムに再分割してしまうことで、同一人物のデータが両方に混ざる実装バグがよく発生します。SHA-256ハッシュと人物IDで交差ゼロを自動検査します。

## 記事の範囲
2026年10月16日にscikit-learn公式ガイド（Common pitfalls: Data leakage、GroupKFold）を確認し、音声・画像認識プロジェクトにおけるデータ分割・前処理・サンプラー設計の監査項目を整理した記事です。文中の件数や比率はリーク構造を説明するための再現・計算例です。


## 参考資料
- [scikit-learn User Guide: Common pitfalls and recommended practices (Data leakage)](https://scikit-learn.org/stable/common_pitfalls.html)
- [scikit-learn User Guide: Cross-validation: evaluating estimator performance (GroupKFold)](https://scikit-learn.org/stable/modules/cross_validation.html)
- [scikit-learn User Guide: Metrics and scoring: quantifying the quality of predictions](https://scikit-learn.org/stable/modules/model_evaluation.html)

## 次に考えたいこと
- [混同行列の見方とBalanced Accuracy：全体の正答率だけ見ると失敗する理由](https://nodus-lab.pages.dev/articles/ml-accuracy-trap-confusion-matrix-balanced-accuracy-guide)
- [機械学習のノイズ誤認識対策：対象外（other）クラスと誤受理率・誤拒否率の設計](https://nodus-lab.pages.dev/articles/ml-noise-other-class-false-acceptance-evaluation-guide)
- [合成データ（TTS・画像生成）を機械学習に使う注意点：精度向上と錯覚する5つの罠](https://nodus-lab.pages.dev/articles/tts-synthetic-data-augmentation-domain-gap-pitfalls)
