# PyTorchで学習したモデルをONNX INT8量子化して実機へ載せるときに精度が落ちる原因：前処理不一致と段階的検証

> GPU上のPyTorch FP32では高精度だったモデルを、Raspberry Pi等のエッジ端末向けにONNX INT8量子化して載せると認識精度が変わってしまう原因を解説。学習時と推論時の前処理不一致、補助ヘッドの切り離し、3段階検証手順を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/edge-ai-pytorch-fp32-to-onnx-int8-preprocess-mismatch-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/edge-ai-pytorch-fp32-to-onnx-int8-preprocess-mismatch-guide.csv
- **Category**: Architecture
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- PyTorchで学習したモデルをONNX INT8へ量子化してエッジ端末に載せる際、PyTorch時点の評価スコアをそのまま実機性能として転記してはいけない。
- 精度変化の多くは量子化誤差だけでなく「学習時は事前に切り出し・音量正規化したファイルを使い、実機推論では生データ入力＋内包前処理を使っていることによる前処理不一致」や「labels.jsonの順序ズレ」で起きる。
- 必ず同一の小さな開発検証セットで『PyTorch FP32』『ONNX FP32』『ONNX INT8』の3段階を生データ入力から比較し、学習用のマルチタスク補助ヘッドはエクスポート前に切り離してドロップイン置換性を保つ。


## 選択肢の比較表
| 検証ステージ | 確認すべき一致項目 | 不一致・劣化があった場合の主な原因 | 対策・ガードレール |
| --- | --- | --- | --- |
| Stage 1: PyTorch (前処理済み入力) vs PyTorch (生データ入力) | 切り出し窓（例：0.6秒）・リサンプリング・音量正規化・FeatureExtractor出力の一致 | 学習時は事前に切り出し・正規化したWAVを使い、評価時は生WAVから異なるルールで切り出している | 前処理関数を1つの共通モジュールに統一し、学習時と推論時で異なる正規化統計を使わない |
| Stage 2: PyTorch FP32 vs ONNX FP32 | 同一入力テンソルに対する出力ロジット（Logits）の数値一致（許容誤差内） | 動的軸（dynamic_axes）の設定漏れ、制御フローの固定化、またはlabels.jsonのクラス順序ズレ | エクスポート直後にダミー入力と実サンプルでロジット差分を自動テストし、ラベル一覧との整合ガードを入れる |
| Stage 3: ONNX FP32 vs ONNX INT8 | 開発検証セット（Val）でのBalanced Accuracy・混同行列・CPU推論レイテンシ | 特定層（Attentionや細かな特徴抽出層）のINT8丸め誤差による境界クラスの反転 | 必ず実運用するINT8 ONNXアーティファクトでVal/Testを再評価し、PyTorch時点のスコアを正式精度として報告しない |
| Stage 4: 学習用マルチタスク構造からの推論モデル抽出 | 本番ランタイムとの入出力インターフェース互換性（ドロップイン置換性） | 学習時に追加した子音・母音等の補助分類ヘッドがONNX出力に残り、既存推論ワーカーが壊れる | エクスポート前に extract_inference_model() 等で補助ヘッドを切り離し、主分類ヘッドのみを出力する |

## 詳細解説・原因分析
### 「PyTorchのスコア」をそのまま実機の性能として報告してはいけない理由
エッジ端末（Raspberry PiやローカルPCのCPUなど）でリアルタイムに音声認識（wav2vec 2.0等）や画像認識を動かす場合、PyTorchのFP32モデルをそのまま動かすと1回の推論に150ms以上かかり、ストリーミング応答が追いつかないことがあります。そこでONNXへエクスポートしたうえでINT8量子化（Quantization）を適用すると、モデルサイズを圧縮し、CPU推論レイテンシを2倍以上（例：150ms台→60ms台へ）高速化できます。

しかしこのとき、クラウドGPU上でPyTorchモデルを評価した時点のAccuracyやMacro-F1を、そのまま「実機モデルの精度」としてレポートに転記してしまうケースが後を絶ちません。実機で動くのはあくまで量子化後のONNX INT8モデルであり、さらに学習時と実機推論時では「前処理の経路」が異なることが多いためです。

例えば、学習高速化のために「あらかじめ0.6秒に切り出して音量処理を施した前処理済みWAVファイル」で学習を回し、本番推論では「マイクからの生音声ストリームをONNX前処理またはランタイム側で切り出してINT8モデルへ渡す」という構成をとっている場合、精度が落ちた原因がモデルの学習不足なのか、切り出し・音量正規化の不一致なのか、INT8量子化の丸め誤差なのかが分からなくなります。

主なチェックポイントは以下の通りです：3段階の切り分け評価：小さな固定開発セットを用意し、(1) PyTorch FP32、(2) ONNX FP32、(3) ONNX INT8 の3つを同じ生データから走らせて予測の一致率を確認する / ラベル順序ガードの自動化：ONNXエクスポート時にモデルの出力次元数と `labels.json` のクラス順序・件数が完全一致しているかを単体テスト（label guard）で強制検証する / キャッシュ混入の防止：推論器がローカルの共有キャッシュディレクトリから古い重みファイルを勝手に読み込んでいないか、実験固有の出力パスとSHA-256ハッシュを明示して評価する。
参照: [ONNX Runtime Documentation: Quantize ONNX Models](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)
参照: [PyTorch Documentation: torch.onnx](https://pytorch.org/docs/stable/onnx.html)

### 学習時の工夫（マルチタスク補助ヘッド等）を推論時にゼロコストで切り離す設計
認識精度を高めるために、学習時に「主分類ヘッド（例：100音節分類）」だけでなく「子音分類ヘッド（30クラス）」「母音分類ヘッド（7クラス）」や知識蒸留（Knowledge Distillation）用の射影層といった補助ヘッドを並列に配置するマルチタスク学習は強力な手法です。

ただし、これらの補助ヘッドを含んだままONNXへエクスポートしてしまうと、実機側の推論ランタイム（既存のストリームリスナーや出力ワーカー）が想定している出力テンソルの形と合わなくなり、本体アプリのコードを書き換える必要が出てきます。また、推論時には使わない補助ヘッドの演算コストも無駄に残ってしまいます。

これを防ぐには、モデルクラスに推論用グラフ抽出メソッド（例：`extract_inference_model()`）を用意し、学習完了後に補助ヘッドを切り離して「既存のベースラインモデルと入出力の型・ラベル体系が100%同一のモデル」に変換してからONNXエクスポートとINT8量子化を実行します。こうすることで、学習側の工夫を本番ランタイムに対して完全なドロップイン置換（レイテンシ増加ゼロ・呼び出し側コード変更ゼロ）として安全に届けることができます。

主なチェックポイントは以下の通りです：学習コードと推論依存の分離：エッジ端末側にはONNX Runtime等の軽量な推論依存だけを持たせ、PyTorch本体やラベリング・学習用の重い依存関係を本番環境へ持ち込まない / セットでのアトミック公開：採用基準を満たしたモデルを公開する際は、INT8 ONNXファイル単体ではなく『ONNXモデル・ラベル定義JSON・前処理設定』を必ず1セットとして配布する / 実運用アーティファクトでの最終回帰確認：量子化後のONNXファイルを使って最終的なVal/Test評価とCPUレイテンシ計測を行い、その数値を正式なリリース記録として残す。
参照: [ONNX Runtime Documentation: Quantize ONNX Models](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)
参照: [PyTorch Documentation: torch.onnx](https://pytorch.org/docs/stable/onnx.html)

## 記事の範囲
2026年10月16日にONNX Runtime Quantization公式ドキュメントおよびPyTorch `torch.onnx` 公式ドキュメントを確認し、音声・画像モデルのONNX変換・INT8量子化時における前処理一致検証と推論グラフ分離の設計手順を整理した記事です。


## 参考資料
- [ONNX Runtime Documentation: Quantize ONNX Models](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)
- [PyTorch Documentation: torch.onnx](https://pytorch.org/docs/stable/onnx.html)

## 次に考えたいこと
- [オフライン正答率は高いのに実機で使えない理由：ストリーミングAIにおける「内容一致率」と「発火タイミング一致率」の乖離](https://nodus-lab.pages.dev/articles/streaming-ai-offline-accuracy-vs-realtime-timing-guide)
- [カメラ距離やマイク（スピーカーフォン）を変えたらAI認識精度が急落する理由：前処理ハイパーパラメータの前提崩壊と再校正](https://nodus-lab.pages.dev/articles/hardware-change-camera-microphone-hyperparameter-regression-guide)
- [実機データの継続学習で「出題ラベル＝正解ラベル」にしてはいけない理由：ユーザーの誤操作とモデル誤認識の分離設計](https://nodus-lab.pages.dev/articles/human-in-the-loop-labeling-prompt-vs-actual-input-guide)
