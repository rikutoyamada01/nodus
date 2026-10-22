# 合成データ（TTS・画像生成）で機械学習の精度が上がったと錯覚する罠：ドメインギャップと防止策

> 不足している属性（女性音声や特定条件の画像など）をTTSや合成データで補う際に陥りやすい5つの罠を解説。同一音声IDの複数設定を独立話者と誤認する問題、合成データのTest混入、ゼロ波形・フォーマット偽装、前処理でのメタデータ消失を防ぐ手順を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/tts-synthetic-data-augmentation-domain-gap-pitfalls
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/tts-synthetic-data-augmentation-domain-gap-pitfalls.csv
- **Category**: Architecture
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- TTS（音声合成）や合成データの追加と、モデル構造の変更を1回の実験で同時に行うと、改善・悪化の原因がデータなのかモデルなのか一切区別できなくなる。
- 同一TTS音声IDのピッチ・速度違い（3設定）は「3人の独立した人間話者」ではなく「未使用設定TTS」として区別し、Testセットでは実データと合成データを完全に分離して集計する。
- 生成スクリプトがAPIエラー時に無音（ゼロ波形）を出力して学習を汚染するバグや、前処理がフォルダ名（`tts_augmented`）から話者IDを上書きして元メタデータを消すバグを品質ゲートで防ぐ。


## 選択肢の比較表
| 合成データ活用の失敗パターン | なぜ起きるか（原因） | 引き起こされる誤判断・バグ | 正しい実験・実装ルール |
| --- | --- | --- | --- |
| 合成データを実データTestに混ぜて合算評価 | Testセットの件数を増やそうとして合成データ104件を実データ620件に合流させる | モデルがTTS特有の音響特徴だけを簡単に当てて全体Accuracyが上昇し、実話者が改善したと錯覚する | 合成Testは実データTestと完全に分けて集計し、採用判断は実データTestの改善と既存群の非劣化で行う |
| 1つのTTS音声の3設定を『3人の話者』とカウント | 同一音声ID（例：Nanami）で標準・高め・低めの3プロファイルを作って分割する | Trainに標準、Testに高めを入れて『未知話者への汎化』と誤認する（実際は同一声質のピッチ違い） | voice_id（音声種別）とprofile_id（設定）を分けて記録し、同一voice_idの別設定は『未使用設定TTS』と呼ぶ |
| 生成エラー時のゼロ波形（無音）フォールバック | TTS生成スクリプトが通信失敗や空レスポンス時に例外で止めず長さ0やゼロ配列の音声を返して続行する | 正解ラベル付きの『無音データ』がTrainに混入し、無音区間を特定クラスへ誤分類する原因になる | 生成失敗時は明示的に未完了エラーで停止し、16kHz PCM_16デコード・無音検査・全ラベル網羅を検証する |
| 前処理での話者メタデータ消失 | dataset_builderがCSVのspeaker列を引き継がず、保存先パス（dataset/tts_augmented/...）の親フォルダ名からspeakerを推定する | 異なるTTS音声やプロファイルがすべて『tts_augmented』という1人の話者IDに潰れ、人物別の集計や補正が壊れる | パスからの推測を廃止し、マニフェストCSVで明示されたspeaker / voice_id / profile_idを最優先で引き継ぐ |

## 詳細解説・原因分析
### 「TTS追加」と「モデル変更」を同時にやると改善・悪化の原因が分からなくなる
「女性話者の認識精度が低いから、TTS（音声合成）で女性音声を生成して足そう。ついでに別ブランチで作った新しいマルチタスクモデルもマージして学習しよう」——このようにデータ追加とモデル構造（またはサンプラー・前処理）の変更を1回の実験に詰め込むと、結果が良くなっても悪くなっても、どちらが原因なのか一切区別できなくなります。

特に既存のAudioAugmentor（データ拡張器）にピッチ変更や速度変更がすでに入っている場合、TTS側でピッチや話速を変えたデータを固定生成して足すことに本当に上積み効果があるのかは、対照実験なしには分かりません。最短で確実な実験順序は、(1) まずモデルのアーキテクチャを一切変えず、固定Splitを厳守した『生データのみ』の基準実験（Baseline）を取り、(2) 次に標準設定の小さなTTSデータを足した条件を同じモデル・同じシードで比較し、(3) 改善傾向が確認できた場合のみピッチ・速度違いのプロファイルを追加する、という段階的な切り分けです。

そして最も重要なルールとして、『合成音声のTestスコアが上がったこと』を採用根拠にしてはいけません。TTSで学習すればTTSのTestが当たるのは当然であり、生データの女性話者Testで改善し、かつ既存の男性話者や実機マイク条件で大幅な回帰低下が起きていないことを確認して初めて採用を判断します。

主なチェックポイントは以下の通りです：実データと合成データの役割分担：TTSやシミュレーションデータはあくまで『補助学習・補助評価』であり、生声や実機画像の評価の代用にはならない / 未知話者と設定違いを区別する：同じTTS音声のピッチを変えたデータは『別の人間』ではないため、評価レポートでは『未使用設定TTS』と表記して未知の実話者テストと明確に分ける / 性別不明データの勝手な割り当て禁止：収集データのうち話者属性が不明なプールを声質やファイル名から推測して女性データとしてカウントせず、『不明は不明』として分離集計する。
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)
参照: [Hugging Face Datasets Documentation: Process and manage datasets](https://huggingface.co/docs/datasets/process)

### 合成データ生成スクリプトに潜む「ゼロ波形」「MP3偽装」「読み誤り」の防止
外部のTTSサービスや生成ライブラリを使ってデータセットを自動生成するコードには、データ品質を静かに破壊するバグが潜みがちです。例えば、ネットワーク瞬断やレート制限で音声データが返らなかった際に、スクリプトを止めないために『長さ0の配列やゼロ波形（完全な無音）を返して処理を継続する』実装になっていると、正解ラベルが付いた無音ファイルが学習データに混入し、モデルの境界を破壊します。

また、TTSライブラリの出力ストリームが実際にはMP3フォーマットであるにもかかわらず、デコード処理を通さずにファイル拡張子だけ `.wav` として保存してしまうミスや、単音節ラベル（例：『は』『へ』『を』や拗音）を渡したときにTTSエンジンの辞書が助詞や別単語のイントネーション・長音として読んでしまう問題も頻発します。

そのため、合成データを学習へ投入する前には必ず以下の品質ゲートを通す必要があります。

主なチェックポイントは以下の通りです：フォーマットと波形の厳密検査：16kHz・モノラル・PCM_16として正しくデコードできるか、無音（RMSエネルギー極小）・空ファイル・極端な短尺や長尺がないかを全件自動検査する / 小規模試聴による発音確認：全件生成を回す前に、単音節や特殊ラベルの発音が意図通りの音素になっているか小規模サンプルを試聴・確認し、生成設定と入力テキストをマニフェストに記録する / クラウド（Colab等）とのデータ同期検証：ローカルで生成した未コミットの合成データがクラウドGPU側へ同期されず、古いデータセットのまま学習が回っていたという事故を防ぐため、マニフェストとSHA-256ハッシュで実使用データを照合する。
参照: [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)
参照: [Hugging Face Datasets Documentation: Process and manage datasets](https://huggingface.co/docs/datasets/process)

## よくある疑問と回答 (FAQ)
### Q. TTS（音声合成）で作ったデータを学習に足したらValidation精度が上がったのに実機で効かないのはなぜですか？
A. 合成データがValidationやTestセットにも混ざっていて「合成音声特有の音響パターン」を当てているだけか、同じTTS話者IDの速度・ピッチ違いを別人物として分割してしまいデータリークが起きているケースが多いためです。

### Q. 合成データを機械学習パイプラインに入れるときの必須チェックは何ですか？
A. Testセットは100%人間の実データに固定すること、モデル構造の変更とデータ追加を同じ実験で同時に行わないこと、API失敗時の無音（ゼロ波形）ファイルやメタデータ消失を自動検査で弾くことです。

## 記事の範囲
2026年10月16日にscikit-learnのCommon pitfallsおよびHugging Face Datasetsのドキュメントを確認し、合成データ（TTS等）を用いたデータ拡張時の実験管理・品質検査ルールを整理した記事です。


## 参考資料
- [scikit-learn User Guide: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)
- [Hugging Face Datasets Documentation: Process and manage datasets](https://huggingface.co/docs/datasets/process)

## 次に考えたいこと
- [機械学習のデータリーク原因：話者・条件リークと学習コード内の再分割バグ](https://nodus-lab.pages.dev/articles/ml-benchmark-data-leakage-group-split-pipeline-guide)
- [混同行列の見方とBalanced Accuracy：全体の正答率だけ見ると失敗する理由](https://nodus-lab.pages.dev/articles/ml-accuracy-trap-confusion-matrix-balanced-accuracy-guide)
- [AIの継続学習：実機データで「出題＝正解ラベル」にしてはいけない理由](https://nodus-lab.pages.dev/articles/human-in-the-loop-labeling-prompt-vs-actual-input-guide)
