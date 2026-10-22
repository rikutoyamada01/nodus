# PyTorchのWeightedRandomSamplerと損失重みの二重補正：重複抽選で未使用データが出る罠

> クラス数や話者数の偏りを補正しようとして、WeightedRandomSampler（重複あり抽選）とCrossEntropyLossのクラス重みを同時に有効化したときに起きる過補正と「エポック内で一度も使われないデータ」の問題を解説します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/ml-class-imbalance-oversampling-loss-weight-double-correction
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/ml-class-imbalance-oversampling-loss-weight-double-correction.csv
- **Category**: Architecture
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- PyTorchの `WeightedRandomSampler(replacement=True)` は重複ありの確率抽選であるため、「全件学習した」と思っていても1エポック内で一度も抽選されない未使用データが大量に発生し、少数派データだけが何度も重複入力される。
- さらにサンプラーでの出現頻度補正と、損失関数（CrossEntropyLoss等）のクラス重み補正を無自覚に二重掛けすると、特定クラスや特定話者への極端な過適合・他条件での回帰低下を引き起こす。
- 基本の学習設計は「全Trainデータを毎エポック最低1回・重複なしでシャッフル通過」させる方式に置き、追加のオーバーサンプリングを使う場合は全件通過とは別枠で件数と実使用ID数を記録してValで検証する。


## 選択肢の比較表
| サンプリング・重み付け方式 | 1エポック内のデータ通過挙動 | 発生しやすい問題 | 推奨される使い分け |
| --- | --- | --- | --- |
| 全件シャッフル通過（重複なし・損失重み1倍） | 全Trainサンプルが毎エポック確実に1回ずつ使われる（未使用0件） | 極端な件数格差（例：100倍差）がある場合は多数派に引っ張られる | すべての実験のベースライン（基準）。クラス件数が65〜123件程度ならこれだけで十分安定する |
| WeightedRandomSampler (replacement=True) 単独 | サンプル総数N回を確率抽選するため、重複抽選されるデータと未使用データ（約3割前後）が生じる | 『全データを学習した』と誤認しやすい。エポックごとに使われないデータがランダムに発生する | 使う場合はエポックごとの実使用ID数と未使用数を必ずログに記録して検証する |
| 全件1回通過 ＋ 追加オーバーサンプリング枠 | 全Trainを確実に1回通した上で、不足群だけを明示的な別枠として追加投入する | エポックあたりのステップ数が少し増える | 全データの網羅性を100%保証しつつ特定条件を補強したい場合の安全な設計 |
| WeightedRandomSampler ＋ 損失クラス重みの二重適用 | 出現頻度でも少数派を増やし、さらに1回あたりの勾配でも重みを掛ける | 実質的に重みの二乗で強調され、少数クラスのノイズや誤ラベルに過適合して全体精度が落ちる | 原則避ける。補正が必要な場合もサンプラーか損失重みのどちらか一方をValで検証して選ぶ |

## 詳細解説・原因分析
### WeightedRandomSamplerで「全件学習しているつもり」になる罠
PyTorch等でクラス間や人物間のデータ件数の偏りを補正する際、`WeightedRandomSampler` を使う実装がよく見られます。しかし標準の `replacement=True`（復元抽出・重複あり）でデータセットサイズ $N$ 件分を抽選すると、統計的な性質上、1エポックの中で同じデータが複数回選ばれる一方、全体の約3割強（$1/e \approx 36.8\%$ 相当）のデータはそのエポックで1回もモデルに入力されません。

もしクラスごとの件数がすでに65件〜123件程度と比較的に揃っているにもかかわらず、習慣的に重複ありサンプラーと損失関数のクラス重み（Class Weight）の両方をオンにしていると、貴重な生データの一部を毎エポック捨てながら、特定サンプルだけを二重に強調して学習することになります。

したがって、「全件学習」のデフォルトは『全Trainサンプルを毎エポック確実に1回ずつ使う（重複なしシャッフル）』に固定すべきです。そのうえで、どうしても追加抽選やオーバーサンプリングが必要な場合は、全件1回通過の枠とは別枠として追加件数と重みを明示し、各エポックで実際に使われたサンプルID数（未使用0件であること）をログに記録して検証する設計が安全です。

主なチェックポイントは以下の通りです：ファイル件数と実使用回数の区別：CSV上の行数、実際の人間話者数、サンプラーの期待比率、そしてエポック内の実使用回数を混同せず別々に記録する / 未分離プールの誤均等化防止：複数人が混ざった3,000件の収集プールを『1人の話者』とみなして人物均等化サンプラーにかけると、1人あたりの学習回数が極端に圧縮されてしまうため、確定した個人IDと混合プールは分けて扱う / 二重補正の廃止：クラス数が比較的均等な状態でサンプラーと損失重みを同時に掛けず、Val（検証セット）のグループ均等Balanced Accuracyで本当に補正が必要かを確かめる。
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)
参照: [scikit-learn User Guide: Metrics and scoring](https://scikit-learn.org/stable/modules/model_evaluation.html)

### モデル選択で「平均値だけ見て最低グループを見ない」リスクを防ぐ
サンプリング比率や損失重みを変更した際、検証セット（Val）の全体平均スコアがわずか0.1〜0.2ポイント上がっただけで「改善した」と自動採用してしまうと、既存の重要なグループ（例えば基本の5母音課題や別マイク条件）で3〜4ポイントの大幅な劣化が起きていても見逃してしまいます。

重みやサンプラーの実験を行う際は、必ず実験前にVal上で「どのグループで何ポイントまでの低下を許容するか」「主指標で何ポイント以上の改善が必要か」という採用基準を固定し、複数シードで再現性を確認してから本学習へ進める規律が不可欠です。

主なチェックポイントは以下の通りです：群別許容差の事前設定：ターゲット条件（スピーカーフォン等）の改善だけでなく、既存条件の回帰幅を監視項目に入れる / Testでの重み調整禁止：Testセットのスコアを見て損失重みの倍率（1倍・2倍・4倍）を選び直さない / 再現性の確保：乱数シード、サンプラーの抽選方法、選択されたエポック番号、早期停止の理由をすべて実験マニフェストに保存する。
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)
参照: [scikit-learn User Guide: Metrics and scoring](https://scikit-learn.org/stable/modules/model_evaluation.html)

## よくある疑問と回答 (FAQ)
### Q. PyTorchのWeightedRandomSamplerで `replacement=True` にすると何が問題になりますか？
A. 復元抽出（重複あり抽選）になるため、1エポック分のデータ数を回しても一度も選ばれない多数派データが大量に発生する一方、少数派データばかりが何度も重複入力されて過学習を引き起こします。

### Q. 不均衡データを学習するとき、サンプラーとCrossEntropyLossのweightは両方使うべきですか？
A. 両方を同時に有効化すると少数クラスへの重み付けが二乗で効く「二重補正」になり、通常のクラスの認識率が大きく崩れます。基本は全データを毎エポック1回ずつ確実に通過させ、補正はどちらか一方に絞ってValで検証します。

## 記事の範囲
2026年10月16日にscikit-learnの評価・不均衡データガイドラインを確認し、エポック内の全件通過保証とサンプラー・損失重みの切り分け設計を整理した記事です。


## 参考資料
- [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)
- [scikit-learn User Guide: Metrics and scoring](https://scikit-learn.org/stable/modules/model_evaluation.html)

## 次に考えたいこと
- [混同行列の見方とBalanced Accuracy：全体の正答率だけ見ると失敗する理由](https://nodus-lab.pages.dev/articles/ml-accuracy-trap-confusion-matrix-balanced-accuracy-guide)
- [カメラやスピーカーフォン変更でAI認識精度が急落する理由と前処理の再校正](https://nodus-lab.pages.dev/articles/hardware-change-camera-microphone-hyperparameter-regression-guide)
- [機械学習のデータリーク原因：話者・条件リークと学習コード内の再分割バグ](https://nodus-lab.pages.dev/articles/ml-benchmark-data-leakage-group-split-pipeline-guide)
