# 学習データにノイズ・対象外（other）クラスを入れないと実機で何が起きるか：誤受理率と誤拒否率の設計

> クリーンな学習データだけで作ったAIモデルが、展示会場の雑音や操作中の無関係な動きに対して誤作動を連発する原因を解説。対象外クラス（other）の設計、環境音誤受理率・発話誤拒否率の分離集計、およびノイズデータのセッション単位保留の重要性を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/ml-noise-other-class-false-acceptance-evaluation-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/ml-noise-other-class-false-acceptance-evaluation-guide.csv
- **Category**: Architecture
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- 正解クラスだけの閉集合（Closed-set）データで学習した分類器は、環境音・咳払い・指の移動中といった「どの正解にも該当しない入力」に対しても無理やりいずれかの正解クラスへ高い確率を割り当てて暴発する。
- 学習・評価データに対象外クラス（other）を組み込み、評価時はotherを人間のクラス平均Accuracyへ混ぜず「other再現率」「環境音誤受理率（FAR）」「有効入力の誤拒否率（FRR）」の3指標を独立して監視する。
- 環境音サンプルを同じ収録セッションからランダム分割すると「その部屋の空調の定常音」を暗記してしまい未知環境のノイズ耐性が測れないため、ノイズはセッション・場所単位で保留（Holdout）する。


## 選択肢の比較表
| 評価指標・データ設計 | 定義（分子 ÷ 分母） | 実機体験への影響 | 運用・集計上の注意点 |
| --- | --- | --- | --- |
| other再現率 (Other Recall) | 正解otherをotherと予測した数 ÷ 評価other総数 | 環境音や無関係な操作を正しく無視できる基礎体力 | 人間の話者別・文字別Balanced Accuracyの平均には混ぜず独立指標として報告する |
| 環境音誤受理率 (False Acceptance Rate) | 環境音（other）を有効クラスと予測した数 ÷ 評価環境音数 | 高いと、黙っていても会場の雑音や衣擦れ音で勝手に判定・読み上げが暴発する | 最も体験を壊しやすいため、確信度閾値や連続フレーム条件で抑え込む対象 |
| 発話・対象誤拒否率 (False Rejection Rate) | 有効クラスの入力をotherと予測した数 ÷ 評価有効入力数 | 高いと、ユーザーが何度発声・操作しても無反応（無視）になりストレスを与える | 別クラスへの誤分類（置換エラー）とは区別して集計し、拒否閾値の厳しすぎを検知する |
| セッション別ノイズ保留 | 収録場所・端末・時間帯ごとにノイズをTrainとVal/Testへ分離 | 未知の会場・未知のマイクでの本当の雑音耐性が分かる | 同じ部屋で録った100件の雑音から10件をランダム抽出してTestにしても、空調の定常音を暗記しているため未知環境評価にならない |

## 詳細解説・原因分析
### 静かな部屋のベンチマークで80%出ても展示会場や実機で暴発する理由
開発室の静かな環境で録音した音声や、綺麗に固定されたカメラ画像だけで学習・評価を行うと、モデルは「入力されるデータは必ずN個の正解クラスのどれかである」という強い前提（閉集合仮定：Closed-set assumption）を学習します。

しかし実機を展示会場やリビング、教室などの実環境へ持ち込むと、周囲の話し声、空調・ファン音、マイクのポップノイズ、スピーカーフォンからの反響、あるいはカメラの前で指を別の行へ移動させている途中のブレ画像など、「どの正解クラスでもない入力」が絶えず流れ込みます。閉集合モデルには「どれでもない（other）」という出口がないため、ソフトマックス層の出力が特定のクラス（例えば母音の『あ』『お』や、点1つだけで構成される文字『あ』『わ』など）へ偏り、何もしていないのに勝手に誤判定・誤発話を繰り返すことになります。

これを防ぐには、前段の音声区間検出（ノイズ適応型VAD）や対象領域トラッキングで非対象区間を弾くだけでなく、分類モデル自体の学習・評価データに明示的な『other（対象外・環境音・不明音）』クラスを含め、さらに後段の確定ロジックで「第1候補がotherや低確信度の場合は判定を保留する」二段構えの設計が必要です。

主なチェックポイントは以下の通りです：音声認識でのノイズ対策：無音だけでなく、生活雑音・咳払い・衣擦れ・複数人のざわめきをotherクラスとして収集し、室内インパルス応答（RIR）畳み込み等で空間残響への耐性を補う / カメラ画像認識でのノイズ対策：誤検出の点1つが数フレームだけ現れて消える現象や、指が行間を移動して複数文字が一気に視野から消える現象を『有効ななぞりではない』として棄却する / Validationにotherを必ず含める：TrainとTestだけにotherがありValにotherが0件だと、モデル選択や閾値決定の段階で雑音耐性を一切評価できない。
参照: [scikit-learn User Guide: Metrics and scoring: quantifying the quality of predictions](https://scikit-learn.org/stable/modules/model_evaluation.html)
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)

### 「環境音誤受理率」と「発話誤拒否率」を分けて測る方法
otherクラスを導入した際、otherを通常の正解クラス（100個の音節や文字）と同列に並べて101クラスの平均Accuracyを計算してしまうと、また別の罠に陥ります。代わりに、人間の発話・文字に対する分類精度（Balanced Accuracy）とは切り離して、以下の3つの専用指標を定義して監視します。

1つ目は『other再現率（正解otherをotherと予測した割合）』、2つ目は『環境音誤受理率（環境音であるotherを誤って有効な文字・音節として予測してしまった割合）』、3つ目は『発話誤拒否率（本来の有効な発話・文字を誤ってotherとして棄却してしまった割合）』です。なお、有効な発話を別の文字に言い間違えたケースは『誤拒否』ではなく『クラス間の分類誤り（置換エラー）』として保持します。

また、環境音データをTrain/Val/Testへ振り分ける際、1回の収録セッションで録った雑音ファイルをランダムに分割して「Testで環境音誤受理率が下がった」と結論づけるのは危険です。同一セッションの雑音は同じ空調周波数や背景の定常ノイズを共有しているため、モデルがその部屋のノイズ波形を丸暗記しているだけだからです。環境音は話者ではなく「収録セッション・場所・端末条件」の単位で分割し、さらに少数の環境音サンプル（例：10件のみ）での改善を未知環境全般への保証と拡大解釈しない規律が求められます。

主なチェックポイントは以下の通りです：環境音誤受理率（FAR）の抑制：実機体験で「触っていない・話していないのに勝手に反応する」のを防ぐ指標 / 発話誤拒否率（FRR）の抑制：拒否条件を厳しくしすぎて「何度やっても反応しない」状態になるのを防ぐ指標 / 閾値の事前決定：確信度閾値やフレーム継続数の条件は必ずVal（検証セット）のFAR/FRRバランスを見て固定し、Testの結果を見て後付けで誤予測を除外しない。
参照: [scikit-learn User Guide: Metrics and scoring: quantifying the quality of predictions](https://scikit-learn.org/stable/modules/model_evaluation.html)
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)

## 記事の範囲
2026年10月16日にscikit-learnの分類評価指標リファレンスおよびCommon pitfallsガイドを確認し、閉集合分類モデルを実環境（連続ストリーム）へ適用する際の対象外クラス（other）設計と誤受理・誤拒否指標の定義を整理した記事です。


## 参考資料
- [scikit-learn User Guide: Metrics and scoring: quantifying the quality of predictions](https://scikit-learn.org/stable/modules/model_evaluation.html)
- [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)

## 次に考えたいこと
- [機械学習で「全体の正答率（Accuracy）」だけ見ると失敗する理由：混同行列・Balanced Accuracy・誤り内訳の読み方](https://nodus-lab.pages.dev/articles/ml-accuracy-trap-confusion-matrix-balanced-accuracy-guide)
- [機械学習のベンチマークが正しく測れない原因：話者・撮影条件リークと学習パイプライン内の再分割バグ](https://nodus-lab.pages.dev/articles/ml-benchmark-data-leakage-group-split-pipeline-guide)
- [展示会やコンテスト実機審査でAIが動かなくなる原因：会場Wi-Fi混雑・騒音による精度劣化とローカル完結設計](https://nodus-lab.pages.dev/articles/edge-ai-venue-wifi-congestion-offline-fallback-design)
