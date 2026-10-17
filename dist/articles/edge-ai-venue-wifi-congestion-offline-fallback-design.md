# 展示会やコンテスト実機審査でAIが動かなくなる原因：会場Wi-Fi混雑・騒音による精度劣化とローカル完結設計

> 開発室では完璧に動いていたAI・IoTシステムが、展示会やコンテスト会場に持ち込んだ瞬間にネットワーク混雑と会場騒音で動かなくなる原因を解説。完全ローカル推論モード、有線・ローカルAP切り離し、ノイズ適応VADとTop-3救済の設計を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/edge-ai-venue-wifi-congestion-offline-fallback-design
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/edge-ai-venue-wifi-congestion-offline-fallback-design.csv
- **Category**: Architecture
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- 展示会やコンテスト会場では数百台の端末と来場者のスマホで2.4GHz帯・会場Wi-Fiやテザリングが極度に混雑するため、起動時のモデルダウンロードやクラウド通信に依存していると実機デモが停止する。
- さらに会場の反響音・周囲のプレゼン音声によりマイク入力のSNRが急落するため、静かな部屋で調整した固定音量閾値のVADやTop-1厳密一致判定のままだと音声認識がほぼ通らなくなる。
- 実機審査・展示に持ち込むシステムは、(1) ネットワークを一切使わない『ローカル限定モード（ONNX INT8等の事前バンドル）』、(2) 機器間通信の有線化または5GHz専用ローカルルーター化、(3) ノイズ適応型VADとTop-3候補救済・手動進行フォールバックを必ず備える。


## 選択肢の比較表
| 障害ポイント | 開発室（普段の環境） | 展示会・実機審査会場 | 必須のフェイルセーフ・設計対策 |
| --- | --- | --- | --- |
| モデル読込・データ同期通信 | 高速な光回線で起動時にHubから最新モデルや設定を数秒で取得できる | 会場Wi-Fiやモバイル回線が輻輳し、起動時のモデル確認・ダウンロードでタイムアウトやフリーズが起きる | 『ローカル限定モード（オフライン固定）』を用意し、体験セッション中はネットワーク通信を一切行わずローカルのONNXモデルで即起動させる |
| エッジ端末・マイコン間のローカル通信 | 2.4GHz Wi-FiやmDNS（.local）名前解決が遅延なく通る | 周囲の数百個のAP・Bluetooth電波干渉でパケットロスが多発し、音声・映像ストリームが途切れる | カメラ・マイコン〜PC間は可能な限りUSB有線接続または有線LAN＋専用5GHzローカルルーター（固定IP指定）で外部電波と分離する |
| 音声認識・マイク集音（VAD） | 静かな部屋で固定の音量閾値でも発話区間を正確に切り出せる | 周囲の会話・アナウンス・空調騒音で背景ノイズ床が跳ね上がり、発話の切り出し失敗や誤受理が多発する | ノイズ床を追従推定する適応型VAD＋指向性/近接マイクを採用し、第1候補がotherなら判定を待つ＆Top-3候補内にお題があれば救済する |
| 審査・デモ進行の継続性 | 認識が1回で通る前提で画面フローが組まれている | 通信遅延や騒音で認識が連続失敗した際、先の画面へ進めず実機のコア機能を見せられないまま制限時間が終わる | 音声・画像認識が失敗してもキー操作1つで次のステップへ進められるバイパス操作と、録音・送信失敗が体験を止めない非同期分離を入れる |

## 詳細解説・原因分析
### 会場のローカルネットワーク混雑がAIの「認識精度」まで悪化させる理由
技術展示会やコンテストの実機審査（マニュアル審査・デモ審査）で最も多くのチームが直面する悪夢が、「控え室や開発室では動いていたのに、本番会場のブースではネットワークが混雑してうまく動作せず、さらに音声認識の精度まで劇的に悪化した」というトラブルです。

なぜネットワークの混雑が音声認識の精度低下にまで直結するのでしょうか。理由は2つあります。1つ目は、エッジ端末（カメラやマイクを備えたラズパイ・マイコン等）から処理用PCへWi-Fi経由で音声や映像ストリームを飛ばしている場合、会場の電波干渉によるパケット欠落やジッター（遅延の揺らぎ）によって「音声フレームの一部が欠けた状態（またはチャンク境界がズレた状態）」でモデルへ入力され、子音や文字の判定が壊れるためです。2つ目は、起動時や判定ごとにクラウドAPIやHugging Face Hubへ通信する処理が挟まっていると、タイムアウト待ちでストリームバッファが溢れ、発話の頭切れが発生するためです。

これを防ぐ鉄則は、展示・審査モードでは外部ネットワークへのアクセスを完全に遮断する『ローカル限定モード』へ切り替え、事前に検証済みの軽量モデル（ONNX INT8等）を手元のストレージから直接ロードして固定することです。また、機器間の通信も2.4GHz帯のWi-FiやmDNS名前解決に頼らず、USBシリアル/OTG有線接続や有線LAN・固定IPで直結する構成が最も確実です。

主なチェックポイントは以下の通りです：起動時のネットワーク依存排除：`hf_hub_download` 等を使う場合も `local_files_only=True` 相当のローカル限定設定を用意し、会場で通信待ちロックを起こさない / ログとテレメトリの非ブロッキング化：利用データの保存やアップロード処理が失敗・タイムアウトしても、メインの認識ループやUI描画スレッドを絶対にブロックしない / スキーマ駆動の軽量通信：異種環境（C++マイコン〜Python推論器〜フロントエンド）を繋ぐ際は、曖昧なテキスト解析ではなく明確なスキーマ（Protobufや固定JSONスキーマ）とリングバッファで欠損を検知する。
参照: [Hugging Face Hub Documentation: Downloading files and offline mode (hf_hub_download)](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download)
参照: [ONNX Runtime Documentation: Quantize ONNX Models for Edge CPU Inference](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)

### 会場騒音で誤認識しても「体験を止めない」UIとTop-3救済設計
展示会場は想像以上に騒がしく、また審査員や来場者は開発者とは異なる声質・声量・話すタイミングを持っています。静かな部屋で80%の精度が出ていたモデルでも、会場のスピーカーフォン越しでは第1候補（Top-1）の一致率が大きく下がることが珍しくありません。

このとき「第1候補が完全一致しない限り次に進めない」という厳格すぎるUIを作ってしまうと、来場者が何度発声しても不正解になり、肝心のアプリケーション全体の流れ（出題から採点・フィードバックまでの一連の体験）を一度も見せられないまま審査時間が終了してしまいます。

実機デモを成功させるには、(1) 背景ノイズレベルを動的に推定するノイズ適応型VADで雑音区間を切り分け、(2) 第1候補が `other`（環境音・不明音）のときは即座に不正解にせず判定を待ち、(3) 上位3候補（Top-3）以内に出題文字が一定スコア以上で入っていれば正解として進行させる救済ロジックを入れ、(4) 万が一マイク認識が通らない環境でもスタッフのキー操作やボタン1つで即座にフォールバック進行できる設計にしておくことが不可欠です。

主なチェックポイントは以下の通りです：デモ審査の目的を意識する：スライド発表とは異なり、実機審査は『実機が止まらずに一連の体験として動くか』を確かめる場であるため、単一モジュールの通信エラーで全体が止まる構造を避ける / 機械の判定だけで利用者の誤りと断定しない：会場騒音による誤認識が起き得ることを踏まえ、UIや案内で再発声やスキップを自然に促せる導線を作る / 救済有無の正確な記録：Top-3救済を使って体験をスムーズに通した場合でも、内部ログには元のTop-1予測とスコアをそのまま残し、展示後のモデル改善（混同行列分析）に活用する。
参照: [Hugging Face Hub Documentation: Downloading files and offline mode (hf_hub_download)](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download)
参照: [ONNX Runtime Documentation: Quantize ONNX Models for Edge CPU Inference](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)

## 記事の範囲
2026年10月16日にHugging Face Hubのオフライン・キャッシュ取得仕様およびONNX Runtimeのローカル推論仕様を確認し、展示会場・フィールド環境におけるネットワーク遮断耐性と騒音耐性のアーキテクチャ設計を整理した記事です。


## 参考資料
- [Hugging Face Hub Documentation: Downloading files and offline mode (hf_hub_download)](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download)
- [ONNX Runtime Documentation: Quantize ONNX Models for Edge CPU Inference](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)

## 次に考えたいこと
- [実機データの継続学習で「出題ラベル＝正解ラベル」にしてはいけない理由：ユーザーの誤操作とモデル誤認識の分離設計](https://nodus-lab.pages.dev/articles/human-in-the-loop-labeling-prompt-vs-actual-input-guide)
- [学習データにノイズ・対象外（other）クラスを入れないと実機で何が起きるか：誤受理率と誤拒否率の設計](https://nodus-lab.pages.dev/articles/ml-noise-other-class-false-acceptance-evaluation-guide)
- [PyTorchで学習したモデルをONNX INT8量子化して実機へ載せるときに精度が落ちる原因：前処理不一致と段階的検証](https://nodus-lab.pages.dev/articles/edge-ai-pytorch-fp32-to-onnx-int8-preprocess-mismatch-guide)
